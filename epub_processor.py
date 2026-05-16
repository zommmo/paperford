import hashlib
import os
import posixpath
import tempfile
from typing import Iterable

from bs4 import BeautifulSoup
import ebooklib
from ebooklib import epub


def _normalize_text(text: str) -> str:
    # 归一化空白，便于稳定哈希与过滤
    return " ".join(text.split()).strip()


def _is_noise(text: str) -> bool:
    if not text:
        return True
    if len(text) < 5:
        return True
    if text.isdigit():
        return True
    # 纯符号文本：没有任何字母或数字
    if not any(char.isalnum() for char in text):
        return True
    return False


def _iter_text_nodes(soup: BeautifulSoup, tags: Iterable[str]):
    for node in soup.find_all(list(tags)):
        yield node.name, node.get_text(" ", strip=True)


def extract_blocks(epub_bytes: bytes) -> list[dict]:
    """
    解析 EPUB 并按文档顺序抽取文本块。
    """
    blocks: list[dict] = []
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as temp_file:
        temp_file.write(epub_bytes)
        temp_path = temp_file.name

    try:
        book = epub.read_epub(temp_path)
        # spine 是 EPUB 阅读顺序的目录列表，按此顺序抽取能保持章节顺序一致
        for spine_item in book.spine:
            item_id = spine_item[0] if isinstance(spine_item, (tuple, list)) else spine_item
            item = book.get_item_with_id(item_id)
            # 双保险：类型常量+具体类判断，兼容不同版本的 EbookLib
            if not item or (
                item.get_type() != ebooklib.ITEM_DOCUMENT and not isinstance(item, epub.EpubHtml)
            ):
                continue

            doc_name = item.get_name()
            soup = BeautifulSoup(item.get_content(), "lxml")
            index = 0
            for tag, raw_text in _iter_text_nodes(
                soup, ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]
            ):
                normalized = _normalize_text(raw_text)
                if _is_noise(normalized):
                    continue
                text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                # block_id 用文档名+标签+序号定位唯一块，便于追踪来源
                block_id = f"{doc_name}::{tag}::{index}"
                blocks.append(
                    {
                        "block_id": block_id,
                        "doc_name": doc_name,
                        "tag": tag,
                        "index": index,
                        "text": normalized,
                        # hash 是基于归一化文本的指纹，用于去重或一致性校验
                        "text_hash": text_hash,
                    }
                )
                index += 1
    finally:
        os.remove(temp_path)

    return blocks


def apply_translation_css(book) -> None:
    # 统一用 class + CSS 资源控制样式。EbookLib 会重建 HTML head，直接写 style 标签会被丢弃。
    css_text = ".trans-text { color:#666; font-size:0.92em; margin:0.25em 0 1em 0; }"
    css_uid = "trans_text_style"
    css_file_name = "styles/trans-text.css"

    if book.get_item_with_id(css_uid) is None:
        book.add_item(
            epub.EpubItem(
                uid=css_uid,
                file_name=css_file_name,
                media_type="text/css",
                content=css_text,
            )
        )

    for item in book.spine:
        item_id = item[0] if isinstance(item, (tuple, list)) else item
        html_item = book.get_item_with_id(item_id)
        if not html_item or (
            html_item.get_type() != ebooklib.ITEM_DOCUMENT and not isinstance(html_item, epub.EpubHtml)
        ):
            continue
        doc_dir = posixpath.dirname(html_item.get_name()) or "."
        href = posixpath.relpath(css_file_name, start=doc_dir)
        if not any(link.get("href") == href for link in getattr(html_item, "links", [])):
            html_item.add_link(href=href, rel="stylesheet", type="text/css")


def inject_translations(epub_bytes: bytes, translations: dict[str, str]) -> bytes:
    """
    把翻译内容插入到 EPUB 文档中，返回新的 EPUB bytes。
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as temp_file:
        temp_file.write(epub_bytes)
        temp_path = temp_file.name

    output_path = None
    try:
        book = epub.read_epub(temp_path)
        for spine_item in book.spine:
            item_id = (
                spine_item[0] if isinstance(spine_item, (tuple, list)) else spine_item
            )
            item = book.get_item_with_id(item_id)
            if not item or (
                item.get_type() != ebooklib.ITEM_DOCUMENT and not isinstance(item, epub.EpubHtml)
            ):
                continue

            doc_name = item.get_name()
            soup = BeautifulSoup(item.get_content(), "lxml")
            index = 0
            for node in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]):
                normalized = _normalize_text(node.get_text(" ", strip=True))
                if _is_noise(normalized):
                    continue
                # 必须复用 extract_blocks 的定位规则，否则翻译会错位到别的段落
                block_id = f"{doc_name}::{node.name}::{index}"
                translation = translations.get(block_id)
                if translation:
                    trans_tag = soup.new_tag("p")
                    trans_tag["class"] = "trans-text"
                    trans_tag.string = translation
                    node.insert_after(trans_tag)
                index += 1

            item.set_content(str(soup).encode("utf-8"))

        apply_translation_css(book)

        def _ensure_toc_uids(toc):
            # lxml 生成 NCX 时需要 uid 非空，部分 toc 条目 uid 可能为 None，这里补齐唯一 uid 以避免写出报错
            counter = {"n": 0}

            def walk(node):
                if isinstance(node, (list, tuple)):
                    for child in node:
                        walk(child)
                    return
                if hasattr(node, "uid") and getattr(node, "uid", None) is None:
                    counter["n"] += 1
                    node.uid = f"toc_uid_{counter['n']}"
                children = getattr(node, "children", None)
                if children:
                    walk(children)

            walk(toc)

        _ensure_toc_uids(book.toc)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".epub") as out_file:
            output_path = out_file.name
        epub.write_epub(output_path, book)
        with open(output_path, "rb") as f:
            return f.read()
    finally:
        os.remove(temp_path)
        if output_path and os.path.exists(output_path):
            os.remove(output_path)
