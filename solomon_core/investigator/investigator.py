# ------------------------------------------------------------------
# FILE: investigator.py
# DIRECTORY: solomon_core/investigator/
# ------------------------------------------------------------------
# Constitutional Investigator
#
# PURPOSE
#   Observe supplied request evidence, invoke the deterministic Knowledge
#   Layer, construct an immutable CaseFile, and persist that artifact.
#
# CONTRACT
#   - Witness and evidence producer only
#   - No execution-lane selection
#   - No workflow authorization
#   - No LLM or embedding-based routing
#   - No recommendations or execution commands
# ------------------------------------------------------------------

from datetime import datetime, timezone
from typing import Dict, Optional

from solomon_core.investigator.investigator_archetype_checklists import (
    get_checklist_for_archetype,
)
from solomon_core.investigator.investigator_casefile_builder import (
    build_casefile,
)
from solomon_core.investigator.investigator_casefile_persistence import (
    persist_casefile,
)
from solomon_core.investigator.investigator_casefile_types import (
    CaseFile,
    ChecklistResult,
    ConfidenceValues,
    EvidenceInputs,
    Hypothesis,
    Hypotheses,
    NegativeEvidenceItem,
    ProposedIntent,
    QualitySignals,
    RequestContext,
    RiskIndicator,
    SufficiencyState,
)
from solomon_core.investigator.investigator_knowledge_observations import (
    build_knowledge_layer_observations,
)


def _get_archetype_indicator_ids(archetype_id: str) -> list[str]:
    """
    Return the configured archetype checklist without treating absence as error.
    """

    try:
        indicator_ids = get_checklist_for_archetype(archetype_id)
    except KeyError:
        return []

    return [
        str(indicator_id).strip()
        for indicator_id in indicator_ids
        if str(indicator_id or "").strip()
    ]


def _build_checklist_results(
    indicator_ids: list[str],
) -> Dict[str, ChecklistResult]:
    """
    Record unobserved archetype indicators without inferring their presence.
    """

    return {
        indicator_id: ChecklistResult(
            value=0,
            source_refs=[],
        )
        for indicator_id in indicator_ids
    }


def _build_archetype_negative_evidence(
    indicator_ids: list[str],
) -> list[NegativeEvidenceItem]:
    """
    Record explicit absence for configured archetype indicators.
    """

    return [
        NegativeEvidenceItem(
            indicator_id=indicator_id,
            description="Indicator not observed in the supplied evidence.",
            expected_by="archetype",
        )
        for indicator_id in indicator_ids
    ]


def _build_legacy_hypotheses(
    *,
    archetype_id: str,
    explicit_operation: Optional[str],
    overall_evidence_strength: float,
) -> Hypotheses:
    """
    Populate the legacy hypothesis structure as an evidence summary only.

    The Orchestrator must not use this object as a routing decision.
    """

    if explicit_operation:
        intent_label = explicit_operation
        narrative = (
            f"Explicit requested operation observed: {explicit_operation}."
        )
        supports = ["observation:explicit_requested_operation"]
        confidence = overall_evidence_strength
    else:
        intent_label = archetype_id or "undetermined"
        narrative = "No explicit requested operation was observed."
        supports = []
        confidence = 0.0

    return Hypotheses(
        primary=Hypothesis(
            hypothesis_id="observed_request_state",
            intent_label=intent_label,
            narrative=narrative,
            supports=supports,
            contradicts=[],
            confidence=confidence,
        ),
        alternates=[],
    )


def _build_insufficiency_risk_indicators(
    *,
    sufficiency_state: SufficiencyState,
    missing_information: list[str],
    evidence_refs: list[str],
) -> list[RiskIndicator]:
    """
    Express observed material insufficiency without selecting clarification.
    """

    if sufficiency_state != "insufficient":
        return []

    description = "The request is missing information required for execution."

    if missing_information:
        description = (
            "The request is missing required information: "
            + ", ".join(missing_information)
            + "."
        )

    return [
        RiskIndicator(
            risk_id="request_insufficient",
            description=description,
            severity="medium",
            drivers=list(evidence_refs),
        )
    ]


