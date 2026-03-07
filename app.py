import asyncio
import hashlib
import json
import os
import re
import time

import streamlit as st

import config
from database import bulk_get, init_db, make_cache_key, make_prompt_hash, set_many
from epub_processor import extract_blocks, inject_translations
from provider_tools import fetch_models, health_check, normalize_base_url
from providers import BUILTIN_PROVIDERS
from settings_store import load_settings, save_settings
from translator import translate_batches
from i18n import get_i18n


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
        "custom_prompt": "",
        "language": "zh",
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


def _empty_job_state() -> dict:
    return {
        "status": "idle",
        "pending_blocks": [],
        "total_blocks": 0,
        "processed_blocks": 0,
        "hit_count": 0,
        "failures": [],
        "start_time": None,
        "last_update_time": None,
        "results_map": {},
        "epub_bytes": None,
        "output_name": None,
        "params_json": None,
        "model": None,
        "temperature": None,
        "batch_size": None,
        "concurrency": None,
        "base_url": None,
        "miss_count": 0,
        "output_bytes": None,
        "custom_prompt": "",
        "prompt_hash": "",
    }


# 初始化缓存数据库
init_db(config.DB_PATH)

if "settings" not in st.session_state:
    st.session_state.settings = _load_initial_settings()
settings = st.session_state.settings

# 页面标题
lang = settings.get("language", "zh")

st.title(get_i18n("app_title", lang))
st.markdown(
    """
    <style>
    /* 只隐藏 Deploy 按钮，保留 Settings 与侧边栏控制 */
    .stAppDeployButton { display: none !important; }
    [data-testid="stAppDeployButton"] { display: none !important; }
    </style>
    """,
    unsafe_allow_html=True,
)
if "models" not in st.session_state:
    st.session_state.models = None
if "models_base_url" not in st.session_state:
    st.session_state.models_base_url = None
if "health_check_result" not in st.session_state:
    st.session_state.health_check_result = None
if "job" not in st.session_state:
    st.session_state.job = _empty_job_state()
if "custom_prompt" not in st.session_state:
    st.session_state.custom_prompt = settings.get("custom_prompt", "")

# 侧边栏配置区域
st.sidebar.header(get_i18n("sidebar_config", lang))

# Language Selection
selected_lang = st.sidebar.selectbox(
    get_i18n("language_label", lang),
    ["zh", "en"],
    index=0 if settings.get("language", "zh") == "zh" else 1
)
if selected_lang != settings.get("language"):
    settings["language"] = selected_lang
    save_settings(settings)
    st.rerun()

api_key = st.sidebar.text_input(get_i18n("api_key", lang), type="password")

custom_providers = settings.get("custom_providers", [])
all_providers = [dict(p) for p in BUILTIN_PROVIDERS] + [dict(p) for p in custom_providers]
provider_ids = [p["id"] for p in all_providers]
provider_labels = {p["id"]: p["name"] for p in all_providers}

if settings.get("selected_provider_id") not in provider_ids:
    settings["selected_provider_id"] = provider_ids[0] if provider_ids else "openai"
    save_settings(settings)

selected_provider_id = st.sidebar.selectbox(
    get_i18n("provider_label", lang),
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
    get_i18n("base_url", lang),
    value=normalize_base_url(selected_provider["base_url"]),
    key=f"base_url_{selected_provider_id}",
)
base_url = normalize_base_url(base_url_input)

if st.session_state.models_base_url != base_url:
    st.session_state.models = None
    st.session_state.models_base_url = base_url
    st.session_state.pop("model_select", None)

if st.sidebar.button(get_i18n("fetch_models", lang)):
    if not api_key:
        st.sidebar.warning(get_i18n("warn_empty_api_key", lang))
    elif not base_url:
        st.sidebar.warning(get_i18n("warn_empty_base_url", lang))
    else:
        models, error = fetch_models(base_url, api_key)
        if models is None:
            st.sidebar.error(get_i18n("fetch_models_failed", lang).format(error))
        else:
            st.session_state.models = models
            st.session_state.models_base_url = base_url
            st.sidebar.success(get_i18n("fetch_models_success", lang).format(len(models)))

