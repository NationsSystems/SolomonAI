# ------------------------------------------------------------------
# FILE: orchestrator_runtime.py
# DIRECTORY: solomon_core/
# ------------------------------------------------------------------
# Constitutional Orchestrator Runtime
#
# PURPOSE
#   Evaluate the immutable Investigator CaseFile, select exactly one
#   execution lane, invoke that lane, and emit the resulting packet.
#
# AUTHORITY
#   - Sole execution-routing authority
#   - Deterministic CaseFile-driven lane selection
#   - Execution context supplies resources only
#
# CONSTRAINTS
#   - No LLM or embedding-based routing
#   - No attachment-presence routing
#   - No lane may redirect execution
#   - No CaseFile mutation
#   - Authorized-source RAG is chosen only from CaseFile evidence
# ------------------------------------------------------------------

from __future__ import annotations

import traceback
import uuid
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict

from solomon_core.context.state_store import (
    read_state,
    write_state,
)
from solomon_core.error_sentinel import record_error
from solomon_core.investigator.investigator_casefile_types import (
    EvidenceInputs,
    RequestContext,
)
from solomon_core.investigator.investigator_runtime import run_investigator
from solomon_core.intelligence_service.portable_compute_dispatch import (
    execute_llm_on_configured_compute,
)
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionFailure,
    LLMExecutionInput,
    LLMExecutionResult,
    LLMFailureReason,
    validate_execution_input,
)
from solomon_core.logger import get_logger
from solomon_core.observability.packet_observer import observe_packet
from solomon_core.orchestrator_docintel_flow import (
    run_bei_flow,
    run_docintel_flow,
)
from solomon_core.orchestrator_lanes.clarification_lane_handler import (
    run_clarification_lane,
)
from solomon_core.orchestrator_lanes.llm_lane_handler import run_llm_lane
from solomon_core.orchestrator_lanes.rag_lane_handler import run_rag_lane
from solomon_core.orchestrator_lanes.web_lane_handler import run_web_lane
from solomon_core.packets.packet_envelope import PacketEnvelope
from solomon_core.packets.packet_header import (
    PacketHeader,
    PacketHeaderMinimal,
)
from solomon_core.validation.llm_output_validator import (
    build_fallback_response,
    validate_llm_output,
)


logger = get_logger("orchestrator_runtime")


_GOVERNED_OPERATION_PREFIX = "governed_operation:"
_GOVERNED_OPERATION_HANDOFF_CONTRACT = "solomon_governed_operation_handoff_v1"


def _clean_governed_operation_component(value: Any) -> str:
    return str(value or "").strip().lower().replace(":", "_")


def _build_governed_operation_ref(
    *,
    operation_kind: str,
    operation_id: str,
    contract_version: str,
) -> str:
    clean_kind = _clean_governed_operation_component(operation_kind)
    clean_operation_id = _clean_governed_operation_component(operation_id)
    clean_contract_version = _clean_governed_operation_component(contract_version)

    if not clean_kind or not clean_operation_id or not clean_contract_version:
        raise ValueError(
            "Governed operation kind, id, and contract version are required."
        )

    return (
        f"{_GOVERNED_OPERATION_PREFIX}{clean_kind}:"
        f"{clean_operation_id}:v{clean_contract_version}"
    )


def _governed_operation_ref_from_casefile(casefile) -> str:
    observations = _casefile_observations(casefile)
    operation = str(
        getattr(
            observations,
            "explicit_requested_operation",
            "",
        )
        or ""
    ).strip().lower()

    if not operation.startswith(_GOVERNED_OPERATION_PREFIX):
        return ""

    return operation


def _governed_operation_failure(message: str) -> LLMExecutionResult:
    return LLMExecutionResult(
        failure=LLMExecutionFailure(
            reason=LLMFailureReason.INTERNAL_ERROR,
            message=str(message or "Governed operation execution failed."),
        )
    )


