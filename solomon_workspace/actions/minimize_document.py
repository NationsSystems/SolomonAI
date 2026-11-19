# -------------------------------------------------------------------
# FILE: minimize_document.py
# DIRECTORY: solomon_workspace/actions/
# -------------------------------------------------------------------
# Workspace action for minimizing an open document panel.
# -------------------------------------------------------------------

from solomon_workspace.panels.panel_state import WorkspacePanelState


def minimize_workspace_document(
    panel_state: WorkspacePanelState,
    document_id: str,
) -> dict:
    """Minimize the panel associated with a workspace document."""

    clean_id = str(document_id or "").strip()
    minimized_panel = None

    for panel in panel_state.list_panels():
        if panel.document_id == clean_id:
            minimized_panel = panel_state.minimize_panel(panel.panel_id)
            break

    return {
        "ok": minimized_panel is not None,
        "action": "minimize_document",
        "document_id": clean_id,
        "minimized_panel": minimized_panel.to_dict() if minimized_panel else None,
    }


__all__ = [
    "minimize_workspace_document",
]