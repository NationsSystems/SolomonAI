# -------------------------------------------------------------
# FILE: task_api_attachments.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------
# Task API Document Transport Helpers
#
# PURPOSE
#   Resolve explicitly activated workflow documents and explicitly
#   selected SolomonAI conversation sources, then build a resource-only
#   execution context for the lane selected by the Orchestrator.
#
# CONSTITUTIONAL CONTRACT
#   - Artifact resolution and authorization only
#   - No lane selection
#   - No routing inference
#   - No semantic-domain assignment from document presence
#   - Requested operation is copied from the emitted CaseFile
# -------------------------------------------------------------

import os

from flask import has_request_context, session

from solomon_core.logger import get_logger
from solomon_core.solomon_ai_conversation_store import (
    get_solomon_ai_conversation,
)
from solomon_core.workspace_reader.workspace_reader_file_access import (
    QUERY_ACTION,
    READ_ACTION,
    resolve_authorized_file_registry_entry,
)


logger = get_logger("task_api_attachments")

DOCUMENT_HANDOFF_CONTRACT = "explicit_active_documents_only"
DOCUMENT_AUTHORIZATION_STATUS = "workflow_selected"
SOLOMON_AI_SOURCE_HANDOFF_CONTRACT = (
    "explicit_authorized_conversation_sources"
)
SOLOMON_AI_SOURCE_AUTHORIZATION_STATUS = (
    "conversation_selected"
)

ACTIVE_DOCUMENT_SESSION_KEYS = (
    "document_operation_active_document_ids",
    "document_analysis_active_document_ids",
)

AUTHORITY_METADATA_KEYS = (
    "access_scope",
    "permission",
    "authorized_action",
    "organization_id",
    "membership_id",
    "membership_role",
    "custody_id",
    "custody_mode",
    "library_scope",
    "group_id",
    "group_membership_id",
    "group_grant_id",
    "grant_id",
    "grant_type",
    "authority_basis",
    "policy_version",
    "is_discoverable",
    "allow_ai_query",
    "expires_at",
    "conversation_id",
)


def _collect_document_identifiers(payload):
    identifiers = []

    if not isinstance(payload, dict):
        return identifiers

    def add_identifier(value):
        if isinstance(value, str) and value.strip():
            cleaned = value.strip()

            if cleaned not in identifiers:
                identifiers.append(cleaned)

    for value in payload.get("attachment_ids") or []:
        add_identifier(value)

    for key in (
        "documents",
        "uploaded_documents",
    ):
        records = payload.get(key) or []

        if not isinstance(records, list):
            continue

        for record in records:
            if isinstance(record, str):
                add_identifier(record)
                continue

            if not isinstance(record, dict):
                continue

            add_identifier(record.get("document_id"))
            add_identifier(record.get("random_name"))
            add_identifier(record.get("upload_id"))
            add_identifier(record.get("file_id"))

    return identifiers


def _collect_conversation_source_identifiers(payload):
    """Collect source identifiers supplied by the SolomonAI workspace."""

    identifiers = []

    if not isinstance(payload, dict):
        return identifiers

    def add_identifier(value):
        if isinstance(value, str) and value.strip():
            cleaned = value.strip()

            if cleaned not in identifiers:
                identifiers.append(cleaned)

    def add_record(record):
        if isinstance(record, str):
            add_identifier(record)
            return

        if not isinstance(record, dict):
            return

        add_identifier(record.get("document_id"))
        add_identifier(record.get("random_name"))
        add_identifier(record.get("upload_id"))
        add_identifier(record.get("file_id"))
        add_identifier(record.get("id"))

    for key in (
        "document_ids",
        "selected_document_ids",
        "attachment_ids",
    ):
        values = payload.get(key) or []

        if isinstance(values, list):
            for value in values:
                add_identifier(value)

    for key in (
        "documents",
        "uploaded_documents",
        "sources",
    ):
        records = payload.get(key) or []

        if isinstance(records, list):
            for record in records:
                add_record(record)

    source_context = payload.get("source_context")

    if isinstance(source_context, dict):
        for key in (
            "document_ids",
            "selected_document_ids",
        ):
            values = source_context.get(key) or []

            if isinstance(values, list):
                for value in values:
                    add_identifier(value)

        files = source_context.get("files") or []

        if isinstance(files, list):
            for record in files:
                add_record(record)

    return identifiers


