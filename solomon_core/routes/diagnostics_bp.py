# diagnostics_bp.py — Diagnostic Routes (Phase 19 + Phase 20 Step 11 + Step 14 + Step 18 USDI Normalization)
# ------------------------------------------------------------
# Read-only API endpoints for system diagnostics, cognition,
# meta diagnostics, self-repair reports, error trends, and USDI.
#
# PHASE 47.1 ADDITION:
#   • Diagnostic Isolation Invariant
#   • All emitted payloads are explicitly marked as diagnostic-only
#   • Payloads are observational and non-consumable by LLM, skills, or packets
# ------------------------------------------------------------

from flask import Blueprint, jsonify
import os
import json
from solomon_core.logger import get_logger
from solomon_core.solomon_tools import diagnostics, self_repair
from solomon_core.auth_utils import login_required, admin_required
from config import settings

# Cognition controllers
from solomon_core.cognition.operational_cognition_controller import (
    get_operational_diagnostics,
)
from solomon_core.cognition.strategic_cognition_controller import (
    get_strategic_diagnostics,
)
from solomon_core.cognition.meta.meta_context import MetaContext
from solomon_core.cognition.meta.meta_orchestrator import (
    run_meta_cognitive_cycle,
)
from solomon_core.cognitive_orchestrator import run_full_cognition_with_meta

# Strategic memory snapshot
from solomon_core.planner.strategic_memory import get_strategic_memory_snapshot

# Error Trend Analyzer
from solomon_core.cognition.error_trend_analyzer import get_error_trend_summary

# ★ Phase 20 Step 18 — Normalized USDI
from solomon_core.cognition.usdi_normalizer import get_normalized_usdi

logger = get_logger("diagnostics")


# ------------------------------------------------------------
# JSON-SAFE SERIALIZER
# ------------------------------------------------------------
def _json_safe(obj):
    """Recursively convert objects (including dataclasses) into JSON-safe structures."""
    try:
        import dataclasses
        if dataclasses.is_dataclass(obj):
            return {str(k): _json_safe(v) for k, v in dataclasses.asdict(obj).items()}
    except Exception:
        pass

    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple, set)):
        return [_json_safe(x) for x in obj]

    return obj


# ------------------------------------------------------------
# Diagnostic Marker (Phase 47.1)
# ------------------------------------------------------------
def _diagnostic_payload(payload: dict) -> dict:
    """
    Wrap payload with an explicit diagnostic-only marker.
    Observational only. No enforcement. No execution impact.
    """
    return {
        "__diagnostic__": True,
        "is_diagnostic": True,
        "payload": payload,
    }


# ------------------------------------------------------------
# Blueprint root
# ------------------------------------------------------------
diagnostics_bp = Blueprint("diagnostics", __name__, url_prefix="/admin/diagnostics")


