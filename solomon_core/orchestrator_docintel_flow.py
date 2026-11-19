# ---------------------------------------------------------------------------
# FILE: orchestrator_docintel_flow.py
# DIRECTORY: solomon_core/
# ---------------------------------------------------------------------------
# DocIntel and BEI Execution Flows
#
# PURPOSE
#   Provide separate execution entry points for:
#     - Core DocIntel Lane
#     - BEI Skill Lane
#
# AUTHORITY
#   - Execution only
#   - No lane selection
#   - No workflow routing
#   - No CaseFile mutation
#
# CONTRACT
#   The Orchestrator selects the lane before invoking either entry point.
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, Optional

from solomon_core.docintel.ingestion.docintel_ingestor import (
    ingest_documents_for_intent,
)
from solomon_core.docintel.reconciliation.bei_fact import (
    BEIFactSet,
    facts_from_tier1_evidence,
)
from solomon_core.docintel.reconciliation.reconciliation_engine import (
    reconcile,
)
from solomon_core.logger import get_logger
from solomon_core.presentation.docintel_execution_adapter import (
    adapt_docintel_execution,
)
from solomon_core.presentation.esl_orchestrator import (
    run_esl_orchestrator,
)
from solomon_core.skills.semantic.bei.bei_report_pipeline import (
    build_bei_report_packet,
)


logger = get_logger("orchestrator_docintel_flow")


SOLOMON_AI_REQUEST_ACTION_SUMMARIZE_SOURCES = (
    "summarize_sources"
)
SOLOMON_AI_REQUEST_ACTION_IDENTIFY_KEY_DETAILS = (
    "identify_key_details"
)
SOLOMON_AI_REQUEST_ACTION_COMPARE_SOURCES = (
    "compare_sources"
)
BEI_REPORT_KIND = "bid_scope_review"


DOCINTEL_OPERATION_REQUEST_ACTIONS = {
    "summary": (
        SOLOMON_AI_REQUEST_ACTION_SUMMARIZE_SOURCES
    ),
    "summarize": (
        SOLOMON_AI_REQUEST_ACTION_SUMMARIZE_SOURCES
    ),
    "summarize_source": (
        SOLOMON_AI_REQUEST_ACTION_SUMMARIZE_SOURCES
    ),
    "summarize_sources": (
        SOLOMON_AI_REQUEST_ACTION_SUMMARIZE_SOURCES
    ),
    "identify_key_details": (
        SOLOMON_AI_REQUEST_ACTION_IDENTIFY_KEY_DETAILS
    ),
    "key_details": (
        SOLOMON_AI_REQUEST_ACTION_IDENTIFY_KEY_DETAILS
    ),
    "extract_key_details": (
        SOLOMON_AI_REQUEST_ACTION_IDENTIFY_KEY_DETAILS
    ),
    "compare": (
        SOLOMON_AI_REQUEST_ACTION_COMPARE_SOURCES
    ),
    "compare_documents": (
        SOLOMON_AI_REQUEST_ACTION_COMPARE_SOURCES
    ),
    "compare_sources": (
        SOLOMON_AI_REQUEST_ACTION_COMPARE_SOURCES
    ),
}

DOCINTEL_PAYLOAD_PASSTHROUGH_KEYS = (
    "answer_source",
    "summary_source",
    "summary_mode",
    "used_fallback",
    "fallback_used",
    "raw_narration_success",
    "narration_brief_chars",
    "source_text_chars",
    "llm_error_present",
    "llm_error_signals",
)


# ============================================================================
# Shared Helpers
# ============================================================================

def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> list:
    return value if isinstance(value, list) else []


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _reject_casefile(kwargs: Dict[str, Any]) -> None:
    if "casefile" in kwargs:
        raise RuntimeError(
            "Architectural violation: an Investigator CaseFile cannot be "
            "passed into an execution lane."
        )


def _resolve_docintel_request_action(
    *,
    requested_operation: str,
) -> str:
    """
    Return the presentation contract derived from the Orchestrator operation.

    The selected operation is authoritative. Workflow context and client
    presentation hints cannot supply or replace this value.
    """

    return (
        DOCINTEL_OPERATION_REQUEST_ACTIONS.get(
            _safe_text(
                requested_operation
            ).lower()
        )
        or ""
    )


