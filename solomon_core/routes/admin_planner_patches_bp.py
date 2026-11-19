# solomon_core/routes/admin_planner_patches_bp.py — Phase 21 Strict Mode Stub (Phase 40G Remediated)
# ---------------------------------------------------------------------------
# Phase 21:
#   • The LLM planner folder has been permanently removed.
#   • Planner patching and rollback are NO-OP operations.
#
# Admin UI still needs:
#   • Patch list viewer
#   • Rollback button (for logging only)
#   • Patch/rollback logs to remain functional
#
# This stub:
#   • Never touches any planner files
#   • Never references llm_planner or PLANNER_PATH
#   • Logs rollback requests in DB only
# ---------------------------------------------------------------------------

from flask import Blueprint, render_template, request, redirect, url_for, flash
from solomon_core.auth_utils import login_required, admin_required
from solomon_core.db import SessionLocal
from solomon_core.models import PlannerPatchLog, PlannerRollbackLog
from solomon_core.logger import get_logger
from datetime import datetime

logger = get_logger("admin_planner_patches")

admin_planner_patches_bp = Blueprint(
    "admin_planner_patches",
    __name__,
    url_prefix="/admin/planner_patches",
    template_folder="../../webui/templates",
)

# ---------------------------------------------------------------------------
# LIST PATCHES (ADMIN ONLY)
# ---------------------------------------------------------------------------
@admin_planner_patches_bp.route("")
@admin_planner_patches_bp.route("/")
@login_required
@admin_required
def list_patches():
    db = SessionLocal()
    try:
        patches = (
            db.query(PlannerPatchLog)
            .order_by(PlannerPatchLog.applied_at.desc())
            .all()
        )
    finally:
        db.close()

    return render_template("admin_planner_patches.html", patches=patches)

# ---------------------------------------------------------------------------
# PHASE 21 ROLLBACK STUB (ADMIN ONLY)
# ---------------------------------------------------------------------------
@admin_planner_patches_bp.route("/rollback", methods=["POST"])
@login_required
@admin_required
def rollback_patch():
    """
    Phase 21:
        Rollback does NOT restore files.
        It only logs the rollback request.
    """

    patch_id = request.form.get("patch_id")
    if not patch_id:
        flash("Invalid rollback request (missing patch_id).", "error")
        return redirect(url_for("admin_planner_patches.list_patches"))

    db = SessionLocal()
    try:
        patch = db.query(PlannerPatchLog).filter(PlannerPatchLog.id == patch_id).first()
        if not patch:
            flash("Patch not found.", "error")
            return redirect(url_for("admin_planner_patches.list_patches"))

        # Log rollback (NO file operations)
        entry = PlannerRollbackLog(
            rollback_at=datetime.utcnow(),
            patch_id=patch.id,
            backup_path="phase21-strict-mode",
            restored_to_version="strict-mode-no-restore",
            reason="Manual rollback — Phase 21 strict mode",
        )

        db.add(entry)
        db.commit()

        flash(
            f"Rollback logged for patch #{patch.id} (Phase 21 strict mode — no file restore).",
            "success",
        )

    except Exception as e:
        db.rollback()
        logger.error(f"[PlannerRollback] Error during rollback: {e}")
        flash("Rollback failed due to internal error.", "error")

    finally:
        db.close()

    return redirect(url_for("admin_planner_patches.list_patches"))
