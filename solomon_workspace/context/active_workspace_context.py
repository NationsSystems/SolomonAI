# -------------------------------------------------------------------
# FILE: active_workspace_context.py
# DIRECTORY: solomon_workspace/context/
# -------------------------------------------------------------------
# Active workspace context exposed to SolomonAI.
# -------------------------------------------------------------------

from dataclasses import dataclass
from typing import List, Optional

from solomon_workspace.context.active_document_context import (
    ActiveDocumentContext,
    build_active_document_context,
)
from solomon_workspace.documents.document_session import WorkspaceDocumentSession
from solomon_workspace.panels.panel_state import WorkspacePanelState


@dataclass(frozen=True)
class ActiveWorkspaceContext:
    """Controlled context for the active Solomon workspace."""

    workspace_id: str
    active_document: ActiveDocumentContext
    open_document_count: int
    open_panel_count: int
    focused_panel_id: Optional[str]
    available_actions: List[str]

    def to_dict(self) -> dict:
        """Return a JSON-safe active workspace context packet."""

        return {
            "workspace_id": self.workspace_id,
            "active_document": self.active_document.to_dict(),
            "open_document_count": self.open_document_count,
            "open_panel_count": self.open_panel_count,
            "focused_panel_id": self.focused_panel_id,
            "available_actions": list(self.available_actions),
        }


def build_active_workspace_context(
    document_session: WorkspaceDocumentSession,
    panel_state: WorkspacePanelState,
) -> ActiveWorkspaceContext:
    """Build controlled active workspace context from session state."""

    active_document = document_session.get_active_document()
    focused_panel = panel_state.get_focused_panel()

    actions = [
        "open_document",
    ]

    if active_document:
        actions.extend([
            "close_document",
            "focus_document",
            "minimize_document",
        ])

    return ActiveWorkspaceContext(
        workspace_id=document_session.workspace_id,
        active_document=build_active_document_context(active_document),
        open_document_count=len(document_session.list_open_documents()),
        open_panel_count=len(panel_state.list_panels()),
        focused_panel_id=focused_panel.panel_id if focused_panel else None,
        available_actions=actions,
    )


__all__ = [
    "ActiveWorkspaceContext",
    "build_active_workspace_context",
]