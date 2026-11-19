# -------------------------------------------------------------------
# FILE: files_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Upload routes for Solomon Documents storage, upload management,
# durable SolomonAI conversations, and explicit governed handoff.
# -------------------------------------------------------------------

import hashlib
import html
import json
import os
import uuid
from io import BytesIO
from pathlib import Path
from urllib.parse import quote

from flask import (
    Blueprint,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    session,
)

from config import settings
from solomon_core.auth_utils import (
    admin_required,
    login_required,
)
from solomon_core.actions.solomon_file_action_applicability import (
    register_solomon_file_action_applicability_for_record,
)
from solomon_core.db import SessionLocal
from solomon_core.logger import get_logger
from solomon_core.models import (
    FileRegistry,
    IntelligenceJob,
    WorkspaceFolder,
    WorkspaceIntelligenceObject,
)
from solomon_core.intelligence_service.intelligence_job_repository import (
    IntelligenceJobEnqueueSpec,
    IntelligenceJobRepository,
    build_intelligence_job_idempotency_key,
)
from solomon_core.intelligence_service.document_embedding_contract import (
    DOCUMENT_EMBEDDING_ARTIFACT_TYPE,
    DOCUMENT_EMBEDDING_JOB_TYPE,
    DOCUMENT_EMBEDDING_PRIORITY,
    DOCUMENT_EMBEDDING_PROCESSOR_KEY,
    DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
    DOCUMENT_EMBEDDING_SOURCE,
    DOCUMENT_EMBEDDING_TARGET_TYPE,
    DOCUMENT_EMBEDDING_TRIGGER_TYPE,
)
from solomon_core.intelligence_service.document_summary_contract import (
    AUTO_SUMMARY_ARTIFACT_TYPE,
    AUTO_SUMMARY_JOB_TYPE,
    AUTO_SUMMARY_PRIORITY,
    AUTO_SUMMARY_PROCESSOR_KEY,
    AUTO_SUMMARY_PROCESSOR_VERSION,
    AUTO_SUMMARY_SOURCE,
    AUTO_SUMMARY_TARGET_TYPE,
    AUTO_SUMMARY_TRIGGER_TYPE,
)
from solomon_core.solomon_ai_conversation_store import (
    create_solomon_ai_conversation,
    get_latest_solomon_ai_conversation,
    get_solomon_ai_conversation,
    list_solomon_ai_conversation_history,
)
from solomon_core.solomon_tools import file_resolver
from solomon_core.workspace_intelligence.workspace_intelligence_index import (
    WORKSPACE_INTELLIGENCE_FILE_OBJECT_TYPE,
    enrich_file_intelligence_object,
    record_supports_text_enrichment,
    safe_metadata_payload,
    upsert_file_intelligence_object,
)
from solomon_core.workspace_reader.workspace_reader_file_access import (
    READ_ACTION,
    resolve_authorized_file_registry_entry,
)

files_bp = Blueprint(
    "files",
    __name__,
)

logger = get_logger("files_bp")

WORKFLOW_DOCUMENT_ANALYSIS = "document_analysis"

DOCUMENT_ANALYSIS_EXECUTE_ENDPOINT = "/api/task/execute"
DOCUMENT_ANALYSIS_HANDOFF_CONTRACT = (
    "documents_selected_backend_analysis_ready"
)
DOCUMENT_ANALYSIS_SESSION_CONTRACT = (
    "explicit_documents_backend_analysis"
)
DOCUMENT_ANALYSIS_SAFE_STAY_TARGET = "#document-analysis"

SOLOMON_AI_WORKSPACE_TEMPLATE = (
    "components/workspace_solomon_ai.html"
)
WORKSPACE_RENDER_TEMPLATE = (
    "components/workspace_content.html"
)
WORKSPACE_RENDER_MODE_HEADER = (
    "X-Solomon-Render-Mode"
)
WORKSPACE_RENDER_MODE_WORKSPACE = "workspace"
LEGACY_DOCUMENT_AI_SESSION_QUERY = (
    "document_ai_session"
)

ACTIVE_DOCUMENT_SESSION_KEYS = (
    "document_operation_active_document_ids",
    "document_analysis_active_document_ids",
)

SOLOMON_AI_ACTIVE_SESSION_KEYS = (
    "solomon_ai_active_conversation",
    "solomon_ai_active_conversation_id",
    "solomon_ai_active_document_ids",
    "solomon_ai_active_document_names",
    "document_ai_active_session",
    "document_ai_active_session_id",
    "document_ai_active_document_ids",
    "document_ai_active_document_names",
)

AUTHORIZED_FILE_SUMMARY_FIELDS = (
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
)

WORKSPACE_FOLDER_ACTIVE_STATUS = "active"
WORKSPACE_UPLOAD_PARENT_FOLDER_FIELDS = (
    "parent_folder_id",
    "workspace_folder_id",
)
WORKSPACE_FOLDER_UPLOAD_CONTRACT = "workspace_folder_upload_location_v1"

_INTELLIGENCE_JOB_REPOSITORY = IntelligenceJobRepository()

AUTO_SUMMARY_VIEW_CONTRACT = "persisted_document_summary_v1"
AUTO_SUMMARY_VIEW_STATE_READY = "ready"
AUTO_SUMMARY_VIEW_STATE_PENDING = "pending"
AUTO_SUMMARY_VIEW_STATE_STALE = "stale"
AUTO_SUMMARY_VIEW_STATE_FAILED = "failed"
AUTO_SUMMARY_VIEW_STATE_MISSING = "missing"

AUTO_SUMMARY_ACTIVE_JOB_STATUSES = frozenset({
    "pending",
    "claimed",
    "running",
    "retry_wait",
})
AUTO_SUMMARY_FAILED_JOB_STATUSES = frozenset({
    "failed",
    "cancelled",
})


