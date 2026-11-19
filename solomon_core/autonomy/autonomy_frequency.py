# autonomy_frequency.py — Phase 16 Step 3
# -------------------------------------------------------------
# AUTONOMY FREQUENCY ENFORCEMENT
#
# Purpose:
#   Encapsulate the rules that determine *how often*
#   Solomon is allowed to run autonomy cycles.
#
# Includes:
#   • Hourly autonomy cap
#   • Daily autonomy cap
#
# Notes:
#   • Isolated from strategic/operational logic
#   • Does not consider CPU/disk (handled in autonomy_safety.py)
#   • Does not consider skill/upgrade quotas (handled in autonomy_policy.py)
# -------------------------------------------------------------

from datetime import datetime, timedelta
from solomon_core.db import SessionLocal
from solomon_core.models import AutonomyLog
from config import settings


# -------------------------------------------------------------
# Pull limits from config
# -------------------------------------------------------------
MAX_AUTONOMY_RUNS_PER_HOUR = settings.AUTONOMY_SETTINGS["MAX_AUTONOMY_RUNS_PER_HOUR"]
MAX_AUTONOMY_TASKS_PER_DAY = settings.AUTONOMY_SETTINGS["MAX_AUTONOMY_TASKS_PER_DAY"]


# -------------------------------------------------------------
# Hourly Frequency Check
# -------------------------------------------------------------
def allow_autonomy_cycle():
    """
    Returns True if Solomon has not exceeded the maximum number
    of autonomy runs in the last hour.
    """
    db = SessionLocal()
    window = datetime.utcnow() - timedelta(hours=1)

    count = (
        db.query(AutonomyLog)
        .filter(AutonomyLog.created_at >= window)
        .count()
    )
    db.close()

    return count < MAX_AUTONOMY_RUNS_PER_HOUR


# -------------------------------------------------------------
# Daily Frequency Check
# -------------------------------------------------------------
def allow_daily_autonomy():
    """
    Returns True if Solomon has not exceeded the maximum number
    of autonomy tasks today.
    """
    db = SessionLocal()
    today = datetime.utcnow().date()

    # midnight of today
    start = datetime(today.year, today.month, today.day)

    count = (
        db.query(AutonomyLog)
        .filter(AutonomyLog.created_at >= start)
        .count()
    )
    db.close()

    return count < MAX_AUTONOMY_TASKS_PER_DAY


# -------------------------------------------------------------
# Explicit exports required by Phase 40G / Solomon boot
# -------------------------------------------------------------
def get_hourly_autonomy_usage():
    """
    Returns the number of autonomy runs in the last hour.
    """
    db = SessionLocal()
    window = datetime.utcnow() - timedelta(hours=1)
    count = db.query(AutonomyLog).filter(AutonomyLog.created_at >= window).count()
    db.close()
    return count


def get_daily_autonomy_usage():
    """
    Returns the number of autonomy tasks completed today.
    """
    db = SessionLocal()
    today = datetime.utcnow().date()
    start = datetime(today.year, today.month, today.day)
    count = db.query(AutonomyLog).filter(AutonomyLog.created_at >= start).count()
    db.close()
    return count
