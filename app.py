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
from provider_tools import fetch_models, health_check, normalize_base_url
from providers import BUILTIN_PROVIDERS
from settings_store import load_settings, save_settings
from translator import translate_batches


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
    }


# 页面标题
st.title("EPUB 行间双语翻译器")

# 初始化缓存数据库
init_db(config.DB_PATH)

if "settings" not in st.session_state:
    st.session_state.settings = _load_initial_settings()
settings = st.session_state.settings
if "models" not in st.session_state:
    st.session_state.models = None
if "models_base_url" not in st.session_state:
    st.session_state.models_base_url = None
if "health_check_result" not in st.session_state:
    st.session_state.health_check_result = None
if "job" not in st.session_state:
    st.session_state.job = _empty_job_state()

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

if st.session_state.models_base_url != base_url:
    st.session_state.models = None
    st.session_state.models_base_url = base_url
    st.session_state.pop("model_select", None)

if st.sidebar.button("获取模型列表"):
    if not api_key:
        st.sidebar.warning("请先填写 API Key。")
    elif not base_url:
        st.sidebar.warning("请先填写 Base URL。")
    else:
        models, error = fetch_models(base_url, api_key)
        if models is None:
            st.sidebar.error(f"获取失败：{error}")
        else:
            st.session_state.models = models
            st.session_state.models_base_url = base_url
            st.sidebar.success(f"获取成功，共 {len(models)} 个模型。")

models = st.session_state.models or []
if models:
    if st.session_state.get("model_select") not in models:
        st.session_state.pop("model_select", None)
    default_model = str(settings.get("model", config.MODEL))
    model_index = models.index(default_model) if default_model in models else 0
    model = st.sidebar.selectbox("Model", options=models, index=model_index, key="model_select")
else:
    model = st.sidebar.text_input(
        "Model", value=str(settings.get("model", config.MODEL)), key="model_input"
    )
temperature = st.sidebar.number_input(
    "temperature（随机性）",
    min_value=0.0,
    max_value=2.0,
    value=float(settings.get("temperature", config.TEMPERATURE)),
    step=0.1,
)
batch_size = st.sidebar.number_input(
    "batch_size（每批条数）",
    min_value=1,
    value=int(settings.get("batch_size", config.BATCH_SIZE)),
    step=1,
)
concurrency = st.sidebar.number_input(
    "concurrency（并发数）",
    min_value=1,
    value=int(settings.get("concurrency", config.CONCURRENCY)),
    step=1,
)

if st.sidebar.button("测试连接"):
    if not api_key:
        st.sidebar.warning("请先填写 API Key。")
    elif not base_url:
        st.sidebar.warning("请先填写 Base URL。")
    elif not model:
        st.sidebar.warning("请先填写 Model。")
    else:
        st.session_state.health_check_result = health_check(base_url, api_key, model)

health_result = st.session_state.health_check_result
if health_result:
    if health_result.get("ok"):
        st.sidebar.success("连接正常")
    else:
        st.sidebar.error("连接失败")
    with st.sidebar.expander("连接详情", expanded=True):
        st.json(health_result)

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

with st.sidebar.expander("自定义 Provider 管理"):
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
st.caption("上传 EPUB → 翻译并回填 → 导出双语 EPUB")

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


st.subheader("翻译 EPUB")
max_blocks = st.number_input(
    "max_blocks（0 表示不限制）",
    min_value=0,
    value=int(settings.get("max_blocks", 50)),
    step=1,
)
if int(max_blocks) != settings.get("max_blocks"):
    settings["max_blocks"] = int(max_blocks)
    save_settings(settings)
job = st.session_state.job
col_start, col_pause, col_resume, col_stop = st.columns(4)
start_clicked = col_start.button("开始翻译", disabled=job["status"] == "running")
pause_clicked = col_pause.button("暂停", disabled=job["status"] != "running")
resume_clicked = col_resume.button("继续", disabled=job["status"] != "paused")
stop_clicked = col_stop.button("停止并清空", disabled=job["status"] == "idle")

if stop_clicked:
    st.session_state.job = _empty_job_state()
    job = st.session_state.job
    st.info("已停止并清空任务（不会删除缓存）。")

if start_clicked:
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
            }
            job = st.session_state.job

if pause_clicked and job["status"] == "running":
    job["status"] = "paused"
    st.info("已请求暂停，将在当前批次结束后生效。")

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
            remaining_text = f"{remaining:.2f} 秒"
        else:
            remaining_text = "—"
        cache_hit_count = job.get("hit_count", 0)
        miss_count = job.get("miss_count")
        if miss_count is None:
            miss_count = max(total_count - cache_hit_count, 0)
        success_count = len(job.get("results_map") or {})
        failure_count = len(job.get("failures") or [])
        progress_info.markdown(
            "\n".join(
                [
                    f"- 总 blocks：{total_count}",
                    f"- 已处理 blocks：{processed_count}",
                    f"- 缓存命中数：{cache_hit_count}",
                    f"- 请求翻译数：{miss_count}",
                    f"- 已完成翻译数：{success_count}",
                    f"- 失败数：{failure_count}",
                    f"- 已耗时：{elapsed:.2f} 秒",
                    f"- 预计剩余时间：{remaining_text}",
                ]
            )
        )

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
    st.info(f"已暂停，还剩 {len(job.get('pending_blocks', []))} 段未翻译。")

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
    st.success("翻译完成")
    st.write(f"本次处理 blocks 数：{total_count}")
    st.write(f"缓存命中数：{cache_hit_count}")
    st.write(f"未命中数（请求翻译数）：{miss_count}")
    st.write(f"插入译文数量：{translated_count}")
    st.write(f"未翻译占位数量：{placeholder_count}")
    st.write(f"失败数：{len(job.get('failures') or [])}")
    st.write(f"总耗时：{elapsed:.2f} 秒")

    if job.get("output_bytes") is not None:
        st.download_button(
            "下载双语 EPUB",
            data=job["output_bytes"],
            file_name=job.get("output_name") or "bilingual.epub",
            mime="application/epub+zip",
        )

    if job.get("failures"):
        st.write("失败详情（block_id / 原文前 50 字 / 错误原因）：")
        st.table(
            [
                {
                    "block_id": f["id"],
                    "text_snippet": f.get("text_snippet", ""),
                    "reason": f.get("reason", ""),
                }
                for f in job["failures"]
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
