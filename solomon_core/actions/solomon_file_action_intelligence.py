# -------------------------------------------------------------------
# FILE: solomon_file_action_intelligence.py
# DIRECTORY: solomon_core/actions/
# -------------------------------------------------------------------
# Canonical on-demand intelligence executor for governed Solomon file Actions.
# The browser supplies only Action identity and governed resource identity.
# LOCAL Solomon owns authority, source binding, result persistence, and reuse;
# every fresh model execution enters the V3 Investigator/CaseFile/Orchestrator
# drivetrain before configured SIS compute is permitted.
# -------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Optional

from config import settings
from solomon_core.db import SessionLocal
from solomon_core.docintel.ingestion.docintel_ingestor import (
    DocIntelIngestError,
    ingest_documents_for_intent,
)
from solomon_core.orchestrator_runtime import (
    execute_governed_llm_operation,
)
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionInput,
    LLMExecutionMode,
    LLMFailureReason,
    LLMResponseFormat,
    LLMRuntimeProfile,
)
from solomon_core.llm.llm_prompting import MAX_LLM_INPUT_CHARS
from solomon_core.logger import get_logger
from solomon_core.models import WorkspaceIntelligenceObject
from solomon_core.workspace_intelligence.workspace_intelligence_index import (
    clean_multiline_text,
    representative_document_lines,
    select_docintel_document,
    stable_hash,
)

from .solomon_file_action_context_strategy import (
    CONTEXT_STRATEGY_EXHAUSTIVE_SIGNAL,
    CONTEXT_STRATEGY_HIERARCHICAL_GLOBAL,
    ensure_large_resource_action_preparation,
    resolve_large_resource_action_context,
)
from .solomon_file_action_results import (
    link_ready_solomon_file_action_result,
    persist_ready_solomon_file_action_result,
    resolve_ready_solomon_file_action_result,
)


logger = get_logger("actions.solomon_file_action_intelligence")


_ACTION_COMPLETION_MARKER = "[[SOLOMON_ACTION_COMPLETE]]"


@dataclass(frozen=True)
class SolomonFileActionIntelligenceSpec:
    action_id: str
    title: str
    instruction: str
    empty_message: str


