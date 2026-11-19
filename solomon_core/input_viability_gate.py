# solomon_core/input_viability_gate.py
# ------------------------------------------------------------
# PURPOSE:
#   Input Viability Gate (IVG) — signal-only, non-authoritative.
#
# GUARANTEES:
#   • HARD BYPASS MAINTAINED
#   • NO semantic judgment
#   • NO clarification authority
#   • NO rejection authority
#   • NO state / code emission
#
# ROLE:
#   • Emit viability OBSERVATION VECTOR ONLY
#   • Preserve deterministic call-chain integrity
#   • Prevent downstream semantic inference
#   • Orchestrator remains sole authority
#
# LOGGING:
#   • Subsystem-based tags only
#   • No phase labels in log messages
# ------------------------------------------------------------

from typing import Dict
from solomon_core.logger import get_logger

logger = get_logger("solomon_core.input_viability_gate")


# ------------------------------------------------------------
# Main IVG entrypoint (VECTOR-ONLY BYPASS)
# ------------------------------------------------------------
def evaluate_input_viability(text: str) -> Dict[str, object]:
    """
    Invariants:

    • IVG performs NO semantic judgment
    • IVG emits NO user-facing message
    • IVG emits NO response_mode
    • IVG emits NO failure_type
    • IVG emits NO orchestrator state or code
    • Output is a pure viability observation vector

    Authority remains exclusively with the orchestrator.
    """

    # Single, low-noise observability signal
    logger.info(
        "Input viability bypassed",
        extra={"evaluated": False, "bypassed": True},
    )

    # ------------------------------------------------------------------
    # Viability Observation Vector (NON-AUTHORITATIVE)
    # ------------------------------------------------------------------
    viability_vector = {
        "evaluated": False,
        "bypassed": True,
        "has_issues": False,
    }

    return {
        "viability_vector": viability_vector
    }


__all__ = ["evaluate_input_viability"]
