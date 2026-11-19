# skill_patching_engine.py — Phase 12.8 (Updated for Phase 18 Option H1)
# ---------------------------------------------------------------------------
# Solomon Autonomous Skill Patching Engine
#
# Phase 18 adds:
#   • KG importance weighting in patch actions
#   • Planner-confidence weighted recommendations
#   • Reinforcement-weight weighted patch targeting
#   • HFLO pending awareness
#   • Skill weakness engine stabilized scoring
#   • Safer, narrower patch actions to avoid destabilizing skills
#   • NEW (Option H1): planner_learning_engine does NOT generate code.
#     Only analysis; patch code generation is handled safely here.
# ---------------------------------------------------------------------------

import ast
import textwrap
from collections import defaultdict

from solomon_core.logger import get_logger
from solomon_core.knowledge.skill_weakness_engine import (
    get_skill_weakness_report,
    score_skill_stability,
)
from solomon_core.knowledge.knowledge_graph import (
    compute_error_affinity,
    get_skill_usage,
)
from solomon_core.skill_registry import lookup_skill

# Sandbox runner
from solomon_core.autonomy.planner_sandbox import run_code_in_sandbox

# HFLO-aware planner analysis (NO CODE GENERATION)
from solomon_core.autonomy.planner_learning_engine import (
    analyze_and_generate_planner_patch,
)

logger = get_logger("skill_patching_engine")


# =============================================================
# Phase 18 — Helper Weighting
# =============================================================

def _phase18_weighted_patch_priority(stability):
    """
    Determine how aggressive a patch should be based on:
        - reinforcement_weight
        - planner_confidence
        - kg_importance
        - hflo_pending
    """
    w_rf = stability.get("reinforcement_weight", 0)
    w_conf = stability.get("planner_confidence", 0)
    w_imp = stability.get("kg_importance", 0)
    w_hflo = stability.get("hflo_pending", 0)

    raw = (w_hflo * 1.5) + (-w_rf * 1.2) + (-w_conf * 1.1) + (w_imp * 0.3)

    if raw > 2.5:
        return "high_priority"
    elif raw > 1.0:
        return "medium_priority"
    return "low_priority"


# =============================================================
# Patch Plan Generator (Phase 18 Upgrade)
# =============================================================

def generate_patch_plan(skill_name: str):
    skill_name = str(skill_name).lower()
    weakness = get_skill_weakness_report(skill_name)
    stability = score_skill_stability(skill_name)

    error_aff = compute_error_affinity()
    usage_count = get_skill_usage(skill_name)

    error_list = [
        err for (skill, err), weight in error_aff.items()
        if skill == skill_name
    ]

    priority = _phase18_weighted_patch_priority(stability)

    plan = {
        "skill": skill_name,
        "reason": weakness["issues"],
        "base_score": stability["score"],
        "error_targets": error_list,
        "usage": usage_count,
        "priority": priority,
        "signals": {
            "reinforcement_weight": stability.get("reinforcement_weight"),
            "planner_confidence": stability.get("planner_confidence"),
            "kg_importance": stability.get("kg_importance"),
            "hflo_pending": stability.get("hflo_pending"),
        },
        "actions": [],
    }

    issues = weakness["issues"]

    if "High failure rate" in issues:
        plan["actions"].append({"action": "improve_error_handling"})

    if "LLM fallback detected" in issues:
        plan["actions"].append({"action": "add_argument_validation"})

    if "Strong error affinity" in issues and error_list:
        plan["actions"].append({
            "action": "patch_error_pattern",
            "errors": error_list,
        })

    if "High complexity function" in issues:
        plan["actions"].append({"action": "reduce_complexity"})

    if stability.get("planner_confidence", 0) < 0.25:
        plan["actions"].append({"action": "simplify_signature"})

    if stability.get("reinforcement_weight", 0) < -0.2:
        plan["actions"].append({"action": "clean_edge_cases"})

    if not plan["actions"]:
        plan["actions"].append({"action": "optimize_logic"})

    # ------------------------------------------------------------
    # NEW Phase 18 (Option H1)
    # Planner contributes informational suggestions ONLY.
    # ------------------------------------------------------------
    instruction = analyze_and_generate_planner_patch()
    if not instruction:
        instruction = {
            "patch_description": "none",
            "patch_type": "none",
            "python_patch": "",
            "risk_level": "low",
        }

    plan["llm_instruction"] = instruction

    logger.info(f"[PatchPlan] Phase 18 patch plan for {skill_name} (priority={priority})")
    return plan