def get_current_user_id() -> int:
    """Return the authenticated user id from session state."""

    try:
        return int(
            session.get("user_id")
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def get_request_id() -> str:
    """Return the active request id when available."""

    return getattr(
        g,
        "request_id",
        "untracked",
    )


def handoff_response(
    payload: dict,
    status_code: int = 200,
):
    """Return the backend document handoff payload as JSON."""

    return jsonify(payload), status_code


def clean_original_name(filename: str) -> str:
    """Return a display-safe original filename."""

    raw_name = (
        str(filename or "")
        .replace("\\", "/")
        .split("/")[-1]
        .strip()
    )
    safe_name = "".join(
        character
        for character in raw_name
        if (
            character.isprintable()
            and character
            not in {
                "\x00",
                "\r",
                "\n",
                "\t",
            }
        )
    ).strip()

    return (
        safe_name
        or "uploaded_file"
    )[:255]


def get_upload_extension(
    original_name: str,
) -> str:
    """Return a normalized upload extension."""

    extension = (
        Path(original_name)
        .suffix
        .lower()
        .strip()
    )

    if (
        not extension
        or len(extension) > 16
    ):
        return ""

    return extension


def create_public_file_handle() -> str:
    """Return an opaque extensionless public file handle."""

    return uuid.uuid4().hex


def normalize_folder_identifier(value) -> str:
    """Return a normalized opaque workspace folder identifier."""

    return str(value or "").strip()


def get_requested_upload_folder_identifier() -> str:
    """Return the requested upload destination folder identifier."""

    for field_name in WORKSPACE_UPLOAD_PARENT_FOLDER_FIELDS:
        clean_identifier = normalize_folder_identifier(
            request.form.get(field_name)
        )

        if clean_identifier:
            return clean_identifier

    return ""


def is_active_workspace_folder(folder: WorkspaceFolder) -> bool:
    """Return whether a workspace folder may receive uploads."""

    if not folder:
        return False

    folder_status = str(
        getattr(
            folder,
            "status",
            "",
        )
        or ""
    ).strip().lower()

    return bool(
        not getattr(folder, "deleted_at", None)
        and (
            not folder_status
            or folder_status == WORKSPACE_FOLDER_ACTIVE_STATUS
        )
    )


def resolve_upload_workspace_folder_id(
    user_id: int,
    folder_identifier: str,
) -> tuple[str, str]:
    """Resolve a user-owned active upload destination folder."""

    clean_identifier = normalize_folder_identifier(
        folder_identifier
    )

    if not clean_identifier:
        return "", ""

    db_session = SessionLocal()

    try:
        folder = None

        if clean_identifier.isdigit():
            folder = db_session.get(
                WorkspaceFolder,
                int(clean_identifier),
            )

        if not folder:
            folder = (
                db_session.query(
                    WorkspaceFolder
                )
                .filter(
                    WorkspaceFolder.folder_id
                    == clean_identifier
                )
                .first()
            )

        if (
            not folder
            or str(
                getattr(
                    folder,
                    "user_id",
                    "",
                )
                or ""
            )
            != str(user_id)
            or not is_active_workspace_folder(folder)
        ):
            return "", "not_found"

        return normalize_folder_identifier(
            getattr(
                folder,
                "folder_id",
                "",
            )
        ), ""
    finally:
        db_session.close()


def build_reader_url(
    file_handle: str,
) -> str:
    """Build the canonical first-party Reader URL."""

    safe_handle = quote(
        str(file_handle or "").strip(),
        safe="",
    )

    return (
        f"/workspace/file/"
        f"{safe_handle}/reader"
    )


def is_workspace_render_request() -> bool:
    """Return whether workspace-only markup was requested."""

    render_mode = str(
        request.headers.get(
            WORKSPACE_RENDER_MODE_HEADER
        )
        or ""
    ).strip().lower()

    return (
        render_mode
        == WORKSPACE_RENDER_MODE_WORKSPACE
    )


def build_solomon_ai_conversation_url(
    conversation_id: str,
) -> str:
    """Build the canonical SolomonAI conversation URL."""

    clean_conversation_id = str(
        conversation_id or ""
    ).strip()

    if not clean_conversation_id:
        return "/ai"

    safe_conversation_id = quote(
        clean_conversation_id,
        safe="",
    )

    return (
        f"/ai/c/"
        f"{safe_conversation_id}"
    )


def get_active_solomon_ai_conversation_id() -> str:
    """Return the active SolomonAI conversation pointer."""

    direct_conversation_id = str(
        session.get(
            "solomon_ai_active_conversation_id"
        )
        or session.get(
            "document_ai_active_session_id"
        )
        or ""
    ).strip()

    if direct_conversation_id:
        return direct_conversation_id

    for key in (
        "solomon_ai_active_conversation",
        "document_ai_active_session",
    ):
        conversation_packet = session.get(key)

        if not isinstance(
            conversation_packet,
            dict,
        ):
            continue

        conversation_id = str(
            conversation_packet.get(
                "conversation_id"
            )
            or conversation_packet.get(
                "session_id"
            )
            or ""
        ).strip()

        if conversation_id:
            return conversation_id

    return ""


def clear_active_solomon_ai_conversation() -> None:
    """Clear stale SolomonAI navigation pointers."""

    changed = False

    for key in SOLOMON_AI_ACTIVE_SESSION_KEYS:
        if key not in session:
            continue

        session.pop(
            key,
            None,
        )
        changed = True

    if changed:
        session.modified = True


def set_active_solomon_ai_conversation(
    conversation: dict,
) -> dict:
    """Store a lightweight active conversation pointer."""

    conversation_packet = (
        dict(conversation)
        if isinstance(
            conversation,
            dict,
        )
        else {}
    )
    conversation_packet.pop(
        "messages",
        None,
    )

    conversation_id = str(
        conversation_packet.get(
            "conversation_id"
        )
        or conversation_packet.get(
            "session_id"
        )
        or ""
    ).strip()

    sources = (
        conversation_packet.get("sources")
        if isinstance(
            conversation_packet.get(
                "sources"
            ),
            list,
        )
        else []
    )

    document_ids = [
        str(
            source.get(
                "document_id"
            )
            or ""
        ).strip()
        for source in sources
        if (
            isinstance(
                source,
                dict,
            )
            and str(
                source.get(
                    "document_id"
                )
                or ""
            ).strip()
        )
    ]

    document_names = [
        str(
            source.get(
                "original_name"
            )
            or ""
        ).strip()
        for source in sources
        if (
            isinstance(
                source,
                dict,
            )
            and str(
                source.get(
                    "original_name"
                )
                or ""
            ).strip()
        )
    ]

    conversation_packet[
        "conversation_id"
    ] = conversation_id
    conversation_packet[
        "session_id"
    ] = conversation_id
    conversation_packet[
        "document_ids"
    ] = document_ids
    conversation_packet[
        "document_names"
    ] = document_names
    conversation_packet[
        "source_count"
    ] = len(document_ids)

    session[
        "solomon_ai_active_conversation"
    ] = conversation_packet
    session[
        "solomon_ai_active_conversation_id"
    ] = conversation_id
    session[
        "solomon_ai_active_document_ids"
    ] = document_ids
    session[
        "solomon_ai_active_document_names"
    ] = document_names

    session[
        "document_ai_active_session"
    ] = conversation_packet
    session[
        "document_ai_active_session_id"
    ] = conversation_id
    session[
        "document_ai_active_document_ids"
    ] = document_ids
    session[
        "document_ai_active_document_names"
    ] = document_names

    session.modified = True

    return conversation_packet


def render_solomon_ai_workspace(
    *,
    user_id: int,
    workspace_session: dict,
):
    """Render one durable SolomonAI conversation."""

    workspace_session = (
        dict(workspace_session)
        if isinstance(
            workspace_session,
            dict,
        )
        else {}
    )

    workspace_sources = (
        get_solomon_ai_workspace_sources(
            user_id,
            workspace_session,
        )
        if workspace_session
        else []
    )

    workspace_messages = (
        workspace_session.get(
            "messages"
        )
        if isinstance(
            workspace_session.get(
                "messages"
            ),
            list,
        )
        else []
    )

    conversation_id = str(
        workspace_session.get(
            "conversation_id"
        )
        or workspace_session.get(
            "session_id"
        )
        or ""
    ).strip()

    workspace_history = (
        list_solomon_ai_conversation_history(
            user_id=user_id,
            active_conversation_id=(
                conversation_id
            ),
        )
    )

    workspace_session[
        "sources"
    ] = workspace_sources
    workspace_session[
        "document_ids"
    ] = [
        source.get(
            "document_id"
        )
        for source in workspace_sources
        if source.get(
            "document_id"
        )
    ]
    workspace_session[
        "document_names"
    ] = [
        source.get(
            "original_name"
        )
        for source in workspace_sources
        if source.get(
            "original_name"
        )
    ]
    workspace_session[
        "source_count"
    ] = len(workspace_sources)
    workspace_session[
        "messages"
    ] = workspace_messages
    workspace_session[
        "message_count"
    ] = len(workspace_messages)

    set_active_solomon_ai_conversation(
        workspace_session
    )

    if is_workspace_render_request():
        response = make_response(
            render_template(
                SOLOMON_AI_WORKSPACE_TEMPLATE,
                solomon_workspace_session=(
                    workspace_session
                ),
                solomon_workspace_sources=(
                    workspace_sources
                ),
                solomon_workspace_messages=(
                    workspace_messages
                ),
                solomon_workspace_history=(
                    workspace_history
                ),
            )
        )
    else:
        response = make_response(
            render_template(
                "index.html",
                active_module="solomon_ai",
                workspace_surface_template=(
                    SOLOMON_AI_WORKSPACE_TEMPLATE
                ),
                solomon_workspace_session=(
                    workspace_session
                ),
                solomon_workspace_sources=(
                    workspace_sources
                ),
                solomon_workspace_messages=(
                    workspace_messages
                ),
                solomon_workspace_history=(
                    workspace_history
                ),
            )
        )

    response.headers[
        "X-Solomon-Workspace-Module"
    ] = "solomon_ai"
    response.vary.add(
        WORKSPACE_RENDER_MODE_HEADER
    )

    return response


def get_solomon_ai_workspace_sources(
    user_id: int,
    active_conversation: dict,
) -> list:
    """Resolve durable conversation source display through file authority."""

    raw_sources = (
        active_conversation.get(
            "sources"
        )
        if isinstance(
            active_conversation.get(
                "sources"
            ),
            list,
        )
        else []
    )
    raw_document_ids = (
        active_conversation.get(
            "document_ids"
        )
    )

    if not isinstance(
        raw_document_ids,
        list,
    ):
        raw_document_ids = (
            [
                source.get(
                    "document_id"
                )
                for source in raw_sources
                if isinstance(
                    source,
                    dict,
                )
            ]
            if raw_sources
            else []
        )

    source_by_id = {
        str(
            source.get(
                "document_id"
            )
            or source.get(
                "random_name"
            )
            or ""
        ).strip(): source
        for source in raw_sources
        if isinstance(
            source,
            dict,
        )
    }
    sources = []
    seen = set()

    for document_id in raw_document_ids:
        clean_document_id = str(
            document_id or ""
        ).strip()

        if (
            not clean_document_id
            or clean_document_id in seen
        ):
            continue

        source = resolve_registered_file_summary(
            user_id,
            clean_document_id,
        )
        resolved_id = str(
            source.get(
                "document_id"
            )
            or ""
        ).strip()

        if not resolved_id:
            continue

        source_packet = source_by_id.get(
            clean_document_id,
            {},
        )
        sources.append({
            **source_packet,
            **source,
            "filename": (
                source.get(
                    "original_name"
                )
                or resolved_id
            ),
            "analysis_status": (
                source_packet.get(
                    "analysis_status"
                )
                if isinstance(
                    source_packet,
                    dict,
                )
                else ""
            )
            or "not_started",
        })
        seen.add(resolved_id)

    return sources


def calculate_file_checksum(
    path: str,
) -> str:
    """Return the SHA-256 checksum for a stored upload."""

    digest = hashlib.sha256()

    with open(
        path,
        "rb",
    ) as stored_file:
        for chunk in iter(
            lambda: stored_file.read(
                1024 * 1024
            ),
            b"",
        ):
            digest.update(chunk)

    return digest.hexdigest()


def enqueue_document_summary_job(
    *,
    db_session,
    record: FileRegistry,
    intelligence_object,
):
    """Enqueue one content-bound Auto Summary job in the upload transaction."""

    if not bool(settings.SIS_AUTO_SUMMARY_ENABLED):
        return None

    if not record_supports_text_enrichment(record):
        intelligence_object.summary_status = "skipped"
        object_metadata = safe_metadata_payload(
            intelligence_object.metadata_json
        )
        intelligence_object.metadata_json = {
            **object_metadata,
            "summary_source": AUTO_SUMMARY_SOURCE,
            "summary_status": "skipped",
            "summary_skip_reason": "unsupported_file_type",
        }
        return None

    db_session.flush()

    target_version = int(
        getattr(record, "version_number", None)
        or 1
    )
    source_hash = str(record.checksum or "").strip() or None
    model_key = str(settings.LLM_DIRECT_MODEL_NAME or "").strip() or None
    idempotency_key = build_intelligence_job_idempotency_key(
        job_type=AUTO_SUMMARY_JOB_TYPE,
        artifact_type=AUTO_SUMMARY_ARTIFACT_TYPE,
        target_type=AUTO_SUMMARY_TARGET_TYPE,
        target_id=str(record.random_name),
        target_version=target_version,
        source_hash=source_hash,
        processor_key=AUTO_SUMMARY_PROCESSOR_KEY,
        processor_version=AUTO_SUMMARY_PROCESSOR_VERSION,
        model_key=model_key,
    )

    job = _INTELLIGENCE_JOB_REPOSITORY.enqueue(
        IntelligenceJobEnqueueSpec(
            job_type=AUTO_SUMMARY_JOB_TYPE,
            artifact_type=AUTO_SUMMARY_ARTIFACT_TYPE,
            target_type=AUTO_SUMMARY_TARGET_TYPE,
            target_id=str(record.random_name),
            target_version=target_version,
            source_hash=source_hash,
            trigger_type=AUTO_SUMMARY_TRIGGER_TYPE,
            trigger_ref=str(record.random_name),
            idempotency_key=idempotency_key,
            priority=AUTO_SUMMARY_PRIORITY,
            user_id=record.uploader_id,
            organization_id=getattr(
                intelligence_object,
                "organization_id",
                None,
            ),
            file_registry_id=record.id,
            intelligence_object_id=intelligence_object.id,
            request_id=get_request_id() or None,
            payload={
                "document_id": str(record.random_name),
                "original_name": str(record.original_name or ""),
                "extension": str(record.extension or ""),
            },
            processor_key=AUTO_SUMMARY_PROCESSOR_KEY,
            processor_version=AUTO_SUMMARY_PROCESSOR_VERSION,
            model_key=model_key,
            max_attempts=3,
        ),
        session=db_session,
    )

    job_status = str(job.status or "").strip().lower()
    object_metadata = safe_metadata_payload(
        intelligence_object.metadata_json
    )

    if job_status in AUTO_SUMMARY_ACTIVE_JOB_STATUSES:
        intelligence_object.summary_status = "pending"
        intelligence_object.error_message = None
        for key in (
            "summary_failure_code",
            "summary_failure_message",
            "summary_failed_at",
        ):
            object_metadata.pop(key, None)
        summary_status = "pending"
    elif job_status in AUTO_SUMMARY_FAILED_JOB_STATUSES:
        intelligence_object.summary_status = "failed"
        summary_status = "failed"
    else:
        summary_status = str(
            intelligence_object.summary_status or job_status or "pending"
        ).strip().lower()

    intelligence_object.metadata_json = {
        **object_metadata,
        "summary_source": AUTO_SUMMARY_SOURCE,
        "summary_status": summary_status,
        "summary_job_id": job.job_id,
        "summary_job_status": job_status,
        "summary_source_hash": source_hash,
        "summary_target_version": target_version,
        "summary_processor_key": AUTO_SUMMARY_PROCESSOR_KEY,
        "summary_processor_version": AUTO_SUMMARY_PROCESSOR_VERSION,
    }

    record_metadata = safe_metadata_payload(record.meta)
    if job_status in AUTO_SUMMARY_ACTIVE_JOB_STATUSES:
        for key in (
            "workspace_intelligence_summary_failure_code",
            "workspace_intelligence_summary_failure_message",
            "workspace_intelligence_summary_failed_at",
        ):
            record_metadata.pop(key, None)
    record.meta = {
        **record_metadata,
        "workspace_intelligence_summary_status": summary_status,
        "workspace_intelligence_summary_job_id": job.job_id,
        "workspace_intelligence_summary_job_status": job_status,
    }

    return job


def enqueue_document_embedding_job(
    *,
    db_session,
    record: FileRegistry,
    intelligence_object,
):
    """Enqueue one content-bound document embedding job in the upload transaction."""

    if not bool(settings.SIS_EMBEDDING_ENABLED):
        return None

    if not record_supports_text_enrichment(record):
        intelligence_object.embedding_status = "skipped"
        object_metadata = safe_metadata_payload(
            intelligence_object.metadata_json
        )
        intelligence_object.metadata_json = {
            **object_metadata,
            "embedding_source": DOCUMENT_EMBEDDING_SOURCE,
            "embedding_status": "skipped",
            "embedding_skip_reason": "unsupported_file_type",
        }
        return None

    db_session.flush()

    target_version = int(
        getattr(record, "version_number", None)
        or 1
    )
    source_hash = str(record.checksum or "").strip() or None
    model_key = str(
        settings.WORKSPACE_ACTION_SELECTOR_MODEL_NAME
        or ""
    ).strip() or None
    idempotency_key = build_intelligence_job_idempotency_key(
        job_type=DOCUMENT_EMBEDDING_JOB_TYPE,
        artifact_type=DOCUMENT_EMBEDDING_ARTIFACT_TYPE,
        target_type=DOCUMENT_EMBEDDING_TARGET_TYPE,
        target_id=str(record.random_name),
        target_version=target_version,
        source_hash=source_hash,
        processor_key=DOCUMENT_EMBEDDING_PROCESSOR_KEY,
        processor_version=DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
        model_key=model_key,
    )

    job = _INTELLIGENCE_JOB_REPOSITORY.enqueue(
        IntelligenceJobEnqueueSpec(
            job_type=DOCUMENT_EMBEDDING_JOB_TYPE,
            artifact_type=DOCUMENT_EMBEDDING_ARTIFACT_TYPE,
            target_type=DOCUMENT_EMBEDDING_TARGET_TYPE,
            target_id=str(record.random_name),
            target_version=target_version,
            source_hash=source_hash,
            trigger_type=DOCUMENT_EMBEDDING_TRIGGER_TYPE,
            trigger_ref=str(record.random_name),
            idempotency_key=idempotency_key,
            priority=DOCUMENT_EMBEDDING_PRIORITY,
            user_id=record.uploader_id,
            organization_id=getattr(
                intelligence_object,
                "organization_id",
                None,
            ),
            file_registry_id=record.id,
            intelligence_object_id=intelligence_object.id,
            request_id=get_request_id() or None,
            payload={
                "document_id": str(record.random_name),
                "original_name": str(record.original_name or ""),
                "extension": str(record.extension or ""),
            },
            processor_key=DOCUMENT_EMBEDDING_PROCESSOR_KEY,
            processor_version=DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
            model_key=model_key,
            max_attempts=3,
        ),
        session=db_session,
    )

    intelligence_object.embedding_status = "pending"
    object_metadata = safe_metadata_payload(
        intelligence_object.metadata_json
    )
    intelligence_object.metadata_json = {
        **object_metadata,
        "embedding_source": DOCUMENT_EMBEDDING_SOURCE,
        "embedding_status": "pending",
        "embedding_job_id": job.job_id,
        "embedding_source_hash": source_hash,
        "embedding_target_version": target_version,
        "embedding_processor_key": DOCUMENT_EMBEDDING_PROCESSOR_KEY,
        "embedding_processor_version": DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
        "embedding_model": model_key,
    }

    return job


def create_file_registry_record(
    *,
    original_name: str,
    file_handle: str,
    path: str,
    uploader_id: int,
    workspace_folder_id: str = "",
) -> dict:
    """Create the canonical FileRegistry record."""

    absolute_path = os.path.abspath(path)
    extension = get_upload_extension(
        original_name
    )
    size_bytes = os.path.getsize(
        absolute_path
    )
    checksum = calculate_file_checksum(
        absolute_path
    )
    clean_workspace_folder_id = normalize_folder_identifier(
        workspace_folder_id
    )
    db_session = SessionLocal()

    try:
        existing = (
            db_session.query(
                FileRegistry
            )
            .filter(
                FileRegistry.random_name
                == file_handle
            )
            .first()
        )

        metadata = {
            "storage_contract": (
                "registered_file_only"
            ),
            "workflow_status": (
                "not_started"
            ),
            "analysis_status": (
                "not_started"
            ),
            "activation_required": True,
            "public_identity": (
                "file_registry_random_name"
            ),
            "storage_filename": (
                os.path.basename(
                    absolute_path
                )
            ),
            "document_status": "active",
            "trashed": False,
            "workspace_intelligence_status": "pending",
        }

        if clean_workspace_folder_id:
            metadata.update({
                "workspace_folder_id": clean_workspace_folder_id,
                "parent_folder_id": clean_workspace_folder_id,
                "folder_upload_contract": (
                    WORKSPACE_FOLDER_UPLOAD_CONTRACT
                ),
            })

        if existing:
            existing.original_name = (
                original_name
            )
            existing.extension = extension
            existing.path = absolute_path
            existing.size_bytes = size_bytes
            existing.checksum = checksum
            existing.uploader_id = (
                uploader_id
            )
            existing.workspace_folder_id = (
                clean_workspace_folder_id
                or None
            )
            existing.meta = metadata
            record = existing
        else:
            record = FileRegistry(
                random_name=file_handle,
                original_name=original_name,
                extension=extension,
                path=absolute_path,
                size_bytes=size_bytes,
                checksum=checksum,
                uploader_id=uploader_id,
                workspace_folder_id=(
                    clean_workspace_folder_id
                    or None
                ),
                meta=metadata,
            )
            db_session.add(record)

        db_session.flush()
        register_solomon_file_action_applicability_for_record(
            db_session=db_session,
            record=record,
        )
        intelligence_object = upsert_file_intelligence_object(
            db_session=db_session,
            record=record,
            metadata=metadata,
        )

        if not intelligence_object:
            raise RuntimeError(
                "Workspace intelligence object could not be created for upload."
            )

        summary_job = enqueue_document_summary_job(
            db_session=db_session,
            record=record,
            intelligence_object=intelligence_object,
        )
        embedding_job = enqueue_document_embedding_job(
            db_session=db_session,
            record=record,
            intelligence_object=intelligence_object,
        )

        metadata = {
            **metadata,
            "workspace_intelligence_summary_status": str(
                intelligence_object.summary_status or "pending"
            ),
            "workspace_intelligence_embedding_status": str(
                intelligence_object.embedding_status or "pending"
            ),
        }
        if summary_job is not None:
            metadata.update({
                "workspace_intelligence_summary_job_id": summary_job.job_id,
                "workspace_intelligence_summary_job_status": summary_job.status,
            })
        if embedding_job is not None:
            metadata.update({
                "workspace_intelligence_embedding_job_id": embedding_job.job_id,
                "workspace_intelligence_embedding_job_status": embedding_job.status,
            })
        record.meta = metadata

        db_session.commit()
        db_session.refresh(record)

        return {
            "document_id": (
                record.random_name
            ),
            "file_id": str(record.id),
            "original_name": (
                record.original_name
            ),
            "random_name": (
                record.random_name
            ),
            "workspace_folder_id": (
                clean_workspace_folder_id
            ),
            "parent_folder_id": (
                clean_workspace_folder_id
            ),
            "extension": (
                record.extension
            ),
            "size_bytes": (
                record.size_bytes
            ),
            "checksum": record.checksum,
            "reader_url": (
                build_reader_url(
                    record.random_name
                )
            ),
            "workspace_reader_url": (
                build_reader_url(
                    record.random_name
                )
            ),
            "workflow_status": (
                "not_started"
            ),
            "analysis_status": (
                "not_started"
            ),
            "workspace_intelligence_status": (
                "pending"
            ),
            "workspace_intelligence_summary_status": str(
                intelligence_object.summary_status or "pending"
            ),
            "intelligence_job_id": (
                summary_job.job_id
                if summary_job is not None
                else ""
            ),
            "intelligence_job_status": (
                summary_job.status
                if summary_job is not None
                else ""
            ),
            "handoff_required": True,
        }
    except Exception:
        db_session.rollback()
        raise
    finally:
        db_session.close()


def _safe_meta_payload(value) -> dict:
    """Return FileRegistry metadata as a dictionary."""

    if isinstance(
        value,
        dict,
    ):
        return dict(value)

    if isinstance(
        value,
        str,
    ):
        try:
            parsed = json.loads(value)
        except (
            TypeError,
            ValueError,
        ):
            return {}

        if isinstance(
            parsed,
            dict,
        ):
            return parsed

    return {}


def _record_is_trashed(
    record: FileRegistry,
) -> bool:
    """Return whether a FileRegistry row is in Trash."""

    metadata = _safe_meta_payload(
        record.meta
    )
    status = str(
        metadata.get(
            "document_status"
        )
        or metadata.get(
            "library_status"
        )
        or metadata.get(
            "storage_status"
        )
        or ""
    ).strip().lower()

    return bool(
        metadata.get("trashed")
        or metadata.get(
            "trashed_at"
        )
        or status
        in {
            "trash",
            "trashed",
            "deleted",
        }
    )


def resolve_uploader_file_registry_record(
    db_session,
    user_id: int,
    identifier: str,
):
    """Return an uploader-owned FileRegistry row for metadata mutation."""

    clean_identifier = str(
        identifier or ""
    ).strip()

    if (
        not user_id
        or not clean_identifier
    ):
        return None

    record = None

    if clean_identifier.isdigit():
        record = db_session.get(
            FileRegistry,
            int(clean_identifier),
        )

    if not record:
        record = (
            db_session.query(
                FileRegistry
            )
            .filter(
                FileRegistry.random_name
                == clean_identifier
            )
            .first()
        )

    if (
        not record
        or str(
            record.uploader_id
            or ""
        )
        != str(user_id)
        or _record_is_trashed(
            record
        )
    ):
        return None

    return record


def update_file_registry_intelligence_metadata(
    *,
    record: FileRegistry,
    intelligence_object,
) -> dict:
    """Persist current intelligence index status back to FileRegistry metadata."""

    metadata = _safe_meta_payload(
        record.meta
    )
    indexed_at = getattr(
        intelligence_object,
        "indexed_at",
        None,
    )

    index_status = str(
        getattr(
            intelligence_object,
            "index_status",
            None,
        )
        or "pending"
    ).strip()

    extraction_status = str(
        getattr(
            intelligence_object,
            "extraction_status",
            None,
        )
        or "pending"
    ).strip()

    summary_status = str(
        getattr(
            intelligence_object,
            "summary_status",
            None,
        )
        or "pending"
    ).strip()

    facts_status = str(
        getattr(
            intelligence_object,
            "facts_status",
            None,
        )
        or "pending"
    ).strip()

    metadata = {
        **metadata,
        "workspace_intelligence_status": index_status,
        "workspace_intelligence_extraction_status": extraction_status,
        "workspace_intelligence_summary_status": summary_status,
        "workspace_intelligence_facts_status": facts_status,
    }

    if indexed_at:
        metadata[
            "workspace_intelligence_indexed_at"
        ] = indexed_at.isoformat()

    record.meta = metadata

    return metadata


def build_upload_intelligence_result(
    *,
    record: FileRegistry,
    intelligence_object,
    status: str,
    error: str = "",
) -> dict:
    """Return a transport-safe upload intelligence result."""

    index_status = str(
        getattr(
            intelligence_object,
            "index_status",
            None,
        )
        or ""
    ).strip()

    extraction_status = str(
        getattr(
            intelligence_object,
            "extraction_status",
            None,
        )
        or ""
    ).strip()

    summary_status = str(
        getattr(
            intelligence_object,
            "summary_status",
            None,
        )
        or ""
    ).strip()

    facts_status = str(
        getattr(
            intelligence_object,
            "facts_status",
            None,
        )
        or ""
    ).strip()

    payload = {
        "ok": status in {
            "enriched",
            "skipped",
        },
        "status": status,
        "document_id": record.random_name,
        "file_id": str(record.id),
        "original_name": record.original_name,
        "random_name": record.random_name,
        "reader_url": build_reader_url(
            record.random_name
        ),
        "workspace_reader_url": build_reader_url(
            record.random_name
        ),
        "workspace_intelligence_status": (
            index_status
            or "pending"
        ),
        "extraction_status": (
            extraction_status
            or "pending"
        ),
        "summary_status": (
            summary_status
            or "pending"
        ),
        "facts_status": (
            facts_status
            or "pending"
        ),
        "search_ready": index_status == "ready",
        "short_summary": str(
            getattr(
                intelligence_object,
                "short_summary",
                "",
            )
            or ""
        ).strip(),
    }

    if error:
        payload["error"] = error

    return payload


def resolve_registered_file_summary(
    user_id: int,
    identifier: str,
) -> dict:
    """Resolve an authorized canonical FileRegistry record summary."""

    clean_identifier = str(
        identifier or ""
    ).strip()

    if (
        not user_id
        or not clean_identifier
    ):
        return {}

    try:
        authorized_file = resolve_authorized_file_registry_entry(
            user_id,
            clean_identifier,
            request_id=get_request_id(),
            action=READ_ACTION,
        )
    except Exception:
        logger.warning(
            (
                "[files.authorized_summary_failed] "
                "user_id=%s identifier=%s request_id=%s"
            ),
            user_id,
            clean_identifier,
            get_request_id(),
        )
        return {}

    if not authorized_file:
        return {}

    document_id = str(
        authorized_file.get(
            "document_id"
        )
        or authorized_file.get(
            "random_name"
        )
        or ""
    ).strip()
    path = str(
        authorized_file.get(
            "path"
        )
        or ""
    ).strip()

    if (
        not document_id
        or not path
        or not os.path.isfile(path)
    ):
        return {}

    summary = {
        "document_id": document_id,
        "file_id": str(
            authorized_file.get(
                "file_id"
            )
            or ""
        ).strip(),
        "original_name": (
            authorized_file.get(
                "original_name"
            )
            or document_id
        ),
        "random_name": document_id,
        "extension": (
            authorized_file.get(
                "extension"
            )
            or Path(
                str(
                    authorized_file.get(
                        "original_name"
                    )
                    or document_id
                )
            ).suffix.lower()
        ),
        "path": path,
        "size_bytes": (
            authorized_file.get(
                "size_bytes"
            )
        ),
        "checksum": (
            authorized_file.get(
                "checksum"
            )
        ),
        "active": False,
        "reader_url": (
            build_reader_url(
                document_id
            )
        ),
        "workspace_reader_url": (
            build_reader_url(
                document_id
            )
        ),
    }

    for field_name in AUTHORIZED_FILE_SUMMARY_FIELDS:
        field_value = authorized_file.get(
            field_name
        )

        if field_value not in (
            None,
            "",
        ):
            summary[field_name] = field_value

    return summary


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (
        TypeError,
        ValueError,
    ):
        return default


def _isoformat_or_empty(value) -> str:
    if value is None:
        return ""

    try:
        return value.isoformat()
    except AttributeError:
        return str(value or "").strip()


def resolve_persisted_auto_summary_state(
    authorized_file: dict,
) -> dict:
    """Return current persisted Auto Summary state without invoking SIS."""

    file_registry_id = _safe_int(
        authorized_file.get("file_id")
    )
    document_id = str(
        authorized_file.get("document_id")
        or authorized_file.get("random_name")
        or ""
    ).strip()
    original_name = str(
        authorized_file.get("original_name")
        or document_id
    ).strip()
    source_hash = str(
        authorized_file.get("checksum")
        or ""
    ).strip()
    source_version = _safe_int(
        authorized_file.get("version_number"),
        1,
    )

    base_payload = {
        "ok": True,
        "summary_contract": AUTO_SUMMARY_VIEW_CONTRACT,
        "document_id": document_id,
        "file_id": str(file_registry_id or ""),
        "original_name": original_name,
        "source_hash": source_hash,
        "source_version": source_version,
        "summary_state": AUTO_SUMMARY_VIEW_STATE_MISSING,
        "summary_status": "missing",
        "job_status": "",
        "summary_hash": "",
        "short_summary": "",
        "detailed_summary": "",
        "generated_at": "",
        "fresh_llm_call": False,
    }

    if not file_registry_id:
        return base_payload

    db_session = SessionLocal()

    try:
        intelligence_object = (
            db_session.query(
                WorkspaceIntelligenceObject
            )
            .filter(
                WorkspaceIntelligenceObject.file_registry_id
                == file_registry_id,
                WorkspaceIntelligenceObject.object_type
                == WORKSPACE_INTELLIGENCE_FILE_OBJECT_TYPE,
            )
            .first()
        )
        latest_job = (
            db_session.query(IntelligenceJob)
            .filter(
                IntelligenceJob.file_registry_id
                == file_registry_id,
                IntelligenceJob.job_type
                == AUTO_SUMMARY_JOB_TYPE,
                IntelligenceJob.target_version
                == source_version,
                IntelligenceJob.source_hash
                == source_hash,
            )
            .order_by(
                IntelligenceJob.created_at.desc(),
                IntelligenceJob.id.desc(),
            )
            .first()
        )

        job_status = str(
            getattr(
                latest_job,
                "status",
                "",
            )
            or ""
        ).strip().lower()
        base_payload["job_status"] = job_status

        if intelligence_object is None:
            if job_status in AUTO_SUMMARY_ACTIVE_JOB_STATUSES:
                base_payload.update({
                    "summary_state": AUTO_SUMMARY_VIEW_STATE_PENDING,
                    "summary_status": "pending",
                })
            elif job_status in AUTO_SUMMARY_FAILED_JOB_STATUSES:
                base_payload.update({
                    "summary_state": AUTO_SUMMARY_VIEW_STATE_FAILED,
                    "summary_status": "failed",
                })

            return base_payload

        metadata = safe_metadata_payload(
            intelligence_object.metadata_json
        )
        summary_status = str(
            intelligence_object.summary_status
            or "pending"
        ).strip().lower()
        detailed_summary = str(
            intelligence_object.detailed_summary
            or ""
        ).strip()
        short_summary = str(
            intelligence_object.short_summary
            or ""
        ).strip()
        summary_hash = str(
            intelligence_object.summary_hash
            or ""
        ).strip()
        object_source_hash = str(
            intelligence_object.source_hash
            or ""
        ).strip()
        metadata_source = str(
            metadata.get("summary_source")
            or ""
        ).strip()
        metadata_source_hash = str(
            metadata.get("summary_source_hash")
            or ""
        ).strip()
        metadata_target_version = _safe_int(
            metadata.get("summary_target_version"),
            0,
        )
        has_persisted_summary = bool(
            detailed_summary
            or short_summary
            or summary_hash
        )
        source_is_current = bool(
            source_hash
            and object_source_hash == source_hash
            and (
                not metadata_source_hash
                or metadata_source_hash == source_hash
            )
            and (
                not metadata_target_version
                or metadata_target_version == source_version
            )
        )
        is_canonical_auto_summary = (
            metadata_source == AUTO_SUMMARY_SOURCE
        )

        base_payload.update({
            "summary_status": summary_status,
            "summary_hash": summary_hash,
            "generated_at": _isoformat_or_empty(
                intelligence_object.updated_at
            ),
        })

        if has_persisted_summary and not source_is_current:
            base_payload.update({
                "summary_state": AUTO_SUMMARY_VIEW_STATE_STALE,
                "summary_status": "stale",
            })
            return base_payload

        if has_persisted_summary and not is_canonical_auto_summary:
            return base_payload

        if (
            summary_status == "ready"
            and source_is_current
            and is_canonical_auto_summary
            and detailed_summary
            and summary_hash
        ):
            base_payload.update({
                "summary_state": AUTO_SUMMARY_VIEW_STATE_READY,
                "summary_status": "ready",
                "short_summary": short_summary,
                "detailed_summary": detailed_summary,
            })
            return base_payload

        if (
            summary_status == "failed"
            or job_status in AUTO_SUMMARY_FAILED_JOB_STATUSES
        ):
            base_payload.update({
                "summary_state": AUTO_SUMMARY_VIEW_STATE_FAILED,
                "summary_status": "failed",
            })
            return base_payload

        if (
            summary_status == "pending"
            or job_status in AUTO_SUMMARY_ACTIVE_JOB_STATUSES
        ):
            base_payload.update({
                "summary_state": AUTO_SUMMARY_VIEW_STATE_PENDING,
                "summary_status": "pending",
            })
            return base_payload

        return base_payload
    finally:
        db_session.close()


def _build_persisted_summary_pdf(payload: dict) -> BytesIO:
    """Build a professional PDF export from one persisted summary payload."""

    try:
        import reportlab
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        from reportlab.lib.pagesizes import LETTER
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.platypus import (
            Paragraph,
            SimpleDocTemplate,
            Spacer,
        )
    except ImportError as exc:
        raise RuntimeError(
            "PDF summary export requires the ReportLab runtime dependency"
        ) from exc

    font_directory = Path(reportlab.__file__).resolve().parent / "fonts"
    font_specs = {
        "SolomonSummaryBody": font_directory / "Vera.ttf",
        "SolomonSummaryBold": font_directory / "VeraBd.ttf",
    }

    for font_name, font_path in font_specs.items():
        if font_name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(
                TTFont(
                    font_name,
                    str(font_path),
                )
            )

    original_name = clean_original_name(
        payload.get("original_name")
        or "Document"
    )
    detailed_summary = str(
        payload.get("detailed_summary")
        or ""
    ).strip()
    generated_at = str(
        payload.get("generated_at")
        or ""
    ).strip()
    source_version = _safe_int(
        payload.get("source_version"),
        1,
    )

    if not detailed_summary:
        raise ValueError("A persisted detailed summary is required for PDF export")

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=LETTER,
        rightMargin=0.72 * inch,
        leftMargin=0.72 * inch,
        topMargin=0.70 * inch,
        bottomMargin=0.68 * inch,
        title=f"{original_name} - Summary",
        author="Nations Systems",
        subject="Persisted document summary",
    )

    title_style = ParagraphStyle(
        "SolomonSummaryTitle",
        fontName="SolomonSummaryBold",
        fontSize=15,
        leading=19,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=8,
    )
    file_style = ParagraphStyle(
        "SolomonSummaryFile",
        fontName="SolomonSummaryBody",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#64748B"),
        spaceAfter=18,
    )
    lead_style = ParagraphStyle(
        "SolomonSummaryLead",
        fontName="SolomonSummaryBold",
        fontSize=11.5,
        leading=17,
        textColor=colors.HexColor("#0F172A"),
        spaceAfter=12,
    )
    body_style = ParagraphStyle(
        "SolomonSummaryBody",
        fontName="SolomonSummaryBody",
        fontSize=10.5,
        leading=16,
        textColor=colors.HexColor("#1E293B"),
        spaceAfter=11,
    )
    footer_style = ParagraphStyle(
        "SolomonSummaryFooter",
        fontName="SolomonSummaryBody",
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#64748B"),
        alignment=TA_CENTER,
        spaceBefore=12,
    )

    paragraphs = [
        part.strip()
        for part in detailed_summary.split("\n\n")
        if part.strip()
    ]
    story = [
        Paragraph("Summary", title_style),
        Paragraph(html.escape(original_name), file_style),
    ]

    for index, paragraph_text in enumerate(paragraphs):
        escaped_text = html.escape(paragraph_text).replace("\n", "<br/>")
        story.append(
            Paragraph(
                escaped_text,
                lead_style if index == 0 else body_style,
            )
        )

    generated_copy = generated_at.replace("T", " ") if generated_at else "Saved summary"
    story.extend([
        Spacer(1, 4),
        Paragraph(
            html.escape(
                f"{generated_copy} · Current file version {source_version}"
            ),
            footer_style,
        ),
    ])

    document.build(story)
    output.seek(0)
    return output