def _read_document_value(document, *names):
    for name in names:
        value = (
            document.get(name)
            if isinstance(document, dict)
            else getattr(document, name, None)
        )

        if value not in (None, ""):
            return value

    return None


def _resolve_document_path(document):
    value = _read_document_value(
        document,
        "resolved_path",
        "absolute_path",
        "file_path",
        "filepath",
        "stored_path",
        "saved_path",
        "path",
    )

    if value is None:
        return ""

    return str(value).strip()


def _copy_authority_metadata(source, target):
    if not isinstance(source, dict) or not isinstance(target, dict):
        return target

    for key in AUTHORITY_METADATA_KEYS:
        value = source.get(key)

        if value not in (None, ""):
            target[key] = value

    return target


def _normalize_document_record(document):
    document_id = _read_document_value(
        document,
        "document_id",
        "random_name",
        "upload_id",
        "file_id",
        "id",
    )
    random_name = _read_document_value(
        document,
        "random_name",
        "stored_name",
    )
    original_name = _read_document_value(
        document,
        "original_name",
        "filename",
        "file_name",
        "name",
    )
    resolved_path = _resolve_document_path(
        document
    )
    selected_for_workflow = _read_document_value(
        document,
        "selected_for_workflow",
    )
    selected_for_conversation = _read_document_value(
        document,
        "selected_for_conversation",
    )
    authorization_status = _read_document_value(
        document,
        "authorization_status",
    )
    handoff_contract = _read_document_value(
        document,
        "handoff_contract",
    )
    analysis_status = _read_document_value(
        document,
        "analysis_status",
    )

    clean_document_id = str(
        document_id
        or random_name
        or original_name
        or ""
    ).strip()
    clean_random_name = str(
        random_name
        or document_id
        or ""
    ).strip()

    record = {
        "document_id": clean_document_id,
        "random_name": clean_random_name,
        "original_name": str(
            original_name
            or clean_document_id
            or clean_random_name
        ).strip(),
        "selected_for_workflow": (
            bool(selected_for_workflow)
            if selected_for_workflow is not None
            else True
        ),
        "authorization_status": str(
            authorization_status
            or DOCUMENT_AUTHORIZATION_STATUS
        ).strip(),
        "handoff_contract": str(
            handoff_contract
            or DOCUMENT_HANDOFF_CONTRACT
        ).strip(),
        "analysis_status": str(
            analysis_status
            or "not_started"
        ).strip(),
    }

    if selected_for_conversation is not None:
        record["selected_for_conversation"] = bool(
            selected_for_conversation
        )

    if resolved_path:
        record["resolved_path"] = resolved_path

    return _copy_authority_metadata(
        document if isinstance(document, dict) else {},
        record,
    )


def _get_session_active_identifiers():
    """Return workflow document identifiers stored in the current session."""

    if not has_request_context():
        return []

    identifiers = []
    seen = set()

    for key in ACTIVE_DOCUMENT_SESSION_KEYS:
        values = session.get(key)

        if isinstance(values, str):
            values = [values]

        if not isinstance(values, (list, tuple, set)):
            continue

        for value in values:
            clean_value = str(value or "").strip()

            if not clean_value or clean_value in seen:
                continue

            identifiers.append(clean_value)
            seen.add(clean_value)

    return identifiers


def _enabled_flag(value):
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    if value is None:
        return True

    return bool(value)


def _build_authorized_payload_document(
    access_result,
    *,
    selected_for_workflow,
    authorization_status,
    handoff_contract,
):
    """Build a transport-safe document record from an authorized resolver payload."""

    if not isinstance(access_result, dict):
        return None

    document_id = str(
        access_result.get("document_id")
        or access_result.get("random_name")
        or access_result.get("upload_id")
        or access_result.get("file_id")
        or access_result.get("id")
        or ""
    ).strip()
    random_name = str(
        access_result.get("random_name")
        or document_id
        or ""
    ).strip()
    original_name = str(
        access_result.get("original_name")
        or access_result.get("filename")
        or access_result.get("file_name")
        or document_id
        or random_name
        or ""
    ).strip()
    resolved_path = _resolve_document_path(
        access_result
    )

    if not document_id or not resolved_path:
        return None

    resolved_path = os.path.abspath(
        resolved_path
    )

    if not os.path.isfile(
        resolved_path
    ):
        return None

    try:
        size_bytes = int(
            access_result.get("size_bytes")
            or os.path.getsize(resolved_path)
        )
    except (TypeError, OSError, ValueError):
        size_bytes = None

    document = dict(
        access_result
    )
    document.update(
        {
            "document_id": document_id,
            "file_id": str(
                access_result.get("file_id")
                or ""
            ).strip(),
            "random_name": random_name,
            "original_name": original_name,
            "filename": original_name,
            "resolved_path": resolved_path,
            "path": resolved_path,
            "size_bytes": size_bytes,
            "active": bool(selected_for_workflow),
            "selected_for_workflow": bool(
                selected_for_workflow
            ),
            "authorization_status": authorization_status,
            "handoff_contract": handoff_contract,
            "analysis_status": "not_started",
            "allow_ai_query": _enabled_flag(
                access_result.get("allow_ai_query")
            ),
        }
    )

    return document


