# -------------------------------------------------------------------
# FILE: workspace_reader_payload.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# Server-owned reader document payload construction.
# -------------------------------------------------------------------

from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from solomon_core.logger import get_logger
from solomon_core.workspace_reader.workspace_reader_csv_preview import (
    build_csv_preview,
    build_csv_preview_text_blocks,
)
from solomon_core.workspace_reader.workspace_reader_doc_preview import (
    get_doc_preview_cache_state,
)
from solomon_core.workspace_reader.workspace_reader_docx_preview import (
    build_docx_structured_preview_blocks_with_python_docx,
    flatten_docx_structured_preview_blocks,
    get_docx_structured_preview_total_chars,
    get_preview_block_total_chars,
    limit_docx_preview_blocks,
    limit_docx_structured_preview_blocks,
    merge_docx_preview_blocks,
    merge_docx_structured_preview_blocks,
)
from solomon_core.workspace_reader.workspace_reader_docx_xml import (
    build_docx_preview_blocks_from_xml_parts,
)
from solomon_core.workspace_reader.workspace_reader_formats import (
    build_reader_metadata_items,
    build_reader_metadata_line,
    format_datetime_label,
    format_file_size,
    get_checksum_preview,
    get_file_extension,
    get_page_count_label,
    get_reader_message,
    get_reader_mode,
    get_reader_title,
    get_type_label,
    is_reader_supported,
)
from solomon_core.workspace_reader.workspace_reader_image_preview import (
    build_image_preview,
)
from solomon_core.workspace_reader.workspace_reader_pdf_preview import (
    build_pdf_reader_pages,
    get_pdf_page_count,
)
from solomon_core.workspace_reader.workspace_reader_text_preview import (
    build_text_preview_blocks,
)
from solomon_core.workspace_reader.workspace_reader_xls_preview import (
    build_xls_preview,
    build_xls_preview_text_blocks,
)
from solomon_core.workspace_reader.workspace_reader_xlsx_preview import (
    build_xlsx_preview,
    build_xlsx_preview_text_blocks,
)

logger = get_logger("workspace_reader.payload")


def get_spreadsheet_preview_total_cells(sheets: List[Dict]) -> int:
    """Return total rendered spreadsheet preview cells for reader logging."""

    total_cells = 0

    for sheet in sheets:
        for row in sheet.get("rows") or []:
            total_cells += len(row.get("cells") or [])

    return total_cells


def build_workspace_document_download_url(document_id: str) -> str:
    """Return the protected original-file download URL for a workspace file."""

    clean_document_id = str(document_id or "").strip()

    if not clean_document_id:
        return ""

    return f"/workspace/file/{quote(clean_document_id, safe='')}/download"


def build_workspace_document_original_url(document_id: str) -> str:
    """Return the protected inline original-file URL for a workspace file."""

    clean_document_id = str(document_id or "").strip()

    if not clean_document_id:
        return ""

    return f"/workspace/file/{quote(clean_document_id, safe='')}/reader/original"


def apply_csv_preview_display_name(
    sheets: List[Dict],
    *,
    display_name: str,
) -> List[Dict]:
    """Apply the server-owned original filename to CSV preview sheets."""

    clean_display_name = Path(str(display_name or "")).name.strip() or "CSV File"

    for sheet in sheets:
        sheet["name"] = clean_display_name

    return sheets


def get_legacy_doc_reader_message(cache_state: str, cache_message: str = "") -> str:
    """Return the reader message for a legacy DOC preview state."""

    clean_message = str(cache_message or "").strip()

    if clean_message:
        return clean_message

    if cache_state == "missing":
        return (
            "Legacy Word document. This file was stored successfully. Visual preview "
            "is not available for legacy `.doc` files. Solomon can still attempt "
            "analysis using text-only extraction. For best results, upload PDF or DOCX."
        )

    return (
        "Legacy Word document. This file was stored successfully. Visual preview "
        "is not available for legacy `.doc` files. Solomon can still attempt "
        "analysis using text-only extraction. For best results, upload PDF or DOCX."
    )


