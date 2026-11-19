# solomon_core/autonomy/planner_learning_engine.py
# ------------------------------------------------------------------------
# Phase 38 — Planner Learning Engine (SIGNAL-ONLY)
#
# GUARANTEES:
#   • NO LLM calls
#   • NO code generation
#   • NO planner mutation
#   • NO execution authority
#   • Emits diagnostic signal ONLY
# ------------------------------------------------------------------------

from datetime import datetime, timedelta

from solomon_core.db import SessionLocal
from solomon_core.models import ExecutionLog, PlanLog
from solomon_core.logger import get_logger
from config import settings

logger = get_logger("planner_learning")

# ---------------------------------------------------------------------------
# Phase-38 Authority Declaration
# ---------------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # Planner learning is analysis-only


# ------------------------------------------------------------------------
# Fetch recent planner failures (read-only)
# ------------------------------------------------------------------------
def _fetch_recent_planner_failures():
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(
            hours=settings.HFLO_RETROSPECTIVE_WINDOW_HOURS
        )

        failures = (
            db.query(ExecutionLog)
            .filter(
                ExecutionLog.reasoning_source == "planner",
                ExecutionLog.created_at >= cutoff,
                (
                    (ExecutionLog.status == "error")
                    | (ExecutionLog.error_message != None)
                ),
            )
            .order_by(ExecutionLog.created_at.desc())
            .all()
        )

        return failures

    except Exception as e:
        logger.error(f"[PlannerLearn] Failed to fetch planner failures: {e}")
        return []

    finally:
        db.close()


# ------------------------------------------------------------------------
# Fetch PlanLog context (read-only)
# ------------------------------------------------------------------------
def _fetch_plan_context(failure):
    if not failure.plan_id:
        return None

    db = SessionLocal()
    try:
        return db.query(PlanLog).filter(PlanLog.id == failure.plan_id).first()
    except Exception:
        return None
    finally:
        db.close()


# ------------------------------------------------------------------------
# Summarize failure patterns (deterministic)
# ------------------------------------------------------------------------
def _summarize_failure_patterns(failures):
    patterns = {}

    for f in failures:
        msg = f.error_message or "Unknown planner error"
        msg = " ".join(msg.replace("\n", " ").replace("\r", " ").split())
        patterns[msg] = patterns.get(msg, 0) + 1

    return patterns


# ------------------------------------------------------------------------
# Public API — SIGNAL EMISSION ONLY
# ------------------------------------------------------------------------
def analyze_and_generate_planner_patch(
    *,
    skill_name=None,
    weakness_report=None,
    stability_report=None,
):
    """
    Phase-38 contract:
        • Observe planner failures
        • Emit diagnostic signal
        • NO LLM calls
        • NO patch generation
    """

    failures = _fetch_recent_planner_failures()

    if not failures:
        logger.debug("[PlannerLearn] No planner failures found.")
        return None

    patterns = _summarize_failure_patterns(failures)

    # HFLO threshold gate
    if all(count < settings.HFLO_MIN_FAILURES for count in patterns.values()):
        logger.debug("[PlannerLearn] Failure patterns below HFLO threshold.")
        return None

    signal = {
        "type": "planner_analysis_request",
        "schema": "PlannerLearning.Request.Analysis",
        "patterns": patterns,
        "context": {
            "skill_name": skill_name,
            "weakness_report": weakness_report,
            "stability_report": stability_report,
        },
        "metadata": {
            "signal_only": True,
            "window_hours": settings.HFLO_RETROSPECTIVE_WINDOW_HOURS,
            "generated_at": datetime.utcnow().isoformat(),
        },
    }

    logger.info(
        "[PlannerLearn] Emitting planner analysis signal (%d patterns)",
        len(patterns),
    )

    return {
        "ok": True,
        "result": signal,
        "user_output": None,
    }
