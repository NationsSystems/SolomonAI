# ------------------------------------------------------------------
# FILE: investigator_casefile_types.py
# DIRECTORY: solomon_core/investigator/
# ------------------------------------------------------------------
# Investigator CaseFile & Input Type Definitions (Design-Binding)
#
# Location:
#   solomon_core/investigator/investigator_casefile_types.py
#
# Purpose:
#   Defines the canonical data contracts consumed and emitted by the
#   Investigator module, including RequestContext, EvidenceInputs,
#   Knowledge Layer observations, and the MVI CaseFile artifact.
#
# Governing Documents:
#   - Investigator Interface Specification v1.0
#   - Investigator Module API v1.0
#   - MVI CaseFile Specification v1.0
#
# Notes:
#   - Structure only (no behavior)
#   - No silent analytical defaults
#   - Absence must be explicit
#   - Artifacts are immutable post-emission
#   - Knowledge Layer output is observational and has no routing authority
# ------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional


RequirementState = Literal[
    "required",
    "not_required",
    "undetermined",
]

AmbiguityState = Literal[
    "none",
    "limited",
    "material",
]

SufficiencyState = Literal[
    "sufficient",
    "insufficient",
    "undetermined",
]

SkillApplicabilityState = Literal[
    "applicable",
    "not_applicable",
    "undetermined",
]


# ------------------------------------------------------------------
# Request Context
# ------------------------------------------------------------------

@dataclass(frozen=True)
class RequestContext:
    case_id: str
    user_id: int | str
    archetype_id: str
    timestamp: str
    session_id: Optional[str] = None
    request_id: Optional[str] = None


# ------------------------------------------------------------------
# Evidence Inputs
# ------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceInputs:
    raw_user_input: str
    attachments: List[Dict[str, Any]]
    conversation_memory: Optional[Dict[str, Any]]
    environmental_ctx: Dict[str, Any]
    historical_patterns: Optional[Dict[str, Any]]
    hflo_signals: Optional[Dict[str, Any]] = None


# ------------------------------------------------------------------
# CaseFile Substructures
# ------------------------------------------------------------------

@dataclass(frozen=True)
class ChecklistResult:
    value: int  # 0 or 1
    source_refs: Optional[List[str]] = None


@dataclass(frozen=True)
class EvidenceItem:
    ref_id: str
    kind: str
    description: str
    source: str
    confidence: Optional[float] = None


@dataclass(frozen=True)
class StructuredEvidenceItem(EvidenceItem):
    """Evidence item carrying durable, source-authored provenance metadata."""

    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NegativeEvidenceItem:
    indicator_id: str
    description: str
    expected_by: str


@dataclass(frozen=True)
class AmbiguityItem:
    ambiguity_id: str
    description: str
    scope: str


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    intent_label: str
    narrative: str
    supports: List[str]
    contradicts: List[str]
    confidence: float


@dataclass(frozen=True)
class Hypotheses:
    primary: Hypothesis
    alternates: List[Hypothesis]


@dataclass(frozen=True)
class ConfidenceValues:
    primary_confidence: float


@dataclass(frozen=True)
class ConfidenceDeltas:
    delta: float
    cause_refs: List[str]


@dataclass(frozen=True)
class RiskIndicator:
    risk_id: str
    description: str
    severity: str
    drivers: List[str]


@dataclass(frozen=True)
class ProposedIntent:
    summary: str
    rationale: str


@dataclass(frozen=True)
class QualitySignals:
    data_sparsity: str
    novelty: str


# ------------------------------------------------------------------
# Knowledge Layer Observations
# ------------------------------------------------------------------

@dataclass(frozen=True)
class ArtifactInventory:
    """
    Deterministic inventory of artifacts supplied with the request.

    Artifact presence is evidence only. It does not imply that document
    analysis is required and cannot select an execution lane.
    """

    total_count: int
    document_count: int
    attachment_count: int
    resolved_path_count: int
    artifacts: List[Dict[str, Any]]


@dataclass(frozen=True)
class RequirementObservation:
    """
    Observed requirement state supported by explicit evidence references.

    The state remains observational. The Orchestrator alone converts the
    observation into an execution decision.
    """

    state: RequirementState
    evidence_refs: List[str]
    negative_evidence_refs: List[str]
    strength: float


@dataclass(frozen=True)
class SufficiencyObservation:
    """
    Deterministic ambiguity and request-sufficiency observations.

    The Orchestrator alone determines whether these observations require
    execution through the Clarification Lane.
    """

    ambiguity_state: AmbiguityState
    sufficiency_state: SufficiencyState
    missing_information: List[str]
    evidence_refs: List[str]
    strength: float


@dataclass(frozen=True)
class SkillLaneObservation:
    """
    Observed applicability of one registered Skill Lane.

    Applicability is not selection. Skill Lane selection remains exclusively
    within the Orchestrator.
    """

    skill_id: str
    applicability: SkillApplicabilityState
    evidence_refs: List[str]
    negative_evidence_refs: List[str]
    strength: float


@dataclass(frozen=True)
class KnowledgeLayerObservations:
    """
    Canonical deterministic observations emitted from inside the Investigator.

    These observations provide the complete evidence contract required by the
    Orchestrator while preserving the Investigator's non-authoritative role.
    """

    raw_user_request: str
    artifact_inventory: ArtifactInventory
    semantic_domains: List[str]
    explicit_requested_operation: Optional[str]
    document_analysis_requirement: RequirementObservation
    external_information_requirement: RequirementObservation
    sufficiency: SufficiencyObservation
    skill_lanes: List[SkillLaneObservation]
    positive_evidence_refs: List[str]
    negative_evidence_refs: List[str]
    overall_evidence_strength: float


# ------------------------------------------------------------------
# CaseFile (MVI)
# ------------------------------------------------------------------

@dataclass(frozen=True)
class CaseFile:
    # -------------------------
    # Core identity & version
    # -------------------------
    casefile_version: str
    case_id: str
    user_id: int | str
    archetype_id: str
    timestamp_created: str
    timestamp_emitted: str

    # -------------------------
    # Required source state
    # -------------------------
    raw_user_input: str
    knowledge_layer_observations: KnowledgeLayerObservations

    # -------------------------
    # Required analytical state
    # -------------------------
    checklist_results: Dict[str, ChecklistResult]
    positive_evidence: List[EvidenceItem]
    negative_evidence: List[NegativeEvidenceItem]
    ambiguities: List[AmbiguityItem]
    hypotheses: Hypotheses
    confidence_values: ConfidenceValues
    risk_indicators: List[RiskIndicator]
    proposed_intent: ProposedIntent
    recommended_next_step: Optional[str]

    # -------------------------
    # Optional / versioned
    # -------------------------
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    prior_case_id: Optional[str] = None
    confidence_deltas: Optional[ConfidenceDeltas] = None
    quality_signals: Optional[QualitySignals] = None
    intent_snapshot: Optional[Dict[str, Any]] = None