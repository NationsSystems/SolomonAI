# solomon_core/solomon_tools/intent_router.py — Phase 39 FSM Spoke (FOCUSED OBSERVABILITY)
# ---------------------------------------------------------------------------
# ROLE:
#   • Observe request characteristics
#   • Emit a factual observation vector (FLAT, FSM-COMPATIBLE)
#
# GUARANTEES:
#   • NO execution authority
#   • NO gating
#   • NO routing decisions
#   • NO implicit requirements
#
# AUTHORITY:
#   • Orchestrator is sole decision-maker
#   • This module emits OBSERVATIONS ONLY
#
# Phase 39:
#   • No logic changes
#   • Logging aligned to FOM-39 (decision-level visibility, low noise)
# ---------------------------------------------------------------------------

from solomon_core.logger import get_logger

logger = get_logger("intent_router")


# ============================================================================
# Router Entrypoint (PURE OBSERVATION)
# ============================================================================
def route_intent(task_text: str, entities: dict) -> dict:
    """
    Emit a single, stateless, FLAT observation vector.

    Phase-38B REQUIREMENTS:
        • Must NEVER infer requirements
        • Must NEVER imply execution
        • Must NEVER promote 'unknown' into a runnable path
        • Output must be FSM-compatible
    """

    safe_entities = dict(entities) if isinstance(entities, dict) else {}

    docs = safe_entities.get("docs")
    docs = docs if isinstance(docs, list) else []
    docs_count = len(docs)

    intent = safe_entities.get("intent")

    observation = {
        # ----------------------------
        # Task facts
        # ----------------------------
        "task_present": bool(safe_entities.get("task_present")),

        # CRITICAL FIX:
        # intent_present MUST be False for "unknown"
        "intent_present": bool(intent and intent != "unknown"),

        # ----------------------------
        # Artifact facts
        # ----------------------------
        "docs_count": docs_count,
        "has_single_doc": docs_count == 1,
        "has_multiple_docs": docs_count >= 2,

        # Phase-38 rule:
        # Artifacts are required ONLY if documents already exist
        "artifacts_required": docs_count > 0,

        # ----------------------------
        # Safety facts (FSM expects this)
        # ----------------------------
        "system_safe": True,

        # ----------------------------
        # Telemetry facts (NON-AUTHORITATIVE)
        # ----------------------------
        "prototype_telemetry_present": bool(
            safe_entities.get("prototype_telemetry")
        ),
    }

    # Phase 39: log observation summary, not full chatter
    logger.info(
        "[Phase39][ROUTER_OBSERVATION]",
        extra={
            "event_id": safe_entities.get("orchestrator_event_id"),
            "intent_present": observation["intent_present"],
            "docs_count": observation["docs_count"],
            "task_present": observation["task_present"],
        },
    )

    return observation


__all__ = ["route_intent"]