def execute_governed_llm_operation(
    input_packet: LLMExecutionInput,
    *,
    operation_kind: str,
    operation_id: str,
    contract_version: str,
    actor_id: int | str,
    request_id: str,
    trigger_type: str,
    source_resource: Dict[str, Any] | None = None,
    priority: Any = "P0",
    request_class: str | None = None,
) -> LLMExecutionResult:
    """Execute one bounded LLM operation only after Investigator/CaseFile routing.

    Known Actions and automatic intelligence use this fast path so they inherit
    the same V3 constitutional authority as Chat without forcing conversational
    intent discovery that the registered operation has already resolved.
    """

    governance_started = perf_counter()

    try:
        validate_execution_input(input_packet)
        operation_ref = _build_governed_operation_ref(
            operation_kind=operation_kind,
            operation_id=operation_id,
            contract_version=contract_version,
        )
    except Exception as exc:
        return _governed_operation_failure(
            f"Invalid governed operation contract: {type(exc).__name__}: {exc}"
        )

    clean_request_id = str(request_id or "unbound").strip() or "unbound"
    clean_trigger_type = (
        str(trigger_type or "unspecified").strip().lower() or "unspecified"
    )
    resource = dict(source_resource or {})
    attachment = None

    if resource:
        attachment = {
            "document_id": (
                resource.get("document_id")
                or resource.get("random_name")
                or resource.get("file_id")
                or ""
            ),
            "original_name": (
                resource.get("original_name")
                or resource.get("name")
                or "Governed resource"
            ),
            "extension": resource.get("extension") or "",
            "resolved_path": resource.get("path") or "",
            "selected_for_workflow": True,
            "authorization_status": "authorized",
            "handoff_contract": _GOVERNED_OPERATION_HANDOFF_CONTRACT,
        }

    case_id = str(uuid.uuid4())
    request_context = RequestContext(
        case_id=case_id,
        user_id=actor_id,
        archetype_id="governed_operation",
        timestamp=datetime.utcnow().isoformat(),
        session_id=f"governed_operation:{clean_trigger_type}",
        request_id=clean_request_id,
    )
    evidence_inputs = EvidenceInputs(
        raw_user_input=(
            "Execute registered governed operation "
            f"{operation_id} under contract {contract_version}."
        ),
        attachments=[attachment] if attachment else [],
        conversation_memory=None,
        environmental_ctx={
            "workflow_context": {
                "workflow_id": "governed_operation",
                "input_mode": "governed_operation",
                "workflow": {
                    "id": f"governed_operation:{operation_kind}",
                    "module": "governed_intelligence",
                    "requested_action": operation_ref,
                },
            },
            "workspace_context": {},
            "governed_operation": {
                "operation_ref": operation_ref,
                "operation_kind": str(operation_kind or "").strip(),
                "operation_id": str(operation_id or "").strip(),
                "contract_version": str(contract_version or "").strip(),
                "trigger_type": clean_trigger_type,
                "source_document_id": str(
                    resource.get("document_id")
                    or resource.get("random_name")
                    or ""
                ).strip(),
                "source_version": resource.get("version_number"),
                "source_hash": str(resource.get("checksum") or "").strip(),
            },
        },
        historical_patterns=None,
        hflo_signals=None,
    )

    casefile = run_investigator(
        request_context=request_context,
        evidence_inputs=evidence_inputs,
        prior_casefile=None,
    )

    if casefile is None:
        return _governed_operation_failure(
            "Investigator could not emit the governed-operation CaseFile."
        )

    observed_operation_ref = _governed_operation_ref_from_casefile(casefile)

    if observed_operation_ref != operation_ref:
        return _governed_operation_failure(
            "CaseFile governed-operation identity did not match the requested operation."
        )

    selected_lane = _select_lane(casefile=casefile)

    logger.info(
        "[ORCHESTRATOR][LANE_SELECTED] request_id=%s case_id=%s lane=%s "
        "operation_ref=%s",
        clean_request_id,
        getattr(casefile, "case_id", None),
        selected_lane,
        operation_ref,
    )

    if selected_lane != "governed_operation":
        return _governed_operation_failure(
            f"Orchestrator selected unexpected lane {selected_lane!r} "
            "for a governed operation."
        )

    governance_ms = max(0.0, (perf_counter() - governance_started) * 1000.0)
    logger.info(
        "[ORCHESTRATOR][GOVERNED_OPERATION_ADMITTED] request_id=%s case_id=%s "
        "operation_ref=%s trigger_type=%s governance_ms=%.3f",
        clean_request_id,
        getattr(casefile, "case_id", None),
        operation_ref,
        clean_trigger_type,
        governance_ms,
    )

    try:
        return execute_llm_on_configured_compute(
            input_packet,
            priority=priority,
            request_id=clean_request_id,
            request_class=request_class,
        )
    except Exception as exc:
        logger.exception(
            "[ORCHESTRATOR][GOVERNED_OPERATION_FAILED] request_id=%s "
            "operation_ref=%s",
            clean_request_id,
            operation_ref,
        )
        return _governed_operation_failure(
            f"Governed operation compute failed: {type(exc).__name__}: {exc}"
        )