def _summary_download_name(original_name: str) -> str:
    """Return a safe user-facing PDF filename for a persisted summary."""

    clean_name = clean_original_name(original_name)
    stem = Path(clean_name).stem.strip() or "Document"
    return f"{stem} - Summary.pdf"


def collect_handoff_identifiers() -> list:
    """Collect document identifiers from request input."""

    payload = (
        request.get_json(
            silent=True
        )
        or {}
    )
    values = []

    for key in (
        "identifier",
        "document_id",
        "file_id",
        "random_name",
    ):
        value = payload.get(key)

        if value:
            values.append(value)

    for key in (
        "identifiers",
        "document_ids",
        "file_ids",
        "random_names",
    ):
        value = payload.get(key)

        if isinstance(
            value,
            list,
        ):
            values.extend(value)

    files = payload.get("files")

    if isinstance(
        files,
        list,
    ):
        for item in files:
            if not isinstance(
                item,
                dict,
            ):
                continue

            values.append(
                item.get(
                    "document_id"
                )
                or item.get(
                    "random_name"
                )
                or item.get(
                    "file_id"
                )
                or item.get(
                    "identifier"
                )
            )

    for key in (
        "identifier",
        "document_id",
        "file_id",
        "random_name",
    ):
        values.extend(
            request.form.getlist(key)
        )

    seen = set()
    identifiers = []

    for value in values:
        clean_value = str(
            value or ""
        ).strip()

        if (
            clean_value
            and clean_value not in seen
        ):
            identifiers.append(
                clean_value
            )
            seen.add(clean_value)

    return identifiers


