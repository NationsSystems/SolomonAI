# ---------------------------------------------------------------------------
# FILE: health_bp.py
# DIRECTORY: solomon_core/routes/
# ---------------------------------------------------------------------------
# Health and Diagnostics Blueprint
#
# PURPOSE:
#   Provide authenticated administrative liveness, readiness, evaluator,
#   recovery-review, and controlled failure-drill endpoints.
#
# READINESS CONTRACT:
#   - The web lane remains non-authoritative and excluded from readiness.
#   - The configured SIS execution service is the intelligence boundary.
#   - Local model files are not required while SIS execution is enabled.
#   - Readiness checks consume the Flask-owned SIS availability snapshot.
# ---------------------------------------------------------------------------

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path

from flask import Blueprint, jsonify, request
from sqlalchemy import text

from config import settings
from solomon_core.auth_utils import (
    admin_required,
    login_required,
)
from solomon_core.db import engine, init_db
from solomon_core.intelligence_service.intelligence_service_client import (
    get_intelligence_service_health,
)
from solomon_core.llm.llm_transport import (
    direct_model_files_available,
)
from solomon_core.solomon_tools.evaluator import (
    summarize_performance,
)


health_bp = Blueprint(
    "health",
    __name__,
    url_prefix="/admin/health",
)

HEALTH_CACHE = {
    "last_check": 0,
    "ready_state": None,
    "recent_recovery": [],
}

UPLOAD_DIR = settings.UPLOADS_DIR


# ---------------------------------------------------------------------------
# Local Model Checks
# ---------------------------------------------------------------------------

def _model_files_available(
    model_path: str | Path,
) -> bool:
    """Return whether one local Transformers model folder is complete."""

    path = Path(model_path)

    if not path.exists() or not path.is_dir():
        return False

    has_config = (path / "config.json").exists()
    has_tokenizer = (
        (path / "tokenizer.json").exists()
        or (path / "tokenizer_config.json").exists()
    )
    has_weights = (
        any(path.glob("*.safetensors"))
        or any(path.glob("*.bin"))
    )

    return has_config and has_tokenizer and has_weights


def _embedding_model_files_available() -> bool:
    """Return whether the configured local embedding model is present."""

    try:
        return _model_files_available(
            settings.WORKSPACE_ACTION_SELECTOR_MODEL_PATH
        )
    except Exception:
        return False


# ---------------------------------------------------------------------------
# 1. Live Check
# ---------------------------------------------------------------------------

@health_bp.route("/live", methods=["GET"])
@login_required
@admin_required
def health_live():
    return jsonify(
        {
            "status": "alive",
            "timestamp": time.time(),
        }
    ), 200


# ---------------------------------------------------------------------------
# 2. Evaluator Performance Summary
# ---------------------------------------------------------------------------

@health_bp.route("/evaluator", methods=["GET"])
@login_required
@admin_required
def health_evaluator():
    try:
        data = summarize_performance()

        return jsonify(
            {
                "status": "ok",
                "message": (
                    "Evaluation metrics retrieved successfully."
                ),
                "data": data,
            }
        ), 200
    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "message": (
                    f"Evaluator summary unavailable: {exc}"
                ),
            }
        ), 500


# ---------------------------------------------------------------------------
# 3. Deep Readiness Probe
# ---------------------------------------------------------------------------

