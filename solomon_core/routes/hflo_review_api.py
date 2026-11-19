# hflo_review_api.py — Phase 10.5.5 (Review & Simulation API)
# ---------------------------------------------------------------
# Provides backend endpoints for the HFLO admin review system.
#
# Capabilities:
#   • Run safe sandbox simulation for proposed skill code
#   • Approve a proposed upgrade (EXPLICIT ADMIN ACTION)
#   • Reject a proposed upgrade (EXPLICIT ADMIN ACTION)
#   • Return structured JSON for frontend
#
# NOTE (Phase 40G):
#   • All state-changing actions are ADMIN-GATED
#   • No autonomous execution or inference authority
# ---------------------------------------------------------------

from flask import Blueprint, jsonify
from datetime import datetime

from solomon_core.db import SessionLocal
from solomon_core.models import SkillRegistry, SkillUpgradeLog
from solomon_core.autonomy.skill_simulation_engine import simulate_skill_execution
from solomon_core.auth_utils import login_required, admin_required

hflo_review_api = Blueprint("hflo_review_api", __name__, url_prefix="/api/hflo_review")


# ---------------------------------------------------------------
# RUN SIMULATION (READ-ONLY)
# ---------------------------------------------------------------
@hflo_review_api.route("/simulate/<int:upgrade_id>", methods=["GET"])
@login_required
@admin_required
def simulate_upgrade(upgrade_id):
    db = SessionLocal()
    try:
        record = (
            db.query(SkillUpgradeLog)
            .filter(SkillUpgradeLog.id == upgrade_id)
            .first()
        )

        if not record:
            return jsonify({"ok": False, "error": "Upgrade not found"}), 404

        python_code = record.new_code
        if not python_code:
            return jsonify({"ok": False, "error": "No code to simulate"}), 400

        # Run code in HFLO sandbox (no persistence)
        result = simulate_skill_execution(python_code)

        return jsonify({"ok": True, "simulation": result})

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        db.close()


# ---------------------------------------------------------------
# APPROVE UPGRADE (EXPLICIT ADMIN ACTION)
# ---------------------------------------------------------------
@hflo_review_api.route("/approve/<int:upgrade_id>", methods=["POST"])
@login_required
@admin_required
def approve_upgrade(upgrade_id):
    db = SessionLocal()
    try:
        record = db.query(SkillUpgradeLog).filter(
            SkillUpgradeLog.id == upgrade_id
        ).first()

        if not record:
            return jsonify({"ok": False, "error": "Upgrade not found"}), 404

        skill_name = record.skill_name
        new_code = record.new_code
        summary = record.summary

        skill = (
            db.query(SkillRegistry)
            .filter(SkillRegistry.skill_name == skill_name)
            .first()
        )

        if not skill:
            return jsonify({"ok": False, "error": "Skill not found"}), 400

        # Apply upgrade (explicit admin-controlled state change)
        skill.python_code = new_code
        skill.version += 1
        skill.updated_at = datetime.utcnow()

        db.commit()

        return jsonify({
            "ok": True,
            "message": f"Skill '{skill_name}' upgraded to version {skill.version}.",
            "summary": summary
        })

    except Exception as e:
        db.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        db.close()


# ---------------------------------------------------------------
# REJECT UPGRADE (EXPLICIT ADMIN ACTION)
# ---------------------------------------------------------------
@hflo_review_api.route("/reject/<int:upgrade_id>", methods=["POST"])
@login_required
@admin_required
def reject_upgrade(upgrade_id):
    db = SessionLocal()
    try:
        record = (
            db.query(SkillUpgradeLog)
            .filter(SkillUpgradeLog.id == upgrade_id)
            .first()
        )

        if not record:
            return jsonify({"ok": False, "error": "Upgrade not found"}), 404

        # Mark as rejected
        record.summary = f"(REJECTED) {record.summary}"
        record.model_name = "REJECTED"
        record.updated_at = datetime.utcnow()

        db.commit()

        return jsonify({
            "ok": True,
            "message": "Upgrade rejected."
        })

    except Exception as e:
        db.rollback()
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        db.close()