def build_docx_preview(
    source_path: str,
    *,
    request_id: str = "untracked",
) -> tuple[List[str], List[Dict], bool]:
    """Build safe first-party DOCX preview text and style-aware blocks."""

    structured_blocks: List[Dict] = []
    fallback_blocks: List[str] = []

    try:
        structured_blocks = build_docx_structured_preview_blocks_with_python_docx(
            source_path
        )
    except Exception as exc:
        logger.warning(
            "[workspace.reader.docx_python_preview_failed] request_id=%s "
            "path=%s error=%s",
            request_id,
            Path(source_path).name,
            exc,
        )

    try:
        fallback_blocks = build_docx_preview_blocks_from_xml_parts(
            source_path,
            request_id=request_id,
        )
    except Exception as exc:
        logger.warning(
            "[workspace.reader.docx_xml_preview_failed] request_id=%s "
            "path=%s error=%s",
            request_id,
            Path(source_path).name,
            exc,
        )

    merged_structured_blocks = merge_docx_structured_preview_blocks(
        structured_blocks,
        [],
    )
    limited_structured_blocks, structured_truncated = (
        limit_docx_structured_preview_blocks(merged_structured_blocks)
    )

    primary_text_blocks = flatten_docx_structured_preview_blocks(
        limited_structured_blocks or structured_blocks
    )
    merged_text_blocks = merge_docx_preview_blocks(primary_text_blocks, fallback_blocks)
    limited_text_blocks, text_truncated = limit_docx_preview_blocks(merged_text_blocks)
    truncated = bool(structured_truncated or text_truncated)

    logger.info(
        "[workspace.reader.docx_preview_ready] request_id=%s path=%s "
        "style_blocks=%s fallback_blocks=%s rendered_blocks=%s "
        "rendered_style_blocks=%s rendered_chars=%s rendered_style_chars=%s "
        "truncated=%s",
        request_id,
        Path(source_path).name,
        len(structured_blocks),
        len(fallback_blocks),
        len(limited_text_blocks),
        len(limited_structured_blocks),
        get_preview_block_total_chars(limited_text_blocks),
        get_docx_structured_preview_total_chars(limited_structured_blocks),
        truncated,
    )

    return limited_text_blocks, limited_structured_blocks, truncated