def resolve_handoff_random_names(
    user_id: int,
    identifiers: list,
) -> list:
    """Resolve request identifiers to canonical authorized document ids."""

    random_names = []
    seen = set()

    for identifier in identifiers:
        registered_file = (
            resolve_registered_file_summary(
                user_id,
                identifier,
            )
        )
        random_name = (
            registered_file.get(
                "random_name"
            )
        )

        if (
            random_name
            and random_name not in seen
        ):
            random_names.append(
                random_name
            )
            seen.add(random_name)

    return random_names


def get_session_active_document_ids() -> list:
    """Return unique active workflow document ids from session."""

    active_ids = []
    seen = set()

    for key in ACTIVE_DOCUMENT_SESSION_KEYS:
        values = session.get(key)

        if isinstance(
            values,
            str,
        ):
            values = [values]

        if not isinstance(
            values,
            (
                list,
                tuple,
                set,
            ),
        ):
            continue

        for value in values:
            clean_value = str(
                value or ""
            ).strip()

            if (
                not clean_value
                or clean_value in seen
            ):
                continue

            active_ids.append(
                clean_value
            )
            seen.add(clean_value)

    return active_ids


def set_session_active_document_ids(
    document_ids: list,
) -> list:
    """Store canonical active workflow document ids in session."""

    clean_ids = []
    seen = set()

    for document_id in document_ids or []:
        clean_document_id = str(
            document_id or ""
        ).strip()

        if (
            not clean_document_id
            or clean_document_id in seen
        ):
            continue

        clean_ids.append(
            clean_document_id
        )
        seen.add(clean_document_id)

    for key in ACTIVE_DOCUMENT_SESSION_KEYS:
        if clean_ids:
            session[key] = list(
                clean_ids
            )
        else:
            session.pop(
                key,
                None,
            )

    if clean_ids:
        session[
            "document_operation_active_key"
        ] = WORKFLOW_DOCUMENT_ANALYSIS
    else:
        session.pop(
            "document_operation_active_key",
            None,
        )
        session.pop(
            "document_analysis_handoff_contract",
            None,
        )
        session.pop(
            "document_analysis_handoff_request_id",
            None,
        )

    session.modified = True

    return clean_ids


