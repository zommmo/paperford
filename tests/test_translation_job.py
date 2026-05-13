import asyncio
import tempfile
import unittest
from pathlib import Path

from database import bulk_get, init_db
from translation_job import (
    build_params_json,
    create_job_from_blocks,
    job_counts,
    prepare_retry_failed_blocks,
    process_next_batch,
)


def _block(block_id: str, text: str, text_hash: str) -> dict:
    return {
        "block_id": block_id,
        "doc_name": "chapter.xhtml",
        "tag": "p",
        "index": 0,
        "text": text,
        "text_hash": text_hash,
    }


class TranslationJobTests(unittest.TestCase):
    def test_params_json_includes_target_language(self):
        chinese = build_params_json(0.7, "Chinese")
        japanese = build_params_json(0.7, "Japanese")

        self.assertIn('"target_language":"Chinese"', chinese)
        self.assertIn('"temperature":0.7', chinese)
        self.assertNotEqual(chinese, japanese)

    def test_create_job_splits_cache_hits_and_pending_blocks(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "translations.sqlite3")
            init_db(db_path)
            blocks = [
                _block("chapter.xhtml::p::0", "Hello", "hash-1"),
                _block("chapter.xhtml::p::1", "World", "hash-2"),
            ]
            first_job = create_job_from_blocks(
                blocks[:1],
                b"epub",
                "book.epub",
                "model-a",
                0.7,
                1,
                1,
                "https://api.example.com/v1",
                "",
                db_path,
                now=10,
            )

            async def fake_translate(batch, *_args):
                return {batch[0]["block_id"]: "你好"}, []

            asyncio.run(process_next_batch(first_job, "key", db_path, fake_translate))

            second_job = create_job_from_blocks(
                blocks,
                b"epub",
                "book.epub",
                "model-a",
                0.7,
                1,
                1,
                "https://api.example.com/v1",
                "",
                db_path,
                now=20,
            )

            self.assertEqual(second_job["status"], "running")
            self.assertEqual(second_job["processed_blocks"], 1)
            self.assertEqual(second_job["hit_count"], 1)
            self.assertEqual(second_job["results_map"], {"chapter.xhtml::p::0": "你好"})
            self.assertEqual(
                [block["block_id"] for block in second_job["pending_blocks"]],
                ["chapter.xhtml::p::1"],
            )

    def test_process_next_batch_updates_job_and_cache(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "translations.sqlite3")
            init_db(db_path)
            blocks = [_block("chapter.xhtml::p::0", "Hello", "hash-1")]
            job = create_job_from_blocks(
                blocks,
                b"epub",
                "book.epub",
                "model-a",
                0.7,
                1,
                1,
                "https://api.example.com/v1",
                "literal",
                db_path,
                now=10,
            )
            cache_key = job["pending_blocks"][0]["cache_key"]

            async def fake_translate(
                batch,
                api_key,
                base_url,
                model,
                temperature,
                batch_size,
                concurrency,
                prompt,
                target_language,
            ):
                self.assertEqual(api_key, "key")
                self.assertEqual(base_url, "https://api.example.com/v1")
                self.assertEqual(model, "model-a")
                self.assertEqual(temperature, 0.7)
                self.assertEqual(batch_size, 1)
                self.assertEqual(concurrency, 1)
                self.assertEqual(prompt, "literal")
                self.assertEqual(target_language, "Chinese")
                return {batch[0]["block_id"]: "你好"}, []

            asyncio.run(process_next_batch(job, "key", db_path, fake_translate))

            self.assertEqual(job["status"], "done")
            self.assertEqual(job["processed_blocks"], 1)
            self.assertEqual(job["pending_blocks"], [])
            self.assertEqual(job["results_map"], {"chapter.xhtml::p::0": "你好"})
            self.assertEqual(job_counts(job)["placeholders"], 0)
            self.assertEqual(bulk_get(db_path, [cache_key]), {cache_key: "你好"})

    def test_failed_batch_can_be_requeued_for_retry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "translations.sqlite3")
            init_db(db_path)
            blocks = [_block("chapter.xhtml::p::0", "Hello", "hash-1")]
            job = create_job_from_blocks(
                blocks,
                b"epub",
                "book.epub",
                "model-a",
                0.7,
                1,
                1,
                "https://api.example.com/v1",
                "",
                db_path,
                now=10,
            )

            async def failing_translate(batch, *_args):
                return {}, [{"id": batch[0]["block_id"], "reason": "rate limited"}]

            asyncio.run(process_next_batch(job, "key", db_path, failing_translate))

            self.assertEqual(job["status"], "done")
            self.assertEqual(job_counts(job)["failures"], 1)
            self.assertEqual(job["failures"][0]["block"]["block_id"], "chapter.xhtml::p::0")

            retry_count = prepare_retry_failed_blocks(job)

            self.assertEqual(retry_count, 1)
            self.assertEqual(job["status"], "running")
            self.assertEqual(job["failures"], [])
            self.assertEqual(job["processed_blocks"], 0)
            self.assertEqual([block["block_id"] for block in job["pending_blocks"]], ["chapter.xhtml::p::0"])


if __name__ == "__main__":
    unittest.main()