def _build_proposed_intent(
    explicit_operation: Optional[str],
) -> ProposedIntent:
    """
    Preserve the legacy ProposedIntent field as a non-authoritative observation.
    """

    if explicit_operation:
        return ProposedIntent(
            summary=f"Observed requested operation: {explicit_operation}.",
            rationale=(
                "Derived from explicit request or structured transport evidence. "
                "No execution lane was selected."
            ),
        )

    return ProposedIntent(
        summary="No explicit requested operation observed.",
        rationale=(
            "The Investigator recorded supplied evidence without selecting "
            "an execution lane."
        ),
    )


def _build_quality_signals(
    *,
    sufficiency_state: SufficiencyState,
    explicit_operation: Optional[str],
) -> QualitySignals:
    """
    Record deterministic evidence quality without selecting execution behavior.
    """

    if sufficiency_state == "insufficient":
        data_sparsity = "high"
    elif not explicit_operation:
        data_sparsity = "moderate"
    else:
        data_sparsity = "low"

    return QualitySignals(
        data_sparsity=data_sparsity,
        novelty="not_assessed",
    )


def investigate(
    *,
    request_context: RequestContext,
    evidence_inputs: EvidenceInputs,
    prior_casefile: Optional[CaseFile] = None,
) -> CaseFile:
    """
    Observe request evidence and emit one immutable constitutional CaseFile.
    """

    if request_context is None:
        raise RuntimeError(
            "Investigator invocation violation: request_context must be provided."
        )

    if evidence_inputs is None:
        raise RuntimeError(
            "Investigator invocation violation: evidence_inputs must be provided."
        )

    timestamp_emitted = datetime.now(timezone.utc).isoformat()
    indicator_ids = _get_archetype_indicator_ids(
        request_context.archetype_id
    )
    checklist_results = _build_checklist_results(
        indicator_ids
    )

    observation_result = build_knowledge_layer_observations(
        raw_user_request=evidence_inputs.raw_user_input,
        attachments=evidence_inputs.attachments,
        environmental_ctx=evidence_inputs.environmental_ctx,
        conversation_memory=evidence_inputs.conversation_memory,
    )
    observations = observation_result.observations

    positive_evidence = list(
        observation_result.positive_evidence
    )
    negative_evidence = [
        *observation_result.negative_evidence,
        *_build_archetype_negative_evidence(
            indicator_ids
        ),
    ]
    ambiguities = list(
        observation_result.ambiguities
    )

    hypotheses = _build_legacy_hypotheses(
        archetype_id=request_context.archetype_id,
        explicit_operation=(
            observations.explicit_requested_operation
        ),
        overall_evidence_strength=(
            observations.overall_evidence_strength
        ),
    )
    confidence_values = ConfidenceValues(
        primary_confidence=(
            hypotheses.primary.confidence
        )
    )
    risk_indicators = _build_insufficiency_risk_indicators(
        sufficiency_state=(
            observations.sufficiency.sufficiency_state
        ),
        missing_information=(
            observations.sufficiency.missing_information
        ),
        evidence_refs=(
            observations.sufficiency.evidence_refs
        ),
    )
    proposed_intent = _build_proposed_intent(
        observations.explicit_requested_operation
    )
    quality_signals = _build_quality_signals(
        sufficiency_state=(
            observations.sufficiency.sufficiency_state
        ),
        explicit_operation=(
            observations.explicit_requested_operation
        ),
    )

    casefile = build_casefile(
        request_context=request_context,
        evidence_inputs=evidence_inputs,
        knowledge_layer_observations=observations,
        checklist_results=checklist_results,
        positive_evidence=positive_evidence,
        negative_evidence=negative_evidence,
        ambiguities=ambiguities,
        hypotheses=hypotheses,
        confidence_values=confidence_values,
        risk_indicators=risk_indicators,
        proposed_intent=proposed_intent,
        recommended_next_step=None,
        timestamp_emitted=timestamp_emitted,
        prior_casefile=prior_casefile,
        quality_signals=quality_signals,
    )

    if casefile is None:
        raise RuntimeError(
            "Investigator failure: CaseFile construction returned None."
        )

    persist_casefile(casefile=casefile)

    return casefile