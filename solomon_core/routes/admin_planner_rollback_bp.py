# admin_planner_rollback_bp.py — Phase 21 Strict-Mode Rollback Stub (Phase 40G Remediated)
# ---------------------------------------------------------------------------
# Phase 21:
#   • Planner is no longer patchable.
#   • Rollbacks MUST still appear in the admin UI.
#   • Rollbacks MUST still be logged to database.
#   • NO file restoration is ever performed.
#
# This stub:
#   • Removes PLANNER_PATH completely
#   • Never touches any planner files
#   • Logs rollback requests safely
#   • Fully replaces the old Phase 10.4 implementation
# ---------------------------------------------------------------------------

from flask import Blueprint, render_template, request, jsonify
from sqlalchemy import desc
from datetime import datetime

from solomon_core.auth_utils import login_required, admin_required
from solomon_core.db import SessionLocal
from solomon_core.models import PlannerPatchLog, PlannerRollbackLog

admin_planner_rollback_bp = Blueprint(
    "admin_planner_rollback",
    __name__,
    url_prefix="/admin/planner_rollback",
    template_folder="../../webui/templates"
)

# ---------------------------------------------------------------------------
# VIEW ROLLBACK HISTORY (ADMIN ONLY)
# ---------------------------------------------------------------------------
@admin_planner_rollback_bp.route("/", methods=["GET"])
@login_required
@admin_required
def rollback_history():
    session = SessionLocal()
    try:
        rollbacks = (
            session.query(PlannerRollbackLog)
            .order_by(desc(PlannerRollbackLog.rollback_at))
            .all()
        )
        patches = (
            session.query(PlannerPatchLog)
            .order_by(desc(PlannerPatchLog.applied_at))
            .all()
        )
    finally:
        session.close()

    return render_template(
        "admin_planner_rollback.html",
        rollbacks=rollbacks,
        patches=patches
    )

# ---------------------------------------------------------------------------
# STRICT-MODE ROLLBACK (NO FILE RESTORE — ADMIN ONLY)
# ---------------------------------------------------------------------------
@admin_planner_rollback_bp.route("/run/<int:patch_id>", methods=["POST"])
@login_required
@admin_required
def run_rollback(patch_id: int):

    session = SessionLocal()

    try:
        patch = session.query(PlannerPatchLog).filter_by(id=patch_id).first()
        if not patch:
            return jsonify({"ok": False, "error": "Patch not found"}), 404

        reason = None
        if request.is_json:
            reason = request.json.get("reason")

        # Phase 21: Log rollback ONLY — no file operations
        rb = PlannerRollbackLog(
            rollback_at=datetime.utcnow(),
            patch_id=patch_id,
            reason=reason or "Manual rollback — Phase 21 strict mode",
            backup_path="phase21-strict-mode",
            restored_to_version="strict-mode-no-restore"
        )

        session.add(rb)
        session.commit()

        return jsonify({"ok": True, "phase21": True})

    except Exception as e:
        session.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        session.close()
