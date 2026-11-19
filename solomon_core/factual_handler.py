# solomon_core/factual_handler.py — FACTUAL HANDLER REGISTRY (PACKET-COMPATIBLE)
# ---------------------------------------------------------------------------
# PURPOSE:
#   Central, authoritative registry for ALL factual queries.
#
# GUARANTEES:
#   • Emits PAYLOAD ONLY (no headers, no routing flags)
#   • Orchestrator wraps results into PacketEnvelope
#   • Deterministic authority preserved
#
# LOGGING:
#   • Subsystem-based tags only
#   • No phase labels in log messages
# ---------------------------------------------------------------------------

from typing import Callable, Dict, Any
import re

from solomon_core.logger import get_logger

logger = get_logger("solomon_core.factual_handler")

# ============================================================================
# Registry
# ============================================================================

_FACTUAL_HANDLERS: Dict[str, Callable[[str, Dict[str, Any]], Dict[str, Any]]] = {}


# ============================================================================
# Registration API
# ============================================================================

def register_factual_handler(
    intent: str,
    handler: Callable[[str, Dict[str, Any]], Dict[str, Any]],
):
    if not callable(handler):
        raise TypeError("Factual handler must be callable")

    _FACTUAL_HANDLERS[intent] = handler
    logger.info("[FACTUAL][REGISTER]", extra={"intent": intent})


def has_factual_handler(intent: str) -> bool:
    return intent in _FACTUAL_HANDLERS


# ============================================================================
# Dispatch API (PAYLOAD ONLY)
# ============================================================================

def handle_factual_query(
    intent: str,
    raw_text: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Returns a payload-only dict.
    Header, routing, and presentation are Orchestrator-owned.
    """

    if intent not in _FACTUAL_HANDLERS:
        logger.warning(
            "[FACTUAL][MISS]",
            extra={"intent": intent, "event_id": context.get("event_id")},
        )
        return {
            "ok": False,
            "resolvable": False,
            "result": None,
            "user_output": None,
        }

    logger.info(
        "[FACTUAL][HANDLE]",
        extra={"intent": intent, "event_id": context.get("event_id")},
    )

    try:
        return _FACTUAL_HANDLERS[intent](raw_text, context)
    except Exception as exc:
        logger.error(
            "[FACTUAL][ERROR]",
            extra={
                "intent": intent,
                "event_id": context.get("event_id"),
                "error": str(exc),
            },
        )
        return {
            "ok": False,
            "resolvable": False,
            "result": None,
            "user_output": None,
        }


# ============================================================================
# Deterministic Resolution Logic
# ============================================================================

_CAPITALS = {
    "texas": "Austin",
    "california": "Sacramento",
    "new york": "Albany",
    "florida": "Tallahassee",
}


def _solve_simple_math(text: str):
    """Deterministic arithmetic resolver (two integers only)."""
    patterns = [
        (r"(\d+)\s*\+\s*(\d+)", lambda a, b: a + b),
        (r"(\d+)\s*-\s*(\d+)", lambda a, b: a - b),
        (r"(\d+)\s*\*\s*(\d+)", lambda a, b: a * b),
        (r"(\d+)\s*/\s*(\d+)", lambda a, b: a // b),
        (r"(\d+)\s+multiplied by\s+(\d+)", lambda a, b: a * b),
        (r"(\d+)\s+times\s+(\d+)", lambda a, b: a * b),
        (r"(\d+)\s+divided by\s+(\d+)", lambda a, b: a // b),
        (r"(\d+)\s+plus\s+(\d+)", lambda a, b: a + b),
        (r"(\d+)\s+minus\s+(\d+)", lambda a, b: a - b),
    ]

    for pattern, op in patterns:
        match = re.search(pattern, text)
        if match:
            a, b = int(match.group(1)), int(match.group(2))
            return op(a, b)

    return None


def _factual_query_handler(raw_text: str, context: Dict[str, Any]) -> Dict[str, Any]:
    text = raw_text.lower().strip()

    # ----------------------------------
    # Capital lookup (resolvable)
    # ----------------------------------
    if "capital of" in text:
        for region, capital in _CAPITALS.items():
            if region in text:
                return {
                    "ok": True,
                    "resolvable": True,
                    "result": capital,
                    "user_output": capital,
                }

        return {
            "ok": True,
            "resolvable": False,
            "result": None,
            "user_output": None,
        }

    # ----------------------------------
    # Arithmetic (resolvable)
    # ----------------------------------
    math_result = _solve_simple_math(text)
    if math_result is not None:
        return {
            "ok": True,
            "resolvable": True,
            "result": math_result,
            "user_output": str(math_result),
        }

    # ----------------------------------
    # Definition-style (sometimes resolvable)
    # ----------------------------------
    if text.startswith("what does") or text.startswith("what is"):
        if "scope of work" in text:
            definition = (
                "Scope of work refers to the specific tasks, deliverables, "
                "services, responsibilities, boundaries, and assumptions that "
                "are included in an agreement, request, project, or work plan. "
                "Items not stated in the scope may need clarification before "
                "they should be treated as included."
            )
            return {
                "ok": True,
                "resolvable": True,
                "result": definition,
                "user_output": definition,
            }

        return {
            "ok": True,
            "resolvable": False,
            "result": None,
            "user_output": None,
        }

    # ----------------------------------
    # Advisory / subjective factual forms (non-resolvable)
    # ----------------------------------
    advisory_markers = [
        "should i",
        "what should",
        "is it a good idea",
        "best way to",
        "right now",
    ]

    if any(marker in text for marker in advisory_markers):
        return {
            "ok": True,
            "resolvable": False,
            "result": None,
            "user_output": None,
        }

    # ----------------------------------
    # Default factual non-resolution
    # ----------------------------------
    return {
        "ok": True,
        "resolvable": False,
        "result": None,
        "user_output": None,
    }


# ============================================================================
# Registration
# ============================================================================

register_factual_handler("factual_query", _factual_query_handler)