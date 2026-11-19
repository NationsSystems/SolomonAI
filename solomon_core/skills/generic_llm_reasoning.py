# solomon_core/skills/generic_llm_reasoning.py
# ---------------------------------------------------------------
# Phase 38 — Generic LLM Reasoning Micro-Skill (SIGNAL ONLY)
#
# GUARANTEES:
#   • NO direct LLM execution
#   • NO query_llm calls
#   • Emits reasoning request ONLY
#   • Orchestrator is sole execution authority
# ---------------------------------------------------------------

import json
from solomon_core.logger import get_logger

logger = get_logger("skill_generic_llm_reasoning")

# ---------------------------------------------------------------------------
# Phase-38 Authority Declaration
# ---------------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # Skills may NEVER execute reasoning


# ---------------------------------------------------------------
# Micro-skill entrypoint (signal-only)
# ---------------------------------------------------------------
def execute(arguments: dict):
    """
    Phase-38 contract:
        • Build reasoning intent
        • Emit structured request
        • Do NOT call LLM
    """

    try:
        query_text = None

        # Preferred key
        if isinstance(arguments, dict):
            query_text = arguments.get("query") or arguments.get("action")

        if not query_text:
            query_text = json.dumps(arguments, ensure_ascii=False)

        reasoning_request = {
            "type": "generic_llm_reasoning",
            "prompt": (
                "You are Solomon's reasoning engine.\n"
                "Provide a concise final answer.\n"
                "No chain-of-thought.\n\n"
                f"Task: {query_text}\n"
                f"Context: {json.dumps(arguments, indent=2, ensure_ascii=False)}\n"
            ),
            "metadata": {
                "skill": "generic_llm_reasoning",
                "signal_only": True,
            },
        }

        return {
            "ok": True,
            "schema": "ReasoningRequest.Generic",
            "result": reasoning_request,
            "user_output": None,
        }

    except Exception as e:
        logger.error(f"[generic_llm_reasoning] Signal construction error: {e}")
        return {
            "ok": False,
            "schema": "ReasoningRequest.Generic",
            "error": str(e),
            "user_output": "Unable to construct reasoning request.",
        }
