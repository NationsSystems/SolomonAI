# -------------------------------------------------------------------
# FILE: workspace_reader_office_thumbnail.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# Server-owned Office document thumbnail compatibility helpers for
# Solomon Documents. Office visual thumbnail conversion is intentionally
# disabled; preview artifacts are decorative and never source truth.
# -------------------------------------------------------------------

from io import BytesIO
from pathlib import Path
from typing import Dict, Optional

from solomon_core.logger import get_logger

logger = get_logger("workspace_reader.office_thumbnail")

OFFICE_THUMBNAIL_EXTENSIONS = {".docx", ".doc"}
LEGACY_DOC_EXTENSION = ".doc"
DOCX_EXTENSION = ".docx"

OFFICE_THUMBNAIL_CACHE_VERSION = "office_thumbnail_disabled_v1"
OFFICE_THUMBNAIL_CACHE_DIRECTORY = "office_thumbnail"

OFFICE_THUMBNAIL_UNSUPPORTED_MESSAGE = (
    "Office document visual thumbnails are not available."
)
LEGACY_DOC_THUMBNAIL_UNSUPPORTED_MESSAGE = (
    "Legacy Word document. This file was stored successfully. Visual preview is "
    "not available for legacy `.doc` files. Solomon can still attempt analysis "
    "using text-only extraction. For best results, upload PDF or DOCX."
)
DOCX_THUMBNAIL_UNSUPPORTED_MESSAGE = (
    "Word document visual thumbnails are not available. Open the file reader "
    "for text preview where supported."
)


def get_office_thumbnail_extension(source_path: str) -> str:
    """Return the normalized Office thumbnail source extension."""

    return Path(str(source_path or "")).suffix.lower().strip()


def is_office_thumbnail_source(source_path: str) -> bool:
    """Return whether the file is a known Office document type."""

    path = Path(str(source_path or ""))

    if get_office_thumbnail_extension(str(path)) not in OFFICE_THUMBNAIL_EXTENSIONS:
        return False

    return path.is_file()


def is_legacy_doc_thumbnail_source(source_path: str) -> bool:
    """Return whether the Office source is a legacy DOC file."""

    return get_office_thumbnail_extension(source_path) == LEGACY_DOC_EXTENSION


def is_docx_thumbnail_source(source_path: str) -> bool:
    """Return whether the Office source is a DOCX file."""

    return get_office_thumbnail_extension(source_path) == DOCX_EXTENSION


def get_office_thumbnail_unsupported_message(source_path: str) -> str:
    """Return the controlled unsupported-thumbnail message for an Office file."""

    if is_legacy_doc_thumbnail_source(source_path):
        return LEGACY_DOC_THUMBNAIL_UNSUPPORTED_MESSAGE

    if is_docx_thumbnail_source(source_path):
        return DOCX_THUMBNAIL_UNSUPPORTED_MESSAGE

    return OFFICE_THUMBNAIL_UNSUPPORTED_MESSAGE


def get_office_thumbnail_source_fingerprint(source_path: Path) -> Dict:
    """Return a stable non-rendering fingerprint for compatibility callers."""

    try:
        stat_result = source_path.stat()
    except OSError:
        return {
            "cache_version": OFFICE_THUMBNAIL_CACHE_VERSION,
            "source_path": str(source_path),
            "source_name": source_path.name,
            "source_size": 0,
            "source_modified_ns": 0,
            "thumbnail_status": "disabled",
        }

    return {
        "cache_version": OFFICE_THUMBNAIL_CACHE_VERSION,
        "source_path": str(source_path.resolve()),
        "source_name": source_path.name,
        "source_size": int(stat_result.st_size),
        "source_modified_ns": int(stat_result.st_mtime_ns),
        "thumbnail_status": "disabled",
    }


def get_office_thumbnail_cache_root() -> Path:
    """Return the legacy cache root path without creating conversion state."""

    return Path("")


def get_office_thumbnail_cache_directory(source_path: Path) -> Path:
    """Return an inert cache directory path for compatibility callers."""

    return get_office_thumbnail_cache_root() / source_path.stem


def get_office_thumbnail_cache_pdf_path(source_path: Path) -> Path:
    """Return an inert cached PDF path for compatibility callers."""

    return get_office_thumbnail_cache_directory(source_path) / "thumbnail.pdf"


def get_office_thumbnail_cache_metadata_path(source_path: Path) -> Path:
    """Return an inert metadata path for compatibility callers."""

    return get_office_thumbnail_cache_directory(source_path) / "metadata.json"


def get_office_thumbnail_cache_error_path(source_path: Path) -> Path:
    """Return an inert error-marker path for compatibility callers."""

    return get_office_thumbnail_cache_directory(source_path) / "conversion_error.txt"


def get_office_thumbnail_cache_lock_path(source_path: Path) -> Path:
    """Return an inert lock path for compatibility callers."""

    return get_office_thumbnail_cache_directory(source_path) / "conversion.lock"


def read_office_thumbnail_cache_metadata(metadata_path: Path) -> Dict:
    """Return no Office thumbnail metadata because conversion is disabled."""

    return {}


