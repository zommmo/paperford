import asyncio
import hashlib
import json
import os
import re
import time

import streamlit as st

import config
from database import bulk_get, init_db, make_cache_key, set_many
from epub_processor import extract_blocks, inject_translations
from providers import BUILTIN_PROVIDERS
from settings_store import load_settings, save_settings
from translator import translate_batches


def normalize_base_url(url: str) -> str:
    """
    规范化 Base URL：去掉尾部多余的 /，并消除重复的 /v1，避免请求路径拼接成 /v1/v1/chat。
    """
    cleaned = (url or "").strip().rstrip("/")
    while cleaned.endswith("/v1/v1"):
        cleaned = cleaned[:-3].rstrip("/")
    return cleaned


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", name.strip().lower()).strip("-")
    return slug or "custom-provider"


def _load_initial_settings() -> dict:
    defaults = {
        "custom_providers": [],
        "selected_provider_id": "openai",
        "model": config.MODEL,
        "temperature": float(config.TEMPERATURE),
        "batch_size": int(config.BATCH_SIZE),
        "concurrency": int(config.CONCURRENCY),
        "max_blocks": 50,
    }
    loaded = load_settings()
    if not isinstance(loaded, dict):
        loaded = {}
    settings = defaults.copy()
    settings.update({k: loaded.get(k, v) for k, v in defaults.items()})
    if isinstance(loaded.get("custom_providers"), list):
        settings["custom_providers"] = loaded["custom_providers"]
    else:
        settings["custom_providers"] = []
    return settings


# 页面标题
st.title("EPUB 行间双语翻译器")

# 初始化缓存数据库
init_db(config.DB_PATH)

if "settings" not in st.session_state:
    st.session_state.settings = _load_initial_settings()
settings = st.session_state.settings

# 侧边栏配置区域
st.sidebar.header("配置")
api_key = st.sidebar.text_input("API Key", type="password")

custom_providers = settings.get("custom_providers", [])
all_providers = [dict(p) for p in BUILTIN_PROVIDERS] + [dict(p) for p in custom_providers]
provider_ids = [p["id"] for p in all_providers]
provider_labels = {p["id"]: p["name"] for p in all_providers}

if settings.get("selected_provider_id") not in provider_ids:
    settings["selected_provider_id"] = provider_ids[0] if provider_ids else "openai"
    save_settings(settings)

selected_provider_id = st.sidebar.selectbox(
    "Provider",
    options=provider_ids,
    index=provider_ids.index(settings["selected_provider_id"])
    if settings["selected_provider_id"] in provider_ids
    else 0,
    format_func=lambda pid: provider_labels.get(pid, pid),
)
if selected_provider_id != settings.get("selected_provider_id"):
    settings["selected_provider_id"] = selected_provider_id
    save_settings(settings)

selected_provider = next((p for p in all_providers if p["id"] == selected_provider_id), all_providers[0])
base_url_input = st.sidebar.text_input(
    "Base URL",
    value=normalize_base_url(selected_provider["base_url"]),
    key=f"base_url_{selected_provider_id}",
)
base_url = normalize_base_url(base_url_input)

model = st.sidebar.text_input("Model", value=str(settings.get("model", config.MODEL)))
temperature = st.sidebar.number_input(
    "temperature",
    min_value=0.0,
    max_value=2.0,
    value=float(settings.get("temperature", config.TEMPERATURE)),
    step=0.1,
)
batch_size = st.sidebar.number_input(
    "batch_size",
    min_value=1,
    value=int(settings.get("batch_size", config.BATCH_SIZE)),
    step=1,
)
concurrency = st.sidebar.number_input(
    "concurrency",
    min_value=1,
    value=int(settings.get("concurrency", config.CONCURRENCY)),
    step=1,
)

settings_changed = False
for key, val in [
    ("model", model),
    ("temperature", float(temperature)),
    ("batch_size", int(batch_size)),
    ("concurrency", int(concurrency)),
]:
    if settings.get(key) != val:
        settings[key] = val
        settings_changed = True

if settings_changed:
    save_settings(settings)

