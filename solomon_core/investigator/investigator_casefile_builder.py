# ------------------------------------------------------------------
# FILE: investigator_casefile_builder.py
# DIRECTORY: solomon_core/investigator/
# ------------------------------------------------------------------
# Investigator CaseFile Builder
#
# PURPOSE
#   Perform deterministic construction of the immutable Investigator
#   CaseFile from fully prepared observational inputs.
#
# CONTRACT
#   - Construction only
#   - No inference
#   - No routing
#   - No FIS execution
#   - No evidence generation
#   - No silent analytical defaults
# ------------------------------------------------------------------

from typing import Dict, List, Optional

from solomon_core.investigator.investigator_casefile_types import (
    AmbiguityItem,
    CaseFile,
    ChecklistResult,
    ConfidenceDeltas,
    ConfidenceValues,
    EvidenceInputs,
    EvidenceItem,
    Hypotheses,
    KnowledgeLayerObservations,
    NegativeEvidenceItem,
    ProposedIntent,
    QualitySignals,
    RequestContext,
    RiskIndicator,
)


def build_casefile(
    *,
    request_context: RequestContext,
    evidence_inputs: EvidenceInputs,
    knowledge_layer_observations: KnowledgeLayerObservations,
    checklist_results: Dict[str, ChecklistResult],
    positive_evidence: List[EvidenceItem],
    negative_evidence: List[NegativeEvidenceItem],
    ambiguities: List[AmbiguityItem],
    hypotheses: Hypotheses,
    confidence_values: ConfidenceValues,
    risk_indicators: List[RiskIndicator],
    proposed_intent: ProposedIntent,
    recommended_next_step: Optional[str],
    timestamp_emitted: str,
    prior_casefile: Optional[CaseFile] = None,
    confidence_deltas: Optional[ConfidenceDeltas] = None,
    quality_signals: Optional[QualitySignals] = None,
) -> CaseFile:
    """
    Build one immutable CaseFile from fully bound Investigator observations.

    Knowledge Layer observations must be created before this boundary. The
    builder does not derive, infer, normalize, classify, or select anything.
    """

    if request_context is None:
        raise RuntimeError(
            "CaseFile construction violation: request_context is required."
        )

    if evidence_inputs is None:
        raise RuntimeError(
            "CaseFile construction violation: evidence_inputs is required."
        )

    if knowledge_layer_observations is None:
        raise RuntimeError(
            "CaseFile construction violation: "
            "knowledge_layer_observations are required."
        )

    raw_user_input = evidence_inputs.raw_user_input

    if not isinstance(raw_user_input, str):
        raise RuntimeError(
            "CaseFile construction violation: raw_user_input must be a string."
        )

    return CaseFile(
        casefile_version="1.1",
        case_id=request_context.case_id,
        user_id=request_context.user_id,
        archetype_id=request_context.archetype_id,
        timestamp_created=request_context.timestamp,
        timestamp_emitted=timestamp_emitted,
        raw_user_input=raw_user_input,
        knowledge_layer_observations=knowledge_layer_observations,
        checklist_results=checklist_results,
        positive_evidence=positive_evidence,
        negative_evidence=negative_evidence,
        ambiguities=ambiguities,
        hypotheses=hypotheses,
        confidence_values=confidence_values,
        risk_indicators=risk_indicators,
        proposed_intent=proposed_intent,
        recommended_next_step=recommended_next_step,
        session_id=getattr(
            request_context,
            "session_id",
            None,
        ),
        request_id=getattr(
            request_context,
            "request_id",
            None,
        ),
        prior_case_id=(
            prior_casefile.case_id
            if prior_casefile
            else None
        ),
        confidence_deltas=confidence_deltas,
        quality_signals=quality_signals,
        intent_snapshot=None,
    )