@health_bp.route("/ready", methods=["GET"])
@login_required
@admin_required
def health_ready():
    """
    Return the authoritative administrative readiness state.

    The web lane remains informational and does not affect readiness.
    """

    sis_health = (
        get_intelligence_service_health()
        if bool(settings.SIS_ENABLED)
        else None
    )
    intelligence_ready = (
        bool(sis_health.get("interactive_ready"))
        if isinstance(sis_health, dict)
        else (
            direct_model_files_available()
            and _embedding_model_files_available()
        )
    )

    details = {
        "uploads_accessible": os.path.isdir(UPLOAD_DIR),
        "intelligence_ready": bool(intelligence_ready),
        "sis": (
            {
                "status": sis_health.get("status"),
                "interactive_ready": bool(
                    sis_health.get("interactive_ready")
                ),
                "circuit_open": bool(
                    sis_health.get("circuit_open")
                ),
                "monitor_running": bool(
                    sis_health.get("monitor_running")
                ),
                "last_success_at": sis_health.get("last_success_at"),
                "last_failure_at": sis_health.get("last_failure_at"),
            }
            if isinstance(sis_health, dict)
            else None
        ),
        "direct_llm_model_present": (
            None
            if bool(settings.SIS_ENABLED)
            else direct_model_files_available()
        ),
        "embedding_model_present": (
            None
            if bool(settings.SIS_ENABLED)
            else _embedding_model_files_available()
        ),
        "web_lane": {
            "enabled": bool(settings.WEB_LANE_ENABLED),
            "sources_configured": (
                len(settings.WEB_LANE_SOURCES or []) > 0
            ),
            "mode": "bypass-safe",
        },
    }

    now = time.time()

    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SHOW TABLES")
            )
            tables = [
                row[0]
                for row in result
            ]

            if "task_history" not in tables:
                init_db()

            details["schema_ok"] = True
    except Exception as exc:
        details["schema_ok"] = False
        details["db_error"] = str(exc)

    try:
        from solomon_core.solomon_tools import diagnostics

        core_report = diagnostics.check_core()
        details["core_ok"] = bool(
            core_report.get("ok", False)
        )

        if not details["core_ok"]:
            details["core_error"] = core_report.get(
                "error",
                "Unknown core issue",
            )
    except Exception as exc:
        details["core_ok"] = False
        details["core_error"] = str(exc)

    required_checks = (
        "uploads_accessible",
        "core_ok",
        "schema_ok",
        "intelligence_ready",
    )

    status = (
        "ready"
        if all(
            details.get(key) is True
            for key in required_checks
        )
        else "degraded"
    )

    HEALTH_CACHE.update(
        {
            "last_check": now,
            "ready_state": status,
        }
    )

    return jsonify(
        {
            "status": status,
            "details": details,
            "readiness_contract": (
                "sis_execution_service_required"
                if bool(settings.SIS_ENABLED)
                else "direct_local_models_required"
            ),
            "web_lane_contract": (
                "non_authoritative"
            ),
        }
    ), 200


# ---------------------------------------------------------------------------
# 4. Self-Repair Event Review
# ---------------------------------------------------------------------------

@health_bp.route("/selfrepair", methods=["GET"])
@login_required
@admin_required
def health_selfrepair():
    traces = HEALTH_CACHE.get(
        "recent_recovery",
        [],
    )

    return jsonify(
        {
            "count": len(traces),
            "events": traces[-50:],
        }
    ), 200


# ---------------------------------------------------------------------------
# 5. Controlled Failure Drill
# ---------------------------------------------------------------------------

@health_bp.route("/drill", methods=["POST"])
@login_required
@admin_required
def health_drill():
    data = request.get_json(
        silent=True
    ) or {}

    target = str(
        data.get("target") or ""
    ).strip().lower()

    try:
        duration = max(
            0,
            min(
                int(data.get("duration", 3)),
                30,
            ),
        )
    except (TypeError, ValueError):
        return jsonify(
            {
                "error": (
                    "Duration must be an integer between 0 and 30."
                )
            }
        ), 400

    start_state = HEALTH_CACHE.get(
        "ready_state",
        "unknown",
    )

    restored = False
    valid_targets = {
        "database",
        "direct_llm",
        "uploads",
    }

    if target not in valid_targets:
        return jsonify(
            {
                "error": "Invalid target",
                "valid_targets": sorted(valid_targets),
            }
        ), 400

    if target == "database":
        time.sleep(duration)

        try:
            init_db()
            restored = True
        except Exception:
            restored = False

    elif target == "direct_llm":
        time.sleep(duration)
        restored = bool(
            direct_model_files_available()
        )

    elif target == "uploads":
        temporary_dir = f"{UPLOAD_DIR}_bak"
        moved_original = False

        try:
            if os.path.exists(temporary_dir):
                raise RuntimeError(
                    "Uploads drill backup directory already exists."
                )

            if os.path.exists(UPLOAD_DIR):
                os.rename(
                    UPLOAD_DIR,
                    temporary_dir,
                )
                moved_original = True

            time.sleep(duration)
        except Exception:
            restored = False
        finally:
            try:
                if moved_original:
                    if os.path.isdir(UPLOAD_DIR):
                        shutil.rmtree(UPLOAD_DIR)
                    elif os.path.exists(UPLOAD_DIR):
                        os.remove(UPLOAD_DIR)

                    os.rename(
                        temporary_dir,
                        UPLOAD_DIR,
                    )
                else:
                    os.makedirs(
                        UPLOAD_DIR,
                        exist_ok=True,
                    )

                restored = True
            except Exception:
                restored = False

    return jsonify(
        {
            "simulation": target,
            "duration": duration,
            "status_before": start_state,
            "restored": restored,
            "timestamp": time.time(),
        }
    ), 200
