# solomon_core/skills/run_diagnostics.py
# -----------------------------------------------------------
# Phase 22 — Unified Diagnostic Aggregator Micro-Skill (Strict)
#
# MUST expose a top-level function named `run()` so that
# resolve_micro_skill("skill_run_diagnostics") returns a callable
# that the micro-skill executor can invoke directly.
#
# Strict contract:
#   {
#       "ok": bool,
#       "result": {...},      # REQUIRED
#       "summary": "...",
#       "user_output": "...",
#       "skill": "skill_run_diagnostics"
#   }
# -----------------------------------------------------------

from solomon_core.logger import get_logger

from solomon_core.diagnostics.system_diagnostics import run as run_system
from solomon_core.diagnostics.skill_diagnostics import run as run_skill
from solomon_core.diagnostics.planner_diagnostics import run as run_planner
from solomon_core.diagnostics.memory_diagnostics import run as run_memory
from solomon_core.diagnostics.safety_diagnostics import run as run_safety

logger = get_logger("skill.run_diagnostics")


def _safe_run(fn, label):
    """Run a diagnostics module safely, preventing aggregation crash."""
    try:
        return fn()
    except Exception as e:
        logger.error(f"[run_diagnostics] {label} diagnostics failed: {e}")
        return {
            "ok": False,
            "summary": f"{label} failed: {e}",
            "metrics": {},
            "error": str(e),
        }


# -----------------------------------------------------------
# PHASE-22 MICRO-SKILL ENTRYPOINT
# -----------------------------------------------------------
def run(arguments=None):
    """
    Unified diagnostics aggregator.
    Phase-22 STRICT micro-skill entrypoint.
    """

    # Normalize arguments (strict deterministic behavior)
    if arguments is None or not isinstance(arguments, dict):
        arguments = {}

    logger.info("[run_diagnostics] Starting unified diagnostics...")

    # -----------------------------------------------------------
    # Run each diagnostics module safely
    # -----------------------------------------------------------
    system_result = _safe_run(run_system, "System")
    skill_result = _safe_run(run_skill, "Skills")
    planner_result = _safe_run(run_planner, "Planner")
    memory_result = _safe_run(run_memory, "Memory")
    safety_result = _safe_run(run_safety, "Safety")

    # -----------------------------------------------------------
    # Determine global OK state
    # -----------------------------------------------------------
    overall_ok = all([
        system_result.get("ok"),
        skill_result.get("ok"),
        planner_result.get("ok"),
        memory_result.get("ok"),
        safety_result.get("ok"),
    ])

    # -----------------------------------------------------------
    # Human-readable summary
    # -----------------------------------------------------------
    summary = (
        f"SYSTEM[{system_result.get('summary')}] | "
        f"SKILLS[{skill_result.get('summary')}] | "
        f"PLANNER[{planner_result.get('summary')}] | "
        f"MEMORY[{memory_result.get('summary')}] | "
        f"SAFETY[{safety_result.get('summary')}]"
    )

    # -----------------------------------------------------------
    # Phase-22 strict micro-skill contract
    # -----------------------------------------------------------
    packet = {
        "ok": bool(overall_ok),
        "result": {
            "system": system_result,
            "skills": skill_result,
            "planner": planner_result,
            "memory": memory_result,
            "safety": safety_result,
        },
        "summary": summary,
        "user_output": summary,
        "skill": "skill_run_diagnostics",
    }

    return packet


# -----------------------------------------------------------
# BACKWARD COMPATIBILITY (OPTIONAL)
# -----------------------------------------------------------
def execute(arguments=None):
    """Alias for older code paths."""
    return run(arguments)
