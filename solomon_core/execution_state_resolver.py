# -------------------------------------------------------------------
# FILE: execution_state_resolver.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# Phase 39 FSM Spoke — Focused Observability
#
# Collapse factual signals into a single ExecutionState.
# Hub-and-spoke compliant, pure reducer, deterministic.
# No execution, no interpretation.
#
# Phase 39:
#   - No semantic changes
#   - No authority changes
#   - Decision-level logging only (FOM-39)
# -------------------------------------------------------------------

from enum import Enum, auto
from typing import Any, Dict

from config import settings
from solomon_core.logger import get_logger

logger = get_logger("execution_state_resolver")


# ------------------------------------------------------------
# Canonical Execution States (ENUM ONLY)
# ------------------------------------------------------------
class ExecutionState(Enum):
    EXECUTION_ALLOWED = auto()
    EXECUTION_BLOCKED_MISSING_ARTIFACTS = auto()
    EXECUTION_DEFERRED_CLARIFICATION = auto()
    EXECUTION_BLOCKED_UNSAFE = auto()
    EXECUTION_FAILED = auto()


# ------------------------------------------------------------
# FACT COLLAPSER (PURE FUNCTION)
# ------------------------------------------------------------
def resolve_execution_state(
    *,
    router_vector: Dict[str, Any],
    continuation_vector: Dict[str, Any],
    epistemic_vector: Dict[str, Any],
) -> ExecutionState:
    """
    Collapse factual signals into ONE ExecutionState.

    CONTRACT (Phase 38B):
        - router_vector MUST be a flat observation dict
        - orchestrator is responsible for flattening
        - this function refuses ambiguous input
    """

    # --------------------------------------------------------
    # DEV-ONLY SAFETY NET (prevents silent regressions)
    # --------------------------------------------------------
    if settings.DEV_ASSERTIONS_ENABLED:
        assert isinstance(router_vector, dict), "router_vector must be dict"
        assert "task_present" in router_vector, "router_vector missing 'task_present'"
        assert "system_safe" in router_vector, "router_vector missing 'system_safe'"

    # --------------------------------------------------------
    # Defensive reads (FACTS ONLY)
    # --------------------------------------------------------
    task_present = bool(router_vector.get("task_present", False))
    system_safe = bool(router_vector.get("system_safe", True))

    clarification_required = bool(
        epistemic_vector.get("clarification_required", False)
    )
    fatal_error = bool(epistemic_vector.get("fatal_error", False))

    # --------------------------------------------------------
    # Truth-table reduction — Phase 38 (unchanged)
    # --------------------------------------------------------

    # Hard failures
    if fatal_error:
        state = ExecutionState.EXECUTION_FAILED

    elif not system_safe:
        state = ExecutionState.EXECUTION_BLOCKED_UNSAFE

    # --------------------------------------------------------
    # TEMPORARY PROOF OVERRIDE (Phase 38 legacy, unchanged)
    # --------------------------------------------------------
    elif task_present and not clarification_required:
        state = ExecutionState.EXECUTION_ALLOWED

    # Epistemic gating (explicit clarification)
    elif clarification_required:
        state = ExecutionState.EXECUTION_DEFERRED_CLARIFICATION

    else:
        state = ExecutionState.EXECUTION_FAILED

    # --------------------------------------------------------
    # Phase 39: decision-level observability (no chatter)
    # --------------------------------------------------------
    logger.info(
        "[Phase39][FSM_RESOLVE]",
        extra={
            "task_present": task_present,
            "system_safe": system_safe,
            "clarification_required": clarification_required,
            "fatal_error": fatal_error,
            "resolved_state": state.name,
        },
    )

    return state


__all__ = [
    "ExecutionState",
    "resolve_execution_state",
]
