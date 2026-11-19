# -------------------------------------------------------------------
# FILE: document_operations_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Backend document operation routes for selected workspace files.
# -------------------------------------------------------------------

from pathlib import Path
from html import unescape
from urllib.parse import quote
import csv
import io
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET

from flask import Blueprint, g, jsonify, redirect, render_template, request, session, url_for

from solomon_core.auth_utils import login_required
from solomon_core.document_operations import (
    get_document_operation,
    list_document_operations,
)
from solomon_core.document_operations.operation_jobs import (
    DocumentOperationJobError,
    get_document_operation_job_packet,
    register_document_operation_runner,
    submit_document_operation_job,
)
from solomon_core.document_operations.saved_reviews import get_saved_review, load_saved_reviews
from solomon_core.intelligence_service.intelligence_service_client import (
    get_intelligence_service_health,
    request_intelligence_service_recovery,
)
from solomon_core.llm.llm_transport import (
    direct_model_files_available,
    select_backend,
)
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.bei.bei_report_pipeline import (
    build_bei_report_packet as build_document_analysis_report_packet,
)
from solomon_core.solomon_ai_conversation_store import (
    SolomonAIConversationStoreError,
    create_solomon_ai_conversation as create_durable_solomon_ai_conversation,
    delete_solomon_ai_conversation as delete_durable_solomon_ai_conversation,
    get_solomon_ai_conversation as get_durable_solomon_ai_conversation,
    rename_solomon_ai_conversation as rename_durable_solomon_ai_conversation,
    replace_solomon_ai_conversation_sources,
    set_solomon_ai_conversation_public_web,
)
from solomon_core.workspace_reader.workspace_reader_file_access import (
    resolve_authorized_file_registry_entry,
)
from solomon_core.workspace_reader.workspace_reader_file_catalog import (
    SUPPORTED_SCOPES,
    list_authorized_file_catalog,
)

document_operations_bp = Blueprint(
    "document_operations_bp",
    __name__,
    url_prefix="/workspace/document-operation",
)

solomon_conversations_bp = Blueprint(
    "solomon_conversations_bp",
    __name__,
    url_prefix="/workspace/solomon",
)

logger = get_logger("document_operations_bp")

DOCUMENT_OPERATION_HANDOFF_CONTRACT = "document_operation_explicit_backend_execution"
SOLOMON_AI_CONVERSATION_CONTRACT = "document_ai_explicit_source_session"
SOLOMON_AI_SOURCE_MEMBERSHIP_CONTRACT = (
    "solomon_ai_conversation_source_membership_v1"
)
DOCUMENT_ANALYSIS_OPERATION_KEY = "document_analysis"
DOCUMENT_ANALYSIS_OPERATION_LABEL = "Document Analysis"
SOLOMON_AI_CONVERSATION_OPERATION_KEY = "ask_solomon_ai"
SOLOMON_AI_CONVERSATION_LABEL = "Ask SolomonAI"
REPORT_SURFACE_TEMPLATE = "components/workspace_document_report_surface.html"
REPORT_FRAGMENT_TEMPLATE = "components/workspace_document_report_fragment.html"

