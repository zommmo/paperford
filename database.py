import hashlib
import sqlite3
from contextlib import closing
from typing import Dict, List


def init_db(db_path: str) -> None:
    # 建表：用于缓存翻译结果，避免重复请求
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS translations (
                    cache_key TEXT PRIMARY KEY,
                    text_hash TEXT,
                    model TEXT,
                    prompt_version TEXT,
                    params_json TEXT,
                    translation TEXT,
                    created_at INTEGER
                )
                """
            )


def make_prompt_hash(custom_prompt: str, glossary: str = "") -> str:
    # 无论是否为空都返回固定 hash，保证缓存键稳定可复现
    normalized = f"{custom_prompt or ''}|{glossary or ''}".strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def make_cache_key(
    text_hash: str, model: str, prompt_version: str, params_json: str, prompt_hash: str
) -> str:
    # 缓存键包含模型/提示版本/参数/风格提示 hash，避免不同翻译配置或风格串缓存
    payload = "|".join([text_hash, model, prompt_version, params_json, prompt_hash])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def bulk_get(db_path: str, cache_keys: List[str]) -> Dict[str, str]:
    if not cache_keys:
        return {}
    placeholders = ",".join(["?"] * len(cache_keys))
    sql = f"SELECT cache_key, translation FROM translations WHERE cache_key IN ({placeholders})"
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.execute(sql, cache_keys)
        return {row[0]: row[1] for row in cursor.fetchall()}


def set_many(db_path: str, rows: List[Dict]) -> None:
    if not rows:
        return
    values = [
        (
            row["cache_key"],
            row["text_hash"],
            row["model"],
            row["prompt_version"],
            row["params_json"],
            row["translation"],
            row["created_at"],
        )
        for row in rows
    ]
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.executemany(
                """
                INSERT OR REPLACE INTO translations (
                    cache_key, text_hash, model, prompt_version, params_json, translation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )


def clear_cache(db_path: str) -> int:
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            cursor = conn.execute("DELETE FROM translations")
            return cursor.rowcount
