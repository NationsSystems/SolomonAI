# -------------------------------------------------------------------
# FILE: image_viewer.py
# DIRECTORY: solomon_workspace/viewers/
# -------------------------------------------------------------------
# Image viewer packet builder for Solomon workspace documents.
# -------------------------------------------------------------------

from typing import Any, Dict, Optional

from solomon_workspace.documents.document_metadata import WorkspaceDocumentMetadata
from solomon_workspace.documents.document_types import WorkspaceDocumentType
from solomon_workspace.viewers.viewer_packet import (
    WorkspaceViewerPacket,
    build_unsupported_viewer_packet,
    build_workspace_viewer_packet,
)


DEFAULT_IMAGE_ACTIONS = [
    "close_document",
    "focus_document",
    "minimize_document",
]


def is_image_document(metadata: WorkspaceDocumentMetadata) -> bool:
    """Return whether metadata represents an image workspace document."""

    return metadata.document_type == WorkspaceDocumentType.IMAGE


def build_image_display_payload(
    metadata: WorkspaceDocumentMetadata,
    *,
    display_url: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    zoom: float = 1.0,
    extra_display: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a backend-neutral image display payload."""

    safe_zoom = float(zoom or 1.0)

    display = {
        "mode": "image",
        "document_id": metadata.document_id,
        "source_path": metadata.source_path,
        "display_url": display_url,
        "width": width,
        "height": height,
        "zoom": safe_zoom,
        "supports_pan": True,
        "supports_zoom": True,
    }

    display.update(dict(extra_display or {}))
    return display


def build_image_viewer_packet(
    metadata: WorkspaceDocumentMetadata,
    *,
    display_url: Optional[str] = None,
    width: Optional[int] = None,
    height: Optional[int] = None,
    zoom: float = 1.0,
    extra_display: Optional[Dict[str, Any]] = None,
) -> WorkspaceViewerPacket:
    """Build a viewer packet for an image workspace document."""

    if not metadata.supported:
        return build_unsupported_viewer_packet(metadata)

    if not is_image_document(metadata):
        return build_unsupported_viewer_packet(
            metadata,
            message="This document is not an image document.",
        )

    return build_workspace_viewer_packet(
        metadata,
        actions=DEFAULT_IMAGE_ACTIONS,
        display=build_image_display_payload(
            metadata,
            display_url=display_url,
            width=width,
            height=height,
            zoom=zoom,
            extra_display=extra_display,
        ),
    )


__all__ = [
    "DEFAULT_IMAGE_ACTIONS",
    "is_image_document",
    "build_image_display_payload",
    "build_image_viewer_packet",
]