AUTHORIZED_DOCUMENT_AUTHORITY_FIELDS = (
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

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_HTML_BREAK_RE = re.compile(r"(?i)<\s*br\s*/?\s*>")
_HTML_HEADING_OPEN_RE = re.compile(r"(?i)<\s*h[1-6][^>]*>")
_HTML_HEADING_CLOSE_RE = re.compile(r"(?i)</\s*h[1-6]\s*>")
_HTML_LIST_ITEM_OPEN_RE = re.compile(r"(?i)<\s*li[^>]*>")
_HTML_LIST_ITEM_CLOSE_RE = re.compile(r"(?i)</\s*li\s*>")
_HTML_BLOCK_RE = re.compile(r"(?i)</\s*(?:div|p|section|article|tr)\s*>")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_REPORT_SOURCE_READOUT_RE = re.compile(
    r"(?i)(?:^|\s)([A-Z0-9][A-Z0-9 _.,()&'#/+–—-]{0,160}\."
    r"(?:pdf|docx|txt|csv|xlsx|xls))\s+SolomonAI\s+Readout(?=[A-Z0-9])"
)
_WORD_XML_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

SUPPORTED_DOCUMENT_ANALYSIS_SUFFIXES = frozenset({
    ".pdf",
    ".docx",
    ".txt",
    ".csv",
})

REPORT_SECTION_TITLES = (
    "Document Summary",
    "Executive Snapshot",
    "Key Details",
    "Risk Signals",
    "Missing Information",
    "Commercial Terms",
    "Recommended Next Steps",
)


class DocumentOperationError(Exception):
    """Raised when a document operation cannot prepare or execute safely."""


def get_request_id() -> str:
    """Return the active request id."""

    return getattr(g, "request_id", None) or str(uuid.uuid4())


def get_current_user_id() -> int:
    """Return the authenticated user id from session state."""

    try:
        return int(session.get("user_id") or 0)
    except (TypeError, ValueError):
        return 0


def operation_error(error_code, user_output, *, status_code=400, extra=None):
    """Return a normalized document operation error."""

    payload = {
        "ok": False,
        "packet_type": "document_operation_result",
        "error": error_code,
        "user_output": user_output,
        "request_id": get_request_id(),
    }

    if extra:
        payload.update(extra)

    return jsonify(payload), status_code


def solomon_ai_conversation_error(
    error_code,
    user_output,
    *,
    status_code=400,
    legacy_response=False,
):
    """Return a normalized SolomonAI conversation error."""

    payload = {
        "ok": False,
        "packet_type": (
            "document_ai_session"
            if legacy_response
            else "solomon_ai_conversation"
        ),
        "artifact_type": (
            "source_session"
            if legacy_response
            else "source_conversation"
        ),
        "error": error_code,
        "user_output": user_output,
        "operation": SOLOMON_AI_CONVERSATION_OPERATION_KEY,
        "request_id": get_request_id(),
    }

    return jsonify(payload), status_code


def read_operation_payload() -> dict:
    """Return a safe JSON payload for a document operation request."""

    payload = request.get_json(silent=True)

    return payload if isinstance(payload, dict) else {}


def read_operation_form_payload() -> dict:
    """Return a normalized form payload for a document operation request."""

    payload = {}

    for key in ("operation", "document_id", "file_id", "random_name", "identifier"):
        value = request.form.get(key)
        if value:
            payload[key] = value

    for key in ("document_ids", "file_ids", "random_names", "identifiers"):
        values = request.form.getlist(key)
        if values:
            payload[key] = values

    return payload


def read_operation_request_payload() -> dict:
    """Return JSON or form payload for a document operation request."""

    if request.is_json:
        return read_operation_payload()

    return read_operation_form_payload()


def collect_document_ids(payload: dict) -> list:
    """Collect selected document ids from operation payload variants."""

    values = []

    for key in ("document_id", "file_id", "random_name", "identifier"):
        value = payload.get(key)
        if value:
            values.append(value)

    for key in ("document_ids", "file_ids", "random_names", "identifiers"):
        value = payload.get(key)
        if isinstance(value, list):
            values.extend(value)

    documents = payload.get("documents")
    if isinstance(documents, list):
        for item in documents:
            if isinstance(item, str):
                values.append(item)
                continue

            if not isinstance(item, dict):
                continue

            values.append(
                item.get("document_id")
                or item.get("random_name")
                or item.get("file_id")
                or item.get("identifier")
            )

    seen = set()
    document_ids = []

    for value in values:
        clean_value = str(value or "").strip()
        if clean_value and clean_value not in seen:
            document_ids.append(clean_value)
            seen.add(clean_value)

    return document_ids


def collect_query_document_ids() -> list:
    """Collect selected document ids from report-page query arguments."""

    values = []

    for key in ("document_id", "file_id", "random_name", "identifier"):
        value = request.args.get(key)
        if value:
            values.append(value)

    for key in ("document_ids", "file_ids", "random_names", "identifiers"):
        values.extend(request.args.getlist(key))

    seen = set()
    document_ids = []

    for value in values:
        clean_value = str(value or "").strip()
        if clean_value and clean_value not in seen:
            document_ids.append(clean_value)
            seen.add(clean_value)

    return document_ids


def resolve_authorized_document(user_id: int, identifier: str) -> dict:
    """Resolve an authorized FileRegistry document into operation metadata."""

    clean_identifier = str(identifier or "").strip()

    if not clean_identifier or not user_id:
        return {}

    authorized_file = resolve_authorized_file_registry_entry(
        user_id,
        clean_identifier,
        request_id=get_request_id(),
    )

    if not authorized_file:
        return {}

    document_id = str(
        authorized_file.get("document_id")
        or authorized_file.get("random_name")
        or ""
    ).strip()
    original_name = str(
        authorized_file.get("original_name")
        or document_id
    ).strip()

    if not document_id:
        return {}

    document = {
        "document_id": document_id,
        "file_id": str(authorized_file.get("file_id") or "").strip(),
        "random_name": document_id,
        "original_name": original_name,
        "filename": original_name,
        "size_bytes": authorized_file.get("size_bytes"),
        "resolved_path": authorized_file.get("path"),
        "selected_for_workflow": True,
        "handoff_contract": DOCUMENT_OPERATION_HANDOFF_CONTRACT,
        "analysis_status": "not_started",
    }

    for field_name in AUTHORIZED_DOCUMENT_AUTHORITY_FIELDS:
        field_value = authorized_file.get(field_name)

        if field_value not in (None, ""):
            document[field_name] = field_value

    return document


def resolve_authorized_documents(user_id: int, document_ids: list) -> list:
    """Resolve selected document ids into authorized document records."""

    documents = []
    seen = set()

    for document_id in document_ids:
        document = resolve_authorized_document(user_id, document_id)
        random_name = document.get("random_name")

        if random_name and random_name not in seen:
            documents.append(document)
            seen.add(random_name)

    return documents


def prepare_operation_context(operation_key: str, document_ids: list) -> tuple:
    """Validate and prepare one document operation execution context."""

    operation = get_document_operation(operation_key)

    if not operation:
        raise DocumentOperationJobError(
            "DocumentOperationNotFound",
            "The requested document operation is not available.",
            status_code=404,
        )

    user_id = get_current_user_id()

    if not user_id:
        raise DocumentOperationJobError(
            "AuthenticationRequired",
            "Authentication is required to run document operations.",
            status_code=401,
        )

    if operation.requires_documents and not document_ids:
        raise DocumentOperationJobError(
            "DocumentOperationMissingDocuments",
            "Select at least one stored document before running this operation.",
            status_code=400,
        )

    documents = resolve_authorized_documents(user_id, document_ids)

    if operation.requires_documents and not documents:
        raise DocumentOperationJobError(
            "DocumentOperationNoAuthorizedDocuments",
            "No valid authorized documents were available for this operation.",
            status_code=404,
        )

    session["document_operation_active_key"] = operation.key
    session["document_operation_active_document_ids"] = [
        document.get("document_id") for document in documents
    ]
    session.modified = True

    return user_id, operation, documents


def get_active_solomon_ai_conversation() -> dict:
    """Return the lightweight active conversation pointer from session state."""

    active_conversation = session.get(
        "solomon_ai_active_conversation"
    )

    if not isinstance(active_conversation, dict):
        active_conversation = session.get(
            "document_ai_active_session"
        )

    return (
        active_conversation
        if isinstance(active_conversation, dict)
        else {}
    )



def normalize_solomon_ai_organization_context(
    conversation_packet: dict,
) -> dict:
    """Return the validated organization context from a conversation packet."""

    raw_context = (
        conversation_packet.get("organization_context")
        if isinstance(
            conversation_packet.get("organization_context"),
            dict,
        )
        else {}
    )

    return {
        "is_bound": bool(raw_context.get("is_bound")),
        "is_active": bool(
            raw_context.get("is_active", True)
        ),
        "organization_id": str(
            raw_context.get("organization_id")
            or ""
        ).strip(),
        "membership_id": raw_context.get(
            "membership_id"
        ),
    }


def build_solomon_ai_file_picker_item(
    file_packet: dict,
    *,
    attached_document_ids: set,
) -> dict:
    """Build one browser-safe existing-file selection item."""

    document_id = str(
        file_packet.get("document_id")
        or file_packet.get("random_name")
        or ""
    ).strip()
    original_name = str(
        file_packet.get("original_name")
        or document_id
    ).strip()
    access_scope = str(
        file_packet.get("access_scope")
        or ""
    ).strip().lower()
    attached = bool(
        document_id
        and document_id in attached_document_ids
    )

    return {
        "document_id": document_id,
        "original_name": original_name,
        "filename": original_name,
        "extension": str(
            file_packet.get("extension")
            or ""
        ).strip().lower(),
        "size_bytes": file_packet.get(
            "size_bytes"
        ),
        "uploaded_at": str(
            file_packet.get("uploaded_at")
            or ""
        ).strip(),
        "updated_at": str(
            file_packet.get("updated_at")
            or ""
        ).strip(),
        "reader_url": str(
            file_packet.get("reader_url")
            or file_packet.get("workspace_reader_url")
            or ""
        ).strip(),
        "workspace_reader_url": str(
            file_packet.get("workspace_reader_url")
            or file_packet.get("reader_url")
            or ""
        ).strip(),
        "access_scope": access_scope,
        "permission": str(
            file_packet.get("permission")
            or ""
        ).strip().lower(),
        "organization_id": str(
            file_packet.get("organization_id")
            or ""
        ).strip(),
        "attached": attached,
        "selectable": bool(
            document_id
            and not attached
        ),
    }


def build_solomon_ai_file_catalog_response(
    *,
    conversation_packet: dict,
    file_catalog: list,
    request_id: str,
    requested_scope: str = "",
    search_query: str = "",
) -> dict:
    """Build the conversation-scoped existing-file picker packet."""

    conversation_id = str(
        conversation_packet.get("conversation_id")
        or conversation_packet.get("session_id")
        or ""
    ).strip()
    attached_document_ids = {
        str(document_id or "").strip()
        for document_id in (
            conversation_packet.get("document_ids")
            if isinstance(
                conversation_packet.get("document_ids"),
                list,
            )
            else []
        )
        if str(document_id or "").strip()
    }
    normalized_query = str(
        search_query or ""
    ).strip().casefold()
    scope_counts = {
        scope: 0
        for scope in sorted(SUPPORTED_SCOPES)
    }
    files = []

    for file_packet in file_catalog:
        if not isinstance(file_packet, dict):
            continue

        picker_item = build_solomon_ai_file_picker_item(
            file_packet,
            attached_document_ids=attached_document_ids,
        )

        if not picker_item["document_id"]:
            continue

        searchable_text = " ".join([
            picker_item["original_name"],
            picker_item["extension"],
            picker_item["access_scope"],
        ]).casefold()

        if (
            normalized_query
            and normalized_query not in searchable_text
        ):
            continue

        access_scope = picker_item["access_scope"]

        if access_scope in scope_counts:
            scope_counts[access_scope] += 1

        files.append(picker_item)

    return {
        "ok": True,
        "packet_type": "solomon_ai_available_files",
        "artifact_type": "file_catalog",
        "contract": SOLOMON_AI_SOURCE_MEMBERSHIP_CONTRACT,
        "conversation_id": conversation_id,
        "conversation_url": get_solomon_ai_conversation_url(
            conversation_id
        ),
        "organization_context": (
            normalize_solomon_ai_organization_context(
                conversation_packet
            )
        ),
        "scope": requested_scope or "all",
        "query": str(search_query or "").strip(),
        "count": len(files),
        "available_count": sum(
            1
            for item in files
            if item["selectable"]
        ),
        "attached_count": len(
            attached_document_ids
        ),
        "scope_counts": scope_counts,
        "files": files,
        "status": "ready",
        "request_id": request_id,
    }


def get_solomon_ai_source_store_error_status(
    error: Exception,
) -> int:
    """Return an appropriate HTTP status for a source persistence error."""

    message = str(error or "").strip().casefold()

    if "not found" in message:
        return 404

    if any(
        marker in message
        for marker in (
            "different organizations",
            "organization context",
            "do not match",
            "no longer active",
            "membership",
        )
    ):
        return 409

    if any(
        marker in message
        for marker in (
            "invalid",
            "selected documents",
            "required",
        )
    ):
        return 400

    return 500


def build_solomon_ai_source_response(
    *,
    conversation_packet: dict,
    request_id: str,
    source_action: str,
) -> dict:
    """Build the canonical conversation-scoped source membership packet."""

    sources = (
        conversation_packet.get("sources")
        if isinstance(
            conversation_packet.get("sources"),
            list,
        )
        else []
    )
    document_ids = [
        str(source.get("document_id") or "").strip()
        for source in sources
        if isinstance(source, dict)
        and str(source.get("document_id") or "").strip()
    ]
    document_names = [
        str(source.get("original_name") or "").strip()
        for source in sources
        if isinstance(source, dict)
        and str(source.get("original_name") or "").strip()
    ]
    conversation_id = str(
        conversation_packet.get("conversation_id")
        or conversation_packet.get("session_id")
        or ""
    ).strip()

    return {
        "ok": True,
        "packet_type": "solomon_ai_conversation_sources",
        "artifact_type": "source_membership",
        "contract": SOLOMON_AI_SOURCE_MEMBERSHIP_CONTRACT,
        "conversation_id": conversation_id,
        "conversation_url": get_solomon_ai_conversation_url(
            conversation_id
        ),
        "source_action": source_action,
        "organization_context": (
            normalize_solomon_ai_organization_context(
                conversation_packet
            )
        ),
        "document_ids": document_ids,
        "document_names": document_names,
        "source_count": len(document_ids),
        "sources": sources,
        "public_web_selected": bool(
            conversation_packet.get("public_web_selected")
        ),
        "status": "ready",
        "request_id": request_id,
    }


def build_solomon_ai_conversation_response(
    *,
    conversation_packet: dict,
    request_id: str,
    conversation_action: str,
) -> dict:
    """Build the canonical conversation creation/update packet."""

    sources = (
        conversation_packet.get("sources")
        if isinstance(
            conversation_packet.get("sources"),
            list,
        )
        else []
    )
    document_ids = [
        str(source.get("document_id") or "").strip()
        for source in sources
        if isinstance(source, dict)
        and str(source.get("document_id") or "").strip()
    ]
    document_names = [
        str(source.get("original_name") or "").strip()
        for source in sources
        if isinstance(source, dict)
        and str(source.get("original_name") or "").strip()
    ]
    conversation_id = str(
        conversation_packet.get("conversation_id")
        or conversation_packet.get("session_id")
        or ""
    ).strip()

    return {
        "ok": True,
        "packet_type": "solomon_ai_conversation",
        "artifact_type": "source_conversation",
        "conversation_id": conversation_id,
        "conversation_url": get_solomon_ai_conversation_url(
            conversation_id
        ),
        "conversation_action": conversation_action,
        "organization_context": (
            normalize_solomon_ai_organization_context(
                conversation_packet
            )
        ),
        "document_ids": document_ids,
        "document_names": document_names,
        "document_count": len(document_ids),
        "sources": sources,
        "public_web_selected": bool(
            conversation_packet.get("public_web_selected")
        ),
        "status": "ready",
        "request_id": request_id,
    }


def store_solomon_ai_conversation(
    *,
    conversation_packet: dict,
    request_id: str,
) -> dict:
    """Store only a compatibility pointer to durable conversation state."""

    durable_packet = (
        conversation_packet
        if isinstance(conversation_packet, dict)
        else {}
    )
    conversation_id = str(
        durable_packet.get("conversation_id")
        or durable_packet.get("session_id")
        or ""
    ).strip()
    user_id = int(
        durable_packet.get("user_id")
        or 0
    )
    sources = (
        durable_packet.get("sources")
        if isinstance(
            durable_packet.get("sources"),
            list,
        )
        else []
    )
    source_ids = [
        str(source.get("document_id") or "").strip()
        for source in sources
        if isinstance(source, dict)
        and str(source.get("document_id") or "").strip()
    ]
    source_names = [
        str(source.get("original_name") or "").strip()
        for source in sources
        if isinstance(source, dict)
        and str(source.get("original_name") or "").strip()
    ]
    organization_context = (
        normalize_solomon_ai_organization_context(
            durable_packet
        )
    )
    session_packet = {
        "conversation_id": conversation_id,
        "session_id": conversation_id,
        "user_id": user_id,
        "contract": str(
            durable_packet.get("contract")
            or SOLOMON_AI_CONVERSATION_CONTRACT
        ).strip(),
        "operation": str(
            durable_packet.get("operation")
            or SOLOMON_AI_CONVERSATION_OPERATION_KEY
        ).strip(),
        "operation_label": str(
            durable_packet.get("operation_label")
            or SOLOMON_AI_CONVERSATION_LABEL
        ).strip(),
        "request_id": request_id,
        "source_membership_contract": str(
            durable_packet.get("source_membership_contract")
            or SOLOMON_AI_SOURCE_MEMBERSHIP_CONTRACT
        ).strip(),
        "organization_context": organization_context,
        "document_ids": source_ids,
        "document_names": source_names,
        "source_count": len(source_ids),
        "sources": sources,
        "public_web_selected": bool(
            durable_packet.get("public_web_selected")
        ),
    }

    session["solomon_ai_active_conversation"] = session_packet
    session["solomon_ai_active_conversation_id"] = conversation_id
    session["solomon_ai_active_document_ids"] = source_ids
    session["solomon_ai_active_document_names"] = source_names

    # Temporary compatibility for server readers still using the prior keys.
    session["document_ai_active_session"] = session_packet
    session["document_ai_active_session_id"] = conversation_id
    session["document_ai_active_document_ids"] = source_ids
    session["document_ai_active_document_names"] = source_names
    session.modified = True

    return session_packet


def clear_active_solomon_ai_conversation(
    conversation_id: str,
) -> bool:
    """Clear compatibility pointers when the active conversation is deleted."""

    clean_conversation_id = str(
        conversation_id or ""
    ).strip()
    active_packet = get_active_solomon_ai_conversation()
    active_conversation_id = str(
        session.get("solomon_ai_active_conversation_id")
        or active_packet.get("conversation_id")
        or active_packet.get("session_id")
        or ""
    ).strip()

    if (
        not clean_conversation_id
        or active_conversation_id != clean_conversation_id
    ):
        return False

    for key in (
        "solomon_ai_active_conversation",
        "solomon_ai_active_conversation_id",
        "solomon_ai_active_document_ids",
        "solomon_ai_active_document_names",
        "document_ai_active_session",
        "document_ai_active_session_id",
        "document_ai_active_document_ids",
        "document_ai_active_document_names",
    ):
        session.pop(key, None)

    session.modified = True

    return True


def get_solomon_ai_conversation_url(conversation_id: str) -> str:
    """Return the canonical public SolomonAI conversation URL."""

    clean_conversation_id = str(conversation_id or "").strip()

    if not clean_conversation_id:
        return "/ai"

    safe_conversation_id = quote(
        clean_conversation_id,
        safe="",
    )

    return f"/ai/c/{safe_conversation_id}"


def get_solomon_ai_documents_url() -> str:
    """Return the canonical Documents workspace URL."""

    return "/"


def sanitize_extracted_text(value: str) -> str:
    """Return normalized text for document analysis input."""

    if not isinstance(value, str) or not value.strip():
        return ""

    cleaned = _CONTROL_CHAR_RE.sub(" ", value)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def decode_text_bytes(data: bytes, file_name: str) -> str:
    """Decode text bytes using common document encodings."""

    last_error = None

    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except Exception as exc:
            last_error = exc

    raise DocumentOperationError(
        f"Could not decode text from {file_name}: {last_error}"
    )


def extract_pdf_text(path: Path) -> str:
    """Extract text from a PDF for document analysis."""

    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(str(path))
    except Exception as exc:
        raise DocumentOperationError(
            f"PDF extraction failed opening {path.name}."
        ) from exc

    pages = []

    for page_index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise DocumentOperationError(
                f"PDF extraction failed on page {page_index + 1} of {path.name}."
            ) from exc

        if text.strip():
            pages.append(text.strip())

    return sanitize_extracted_text("\n\n".join(pages))


def extract_docx_part_text(zip_file: zipfile.ZipFile, member_name: str) -> str:
    """Extract readable text from one DOCX XML member."""

    try:
        root = ET.fromstring(zip_file.read(member_name))
    except Exception:
        return ""

    lines = []

    for paragraph in root.iter(f"{_WORD_XML_NAMESPACE}p"):
        fragments = [
            node.text
            for node in paragraph.iter(f"{_WORD_XML_NAMESPACE}t")
            if node.text
        ]
        line = "".join(fragments).strip()

        if line:
            lines.append(line)

    return "\n".join(lines).strip()


def extract_docx_text(path: Path) -> str:
    """Extract DOCX text from the zipped XML body."""

    try:
        with zipfile.ZipFile(str(path)) as archive:
            names = archive.namelist()
            members = ["word/document.xml"]
            members.extend(
                sorted(
                    name for name in names
                    if name.startswith("word/header") and name.endswith(".xml")
                )
            )
            members.extend(
                sorted(
                    name for name in names
                    if name.startswith("word/footer") and name.endswith(".xml")
                )
            )

            blocks = [
                extract_docx_part_text(archive, member)
                for member in members
                if member in names
            ]
    except Exception as exc:
        raise DocumentOperationError(
            f"DOCX extraction failed for {path.name}."
        ) from exc

    return sanitize_extracted_text("\n\n".join(block for block in blocks if block))


def extract_plain_text(path: Path) -> str:
    """Extract TXT text for document analysis input."""

    return sanitize_extracted_text(decode_text_bytes(path.read_bytes(), path.name))


def extract_csv_text(path: Path) -> str:
    """Extract CSV rows into readable line text."""

    raw_text = decode_text_bytes(path.read_bytes(), path.name)
    rows = []

    try:
        reader = csv.reader(io.StringIO(raw_text))
        for row in reader:
            cells = [str(cell or "").strip() for cell in row if str(cell or "").strip()]
            if cells:
                rows.append(" | ".join(cells))
    except Exception:
        return sanitize_extracted_text(raw_text)

    return sanitize_extracted_text("\n".join(rows))


def extract_document_analysis_text(path_value: str) -> str:
    """Extract readable text for the document analysis pipeline."""

    path = Path(str(path_value or "").strip())
    suffix = path.suffix.lower()

    if not path.exists() or not path.is_file():
        raise DocumentOperationError(f"Document path does not exist: {path}")

    if suffix not in SUPPORTED_DOCUMENT_ANALYSIS_SUFFIXES:
        raise DocumentOperationError(f"Unsupported document analysis file type: {suffix}")

    if suffix == ".pdf":
        return extract_pdf_text(path)

    if suffix == ".docx":
        return extract_docx_text(path)

    if suffix == ".csv":
        return extract_csv_text(path)

    return extract_plain_text(path)


def build_document_analysis_documents(documents: list) -> list:
    """Build the document shape expected by the analysis pipeline."""

    analysis_documents = []

    for document in documents:
        if not isinstance(document, dict):
            continue

        resolved_path = str(document.get("resolved_path") or "").strip()
        document_id = str(
            document.get("document_id")
            or document.get("random_name")
            or ""
        ).strip()
        original_name = str(
            document.get("original_name")
            or document.get("filename")
            or document_id
        ).strip()

        if not resolved_path or not document_id:
            continue

        text = extract_document_analysis_text(resolved_path)

        if not text:
            raise DocumentOperationError(
                f"Document analysis could not extract readable text from {original_name}."
            )

        analysis_documents.append({
            "document_id": document_id,
            "original_name": original_name,
            "filename": original_name,
            "display_name": original_name,
            "text": text,
            "source_path": resolved_path,
        })

    return analysis_documents


def run_document_analysis_operation(documents: list) -> dict:
    """Run the document analysis pipeline without entering V1 drivetrain."""

    analysis_documents = build_document_analysis_documents(documents)

    if not analysis_documents:
        return {
            "ok": False,
            "packet_type": "docintel",
            "payload": {
                "answer": "Document analysis requires at least one readable document.",
                "bridge": "",
                "report_kind": DOCUMENT_ANALYSIS_OPERATION_KEY,
                "suggestions": [],
            },
            "verdict": "REQUIRES_ACTION",
        }

    logger.info(
        "[document_operation.analysis_pipeline] docs=%s",
        len(analysis_documents),
    )

    return build_document_analysis_report_packet(
        documents=analysis_documents,
        reconciliation=None,
        use_llm_wording=True,
    )


def nested_packet_value(source, path):
    """Read a dotted path from a nested packet."""

    current = source

    for key in str(path or "").split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def wants_json_response() -> bool:
    """Return whether the caller expects a JSON report-job response."""

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return True

    best_match = request.accept_mimetypes.best_match([
        "application/json",
        "text/html",
    ])

    if best_match != "application/json":
        return False

    return (
        request.accept_mimetypes["application/json"]
        >= request.accept_mimetypes["text/html"]
    )


def get_operation_label(operation) -> str:
    """Return a safe display label for a document operation."""

    label = str(
        getattr(operation, "label", "")
        or getattr(operation, "name", "")
        or DOCUMENT_ANALYSIS_OPERATION_LABEL
    ).strip()

    return label or DOCUMENT_ANALYSIS_OPERATION_LABEL


def html_to_plain_report_text(value: str) -> str:
    """Convert report HTML into stable server-rendered text."""

    text = unescape(str(value or "").strip())

    if not text:
        return ""

    text = _HTML_BREAK_RE.sub("\n", text)
    text = _HTML_HEADING_OPEN_RE.sub("\n\n", text)
    text = _HTML_HEADING_CLOSE_RE.sub("\n\n", text)
    text = _HTML_LIST_ITEM_OPEN_RE.sub("\n• ", text)
    text = _HTML_LIST_ITEM_CLOSE_RE.sub("\n", text)
    text = _HTML_BLOCK_RE.sub("\n\n", text)
    text = _HTML_TAG_RE.sub("", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def normalize_report_text(value) -> str:
    """Normalize report text for server-rendered report pages."""

    if isinstance(value, str):
        return html_to_plain_report_text(value)

    if isinstance(value, list):
        return "\n\n".join(
            normalize_report_text(item)
            for item in value
            if normalize_report_text(item)
        ).strip()

    if isinstance(value, dict):
        return "\n\n".join(
            f"{key}: {normalize_report_text(item)}"
            for key, item in value.items()
            if normalize_report_text(item)
        ).strip()

    return str(value or "").strip()


def is_report_renderer_metadata(value) -> bool:
    """Return whether text is renderer/debug metadata rather than report content."""

    text = normalize_report_text(value)

    if not text:
        return False

    normalized = re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()

    renderer_markers = (
        "bei document extract v1",
        "direct custom report writer",
        "model brief with deterministic report",
    )

    if all(marker in normalized for marker in renderer_markers):
        return True

    return (
        normalized.startswith("source bei document extract")
        and "renderer" in normalized
        and "status" in normalized
    )


def remove_report_readout_joiners(value: str) -> str:
    """Remove generated source/readout joiners from report body text."""

    text = str(value or "")

    if not text.strip():
        return ""

    text = _REPORT_SOURCE_READOUT_RE.sub(" ", text)
    text = re.sub(
        r"(?i)\bSolomonAI\s+Readout(?=[A-Z0-9])",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)\bSolomonAI\s+Readout\b",
        " ",
        text,
    )
    text = re.sub(
        r"(?i)(\.[a-z0-9]{2,5})(?=[A-Z0-9])",
        r"\1 ",
        text,
    )

    return text.strip()


def inject_report_section_boundaries(value: str) -> str:
    """Insert stable boundaries around known report headings."""

    text = remove_report_readout_joiners(value)

    if not text.strip():
        return ""

    text = re.sub(
        r"(?i)\bDocument\s+Summary\s*[—–-]\s*.*?\.(?:pdf|docx|txt|csv|xlsx|xls)\s*",
        "Document Summary\n\n",
        text,
        count=1,
    )
    text = re.sub(
        r"(?i)\bDocument\s+Summary\s*[—–-]\s*",
        "Document Summary\n\n",
        text,
        count=1,
    )

    for title in REPORT_SECTION_TITLES:
        escaped_title = re.escape(title)
        field_pattern = r"(?=[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){0,3}\s*:)"

        text = re.sub(
            rf"(?<!\n)(?<!^)\b{escaped_title}\b\s*[:—–-]\s*",
            f"\n\n{title}\n\n",
            text,
        )
        text = re.sub(
            rf"(?m)^[ \t]*\b{escaped_title}\b\s*[:—–-]\s*",
            f"{title}\n\n",
            text,
        )
        text = re.sub(
            rf"(?<!\n)(?<!^)\b{escaped_title}\b\s+(?=\([^)]+\))",
            f"\n\n{title}\n\n",
            text,
        )
        text = re.sub(
            rf"(?m)^[ \t]*\b{escaped_title}\b\s+(?=\([^)]+\))",
            f"{title}\n\n",
            text,
        )
        text = re.sub(
            rf"(?<!\n)(?<!^)\b{escaped_title}\b\s+{field_pattern}",
            f"\n\n{title}\n\n",
            text,
        )
        text = re.sub(
            rf"(?m)^[ \t]*\b{escaped_title}\b\s+{field_pattern}",
            f"{title}\n\n",
            text,
        )

    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def split_report_paragraphs(value) -> list:
    """Split report text into safe server-side paragraphs."""

    text = inject_report_section_boundaries(normalize_report_text(value))

    if is_report_renderer_metadata(text):
        text = ""

    blocks = [
        re.sub(r"\s*\n\s*", " ", block).strip()
        for block in re.split(r"\n{2,}", text)
        if block.strip()
    ]

    return blocks or ["No report text was returned."]


def get_report_text_for_page(packet: dict) -> str:
    """Return the best available report text from a result packet."""

    paths = (
        "workflow_response.payload.answer",
        "workflow_response.payload.rendered_report",
        "workflow_response.payload.report_html",
        "workflow_response.payload.output",
        "workflow_response.payload.summary",
        "workflow_response.payload.report",
        "result.summary",
        "result.body",
        "result.output",
        "user_output",
        "payload.answer",
        "payload.report",
        "payload.output",
        "payload.summary",
    )

    for path in paths:
        text = inject_report_section_boundaries(
            normalize_report_text(nested_packet_value(packet, path))
        )

        if text and not is_report_renderer_metadata(text):
            return text

    return "The report completed, but no display text was returned."


def normalize_report_heading(value: str) -> str:
    """Normalize a possible report heading for section detection."""

    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def get_canonical_report_heading(value: str) -> str:
    """Return a canonical report section heading when a paragraph is a heading."""

    normalized = normalize_report_heading(value)

    for title in REPORT_SECTION_TITLES:
        if normalized == normalize_report_heading(title):
            return title

    return ""


def build_report_sections_from_text(value) -> list:
    """Build commercial report sections from normalized report text."""

    paragraphs = split_report_paragraphs(value)
    sections = []
    intro = []
    current = None

    for paragraph in paragraphs:
        heading = get_canonical_report_heading(paragraph.rstrip(":"))

        if heading:
            current = {
                "title": heading,
                "paragraphs": [],
            }
            sections.append(current)
            continue

        if current:
            current["paragraphs"].append(paragraph)
        else:
            intro.append(paragraph)

    if sections:
        if intro:
            sections.insert(0, {
                "title": "Report Overview",
                "paragraphs": intro,
            })

        for section in sections:
            if not section["paragraphs"]:
                section["paragraphs"] = ["No details were returned for this section."]

        return sections

    return [{
        "title": "Report",
        "paragraphs": paragraphs,
    }]


def get_report_sections_for_page(packet: dict) -> list:
    """Return server-provided report sections or one stable report body section."""

    result = packet.get("result") if isinstance(packet.get("result"), dict) else {}
    report = packet.get("report") if isinstance(packet.get("report"), dict) else {}

    raw_sections = []

    if isinstance(report.get("sections"), list) and report.get("sections"):
        raw_sections = report.get("sections")
    elif isinstance(result.get("sections"), list) and result.get("sections"):
        raw_sections = result.get("sections")

    sections = []

    for item in raw_sections:
        if not isinstance(item, dict):
            continue

        title = str(
            item.get("title")
            or item.get("section_title")
            or ""
        ).strip()
        body = inject_report_section_boundaries(
            normalize_report_text(
                item.get("body")
                or item.get("summary")
                or item.get("output")
                or item.get("text")
                or item.get("body_text")
                or item.get("body_html")
            )
        )

        if is_report_renderer_metadata(body):
            body = ""

        if body:
            sections.append({
                "title": title,
                "paragraphs": split_report_paragraphs(body),
            })

    if sections:
        return sections

    return build_report_sections_from_text(get_report_text_for_page(packet))


def get_packet_document_name(packet: dict, fallback: str = "Selected file") -> str:
    """Return display document name from a result packet."""

    document = packet.get("document") if isinstance(packet.get("document"), dict) else {}

    return (
        str(document.get("original_name") or "").strip()
        or str(document.get("filename") or "").strip()
        or str(document.get("random_name") or "").strip()
        or fallback
    )


def get_packet_document_id(packet: dict) -> str:
    """Return display document id from a result packet."""

    document = packet.get("document") if isinstance(packet.get("document"), dict) else {}

    return (
        str(document.get("document_id") or "").strip()
        or str(document.get("random_name") or "").strip()
        or str(document.get("file_id") or "").strip()
    )


def get_saved_review_label(packet: dict) -> str:
    """Return a saved-review label for the report page."""

    saved_review = packet.get("saved_review")

    if not isinstance(saved_review, dict) or not saved_review.get("saved"):
        return "Current session"

    review_id = str(saved_review.get("review_id") or "").strip()

    return f"#{review_id}" if review_id else "Saved"


def is_pending_job_packet(packet: dict) -> bool:
    """Return whether a job packet is still pending."""

    status = str(packet.get("status") or "").strip().lower()

    return status in {"queued", "submitted", "running"}


def get_report_view_context(packet: dict) -> dict:
    """Return the shared context for completed report surfaces and fragments."""

    operation_label = str(packet.get("operation_label") or DOCUMENT_ANALYSIS_OPERATION_LABEL).strip()
    result = packet.get("result") if isinstance(packet.get("result"), dict) else {}
    document_name = get_packet_document_name(packet)
    document_id = get_packet_document_id(packet)
    status = str(packet.get("status") or "").strip().lower()
    ok = packet.get("ok") is not False and status != "failed"
    result_title = (
        str(result.get("title") or "").strip()
        or f"{operation_label} {'Complete' if ok else 'Failed'}"
    )

    return {
        "operation_label": operation_label,
        "result_title": result_title,
        "document_name": document_name,
        "status_label": "Complete" if ok else "Failed",
        "saved_review_label": get_saved_review_label(packet),
        "sections": get_report_sections_for_page(packet),
        "reader_url": f"/workspace/file/{document_id}/reader" if document_id else "",
        "back_url": "/docs",
    }


def get_saved_review_source_document(review: dict) -> dict:
    """Return the best source document metadata from a saved review."""

    sources = review.get("sources") if isinstance(review.get("sources"), list) else []
    source = sources[0] if sources and isinstance(sources[0], dict) else {}
    document_id = str(source.get("source_document_id") or "").strip()
    source_name = str(source.get("source_name") or "").strip()

    return {
        "document_id": document_id,
        "random_name": document_id,
        "file_id": str(source.get("file_registry_id") or "").strip(),
        "original_name": source_name or document_id or "Selected file",
        "filename": source_name or document_id or "Selected file",
    }


def get_saved_review_display_title(review: dict) -> str:
    """Return a clean saved-review display title."""

    title = str(
        review.get("review_title")
        or review.get("title")
        or DOCUMENT_ANALYSIS_OPERATION_LABEL
    ).strip()

    normalized = normalize_report_heading(title)

    if normalized.startswith("run document analysis"):
        return "Document Analysis Complete"

    if normalized == normalize_report_heading(DOCUMENT_ANALYSIS_OPERATION_LABEL):
        return "Document Analysis Complete"

    return title or "Document Analysis Complete"


def saved_review_to_report_packet(review: dict) -> dict:
    """Convert a saved WorkspaceArtifact review into the report-surface packet contract."""

    review_id = str(
        review.get("review_id")
        or review.get("artifact_id")
        or review.get("record_id")
        or ""
    ).strip()
    title = get_saved_review_display_title(review)
    sections = review.get("sections") if isinstance(review.get("sections"), list) else []

    return {
        "ok": True,
        "packet_type": "document_operation_result",
        "artifact_type": "report",
        "status": "complete",
        "operation": DOCUMENT_ANALYSIS_OPERATION_KEY,
        "operation_key": DOCUMENT_ANALYSIS_OPERATION_KEY,
        "operation_label": DOCUMENT_ANALYSIS_OPERATION_LABEL,
        "job_id": str(review.get("job_id") or "").strip(),
        "request_id": str(review.get("request_id") or get_request_id()).strip(),
        "document": get_saved_review_source_document(review),
        "saved_review": {
            "saved": True,
            "review_id": review_id,
            "artifact_id": review.get("artifact_id") or review_id,
            "record_id": review.get("record_id") or review_id,
        },
        "result": {
            "title": title,
            "summary": review.get("summary") or "",
            "sections": sections,
            "risk_level": review.get("risk_level") or "",
            "completeness": (
                review.get("completeness")
                or review.get("document_completeness")
                or ""
            ),
            "confidence_level": review.get("confidence_level") or "",
            "created_at": review.get("created_at") or "",
            "updated_at": review.get("updated_at") or "",
        },
        "report": {
            "sections": sections,
        },
    }


def get_saved_review_packet_for_current_user(review_id: str) -> dict | None:
    """Return a saved-review packet owned by the current user."""

    user_id = get_current_user_id()

    if not user_id:
        return None

    review = get_saved_review(user_id, review_id)

    if not review:
        return None

    return saved_review_to_report_packet(review)


def render_report_shell_surface(*, report_surface_mode: str, status_code: int = 200, **context):
    """Render a report surface inside the Operations Console shell."""

    return render_template(
        "index.html",
        active_module="home",
        workspace_surface_template=REPORT_SURFACE_TEMPLATE,
        report_surface_mode=report_surface_mode,
        **context,
    ), status_code


def render_report_start_surface(
    *,
    operation_key: str,
    document_ids: list,
    document_name: str,
    status_code: int = 200,
):
    """Render the app-shell report start surface."""

    return render_report_shell_surface(
        report_surface_mode="start",
        status_code=status_code,
        operation_key=operation_key,
        operation_label=DOCUMENT_ANALYSIS_OPERATION_LABEL,
        document_ids=document_ids,
        document_name=document_name,
        create_url=url_for(".create_document_operation_report"),
        back_url="/docs",
    )


def render_report_prepare_surface(packet: dict, job_id: str, *, status_code: int = 200):
    """Render the app-shell report preparation surface."""

    document_id = get_packet_document_id(packet)

    return render_report_shell_surface(
        report_surface_mode="preparing",
        status_code=status_code,
        operation_label=str(packet.get("operation_label") or DOCUMENT_ANALYSIS_OPERATION_LABEL).strip(),
        document_name=get_packet_document_name(packet),
        reader_url=f"/workspace/file/{document_id}/reader" if document_id else "",
        status_url=url_for(".document_operation_report_status", job_id=job_id),
        result_url=url_for(".render_document_operation_report_result", job_id=job_id),
        back_url="/docs",
    )


def render_report_page(packet: dict, *, status_code: int = 200):
    """Render a complete server-owned report surface inside the app shell."""

    return render_report_shell_surface(
        report_surface_mode="result",
        status_code=status_code,
        **get_report_view_context(packet),
    )


def render_report_fragment(packet: dict, *, status_code: int = 200):
    """Render a completed report fragment for the file-details content panel."""

    return render_template(
        REPORT_FRAGMENT_TEMPLATE,
        **get_report_view_context(packet),
    ), status_code


def render_report_fragment_error(message: str, *, status_code: int = 400):
    """Render a stable report error fragment for the file-details content panel."""

    packet = {
        "ok": False,
        "status": "failed",
        "operation_label": DOCUMENT_ANALYSIS_OPERATION_LABEL,
        "result": {
            "title": "Document Analysis Failed",
            "summary": message or "The report could not be completed.",
        },
        "document": {
            "original_name": "Selected file",
        },
    }

    return render_report_fragment(packet, status_code=status_code)


def render_report_error_page(message: str, *, status_code: int = 400):
    """Render a server-owned report error surface inside the app shell."""

    packet = {
        "ok": False,
        "status": "failed",
        "operation_label": DOCUMENT_ANALYSIS_OPERATION_LABEL,
        "result": {
            "title": "Document Analysis Failed",
            "summary": message or "The report could not be completed.",
        },
        "document": {
            "original_name": "Selected file",
        },
    }

    return render_report_page(packet, status_code=status_code)


register_document_operation_runner(
    DOCUMENT_ANALYSIS_OPERATION_KEY,
    run_document_analysis_operation,
)


@document_operations_bp.route("/list", methods=["GET"])
@login_required
def list_operations():
    """Return registered backend document operations."""

    return jsonify({
        "ok": True,
        "operations": list_document_operations(),
        "request_id": get_request_id(),
    })


@document_operations_bp.route("/reviews", methods=["GET"])
@login_required
def list_saved_reviews():
    """Return saved document review artifacts owned by the current user."""

    user_id = get_current_user_id()

    if not user_id:
        return operation_error(
            "AuthenticationRequired",
            "Authentication is required to read saved reviews.",
            status_code=401,
        )

    try:
        reviews = load_saved_reviews(user_id)
    except Exception as exc:
        logger.warning(
            "[document_operation.saved_reviews_failed] user_id=%s error=%s",
            user_id,
            exc,
        )
        return operation_error(
            "SavedReviewsUnavailable",
            "Saved reviews could not be loaded.",
            status_code=500,
        )

    return jsonify({
        "ok": True,
        "packet_type": "saved_reviews",
        "artifact_type": "review",
        "count": len(reviews),
        "reviews": reviews,
        "request_id": get_request_id(),
    }), 200


@document_operations_bp.route("/review/fragment/<review_id>", methods=["GET"])
@login_required
def render_saved_review_fragment(review_id):
    """Render a saved review artifact fragment for the file-details content panel."""

    user_id = get_current_user_id()

    if not user_id:
        return render_report_fragment_error(
            "Authentication is required to read saved reviews.",
            status_code=401,
        )

    packet = get_saved_review_packet_for_current_user(review_id)

    if not packet:
        return render_report_fragment_error(
            "The saved report could not be found.",
            status_code=404,
        )

    return render_report_fragment(packet, status_code=200)


@document_operations_bp.route("/review/result/<review_id>", methods=["GET"])
@login_required
def render_saved_review_result(review_id):
    """Render a saved review artifact result inside the app shell."""

    user_id = get_current_user_id()

    if not user_id:
        return render_report_error_page(
            "Authentication is required to read saved reviews.",
            status_code=401,
        )

    packet = get_saved_review_packet_for_current_user(review_id)

    if not packet:
        return render_report_error_page(
            "The saved report could not be found.",
            status_code=404,
        )

    return render_report_page(packet, status_code=200)


@document_operations_bp.route("/report", methods=["GET"])
@login_required
def render_document_operation_report_start():
    """Render a safe app-shell start surface for a report request without running the report."""

    operation_key = str(
        request.args.get("operation")
        or DOCUMENT_ANALYSIS_OPERATION_KEY
    ).strip()
    document_ids = collect_query_document_ids()
    user_id = get_current_user_id()
    documents = resolve_authorized_documents(user_id, document_ids) if user_id else []
    document_name = "Selected file"

    if documents:
        document_name = (
            documents[0].get("original_name")
            or documents[0].get("filename")
            or documents[0].get("random_name")
            or document_name
        )

    if not document_ids:
        return render_report_error_page(
            "Select at least one stored document before running this operation.",
            status_code=400,
        )

    return render_report_start_surface(
        operation_key=operation_key,
        document_ids=document_ids,
        document_name=document_name,
    )


@document_operations_bp.route("/report/create", methods=["POST"])
@login_required
def create_document_operation_report():
    """Create a background report job and open the app-shell report preparation surface."""

    request_id = get_request_id()
    payload = read_operation_request_payload()
    operation_key = str(payload.get("operation") or DOCUMENT_ANALYSIS_OPERATION_KEY).strip()
    document_ids = collect_document_ids(payload)

    try:
        user_id, operation, documents = prepare_operation_context(
            operation_key,
            document_ids,
        )
        submitted_packet = submit_document_operation_job(
            operation=operation,
            documents=documents,
            user_id=user_id,
            request_id=request_id,
        )
    except DocumentOperationJobError as exc:
        if wants_json_response():
            return operation_error(
                exc.error_code,
                exc.user_output,
                status_code=exc.status_code,
                extra={"operation": operation_key},
            )

        return render_report_error_page(
            exc.user_output,
            status_code=exc.status_code,
        )

    job_id = str(submitted_packet.get("job_id") or "").strip()

    if not job_id:
        message = "The report job could not be created."

        if wants_json_response():
            return operation_error(
                "DocumentOperationJobMissing",
                message,
                status_code=500,
                extra={"operation": operation_key},
            )

        return render_report_error_page(message, status_code=500)

    if wants_json_response():
        return jsonify(submitted_packet), 202

    return render_report_prepare_surface(
        submitted_packet,
        job_id,
        status_code=202,
    )


@document_operations_bp.route("/report/status/<job_id>", methods=["GET"])
@login_required
def document_operation_report_status(job_id):
    """Return the current report-job packet."""

    user_id = get_current_user_id()

    if not user_id:
        return operation_error(
            "AuthenticationRequired",
            "Authentication is required to read report status.",
            status_code=401,
            extra={"job_id": job_id},
        )

    try:
        packet = get_document_operation_job_packet(
            job_id=job_id,
            user_id=user_id,
        )
    except DocumentOperationJobError as exc:
        return operation_error(
            exc.error_code,
            exc.user_output,
            status_code=exc.status_code,
            extra={"job_id": job_id},
        )

    return jsonify(packet), 200


@document_operations_bp.route("/report/result/<job_id>", methods=["GET"])
@login_required
def render_document_operation_report_result(job_id):
    """Render a completed report result inside the app shell."""

    user_id = get_current_user_id()

    if not user_id:
        return render_report_error_page(
            "Authentication is required to read report results.",
            status_code=401,
        )

    try:
        packet = get_document_operation_job_packet(
            job_id=job_id,
            user_id=user_id,
        )
    except DocumentOperationJobError as exc:
        return render_report_error_page(
            exc.user_output,
            status_code=exc.status_code,
        )

    if is_pending_job_packet(packet):
        return render_report_prepare_surface(
            packet,
            job_id,
            status_code=202,
        )

    return render_report_page(packet, status_code=200)


@document_operations_bp.route("/report/fragment/<job_id>", methods=["GET"])
@login_required
def render_document_operation_report_fragment(job_id):
    """Render a completed report fragment for the file-details content panel."""

    user_id = get_current_user_id()

    if not user_id:
        return render_report_fragment_error(
            "Authentication is required to read report results.",
            status_code=401,
        )

    try:
        packet = get_document_operation_job_packet(
            job_id=job_id,
            user_id=user_id,
        )
    except DocumentOperationJobError as exc:
        return render_report_fragment_error(
            exc.user_output,
            status_code=exc.status_code,
        )

    if is_pending_job_packet(packet):
        return render_report_fragment_error(
            "The report is still being prepared.",
            status_code=202,
        )

    return render_report_fragment(packet, status_code=200)


def get_conversation_id_from_payload(payload: dict) -> str:
    """Return an optional conversation id from a request payload."""

    return str(
        payload.get("conversation_id")
        or payload.get("session_id")
        or payload.get("document_ai_session")
        or ""
    ).strip()


def create_or_extend_solomon_ai_conversation(
    *,
    legacy_response=False,
):
    """Create or extend one durable SolomonAI conversation and its sources."""

    request_id = get_request_id()
    payload = read_operation_payload()
    requested_document_ids = collect_document_ids(
        payload
    )
    requested_conversation_id = str(
        payload.get("conversation_id")
        or (
            payload.get("document_ai_session")
            if legacy_response
            else ""
        )
        or ""
    ).strip()
    user_id = get_current_user_id()

    if not user_id:
        return solomon_ai_conversation_error(
            "AuthenticationRequired",
            "Authentication is required to start a SolomonAI conversation.",
            status_code=401,
            legacy_response=legacy_response,
        )

    # Modern SolomonAI conversations are valid without explicit sources.
    # The legacy document-session endpoint retains its historical requirement
    # because that endpoint exists specifically to open a document-grounded
    # session. Explicit source additions remain governed by the dedicated
    # /conversations/<id>/sources route below.
    if legacy_response and not requested_document_ids:
        return solomon_ai_conversation_error(
            "SolomonAiConversationMissingDocuments",
            "Select at least one stored document before asking SolomonAI.",
            status_code=400,
            legacy_response=legacy_response,
        )

    requested_documents = resolve_authorized_documents(
        user_id,
        requested_document_ids,
    )

    if len(requested_documents) != len(
        requested_document_ids
    ):
        return solomon_ai_conversation_error(
            "SolomonAiConversationDocumentAccessDenied",
            (
                "One or more selected documents are missing "
                "or are not authorized."
            ),
            status_code=404,
            legacy_response=legacy_response,
        )

    conversation_action = "created"
    response_status = 201

    try:
        if requested_conversation_id:
            durable_conversation = (
                get_durable_solomon_ai_conversation(
                    user_id=user_id,
                    conversation_id=requested_conversation_id,
                    include_messages=False,
                )
            )

            if not durable_conversation:
                return solomon_ai_conversation_error(
                    "SolomonAiConversationInvalid",
                    (
                        "The selected SolomonAI conversation "
                        "could not be found."
                    ),
                    status_code=404,
                    legacy_response=legacy_response,
                )

            existing_document_ids = (
                durable_conversation.get("document_ids")
                if isinstance(
                    durable_conversation.get(
                        "document_ids"
                    ),
                    list,
                )
                else []
            )
            merged_document_ids = []
            seen_document_ids = set()

            for document_id in [
                *existing_document_ids,
                *[
                    document.get("document_id")
                    for document in requested_documents
                ],
            ]:
                clean_document_id = str(
                    document_id or ""
                ).strip()

                if (
                    not clean_document_id
                    or clean_document_id
                    in seen_document_ids
                ):
                    continue

                seen_document_ids.add(
                    clean_document_id
                )
                merged_document_ids.append(
                    clean_document_id
                )

            merged_documents = resolve_authorized_documents(
                user_id,
                merged_document_ids,
            )

            if len(merged_documents) != len(
                merged_document_ids
            ):
                return solomon_ai_conversation_error(
                    "SolomonAiConversationSourceUnavailable",
                    (
                        "One or more existing conversation "
                        "sources are no longer available."
                    ),
                    status_code=409,
                    legacy_response=legacy_response,
                )

            conversation_id = requested_conversation_id
            conversation_action = "updated"
            response_status = 200
        else:
            durable_conversation = (
                create_durable_solomon_ai_conversation(
                    user_id=user_id
                )
            )
            conversation_id = str(
                durable_conversation.get(
                    "conversation_id"
                )
                or ""
            ).strip()
            merged_documents = requested_documents

        durable_conversation = (
            replace_solomon_ai_conversation_sources(
                user_id=user_id,
                conversation_id=conversation_id,
                documents=merged_documents,
            )
        )
    except SolomonAIConversationStoreError as exc:
        logger.warning(
            (
                "[solomon_ai.conversation_persistence_failed] "
                "request_id=%s user_id=%s conversation_id=%s "
                "error=%s"
            ),
            request_id,
            user_id,
            requested_conversation_id,
            exc,
        )
        return solomon_ai_conversation_error(
            "SolomonAiConversationPersistenceFailed",
            str(exc)
            or (
                "The SolomonAI conversation could not "
                "be saved."
            ),
            status_code=500,
            legacy_response=legacy_response,
        )

    conversation_packet = store_solomon_ai_conversation(
        conversation_packet=durable_conversation,
        request_id=request_id,
    )

    logger.info(
        (
            "[solomon_ai.conversation_sources_saved] "
            "request_id=%s user_id=%s conversation_id=%s "
            "documents=%s action=%s"
        ),
        request_id,
        user_id,
        conversation_packet.get("conversation_id"),
        conversation_packet.get("source_count"),
        conversation_action,
    )

    if legacy_response:
        response_payload = build_solomon_ai_source_response(
            conversation_packet=conversation_packet,
            request_id=request_id,
            source_action=conversation_action,
        )
    else:
        response_payload = build_solomon_ai_conversation_response(
            conversation_packet=conversation_packet,
            request_id=request_id,
            conversation_action=conversation_action,
        )

    return jsonify(response_payload), response_status


@document_operations_bp.route("/ai", methods=["POST"])
@login_required
def create_solomon_ai_conversation():
    """Create or extend a durable SolomonAI conversation and source membership."""

    return create_or_extend_solomon_ai_conversation(
        legacy_response=False,
    )


@solomon_conversations_bp.route("/intelligence/readiness", methods=["GET"])
@login_required
def get_solomon_ai_intelligence_readiness():
    """Expose readiness for the selected local or SIS inference transport."""

    request_id = get_request_id()
    backend = select_backend()
    if backend == "transformers_direct":
        # Local inference is an existing, in-process execution path. Do not
        # require a separate SIS process or launch a GPU warmup on every UI poll.
        # Model file presence establishes eligibility; the execution boundary
        # remains responsible for reporting generation-time failures.
        local_available = direct_model_files_available()
        health = {
            "status": "ready" if local_available else "unavailable",
            "interactive_ready": local_available,
        }
    elif backend == "sis":
        health = get_intelligence_service_health()
    else:
        health = {"status": "unavailable", "interactive_ready": False}

    raw_status = str(health.get("status") or "").strip().lower()
    interactive_ready = bool(health.get("interactive_ready"))
    if not interactive_ready and backend == "sis":
        # Only remote SIS uses the Flask-owned recovery monitor. Keep browser
        # polling from triggering network recovery or GPU load in local mode.
        request_intelligence_service_recovery()

    if raw_status == "ready" and interactive_ready:
        status = "ready"
        can_submit = True
        user_message = ""
    elif raw_status == "checking":
        status = "checking"
        can_submit = False
        user_message = "Checking Solomon availability…"
    elif raw_status in {"starting", "warming"}:
        status = "warming"
        can_submit = False
        user_message = "Solomon is warming up. Chat will be available shortly."
    elif raw_status == "degraded":
        status = "degraded"
        can_submit = False
        user_message = (
            "Solomon is temporarily unavailable. "
            "Your other workspace features are unaffected."
        )
    else:
        status = "unavailable"
        can_submit = False
        user_message = (
            "Solomon is temporarily unavailable. "
            "Your other workspace features are unaffected."
        )

    response = jsonify({
        "ok": True,
        "packet_type": "solomon_ai_intelligence_readiness",
        "artifact_type": "interactive_intelligence",
        "capability": "solomon_ai_chat",
        "request_id": request_id,
        "status": status,
        "can_submit": can_submit,
        "user_message": user_message,
    })
    response.headers["Cache-Control"] = (
        "no-store, no-cache, must-revalidate, max-age=0"
    )
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response, 200


@solomon_conversations_bp.route("/conversations", methods=["GET"])
@login_required
def list_solomon_ai_conversations():
    """Return the current user's durable SolomonAI conversations."""

    request_id = get_request_id()
    user_id = get_current_user_id()

    if not user_id:
        return solomon_ai_conversation_error(
            "AuthenticationRequired",
            "Authentication is required to read SolomonAI conversations.",
            status_code=401,
        )

    try:
        conversations = []
        active_conversation_id = str(
            session.get(
                "solomon_ai_active_conversation_id"
            )
            or ""
        ).strip()
        durable_conversations = load_solomon_ai_conversations(
            user_id=user_id,
            request_id=request_id,
        )
    except Exception as exc:
        logger.warning(
            (
                "[solomon_ai.conversations_load_failed] "
                "request_id=%s user_id=%s error=%s"
            ),
            request_id,
            user_id,
            exc,
        )
        return solomon_ai_conversation_error(
            "SolomonAiConversationsUnavailable",
            (
                "SolomonAI conversations could not "
                "be loaded."
            ),
            status_code=500,
        )

    for conversation in durable_conversations:
        conversation_id = str(
            conversation.get("conversation_id")
            or conversation.get("session_id")
            or ""
        ).strip()
        source_names = (
            conversation.get("document_names")
            if isinstance(
                conversation.get("document_names"),
                list,
            )
            else []
        )
        title = str(
            conversation.get("title")
            or ""
        ).strip()
        preview_names = [
            str(name or "").strip()
            for name in source_names
            if str(name or "").strip()
        ][:3]

        if not title:
            if preview_names:
                title = ", ".join(preview_names)
            else:
                title = "New conversation"

        conversations.append({
            "conversation_id": conversation_id,
            "title": title,
            "source_count": conversation.get("source_count", 0),
            "source_preview": preview_names,
            "active": conversation_id == active_conversation_id,
            "conversation_url": get_solomon_ai_conversation_url(
                conversation_id
            ),
            "updated_at": str(
                conversation.get("updated_at")
                or ""
            ),
            "last_message_at": str(
                conversation.get("last_message_at")
                or ""
            ),
        })

    return jsonify({
        "ok": True,
        "packet_type": "solomon_ai_conversation_list",
        "artifact_type": "source_conversation",
        "count": len(conversations),
        "active_conversation_id": active_conversation_id,
        "conversations": conversations,
        "status": "ready",
        "request_id": request_id,
    }), 200


def load_solomon_ai_conversations(
    *,
    user_id: int,
    request_id: str,
) -> list:
    """Load durable SolomonAI conversations for the current user."""

    try:
        from solomon_core.solomon_ai_conversation_store import (
            list_solomon_ai_conversations as list_durable_conversations,
        )

        return list_durable_conversations(
            user_id=user_id
        )
    except Exception as exc:
        logger.warning(
            (
                "[solomon_ai.conversations_store_failed] "
                "request_id=%s user_id=%s error=%s"
            ),
            request_id,
            user_id,
            exc,
        )
        return []


@solomon_conversations_bp.route(
    "/conversations/<conversation_id>",
    methods=["GET"],
)
@login_required
def get_solomon_ai_conversation(conversation_id):
    """Return one durable SolomonAI conversation for the current user."""

    request_id = get_request_id()
    user_id = get_current_user_id()

    if not user_id:
        return solomon_ai_conversation_error(
            "AuthenticationRequired",
            "Authentication is required to read SolomonAI conversations.",
            status_code=401,
        )

    durable_conversation = (
        get_durable_solomon_ai_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            include_messages=False,
        )
    )

    if not durable_conversation:
        return solomon_ai_conversation_error(
            "SolomonAiConversationInvalid",
            "This SolomonAI conversation could not be found.",
            status_code=404,
        )

    conversation_packet = store_solomon_ai_conversation(
        conversation_packet=durable_conversation,
        request_id=request_id,
    )

    logger.debug(
        (
            "[solomon_ai.conversation_loaded] "
            "request_id=%s user_id=%s conversation_id=%s sources=%s"
        ),
        request_id,
        user_id,
        conversation_id,
        conversation_packet.get("source_count"),
    )

    return jsonify({
        "ok": True,
        "packet_type": "solomon_ai_conversation",
        "artifact_type": "source_conversation",
        "conversation": conversation_packet,
        "status": "ready",
        "request_id": request_id,
    }), 200


