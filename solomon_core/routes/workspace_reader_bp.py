# -------------------------------------------------------------------
# FILE: workspace_reader_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Internal Solomon document reader routes for authorized workspace files.
# -------------------------------------------------------------------

from mimetypes import guess_type
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from flask import Blueprint, abort, g, render_template, request, send_file, session

from solomon_core.auth_utils import login_required
from solomon_core.logger import get_logger
from solomon_core.workspace_reader.workspace_reader_file_access import (
    DOWNLOAD_ACTION,
    READ_ACTION,
    record_file_recent_activity,
    resolve_authorized_file_registry_entry,
)
from solomon_core.workspace_reader.workspace_reader_formats import get_reader_mode
from solomon_core.workspace_reader.workspace_reader_image_preview import (
    TIFF_PREVIEW_MIME_TYPE,
    get_image_mime_type,
    get_tiff_mime_type,
    render_tiff_preview_png,
)
from solomon_core.workspace_reader.workspace_reader_payload import (
    build_reader_document,
    build_reader_template_context,
)
from solomon_core.workspace_reader.workspace_reader_pdf_preview import (
    render_pdf_page_image,
)
from solomon_core.workspace_reader.workspace_reader_urls import (
    build_workspace_document_reader_url,
    normalize_document_id,
)

workspace_reader_bp = Blueprint(
    "workspace_reader_bp",
    __name__,
    url_prefix="/workspace",
)

logger = get_logger("workspace_reader")
BACK_URL = "/docs"
WORKSPACE_SURFACE_TEMPLATE = "components/workspace_content.html"
WORKSPACE_READER_SURFACE_TEMPLATE = "components/workspace_document_reader_panel.html"


def get_request_id() -> str:
    """Return the current request id when available."""

    return getattr(g, "request_id", "untracked")


def get_current_user_id() -> int:
    """Return the authenticated user id from session state."""

    try:
        return int(session.get("user_id") or 0)
    except (TypeError, ValueError):
        return 0


def get_current_request_path() -> str:
    """Return the current request path without trailing slash drift."""

    return str(request.path or "").rstrip("/") or "/"


def is_reader_route_path(path: str) -> bool:
    """Return true when the supplied path points back into a reader route."""

    clean_path = str(path or "").strip().rstrip("/") or "/"
    path_parts = [
        part
        for part in clean_path.split("/")
        if part
    ]

    return (
        len(path_parts) >= 4
        and path_parts[0] == "workspace"
        and path_parts[1] in {"file", "document"}
        and path_parts[3] == "reader"
    )


def normalize_safe_reader_back_url(raw_url: str) -> str:
    """Return a safe in-app reader close destination or an empty string."""

    candidate_url = str(raw_url or "").strip()

    if not candidate_url:
        return ""

    parsed_url = urlsplit(candidate_url)

    if parsed_url.scheme or parsed_url.netloc:
        if parsed_url.scheme not in {"http", "https"}:
            return ""

        if parsed_url.netloc != request.host:
            return ""

    if not parsed_url.path.startswith("/"):
        return ""

    clean_path = parsed_url.path.rstrip("/") or "/"
    path_parts = [
        part
        for part in clean_path.split("/")
        if part
    ]

    if clean_path == get_current_request_path() or is_reader_route_path(clean_path):
        return ""

    if clean_path == "/search":
        return urlunsplit(
            (
                "",
                "",
                clean_path,
                parsed_url.query,
                "",
            )
        )

    if clean_path in {"/", "/docs"}:
        return clean_path

    if path_parts == ["ai"]:
        return "/ai"

    if (
        len(path_parts) == 3
        and path_parts[0] == "ai"
        and path_parts[1] == "c"
        and path_parts[2] not in {".", ".."}
    ):
        return clean_path

    return ""


def get_reader_back_url() -> str:
    """Return a safe in-app destination for closing the full Reader."""

    requested_back_url = normalize_safe_reader_back_url(
        request.args.get("back") or ""
    )

    if requested_back_url:
        return requested_back_url

    referrer_back_url = normalize_safe_reader_back_url(
        request.referrer or ""
    )

    if referrer_back_url:
        return referrer_back_url

    return BACK_URL


