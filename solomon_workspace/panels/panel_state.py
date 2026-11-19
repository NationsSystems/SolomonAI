# -------------------------------------------------------------------
# FILE: panel_state.py
# DIRECTORY: solomon_workspace/panels/
# -------------------------------------------------------------------
# Workspace panel state helpers.
# -------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Any, List, Optional

from solomon_workspace.panels.panel_registry import WorkspacePanelRegistry
from solomon_workspace.panels.workspace_panel import WorkspacePanel


@dataclass
class WorkspacePanelState:
    """Workspace-level visible panel state."""

    registry: WorkspacePanelRegistry = field(default_factory=WorkspacePanelRegistry)

    def open_panel(self, panel: WorkspacePanel) -> WorkspacePanel:
        """Open a panel and focus it."""

        self.registry.add(panel)
        focused = self.registry.focus(panel.panel_id)
        return focused or panel

    def focus_panel(self, panel_id: str) -> Optional[WorkspacePanel]:
        """Focus a panel by id."""

        return self.registry.focus(panel_id)

    def minimize_panel(self, panel_id: str) -> Optional[WorkspacePanel]:
        """Minimize a panel by id."""

        return self.registry.minimize(panel_id)

    def close_panel(self, panel_id: str) -> Optional[WorkspacePanel]:
        """Close a panel by id."""

        return self.registry.close(panel_id)

    def list_panels(self) -> List[WorkspacePanel]:
        """Return visible workspace panels."""

        return self.registry.list_panels()

    def get_focused_panel(self) -> Optional[WorkspacePanel]:
        """Return the focused panel if one exists."""

        for panel in self.registry.list_panels():
            if panel.focused:
                return panel

        return None

    def replace_from_dict(self, payload: Any) -> None:
        """Replace this panel state from a JSON-safe payload."""

        if not isinstance(payload, dict):
            self.registry.clear()
            return

        panels = payload.get("panels")
        self.registry.replace_from_list(panels if isinstance(panels, list) else [])

        focused_panel_id = str(payload.get("focused_panel_id") or "").strip()
        if focused_panel_id and self.registry.get(focused_panel_id):
            self.registry.focus(focused_panel_id)

    def to_dict(self) -> dict:
        """Return JSON-safe panel state."""

        focused = self.get_focused_panel()

        return {
            "focused_panel_id": focused.panel_id if focused else None,
            "focused_panel": focused.to_dict() if focused else None,
            "panels": self.registry.to_list(),
        }


def build_workspace_panel_state_from_dict(payload: Any) -> WorkspacePanelState:
    """Build workspace panel state from JSON-safe state."""

    panel_state = WorkspacePanelState()
    panel_state.replace_from_dict(payload)
    return panel_state


__all__ = [
    "WorkspacePanelState",
    "build_workspace_panel_state_from_dict",
]