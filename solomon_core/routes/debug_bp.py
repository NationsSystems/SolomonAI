# solomon_core/routes/debug_bp.py
# -------------------------------------------------------------
# Phase 22 — Debug Blueprint (Read-Only, Safe Introspection)
# -------------------------------------------------------------

from flask import Blueprint, jsonify
from solomon_core.auth_utils import secure_debug_required

debug_bp = Blueprint("debug_bp", __name__, url_prefix="/debug")


@debug_bp.route("/ping", methods=["GET"])
@secure_debug_required
def ping():
    """
    Minimal debug endpoint.
    No execution, no routing, no authority.
    """
    return jsonify({
        "ok": True,
        "status": "debug_bp alive"
    })
