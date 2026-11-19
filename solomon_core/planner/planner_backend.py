# solomon_core/planner/planner_backend.py
# ---------------------------------------------------------------------------
# Phase 38 — PLANNER BACKEND (SIGNAL-ONLY)
#
# GUARANTEES:
#   • NO LLM invocation
#   • NO execution authority
#   • NO planning performed here
#   • Planner backend emits REQUESTS, not plans
#   • Orchestrator is the sole authority allowed to invoke planners
#
# ROLE:
#   This module declares the planner contract and returns a
#   deterministic SIGNAL requesting a strict plan.
# ---------------------------------------------------------------------------

import uuid
from solomon_core.logger import get_logger

logger = get_logger("planner_backend")

PIPELINE_VERSION = "v23.5-strict"


# ---------------------------------------------------------------------------
# Phase-38 Authority Declaration
# ---------------------------------------------------------------------------
EXECUTION_AUTHORITY = False
PLANNER_AUTHORITY = False


# ---------------------------------------------------------------------------
# SIGNAL-ONLY planner request
# ---------------------------------------------------------------------------
def build_strict_plan(task_text: str, entities: dict = None) -> dict:
    """
    Phase 38:
        • This function does NOT build a plan
        • This function does NOT call any LLM
        • It returns a SIGNAL requesting a strict planner invocation
    """

    logger.info("[planner_backend] Emitting strict planner request (signal-only)")

    return {
        "ok": True,
        "signal": "REQUEST_STRICT_PLAN",
        "plan_id": str(uuid.uuid4()),
        "planner_mode": "strict",
        "pipeline_version": PIPELINE_VERSION,
        "task": task_text,
        "context": entities or {},
        "execution_authorized": False,
    }


# ---------------------------------------------------------------------------
# Readiness indicator (informational only)
# ---------------------------------------------------------------------------
def planner_backend_ready():
    return {
        "available": True,
        "pipeline_version": PIPELINE_VERSION,
        "mode": "strict",
        "execution_authorized": False,
    }