def _intent_operation(
    explicit_intent: Any,
    operation: Optional[str],
) -> str:
    intent_operation = getattr(
        explicit_intent,
        "operation",
        None,
    )

    return _safe_text(
        intent_operation
        or operation
    ).lower()


def _ingest_document_bundle(
    *,
    explicit_intent: Any,
    resolved_paths: list,
) -> Optional[Dict[str, Any]]:
    ingested = ingest_documents_for_intent(
        intent=explicit_intent,
        resolved_paths=resolved_paths,
    )

    if not isinstance(ingested, dict):
        logger.warning(
            "[DOCUMENT_FLOW] ingestion returned non-dict"
        )
        return None

    inputs = _safe_dict(
        ingested.get("inputs")
    )
    documents = _safe_list(
        inputs.get("documents")
    )
    signals = _safe_dict(
        inputs.get("signals")
    )

    if not documents:
        logger.warning(
            "[DOCUMENT_FLOW] no documents after ingestion"
        )
        return None

    return {
        "inputs": inputs,
        "documents": documents,
        "signals": signals,
    }


def _build_esl_documents(
    ingested_documents: list[dict],
) -> list[dict]:
    esl_documents = []

    for document in ingested_documents:
        if not isinstance(document, dict):
            continue

        document_id = document.get(
            "document_id"
        )
        original_name = (
            document.get("original_name")
            or document_id
        )
        text = document.get("text") or ""

        esl_documents.append(
            {
                "document_id": document_id,
                "original_name": original_name,
                "display_name": original_name,
                "text": text,
            }
        )

    return esl_documents


def _build_evidence_shell(
    esl_documents: list[dict],
) -> dict:
    evidence = {}

    for document in esl_documents:
        document_id = document.get(
            "document_id"
        )
        display_name = (
            document.get("display_name")
            or document_id
        )
        text = document.get("text") or ""

        evidence[document_id] = {
            "raw_text": text,
        }
        evidence[display_name] = {
            "raw_text": text,
        }

    if (
        esl_documents
        and isinstance(
            esl_documents[0].get("text"),
            str,
        )
    ):
        evidence["raw_text"] = (
            esl_documents[0]["text"]
        )

    return evidence


def _belongs_to_document(
    item: dict,
    document_id: str,
) -> bool:
    if not isinstance(item, dict):
        return False

    item_document_id = (
        item.get("document_id")
        or item.get("source_document_id")
    )

    return (
        item_document_id == document_id
        if item_document_id
        else True
    )


def _build_bei_fact_sets(
    *,
    esl_documents: list[dict],
    ingested_signals: dict,
) -> list[BEIFactSet]:
    sections = _safe_list(
        ingested_signals.get("sections")
    )
    values = _safe_list(
        ingested_signals.get("values")
    )
    structural = _safe_list(
        ingested_signals.get("structural")
    )

    fact_sets: list[BEIFactSet] = []

    for document in esl_documents:
        document_id = document.get(
            "document_id"
        )
        display_name = (
            document.get("display_name")
            or document_id
        )

        document_sections = [
            item
            for item in sections
            if _belongs_to_document(
                item,
                document_id,
            )
        ]
        document_values = [
            item
            for item in values
            if _belongs_to_document(
                item,
                document_id,
            )
        ]
        document_structural = [
            item
            for item in structural
            if _belongs_to_document(
                item,
                document_id,
            )
        ]

        fact_sets.append(
            facts_from_tier1_evidence(
                evidence={
                    "signals": (
                        document_values
                        + document_sections
                        + document_structural
                    )
                },
                document_id=document_id,
                display_name=display_name,
            )
        )

    return fact_sets


# ============================================================================
# Packet Helpers
# ============================================================================

def _packet_verdict(
    packet: dict,
    default: str = "AUTHORIZED",
) -> str:
    if isinstance(packet, dict):
        verdict = packet.get("verdict")

        if isinstance(verdict, str) and verdict.strip():
            return verdict.strip()

    return default


def _packet_ok(
    packet: dict,
    default: bool = True,
) -> bool:
    if (
        isinstance(packet, dict)
        and isinstance(
            packet.get("ok"),
            bool,
        )
    ):
        return packet["ok"]

    return default


