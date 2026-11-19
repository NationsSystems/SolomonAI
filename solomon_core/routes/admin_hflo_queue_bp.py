# admin_hflo_queue_bp.py — Phase 10.5.5 (Phase 40G Remediated)
# ---------------------------------------------------------------
# Admin API for managing the HFLO Pending Upgrade Queue.
#
# Provides:
#   GET    /admin/hflo_queue
#   POST   /admin/hflo_queue/approve/<id>
#   POST   /admin/hflo_queue/reject/<id>
#   DELETE /admin/hflo_queue/<id>
#
# Used by:
#   - Admin HFLO Review UI (Phase 10.5.6)
# ---------------------------------------------------------------

from flask import Blueprint, jsonify
from solomon_core.auth_utils import login_required, admin_required
from solomon_core.db import SessionLocal
from solomon_core.models import HfloPendingUpgrade

admin_hflo_queue_bp = Blueprint(
    "admin_hflo_queue",
    __name__,
    url_prefix="/admin/hflo_queue"
)


# ---------------------------------------------------------------
# GET — return all pending upgrades
# ---------------------------------------------------------------
@admin_hflo_queue_bp.route("/", methods=["GET"])
@login_required
@admin_required
def list_pending_upgrades():
    db = SessionLocal()
    try:
        rows = (
            db.query(HfloPendingUpgrade)
            .order_by(HfloPendingUpgrade.created_at.desc())
            .all()
        )

        result = []
        for r in rows:
            result.append({
                "id": r.id,
                "task_id": r.task_id,
                "action": r.action,
                "skill_name": r.skill_name,
                "python_code": r.python_code,
                "description": r.description,
                "reason": r.reason,
                "created_at": r.created_at.isoformat(),
                "reviewed": r.reviewed,
                "approved": r.approved,
                "metadata": r.metadata or {}
            })

        return jsonify({"ok": True, "items": result})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

    finally:
        db.close()


# ---------------------------------------------------------------
# POST — approve
# ---------------------------------------------------------------
@admin_hflo_queue_bp.route("/approve/<int:item_id>", methods=["POST"])
@login_required
@admin_required
def approve_item(item_id):
    db = SessionLocal()
    try:
        item = db.query(HfloPendingUpgrade).get(item_id)
        if not item:
            return jsonify({"ok": False, "error": "Item not found"})

        item.reviewed = True
        item.approved = True
        db.commit()

        return jsonify({"ok": True})

    except Exception as e:
        db.rollback()
        return jsonify({"ok": False, "error": str(e)})

    finally:
        db.close()


# ---------------------------------------------------------------
# POST — reject
# ---------------------------------------------------------------
@admin_hflo_queue_bp.route("/reject/<int:item_id>", methods=["POST"])
@login_required
@admin_required
def reject_item(item_id):
    db = SessionLocal()
    try:
        item = db.query(HfloPendingUpgrade).get(item_id)
        if not item:
            return jsonify({"ok": False, "error": "Item not found"})

        item.reviewed = True
        item.approved = False
        db.commit()

        return jsonify({"ok": True})

    except Exception as e:
        db.rollback()
        return jsonify({"ok": False, "error": str(e)})

    finally:
        db.close()


# ---------------------------------------------------------------
# DELETE — remove item
# ---------------------------------------------------------------
@admin_hflo_queue_bp.route("/<int:item_id>", methods=["DELETE"])
@login_required
@admin_required
def delete_item(item_id):
    db = SessionLocal()
    try:
        item = db.query(HfloPendingUpgrade).get(item_id)
        if not item:
            return jsonify({"ok": False, "error": "Item not found"})

        db.delete(item)
        db.commit()

        return jsonify({"ok": True})

    except Exception as e:
        db.rollback()
        return jsonify({"ok": False, "error": str(e)})

    finally:
        db.close()