@solomon_conversations_bp.route(
    "/conversations/<conversation_id>/rename",
    methods=["POST"],
)
@login_required
def rename_solomon_ai_conversation(conversation_id):
    """Rename one durable SolomonAI conversation owned by the current user."""

    request_id = get_request_id()
    user_id = get_current_user_id()
    payload = read_operation_payload()
    title = str(
        payload.get("title")
        or payload.get("conversation_title")
        or ""
    ).strip()

    if not user_id:
        return solomon_ai_conversation_error(
            "AuthenticationRequired",
            "Authentication is required to rename SolomonAI conversations.",
            status_code=401,
        )

    if not title:
        return solomon_ai_conversation_error(
            "SolomonAiConversationTitleRequired",
            "Enter a conversation title before saving.",
            status_code=400,
        )

    try:
        conversation_packet = (
            rename_durable_solomon_ai_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
                title=title,
            )
        )
    except SolomonAIConversationStoreError as exc:
        logger.warning(
            (
                "[solomon_ai.conversation_rename_failed] "
                "request_id=%s user_id=%s conversation_id=%s "
                "error=%s"
            ),
            request_id,
            user_id,
            conversation_id,
            exc,
        )
        return solomon_ai_conversation_error(
            "SolomonAiConversationRenameFailed",
            str(exc)
            or "Conversation could not be renamed.",
            status_code=400,
        )

    active_packet = get_active_solomon_ai_conversation()
    active_conversation_id = str(
        active_packet.get("conversation_id")
        or active_packet.get("session_id")
        or ""
    ).strip()

    if active_conversation_id == str(conversation_id or "").strip():
        store_solomon_ai_conversation(
            conversation_packet=conversation_packet,
            request_id=request_id,
        )

    clean_conversation_id = str(
        conversation_id or ""
    ).strip()
    clean_title = str(
        conversation_packet.get("title")
        or title
        or ""
    ).strip()

    return jsonify({
        "ok": True,
        "packet_type": "solomon_ai_conversation_management",
        "artifact_type": "conversation",
        "conversation_action": "renamed",
        "conversation_id": clean_conversation_id,
        "conversation_url": get_solomon_ai_conversation_url(
            clean_conversation_id
        ),
        "title": clean_title,
        "status": "ready",
        "request_id": request_id,
    }), 200