def _build_authorized_file_registry_document(
    *,
    user_id,
    identifier,
    request_id,
    selected_for_workflow,
    authorization_status,
    handoff_contract,
    require_ai_query=False,
):
    clean_identifier = str(
        identifier or ""
    ).strip()

    if not user_id or not clean_identifier:
        return None

    action = (
        QUERY_ACTION
        if require_ai_query
        else READ_ACTION
    )

    try:
        access_result = resolve_authorized_file_registry_entry(
            int(user_id),
            clean_identifier,
            request_id=request_id,
            action=action,
        )
    except Exception:
        logger.warning(
            "[API][AUTHORIZED_FILE_RESOLVE_FAILED] "
            "request_id=%s user_id=%s document_id=%s action=%s",
            request_id,
            user_id,
            clean_identifier,
            action,
        )
        return None

    if not access_result:
        return None

    if require_ai_query and not _enabled_flag(
        access_result.get("allow_ai_query")
    ):
        logger.warning(
            "[API][CONVERSATION_SOURCE_REJECTED_AI_DISABLED] "
            "request_id=%s user_id=%s document_id=%s access_scope=%s",
            request_id,
            user_id,
            clean_identifier,
            access_result.get("access_scope"),
        )
        return None

    return _build_authorized_payload_document(
        access_result,
        selected_for_workflow=selected_for_workflow,
        authorization_status=authorization_status,
        handoff_contract=handoff_contract,
    )


def _resolve_authorized_workflow_document(
    user_id,
    identifier,
    *,
    request_id=None,
):
    """Resolve one explicit workflow document through current file authority."""

    return _build_authorized_file_registry_document(
        user_id=user_id,
        identifier=identifier,
        request_id=request_id,
        selected_for_workflow=True,
        authorization_status=DOCUMENT_AUTHORIZATION_STATUS,
        handoff_contract=DOCUMENT_HANDOFF_CONTRACT,
        require_ai_query=False,
    )


def _get_active_upload_snapshot(user_id):
    """Return the current SQL-backed active workflow document snapshot."""

    docs = []
    resolved_paths = []
    seen = set()

    for identifier in _get_session_active_identifiers():
        document = _resolve_authorized_workflow_document(
            user_id,
            identifier,
            request_id="active_upload_snapshot",
        )

        if not document:
            continue

        document_id = str(
            document.get("document_id") or ""
        ).strip()

        if not document_id or document_id in seen:
            continue

        docs.append(document)
        seen.add(document_id)

        resolved_path = str(
            document.get("resolved_path") or ""
        ).strip()

        if (
            resolved_path
            and resolved_path not in resolved_paths
        ):
            resolved_paths.append(resolved_path)

    return docs, resolved_paths


def _get_active_document_ids(user_id):
    """Return canonical document ids authorized for workflow use."""

    docs, _ = _get_active_upload_snapshot(user_id)

    return {
        str(document.get("document_id") or "").strip()
        for document in docs
        if str(document.get("document_id") or "").strip()
    }


def _resolve_active_attachment(user_id, identifier, request_id=None):
    if not user_id:
        return None

    clean_identifier = str(
        identifier or ""
    ).strip()

    if not clean_identifier:
        return None

    document = _resolve_authorized_workflow_document(
        user_id,
        clean_identifier,
        request_id=request_id,
    )

    if not document:
        return None

    document_id = str(
        document.get("document_id") or ""
    ).strip()

    if document_id not in _get_active_document_ids(
        user_id
    ):
        return None

    return document


