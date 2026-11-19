# solomon_core/planner/plan_validator.py
# ---------------------------------------------------------------
# Phase 23.5 — Strict Deterministic Plan Validator (Structural Only)
#
# PURPOSE:
#   • Validate ONLY the structure of planner-generated plans
#   • Enforce strict schema for steps[]
#   • Reject malformed plans early with explicit errors
#   • NEVER mutate or infer arguments (no domain logic)
#   • NEVER normalize document structures (Phase-23 requirement)
#
# CONTRACT:
#   VALID plan must contain:
#       plan.steps = list of step dicts
#       each step contains:
#           id: str (non-empty)
#           action: str (non-empty)
#           arguments: dict
#           depends_on: list
#
# Everything else is passed through untouched.
#
# This validator is intentionally minimal and deterministic.
# It is the foundation of ALL strict planning in Solomon.
# ---------------------------------------------------------------

import uuid

REQUIRED_FIELDS = {"id", "action", "arguments", "depends_on"}


def _force_list(x):
    return x if isinstance(x, list) else []


def _force_dict(x):
    return x if isinstance(x, dict) else {}


def _force_string(x, default=""):
    if x is None:
        return default
    if not isinstance(x, str):
        try:
            x = str(x)
        except Exception:
            return default
    x = x.strip()
    return x if x else default


# ---------------------------------------------------------------
# Normalize & Validate a Single Planner Step
# ---------------------------------------------------------------
def _validate_step(step, index):
    if not isinstance(step, dict):
        return None, f"Step {index}: must be a dict"

    normalized = {}

    # Ensure all required fields exist
    for field in REQUIRED_FIELDS:
        normalized[field] = step.get(field)

    # --- ID ------------------------------------------------------
    sid = normalized["id"]
    if not isinstance(sid, str) or not sid.strip():
        normalized["id"] = str(uuid.uuid4())
    else:
        normalized["id"] = sid.strip()

    # --- ACTION --------------------------------------------------
    action = normalized["action"]
    if not isinstance(action, str):
        action = _force_string(action)

    normalized["action"] = action

    if not normalized["action"]:
        return None, f"Step {index}: action must be a non-empty string"

    # --- ARGUMENTS ----------------------------------------------
    args = _force_dict(step.get("arguments"))
    normalized["arguments"] = args

    # --- DEPENDS_ON ---------------------------------------------
    normalized["depends_on"] = _force_list(step.get("depends_on"))

    return normalized, None


# ---------------------------------------------------------------
# MAIN VALIDATOR — STRICT STRUCTURAL CHECK ONLY
# ---------------------------------------------------------------
def validate_strict_plan(raw):
    """
    Input: raw planner LLM JSON
    Output:
        {
            ok: bool,
            error: str,
            plan: { steps: [...], code: "...", user_output: "...", ... }
        }

    STRICT RULES:
      • steps MUST exist and be non-empty
      • each step must contain valid fields
      • arguments are passed through untouched
      • no inference, no normalization, no guessing
      • failure ALWAYS returns a clear error
    """

    # 1. Top-level must be a dict
    if not isinstance(raw, dict):
        return {
            "ok": False,
            "error": "Plan must be a dictionary",
            "plan": {},
        }

    steps = _force_list(raw.get("steps", []))

    # 2. HARD FAILURE: NO STEPS
    if not steps:
        return {
            "ok": False,
            "error": "Planner returned ZERO steps (hard failure)",
            "plan": {},
        }

    validated_steps = []

    # 3. Validate each step
    for idx, step in enumerate(steps, start=1):
        cleaned, err = _validate_step(step, idx)
        if err:
            return {
                "ok": False,
                "error": err,
                "plan": {},
            }
        validated_steps.append(cleaned)

    # 4. Build normalized, safe plan object (structural only)
    plan_out = {
        "ok": True,
        "steps": validated_steps,
        "code": _force_string(raw.get("code")),
        "user_output": _force_string(raw.get("user_output")),
        "plan_summary": _force_string(raw.get("plan_summary")),
        "error": _force_string(raw.get("error")),
        "planner_confidence": raw.get("planner_confidence", 0.0),
        "pipeline_version": _force_string(raw.get("pipeline_version", "v23.5")),
    }

    return {
        "ok": True,
        "error": "",
        "plan": plan_out,
    }
