# -------------------------------------------------------------------
# FILE: workspace_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Workspace bridge routes for Solomon document preview and panel state.
# -------------------------------------------------------------------

import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

from flask import Blueprint, g, jsonify, request, send_file, session

from solomon_core.auth_utils import login_required
from solomon_core.logger import get_logger
from solomon_core.workspace_reader.workspace_reader_file_access import (
    READ_ACTION,
    resolve_authorized_file_registry_entry,
)
from solomon_workspace.actions.open_document import open_workspace_document
from solomon_workspace.context.workspace_context_packet import build_workspace_context_packet
from solomon_workspace.documents.document_session import (
    WorkspaceDocumentSession,
    build_workspace_document_session_from_dict,
)
from solomon_workspace.panels.panel_state import (
    WorkspacePanelState,
    build_workspace_panel_state_from_dict,
)

workspace_bp = Blueprint("workspace_bp", __name__, url_prefix="/workspace")

logger = get_logger("Solomon.workspace")

WORKSPACE_SESSION_KEY = "solomon_workspace_state"
WORKSPACE_DEFAULT_ID = "solomon_command_workspace"

PDF_EXTENSIONS = {".pdf"}
WORD_EXTENSIONS = {".doc", ".docx"}
SPREADSHEET_EXTENSIONS = {".xls", ".xlsx"}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}
TEXT_EXTENSIONS = {".txt"}
CSV_EXTENSIONS = {".csv"}


def get_request_id() -> str:
    """Return the current request id when available."""

    return getattr(g, "request_id", "untracked")


def get_current_user_id() -> int:
    """Return the authenticated user id from session state."""

    try:
        return int(session.get("user_id") or 0)
    except (TypeError, ValueError):
        return 0


def get_workspace_id() -> str:
    """Return the active workspace id from session state."""

    stored_state = session.get(WORKSPACE_SESSION_KEY)

    if isinstance(stored_state, dict):
        stored_workspace_id = str(stored_state.get("workspace_id") or "").strip()

        if stored_workspace_id:
            return stored_workspace_id

    return WORKSPACE_DEFAULT_ID


def get_workspace_state_payload() -> Dict[str, Any]:
    """Return the stored workspace state payload."""

    stored_state = session.get(WORKSPACE_SESSION_KEY)
    return stored_state if isinstance(stored_state, dict) else {}


def load_workspace_runtime() -> Tuple[WorkspaceDocumentSession, WorkspacePanelState]:
    """Load workspace document and panel runtime state from session."""

    state_payload = get_workspace_state_payload()
    workspace_id = str(
        state_payload.get("workspace_id") or get_workspace_id()
    ).strip()

    document_session = build_workspace_document_session_from_dict(
        state_payload.get("documents"),
        workspace_id=workspace_id or WORKSPACE_DEFAULT_ID,
    )
    panel_state = build_workspace_panel_state_from_dict(
        state_payload.get("panels")
    )

    return document_session, panel_state


def save_workspace_runtime(
    document_session: WorkspaceDocumentSession,
    panel_state: WorkspacePanelState,
) -> Dict[str, Any]:
    """Persist workspace runtime state and return the context packet."""

    context_packet = build_workspace_context_packet(
        document_session=document_session,
        panel_state=panel_state,
    )

    session[WORKSPACE_SESSION_KEY] = {
        "workspace_id": document_session.workspace_id,
        "documents": document_session.to_dict(),
        "panels": panel_state.to_dict(),
    }
    session.modified = True

    return context_packet


def normalize_document_id(document_id: str) -> str:
    """Return a normalized document id for FileRegistry lookup."""

    return str(document_id or "").strip()


def encode_document_id(document_id: str) -> str:
    """Return a URL-safe document id."""

    return quote(normalize_document_id(document_id), safe="")


def get_file_extension(filename: str) -> str:
    """Return a normalized file extension."""

    return Path(str(filename or "")).suffix.lower().strip()