def _resolve_authorized_conversation_source(
    user_id,
    identifier,
    *,
    request_id=None,
):
    """Resolve one conversation source through current file and AI authority."""

    clean_identifier = str(
        identifier or ""
    ).strip()

    if not user_id or not clean_identifier:
        return None

    return _build_authorized_file_registry_document(
        user_id=user_id,
        identifier=clean_identifier,
        request_id=request_id,
        selected_for_workflow=False,
        authorization_status=(
            SOLOMON_AI_SOURCE_AUTHORIZATION_STATUS
        ),
        handoff_contract=(
            SOLOMON_AI_SOURCE_HANDOFF_CONTRACT
        ),
        require_ai_query=True,
    )


def _resolve_attachments(
    payload,
    request_id,
    user_id=None,
):
    identifiers = _collect_document_identifiers(
        payload
    )
    attachments = []

    if identifiers and not user_id:
        logger.warning(
            "[API][ATTACHMENTS_REJECTED_NO_USER] "
            "request_id=%s requested=%s",
            request_id,
            len(identifiers),
        )
        return attachments

    for identifier in identifiers:
        document = _resolve_active_attachment(
            user_id,
            identifier,
            request_id=request_id,
        )

        if not document:
            logger.warning(
                "[API][ATTACHMENT_NOT_ACTIVE] "
                "request_id=%s user_id=%s document_id=%s",
                request_id,
                user_id,
                identifier,
            )
            continue

        attachments.append(document)

    if identifiers:
        logger.debug(
            "[API][ATTACHMENTS] "
            "request_id=%s requested=%s active_resolved=%s",
            request_id,
            len(identifiers),
            len(attachments),
        )

    return attachments


def _resolve_conversation_sources(
    payload,
    request_id,
    user_id=None,
    conversation_id=None,
):
    """Resolve sources only from an authorized durable SolomonAI conversation."""

    del payload

    sources = []
    clean_conversation_id = str(
        conversation_id or ""
    ).strip()

    if not user_id or not clean_conversation_id:
        logger.warning(
            "[API][CONVERSATION_SOURCES_REJECTED_NO_AUTHORITY] "
            "request_id=%s user_id=%s conversation_id=%s",
            request_id,
            user_id,
            clean_conversation_id,
        )
        return sources

    conversation = get_solomon_ai_conversation(
        user_id=int(user_id),
        conversation_id=clean_conversation_id,
        include_messages=False,
    )

    if not conversation:
        logger.warning(
            "[API][CONVERSATION_SOURCES_REJECTED_NOT_OWNED] "
            "request_id=%s user_id=%s conversation_id=%s",
            request_id,
            user_id,
            clean_conversation_id,
        )
        return sources

    identifiers = (
        conversation.get("document_ids")
        if isinstance(
            conversation.get("document_ids"),
            list,
        )
        else []
    )

    for identifier in identifiers:
        document = _resolve_authorized_conversation_source(
            user_id,
            identifier,
            request_id=request_id,
        )

        if not document:
            logger.warning(
                "[API][CONVERSATION_SOURCE_UNAVAILABLE] "
                "request_id=%s user_id=%s "
                "conversation_id=%s document_id=%s",
                request_id,
                user_id,
                clean_conversation_id,
                identifier,
            )
            continue

        source_record = dict(document)
        source_record.update(
            {
                "selected_for_workflow": False,
                "selected_for_conversation": True,
                "authorization_status": (
                    SOLOMON_AI_SOURCE_AUTHORIZATION_STATUS
                ),
                "handoff_contract": (
                    SOLOMON_AI_SOURCE_HANDOFF_CONTRACT
                ),
                "analysis_status": "not_started",
                "conversation_id": clean_conversation_id,
            }
        )
        sources.append(source_record)

    logger.debug(
        "[API][CONVERSATION_SOURCES] "
        "request_id=%s conversation_id=%s "
        "persisted=%s authorized_resolved=%s",
        request_id,
        clean_conversation_id,
        len(identifiers),
        len(sources),
    )

    return sources


def _build_document_transport(
    attachments,
    active_docs,
    active_paths,
):
    documents_by_id = {}
    resolved_paths = []

    def add_path(value):
        if value is None:
            return

        cleaned = str(value).strip()

        if cleaned and cleaned not in resolved_paths:
            resolved_paths.append(cleaned)

    def add_document(document):
        if not document:
            return

        record = _normalize_document_record(
            document
        )
        document_id = record.get(
            "document_id"
        )

        if not document_id:
            return

        documents_by_id[document_id] = record
        add_path(
            record.get("resolved_path")
        )

    for document in active_docs:
        add_document(document)

    for document in attachments:
        add_document(document)

    if isinstance(active_paths, list):
        for path in active_paths:
            add_path(path)

    return (
        list(documents_by_id.values()),
        resolved_paths,
    )


