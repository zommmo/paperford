import asyncio
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api_app import create_app
from database import init_db
from job_manager import SingleJobManager
from tests.test_epub_processor import _build_epub_bytes


async def fake_translate(batch, *_args):
    return {
        block["block_id"]: f"译文：{block['text']}"
        for block in batch
    }, []


class ApiAppTests(unittest.TestCase):
    def _client(self, tmpdir: str) -> TestClient:
        db_path = str(Path(tmpdir) / "translations.sqlite3")
        init_db(db_path)
        manager = SingleJobManager(
            db_path=db_path,
            output_dir=str(Path(tmpdir) / "output"),
            translate_func=fake_translate,
        )
        return TestClient(create_app(manager))

    def test_preview_parses_epub(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            client = self._client(tmpdir)
            response = client.post(
                "/api/preview",
                files={"file": ("sample.epub", _build_epub_bytes(), "application/epub+zip")},
            )

            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["total_blocks"], 2)
            self.assertEqual(data["preview"][0]["text"], "Chapter One")

    def test_job_lifecycle_and_download(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            client = self._client(tmpdir)
            create_response = client.post(
                "/api/jobs",
                data={
                    "api_key": "key",
                    "base_url": "https://api.example.com/v1",
                    "model": "model-a",
                    "temperature": "0",
                    "batch_size": "1",
                    "concurrency": "1",
                    "target_language": "Chinese",
                    "max_blocks": "0",
                },
                files={"file": ("sample.epub", _build_epub_bytes(), "application/epub+zip")},
            )

            self.assertEqual(create_response.status_code, 200)
            for _ in range(50):
                status = client.get("/api/jobs/current").json()
                if status["status"] == "done":
                    break
                time.sleep(0.02)

            self.assertEqual(status["status"], "done")
            self.assertEqual(status["counts"]["translated"], 2)
            download = client.get("/api/jobs/current/download")
            self.assertEqual(download.status_code, 200)
            self.assertEqual(download.headers["content-type"], "application/epub+zip")
            self.assertGreater(len(download.content), 100)

    def test_running_job_rejects_second_job(self):
        async def slow_translate(batch, *_args):
            await asyncio.sleep(0.2)
            return {block["block_id"]: "译文" for block in batch}, []

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "translations.sqlite3")
            init_db(db_path)
            manager = SingleJobManager(
                db_path=db_path,
                output_dir=str(Path(tmpdir) / "output"),
                translate_func=slow_translate,
            )
            client = TestClient(create_app(manager))
            payload = {
                "api_key": "key",
                "base_url": "https://api.example.com/v1",
                "model": "model-a",
                "temperature": "0",
                "batch_size": "1",
                "concurrency": "1",
                "target_language": "Chinese",
                "max_blocks": "0",
            }
            first = client.post(
                "/api/jobs",
                data=payload,
                files={"file": ("sample.epub", _build_epub_bytes(), "application/epub+zip")},
            )
            second = client.post(
                "/api/jobs",
                data=payload,
                files={"file": ("sample.epub", _build_epub_bytes(), "application/epub+zip")},
            )

            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 409)


if __name__ == "__main__":
    unittest.main()