with st.sidebar.expander("新增/编辑/删除自定义 Provider"):
    custom_ids = [p["id"] for p in settings.get("custom_providers", [])]
    custom_selection = st.selectbox(
        "选择自定义 Provider",
        options=["__new__"] + custom_ids,
        format_func=lambda pid: "新建" if pid == "__new__" else next(
            (p["name"] for p in settings.get("custom_providers", []) if p["id"] == pid),
            pid,
        ),
    )
    selected_custom = (
        next((p for p in settings.get("custom_providers", []) if p["id"] == custom_selection), None)
        if custom_selection != "__new__"
        else None
    )
    custom_name = st.text_input(
        "名称",
        value=selected_custom["name"] if selected_custom else "",
        key=f"custom_name_{custom_selection}",
    )
    custom_base_url = st.text_input(
        "Base URL",
        value=normalize_base_url(selected_custom["base_url"]) if selected_custom else "",
        key=f"custom_base_{custom_selection}",
    )

    if st.button("保存/更新自定义 Provider"):
        normalized_custom_url = normalize_base_url(custom_base_url)
        if not custom_name.strip():
            st.warning("请填写名称。")
        elif not normalized_custom_url:
            st.warning("请填写 Base URL。")
        else:
            base_id = _slugify(custom_name)
            existing_ids = {p["id"] for p in settings.get("custom_providers", [])} | {
                p["id"] for p in BUILTIN_PROVIDERS
            }
            provider_id = custom_selection if custom_selection != "__new__" else base_id
            counter = 1
            while provider_id in existing_ids and provider_id != custom_selection:
                provider_id = f"{base_id}-{counter}"
                counter += 1

            new_provider = {
                "id": provider_id,
                "name": custom_name.strip(),
                "base_url": normalized_custom_url,
            }
            updated = []
            replaced = False
            for p in settings.get("custom_providers", []):
                if p["id"] == provider_id:
                    updated.append(new_provider)
                    replaced = True
                else:
                    updated.append(p)
            if not replaced:
                updated.append(new_provider)

            settings["custom_providers"] = updated
            settings["selected_provider_id"] = provider_id
            save_settings(settings)
            st.success("已保存自定义 Provider。")

    if custom_selection != "__new__" and st.button("删除自定义 Provider"):
        settings["custom_providers"] = [
            p for p in settings.get("custom_providers", []) if p["id"] != custom_selection
        ]
        if settings.get("selected_provider_id") == custom_selection:
            settings["selected_provider_id"] = "openai"
        save_settings(settings)
        st.success("已删除自定义 Provider。")

# 主区域说明
st.markdown(
    """
    这是一个用于 EPUB 行间双语翻译的 Streamlit 空壳页面。

    阶段进度：MVP-3
    """
)

uploaded_file = st.file_uploader("上传 EPUB 文件", type=["epub"])
if st.button("解析预览"):
    if not uploaded_file:
        st.warning("请先上传 EPUB 文件。")
    else:
        epub_bytes = uploaded_file.getvalue()
        blocks = extract_blocks(epub_bytes)
        st.success(f"解析完成，blocks 数量：{len(blocks)}")
        st.subheader("前 8 条预览")
        for block in blocks[:8]:
            preview = block["text"][:80]
            st.write(f"{block['block_id']} | {block['tag']} | {preview}")


st.subheader("缓存自检")
if st.button("缓存自检"):
    demo_text = "This is a cache smoke test."
    text_hash = hashlib.sha256(demo_text.encode("utf-8")).hexdigest()
    params_json = json.dumps(
        {
            "temperature": float(temperature),
            "batch_size": int(batch_size),
            "concurrency": int(concurrency),
        },
        sort_keys=True,
    )
    # 缓存键包含模型/提示版本/参数，防止不同配置的翻译结果混用
    cache_key = make_cache_key(text_hash, model, config.PROMPT_VERSION, params_json)
    now_ts = int(time.time())

    set_many(
        config.DB_PATH,
        [
            {
                "cache_key": cache_key,
                "text_hash": text_hash,
                "model": model,
                "prompt_version": config.PROMPT_VERSION,
                "params_json": params_json,
                "translation": "这是缓存写入示例",
                "created_at": now_ts,
            }
        ],
    )

    result = bulk_get(config.DB_PATH, [cache_key, "non-existent-key"])
    st.success("缓存写入并读取成功")
    st.json(result)


st.subheader("翻译 EPUB（MVP-4）")
max_blocks = st.number_input(
    "max_blocks（0 表示不限制）",
    min_value=0,
    value=int(settings.get("max_blocks", 50)),
    step=1,
)
if int(max_blocks) != settings.get("max_blocks"):
    settings["max_blocks"] = int(max_blocks)
    save_settings(settings)
