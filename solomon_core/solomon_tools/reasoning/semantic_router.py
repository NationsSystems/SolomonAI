# semantic_router.py — Phase-38 SAFE
# ------------------------------------------------------------
# SIGNAL-ONLY semantic routing
#
# Phase-38 GUARANTEES:
#   • NO LLM calls
#   • NO embeddings
#   • NO file parsing
#   • NO execution or conclusions
#   • Emits reasoning REQUESTS ONLY
# ------------------------------------------------------------

from typing import Dict, Any, Tuple

# ------------------------------------------------------------------
# Phase-38 Authority Declaration
# ------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # Router is SIGNAL-ONLY


# ------------------------------------------------------------------
# Semantic comparison signal builder (NO execution)
# ------------------------------------------------------------------
def build_semantic_comparison_request(file1: str, file2: str) -> Dict[str, Any]:
    """
    Build a structured semantic comparison REQUEST.
    This does NOT perform any computation.
    """

    return {
        "reasoning_type": "semantic_comparison",
        "inputs": {
            "file1": file1,
            "file2": file2,
        },
        "constraints": {
            "no_execution": True,
            "requires_orchestrator": True,
        },
        "expected_outputs": [
            "similarity_assessment",
            "key_differences",
            "shared_topics",
            "high_level_summary",
        ],
    }


# ------------------------------------------------------------------
# Task router — SIGNAL ONLY
# ------------------------------------------------------------------
def route_reasoning(intent: str, entities: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Determines which reasoning REQUEST to emit based on intent.
    Returns (route_name, reasoning_request).
    """

    intent_lower = (intent or "").lower()
    e = entities or {}

    # --- Detect multi-file comparison intent ---
    if intent_lower in {"compare", "contrast", "difference", "similarity"} \
       or ("file2" in e and "filename" in e):

        f1 = e.get("filename")
        f2 = e.get("file2")

        if f1 and f2:
            return "semantic_comparison", build_semantic_comparison_request(f1, f2)

        # Missing artifacts → orchestrator follow-up path
        return "waiting_for_artifacts", {
            "reason": "Two documents are required for semantic comparison.",
            "required_inputs": ["filename", "file2"],
        }

    # --- Default: no semantic route ---
    return "no_route", {
        "reason": f"No semantic route matched intent '{intent_lower}'."
    }


# ------------------------------------------------------------------
# NO local execution hooks allowed in Phase-38
# ------------------------------------------------------------------
if __name__ == "__main__":
    raise RuntimeError(
        "Phase-38 violation: semantic_router.py is SIGNAL-ONLY "
        "and must not be executed directly."
    )