_ACTION_SPECS = {
    "key_points.extract": SolomonFileActionIntelligenceSpec(
        action_id="key_points.extract",
        title="Key Points",
        instruction=(
            "Extract only the most important points explicitly supported by the supplied "
            "document evidence. Return 5 to 8 concise Solomon Markdown bullets when the "
            "evidence supports that many; use '- ' for each bullet and no heading, "
            "introduction, or conclusion. Each bullet should communicate one material fact "
            "or closely related fact cluster in one short sentence, with a second short "
            "sentence only when necessary. Synthesize related details; do not reproduce "
            "document headings, exhaustive line-item lists, or large blocks of source text. "
            "Prioritize obligations, decisions, scope, amounts, dates, constraints, and "
            "conclusions over incidental metadata. You may begin a bullet with a brief "
            "'**Label:**' only when it improves scanning. Keep the complete user-facing "
            "result under 240 words. Do not invent facts or implications. Do not emit HTML, "
            "links, tables, code fences, or unsupported Markdown. If the evidence does not "
            "support meaningful key points, say so plainly."
        ),
        empty_message="No reliable key points were identified in the supplied evidence.",
    ),
    "dates_deadlines.extract": SolomonFileActionIntelligenceSpec(
        action_id="dates_deadlines.extract",
        title="Dates & Deadlines",
        instruction=(
            "Identify only genuine temporal items that materially function as deadlines, due "
            "dates, effective dates, meetings, milestones, schedule commitments, expiration "
            "dates, or other time-bound obligations in the supplied document evidence. A "
            "qualifying item must contain an actual calendar date, clock time, day/month name, "
            "or explicit relative schedule expression such as 'within 30 days' or 'end of day'. "
            "Never interpret phone extensions, identifiers, account numbers, quantities, prices, "
            "section numbers, or other numeric values as dates. Distinguish qualifying temporal "
            "items from incidental publication, revision, or reference dates. Return no more than "
            "10 concise Solomon Markdown bullets using '- ' and no heading, introduction, or "
            "conclusion. Prefer the scan-friendly form '- **Date or time** — meaning' when the "
            "source date/time is explicit. Keep the complete user-facing result under 240 words. "
            "Never infer a due date the evidence does not support. Do not emit HTML, links, "
            "tables, code fences, or unsupported Markdown. If no qualifying temporal item exists, "
            "return exactly: 'No supported dates or deadlines were identified in the supplied evidence.'"
        ),
        empty_message="No supported dates or deadlines were identified in the supplied evidence.",
    ),
    "action_items.extract": SolomonFileActionIntelligenceSpec(
        action_id="action_items.extract",
        title="Action Items",
        instruction=(
            "Extract only explicit tasks, required follow-ups, deliverables, approvals, decisions, "
            "or obligations that the supplied document evidence clearly requires someone to "
            "perform. Do not convert names, contact details, phone extensions, identifiers, "
            "amounts, dates, descriptive facts, completed events, exclusions, or general background "
            "into action items unless the source clearly assigns or requires an action. Scope "
            "language such as 'provide', 'install', 'submit', 'confirm', 'review', 'approve', "
            "'coordinate', or 'complete' may qualify when it expresses a real obligation. Return no "
            "more than 10 concise Solomon Markdown bullets using '- ' and no heading, introduction, "
            "or conclusion. Start each bullet with the concrete action; include the responsible "
            "person or organization and due date only when the source states them. Use brief "
            "'**Owner:**' or '**Due:**' emphasis only when those fields are actually supported. "
            "Keep the complete user-facing result under 260 words. Never invent owners, deadlines, "
            "or tasks. Do not emit HTML, links, tables, code fences, or unsupported Markdown. If no "
            "explicit or reliably supported action item exists, return exactly: 'No explicit action "
            "items were identified in the supplied evidence.'"
        ),
        empty_message="No explicit action items were identified in the supplied evidence.",
    ),
    "document.explain": SolomonFileActionIntelligenceSpec(
        action_id="document.explain",
        title="Document Explanation",
        instruction=(
            "Explain the supplied document in clear, plain business language. Describe what "
            "the document is, its apparent purpose, the most material information it contains, "
            "and what a reader should understand from it. Stay within the supplied evidence. "
            "Use bounded Solomon Markdown only: two to four '## ' section headings, short "
            "paragraphs, '- ' bullets where they improve scanning, and sparse '**...**' emphasis. "
            "Do not repeat the document title as a heading and do not add generic introduction "
            "or conclusion filler. Keep the complete user-facing explanation under 220 words. "
            "Prioritize whole-document purpose, major themes, structure, and the few details a "
            "reader most needs; omit lower-priority detail rather than expanding the response. "
            "Do not provide unsupported legal, financial, technical, or professional advice and "
            "do not invent missing context. Do not emit HTML, links, tables, code fences, H1 "
            "headings, or unsupported Markdown, and end on a complete thought."
        ),
        empty_message="The supplied evidence was not sufficient to explain this document reliably.",
    ),
}