if st.button("开始翻译（MVP-4）"):
    if not uploaded_file:
        st.warning("请先上传 EPUB 文件。")
    elif not api_key:
        st.warning("请先填写 API Key。")
    else:
        start_ts = time.time()
        epub_bytes = uploaded_file.getvalue()
        blocks = extract_blocks(epub_bytes)
        if max_blocks > 0:
            blocks = blocks[: int(max_blocks)]

        if not blocks:
            st.warning("未解析到可翻译的 blocks。")
        else:
            params = {"temperature": float(temperature)}
            # params_json 必须稳定序列化，否则同一参数顺序或空白不同会导致缓存键不一致、命中失效
            params_json = json.dumps(params, sort_keys=True, separators=(",", ":"))

            for block in blocks:
                # 缓存键必须包含 model/prompt_version/params_json，避免不同模型或提示参数共享同一缓存
                block["cache_key"] = make_cache_key(
                    block["text_hash"], model, config.PROMPT_VERSION, params_json
                )

            cache_hits = bulk_get(config.DB_PATH, [b["cache_key"] for b in blocks])
            results = {}
            missing_blocks = []
            cache_hit_count = 0
            for block in blocks:
                cached_translation = cache_hits.get(block["cache_key"])
                if cached_translation is not None:
                    results[block["block_id"]] = cached_translation
                    cache_hit_count += 1
                else:
                    missing_blocks.append(block)

            failures = []
            miss_count = len(missing_blocks)
            if missing_blocks:
                fresh_results, failures = asyncio.run(
                    translate_batches(
                        missing_blocks,
                        api_key=api_key,
                        base_url=base_url,
                        model=model,
                        temperature=float(temperature),
                        batch_size=int(batch_size),
                        concurrency=int(concurrency),
                    )
                )
                results.update(fresh_results)

                now_ts = int(time.time())
                rows = []
                for block in missing_blocks:
                    translation = fresh_results.get(block["block_id"])
                    if translation is None:
                        continue
                    rows.append(
                        {
                            "cache_key": block["cache_key"],
                            "text_hash": block["text_hash"],
                            "model": model,
                            "prompt_version": config.PROMPT_VERSION,
                            "params_json": params_json,
                            "translation": translation,
                            "created_at": now_ts,
                        }
                    )
                set_many(config.DB_PATH, rows)

            translated_count = sum(
                1 for block in blocks if results.get(block["block_id"]) is not None
            )
            placeholder_count = len(blocks) - translated_count

            # 回填译文时必须复用同一套定位规则（doc_name/tag/index），否则段落会错位
            output_bytes = inject_translations(epub_bytes, results)
            output_dir = "output"
            os.makedirs(output_dir, exist_ok=True)
            base_name, _ = os.path.splitext(uploaded_file.name)
            output_name = f"{base_name}_bilingual.epub"
            output_path = os.path.join(output_dir, output_name)
            with open(output_path, "wb") as f:
                f.write(output_bytes)

            elapsed = time.time() - start_ts
            st.success("翻译完成")
            st.write(f"本次处理 blocks 数：{len(blocks)}")
            st.write(f"缓存命中数：{cache_hit_count}")
            st.write(f"未命中数（请求翻译数）：{miss_count}")
            st.write(f"插入译文数量：{translated_count}")
            st.write(f"未翻译占位数量：{placeholder_count}")
            st.write(f"失败数：{len(failures)}")
            st.write(f"总耗时：{elapsed:.2f} 秒")

            st.download_button(
                "下载双语 EPUB",
                data=output_bytes,
                file_name=output_name,
                mime="application/epub+zip",
            )

            if failures:
                st.write("失败详情（block_id / 原文前 50 字 / 错误原因）：")
                st.table(
                    [
                        {
                            "block_id": f["id"],
                            "text_snippet": f.get("text_snippet", ""),
                            "reason": f.get("reason", ""),
                        }
                        for f in failures
                    ]
                )


st.subheader("翻译自测（MVP-3）")
if st.button("翻译自测（MVP-3）"):
    if not api_key:
        st.warning("请先填写 API Key。")
    else:
        # 构造三条示例段落，用固定 block_id 和 text_hash 便于验证
        demo_blocks = [
            {
                "block_id": "sample::p::0",
                "text": "This is the first sample paragraph for translation.",
            },
            {
                "block_id": "sample::p::1",
                "text": "Here is the second sentence to check batching behavior.",
            },
            {
                "block_id": "sample::p::2",
                "text": "Finally, this third piece ensures ordering is preserved.",
            },
        ]
        for blk in demo_blocks:
            blk["text_hash"] = hashlib.sha256(blk["text"].encode("utf-8")).hexdigest()

        # 结构化 JSON 输出让模型按 id 返回，可保证多段翻译不乱序
        results, failures = asyncio.run(
            translate_batches(
                demo_blocks,
                api_key=api_key,
                base_url=base_url,
                model=model,
                temperature=float(temperature),
                batch_size=int(batch_size),
                concurrency=int(concurrency),
            )
        )
        st.success("翻译完成")
        st.write("成功映射：")
        st.json(results)
        st.write("失败记录：")
        st.json(failures)
