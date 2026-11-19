# admin_skill_simulator_bp.py — Phase 10.5.3 (Phase 40G Remediated)
# ---------------------------------------------------------------
# Admin UI API for simulating proposed HFLO skill upgrades.
#
# Provides:
#   GET  /admin/skill_simulator/      → UI page
#   POST /admin/skill_simulator/run   → simulation API
# ---------------------------------------------------------------

from flask import Blueprint, request, jsonify, render_template

from solomon_core.auth_utils import login_required, admin_required
from solomon_core.autonomy.skill_simulation_engine import (
    simulate_skill_execution
)

admin_skill_simulator_bp = Blueprint(
    "admin_skill_simulator",
    __name__,
    url_prefix="/admin/skill_simulator",
    template_folder="../../webui/templates"
)


# ---------------------------------------------------------------
# UI PAGE (ADMIN ONLY)
# ---------------------------------------------------------------
@admin_skill_simulator_bp.route("/", methods=["GET"])
@login_required
@admin_required
def simulator_page():
    return render_template("admin_skill_simulator.html")


# ---------------------------------------------------------------
# Skill Simulation Endpoint (ADMIN ONLY)
# ---------------------------------------------------------------
@admin_skill_simulator_bp.route("/run", methods=["POST"])
@login_required
@admin_required
def run_skill_simulation():
    """
    Simulates execution of a proposed skill upgrade:
        - sandboxed
        - restricted builtins
        - isolated namespace
    """

    data = request.get_json(force=True, silent=True) or {}

    skill_name = data.get("skill_name")
    python_code = data.get("python_code")
    test_input = data.get("test_input") or {}

    if not python_code:
        return jsonify({
            "ok": False,
            "error": "No python_code provided",
            "report": None
        })

    # Execute inside the safe sandbox
    report = simulate_skill_execution(
        python_code=python_code,
        test_input=test_input
    )

    return jsonify({
        "ok": True,
        "skill_name": skill_name,
        "report": report
    })