def get_active_documents_for_user(
    user_id: int,
) -> list:
    """Return active session documents reauthorized through SQL."""

    requested_ids = (
        get_session_active_document_ids()
    )
    authorized_documents = []
    authorized_ids = []

    for document_id in requested_ids:
        document = (
            resolve_registered_file_summary(
                user_id,
                document_id,
            )
        )

        if not document:
            continue

        document["active"] = True
        authorized_documents.append(
            document
        )
        authorized_ids.append(
            document["document_id"]
        )

    if authorized_ids != requested_ids:
        set_session_active_document_ids(
            authorized_ids
        )

    return authorized_documents


@files_bp.route(
    "/ai",
    methods=["GET"],
)
@login_required
def document_ai_workspace():
    """Reopen the active durable conversation or create one."""

    user_id = get_current_user_id()
    workspace_render = is_workspace_render_request()
    legacy_session_id = str(
        request.args.get(
            LEGACY_DOCUMENT_AI_SESSION_QUERY
        )
        or ""
    ).strip()

    if legacy_session_id:
        legacy_conversation = (
            get_solomon_ai_conversation(
                user_id=user_id,
                conversation_id=(
                    legacy_session_id
                ),
                include_messages=workspace_render,
            )
        )

        if legacy_conversation:
            set_active_solomon_ai_conversation(
                legacy_conversation
            )

            if workspace_render:
                return render_solomon_ai_workspace(
                    user_id=user_id,
                    workspace_session=legacy_conversation,
                )

            return redirect(
                build_solomon_ai_conversation_url(
                    legacy_session_id
                ),
                code=302,
            )

        if not workspace_render:
            return redirect(
                build_solomon_ai_conversation_url(
                    ""
                ),
                code=302,
            )

    active_conversation_id = (
        get_active_solomon_ai_conversation_id()
    )

    if active_conversation_id:
        active_conversation = (
            get_solomon_ai_conversation(
                user_id=user_id,
                conversation_id=(
                    active_conversation_id
                ),
                include_messages=workspace_render,
            )
        )

        if active_conversation:
            set_active_solomon_ai_conversation(
                active_conversation
            )

            logger.info(
                (
                    "[solomon_ai.active_conversation_reopened] "
                    "user_id=%s conversation_id=%s"
                ),
                user_id,
                active_conversation_id,
            )

            if workspace_render:
                return render_solomon_ai_workspace(
                    user_id=user_id,
                    workspace_session=active_conversation,
                )

            return redirect(
                build_solomon_ai_conversation_url(
                    active_conversation_id
                ),
                code=302,
            )

        logger.warning(
            (
                "[solomon_ai.active_conversation_pointer_cleared] "
                "user_id=%s conversation_id=%s"
            ),
            user_id,
            active_conversation_id,
        )
        clear_active_solomon_ai_conversation()

    latest_conversation = (
        get_latest_solomon_ai_conversation(
            user_id=user_id,
            include_messages=workspace_render,
        )
    )

    if latest_conversation:
        conversation_id = str(
            latest_conversation.get(
                "conversation_id"
            )
            or ""
        ).strip()

        set_active_solomon_ai_conversation(
            latest_conversation
        )

        logger.info(
            (
                "[solomon_ai.durable_conversation_reopened] "
                "user_id=%s conversation_id=%s"
            ),
            user_id,
            conversation_id,
        )

        if workspace_render:
            return render_solomon_ai_workspace(
                user_id=user_id,
                workspace_session=latest_conversation,
            )

        return redirect(
            build_solomon_ai_conversation_url(
                conversation_id
            ),
            code=302,
        )

    conversation = (
        create_solomon_ai_conversation(
            user_id=user_id,
        )
    )
    conversation_id = str(
        conversation.get(
            "conversation_id"
        )
        or ""
    ).strip()

    set_active_solomon_ai_conversation(
        conversation
    )

    logger.info(
        (
            "[solomon_ai.durable_conversation_created] "
            "user_id=%s conversation_id=%s"
        ),
        user_id,
        conversation_id,
    )

    if workspace_render:
        return render_solomon_ai_workspace(
            user_id=user_id,
            workspace_session=conversation,
        )

    return redirect(
        build_solomon_ai_conversation_url(
            conversation_id
        ),
        code=303,
    )


