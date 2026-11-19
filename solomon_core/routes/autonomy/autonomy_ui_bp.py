# solomon_core/routes/autonomy/autonomy_ui_bp.py
# -----------------------------------------------------------
# Autonomy UI Blueprint — Phase 9.12
# Now protected under /admin/autonomy and admin-only.
# -----------------------------------------------------------

from flask import Blueprint, render_template
from solomon_core.auth_utils import login_required, admin_required
from solomon_core.autonomy.recomputation_controller import recompute_autonomy_stability

# 🔥 New global admin namespace
autonomy_ui_bp = Blueprint("autonomy_ui", __name__, url_prefix="/admin/autonomy")


@autonomy_ui_bp.route("/", methods=["GET"])
@login_required
@admin_required
def autonomy_dashboard():
    """Render the main autonomy dashboard UI."""
    return render_template("autonomy.html")


# -----------------------------------------------------------
# NEW: Alias route so /admin/autonomy/ui works from navbar
# -----------------------------------------------------------
@autonomy_ui_bp.route("/ui", methods=["GET"])
@login_required
@admin_required
def autonomy_dashboard_alias():
    """Alias for dashboard, matching admin.html link."""
    return render_template("autonomy.html")


@autonomy_ui_bp.route("/stability", methods=["GET"])
@login_required
@admin_required
def autonomy_stability():
    """Return stability-only JSON for async polling."""
    stability = recompute_autonomy_stability()
    return stability