@solomon_conversations_bp.route(
    "/conversations/<conversation_id>/delete",
    methods=["POST", "DELETE"],
)
@login_required
def delete_solomon_ai_conversation(conversation_id):
    """Soft-delete one durable SolomonAI conversation owned by the user."""

    request_id = get_request_id()
    user_id = get_current_user_id()

    if not user_id:
        return solomon_ai_conversation_error(
            "AuthenticationRequired",
            "Authentication is required to delete SolomonAI conversations.",
            status_code=401,
        )

    try:
        deleted = (
            delete_durable_solomon_ai_conversation(
                user_id=user_id,
                conversation_id=conversation_id,
            )
        )
    except SolomonAIConversationStoreError as exc:
        logger.warning(
            (
                "[solomon_ai.conversation_delete_failed] "
                "request_id=%s user_id=%s conversation_id=%s error=%s"
            ),
            request_id,
            user_id,
            conversation_id,
            exc,
        )
        return solomon_ai_conversation_error(
            "SolomonAiConversationDeleteFailed",
            str(exc)
            or "Conversation could not be deleted.",
            status_code=400,
        )

    if not deleted:
        return solomon_ai_conversation_error(
            "SolomonAiConversationInvalid",
            "This SolomonAI conversation could not be found.",
            status_code=404,
        )

    active_conversation_cleared = (
        clear_active_solomon_ai_conversation(
            conversation_id
        )
    )

    return jsonify({
        "ok": True,
        "packet_type": "solomon_ai_conversation_management",
        "artifact_type": "conversation",
        "conversation_action": "deleted",
        "conversation_id": str(conversation_id or "").strip(),
        "workspace_url": "/ai",
        "active_conversation_cleared": bool(
            active_conversation_cleared
        ),
        "status": "deleted",
        "request_id": request_id,
    }), 200