class SolomonFileActionIntelligenceError(RuntimeError):
    """Bounded execution failure for a user-triggered Solomon file Action."""

    def __init__(
        self,
        error_code: str,
        user_output: str,
        *,
        status_code: int = 500,
    ):
        super().__init__(user_output)
        self.error_code = str(error_code or "action_intelligence_failed").strip()
        self.user_output = str(
            user_output or "Solomon could not complete that Action."
        ).strip()
        self.status_code = int(status_code or 500)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _current_cached_evidence(entry: dict) -> tuple[str, dict]:
    """Reuse current Auto Summary evidence when it matches this exact file version."""

    file_id = _safe_int(entry.get("file_id"))
    source_hash = _clean_text(entry.get("checksum"))
    source_version = _safe_int(entry.get("version_number"), 1)

    if not file_id or not source_hash:
        return "", {}

    db_session = SessionLocal()

    try:
        intelligence_objects = (
            db_session.query(WorkspaceIntelligenceObject)
            .filter(
                WorkspaceIntelligenceObject.file_registry_id == file_id,
                WorkspaceIntelligenceObject.object_type == "file",
                WorkspaceIntelligenceObject.status == "active",
                WorkspaceIntelligenceObject.source_hash == source_hash,
            )
            .all()
        )

        for intelligence_object in intelligence_objects:
            metadata = (
                dict(intelligence_object.metadata_json)
                if isinstance(intelligence_object.metadata_json, dict)
                else {}
            )
            cache = metadata.get("summary_evidence_cache")

            if not isinstance(cache, dict):
                continue

            cached_hash = _clean_text(cache.get("source_hash"))
            cached_version = _safe_int(cache.get("target_version"))
            evidence_text = clean_multiline_text(cache.get("text"))
            evidence_hash = _clean_text(cache.get("text_hash"))

            if not (
                cached_hash == source_hash
                and cached_version == source_version
                and evidence_text
                and evidence_hash
                and stable_hash(evidence_text) == evidence_hash
            ):
                continue

            extraction = (
                dict(cache.get("extraction"))
                if isinstance(cache.get("extraction"), dict)
                else {}
            )
            return evidence_text, extraction

        return "", {}
    finally:
        db_session.close()


def _extract_source_evidence(entry: dict) -> tuple[str, dict]:
    cached_text, cached_metadata = _current_cached_evidence(entry)

    if cached_text:
        return cached_text, {
            **cached_metadata,
            "evidence_source": "persisted_auto_summary_evidence",
        }

    source_path = _clean_text(entry.get("path"))

    if not source_path or not Path(source_path).is_file():
        raise SolomonFileActionIntelligenceError(
            "action_source_unavailable",
            "The current file content is unavailable for this Action.",
            status_code=409,
        )

    try:
        packet = ingest_documents_for_intent(
            intent=None,
            resolved_paths=[source_path],
        )
        document = select_docintel_document(packet)
    except DocIntelIngestError as exc:
        raise SolomonFileActionIntelligenceError(
            "action_source_extraction_failed",
            "Solomon could not read enough of this file to complete that Action.",
            status_code=422,
        ) from exc
    except Exception as exc:
        raise SolomonFileActionIntelligenceError(
            "action_source_extraction_failed",
            "Solomon could not read enough of this file to complete that Action.",
            status_code=500,
        ) from exc

    document_text = clean_multiline_text(document.get("text"))

    if not document_text:
        raise SolomonFileActionIntelligenceError(
            "action_source_text_empty",
            "This file did not provide usable text for that Action.",
            status_code=422,
        )

    extraction = (
        dict(document.get("extraction"))
        if isinstance(document.get("extraction"), dict)
        else {}
    )

    return document_text, {
        **extraction,
        "evidence_source": "docintel",
        "complete_source_coverage": extraction.get(
            "complete_source_coverage",
            True,
        ),
    }


def _bounded_source_context(document_text: str) -> str:
    clean_text = clean_multiline_text(document_text)

    if not clean_text:
        return ""

    configured_limit = max(1200, int(settings.SIS_FILE_ACTION_SOURCE_MAX_CHARS))
    transport_limit = max(1200, int(MAX_LLM_INPUT_CHARS * 0.55))
    budget = min(configured_limit, transport_limit)

    if len(clean_text) <= budget:
        return clean_text

    representative = "\n".join(
        representative_document_lines(
            clean_text,
            limit=24,
        )
    ).strip()
    representative_budget = min(
        max(1200, int(budget * 0.25)),
        len(representative),
    )
    head_budget = max(600, int((budget - representative_budget) * 0.65))
    tail_budget = max(400, budget - representative_budget - head_budget)

    parts = [
        clean_text[:head_budget].strip(),
    ]

    if representative_budget:
        parts.append(
            "Representative material:\n"
            + representative[:representative_budget].strip()
        )

    parts.append(
        "Later source material:\n"
        + clean_text[-tail_budget:].strip()
    )

    return clean_multiline_text("\n\n".join(part for part in parts if part))[:budget]


