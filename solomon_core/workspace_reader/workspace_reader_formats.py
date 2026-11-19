# -------------------------------------------------------------------
# FILE: workspace_reader_formats.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# File format labels, reader modes, and reader metadata helpers.
# -------------------------------------------------------------------

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python compatibility guard.
    ZoneInfo = None


PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
LEGACY_WORD_EXTENSIONS = {".doc"}
WORD_EXTENSIONS = DOCX_EXTENSIONS | LEGACY_WORD_EXTENSIONS
XLSX_EXTENSIONS = {".xlsx"}
LEGACY_SPREADSHEET_EXTENSIONS = {".xls"}
SPREADSHEET_EXTENSIONS = XLSX_EXTENSIONS | LEGACY_SPREADSHEET_EXTENSIONS
BROWSER_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
TIFF_IMAGE_EXTENSIONS = {".tif", ".tiff"}
IMAGE_EXTENSIONS = BROWSER_IMAGE_EXTENSIONS | TIFF_IMAGE_EXTENSIONS
TEXT_EXTENSIONS = {".txt"}
CSV_EXTENSIONS = {".csv"}

SUPPORTED_READER_MODES = {"pdf", "docx", "xlsx", "xls", "text", "csv", "image"}
DEFAULT_READER_TIMEZONE_NAME = "America/Chicago"
FALLBACK_CENTRAL_TIMEZONE = timezone(timedelta(hours=-6), "CST")


def get_file_extension(filename: str) -> str:
    """Return a normalized file extension."""

    return Path(str(filename or "")).suffix.lower().strip()


def _get_reader_timezone():
    """Return local machine timezone, falling back to Central time."""

    try:
        local_timezone = datetime.now().astimezone().tzinfo

        if local_timezone:
            return local_timezone
    except Exception:
        pass

    if ZoneInfo:
        try:
            return ZoneInfo(DEFAULT_READER_TIMEZONE_NAME)
        except Exception:
            pass

    return FALLBACK_CENTRAL_TIMEZONE


def _parse_datetime_value(value) -> Optional[datetime]:
    """Parse a datetime-like metadata value."""

    if not value:
        return None

    if isinstance(value, datetime):
        return value

    clean_value = str(value or "").strip()

    if not clean_value:
        return None

    normalized_value = clean_value

    if normalized_value.endswith("Z"):
        normalized_value = f"{normalized_value[:-1]}+00:00"

    try:
        return datetime.fromisoformat(normalized_value)
    except ValueError:
        pass

    for date_format in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
    ):
        try:
            return datetime.strptime(clean_value, date_format)
        except ValueError:
            continue

    return None


def _format_reader_datetime(value: datetime) -> str:
    """Format a datetime label in reader-local time."""

    local_datetime = value
    reader_timezone = _get_reader_timezone()

    if local_datetime.tzinfo is None:
        local_datetime = local_datetime.replace(tzinfo=timezone.utc)

    local_datetime = local_datetime.astimezone(reader_timezone)
    hour_label = local_datetime.strftime("%I").lstrip("0") or "12"
    minute_label = local_datetime.strftime("%M")
    meridiem_label = local_datetime.strftime("%p")
    timezone_label = local_datetime.strftime("%Z").strip()

    label = (
        f"{local_datetime.strftime('%b %d, %Y')} "
        f"{hour_label}:{minute_label} {meridiem_label}"
    )

    if timezone_label:
        return f"{label} {timezone_label}"

    return label


def format_file_size(size_bytes) -> str:
    """Return a compact user-facing file size."""

    try:
        size = float(size_bytes or 0)
    except (TypeError, ValueError):
        size = 0

    if size <= 0:
        return "Size unavailable"
    if size < 1024:
        return f"{int(size)} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"

    return f"{size / (1024 * 1024 * 1024):.1f} GB"


def format_datetime_label(value) -> Optional[str]:
    """Return a compact user-facing datetime label."""

    parsed_datetime = _parse_datetime_value(value)

    if parsed_datetime:
        return _format_reader_datetime(parsed_datetime)

    clean_value = str(value or "").strip()
    return clean_value or None


def get_page_count_label(page_count: int) -> str:
    """Return a user-facing page count label."""

    count = int(page_count or 0)

    if count == 1:
        return "1 page"

    return f"{count} pages"


def get_status_label(is_active: bool) -> str:
    """Return a compact file status label."""

    return "Workflow active" if is_active else "Stored"


def get_checksum_preview(checksum: Optional[str]) -> Optional[str]:
    """Return a short checksum preview for metadata display."""

    clean_checksum = str(checksum or "").strip()

    if len(clean_checksum) < 12:
        return None

    return f"{clean_checksum[:12]}…"


def get_type_label(filename: str) -> str:
    """Return a simple user-facing file type label."""

    extension = get_file_extension(filename)

    if extension in PDF_EXTENSIONS:
        return "PDF Document"
    if extension in DOCX_EXTENSIONS:
        return "Word Document"
    if extension in LEGACY_WORD_EXTENSIONS:
        return "Legacy Word Document"
    if extension in XLSX_EXTENSIONS:
        return "Excel Workbook"
    if extension in LEGACY_SPREADSHEET_EXTENSIONS:
        return "Excel 97-2003 Workbook"
    if extension in CSV_EXTENSIONS:
        return "CSV File"
    if extension in TEXT_EXTENSIONS:
        return "Text Document"
    if extension in TIFF_IMAGE_EXTENSIONS:
        return "TIFF Image File"
    if extension in IMAGE_EXTENSIONS:
        return "Image File"

    return "Workspace File"


