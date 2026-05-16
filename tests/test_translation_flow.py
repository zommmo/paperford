import asyncio
import tempfile
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

from database import bulk_get, init_db
from tests.test_epub_processor import (
    _build_epub_bytes,
    _read_first_document_html,
    _read_translation_css,
)
from translation_job import create_translation_job, ensure_output, job_counts, process_next_batch


class TranslationFlowTests(unittest.TestCase):
    def test_epub_translation_job_writes_cache_and_output_epub(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = str(Path(tmpdir) / "translations.sqlite3")
            output_dir = str(Path(tmpdir) / "output")
            init_db(db_path)
            epub_bytes = _build_epub_bytes()
            job = create_translation_job(
                epub_bytes=epub_bytes,
                input_name="sample.epub",
                model="model-a",
                temperature=0.0,
                batch_size=1,
                concurrency=1,
            base_url="https://api.example.com/v1",
            custom_prompt="literal",
            glossary="",
            max_blocks=0,
                db_path=db_path,
                target_language="Chinese",
            )
            cache_keys = [block["cache_key"] for block in job["pending_blocks"]]

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
                glossary,
                context,
            ):
                self.assertEqual(api_key, "key")
                self.assertEqual(base_url, "https://api.example.com/v1")
                self.assertEqual(model, "model-a")
                self.assertEqual(temperature, 0.0)
                self.assertEqual(batch_size, 1)
                self.assertEqual(concurrency, 1)
                self.assertEqual(prompt, "literal")
                self.assertEqual(target_language, "Chinese")
                return {
                    block["block_id"]: f"译文：{block['text']}"
                    for block in batch
                }, []

            while job["status"] == "running":
                asyncio.run(process_next_batch(job, "key", db_path, fake_translate))

            output_bytes = ensure_output(job, output_dir=output_dir)
            html = _read_first_document_html(output_bytes)
            css = _read_translation_css(output_bytes)
            soup = BeautifulSoup(html, "xml")
            translations = [node.get_text(strip=True) for node in soup.select("p.trans-text")]

            self.assertEqual(job["status"], "done")
            self.assertEqual(job_counts(job)["translated"], 2)
            self.assertEqual(
                translations,
                ["译文：Chapter One", "译文：Hello world paragraph."],
            )
            self.assertIn('href="styles/trans-text.css"', html)
            self.assertIn(".trans-text", css)
            self.assertEqual(
                set(bulk_get(db_path, cache_keys).values()),
                {"译文：Chapter One", "译文：Hello world paragraph."},
            )
            self.assertTrue((Path(output_dir) / "sample_bilingual.epub").exists())


if __name__ == "__main__":
    unittest.main()
