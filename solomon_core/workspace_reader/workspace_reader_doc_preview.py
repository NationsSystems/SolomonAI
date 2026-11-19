# -------------------------------------------------------------------
# FILE: workspace_reader_doc_preview.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# Server-owned legacy DOC preview compatibility helpers for Solomon
# Documents. Legacy DOC upload remains supported, but visual preview
# conversion is intentionally disabled.
# -------------------------------------------------------------------

import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

from solomon_core.logger import get_logger

logger = get_logger("workspace_reader.doc_preview")

SOFFICE_ENVIRONMENT_VARIABLE = "SOLOMON_SOFFICE_PATH"
DOC_PREVIEW_CACHE_ENVIRONMENT_VARIABLE = "SOLOMON_READER_PREVIEW_CACHE_DIR"

LEGACY_DOC_EXTENSIONS = {".doc"}
DOC_BINARY_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
DOC_PREVIEW_CACHE_VERSION = "doc_preview_disabled_v1"
DOC_PREVIEW_CACHE_DIRECTORY = "doc"
DOC_PREVIEW_DOCX_FILENAME = "preview.docx"
DOC_PREVIEW_METADATA_FILENAME = "metadata.json"
DOC_PREVIEW_ERROR_FILENAME = "conversion_error.txt"
DOC_PREVIEW_LOCK_FILENAME = "conversion.lock"

LEGACY_DOC_PREVIEW_UNSUPPORTED_MESSAGE = (
    "Legacy Word document. This file was stored successfully. Visual preview is "
    "not available for legacy `.doc` files. Solomon can still attempt analysis "
    "using text-only extraction. For best results, upload PDF or DOCX."
)
LEGACY_DOC_ANALYSIS_FAILURE_MESSAGE = (
    "This legacy Word document could not be read reliably. Upload PDF or DOCX "
    "for full analysis."
)


def get_legacy_doc_extension(source_path: str) -> str:
    """Return the normalized legacy Word extension."""

    return Path(str(source_path or "")).suffix.lower().strip()


def is_legacy_doc_source(source_path: str) -> bool:
    """Return whether the file is a stored legacy DOC source."""

    path = Path(str(source_path or ""))

    if get_legacy_doc_extension(str(path)) not in LEGACY_DOC_EXTENSIONS:
        return False

    return path.is_file()


def has_legacy_doc_binary_signature(source_path: str) -> bool:
    """Return whether the file has the expected legacy Office binary signature."""

    try:
        with Path(source_path).open("rb") as source_file:
            header = source_file.read(len(DOC_BINARY_SIGNATURE))
    except OSError:
        return False

    return header == DOC_BINARY_SIGNATURE


def resolve_soffice_path() -> str:
    """Raise because LibreOffice is not part of Solomon's trusted runtime."""

    raise RuntimeError(
        "LibreOffice conversion is disabled. Solomon stores legacy `.doc` files "
        "and may attempt text-only analysis through a narrow extractor, but does "
        "not use LibreOffice for preview, thumbnails, AI source truth, or reports."
    )


def resolve_doc_preview_cache_root() -> Path:
    """Return the legacy preview-cache root path for compatibility callers."""

    project_root = Path(__file__).resolve().parents[2]
    return project_root / "runtime" / "reader_preview_cache"


def get_doc_preview_source_fingerprint(source_path: Path) -> Dict:
    """Return a stable fingerprint for compatibility and stale-cache checks."""

    try:
        stat_result = source_path.stat()
    except OSError:
        return {
            "cache_version": DOC_PREVIEW_CACHE_VERSION,
            "source_path": str(source_path),
            "source_name": source_path.name,
            "source_size": 0,
            "source_modified_ns": 0,
            "preview_status": "disabled",
        }

    return {
        "cache_version": DOC_PREVIEW_CACHE_VERSION,
        "source_path": str(source_path.resolve()),
        "source_name": source_path.name,
        "source_size": int(stat_result.st_size),
        "source_modified_ns": int(stat_result.st_mtime_ns),
        "preview_status": "disabled",
    }


def get_doc_preview_cache_key(source_path: Path) -> str:
    """Return the deterministic disabled-preview cache key for one source DOC."""

    fingerprint = get_doc_preview_source_fingerprint(source_path)
    payload = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))

    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def get_doc_preview_cache_directory(source_path: Path) -> Path:
    """Return the inert cache directory path for one source DOC file."""

    return (
        resolve_doc_preview_cache_root()
        / DOC_PREVIEW_CACHE_DIRECTORY
        / get_doc_preview_cache_key(source_path)
    )


def get_doc_preview_cache_docx_path(source_path: Path) -> Path:
    """Return the inert cached DOCX path for compatibility callers."""

    return get_doc_preview_cache_directory(source_path) / DOC_PREVIEW_DOCX_FILENAME


def get_doc_preview_cache_metadata_path(source_path: Path) -> Path:
    """Return the inert cache metadata path for compatibility callers."""

    return get_doc_preview_cache_directory(source_path) / DOC_PREVIEW_METADATA_FILENAME


def get_doc_preview_cache_error_path(source_path: Path) -> Path:
    """Return the inert cache error-marker path for compatibility callers."""

    return get_doc_preview_cache_directory(source_path) / DOC_PREVIEW_ERROR_FILENAME


