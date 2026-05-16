from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

import config
from database import clear_cache, init_db
from epub_processor import extract_blocks
from job_manager import JobConflictError, JobNotReadyError, SingleJobManager
from provider_tools import fetch_models, health_check, normalize_base_url
from providers import BUILTIN_PROVIDERS


class ModelsRequest(BaseModel):
    base_url: str
    api_key: str


class HealthRequest(BaseModel):
    base_url: str
    api_key: str
    model: str
    target_language: str = config.DEFAULT_TARGET_LANGUAGE


def create_app(manager: SingleJobManager | None = None) -> FastAPI:
    init_db(config.DB_PATH)
    app = FastAPI(title="EPUB Bilingual Translator API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.manager = manager or SingleJobManager()

    @app.get("/api/config")
    def get_config() -> dict:
        return {
            "providers": BUILTIN_PROVIDERS,
            "target_languages": config.TARGET_LANGUAGES,
            "defaults": {
                "model": config.MODEL,
                "temperature": config.TEMPERATURE,
                "batch_size": config.BATCH_SIZE,
                "concurrency": config.CONCURRENCY,
                "max_blocks": 0,
                "target_language": config.DEFAULT_TARGET_LANGUAGE,
            },
        }

    @app.post("/api/models")
    def get_models(request: ModelsRequest) -> dict:
        models, error = fetch_models(request.base_url, request.api_key)
        if models is None:
            return {"ok": False, "models": [], "error": error}
        return {"ok": True, "models": models, "error": None}

    @app.post("/api/health")
    def post_health(request: HealthRequest) -> dict:
        return health_check(
            request.base_url,
            request.api_key,
            request.model,
            request.target_language,
        )

    @app.post("/api/preview")
    async def preview(file: UploadFile = File(...)) -> dict:
        epub_bytes = await file.read()
        try:
            blocks = extract_blocks(epub_bytes)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to parse EPUB: {exc}") from exc
        return {
            "total_blocks": len(blocks),
            "preview": [
                {
                    "block_id": block["block_id"],
                    "tag": block["tag"],
                    "text": block["text"][:240],
                }
                for block in blocks[:8]
            ],
        }

    @app.post("/api/jobs")
    async def create_job(
        file: UploadFile = File(...),
        api_key: str = Form(...),
        base_url: str = Form(...),
        model: str = Form(...),
        temperature: float = Form(config.TEMPERATURE),
        batch_size: int = Form(config.BATCH_SIZE),
        concurrency: int = Form(config.CONCURRENCY),
        custom_prompt: str = Form(""),
        target_language: str = Form(config.DEFAULT_TARGET_LANGUAGE),
        max_blocks: int = Form(0),
    ) -> dict:
        epub_bytes = await file.read()
        try:
            return await app.state.manager.create_job(
                epub_bytes=epub_bytes,
                input_name=file.filename or "book.epub",
                api_key=api_key,
                base_url=normalize_base_url(base_url),
                model=model,
                temperature=temperature,
                batch_size=batch_size,
                concurrency=concurrency,
                custom_prompt=custom_prompt,
                target_language=target_language,
                max_blocks=max_blocks,
            )
        except JobConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to create job: {exc}") from exc

    @app.get("/api/jobs/current")
    def current_job() -> dict:
        return app.state.manager.snapshot()

    @app.post("/api/jobs/current/pause")
    async def pause_job() -> dict:
        return app.state.manager.pause()

    @app.post("/api/jobs/current/resume")
    async def resume_job() -> dict:
        return app.state.manager.resume()

    @app.post("/api/jobs/current/stop")
    async def stop_job() -> dict:
        return app.state.manager.stop()

    @app.post("/api/jobs/current/retry-failures")
    async def retry_failures() -> dict:
        return app.state.manager.retry_failures()

    @app.get("/api/jobs/current/download")
    def download() -> Response:
        try:
            output_bytes, output_name = app.state.manager.download_bytes()
        except JobNotReadyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            output_bytes,
            media_type="application/epub+zip",
            headers={"Content-Disposition": f'attachment; filename="{output_name}"'},
        )

    @app.post("/api/cache/clear")
    def clear_translation_cache() -> dict:
        cleared = clear_cache(app.state.manager.db_path)
        return {"ok": True, "cleared": cleared}

    return app


app = create_app()
