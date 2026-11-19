# -------------------------------------------------------------------
# FILE: task_api_workflow_executor.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Shared explicit workflow execution service for task API routes and
# backend document operations.
#
# CONSTITUTIONAL CONTRACT:
#   - Artifact and user request evidence is bound before Investigator execution
#   - Client presentation hints cannot enter governed workflow evidence
#   - Dedicated SolomonAI conversations cannot supply workflow authority
#   - Investigator emits the authoritative immutable CaseFile
#   - The emitted CaseFile is not modified by this service
#   - Orchestrator receives the emitted CaseFile unchanged
#   - Execution lanes produce the substantive assistant answer
#   - Optional request-scoped transport may expose incremental lane text
#   - Optional completed-answer transport occurs after lane execution
#   - UX Synthesis runs only after lane execution
#   - Final packet normalization runs after UX Synthesis
#   - Final SolomonAI transport preserves the emitted CaseFile ID
#   - SQL-authorized corpus exposure is resource context, not routing authority
# -------------------------------------------------------------------

from datetime import datetime, timezone
import uuid

from solomon_core.database_connectivity.structured_evidence_service import (
    resolve_structured_evidence_for_request,
)
from solomon_core.intelligence_service.compute_capacity_repository import (
    persist_request_usage_attribution,
)
from solomon_core.investigator.investigator_casefile_types import (
    EvidenceInputs,
    RequestContext,
)
from solomon_core.investigator.investigator_runtime import run_investigator
from solomon_core.logger import get_logger
from solomon_core.orchestrator_runtime import run_task as orchestrate_task
from solomon_core.presentation.solomon_ai_response_synthesis import (
    synthesize_solomon_ai_response,
)
from solomon_core.solomon_ai_conversation_store import (
    get_solomon_ai_conversation,
    get_solomon_ai_conversation_source_membership_count,
)
from solomon_core.workspace_reader.workspace_reader_file_access import (
    resolve_authorized_file_registry_corpus,
)

from .command_center_context import (
    _build_command_center_manifest,
    _clean_command_context,
    _clean_workflow_context,
)
from .task_api_attachments import (
    DOCUMENT_HANDOFF_CONTRACT,
    SOLOMON_AI_SOURCE_HANDOFF_CONTRACT,
    _build_execution_context,
    _get_active_upload_snapshot,
    _resolve_attachments,
    _resolve_conversation_sources,
)
from .solomon_ai_stream_bridge import (
    register_solomon_ai_stream_callback,
    unregister_solomon_ai_stream_callback,
)
from .task_api_history import _save_bid_review_history
from .task_api_response import _normalize_response
from .task_api_support import (
    _get_or_create_conversation_id,
    _run_orchestrator_with_timeout,
)
from .workspace_context import _clean_workspace_context


logger = get_logger("task_api_workflow_executor")

SOURCE_CORPUS_HANDOFF_CONTRACT = "sql_authorized_file_corpus_v1"
SOURCE_CORPUS_LIMIT = 75
SOURCE_CORPUS_ACTION = "query"
SOURCE_CORPUS_PERSONAL_SCOPE = "my_files"


def workflow_execution_error(
    error_code,
    user_output,
    status_code=200,
    extra=None,
):
    """Return a normalized explicit workflow error payload."""

    payload = {
        "ok": False,
        "error": error_code,
        "user_output": user_output,
    }

    if extra:
        payload.update(extra)

    return status_code, payload


def resolve_active_uploads_for_request(
    current_user,
    workspace_command_request,
):
    """Resolve active uploads only for explicit governed workflow execution."""

    if workspace_command_request:
        logger.debug(
            "[API][ASSISTANT_UPLOAD_BINDING_SKIPPED] user_id=%s",
            current_user,
        )
        return [], []

    return _get_active_upload_snapshot(current_user)


def _is_solomon_ai_conversation_request(workspace_context):
    """Identify the dedicated SolomonAI conversation surface."""

    if not isinstance(workspace_context, dict):
        return False

    source = str(
        workspace_context.get("source")
        or ""
    ).strip().lower()
    command_mode = str(
        workspace_context.get("command_mode")
        or ""
    ).strip().lower()

    return (
        source == "solomon_ai_workspace"
        and command_mode == "conversation"
    )


