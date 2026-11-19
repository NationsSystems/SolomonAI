# solomon_core/autonomy/__init__.py
# -------------------------------------------------------------
# Autonomy package export layer
#
# Phase 16 Step 8 (Option A):
#   Expose ONLY the orchestrator entry points.
#   Does NOT trigger autonomy automatically.
#   Zero side-effects; safe for import by core modules.
# -------------------------------------------------------------

from .autonomy_orchestrator import (
    run_autonomy_cycle,
    autonomy_status_preview
)

__all__ = [
    "run_autonomy_cycle",
    "autonomy_status_preview",
]
