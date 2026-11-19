# recomputation_controller.py — Phase 9.11.3
# ------------------------------------------------------
# Monitors autonomy stability using:
#   • skill creation rates
#   • upgrade frequencies
#   • recent autonomy failures
#
# Produces a stability flag used by:
#   cognitive_loop.py
#   autonomy_controller.py
#
# Strict Mode = always allow autonomy
# Adaptive Mode = dynamically throttle autonomy
# ------------------------------------------------------

from datetime import datetime, timedelta
from solomon_core.db import SessionLocal, Skill  # ✅ Skill comes from db.py
from solomon_core.models import AutonomyLog, SkillUpgradeLog
from solomon_core.logger import get_logger

# NEW — bring in HFLO/autonomy parameters for future adaptive mode
from config import settings

logger = get_logger("recompute_autonomy")


# ------------------------------------------------------
# Strict-mode controller always returns a safe YES
# ------------------------------------------------------
def recompute_autonomy_stability_strict():
    """
    Phase 9.11 Option A (STRICT MODE):
    Autonomy always stays enabled unless the last run produced
    a fatal internal error.
    """
    session = SessionLocal()
    try:
        last = (
            session.query(AutonomyLog)
            .order_by(AutonomyLog.run_at.desc())
            .first()
        )
    except Exception:
        session.close()
        return {"ok": True, "stable": True, "reason": "DB unavailable, default allow"}

    session.close()

    # No data → assume stable
    if not last:
        return {"ok": True, "stable": True, "reason": "No autonomy history"}

    # Only block if last run had a fatal error
    if last.error_count and last.error_count > 5:
        return {
            "ok": True,
            "stable": False,
            "reason": "Recent autonomy failure threshold exceeded",
        }

    return {"ok": True, "stable": True, "reason": "Strict mode always allows autonomy"}


# ------------------------------------------------------
# Adaptive-mode logic (Phase 9.11 — disabled until beta)
# ------------------------------------------------------
def recompute_autonomy_stability():
    """
    Unified dual-interface.
    Strict mode is active for now.
    Adaptive mode will be activated in Phase 11 when:
        • HFLO learning signals accumulate
        • upgrade frequency exceeds safe thresholds
        • autonomy cycles spike too quickly
        • user feedback indicates uncertainty
    """

    # Future-ready logging for adaptive triggers
    logger.debug(
        f"[Autonomy Stability] HFLO enabled: {settings.HFLO_ENABLED}, "
        f"Upgrade interval: {settings.HFLO_INTERVAL_MINUTES} min, "
        f"Autonomy interval: {settings.AUTONOMY_INTERVAL_SECONDS} sec"
    )

    # Strict mode for now
    return recompute_autonomy_stability_strict()
