import asyncio
from typing import Awaitable, Callable

import config
from translation_job import (
    create_translation_job,
    empty_job_state,
    ensure_output,
    job_counts,
    prepare_retry_failed_blocks,
    process_next_batch,
)
from translator import translate_batches


TranslateFunc = Callable[
    [list[dict], str, str, str, float, int, int, str, str, str, list[dict]],
    Awaitable[tuple[dict[str, str], list[dict]]],
]


class JobConflictError(Exception):
    pass


class JobNotReadyError(Exception):
    pass


class SingleJobManager:
    def __init__(
        self,
        db_path: str = config.DB_PATH,
        output_dir: str = "output",
        translate_func: TranslateFunc = translate_batches,
    ) -> None:
        self.db_path = db_path
        self.output_dir = output_dir
        self.translate_func = translate_func
        self.job = empty_job_state()
        self.api_key = ""
        self._task: asyncio.Task | None = None

    def _is_active(self) -> bool:
        return self.job.get("status") in {"running", "paused"}

    def _start_worker(self) -> None:
        if self.job.get("status") != "running":
            return
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while self.job.get("status") == "running":
            if not self.job.get("pending_blocks"):
                self.job["status"] = "done"
                break
            await process_next_batch(
                self.job,
                api_key=self.api_key,
                db_path=self.db_path,
                translate_func=self.translate_func,
            )
            await asyncio.sleep(0)
        if self.job.get("status") == "done" and self.job.get("epub_bytes"):
            ensure_output(self.job, output_dir=self.output_dir)

    async def create_job(
        self,
        epub_bytes: bytes,
        input_name: str,
        api_key: str,
        base_url: str,
        model: str,
        temperature: float,
        batch_size: int,
        concurrency: int,
        custom_prompt: str,
        glossary: str,
        target_language: str,
        max_blocks: int,
    ) -> dict:
        if self._is_active():
            raise JobConflictError("A translation job is already running or paused.")

        self.api_key = api_key
        self.job = create_translation_job(
            epub_bytes=epub_bytes,
            input_name=input_name,
            model=model,
            temperature=temperature,
            batch_size=batch_size,
            concurrency=concurrency,
            base_url=base_url,
            custom_prompt=custom_prompt,
            glossary=glossary,
            max_blocks=max_blocks,
            db_path=self.db_path,
            target_language=target_language,
        )
        self._start_worker()
        return self.snapshot()

    def pause(self) -> dict:
        if self.job.get("status") == "running":
            self.job["status"] = "paused"
        return self.snapshot()

    def resume(self) -> dict:
        if self.job.get("status") == "paused":
            if self._task and not self._task.done():
                self._task.cancel()
                self._task = None
            self.job["status"] = "running"
            self._start_worker()
        return self.snapshot()

    def stop(self) -> dict:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None
        self.api_key = ""
        self.job = empty_job_state()
        return self.snapshot()

    def retry_failures(self) -> dict:
        retry_count = 0
        if self.job.get("status") == "done":
            retry_count = prepare_retry_failed_blocks(self.job)
            self._start_worker()
        snapshot = self.snapshot()
        snapshot["retry_count"] = retry_count
        return snapshot

    def download_bytes(self) -> tuple[bytes, str]:
        if self.job.get("status") != "done" or not self.job.get("epub_bytes"):
            raise JobNotReadyError("No completed EPUB is available for download.")
        output_bytes = ensure_output(self.job, output_dir=self.output_dir)
        if output_bytes is None:
            raise JobNotReadyError("No completed EPUB is available for download.")
        return output_bytes, self.job.get("output_name") or "bilingual.epub"

    def snapshot(self) -> dict:
        counts = job_counts(self.job)
        total = counts["total"]
        processed = self.job.get("processed_blocks", 0)
        return {
            "status": self.job.get("status", "idle"),
            "progress": int(processed / total * 100) if total else 0,
            "processed_blocks": processed,
            "pending_blocks": len(self.job.get("pending_blocks") or []),
            "counts": counts,
            "failures": [
                {
                    "id": failure.get("id"),
                    "text_snippet": failure.get("text_snippet", ""),
                    "reason": failure.get("reason", ""),
                }
                for failure in self.job.get("failures") or []
            ],
            "output_name": self.job.get("output_name"),
            "can_download": self.job.get("status") == "done" and bool(self.job.get("epub_bytes")),
            "target_language": self.job.get("target_language") or config.DEFAULT_TARGET_LANGUAGE,
        }
