# ------------------------------------------------------------------
# FILE: solomon_core/presentation/response_governor.py
# DIRECTORY: solomon_core/presentation/
# ------------------------------------------------------------------
# Response Governor (STRUCTURAL VALIDATION — NO MUTATION)
#
# PURPOSE:
#   Deterministic structural validation layer for assistant payloads.
#
# GUARANTEES:
#   • NO mutation
#   • NO fallback generation
#   • NO rewriting
#   • VALIDATE STRUCTURE ONLY
#   • FAIL FAST only when no displayable answer exists
# ------------------------------------------------------------------

import json
from typing import Any, Dict

from solomon_core.logger import get_logger

logger = get_logger("response_governor")


# ============================================================================
# RULES
# ============================================================================
MAX_SUGGESTIONS = 5


# ============================================================================
# HELPERS
# ============================================================================
def _safe_json_load(text: str) -> Dict[str, Any] | None:
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    return None


def _validate_answer(answer: Any) -> bool:
    return isinstance(answer, str) and len(answer.strip()) > 0


def _validate_bridge(bridge: Any) -> bool:
    """
    Bridge text is a UI support field.

    It should not invalidate an otherwise useful assistant answer simply
    because the model missed a phrasing or word-count preference.
    """

    return bridge is None or isinstance(bridge, str)


def _validate_suggestions(suggestions: Any) -> bool:
    """
    Suggestions are optional UI support fields.

    The renderer may choose to ignore, trim, or hide invalid suggestion
    structures, but the governor should not discard a valid answer because
    suggestion chips are imperfect.
    """

    if suggestions is None:
        return True

    if not isinstance(suggestions, list):
        return True

    return all(isinstance(item, str) for item in suggestions)


def _bridge_word_count(bridge: Any) -> int:
    if not isinstance(bridge, str):
        return 0

    return len(bridge.strip().split())


def _suggestion_count(suggestions: Any) -> int:
    if not isinstance(suggestions, list):
        return 0

    return min(len(suggestions), MAX_SUGGESTIONS)


# ============================================================================
# GOVERNOR (STRUCTURAL VALIDATION — PASS THROUGH)
# ============================================================================
def govern_response(text: str, mode: str = "chat") -> str:
    """
    Structural validation governor.

    - parses JSON
    - requires a displayable answer
    - allows non-fatal UI support fields to pass through
    - DOES NOT modify output
    - raises only when the response cannot safely produce an answer
    """

    if text is None:
        raise ValueError("Governor received None response")

    parsed = _safe_json_load(text)

    if not parsed:
        logger.error("[GOVERNOR][INVALID_JSON]")
        raise ValueError("Invalid JSON response from LLM")

    answer = parsed.get("answer")
    bridge = parsed.get("bridge")
    suggestions = parsed.get("suggestions")

    if not _validate_answer(answer):
        logger.error("[GOVERNOR][INVALID_ANSWER]")
        raise ValueError("Invalid answer field")

    if not _validate_bridge(bridge):
        logger.warning("[GOVERNOR][BRIDGE_IGNORED]")

    if not _validate_suggestions(suggestions):
        logger.warning("[GOVERNOR][SUGGESTIONS_IGNORED]")

    logger.info(
        "[GOVERNOR][VALID]",
        extra={
            "mode": mode,
            "suggestion_count": _suggestion_count(suggestions),
            "bridge_len": _bridge_word_count(bridge),
        },
    )

    return text