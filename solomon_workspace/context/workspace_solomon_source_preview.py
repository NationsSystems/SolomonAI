# -------------------------------------------------------------------
# FILE: workspace_solomon_source_preview.py
# DIRECTORY: solomon_workspace/context/
# -------------------------------------------------------------------
# Bounded source-preview extraction for the SolomonAI workspace.
# This module reads limited preview text only; it does not execute AI,
# mutate workspace state, decide workflow authority, or shape UI state.
# -------------------------------------------------------------------

import os
import re
import zipfile
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree


WORKSPACE_SOLOMON_SOURCE_PREVIEW_TOTAL_CHARS = 9000
WORKSPACE_SOLOMON_SOURCE_PREVIEW_PER_FILE_CHARS = 4500
WORKSPACE_SOLOMON_SOURCE_BRIEFING_PREVIEW_TOTAL_CHARS = 6000
WORKSPACE_SOLOMON_SOURCE_BRIEFING_PREVIEW_PER_FILE_CHARS = 3500


def clean_workspace_solomon_preview_line(
    value: Any,
    *,
    limit: int = 260,
) -> str:
    """Normalize one preview line for safe user-facing or prompt-facing use."""

    clean_value = " ".join(
        str(value or "").replace("\x00", " ").split()
    )

    if len(clean_value) > limit:
        return clean_value[:limit].strip()

    return clean_value


def normalize_workspace_solomon_preview_match_text(value: Any) -> str:
    """Normalize preview text for lightweight deterministic term matching."""

    return " ".join(
        str(value or "").replace("&", " and ").lower().split()
    )


def normalize_workspace_solomon_source_text(
    value: Any,
    *,
    limit: int,
) -> str:
    """Normalize extracted source text while preserving paragraph boundaries."""

    clean_value = re.sub(
        r"[ \t]+",
        " ",
        str(value or "").replace("\x00", " "),
    )
    clean_value = re.sub(r"\n{3,}", "\n\n", clean_value).strip()

    if len(clean_value) > limit:
        return clean_value[:limit].strip()

    return clean_value


def read_workspace_solomon_plain_text(
    path: str,
    *,
    limit: int,
) -> str:
    """Read bounded preview text from plain text-like files."""

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            return normalize_workspace_solomon_source_text(
                handle.read(limit * 2),
                limit=limit,
            )
    except OSError:
        return ""


def extract_workspace_solomon_pdf_text_with_pypdf(
    path: str,
    *,
    limit: int,
    max_pages: int = 1,
) -> str:
    """Extract bounded PDF text with pypdf or PyPDF2."""

    try:
        try:
            from pypdf import PdfReader
        except Exception:
            from PyPDF2 import PdfReader

        reader = PdfReader(path)
        chunks = []
        chars_remaining = limit

        for page in reader.pages[:max(1, max_pages)]:
            if chars_remaining <= 0:
                break

            page_text = str(page.extract_text() or "").strip()

            if not page_text:
                continue

            chunks.append(page_text[:chars_remaining])
            chars_remaining -= len(chunks[-1])

        return normalize_workspace_solomon_source_text(
            "\n\n".join(chunks),
            limit=limit,
        )
    except Exception:
        return ""


def extract_workspace_solomon_pdf_text(
    path: str,
    *,
    limit: int,
    max_pages: int = 1,
) -> str:
    """Extract bounded PDF preview text using the local PDF parser."""

    return extract_workspace_solomon_pdf_text_with_pypdf(
        path,
        limit=limit,
        max_pages=max_pages,
    )