# ============================================================================
# Packet Helpers
# ============================================================================

def _build_minimal_header(
    *,
    packet_type,
    origin,
    destination,
    presentation_mode,
    request_id=None,
):
    return PacketHeaderMinimal(
        packet_id=str(uuid.uuid4()),
        packet_type=packet_type,
        origin=origin,
        destination=destination,
        authority_level="orchestrator_only",
        presentation_mode=presentation_mode,
        phase_tag="orchestrator",
        timestamp=datetime.utcnow().isoformat(),
        request_id=request_id,
    )


def _emit_packet(
    *,
    header_minimal,
    payload,
    conversation_id=None,
):
    packet = PacketEnvelope(
        header=PacketHeader(
            minimal=header_minimal
        ),
        payload=payload,
    )

    header_dict = header_minimal.__dict__.copy()

    if conversation_id:
        header_dict["conversation_id"] = conversation_id

    observe_packet(
        packet_header=header_dict
    )

    return packet


def _safe_list(value):
    return value if isinstance(value, list) else []


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def _coerce_lane_payload(
    result: Any,
    *,
    fallback_answer: str,
) -> Dict[str, Any]:
    if isinstance(result, dict):
        return dict(result)

    answer = str(result or "").strip()

    return {
        "answer": answer or fallback_answer,
    }


def _no_lane_suggestions(*_, **__):
    """
    Temporary lane-boundary callback.

    Execution lanes must not generate conversational suggestion chips.
    Shared UX synthesis will provide them after assistant-answer generation.
    """

    return []


# ============================================================================
# CaseFile Evidence Access
# ============================================================================

def _casefile_observations(casefile):
    if casefile is None:
        raise RuntimeError(
            "Orchestrator requires an emitted CaseFile."
        )

    observations = getattr(
        casefile,
        "knowledge_layer_observations",
        None,
    )

    if observations is None:
        raise RuntimeError(
            "CaseFile is missing Knowledge Layer observations."
        )

    return observations


def _document_count(casefile) -> int:
    observations = _casefile_observations(
        casefile
    )
    inventory = getattr(
        observations,
        "artifact_inventory",
        None,
    )

    try:
        return max(
            0,
            int(
                getattr(
                    inventory,
                    "document_count",
                    0,
                )
                or 0
            ),
        )
    except (TypeError, ValueError):
        return 0


def _skill_is_applicable(
    observations,
    skill_id: str,
) -> bool:
    clean_skill_id = str(
        skill_id or ""
    ).strip().lower()

    for observation in _safe_list(
        getattr(
            observations,
            "skill_lanes",
            [],
        )
    ):
        observed_skill_id = str(
            getattr(
                observation,
                "skill_id",
                "",
            )
            or ""
        ).strip().lower()
        applicability = str(
            getattr(
                observation,
                "applicability",
                "",
            )
            or ""
        ).strip().lower()

        if (
            observed_skill_id == clean_skill_id
            and applicability == "applicable"
        ):
            return True

    return False


def _semantic_domain_present(
    observations,
    domain: str,
) -> bool:
    clean_domain = str(
        domain or ""
    ).strip().lower()

    if not clean_domain:
        return False

    domains = _safe_list(
        getattr(
            observations,
            "semantic_domains",
            [],
        )
    )

    return clean_domain in {
        str(value or "").strip().lower()
        for value in domains
    }