def get_reader_mode(filename: str) -> str:
    """Return the server-selected reader mode for the document format."""

    extension = get_file_extension(filename)

    if extension in PDF_EXTENSIONS:
        return "pdf"
    if extension in DOCX_EXTENSIONS:
        return "docx"
    if extension in LEGACY_WORD_EXTENSIONS:
        return "doc"
    if extension in XLSX_EXTENSIONS:
        return "xlsx"
    if extension in LEGACY_SPREADSHEET_EXTENSIONS:
        return "xls"
    if extension in CSV_EXTENSIONS:
        return "csv"
    if extension in TEXT_EXTENSIONS:
        return "text"
    if extension in IMAGE_EXTENSIONS:
        return "image"

    return "stored_file"


def is_reader_supported(reader_mode: str) -> bool:
    """Return whether the selected reader mode can render in-app."""

    return reader_mode in SUPPORTED_READER_MODES


def get_reader_title(filename: str) -> str:
    """Return the user-facing title for the active reader mode."""

    extension = get_file_extension(filename)

    if extension in PDF_EXTENSIONS:
        return "Solomon PDF Reader"
    if extension in DOCX_EXTENSIONS:
        return "Solomon Word Reader"
    if extension in LEGACY_WORD_EXTENSIONS:
        return "Legacy Word Document"
    if extension in XLSX_EXTENSIONS:
        return "Solomon Excel Reader"
    if extension in LEGACY_SPREADSHEET_EXTENSIONS:
        return "Solomon Excel Reader"
    if extension in CSV_EXTENSIONS:
        return "Solomon CSV Reader"
    if extension in TEXT_EXTENSIONS:
        return "Solomon Text Reader"
    if extension in IMAGE_EXTENSIONS:
        return "Solomon Image Reader"

    return "File stored"


def get_reader_message(filename: str) -> str:
    """Return a safe read-only message for the document format."""

    extension = get_file_extension(filename)

    if extension in PDF_EXTENSIONS:
        return "This PDF is rendered as first-party read-only Solomon pages."
    if extension in DOCX_EXTENSIONS:
        return (
            "This Word document is rendered as first-party read-only Solomon "
            "text. Layout, images, comments, and tracked changes may not be "
            "fully represented in this preview."
        )
    if extension in LEGACY_WORD_EXTENSIONS:
        return (
            "Legacy Word document. This file was stored successfully. Visual "
            "preview is not available for legacy `.doc` files. Solomon can still "
            "attempt analysis using text-only extraction. For best results, "
            "upload PDF or DOCX."
        )
    if extension in XLSX_EXTENSIONS:
        return (
            "This Excel workbook is rendered as a first-party read-only "
            "Solomon spreadsheet preview. Formulas, macros, charts, comments, "
            "and advanced workbook features may not be fully represented."
        )
    if extension in LEGACY_SPREADSHEET_EXTENSIONS:
        return (
            "This legacy Excel workbook is rendered as a first-party read-only "
            "Solomon spreadsheet preview. Formulas, macros, charts, comments, "
            "formatting, and advanced workbook features may not be fully "
            "represented."
        )
    if extension in CSV_EXTENSIONS:
        return (
            "This CSV file is rendered as a first-party read-only Solomon "
            "table preview. Very large files may be limited for safe "
            "in-browser reading."
        )
    if extension in TEXT_EXTENSIONS:
        return (
            "This text document is rendered as a first-party read-only Solomon "
            "text preview. Very large files may be limited for safe in-browser "
            "reading."
        )
    if extension in TIFF_IMAGE_EXTENSIONS:
        return (
            "This TIFF image is rendered as a first-party read-only Solomon "
            "PNG preview. Multi-page TIFF files show the first frame only. "
            "The original file remains stored under server-owned document "
            "authority."
        )
    if extension in IMAGE_EXTENSIONS:
        return (
            "This image file is rendered as a first-party read-only Solomon "
            "image preview. The original file remains stored under server-owned "
            "document authority."
        )

    return (
        "This file is stored in Solomon Documents. Full in-app reading for "
        "this format is not available yet."
    )


def build_reader_metadata_items(
    *,
    type_label: str,
    size_bytes,
    page_count: int,
    active: bool,
    uploaded_at=None,
    updated_at=None,
    checksum: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Build compact server-owned metadata items for the reader UI."""

    items = [
        {"label": "Type", "value": type_label},
        {"label": "Size", "value": format_file_size(size_bytes)},
    ]

    if int(page_count or 0) > 0:
        items.append({"label": "Pages", "value": get_page_count_label(page_count)})

    items.append({"label": "Status", "value": get_status_label(active)})

    uploaded_label = format_datetime_label(uploaded_at)
    updated_label = format_datetime_label(updated_at)
    checksum_preview = get_checksum_preview(checksum)

    if uploaded_label:
        items.append({"label": "Uploaded", "value": uploaded_label})

    if updated_label and updated_label != uploaded_label:
        items.append({"label": "Updated", "value": updated_label})

    if checksum_preview:
        items.append({"label": "Checksum", "value": checksum_preview})

    return items


def build_reader_metadata_line(metadata_items: List[Dict[str, str]]) -> str:
    """Build a compact metadata line for the title bar."""

    preferred_labels = {"Type", "Size", "Pages", "Status"}
    values = [
        item.get("value")
        for item in metadata_items
        if item.get("label") in preferred_labels and item.get("value")
    ]

    return " · ".join(values)