def extract_workspace_solomon_docx_text(
    path: str,
    *,
    limit: int,
) -> str:
    """Extract bounded DOCX paragraph text directly from the document XML."""

    try:
        with zipfile.ZipFile(path) as archive:
            xml_bytes = archive.read("word/document.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return ""

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return ""

    namespace = {
        "w": (
            "http://schemas.openxmlformats.org/"
            "wordprocessingml/2006/main"
        )
    }
    paragraphs = []

    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(
            node.text or ""
            for node in paragraph.findall(".//w:t", namespace)
        ).strip()

        if text:
            paragraphs.append(text)

        if sum(len(item) for item in paragraphs) >= limit:
            break

    return normalize_workspace_solomon_source_text(
        "\n".join(paragraphs),
        limit=limit,
    )


def read_workspace_solomon_xlsx_shared_strings(
    archive: zipfile.ZipFile,
) -> List[str]:
    """Read workbook shared strings for bounded XLSX preview extraction."""

    try:
        xml_bytes = archive.read("xl/sharedStrings.xml")
    except KeyError:
        return []

    try:
        root = ElementTree.fromstring(xml_bytes)
    except ElementTree.ParseError:
        return []

    namespace = {
        "x": (
            "http://schemas.openxmlformats.org/"
            "spreadsheetml/2006/main"
        )
    }
    values = []

    for item in root.findall(".//x:si", namespace):
        values.append(
            "".join(
                text_node.text or ""
                for text_node in item.findall(".//x:t", namespace)
            )
        )

    return values


def extract_workspace_solomon_xlsx_text(
    path: str,
    *,
    limit: int,
) -> str:
    """Extract bounded tabular text from the first workbook worksheets."""

    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile):
        return ""

    with archive:
        shared_strings = read_workspace_solomon_xlsx_shared_strings(archive)
        worksheet_names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("xl/worksheets/")
            and name.endswith(".xml")
        )[:2]
        rows = []

        for worksheet_name in worksheet_names:
            if sum(len(item) for item in rows) >= limit:
                break

            try:
                root = ElementTree.fromstring(
                    archive.read(worksheet_name)
                )
            except (KeyError, ElementTree.ParseError):
                continue

            namespace = {
                "x": (
                    "http://schemas.openxmlformats.org/"
                    "spreadsheetml/2006/main"
                )
            }
            rows.append(f"[{os.path.basename(worksheet_name)}]")

            for row in root.findall(
                ".//x:sheetData/x:row",
                namespace,
            )[:30]:
                cell_values = []

                for cell in row.findall("x:c", namespace)[:16]:
                    value_node = cell.find("x:v", namespace)
                    raw_value = (
                        str(value_node.text or "").strip()
                        if value_node is not None
                        else ""
                    )

                    if cell.get("t") == "s" and raw_value.isdigit():
                        index = int(raw_value)
                        raw_value = (
                            shared_strings[index]
                            if index < len(shared_strings)
                            else raw_value
                        )

                    if raw_value:
                        cell_values.append(raw_value)

                if cell_values:
                    rows.append(" | ".join(cell_values))

                if sum(len(item) for item in rows) >= limit:
                    break

        return normalize_workspace_solomon_source_text(
            "\n".join(rows),
            limit=limit,
        )


def extract_workspace_solomon_source_text(
    source: Dict[str, Any],
    *,
    limit: int,
    max_pages: int = 1,
) -> Dict[str, Any]:
    """Extract bounded preview text from one resolved SolomonAI source."""

    path = str(source.get("_source_path") or "").strip()
    extension = str(source.get("extension") or "").strip().lower()

    if not path or not os.path.exists(path):
        return {
            "document_id": source.get("document_id") or "",
            "name": source.get("name") or "Selected document",
            "status": "unavailable",
            "text": "",
            "chars": 0,
        }

    text = ""
    status = "unsupported"

    if extension == "pdf":
        text = extract_workspace_solomon_pdf_text(
            path,
            limit=limit,
            max_pages=max_pages,
        )
        status = "ready" if text else "unavailable"
    elif extension == "docx":
        text = extract_workspace_solomon_docx_text(
            path,
            limit=limit,
        )
        status = "ready" if text else "unavailable"
    elif extension in {"txt", "md", "csv"}:
        text = read_workspace_solomon_plain_text(
            path,
            limit=limit,
        )
        status = "ready" if text else "unavailable"
    elif extension in {"xlsx", "xlsm"}:
        text = extract_workspace_solomon_xlsx_text(
            path,
            limit=limit,
        )
        status = "ready" if text else "unavailable"

    return {
        "document_id": source.get("document_id") or "",
        "name": source.get("name") or "Selected document",
        "extension": source.get("extension") or "",
        "status": status,
        "text": text,
        "chars": len(text),
    }


