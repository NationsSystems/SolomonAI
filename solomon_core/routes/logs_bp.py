# solomon_core/routes/logs_bp.py
# -------------------------------------------------------
# Admin Logs Blueprint
# Provides:
#   • /admin/logs       → logs.html (UI page)
#   • /admin/logs/data  → JSON recent task logs
# -------------------------------------------------------

from flask import Blueprint, jsonify, render_template, session
from solomon_core.auth_utils import login_required, admin_required
from solomon_core.memory_store import get_recent_tasks

# ✅ Renamed variable to match module name for auto-loader compatibility
logs_bp = Blueprint("logs", __name__, url_prefix="/admin")


# -------------------------------------------------------
# UI page: /admin/logs
# -------------------------------------------------------
@logs_bp.route("/logs", methods=["GET"])
@login_required
@admin_required
def logs_page():
    """Render logs UI page."""
    return render_template("logs.html")


# -------------------------------------------------------
# JSON endpoint: /admin/logs/data
# -------------------------------------------------------
@logs_bp.route("/logs/data", methods=["GET"])
@login_required
@admin_required
def logs_data():
    """Return last N task executions in JSON format."""
    try:
        recent = get_recent_tasks(limit=50)
        return jsonify({
            "status": "ok",
            "count": len(recent),
            "recent_tasks": recent,
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to retrieve logs: {e}"
        }), 500
