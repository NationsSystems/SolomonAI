# solomon_core/planner/planner_action_router.py
# ---------------------------------------------------------------
# Phase 23.5 — Strict Planner Action Router (DocIntel-Aware)
#
# CONTRACT:
#   • ABSOLUTELY NO domain logic allowed here
#   • ONLY maps action strings → micro_skill names
#   • Planner backend determines actions
#   • Micro-skills implement DocIntel intelligence
#   • Unknown actions always map to skill_generic_llm_reasoning
#
# This file must remain “as dumb as possible” so the
# DocIntel pipeline stays stable, debuggable, and predictable.
# ---------------------------------------------------------------

import uuid
from solomon_core.logger import get_logger

logger = get_logger("planner_action_router")

# ================================================================
# PHASE 23.5 — DocIntel Micro-Skill Action Map
# ================================================================
# NOTE:
# These strings are referenced by planner LLM output.
# They represent ALLOWED actions, not logic.
# ================================================================
_DOCINTEL_ACTIONS = {
    "extract_scope": "skill_docintel_extract_scope",
    "normalize_scope": "skill_docintel_normalize_scope",
    "semantic_match": "skill_docintel_semantic_match",
    "compare_documents": "skill_docintel_compare_documents",
    "generate_comparison_table": "skill_docintel_generate_comparison_table",
    "analyze_documents": "skill_docintel_analyze_documents",
    "extract_text_blocks": "skill_docintel_extract_text_blocks",
}

# ================================================================
# PHASE 22 + 23.5 — Strict Core Action Map
# ================================================================
_ACTION_MAP = {
    # Core generic reasoning
    "generic_llm_reasoning": "skill_generic_llm_reasoning",

    # Diagnostics
    "run_diagnostics": "run_diagnostics",
    "system_diagnostics": "run_system_diagnostics",
    "skill_diagnostics": "run_skill_diagnostics",
    "planner_diagnostics": "run_planner_diagnostics",
    "memory_diagnostics": "run_memory_diagnostics",
    "safety_diagnostics": "run_safety_diagnostics",
}

# Merge DocIntel into action map
_ACTION_MAP.update(_DOCINTEL_ACTIONS)


# ================================================================
# STRICT ACTION ROUTER
# ================================================================
def route_planner_action(step: dict) -> dict:
    """
    STRICT Phase-23.5 router.

    Responsibilities:
        • map planner “action” → micro-skill name
        • always return valid packet
        • no inference, no domain logic
        • fallback: skill_generic_llm_reasoning
    """

    # -----------------------------------------------------------
    # Validate step object
    # -----------------------------------------------------------
    if not isinstance(step, dict):
        return {
            "ok": True,
            "skill_name": "skill_generic_llm_reasoning",
            "arguments": {},
            "is_fallback": True,
        }

    # -----------------------------------------------------------
    # Normalize the action string
    # -----------------------------------------------------------
    raw_action = step.get("action") or ""
    if not isinstance(raw_action, str):
        raw_action = str(raw_action)

    action = raw_action.strip().lower()

    # -----------------------------------------------------------
    # Map → skill or fallback
    # -----------------------------------------------------------
    if action in _ACTION_MAP:
        skill_name = _ACTION_MAP[action]
        is_fallback = (skill_name == "skill_generic_llm_reasoning")
    else:
        logger.debug(
            f"[planner_action_router] Unknown action '{raw_action}', "
            f"falling back to generic_llm_reasoning"
        )
        skill_name = "skill_generic_llm_reasoning"
        is_fallback = True

    # -----------------------------------------------------------
    # Normalize arguments
    # -----------------------------------------------------------
    raw_args = step.get("arguments") or step.get("args") or {}
    if not isinstance(raw_args, dict):
        logger.debug(
            f"[planner_action_router] Invalid arguments type {type(raw_args)}, "
            f"forcing empty dict."
        )
        raw_args = {}

    # -----------------------------------------------------------
    # Strict return packet
    # -----------------------------------------------------------
    return {
        "ok": True,
        "skill_name": skill_name,
        "arguments": raw_args,
        "is_fallback": is_fallback,
    }


__all__ = ["route_planner_action"]
