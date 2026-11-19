# skill_quality_engine.py — Phase 20 Step 2
# --------------------------------------------------------------
# Solomon Skill Quality Scoring Engine (SQSE)
#
# Purpose:
#   • Compute quality scores for each skill using:
#       - ExecutionLog successes/failures
#       - Recent performance (last 20 runs)
#       - Runtime durations
#       - Error frequency from Error Sentinel (Phase 19)
#       - HFLO feedback and corrections
#       - Reinforcement weight (Phase 18)
#   • Provide get_skill_quality(), get_all_skill_qualities()
#   • Prepare intelligence signals for cognition, routing,
#     planner decisions, auto-patching, and HFLO ranking.
#
# Output: JSON-ready dicts with normalized 0–100 scores.
# --------------------------------------------------------------

from datetime import datetime, timedelta
from sqlalchemy import text
from solomon_core.db import SessionLocal
from solomon_core.logger import get_logger

# Model imports
from solomon_core.models import (
    ExecutionLog,
    SkillRegistry,
    Feedback,
    Correction,
)

# Phase 19 error intelligence
from solomon_core.cognition.error_trend_analyzer import get_error_trend_summary

# Phase 18 reinforcement
from solomon_core.reinforcement_store import get_reinforcement_weight

logger = get_logger("skill_quality_engine")


# --------------------------------------------------------------
# Utility helpers
# --------------------------------------------------------------
def _normalize(v, max_v):
    """Normalize a metric into 0–1 range safely."""
    if max_v <= 0:
        return 0.0
    v = max(0.0, min(v, max_v))
    return v / max_v


def _safe_ratio(a, b):
    if b == 0:
        return 0.0
    return a / b


# --------------------------------------------------------------
# Core scoring function
# --------------------------------------------------------------
def score_skill(skill_name: str) -> dict:
    """
    Main scoring routine. Computes a 0–100 quality score
    using weighted metrics.
    """

    db = SessionLocal()
    try:
        # ------------------------------------------------------
        # 1) Pull execution history (recent + total)
        # ------------------------------------------------------
        recent = (
            db.query(ExecutionLog)
            .filter(ExecutionLog.skill_name == skill_name)
            .order_by(ExecutionLog.id.desc())
            .limit(20)
            .all()
        )

        total = (
            db.query(ExecutionLog)
            .filter(ExecutionLog.skill_name == skill_name)
            .count()
        )

        if not recent:
            # Skills with no history start neutral
            return {
                "skill_name": skill_name,
                "score": 50.0,
                "reason": "no_history",
                "metrics": {},
                "timestamp": datetime.utcnow().isoformat(),
            }

        successes = sum(1 for r in recent if r.status == "success")
        errors = sum(1 for r in recent if r.status == "error")
        avg_success_rate = _safe_ratio(successes, len(recent))

        # Execution duration
        durations = []
        for r in recent:
            if r.started_at and r.finished_at:
                delta = (r.finished_at - r.started_at).total_seconds()
                durations.append(max(delta, 0))

        avg_duration = sum(durations) / len(durations) if durations else 0.0
        duration_penalty = _normalize(avg_duration, 5.0)  # 5 sec = full penalty

        # ------------------------------------------------------
        # 2) HFLO signals
        # ------------------------------------------------------
        feedback_pos = (
            db.query(Feedback)
            .filter(Feedback.skill_name == skill_name, Feedback.feedback_type == "positive")
            .count()
        )

        feedback_neg = (
            db.query(Feedback)
            .filter(Feedback.skill_name == skill_name, Feedback.feedback_type == "negative")
            .count()
        )

        corrections = (
            db.query(Correction)
            .filter(Correction.skill_name == skill_name)
            .count()
        )

        hfl_ratio = _safe_ratio(feedback_pos - corrections, max(1, feedback_pos + feedback_neg + corrections))

        # ------------------------------------------------------
        # 3) Reinforcement signals (Phase 18)
        # ------------------------------------------------------
        reinforcement = get_reinforcement_weight(skill_name) or 0.0

        # ------------------------------------------------------
        # 4) Error trends (Phase 19)
        # ------------------------------------------------------
        error_trends = get_error_trend_summary() or {}
        regressions = error_trends.get("regressions", [])

        # Penalize if this skill appears in recent regressions
        regression_penalty = 0.0
        for r in regressions:
            if skill_name in r.get("message", ""):
                regression_penalty += 0.15  # ~15% score hit

        # ------------------------------------------------------
        # 5) Quality score composition
        # ------------------------------------------------------
        score = (
            avg_success_rate * 0.55 +          # primary weight
            (1 - duration_penalty) * 0.10 +    # runtime efficiency
            (hfl_ratio + 1) / 2 * 0.15 +       # HFLO bias (–1..1 → 0..1)
            _normalize(reinforcement, 10) * 0.15 +    # reinforcement
            (1 - regression_penalty) * 0.05          # stability + error pressure
        )

        score = max(0.0, min(score, 1.0)) * 100.0

        return {
            "skill_name": skill_name,
            "score": round(score, 2),
            "metrics": {
                "avg_success_rate": round(avg_success_rate, 3),
                "avg_duration": round(avg_duration, 3),
                "feedback_pos": feedback_pos,
                "feedback_neg": feedback_neg,
                "corrections": corrections,
                "reinforcement": reinforcement,
                "regression_penalty": regression_penalty,
            },
            "total_executions": total,
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"[SkillQuality] Scoring error for '{skill_name}': {e}")
        return {
            "skill_name": skill_name,
            "score": 0.0,
            "reason": "scoring_error",
            "error": str(e),
        }
    finally:
        db.close()


# --------------------------------------------------------------
# Public API
# --------------------------------------------------------------
def get_skill_quality(skill_name: str):
    return score_skill(skill_name)


def get_all_skill_qualities():
    """Return quality scores for all skills in SkillRegistry."""
    db = SessionLocal()
    try:
        rows = db.query(SkillRegistry.skill_name).all()
        names = [r[0] for r in rows]
        return [score_skill(n) for n in names]
    finally:
        db.close()
