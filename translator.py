import asyncio
import json
import re
from typing import Dict, List, Tuple

import httpx
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt, wait_exponential_jitter

import config


class TranslationError(Exception):
    """自定义异常用于触发重试"""


async def _call_model(client: httpx.AsyncClient, payload: dict) -> str:
    # 结构化 JSON 响应能保证段落不乱序，可精确按 id 对齐
    async for attempt in AsyncRetrying(
        retry=retry_if_exception_type(TranslationError),
        wait=wait_exponential_jitter(initial=1, max=10),
        stop=stop_after_attempt(config.MAX_RETRIES),
    ):
        with attempt:
            try:
                resp = await client.post(
                    "/chat/completions",
                    json=payload,
                    timeout=config.DEFAULT_TIMEOUT,
                )
                if resp.status_code != 200:
                    body_snippet = resp.text[:200]
                    if resp.status_code in {429, 500, 502, 503, 504}:
                        raise TranslationError(
                            f"server busy: {resp.status_code}; body_snippet={body_snippet}"
                        )
                    raise TranslationError(
                        f"bad status: {resp.status_code}; body_snippet={body_snippet}"
                    )
                try:
                    data = resp.json()
                except Exception as exc:
                    raise TranslationError(f"json decode failed: {exc}")

                try:
                    return data["choices"][0]["message"]["content"]
                except Exception as exc:
                    raise TranslationError(f"parse response failed: {exc}")
            except httpx.HTTPError as exc:
                raise TranslationError(f"http error: {exc}")
            except TranslationError:
                raise
            except Exception as exc:
                raise TranslationError(f"unexpected error: {exc}")
    raise TranslationError("exceeded retries")


def extract_json_array(text: str) -> list:
    # 模型偶尔会输出 Markdown 包装或夹带说明，先容错提取 JSON 避免解析失败
    raw_text = text
    cleaned = text.strip()
    if "```" in cleaned:
        lines = []
        for line in cleaned.splitlines():
            if line.strip().startswith("```"):
                continue
            lines.append(line)
        cleaned = "\n".join(lines).strip()

    start = cleaned.find("[")
    end = cleaned.rfind("]")
    candidate = cleaned
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start : end + 1]

    try:
        parsed = json.loads(candidate)
    except Exception as exc:
        snippet = raw_text[:200]
        raise TranslationError(
            f"response json parse failed: {exc}; 原始返回片段前 200 字符: {snippet}"
        )

    if not isinstance(parsed, list):
        raise TranslationError("response is not a list")
    return parsed


