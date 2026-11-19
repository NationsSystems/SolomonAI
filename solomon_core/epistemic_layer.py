# solomon_core/epistemic_layer.py
# ------------------------------------------------------------
# Phase 38B — Epistemic Layer (Signal-Only, FSM-Compatible)
#
# PURPOSE:
#   • Compute epistemic state strictly from vectors
#   • Emit ADVISORY signals only (no flow control)
#   • Provide a FLAT epistemic_vector for FSM reduction
#
# Phase 39:
#   • NO semantic changes
#   • NO authority changes
#   • Logging aligned to Focused Observability Mode (FOM-39)
#
# GUARANTEES:
#   • No execution authority
#   • No LLM dependency
#   • Deterministic, inspectable
# ------------------------------------------------------------

from enum import Enum, auto
from typing import Dict, Any, Optional, List

from solomon_core.logger import get_logger

logger = get_logger("Solomon.epistemic_layer")

# ---------------------------------------------------------------------------
# Phase-38 Authority Declarations (HARD)
# ---------------------------------------------------------------------------
EXECUTION_AUTHORITY = False
SIGNAL_ONLY_MODULE = True
AUTHORITY_SCOPE = "signal_only"


# ------------------------------------------------------------
# Epistemic confidence state (SIGNAL ONLY)
# ------------------------------------------------------------
class EpistemicState(Enum):
    CONFIDENT = auto()
    PARTIALLY_CONFIDENT = auto()
    UNCERTAIN = auto()
    BLOCKED = auto()


# ------------------------------------------------------------
# Failure classification (SIGNAL ONLY)
# ------------------------------------------------------------
class EpistemicFailureType(Enum):
    INPUT_FAILURE = "input_failure"
    EXECUTION_FAILURE = "execution_failure"
    GROUNDING_FAILURE = "grounding_failure"


# ------------------------------------------------------------
# Decision object (SIGNAL CONTAINER)
# ------------------------------------------------------------
class EpistemicDecision:
    def __init__(
        self,
        *,
        state: EpistemicState,
        failure_type: Optional[EpistemicFailureType] = None,
        uncertainty_reasons: Optional[List[str]] = None,
        followup_required: bool = False,
        fatal_error: bool = False,
    ):
        # Signals only (non-authoritative)
        self.state = state
        self.failure_type = failure_type
        self.uncertainty_reasons = uncertainty_reasons or []
        self.followup_required = followup_required
        self.fatal_error = fatal_error

    # --------------------------------------------------------
    # Phase-38B FSM ADAPTER (CRITICAL)
    # --------------------------------------------------------
    def to_fsm_vector(self) -> Dict[str, Any]:
        """
        Return a FLAT epistemic vector compatible with
        execution_state_resolver.resolve_execution_state().

        Required keys (FSM contract):
            • clarification_required: bool
            • fatal_error: bool
        """
        return {
            "clarification_required": bool(self.followup_required),
            "fatal_error": bool(self.fatal_error),
        }


# ------------------------------------------------------------
# Epistemic Layer
# ------------------------------------------------------------
class EpistemicLayer:
    def __init__(self):
        logger.info("[Phase39][EPISTEMIC_INIT] EpistemicLayer initialized")

    def evaluate(
        self,
        task_type: Any,
        evidence: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> EpistemicDecision:
        """
        Compute epistemic signals ONLY.
        NO flow control, NO execution authority.
        """

        context = context or {}

        # Observable facts only
        execution_ok = bool(evidence.get("execution_ok"))
        grounded = bool(evidence.get("grounded"))
        execution_error = bool(evidence.get("execution_error"))
        missing_required_inputs = bool(evidence.get("missing_required_inputs"))
        task_present = bool(evidence.get("task_present"))

        reasons: List[str] = []
        failure_type: Optional[EpistemicFailureType] = None
        followup_required = False
        fatal_error = False

        # --------------------------------------------------
        # Deterministic signal classification (NO inference)
        # --------------------------------------------------
        if not task_present:
            reasons.append("task_absent")
            failure_type = EpistemicFailureType.INPUT_FAILURE
            followup_required = True
            state = EpistemicState.BLOCKED

        elif missing_required_inputs:
            reasons.append("missing_required_inputs")
            failure_type = EpistemicFailureType.INPUT_FAILURE
            followup_required = True
            state = EpistemicState.BLOCKED

        elif execution_error:
            reasons.append("execution_error")
            failure_type = EpistemicFailureType.EXECUTION_FAILURE
            fatal_error = True
            state = EpistemicState.UNCERTAIN

        elif execution_ok and not grounded:
            reasons.append("insufficient_grounding")
            failure_type = EpistemicFailureType.GROUNDING_FAILURE
            followup_required = True
            state = EpistemicState.PARTIALLY_CONFIDENT

        elif execution_ok and grounded:
            reasons.append("execution_and_grounding_ok")
            state = EpistemicState.CONFIDENT

        else:
            reasons.append("insufficient_epistemic_signal")
            state = EpistemicState.UNCERTAIN

        decision = EpistemicDecision(
            state=state,
            failure_type=failure_type,
            uncertainty_reasons=reasons,
            followup_required=followup_required,
            fatal_error=fatal_error,
        )

        # Phase 39: decision-level visibility only
        logger.info(
            "[Phase39][EPISTEMIC_DECISION]",
            extra={
                "state": decision.state.name,
                "followup_required": decision.followup_required,
                "fatal_error": decision.fatal_error,
                "reasons": decision.uncertainty_reasons,
            },
        )

        return decision


__all__ = [
    "EpistemicLayer",
    "EpistemicDecision",
    "EpistemicState",
    "EpistemicFailureType",
]
