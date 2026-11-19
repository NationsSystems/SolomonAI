# solomon_core/routes/metrics_bp.py
# -------------------------------------------------------
# Metrics blueprint extracted from app.py (safe refactor)
# Route parity: GET /admin/metrics  (admin-only)
# Phase 40G FIX: Metrics routes are READ-ONLY (NO mutation)
# -------------------------------------------------------

from flask import Blueprint, jsonify, render_template
from solomon_core.analytics import get_metrics
from solomon_core.auth_utils import login_required, admin_required
from solomon_core.solomon_tools.diagnostics import get_uptime, get_last_error
from solomon_core.solomon_tools.adaptive_router import (
    export_bias_summary,
    export_current_weights,
)
from config import settings
import os
import psutil
import time

# -------------------------------------------------------
# 🔥 All metrics now live under: /admin/metrics/...
# -------------------------------------------------------
metrics_bp = Blueprint("metrics", __name__, url_prefix="/admin")


# -------------------------------------------------------
# 1️⃣ Standard metrics (HTML dashboard)
# -------------------------------------------------------
@metrics_bp.route("/metrics", methods=["GET"])
@login_required
@admin_required
def metrics():
    """Render analytics dashboard (HTML view)."""
    try:
        from solomon_core.reinforcement_store import get_all_reinforcement

        data = get_metrics(limit=50)
        reinforcement = get_all_reinforcement()
        return render_template(
            "metrics.html",
            metrics_data=data,
            reinforcement_summary=reinforcement,
        )
    except Exception as e:
        import traceback
        return render_template(
            "error.html",
            error_message="Analytics unavailable",
            error_details=f"{e}\n{traceback.format_exc()}",
        ), 500


# -------------------------------------------------------
# 1️⃣b Pure JSON data endpoint
# -------------------------------------------------------
@metrics_bp.route("/metrics/data", methods=["GET"])
@login_required
@admin_required
def metrics_data():
    try:
        data = get_metrics(limit=50)
        return jsonify({
            "status": "ok",
            "summary": data.get("summary"),
            "by_reasoning_source": data.get("by_reasoning_source"),
            "by_intent": data.get("by_intent"),
            "recent": data.get("recent"),
        }), 200
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "trace": traceback.format_exc()
        }), 500


# -------------------------------------------------------
# 2️⃣ Reinforcement metrics (READ-ONLY)
# -------------------------------------------------------
@metrics_bp.route("/metrics/reinforcement", methods=["GET"])
@login_required
@admin_required
def reinforcement_metrics():
    try:
        from solomon_core.reinforcement_store import get_all_reinforcement
        data = get_all_reinforcement()
        return jsonify({"ok": True, "data": data}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# -------------------------------------------------------
# 3️⃣ System performance metrics
# -------------------------------------------------------
@metrics_bp.route("/metrics/system", methods=["GET"])
@login_required
@admin_required
def system_metrics():
    try:
        uptime = get_uptime()
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        log_dir = os.path.join(settings.BASE_DIR, "logs")

        return jsonify({
            "status": "ok",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "uptime": uptime,
            "cpu_percent": cpu_percent,
            "memory_used_mb": round(mem.used / (1024 ** 2), 2),
            "memory_total_mb": round(mem.total / (1024 ** 2), 2),
            "last_error": get_last_error()
        }), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# -------------------------------------------------------
# 4️⃣ Adaptive Router Bias (READ-ONLY — Phase 40G)
# -------------------------------------------------------
@metrics_bp.route("/metrics/adaptive", methods=["GET"])
@login_required
@admin_required
def adaptive_metrics():
    """
    Phase 40G:
    • EXPORT ONLY
    • NO adaptive bias updates allowed here
    """
    try:
        summary = export_bias_summary()
        return jsonify({"ok": True, "data": summary}), 200
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# -------------------------------------------------------
# 5️⃣ Adaptive Reasoning Weights (READ-ONLY)
# -------------------------------------------------------
@metrics_bp.route("/metrics/weights", methods=["GET"])
@login_required
@admin_required
def metrics_weights():
    try:
        from solomon_core.reinforcement_store import get_weight_history
        history = get_weight_history() or {}
        current_weights = export_current_weights()

        return jsonify({
            "ok": True,
            "weights": current_weights,
            "history": history.get("history", [])
        }), 200

    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