def get_type_label(filename: str) -> str:
    """Return a server-owned user-facing file type label."""

    extension = get_file_extension(filename)

    if extension in PDF_EXTENSIONS:
        return "PDF Document"

    if extension in WORD_EXTENSIONS:
        return "Word Document"

    if extension in SPREADSHEET_EXTENSIONS:
        return "Spreadsheet"

    if extension in CSV_EXTENSIONS:
        return "CSV File"

    if extension in TEXT_EXTENSIONS:
        return "Text Document"

    if extension in IMAGE_EXTENSIONS:
        return "Image File"

    return "Workspace File"


def resolve_authorized_workspace_file(
    user_id: int,
    identifier: str,
) -> Optional[Dict[str, Any]]:
    """Resolve a workspace file through the central SQL file authority."""

    clean_identifier = normalize_document_id(identifier)

    if not clean_identifier or not user_id:
        return None

    return resolve_authorized_file_registry_entry(
        user_id,
        clean_identifier,
        request_id=get_request_id(),
        action=READ_ACTION,
        allow_trashed_owner_read=False,
    )


def resolve_owned_file_registry_entry(
    user_id: int,
    identifier: str,
) -> Optional[Dict[str, Any]]:
    """Compatibility wrapper for central authorized file resolution."""

    return resolve_authorized_workspace_file(
        user_id,
        identifier,
    )


def resolve_owned_workspace_file(
    user_id: int,
    identifier: str,
) -> Optional[Dict[str, Any]]:
    """Compatibility wrapper for central authorized workspace files."""

    return resolve_authorized_workspace_file(
        user_id,
        identifier,
    )


def find_panel_id_for_document(
    panel_state: WorkspacePanelState,
    document_id: str,
) -> Optional[str]:
    """Return the open panel id for a document when available."""

    clean_document_id = normalize_document_id(document_id)

    if not clean_document_id:
        return None

    for panel in panel_state.list_panels():
        if panel.document_id == clean_document_id:
            return panel.panel_id

    return None


def refocus_after_panel_close(
    document_session: WorkspaceDocumentSession,
    panel_state: WorkspacePanelState,
) -> None:
    """Set a sensible active document after an open panel closes."""

    focused_panel = panel_state.get_focused_panel()

    if focused_panel:
        if focused_panel.document_id:
            document_session.set_active_document(focused_panel.document_id)

        return

    for panel in reversed(panel_state.list_panels()):
        if panel.minimized:
            continue

        focused = panel_state.focus_panel(panel.panel_id)

        if focused and focused.document_id:
            document_session.set_active_document(focused.document_id)

        return


def prune_workspace_runtime_to_authorized_files(
    document_session: WorkspaceDocumentSession,
    panel_state: WorkspacePanelState,
) -> int:
    """Close runtime document panels that no longer pass file authority."""

    user_id = get_current_user_id()
    removed_count = 0

    for metadata in list(document_session.list_open_documents()):
        resolved = resolve_authorized_workspace_file(
            user_id,
            metadata.document_id,
        )

        if resolved:
            continue

        panel_id = find_panel_id_for_document(
            panel_state,
            metadata.document_id,
        )

        if panel_id:
            panel_state.close_panel(panel_id)

        document_session.close_document(metadata.document_id)
        removed_count += 1

    if removed_count:
        refocus_after_panel_close(
            document_session,
            panel_state,
        )

    return removed_count


def build_workspace_document_view_url(document_id: str) -> str:
    """Build the protected raw stream URL for a workspace document."""

    return f"/workspace/file/{encode_document_id(document_id)}/view"


def build_workspace_document_reader_url(document_id: str) -> str:
    """Build the approved server-rendered reader shell URL."""

    return f"/workspace/file/{encode_document_id(document_id)}/reader"