models = st.session_state.models or []
if models:
    if st.session_state.get("model_select") not in models:
        st.session_state.pop("model_select", None)
    default_model = str(settings.get("model", config.MODEL))
    model_index = models.index(default_model) if default_model in models else 0
    model = st.sidebar.selectbox(get_i18n("model_label", lang), options=models, index=model_index, key="model_select")
else:
    model = st.sidebar.text_input(
        get_i18n("model_label", lang), value=str(settings.get("model", config.MODEL)), key="model_input"
    )
with st.sidebar.expander(get_i18n("advanced_settings", lang)):
    custom_prompt = st.text_area(
        get_i18n("custom_prompt_label", lang),
        value=st.session_state.custom_prompt,
        help=get_i18n("custom_prompt_help", lang),
        key="custom_prompt",
    )
    prompt_hash = make_prompt_hash(custom_prompt)
    st.caption(f"{get_i18n('prompt_hash_label', lang)}: {prompt_hash[:8]}...")
    temperature = st.number_input(
        get_i18n("temperature_label", lang),
        min_value=0.0,
        max_value=2.0,
        value=float(settings.get("temperature", config.TEMPERATURE)),
        step=0.1,
    )
    batch_size = st.number_input(
        get_i18n("batch_size_label", lang),
        min_value=1,
        value=int(settings.get("batch_size", config.BATCH_SIZE)),
        step=1,
    )
    concurrency = st.number_input(
        get_i18n("concurrency_label", lang),
        min_value=1,
        value=int(settings.get("concurrency", config.CONCURRENCY)),
        step=1,
    )
    max_blocks = st.number_input(
        get_i18n("max_blocks_label", lang),
        min_value=0,
        value=int(settings.get("max_blocks", 50)),
        step=1,
    )
    if int(max_blocks) != settings.get("max_blocks"):
        settings["max_blocks"] = int(max_blocks)
        save_settings(settings)

if st.sidebar.button(get_i18n("test_connection", lang)):
    if not api_key:
        st.sidebar.warning(get_i18n("warn_empty_api_key", lang))
    elif not base_url:
        st.sidebar.warning(get_i18n("warn_empty_base_url", lang))
    elif not model:
        st.sidebar.warning(get_i18n("warn_empty_model", lang))
    else:
        st.session_state.health_check_result = health_check(base_url, api_key, model)

health_result = st.session_state.health_check_result
if health_result:
    if health_result.get("ok"):
        st.sidebar.success(get_i18n("connection_ok", lang))
    else:
        st.sidebar.error(get_i18n("connection_failed", lang))
    with st.sidebar.expander(get_i18n("connection_details", lang), expanded=True):
        st.json(health_result)

settings_changed = False
for key, val in [
    ("model", model),
    ("temperature", float(temperature)),
    ("batch_size", int(batch_size)),
    ("concurrency", int(concurrency)),
    ("custom_prompt", custom_prompt),
]:
    if settings.get(key) != val:
        settings[key] = val
        settings_changed = True

if settings_changed:
    save_settings(settings)

