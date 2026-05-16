# EPUB 行间双语翻译器

一个本地运行的 FastAPI + React Web 应用，用于把 EPUB 电子书翻译成行间双语版本。

工作流程：

1. 上传 `.epub` 文件。
2. 按 EPUB 阅读顺序抽取标题、段落和列表文本。
3. 调用兼容 OpenAI Chat Completions 的模型接口批量翻译。
4. 把译文插回原 EPUB 文本块后方。
5. 下载生成的双语 EPUB。

## 当前能力

- 新版 Web UI：React + Vite + TypeScript。
- 后端 API：FastAPI + 单任务本地队列。
- 支持 OpenAI、DeepSeek、xAI、Gemini OpenAI 兼容接口。
- 支持当前页面会话内添加自定义 Provider 和 Base URL。
- 支持中文/英文界面切换，语言选择会保存在浏览器。
- 支持获取模型列表和连接测试。
- 支持从页面清除 SQLite 翻译缓存。
- 支持批量翻译、并发控制、暂停、继续、停止。
- 支持 SQLite 翻译缓存，重复文本和相同配置不会重复请求。
- 支持选择目标语言和自定义目标语言，目标语言会参与缓存 key。
- 支持自定义翻译风格提示词。
- 支持对长段落做 token 估算并在请求模型前自动拆分，译文会合并回原段落。

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend
npm install
```

## 运行

推荐使用项目脚本启动新版 Web UI：

```bash
./run_web.sh
```

启动后打开：

```text
http://127.0.0.1:5173
```

也可以使用 Makefile：

```bash
make run
```

## 使用说明

1. 在右侧配置区填写 API Key。
2. 选择 API 服务商；如需临时兼容接口，可在“添加自定义 Provider”中加入名称和 Base URL。
3. 填写或获取模型名称。
4. 调整目标语言、温度、批大小、并发数、最大文本块数和翻译风格。
5. 上传 EPUB 后可以先点“解析预览”确认文本抽取结果。
6. 点击“开始翻译”，完成后下载双语 EPUB。
7. 如需重新请求所有译文，可在调试区清除翻译缓存。

## 输出和缓存

- 生成文件会写入 `output/` 目录，并通过页面下载按钮提供下载。
- 翻译缓存默认保存在 `translations.sqlite3`。
- 缓存 key 包含文本 hash、模型、提示词版本、目标语言、参数和自定义风格 hash。
- 修改模型、目标语言、温度或自定义风格后，会使用新的缓存 key。

## 开发验证

项目的核心逻辑测试使用 Python 标准库 `unittest`：

```bash
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
```

前端构建验证：

```bash
cd frontend
npm run build
```

## 主要文件

- `api_app.py`：FastAPI 后端接口。
- `job_manager.py`：新版 Web UI 使用的单任务队列管理。
- `frontend/`：React + Vite + TypeScript 新版前端。
- `translation_job.py`：翻译任务状态、缓存命中、批处理推进和输出生成。
- `epub_processor.py`：EPUB 文本抽取与译文回填。
- `translator.py`：模型请求、批处理翻译和 JSON 响应解析。
- `provider_tools.py`：Provider Base URL 规范化、模型列表获取和连接测试。
- `database.py`：SQLite 翻译缓存。

## 已知限制

- 当前只支持单任务队列，同一时间只能处理一本 EPUB。
- 自定义 Provider 只保存在当前页面会话，刷新后会消失。
- 只抽取 `h1-h6`、`p`、`li` 标签中的文本。
- 失败段落可单独重试；重试前下载的 EPUB 仍会用 `[未翻译]` 占位。