@files_bp.route(
    "/ai/c/<session_id>",
    methods=["GET"],
)
@login_required
def document_ai_conversation(
    session_id,
):
    """Render a durable SolomonAI conversation."""

    user_id = get_current_user_id()
    requested_session_id = str(
        session_id or ""
    ).strip()

    if not requested_session_id:
        return redirect(
            build_solomon_ai_conversation_url(
                ""
            ),
            code=303,
        )

    conversation = (
        get_solomon_ai_conversation(
            user_id=user_id,
            conversation_id=(
                requested_session_id
            ),
            include_messages=True,
        )
    )

    if not conversation:
        return redirect(
            build_solomon_ai_conversation_url(
                ""
            ),
            code=303,
        )

    return render_solomon_ai_workspace(
        user_id=user_id,
        workspace_session=conversation,
    )


@files_bp.route(
    "/uploads",
    methods=["POST"],
)
@login_required
def upload_file_api():
    """Store uploads and create canonical FileRegistry rows."""

    incoming_files = []

    if "file" in request.files:
        uploaded_file = (
            request.files.get("file")
        )

        if uploaded_file:
            incoming_files.append(
                uploaded_file
            )

    if "files" in request.files:
        incoming_files.extend(
            request.files.getlist(
                "files"
            )
        )

    if not incoming_files:
        return jsonify({
            "ok": False,
            "error": "Missing file",
        }), 400

    user_id = get_current_user_id()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": (
                "Authentication required"
            ),
        }), 401

    requested_folder_identifier = (
        get_requested_upload_folder_identifier()
    )
    workspace_folder_id, folder_error = (
        resolve_upload_workspace_folder_id(
            user_id,
            requested_folder_identifier,
        )
    )

    if folder_error:
        return jsonify({
            "ok": False,
            "error": "Parent folder not found",
            "contract": WORKSPACE_FOLDER_UPLOAD_CONTRACT,
        }), 404

    user_directory = os.path.join(
        settings.UPLOADS_DIR,
        str(user_id),
    )
    os.makedirs(
        user_directory,
        exist_ok=True,
    )

    saved_files = []

    for uploaded_file in incoming_files:
        if (
            not uploaded_file
            or not str(
                uploaded_file.filename
                or ""
            ).strip()
        ):
            continue

        original_name = clean_original_name(
            uploaded_file.filename
        )
        extension = get_upload_extension(
            original_name
        )
        file_handle = (
            create_public_file_handle()
        )
        storage_name = (
            f"{file_handle}{extension}"
        )
        save_path = os.path.join(
            user_directory,
            storage_name,
        )

        try:
            uploaded_file.save(
                save_path
            )

            registered_file = (
                create_file_registry_record(
                    original_name=(
                        original_name
                    ),
                    file_handle=(
                        file_handle
                    ),
                    path=save_path,
                    uploader_id=user_id,
                    workspace_folder_id=workspace_folder_id,
                )
            )

            saved_files.append(
                registered_file
            )
            session[
                "last_uploaded_file_id"
            ] = registered_file[
                "document_id"
            ]
            session[
                "last_uploaded_registry_id"
            ] = registered_file[
                "file_id"
            ]
        except Exception as exc:
            if os.path.exists(
                save_path
            ):
                os.remove(save_path)

            logger.error(
                "Failed to store uploaded file",
                extra={
                    "user_id": user_id,
                    "original_name": (
                        original_name
                    ),
                    "error": str(exc),
                },
            )

    if not saved_files:
        return jsonify({
            "ok": False,
            "error": (
                "No valid files uploaded"
            ),
        }), 400

    session.modified = True

    return jsonify({
        "ok": True,
        "count": len(saved_files),
        "workspace_folder_id": workspace_folder_id,
        "parent_folder_id": workspace_folder_id,
        "folder_upload_contract": (
            WORKSPACE_FOLDER_UPLOAD_CONTRACT
            if workspace_folder_id
            else ""
        ),
        "files": saved_files,
        "storage_contract": (
            "registered_file_only"
        ),
        "analysis_status": (
            "not_started"
        ),
        "handoff_required": True,
    }), 200


