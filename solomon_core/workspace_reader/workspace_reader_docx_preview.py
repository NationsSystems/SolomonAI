# -------------------------------------------------------------------
# FILE: workspace_reader_docx_preview.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# Server-owned DOCX text preview helpers for the Solomon workspace reader.
# -------------------------------------------------------------------

import re
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Tuple
from xml.etree import ElementTree

from solomon_core.logger import get_logger

logger = get_logger("workspace_reader.docx_preview")

DOCX_DOCUMENT_XML_PATH = "word/document.xml"
DOCX_XML_MAX_BYTES = 8 * 1024 * 1024
DOCX_PREVIEW_MAX_BLOCKS = 420
DOCX_PREVIEW_MAX_CHARS = 80000

DOCX_BLOCK_TYPE_TITLE = "title"
DOCX_BLOCK_TYPE_HEADING = "heading"
DOCX_BLOCK_TYPE_PARAGRAPH = "paragraph"
DOCX_BLOCK_TYPE_LIST_ITEM = "list_item"
DOCX_BLOCK_TYPE_TABLE = "table"

DOCX_STYLE_TITLE = "title"
DOCX_STYLE_HEADING_PREFIX = "heading"
DOCX_STYLE_LIST_KEYWORDS = (
    "list bullet",
    "list paragraph",
    "bullet",
    "list continue",
    "list number",
)


def get_xml_local_name(tag: str) -> str:
    """Return an XML local name without namespace noise."""

    clean_tag = str(tag or "")

    if "}" in clean_tag:
        return clean_tag.rsplit("}", 1)[-1]

    return clean_tag


def normalize_preview_text_block(value: str) -> str:
    """Normalize extracted preview text without adding interpretation."""

    text = str(value or "").replace("\xa0", " ").strip()

    if not text:
        return ""

    lines = []
    for line in text.splitlines():
        clean_line = re.sub(r"[ \t]+", " ", line).strip()
        if clean_line:
            lines.append(clean_line)

    return "\n".join(lines).strip()


def get_preview_block_signature(value: str) -> str:
    """Return a normalized signature for duplicate extraction cleanup."""

    clean_value = normalize_preview_text_block(value).lower()
    return re.sub(r"\s+", " ", clean_value).strip()


def get_preview_block_total_chars(blocks: List[str]) -> int:
    """Return the total character volume for preview diagnostics."""

    return sum(len(str(block or "")) for block in blocks)


def limit_docx_preview_blocks(blocks: List[str]) -> Tuple[List[str], bool]:
    """Apply bounded preview limits to extracted DOCX text blocks."""

    limited_blocks: List[str] = []
    total_chars = 0
    truncated = False

    for block in blocks:
        clean_block = normalize_preview_text_block(block)

        if not clean_block:
            continue

        remaining_chars = DOCX_PREVIEW_MAX_CHARS - total_chars

        if remaining_chars <= 0:
            truncated = True
            break

        if len(clean_block) > remaining_chars:
            clean_block = f"{clean_block[:remaining_chars].rstrip()}…"
            truncated = True

        limited_blocks.append(clean_block)
        total_chars += len(clean_block)

        if len(limited_blocks) >= DOCX_PREVIEW_MAX_BLOCKS:
            truncated = True
            break

    return limited_blocks, truncated


def merge_docx_preview_blocks(
    primary_blocks: List[str],
    fallback_blocks: List[str],
) -> List[str]:
    """Merge DOCX extraction results without duplicating the same text."""

    merged_blocks: List[str] = []
    seen_signatures = set()

    for block in primary_blocks:
        signature = get_preview_block_signature(block)

        if not signature or signature in seen_signatures:
            continue

        seen_signatures.add(signature)
        merged_blocks.append(normalize_preview_text_block(block))

    primary_index = "\n".join(seen_signatures)

    for block in fallback_blocks:
        signature = get_preview_block_signature(block)

        if not signature:
            continue
        if signature in seen_signatures:
            continue
        if signature in primary_index:
            continue

        seen_signatures.add(signature)
        merged_blocks.append(normalize_preview_text_block(block))

    return merged_blocks


