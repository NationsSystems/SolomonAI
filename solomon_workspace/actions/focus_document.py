# -------------------------------------------------------------------
# FILE: focus_document.py
# DIRECTORY: solomon_workspace/actions/
# -------------------------------------------------------------------
# Workspace action for focusing an open document.
# -------------------------------------------------------------------

from solomon_workspace.documents.document_session import WorkspaceDocumentSession
from solomon_workspace.panels.panel_state import WorkspacePanelState


def focus_workspace_document(
    document_session: WorkspaceDocumentSession,
    panel_state: WorkspacePanelState,
    document_id: str,
) -> dict:
    """Focus an open workspace document and its panel."""

    clean_id = str(document_id or "").strip()
    metadata = document_session.set_active_document(clean_id)
    focused_panel = None

    if metadata:
        for panel in panel_state.list_panels():
            if panel.document_id == clean_id:
                focused_panel = panel_state.focus_panel(panel.panel_id)
                break

    return {
        "ok": metadata is not None,
        "action": "focus_document",
        "document_id": clean_id,
        "active_document": metadata.to_dict() if metadata else None,
        "focused_panel": focused_panel.to_dict() if focused_panel else None,
    }


__all__ = [
    "focus_workspace_document",
]