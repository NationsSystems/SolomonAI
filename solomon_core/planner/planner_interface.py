# solomon_core/planner_interface.py
# ---------------------------------------------------------------
# Phase 23.5 — Strict Planner Interface (Minimal + DocIntel-Aware)
# ---------------------------------------------------------------
# DESIGN CONTRACT (Phase 23.5):
#
#   The strict planner:
#     • NEVER performs document logic
#     • NEVER inspects file contents or doc_texts
#     • NEVER manipulates docs[] beyond structural validation
#     • NEVER merges or rewrites entities
#     • ONLY:
#          – call backend LLM planner
#          – validate output structure
#          – attach routed planner steps
#
#   DocIntel logic (scope extraction, comparison, summarization, etc.)
#   happens inside micro-skills ONLY.
# ---------------------------------------------------------------

import uuid
import json
from solomon_core.logger import get_logger

from solomon_core.planner.planner_backend import build_strict_plan
from solomon_core.planner.plan_validator import validate_strict_plan
from solomon_core.planner.planner_action_router import route_planner_action

# Domain-level DocIntel intent constants
from solomon_core.domains import (
    BID, PROPOSAL, ESTIMATE, CONTRACT, INVOICE,
    SPECIFICATION, PROCUREMENT, GENERIC_DOCUMENT,
)

DOCINTEL_INTENTS = {
    BID, PROPOSAL, ESTIMATE, CONTRACT, INVOICE,
    SPECIFICATION, PROCUREMENT, GENERIC_DOCUMENT,
}

logger = get_logger("planner_interface")


# ---------------------------------------------------------------
# Strict EMPTY plan
# ---------------------------------------------------------------
def _empty(reason: str):
    return {
        "ok": False,
        "steps": [],
        "plan_id": str(uuid.uuid4()),
        "user_output": reason,
        "plan_summary": reason,
        "code": "",
        "error": reason,
        "planner_mode": "strict",
        "pipeline_version": "v23.5",
        "planner_confidence": 0.0,
    }


# ---------------------------------------------------------------
# Minimal structural multi-doc sanity (no DocIntel logic)
# ---------------------------------------------------------------
def _validate_multi_doc_structure(entities: dict):
    """
    Phase 23.5 — Only validate that docs[] exists and is structurally correct.
    NO domain logic. NO exploration of intent semantics.
    """

    if not isinstance(entities, dict):
        return True, None

    docs = entities.get("docs")

    # docs missing → okay for planner
    if docs is None:
        return True, None

    # docs must be a list
    if not isinstance(docs, list):
        return False, "Invalid entities.docs: must be a list"

    # empty list → structural failure
    if len(docs) == 0:
        return False, "No documents provided for multi-document task"

    return True, None


# ---------------------------------------------------------------
# PUBLIC ENTRYPOINT — Strict Planner Interface
# ---------------------------------------------------------------
def generate_plan_strict(task_text: str, entities: dict = None) -> dict:

    if not isinstance(task_text, str) or not task_text.strip():
        return _empty("Invalid task_text")

    # Phase-22 realtime restrictions remain intact
    realtime_triggers = (
        "time", "current time", "what time",
        "date", "current date", "today",
        "now", "right now",
    )
    lowered = task_text.lower()
    if any(trigger in lowered for trigger in realtime_triggers):
        return _empty(
            "I do not have access to real-time data such as the current time or date "
            "unless an authorized external tool is enabled."
        )

    entities = entities or {}
    intent = entities.get("intent")

    # -----------------------------------------------------------
    # Phase-23.5 Multi-document STRUCTURE check ONLY
    # -----------------------------------------------------------
    if intent in DOCINTEL_INTENTS:
        ok_struct, struct_err = _validate_multi_doc_structure(entities)
        if not ok_struct:
            return _empty(f"Multi-document validation failed: {struct_err}")

    # -----------------------------------------------------------
    # 1) CALL LLM PLANNER BACKEND
    # -----------------------------------------------------------
    raw = build_strict_plan(task_text, entities)

    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            return _empty("Planner backend returned invalid JSON")

    if not isinstance(raw, dict):
        return _empty("Planner backend failure")

    # -----------------------------------------------------------
    # 2) VALIDATE STRUCTURE
    # -----------------------------------------------------------
    validation = validate_strict_plan(raw)

    if not validation.get("ok"):
        return _empty(f"Validation failed: {validation.get('error')}")

    if "plan" not in validation:
        return _empty("Validator returned no 'plan' field")

    normalized = validation["plan"]

    # Extract steps safely
    steps = normalized.get("steps", [])
    if not isinstance(steps, list):
        return _empty("Validator produced invalid steps list")

    try:
        logger.debug("[PLAN STEPS]\n" + json.dumps(steps, indent=2))
    except Exception:
        logger.debug("Could not print plan steps")

    # -----------------------------------------------------------
    # 3) ROUTE EACH STEP TO A MICRO-SKILL
    # -----------------------------------------------------------
    routed_steps = []

    for idx, step in enumerate(steps, start=1):
        routed = route_planner_action(step)

        if not routed.get("ok"):
            routed = {
                "ok": True,
                "skill_name": "skill_generic_llm_reasoning",
                "arguments": {},
                "is_fallback": True,
            }

        routed_steps.append({
            "id": step.get("id") or f"step_{idx}_{uuid.uuid4()}",
            "action": (step.get("action") or "").strip().lower(),
            "arguments": routed.get("arguments", {}),
            "depends_on": step.get("depends_on", []),
            "skill_name": routed.get("skill_name"),
            "is_fallback": routed.get("is_fallback", False),
        })

    # -----------------------------------------------------------
    # 4) Ensure canonical plan_id
    # -----------------------------------------------------------
    raw_id = raw.get("plan_id") or normalized.get("plan_id") or uuid.uuid4()
    try:
        final_plan_id = str(raw_id)
    except Exception:
        final_plan_id = str(uuid.uuid4())

    # -----------------------------------------------------------
    # RETURN STRICT PLAN (DO NOT EXPAND IT)
    # -----------------------------------------------------------
    return {
        "ok": True,
        "plan_id": final_plan_id,
        "steps": routed_steps,
        "code": normalized.get("code", ""),
        "user_output": normalized.get("user_output", ""),
        "plan_summary": normalized.get("plan_summary", ""),
        "planner_confidence": normalized.get("planner_confidence", 0.0),
        "pipeline_version": normalized.get("pipeline_version", "v23.5"),
        "error": "",
        "planner_mode": "strict",
    }