def _workflow_context_has_authority_values(
    workflow_context,
):
    """Return whether cleaned workflow context contains authority-bearing data."""

    if not isinstance(workflow_context, dict):
        return False

    for key in (
        "workflow_id",
        "input_mode",
    ):
        if str(
            workflow_context.get(key)
            or ""
        ).strip():
            return True

    workflow = workflow_context.get("workflow")

    if not isinstance(workflow, dict):
        return False

    return any(
        str(
            workflow.get(key)
            or ""
        ).strip()
        for key in (
            "id",
            "module",
            "requested_action",
        )
    )


def _safe_dict(value):
    return value if isinstance(value, dict) else {}


def _conversation_organization_id(durable_conversation):
    """
    Return an active organization binding for corpus scope, when present.

    This only reads durable conversation authority already resolved by the
    conversation store. It does not create organization authority.
    """

    organization_context = _safe_dict(
        durable_conversation.get("organization_context")
    )

    if not (
        organization_context.get("is_bound")
        and organization_context.get("is_active")
    ):
        return ""

    return str(
        organization_context.get("organization_id")
        or ""
    ).strip()


def _source_corpus_document_id(entry):
    """Return the durable document identity used to de-duplicate corpus entries."""

    if not isinstance(entry, dict):
        return ""

    return str(
        entry.get("document_id")
        or entry.get("random_name")
        or entry.get("file_id")
        or ""
    ).strip()


def _append_source_corpus_entries(
    target,
    seen_document_ids,
    entries,
):
    """Append unique authorized corpus entries without exceeding the request cap."""

    for entry in entries:
        if len(target) >= SOURCE_CORPUS_LIMIT:
            break

        document_id = _source_corpus_document_id(
            entry
        )

        if (
            not document_id
            or document_id in seen_document_ids
        ):
            continue

        target.append(entry)
        seen_document_ids.add(document_id)


def _resolve_solomon_ai_source_corpus(
    *,
    current_user,
    durable_conversation,
    request_id,
):
    """Resolve the authorized searchable corpus for a SolomonAI conversation."""

    organization_id = _conversation_organization_id(
        durable_conversation
    )
    clean_user_id = int(current_user or 0)

    if organization_id:
        organization_corpus = resolve_authorized_file_registry_corpus(
            user_id=clean_user_id,
            organization_id=organization_id,
            request_id=request_id,
            limit=SOURCE_CORPUS_LIMIT,
            action=SOURCE_CORPUS_ACTION,
        )
        personal_corpus = resolve_authorized_file_registry_corpus(
            user_id=clean_user_id,
            organization_id="",
            request_id=f"{request_id}.personal",
            limit=SOURCE_CORPUS_LIMIT,
            action=SOURCE_CORPUS_ACTION,
        )

        corpus = []
        seen_document_ids = set()

        _append_source_corpus_entries(
            corpus,
            seen_document_ids,
            organization_corpus,
        )
        _append_source_corpus_entries(
            corpus,
            seen_document_ids,
            [
                entry
                for entry in personal_corpus
                if str(
                    entry.get("access_scope")
                    or ""
                ).strip().lower() == SOURCE_CORPUS_PERSONAL_SCOPE
            ],
        )
    else:
        corpus = resolve_authorized_file_registry_corpus(
            user_id=clean_user_id,
            organization_id="",
            request_id=request_id,
            limit=SOURCE_CORPUS_LIMIT,
            action=SOURCE_CORPUS_ACTION,
        )

    logger.debug(
        "[API][SOURCE_CORPUS_RESOLVED] request_id=%s user_id=%s "
        "organization_id=%s corpus_action=%s corpus_count=%s",
        request_id,
        current_user,
        organization_id or "",
        SOURCE_CORPUS_ACTION,
        len(corpus),
    )

    return corpus, organization_id