def build_workspace_reader_contract(
    document_id: str,
    resolved: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the server-owned reader contract for the workspace bridge."""

    public_document_id = str(
        resolved.get("random_name")
        or resolved.get("document_id")
        or document_id
    ).strip()
    title = str(
        resolved.get("original_name") or public_document_id
    ).strip()
    reader_url = build_workspace_document_reader_url(
        public_document_id
    )
    raw_view_url = build_workspace_document_view_url(
        public_document_id
    )

    return {
        "reader_url": reader_url,
        "workspace_reader_url": reader_url,
        "full_reader_url": reader_url,
        "full_view_url": reader_url,
        "display_url": reader_url,
        "raw_view_url": raw_view_url,
        "document_id": public_document_id,
        "file_id": resolved.get("file_id"),
        "random_name": resolved.get("random_name"),
        "title": title,
        "type_label": get_type_label(title),
        "read_only": True,
    }


def ensure_metadata_extra(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Return a mutable metadata.extra payload."""

    metadata = payload.get("metadata")

    if not isinstance(metadata, dict):
        metadata = {}

    extra = metadata.get("extra")

    if not isinstance(extra, dict):
        extra = {}

    metadata["extra"] = extra
    payload["metadata"] = metadata

    return extra


def attach_reader_contract_to_payload(
    payload: Dict[str, Any],
    reader_contract: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach server-approved reader fields to a viewer payload."""

    payload.update({
        "reader_url": reader_contract["reader_url"],
        "workspace_reader_url": reader_contract["workspace_reader_url"],
        "read_only": True,
    })

    display = payload.get("display")

    if not isinstance(display, dict):
        display = {}

    display.update({
        "display_url": reader_contract["display_url"],
        "reader_url": reader_contract["reader_url"],
        "full_reader_url": reader_contract["full_reader_url"],
        "full_view_url": reader_contract["full_view_url"],
        "type_label": reader_contract["type_label"],
        "title": reader_contract["title"],
    })
    payload["display"] = display

    extra = ensure_metadata_extra(payload)
    extra.update({
        "upload_document_id": reader_contract["document_id"],
        "upload_file_id": reader_contract.get("file_id"),
        "upload_random_name": reader_contract.get("random_name"),
        "reader_url": reader_contract["reader_url"],
        "workspace_reader_url": reader_contract["workspace_reader_url"],
        "raw_view_url": reader_contract["raw_view_url"],
    })

    return payload


def attach_reader_contract_to_result(
    result: Dict[str, Any],
    reader_contract: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach approved reader URLs to the workspace action result."""

    if not isinstance(result, dict):
        result = {}

    result.update({
        "reader_url": reader_contract["reader_url"],
        "workspace_reader_url": reader_contract["workspace_reader_url"],
    })

    document = result.get("document")

    if isinstance(document, dict):
        document.setdefault(
            "type_label",
            reader_contract["type_label"],
        )
        document.setdefault(
            "reader_url",
            reader_contract["reader_url"],
        )

    viewer_packet = result.get("viewer_packet")

    if not isinstance(viewer_packet, dict):
        viewer_packet = {}

    viewer_packet.update({
        "title": (
            viewer_packet.get("title")
            or reader_contract["title"]
        ),
        "type_label": (
            viewer_packet.get("type_label")
            or reader_contract["type_label"]
        ),
    })
    result["viewer_packet"] = attach_reader_contract_to_payload(
        viewer_packet,
        reader_contract,
    )

    panel = result.get("panel")

    if isinstance(panel, dict):
        payload = panel.get("payload")

        if isinstance(payload, dict):
            panel["payload"] = attach_reader_contract_to_payload(
                payload,
                reader_contract,
            )

    return result


def workspace_bridge_error(
    error_code: str,
    user_output: str,
    *,
    status_code: int = 200,
    extra: Optional[Dict[str, Any]] = None,
):
    """Return a normalized workspace bridge error response."""

    payload = {
        "ok": False,
        "error": error_code,
        "user_output": user_output,
        "request_id": get_request_id(),
    }

    if extra:
        payload.update(extra)

    return jsonify(payload), status_code


def workspace_bridge_success(
    action: str,
    document_session: WorkspaceDocumentSession,
    panel_state: WorkspacePanelState,
    *,
    result: Optional[Dict[str, Any]] = None,
):
    """Persist workspace runtime and return a normalized bridge response."""

    context_packet = save_workspace_runtime(
        document_session,
        panel_state,
    )

    return jsonify({
        "ok": True,
        "action": action,
        "result": result or {},
        "workspace_context": context_packet,
        "request_id": get_request_id(),
    })


def read_workspace_action_payload() -> Dict[str, Any]:
    """Read the JSON payload for a workspace action."""

    payload = request.get_json(silent=True)

    if not isinstance(payload, dict):
        return {}

    return payload


def get_requested_document_id(
    *,
    file_id: Optional[str] = None,
    document_id: Optional[str] = None,
) -> str:
    """Return the active route identifier from canonical or legacy routes."""

    return normalize_document_id(
        file_id if file_id is not None else document_id
    )


@workspace_bp.route("/context", methods=["GET"])
@login_required
def workspace_context():
    """Return the current workspace bridge context packet."""

    document_session, panel_state = load_workspace_runtime()
    prune_workspace_runtime_to_authorized_files(
        document_session,
        panel_state,
    )
    context_packet = save_workspace_runtime(
        document_session,
        panel_state,
    )

    return jsonify({
        "ok": True,
        "workspace_context": context_packet,
        "request_id": get_request_id(),
    })


@workspace_bp.route("/file/<file_id>/view", methods=["GET"])
@workspace_bp.route("/document/<document_id>/view", methods=["GET"])
@login_required
def workspace_document_view(file_id=None, document_id=None):
    """Stream an authorized workspace document for protected reader use."""

    clean_document_id = get_requested_document_id(
        file_id=file_id,
        document_id=document_id,
    )

    if not clean_document_id:
        return workspace_bridge_error(
            "WorkspaceDocumentMissing",
            "No document was selected.",
            status_code=404,
        )

    resolved = resolve_authorized_workspace_file(
        get_current_user_id(),
        clean_document_id,
    )

    if not resolved:
        return workspace_bridge_error(
            "WorkspaceDocumentNotFound",
            "The selected document is not available in your file library.",
            extra={"document_id": clean_document_id},
            status_code=404,
        )

    return send_file(
        resolved["path"],
        as_attachment=False,
        download_name=(
            resolved.get("original_name")
            or clean_document_id
        ),
    )


@workspace_bp.route("/action/open-document", methods=["POST"])
@login_required
def workspace_action_open_document():
    """Open an authorized document in the workspace preview context."""

    payload = read_workspace_action_payload()
    requested_document_id = normalize_document_id(
        payload.get("document_id")
        or payload.get("random_name")
        or ""
    )

    if not requested_document_id:
        return workspace_bridge_error(
            "WorkspaceDocumentMissing",
            "No document was selected.",
        )

    resolved = resolve_authorized_workspace_file(
        get_current_user_id(),
        requested_document_id,
    )

    if not resolved:
        return workspace_bridge_error(
            "WorkspaceDocumentNotFound",
            "The selected document is not available in your file library.",
            extra={"document_id": requested_document_id},
            status_code=404,
        )

    reader_contract = build_workspace_reader_contract(
        requested_document_id,
        resolved,
    )
    document_session, panel_state = load_workspace_runtime()
    prune_workspace_runtime_to_authorized_files(
        document_session,
        panel_state,
    )

    result = open_workspace_document(
        document_session=document_session,
        panel_state=panel_state,
        source_path=resolved["path"],
        title=payload.get("title") or resolved.get("original_name"),
        source_name=resolved.get("original_name"),
        created_by=(
            session.get("user_email")
            or session.get("user_id")
        ),
        size_bytes=resolved.get("size_bytes"),
        display_url=reader_contract["display_url"],
        raw_view_url=reader_contract["raw_view_url"],
    )
    result = attach_reader_contract_to_result(
        result,
        reader_contract,
    )

    logger.info(
        "[workspace.action.open_document] request_id=%s document_id=%s "
        "panel_id=%s source=authorized_file active=%s reader_url=%s",
        get_request_id(),
        reader_contract["document_id"],
        result.get("panel", {}).get("panel_id"),
        resolved.get("active"),
        reader_contract["reader_url"],
    )

    return workspace_bridge_success(
        "open_document",
        document_session,
        panel_state,
        result=result,
    )


@workspace_bp.route("/action/focus-document", methods=["POST"])
@login_required
def workspace_action_focus_document():
    """Focus an open workspace document panel."""

    payload = read_workspace_action_payload()
    document_session, panel_state = load_workspace_runtime()
    prune_workspace_runtime_to_authorized_files(
        document_session,
        panel_state,
    )

    panel_id = str(payload.get("panel_id") or "").strip()
    document_id = normalize_document_id(
        payload.get("document_id") or ""
    )

    if not panel_id and document_id:
        panel_id = (
            find_panel_id_for_document(
                panel_state,
                document_id,
            )
            or ""
        )

    if not panel_id:
        return workspace_bridge_error(
            "WorkspacePanelMissing",
            "No workspace panel was selected.",
        )

    focused_panel = panel_state.focus_panel(panel_id)

    if not focused_panel:
        return workspace_bridge_error(
            "WorkspacePanelNotFound",
            "The selected workspace panel is not open.",
            extra={"panel_id": panel_id},
        )

    if focused_panel.document_id:
        document_session.set_active_document(
            focused_panel.document_id
        )

    logger.info(
        "[workspace.action.focus_document] request_id=%s "
        "panel_id=%s document_id=%s",
        get_request_id(),
        focused_panel.panel_id,
        focused_panel.document_id,
    )

    return workspace_bridge_success(
        "focus_document",
        document_session,
        panel_state,
        result={"panel": focused_panel.to_dict()},
    )


@workspace_bp.route("/action/minimize-document", methods=["POST"])
@login_required
def workspace_action_minimize_document():
    """Minimize an open workspace document panel."""

    payload = read_workspace_action_payload()
    document_session, panel_state = load_workspace_runtime()
    prune_workspace_runtime_to_authorized_files(
        document_session,
        panel_state,
    )

    panel_id = str(payload.get("panel_id") or "").strip()
    document_id = normalize_document_id(
        payload.get("document_id") or ""
    )

    if not panel_id and document_id:
        panel_id = (
            find_panel_id_for_document(
                panel_state,
                document_id,
            )
            or ""
        )

    if not panel_id:
        return workspace_bridge_error(
            "WorkspacePanelMissing",
            "No workspace panel was selected.",
        )

    minimized_panel = panel_state.minimize_panel(panel_id)

    if not minimized_panel:
        return workspace_bridge_error(
            "WorkspacePanelNotFound",
            "The selected workspace panel is not open.",
            extra={"panel_id": panel_id},
        )

    logger.info(
        "[workspace.action.minimize_document] request_id=%s "
        "panel_id=%s document_id=%s",
        get_request_id(),
        minimized_panel.panel_id,
        minimized_panel.document_id,
    )

    return workspace_bridge_success(
        "minimize_document",
        document_session,
        panel_state,
        result={"panel": minimized_panel.to_dict()},
    )


@workspace_bp.route("/action/close-document", methods=["POST"])
@login_required
def workspace_action_close_document():
    """Close an open workspace document panel."""

    payload = read_workspace_action_payload()
    document_session, panel_state = load_workspace_runtime()
    prune_workspace_runtime_to_authorized_files(
        document_session,
        panel_state,
    )

    panel_id = str(payload.get("panel_id") or "").strip()
    document_id = normalize_document_id(
        payload.get("document_id") or ""
    )

    if not panel_id and document_id:
        panel_id = (
            find_panel_id_for_document(
                panel_state,
                document_id,
            )
            or ""
        )

    if not panel_id:
        return workspace_bridge_error(
            "WorkspacePanelMissing",
            "No workspace panel was selected.",
        )

    closed_panel = panel_state.close_panel(panel_id)

    if not closed_panel:
        return workspace_bridge_error(
            "WorkspacePanelNotFound",
            "The selected workspace panel is not open.",
            extra={"panel_id": panel_id},
        )

    if closed_panel.document_id:
        document_session.close_document(
            closed_panel.document_id
        )

    refocus_after_panel_close(
        document_session,
        panel_state,
    )

    logger.info(
        "[workspace.action.close_document] request_id=%s "
        "panel_id=%s document_id=%s",
        get_request_id(),
        closed_panel.panel_id,
        closed_panel.document_id,
    )

    return workspace_bridge_success(
        "close_document",
        document_session,
        panel_state,
        result={"panel": closed_panel.to_dict()},
    )


__all__ = [
    "workspace_bp",
]