def get_docx_style_name(element: Any) -> str:
    """Return a normalized python-docx style name for a paragraph/table object."""

    try:
        style = getattr(element, "style", None)
        style_name = getattr(style, "name", "")
    except Exception:
        style_name = ""

    return normalize_preview_text_block(style_name).lower()


def get_docx_heading_level(style_name: str) -> int:
    """Return heading level from a Word heading style name."""

    clean_style_name = str(style_name or "").strip().lower()

    if not clean_style_name.startswith(DOCX_STYLE_HEADING_PREFIX):
        return 0

    level_match = re.search(r"heading\s*(\d+)", clean_style_name)

    if not level_match:
        return 1

    try:
        return max(1, min(9, int(level_match.group(1))))
    except ValueError:
        return 1


def has_docx_numbering_properties(paragraph: Any) -> bool:
    """Return whether a paragraph has Word numbering/list metadata."""

    try:
        paragraph_properties = paragraph._p.pPr
    except Exception:
        return False

    if paragraph_properties is None:
        return False

    return getattr(paragraph_properties, "numPr", None) is not None


def is_docx_list_paragraph(paragraph: Any) -> bool:
    """Return whether a paragraph is styled as a Word list item."""

    style_name = get_docx_style_name(paragraph)

    if any(keyword in style_name for keyword in DOCX_STYLE_LIST_KEYWORDS):
        return True

    return has_docx_numbering_properties(paragraph)


def build_docx_paragraph_structured_block(
    paragraph: Any,
) -> Dict[str, Any]:
    """Build a style-aware structured block from a DOCX paragraph."""

    paragraph_text = normalize_preview_text_block(getattr(paragraph, "text", ""))

    if not paragraph_text:
        return {}

    style_name = get_docx_style_name(paragraph)
    heading_level = get_docx_heading_level(style_name)

    if style_name == DOCX_STYLE_TITLE:
        return {
            "type": DOCX_BLOCK_TYPE_TITLE,
            "text": paragraph_text,
            "style": style_name,
        }

    if heading_level:
        return {
            "type": DOCX_BLOCK_TYPE_HEADING,
            "text": paragraph_text,
            "level": heading_level,
            "style": style_name,
        }

    if is_docx_list_paragraph(paragraph):
        return {
            "type": DOCX_BLOCK_TYPE_LIST_ITEM,
            "text": paragraph_text,
            "style": style_name,
        }

    return {
        "type": DOCX_BLOCK_TYPE_PARAGRAPH,
        "text": paragraph_text,
        "style": style_name,
    }


def build_docx_table_cell_text(cell: Any) -> str:
    """Extract display text from a DOCX table cell."""

    cell_parts = []

    for paragraph in getattr(cell, "paragraphs", []) or []:
        paragraph_text = normalize_preview_text_block(getattr(paragraph, "text", ""))

        if paragraph_text:
            cell_parts.append(paragraph_text)

    for nested_table in getattr(cell, "tables", []) or []:
        nested_table_block = build_docx_table_structured_block(nested_table)

        for header in nested_table_block.get("headers") or []:
            if header:
                cell_parts.append(str(header))

        for row in nested_table_block.get("rows") or []:
            row_text = " | ".join(
                normalize_preview_text_block(value)
                for value in row.get("cells") or []
                if normalize_preview_text_block(value)
            )

            if row_text:
                cell_parts.append(row_text)

    return normalize_preview_text_block("\n".join(cell_parts))


def build_docx_table_row_cells(row: Any) -> List[str]:
    """Extract structured cell values from a DOCX table row."""

    cells = []

    for cell in getattr(row, "cells", []) or []:
        cell_text = build_docx_table_cell_text(cell)
        cells.append(cell_text)

    return cells


def trim_empty_docx_table_edges(rows: List[List[str]]) -> List[List[str]]:
    """Remove fully empty table rows while preserving real cell positions."""

    trimmed_rows = []

    for row in rows:
        clean_row = [normalize_preview_text_block(cell) for cell in row]

        if any(clean_row):
            trimmed_rows.append(clean_row)

    return trimmed_rows


def normalize_docx_table_width(rows: List[List[str]]) -> List[List[str]]:
    """Normalize row cell counts so template rendering remains stable."""

    max_cells = max((len(row) for row in rows), default=0)

    if max_cells <= 0:
        return []

    normalized_rows = []

    for row in rows:
        clean_row = [normalize_preview_text_block(cell) for cell in row]
        clean_row.extend([""] * (max_cells - len(clean_row)))
        normalized_rows.append(clean_row[:max_cells])

    return normalized_rows


