# AI 交接文档

更新时间：2026-05-17

## 项目定位

这是一个本地运行的 FastAPI + React Web 应用，用于把 EPUB 电子书生成行间双语版本。旧 Streamlit UI 已移除，当前唯一推荐入口是新版 Web UI。

核心流程：

1. 上传 `.epub`。
2. 按 EPUB spine 阅读顺序抽取 `h1-h6`、`p`、`li` 文本块。
3. 调用兼容 OpenAI Chat Completions 的模型接口批量翻译。
4. 把译文作为 `p.trans-text` 插回原文本块后方。
5. 输出并下载双语 EPUB。

## 当前已完成能力

- Web UI：React + Vite + TypeScript，文学书房风格界面。
- API：FastAPI 后端，前端只通过 `/api/*` 访问后端。
- Provider：
  - 内置 OpenAI、DeepSeek、xAI、Gemini OpenAI-compatible。
  - 支持当前页面会话内添加和删除自定义 Provider。
  - 支持模型列表获取和连接测试。
- 界面语言：
  - 支持中文/英文切换。
  - 语言选择保存到浏览器 `localStorage["epub-bilingual-ui-language"]`。
- 翻译任务：
  - 单任务本地队列。
  - 批量翻译、并发控制、暂停、继续、停止。
  - 失败段落可单独重试。
  - 长段落会先做 token 估算并拆分为内部 part，译文再合并回原段落 ID。
- 缓存：
  - SQLite 缓存文件：`translations.sqlite3`。
  - 缓存 key 包含文本 hash、模型、prompt version、目标语言、温度参数、自定义风格 prompt hash。
- EPUB 输出：
  - 译文用 `p.trans-text` 插入。
  - 样式通过 EPUB CSS 资源 `styles/trans-text.css` 注入。

## 关键文件

- `api_app.py`
  - FastAPI 应用与接口。
  - 包含配置、模型列表、健康检查、预览、任务控制和下载接口。
- `job_manager.py`
  - 新版 Web UI 的单任务队列管理。
  - 持有当前 job、后台 task 和下载输出。
- `frontend/`
  - React + Vite + TypeScript 前端。
  - `frontend/src/App.tsx` 包含主要交互、会话内自定义 Provider 和中英切换。
  - `frontend/src/styles.css` 包含文学书房风格和响应式布局。
- `translation_job.py`
  - 翻译任务状态、缓存命中与待翻译块拆分、批处理推进、失败段落重试、输出 EPUB 生成。
- `translator.py`
  - 模型请求、JSON 响应容错解析、token 估算、长文本拆分与译文合并。
- `epub_processor.py`
  - EPUB 文本抽取、译文回填、EPUB CSS 资源注入。
- `provider_tools.py`
  - Base URL 规范化、`/models` 获取、健康检查。
- `database.py`
  - SQLite 缓存读写。

## 运行方式

推荐：

```bash
cd /Users/tengjingshu/Documents/project/epub-bilingual-translator
./run_web.sh
```

启动后打开：

```text
http://127.0.0.1:5173
```

Makefile：

```bash
make run
```

## 测试方式

Python 回归测试：

```bash
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
```

前端构建：

```bash
cd frontend
npm run build
```

测试覆盖范围：

- 缓存 key 与 SQLite 读写。
- Provider Base URL 规范化。
- FastAPI 预览、任务创建、下载和 running 冲突。
- 模型 JSON 响应解析。
- 长段落拆分与合并。
- EPUB 抽取、注入和 CSS 资源。
- 翻译任务创建、缓存命中、批处理推进。
- 失败段落重试。
- 小型 EPUB 端到端流程：抽取 -> mock 翻译 -> 写缓存 -> 注入 -> 校验输出 EPUB。

## 已知限制

- 当前任务状态保存在进程内存中，重启服务会丢失当前任务状态。
- 同一时间只能处理一本 EPUB。
- 自定义 Provider 只保存在当前前端页面会话，刷新页面后丢失。
- 文本抽取范围仅覆盖 `h1-h6`、`p`、`li`。
- 对复杂 EPUB 结构的支持还有限，例如脚注、表格、图片说明、分栏、嵌套 span 的精细还原。
- 翻译插入策略固定为“原文后插入译文段落”，没有提供样式配置 UI。
- 没有真实 API 的集成测试，当前模型调用相关测试使用 mock。

## 建议下一步

1. 用真实 EPUB 和真实 API Key 做完整手动验收。
2. 增加术语表/专名保护，cache key 需要加入术语表 hash。
3. 改进 EPUB 抽取范围，评估 `blockquote`、`figcaption`、`td`、`th`。
4. 增加输出样式设置，例如译文字号、颜色、是否斜体、间距。
5. 增加 GitHub Actions，固定 Python 测试和前端构建。

## 给下一个 AI 的注意事项

- 不要直接改 `.venv` 并提交，它在 `.gitignore` 中。
- 推荐通过 `./run_web.sh` 或 `make run` 启动应用。
- 改缓存相关逻辑时，务必同步更新 `tests/test_translation_job.py` 和 `tests/test_translation_flow.py`。
- 改 EPUB 注入逻辑时，务必确认 `tests/test_epub_processor.py` 和端到端测试仍能读取真实 zip 内的 XHTML。
- 改 prompt 或目标语言逻辑时，务必考虑缓存 key 是否需要变化。
- 如果新增依赖，更新 `requirements.txt`，并确认 Python 测试和前端构建都通过。
