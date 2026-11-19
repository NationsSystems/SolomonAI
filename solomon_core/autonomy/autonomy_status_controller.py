# autonomy_status_controller.py — Phase 9.11.5
# -----------------------------------------------------------
# Provides a clean telemetry API for Solomon autonomy.
# Used by the web UI and diagnostics to avoid unsafe
# assumptions about internal autonomy timing or stability.
# -----------------------------------------------------------

import datetime
from solomon_core.db import SessionLocal
from solomon_core.models import AutonomyLog
from solomon_core.autonomy_controller import (
    STRICT_MODE,
    AUTONOMY_ENABLED,
    should_autonomy_run,
)
from solomon_core.autonomy.recomputation_controller import (
    recompute_autonomy_stability,
)

def get_autonomy_status():
    """
    Collects autonomy telemetry for JSON output.
    """

    session = SessionLocal()
    now = datetime.datetime.utcnow()

    # ------------------------------
    # Last run
    # ------------------------------
    try:
        last_run = (
            session.query(AutonomyLog)
            .order_by(AutonomyLog.run_at.desc())
            .first()
        )
        last_run_time = last_run.run_at if last_run else None
    except:
        last_run_time = None

    # ------------------------------
    # Cooldown (strict mode)
    # ------------------------------
    cooldown_remaining = None
    if last_run_time and STRICT_MODE:
        diff = now - last_run_time
        minutes = diff.total_seconds() / 60.0
        if minutes < 30:
            cooldown_remaining = round(30 - minutes, 2)

    # ------------------------------
    # Stability recomputation
    # ------------------------------
    stability = recompute_autonomy_stability()

    # ------------------------------
    # 24h stats
    # ------------------------------
    try:
        cutoff = now - datetime.timedelta(hours=24)
        last24 = (
            session.query(AutonomyLog)
            .filter(AutonomyLog.run_at >= cutoff)
            .count()
        )
    except:
        last24 = None

    session.close()

    return {
        "ok": True,
        "autonomy_enabled": AUTONOMY_ENABLED,
        "strict_mode": STRICT_MODE,
        "allowed_to_run_now": should_autonomy_run(),
        "last_run": last_run_time.isoformat() if last_run_time else None,
        "cooldown_remaining_minutes": cooldown_remaining,
        "stability": stability,
        "runs_last_24h": last24,
        "timestamp": now.isoformat(),
    }