def _read_lane_payload(result):
    """Read the execution-lane payload without normalizing a final packet."""

    if hasattr(result, "payload"):
        payload = getattr(
            result,
            "payload",
            None,
        )

        return (
            dict(payload)
            if isinstance(payload, dict)
            else {}
        )

    if isinstance(result, dict):
        payload = result.get("payload")

        if isinstance(payload, dict):
            return dict(payload)

        return {
            key: value
            for key, value in result.items()
            if key not in {
                "ok",
                "packet_type",
                "verdict",
            }
        }

    return {}


def _read_lane_packet_type(result):
    """Read the selected lane packet type without assembling a UI packet."""

    if hasattr(result, "header"):
        header = getattr(
            result,
            "header",
            None,
        )
        minimal = getattr(
            header,
            "minimal",
            None,
        )
        packet_type = getattr(
            minimal,
            "packet_type",
            None,
        )

        if (
            isinstance(packet_type, str)
            and packet_type.strip()
        ):
            return packet_type.strip()

    if isinstance(result, dict):
        packet_type = result.get(
            "packet_type"
        )

        if (
            isinstance(packet_type, str)
            and packet_type.strip()
        ):
            return packet_type.strip()

    return ""


def _emit_lane_answer_stage(
    *,
    callback,
    result,
    request_id,
    conversation_id,
    case_id,
):
    """
    Emit the completed substantive answer before optional UX synthesis.

    This callback is transport-only. It does not normalize, persist, mutate,
    synthesize, route, or authorize a final response packet.
    """

    if not callable(callback):
        return

    payload = _read_lane_payload(
        result
    )
    answer = str(
        payload.get("answer")
        or ""
    ).strip()

    if not answer:
        return

    answer_stage = {
        "ok": True,
        "stage": "lane_answer",
        "request_id": request_id,
        "conversation_id": conversation_id,
        "case_id": case_id,
        "packet_type": _read_lane_packet_type(
            result
        ),
        "answer": answer,
    }

    try:
        callback(
            answer_stage
        )
        logger.debug(
            "[API][LANE_ANSWER_EMITTED] "
            "request_id=%s conversation_id=%s "
            "case_id=%s packet_type=%s answer_chars=%s",
            request_id,
            conversation_id,
            case_id,
            answer_stage.get("packet_type"),
            len(answer),
        )
    except Exception as exc:
        logger.warning(
            "[API][LANE_ANSWER_EMIT_FAILED] "
            "request_id=%s conversation_id=%s error=%s",
            request_id,
            conversation_id,
            str(exc),
        )