def _chunk_list(items: List[dict], size: int) -> List[List[dict]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def estimate_token_count(text: str, model: str = "") -> int:
    try:
        import tiktoken

        try:
            encoding = tiktoken.encoding_for_model(model)
        except Exception:
            encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text or ""))
    except Exception:
        return max(1, len(text or "") // 4)


def _split_piece_by_estimate(piece: str, max_tokens: int, model: str) -> List[str]:
    pending = piece.strip()
    chunks = []
    while pending and estimate_token_count(pending, model) > max_tokens:
        low = 1
        high = len(pending)
        best = 1
        while low <= high:
            mid = (low + high) // 2
            if estimate_token_count(pending[:mid], model) <= max_tokens:
                best = mid
                low = mid + 1
            else:
                high = mid - 1

        boundary = best
        prefix = pending[:best]
        matches = list(re.finditer(r"[\s,.;:!?，。；：！？、]", prefix))
        if matches and matches[-1].end() >= max(1, best // 2):
            boundary = matches[-1].end()

        chunk = pending[:boundary].strip()
        if not chunk:
            chunk = pending[:best].strip() or pending[:1]
            boundary = len(chunk)
        chunks.append(chunk)
        pending = pending[boundary:].strip()

    if pending:
        chunks.append(pending)
    return chunks


def split_text_for_translation(
    text: str,
    max_tokens: int = config.MAX_BLOCK_TOKENS,
    model: str = "",
) -> List[str]:
    normalized = (text or "").strip()
    if not normalized:
        return [""]
    if max_tokens <= 0 or estimate_token_count(normalized, model) <= max_tokens:
        return [normalized]

    sentences = [
        item.strip()
        for item in re.split(r"(?<=[.!?。！？；;])\s+|\n+", normalized)
        if item.strip()
    ] or [normalized]

    chunks = []
    current = ""
    for sentence in sentences:
        if estimate_token_count(sentence, model) > max_tokens:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(_split_piece_by_estimate(sentence, max_tokens, model))
            continue

        candidate = f"{current} {sentence}".strip()
        if current and estimate_token_count(candidate, model) > max_tokens:
            chunks.append(current)
            current = sentence
        else:
            current = candidate

    if current:
        chunks.append(current)
    return chunks


def _build_translation_units(blocks: List[dict], model: str) -> tuple[List[dict], Dict[str, List[dict]]]:
    units = []
    units_by_parent: Dict[str, List[dict]] = {}
    for block in blocks:
        parent_id = block["block_id"]
        chunks = split_text_for_translation(block.get("text", ""), config.MAX_BLOCK_TOKENS, model)
        units_by_parent[parent_id] = []
        for index, chunk in enumerate(chunks):
            unit = dict(block)
            unit["parent_block_id"] = parent_id
            unit["chunk_index"] = index
            unit["chunk_count"] = len(chunks)
            unit["text"] = chunk
            if len(chunks) > 1:
                unit["block_id"] = f"{parent_id}::part::{index}"
            units.append(unit)
            units_by_parent[parent_id].append(unit)
    return units, units_by_parent


async def translate_batches(
    blocks: List[dict],
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    batch_size: int,
    concurrency: int,
    custom_prompt: str = "",
    target_language: str = config.DEFAULT_TARGET_LANGUAGE,
    glossary: str = "",
    context: list[dict] | None = None,
) -> Tuple[Dict[str, str], List[dict]]:
    """
    批量翻译：返回成功映射与失败列表。
    返回 mapping: id -> translation
    failures: {id, reason, text_snippet}
    custom_prompt: 仅作为风格说明，系统提示保持固定以保证 JSON 解析稳定。
    target_language: 目标语言名称，例如 Chinese、English、Japanese。
    """

    if not blocks:
        return {}, []

    headers = {"Authorization": f"Bearer {api_key}"}
    # 使用 semaphore 控制并发，避免过高并发触发限流
    semaphore = asyncio.Semaphore(concurrency)
    units, units_by_parent = _build_translation_units(blocks, model)
    unit_results: Dict[str, str] = {}
    unit_failures: List[dict] = []

    async def handle_batch(batch: List[dict]):
        async with semaphore:
            user_payload = [{"id": b["block_id"], "text": b["text"]} for b in batch]
            # 系统提示必须固定，用户提示只做风格说明，避免 JSON 约束被覆盖导致解析崩溃
            user_content_prefix = ""
            glossary_prompt = (glossary or "").strip()
            if glossary_prompt:
                user_content_prefix += f"参考全局术语表，严格遵循以下译名翻译：\n{glossary_prompt}\n\n"
            style_prompt = (custom_prompt or "").strip()
            if style_prompt:
                user_content_prefix += f"翻译风格要求：{style_prompt}\n\n"
            if context:
                user_content_prefix += "以下是上文参考语境（仅供消歧和语气参考，请勿翻译这部分）：\n"
                for ctx in context:
                    user_content_prefix += f"原文：{ctx['original']}\n译文：{ctx['translation']}\n"
                user_content_prefix += "\n请翻译以下内容：\n"
            messages = [
                {"role": "system", "content": config.build_system_prompt(target_language)},
                {
                    "role": "user",
                    "content": (
                        f"{user_content_prefix}待翻译内容(JSON)："
                        f"{json.dumps(user_payload, ensure_ascii=False)}"
                    ),
                },
            ]
            payload = {
                "model": model,
                "temperature": float(temperature),
                "messages": messages,
                # 结构化 JSON 约束：让模型逐条按 id 输出，防止自由回答导致段落乱序
            }
            try:
                content = await _call_model(client, payload)
                parsed = extract_json_array(content)
                received_ids = set()
                for item in parsed:
                    if not isinstance(item, dict) or "id" not in item or "translation" not in item:
                        raise TranslationError("response item missing fields")
                    received_ids.add(item["id"])
                    unit_results[item["id"]] = item["translation"]
                # 校验覆盖所有输入 id，避免漏翻
                input_ids = {b["block_id"] for b in batch}
                if received_ids != input_ids:
                    raise TranslationError("response ids mismatch input")
            except Exception as exc:  # 捕获重试终止后的异常，记录失败
                for b in batch:
                    unit_failures.append(
                        {
                            "id": b["block_id"],
                            "reason": str(exc),
                            "text_snippet": b.get("text", "")[:50],
                        }
                    )

    batches = _chunk_list(units, batch_size)
    async with httpx.AsyncClient(base_url=base_url, headers=headers) as client:
        await asyncio.gather(*(handle_batch(batch) for batch in batches))

    failures_by_unit = {failure["id"]: failure for failure in unit_failures}
    results: Dict[str, str] = {}
    failures: List[dict] = []
    for block in blocks:
        parent_id = block["block_id"]
        parent_units = units_by_parent.get(parent_id, [])
        unit_ids = [unit["block_id"] for unit in parent_units]
        failed = [failures_by_unit[unit_id] for unit_id in unit_ids if unit_id in failures_by_unit]
        missing = [unit_id for unit_id in unit_ids if unit_id not in unit_results and unit_id not in failures_by_unit]
        if failed or missing:
            reasons = [failure.get("reason", "") for failure in failed]
            if missing:
                reasons.append(f"missing translated chunks: {len(missing)}")
            failures.append(
                {
                    "id": parent_id,
                    "reason": "; ".join(reason for reason in reasons if reason),
                    "text_snippet": block.get("text", "")[:50],
                }
            )
            continue
        results[parent_id] = "\n".join(unit_results[unit_id] for unit_id in unit_ids)

    return results, failures