@solomon_conversations_bp.route(
    "/conversations/<conversation_id>/files",
    methods=["GET"],
)
@login_required
def list_solomon_ai_available_files(conversation_id):
    """Return authorized existing files available for one conversation."""

    request_id = get_request_id()
    user_id = get_current_user_id()
    requested_scope = str(
        request.args.get("scope")
        or ""
    ).strip().lower()
    search_query = str(
        request.args.get("q")
        or request.args.get("query")
        or ""
    ).strip()

    if requested_scope and requested_scope not in SUPPORTED_SCOPES:
        return solomon_ai_conversation_error(
            "SolomonAiFileScopeInvalid",
            "The requested file collection is not available.",
            status_code=400,
        )

    durable_conversation = (
        get_durable_solomon_ai_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            include_messages=False,
        )
    )

    if not durable_conversation:
        return solomon_ai_conversation_error(
            "SolomonAiConversationInvalid",
            "This SolomonAI conversation could not be found.",
            status_code=404,
        )

    organization_context = (
        normalize_solomon_ai_organization_context(
            durable_conversation
        )
    )

    if (
        organization_context["is_bound"]
        and not organization_context["is_active"]
    ):
        return solomon_ai_conversation_error(
            "SolomonAiConversationOrganizationUnavailable",
            (
                "This conversation's organization access is no "
                "longer active."
            ),
            status_code=409,
        )

    organization_id = (
        organization_context["organization_id"]
        if organization_context["is_bound"]
        else ""
    )
    file_catalog = list_authorized_file_catalog(
        user_id=user_id,
        organization_id=organization_id,
        access_scope=requested_scope,
    )
    response_payload = (
        build_solomon_ai_file_catalog_response(
            conversation_packet=durable_conversation,
            file_catalog=file_catalog,
            request_id=request_id,
            requested_scope=requested_scope,
            search_query=search_query,
        )
    )

    logger.info(
        (
            "[solomon_ai.available_files_loaded] "
            "request_id=%s user_id=%s conversation_id=%s "
            "organization_id=%s scope=%s files=%s"
        ),
        request_id,
        user_id,
        conversation_id,
        organization_id,
        requested_scope or "all",
        response_payload.get("count"),
    )

    return jsonify(response_payload), 200


