# -------------------------------------------------------------------
# FILE: pdf_viewer.py
# DIRECTORY: solomon_workspace/viewers/
# -------------------------------------------------------------------
# PDF viewer packet builder for Solomon workspace documents.
# -------------------------------------------------------------------

from typing import Any, Dict, Optional

from solomon_workspace.documents.document_metadata import WorkspaceDocumentMetadata
from solomon_workspace.documents.document_types import WorkspaceDocumentType
from solomon_workspace.viewers.viewer_packet import (
    WorkspaceViewerPacket,
    build_unsupported_viewer_packet,
    build_workspace_viewer_packet,
)


DEFAULT_PDF_ACTIONS = [
    "close_document",
    "focus_document",
    "minimize_document",
]


def is_pdf_document(metadata: WorkspaceDocumentMetadata) -> bool:
    """Return whether metadata represents a PDF workspace document."""

    return metadata.document_type == WorkspaceDocumentType.PDF


def normalize_optional_url(value: Optional[str]) -> str:
    """Return a normalized optional URL value."""

    return str(value or "").strip()


def build_pdf_display_payload(
    metadata: WorkspaceDocumentMetadata,
    *,
    display_url: Optional[str] = None,
    page_count: Optional[int] = None,
    current_page: int = 1,
    zoom: float = 1.0,
    extra_display: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build the server-owned PDF display payload."""

    safe_current_page = max(int(current_page or 1), 1)
    safe_zoom = float(zoom or 1.0)
    approved_reader_url = normalize_optional_url(display_url)

    display = {
        "mode": "pdf",
        "document_id": metadata.document_id,
        "display_url": approved_reader_url,
        "reader_url": approved_reader_url,
        "full_reader_url": approved_reader_url,
        "full_view_url": approved_reader_url,
        "page_count": page_count,
        "current_page": safe_current_page,
        "zoom": safe_zoom,
        "read_only": True,
        "viewer_surface": "server_reader",
        "content_mount": "reader_shell",
        "supports_page_navigation": True,
        "supports_zoom": True,
    }

    display.update(dict(extra_display or {}))
    return display


def build_pdf_viewer_packet(
    metadata: WorkspaceDocumentMetadata,
    *,
    display_url: Optional[str] = None,
    page_count: Optional[int] = None,
    current_page: int = 1,
    zoom: float = 1.0,
    extra_display: Optional[Dict[str, Any]] = None,
) -> WorkspaceViewerPacket:
    """Build a viewer packet for a PDF workspace document."""

    if not metadata.supported:
        return build_unsupported_viewer_packet(metadata)

    if not is_pdf_document(metadata):
        return build_unsupported_viewer_packet(
            metadata,
            message="This document is not a PDF document.",
        )

    return build_workspace_viewer_packet(
        metadata,
        actions=DEFAULT_PDF_ACTIONS,
        display=build_pdf_display_payload(
            metadata,
            display_url=display_url,
            page_count=page_count,
            current_page=current_page,
            zoom=zoom,
            extra_display=extra_display,
        ),
    )


__all__ = [
    "DEFAULT_PDF_ACTIONS",
    "build_pdf_display_payload",
    "build_pdf_viewer_packet",
    "is_pdf_document",
]