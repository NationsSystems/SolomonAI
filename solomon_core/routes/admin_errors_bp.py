# solomon_core/routes/admin_errors_bp.py
# -------------------------------------------------------
# Admin Error Sentinel Blueprint
# Provides:
#   • /admin/errors              → admin_errors.html (UI page)
#   • /admin/errors/data         → JSON recent error events
#   • /admin/errors/summary      → JSON error summary (NEW)
#   • /admin/errors/clear        → Clear all errors (POST)
#   • /admin/errors/delete/<id>  → Delete single error (POST)
# -------------------------------------------------------

from flask import Blueprint, jsonify, render_template
from solomon_core.auth_utils import login_required, admin_required
from solomon_core.db import SessionLocal
from sqlalchemy import text

# IMPORTANT:
# Variable name MUST match module name for auto-loader compatibility
admin_errors_bp = Blueprint("admin_errors", __name__, url_prefix="/admin")


# -------------------------------------------------------
# UI page: /admin/errors
# -------------------------------------------------------
@admin_errors_bp.route("/errors", methods=["GET"])
@login_required
@admin_required
def errors_page():
    """Render the errors UI page."""
    return render_template("admin_errors.html")


# -------------------------------------------------------
# JSON endpoint: /admin/errors/data
# -------------------------------------------------------
@admin_errors_bp.route("/errors/data", methods=["GET"])
@login_required
@admin_required
def errors_data():
    """Return recent error events in JSON format."""
    session = SessionLocal()
    try:
        rows = session.execute(text("""
            SELECT
                id,
                created_at,
                phase,
                error_type,
                message,
                traceback,
                count
            FROM error_events
            ORDER BY created_at DESC
            LIMIT 50
        """)).fetchall()

        result = []
        for r in rows:
            result.append({
                "id": r.id,
                "created_at": str(r.created_at),
                "phase": r.phase,
                "error_type": r.error_type,
                "message": r.message,
                "traceback": r.traceback,
                "count": r.count,
            })

        return jsonify({
            "status": "ok",
            "count": len(result),
            "errors": result
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to retrieve errors: {e}"
        }), 500

    finally:
        session.close()


# -------------------------------------------------------
# NEW: Summary endpoint — /admin/errors/summary
# -------------------------------------------------------
@admin_errors_bp.route("/errors/summary", methods=["GET"])
@login_required
@admin_required
def errors_summary():
    """
    Return a compact summary of recent errors for the navbar badge.
    Structure:
        {
            "status": "ok",
            "total": <int>,
            "types": { "<error_type>": count, ... },
            "recent_type": "<most_recent_error_type>"
        }
    """
    session = SessionLocal()
    try:
        rows = session.execute(text("""
            SELECT error_type, count
            FROM error_events
        """)).fetchall()

        if not rows:
            return jsonify({
                "status": "ok",
                "total": 0,
                "types": {},
                "recent_type": None
            }), 200

        type_counts = {}
        for r in rows:
            type_counts[r.error_type] = type_counts.get(r.error_type, 0) + r.count

        # Get the most recent type
        recent_row = session.execute(text("""
            SELECT error_type
            FROM error_events
            ORDER BY created_at DESC
            LIMIT 1
        """)).fetchone()

        recent_type = recent_row.error_type if recent_row else None

        return jsonify({
            "status": "ok",
            "total": sum(type_counts.values()),
            "types": type_counts,
            "recent_type": recent_type
        }), 200

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to summarize errors: {e}"
        }), 500

    finally:
        session.close()


# -------------------------------------------------------
# Clear all errors
# -------------------------------------------------------
@admin_errors_bp.route("/errors/clear", methods=["POST"])
@login_required
@admin_required
def errors_clear():
    """Clear all error events from the database."""
    session = SessionLocal()
    try:
        session.execute(text("DELETE FROM error_events"))
        session.commit()
        return jsonify({"status": "ok", "message": "All errors cleared."}), 200
    except Exception as e:
        session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Failed to clear errors: {e}"
        }), 500
    finally:
        session.close()


# -------------------------------------------------------
# Delete a single error by ID
# -------------------------------------------------------
@admin_errors_bp.route("/errors/delete/<int:error_id>", methods=["POST"])
@login_required
@admin_required
def errors_delete(error_id):
    """Delete a specific error event by ID."""
    session = SessionLocal()
    try:
        session.execute(
            text("DELETE FROM error_events WHERE id = :id"),
            {"id": error_id}
        )
        session.commit()
        return jsonify({"status": "ok", "message": f"Error {error_id} deleted."}), 200
    except Exception as e:
        session.rollback()
        return jsonify({
            "status": "error",
            "message": f"Failed to delete error: {e}"
        }), 500
    finally:
        session.close()
