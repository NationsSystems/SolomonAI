# solomon_core/routes/autonomy/autonomy_status_bp.py
# ------------------------------------------------------------------
# Autonomy Status API (Phase 9.11.6)
# Now protected under /admin/autonomy and admin-only.
# ------------------------------------------------------------------

from flask import Blueprint, jsonify
from sqlalchemy import func
from datetime import datetime, date, timedelta

from solomon_core.db import SessionLocal
from solomon_core.models import AutonomyLog, AutonomyStats
from solomon_core.autonomy.recomputation_controller import recompute_autonomy_stability
from solomon_core.auth_utils import login_required, admin_required  # ✅ NEW

# 🔵 Updated URL prefix under /admin/autonomy
autonomy_status_bp = Blueprint("autonomy_status_bp", __name__, url_prefix="/admin/autonomy")


@autonomy_status_bp.route("/status", methods=["GET"])
@login_required
@admin_required   # 🔐 ADMIN ONLY
def autonomy_status():
    """
    Returns JSON describing autonomy health + activity:
        {
            "today": { "new_skills": int, "upgrades": int },
            "last_run": { "timestamp": iso, "success": bool },
            "stability": { "autopause": bool, "reason": str }
        }
    """
    session = SessionLocal()

    try:
        # ---------------------------
        # Today’s autonomy statistics
        # ---------------------------
        today = date.today()
        stats = (
            session.query(AutonomyStats)
            .filter(AutonomyStats.stat_date == today)
            .first()
        )

        today_stats = {
            "new_skills": stats.new_skills if stats else 0,
            "upgrades": stats.upgrades if stats else 0,
        }

        # ---------------------------
        # Last autonomy run
        # ---------------------------
        last = (
            session.query(AutonomyLog)
            .order_by(AutonomyLog.run_at.desc())
            .first()
        )

        last_run = {
            "timestamp": last.run_at.isoformat() if last else None,
            "success": bool(last.success) if last else None,
        }

        # ---------------------------
        # Stability / Autopause
        # ---------------------------
        stability = recompute_autonomy_stability()

        return jsonify({
            "today": today_stats,
            "last_run": last_run,
            "stability": stability,
        })

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        session.close()
