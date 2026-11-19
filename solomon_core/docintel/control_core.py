"""
File: solomon_core/docintel/control_core.py

Solomon AI — DocIntel Control Core
Phase: 53 — Axial Control Genesis
Status: CONTROL-ONLY · FAIL-CLOSED

This module defines the DocIntel Control Core as a strictly non-authoritative
control surface. It enforces Orchestrator authority, governs Certified Analysis
Primitive eligibility, and implements inhibition and observability semantics.

This file intentionally contains:
- NO intelligence
- NO planning
- NO inference
- NO execution logic
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional, Union
from datetime import datetime, timezone

from solomon_core.docintel.certified_primitive_registry import (
    CertifiedPrimitiveRegistry,
    CertificationViolation,
    CertifiedPrimitiveRecord,
)


# ---------------------------------------------------------------------------
# Control Signals
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ControlRefusal:
    """Explicit refusal due to invalid request structure or missing authority."""
    reason: str
    details: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ControlInhibition:
    """Terminal inhibition due to policy, evidence, or scope violation."""
    cause: str
    details: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class ControlAcceptance:
    """
    Structural acceptance indicating all control gates have passed.

    NOTE:
    Acceptance does NOT imply execution.
    Acceptance may still be followed by downstream inhibition.
    """
    authorization_id: str
    timestamp_utc: str


ControlResult = Union[ControlAcceptance, ControlRefusal, ControlInhibition]


# ---------------------------------------------------------------------------
# DocIntel Control Core
# ---------------------------------------------------------------------------

class DocIntelControlCore:
    """
    Control-only governance surface for DocIntel.

    HARD CONSTRAINTS:
    - No intent interpretation
    - No task decomposition
    - No workflow sequencing
    - No primitive execution
    - No fallback or retry logic
    - Fail-closed by default
    """

    def __init__(self, *, registry: CertifiedPrimitiveRegistry) -> None:
        """
        Constructed with an explicit CertifiedPrimitiveRegistry.

        Registry is treated as read-only.
        """
        self._registry = registry

    # ---------------------------------------------------------------------
    # Public Interface
    # ---------------------------------------------------------------------

    def request_execution(
        self,
        *,
        orchestrator_authorization: Optional[str],
        primitive_name: str,
        primitive_version: str,
        inputs: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> ControlResult:
        """
        Entry point for all DocIntel primitive execution requests.

        Performs ONLY:
        - authority presence verification
        - structural request validation
        - certification enforcement
        - evidence requirement enforcement
        - explicit refusal or inhibition

        Does NOT:
        - validate authorization content
        - inspect evidence contents
        - execute primitives
        - infer intent
        """

        # ---- Authority Gate (Refusal) ----
        if not orchestrator_authorization:
            return ControlRefusal(
                reason="missing_orchestrator_authorization",
                details={
                    "primitive": f"{primitive_name}@{primitive_version}"
                },
            )

        # ---- Structural Identity Gate (Refusal) ----
        if not primitive_name or not primitive_version:
            return ControlRefusal(
                reason="invalid_primitive_identity",
                details={
                    "primitive_name": primitive_name,
                    "primitive_version": primitive_version,
                },
            )

        # ---- Certification Gate (Inhibition) ----
        try:
            record: CertifiedPrimitiveRecord = self._registry.assert_certified(
                name=primitive_name,
                version=primitive_version,
            )
        except CertificationViolation as exc:
            return ControlInhibition(
                cause="primitive_not_certified",
                details={
                    "primitive": f"{primitive_name}@{primitive_version}",
                    "reason": str(exc),
                },
            )

        # ---- Evidence Presence Gate (Inhibition) ----
        if not evidence:
            return ControlInhibition(
                cause="missing_evidence",
                details={
                    "primitive": f"{primitive_name}@{primitive_version}"
                },
            )

        # ---- Evidence Requirement Enforcement (Inhibition) ----
        required_sources = record.evidence.required_sources
        missing_sources = [
            src for src in required_sources if src not in evidence
        ]

        if missing_sources:
            return ControlInhibition(
                cause="missing_required_evidence_sources",
                details={
                    "primitive": f"{primitive_name}@{primitive_version}",
                    "missing_sources": missing_sources,
                },
            )

        # ---- Structural Acceptance (No Execution) ----
        return ControlAcceptance(
            authorization_id=orchestrator_authorization,
            timestamp_utc=datetime.now(timezone.utc).isoformat(),
        )

    # ---------------------------------------------------------------------
    # Observability (Control-Only)
    # ---------------------------------------------------------------------

    def emit_observability_record(
        self,
        *,
        result: ControlResult,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Emit a structured observability record.

        NOTE:
        - No logging side effects.
        - Caller owns persistence.
        """

        return {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "result_type": type(result).__name__,
            "result": result,
            "context": context,
        }

    # ---------------------------------------------------------------------
    # Explicit Non-Capabilities
    # ---------------------------------------------------------------------

    def __getattr__(self, name: str):
        """Any attempt to access undeclared behavior is an explicit violation."""
        raise AttributeError(
            f"DocIntelControlCore has no capability '{name}'. "
            "Control Core is control-only."
        )