def _payload_from_packet(
    packet: dict,
) -> Optional[dict]:
    if not isinstance(packet, dict):
        return None

    payload = packet.get("payload")

    if isinstance(payload, dict):
        return payload

    result = packet.get("result")

    if isinstance(result, dict):
        nested_payload = result.get("payload")

        if isinstance(nested_payload, dict):
            return nested_payload

        return result

    answer = packet.get("answer")

    if (
        isinstance(answer, str)
        and answer.strip()
    ):
        return dict(packet)

    return None


def _normalize_constructed_payload(
    payload: Any,
) -> dict:
    """Return the payload dict that should survive in the final packet."""

    if not isinstance(payload, dict):
        return {
            "answer": _safe_text(payload),
        }

    nested_payload = _payload_from_packet(payload)

    if (
        isinstance(nested_payload, dict)
        and nested_payload is not payload
    ):
        return nested_payload

    return payload


def _propagate_payload_metadata(
    *,
    packet: dict,
    payload: dict,
) -> dict:
    """Copy DocIntel presenter metadata onto the packet envelope."""

    if not isinstance(packet, dict) or not isinstance(payload, dict):
        return packet

    if not isinstance(packet.get("payload"), dict):
        packet["payload"] = payload

    for key in DOCINTEL_PAYLOAD_PASSTHROUGH_KEYS:
        if key in payload:
            packet[key] = payload[key]

    return packet


def _emit_constructed_packet(
    *,
    packet_type: str,
    origin: str,
    emit_packet,
    build_header,
    payload: dict,
    conversation_id,
    request_id,
    ok: bool = True,
    verdict: str = "AUTHORIZED",
) -> dict:
    final_payload = _normalize_constructed_payload(payload)

    if emit_packet and build_header:
        packet = emit_packet(
            header_minimal=build_header(
                packet_type=packet_type,
                origin=origin,
                destination="ui",
                presentation_mode="constructed",
                request_id=request_id,
            ),
            payload=final_payload,
            conversation_id=conversation_id,
        )

        if isinstance(packet, dict):
            packet["ok"] = ok
            packet["packet_type"] = (
                packet.get("packet_type")
                or packet_type
            )
            packet["verdict"] = verdict

            return _propagate_payload_metadata(
                packet=packet,
                payload=final_payload,
            )

        emitted_payload = getattr(
            packet,
            "payload",
            None,
        )
        fallback_packet = {
            "ok": ok,
            "packet_type": packet_type,
            "payload": (
                emitted_payload
                if isinstance(emitted_payload, dict)
                else final_payload
            ),
            "verdict": verdict,
        }

        return _propagate_payload_metadata(
            packet=fallback_packet,
            payload=(
                emitted_payload
                if isinstance(emitted_payload, dict)
                else final_payload
            ),
        )

    packet = {
        "ok": ok,
        "packet_type": packet_type,
        "payload": final_payload,
        "verdict": verdict,
    }

    return _propagate_payload_metadata(
        packet=packet,
        payload=final_payload,
    )


def _emit_docintel_packet(
    *,
    emit_packet,
    build_header,
    payload,
    conversation_id,
    request_id,
    ok=True,
    verdict="AUTHORIZED",
):
    return _emit_constructed_packet(
        packet_type="docintel",
        origin="docintel",
        emit_packet=emit_packet,
        build_header=build_header,
        payload=payload,
        conversation_id=conversation_id,
        request_id=request_id,
        ok=ok,
        verdict=verdict,
    )


def _emit_bei_packet(
    *,
    emit_packet,
    build_header,
    payload,
    conversation_id,
    request_id,
    ok=True,
    verdict="AUTHORIZED",
):
    return _emit_constructed_packet(
        packet_type="bei",
        origin="bei",
        emit_packet=emit_packet,
        build_header=build_header,
        payload=payload,
        conversation_id=conversation_id,
        request_id=request_id,
        ok=ok,
        verdict=verdict,
    )


# ============================================================================
# DocIntel Lane
# ============================================================================