@files_bp.route(
    "/uploads/<identifier>/summary",
    methods=["GET"],
)
@login_required
def get_persisted_upload_summary(identifier):
    """Return only the current persisted Auto Summary for an authorized file."""

    user_id = get_current_user_id()
    clean_identifier = str(
        identifier or ""
    ).strip()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Authentication required",
        }), 401

    if not clean_identifier:
        return jsonify({
            "ok": False,
            "error": "Document not found",
        }), 404

    authorized_file = resolve_authorized_file_registry_entry(
        user_id,
        clean_identifier,
        request_id=get_request_id(),
        action=READ_ACTION,
    )

    if not authorized_file:
        return jsonify({
            "ok": False,
            "error": "Document not found or not available",
        }), 404

    if str(
        authorized_file.get("document_status")
        or ""
    ).strip().lower() != "active":
        return jsonify({
            "ok": False,
            "error": "Summary is not available for this document state",
        }), 409

    payload = resolve_persisted_auto_summary_state(
        authorized_file
    )

    logger.info(
        (
            "[files.auto_summary_view] user_id=%s document_id=%s "
            "summary_state=%s job_status=%s request_id=%s"
        ),
        user_id,
        payload.get("document_id"),
        payload.get("summary_state"),
        payload.get("job_status"),
        get_request_id(),
    )

    return jsonify(payload), 200


