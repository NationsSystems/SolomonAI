# solomon_core/routes/skill_routes_bp.py — Phase 9.10.3
# ---------------------------------------------------
# Admin API for inspecting Solomon's skills.
#
# Provides unified metadata for:
#   • in-memory registry
#   • persistent DB skills
#   • FAISS vector similarity state
#
# NOTE:
# This route layer is responsible for JSON safety.
# No raw registry objects may cross this boundary.
# ---------------------------------------------------

from flask import Blueprint, jsonify
from solomon_core.logger import get_logger
from solomon_core.auth_utils import admin_required

from solomon_core.skill_registry import (
    get_all_skill_metadata,
    get_skill_info,
    sync_faiss_with_db,
)

logger = get_logger("skill_routes")

skill_routes_bp = Blueprint(
    "skill_routes_bp",
    __name__,
    url_prefix="/admin/api/skills"
)


# ---------------------------------------------------
# INTERNAL — JSON safety guard
# ---------------------------------------------------
def _json_safe(obj):
    """
    Recursively coerce objects into JSON-safe primitives.
    Registry objects, callables, and unknown types are stringified.
    """
    if obj is None:
        return None

    if isinstance(obj, (str, int, float, bool)):
        return obj

    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]

    if isinstance(obj, dict):
        return {str(k): _json_safe(v) for k, v in obj.items()}

    # Fallback for SkillRegistry, classes, functions, etc.
    return str(obj)


# ---------------------------------------------------
# GET /admin/api/skills
# ---------------------------------------------------
@skill_routes_bp.route("", methods=["GET"])
@admin_required
def list_skills():
    """
    Return unified metadata for all skills.
    JSON-safe by construction.
    """
    try:
        data = get_all_skill_metadata()
        safe_data = _json_safe(data)
        return jsonify({"ok": True, "skills": safe_data})

    except Exception as e:
        logger.error(f"[skill_routes] list_skills failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------------------------------------------------
# GET /admin/api/skills/<name>
# ---------------------------------------------------
@skill_routes_bp.route("/<name>", methods=["GET"])
@admin_required
def skill_details(name):
    """
    Return detailed metadata for a single skill.
    Introspection only; JSON-safe output guaranteed.
    """
    try:
        info = get_skill_info(name)
        if not info:
            return jsonify({"ok": False, "error": "Skill not found"}), 404

        safe_info = _json_safe(info)
        return jsonify({"ok": True, "skill": safe_info})

    except Exception as e:
        logger.error(f"[skill_routes] skill_details({name}) failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


# ---------------------------------------------------
# POST /admin/api/skills/sync
# ---------------------------------------------------
@skill_routes_bp.route("/sync", methods=["POST"])
@admin_required
def sync_faiss():
    """
    Force FAISS ↔ DB consistency sync (Phase 9.9).
    Result is JSON-sanitized to avoid registry leakage.
    """
    try:
        result = sync_faiss_with_db()
        safe_result = _json_safe(result)
        return jsonify({"ok": True, "result": safe_result})

    except Exception as e:
        logger.error(f"[skill_routes] sync_faiss failed: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