def _coverage_note(evidence: dict) -> str:
    if not isinstance(evidence, dict):
        return "Evidence coverage: source text supplied by governed DocIntel."

    strategy = _clean_text(evidence.get("context_strategy"))

    if strategy == CONTEXT_STRATEGY_EXHAUSTIVE_SIGNAL:
        if evidence.get("complete_source_scan") is True:
            return (
                "Evidence coverage: Solomon scanned every current persisted document chunk "
                "for Action-relevant signals and supplied the matching evidence that fit the "
                "qualified context budget. Do not invent unsupported items."
            )

    if strategy == CONTEXT_STRATEGY_HIERARCHICAL_GLOBAL:
        return (
            "Evidence coverage: Solomon used a whole-document structural map and distributed "
            "representative evidence across the resource. Use it for global understanding, "
            "but do not imply that every source line was supplied verbatim."
        )

    if evidence.get("complete_source_coverage") is False:
        return (
            "Evidence coverage: bounded representative evidence only. Do not imply that "
            "unsupplied portions of the source were reviewed."
        )

    return "Evidence coverage: governed source evidence."


_TEMPORAL_SIGNAL_PATTERNS = (
    re.compile(r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b", re.IGNORECASE),
    re.compile(r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b", re.IGNORECASE),
    re.compile(r"\b(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b"),
    re.compile(r"\b(?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])[-/.](?:(?:19|20)?\d{2})\b"),
    re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b"),
    re.compile(r"\b(?:0?[1-9]|1[0-2])(?::[0-5]\d)?\s*[ap]\.?m\.?\b", re.IGNORECASE),
    re.compile(r"\b\d+\s+(?:business\s+)?(?:day|days|week|weeks|month|months|year|years|hour|hours)\b", re.IGNORECASE),
    re.compile(r"\b(?:today|tomorrow|tonight|noon|midnight|end of day|end of week|end of month|before close of business)\b", re.IGNORECASE),
)

_ACTION_OBLIGATION_RE = re.compile(
    r"\b(?:must|shall|should|required to|needs? to|expected to|responsible for|action required|approval required|due by)\b",
    re.IGNORECASE,
)
_ACTION_IMPERATIVE_RE = re.compile(
    r"^(?:submit|provide|install|confirm|review|approve|coordinate|complete|prepare|deliver|send|update|verify|remove|replace|carry|inspect|notify|schedule|pay|respond|follow up)\b",
    re.IGNORECASE,
)
_ACTION_WILL_RE = re.compile(
    r"\bwill\s+(?:submit|provide|install|confirm|review|approve|coordinate|complete|prepare|deliver|send|update|verify|remove|replace|carry|inspect|notify|schedule|pay|respond|follow up)\b",
    re.IGNORECASE,
)


def _contains_temporal_signal(value: str) -> bool:
    return any(pattern.search(value or "") for pattern in _TEMPORAL_SIGNAL_PATTERNS)


def _contains_action_signal(value: str) -> bool:
    clean_value = re.sub(r"^[-*•]\s+", "", _clean_text(value))
    clean_value = re.sub(r"[*_`]+", "", clean_value)
    return bool(
        _ACTION_OBLIGATION_RE.search(clean_value)
        or _ACTION_IMPERATIVE_RE.search(clean_value)
        or _ACTION_WILL_RE.search(clean_value)
    )


def _generated_bullet_lines(value: str) -> list[str]:
    return [
        line.strip()
        for line in str(value or "").splitlines()
        if re.match(r"^\s*[-*•]\s+\S+", line)
    ]


def _apply_action_semantic_guard(
    *,
    definition,
    spec: SolomonFileActionIntelligenceSpec,
    generated_text: str,
    request_id: str,
) -> str:
    if definition.action_id == "key_points.extract":
        supported_lines = _generated_bullet_lines(generated_text)

        if supported_lines:
            return clean_multiline_text("\n".join(supported_lines))

        logger.info(
            "[actions.intelligence_abstained] request_id=%s action_id=%s reason=no_key_point_bullets",
            request_id,
            definition.action_id,
        )
        return spec.empty_message

    if definition.action_id == "dates_deadlines.extract":
        supported_lines = [
            line
            for line in _generated_bullet_lines(generated_text)
            if _contains_temporal_signal(line)
        ]

        if supported_lines:
            return clean_multiline_text("\n".join(supported_lines))

        logger.info(
            "[actions.intelligence_abstained] request_id=%s action_id=%s reason=no_temporal_signal",
            request_id,
            definition.action_id,
        )
        return spec.empty_message

    if definition.action_id == "action_items.extract":
        supported_lines = [
            line
            for line in _generated_bullet_lines(generated_text)
            if _contains_action_signal(line)
        ]

        if supported_lines:
            return clean_multiline_text("\n".join(supported_lines))

        logger.info(
            "[actions.intelligence_abstained] request_id=%s action_id=%s reason=no_action_signal",
            request_id,
            definition.action_id,
        )
        return spec.empty_message

    return generated_text


def _generate_action_result(
    *,
    definition,
    spec: SolomonFileActionIntelligenceSpec,
    entry: dict,
    source_context: str,
    evidence: dict,
    user_id: int,
    request_id: str,
) -> tuple[str, str, int]:
    original_name = _clean_text(entry.get("original_name")) or "Selected file"
    completion_instruction = (
        "\n\nCompletion requirement: after the complete user-facing result, output the "
        f"exact line {_ACTION_COMPLETION_MARKER}. This is an internal completion marker, "
        "not user-facing content. If space is limited, shorten or omit lower-priority detail "
        "so the marker is still emitted. Never emit a partial sentence or partial bullet just "
        "to reach the marker, and do not explain the marker."
    )

    prompt = (
        f"Document: {original_name}\n\n"
        f"{_coverage_note(evidence)}\n\n"
        f"Action: {spec.title}\n\n"
        f"{spec.instruction}"
        f"{completion_instruction}"
    )
    def execute_generation(generation_prompt: str, *, attempt: int):
        input_packet = LLMExecutionInput(
            user_query=generation_prompt,
            mode=LLMExecutionMode.INFORMATIONAL_ONLY,
            context={
                "document_context": {
                    "document_text": source_context,
                }
            },
            response_format=LLMResponseFormat.TEXT,
            call_site=(
                f"solomon_action:{definition.action_id}:"
                f"v{definition.action_contract_version}:attempt{attempt}"
            ),
            max_new_tokens=int(settings.SIS_FILE_ACTION_MAX_NEW_TOKENS),
            runtime_profile=LLMRuntimeProfile.DEFAULT,
            timeout_seconds=int(settings.SIS_FILE_ACTION_TIMEOUT_SECONDS),
        )

        result = execute_governed_llm_operation(
            input_packet,
            operation_kind="action",
            operation_id=definition.action_id,
            contract_version=definition.action_contract_version,
            actor_id=int(user_id),
            request_id=(
                _clean_text(request_id)
                or f"solomon_action.{definition.action_id}"
            ),
            trigger_type="manual_action",
            source_resource={
                "document_id": _clean_text(entry.get("document_id")),
                "file_id": _safe_int(entry.get("file_id")),
                "original_name": original_name,
                "extension": _clean_text(entry.get("extension")),
                "path": _clean_text(entry.get("path")),
                "version_number": _safe_int(entry.get("version_number"), 1),
                "checksum": _clean_text(entry.get("checksum")),
            },
            priority=definition.execution_priority,
            request_class="foreground",
        )

        if result.is_failure():
            failure = result.failure
            reason = (
                failure.reason
                if failure is not None
                else LLMFailureReason.INTERNAL_ERROR
            )
            logger.warning(
                "[actions.intelligence_failed] request_id=%s action_id=%s "
                "attempt=%s reason=%s",
                request_id,
                definition.action_id,
                attempt,
                reason.value,
            )

            if reason == LLMFailureReason.REFUSED:
                raise SolomonFileActionIntelligenceError(
                    "action_generation_refused",
                    "Solomon could not produce a reliable result from this file.",
                    status_code=422,
                )

            raise SolomonFileActionIntelligenceError(
                f"action_generation_{reason.value}",
                "Solomon could not complete that Action right now.",
                status_code=503 if reason == LLMFailureReason.TIMEOUT else 500,
            )

        return clean_multiline_text(
            result.output.text if result.output is not None else ""
        )

    def verified_completion_text(generated_value: str) -> tuple[str, bool]:
        marker_index = generated_value.rfind(_ACTION_COMPLETION_MARKER)
        marker_verified = bool(
            marker_index >= 0
            and not generated_value[
                marker_index + len(_ACTION_COMPLETION_MARKER):
            ].strip()
        )

        if not marker_verified:
            return generated_value, False

        return clean_multiline_text(generated_value[:marker_index]), True

    completion_attempts = 1
    generated_text = execute_generation(prompt, attempt=completion_attempts)
    generated_text, marker_verified = verified_completion_text(generated_text)

    if not marker_verified:
        completion_attempts = 2
        retry_word_limit = 260 if definition.action_id == "document.explain" else 180
        retry_prompt = (
            f"{prompt}\n\n"
            "Reliability retry: the prior generation did not prove complete termination. "
            "Produce a new, shorter, self-contained result from the same supplied evidence. "
            f"Keep the user-facing result under {retry_word_limit} words, finish every sentence "
            "and bullet, preserve only the highest-priority supported information, and obey the "
            f"completion requirement exactly by ending with {_ACTION_COMPLETION_MARKER}. "
            "Do not mention this retry or the prior generation."
        )
        logger.info(
            "[actions.intelligence_completion_retry] request_id=%s action_id=%s "
            "max_new_tokens=%s",
            request_id,
            definition.action_id,
            settings.SIS_FILE_ACTION_MAX_NEW_TOKENS,
        )
        generated_text = execute_generation(retry_prompt, attempt=completion_attempts)
        generated_text, marker_verified = verified_completion_text(generated_text)

    if not marker_verified:
        logger.warning(
            "[actions.intelligence_incomplete] request_id=%s action_id=%s "
            "attempts=%s max_new_tokens=%s",
            request_id,
            definition.action_id,
            completion_attempts,
            settings.SIS_FILE_ACTION_MAX_NEW_TOKENS,
        )
        raise SolomonFileActionIntelligenceError(
            "action_generation_incomplete",
            "Solomon could not complete a reliable result from this file.",
            status_code=503,
        )

    if not generated_text:
        generated_text = spec.empty_message

    generated_text = _apply_action_semantic_guard(
        definition=definition,
        spec=spec,
        generated_text=generated_text,
        request_id=request_id,
    )

    model_key = ""
    return generated_text, model_key, completion_attempts


def execute_on_demand_solomon_file_action(
    *,
    definition,
    entry: dict,
    user_id: int,
    request_id: str,
    parameters: Optional[dict] = None,
) -> dict:
    """Resolve cache or execute/persist one registered on-demand file Action."""

    spec = _ACTION_SPECS.get(definition.action_id)

    if spec is None:
        raise SolomonFileActionIntelligenceError(
            "action_processor_unavailable",
            "That Action does not have an on-demand processor yet.",
            status_code=409,
        )

    source_hash = _clean_text(entry.get("checksum"))
    file_registry_id = _safe_int(entry.get("file_id"))
    source_version = _safe_int(entry.get("version_number"), 1)
    clean_parameters = dict(parameters) if isinstance(parameters, dict) else {}

    if not source_hash or not file_registry_id:
        raise SolomonFileActionIntelligenceError(
            "action_source_identity_missing",
            "The current file version does not have a reusable content identity.",
            status_code=409,
        )

    cached = resolve_ready_solomon_file_action_result(
        action_id=definition.action_id,
        action_contract_version=definition.action_contract_version,
        source_hash=source_hash,
        parameters=clean_parameters,
    )

    if cached:
        link_ready_solomon_file_action_result(
            result_id=cached.get("result_id", ""),
            file_registry_id=file_registry_id,
            source_version=source_version,
            source_hash=source_hash,
            linked_by_user_id=user_id,
            trigger_type="manual_action_reuse",
            request_id=request_id,
        )
        cached["reused"] = True
        return cached

    prepared_context = resolve_large_resource_action_context(
        definition=definition,
        entry=entry,
    )

    if prepared_context is not None:
        source_context = prepared_context.text
        evidence = dict(prepared_context.evidence)
    else:
        preparation = ensure_large_resource_action_preparation(
            definition=definition,
            entry=entry,
            request_id=request_id,
        )
        preparation_state = _clean_text(
            preparation.get("large_resource_preparation_state")
            if isinstance(preparation, dict)
            else ""
        ).lower()

        if (
            isinstance(preparation, dict)
            and preparation.get("large_resource_preparation_required") is True
        ):
            if preparation_state == "ready":
                prepared_context = resolve_large_resource_action_context(
                    definition=definition,
                    entry=entry,
                )
                if prepared_context is not None:
                    source_context = prepared_context.text
                    evidence = dict(prepared_context.evidence)
                else:
                    raise SolomonFileActionIntelligenceError(
                        "action_context_preparing",
                        (
                            "Solomon is finalizing this large file for reliable "
                            "whole-document Actions. You can keep working and run "
                            "this Action again shortly."
                        ),
                        status_code=409,
                    )
            elif preparation_state in {"pending", "processing", "running", "queued"}:
                raise SolomonFileActionIntelligenceError(
                    "action_context_preparing",
                    (
                        "Solomon is preparing this large file for reliable "
                        "whole-document Actions. You can keep working and run "
                        "this Action again when preparation finishes."
                    ),
                    status_code=409,
                )
            else:
                raise SolomonFileActionIntelligenceError(
                    "action_context_preparation_unavailable",
                    (
                        "Solomon could not prepare enough current whole-document "
                        "evidence to run this Action reliably."
                    ),
                    status_code=503,
                )
        else:
            document_text, evidence = _extract_source_evidence(entry)
            source_context = _bounded_source_context(document_text)

    if not source_context:
        raise SolomonFileActionIntelligenceError(
            "action_source_text_empty",
            "This file did not provide usable text for that Action.",
            status_code=422,
        )

    generated_text, model_key, completion_attempts = _generate_action_result(
        definition=definition,
        spec=spec,
        entry=entry,
        source_context=source_context,
        evidence=evidence,
        user_id=user_id,
        request_id=request_id,
    )
    completed_payload = {
        "type": definition.result_type,
        "format": definition.result_format,
        "title": spec.title,
        "content": generated_text,
    }
    provenance = {
        "source_hash": source_hash,
        "action_id": definition.action_id,
        "action_contract_version": definition.action_contract_version,
        "source_context_hash": stable_hash(source_context),
        "context_strategy": _clean_text(evidence.get("context_strategy")) or "direct",
        "document_map_contract": _clean_text(evidence.get("document_map_contract")),
    }
    stored = persist_ready_solomon_file_action_result(
        action_id=definition.action_id,
        action_contract_version=definition.action_contract_version,
        source_hash=source_hash,
        result_type=definition.result_type,
        result_text=generated_text,
        result_json=completed_payload,
        parameters=clean_parameters,
        processor_key=definition.processor_key,
        processor_version=definition.processor_version,
        model_key=model_key,
        provenance=provenance,
        evidence=evidence,
        metadata={
            "source_context_chars": len(source_context),
            "source_context_hash": stable_hash(source_context),
            "context_strategy": _clean_text(evidence.get("context_strategy")) or "direct",
            "large_resource": bool(evidence.get("large_resource")),
            "source_chunk_count": _safe_int(evidence.get("source_chunk_count")),
            "selected_chunk_count": _safe_int(evidence.get("selected_chunk_count")),
            "completion_verified": True,
            "completion_attempts": completion_attempts,
            "result_format": definition.result_format,
        },
        file_registry_id=file_registry_id,
        source_version=source_version,
        linked_by_user_id=user_id,
        trigger_type="manual_action",
        request_id=request_id,
    )
    stored["reused"] = bool(stored.get("reused"))
    return stored


__all__ = [
    "SolomonFileActionIntelligenceError",
    "execute_on_demand_solomon_file_action",
]
