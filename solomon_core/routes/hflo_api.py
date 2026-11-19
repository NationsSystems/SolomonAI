# solomon_core/routes/hflo_api.py
# --------------------------------------------------------------
# Internal HFLO API — Phase 18 Step 1 Upgrade
#
# Purpose:
#   • Accept + validate HFLO feedback signals
#   • Properly route HFLO → reinforcement store
#   • Trigger HFLO correction engine when negative
#   • Prepare feedback envelope for future KG integration
# --------------------------------------------------------------

from flask import Blueprint, jsonify, session
from solomon_core.db import SessionLocal
from solomon_core.models import Feedback, HfloPendingUpgrade
from solomon_core.auth_utils import login_required
from solomon_core.logger import get_logger

# HFLO Engine
from solomon_core.autonomy.hflo_engine import run_hflo

# Reinforcement Store (Phase 18)
from solomon_core.reinforcement_store import update_reinforcement

logger = get_logger("hflo_api")

hflo_api = Blueprint("hflo_api", __name__)


# --------------------------------------------------------------
# Internal helper
# --------------------------------------------------------------
def _store_feedback(db, task_id, feedback_type, user_id):
    """Internal helper to store feedback into DB."""
    fb = Feedback(
        task_id=task_id,
        skill_name=None,
        reasoning_type=None,
        feedback_type=feedback_type,
        user_id=user_id,
    )
    db.add(fb)
    db.commit()
    return fb


# --------------------------------------------------------------
# Positive Feedback
# --------------------------------------------------------------
@hflo_api.route("/feedback/positive/<task_id>", methods=["POST"])
@login_required
def feedback_positive(task_id):
    """Record positive feedback + reinforcement update."""
    db = SessionLocal()

    try:
        if not task_id or task_id.strip() == "":
            return jsonify({"ok": False, "error": "Missing or invalid task_id"}), 400

        fb = _store_feedback(db, task_id, "positive", session.get("user_id"))

        # Phase 18 — reinforcement learning impact
        update_reinforcement(task_id, delta=+1)
        logger.info(f"[HFLO] (+) Positive reinforcement applied for task {task_id}")

        return jsonify({"ok": True})

    except Exception as e:
        db.rollback()
        logger.error(f"[HFLO] Error logging positive feedback: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        db.close()


# --------------------------------------------------------------
# Negative Feedback + Immediate HFLO Correction
# --------------------------------------------------------------
@hflo_api.route("/feedback/negative/<task_id>", methods=["POST"])
@login_required
def feedback_negative(task_id):
    """Record negative feedback, reinforcement signal, and perform correction."""
    db = SessionLocal()

    try:
        if not task_id or task_id.strip() == "":
            return jsonify({"ok": False, "error": "Missing or invalid task_id"}), 400

        # Log feedback
        fb = _store_feedback(db, task_id, "negative", session.get("user_id"))
        logger.info(f"[HFLO] (-) Negative feedback recorded for task {task_id}")

        # Phase 18 — reinforcement learning impact
        update_reinforcement(task_id, delta=-1)
        logger.info(f"[HFLO] (-) Negative reinforcement applied for task {task_id}")

        # ------------------------------------------------------
        # HFLO Envelope (Phase 18)
        # ------------------------------------------------------
        original_task = session.get("last_task_text")
        original_output = session.get("last_task_output")

        if not original_task:
            original_task = ""
            logger.warning("[HFLO] Missing last_task_text in session.")

        if not original_output:
            original_output = ""
            logger.warning("[HFLO] Missing last_task_output in session.")

        hflo_envelope = {
            "task_id": task_id,
            "original_task": original_task,
            "original_output": original_output,
            "user_id": session.get("user_id"),
        }

        # Run correction cycle
        corrected_output = run_hflo(**hflo_envelope)

        return jsonify({
            "ok": True,
            "corrected_output": corrected_output
        })

    except Exception as e:
        db.rollback()
        logger.error(f"[HFLO] Error logging negative feedback: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        db.close()


# --------------------------------------------------------------
# HFLO Pending Count Endpoint  (Phase 10.5 — Still Required)
# --------------------------------------------------------------
@hflo_api.route("/api/hflo_pending/count", methods=["GET"])
@login_required
def hflo_pending_count():
    """Return number of pending HFLO upgrades."""
    db = SessionLocal()
    try:
        count = db.query(HfloPendingUpgrade).filter_by(reviewed=False).count()
        return jsonify({"ok": True, "count": count})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    finally:
        db.close()
