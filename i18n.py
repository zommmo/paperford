I18N = {
    "app_title": {
        "zh": "📚 EPUB 行间双语翻译器",
        "en": "📚 EPUB Bilingual Contextual Translator"
    },
    "app_description": {
        "zh": "上传 EPUB → 翻译并回填 → 导出双语 EPUB",
        "en": "Upload EPUB → Translate & Inject → Export Bilingual EPUB"
    },
    "language_label": {
        "zh": "界面语言",
        "en": "Language"
    },
    "sidebar_config": {
        "zh": "⚙️ 配置",
        "en": "⚙️ Configuration"
    },
    "api_key": {
        "zh": "API 密钥",
        "en": "API Key"
    },
    "warn_empty_api_key": {
        "zh": "请先填写 API 密钥。",
        "en": "Please provide an API Key first."
    },
    "base_url": {
        "zh": "接口地址（Base URL）",
        "en": "Base URL"
    },
    "warn_empty_base_url": {
        "zh": "请先填写接口地址（Base URL）。",
        "en": "Please provide a Base URL first."
    },
    "fetch_models": {
        "zh": "获取模型列表",
        "en": "Fetch Models"
    },
    "fetch_models_failed": {
        "zh": "获取失败：{}",
        "en": "Failed to fetch: {}"
    },
    "fetch_models_success": {
        "zh": "获取成功，共 {} 个模型。",
        "en": "Successfully fetched {} models."
    },
    "advanced_settings": {
        "zh": "🛠️ 高级设置",
        "en": "🛠️ Advanced Settings"
    },
    "custom_prompt_label": {
        "zh": "自定义翻译风格提示词（可选）",
        "en": "Custom Translation Prompt (Optional)"
    },
    "custom_prompt_help": {
        "zh": "只影响翻译风格，不要写 JSON 格式要求；留空则使用默认风格",
        "en": "Restricts only translation style, DO NOT include JSON formatting rules; leave blank for default style."
    },
    "target_language_label": {
        "zh": "目标语言",
        "en": "Target Language"
    },
    "target_language_help": {
        "zh": "译文输出语言；会参与缓存 key，切换语言不会复用旧语言缓存。",
        "en": "Translation output language. It is included in the cache key, so different languages use separate caches."
    },
    "custom_target_language_label": {
        "zh": "自定义目标语言",
        "en": "Custom Target Language"
    },
    "custom_target_language_placeholder": {
        "zh": "例如：繁体中文、Italian、Portuguese",
        "en": "For example: Traditional Chinese, Italian, Portuguese"
    },
    "custom_target_language_help": {
        "zh": "会原样写入翻译提示词和缓存 key；建议使用模型能理解的语言名称。",
        "en": "Saved as-is in the translation prompt and cache key; use a language name the model can understand."
    },
    "temperature_label": {
        "zh": "温度（随机性）",
        "en": "Temperature (Randomness)"
    },
    "batch_size_label": {
        "zh": "批大小（每批条数）",
        "en": "Batch Size"
    },
    "concurrency_label": {
        "zh": "并发数",
        "en": "Concurrency"
    },
    "max_blocks_label": {
        "zh": "最大文本块数（0 表示不限制）",
        "en": "Max Blocks (0 for unlimited)"
    },
    "max_blocks_limited_warning": {
        "zh": "当前只会翻译前 {} 个文本块。要翻译整本书，请把这里改成 0。",
        "en": "Only the first {} text blocks will be translated. Set this to 0 to translate the full book."
    },
    "test_connection": {
        "zh": "测试连接",
        "en": "Test Connection"
    },
    "warn_empty_model": {
        "zh": "请先填写模型名称。",
        "en": "Please provide a Model first."
    },
    "connection_ok": {
        "zh": "✅ 连接正常",
        "en": "✅ Connection OK"
    },
    "connection_failed": {
        "zh": "❌ 连接失败",
        "en": "❌ Connection Failed"
    },
    "connection_details": {
        "zh": "连接详情",
        "en": "Connection Details"
    },
    "custom_provider_mgr": {
        "zh": "自定义服务商管理",
        "en": "Custom Provider Manager"
    },
    "select_custom_provider": {
        "zh": "选择自定义服务商",
        "en": "Select Custom Provider"
    },
    "new_provider": {
        "zh": "新建",
        "en": "New"
    },
    "name_label": {
        "zh": "名称",
        "en": "Name"
    },
    "save_custom_provider": {
        "zh": "保存/更新自定义服务商",
        "en": "Save/Update Custom Provider"
    },
    "warn_empty_name": {
        "zh": "请填写名称。",
        "en": "Please provide a name."
    },
    "saved_custom_provider": {
        "zh": "已保存自定义服务商。",
        "en": "Custom Provider saved successfully."
    },
    "delete_custom_provider": {
        "zh": "删除自定义服务商",
        "en": "Delete Custom Provider"
    },
    "deleted_custom_provider": {
        "zh": "已删除自定义服务商。",
        "en": "Custom Provider deleted."
    },
    "upload_epub": {
        "zh": "上传 EPUB 文件",
        "en": "Upload EPUB file"
    },
    "parse_preview": {
        "zh": "解析预览",
        "en": "Parse & Preview"
    },
    "warn_empty_epub": {
        "zh": "请先上传 EPUB 文件。",
        "en": "Please upload an EPUB file first."
    },
    "parse_success": {
        "zh": "✅ 解析完成，文本块数量：{}",
        "en": "✅ Parsing complete, blocks count: {}"
    },
    "preview_top_8": {
        "zh": "前 8 条预览",
        "en": "Top 8 Blocks Preview"
    },
    "cache_smoke_test": {
        "zh": "缓存自检",
        "en": "Cache Smoke Test"
    },
    "cache_test_success": {
        "zh": "✅ 缓存写入并读取成功",
        "en": "✅ Cache Write and Read successful"
    },
    "translate_epub_title": {
        "zh": "🚀 翻译 EPUB",
        "en": "🚀 Translate EPUB"
    },
    "start_translation": {
        "zh": "▶️ 开始翻译",
        "en": "▶️ Start Translation"
    },
    "pause": {
        "zh": "⏸️ 暂停",
        "en": "⏸️ Pause"
    },
    "resume": {
        "zh": "⏯️ 继续",
        "en": "⏯️ Resume"
    },
    "stop_clear": {
        "zh": "⏹️ 停止并清空",
        "en": "⏹️ Stop & Clear"
    },
    "stopped_info": {
        "zh": "已停止并清空任务（不会删除缓存）。",
        "en": "Job stopped and cleared (caches are preserved)."
    },
    "warn_no_blocks": {
        "zh": "未解析到可翻译的文本块。",
        "en": "No translatable blocks parsed."
    },
    "pause_requested": {
        "zh": "已请求暂停，将在当前批次结束后生效。",
        "en": "Pause requested. It will take effect after current batch finishes."
    },
    "stats_total_blocks": {
        "zh": "总文本块",
        "en": "Total Blocks"
    },
    "stats_processed_blocks": {
        "zh": "已处理文本块",
        "en": "Processed Blocks"
    },
    "stats_cache_hits": {
        "zh": "缓存命中数",
        "en": "Cache Hits"
    },
    "stats_misses": {
        "zh": "请求翻译数",
        "en": "API Requests"
    },
    "stats_translated": {
        "zh": "已完成翻译数",
        "en": "Translated Count"
    },
    "stats_failures": {
        "zh": "失败数",
        "en": "Failures"
    },
    "stats_elapsed": {
        "zh": "已耗时 (秒)",
        "en": "Elapsed (s)"
    },
    "stats_remaining_time": {
        "zh": "预计剩余时间 (秒)",
        "en": "Est. Remaining (s)"
    },
    "paused_info": {
        "zh": "已暂停，还剩 {} 段未翻译。",
        "en": "Paused. {} blocks remaining to translate."
    },
    "partial_translation_warning": {
        "zh": "当前是部分翻译模式：最多处理前 {} 个文本块，其他段落会保留原文且不会插入译文。",
        "en": "Partial translation mode is enabled: at most the first {} text blocks are processed. Other blocks keep the original text without inserted translations."
    },
    "job_status_idle": {
        "zh": "未开始。",
        "en": "Not started."
    },
    "job_status_running": {
        "zh": "正在翻译：已处理 {processed}/{total} 段，剩余 {pending} 段。",
        "en": "Translating: processed {processed}/{total} blocks, {pending} remaining."
    },
    "job_status_paused": {
        "zh": "已暂停：已处理 {processed}/{total} 段。点击“继续”恢复当前任务，点击“停止并清空”放弃当前任务。",
        "en": "Paused: processed {processed}/{total} blocks. Click Resume to continue this job, or Stop & Clear to discard it."
    },
    "job_status_done": {
        "zh": "任务完成：已得到 {translated} 段译文，失败 {failures} 段。",
        "en": "Done: {translated} translations ready, {failures} failures."
    },
    "job_status_empty": {
        "zh": "未解析到可翻译文本。",
        "en": "No translatable text found."
    },
    "translation_completed": {
        "zh": "🎉 翻译完成",
        "en": "🎉 Translation Completed"
    },
    "stats_final_inserted": {
        "zh": "插入译文数量",
        "en": "Translations Injected"
    },
    "stats_final_placeholders": {
        "zh": "未翻译占位数量",
        "en": "Missing Placeholders"
    },
    "download_bilingual_epub": {
        "zh": "⬇️ 下载双语 EPUB",
        "en": "⬇️ Download Bilingual EPUB"
    },
    "failure_details": {
        "zh": "失败详情（文本块 ID / 原文前 50 字 / 错误原因）：",
        "en": "Failure Details (block_id / first 50 chars / reason):"
    },
    "retry_failed_blocks": {
        "zh": "重试失败段落",
        "en": "Retry Failed Blocks"
    },
    "retry_failed_started": {
        "zh": "已重新加入 {} 个失败段落。",
        "en": "{} failed blocks queued for retry."
    },
    "translate_self_test": {
        "zh": "翻译自测（MVP-3）",
        "en": "Translation Self Test (MVP-3)"
    },
    "success_mapping": {
        "zh": "成功映射：",
        "en": "Successful mappings:"
    },
    "failure_records": {
        "zh": "失败记录：",
        "en": "Failure records:"
    },
    "provider_label": {
        "zh": "API 服务商",
        "en": "API Providers"
    },
    "prompt_hash_label": {
        "zh": "提示词哈希",
        "en": "Prompt Hash"
    },
    "col_block_id": {
        "zh": "文本块 ID",
        "en": "Block ID"
    },
    "col_text_snippet": {
        "zh": "原文片段",
        "en": "Text Snippet"
    },
    "col_reason": {
        "zh": "错误原因",
        "en": "Reason"
    },
    "model_label": {
        "zh": "模型",
        "en": "Model"
    }
}

def get_i18n(key: str, lang: str) -> str:
    return I18N.get(key, {}).get(lang, I18N.get(key, {}).get("zh", key))
