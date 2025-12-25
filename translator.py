import asyncio
import json
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
                if resp.status_code in {429, 500, 502, 503, 504}:
                    raise TranslationError(f"server busy: {resp.status_code}")
                resp.raise_for_status()
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


def _chunk_list(items: List[dict], size: int) -> List[List[dict]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def translate_batches(
    blocks: List[dict],
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    batch_size: int,
    concurrency: int,
) -> Tuple[Dict[str, str], List[dict]]:
    """
    批量翻译：返回成功映射与失败列表。
    返回 mapping: id -> translation
    failures: {id, reason, text_snippet}
    """

    if not blocks:
        return {}, []

    headers = {"Authorization": f"Bearer {api_key}"}
    # 使用 semaphore 控制并发，避免过高并发触发限流
    semaphore = asyncio.Semaphore(concurrency)
    results: Dict[str, str] = {}
    failures: List[dict] = []

    async def handle_batch(batch: List[dict]):
        async with semaphore:
            user_payload = [{"id": b["block_id"], "text": b["text"]} for b in batch]
            messages = [
                {"role": "system", "content": config.SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ]
            payload = {
                "model": model,
                "temperature": float(temperature),
                "messages": messages,
                # 结构化 JSON 约束：让模型逐条按 id 输出，防止自由回答导致段落乱序
            }
            try:
                content = await _call_model(client, payload)
                parsed = json.loads(content)
                if not isinstance(parsed, list):
                    raise TranslationError("response is not a list")
                received_ids = set()
                for item in parsed:
                    if not isinstance(item, dict) or "id" not in item or "translation" not in item:
                        raise TranslationError("response item missing fields")
                    received_ids.add(item["id"])
                    results[item["id"]] = item["translation"]
                # 校验覆盖所有输入 id，避免漏翻
                input_ids = {b["block_id"] for b in batch}
                if received_ids != input_ids:
                    raise TranslationError("response ids mismatch input")
            except Exception as exc:  # 捕获重试终止后的异常，记录失败
                for b in batch:
                    failures.append(
                        {
                            "id": b["block_id"],
                            "reason": str(exc),
                            "text_snippet": b.get("text", "")[:50],
                        }
                    )

    batches = _chunk_list(blocks, batch_size)
    async with httpx.AsyncClient(base_url=base_url, headers=headers) as client:
        await asyncio.gather(*(handle_batch(batch) for batch in batches))

    return results, failures
