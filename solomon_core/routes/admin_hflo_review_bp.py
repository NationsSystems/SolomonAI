# admin_hflo_review_bp.py — Phase 10.5.5 (Phase 40G Remediated)
# ---------------------------------------------------------------
# Provides the admin UI for reviewing proposed HFLO skill upgrades:
#   • List pending HFLO-generated skill changes
#   • View details and simulation output
#   • Approve or reject upgrades (API handles logic)
# ---------------------------------------------------------------

from flask import Blueprint, render_template
from solomon_core.auth_utils import login_required, admin_required
from solomon_core.db import SessionLocal
from solomon_core.models import SkillUpgradeLog  # used for history
from solomon_core.models import SkillRegistry    # for viewing current code

admin_hflo_review_bp = Blueprint(
    "admin_hflo_review",
    __name__,
    url_prefix="/admin/hflo_review",
    template_folder="../../webui/templates"
)

# ---------------------------------------------------------------
# List all pending HFLO-generated skill upgrades
# ---------------------------------------------------------------
@admin_hflo_review_bp.route("/")
@login_required
@admin_required
def review_list():
    db = SessionLocal()
    try:
        upgrade_history = (
            db.query(SkillUpgradeLog)
            .order_by(SkillUpgradeLog.created_at.desc())
            .all()
        )
    finally:
        db.close()

    return render_template(
        "admin_hflo_review.html",
        upgrades=upgrade_history
    )


# ---------------------------------------------------------------
# View a specific proposed upgrade
# ---------------------------------------------------------------
@admin_hflo_review_bp.route("/<int:upgrade_id>")
@login_required
@admin_required
def review_detail(upgrade_id):
    db = SessionLocal()
    try:
        record = db.query(SkillUpgradeLog).filter(
            SkillUpgradeLog.id == upgrade_id
        ).first()

        if not record:
            return render_template("error.html", message="Upgrade not found")

    finally:
        db.close()

    return render_template(
        "admin_hflo_review_detail.html",
        record=record
    )
