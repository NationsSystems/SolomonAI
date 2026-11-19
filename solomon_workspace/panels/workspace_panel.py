# -------------------------------------------------------------------
# FILE: workspace_panel.py
# DIRECTORY: solomon_workspace/panels/
# -------------------------------------------------------------------
# Workspace panel contract for visible Solomon workspace objects.
# -------------------------------------------------------------------

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional
from uuid import uuid4


@dataclass(frozen=True)
class WorkspacePanel:
    """Canonical panel object for workspace-visible content."""

    panel_id: str
    panel_type: str
    title: str
    payload: Dict[str, Any] = field(default_factory=dict)
    focused: bool = False
    minimized: bool = False
    closed: bool = False
    document_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe panel representation."""

        return asdict(self)


def build_workspace_panel(
    *,
    panel_type: str,
    title: str,
    payload: Optional[Dict[str, Any]] = None,
    panel_id: Optional[str] = None,
    document_id: Optional[str] = None,
    focused: bool = False,
    minimized: bool = False,
    closed: bool = False,
) -> WorkspacePanel:
    """Build a workspace panel object."""

    return WorkspacePanel(
        panel_id=str(panel_id or uuid4()),
        panel_type=str(panel_type or "workspace_panel").strip(),
        title=str(title or "Workspace Panel").strip(),
        payload=dict(payload or {}),
        focused=bool(focused),
        minimized=bool(minimized),
        closed=bool(closed),
        document_id=document_id,
    )


__all__ = [
    "WorkspacePanel",
    "build_workspace_panel",
]