def run_docintel_flow(
    *args,
    **kwargs,
) -> dict:
    """
    Execute the core DocIntel Lane.

    This entry point performs no BEI contract detection and cannot select the
    BEI Skill Lane.
    """

    try:
        _reject_casefile(
            kwargs
        )

        if (
            args
            and isinstance(args[0], dict)
            and not kwargs
        ):
            return run_esl_orchestrator(
                args[0]
            )

        emit_packet = kwargs.get(
            "emit_packet"
        )
        build_header = kwargs.get(
            "build_header"
        )
        conversation_id = kwargs.get(
            "conversation_id"
        )
        request_id = kwargs.get(
            "request_id"
        )
        explicit_intent = kwargs.get(
            "explicit_intent"
        )
        resolved_paths = _safe_list(
            kwargs.get("resolved_paths")
        )
        raw_text = _safe_text(
            kwargs.get("raw_text")
        )
        operation = _safe_text(
            kwargs.get("operation")
        )

        document_bundle = _ingest_document_bundle(
            explicit_intent=explicit_intent,
            resolved_paths=resolved_paths,
        )

        if not document_bundle:
            fallback_payload = run_esl_orchestrator(
                {
                    "documents": [],
                    "evidence": {},
                    "decision": {},
                }
            )

            return _emit_docintel_packet(
                emit_packet=emit_packet,
                build_header=build_header,
                payload=(
                    fallback_payload
                    if isinstance(
                        fallback_payload,
                        dict,
                    )
                    else {
                        "answer": (
                            "No usable document evidence was available."
                        )
                    }
                ),
                conversation_id=conversation_id,
                request_id=request_id,
                ok=False,
                verdict="ERROR",
            )

        inputs = document_bundle["inputs"]
        ingested_documents = document_bundle[
            "documents"
        ]
        requested_operation = _intent_operation(
            explicit_intent,
            operation,
        )

        if (
            len(ingested_documents) >= 2
            and requested_operation == "compare"
        ):
            logger.info(
                "[DOCINTEL_FLOW] comparison path engaged"
            )

            summaries = []

            for document in ingested_documents:
                name = (
                    document.get("original_name")
                    or document.get("document_id")
                )
                text = (
                    document.get("text")
                    or ""
                )[:800]
                preview = (
                    text.strip()
                    .replace(
                        "\n",
                        " ",
                    )
                )

                if len(preview) > 300:
                    preview = (
                        preview[:300]
                        + "..."
                    )

                summaries.append(
                    f"{name}: {preview}"
                )

            answer = (
                "Document Comparison Overview\n\n"
            )

            for summary in summaries:
                answer += (
                    f"- {summary}\n\n"
                )

            return _emit_docintel_packet(
                emit_packet=emit_packet,
                build_header=build_header,
                payload={
                    "answer": answer.strip(),
                },
                conversation_id=conversation_id,
                request_id=request_id,
            )

        esl_documents = _build_esl_documents(
            ingested_documents
        )
        evidence = _build_evidence_shell(
            esl_documents
        )
        reasoning = {
            "reasoning_type": "docintel",
            "inputs": inputs,
            "reconciliation": {},
            "evidence": evidence,
        }

        decision_object = adapt_docintel_execution(
            reasoning=reasoning,
            user_task=raw_text,
        )

        if request_id:
            decision_object["request_id"] = _safe_text(
                request_id
            )

        request_action = (
            _resolve_docintel_request_action(
                requested_operation=requested_operation,
            )
        )

        if request_action:
            decision_object[
                "request_action"
            ] = request_action

        esl_payload = run_esl_orchestrator(
            {
                "documents": esl_documents,
                "evidence": evidence,
                "decision": decision_object,
            }
        )

        if not isinstance(esl_payload, dict):
            logger.warning(
                "[DOCINTEL_FLOW] ESL returned non-dict payload"
            )
            esl_payload = {
                "answer": "",
                "sections": {},
                "posture": None,
                "confidence": None,
            }

        return _emit_docintel_packet(
            emit_packet=emit_packet,
            build_header=build_header,
            payload=esl_payload,
            conversation_id=conversation_id,
            request_id=request_id,
        )

    except Exception:
        logger.exception(
            "[DOCINTEL_FLOW] fatal failure"
        )

        return {
            "ok": False,
            "packet_type": "docintel",
            "payload": {
                "answer": (
                    "DocIntel processing failed."
                )
            },
            "verdict": "ERROR",
        }


# ============================================================================
# BEI Skill Lane
# ============================================================================