def get_doc_preview_cache_lock_path(source_path: Path) -> Path:
    """Return the inert cache lock path for compatibility callers."""

    return get_doc_preview_cache_directory(source_path) / DOC_PREVIEW_LOCK_FILENAME


def read_doc_preview_cache_metadata(metadata_path: Path) -> Dict:
    """Return no cache metadata because legacy DOC preview is disabled."""

    return {}


def write_doc_preview_cache_metadata(source_path: Path, metadata_path: Path) -> None:
    """Do not write preview metadata because legacy DOC preview is disabled."""

    return


def doc_preview_cache_metadata_matches(source_path: Path, metadata_path: Path) -> bool:
    """Return False because converted DOC preview cache is not authoritative."""

    return False


def is_doc_preview_cache_ready(source_path: str) -> bool:
    """Return False because legacy DOC visual preview conversion is disabled."""

    return False


def is_doc_preview_cache_failed(source_path: str) -> bool:
    """Return False because disabled visual preview is not a conversion failure."""

    return False


def is_doc_preview_cache_preparing(source_path: str) -> bool:
    """Return False because legacy DOC preview conversion is never queued."""

    return False


def get_doc_preview_cache_state(source_path: str) -> Dict[str, str]:
    """Return the server-owned preview state for one legacy DOC file."""

    source = Path(str(source_path or ""))

    if get_legacy_doc_extension(str(source)) not in LEGACY_DOC_EXTENSIONS:
        return {
            "state": "unsupported",
            "message": "This file is not a supported legacy Word document.",
            "preview_contract": "not_applicable",
        }

    if not source.is_file():
        return {
            "state": "missing",
            "message": "Legacy Word source file was not found.",
            "preview_contract": "missing_source",
        }

    return {
        "state": "unsupported",
        "message": LEGACY_DOC_PREVIEW_UNSUPPORTED_MESSAGE,
        "preview_contract": "legacy_doc_visual_preview_disabled",
        "analysis_contract": "text_only_extraction_allowed",
    }


def acquire_doc_preview_cache_lock(lock_path: Path) -> bool:
    """Return False because legacy DOC preview conversion locks are disabled."""

    return False


def release_doc_preview_cache_lock(lock_path: Path) -> None:
    """Do nothing because legacy DOC preview conversion locks are disabled."""

    return


def clear_doc_preview_error_marker(error_path: Path) -> None:
    """Do nothing because legacy DOC preview error markers are disabled."""

    return


def write_doc_preview_error_marker(
    source_path: Path,
    error_path: Path,
    error: Exception,
) -> None:
    """Log disabled preview conversion without writing error markers."""

    logger.info(
        "[workspace.reader.doc_preview_disabled] source=%s message=%s",
        source_path.name,
        error,
    )


def find_converted_docx_file(
    output_directory: Path,
    *,
    source_path: Path,
) -> Path:
    """Raise because LibreOffice DOC-to-DOCX preview conversion is disabled."""

    raise RuntimeError(LEGACY_DOC_PREVIEW_UNSUPPORTED_MESSAGE)


def convert_doc_to_docx(
    source_path: str,
    output_directory: str,
    *,
    request_id: str = "untracked",
) -> Path:
    """Raise because LibreOffice DOC-to-DOCX preview conversion is disabled."""

    logger.info(
        "[workspace.reader.doc_convert_blocked] request_id=%s source=%s",
        request_id,
        Path(str(source_path or "")).name,
    )

    raise RuntimeError(LEGACY_DOC_PREVIEW_UNSUPPORTED_MESSAGE)


def prepare_doc_preview_cache(
    source_path: str,
    *,
    request_id: str = "untracked",
    force: bool = False,
) -> Path:
    """Raise a controlled message instead of preparing legacy DOC preview."""

    logger.info(
        "[workspace.reader.doc_preview_prepare_blocked] request_id=%s source=%s",
        request_id,
        Path(str(source_path or "")).name,
    )

    raise RuntimeError(LEGACY_DOC_PREVIEW_UNSUPPORTED_MESSAGE)


def get_cached_doc_preview_path(
    source_path: str,
    *,
    request_id: str = "untracked",
) -> Optional[Path]:
    """Return no cached DOCX preview because conversion is disabled."""

    return None


def build_converted_docx_preview(
    converted_docx_path: str,
    *,
    original_name: str,
    request_id: str = "untracked",
) -> tuple[List[str], List[Dict], bool]:
    """Raise because converted DOCX preview artifacts are not produced."""

    logger.info(
        "[workspace.reader.doc_converted_preview_blocked] "
        "request_id=%s source=%s",
        request_id,
        original_name,
    )

    raise RuntimeError(LEGACY_DOC_PREVIEW_UNSUPPORTED_MESSAGE)


def build_doc_preview(
    source_path: str,
    *,
    request_id: str = "untracked",
) -> tuple[List[str], List[Dict], bool]:
    """Raise a controlled unsupported-preview message for legacy DOC files."""

    source = Path(str(source_path or ""))

    if not is_legacy_doc_source(str(source)):
        raise ValueError("Unsupported or missing legacy DOC source file.")

    logger.info(
        "[workspace.reader.doc_preview_blocked] request_id=%s source=%s",
        request_id,
        source.name,
    )

    raise RuntimeError(LEGACY_DOC_PREVIEW_UNSUPPORTED_MESSAGE)