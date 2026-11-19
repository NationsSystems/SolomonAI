# -------------------------------------------------------------
# FILE: solomon_core/workspace_actions/__init__.py
# DIRECTORY: solomon_core/workspace_actions/
# -------------------------------------------------------------
# Workspace action selection package.
#
# CONTRACT
#   Registered visual workspace actions only.
#   No Solomon authority, no workflow routing, and no frontend guessing.
# -------------------------------------------------------------

from .workspace_action_selector import (
    WorkspaceActionSelection,
    select_workspace_action,
    warm_workspace_action_selector,
)

__all__ = [
    "WorkspaceActionSelection",
    "select_workspace_action",
    "warm_workspace_action_selector",
]