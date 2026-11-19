# solomon_core/routes/metrics_api.py
# --------------------------------------------------------------------
# Admin Metrics API (Phase 9 Migration)
# Provides JSON endpoints for adaptive reasoning weights.
# New namespace: /admin/metrics/weights
# --------------------------------------------------------------------

from flask import Blueprint, jsonify, session
import os, json
from solomon_core.memory_store import read_memory_entries
from solomon_core.auth_utils import login_required, admin_required
from config import settings

# 🔥 NEW: admin namespace
metrics_api = Blueprint("metrics_api", __name__, url_prefix="/admin/metrics")


@metrics_api.route("/weights", methods=["GET"])
@login_required
@admin_required       # 🔐 Admin-only access
def get_weights():
    """Return current adaptive reasoning weights and adjustment history."""
    try:
        base_dir = os.path.join(settings.DATA_DIR, "memory")
        weights_file = os.path.join(base_dir, "weights.json")

        # Default values
        weights = {
            "deterministic": 0.6,
            "semantic": 0.3,
            "llm": 0.1
        }

        # Load override file if present
        if os.path.exists(weights_file):
            try:
                with open(weights_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        weights.update(loaded)
            except Exception as e:
                print(f"[metrics_api] Warning: failed to parse weights.json: {e}")

        # Load recent adaptation history
        history = []
        try:
            logs = read_memory_entries("auto_adjust", limit=20)
            for entry in logs:
                try:
                    history.append(json.loads(entry["data"]))
                except Exception:
                    continue
            history.sort(key=lambda e: e.get("timestamp", ""))
        except Exception as e:
            print(f"[metrics_api] Warning: could not read memory entries: {e}")

        return jsonify({
            "status": "ok",
            "weights": weights,
            "history": history
        }), 200

    except Exception as e:
        print(f"[metrics_api] /weights error: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "weights": {},
            "history": []
        }), 500