def get_requested_document_id(
    *,
    file_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> str:
    """Return the active route identifier from canonical or legacy routes."""

    return normalize_document_id(file_id if file_id is not None else document_id)


def get_inline_mime_type(source_path: Path, title: str) -> str:
    """Return a safe MIME type for inline original-file serving."""

    reader_mode = get_reader_mode(title)

    if reader_mode == "pdf":
        return "application/pdf"

    if reader_mode == "image":
        return (
            get_image_mime_type(str(source_path))
            or get_tiff_mime_type(str(source_path))
            or "application/octet-stream"
        )

    if reader_mode == "text" or source_path.suffix.lower() in {".txt", ".csv"}:
        return "text/plain; charset=utf-8"

    guessed_type, _encoding = guess_type(str(source_path))

    return guessed_type or "application/octet-stream"


def resolve_authorized_reader_file(
    user_id: int,
    identifier: str,
    *,
    allow_trashed_owner_read: bool = True,
) -> Optional[dict]:
    """Resolve one reader file through central SQL file authority."""

    clean_identifier = normalize_document_id(identifier)

    if not clean_identifier or not user_id:
        return None

    return resolve_authorized_file_registry_entry(
        user_id,
        clean_identifier,
        request_id=get_request_id(),
        action=READ_ACTION,
        allow_trashed_owner_read=allow_trashed_owner_read,
    )


def build_documents_reader_shell_context(reader_context: dict) -> dict:
    """Return the Operations Console context for an embedded reader surface."""

    shell_context = {
        "active_module": "documents",
        "current_module": "documents",
        "module_label": "Documents",
        "workspace_surface_template": WORKSPACE_SURFACE_TEMPLATE,
        "workspace_initial_view": "reader",
        "workspace_reader_route": True,
        "workspace_window_closeable": False,
        "workspace_back_url": reader_context.get("back_url") or BACK_URL,
        "workspace_reader_surface_template": WORKSPACE_READER_SURFACE_TEMPLATE,
        "command_department": {
            "id": "documents",
            "key": "documents",
            "label": "Documents",
            "description": (
                "Stored plans, specs, proposals, spreadsheets, images, "
                "and supporting files."
            ),
            "functions": [],
        },
        "command_module": {
            "id": "documents",
            "key": "documents",
            "label": "Documents",
            "description": (
                "Stored plans, specs, proposals, spreadsheets, images, "
                "and supporting files."
            ),
            "path": "/docs",
        },
    }

    shell_context.update(reader_context)
    return shell_context


def build_authorized_reader_context(clean_document_id: str):
    """Return a reader template context and HTTP status for an authorized file."""

    back_url = get_reader_back_url()

    if not clean_document_id:
        return (
            build_reader_template_context(
                document=None,
                error_message="No document was selected.",
                document_id=None,
                back_url=back_url,
                request_id=get_request_id(),
            ),
            404,
        )

    resolved = resolve_authorized_reader_file(
        get_current_user_id(),
        clean_document_id,
        allow_trashed_owner_read=True,
    )

    if not resolved:
        logger.warning(
            "[workspace.reader.not_found] request_id=%s document_id=%s",
            get_request_id(),
            clean_document_id,
        )
        return (
            build_reader_template_context(
                document=None,
                error_message=(
                    "The selected document is not available in your file library."
                ),
                document_id=clean_document_id,
                back_url=back_url,
                request_id=get_request_id(),
            ),
            404,
        )

    reader_document = build_reader_document(
        clean_document_id,
        resolved,
        request_id=get_request_id(),
    )

    record_file_recent_activity(
        get_current_user_id(),
        reader_document.get("document_id") or clean_document_id,
        activity_kind="opened",
    )

    logger.info(
        "[workspace.reader.open] request_id=%s document_id=%s active=%s "
        "mode=%s supported=%s page_count=%s",
        get_request_id(),
        reader_document.get("document_id"),
        resolved.get("active"),
        reader_document.get("reader_mode"),
        reader_document.get("reader_supported"),
        reader_document.get("page_count"),
    )

    return (
        build_reader_template_context(
            document=reader_document,
            error_message=None,
            document_id=reader_document.get("document_id"),
            back_url=back_url,
            request_id=get_request_id(),
        ),
        200,
    )


def render_reader_shell(
    *,
    reader_context: dict,
    status_code: int = 200,
):
    """Render the reader inside the Documents/File Manager app shell."""

    return (
        render_template(
            "index.html",
            **build_documents_reader_shell_context(reader_context),
        ),
        status_code,
    )


def render_reader_fragment(
    *,
    reader_context: dict,
    status_code: int = 200,
):
    """Render only the reader panel content for the existing Documents shell."""

    return (
        render_template(
            WORKSPACE_READER_SURFACE_TEMPLATE,
            **reader_context,
        ),
        status_code,
    )


def render_reader_error(
    message: str,
    *,
    status_code: int = 404,
    document_id: Optional[str] = None,
):
    """Render an app-controlled document reader error state."""

    return render_reader_shell(
        reader_context=build_reader_template_context(
            document=None,
            error_message=message,
            document_id=document_id,
            back_url=get_reader_back_url(),
            request_id=get_request_id(),
        ),
        status_code=status_code,
    )


def render_authorized_pdf_page_image(
    *,
    clean_document_id: str,
    page_number: int,
    log_event: str,
):
    """Render a protected authorized PDF page image."""

    if not clean_document_id or page_number < 1:
        abort(404)

    resolved = resolve_authorized_reader_file(
        get_current_user_id(),
        clean_document_id,
        allow_trashed_owner_read=True,
    )

    if not resolved:
        logger.warning(
            "[workspace.reader.%s_not_found] request_id=%s document_id=%s page=%s",
            log_event,
            get_request_id(),
            clean_document_id,
            page_number,
        )
        abort(404)

    title = str(resolved.get("original_name") or clean_document_id).strip()
    source_path = str(resolved.get("path") or "").strip()

    if get_reader_mode(title) != "pdf":
        abort(404)

    try:
        image_stream = render_pdf_page_image(
            source_path,
            page_number,
        )
    except Exception as exc:
        logger.warning(
            "[workspace.reader.%s_render_failed] request_id=%s document_id=%s "
            "page=%s error=%s",
            log_event,
            get_request_id(),
            clean_document_id,
            page_number,
            exc,
        )
        abort(404)

    logger.info(
        "[workspace.reader.%s_open] request_id=%s document_id=%s filename=%s "
        "page=%s",
        log_event,
        get_request_id(),
        clean_document_id,
        title,
        page_number,
    )

    return send_file(
        image_stream,
        mimetype="image/png",
        as_attachment=False,
        download_name=f"{Path(title).stem}-{log_event}.png",
        max_age=3600,
    )


def render_authorized_document_thumbnail_image(clean_document_id: str):
    """Render a protected first-page thumbnail for supported document types."""

    if not clean_document_id:
        abort(404)

    resolved = resolve_authorized_reader_file(
        get_current_user_id(),
        clean_document_id,
        allow_trashed_owner_read=True,
    )

    if not resolved:
        logger.warning(
            "[workspace.reader.thumbnail_not_found] request_id=%s document_id=%s",
            get_request_id(),
            clean_document_id,
        )
        abort(404)

    title = str(resolved.get("original_name") or clean_document_id).strip()
    source_path = str(resolved.get("path") or "").strip()
    reader_mode = get_reader_mode(title)

    if reader_mode != "pdf":
        logger.info(
            "[workspace.reader.thumbnail_unsupported] request_id=%s "
            "document_id=%s filename=%s mode=%s",
            get_request_id(),
            clean_document_id,
            title,
            reader_mode,
        )
        abort(404)

    try:
        image_stream = render_pdf_page_image(source_path, 1)
    except Exception as exc:
        logger.warning(
            "[workspace.reader.thumbnail_render_failed] request_id=%s "
            "document_id=%s filename=%s mode=%s error=%s",
            get_request_id(),
            clean_document_id,
            title,
            reader_mode,
            exc,
        )
        abort(404)

    logger.info(
        "[workspace.reader.thumbnail_open] request_id=%s document_id=%s "
        "filename=%s mode=%s",
        get_request_id(),
        clean_document_id,
        title,
        reader_mode,
    )

    return send_file(
        image_stream,
        mimetype="image/png",
        as_attachment=False,
        download_name=f"{Path(title).stem}-thumbnail.png",
        max_age=3600,
    )


@workspace_reader_bp.route("/file/<file_id>/reader", methods=["GET"])
@workspace_reader_bp.route("/document/<document_id>/reader", methods=["GET"])
@login_required
def workspace_document_reader(file_id=None, document_id=None):
    """Render a full Documents shell with the reader panel active."""

    clean_document_id = get_requested_document_id(
        file_id=file_id,
        document_id=document_id,
    )
    reader_context, status_code = build_authorized_reader_context(
        clean_document_id
    )

    return render_reader_shell(
        reader_context=reader_context,
        status_code=status_code,
    )


@workspace_reader_bp.route("/file/<file_id>/reader/fragment", methods=["GET"])
@workspace_reader_bp.route("/document/<document_id>/reader/fragment", methods=["GET"])
@login_required
def workspace_document_reader_fragment(file_id=None, document_id=None):
    """Render a reader fragment for injection into the existing Documents shell."""

    clean_document_id = get_requested_document_id(
        file_id=file_id,
        document_id=document_id,
    )
    reader_context, status_code = build_authorized_reader_context(
        clean_document_id
    )

    return render_reader_fragment(
        reader_context=reader_context,
        status_code=status_code,
    )


@workspace_reader_bp.route("/file/<file_id>/download", methods=["GET"])
@workspace_reader_bp.route("/document/<document_id>/download", methods=["GET"])
@login_required
def workspace_document_download(file_id=None, document_id=None):
    """Download the protected original workspace file."""

    clean_document_id = get_requested_document_id(
        file_id=file_id,
        document_id=document_id,
    )

    if not clean_document_id:
        abort(404)

    resolved = resolve_authorized_file_registry_entry(
        get_current_user_id(),
        clean_document_id,
        request_id=get_request_id(),
        action=DOWNLOAD_ACTION,
        allow_trashed_owner_read=True,
    )

    if not resolved:
        logger.warning(
            "[workspace.reader.download_not_found] request_id=%s document_id=%s",
            get_request_id(),
            clean_document_id,
        )
        abort(404)

    title = str(resolved.get("original_name") or clean_document_id).strip()
    source_path = Path(str(resolved.get("path") or "").strip())

    if not source_path.is_file():
        logger.warning(
            "[workspace.reader.download_missing_source] request_id=%s "
            "document_id=%s filename=%s path=%s",
            get_request_id(),
            clean_document_id,
            title,
            source_path,
        )
        abort(404)

    logger.info(
        "[workspace.reader.download] request_id=%s document_id=%s filename=%s",
        get_request_id(),
        clean_document_id,
        title,
    )

    return send_file(
        source_path,
        as_attachment=True,
        download_name=Path(title).name,
        max_age=0,
    )


@workspace_reader_bp.route("/file/<file_id>/reader/original", methods=["GET"])
@workspace_reader_bp.route("/document/<document_id>/reader/original", methods=["GET"])
@login_required
def workspace_document_reader_original(file_id=None, document_id=None):
    """Serve the protected original workspace file inline for browser print/view."""

    clean_document_id = get_requested_document_id(
        file_id=file_id,
        document_id=document_id,
    )

    if not clean_document_id:
        abort(404)

    resolved = resolve_authorized_reader_file(
        get_current_user_id(),
        clean_document_id,
        allow_trashed_owner_read=True,
    )

    if not resolved:
        logger.warning(
            "[workspace.reader.original_not_found] request_id=%s document_id=%s",
            get_request_id(),
            clean_document_id,
        )
        abort(404)

    title = str(resolved.get("original_name") or clean_document_id).strip()
    source_path = Path(str(resolved.get("path") or "").strip())

    if not source_path.is_file():
        logger.warning(
            "[workspace.reader.original_missing_source] request_id=%s "
            "document_id=%s filename=%s path=%s",
            get_request_id(),
            clean_document_id,
            title,
            source_path,
        )
        abort(404)

    logger.info(
        "[workspace.reader.original_inline] request_id=%s document_id=%s "
        "filename=%s",
        get_request_id(),
        clean_document_id,
        title,
    )

    return send_file(
        source_path,
        mimetype=get_inline_mime_type(source_path, title),
        as_attachment=False,
        download_name=Path(title).name,
        max_age=0,
    )


@workspace_reader_bp.route(
    "/file/<file_id>/reader/thumbnail.png",
    methods=["GET"],
)
@workspace_reader_bp.route(
    "/document/<document_id>/reader/thumbnail.png",
    methods=["GET"],
)
@login_required
def workspace_document_reader_thumbnail(file_id=None, document_id=None):
    """Render a protected first-page thumbnail for supported document types."""

    clean_document_id = get_requested_document_id(
        file_id=file_id,
        document_id=document_id,
    )

    return render_authorized_document_thumbnail_image(clean_document_id)


@workspace_reader_bp.route(
    "/file/<file_id>/reader/page/<int:page_number>.png",
    methods=["GET"],
)
@workspace_reader_bp.route(
    "/document/<document_id>/reader/page/<int:page_number>.png",
    methods=["GET"],
)
@login_required
def workspace_document_reader_page(file_id=None, document_id=None, page_number=0):
    """Render one protected PDF page as a first-party Solomon page image."""

    clean_document_id = get_requested_document_id(
        file_id=file_id,
        document_id=document_id,
    )

    return render_authorized_pdf_page_image(
        clean_document_id=clean_document_id,
        page_number=page_number,
        log_event="page",
    )


@workspace_reader_bp.route(
    "/file/<file_id>/reader/image",
    methods=["GET"],
)
@workspace_reader_bp.route(
    "/document/<document_id>/reader/image",
    methods=["GET"],
)
@login_required
def workspace_document_reader_image(file_id=None, document_id=None):
    """Serve one protected browser-readable image file through Solomon authority."""

    clean_document_id = get_requested_document_id(
        file_id=file_id,
        document_id=document_id,
    )

    if not clean_document_id:
        abort(404)

    resolved = resolve_authorized_reader_file(
        get_current_user_id(),
        clean_document_id,
        allow_trashed_owner_read=True,
    )

    if not resolved:
        logger.warning(
            "[workspace.reader.image_not_found] request_id=%s document_id=%s",
            get_request_id(),
            clean_document_id,
        )
        abort(404)

    title = str(resolved.get("original_name") or clean_document_id).strip()
    source_path = str(resolved.get("path") or "").strip()

    if get_reader_mode(title) != "image":
        abort(404)

    mime_type = get_image_mime_type(source_path)

    if not mime_type:
        logger.warning(
            "[workspace.reader.image_invalid] request_id=%s document_id=%s "
            "filename=%s",
            get_request_id(),
            clean_document_id,
            title,
        )
        abort(404)

    logger.info(
        "[workspace.reader.image_open] request_id=%s document_id=%s filename=%s "
        "mime_type=%s",
        get_request_id(),
        clean_document_id,
        title,
        mime_type,
    )

    return send_file(
        source_path,
        mimetype=mime_type,
        as_attachment=False,
        download_name=Path(title).name,
        max_age=3600,
    )


@workspace_reader_bp.route(
    "/file/<file_id>/reader/image/preview.png",
    methods=["GET"],
)
@workspace_reader_bp.route(
    "/document/<document_id>/reader/image/preview.png",
    methods=["GET"],
)
@login_required
def workspace_document_reader_tiff_preview(file_id=None, document_id=None):
    """Render one protected TIFF source as a bounded PNG preview."""

    clean_document_id = get_requested_document_id(
        file_id=file_id,
        document_id=document_id,
    )

    if not clean_document_id:
        abort(404)

    resolved = resolve_authorized_reader_file(
        get_current_user_id(),
        clean_document_id,
        allow_trashed_owner_read=True,
    )

    if not resolved:
        logger.warning(
            "[workspace.reader.tiff_not_found] request_id=%s document_id=%s",
            get_request_id(),
            clean_document_id,
        )
        abort(404)

    title = str(resolved.get("original_name") or clean_document_id).strip()
    source_path = str(resolved.get("path") or "").strip()

    if get_reader_mode(title) != "image":
        abort(404)

    if not get_tiff_mime_type(source_path):
        logger.warning(
            "[workspace.reader.tiff_invalid] request_id=%s document_id=%s "
            "filename=%s",
            get_request_id(),
            clean_document_id,
            title,
        )
        abort(404)

    try:
        image_stream = render_tiff_preview_png(source_path)
    except Exception as exc:
        logger.warning(
            "[workspace.reader.tiff_render_failed] request_id=%s document_id=%s "
            "filename=%s error=%s",
            get_request_id(),
            clean_document_id,
            title,
            exc,
        )
        abort(404)

    logger.info(
        "[workspace.reader.tiff_preview_open] request_id=%s document_id=%s "
        "filename=%s mime_type=%s",
        get_request_id(),
        clean_document_id,
        title,
        TIFF_PREVIEW_MIME_TYPE,
    )

    return send_file(
        image_stream,
        mimetype=TIFF_PREVIEW_MIME_TYPE,
        as_attachment=False,
        download_name=f"{Path(title).stem}-preview.png",
        max_age=3600,
    )


__all__ = [
    "build_workspace_document_reader_url",
    "workspace_reader_bp",
]