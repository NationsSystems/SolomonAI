# -------------------------------------------------------------------
# FILE: workspace_context_packet.py
# DIRECTORY: solomon_workspace/context/
# -------------------------------------------------------------------
# Full workspace context packet for API and SolomonAI handoff.
# -------------------------------------------------------------------

from solomon_workspace.context.active_workspace_context import (
    build_active_workspace_context,
)
from solomon_workspace.documents.document_session import WorkspaceDocumentSession
from solomon_workspace.panels.panel_state import WorkspacePanelState


def build_workspace_context_packet(
    document_session: WorkspaceDocumentSession,
    panel_state: WorkspacePanelState,
) -> dict:
    """Build a JSON-safe workspace context packet."""

    active_context = build_active_workspace_context(
        document_session=document_session,
        panel_state=panel_state,
    )

    return {
        "packet_type": "workspace_context",
        "workspace": active_context.to_dict(),
        "documents": document_session.to_dict(),
        "panels": panel_state.to_dict(),
    }


__all__ = [
    "build_workspace_context_packet",
]