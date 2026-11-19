# solomon_core/skills/run_planner_diagnostics.py
# -----------------------------------------------------------
# Phase 38 — Planner Diagnostics Micro-Skill (SIGNAL ONLY)
#
# GUARANTEES:
#   • NO diagnostics execution
#   • NO subsystem calls
#   • Emits diagnostic request ONLY
#   • Orchestrator is sole execution authority
# -----------------------------------------------------------

from solomon_core.logger import get_logger

logger = get_logger("skill_run_planner_diagnostics")

# ---------------------------------------------------------------------------
# Phase-38 Authority Declaration
# ---------------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # Skills may NEVER execute diagnostics


def execute(arguments: dict | None = None):
    """
    Phase-38 micro-skill contract:
        • Accepts arguments (ignored)
        • Emits diagnostic request signal
        • Does NOT execute diagnostics
    """

    try:
        diagnostic_request = {
            "type": "planner_diagnostics",
            "schema": "DiagnosticsRequest.Planner",
            "metadata": {
                "skill": "run_planner_diagnostics",
                "signal_only": True,
            },
        }

        logger.info("[run_planner_diagnostics] Emitting planner diagnostics signal")

        return {
            "ok": True,
            "schema": "DiagnosticsRequest.Planner",
            "result": diagnostic_request,
            "user_output": None,
        }

    except Exception as e:
        logger.error(f"[run_planner_diagnostics] Signal construction error: {e}")
        return {
            "ok": False,
            "schema": "DiagnosticsRequest.Planner",
            "error": str(e),
            "user_output": "Unable to construct planner diagnostics request.",
        }
