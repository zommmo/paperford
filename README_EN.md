# Paperford

Paperford is a local FastAPI + React web app for translating EPUB books into bilingual, interleaved reading copies.

The app runs on your own machine. EPUB files, API keys, and translation requests stay under your control; requests are sent directly from your local environment to the LLM provider or proxy endpoint you configure.

## Workflow

1. Upload an `.epub` file.
2. Extract headings, paragraphs, and list items in EPUB reading order.
3. Translate text blocks in batches through an OpenAI Chat Completions-compatible API.
4. Insert translations back after the original text blocks.
5. Download the generated bilingual EPUB.

## Features

- React + Vite + TypeScript web UI with a quiet literary-study style.
- FastAPI backend with a single local translation job queue.
- Built-in OpenAI-compatible providers: OpenAI, DeepSeek, xAI, and Gemini.
- Session-only custom providers and Base URLs.
- Chinese and English UI switching, remembered in the browser.
- Model list fetching and connection testing.
- Translation cache clearing from the UI.
- Batch translation with concurrency control, pause, resume, stop, and failed-block retry.
- SQLite translation cache to avoid repeated requests for identical text and settings.
- Target language selection, including custom target language input.
- Optional custom style prompt.
- Long-block token estimation and splitting before model requests, with merged translations in the final EPUB.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd frontend
npm install
```

## Run

Start the local web app:

```bash
./run_web.sh
```

Then open:

```text
http://127.0.0.1:5173
```

You can also use:

```bash
make run
```

## Usage

1. Enter your API key in the settings panel.
2. Choose a provider, or add a temporary custom provider with a name and Base URL.
3. Enter a model name or fetch the available model list.
4. Adjust target language, temperature, batch size, concurrency, max block count, and translation style.
5. Upload an EPUB and optionally parse a preview first.
6. Start translation and download the bilingual EPUB when the job is complete.
7. Clear the translation cache from the debug section when you want to force fresh translations.

## Output and Cache

- Generated files are written to `output/` and are also available through the download button.
- The translation cache is stored in `translations.sqlite3`.
- Cache keys include text hash, model, prompt version, target language, parameters, and custom style prompt hash.
- Changing the model, target language, temperature, or style prompt creates separate cache entries.

## Development

Run Python tests:

```bash
.venv/bin/python -W error::ResourceWarning -m unittest discover -s tests
```

Build the frontend:

```bash
cd frontend
npm run build
```

## Key Files

- `api_app.py`: FastAPI backend API.
- `job_manager.py`: single-job queue manager for the web UI.
- `frontend/`: React + Vite + TypeScript frontend.
- `translation_job.py`: job state, cache hits, batch progression, retry flow, and EPUB output.
- `epub_processor.py`: EPUB extraction and translation injection.
- `translator.py`: model requests, batch translation, and JSON response parsing.
- `provider_tools.py`: provider Base URL normalization, model fetching, and health checks.
- `database.py`: SQLite translation cache.

## Limitations

- Only one EPUB can be processed at a time.
- Custom providers are stored only in the current page session and disappear after refresh.
- Text extraction currently covers `h1-h6`, `p`, and `li` tags.
- Failed blocks can be retried; downloaded EPUBs created before retry still use `[未翻译]` placeholders.

## API Key Safety

Paperford runs locally. API requests are made directly from your machine to the LLM provider or proxy endpoint you configure.

Your API key is kept only in the current page memory and is lost after refresh. It is not uploaded to any third-party server by this app.

Do not hard-code API keys in source files or commit them to a public repository.

## License

MIT License