def run_explicit_workflow_execution(
    *,
    payload,
    current_user,
    request_id,
    agent_id=None,
    workspace_command_request=False,
    lane_answer_callback=None,
):
    """
    Run the governed explicit workflow path.

    Returns:
        Tuple of HTTP status code and final normalized response payload.

    Optional lane_answer_callback:
        Receives request-scoped incremental lane text when supported, then the
        completed substantive lane answer before UX synthesis. The callback
        does not replace final packet normalization or persistence.
    """

    clean_payload = (
        payload
        if isinstance(payload, dict)
        else {}
    )
    task_text = str(
        clean_payload.get("task")
        or ""
    ).strip()

    if not task_text:
        return workflow_execution_error(
            "MissingTaskParameter",
            "Missing 'task' parameter",
            status_code=400,
        )

    command_context = _clean_command_context(
        clean_payload.get("command_context")
    )
    workflow_context = _clean_workflow_context(
        clean_payload
    )
    workflow_context.pop(
        "request_action",
        None,
    )
    workflow_context.pop(
        "solomon_ai_request_action",
        None,
    )
    workspace_context = _clean_workspace_context(
        clean_payload.get("workspace_context")
    )
    solomon_ai_conversation_request = (
        _is_solomon_ai_conversation_request(
            workspace_context
        )
    )

    if solomon_ai_conversation_request:
        if _workflow_context_has_authority_values(
            workflow_context
        ):
            logger.warning(
                "[API][SOLOMON_AI_WORKFLOW_AUTHORITY_IGNORED] "
                "request_id=%s user_id=%s",
                request_id,
                current_user,
            )

        workflow_context = {}

    active_module = (
        command_context.get("module")
        or "home"
    )
    command_manifest = _build_command_center_manifest(
        active_module
    )

    if solomon_ai_conversation_request:
        conversation_id = str(
            clean_payload.get("conversation_id")
            or ""
        ).strip()
    else:
        conversation_id = str(
            clean_payload.get("conversation_id")
            or _get_or_create_conversation_id()
        ).strip()

    case_id = str(uuid.uuid4())
    source_corpus = []
    source_corpus_organization_id = ""
    public_web_selected = False

    if solomon_ai_conversation_request:
        if not conversation_id:
            return workflow_execution_error(
                "SolomonAiConversationRequired",
                (
                    "Open a SolomonAI conversation before "
                    "sending this request."
                ),
                status_code=400,
            )

        durable_conversation = get_solomon_ai_conversation(
            user_id=int(current_user or 0),
            conversation_id=conversation_id,
            include_messages=False,
        )

        if not durable_conversation:
            return workflow_execution_error(
                "SolomonAiConversationInvalid",
                (
                    "This SolomonAI conversation could not "
                    "be found or is not authorized."
                ),
                status_code=404,
            )

        public_web_selected = bool(
            durable_conversation.get(
                "public_web_selected",
                False,
            )
        )

        persisted_source_count = (
            get_solomon_ai_conversation_source_membership_count(
                user_id=int(current_user or 0),
                conversation_id=conversation_id,
            )
        )
        attachments = _resolve_conversation_sources(
            payload=clean_payload,
            request_id=request_id,
            user_id=current_user,
            conversation_id=conversation_id,
        )

        if len(attachments) != persisted_source_count:
            return workflow_execution_error(
                "ConversationSourceResolutionFailed",
                (
                    "One or more conversation sources are "
                    "no longer available or authorized."
                ),
                status_code=409,
                extra={
                    "persisted_source_count": (
                        persisted_source_count
                    ),
                    "resolved_source_count": len(
                        attachments
                    ),
                },
            )

        source_corpus_organization_id = (
            _conversation_organization_id(
                durable_conversation
            )
        )

        if attachments:
            logger.debug(
                "[API][SOURCE_CORPUS_FOCUSED_SUPPRESSED] "
                "request_id=%s user_id=%s conversation_id=%s "
                "explicit_sources=%s organization_id=%s",
                request_id,
                current_user,
                conversation_id,
                len(attachments),
                source_corpus_organization_id or "",
            )
        else:
            source_corpus, source_corpus_organization_id = (
                _resolve_solomon_ai_source_corpus(
                    current_user=current_user,
                    durable_conversation=durable_conversation,
                    request_id=request_id,
                )
            )

        active_docs = []
        active_paths = []
        document_authority = (
            SOLOMON_AI_SOURCE_HANDOFF_CONTRACT
        )
    else:
        attachments = _resolve_attachments(
            payload=clean_payload,
            request_id=request_id,
            user_id=current_user,
        )
        active_docs, active_paths = (
            resolve_active_uploads_for_request(
                current_user=current_user,
                workspace_command_request=(
                    workspace_command_request
                ),
            )
        )
        document_authority = DOCUMENT_HANDOFF_CONTRACT

    structured_evidence = {}
    structured_evidence_matched = False

    if solomon_ai_conversation_request:
        structured_resolution = (
            resolve_structured_evidence_for_request(
                task_text=task_text,
                user_id=current_user,
                request_id=request_id,
                explicit_source_count=len(
                    attachments
                ),
                public_web_selected=(
                    public_web_selected
                ),
            )
        )
        structured_evidence_matched = bool(
            structured_resolution.matched
        )

        if (
            structured_resolution.packet
            is not None
        ):
            structured_evidence = (
                structured_resolution.packet.to_dict()
            )

        if (
            structured_evidence_matched
            and source_corpus
        ):
            logger.debug(
                "[API][SOURCE_CORPUS_STRUCTURED_SUPPRESSED] "
                "request_id=%s user_id=%s conversation_id=%s "
                "corpus_count=%s semantic_operation=%s",
                request_id,
                current_user,
                conversation_id,
                len(source_corpus),
                structured_evidence.get(
                    "semantic_operation"
                ),
            )
            source_corpus = []

    request_surface = (
        "solomon_ai_conversation"
        if solomon_ai_conversation_request
        else (
            "workspace_workflow"
            if workspace_command_request
            else "explicit_workflow"
        )
    )
    request_scope_type = (
        "organization"
        if source_corpus_organization_id
        else "user"
    )
    attribution_source = (
        "durable_conversation"
        if source_corpus_organization_id
        else "authenticated_request"
    )

    # This request path currently has no explicit Group execution authority.
    # File-level group_id values are resource authority only and must not be
    # reinterpreted as workload attribution. Group remains NULL until a true
    # Group-scoped request contract exists.
    persist_request_usage_attribution(
        request_id=request_id,
        user_id=current_user,
        organization_id=(
            source_corpus_organization_id or None
        ),
        group_id=None,
        conversation_id=conversation_id,
        case_id=case_id,
        request_surface=request_surface,
        scope_type=request_scope_type,
        attribution_source=attribution_source,
    )

    request_context = RequestContext(
        case_id=case_id,
        user_id=current_user,
        session_id=conversation_id,
        timestamp=datetime.now(
            timezone.utc
        ).isoformat(),
        archetype_id="unknown",
        request_id=request_id,
    )

    evidence_inputs = EvidenceInputs(
        raw_user_input=task_text,
        attachments=attachments,
        conversation_memory=None,
        environmental_ctx={
            "command_context": command_context,
            "command_center_manifest": command_manifest,
            "workflow_context": workflow_context,
            "workspace_context": workspace_context,
            "assistant_request": workspace_command_request,
            "document_authority": document_authority,
            "source_corpus": source_corpus,
            "source_corpus_count": len(source_corpus),
            "source_corpus_authority": SOURCE_CORPUS_HANDOFF_CONTRACT,
            "source_corpus_action": SOURCE_CORPUS_ACTION,
            "source_corpus_organization_id": source_corpus_organization_id,
            "structured_evidence": structured_evidence,
            "structured_evidence_count": len(
                structured_evidence.get(
                    "records"
                )
                or []
            ),
            "structured_evidence_authority": (
                structured_evidence.get(
                    "authority"
                )
            ),
            "structured_evidence_matched": (
                structured_evidence_matched
            ),
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
        return workflow_execution_error(
            "InvestigatorFailure",
            (
                "Solomon could not construct the evidence record "
                "for this request."
            ),
            status_code=500,
        )

    emitted_case_id = str(
        getattr(
            casefile,
            "case_id",
            None,
        )
        or case_id
    ).strip()

    execution_context = _build_execution_context(
        current_user=current_user,
        task_text=task_text,
        casefile=casefile,
        attachments=attachments,
        active_docs=active_docs,
        active_paths=active_paths,
        command_context=command_context,
        command_manifest=command_manifest,
        workflow_context=workflow_context,
        workspace_context=workspace_context,
        conversation_id=conversation_id,
        request_id=request_id,
        default_document_handoff_contract=(
            document_authority
        ),
    )

    execution_context["assistant_request"] = (
        workspace_command_request
    )
    execution_context["current_user_id"] = current_user
    execution_context["source_corpus"] = source_corpus
    execution_context["source_corpus_count"] = len(source_corpus)
    execution_context["source_corpus_authority"] = (
        SOURCE_CORPUS_HANDOFF_CONTRACT
    )
    execution_context["source_corpus_action"] = SOURCE_CORPUS_ACTION
    execution_context["source_corpus_organization_id"] = (
        source_corpus_organization_id
    )
    execution_context["public_web_selected"] = bool(
        public_web_selected
    )
    execution_context["structured_evidence"] = (
        structured_evidence
    )
    execution_context["structured_evidence_count"] = len(
        structured_evidence.get(
            "records"
        )
        or []
    )
    execution_context["structured_evidence_authority"] = (
        structured_evidence.get(
            "authority"
        )
    )
    execution_context["structured_evidence_matched"] = (
        structured_evidence_matched
    )

    logger.debug(
        "[API][EXECUTION_CONTEXT] request_id=%s docs=%s paths=%s "
        "operation=%s workspace_context=%s assistant_request=%s "
        "solomon_ai_conversation=%s authority=%s corpus=%s "
        "corpus_action=%s corpus_org=%s public_web_selected=%s "
        "structured_matched=%s structured_records=%s structured_status=%s",
        request_id,
        execution_context.get("document_count"),
        len(
            execution_context.get("resolved_paths")
            or []
        ),
        execution_context.get("operation"),
        bool(workspace_context),
        workspace_command_request,
        solomon_ai_conversation_request,
        execution_context.get(
            "document_handoff_contract"
        ),
        execution_context.get("source_corpus_count"),
        execution_context.get("source_corpus_action"),
        execution_context.get("source_corpus_organization_id"),
        execution_context.get("public_web_selected"),
        execution_context.get(
            "structured_evidence_matched"
        ),
        execution_context.get(
            "structured_evidence_count"
        ),
        structured_evidence.get(
            "status"
        ),
    )

    stream_callback_registered = False

    if (
        solomon_ai_conversation_request
        and callable(lane_answer_callback)
    ):
        stream_callback_registered = (
            register_solomon_ai_stream_callback(
                request_id=request_id,
                callback=lane_answer_callback,
                conversation_id=conversation_id,
            )
        )

    try:
        status, result = _run_orchestrator_with_timeout(
            orchestrate_task,
            dict(
                task_text=task_text,
                execution_context=execution_context,
                casefile=casefile,
                agent_id=agent_id,
                conversation_id=conversation_id,
                request_id=request_id,
            ),
            timeout_seconds=75,
        )
    finally:
        if stream_callback_registered:
            unregister_solomon_ai_stream_callback(
                request_id=request_id,
                callback=lane_answer_callback,
            )

    if status == "timeout":
        return workflow_execution_error(
            "ExecutionTimeout",
            "Execution timed out.",
            status_code=504,
        )

    if status == "err":
        raise result

    _emit_lane_answer_stage(
        callback=lane_answer_callback,
        result=result,
        request_id=request_id,
        conversation_id=conversation_id,
        case_id=emitted_case_id,
    )

    result = synthesize_solomon_ai_response(
        result,
        original_request=task_text,
        request_id=request_id,
        enabled=solomon_ai_conversation_request,
    )

    response = _normalize_response(
        result,
        request_id=request_id,
        conversation_id=conversation_id,
    )

    if solomon_ai_conversation_request:
        response["case_id"] = emitted_case_id

        if isinstance(
            response.get("payload"),
            dict,
        ):
            response["payload"]["case_id"] = (
                emitted_case_id
            )

            if structured_evidence_matched:
                response["payload"][
                    "structured_evidence_provenance"
                ] = {
                    "authority": structured_evidence.get(
                        "authority"
                    ),
                    "source_type": structured_evidence.get(
                        "source_type"
                    ),
                    "source_id": structured_evidence.get(
                        "source_id"
                    ),
                    "engine": structured_evidence.get(
                        "engine"
                    ),
                    "semantic_operation": (
                        structured_evidence.get(
                            "semantic_operation"
                        )
                    ),
                    "dataset_id": structured_evidence.get(
                        "dataset_id"
                    ),
                    "retrieved_at": structured_evidence.get(
                        "retrieved_at"
                    ),
                    "status": structured_evidence.get(
                        "status"
                    ),
                    "record_count": len(
                        structured_evidence.get(
                            "records"
                        )
                        or []
                    ),
                    "error_code": structured_evidence.get(
                        "error_code"
                    ),
                }

    review_id = _save_bid_review_history(
        response,
        execution_context,
    )

    if review_id:
        response["review_id"] = review_id

        if isinstance(
            response.get("payload"),
            dict,
        ):
            response["payload"]["review_id"] = (
                review_id
            )

    logger.debug(
        "[API][RESPONSE] request_id=%s case_id=%s packet_type=%s",
        request_id,
        emitted_case_id,
        response.get("packet_type"),
    )

    return 200, response


__all__ = [
    "run_explicit_workflow_execution",
]