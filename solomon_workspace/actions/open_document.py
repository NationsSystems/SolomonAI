# -------------------------------------------------------------------
# FILE: open_document.py
# DIRECTORY: solomon_workspace/actions/
# -------------------------------------------------------------------
# Workspace action for opening a document into a panel.
# -------------------------------------------------------------------

from typing import Dict, Optional

from solomon_workspace.documents.document_metadata import (
    WorkspaceDocumentMetadata,
    build_workspace_document_metadata,
)
from solomon_workspace.documents.document_session import WorkspaceDocumentSession
from solomon_workspace.panels.panel_state import WorkspacePanelState
from solomon_workspace.panels.workspace_panel import build_workspace_panel
from solomon_workspace.viewers.image_viewer import build_image_viewer_packet
from solomon_workspace.viewers.pdf_viewer import build_pdf_viewer_packet
from solomon_workspace.viewers.spreadsheet_viewer import build_spreadsheet_viewer_packet
from solomon_workspace.viewers.text_document_viewer import build_text_document_viewer_packet
from solomon_workspace.viewers.viewer_packet import (
    WorkspaceViewerPacket,
    build_unsupported_viewer_packet,
)


def normalize_optional_url(value: Optional[str]) -> str:
    """Return a normalized optional URL value."""

    return str(value or "").strip()


def build_viewer_packet_for_document(
    metadata: WorkspaceDocumentMetadata,
    *,
    display_url: Optional[str] = None,
) -> WorkspaceViewerPacket:
    """Build the server-selected viewer packet for a workspace document."""

    viewer_type = metadata.viewer_type.value

    if viewer_type == "pdf_viewer":
        return build_pdf_viewer_packet(
            metadata,
            display_url=display_url,
        )

    if viewer_type == "image_viewer":
        return build_image_viewer_packet(metadata)

    if viewer_type == "text_document_viewer":
        return build_text_document_viewer_packet(metadata)

    if viewer_type == "spreadsheet_viewer":
        return build_spreadsheet_viewer_packet(metadata)

    return build_unsupported_viewer_packet(metadata)


def build_server_owned_viewer_payload(
    viewer_packet: WorkspaceViewerPacket,
    *,
    reader_url: Optional[str] = None,
    raw_view_url: Optional[str] = None,
) -> Dict:
    """Return a viewer payload with server-owned reader URLs attached."""

    payload = viewer_packet.to_dict()
    approved_reader_url = normalize_optional_url(reader_url)
    protected_raw_view_url = normalize_optional_url(raw_view_url)

    payload["read_only"] = True

    if approved_reader_url:
        payload["reader_url"] = approved_reader_url
        payload["workspace_reader_url"] = approved_reader_url

        display = payload.get("display")
        if not isinstance(display, dict):
            display = {}

        display.update({
            "display_url": approved_reader_url,
            "reader_url": approved_reader_url,
            "full_reader_url": approved_reader_url,
            "full_view_url": approved_reader_url,
        })
        payload["display"] = display

    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    extra = metadata.get("extra")
    if not isinstance(extra, dict):
        extra = {}

    if approved_reader_url:
        extra["reader_url"] = approved_reader_url
        extra["workspace_reader_url"] = approved_reader_url

    if protected_raw_view_url:
        extra["raw_view_url"] = protected_raw_view_url

    metadata["extra"] = extra
    payload["metadata"] = metadata

    return payload


def open_workspace_document(
    document_session: WorkspaceDocumentSession,
    panel_state: WorkspacePanelState,
    source_path: str,
    *,
    title: Optional[str] = None,
    source_name: Optional[str] = None,
    created_by: Optional[str] = None,
    size_bytes: Optional[int] = None,
    display_url: Optional[str] = None,
    raw_view_url: Optional[str] = None,
) -> dict:
    """Open a document into the workspace and return action result data."""

    approved_reader_url = normalize_optional_url(display_url)

    metadata = build_workspace_document_metadata(
        source_path,
        title=title,
        source_name=source_name,
        created_by=created_by,
        workspace_id=document_session.workspace_id,
        size_bytes=size_bytes,
    )

    document_session.open_document(metadata)

    viewer_packet = build_viewer_packet_for_document(
        metadata,
        display_url=approved_reader_url,
    )
    viewer_payload = build_server_owned_viewer_payload(
        viewer_packet,
        reader_url=approved_reader_url,
        raw_view_url=raw_view_url,
    )

    panel = build_workspace_panel(
        panel_type="document_viewer",
        title=metadata.title,
        payload=viewer_payload,
        document_id=metadata.document_id,
        focused=True,
    )

    opened_panel = panel_state.open_panel(panel)

    return {
        "ok": True,
        "action": "open_document",
        "document": metadata.to_dict(),
        "viewer_packet": viewer_payload,
        "panel": opened_panel.to_dict(),
    }


__all__ = [
    "build_server_owned_viewer_payload",
    "build_viewer_packet_for_document",
    "open_workspace_document",
]