def build_reader_document(
    document_id: str,
    resolved: dict,
    *,
    request_id: str = "untracked",
) -> dict:
    """Build a server-owned document payload for the reader template."""

    canonical_document_id = str(resolved.get("document_id") or document_id).strip()
    title = str(resolved.get("original_name") or canonical_document_id).strip()
    source_path = str(resolved.get("path") or "").strip()
    type_label = get_type_label(title)
    size_bytes = resolved.get("size_bytes")
    active = bool(resolved.get("active"))
    reader_mode = get_reader_mode(title)
    reader_supported = is_reader_supported(reader_mode) and bool(source_path)
    reader_message = get_reader_message(title)
    reader_preview_state = "ready" if reader_supported else "stored"
    page_count = 0
    reader_pages: List[Dict] = []
    reader_text_blocks: List[str] = []
    reader_docx_blocks: List[Dict] = []
    reader_spreadsheet_sheets: List[Dict] = []
    reader_image_preview: Dict = {}
    reader_preview_truncated = False
    capabilities = dict(resolved.get("capabilities") or {})
    available_actions = list(resolved.get("available_actions") or [])
    solomon_actions_authoritative = (
        resolved.get("solomon_actions_authoritative") is True
    )
    solomon_actions = [
        dict(action)
        for action in (resolved.get("solomon_actions") or [])
        if isinstance(action, dict)
    ]
    if not solomon_actions_authoritative:
        solomon_actions = []
    solomon_action_count = len(solomon_actions)
    summary_available = bool(
        capabilities.get("can_view_summary")
        and "view_summary" in available_actions
    )
    download_url = (
        build_workspace_document_download_url(canonical_document_id)
        if source_path
        else ""
    )
    original_url = (
        build_workspace_document_original_url(canonical_document_id)
        if source_path
        else ""
    )
    print_url = original_url if reader_mode in {"pdf", "image", "text"} else ""

    if reader_mode == "pdf" and source_path:
        page_count = get_pdf_page_count(source_path, request_id=request_id)
        reader_supported = page_count > 0
        reader_preview_state = "ready" if reader_supported else "failed"
        reader_pages = build_pdf_reader_pages(canonical_document_id, page_count)

    if reader_mode == "docx" and source_path:
        try:
            (
                reader_text_blocks,
                reader_docx_blocks,
                reader_preview_truncated,
            ) = build_docx_preview(
                source_path,
                request_id=request_id,
            )
            reader_supported = bool(reader_docx_blocks or reader_text_blocks)
            reader_preview_state = "ready" if reader_supported else "failed"
        except Exception as exc:
            reader_supported = False
            reader_preview_state = "failed"
            logger.warning(
                "[workspace.reader.docx_preview_failed] request_id=%s "
                "document_id=%s filename=%s error=%s",
                request_id,
                canonical_document_id,
                title,
                exc,
            )

    if reader_mode == "doc" and source_path:
        cache_state_payload = get_doc_preview_cache_state(source_path)
        reader_preview_state = str(
            cache_state_payload.get("state") or "unsupported"
        ).strip()
        reader_message = get_legacy_doc_reader_message(
            reader_preview_state,
            str(cache_state_payload.get("message") or ""),
        )
        reader_supported = False
        reader_text_blocks = []
        reader_docx_blocks = []
        reader_preview_truncated = False

        logger.info(
            "[workspace.reader.doc_visual_preview_unsupported] request_id=%s "
            "document_id=%s filename=%s preview_state=%s preview_contract=%s "
            "analysis_contract=%s",
            request_id,
            canonical_document_id,
            title,
            reader_preview_state,
            cache_state_payload.get("preview_contract"),
            cache_state_payload.get("analysis_contract"),
        )

    if reader_mode == "xlsx" and source_path:
        try:
            reader_spreadsheet_sheets, reader_preview_truncated = build_xlsx_preview(
                source_path,
                request_id=request_id,
            )
            reader_text_blocks = build_xlsx_preview_text_blocks(
                reader_spreadsheet_sheets
            )
            reader_supported = bool(reader_spreadsheet_sheets)
            reader_preview_state = "ready" if reader_supported else "failed"
        except Exception as exc:
            reader_supported = False
            reader_preview_state = "failed"
            logger.warning(
                "[workspace.reader.xlsx_preview_failed] request_id=%s "
                "document_id=%s filename=%s error=%s",
                request_id,
                canonical_document_id,
                title,
                exc,
            )

    if reader_mode == "xls" and source_path:
        try:
            reader_spreadsheet_sheets, reader_preview_truncated = build_xls_preview(
                source_path,
                request_id=request_id,
            )
            reader_text_blocks = build_xls_preview_text_blocks(
                reader_spreadsheet_sheets
            )
            reader_supported = bool(reader_spreadsheet_sheets)
            reader_preview_state = "ready" if reader_supported else "failed"
        except Exception as exc:
            reader_supported = False
            reader_preview_state = "failed"
            logger.warning(
                "[workspace.reader.xls_preview_failed] request_id=%s "
                "document_id=%s filename=%s error=%s",
                request_id,
                canonical_document_id,
                title,
                exc,
            )

    if reader_mode == "csv" and source_path:
        try:
            reader_spreadsheet_sheets, reader_preview_truncated = build_csv_preview(
                source_path,
                request_id=request_id,
            )
            reader_spreadsheet_sheets = apply_csv_preview_display_name(
                reader_spreadsheet_sheets,
                display_name=title,
            )
            reader_text_blocks = build_csv_preview_text_blocks(
                reader_spreadsheet_sheets
            )
            reader_supported = bool(reader_spreadsheet_sheets)
            reader_preview_state = "ready" if reader_supported else "failed"
        except Exception as exc:
            reader_supported = False
            reader_preview_state = "failed"
            logger.warning(
                "[workspace.reader.csv_preview_failed] request_id=%s "
                "document_id=%s filename=%s error=%s",
                request_id,
                canonical_document_id,
                title,
                exc,
            )

    if reader_mode == "text" and source_path:
        try:
            reader_text_blocks, reader_preview_truncated = build_text_preview_blocks(
                source_path,
                request_id=request_id,
            )
            reader_supported = bool(reader_text_blocks)
            reader_preview_state = "ready" if reader_supported else "failed"
        except Exception as exc:
            reader_supported = False
            reader_preview_state = "failed"
            logger.warning(
                "[workspace.reader.text_preview_failed] request_id=%s "
                "document_id=%s filename=%s error=%s",
                request_id,
                canonical_document_id,
                title,
                exc,
            )

    if reader_mode == "image" and source_path:
        try:
            reader_image_preview = build_image_preview(
                source_path,
                document_id=canonical_document_id,
                display_name=title,
                request_id=request_id,
            )
            reader_supported = bool(reader_image_preview.get("image_url"))
            reader_preview_state = "ready" if reader_supported else "failed"
        except Exception as exc:
            reader_supported = False
            reader_preview_state = "failed"
            logger.warning(
                "[workspace.reader.image_preview_failed] request_id=%s "
                "document_id=%s filename=%s error=%s",
                request_id,
                canonical_document_id,
                title,
                exc,
            )

    logger.info(
        "[workspace.reader.document_ready] request_id=%s document_id=%s "
        "filename=%s mode=%s supported=%s preview_state=%s size=%s "
        "checksum=%s blocks=%s docx_structure_blocks=%s spreadsheet_sheets=%s "
        "spreadsheet_cells=%s image_preview=%s download_available=%s "
        "original_available=%s print_available=%s",
        request_id,
        canonical_document_id,
        title,
        reader_mode,
        reader_supported,
        reader_preview_state,
        size_bytes,
        get_checksum_preview(resolved.get("checksum")),
        len(reader_text_blocks),
        len(reader_docx_blocks),
        len(reader_spreadsheet_sheets),
        get_spreadsheet_preview_total_cells(reader_spreadsheet_sheets),
        bool(reader_image_preview),
        bool(download_url),
        bool(original_url),
        bool(print_url),
    )

    metadata_items = build_reader_metadata_items(
        type_label=type_label,
        size_bytes=size_bytes,
        page_count=page_count,
        active=active,
        uploaded_at=resolved.get("uploaded_at"),
        updated_at=resolved.get("updated_at"),
        checksum=resolved.get("checksum"),
    )

    return {
        "document_id": canonical_document_id,
        "file_id": resolved.get("file_id"),
        "title": title,
        "type_label": type_label,
        "file_extension": resolved.get("extension") or get_file_extension(title),
        "size_bytes": size_bytes,
        "size_label": format_file_size(size_bytes),
        "checksum": resolved.get("checksum"),
        "checksum_preview": get_checksum_preview(resolved.get("checksum")),
        "uploaded_at": format_datetime_label(resolved.get("uploaded_at")),
        "updated_at": format_datetime_label(resolved.get("updated_at")),
        "active": active,
        "status_label": "Workflow active" if active else "Stored",
        "reader_mode": reader_mode,
        "reader_supported": reader_supported,
        "reader_title": get_reader_title(title),
        "reader_message": reader_message,
        "reader_preview_state": reader_preview_state,
        "reader_pages": reader_pages,
        "reader_text_blocks": reader_text_blocks,
        "reader_docx_blocks": reader_docx_blocks,
        "reader_spreadsheet_sheets": reader_spreadsheet_sheets,
        "reader_image_preview": reader_image_preview,
        "reader_preview_truncated": reader_preview_truncated,
        "page_count": page_count,
        "page_count_label": get_page_count_label(page_count),
        "metadata_items": metadata_items,
        "reader_metadata_line": build_reader_metadata_line(metadata_items),
        "download_url": download_url,
        "file_download_url": download_url,
        "original_download_url": download_url,
        "reader_download_url": download_url,
        "download_available": bool(download_url),
        "original_url": original_url,
        "reader_original_url": original_url,
        "print_url": print_url,
        "reader_print_url": print_url,
        "print_available": bool(print_url),
        "summary_available": summary_available,
        "capabilities": capabilities,
        "available_actions": available_actions,
        "solomon_actions_authoritative": solomon_actions_authoritative,
        "solomon_actions": solomon_actions,
        "solomon_action_count": solomon_action_count,
        "read_only": True,
    }


def build_reader_template_context(
    *,
    document: Optional[Dict] = None,
    error_message: Optional[str] = None,
    document_id: Optional[str] = None,
    back_url: str = "/docs",
    request_id: str = "untracked",
) -> dict:
    """Build the complete server-owned reader template context."""

    reader_state = "error"

    if document:
        reader_state = "open" if document.get("reader_supported") else "stored"

    return {
        "document": document,
        "error_message": error_message,
        "reader_pages": list((document or {}).get("reader_pages") or []),
        "reader_text_blocks": list((document or {}).get("reader_text_blocks") or []),
        "reader_docx_blocks": list((document or {}).get("reader_docx_blocks") or []),
        "reader_spreadsheet_sheets": list(
            (document or {}).get("reader_spreadsheet_sheets") or []
        ),
        "reader_image_preview": dict(
            (document or {}).get("reader_image_preview") or {}
        ),
        "page_count": int((document or {}).get("page_count") or 0),
        "back_url": back_url,
        "request_id": str(request_id or "untracked"),
        "document_id": document_id,
        "reader_state": reader_state,
        "workspace_reader_active": True,
        "reader_supported": bool((document or {}).get("reader_supported")),
        "reader_summary_available": bool(
            (document or {}).get("summary_available")
        ),
    }