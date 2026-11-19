# reasoning_controller.py — Phase 21 Strict Semantic Context Engine
# -------------------------------------------------------------------------
# Phase 21 removes all semantic execution paths:
#
#   • No file grounding
#   • No contextual summaries
#   • No deterministic or semantic fallback reasoning
#   • No user_output / result generation
#
# Reasoning Controller now serves ONE purpose:
#   → Provide lightweight semantic *context hints* for the strict planner.
#
# Notes:
#   • MUST NOT perform any execution
#   • MUST NOT touch fileops
#   • MUST NOT modify entities for execution
#   • MUST return a consistent Phase-21 metadata packet
#
# -------------------------------------------------------------------------

from solomon_core.logger import get_logger

logger = get_logger("reasoning_controller")


# -------------------------------------------------------------------------
# Phase-21 semantic context extractor
# -------------------------------------------------------------------------
def process_reasoning(intent: str, entities: dict, task_text: str) -> dict:
    """
    Phase-21 strict reasoning controller.

    Purpose:
        Provide optional semantic hints ONLY.
        Zero execution, zero grounding, zero summaries.

    This is purely metadata for:
        • planner_interface
        • diagnostics
        • unified_executor context
    """

    try:
        logger.debug(f"[Reasoning] Generating Phase-21 semantic context for: {task_text}")

        # ------------------------------------------------------------------
        # Extract minimal context hints (non-executable)
        # ------------------------------------------------------------------
        filename = entities.get("filename")
        has_file = bool(filename)

        context = {
            "intent": intent,
            "task_text": task_text,
            "has_file": has_file,
            "filename": filename if has_file else None,
        }

        # ------------------------------------------------------------------
        # Lightweight semantic tags (planner metadata only)
        # ------------------------------------------------------------------
        semantic_tags = []

        if has_file:
            semantic_tags.append("file-referenced")

        if len(task_text.split()) < 6:
            semantic_tags.append("short-query")

        if any(w in task_text.lower() for w in ["analyze", "summarize", "explain"]):
            semantic_tags.append("analysis-requested")

        # ------------------------------------------------------------------
        # Phase-21 Standardized Packet
        # ------------------------------------------------------------------
        return {
            "ok": True,
            "reasoning_source": "semantic",
            "context_hint": "phase21-semantic-metadata",
            "semantic_tags": semantic_tags,
            "context": context,
        }

    except Exception as e:
        logger.error(f"[Reasoning] Exception in Phase-21 reasoning: {e}")

        return {
            "ok": False,
            "reasoning_source": "semantic",
            "context_hint": "semantic-error",
            "error_message": str(e),
            "semantic_tags": [],
            "context": {
                "intent": intent,
                "task_text": task_text,
                "has_file": False,
                "filename": None,
            },
        }
