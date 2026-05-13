import asyncio
import json
import unittest

import config
import translator
from translator import TranslationError, extract_json_array, split_text_for_translation


class TranslatorTests(unittest.TestCase):
    def test_build_system_prompt_uses_target_language(self):
        prompt = config.build_system_prompt("Japanese")

        self.assertIn("Translations must be Japanese.", prompt)
        self.assertIn("only outputs JSON", prompt)

    def test_extract_json_array_accepts_plain_json(self):
        parsed = extract_json_array('[{"id":"a","translation":"你好"}]')

        self.assertEqual(parsed, [{"id": "a", "translation": "你好"}])

    def test_extract_json_array_strips_markdown_fence_and_extra_text(self):
        parsed = extract_json_array(
            'result:\n```json\n[{"id":"a","translation":"你好"}]\n```\n'
        )

        self.assertEqual(parsed, [{"id": "a", "translation": "你好"}])

    def test_extract_json_array_rejects_non_array(self):
        with self.assertRaises(TranslationError):
            extract_json_array('{"id":"a","translation":"你好"}')

    def test_split_text_for_translation_splits_long_text(self):
        text = "First sentence. Second sentence. Third sentence."
        chunks = split_text_for_translation(text, max_tokens=3, model="unknown-model")

        self.assertGreater(len(chunks), 1)
        self.assertEqual(" ".join(chunks), text)

    def test_translate_batches_reassembles_split_block(self):
        original_call_model = translator._call_model
        original_max_tokens = config.MAX_BLOCK_TOKENS

        async def fake_call_model(_client, payload):
            content = payload["messages"][1]["content"]
            items = json.loads(content[content.find("[") :])
            return json.dumps(
                [
                    {"id": item["id"], "translation": f"T({item['text']})"}
                    for item in items
                ],
                ensure_ascii=False,
            )

        try:
            translator._call_model = fake_call_model
            config.MAX_BLOCK_TOKENS = 3
            results, failures = asyncio.run(
                translator.translate_batches(
                    [{"block_id": "block-1", "text": "First sentence. Second sentence."}],
                    api_key="key",
                    base_url="https://api.example.com/v1",
                    model="unknown-model",
                    temperature=0,
                    batch_size=1,
                    concurrency=1,
                )
            )
        finally:
            translator._call_model = original_call_model
            config.MAX_BLOCK_TOKENS = original_max_tokens

        self.assertEqual(failures, [])
        self.assertGreater(results["block-1"].count("T("), 1)
        self.assertIn("\n", results["block-1"])


if __name__ == "__main__":
    unittest.main()