def build_docx_table_structured_block(table: Any) -> Dict[str, Any]:
    """Build a structured preview block from a DOCX table."""

    raw_rows = []

    for row in getattr(table, "rows", []) or []:
        row_cells = build_docx_table_row_cells(row)

        if row_cells:
            raw_rows.append(row_cells)

    normalized_rows = normalize_docx_table_width(trim_empty_docx_table_edges(raw_rows))

    if not normalized_rows:
        return {}

    header_cells = normalized_rows[0]
    body_rows = normalized_rows[1:] if len(normalized_rows) > 1 else []

    return {
        "type": DOCX_BLOCK_TYPE_TABLE,
        "headers": header_cells,
        "rows": [
            {
                "cells": row,
            }
            for row in body_rows
        ],
        "style": get_docx_style_name(table),
    }


def get_docx_structured_block_text(block: Dict[str, Any]) -> str:
    """Return text content from a structured DOCX preview block."""

    block_type = str((block or {}).get("type") or "").strip()

    if block_type == DOCX_BLOCK_TYPE_TABLE:
        values = list((block or {}).get("headers") or [])

        for row in (block or {}).get("rows") or []:
            values.extend(row.get("cells") or [])

        return normalize_preview_text_block("\n".join(str(value or "") for value in values))

    return normalize_preview_text_block((block or {}).get("text") or "")


def get_docx_structured_block_signature(block: Dict[str, Any]) -> str:
    """Return a normalized signature for a structured DOCX block."""

    block_type = str((block or {}).get("type") or "").strip()
    block_text = get_docx_structured_block_text(block)

    if not block_type or not block_text:
        return ""

    return f"{block_type}:{get_preview_block_signature(block_text)}"


def get_docx_structured_preview_total_chars(blocks: List[Dict[str, Any]]) -> int:
    """Return total text characters inside structured DOCX preview blocks."""

    return sum(len(get_docx_structured_block_text(block)) for block in blocks or [])


def limit_docx_structured_preview_blocks(
    blocks: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], bool]:
    """Apply preview limits to structured DOCX blocks."""

    limited_blocks: List[Dict[str, Any]] = []
    total_chars = 0
    truncated = False

    for block in blocks:
        block_text = get_docx_structured_block_text(block)

        if not block_text:
            continue

        remaining_chars = DOCX_PREVIEW_MAX_CHARS - total_chars

        if remaining_chars <= 0:
            truncated = True
            break

        if len(block_text) > remaining_chars:
            truncated = True
            break

        limited_blocks.append(block)
        total_chars += len(block_text)

        if len(limited_blocks) >= DOCX_PREVIEW_MAX_BLOCKS:
            truncated = True
            break

    return limited_blocks, truncated


