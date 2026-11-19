# solomon_core/autonomy/hflo_engine.py
# ---------------------------------------------------------------
# Phase 38 — Human Feedback Learning & Optimization (HFLO)
#
# GUARANTEES:
#   • SIGNAL-ONLY
#   • NO LLM calls
#   • NO skill mutation
#   • NO planner patch application
#   • NO execution authority
#   • Orchestrator is sole execution authority
# ---------------------------------------------------------------

import json
from datetime import datetime, timedelta

from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal
from solomon_core.models import Feedback, Correction

from config import settings

logger = get_logger("hflo_engine")

# ---------------------------------------------------------------------------
# Phase-38 Authority Declaration
# ---------------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # HFLO may NEVER execute changes


# ==================================================================
# PHASE 38 — HFLO SIGNAL CONSTRUCTION
# ==================================================================
def run_hflo(task_id: str, original_task: str, original_output: str):
    """
    Phase-38:
        • Inspect feedback
        • Emit HFLO correction request
        • NO correction execution
    """

    db = SessionLocal()

    try:
        fb = (
            db.query(Feedback)
            .filter(
                Feedback.task_id == task_id,
                Feedback.feedback_type == "negative"
            )
            .order_by(Feedback.created_at.desc())
            .first()
        )

        if not fb:
            return None

        signal = {
            "type": "hflo_correction_request",
            "schema": "HFLO.Request.Correction",
            "task_id": task_id,
            "original_task": original_task,
            "original_output": original_output,
            "user_id": fb.user_id,
            "metadata": {
                "signal_only": True,
                "requested_at": datetime.utcnow().isoformat(),
            },
        }

        logger.info("[HFLO] Emitting correction request signal for task %s", task_id)

        return {
            "ok": True,
            "result": signal,
            "user_output": None,
        }

    finally:
        db.close()


# ==================================================================
# PHASE 38 — RETROSPECTIVE LEARNING (SIGNAL-ONLY)
# ==================================================================
def run_hflo_retrospective_learning():
    """
    Phase-38:
        • Detect repeated failures
        • Emit learning candidate signal
    """

    db = SessionLocal()

    try:
        window_start = datetime.utcnow() - timedelta(
            hours=settings.HFLO_RETROSPECTIVE_WINDOW_HOURS
        )

        recent = (
            db.query(Feedback)
            .filter(
                Feedback.feedback_type == "negative",
                Feedback.created_at >= window_start,
            )
            .all()
        )

        if not recent:
            return []

        freq = {}
        for fb in recent:
            freq[fb.task_id] = freq.get(fb.task_id, 0) + 1

        candidates = [
            tid for tid, count in freq.items()
            if count >= settings.HFLO_MIN_FAILURES
        ]

        if not candidates:
            return []

        signal = {
            "type": "hflo_retrospective_request",
            "schema": "HFLO.Request.Retrospective",
            "candidates": candidates,
            "metadata": {
                "signal_only": True,
                "window_hours": settings.HFLO_RETROSPECTIVE_WINDOW_HOURS,
            },
        }

        logger.info("[HFLO] Emitting retrospective learning signal (%d candidates)", len(candidates))

        return {
            "ok": True,
            "result": signal,
            "user_output": None,
        }

    finally:
        db.close()


# ==================================================================
# PHASE 38 — SKILL / PLANNER EVOLUTION (SIGNAL-ONLY)
# ==================================================================
def apply_hflo_skill_upgrades(candidates: list):
    """
    Phase-38:
        • Emit HFLO evolution request
        • NO upgrades applied here
    """

    if not candidates:
        return None

    signal = {
        "type": "hflo_evolution_request",
        "schema": "HFLO.Request.Evolution",
        "candidates": candidates,
        "metadata": {
            "signal_only": True,
            "allow_skill_upgrades": settings.HFLO_ALLOW_SKILL_UPGRADES,
            "allow_micro_skills": settings.HFLO_ALLOW_MICROSKILLS,
        },
    }

    logger.info("[HFLO] Emitting evolution request for %d candidates", len(candidates))

    return {
        "ok": True,
        "result": signal,
        "user_output": None,
    }