def _positive_evidence_present(
    observations,
    ref_id: str,
) -> bool:
    clean_ref_id = str(
        ref_id or ""
    ).strip().lower()

    if not clean_ref_id:
        return False

    refs = _safe_list(
        getattr(
            observations,
            "positive_evidence_refs",
            [],
        )
    )

    return clean_ref_id in {
        str(value or "").strip().lower()
        for value in refs
    }


def _source_evidence_required(observations) -> bool:
    """
    Return whether the CaseFile contains authorized source-evidence dependency.

    This is Orchestrator-owned lane selection from deterministic Investigator
    observations. It does not inspect file contents, embeddings, raw paths, or
    attachment presence.
    """

    return bool(
        _semantic_domain_present(
            observations,
            "selected_source_evidence",
        )
        or _positive_evidence_present(
            observations,
            "observation:source_evidence_dependency",
        )
        or _positive_evidence_present(
            observations,
            "observation:selected_conversation_source_dependency",
        )
    )


# ============================================================================
# Constitutional Routing
# ============================================================================

def _select_lane(*, casefile) -> str:
    """
    Select one execution lane from deterministic CaseFile evidence.

    Precedence:
        1. Registered governed operation -> Governed Operation fast lane
        2. Insufficient evidence -> Clarification
        3. Explicit applicable BEI contract -> BEI Skill Lane
        4. Authorized source evidence -> RAG
        5. External/live information required -> Web
        6. Document analysis required -> DocIntel
        7. Otherwise -> LLM
    """

    observations = _casefile_observations(
        casefile
    )

    if _governed_operation_ref_from_casefile(casefile):
        return "governed_operation"

    sufficiency = getattr(
        observations,
        "sufficiency",
        None,
    )
    sufficiency_state = str(
        getattr(
            sufficiency,
            "sufficiency_state",
            "undetermined",
        )
        or "undetermined"
    ).strip().lower()

    if sufficiency_state == "insufficient":
        return "clarification"

    if _skill_is_applicable(
        observations,
        "bei",
    ):
        return "bei"

    if _source_evidence_required(
        observations
    ):
        return "rag"

    external_requirement = getattr(
        observations,
        "external_information_requirement",
        None,
    )
    external_state = str(
        getattr(
            external_requirement,
            "state",
            "undetermined",
        )
        or "undetermined"
    ).strip().lower()

    if external_state == "required":
        return "web"

    document_requirement = getattr(
        observations,
        "document_analysis_requirement",
        None,
    )
    document_state = str(
        getattr(
            document_requirement,
            "state",
            "undetermined",
        )
        or "undetermined"
    ).strip().lower()

    if document_state == "required":
        return "docintel"

    return "llm"


# ============================================================================
# LLM Lane
# ============================================================================

def _run_llm_path(
    *,
    casefile,
    conversation_id,
    request_id,
    state,
):
    attempt = 0
    validated_payload = None

    while attempt <= 2:
        result = run_llm_lane(
            casefile=casefile,
            conversation_id=conversation_id,
            request_id=request_id,
        )

        validation = validate_llm_output(
            result,
            attempt,
        )

        if validation.get("valid"):
            validated_payload = validation.get(
                "corrected"
            )
            break

        if not validation.get("retry"):
            break

        attempt += 1

    if not validated_payload:
        validated_payload = build_fallback_response()

    try:
        if isinstance(validated_payload, dict):
            answer = validated_payload.get("answer")

            if (
                isinstance(answer, str)
                and len(answer.strip()) >= 10
            ):
                new_state = {
                    "current_subject": state.get(
                        "current_subject"
                    ),
                    "last_resolved_query": state.get(
                        "last_resolved_query"
                    ),
                    "last_answer": answer.strip(),
                    "state_version": (
                        state.get(
                            "state_version",
                            0,
                        )
                        + 1
                    ),
                    "updated_at": (
                        datetime.utcnow().isoformat()
                    ),
                }

                write_state(
                    conversation_id,
                    new_state,
                )

    except Exception as exc:
        logger.debug(
            "[STATE][WRITE_FAIL] %s",
            str(exc),
        )

    return _emit_packet(
        header_minimal=_build_minimal_header(
            packet_type="llm",
            origin="llm",
            destination="ui",
            presentation_mode="constructed",
            request_id=request_id,
        ),
        payload=validated_payload,
        conversation_id=conversation_id,
    )


