# solomon_core/ml/ml_hud_contract.py
# ---------------------------------------------------------------------------
# Phase 45 — ML HUD Advisory Contract
# ---------------------------------------------------------------------------
# PURPOSE:
#   Define the canonical, non-authoritative interface for the ML HUD layer.
#
#   The ML HUD provides *situational awareness only*:
#     • Signal extraction
#     • Ranking and prioritization
#     • Ambiguity and confidence signaling
#
#   It MUST NOT:
#     • Make decisions
#     • Route execution
#     • Author packets
#     • Enforce policy
#     • Mask failure
#
# ARCHITECTURAL ROLE:
#   • Level 1B — Interpretation Plane (LLC-like)
#   • Side-band to execution
#   • Advisory only
#   • Removable / disableable
#
# AUTHORITY:
#   • ZERO authority
#   • Orchestrator remains sole decision-maker
#
# GUARANTEES:
#   • Deterministic system behavior when HUD is disabled
#   • HUD failure does not affect correctness
#   • HUD output is optional and ignorable
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Advisory Signal Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HUDSignal:
    """
    Represents a single advisory signal emitted by the ML HUD.

    This is a READ-ONLY, NON-AUTHORITATIVE artifact.
    """
    signal_type: str                 # e.g. "similarity", "ambiguity", "ranking"
    description: str                 # Human-readable explanation
    confidence: Optional[float] = None  # 0.0–1.0 if applicable
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# HUD Output Envelope
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MLHUDOutput:
    """
    Canonical output of the ML HUD layer.

    All fields are OPTIONAL.
    Empty output is a valid and expected state.
    """
    signals: List[HUDSignal] = field(default_factory=list)

    # Ranked candidate interpretations or hints (advisory only)
    ranked_candidates: List[str] = field(default_factory=list)

    # Explicit ambiguity flags (never decisions)
    ambiguity_flags: List[str] = field(default_factory=list)

    # Informational confidence estimates (non-binding)
    confidence_estimates: Dict[str, float] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# HUD Input Context
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MLHUDContext:
    """
    Input context provided to the ML HUD.

    The HUD may OBSERVE this context, but MUST NOT mutate it.
    """
    user_input: Optional[str] = None
    active_documents: List[str] = field(default_factory=list)
    extracted_text: Optional[str] = None
    execution_metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# HUD Contract Interface
# ---------------------------------------------------------------------------

class MLHUDInterface:
    """
    Formal interface for ML HUD implementations.

    Implementations MUST:
      • Be side-effect free
      • Be safe to disable
      • Return MLHUDOutput only
      • Never raise unhandled exceptions
    """

    def evaluate(self, context: MLHUDContext) -> MLHUDOutput:
        """
        Produce advisory signals based on the provided context.

        FAILURE BEHAVIOR:
          • MUST return an empty MLHUDOutput on error
          • MUST NOT throw
          • MUST NOT affect orchestrator behavior
        """
        raise NotImplementedError


__all__ = [
    "HUDSignal",
    "MLHUDOutput",
    "MLHUDContext",
    "MLHUDInterface",
]
