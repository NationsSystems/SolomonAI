# ---------------------------------------------------------------------------
# FILE: solomon_core/clarification/clarification_pipeline.py
# DIRECTORY: solomon_core/clarification/
# ---------------------------------------------------------------------------
# Clarification Pipeline (Constitutional Implementation)
# ---------------------------------------------------------------------------

import json
from typing import List

from solomon_core.logger import get_logger
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionInput,
    LLMExecutionMode,
)
from solomon_core.llm.llm_executor import execute_llm
from solomon_core.llm.llm_prompting import (
    LIAISON_PROMPT_CLARIFICATION,
)

from .clarification_contract import (
    ClarificationResponse,
)

logger = get_logger("clarification_pipeline")


# ============================================================================
# Prompt Builder
# ============================================================================

def _build_prompt(user_query: str) -> str:
    return f"""
TASK:
Generate a clarification response for the user request below.

{LIAISON_PROMPT_CLARIFICATION}

User request:
{user_query}
""".strip()


# ============================================================================
# JSON Parsing
# ============================================================================

def _parse_json(text: str):
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return (
                parsed.get("answer", "").strip(),
                parsed.get("bridge", "").strip(),
                parsed.get("suggestions", []),
            )
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, dict):
                return (
                    parsed.get("answer", "").strip(),
                    parsed.get("bridge", "").strip(),
                    parsed.get("suggestions", []),
                )
        except Exception:
            pass

    return "", "", []


# ============================================================================
# STRICT VALIDATION (NON-DESTRUCTIVE)
# ============================================================================

def _is_invalid(val: str) -> bool:
    if not isinstance(val, str):
        return True
    return val.strip() == ""


def _validate(answer: str, bridge: str, suggestions: List[str]) -> bool:
    if _is_invalid(answer) or _is_invalid(bridge):
        return False

    if not isinstance(suggestions, list):
        return False

    if len(suggestions) < 3 or len(suggestions) > 5:
        return False

    cleaned = []
    for s in suggestions:
        if _is_invalid(s):
            return False
        if not isinstance(s, str):
            return False
        v = s.strip()
        if not v:
            return False
        cleaned.append(v)

    if len(set(cleaned)) != len(cleaned):
        return False

    return True


# ============================================================================
# CONTROLLED NORMALIZATION (SECOND PASS)
# ============================================================================

def _normalize_with_llm(raw_text: str) -> str:
    prompt = f"""
Normalize the following output into valid JSON format.

Preserve meaning exactly. Do not introduce new ideas.

{raw_text}

Return ONLY:

{{
  "answer": "string",
  "bridge": "string",
  "suggestions": ["string","string","string"]
}}

Rules:
- preserve intent exactly
- no generic placeholders
- 3–5 meaningful suggestions
- output ONLY JSON
"""
    result = execute_llm(
        LLMExecutionInput(
            user_query=prompt,
            mode=LLMExecutionMode.INFORMATIONAL_ONLY,
            context=None,
        )
    )

    if result and result.output and result.output.text:
        return result.output.text.strip()

    return ""


# ============================================================================
# USER INPUT EXTRACTION
# ============================================================================

def _extract_user_query(casefile) -> str:
    try:
        raw = getattr(casefile, "raw_user_input", None)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()

        evidence = getattr(casefile, "positive_evidence", []) or []
        for item in evidence:
            if getattr(item, "ref_id", None) == "raw_user_input":
                text = getattr(item, "description", "")
                if text:
                    return str(text).strip()
    except Exception:
        pass

    return ""


# ============================================================================
# Public API
# ============================================================================

def run_clarification_pipeline(
    *,
    casefile,
    conversation_id=None,
    request_id=None,
):

    user_query = _extract_user_query(casefile)

    if not user_query:
        raise ValueError("Clarification pipeline missing user_query.")

    prompt = _build_prompt(user_query)

    # -------------------------------
    # CALL 1 — GENERATION
    # -------------------------------
    result = execute_llm(
        LLMExecutionInput(
            user_query=prompt,
            mode=LLMExecutionMode.INFORMATIONAL_ONLY,
            context=None,
        )
    )

    output_text = ""
    if result and result.output and result.output.text:
        output_text = result.output.text.strip()

    answer, bridge, suggestions = _parse_json(output_text)

    # -------------------------------
    # CALL 2 — NORMALIZATION (IF NEEDED)
    # -------------------------------
    if not _validate(answer, bridge, suggestions):
        logger.info("[CLARIFICATION] Normalization pass triggered")

        normalized = _normalize_with_llm(output_text)
        answer, bridge, suggestions = _parse_json(normalized)

    # -------------------------------
    # FINAL ENFORCEMENT
    # -------------------------------
    if not _validate(answer, bridge, suggestions):
        logger.warning("[CLARIFICATION] Failed after normalization")

        return {
            "answer": "I need a bit more context to clarify your request accurately.",
            "bridge": "Choose the closest direction and I’ll refine it.",
            "suggestions": [
                "Explain previous topic again",
                "Clarify specific part",
                "Give simpler explanation"
            ],
        }

    return {
        "answer": answer,
        "bridge": bridge,
        "suggestions": suggestions,
    }