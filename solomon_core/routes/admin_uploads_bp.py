# solomon_core/routes/admin_uploads_bp.py
# -----------------------------------------------------------
# Admin Upload Management — Phase 9.x
# Provides:
#   • GET /admin/uploads        → HTML UI
#   • GET /admin/uploads/       → JSON of all uploads (global)
# -----------------------------------------------------------

from flask import Blueprint, jsonify, render_template
from solomon_core.auth_utils import login_required, admin_required
from solomon_core.db import SessionLocal
from solomon_core.models import FileRegistry
import os

admin_uploads_bp = Blueprint("admin_uploads", __name__, url_prefix="/admin/uploads")


@admin_uploads_bp.route("", methods=["GET"])
@admin_uploads_bp.route("/", methods=["GET"])
@login_required
@admin_required
def uploads_ui():
    """Render the admin uploads page."""
    return render_template("uploads.html")


@admin_uploads_bp.route("/list", methods=["GET"])
@login_required
@admin_required
def list_all_uploads():
    """Return a list of all registered uploads from the database."""
    db = SessionLocal()
    try:
        rows = db.query(FileRegistry).order_by(FileRegistry.upload_time.desc()).all()

        files = []
        for f in rows:
            files.append({
                "id": f.id,
                "original_name": f.original_name,
                "random_name": f.random_name,
                "path": f.path,
                "size_bytes": f.size_bytes,
                "uploaded_by": f.uploader_id,
                "uploaded_at": f.upload_time.isoformat(),
            })

        return jsonify({"status": "ok", "count": len(files), "uploads": files})

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Failed to fetch uploads: {e}"
        }), 500

    finally:
        db.close()
