# -------------------------------------------------------------------
# FILE: close_document.py
# DIRECTORY: solomon_workspace/actions/
# -------------------------------------------------------------------
# Workspace action for closing an open document.
# -------------------------------------------------------------------

from typing import Optional

from solomon_workspace.documents.document_session import WorkspaceDocumentSession
from solomon_workspace.panels.panel_state import WorkspacePanelState


def close_workspace_document(
    document_session: WorkspaceDocumentSession,
    panel_state: WorkspacePanelState,
    document_id: str,
) -> dict:
    """Close a workspace document and any panel displaying it."""

    clean_id = str(document_id or "").strip()
    closed_document = document_session.close_document(clean_id)
    closed_panels = []

    for panel in list(panel_state.list_panels()):
        if panel.document_id == clean_id:
            closed_panel = panel_state.close_panel(panel.panel_id)

            if closed_panel:
                closed_panels.append(closed_panel.to_dict())

    return {
        "ok": closed_document is not None,
        "action": "close_document",
        "document_id": clean_id,
        "closed_document": closed_document.to_dict() if closed_document else None,
        "closed_panels": closed_panels,
        "active_document": (
            document_session.get_active_document().to_dict()
            if document_session.get_active_document()
            else None
        ),
    }


__all__ = [
    "close_workspace_document",
]