# ============================================================================
# Clarification Lane
# ============================================================================

def _run_clarification_path(
    *,
    casefile,
    conversation_id,
    request_id,
):
    result = run_clarification_lane(
        document_count=_document_count(
            casefile
        ),
        build_suggestions=_no_lane_suggestions,
    )
    payload = _coerce_lane_payload(
        result,
        fallback_answer=(
            "More information is required to complete this request."
        ),
    )

    observations = _casefile_observations(
        casefile
    )
    sufficiency = getattr(
        observations,
        "sufficiency",
        None,
    )
    missing_information = _safe_list(
        getattr(
            sufficiency,
            "missing_information",
            [],
        )
    )

    if missing_information:
        payload["missing_information"] = list(
            missing_information
        )

    return _emit_packet(
        header_minimal=_build_minimal_header(
            packet_type="clarification",
            origin="clarification",
            destination="ui",
            presentation_mode="constructed",
            request_id=request_id,
        ),
        payload=payload,
        conversation_id=conversation_id,
    )


# ============================================================================
# Web Lane
# ============================================================================

def _run_web_path(
    *,
    task_text,
    casefile,
    execution_context,
    conversation_id,
    request_id,
):
    raw_text = str(
        task_text
        or getattr(
            casefile,
            "raw_user_input",
            "",
        )
        or ""
    ).strip()

    result = run_web_lane(
        raw_text=raw_text,
        document_count=_document_count(
            casefile
        ),
        build_suggestions=_no_lane_suggestions,
        execution_context=(
            dict(execution_context)
            if isinstance(
                execution_context,
                dict,
            )
            else {}
        ),
        conversation_id=conversation_id,
        request_id=request_id,
    )
    payload = _coerce_lane_payload(
        result,
        fallback_answer=(
            "No external information result was produced."
        ),
    )

    return _emit_packet(
        header_minimal=_build_minimal_header(
            packet_type="web",
            origin="web",
            destination="ui",
            presentation_mode="constructed",
            request_id=request_id,
        ),
        payload=payload,
        conversation_id=conversation_id,
    )


# ============================================================================
# RAG Lane
# ============================================================================

def _run_rag_path(
    *,
    task_text,
    casefile,
    execution_context,
    conversation_id,
    request_id,
):
    context = (
        dict(execution_context)
        if isinstance(
            execution_context,
            dict,
        )
        else {}
    )
    raw_text = str(
        task_text
        or context.get("task_text")
        or context.get("raw_user_input")
        or getattr(
            casefile,
            "raw_user_input",
            "",
        )
        or ""
    ).strip()

    logger.info(
        "[ORCHESTRATOR][RAG] request_id=%s conversation_id=%s",
        request_id,
        conversation_id,
    )

    result = run_rag_lane(
        task_text=raw_text,
        execution_context=context,
        casefile=casefile,
        conversation_id=conversation_id,
        request_id=request_id,
    )
    payload = _coerce_lane_payload(
        result,
        fallback_answer=(
            "No authorized-source answer was produced."
        ),
    )

    return _emit_packet(
        header_minimal=_build_minimal_header(
            packet_type="rag",
            origin="rag",
            destination="ui",
            presentation_mode="constructed",
            request_id=request_id,
        ),
        payload=payload,
        conversation_id=conversation_id,
    )


# ============================================================================
# Document and BEI Execution
# ============================================================================