@files_bp.route(
    "/uploads/<identifier>/summary/download",
    methods=["GET"],
)
@login_required
def download_persisted_upload_summary(identifier):
    """Download the current persisted Auto Summary as a PDF."""

    user_id = get_current_user_id()
    clean_identifier = str(
        identifier or ""
    ).strip()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Authentication required",
        }), 401

    if not clean_identifier:
        return jsonify({
            "ok": False,
            "error": "Document not found",
        }), 404

    authorized_file = resolve_authorized_file_registry_entry(
        user_id,
        clean_identifier,
        request_id=get_request_id(),
        action=READ_ACTION,
    )

    if not authorized_file:
        return jsonify({
            "ok": False,
            "error": "Document not found or not available",
        }), 404

    if str(
        authorized_file.get("document_status")
        or ""
    ).strip().lower() != "active":
        return jsonify({
            "ok": False,
            "error": "Summary is not available for this document state",
        }), 409

    payload = resolve_persisted_auto_summary_state(
        authorized_file
    )

    if (
        str(
            payload.get("summary_state")
            or ""
        ).strip().lower()
        != AUTO_SUMMARY_VIEW_STATE_READY
        or not str(
            payload.get("detailed_summary")
            or ""
        ).strip()
    ):
        return jsonify({
            "ok": False,
            "error": "A current saved summary is not available for this file version",
        }), 409

    try:
        pdf_stream = _build_persisted_summary_pdf(
            payload
        )
    except Exception as exc:
        logger.exception(
            (
                "[files.auto_summary_download_failed] user_id=%s document_id=%s "
                "request_id=%s error=%s"
            ),
            user_id,
            payload.get("document_id"),
            get_request_id(),
            exc,
        )
        return jsonify({
            "ok": False,
            "error": "The saved summary could not be exported",
        }), 503

    logger.info(
        (
            "[files.auto_summary_download] user_id=%s document_id=%s "
            "summary_hash=%s request_id=%s"
        ),
        user_id,
        payload.get("document_id"),
        payload.get("summary_hash"),
        get_request_id(),
    )

    response = send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=_summary_download_name(
            payload.get("original_name")
            or "Document"
        ),
        max_age=0,
    )
    response.headers["Cache-Control"] = "private, no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@files_bp.route(
    "/uploads/intelligence/enrich",
    methods=["POST"],
)
@login_required
def enrich_upload_intelligence():
    """Explicitly enrich registered uploads owned by the uploader."""

    user_id = get_current_user_id()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": (
                "Authentication required"
            ),
        }), 401

    identifiers = collect_handoff_identifiers()

    if not identifiers:
        latest_identifier = str(
            session.get(
                "last_uploaded_file_id"
            )
            or ""
        ).strip()

        if latest_identifier:
            identifiers = [
                latest_identifier
            ]

    if not identifiers:
        return jsonify({
            "ok": False,
            "error": (
                "No document identifiers supplied"
            ),
        }), 400

    db_session = SessionLocal()
    results = []

    try:
        for identifier in identifiers:
            clean_identifier = str(
                identifier or ""
            ).strip()

            if not clean_identifier:
                continue

            record = resolve_uploader_file_registry_record(
                db_session,
                user_id,
                clean_identifier,
            )

            if not record:
                results.append({
                    "ok": False,
                    "status": "not_found",
                    "identifier": clean_identifier,
                    "error": (
                        "Document was not found or is not available "
                        "for uploader-owned enrichment."
                    ),
                })
                continue

            path = str(
                record.path or ""
            ).strip()

            if (
                not path
                or not os.path.isfile(path)
            ):
                results.append({
                    "ok": False,
                    "status": "file_missing",
                    "document_id": record.random_name,
                    "file_id": str(record.id),
                    "original_name": record.original_name,
                    "error": (
                        "Registered file path is missing or unreadable."
                    ),
                })
                continue

            metadata = _safe_meta_payload(
                record.meta
            )
            intelligence_object = enrich_file_intelligence_object(
                db_session=db_session,
                record=record,
                metadata=metadata,
            )

            if not intelligence_object:
                results.append({
                    "ok": False,
                    "status": "not_enriched",
                    "document_id": record.random_name,
                    "file_id": str(record.id),
                    "original_name": record.original_name,
                    "error": (
                        "Workspace intelligence object could not be "
                        "created."
                    ),
                })
                continue

            update_file_registry_intelligence_metadata(
                record=record,
                intelligence_object=intelligence_object,
            )

            index_status = str(
                getattr(
                    intelligence_object,
                    "index_status",
                    None,
                )
                or ""
            ).strip()

            extraction_status = str(
                getattr(
                    intelligence_object,
                    "extraction_status",
                    None,
                )
                or ""
            ).strip()

            result_status = (
                "skipped"
                if extraction_status == "skipped"
                else "enriched"
                if index_status == "ready"
                else "not_enriched"
            )

            error_message = str(
                getattr(
                    intelligence_object,
                    "error_message",
                    "",
                )
                or ""
            ).strip()

            results.append(
                build_upload_intelligence_result(
                    record=record,
                    intelligence_object=intelligence_object,
                    status=result_status,
                    error=error_message,
                )
            )

        db_session.commit()

        enriched_count = sum(
            1
            for result in results
            if result.get("status")
            in {
                "enriched",
                "skipped",
            }
        )

        return jsonify({
            "ok": enriched_count > 0,
            "count": len(results),
            "enriched_count": enriched_count,
            "results": results,
            "workspace_intelligence_contract": (
                "explicit_upload_enrichment_v1"
            ),
        }), (
            200
            if enriched_count > 0
            else 404
        )

    except Exception as exc:
        db_session.rollback()
        logger.exception(
            "[uploads.intelligence_enrichment_failed]",
            extra={
                "user_id": user_id,
                "error": str(exc),
            },
        )

        return jsonify({
            "ok": False,
            "error": (
                "Workspace intelligence enrichment failed"
            ),
        }), 500
    finally:
        db_session.close()


@files_bp.route(
    "/uploads/use/document-analysis",
    methods=["POST"],
)
@login_required
def use_uploads_in_document_analysis():
    """Select stored authorized documents for Document Analysis."""

    user_id = get_current_user_id()

    if not user_id:
        return handoff_response({
            "ok": False,
            "error": (
                "Authentication required"
            ),
            "workflow_key": (
                WORKFLOW_DOCUMENT_ANALYSIS
            ),
        }, 401)

    identifiers = (
        collect_handoff_identifiers()
    )
    document_ids = (
        resolve_handoff_random_names(
            user_id,
            identifiers,
        )
    )

    if not document_ids:
        return handoff_response({
            "ok": False,
            "error": (
                "No valid authorized documents selected"
            ),
            "workflow_key": (
                WORKFLOW_DOCUMENT_ANALYSIS
            ),
        }, 400)

    set_session_active_document_ids(
        document_ids
    )

    session[
        "document_analysis_handoff_contract"
    ] = DOCUMENT_ANALYSIS_SESSION_CONTRACT
    session[
        "document_analysis_handoff_request_id"
    ] = uuid.uuid4().hex
    session.modified = True

    documents = (
        get_active_documents_for_user(
            user_id
        )
    )

    return handoff_response({
        "ok": True,
        "workflow_key": (
            WORKFLOW_DOCUMENT_ANALYSIS
        ),
        "handoff_contract": (
            DOCUMENT_ANALYSIS_HANDOFF_CONTRACT
        ),
        "analysis_status": (
            "not_started"
        ),
        "active": {
            "docs": documents,
        },
        "backend_process": {
            "label": (
                "Run backend Document Analysis"
            ),
            "target": (
                DOCUMENT_ANALYSIS_EXECUTE_ENDPOINT
            ),
            "method": "POST",
            "type": "backend_process",
        },
        "next": {
            "label": (
                "Stay in Documents"
            ),
            "target": (
                DOCUMENT_ANALYSIS_SAFE_STAY_TARGET
            ),
            "type": (
                "stay_on_current_workspace"
            ),
        },
    }, 200)


@files_bp.route(
    "/uploads/active",
    methods=["GET"],
)
@login_required
def get_active_files():
    """Return the authorized active workflow documents."""

    user_id = get_current_user_id()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": (
                "Authentication required"
            ),
        }), 401

    documents = (
        get_active_documents_for_user(
            user_id
        )
    )

    return jsonify({
        "ok": True,
        "docs": documents,
        "active": {
            "docs": documents,
        },
    }), 200


@files_bp.route(
    "/uploads/active/<identifier>",
    methods=["DELETE"],
)
@login_required
def remove_active_file(
    identifier,
):
    """Remove one document from the active workflow selection."""

    user_id = get_current_user_id()
    clean_identifier = str(
        identifier or ""
    ).strip()

    registered_file = (
        resolve_registered_file_summary(
            user_id,
            clean_identifier,
        )
    )
    document_id = str(
        registered_file.get(
            "document_id"
        )
        or clean_identifier
    ).strip()

    active_ids = (
        get_session_active_document_ids()
    )

    if document_id not in active_ids:
        logger.warning(
            "Attempted delete of non-active file",
            extra={
                "user_id": user_id,
                "identifier": (
                    clean_identifier
                ),
            },
        )

        return jsonify({
            "ok": False,
            "error": (
                "File not in active set"
            ),
        }), 404

    remaining_ids = [
        active_id
        for active_id in active_ids
        if active_id != document_id
    ]

    set_session_active_document_ids(
        remaining_ids
    )

    documents = (
        get_active_documents_for_user(
            user_id
        )
    )

    return jsonify({
        "ok": True,
        "active": {
            "docs": documents,
        },
    }), 200


@files_bp.route(
    "/admin/uploads",
    methods=["GET"],
)
@files_bp.route(
    "/admin/uploads/",
    methods=["GET"],
)
@login_required
@admin_required
def uploads_ui():
    """Render the platform upload inspection page."""

    return render_template(
        "uploads.html"
    )


@files_bp.route(
    "/admin/uploads/data",
    methods=["GET"],
)
@login_required
@admin_required
def list_uploads():
    """Return platform upload inspection data."""

    try:
        uploads = (
            file_resolver.list_all_files()
        )

        return jsonify({
            "status": "ok",
            "count": len(uploads),
            "uploads": uploads,
        }), 200
    except Exception as exc:
        return jsonify({
            "status": "error",
            "message": (
                "Failed to list uploads: "
                f"{exc}"
            ),
        }), 500


__all__ = [
    "files_bp",
]