@solomon_conversations_bp.route(
    "/conversations/<conversation_id>/sources",
    methods=["POST"],
)
@login_required
def add_solomon_ai_conversation_sources(conversation_id):
    """Add authorized existing files to one durable SolomonAI conversation."""

    request_id = get_request_id()
    user_id = get_current_user_id()
    payload = read_operation_payload()
    requested_document_ids = collect_document_ids(
        payload
    )

    if not user_id:
        return solomon_ai_conversation_error(
            "AuthenticationRequired",
            "Authentication is required to update SolomonAI sources.",
            status_code=401,
        )

    if not requested_document_ids:
        return solomon_ai_conversation_error(
            "SolomonAiConversationMissingDocuments",
            "Select at least one existing file to add.",
            status_code=400,
        )

    durable_conversation = (
        get_durable_solomon_ai_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            include_messages=False,
        )
    )

    if not durable_conversation:
        return solomon_ai_conversation_error(
            "SolomonAiConversationInvalid",
            "This SolomonAI conversation could not be found.",
            status_code=404,
        )

    requested_documents = resolve_authorized_documents(
        user_id,
        requested_document_ids,
    )

    if len(requested_documents) != len(
        requested_document_ids
    ):
        return solomon_ai_conversation_error(
            "SolomonAiConversationDocumentAccessDenied",
            (
                "One or more selected files are missing "
                "or are not authorized."
            ),
            status_code=404,
        )

    existing_document_ids = (
        durable_conversation.get("document_ids")
        if isinstance(
            durable_conversation.get("document_ids"),
            list,
        )
        else []
    )
    existing_document_id_set = {
        str(document_id or "").strip()
        for document_id in existing_document_ids
        if str(document_id or "").strip()
    }
    requested_canonical_ids = [
        str(
            document.get("document_id")
            or ""
        ).strip()
        for document in requested_documents
        if str(
            document.get("document_id")
            or ""
        ).strip()
    ]
    added_document_ids = [
        document_id
        for document_id in requested_canonical_ids
        if document_id not in existing_document_id_set
    ]
    merged_document_ids = []
    seen_document_ids = set()

    for document_id in [
        *existing_document_ids,
        *requested_canonical_ids,
    ]:
        clean_document_id = str(
            document_id or ""
        ).strip()

        if (
            not clean_document_id
            or clean_document_id in seen_document_ids
        ):
            continue

        seen_document_ids.add(
            clean_document_id
        )
        merged_document_ids.append(
            clean_document_id
        )

    merged_documents = resolve_authorized_documents(
        user_id,
        merged_document_ids,
    )

    if len(merged_documents) != len(
        merged_document_ids
    ):
        return solomon_ai_conversation_error(
            "SolomonAiConversationSourceUnavailable",
            (
                "One or more existing conversation files "
                "are no longer available."
            ),
            status_code=409,
        )

    try:
        durable_conversation = (
            replace_solomon_ai_conversation_sources(
                user_id=user_id,
                conversation_id=conversation_id,
                documents=merged_documents,
            )
        )
    except SolomonAIConversationStoreError as exc:
        status_code = (
            get_solomon_ai_source_store_error_status(
                exc
            )
        )
        return solomon_ai_conversation_error(
            "SolomonAiConversationSourceUpdateFailed",
            str(exc)
            or "Conversation sources could not be updated.",
            status_code=status_code,
        )

    conversation_packet = store_solomon_ai_conversation(
        conversation_packet=durable_conversation,
        request_id=request_id,
    )
    response_payload = build_solomon_ai_source_response(
        conversation_packet=conversation_packet,
        request_id=request_id,
        source_action="added",
    )
    response_payload["added_document_ids"] = added_document_ids
    response_payload["added_count"] = len(
        added_document_ids
    )

    logger.info(
        (
            "[solomon_ai.sources_added] request_id=%s "
            "user_id=%s conversation_id=%s added=%s total=%s"
        ),
        request_id,
        user_id,
        conversation_id,
        len(added_document_ids),
        response_payload.get("source_count"),
    )

    return jsonify(response_payload), 200