def _run_document_path(
    *,
    selected_lane,
    task_text,
    execution_context,
    conversation_id,
    request_id,
):
    context = (
        dict(execution_context)
        if isinstance(
            execution_context,
            dict,
        )
        else {}
    )
    resolved_paths = _safe_list(
        context.get("resolved_paths")
    )
    explicit_intent = context.get(
        "explicit_intent"
    )
    operation = context.get(
        "operation"
    )
    raw_text = (
        task_text
        or context.get("task_text")
        or context.get("raw_user_input")
        or operation
        or ""
    )
    workflow_context = _safe_dict(
        context.get("workflow_context")
    )
    command_context = _safe_dict(
        context.get("command_context")
    )

    logger.info(
        "[ORCHESTRATOR][%s] request_id=%s paths=%s "
        "operation=%s workflow_id=%s module=%s",
        selected_lane.upper(),
        request_id,
        len(resolved_paths),
        operation,
        workflow_context.get("workflow_id"),
        command_context.get("module"),
    )

    execution_resources = {
        "explicit_intent": explicit_intent,
        "resolved_paths": resolved_paths,
        "operation": operation,
        "workflow_context": workflow_context,
        "emit_packet": _emit_packet,
        "build_header": _build_minimal_header,
        "conversation_id": conversation_id,
        "request_id": request_id,
    }

    if selected_lane == "bei":
        return run_bei_flow(
            **execution_resources
        )

    if selected_lane == "docintel":
        return run_docintel_flow(
            raw_text=raw_text,
            **execution_resources,
        )

    raise RuntimeError(
        f"Unsupported document execution lane: {selected_lane}"
    )


# ============================================================================
# Core Execution
# ============================================================================

def _run_task_body(
    casefile=None,
    task_text=None,
    execution_context=None,
    conversation_id=None,
    request_id=None,
    agent_id=None,
    **_,
):
    del agent_id

    conversation_id = (
        conversation_id
        or "default"
    )
    request_id = (
        request_id
        or "unbound"
    )

    state = read_state(
        conversation_id
    )

    if not isinstance(state, dict):
        state = {}

    try:
        lane = _select_lane(
            casefile=casefile
        )

        logger.info(
            "[ORCHESTRATOR][LANE_SELECTED] "
            "request_id=%s case_id=%s lane=%s",
            request_id,
            getattr(
                casefile,
                "case_id",
                None,
            ),
            lane,
        )

        if lane == "governed_operation":
            raise RuntimeError(
                "Governed operations must execute through "
                "execute_governed_llm_operation()."
            )

        if lane == "clarification":
            return _run_clarification_path(
                casefile=casefile,
                conversation_id=conversation_id,
                request_id=request_id,
            )

        if lane == "bei":
            return _run_document_path(
                selected_lane="bei",
                task_text=task_text,
                execution_context=execution_context,
                conversation_id=conversation_id,
                request_id=request_id,
            )

        if lane == "rag":
            return _run_rag_path(
                task_text=task_text,
                casefile=casefile,
                execution_context=execution_context,
                conversation_id=conversation_id,
                request_id=request_id,
            )

        if lane == "web":
            return _run_web_path(
                task_text=task_text,
                casefile=casefile,
                execution_context=execution_context,
                conversation_id=conversation_id,
                request_id=request_id,
            )

        if lane == "docintel":
            return _run_document_path(
                selected_lane="docintel",
                task_text=task_text,
                execution_context=execution_context,
                conversation_id=conversation_id,
                request_id=request_id,
            )

        if lane == "llm":
            return _run_llm_path(
                casefile=casefile,
                conversation_id=conversation_id,
                request_id=request_id,
                state=state,
            )

        raise RuntimeError(
            f"Unknown lane: {lane}"
        )

    except Exception as exc:
        record_error(
            "orchestrator_runtime",
            type(exc).__name__,
            str(exc),
            traceback.format_exc(),
        )

        return _emit_packet(
            header_minimal=_build_minimal_header(
                packet_type="error",
                origin="system",
                destination="ui",
                presentation_mode="constructed",
                request_id=request_id,
            ),
            payload={
                "answer": (
                    "An internal processing error occurred."
                )
            },
            conversation_id=conversation_id,
        )


def run_task(*args, **kwargs):
    with ThreadPoolExecutor(
        max_workers=1
    ) as pool:
        return pool.submit(
            _run_task_body,
            *args,
            **kwargs,
        ).result()