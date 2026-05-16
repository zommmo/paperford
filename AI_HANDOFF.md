# AI 交接文档

更新时间：2026-05-16

## 项目定位

这是一个本地运行的 Streamlit 工具，用于把 EPUB 电子书生成行间双语版本。

核心流程：

1. 上传 `.epub`。
2. 按 EPUB spine 阅读顺序抽取 `h1-h6`、`p`、`li` 文本块。
3. 调用兼容 OpenAI Chat Completions 的模型接口批量翻译。
4. 把译文作为 `p.trans-text` 插回原文本块后方。
5. 输出并下载双语 EPUB。

## 当前已完成能力

- Streamlit UI：上传、解析预览、开始/暂停/继续/停止、下载结果。
- Provider：
  - 内置 OpenAI、DeepSeek、xAI、Gemini OpenAI-compatible。
  - 支持自定义 Provider 和 Base URL。
  - 支持模型列表获取和连接测试。
- 翻译任务：
  - 批量翻译。
  - 并发控制。
  - 可暂停/继续。
  - 失败段落可单独重试。
  - 长段落会先做 token 估算并拆分为内部 part，译文再合并回原段落 ID。
- 缓存：
  - SQLite 缓存文件：`translations.sqlite3`。
  - 缓存 key 包含文本 hash、模型、prompt version、目标语言、温度参数、自定义风格 prompt hash。
  - SQLite 连接已显式关闭，`ResourceWarning` 已清理。
- EPUB 输出：
  - 译文用 `p.trans-text` 插入。
  - 样式通过 EPUB CSS 资源 `styles/trans-text.css` 注入，不再依赖会被 EbookLib 丢弃的 inline `<style>`。
- 设置：
  - 用户设置保存到 `~/.epub_bilingual_translator/settings.json`。
  - 支持中文/英文 UI。
  - 支持目标语言选择：Chinese、English、Japanese、Korean、French、German、Spanish。
- 启动：
  - 已新增 `run_app.sh`，不依赖已激活 shell，也不依赖 `.venv/bin/streamlit` 脚本是否因路径移动损坏。

## 关键文件

- `app.py`
  - Streamlit UI。
  - 负责读取控件、展示进度、调用任务服务层。
- `translation_job.py`
  - 翻译任务状态。
  - 缓存命中与待翻译块拆分。
  - 批处理推进。
  - 失败段落重试。
  - 输出 EPUB 生成。
- `translator.py`
  - 模型请求。
  - JSON 响应容错解析。
  - token 估算。
  - 长文本拆分与译文合并。
- `epub_processor.py`
  - EPUB 文本抽取。
  - 译文回填。
  - EPUB CSS 资源注入。
- `database.py`
  - SQLite 缓存读写。
- `provider_tools.py`
  - Base URL 规范化。
  - `/models` 获取。
  - 健康检查。
- `settings_store.py`
  - 本机设置文件读写。
- `i18n.py`
  - UI 文案。
- `run_app.sh`
  - 推荐启动入口。
- `tests/`
  - 当前使用标准库 `unittest`，无额外测试框架依赖。

## 运行方式

推荐：

```bash
cd /Users/tengjingshu/Documents/project/epub-bilingual-translator
./run_app.sh
```

手动方式：

```bash
cd /Users/tengjingshu/Documents/project/epub-bilingual-translator
source .venv/bin/activate
python -m streamlit run app.py
```

如果 `.venv` 不存在，重新创建：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

## 测试方式

推荐严格测试：

```bash
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
```

当前最新验证结果：

```text
Ran 19 tests ... OK
```

测试覆盖范围：

- 缓存 key 与 SQLite 读写。
- Provider Base URL 规范化。
- 模型 JSON 响应解析。
- 长段落拆分与合并。
- EPUB 抽取、注入和 CSS 资源。
- 翻译任务创建、缓存命中、批处理推进。
- 失败段落重试。
- 小型 EPUB 端到端流程：抽取 -> mock 翻译 -> 写缓存 -> 注入 -> 校验输出 EPUB。

## 最近提交

- `718ebd2 Add reliable app launcher`
  - 新增 `run_app.sh`，修复/规避虚拟环境迁移后入口脚本路径失效问题。
- `6598c91 Close sqlite connections explicitly`
  - 使用 `contextlib.closing` 显式关闭 SQLite 连接。
- `da63586 Add EPUB translation flow test`
  - 增加小型 EPUB 端到端流程测试。
- `a6b2c05 Add retry flow and split long translation blocks`
  - 增加失败段落重试。
  - 增加长段落 token 估算与拆分。
- `7e49bbb Refactor translation jobs and add target language`
  - 抽出 `translation_job.py`。
  - 增加目标语言选择。

## 当前工作区状态

截至本文档创建前，工作区是干净的。本文档新增后会显示为未提交变更，下一步如需保留请提交。

## 已知限制

- 目标语言当前是内置列表，尚不支持用户自定义输入。
- 文本抽取范围仅覆盖 `h1-h6`、`p`、`li`。
- 对复杂 EPUB 结构的支持还有限，例如脚注、表格、图片说明、分栏、嵌套 span 的精细还原。
- 翻译插入策略固定为“原文后插入译文段落”，没有提供样式配置 UI。
- `app.py` 已经比之前薄很多，但仍包含较多 Streamlit 控件和 Provider 管理逻辑，后续可以继续拆 UI 组件。
- 没有 GitHub Actions 或本地 Makefile，测试命令尚未固化为 CI。
- 没有真实 API 的集成测试，当前模型调用相关测试使用 mock。

## 建议下一步

优先级从高到低：

1. 增加 CI 或 Makefile
   - 增加 `Makefile`：
     - `make test`
     - `make run`
   - 如果仓库会推到 GitHub，再加 GitHub Actions 跑：
     - `.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests`

2. 增加自定义目标语言输入
   - 当前 `config.TARGET_LANGUAGES` 是固定列表。
   - 可以在 UI 增加“自定义目标语言”。
   - 注意目标语言必须继续进入 `params_json`，避免缓存串用。

3. 增加术语表/专名保护
   - UI 支持输入术语表。
   - cache key 需要加入术语表 hash。
   - prompt 需要清楚说明术语保留或指定译法。

4. 改进 EPUB 抽取范围
   - 评估是否加入 `blockquote`、`figcaption`、`td`、`th`。
   - 注意表格和列表中的译文插入可能破坏排版，需要单独测试。

5. 增加输出样式设置
   - 例如译文字号、颜色、是否斜体、间距。
   - 样式参数如影响输出，应进入任务参数或输出配置。

6. 更细的失败恢复
   - 当前能重试失败段落。
   - 后续可以显示“只下载成功段落版本 / 不插入失败占位 / 导出失败清单”。

## 给下一个 AI 的注意事项

- 不要直接改 `.venv` 并提交，它在 `.gitignore` 中。
- 推荐通过 `./run_app.sh` 启动应用。
- 改缓存相关逻辑时，务必同步更新测试，尤其是 `tests/test_translation_job.py` 和 `tests/test_translation_flow.py`。
- 改 EPUB 注入逻辑时，务必确认 `tests/test_epub_processor.py` 和端到端测试仍然能读取真实 zip 内的 XHTML。
- 改 prompt 或目标语言逻辑时，务必考虑缓存 key 是否需要变化。
- 如果新增依赖，更新 `requirements.txt`，并确认 `.venv/bin/python -m unittest discover -s tests` 可通过。