@solomon_conversations_bp.route(
    "/conversations/<conversation_id>/sources",
    methods=["GET"],
)
@login_required
def list_solomon_ai_conversation_sources(conversation_id):
    """Return authorized sources for one durable SolomonAI conversation."""

    request_id = get_request_id()
    user_id = get_current_user_id()

    if not user_id:
        return solomon_ai_conversation_error(
            "AuthenticationRequired",
            "Authentication is required to read SolomonAI sources.",
            status_code=401,
        )

    durable_conversation = (
        get_durable_solomon_ai_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            include_messages=False,
        )
    )

    if not durable_conversation:
        return solomon_ai_conversation_error(
            "SolomonAiConversationInvalid",
            "This SolomonAI conversation could not be found.",
            status_code=404,
        )

    document_ids = (
        durable_conversation.get("document_ids")
        if isinstance(
            durable_conversation.get("document_ids"),
            list,
        )
        else []
    )
    authorized_documents = resolve_authorized_documents(
        user_id,
        document_ids,
    )

    if len(authorized_documents) != len(document_ids):
        return solomon_ai_conversation_error(
            "SolomonAiConversationSourceUnavailable",
            (
                "One or more conversation sources are "
                "no longer available."
            ),
            status_code=409,
        )

    conversation_packet = store_solomon_ai_conversation(
        conversation_packet=durable_conversation,
        request_id=request_id,
    )

    logger.info(
        (
            "[solomon_ai.sources_loaded] request_id=%s user_id=%s "
            "conversation_id=%s docs=%s"
        ),
        request_id,
        user_id,
        conversation_id,
        conversation_packet.get("source_count"),
    )

    return jsonify(
        build_solomon_ai_source_response(
            conversation_packet=conversation_packet,
            request_id=request_id,
            source_action="loaded",
        )
    ), 200


