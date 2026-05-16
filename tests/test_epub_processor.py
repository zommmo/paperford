import os
import tempfile
import unittest
import zipfile

from bs4 import BeautifulSoup
from ebooklib import epub

from epub_processor import extract_blocks, inject_translations


def _build_epub_bytes() -> bytes:
    book = epub.EpubBook()
    book.set_identifier("test-book")
    book.set_title("Test Book")
    book.set_language("en")

    chapter = epub.EpubHtml(title="Chapter 1", file_name="chap_01.xhtml", lang="en")
    chapter.content = """
    <html>
      <head><title>Chapter 1</title></head>
      <body>
        <h1>Chapter One</h1>
        <p>Hello world paragraph.</p>
        <p>123</p>
        <p>Hi</p>
      </body>
    </html>
    """
    book.add_item(chapter)
    book.toc = (epub.Link("chap_01.xhtml", "Chapter 1", "chapter-1"),)
    book.spine = [chapter]
    book.add_item(epub.EpubNcx())

    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as temp_file:
        temp_path = temp_file.name
    try:
        epub.write_epub(temp_path, book)
        with open(temp_path, "rb") as file:
            return file.read()
    finally:
        os.remove(temp_path)


def _read_first_document_html(epub_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as temp_file:
        temp_file.write(epub_bytes)
        temp_path = temp_file.name
    try:
        with zipfile.ZipFile(temp_path) as archive:
            for name in archive.namelist():
                if name.endswith("chap_01.xhtml"):
                    return archive.read(name).decode("utf-8")
    finally:
        os.remove(temp_path)
    raise AssertionError("No document item found")


def _read_translation_css(epub_bytes: bytes) -> str:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as temp_file:
        temp_file.write(epub_bytes)
        temp_path = temp_file.name
    try:
        book = epub.read_epub(temp_path)
        for item in book.get_items():
            if item.get_name() == "styles/trans-text.css":
                return item.get_content().decode("utf-8")
    finally:
        os.remove(temp_path)
    raise AssertionError("No translation CSS item found")


class EpubProcessorTests(unittest.TestCase):
    def test_extract_blocks_skips_noise_and_keeps_order(self):
        blocks = extract_blocks(_build_epub_bytes())

        self.assertEqual([block["text"] for block in blocks], ["Chapter One", "Hello world paragraph."])
        self.assertEqual(
            [block["block_id"] for block in blocks],
            ["chap_01.xhtml::h1::0", "chap_01.xhtml::p::1"],
        )

    def test_inject_translations_adds_translated_paragraphs_and_css(self):
        output = inject_translations(
            _build_epub_bytes(),
            {
                "chap_01.xhtml::h1::0": "第一章",
                "chap_01.xhtml::p::1": "你好，世界段落。",
            },
        )
        html = _read_first_document_html(output)
        css = _read_translation_css(output)
        soup = BeautifulSoup(html, "lxml")
        translations = [node.get_text(strip=True) for node in soup.select("p.trans-text")]

        self.assertEqual(translations, ["第一章", "你好，世界段落。"])
        self.assertIn('href="styles/trans-text.css"', html)
        self.assertIn(".trans-text", css)

    def test_inject_translations_skips_missing_translations(self):
        output = inject_translations(
            _build_epub_bytes(),
            {
                "chap_01.xhtml::h1::0": "第一章",
            },
        )
        html = _read_first_document_html(output)
        soup = BeautifulSoup(html, "lxml")
        translations = [node.get_text(strip=True) for node in soup.select("p.trans-text")]

        self.assertEqual(translations, ["第一章"])
        self.assertNotIn("[未翻译]", html)


if __name__ == "__main__":
    unittest.main()
