# task_loop.py — Phase 21 Strict Pipeline Stub (Upgraded for Phase 23.5 Orchestration)
# ---------------------------------------------------------------------------
# Phase 21:
#   • Deterministic planner engine fully removed.
#   • Strict Planner Pipeline executes ONLY inside solomon_core.run_task().
#
# Phase 23.5:
#   • SAFE orchestration detection ONLY
#   • NO execution authority
#
# Phase 38 FIX:
#   • Explicit non-authoritative module
#   • Hard guard against misuse as execution boundary
#
# Phase 52.1:
#   • Structural Neutralization
#   • All heuristic orchestration detection removed
# ---------------------------------------------------------------------------

from solomon_core.logger import get_logger
from solomon_core.error_sentinel import record_error

logger = get_logger("task_loop")

# ---------------------------------------------------------------------------
# Phase-38 Authority Declaration (MANDATORY)
# ---------------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # This module may NEVER execute tasks


# ============================================================================
# Phase-23.5 Orchestration Detection (NEUTRALIZED)
# ============================================================================
def detect_phase23_5_orchestration(entities: dict):
    """
    Phase 52.1 — Structural Neutralization

    All orchestration detection logic has been removed.
    This function intentionally returns None unconditionally.

    No inference.
    No routing.
    No domain signaling.
    """
    return None


# ============================================================================
# Deterministic path removed (legacy stub)
# ============================================================================
def execute_deterministic(*args, **kwargs):
    logger.error(
        "[Phase38Violation] execute_deterministic() invoked — execution authority removed"
    )
    return {
        "ok": False,
        "error": "Deterministic execution removed in Phase 21",
        "meta": {"reason": "deprecated"},
    }


# ============================================================================
# Planned-step execution stub (SAFE BRIDGE ONLY)
# ============================================================================
def execute_planned_steps(plan: dict, entities: dict):
    """
    Phase-38 GUARANTEE:
        • This function does NOT execute anything
        • Returns detection results ONLY
        • Any attempt to treat output as execution is a violation
    """

    if EXECUTION_AUTHORITY:
        raise RuntimeError(
            "[Phase38Violation] task_loop has no execution authority"
        )

    try:
        orchestration = detect_phase23_5_orchestration(entities or {})
        if orchestration:
            return orchestration

        logger.warning(
            "[task_loop] execute_planned_steps() called but no orchestration matched"
        )

        return {
            "ok": False,
            "error": "No valid orchestration (execution deprecated)",
            "meta": {"reason": "deprecated_phase21"},
            "execution_authorized": False,
        }

    except Exception as e:
        record_error(
            phase="task-loop",
            error_type=type(e).__name__,
            message=str(e),
            tb="",
        )
        return {
            "ok": False,
            "error": str(e),
            "meta": {"reason": "exception"},
            "execution_authorized": False,
        }


__all__ = [
    "detect_phase23_5_orchestration",
    "execute_planned_steps",
    "EXECUTION_AUTHORITY",
]
