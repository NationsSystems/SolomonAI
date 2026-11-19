# admin_hflo_pending_bp.py — Phase 10.5.8 (Phase 63 UI Contract Completion)
# ---------------------------------------------------------------
# Backend API for HFLO Pending Upgrades review + approval system.
#
# Endpoints:
#   GET  /admin/hflo_pending              → UI PAGE
#   GET  /admin/hflo_pending/list          → list all pending items
#   GET  /admin/hflo_pending/get/<id>      → fetch a single item
#   POST /admin/hflo_pending/approve/<id>  → approve & apply
#   POST /admin/hflo_pending/reject/<id>   → reject
#   GET  /admin/hflo_pending/count         → pending count (dashboard)
# ---------------------------------------------------------------

from flask import Blueprint, jsonify, render_template
from solomon_core.auth_utils import login_required, admin_required
from solomon_core.db import SessionLocal
from solomon_core.models import HfloPendingUpgrade
from solomon_core.autonomy.hflo_engine import apply_hflo_skill_upgrades

admin_hflo_pending_bp = Blueprint(
    "admin_hflo_pending",
    __name__,
    url_prefix="/admin/hflo_pending"
)

# ---------------------------------------------------------------
# 0. UI PAGE
# ---------------------------------------------------------------
@admin_hflo_pending_bp.route("")
@admin_hflo_pending_bp.route("/")
@login_required
@admin_required
def pending_ui():
    """Render the HFLO Pending Review UI page."""
    return render_template("admin_hflo_pending.html")


# ---------------------------------------------------------------
# 1. COUNT PENDING ITEMS (DASHBOARD)
# ---------------------------------------------------------------
@admin_hflo_pending_bp.route("/count")
@login_required
@admin_required
def pending_count():
    db = SessionLocal()
    try:
        count = (
            db.query(HfloPendingUpgrade)
            .filter(HfloPendingUpgrade.reviewed == False)
            .count()
        )
        return jsonify({"ok": True, "count": count})
    finally:
        db.close()


# ---------------------------------------------------------------
# 2. LIST ALL PENDING ITEMS
# ---------------------------------------------------------------
@admin_hflo_pending_bp.route("/list")
@login_required
@admin_required
def list_pending():
    db = SessionLocal()
    try:
        items = (
            db.query(HfloPendingUpgrade)
            .filter(HfloPendingUpgrade.reviewed == False)
            .order_by(HfloPendingUpgrade.created_at.desc())
            .all()
        )

        result = []
        for item in items:
            result.append({
                "id": item.id,
                "task_id": item.task_id,
                "action": item.action,
                "skill_name": item.skill_name,
                "created_at": item.created_at.strftime("%Y-%m-%d %H:%M:%S")
            })

        return jsonify({"ok": True, "items": result})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

    finally:
        db.close()


# ---------------------------------------------------------------
# 3. GET A SINGLE PENDING ITEM
# ---------------------------------------------------------------
@admin_hflo_pending_bp.route("/get/<int:item_id>")
@login_required
@admin_required
def get_pending_item(item_id):
    db = SessionLocal()
    try:
        item = db.query(HfloPendingUpgrade).get(item_id)

        if not item:
            return jsonify({"ok": False, "error": "Item not found"})

        data = {
            "id": item.id,
            "task_id": item.task_id,
            "action": item.action,
            "skill_name": item.skill_name,
            "python_code": item.python_code,
            "description": item.description,
            "reason": item.reason,
            "metadata": item.metadata,
            "created_at": item.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "approved": item.approved,
            "reviewed": item.reviewed
        }

        return jsonify({"ok": True, "item": data})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

    finally:
        db.close()


# ---------------------------------------------------------------
# 4. APPROVE A PENDING HFLO UPGRADE (EXPLICIT HUMAN ACTION)
# ---------------------------------------------------------------
@admin_hflo_pending_bp.route("/approve/<int:item_id>", methods=["POST"])
@login_required
@admin_required
def approve_pending(item_id):
    db = SessionLocal()
    try:
        item = db.query(HfloPendingUpgrade).get(item_id)

        if not item:
            return jsonify({"ok": False, "error": "Item not found"})

        item.approved = True
        item.reviewed = True
        db.commit()

        # Explicit operator-approved execution
        apply_hflo_skill_upgrades([item.task_id])

        return jsonify({"ok": True})

    except Exception as e:
        db.rollback()
        return jsonify({"ok": False, "error": str(e)})

    finally:
        db.close()


# ---------------------------------------------------------------
# 5. REJECT A PENDING ITEM
# ---------------------------------------------------------------
@admin_hflo_pending_bp.route("/reject/<int:item_id>", methods=["POST"])
@login_required
@admin_required
def reject_pending(item_id):
    db = SessionLocal()
    try:
        item = db.query(HfloPendingUpgrade).get(item_id)

        if not item:
            return jsonify({"ok": False, "error": "Item not found"})

        item.approved = False
        item.reviewed = True
        db.commit()

        return jsonify({"ok": True})

    except Exception as e:
        db.rollback()
        return jsonify({"ok": False, "error": str(e)})

    finally:
        db.close()
