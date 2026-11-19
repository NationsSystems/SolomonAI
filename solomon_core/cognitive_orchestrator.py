# cognitive_orchestrator.py — Slim Phase 16 Coordinator + Phase 16 Step 19
# ------------------------------------------------------------------------
# Delegates work to:
#   • operational_cognition_controller
#   • strategic_cognition_controller
#   • meta_cognition (unchanged)
#   • unified diagnostics (Phase 16 Step 13–19)
#
# Phase 16 Step 19 adds:
#   • strategic_summary_normalizer integration
#   • meta_memory_integrator integration
#   • stable unified cognition+meta memory result
#
# Phase 21 Step 6A:
#   • Add strict planner pipeline imports
#   • Add planner readiness diagnostics
# ------------------------------------------------------------------------

import datetime
from solomon_core.logger import get_logger

from solomon_core.autonomy.strict_autonomy_controller import should_autonomy_run

# Phase 16 — operational
from solomon_core.cognition.operational_cognition_controller import (
    run_operational_cognitive_cycle,
    get_operational_diagnostics,
)

# Phase 16 — strategic
from solomon_core.cognition.strategic_cognition_controller import (
    run_strategic_cognitive_cycle,
    get_strategic_diagnostics,
    generate_strategic_postmortem,
)

# Phase 21 — strict planner import (corrected)
from solomon_core.planner.planner_interface import generate_plan_strict

# Meta-layer
from solomon_core.cognition.meta.meta_context import MetaContext
from solomon_core.cognition.meta.meta_orchestrator import run_meta_cognitive_cycle

# Unified diagnostics (Step 13)
from solomon_core.autonomy.unified_diagnostics import (
    get_unified_autonomy_cognition_diagnostics,
)

# Skill Selector (Step 14)
from solomon_core.cognition.strategic_skill_selector import (
    get_strategic_skill_diagnostics,
)

# --- Phase 16 Step 19 imports ---
from solomon_core.cognition.strategic_summary_normalizer import (
    normalize_strategic_summary,
)
from solomon_core.cognition.meta.meta_memory_integrator import (
    integrate_meta_memory,
)

logger = get_logger("cognitive_orchestrator")


def _now():
    return datetime.datetime.utcnow().isoformat()


# ------------------------------------------------------------
# Phase 16 Compatibility Shim (for older planner modules)
# ------------------------------------------------------------
def evaluate_autonomy_triggers(*args, **kwargs):
    return {
        "allowed": True,
        "mode": "strategic",
        "reason": "compatibility_autonomy_trigger_stub",
    }


# ------------------------------------------------------------
# Unified Cognition
# ------------------------------------------------------------
def run_full_cognitive_cycle():
    gate = should_autonomy_run()

    if not gate["allowed"]:
        return {
            "success": False,
            "mode": gate["mode"],
            "reason": gate["reason"],
            "timestamp": _now(),
        }

    if gate["mode"] == "strategic":
        return run_strategic_cognitive_cycle()

    if gate["mode"] == "operational":
        return run_operational_cognitive_cycle()

    return {
        "success": False,
        "mode": None,
        "reason": "unknown_autonomy_mode",
        "gate": gate,
        "timestamp": _now(),
    }


# ------------------------------------------------------------
# Light Meta Snapshot Diagnostics
# ------------------------------------------------------------
def get_meta_layer_diagnostics():
    try:
        context = MetaContext.build()
        return {"available": True, "context": context.as_dict(), "timestamp": _now()}
    except Exception as e:
        return {"available": False, "error": str(e), "timestamp": _now()}


# ------------------------------------------------------------
# Unified Diagnostics (Step 13–19 + Phase 21)
# ------------------------------------------------------------
def get_unified_diagnostics():
    base = get_unified_autonomy_cognition_diagnostics()

    # Meta Context
    try:
        meta_ctx = MetaContext.build().as_dict()
    except Exception as e:
        meta_ctx = {"available": False, "error": str(e)}

    # Meta summary
    try:
        from solomon_core.cognition.meta.meta_orchestrator import run_meta_cycle_summary
        meta_cycle = run_meta_cycle_summary()
    except Exception as e:
        meta_cycle = {"success": False, "error": str(e)}

    # Skill Selector
    try:
        skill_selector = get_strategic_skill_diagnostics()
    except Exception as e:
        skill_selector = {"available": False, "error": str(e)}

    # Strategic summary normalization
    try:
        strategic_postmortem = generate_strategic_postmortem()
        if strategic_postmortem.get("available"):
            normalized = normalize_strategic_summary(
                simulation=strategic_postmortem.get("simulation", {}),
                execution_feedback=strategic_postmortem.get("feedback", {}),
                drift_report=strategic_postmortem.get("drift", {}),
                reinforcement_signal=strategic_postmortem.get("reinforcement", {}),
                score_breakdown=strategic_postmortem.get("score", {}),
            )
        else:
            normalized = {"available": False, "reason": "no_strategic_data"}
    except Exception as e:
        normalized = {"available": False, "error": str(e)}

    # Meta memory integrator
    try:
        integrated = integrate_meta_memory(
            meta_snapshot=meta_cycle.get("snapshot", {}),
            strategic_summary=normalized,
            normalized_insights=normalized,
        )
    except Exception as e:
        integrated = {"available": False, "error": str(e)}

    # Planner readiness diagnostics (Phase 21 Step 6A)
    try:
        from solomon_core.planner.planner_backend import planner_backend_ready
        planner_diag = planner_backend_ready()
    except Exception as e:
        planner_diag = {"available": False, "error": str(e)}

    return {
        "success": True,
        "timestamp": _now(),
        "autonomy_cognition": base,
        "meta_context": meta_ctx,
        "meta_cycle": meta_cycle,
        "skill_selector": skill_selector,
        "strategic_normalized": normalized,
        "meta_memory_integrated": integrated,
        "planner_readiness": planner_diag,
    }


# ------------------------------------------------------------
# Legacy passthrough
# ------------------------------------------------------------
def get_strategic_skill_selector_diagnostics():
    return get_strategic_skill_diagnostics()


# ------------------------------------------------------------
# Full Cognition + Meta Evaluation
# ------------------------------------------------------------
def run_full_cognition_with_meta():
    cognition_result = run_full_cognitive_cycle()

    try:
        meta_result = run_meta_cognitive_cycle()
    except Exception as e:
        meta_result = {"success": False, "error": str(e)}

    # Strategic summary normalization
    try:
        strategic_postmortem = generate_strategic_postmortem()
        if strategic_postmortem.get("available"):
            normalized = normalize_strategatic_summary(
                simulation=strategic_postmortem.get("simulation", {}),
                execution_feedback=strategic_postmortem.get("feedback", {}),
                drift_report=strategic_postmortem.get("drift", {}),
                reinforcement_signal=strategic_postmortem.get("reinforcement", {}),
                score_breakdown=strategic_postmortem.get("score", {}),
            )
        else:
            normalized = {"available": False}
    except Exception as e:
        normalized = {"available": False, "error": str(e)}

    # Meta integration
    try:
        integrated = integrate_meta_memory(
            meta_snapshot=meta_result.get("snapshot", {}),
            strategic_summary=normalized,
            normalized_insights=normalized,
        )
    except Exception as e:
        integrated = {"available": False, "error": str(e)}

    return {
        "success": True,
        "cognition": cognition_result,
        "meta": meta_result,
        "normalized_strategic": normalized,
        "integrated_meta_memory": integrated,
        "timestamp": _now(),
    }
