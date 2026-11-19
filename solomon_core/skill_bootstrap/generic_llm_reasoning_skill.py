# solomon_core/skill_bootstrap/generic_llm_reasoning_skill.py
# -----------------------------------------------------------------------
# Phase 38 — Generic LLM Reasoning Skill (SIGNAL-ONLY)
#
# PURPOSE:
#   • Encodes a strict reasoning request for the orchestrator
#   • NO LLM invocation
#   • NO execution authority
#   • NO chain-of-thought leakage
#
# OUTPUT CONTRACT:
#   Always returns a dict:
#       {
#         "ok": bool,
#         "llm_request": {
#             "type": "generic_reasoning",
#             "prompt": <str>
#         },
#         "error": str | None
#       }
# -----------------------------------------------------------------------

import json
from solomon_core.logger import get_logger

logger = get_logger("skill.generic_llm_reasoning")

# -----------------------------------------------------------------------
# Phase-38 Authority Declaration
# -----------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # Skill may NEVER call LLMs


# ======================================================================
# SIGNAL-ONLY MICRO-SKILL
# ======================================================================
def execute(args: dict) -> dict:
    """
    Builds a STRICT reasoning request for the orchestrator.

    Expected args:
        {
           "query": <string>,
           "context": <dict or string> (optional)
        }
    """

    if not isinstance(args, dict):
        return {
            "ok": False,
            "llm_request": None,
            "error": "Invalid arguments for generic_llm_reasoning_skill"
        }

    query = args.get("query")
    context = args.get("context", {})

    if not isinstance(query, str) or not query.strip():
        return {
            "ok": False,
            "llm_request": None,
            "error": "Missing or invalid 'query' for reasoning skill"
        }

    # ------------------------------------------------------------------
    # STRICT PROMPT CONSTRUCTION (NO EXECUTION)
    # ------------------------------------------------------------------
    prompt_payload = {
        "task": query,
        "context": context or {},
        "rules": [
            "Respond ONLY with valid JSON.",
            "JSON must contain: {\"result\": <string>}.",
            "Do NOT include chain-of-thought.",
            "Do NOT include intermediate reasoning.",
            "Return only the final factual answer."
        ]
    }

    prompt_str = json.dumps(prompt_payload, ensure_ascii=False)

    logger.info("[generic_llm_reasoning] Emitting reasoning request signal")

    return {
        "ok": True,
        "llm_request": {
            "type": "generic_llm_reasoning",
            "prompt": prompt_str,
        },
        "error": None,
    }