def run_bei_flow(
    *args,
    **kwargs,
) -> dict:
    """
    Execute the BEI Skill Lane.

    Invocation of this entry point is authorization from the Orchestrator.
    This function performs no workflow detection and no lane selection.
    """

    try:
        _reject_casefile(
            kwargs
        )

        if args:
            raise RuntimeError(
                "BEI execution requires named execution resources."
            )

        emit_packet = kwargs.get(
            "emit_packet"
        )
        build_header = kwargs.get(
            "build_header"
        )
        conversation_id = kwargs.get(
            "conversation_id"
        )
        request_id = kwargs.get(
            "request_id"
        )
        explicit_intent = kwargs.get(
            "explicit_intent"
        )
        resolved_paths = _safe_list(
            kwargs.get("resolved_paths")
        )
        operation = _safe_text(
            kwargs.get("operation")
        )
        workflow_context = _safe_dict(
            kwargs.get("workflow_context")
        )

        document_bundle = _ingest_document_bundle(
            explicit_intent=explicit_intent,
            resolved_paths=resolved_paths,
        )

        if not document_bundle:
            return _emit_bei_packet(
                emit_packet=emit_packet,
                build_header=build_header,
                payload={
                    "answer": (
                        "Document Analysis could not run because no usable "
                        "document evidence was available."
                    ),
                    "report_kind": BEI_REPORT_KIND,
                },
                conversation_id=conversation_id,
                request_id=request_id,
                ok=False,
                verdict="ERROR",
            )

        ingested_documents = document_bundle[
            "documents"
        ]
        ingested_signals = document_bundle[
            "signals"
        ]
        esl_documents = _build_esl_documents(
            ingested_documents
        )
        fact_sets = _build_bei_fact_sets(
            esl_documents=esl_documents,
            ingested_signals=ingested_signals,
        )
        reconciliation = (
            reconcile(
                fact_sets
            )
            if fact_sets
            else {}
        )

        report_packet = build_bei_report_packet(
            documents=esl_documents,
            reconciliation=reconciliation,
        )
        payload = _payload_from_packet(
            report_packet
        )

        if not payload:
            logger.warning(
                "[BEI_FLOW] report pipeline returned no usable payload"
            )

            return _emit_bei_packet(
                emit_packet=emit_packet,
                build_header=build_header,
                payload={
                    "answer": (
                        "Document Analysis could not produce a review "
                        "from the submitted evidence."
                    ),
                    "report_kind": BEI_REPORT_KIND,
                },
                conversation_id=conversation_id,
                request_id=request_id,
                ok=False,
                verdict="ERROR",
            )

        answer = payload.get(
            "answer"
        )

        if not (
            isinstance(answer, str)
            and answer.strip()
        ):
            return _emit_bei_packet(
                emit_packet=emit_packet,
                build_header=build_header,
                payload={
                    "answer": (
                        "Document Analysis returned no usable assistant answer."
                    ),
                    "report_kind": BEI_REPORT_KIND,
                },
                conversation_id=conversation_id,
                request_id=request_id,
                ok=False,
                verdict="ERROR",
            )

        payload.setdefault(
            "report_kind",
            BEI_REPORT_KIND,
        )

        verdict = _packet_verdict(
            report_packet
        )
        ok = _packet_ok(
            report_packet,
            verdict == "AUTHORIZED",
        )

        logger.info(
            "[BEI_FLOW] report pipeline engaged "
            "workflow_id=%s operation=%s verdict=%s",
            workflow_context.get(
                "workflow_id"
            ),
            operation,
            verdict,
        )

        return _emit_bei_packet(
            emit_packet=emit_packet,
            build_header=build_header,
            payload=payload,
            conversation_id=conversation_id,
            request_id=request_id,
            ok=ok,
            verdict=verdict,
        )

    except Exception:
        logger.exception(
            "[BEI_FLOW] fatal failure"
        )

        return {
            "ok": False,
            "packet_type": "bei",
            "payload": {
                "answer": (
                    "Document Analysis failed while processing "
                    "the submitted evidence."
                ),
                "report_kind": BEI_REPORT_KIND,
            },
            "verdict": "ERROR",
        }


__all__ = [
    "run_docintel_flow",
    "run_bei_flow",
]