import asyncio
import json
import time
from typing import List, Optional, Tuple

import httpx

import config
from translator import TranslationError, _call_model, extract_json_array


def normalize_base_url(base_url: str) -> str:
    """
    规范化 Base URL：去掉尾部多余的 /，并消除重复的 /v1，避免请求路径拼接成 /v1/v1/chat。
    保持最小改动，兼容类似 /v1beta/openai/ 的路径。
    """
    cleaned = (base_url or "").strip()
    if not cleaned:
        return ""
    cleaned = cleaned.rstrip("/")
    while cleaned.endswith("/v1/v1"):
        cleaned = cleaned[:-3]
    return cleaned


def fetch_models(
    base_url: str, api_key: str, timeout: int = 20
) -> Tuple[Optional[List[str]], Optional[str]]:
    normalized = normalize_base_url(base_url)
    if not normalized:
        return None, "status_code=0; body_snippet=base_url 为空"

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    url = f"{normalized}/models"
    try:
        resp = httpx.get(url, headers=headers, timeout=timeout)
    except httpx.HTTPError as exc:
        return None, f"status_code=0; body_snippet=http error: {exc}"

    status_code = resp.status_code
    if status_code != 200:
        return None, f"status_code={status_code}; body_snippet={resp.text[:200]}"

    try:
        data = resp.json()
    except Exception as exc:
        return (
            None,
            f"status_code={status_code}; body_snippet=json decode failed: {exc}; {resp.text[:200]}",
        )

    items = None
    if isinstance(data, dict):
        if isinstance(data.get("data"), list):
            items = data["data"]
        elif isinstance(data.get("models"), list):
            items = data["models"]
        elif isinstance(data.get("result"), list):
            items = data["result"]
    elif isinstance(data, list):
        items = data

    if items is None:
        return None, f"status_code={status_code}; body_snippet={resp.text[:200]}"

    models: List[str] = []
    for item in items:
        if isinstance(item, dict):
            if "id" in item:
                models.append(str(item["id"]))
            elif "model" in item:
                models.append(str(item["model"]))
            elif "name" in item:
                models.append(str(item["name"]))
        elif isinstance(item, str):
            models.append(item)

    models = [m for m in models if m]
    if not models:
        return None, f"status_code={status_code}; body_snippet={resp.text[:200]}"

    return models, None


async def _infer_once(base_url: str, api_key: str, model: str) -> None:
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    user_payload = [{"id": "healthcheck", "text": "Hello"}]
    messages = [
        {"role": "system", "content": config.SYSTEM_PROMPT},
        {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
    ]
    payload = {
        "model": model,
        "temperature": 0,
        "messages": messages,
    }
    async with httpx.AsyncClient(base_url=base_url, headers=headers) as client:
        content = await _call_model(client, payload)
    parsed = extract_json_array(content)
    if not parsed:
        raise TranslationError(f"response empty; body_snippet={content[:200]}")
    item = parsed[0]
    if not isinstance(item, dict) or item.get("id") != "healthcheck" or "translation" not in item:
        raise TranslationError(f"response mismatch; body_snippet={content[:200]}")


def health_check(base_url: str, api_key: str, model: str) -> dict:
    start_ts = time.time()
    normalized = normalize_base_url(base_url)
    result = {
        "ok": False,
        "models_ok": False,
        "infer_ok": False,
        "elapsed": 0.0,
        "error": None,
    }

    models_error = None
    models, models_err = fetch_models(normalized, api_key)
    if models is not None:
        result["models_ok"] = True
    else:
        models_error = models_err

    infer_error = None
    if normalized and model:
        try:
            asyncio.run(_infer_once(normalized, api_key, model))
            result["infer_ok"] = True
        except Exception as exc:
            infer_error = str(exc)
    else:
        infer_error = "base_url 或 model 为空"

    result["ok"] = result["infer_ok"]
    errors = []
    if models_error:
        errors.append(f"models: {models_error}")
    if infer_error:
        errors.append(f"infer: {infer_error}")
    result["error"] = "; ".join(errors) if errors else None

    result["elapsed"] = time.time() - start_ts
    return result