def _get_document_authority(
    docs,
    default_handoff_contract=DOCUMENT_HANDOFF_CONTRACT,
):
    """Return the preserved authority contract for the resolved document set."""

    clean_default_handoff_contract = str(
        default_handoff_contract
        or DOCUMENT_HANDOFF_CONTRACT
    ).strip()

    contracts = {
        str(
            document.get("handoff_contract")
            or ""
        ).strip()
        for document in docs
        if (
            isinstance(document, dict)
            and str(
                document.get("handoff_contract")
                or ""
            ).strip()
        )
    }
    statuses = {
        str(
            document.get("authorization_status")
            or ""
        ).strip()
        for document in docs
        if (
            isinstance(document, dict)
            and str(
                document.get("authorization_status")
                or ""
            ).strip()
        )
    }

    if not docs:
        authorization_status = (
            "no_conversation_sources_selected"
            if clean_default_handoff_contract
            == SOLOMON_AI_SOURCE_HANDOFF_CONTRACT
            else "no_documents_selected"
        )

        return (
            clean_default_handoff_contract,
            authorization_status,
        )

    handoff_contract = (
        next(iter(contracts))
        if len(contracts) == 1
        else "mixed_explicit_document_authority"
    )
    authorization_status = (
        next(iter(statuses))
        if len(statuses) == 1
        else "mixed_explicit_document_authority"
    )

    return (
        handoff_contract,
        authorization_status,
    )


def _get_casefile_requested_operation(casefile):
    """
    Read the Investigator observation without deriving a competing operation.
    """

    observations = getattr(
        casefile,
        "knowledge_layer_observations",
        None,
    )
    operation = getattr(
        observations,
        "explicit_requested_operation",
        None,
    )

    if not isinstance(operation, str):
        return None

    clean_operation = operation.strip()

    return clean_operation or None


def _build_execution_context(
    *,
    current_user,
    task_text,
    casefile,
    attachments,
    active_docs,
    active_paths,
    command_context,
    command_manifest,
    workflow_context,
    workspace_context,
    conversation_id,
    request_id,
    default_document_handoff_contract=DOCUMENT_HANDOFF_CONTRACT,
):
    """
    Build execution resources after the Orchestrator authority evidence exists.

    This context supplies authorized paths, records, provenance, and transport
    metadata to the selected lane. It does not determine which lane executes.
    """

    docs, resolved_paths = _build_document_transport(
        attachments=attachments,
        active_docs=active_docs,
        active_paths=active_paths,
    )
    operation = _get_casefile_requested_operation(
        casefile
    )
    (
        document_handoff_contract,
        document_authorization_status,
    ) = _get_document_authority(
        docs,
        default_handoff_contract=(
            default_document_handoff_contract
        ),
    )

    return {
        "request_id": request_id,
        "conversation_id": conversation_id,
        "user_id": current_user,
        "raw_user_input": task_text,
        "task_text": task_text,
        "operation": operation,
        "operation_source": (
            "casefile.knowledge_layer_observations."
            "explicit_requested_operation"
            if operation
            else None
        ),
        "docs": docs,
        "documents": docs,
        "resolved_paths": resolved_paths,
        "document_count": len(docs),
        "attachment_count": len(attachments),
        "casefile": casefile,
        "command_context": command_context,
        "command_center_manifest": command_manifest,
        "workflow_context": workflow_context,
        "workspace_context": workspace_context,
        "document_handoff_contract": (
            document_handoff_contract
        ),
        "document_authorization_status": (
            document_authorization_status
        ),
        "analysis_status": "not_started",
        "source_dependency_profile": {
            "documents_present": bool(docs),
            "resolved_paths_present": bool(
                resolved_paths
            ),
            "workspace_context_present": bool(
                workspace_context
            ),
            "explicit_document_activation_required": (
                document_handoff_contract
                == DOCUMENT_HANDOFF_CONTRACT
            ),
            "active_document_count": len(docs),
            "document_handoff_contract": (
                document_handoff_contract
            ),
            "document_authorization_status": (
                document_authorization_status
            ),
        },
    }