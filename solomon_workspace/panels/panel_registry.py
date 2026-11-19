# -------------------------------------------------------------------
# FILE: panel_registry.py
# DIRECTORY: solomon_workspace/panels/
# -------------------------------------------------------------------
# In-memory workspace panel registry.
# -------------------------------------------------------------------

from dataclasses import replace
from typing import Any, Dict, Iterable, List, Optional

from solomon_workspace.panels.workspace_panel import WorkspacePanel, build_workspace_panel


class WorkspacePanelRegistry:
    """Tracks panels that are open in a workspace session."""

    def __init__(self) -> None:
        self._panels: Dict[str, WorkspacePanel] = {}

    def add(self, panel: WorkspacePanel) -> WorkspacePanel:
        """Register or replace a workspace panel."""

        self._panels[panel.panel_id] = panel
        return panel

    def get(self, panel_id: str) -> Optional[WorkspacePanel]:
        """Return a panel by id."""

        return self._panels.get(str(panel_id or "").strip())

    def remove(self, panel_id: str) -> Optional[WorkspacePanel]:
        """Remove a panel by id."""

        return self._panels.pop(str(panel_id or "").strip(), None)

    def list_panels(self) -> List[WorkspacePanel]:
        """Return all panels in insertion order."""

        return list(self._panels.values())

    def focus(self, panel_id: str) -> Optional[WorkspacePanel]:
        """Focus one panel and unfocus all others."""

        clean_id = str(panel_id or "").strip()

        if clean_id not in self._panels:
            return None

        for existing_id, panel in list(self._panels.items()):
            self._panels[existing_id] = replace(
                panel,
                focused=(existing_id == clean_id),
                minimized=False if existing_id == clean_id else panel.minimized,
            )

        return self._panels[clean_id]

    def minimize(self, panel_id: str) -> Optional[WorkspacePanel]:
        """Mark a panel as minimized."""

        panel = self.get(panel_id)

        if not panel:
            return None

        updated = replace(panel, focused=False, minimized=True)
        self._panels[panel.panel_id] = updated
        return updated

    def close(self, panel_id: str) -> Optional[WorkspacePanel]:
        """Mark a panel closed and remove it from active registry."""

        panel = self.remove(panel_id)

        if not panel:
            return None

        return replace(panel, focused=False, minimized=False, closed=True)

    def clear(self) -> None:
        """Remove all registered panels."""

        self._panels.clear()

    def replace_from_list(self, panels: Iterable[Dict[str, Any]]) -> List[WorkspacePanel]:
        """Replace registry contents from JSON-safe panel data."""

        self.clear()
        restored = []
        focused_panel_id = None

        for payload in panels or []:
            panel = build_workspace_panel_from_dict(payload)

            if not panel:
                continue

            restored.append(self.add(panel))

            if panel.focused:
                focused_panel_id = panel.panel_id

        if focused_panel_id:
            focused = self.focus(focused_panel_id)
            return self.list_panels() if focused else restored

        for panel in reversed(self.list_panels()):
            if not panel.minimized:
                self.focus(panel.panel_id)
                break

        return self.list_panels()

    def to_list(self) -> List[dict]:
        """Return JSON-safe panel data."""

        return [panel.to_dict() for panel in self.list_panels()]


def build_workspace_panel_from_dict(payload: Any) -> Optional[WorkspacePanel]:
    """Rebuild a workspace panel from JSON-safe data."""

    if isinstance(payload, WorkspacePanel):
        return payload

    if not isinstance(payload, dict):
        return None

    panel_id = str(payload.get("panel_id") or "").strip()
    panel_type = str(payload.get("panel_type") or "workspace_panel").strip()
    title = str(payload.get("title") or "Workspace Panel").strip()
    payload_data = payload.get("payload")
    document_id = payload.get("document_id")

    if not panel_id:
        return None

    return build_workspace_panel(
        panel_id=panel_id,
        panel_type=panel_type,
        title=title,
        payload=payload_data if isinstance(payload_data, dict) else {},
        document_id=str(document_id).strip() if document_id else None,
        focused=bool(payload.get("focused")),
        minimized=bool(payload.get("minimized")),
        closed=bool(payload.get("closed")),
    )


__all__ = [
    "WorkspacePanelRegistry",
    "build_workspace_panel_from_dict",
]