def build_workspace_solomon_source_previews(
    sources: List[Dict[str, Any]],
    *,
    total_chars: int = WORKSPACE_SOLOMON_SOURCE_PREVIEW_TOTAL_CHARS,
    per_file_chars: int = WORKSPACE_SOLOMON_SOURCE_PREVIEW_PER_FILE_CHARS,
    max_pages: int = 1,
) -> List[Dict[str, Any]]:
    """Build bounded preview packets for connected source records."""

    previews = []
    remaining_chars = max(0, int(total_chars or 0))

    for source in sources or []:
        if remaining_chars <= 0:
            break

        per_file_limit = min(
            max(0, int(per_file_chars or 0)),
            remaining_chars,
        )
        preview = extract_workspace_solomon_source_text(
            source,
            limit=per_file_limit,
            max_pages=max_pages,
        )
        previews.append(preview)
        remaining_chars -= max(0, preview.get("chars") or 0)

    return previews


def build_workspace_solomon_source_briefing_previews(
    sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build smaller preview packets for source briefing requests."""

    return build_workspace_solomon_source_previews(
        sources,
        total_chars=(
            WORKSPACE_SOLOMON_SOURCE_BRIEFING_PREVIEW_TOTAL_CHARS
        ),
        per_file_chars=(
            WORKSPACE_SOLOMON_SOURCE_BRIEFING_PREVIEW_PER_FILE_CHARS
        ),
        max_pages=1,
    )


def has_workspace_solomon_source_preview_text(
    source_previews: Optional[List[Dict[str, Any]]],
) -> bool:
    """Return whether any connected source preview has readable text."""

    return any(
        str(preview.get("text") or "").strip()
        for preview in source_previews or []
        if isinstance(preview, dict)
    )


def build_workspace_solomon_preview_prompt_block(
    source_previews: Optional[List[Dict[str, Any]]],
) -> str:
    """Format bounded source preview text for the SolomonAI LLM prompt."""

    blocks = []

    for preview in source_previews or []:
        if not isinstance(preview, dict):
            continue

        text = str(preview.get("text") or "").strip()

        if not text:
            continue

        blocks.append(
            "Source: "
            + str(preview.get("name") or "Selected document")
            + "\n"
            + text
        )

    if not blocks:
        return "No extractable source text is available for this request."

    return "\n\n---\n\n".join(blocks)


def build_workspace_solomon_cached_source_previews(
    sources: List[Dict[str, Any]],
    *,
    preview_available: bool,
) -> List[Dict[str, Any]]:
    """Represent cached source-brief availability without rereading source text."""

    if not preview_available:
        return []

    return [
        {
            "document_id": source.get("document_id") or "",
            "name": source.get("name") or "Selected document",
            "extension": source.get("extension") or "",
            "status": "cached",
            "text": "Cached source brief available.",
            "chars": 40,
        }
        for source in sources or []
    ]


def get_workspace_solomon_source_text_for_signals(
    source_previews: Optional[List[Dict[str, Any]]],
) -> str:
    """Join bounded source preview text for lightweight signal matching."""

    return "\n".join(
        str(preview.get("text") or "")
        for preview in source_previews or []
        if isinstance(preview, dict)
    )


def get_workspace_solomon_source_preview_lines(
    source_previews: Optional[List[Dict[str, Any]]],
    *,
    limit: int = 120,
) -> List[str]:
    """Return cleaned preview lines for fallback and guardrail helpers."""

    lines = []

    for preview in source_previews or []:
        if not isinstance(preview, dict):
            continue

        for raw_line in str(preview.get("text") or "").splitlines():
            clean_line = clean_workspace_solomon_preview_line(
                raw_line,
                limit=260,
            )

            if not clean_line or len(clean_line) < 3:
                continue

            lines.append(clean_line)

            if len(lines) >= limit:
                return lines

    return lines


def select_workspace_solomon_source_preview_lines(
    source_previews: Optional[List[Dict[str, Any]]],
    terms: Tuple[str, ...],
    *,
    max_items: int = 8,
) -> List[str]:
    """Select bounded preview lines matching supplied normalized terms."""

    selected = []

    for line in get_workspace_solomon_source_preview_lines(
        source_previews
    ):
        match_line = normalize_workspace_solomon_preview_match_text(line)

        if not any(term in match_line for term in terms):
            continue

        if line in selected:
            continue

        selected.append(line)

        if len(selected) >= max_items:
            break

    return selected