# ------------------------------------------------------------
# 1️⃣ System diagnostics
# ------------------------------------------------------------
@diagnostics_bp.route("/system", methods=["GET"])
@login_required
@admin_required
def get_system_diagnostics():
    try:
        db_report = diagnostics.check_database()
        mem_report = diagnostics.check_memory()
        core_report = diagnostics.check_core()

        system_ok = all([
            db_report.get("ok", False),
            mem_report.get("ok", False),
            core_report.get("ok", False)
        ])

        payload = {
            "ok": system_ok,
            "details": {
                "core_ok": core_report.get("ok", False),
                "database_ok": db_report.get("ok", False),
                "memory_ok": mem_report.get("ok", False),
            },
            "core": core_report,
            "database": db_report,
            "memory": mem_report,
            "status": "ok" if system_ok else "degraded"
        }

        return jsonify(_json_safe(_diagnostic_payload(payload))), 200

    except Exception as e:
        logger.error(f"[Diagnostics] Error running system diagnostics: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ------------------------------------------------------------
# 2️⃣ Self-repair diagnostics
# ------------------------------------------------------------
@diagnostics_bp.route("/self-repair", methods=["GET"])
@login_required
@admin_required
def get_self_repair_report():
    try:
        log_dir = getattr(settings, "LOG_DIR", os.path.join(
            getattr(settings, "DATA_DIR", "./data"),
            "logs"
        ))

        report_path = os.path.join(log_dir, "self_repair_report.json")

        if not os.path.exists(report_path):
            return jsonify(_diagnostic_payload({
                "ok": False,
                "message": "No self-repair report available yet."
            })), 404

        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)

        return jsonify(_json_safe(_diagnostic_payload(report))), 200

    except Exception as e:
        logger.error(f"[Diagnostics] Failed to read self-repair report: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ------------------------------------------------------------
# 3️⃣ Cognitive diagnostics (+ normalized USDI)
# ------------------------------------------------------------
@diagnostics_bp.route("/cognitive", methods=["GET"])
@login_required
@admin_required
def get_cognitive_diagnostics():
    try:
        result = get_operational_diagnostics()
        result["error_trends"] = get_error_trend_summary()

        try:
            result["usdi"] = get_normalized_usdi()
        except Exception:
            result["usdi"] = {"ok": False}

        return jsonify(_json_safe(_diagnostic_payload(result))), 200

    except Exception as e:
        logger.error(f"[Diagnostics] cognitive error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ------------------------------------------------------------
# 4️⃣ Strategic diagnostics (+ normalized USDI)
# ------------------------------------------------------------
@diagnostics_bp.route("/strategic", methods=["GET"])
@login_required
@admin_required
def get_strategic_diagnostics_route():
    try:
        result = get_strategic_diagnostics()
        result["error_trends"] = get_error_trend_summary()

        try:
            result["usdi"] = get_normalized_usdi()
        except Exception:
            result["usdi"] = {"ok": False}

        return jsonify(_json_safe(_diagnostic_payload(result))), 200

    except Exception as e:
        logger.error(f"[Diagnostics] strategic error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ------------------------------------------------------------
# 5️⃣ Strategic memory
# ------------------------------------------------------------
@diagnostics_bp.route("/strategic-memory", methods=["GET"])
@login_required
@admin_required
def get_strategic_memory():
    try:
        snapshot = get_strategic_memory_snapshot()
        return jsonify(_json_safe(_diagnostic_payload(snapshot))), 200
    except Exception as e:
        logger.error(f"[Diagnostics] strategic memory error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ------------------------------------------------------------
# 6️⃣ Meta diagnostics
# ------------------------------------------------------------
@diagnostics_bp.route("/meta", methods=["GET"])
@login_required
@admin_required
def get_meta_diagnostics_route():
    try:
        ctx = MetaContext.build()
        return jsonify(_json_safe(_diagnostic_payload({
            "available": True,
            "context": ctx.as_dict(),
        }))), 200
    except Exception as e:
        return jsonify({"available": False, "error": str(e)}), 500


# ------------------------------------------------------------
# 7️⃣ Full meta diagnostics (+ normalized USDI)
# ------------------------------------------------------------
@diagnostics_bp.route("/meta/full", methods=["GET"])
@login_required
@admin_required
def get_full_meta_diagnostics():
    try:
        result = run_meta_cognitive_cycle()

        payload = {
            "available": True,
            "context": result.get("context"),
            "snapshot": result.get("snapshot"),
            "patterns": result.get("patterns"),
            "trends": result.get("trends"),
            "anomalies": result.get("anomalies"),
            "memory_integrated": result.get("memory_integrated"),
            "summary": result.get("summary"),
            "timestamp": result.get("combined", {}).get("timestamp"),
            "error_trends": get_error_trend_summary(),
            "usdi": get_normalized_usdi(),
        }

        return jsonify(_json_safe(_diagnostic_payload(payload))), 200

    except Exception as e:
        logger.error(f"[Diagnostics] Full meta diagnostics error: {e}")
        return jsonify({"available": False, "error": str(e)}), 500


# ------------------------------------------------------------
# 8️⃣ Unified diagnostics bundle (/all)
# ------------------------------------------------------------
@diagnostics_bp.route("/all", methods=["GET"])
@login_required
@admin_required
def get_all_diagnostics():
    try:
        result = run_full_cognition_with_meta()
        system_diag = diagnostics.check_core()
        strategic_memory = get_strategic_memory_snapshot()

        try:
            usdi = get_normalized_usdi()
        except Exception:
            usdi = {"ok": False}

        payload = {
            "success": True,
            "system": system_diag,
            "cognition": result.get("cognition"),
            "meta": result.get("meta"),
            "strategic_memory": strategic_memory,
            "timestamp": result.get("timestamp"),
            "error_trends": get_error_trend_summary(),
            "usdi": usdi,
        }

        return jsonify(_json_safe(_diagnostic_payload(payload))), 200

    except Exception as e:
        logger.error(f"[Diagnostics] Unified diagnostics error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ------------------------------------------------------------
# 9️⃣ Dedicated USDI Diagnostics
# ------------------------------------------------------------
@diagnostics_bp.route("/usdi", methods=["GET"])
@login_required
@admin_required
def get_usdi_diagnostics():
    try:
        return jsonify(_json_safe(_diagnostic_payload({
            "ok": True,
            "usdi": get_normalized_usdi(),
        }))), 200
    except Exception as e:
        logger.error(f"[Diagnostics] USDI error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
