# strict_autonomy_controller.py — Phase 40 Authority-Safe Autonomy Signals
# ---------------------------------------------------------------------------
# PURPOSE (Phase 40):
#   Emit autonomy *signals only*. No decisions, no enforcement,
#   no user-language exceptions.
#
#   Orchestrator is the sole authority.
# ---------------------------------------------------------------------------

from datetime import datetime
import psutil

from solomon_core.db import SessionLocal
from solomon_core.models import AutonomyLog
from solomon_core.logger import get_logger

from solomon_core.autonomy.autonomy_safety import system_safe_to_run
from solomon_core.autonomy.autonomy_frequency import (
    get_hourly_autonomy_usage,
    get_daily_autonomy_usage,
)

from solomon_core.cognition.error_trend_analyzer import get_error_trend_summary
from solomon_core.knowledge.knowledge_sync import sync_knowledge_graph

from config import settings

logger = get_logger("strict_autonomy")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
ENABLE_STRATEGIC_AUTONOMY = settings.AUTONOMY_SETTINGS["ENABLE_STRATEGIC_AUTONOMY"]
STRATEGIC_CPU_THRESHOLD = settings.AUTONOMY_SETTINGS["STRATEGIC_CPU_THRESHOLD"]
STRATEGIC_MINUTES_SINCE_LAST_CYCLE = settings.AUTONOMY_SETTINGS[
    "STRATEGIC_MINUTES_SINCE_LAST_CYCLE"
]


# ---------------------------------------------------------------------------
# Stability Signal
# ---------------------------------------------------------------------------
def get_stability_signal():
    summary = get_error_trend_summary()
    score = summary.get("stability_score", 100.0)

    if score >= 80:
        band = "stable"
    elif score >= 50:
        band = "caution"
    elif score >= 30:
        band = "unstable"
    else:
        band = "critical"

    return {
        "stability_score": score,
        "stability_band": band,
    }


# ---------------------------------------------------------------------------
# Strategic Eligibility Signal
# ---------------------------------------------------------------------------
def get_strategic_eligibility_signal():
    cpu = psutil.cpu_percent(interval=0.1)
    cpu_ok = cpu <= STRATEGIC_CPU_THRESHOLD

    db = SessionLocal()
    last = (
        db.query(AutonomyLog)
        .filter(AutonomyLog.autonomy_type == "strategic")
        .order_by(AutonomyLog.created_at.desc())
        .first()
    )
    db.close()

    minutes_since = None
    time_ok = True

    if last:
        minutes_since = (datetime.utcnow() - last.created_at).total_seconds() / 60
        time_ok = minutes_since >= STRATEGIC_MINUTES_SINCE_LAST_CYCLE

    return {
        "enabled": ENABLE_STRATEGIC_AUTONOMY,
        "cpu_ok": cpu_ok,
        "cpu_usage": cpu,
        "time_ok": time_ok,
        "minutes_since_last": minutes_since,
    }


# ---------------------------------------------------------------------------
# Frequency Signals
# ---------------------------------------------------------------------------
def get_frequency_signal():
    return {
        "hourly_cycles": get_hourly_autonomy_usage(),
        "daily_cycles": get_daily_autonomy_usage(),
    }


# ---------------------------------------------------------------------------
# Safety Signal
# ---------------------------------------------------------------------------
def get_system_safety_signal():
    safe, code = system_safe_to_run()
    return {
        "safe": safe,
        "code": code,
    }


# ---------------------------------------------------------------------------
# Unified Signal Snapshot (NO DECISIONS)
# ---------------------------------------------------------------------------
def collect_autonomy_signals():
    """
    Emits a complete, non-authoritative snapshot for the orchestrator.
    """

    # Side-effect allowed (sync), no decision
    sync_knowledge_graph(limit_memory=20, limit_tasks=20)

    return {
        "stability": get_stability_signal(),
        "strategic": get_strategic_eligibility_signal(),
        "frequency": get_frequency_signal(),
        "safety": get_system_safety_signal(),
    }


# ---------------------------------------------------------------------------
# Strategic Trigger Check (Phase-40 Signal-Only)
# ---------------------------------------------------------------------------
def strategic_trigger_check():
    """
    Advisory signal indicating whether strategic autonomy is eligible to run.
    Signal-only, no enforcement, no authority.
    """
    eligibility = get_strategic_eligibility_signal()
    # Return True only if enabled, CPU is OK, and timing window satisfied
    return eligibility["enabled"] and eligibility["cpu_ok"] and eligibility["time_ok"]


# ---------------------------------------------------------------------------
# Should Autonomy Run (Phase-40 Signal-Only)
# ---------------------------------------------------------------------------
def should_autonomy_run():
    """
    Returns an advisory boolean signal indicating whether any autonomy
    cycle is eligible to run, combining safety, frequency, and strategic checks.
    Signal-only, no execution authority.
    """
    safety = get_system_safety_signal()
    frequency = get_frequency_signal()
    strategic = get_strategic_eligibility_signal()

    return safety["safe"] and frequency["hourly_cycles"] < settings.AUTONOMY_SETTINGS["MAX_AUTONOMY_RUNS_PER_HOUR"] and strategic["enabled"]


# ---------------------------------------------------------------------------
# TEST OVERRIDE SIGNAL (NON-AUTHORITATIVE)
# ---------------------------------------------------------------------------
_TEST_OVERRIDE_MODE = None


def set_test_override_mode(mode: str):
    global _TEST_OVERRIDE_MODE
    _TEST_OVERRIDE_MODE = mode
    return True


def clear_test_override_mode():
    global _TEST_OVERRIDE_MODE
    _TEST_OVERRIDE_MODE = None
    return True


def get_test_override_signal():
    return {"override_mode": _TEST_OVERRIDE_MODE}


# EOF