@solomon_conversations_bp.route(
    "/conversations/<conversation_id>/sources/public-web",
    methods=["PUT"],
)
@login_required
def update_solomon_ai_conversation_public_web(conversation_id):
    """Persist the user-selected Public Web source permission."""

    request_id = get_request_id()
    user_id = get_current_user_id()
    payload = read_operation_payload()
    requested_selection = payload.get(
        "public_web_selected"
    )

    if not user_id:
        return solomon_ai_conversation_error(
            "AuthenticationRequired",
            "Authentication is required to update SolomonAI sources.",
            status_code=401,
        )

    if not isinstance(requested_selection, bool):
        return solomon_ai_conversation_error(
            "SolomonAiPublicWebSelectionInvalid",
            "Public Web source selection must be true or false.",
            status_code=400,
        )

    try:
        durable_conversation = (
            set_solomon_ai_conversation_public_web(
                user_id=user_id,
                conversation_id=conversation_id,
                selected=requested_selection,
            )
        )
    except SolomonAIConversationStoreError as exc:
        status_code = (
            get_solomon_ai_source_store_error_status(
                exc
            )
        )
        return solomon_ai_conversation_error(
            "SolomonAiPublicWebSelectionUpdateFailed",
            str(exc)
            or "Public Web source selection could not be updated.",
            status_code=status_code,
        )

    conversation_packet = store_solomon_ai_conversation(
        conversation_packet=durable_conversation,
        request_id=request_id,
    )
    response_payload = build_solomon_ai_source_response(
        conversation_packet=conversation_packet,
        request_id=request_id,
        source_action="public_web_updated",
    )

    logger.info(
        (
            "[solomon_ai.public_web_selection_updated] "
            "request_id=%s user_id=%s conversation_id=%s selected=%s"
        ),
        request_id,
        user_id,
        conversation_id,
        requested_selection,
    )

    return jsonify(response_payload), 200


@solomon_conversations_bp.route(
    "/conversations/<conversation_id>/sources/<document_id>",
    methods=["DELETE"],
)
@login_required
def remove_solomon_ai_conversation_source(
    conversation_id,
    document_id,
):
    """Remove one durable source association without deleting the document."""

    request_id = get_request_id()
    user_id = get_current_user_id()

    if not user_id:
        return solomon_ai_conversation_error(
            "AuthenticationRequired",
            "Authentication is required to update SolomonAI sources.",
            status_code=401,
        )

    durable_conversation = (
        get_durable_solomon_ai_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            include_messages=False,
        )
    )

    if not durable_conversation:
        return solomon_ai_conversation_error(
            "SolomonAiConversationInvalid",
            "This SolomonAI conversation could not be found.",
            status_code=404,
        )

    clean_document_id = str(
        document_id or ""
    ).strip()
    existing_document_ids = (
        durable_conversation.get("document_ids")
        if isinstance(
            durable_conversation.get("document_ids"),
            list,
        )
        else []
    )
    remaining_document_ids = [
        existing_document_id
        for existing_document_id in existing_document_ids
        if existing_document_id != clean_document_id
    ]
    source_action = (
        "removed"
        if remaining_document_ids
        != existing_document_ids
        else "not_present"
    )

    if source_action == "removed":
        remaining_documents = resolve_authorized_documents(
            user_id,
            remaining_document_ids,
        )

        if len(remaining_documents) != len(
            remaining_document_ids
        ):
            return solomon_ai_conversation_error(
                "SolomonAiConversationSourceUnavailable",
                (
                    "One or more remaining conversation "
                    "sources are no longer available."
                ),
                status_code=409,
            )

        try:
            durable_conversation = (
                replace_solomon_ai_conversation_sources(
                    user_id=user_id,
                    conversation_id=conversation_id,
                    documents=remaining_documents,
                )
            )
        except SolomonAIConversationStoreError as exc:
            logger.warning(
                (
                    "[solomon_ai.source_remove_failed] "
                    "request_id=%s user_id=%s "
                    "conversation_id=%s document_id=%s "
                    "error=%s"
                ),
                request_id,
                user_id,
                conversation_id,
                clean_document_id,
                exc,
            )
            status_code = (
                get_solomon_ai_source_store_error_status(
                    exc
                )
            )
            return solomon_ai_conversation_error(
                "SolomonAiConversationSourceRemoveFailed",
                str(exc)
                or "Conversation source could not be removed.",
                status_code=status_code,
            )

    conversation_packet = store_solomon_ai_conversation(
        conversation_packet=durable_conversation,
        request_id=request_id,
    )
    response_payload = build_solomon_ai_source_response(
        conversation_packet=conversation_packet,
        request_id=request_id,
        source_action=source_action,
    )
    response_payload["removed_document_id"] = clean_document_id

    logger.info(
        (
            "[solomon_ai.source_removed] request_id=%s "
            "user_id=%s conversation_id=%s document_id=%s "
            "action=%s total=%s"
        ),
        request_id,
        user_id,
        conversation_id,
        clean_document_id,
        source_action,
        response_payload.get("source_count"),
    )

    return jsonify(response_payload), 200


@document_operations_bp.route("/ai/session", methods=["POST"])
@login_required
def create_document_ai_session():
    """Handle the legacy SolomonAI source-session endpoint."""

    return create_or_extend_solomon_ai_conversation(
        legacy_response=True,
    )


@document_operations_bp.route("/ai/<conversation_id>", methods=["GET"])
@login_required
def render_legacy_document_ai_conversation(conversation_id):
    """Redirect an authorized legacy link into the durable SolomonAI workspace."""

    clean_conversation_id = str(
        conversation_id or ""
    ).strip()
    user_id = get_current_user_id()

    if not clean_conversation_id or not user_id:
        return redirect("/ai", code=303)

    durable_conversation = (
        get_durable_solomon_ai_conversation(
            user_id=user_id,
            conversation_id=clean_conversation_id,
            include_messages=False,
        )
    )

    if not durable_conversation:
        return redirect("/ai", code=303)

    store_solomon_ai_conversation(
        conversation_packet=durable_conversation,
        request_id=get_request_id(),
    )

    return redirect(
        get_solomon_ai_conversation_url(
            clean_conversation_id
        ),
        code=303,
    )


@document_operations_bp.route("/run", methods=["POST"])
@login_required
def run_document_operation():
    """Submit one server-authorized document operation job against selected files."""

    request_id = get_request_id()
    payload = read_operation_payload()
    operation_key = str(payload.get("operation") or "").strip()
    document_ids = collect_document_ids(payload)

    try:
        user_id, operation, documents = prepare_operation_context(
            operation_key,
            document_ids,
        )
        submitted_packet = submit_document_operation_job(
            operation=operation,
            documents=documents,
            user_id=user_id,
            request_id=request_id,
        )
    except DocumentOperationJobError as exc:
        return operation_error(
            exc.error_code,
            exc.user_output,
            status_code=exc.status_code,
            extra={"operation": operation_key},
        )

    return jsonify(submitted_packet), 202


@document_operations_bp.route("/job/<job_id>", methods=["GET"])
@login_required
def get_document_operation_job(job_id):
    """Return one server-owned document operation job packet."""

    user_id = get_current_user_id()

    if not user_id:
        return operation_error(
            "AuthenticationRequired",
            "Authentication is required to read document operation jobs.",
            status_code=401,
        )

    try:
        packet = get_document_operation_job_packet(
            job_id=job_id,
            user_id=user_id,
        )
    except DocumentOperationJobError as exc:
        return operation_error(
            exc.error_code,
            exc.user_output,
            status_code=exc.status_code,
            extra={"job_id": job_id},
        )

    return jsonify(packet), 200


__all__ = [
    "document_operations_bp",
    "solomon_conversations_bp",
]