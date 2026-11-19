# solomon_core/skills/semantic/extract_text.py
# ---------------------------------------------------------------
# Phase 26 — Multi-Document Extractor + Explicit Claim Extraction
#
# Deterministic text loading + OCR fallback
# ---------------------------------------------------------------

import os
import re
import subprocess
import tempfile

from solomon_core.logger import get_logger
from solomon_core.solomon_tools.pdf_parser import pdf_to_text
from solomon_core.domains import DOMAIN_DOCINTEL

logger = get_logger("skill_extract_text")


# ---------------------------------------------------------------
# PDF metadata detection
# ---------------------------------------------------------------
def _looks_like_pdf_metadata(text: str) -> bool:
    if not text:
        return True

    lowered = text.lower()
    metadata_markers = [
        "xmpmeta", "<rdf", "trailer", "endobj", "xref",
        "pdf-", "/producer", "/creator",
        "/creationdate", "/moddate", "obj\n", "stream\n",
    ]

    hits = sum(1 for m in metadata_markers if m in lowered)
    word_count = len(text.split())
    unique_ratio = len(set(text.split())) / max(word_count, 1)

    return hits >= 2 or word_count < 80 or unique_ratio < 0.25


# ---------------------------------------------------------------
# Structured extraction
# ---------------------------------------------------------------
def _structured_extract(text: str) -> dict:
    if not text or not isinstance(text, str):
        return {
            "title": None,
            "headings": [],
            "sections": [],
            "dates": [],
            "currency": [],
        }

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0] if lines else None

    headings = [
        ln for ln in lines
        if (ln.isupper() and len(ln) > 3) or (ln.istitle() and len(ln.split()) > 1)
    ]

    section_pattern = re.compile(r"^\s*(\d+\.|[A-Za-z]+\.)\s+.+$")
    sections = [ln for ln in lines if section_pattern.match(ln)]

    date_pattern = re.compile(
        r"\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|[A-Za-z]+\s+\d{1,2},\s*\d{4})\b"
    )
    dates = date_pattern.findall(text)

    currency_pattern = re.compile(r"\$\s*\d{1,3}(?:,\d{3})*(?:\.\d{2})?")
    currency = currency_pattern.findall(text)

    return {
        "title": title,
        "headings": headings[:50],
        "sections": sections[:50],
        "dates": dates[:50],
        "currency": currency[:50],
    }


# ---------------------------------------------------------------
# OCR fallback
# ---------------------------------------------------------------
def _ocr_pdf(path: str) -> str:
    logger.info(f"[extract_text] OCR fallback engaged for {path}")

    with tempfile.TemporaryDirectory() as tmpdir:
        prefix = os.path.join(tmpdir, "page")

        try:
            subprocess.run(
                ["pdftoppm", "-r", "300", "-png", path, prefix],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as e:
            logger.error(f"[extract_text] pdftoppm failed: {e}")
            return ""

        blocks = []
        for fname in sorted(os.listdir(tmpdir)):
            if fname.endswith(".png"):
                img_path = os.path.join(tmpdir, fname)
                try:
                    proc = subprocess.run(
                        ["tesseract", img_path, "stdout"],
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                    if proc.stdout:
                        blocks.append(proc.stdout)
                except Exception as e:
                    logger.error(f"[extract_text] tesseract failed: {e}")

        return "\n".join(blocks).strip()


# ---------------------------------------------------------------
# Load text
# ---------------------------------------------------------------
def _load_text(path: str) -> str:
    if not path or not os.path.isfile(path):
        return ""

    if path.lower().endswith(".pdf"):
        try:
            text = pdf_to_text(path)
            if text and not _looks_like_pdf_metadata(text):
                return text
        except Exception:
            pass
        return _ocr_pdf(path)

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    except Exception:
        return ""


# ---------------------------------------------------------------
# MAIN EXECUTOR (FIXED)
# ---------------------------------------------------------------
def execute(arguments: dict):
    """
    Supports:
      • docs=[...]  (multi-document)
      • file_path="..." (single-document)
    """

    docs = []

    # ✅ NEW: allow single-file execution
    if isinstance(arguments, dict):
        if "docs" in arguments and isinstance(arguments["docs"], list):
            docs = arguments["docs"]
        elif isinstance(arguments.get("file_path"), str):
            docs = [arguments["file_path"]]

    if not docs:
        return {
            "ok": False,
            "result": "No documents provided.",
            "user_output": "No documents were supplied.",
        }

    doc_entries = []
    merged = []

    for entry in docs:
        if isinstance(entry, str):
            path = entry
            original_name = os.path.basename(path)
            display_name = original_name
        elif isinstance(entry, dict):
            path = entry.get("path")
            if not isinstance(path, str):
                continue
            original_name = entry.get("original_name") or os.path.basename(path)
            display_name = entry.get("display_name") or original_name
        else:
            continue

        if not os.path.isfile(path):
            continue

        text = _load_text(path)
        structured = _structured_extract(text)

        doc_entries.append({
            "name": os.path.basename(path),
            "original_name": original_name,
            "display_name": display_name,
            "path": path,
            "text": text,
            "structured": structured,
            "claims": [],
        })

        merged.append(f"[FILE: {display_name}]\n{text}\n")

    if not doc_entries:
        return {
            "ok": False,
            "result": "No valid documents could be loaded.",
            "user_output": "Uploaded documents could not be read.",
        }

    aggregated_text = "\n".join(merged)

    return {
        "ok": True,
        "docs": doc_entries,
        "aggregated_text": aggregated_text,
        "domain": DOMAIN_DOCINTEL,
        "result": aggregated_text,
        "user_output": aggregated_text,
    }
