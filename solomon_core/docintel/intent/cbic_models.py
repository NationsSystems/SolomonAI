"""
cbic_models.py
Constraint-Bound Intent Candidate (CBIC)
Phase 55 — Explicit Intent Materialization

AUTHORITATIVE NOTES
-------------------
• CBIC is a non-authoritative, pre-intent artifact
• CBIC MUST NOT trigger execution
• CBIC MUST be deterministic, auditable, immutable
• CBIC MUST be the sole output of mediation
• CBIC MUST NEVER reach Orchestrator or ExecutionGate
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class CBICSufficiencyState(str, Enum):
    """Authoritative CBIC sufficiency states."""

    INSUFFICIENT = "INSUFFICIENT"   # Missing required constraints
    SALVAGEABLE = "SALVAGEABLE"     # Operation clear, config incomplete
    SUFFICIENT = "SUFFICIENT"       # All constraints resolved


class ConstraintSource(str, Enum):
    """Where a constraint value originated."""

    USER_PROMPT = "user_prompt"
    UI_SELECTION = "ui_selection"


# ---------------------------------------------------------------------------
# Artifact Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DocumentArtifact:
    """Represents an uploaded document under consideration."""

    document_id: str
    document_type: str
    provenance: str

    # ------------------------------------------------------------------
    # Phase 74 — Admissible Fact Record (read-only witness)
    # ------------------------------------------------------------------
    afr: Optional[Dict] = None


@dataclass(frozen=True)
class PromptArtifact:
    """Raw user prompt (untrusted signal, never authoritative)."""

    raw_text: str


# ---------------------------------------------------------------------------
# Operation & Constraint Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CandidateOperation:
    """Non-authoritative operation signal extracted from prompt or UI."""

    name: Optional[str]
    source: Optional[ConstraintSource]


@dataclass(frozen=True)
class ConstraintResolution:
    """Resolved and unresolved constraints."""

    resolved: Dict[str, object] = field(default_factory=dict)
    unresolved: Dict[str, List[object]] = field(default_factory=dict)


@dataclass(frozen=True)
class EligibilityProfile:
    """Eligible and ineligible operations for current artifacts."""

    eligible_operations: List[str] = field(default_factory=list)
    ineligible_operations: Dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Mediation Output Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MediationExplanation:
    """Human-readable mediation explanation."""

    summary: str
    blocking_reasons: List[str] = field(default_factory=list)
    clarification_requests: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class AuthorityAssertion:
    """Explicit lock preventing execution."""

    can_execute: bool = False
    reason: str = "CBIC is non-authoritative"


# ---------------------------------------------------------------------------
# CBIC Root Model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConstraintBoundIntentCandidate:
    """
    Constraint-Bound Intent Candidate (CBIC)

    This object MAY be inspected, logged, serialized, or rendered in UX.
    This object MUST NEVER authorize execution.
    """

    cbic_id: str
    created_at: datetime

    # Artifacts
    documents: List[DocumentArtifact]
    prompt: PromptArtifact

    # Non-authoritative operation signal
    candidate_operation: CandidateOperation

    # Constraints
    constraints: ConstraintResolution

    # Eligibility
    eligibility: EligibilityProfile

    # Sufficiency
    sufficiency_state: CBICSufficiencyState

    # Mediation output
    mediation: MediationExplanation

    # Authority lock (hard-coded)
    authority: AuthorityAssertion = field(default_factory=AuthorityAssertion)

    # -------------------------------------------------------------------
    # Safety Assertions
    # -------------------------------------------------------------------

    def assert_non_authoritative(self) -> None:
        """Fail fast if CBIC is ever marked executable."""
        if self.authority.can_execute:
            raise RuntimeError("CBIC must never be executable")

    def is_upgrade_eligible(self) -> bool:
        """Return True only if CBIC is fully sufficient."""
        return self.sufficiency_state == CBICSufficiencyState.SUFFICIENT


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

class CBICFactory:
    """Factory responsible for lawful CBIC construction."""

    @staticmethod
    def create(
        *,
        cbic_id: str,
        documents: List[DocumentArtifact],
        prompt_text: str,
        candidate_operation: Optional[str],
        operation_source: Optional[ConstraintSource],
        resolved_constraints: Dict[str, object],
        unresolved_constraints: Dict[str, List[object]],
        eligible_operations: List[str],
        ineligible_operations: Dict[str, str],
        sufficiency_state: CBICSufficiencyState,
        explanation: str,
        blocking_reasons: List[str],
        clarification_requests: List[str],
    ) -> ConstraintBoundIntentCandidate:
        """Create a CBIC while enforcing all invariants."""

        cbic = ConstraintBoundIntentCandidate(
            cbic_id=cbic_id,
            created_at=datetime.utcnow(),
            documents=documents,
            prompt=PromptArtifact(raw_text=prompt_text),
            candidate_operation=CandidateOperation(
                name=candidate_operation,
                source=operation_source,
            ),
            constraints=ConstraintResolution(
                resolved=resolved_constraints,
                unresolved=unresolved_constraints,
            ),
            eligibility=EligibilityProfile(
                eligible_operations=eligible_operations,
                ineligible_operations=ineligible_operations,
            ),
            sufficiency_state=sufficiency_state,
            mediation=MediationExplanation(
                summary=explanation,
                blocking_reasons=blocking_reasons,
                clarification_requests=clarification_requests,
            ),
        )

        cbic.assert_non_authoritative()
        return cbic
