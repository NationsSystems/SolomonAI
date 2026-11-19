# -------------------------------------------------------------------
# FILE: spreadsheet_viewer.py
# DIRECTORY: solomon_workspace/viewers/
# -------------------------------------------------------------------
# Spreadsheet viewer packet builder for Solomon workspace documents.
# -------------------------------------------------------------------

from typing import Any, Dict, List, Optional

from solomon_workspace.documents.document_metadata import WorkspaceDocumentMetadata
from solomon_workspace.documents.document_types import WorkspaceDocumentType
from solomon_workspace.viewers.viewer_packet import (
    WorkspaceViewerPacket,
    build_unsupported_viewer_packet,
    build_workspace_viewer_packet,
)


DEFAULT_SPREADSHEET_ACTIONS = [
    "close_document",
    "focus_document",
    "minimize_document",
]


def is_spreadsheet_document(metadata: WorkspaceDocumentMetadata) -> bool:
    """Return whether metadata represents a spreadsheet workspace document."""

    return metadata.document_type == WorkspaceDocumentType.SPREADSHEET


def build_spreadsheet_display_payload(
    metadata: WorkspaceDocumentMetadata,
    *,
    sheet_names: Optional[List[str]] = None,
    active_sheet: Optional[str] = None,
    preview_rows: Optional[List[Dict[str, Any]]] = None,
    row_count: Optional[int] = None,
    column_count: Optional[int] = None,
    extra_display: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a backend-neutral spreadsheet display payload."""

    sheets = list(sheet_names or [])
    selected_sheet = active_sheet or (sheets[0] if sheets else None)

    display = {
        "mode": "spreadsheet",
        "document_id": metadata.document_id,
        "source_path": metadata.source_path,
        "sheet_names": sheets,
        "active_sheet": selected_sheet,
        "preview_rows": list(preview_rows or []),
        "row_count": row_count,
        "column_count": column_count,
        "supports_sheet_navigation": True,
        "supports_search": True,
    }

    display.update(dict(extra_display or {}))
    return display


def build_spreadsheet_viewer_packet(
    metadata: WorkspaceDocumentMetadata,
    *,
    sheet_names: Optional[List[str]] = None,
    active_sheet: Optional[str] = None,
    preview_rows: Optional[List[Dict[str, Any]]] = None,
    row_count: Optional[int] = None,
    column_count: Optional[int] = None,
    extra_display: Optional[Dict[str, Any]] = None,
) -> WorkspaceViewerPacket:
    """Build a viewer packet for a spreadsheet workspace document."""

    if not metadata.supported:
        return build_unsupported_viewer_packet(metadata)

    if not is_spreadsheet_document(metadata):
        return build_unsupported_viewer_packet(
            metadata,
            message="This document is not a spreadsheet.",
        )

    return build_workspace_viewer_packet(
        metadata,
        actions=DEFAULT_SPREADSHEET_ACTIONS,
        display=build_spreadsheet_display_payload(
            metadata,
            sheet_names=sheet_names,
            active_sheet=active_sheet,
            preview_rows=preview_rows,
            row_count=row_count,
            column_count=column_count,
            extra_display=extra_display,
        ),
    )


__all__ = [
    "DEFAULT_SPREADSHEET_ACTIONS",
    "is_spreadsheet_document",
    "build_spreadsheet_display_payload",
    "build_spreadsheet_viewer_packet",
]