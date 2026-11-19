# reasoning_controller.py — Phase-38 SAFE Reasoning Spoke
# ------------------------------------------------------------
# SIGNAL-ONLY reasoning controller
#
# Phase-38 GUARANTEES:
#   • NO independent execution
#   • NO direct LLM calls
#   • All execution gated through orchestrator
#   • Emits reasoning REQUESTS ONLY
# ------------------------------------------------------------

import traceback
from typing import Dict, Tuple

from solomon_core.solomon_tools.reasoning.semantic_router import route_reasoning
from solomon_core.solomon_tools.reasoning.file_grounding import extract_file_facts
from solomon_core.solomon_tools.validators import validate_task
from solomon_core.logger import get_logger

logger = get_logger("reasoning_controller")

# ---------------------------------------------------------------------------
# Phase-38 Authority Declaration
# ---------------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # Reasoning may NEVER execute independently

# ---------------------------------------------------------------------------
# Primary reasoning spoke (signal-only)
# ---------------------------------------------------------------------------
def process_reasoning(
    intent: str,
    entities: dict,
    task_text: str,
    *,
    execution_authorized: bool = False,
) -> dict:
    """
    Phase-38 GUARANTEE:
        • NO execution unless execution_authorized=True
        • NO LLM calls unless execution_authorized=True
        • Returns reasoning signals only when blocked
    """

    logger.info(
        "[ReasoningController] intent=%s execution_authorized=%s",
        intent,
        execution_authorized,
    )

    try:
        # 1️⃣ Validation (always allowed — signal only)
        try:
            validate_task(intent, entities)
        except Exception as e:
            logger.warning(f"Validation warning for intent '{intent}': {e}")
            return {
                "success": False,
                "reasoning_source": "validation",
                "error_type": "ValidationError",
                "error_message": str(e),
                "summary": "Validation failed before reasoning could begin.",
                "execution_authorized": False,
            }

        # 2️⃣ Block execution if unauthorized
        if not execution_authorized:
            logger.info(
                "[Phase38Block] Reasoning requested without execution authorization"
            )
            return {
                "success": False,
                "reasoning_source": "blocked",
                "summary": "Reasoning blocked pending orchestrator authorization.",
                "execution_authorized": False,
            }

        # 3️⃣ Build structured reasoning REQUESTS
        # --- Semantic comparison intent ---
        if "file2" in entities or intent.lower() in {
            "compare", "contrast", "difference", "similarity"
        }:
            route, reasoning_request = route_reasoning(intent, entities)
            return {
                "success": True,
                "reasoning_source": route,
                "reasoning_request": reasoning_request,
                "execution_authorized": True,
            }

        # --- Single-file grounding request ---
        if "filename" in entities:
            file_context = extract_file_facts(entities["filename"])
            return {
                "success": True,
                "reasoning_source": "file_grounding",
                "reasoning_request": {
                    "inputs": {"filename": entities["filename"]},
                    "constraints": {"no_execution": True},
                    "expected_outputs": ["parsed_content", "summary_placeholder"],
                },
                "execution_authorized": True,
            }

        # --- Default fallback request ---
        return {
            "success": False,
            "reasoning_source": "no_route",
            "reasoning_request": {
                "reason": f"No reasoning route matched intent '{intent.lower()}'",
                "inputs": entities,
                "constraints": {"no_execution": True},
            },
            "execution_authorized": True,
        }

    except Exception as e:
        trace = traceback.format_exc(limit=3)
        logger.error(f"[ReasoningController] Exception: {e}\n{trace}")
        return {
            "success": False,
            "reasoning_source": "internal",
            "error_type": type(e).__name__,
            "error_message": str(e),
            "summary": "Reasoning controller failed.",
            "execution_authorized": False,
        }


# ---------------------------------------------------------------------------
# Deterministic task wrapper (signal-only, orchestrator must authorize)
# ---------------------------------------------------------------------------
def deterministic_path(
    intent: str,
    entities: dict,
    fn,
    *,
    execution_authorized: bool = False,
):
    """
    Phase-38 GUARANTEE:
        • Deterministic execution requires orchestrator authorization
        • Emits structured request if unauthorized
    """
    if not execution_authorized:
        logger.error(
            "[Phase38Violation] deterministic_path invoked without authorization"
        )
        return {
            "success": False,
            "reasoning_source": "blocked",
            "summary": "Deterministic execution blocked by orchestrator.",
            "execution_authorized": False,
        }

    return {
        "success": True,
        "reasoning_source": "deterministic_request",
        "reasoning_request": {
            "intent": intent,
            "entities": entities,
            "fn": fn.__name__,
            "constraints": {"requires_orchestrator": True},
        },
        "execution_authorized": True,
    }


__all__ = [
    "process_reasoning",
    "deterministic_path",
    "EXECUTION_AUTHORITY",
]