with st.sidebar.expander(get_i18n("custom_provider_mgr", lang)):
    custom_ids = [p["id"] for p in settings.get("custom_providers", [])]
    custom_selection = st.selectbox(
        get_i18n("select_custom_provider", lang),
        options=["__new__"] + custom_ids,
        format_func=lambda pid: get_i18n("new_provider", lang) if pid == "__new__" else next(
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
        get_i18n("name_label", lang),
        value=selected_custom["name"] if selected_custom else "",
        key=f"custom_name_{custom_selection}",
    )
    custom_base_url = st.text_input(
        get_i18n("base_url", lang),
        value=normalize_base_url(selected_custom["base_url"]) if selected_custom else "",
        key=f"custom_base_{custom_selection}",
    )

    if st.button(get_i18n("save_custom_provider", lang)):
        normalized_custom_url = normalize_base_url(custom_base_url)
        if not custom_name.strip():
            st.warning(get_i18n("warn_empty_name", lang))
        elif not normalized_custom_url:
            st.warning(get_i18n("warn_empty_base_url", lang))
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
            st.success(get_i18n("saved_custom_provider", lang))

    if custom_selection != "__new__" and st.button(get_i18n("delete_custom_provider", lang)):
        settings["custom_providers"] = [
            p for p in settings.get("custom_providers", []) if p["id"] != custom_selection
        ]
        if settings.get("selected_provider_id") == custom_selection:
            settings["selected_provider_id"] = "openai"
        save_settings(settings)
        st.success(get_i18n("deleted_custom_provider", lang))

# 主区域说明
st.caption(get_i18n("app_description", lang))

uploaded_file = st.file_uploader(get_i18n("upload_epub", lang), type=["epub"])
if st.button(get_i18n("parse_preview", lang)):
    if not uploaded_file:
        st.warning(get_i18n("warn_empty_epub", lang))
    else:
        epub_bytes = uploaded_file.getvalue()
        blocks = extract_blocks(epub_bytes)
        st.success(get_i18n("parse_success", lang).format(len(blocks)))
        st.subheader(get_i18n("preview_top_8", lang))
        for block in blocks[:8]:
            preview = block["text"][:80]
            st.write(f"{block['block_id']} | {block['tag']} | {preview}")


st.subheader(get_i18n("cache_smoke_test", lang))
if st.button(get_i18n("cache_smoke_test", lang)):
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
    prompt_hash = make_prompt_hash(custom_prompt)
    # 缓存键包含模型/提示版本/参数/风格提示 hash，防止不同风格串缓存
    cache_key = make_cache_key(
        text_hash, model, config.PROMPT_VERSION, params_json, prompt_hash
    )
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
    st.success(get_i18n("cache_test_success", lang))
    st.json(result)


st.subheader(get_i18n("translate_epub_title", lang))
job = st.session_state.job
col_start, col_pause, col_resume, col_stop = st.columns(4)
start_clicked = col_start.button(get_i18n("start_translation", lang), disabled=job["status"] == "running")
pause_clicked = col_pause.button(get_i18n("pause", lang), disabled=job["status"] != "running")
resume_clicked = col_resume.button(get_i18n("resume", lang), disabled=job["status"] != "paused")
stop_clicked = col_stop.button(get_i18n("stop_clear", lang), disabled=job["status"] == "idle")

if stop_clicked:
    st.session_state.job = _empty_job_state()
    job = st.session_state.job
    st.info(get_i18n("stopped_info", lang))

if start_clicked:
    if not uploaded_file:
        st.warning(get_i18n("warn_empty_epub", lang))
    elif not api_key:
        st.warning(get_i18n("warn_empty_api_key", lang))
    else:
        start_ts = time.time()
        epub_bytes = uploaded_file.getvalue()
        blocks = extract_blocks(epub_bytes)
        max_blocks_val = int(settings.get("max_blocks", 50))
        if max_blocks_val > 0:
            blocks = blocks[: max_blocks_val]

        if not blocks:
            st.warning(get_i18n("warn_no_blocks", lang))
        else:
            params = {"temperature": float(temperature)}
            # params_json 必须稳定序列化，否则同一参数顺序或空白不同会导致缓存键不一致、命中失效
            params_json = json.dumps(params, sort_keys=True, separators=(",", ":"))
            prompt_hash = make_prompt_hash(custom_prompt)

            for block in blocks:
                # 缓存键必须包含风格提示 hash，否则换风格会串缓存
                block["cache_key"] = make_cache_key(
                    block["text_hash"],
                    model,
                    config.PROMPT_VERSION,
                    params_json,
                    prompt_hash,
                )

            cache_hits = bulk_get(config.DB_PATH, [b["cache_key"] for b in blocks])
            results_map = {}
            pending_blocks = []
            cache_hit_count = 0
            for block in blocks:
                cached_translation = cache_hits.get(block["cache_key"])
                if cached_translation is not None:
                    results_map[block["block_id"]] = cached_translation
                    cache_hit_count += 1
                else:
                    pending_blocks.append(block)

            base_name, _ = os.path.splitext(uploaded_file.name)
            output_name = f"{base_name}_bilingual.epub"

            st.session_state.job = {
                "status": "running" if pending_blocks else "done",
                "pending_blocks": pending_blocks,
                "total_blocks": len(blocks),
                "processed_blocks": cache_hit_count,
                "hit_count": cache_hit_count,
                "failures": [],
                "start_time": start_ts,
                "last_update_time": start_ts,
                "results_map": results_map,
                "epub_bytes": epub_bytes,
                "output_name": output_name,
                "params_json": params_json,
                "model": model,
                "temperature": float(temperature),
                "batch_size": int(batch_size),
                "concurrency": int(concurrency),
                "base_url": base_url,
                "miss_count": len(pending_blocks),
                "output_bytes": None,
                "custom_prompt": custom_prompt,
                "prompt_hash": prompt_hash,
            }
            job = st.session_state.job

if pause_clicked and job["status"] == "running":
    job["status"] = "paused"
    st.info(get_i18n("pause_requested", lang))

if resume_clicked and job["status"] == "paused":
    job["status"] = "running"

if job["status"] != "idle":
    progress_bar = st.progress(0)
    progress_info = st.empty()

    def update_progress() -> None:
        total_count = job.get("total_blocks", 0)
        processed_count = job.get("processed_blocks", 0)
        percent = int(processed_count / total_count * 100) if total_count else 0
        progress_bar.progress(min(percent, 100))
        start_time = job.get("start_time") or time.time()
        elapsed = time.time() - start_time
        if processed_count > 0:
            remaining = elapsed / processed_count * (total_count - processed_count)
            remaining_text = f"{remaining:.2f} s"
        else:
            remaining_text = "—"
        cache_hit_count = job.get("hit_count", 0)
        miss_count = job.get("miss_count")
        if miss_count is None:
            miss_count = max(total_count - cache_hit_count, 0)
        success_count = len(job.get("results_map") or {})
        failure_count = len(job.get("failures") or [])
        
        with progress_info.container():
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(get_i18n("stats_total_blocks", lang), total_count)
            c2.metric(get_i18n("stats_processed_blocks", lang), processed_count)
            c3.metric(get_i18n("stats_cache_hits", lang), cache_hit_count)
            c4.metric(get_i18n("stats_misses", lang), miss_count)
            
            c5, c6, c7, c8 = st.columns(4)
            c5.metric(get_i18n("stats_translated", lang), success_count)
            c6.metric(get_i18n("stats_failures", lang), failure_count)
            c7.metric(get_i18n("stats_elapsed", lang), f"{elapsed:.2f}")
            c8.metric(get_i18n("stats_remaining_time", lang), remaining_text)

    update_progress()

if job["status"] == "running":
    if not job.get("pending_blocks"):
        job["status"] = "done"
    else:
        # Streamlit 无法中断正在运行的代码，因此每次 run 只处理 1 个 batch，处理完 st.rerun，
        # 用户就能在批次间隙点击暂停/继续，从而实现“可暂停”的体验。
        batch_size_val = int(
            job.get("batch_size") if job.get("batch_size") is not None else batch_size
        )
        temperature_val = (
            job.get("temperature") if job.get("temperature") is not None else temperature
        )
        concurrency_val = (
            job.get("concurrency") if job.get("concurrency") is not None else concurrency
        )
        model_val = job.get("model") if job.get("model") else model
        base_url_val = job.get("base_url") if job.get("base_url") else base_url
        batch = job["pending_blocks"][:batch_size_val]
        fresh_results, batch_failures = asyncio.run(
            translate_batches(
                batch,
                api_key=api_key,
                base_url=base_url_val,
                model=model_val,
                temperature=float(temperature_val),
                batch_size=batch_size_val,
                concurrency=int(concurrency_val),
                custom_prompt=job.get("custom_prompt") or "",
            )
        )
        job["results_map"].update(fresh_results)
        job["failures"].extend(batch_failures)

        now_ts = int(time.time())
        rows = []
        for block in batch:
            translation = fresh_results.get(block["block_id"])
            if translation is None:
                continue
            rows.append(
                {
                    "cache_key": block["cache_key"],
                    "text_hash": block["text_hash"],
                    "model": model_val,
                    "prompt_version": config.PROMPT_VERSION,
                    "params_json": job.get("params_json"),
                    "translation": translation,
                    "created_at": now_ts,
                }
            )
        set_many(config.DB_PATH, rows)

        job["processed_blocks"] += len(batch)
        job["last_update_time"] = time.time()
        job["pending_blocks"] = job["pending_blocks"][len(batch) :]

        update_progress()

        if job["pending_blocks"] and job["status"] == "running":
            st.rerun()

if job["status"] == "paused":
    st.info(get_i18n("paused_info", lang).format(len(job.get('pending_blocks', []))))

if job["status"] == "done":
    total_count = job.get("total_blocks", 0)
    cache_hit_count = job.get("hit_count", 0)
    miss_count = job.get("miss_count")
    if miss_count is None:
        miss_count = max(total_count - cache_hit_count, 0)
    translated_count = len(job.get("results_map") or {})
    placeholder_count = max(total_count - translated_count, 0)

    if job.get("output_bytes") is None and job.get("epub_bytes"):
        # 回填译文时必须复用同一套定位规则（doc_name/tag/index），否则段落会错位
        output_bytes = inject_translations(job["epub_bytes"], job.get("results_map") or {})
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)
        output_name = job.get("output_name") or "bilingual.epub"
        output_path = os.path.join(output_dir, output_name)
        with open(output_path, "wb") as f:
            f.write(output_bytes)
        job["output_bytes"] = output_bytes

    elapsed = time.time() - (job.get("start_time") or time.time())
    st.success(get_i18n("translation_completed", lang))
    
    c1, c2, c3 = st.columns(3)
    c1.metric(get_i18n("stats_final_total", lang), total_count)
    c2.metric(get_i18n("stats_cache_hits", lang), cache_hit_count)
    c3.metric(get_i18n("stats_misses", lang), miss_count)
    
    c4, c5, c6, c7 = st.columns(4)
    c4.metric(get_i18n("stats_final_inserted", lang), translated_count)
    c5.metric(get_i18n("stats_final_placeholders", lang), placeholder_count)
    c6.metric(get_i18n("stats_failures", lang), len(job.get('failures') or []))
    c7.metric(get_i18n("stats_elapsed", lang), f"{elapsed:.2f}")

    if job.get("output_bytes") is not None:
        st.download_button(
            get_i18n("download_bilingual_epub", lang),
            data=job["output_bytes"],
            file_name=job.get("output_name") or "bilingual.epub",
            mime="application/epub+zip",
        )

    if job.get("failures"):
        st.write(get_i18n("failure_details", lang))
        st.table(
            [
                {
                    get_i18n("col_block_id", lang): f["id"],
                    get_i18n("col_text_snippet", lang): f.get("text_snippet", ""),
                    get_i18n("col_reason", lang): f.get("reason", ""),
                }
                for f in job["failures"]
            ]
        )


st.subheader(get_i18n("translate_self_test", lang))
if st.button(get_i18n("translate_self_test", lang)):
    if not api_key:
        st.warning(get_i18n("warn_empty_api_key", lang))
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
                custom_prompt=custom_prompt,
            )
        )
        st.success(get_i18n("translation_completed", lang))
        st.write(get_i18n("success_mapping", lang))
        st.json(results)
        st.write(get_i18n("failure_records", lang))
        st.json(failures)
