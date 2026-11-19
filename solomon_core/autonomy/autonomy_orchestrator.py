# autonomy_orchestrator.py — Phase 16 Step 7 (Option B)
# -------------------------------------------------------------
# AUTONOMY ORCHESTRATOR (Refactored)
#
# Purpose:
#   Clean separation between:
#     • Safety checks
#     • Frequency enforcement
#     • Skill/upgrade quotas
#     • Strategic/operational mode selection
#     • Action execution (placeholder logic in Phase 16)
#
# Notes:
#   • Phase 17 will implement the full autonomy cognitive loop.
#   • For Phase 16, operational and strategic branches are stubs.
# -------------------------------------------------------------

from solomon_core.logger import get_logger

# Submodules created in Phase 16
from solomon_core.autonomy.autonomy_safety import system_safe_to_run
from solomon_core.autonomy.autonomy_frequency import (
    allow_autonomy_cycle,
    allow_daily_autonomy,
)
from solomon_core.autonomy.autonomy_policy import (
    allow_new_skill,
    allow_upgrade,
)
from solomon_core.autonomy.strict_autonomy_controller import (
    strategic_trigger_check,
)

logger = get_logger("autonomy_orchestrator")


# =============================================================
# Phase 16 Step 7 — Clean placeholder action runners
# =============================================================
def run_strategic_autonomy():
    """
    Placeholder for strategic autonomy execution.
    Real implementation added in Phase 17.
    """
    logger.info("[Autonomy] Strategic autonomy cycle executed (placeholder)")
    return {
        "mode": "strategic",
        "executed": True,
        "details": "Strategic autonomy placeholder logic",
    }


def run_operational_autonomy():
    """
    Placeholder for operational autonomy execution.
    Real implementation added in Phase 17.
    """
    logger.info("[Autonomy] Operational autonomy cycle executed (placeholder)")
    return {
        "mode": "operational",
        "executed": True,
        "details": "Operational autonomy placeholder logic",
    }


# =============================================================
# Phase 16 — Unified Autonomy Decision Pipeline
# =============================================================
def run_autonomy_cycle():
    """
    Unified autonomy pipeline:
        1. Safety check
        2. Frequency limits
        3. Strategic override check
        4. Skill/upgrade quota checks
        5. Execute chosen mode
    """

    logger.info("[Autonomy] Starting autonomy orchestration cycle")

    # ---------------------------------------------------------
    # Step 1: System Safety Check
    # ---------------------------------------------------------
    safe, reason = system_safe_to_run()
    if not safe:
        return {
            "success": False,
            "mode": None,
            "reason": f"Safety block: {reason}",
        }

    # ---------------------------------------------------------
    # Step 2: Frequency enforcement
    # ---------------------------------------------------------
    if not allow_autonomy_cycle():
        return {
            "success": False,
            "mode": None,
            "reason": "Hourly autonomy limit reached",
        }

    if not allow_daily_autonomy():
        return {
            "success": False,
            "mode": None,
            "reason": "Daily autonomy limit reached",
        }

    # ---------------------------------------------------------
    # Step 3: Strategic override
    # ---------------------------------------------------------
    strategic_ok, strategic_reason = strategic_trigger_check()
    if strategic_ok:
        logger.info("[Autonomy] Strategic autonomy selected")
        result = run_strategic_autonomy()
        return {**result, "success": True}

    # ---------------------------------------------------------
    # Step 4: Operational fallback (only if strategic blocked)
    # ---------------------------------------------------------
    logger.info(f"[Autonomy] Strategic blocked: {strategic_reason}")
    logger.info("[Autonomy] Operational autonomy selected")

    result = run_operational_autonomy()
    return {
        **result,
        "success": True,
        "reason": f"Strategic blocked: {strategic_reason}",
    }


# =============================================================
# Simple test function (for manual testing)
# =============================================================
def autonomy_status_preview():
    """
    Returns a lightweight preview of what the autonomy cycle
    *would* do right now, without executing it.
    """
    safe, reason = system_safe_to_run()
    strategic_ok, strategic_reason = strategic_trigger_check()

    return {
        "safe": safe,
        "safe_reason": reason,
        "strategic_allowed": strategic_ok,
        "strategic_reason": strategic_reason,
        "hourly_ok": allow_autonomy_cycle(),
        "daily_ok": allow_daily_autonomy(),
        "skill_allowed": allow_new_skill(),
        "upgrade_allowed": allow_upgrade(),
    }


# EOF
