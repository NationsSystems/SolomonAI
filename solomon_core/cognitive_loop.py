# cognitive_loop.py — Phase 18 Cognition Loop Stability Upgrade
# ------------------------------------------------------------
# Phase 18 Improvements:
#   • Planner confidence + reinforcement snapshot logging
#   • Cycle outcome typing (“success”, “skipped”, “error”)
#   • Safe isolation of HFLO operations
#   • Hardening against drift, deadlocks and silent failures
#   • Stable memory links for future KG v1 integration
# ------------------------------------------------------------

import time
import threading
from datetime import datetime, timedelta

from solomon_core.logger import get_logger

# Autonomy controllers
from solomon_core.autonomy_controller import (
    AUTONOMY_ENABLED,
    should_run_autonomy,
    record_autonomy_run,
)

# HFLO modules
from solomon_core.autonomy.hflo_engine import (
    run_hflo_retrospective_learning,
    apply_hflo_skill_upgrades,
)

# Reinforcement snapshot (Phase 18)
from solomon_core.reinforcement_store import get_reinforcement_snapshot

# DB models
from solomon_core.db import SessionLocal
from solomon_core.models import AutonomyLog

# Config
from config import settings

logger = get_logger("cognitive_loop")

_last_hflo_run = None
_last_hflo_upgrade_run = None


# ------------------------------------------------------------
# Internal helper — runs ONE autonomy cycle
# ------------------------------------------------------------
def _run_single_cycle() -> dict:
    """
    Runs a single operational cognition cycle.

    Returns a dict-shaped outcome, e.g.:
        { "ok": True, "type": "autonomy_success", "timestamp": "..." }
        { "ok": True, "type": "skipped", "timestamp": "..." }
        { "ok": False, "type": "error", "error": "..." }
    """

    # --------------------------------------------------------
    # Log autonomy cycle entry
    # --------------------------------------------------------
    session = SessionLocal()
    try:
        entry = AutonomyLog(
            run_at=datetime.utcnow(),
            intent="autonomous_reflection",
            reasoning_source="autonomy_engine",
            success=True,
            summary="Autonomy cycle executed in strict mode.",
        )
        session.add(entry)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"[cognitive_loop] Failed writing autonomy log: {e}")
        session.close()
        return {
            "ok": False,
            "type": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
    finally:
        session.close()

    logger.info("[cognitive_loop] ✓ Autonomy cycle base entry committed")

    # --------------------------------------------------------
    # Snapshot for Phase 18 cognition stability diagnostics
    # --------------------------------------------------------
    try:
        reinforcement_state = get_reinforcement_snapshot()
        logger.debug(f"[cognitive_loop] Reinforcement snapshot size: {len(reinforcement_state)}")
    except Exception as snapshot_err:
        logger.error(f"[cognitive_loop] reinforcement snapshot failed: {snapshot_err}")
        reinforcement_state = {}

    # --------------------------------------------------------
    # HFLO Retrospective Learning — Phase 10.3.3
    # --------------------------------------------------------
    global _last_hflo_run, _last_hflo_upgrade_run

    if not settings.HFLO_ENABLED:
        logger.debug("[cognitive_loop] HFLO disabled — skipping HFLO stages.")
        return {
            "ok": True,
            "type": "autonomy_success",
            "timestamp": datetime.utcnow().isoformat()
        }

    # Throttle HFLO learning
    if _last_hflo_run:
        next_allowed = _last_hflo_run + timedelta(
            minutes=settings.HFLO_UPGRADE_INTERVAL_MINUTES
        )
        if datetime.utcnow() < next_allowed:
            logger.debug("[cognitive_loop] HFLO learning throttled.")
            return {
                "ok": True,
                "type": "autonomy_success",
                "note": "HFLO throttled",
                "timestamp": datetime.utcnow().isoformat()
            }

    logger.info("[cognitive_loop] Running HFLO retrospective scan...")

    try:
        candidates = run_hflo_retrospective_learning()
        _last_hflo_run = datetime.utcnow()
    except Exception as lf_err:
        logger.error(f"[cognitive_loop] HFLO learning error: {lf_err}")
        return {
            "ok": False,
            "type": "error",
            "error": str(lf_err),
            "timestamp": datetime.utcnow().isoformat()
        }

    if not candidates:
        logger.debug("[cognitive_loop] HFLO found no candidates.")
        return {
            "ok": True,
            "type": "autonomy_success",
            "note": "no_hflo_candidates",
            "timestamp": datetime.utcnow().isoformat()
        }

    # --------------------------------------------------------
    # HFLO Skill Evolution — Phase 10.3.6
    # --------------------------------------------------------
    if _last_hflo_upgrade_run:
        next_upgrade_allowed = _last_hflo_upgrade_run + timedelta(
            minutes=settings.HFLO_UPGRADE_INTERVAL_MINUTES
        )
        if datetime.utcnow() < next_upgrade_allowed:
            logger.debug("[cognitive_loop] HFLO upgrades throttled.")
            return {
                "ok": True,
                "type": "autonomy_success",
                "note": "upgrade_throttled",
                "timestamp": datetime.utcnow().isoformat()
            }

    logger.info(f"[cognitive_loop] HFLO upgrading {len(candidates)} skills...")

    try:
        apply_hflo_skill_upgrades(candidates)
        _last_hflo_upgrade_run = datetime.utcnow()
        logger.info("[cognitive_loop] HFLO skill evolution complete.")
        return {
            "ok": True,
            "type": "autonomy_success",
            "note": "hflo_upgrade_complete",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as up_err:
        logger.error(f"[cognitive_loop] HFLO upgrade error: {up_err}")
        return {
            "ok": False,
            "type": "error",
            "error": str(up_err),
            "timestamp": datetime.utcnow().isoformat()
        }


# ------------------------------------------------------------
# INTERNAL — main loop (daemon)
# ------------------------------------------------------------
def _run_cognitive_loop_forever(interval_seconds=None):
    logger.info("[cognitive_loop] Autonomy loop started (daemon).")

    if interval_seconds is None:
        interval_seconds = settings.AUTONOMY_INTERVAL_SECONDS

    while AUTONOMY_ENABLED:
        try:
            if should_run_autonomy():
                logger.info("[cognitive_loop] Conditions met → running cycle...")
                result = _run_single_cycle()
                logger.debug(f"[cognitive_loop] Cycle result: {result}")
                record_autonomy_run()
            else:
                logger.debug("[cognitive_loop] Conditions NOT met → skipping.")

            time.sleep(interval_seconds)

        except Exception as e:
            logger.error(f"[cognitive_loop] Loop error: {e}")
            time.sleep(interval_seconds)


# ------------------------------------------------------------
# PUBLIC ENTRYPOINT — invoked automatically by app.py
# ------------------------------------------------------------
def start_cognitive_loop():
    logger.info("[cognitive_loop] Launching cognition loop (background thread)...")

    t = threading.Thread(
        target=_run_cognitive_loop_forever,
        args=(settings.AUTONOMY_INTERVAL_SECONDS,),
        daemon=True,
    )
    t.start()
    return t


__all__ = ["start_cognitive_loop"]
