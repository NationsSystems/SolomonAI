# solomon_core/solomon_tools/file_resolver.py
# ---------------------------------------------------------------
# Phase 26 — STRICT File Resolver for DocIntel (Metadata-Safe)
#
# Phase 39:
#   • NO semantic changes
#   • NO metadata changes
#   • Logging aligned to Focused Observability Mode (FOM-39)
#
# Phase 62 ADDITION:
#   • Upload-time text extraction helper (NON-SEMANTIC)
#   • Execution readiness only — no interpretation
# ---------------------------------------------------------------

import os
from solomon_core.logger import get_logger

logger = get_logger("file_resolver")


# ---------------------------------------------------------------
# Helper: Validate a single file entry
# ---------------------------------------------------------------
def _validate_entry(entry):
    """
    Accepts either:
      • str path
      • dict { path, original_name?, display_name? }

    Returns:
      • str (legacy)
      • dict (metadata preserved, canonicalized)
      • None if invalid
    """
    # -----------------------------
    # Legacy string path
    # -----------------------------
    if isinstance(entry, str):
        clean = entry.strip()
        if clean and os.path.isfile(clean):
            return clean

        logger.debug("[file_resolver] File not found (string path)")
        return None

    # -----------------------------
    # Structured document entry
    # -----------------------------
    if isinstance(entry, dict):
        path = entry.get("path")
        if not isinstance(path, str):
            return None

        clean = path.strip()
        if not clean or not os.path.isfile(clean):
            logger.debug("[file_resolver] File not found (dict path)")
            return None

        out = {
            "path": clean
        }

        original_name = entry.get("original_name")
        display_name = entry.get("display_name")

        if isinstance(original_name, str):
            out["original_name"] = original_name

        # Phase 26 canonicalization:
        if isinstance(display_name, str):
            out["display_name"] = display_name
        elif isinstance(original_name, str):
            out["display_name"] = original_name

        return out

    return None


# ---------------------------------------------------------------
# Helper: Validate a list of document entries
# ---------------------------------------------------------------
def _validate_docs(docs) -> list:
    if not isinstance(docs, list):
        return []

    out = []
    for item in docs:
        valid = _validate_entry(item)
        if valid is not None:
            out.append(valid)

    return out


# ---------------------------------------------------------------
# Phase 62 — Upload-Time Text Extraction (NON-SEMANTIC)
# ---------------------------------------------------------------
def extract_text_for_upload(path: str) -> str:
    """
    Phase 62 invariant:
      • Extraction is mechanical, not interpretive
      • No inference, no summarization
      • Fail-safe: empty string if unreadable

    This function exists ONLY to make documents
    execution-ready at upload time.
    """
    if not isinstance(path, str) or not os.path.isfile(path):
        return ""

    try:
        with open(path, "rb") as f:
            raw = f.read()

        # Best-effort decode — no guarantees, no semantics
        return raw.decode(errors="ignore")

    except Exception as exc:
        logger.debug(
            "[Phase62][UPLOAD_EXTRACT_FAIL]",
            extra={"error": str(exc)},
        )
        return ""


# ---------------------------------------------------------------
# STRICT FILE RESOLUTION (Phase 26)
# ---------------------------------------------------------------
def resolve_files(entities: dict) -> dict:
    if not isinstance(entities, dict):
        return {}

    resolved = {}

    if "filename" in entities:
        resolved["filename"] = _validate_entry(entities.get("filename"))

    if "file2" in entities:
        resolved["file2"] = _validate_entry(entities.get("file2"))

    if "docs" in entities:
        resolved["docs"] = _validate_docs(entities.get("docs"))

    # Phase 39: summary-only visibility
    logger.info(
        "[Phase39][FILE_RESOLVE]",
        extra={
            "has_docs": bool(resolved.get("docs")),
            "doc_count": len(resolved.get("docs", [])),
            "has_filename": bool(resolved.get("filename")),
            "has_file2": bool(resolved.get("file2")),
        },
    )

    return resolved


__all__ = [
    "resolve_files",
    "extract_text_for_upload",
]