def write_office_thumbnail_cache_metadata(
    source_path: Path,
    metadata_path: Path,
) -> None:
    """Do not write Office thumbnail metadata because conversion is disabled."""

    return


def office_thumbnail_cache_metadata_matches(
    source_path: Path,
    metadata_path: Path,
) -> bool:
    """Return False because Office thumbnail cache is never authoritative."""

    return False


def is_office_thumbnail_cache_ready(source_path: str) -> bool:
    """Return False because Office thumbnail rendering is disabled."""

    return False


def is_office_thumbnail_cache_failed(source_path: str) -> bool:
    """Return False because disabled thumbnail rendering is not a failure."""

    return False


def is_lock_stale(lock_path: Path, stale_seconds: int) -> bool:
    """Return False because Office thumbnail conversion locks are not used."""

    return False


def remove_stale_lock(lock_path: Path, stale_seconds: int) -> bool:
    """Return False because Office thumbnail conversion locks are not used."""

    return False


def is_office_thumbnail_cache_preparing(source_path: str) -> bool:
    """Return False because Office thumbnail conversion is never queued."""

    return False


def get_office_thumbnail_cache_state(source_path: str) -> Dict[str, str]:
    """Return the server-owned thumbnail state for one Office file."""

    source = Path(str(source_path or ""))

    if get_office_thumbnail_extension(str(source)) not in OFFICE_THUMBNAIL_EXTENSIONS:
        return {
            "state": "unsupported",
            "message": "This file is not an Office thumbnail source.",
            "preview_contract": "not_applicable",
        }

    if not source.is_file():
        return {
            "state": "missing",
            "message": "Office thumbnail source file was not found.",
            "preview_contract": "missing_source",
        }

    return {
        "state": "unsupported",
        "message": get_office_thumbnail_unsupported_message(str(source)),
        "preview_contract": "office_thumbnail_disabled",
    }


def acquire_filesystem_lock(lock_path: Path) -> bool:
    """Return False because Office thumbnail conversion locks are disabled."""

    return False


def release_filesystem_lock(lock_path: Path) -> None:
    """Do nothing because Office thumbnail conversion locks are disabled."""

    return


def acquire_office_thumbnail_cache_lock(lock_path: Path) -> bool:
    """Return False because Office thumbnail conversion locks are disabled."""

    return False


def release_office_thumbnail_cache_lock(lock_path: Path) -> None:
    """Do nothing because Office thumbnail conversion locks are disabled."""

    return


def clear_office_thumbnail_error_marker(error_path: Path) -> None:
    """Do nothing because Office thumbnail error markers are disabled."""

    return


def write_office_thumbnail_error_marker(
    source_path: Path,
    error_path: Path,
    error: Exception,
) -> None:
    """Log disabled thumbnail conversion without writing error markers."""

    logger.info(
        "[workspace.reader.office_thumbnail_disabled] source=%s message=%s",
        source_path.name,
        error,
    )


def find_converted_pdf_file(
    output_directory: Path,
    *,
    source_path: Path,
) -> Path:
    """Raise because Office-to-PDF thumbnail conversion is disabled."""

    raise RuntimeError(get_office_thumbnail_unsupported_message(str(source_path)))


def convert_office_source_to_pdf(
    source_path: str,
    output_directory: str,
    *,
    request_id: str = "untracked",
) -> Path:
    """Raise because Office-to-PDF thumbnail conversion is disabled."""

    logger.info(
        "[workspace.reader.office_thumbnail_conversion_blocked] "
        "request_id=%s source=%s",
        request_id,
        Path(str(source_path or "")).name,
    )

    raise RuntimeError(get_office_thumbnail_unsupported_message(source_path))


def resolve_office_thumbnail_conversion_source(
    source_path: Path,
    *,
    request_id: str = "untracked",
) -> Path:
    """Raise because Office thumbnail conversion sources are not used."""

    logger.info(
        "[workspace.reader.office_thumbnail_source_blocked] "
        "request_id=%s source=%s",
        request_id,
        source_path.name,
    )

    raise RuntimeError(get_office_thumbnail_unsupported_message(str(source_path)))


def prepare_office_thumbnail_cache(
    source_path: str,
    *,
    request_id: str = "untracked",
    force: bool = False,
) -> Path:
    """Raise a controlled message instead of preparing Office thumbnails."""

    logger.info(
        "[workspace.reader.office_thumbnail_prepare_blocked] "
        "request_id=%s source=%s",
        request_id,
        Path(str(source_path or "")).name,
    )

    raise RuntimeError(get_office_thumbnail_unsupported_message(source_path))


def get_cached_office_thumbnail_pdf_path(
    source_path: str,
    *,
    request_id: str = "untracked",
) -> Optional[Path]:
    """Return no cached PDF because Office thumbnails are disabled."""

    return None


def render_office_thumbnail_image(
    source_path: str,
    *,
    request_id: str = "untracked",
) -> BytesIO:
    """Raise a controlled message instead of rendering Office thumbnails."""

    logger.info(
        "[workspace.reader.office_thumbnail_render_blocked] "
        "request_id=%s source=%s",
        request_id,
        Path(str(source_path or "")).name,
    )

    raise RuntimeError(get_office_thumbnail_unsupported_message(source_path))