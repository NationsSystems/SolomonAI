# solomon_core/routes/feedback_api.py — Phase 11.5 HFLO Harmony Layer
# -------------------------------------------------------------------
# This module exposes REST endpoints for:
#   • simple HFLO feedback (👍 / 👎)
#   • correction submissions
#   • pending upgrade requests
#
# All data flows into:
#   • Feedback table
#   • Correction table
#   • HfloPendingUpgrade table
#
# This is the final requirement of Phase 11.5

from flask import Blueprint, request, jsonify
from datetime import datetime
from solomon_core.db import SessionLocal
from solomon_core.models import Feedback, Correction, HfloPendingUpgrade
from solomon_core.logger import get_logger

logger = get_logger("feedback_api")

feedback_bp = Blueprint("feedback_api", __name__)

# -------------------------------------------------------------
# Helper: safe extract
# -------------------------------------------------------------
def _get_json():
    try:
        return request.get_json(force=True, silent=True) or {}
    except Exception:
        return {}


# -------------------------------------------------------------
# 1) Simple HFLO Feedback  (👍 / 👎)
# -------------------------------------------------------------
@feedback_bp.route("/api/feedback", methods=["POST"])
def submit_feedback():
    data = _get_json()

    task_id = data.get("task_id")
    feedback_type = data.get("feedback_type")  # like/dislike
    user_id = data.get("user_id")
    skill_name = data.get("skill_name")
    reasoning_type = data.get("reasoning_type")

    if not task_id or not feedback_type:
        return jsonify({"ok": False, "error": "task_id and feedback_type required"}), 400

    db = SessionLocal()
    try:
        row = Feedback(
            task_id=task_id,
            user_id=user_id,
            feedback_type=feedback_type,
            skill_name=skill_name,
            reasoning_type=reasoning_type,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()

        logger.info(f"[HFLO] Feedback stored: {feedback_type} for task {task_id}")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"[HFLO] Feedback insert error: {e}")
        return jsonify({"ok": False, "error": str(e)})
    finally:
        db.close()


# -------------------------------------------------------------
# 2) Corrections (user fixes an output)
# -------------------------------------------------------------
@feedback_bp.route("/api/feedback/correction", methods=["POST"])
def submit_correction():
    data = _get_json()

    task_id = data.get("task_id")
    original = data.get("original_output")
    corrected = data.get("corrected_output")
    notes = data.get("notes")
    user_id = data.get("user_id")
    skill_name = data.get("skill_name")
    reasoning_type = data.get("reasoning_type")

    if not task_id or not corrected:
        return jsonify({"ok": False, "error": "task_id and corrected_output required"}), 400

    db = SessionLocal()
    try:
        row = Correction(
            task_id=task_id,
            original_output=original,
            corrected_output=corrected,
            correction_notes=notes,
            skill_name=skill_name,
            reasoning_type=reasoning_type,
            user_id=user_id,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()

        logger.info(f"[HFLO] Correction stored for task {task_id}")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"[HFLO] Correction insert error: {e}")
        return jsonify({"ok": False, "error": str(e)})
    finally:
        db.close()


# -------------------------------------------------------------
# 3) Pending Upgrade Queue (Phase 10.3)
# -------------------------------------------------------------
@feedback_bp.route("/api/feedback/upgrade", methods=["POST"])
def submit_upgrade():
    data = _get_json()

    task_id = data.get("task_id")
    action = data.get("action")  # "upgrade" | "create" | "review"
    skill_name = data.get("skill_name")
    code = data.get("python_code")
    reason = data.get("reason")
    description = data.get("description")
    meta = data.get("meta")
    user_id = data.get("user_id")

    if not task_id or not action:
        return jsonify({"ok": False, "error": "task_id and action required"}), 400

    db = SessionLocal()
    try:
        row = HfloPendingUpgrade(
            task_id=task_id,
            action=action,
            skill_name=skill_name,
            python_code=code,
            reason=reason,
            description=description,
            meta=meta,
            reviewed=False,
            approved=None,
            created_at=datetime.utcnow(),
        )
        db.add(row)
        db.commit()

        logger.info(f"[HFLO] Upgrade queued for task {task_id} → {action}")
        return jsonify({"ok": True})
    except Exception as e:
        logger.error(f"[HFLO] Upgrade insert error: {e}")
        return jsonify({"ok": False, "error": str(e)})
    finally:
        db.close()
