# -------------------------------------------------------------------
# FILE: text_document_viewer.py
# DIRECTORY: solomon_workspace/viewers/
# -------------------------------------------------------------------
# Text document viewer packet builder for Solomon workspace documents.
# -------------------------------------------------------------------

from typing import Any, Dict, Optional

from solomon_workspace.documents.document_metadata import WorkspaceDocumentMetadata
from solomon_workspace.documents.document_types import WorkspaceDocumentType
from solomon_workspace.viewers.viewer_packet import (
    WorkspaceViewerPacket,
    build_unsupported_viewer_packet,
    build_workspace_viewer_packet,
)


DEFAULT_TEXT_DOCUMENT_ACTIONS = [
    "close_document",
    "focus_document",
    "minimize_document",
]


def is_text_document(metadata: WorkspaceDocumentMetadata) -> bool:
    """Return whether metadata represents a text document workspace document."""

    return metadata.document_type == WorkspaceDocumentType.TEXT_DOCUMENT


def build_text_document_display_payload(
    metadata: WorkspaceDocumentMetadata,
    *,
    content_url: Optional[str] = None,
    preview_text: Optional[str] = None,
    word_count: Optional[int] = None,
    extra_display: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a backend-neutral text document display payload."""

    display = {
        "mode": "text_document",
        "document_id": metadata.document_id,
        "source_path": metadata.source_path,
        "content_url": content_url,
        "preview_text": preview_text,
        "word_count": word_count,
        "supports_text_selection": True,
        "supports_search": True,
    }

    display.update(dict(extra_display or {}))
    return display


def build_text_document_viewer_packet(
    metadata: WorkspaceDocumentMetadata,
    *,
    content_url: Optional[str] = None,
    preview_text: Optional[str] = None,
    word_count: Optional[int] = None,
    extra_display: Optional[Dict[str, Any]] = None,
) -> WorkspaceViewerPacket:
    """Build a viewer packet for a text document workspace document."""

    if not metadata.supported:
        return build_unsupported_viewer_packet(metadata)

    if not is_text_document(metadata):
        return build_unsupported_viewer_packet(
            metadata,
            message="This document is not a text document.",
        )

    return build_workspace_viewer_packet(
        metadata,
        actions=DEFAULT_TEXT_DOCUMENT_ACTIONS,
        display=build_text_document_display_payload(
            metadata,
            content_url=content_url,
            preview_text=preview_text,
            word_count=word_count,
            extra_display=extra_display,
        ),
    )


__all__ = [
    "DEFAULT_TEXT_DOCUMENT_ACTIONS",
    "is_text_document",
    "build_text_document_display_payload",
    "build_text_document_viewer_packet",
]