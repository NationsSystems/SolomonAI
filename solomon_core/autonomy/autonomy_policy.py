# autonomy_policy.py — Phase 16 Step 2
# -------------------------------------------------------------
# DAILY AUTONOMY LIMITS AND QUOTAS
#
# Purpose:
#   Encapsulate daily counters and enforcement rules for:
#       • New skill creation limits
#       • Skill upgrade limits
#       • Daily autonomy run counters (shared by autonomy controllers)
#
# Notes:
#   • Interacts with AutonomyStats table only
#   • No CPU/disk checks (handled in autonomy_safety.py)
#   • No strategic/operational decisions here
# -------------------------------------------------------------

from datetime import datetime
from solomon_core.db import SessionLocal
from solomon_core.models import AutonomyStats
from config import settings


# -------------------------------------------------------------
# Pull limits from config
# -------------------------------------------------------------
MAX_NEW_SKILLS_PER_DAY = settings.AUTONOMY_SETTINGS["MAX_NEW_SKILLS_PER_DAY"]
MAX_UPGRADES_PER_DAY = settings.AUTONOMY_SETTINGS["MAX_UPGRADES_PER_DAY"]


# -------------------------------------------------------------
# Get (or create) today's entry in AutonomyStats
# -------------------------------------------------------------
def get_today_stats(db):
    today = datetime.utcnow().date()

    stat = (
        db.query(AutonomyStats)
        .filter(AutonomyStats.stat_date == today)
        .first()
    )

    if stat is None:
        stat = AutonomyStats(
            stat_date=today,
            new_skills=0,
            upgrades=0,
        )
        db.add(stat)
        db.commit()
        db.refresh(stat)

    return stat


# -------------------------------------------------------------
# Allowance checks
# -------------------------------------------------------------
def allow_new_skill():
    """
    Returns True if Solomon has not exceeded today's new skill limit.
    """
    db = SessionLocal()
    allowed = get_today_stats(db).new_skills < MAX_NEW_SKILLS_PER_DAY
    db.close()
    return allowed


def allow_upgrade():
    """
    Returns True if Solomon has not exceeded today's upgrade limit.
    """
    db = SessionLocal()
    allowed = get_today_stats(db).upgrades < MAX_UPGRADES_PER_DAY
    db.close()
    return allowed


# -------------------------------------------------------------
# Recording events
# -------------------------------------------------------------
def record_new_skill():
    """
    Increment today's new skill counter.
    """
    db = SessionLocal()
    stat = get_today_stats(db)
    stat.new_skills += 1
    db.commit()
    db.close()


def record_upgrade():
    """
    Increment today's skill upgrade counter.
    """
    db = SessionLocal()
    stat = get_today_stats(db)
    stat.upgrades += 1
    db.commit()
    db.close()