# =============================================================
# Fallback patch-code generator (still required)
# =============================================================

def _fallback_generate_patch_code(skill_name: str, original_func):
    return textwrap.dedent(f"""
    # Auto-generated stub patch for skill '{skill_name}'
    def patched_function(*args, **kwargs):
        try:
            return original_func(*args, **kwargs)
        except Exception:
            return None
    """)


# =============================================================
# NEW (Option H1) — Safe Patch Code Generator
# =============================================================

def generate_safe_patch_code(plan: dict, original_func):
    """
    Uses LLM suggestion ONLY if safe and minimal.
    NEVER modifies planner internals.
    """
    instr = plan.get("llm_instruction", {})
    candidate = instr.get("python_patch", "")

    if not candidate or "def " not in candidate:
        return _fallback_generate_patch_code(plan["skill"], original_func)

    forbidden = [
        "planner.", 
        "strategic_planner", 
        "import planner", 
        "from solomon_core.planner",
    ]
    if any(w in candidate for w in forbidden):
        return _fallback_generate_patch_code(plan["skill"], original_func)

    dangerous = ["exec(", "eval(", "open(", "compile("]
    if any(d in candidate for d in dangerous):
        return _fallback_generate_patch_code(plan["skill"], original_func)

    return candidate.strip()


# =============================================================
# Patch Code Proposal
# =============================================================

def propose_skill_patch(skill_name: str):
    plan = generate_patch_plan(skill_name)
    entry = lookup_skill(skill_name)

    if not entry:
        return {"error": "Skill not found"}

    original = entry.get("callable")

    try:
        proposed_code = generate_safe_patch_code(plan, original)
    except Exception:
        proposed_code = _fallback_generate_patch_code(skill_name, original)

    return {
        "skill": skill_name,
        "plan": plan,
        "proposed_code": proposed_code,
    }


# =============================================================
# Safety validation
# =============================================================

SAFE_IMPORTS = {
    "re", "json", "datetime", "math", "statistics",
    "collections", "typing", "pathlib"
}

FORBIDDEN_NODES = (
    ast.ImportFrom,
    ast.With,
    ast.Try,
    ast.While,
    ast.AsyncFunctionDef,
    ast.Await,
)

def validate_patch_safety(code: str):
    try:
        tree = ast.parse(code)
    except Exception as e:
        return {"safe": False, "reason": f"AST parse error: {e}"}

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name not in SAFE_IMPORTS:
                    return {"safe": False, "reason": f"Forbidden import: {alias.name}"}

        if isinstance(node, FORBIDDEN_NODES):
            return {"safe": False, "reason": f"Forbidden construct: {type(node).__name__}"}

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id in {"open", "exec", "eval", "compile"}:
                    return {"safe": False, "reason": f"Forbidden call: {node.func.id}"}

    return {"safe": True}


# =============================================================
# Patch simulation
# =============================================================

def simulate_patch_execution(skill_name: str, patch_code: str):
    safety = validate_patch_safety(patch_code)
    if not safety["safe"]:
        return {"valid": False, "reason": safety["reason"]}

    result = run_code_in_sandbox(skill_name, patch_code)
    return result


# =============================================================
# Patch staging
# =============================================================

def prepare_patch_for_application(skill_name: str, patch_code: str):
    version_tag = f"{skill_name}_v_patch"
    return {
        "skill": skill_name,
        "new_version": version_tag,
        "patch_code": patch_code,
        "ready": True,
    }


# =============================================================
# Autonomous Patch Cycle
# =============================================================

def autonomous_skill_patch_cycle(skill_name: str):
    proposal = propose_skill_patch(skill_name)
    if "error" in proposal:
        return proposal

    patch_code = proposal["proposed_code"]

    sim = simulate_patch_execution(skill_name, patch_code)
    if not sim.get("valid", False):
        return {
            "success": False,
            "reason": "Patch failed sandbox tests",
            "details": sim,
        }

    prepared = prepare_patch_for_application(skill_name, patch_code)

    return {
        "success": True,
        "proposal": proposal,
        "simulation": sim,
        "prepared": prepared,
    }


# =============================================================
# Public API
# =============================================================

def get_patch_plan(skill_name: str):
    return generate_patch_plan(skill_name)


def run_patch_cycle(skill_name: str):
    return autonomous_skill_patch_cycle(skill_name)

# EOF