def merge_docx_structured_preview_blocks(
    primary_blocks: List[Dict[str, Any]],
    fallback_blocks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Merge structured DOCX blocks without duplicating the same visible text."""

    merged_blocks: List[Dict[str, Any]] = []
    seen_signatures = set()

    for block in primary_blocks or []:
        signature = get_docx_structured_block_signature(block)

        if not signature or signature in seen_signatures:
            continue

        seen_signatures.add(signature)
        merged_blocks.append(block)

    for block in fallback_blocks or []:
        signature = get_docx_structured_block_signature(block)

        if not signature or signature in seen_signatures:
            continue

        seen_signatures.add(signature)
        merged_blocks.append(block)

    return merged_blocks


def flatten_docx_structured_preview_blocks(
    blocks: List[Dict[str, Any]],
) -> List[str]:
    """Return flat text blocks from structured DOCX blocks for compatibility."""

    flat_blocks = []

    for block in blocks or []:
        block_type = str(block.get("type") or "").strip()

        if block_type == DOCX_BLOCK_TYPE_TABLE:
            headers = [
                normalize_preview_text_block(value)
                for value in block.get("headers") or []
            ]

            if any(headers):
                flat_blocks.append(" | ".join(headers).strip())

            for row in block.get("rows") or []:
                row_values = [
                    normalize_preview_text_block(value)
                    for value in row.get("cells") or []
                ]

                if any(row_values):
                    flat_blocks.append(" | ".join(row_values).strip())

            continue

        block_text = normalize_preview_text_block(block.get("text") or "")

        if block_text:
            flat_blocks.append(block_text)

    return flat_blocks


def build_docx_table_row_text(row) -> str:
    """Extract a readable plain-text row from a DOCX table row."""

    cell_values = []

    for cell in row.cells:
        cell_text = build_docx_table_cell_text(cell)

        if cell_text:
            cell_values.append(cell_text)

    return " | ".join(cell_values).strip()


def build_docx_story_blocks(story) -> List[str]:
    """Extract paragraphs and tables from a python-docx story part."""

    story_blocks = []

    for paragraph in getattr(story, "paragraphs", []) or []:
        paragraph_text = normalize_preview_text_block(paragraph.text)
        if paragraph_text:
            story_blocks.append(paragraph_text)

    for table in getattr(story, "tables", []) or []:
        for row in table.rows:
            row_text = build_docx_table_row_text(row)
            if row_text:
                story_blocks.append(row_text)

    return story_blocks


def build_docx_structured_preview_blocks_with_python_docx(
    source_path: str,
) -> List[Dict[str, Any]]:
    """Build style-aware DOCX preview blocks using python-docx."""

    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    document = Document(source_path)
    body_blocks: List[Dict[str, Any]] = []
    parent = document._body

    for child in document.element.body.iterchildren():
        local_name = get_xml_local_name(child.tag)

        if local_name == "p":
            paragraph = Paragraph(child, parent)
            paragraph_block = build_docx_paragraph_structured_block(paragraph)

            if paragraph_block:
                body_blocks.append(paragraph_block)

        elif local_name == "tbl":
            table = Table(child, parent)
            table_block = build_docx_table_structured_block(table)

            if table_block:
                body_blocks.append(table_block)

    return body_blocks


def build_docx_preview_blocks_with_python_docx(source_path: str) -> List[str]:
    """Build DOCX preview blocks using python-docx when available."""

    document_blocks = build_docx_structured_preview_blocks_with_python_docx(source_path)
    body_blocks = flatten_docx_structured_preview_blocks(document_blocks)

    from docx import Document

    document = Document(source_path)
    related_blocks: List[str] = []

    for section in getattr(document, "sections", []) or []:
        for story_name in (
            "header",
            "first_page_header",
            "even_page_header",
            "footer",
            "first_page_footer",
            "even_page_footer",
        ):
            story = getattr(section, story_name, None)

            if story:
                related_blocks.extend(build_docx_story_blocks(story))

    return merge_docx_preview_blocks(body_blocks, related_blocks)


def is_docx_preview_xml_part(part_name: str) -> bool:
    """Return whether a DOCX XML part may contain user-visible text."""

    clean_name = str(part_name or "").strip().lower()

    if clean_name == DOCX_DOCUMENT_XML_PATH:
        return True
    if re.fullmatch(r"word/header\d*\.xml", clean_name):
        return True
    if re.fullmatch(r"word/footer\d*\.xml", clean_name):
        return True

    return clean_name in {
        "word/footnotes.xml",
        "word/endnotes.xml",
        "word/comments.xml",
    }


def load_docx_preview_xml_parts(
    source_path: str,
    *,
    request_id: str,
) -> List[Tuple[str, bytes]]:
    """Load visible DOCX XML parts with bounded read protection."""

    parts: List[Tuple[str, bytes]] = []
    has_document_xml = False

    with zipfile.ZipFile(source_path) as archive:
        for part_info in archive.infolist():
            part_name = str(part_info.filename or "").strip()

            if not is_docx_preview_xml_part(part_name):
                continue

            if int(part_info.file_size or 0) > DOCX_XML_MAX_BYTES:
                logger.warning(
                    "[workspace.reader.docx_part_skipped] request_id=%s "
                    "part=%s size=%s",
                    request_id,
                    part_name,
                    part_info.file_size,
                )
                continue

            if part_name.lower() == DOCX_DOCUMENT_XML_PATH:
                has_document_xml = True

            parts.append((part_name, archive.read(part_info.filename)))

    if not has_document_xml:
        raise ValueError("DOCX document body is missing.")

    return parts