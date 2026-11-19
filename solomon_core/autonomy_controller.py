# autonomy_controller.py — Phase 40 Authority-Safe Autonomy Signals
# ---------------------------------------------------------------------------
# PURPOSE (Phase 40):
#   Emit autonomy-related signals ONLY.
#   No execution, no decisions, no semantic conclusions.
#
#   Orchestrator is the sole authority.
# ---------------------------------------------------------------------------

import datetime

from solomon_core.logger import get_logger
from solomon_core.reinforcement_store import get_weight
from solomon_core.autonomy.recomputation_controller import recompute_autonomy_stability
from solomon_core.db import SessionLocal
from solomon_core.models import AutonomyLog, TaskHistory
from solomon_core.autonomy.internal_tasks import generate_autonomous_tasks
from config import settings

logger = get_logger("autonomy_controller")

# ---------------------------------------------------------------------------
# HARD EXECUTION DENIAL (LOCKED)
# ---------------------------------------------------------------------------
_PHAS38_EXECUTION_DENIED = True

if _PHAS38_EXECUTION_DENIED is not True:
    raise RuntimeError("Autonomy execution authority enabled")

EXECUTION_AUTHORITY = False


# ===========================================================
# Autonomy Profile (DATA ONLY)
# ===========================================================

AUTONOMY_LEVELS = ("passive", "balanced", "active")

AutonomyProfile = {
    "level": "balanced",
    "idle_minutes": 10,
    "pattern_window": 5,
    "hflo_threshold": -2,
    "reinforcement_threshold": -5,
    "log_trigger_enabled": True,
}

_last_task_timestamp = None


def set_autonomy_level(level: str):
    level = level.lower()
    if level not in AUTONOMY_LEVELS:
        raise ValueError("Invalid autonomy level")
    AutonomyProfile["level"] = level
    logger.info("[Autonomy] Level updated")


def get_autonomy_profile():
    return dict(AutonomyProfile)


def record_task_event(task_text: str):
    global _last_task_timestamp
    _last_task_timestamp = datetime.datetime.utcnow()
    logger.debug("[Autonomy] Task event recorded")


# ===========================================================
# Trigger Signal Emitters
# ===========================================================

def _trigger_idle():
    if _last_task_timestamp is None:
        return False
    diff = datetime.datetime.utcnow() - _last_task_timestamp
    return diff.total_seconds() >= (AutonomyProfile["idle_minutes"] * 60)


def _trigger_pattern():
    session = SessionLocal()
    try:
        window = AutonomyProfile["pattern_window"]
        recent = (
            session.query(TaskHistory)
            .order_by(TaskHistory.timestamp.desc())
            .limit(window)
            .all()
        )

        if len(recent) < window:
            return False

        intents = [r.intent for r in recent]
        return len(set(intents)) == 1

    finally:
        session.close()


def _trigger_hflo():
    threshold = AutonomyProfile["hflo_threshold"]
    score = getattr(settings, "HFLO_RECENT_SCORE", 0)
    return score <= threshold


def _trigger_logs():
    if not AutonomyProfile.get("log_trigger_enabled", True):
        return False

    session = SessionLocal()
    try:
        recent = (
            session.query(TaskHistory)
            .order_by(TaskHistory.timestamp.desc())
            .limit(10)
            .all()
        )
        return sum(1 for r in recent if r.error_message) >= 3
    finally:
        session.close()


def _trigger_reinforcement():
    threshold = AutonomyProfile["reinforcement_threshold"]
    weight = get_weight("global-autonomy-signal")
    return weight <= threshold


# ===========================================================
# Trigger Signal Collection
# ===========================================================

def collect_trigger_signals():
    return {
        "idle": _trigger_idle(),
        "pattern": _trigger_pattern(),
        "hflo": _trigger_hflo(),
        "logs": _trigger_logs(),
        "reinforcement": _trigger_reinforcement(),
    }


# ===========================================================
# Gating Signals (NO DECISIONS)
# ===========================================================

STRICT_MODE = True
AUTONOMY_ENABLED = True


def collect_gating_signals():
    cooldown_minutes = getattr(settings, "HFLO_UPGRADE_INTERVAL_MINUTES", 30)

    session = SessionLocal()
    try:
        cutoff = datetime.datetime.utcnow() - datetime.timedelta(minutes=cooldown_minutes)
        recent_runs = (
            session.query(AutonomyLog)
            .filter(AutonomyLog.run_at >= cutoff)
            .count()
        )
    finally:
        session.close()

    stability = recompute_autonomy_stability()

    return {
        "enabled": AUTONOMY_ENABLED,
        "strict_mode": STRICT_MODE,
        "recent_runs": recent_runs,
        "autopause": stability.get("autopause"),
    }


# ===========================================================
# Unified Autonomy Signal Snapshot
# ===========================================================

def collect_autonomy_signals():
    """
    Phase 40:
      Returns a complete, non-authoritative autonomy signal snapshot.
    """
    trigger_signals = collect_trigger_signals()
    gating_signals = collect_gating_signals()
    profile = get_autonomy_profile()

    candidate_tasks = None
    if any(trigger_signals.values()):
        candidate_tasks = generate_autonomous_tasks(
            [k for k, v in trigger_signals.items() if v]
        )

    return {
        "profile": profile,
        "triggers": trigger_signals,
        "gating": gating_signals,
        "candidate_tasks": candidate_tasks,
        "execution_authorized": False,
    }


# ===========================================================
# Compatibility / Inspection Hooks (NO AUTHORITY)
# ===========================================================

def record_autonomy_run():
    logger.debug("[Autonomy] Autonomy cycle recorded (inspection only)")


# EOF
