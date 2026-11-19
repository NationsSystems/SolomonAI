# -------------------------------------------------------------------
# FILE: solomon_ai_conversation_store.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# Durable SolomonAI conversation persistence.
#
# Owns conversation identity, source membership, message ordering,
# history lookup, group context, lifecycle management, and
# serialization. Flask session state may point to an active
# conversation but is never the persistence authority.
# -------------------------------------------------------------------

from datetime import datetime
import re
import uuid

from sqlalchemy import func, inspect, text
from sqlalchemy.orm import selectinload

from solomon_core.db import SessionLocal, engine
from solomon_core.models import (
    FileRegistry,
    Organization,
    OrganizationMembership,
    SolomonAIConversation,
    SolomonAIConversationMessage,
    SolomonAIConversationOrganizationContext,
    SolomonAIConversationSource,
    utc_now,
)
from solomon_core.workspace_reader.workspace_reader_file_access import (
    QUERY_ACTION,
    resolve_file_access_decision,
    resolve_file_record_by_identifier,
)


SOLOMON_AI_CONVERSATION_CONTRACT = (
    "document_ai_explicit_source_session"
)
SOLOMON_AI_SOURCE_MEMBERSHIP_CONTRACT = (
    "solomon_ai_conversation_source_membership_v1"
)
SOLOMON_AI_OPERATION_KEY = "ask_solomon_ai"
SOLOMON_AI_OPERATION_LABEL = "Ask SolomonAI"
SOLOMON_AI_DEFAULT_TITLE = "Untitled chat"
SOLOMON_AI_LEGACY_DEFAULT_TITLE = "New conversation"
SOLOMON_AI_HISTORY_LIMIT = 50
SOLOMON_AI_TITLE_MAX_LENGTH = 96
SOLOMON_AI_AUTO_TITLE_MAX_LENGTH = 64
SOLOMON_AI_AUTOMATIC_TITLES = frozenset({
    SOLOMON_AI_DEFAULT_TITLE,
    SOLOMON_AI_LEGACY_DEFAULT_TITLE,
})
ACTIVE_STATUS = "active"


class SolomonAIConversationStoreError(Exception):
    """Raised when durable conversation state cannot be preserved."""


SOLOMON_AI_CONVERSATION_TABLE = "solomon_ai_conversations"
SOLOMON_AI_MESSAGE_TABLE = "solomon_ai_conversation_messages"
_SOLOMON_AI_SCHEMA_VERIFIED = False
_SOLOMON_AI_CONVERSATION_COLUMN_DDL = {
    "public_web_selected": (
        "public_web_selected BOOLEAN NOT NULL DEFAULT FALSE"
    ),
}
_SOLOMON_AI_MESSAGE_COLUMN_DDL = {
    "bridge": "bridge TEXT NULL",
    "suggestions": "suggestions JSON NULL",
    "packet_json": "packet_json JSON NULL",
    "request_id": "request_id VARCHAR(64) NULL",
    "status": "status VARCHAR(32) NOT NULL DEFAULT 'complete'",
}


def _ensure_solomon_ai_conversation_schema() -> None:
    """Create missing durable SolomonAI conversation columns safely."""

    global _SOLOMON_AI_SCHEMA_VERIFIED

    if _SOLOMON_AI_SCHEMA_VERIFIED:
        return

    SolomonAIConversation.__table__.create(
        bind=engine,
        checkfirst=True,
    )
    SolomonAIConversationMessage.__table__.create(
        bind=engine,
        checkfirst=True,
    )
    SolomonAIConversationSource.__table__.create(
        bind=engine,
        checkfirst=True,
    )
    SolomonAIConversationOrganizationContext.__table__.create(
        bind=engine,
        checkfirst=True,
    )

    inspector = inspect(
        engine
    )
    conversation_columns = {
        column["name"]
        for column in inspector.get_columns(
            SOLOMON_AI_CONVERSATION_TABLE
        )
    }
    missing_conversation_columns = [
        column_name
        for column_name in _SOLOMON_AI_CONVERSATION_COLUMN_DDL
        if column_name not in conversation_columns
    ]
    message_columns = {
        column["name"]
        for column in inspector.get_columns(
            SOLOMON_AI_MESSAGE_TABLE
        )
    }
    missing_message_columns = [
        column_name
        for column_name in _SOLOMON_AI_MESSAGE_COLUMN_DDL
        if column_name not in message_columns
    ]

    if missing_conversation_columns or missing_message_columns:
        with engine.begin() as connection:
            for column_name in missing_conversation_columns:
                connection.execute(
                    text(
                        "ALTER TABLE "
                        f"{SOLOMON_AI_CONVERSATION_TABLE} "
                        "ADD COLUMN "
                        f"{_SOLOMON_AI_CONVERSATION_COLUMN_DDL[column_name]}"
                    )
                )

            for column_name in missing_message_columns:
                connection.execute(
                    text(
                        "ALTER TABLE "
                        f"{SOLOMON_AI_MESSAGE_TABLE} "
                        "ADD COLUMN "
                        f"{_SOLOMON_AI_MESSAGE_COLUMN_DDL[column_name]}"
                    )
                )

    _SOLOMON_AI_SCHEMA_VERIFIED = True


def _clean_value(value) -> str:
    """Return normalized single-space text."""

    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _clean_conversation_id(value) -> str:
    """Return a safe opaque conversation identifier."""

    clean_value = _clean_value(value)

    if not clean_value:
        return ""

    if len(clean_value) > 64:
        return ""

    if not re.fullmatch(r"[A-Za-z0-9_-]+", clean_value):
        return ""

    return clean_value


def _clean_organization_id(value) -> str:
    """Return a normalized group authority identifier."""

    clean_value = _clean_value(value)

    if not clean_value or len(clean_value) > 64:
        return ""

    return clean_value


def _normalize_conversation_title(value) -> str:
    """Return one valid user-managed conversation title."""

    clean_title = _clean_value(value)

    if not clean_title:
        raise SolomonAIConversationStoreError(
            "A conversation title is required."
        )

    if len(clean_title) > SOLOMON_AI_TITLE_MAX_LENGTH:
        raise SolomonAIConversationStoreError(
            (
                "Conversation titles may not exceed "
                f"{SOLOMON_AI_TITLE_MAX_LENGTH} characters."
            )
        )

    return clean_title


def _format_history_label(value: datetime | None) -> str:
    """Return a stable cross-platform conversation date label."""

    if not value:
        return ""

    return value.strftime(
        "%b %d, %Y"
    ).replace(
        " 0",
        " ",
    )


def _is_automatic_conversation_title(value) -> bool:
    """Return whether a title is still an automatic placeholder."""

    clean_title = _clean_value(value)

    return bool(
        not clean_title
        or clean_title in SOLOMON_AI_AUTOMATIC_TITLES
    )


def _build_title(user_content: str) -> str:
    """Build a concise title from the first user message."""

    clean_content = _clean_value(user_content)

    if not clean_content:
        return SOLOMON_AI_DEFAULT_TITLE

    title_limit = min(
        SOLOMON_AI_AUTO_TITLE_MAX_LENGTH,
        SOLOMON_AI_TITLE_MAX_LENGTH,
    )

    if len(clean_content) <= title_limit:
        return clean_content

    candidate = clean_content[
        :title_limit
    ]
    word_boundary = candidate.rfind(" ")

    if word_boundary >= title_limit // 2:
        candidate = candidate[
            :word_boundary
        ]

    shortened = candidate.rstrip(
        " ,.;:!?-"
    )

    if not shortened:
        return SOLOMON_AI_DEFAULT_TITLE

    return f"{shortened}…"


def _normalize_suggestions(value) -> list:
    """Return at most three non-empty suggestion strings."""

    if not isinstance(value, list):
        return []

    suggestions = []

    for item in value:
        clean_item = _clean_value(item)

        if not clean_item:
            continue

        suggestions.append(clean_item[:255])

        if len(suggestions) == 3:
            break

    return suggestions


def _resolve_context_state(
    db_session,
    context: SolomonAIConversationOrganizationContext | None,
    user_id: int,
    *,
    lock_authority: bool = False,
) -> dict:
    """Return the current validity of one durable group binding."""

    if not context:
        return {
            "is_bound": False,
            "is_active": True,
            "organization_id": "",
            "group_id": "",
            "membership_id": None,
        }

    organization_query = db_session.query(
        Organization
    ).filter(
        Organization.organization_id
        == context.organization_id
    )

    if lock_authority:
        organization_query = (
            organization_query.with_for_update()
        )

    organization = organization_query.first()
    organization_active = bool(
        organization
        and organization.status == ACTIVE_STATUS
        and organization.suspended_at is None
    )
    membership_active = True

    if context.membership_id:
        membership_query = db_session.query(
            OrganizationMembership
        ).filter(
            OrganizationMembership.id
            == context.membership_id,
            OrganizationMembership.organization_id
            == context.organization_id,
            OrganizationMembership.user_id
            == user_id,
        )

        if lock_authority:
            membership_query = (
                membership_query.with_for_update()
            )

        membership = membership_query.first()
        membership_active = bool(
            membership
            and membership.status == ACTIVE_STATUS
            and membership.removed_at is None
        )

    bound_by_user_valid = bool(
        not context.bound_by_user_id
        or int(context.bound_by_user_id) == int(user_id)
    )

    return {
        "is_bound": True,
        "is_active": bool(
            organization_active
            and membership_active
            and bound_by_user_valid
        ),
        "organization_id": _clean_organization_id(
            context.organization_id
        ),
        "group_id": _clean_organization_id(
            context.organization_id
        ),
        "membership_id": context.membership_id,
    }


def _default_group_membership(
    db_session,
    user_id: int,
    *,
    lock_authority: bool = False,
) -> tuple[OrganizationMembership, Organization] | None:
    """
    Return the user's default active group membership, when one exists.

    This establishes the account-level ceiling for new SolomonAI
    conversations: users with an active group membership begin in group
    context; users without one begin in personal context.
    """

    clean_user_id = int(user_id or 0)

    if not clean_user_id:
        return None

    query = (
        db_session.query(
            OrganizationMembership,
            Organization,
        )
        .join(
            Organization,
            Organization.organization_id
            == OrganizationMembership.organization_id,
        )
        .filter(
            OrganizationMembership.user_id == clean_user_id,
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
            Organization.status == ACTIVE_STATUS,
            Organization.suspended_at.is_(None),
        )
        .order_by(
            OrganizationMembership.is_primary.desc(),
            OrganizationMembership.id.asc(),
        )
    )

    if lock_authority:
        query = query.with_for_update()

    return query.first()


def _create_default_conversation_context(
    db_session,
    conversation: SolomonAIConversation,
    user_id: int,
) -> SolomonAIConversationOrganizationContext | None:
    """
    Bind a new conversation to the user's active group when available.

    No group row is created here. The function only uses an existing
    active group membership as durable account context. If the user is
    not a group member, the conversation remains personal and unbound.
    """

    membership_result = _default_group_membership(
        db_session,
        user_id,
        lock_authority=True,
    )

    if not membership_result:
        return None

    membership, organization = membership_result

    context = SolomonAIConversationOrganizationContext(
        conversation_id=conversation.conversation_id,
        organization_id=organization.organization_id,
        membership_id=membership.id,
        bound_by_user_id=user_id,
    )

    db_session.add(context)
    db_session.flush()

    return context


def _resolve_authorized_source(
    db_session,
    source: SolomonAIConversationSource,
    user_id: int,
) -> tuple[FileRegistry, dict] | None:
    """Return the current query-authorized file and access decision for one source."""

    record = None

    if source.file_registry_id:
        record = db_session.get(
            FileRegistry,
            source.file_registry_id,
        )

    if not record:
        record = resolve_file_record_by_identifier(
            db_session,
            source.source_document_id,
        )

    if not record:
        return None

    access_decision = resolve_file_access_decision(
        db_session,
        record,
        user_id,
        action=QUERY_ACTION,
    )

    if not access_decision:
        return None

    return record, access_decision


def _serialize_source(
    source: SolomonAIConversationSource,
    *,
    record: FileRegistry,
    access_decision: dict,
) -> dict:
    """Serialize one currently query-authorized source-membership record."""

    document_id = (
        _clean_value(record.random_name)
        or _clean_value(source.source_document_id)
    )
    source_name = (
        _clean_value(record.original_name)
        or _clean_value(source.source_name)
        or document_id
    )

    return {
        "document_id": document_id,
        "random_name": document_id,
        "file_id": str(record.id or ""),
        "original_name": source_name,
        "filename": source_name,
        "reader_url": (
            f"/workspace/file/{document_id}/reader"
            if document_id
            else ""
        ),
        "workspace_reader_url": (
            f"/workspace/file/{document_id}/reader"
            if document_id
            else ""
        ),
        "analysis_status": "not_started",
        "source_order": source.source_order,
        "attached_at": (
            source.created_at.isoformat()
            if source.created_at
            else ""
        ),
        "access_scope": access_decision.get(
            "access_scope"
        ),
        "permission": access_decision.get(
            "permission"
        ),
        "authorized_action": access_decision.get(
            "authorized_action"
        ),
        "organization_id": access_decision.get(
            "organization_id"
        ),
        "group_id": access_decision.get(
            "group_id"
        ),
        "membership_id": access_decision.get(
            "membership_id"
        ),
        "membership_role": access_decision.get(
            "membership_role"
        ),
        "group_membership_id": access_decision.get(
            "group_membership_id"
        ),
        "custody_id": access_decision.get(
            "custody_id"
        ),
        "custody_mode": access_decision.get(
            "custody_mode"
        ),
        "library_scope": access_decision.get(
            "library_scope"
        ),
        "grant_id": access_decision.get(
            "grant_id"
        ),
        "group_grant_id": access_decision.get(
            "group_grant_id"
        ),
        "grant_type": access_decision.get(
            "grant_type"
        ),
        "authority_basis": access_decision.get(
            "authority_basis"
        ),
        "policy_version": access_decision.get(
            "policy_version"
        ),
        "is_discoverable": access_decision.get(
            "is_discoverable"
        ),
        "allow_ai_query": access_decision.get(
            "allow_ai_query"
        ),
        "expires_at": access_decision.get(
            "expires_at"
        ),
    }


def _get_conversation_context_state(
    db_session,
    conversation: SolomonAIConversation,
    user_id: int,
) -> dict:
    """Return the current group context for one conversation."""

    context = (
        db_session.query(
            SolomonAIConversationOrganizationContext
        )
        .filter(
            SolomonAIConversationOrganizationContext.conversation_id
            == conversation.conversation_id
        )
        .first()
    )

    return _resolve_context_state(
        db_session,
        context,
        user_id,
    )


def _serialize_authorized_sources(
    db_session,
    conversation: SolomonAIConversation,
    user_id: int,
    *,
    context_state: dict | None = None,
) -> list:
    """Serialize sources allowed by file query and conversation authority."""

    effective_context_state = (
        context_state
        if isinstance(context_state, dict)
        else _get_conversation_context_state(
            db_session,
            conversation,
            user_id,
        )
    )
    serialized_sources = []

    for source in conversation.sources:
        authorized_source = _resolve_authorized_source(
            db_session,
            source,
            user_id,
        )

        if not authorized_source:
            continue

        record, access_decision = authorized_source
        source_organization_id = _clean_organization_id(
            access_decision.get("organization_id")
        )

        if source_organization_id:
            if (
                not effective_context_state["is_bound"]
                or not effective_context_state["is_active"]
                or source_organization_id
                != effective_context_state["organization_id"]
            ):
                continue

        serialized_sources.append(
            _serialize_source(
                source,
                record=record,
                access_decision=access_decision,
            )
        )

    return serialized_sources


def _serialize_message(
    message: SolomonAIConversationMessage,
) -> dict:
    """Serialize one persisted conversation message."""

    return {
        "message_id": str(message.id or ""),
        "conversation_id": message.conversation_id,
        "role": _clean_value(message.role),
        "content": str(message.content or "").strip(),
        "bridge": str(message.bridge or "").strip(),
        "suggestions": (
            message.suggestions
            if isinstance(message.suggestions, list)
            else []
        ),
        "request_id": _clean_value(message.request_id),
        "message_order": message.message_order,
        "status": _clean_value(message.status) or "complete",
        "created_at": (
            message.created_at.isoformat()
            if message.created_at
            else ""
        ),
    }


def _serialize_conversation(
    db_session,
    conversation: SolomonAIConversation,
    *,
    include_messages: bool = True,
) -> dict:
    """Serialize one durable conversation with current source authority."""

    authority_context = _get_conversation_context_state(
        db_session,
        conversation,
        conversation.user_id,
    )
    sources = _serialize_authorized_sources(
        db_session,
        conversation,
        conversation.user_id,
        context_state=authority_context,
    )
    messages = (
        [
            _serialize_message(message)
            for message in conversation.messages
        ]
        if include_messages
        else []
    )
    document_ids = [
        source["document_id"]
        for source in sources
        if source["document_id"]
    ]
    document_names = [
        source["original_name"]
        for source in sources
        if source["original_name"]
    ]
    group_context = {
        "is_bound": bool(
            authority_context["is_bound"]
        ),
        "is_active": bool(
            authority_context["is_active"]
        ),
        "group_id": (
            authority_context.get("group_id")
            or authority_context.get("organization_id")
            or ""
        ),
        "membership_id": (
            authority_context["membership_id"]
        ),
    }
    organization_context = {
        "is_bound": group_context["is_bound"],
        "is_active": group_context["is_active"],
        "organization_id": (
            authority_context.get("organization_id")
            or group_context["group_id"]
        ),
        "membership_id": group_context["membership_id"],
    }

    return {
        "conversation_id": conversation.conversation_id,
        "session_id": conversation.conversation_id,
        "user_id": conversation.user_id,
        "title": (
            _clean_value(conversation.title)
            or SOLOMON_AI_DEFAULT_TITLE
        ),
        "status": (
            _clean_value(conversation.status)
            or "active"
        ),
        "contract": (
            _clean_value(conversation.contract)
            or SOLOMON_AI_CONVERSATION_CONTRACT
        ),
        "operation": (
            _clean_value(conversation.operation_key)
            or SOLOMON_AI_OPERATION_KEY
        ),
        "operation_label": SOLOMON_AI_OPERATION_LABEL,
        "source_membership_contract": (
            _clean_value(
                conversation.source_membership_contract
            )
            or SOLOMON_AI_SOURCE_MEMBERSHIP_CONTRACT
        ),
        "public_web_selected": bool(
            conversation.public_web_selected
        ),
        "group_context": group_context,
        "organization_context": organization_context,
        "document_ids": document_ids,
        "document_names": document_names,
        "source_count": len(sources),
        "sources": sources,
        "messages": messages,
        "message_count": len(messages),
        "created_at": (
            conversation.created_at.isoformat()
            if conversation.created_at
            else ""
        ),
        "updated_at": (
            conversation.updated_at.isoformat()
            if conversation.updated_at
            else ""
        ),
        "last_message_at": (
            conversation.last_message_at.isoformat()
            if conversation.last_message_at
            else ""
        ),
    }


def _conversation_query(
    db_session,
    *,
    include_messages: bool,
):
    """Return the canonical conversation ORM query."""

    options = [
        selectinload(
            SolomonAIConversation.sources
        ),
    ]

    if include_messages:
        options.append(
            selectinload(
                SolomonAIConversation.messages
            )
        )

    return db_session.query(
        SolomonAIConversation
    ).options(
        *options
    )


def create_solomon_ai_conversation(
    *,
    user_id: int,
    conversation_id: str = "",
) -> dict:
    """Create one durable user-owned SolomonAI conversation."""

    clean_user_id = int(user_id or 0)
    clean_conversation_id = (
        _clean_conversation_id(conversation_id)
        or uuid.uuid4().hex
    )

    if not clean_user_id:
        raise SolomonAIConversationStoreError(
            "A valid user is required to create a conversation."
        )

    _ensure_solomon_ai_conversation_schema()

    db_session = SessionLocal()

    try:
        existing = db_session.get(
            SolomonAIConversation,
            clean_conversation_id,
        )

        if existing:
            if existing.user_id != clean_user_id:
                raise SolomonAIConversationStoreError(
                    "The conversation identifier is already in use."
                )

            return get_solomon_ai_conversation(
                user_id=clean_user_id,
                conversation_id=clean_conversation_id,
            )

        conversation = SolomonAIConversation(
            conversation_id=clean_conversation_id,
            user_id=clean_user_id,
            title=SOLOMON_AI_DEFAULT_TITLE,
            status="active",
            contract=SOLOMON_AI_CONVERSATION_CONTRACT,
            source_membership_contract=(
                SOLOMON_AI_SOURCE_MEMBERSHIP_CONTRACT
            ),
            operation_key=SOLOMON_AI_OPERATION_KEY,
        )
        db_session.add(conversation)
        db_session.flush()

        _create_default_conversation_context(
            db_session,
            conversation,
            clean_user_id,
        )

        packet = _serialize_conversation(
            db_session,
            conversation,
            include_messages=True,
        )

        db_session.commit()

        return packet
    except SolomonAIConversationStoreError:
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()
        raise SolomonAIConversationStoreError(
            "The SolomonAI conversation could not be created."
        ) from exc
    finally:
        SessionLocal.remove()


def get_solomon_ai_conversation(
    *,
    user_id: int,
    conversation_id: str,
    include_messages: bool = True,
) -> dict:
    """Return one durable conversation owned by the user."""

    clean_user_id = int(user_id or 0)
    clean_conversation_id = _clean_conversation_id(
        conversation_id
    )

    if not clean_user_id or not clean_conversation_id:
        return {}

    _ensure_solomon_ai_conversation_schema()

    db_session = SessionLocal()

    try:
        conversation = (
            _conversation_query(
                db_session,
                include_messages=include_messages,
            )
            .filter(
                SolomonAIConversation.conversation_id
                == clean_conversation_id,
                SolomonAIConversation.user_id
                == clean_user_id,
                SolomonAIConversation.deleted_at.is_(None),
            )
            .first()
        )

        if not conversation:
            return {}

        return _serialize_conversation(
            db_session,
            conversation,
            include_messages=include_messages,
        )
    finally:
        SessionLocal.remove()


def get_solomon_ai_conversation_source_membership_count(
    *,
    user_id: int,
    conversation_id: str,
) -> int:
    """
    Return the raw persisted source-membership count for one owned conversation.

    This is an internal execution-authority primitive. It deliberately does not
    serialize source identifiers or bypass current file authorization. Callers
    use the count only to distinguish a genuinely zero-source conversation from
    one whose persisted source membership no longer reauthorizes.
    """

    clean_user_id = int(user_id or 0)
    clean_conversation_id = _clean_conversation_id(
        conversation_id
    )

    if not clean_user_id or not clean_conversation_id:
        return 0

    _ensure_solomon_ai_conversation_schema()

    db_session = SessionLocal()

    try:
        conversation_exists = (
            db_session.query(
                SolomonAIConversation.conversation_id
            )
            .filter(
                SolomonAIConversation.conversation_id
                == clean_conversation_id,
                SolomonAIConversation.user_id
                == clean_user_id,
                SolomonAIConversation.deleted_at.is_(None),
            )
            .first()
        )

        if not conversation_exists:
            return 0

        return int(
            db_session.query(
                func.count(
                    SolomonAIConversationSource.id
                )
            )
            .filter(
                SolomonAIConversationSource.conversation_id
                == clean_conversation_id
            )
            .scalar()
            or 0
        )
    finally:
        SessionLocal.remove()


def get_latest_solomon_ai_conversation(
    *,
    user_id: int,
    include_messages: bool = True,
) -> dict:
    """Return the user's most recently active durable conversation."""

    clean_user_id = int(user_id or 0)

    if not clean_user_id:
        return {}

    _ensure_solomon_ai_conversation_schema()

    db_session = SessionLocal()

    try:
        activity_timestamp = func.coalesce(
            SolomonAIConversation.last_message_at,
            SolomonAIConversation.updated_at,
            SolomonAIConversation.created_at,
        )
        conversation = (
            _conversation_query(
                db_session,
                include_messages=include_messages,
            )
            .filter(
                SolomonAIConversation.user_id
                == clean_user_id,
                SolomonAIConversation.status
                == "active",
                SolomonAIConversation.deleted_at.is_(None),
            )
            .order_by(
                activity_timestamp.desc(),
                SolomonAIConversation.created_at.desc(),
            )
            .first()
        )

        if not conversation:
            return {}

        return _serialize_conversation(
            db_session,
            conversation,
            include_messages=include_messages,
        )
    finally:
        SessionLocal.remove()


def list_solomon_ai_conversation_history(
    *,
    user_id: int,
    active_conversation_id: str = "",
    limit: int = SOLOMON_AI_HISTORY_LIMIT,
) -> list:
    """Return recent durable conversations for the History panel."""

    clean_user_id = int(user_id or 0)

    if not clean_user_id:
        return []

    _ensure_solomon_ai_conversation_schema()

    safe_limit = max(
        1,
        min(int(limit or SOLOMON_AI_HISTORY_LIMIT), 100),
    )
    db_session = SessionLocal()

    try:
        activity_timestamp = func.coalesce(
            SolomonAIConversation.last_message_at,
            SolomonAIConversation.updated_at,
            SolomonAIConversation.created_at,
        )
        conversations = (
            db_session.query(
                SolomonAIConversation
            )
            .options(
                selectinload(
                    SolomonAIConversation.sources
                )
            )
            .filter(
                SolomonAIConversation.user_id
                == clean_user_id,
                SolomonAIConversation.deleted_at.is_(None),
            )
            .order_by(
                activity_timestamp.desc(),
                SolomonAIConversation.created_at.desc(),
            )
            .limit(safe_limit)
            .all()
        )

        return [
            {
                "conversation_id": conversation.conversation_id,
                "title": (
                    _clean_value(conversation.title)
                    or SOLOMON_AI_DEFAULT_TITLE
                ),
                "status": (
                    _clean_value(conversation.status)
                    or "active"
                ),
                "created_at": (
                    conversation.created_at.isoformat()
                    if conversation.created_at
                    else ""
                ),
                "updated_at": (
                    conversation.updated_at.isoformat()
                    if conversation.updated_at
                    else ""
                ),
                "created_label": _format_history_label(
                    conversation.created_at
                ),
                "updated_label": _format_history_label(
                    conversation.last_message_at
                    or conversation.updated_at
                    or conversation.created_at
                ),
                "source_count": len(
                    _serialize_authorized_sources(
                        db_session,
                        conversation,
                        clean_user_id,
                    )
                ),
                "is_active": (
                    conversation.conversation_id
                    == _clean_conversation_id(
                        active_conversation_id
                    )
                ),
            }
            for conversation in conversations
        ]
    finally:
        SessionLocal.remove()


def rename_solomon_ai_conversation(
    *,
    user_id: int,
    conversation_id: str,
    title: str,
) -> dict:
    """Rename one durable conversation owned by the user."""

    clean_user_id = int(user_id or 0)
    clean_conversation_id = _clean_conversation_id(
        conversation_id
    )
    clean_title = _normalize_conversation_title(
        title
    )

    if not clean_user_id or not clean_conversation_id:
        raise SolomonAIConversationStoreError(
            "A valid owned SolomonAI conversation is required."
        )

    _ensure_solomon_ai_conversation_schema()

    db_session = SessionLocal()

    try:
        conversation = (
            _conversation_query(
                db_session,
                include_messages=True,
            )
            .filter(
                SolomonAIConversation.conversation_id
                == clean_conversation_id,
                SolomonAIConversation.user_id
                == clean_user_id,
                SolomonAIConversation.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )

        if not conversation:
            raise SolomonAIConversationStoreError(
                "The SolomonAI conversation was not found."
            )

        conversation.title = clean_title
        conversation.updated_at = utc_now()
        db_session.flush()

        packet = _serialize_conversation(
            db_session,
            conversation,
            include_messages=True,
        )
        db_session.commit()

        return packet
    except SolomonAIConversationStoreError:
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()
        raise SolomonAIConversationStoreError(
            "The SolomonAI conversation could not be renamed."
        ) from exc
    finally:
        SessionLocal.remove()


def delete_solomon_ai_conversation(
    *,
    user_id: int,
    conversation_id: str,
) -> bool:
    """Soft-delete one durable conversation owned by the user."""

    clean_user_id = int(user_id or 0)
    clean_conversation_id = _clean_conversation_id(
        conversation_id
    )

    if not clean_user_id or not clean_conversation_id:
        raise SolomonAIConversationStoreError(
            "A valid owned SolomonAI conversation is required."
        )

    _ensure_solomon_ai_conversation_schema()

    db_session = SessionLocal()

    try:
        conversation = (
            db_session.query(
                SolomonAIConversation
            )
            .filter(
                SolomonAIConversation.conversation_id
                == clean_conversation_id,
                SolomonAIConversation.user_id
                == clean_user_id,
                SolomonAIConversation.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )

        if not conversation:
            raise SolomonAIConversationStoreError(
                "The SolomonAI conversation was not found."
            )

        timestamp = utc_now()
        conversation.status = "deleted"
        conversation.deleted_at = timestamp
        conversation.updated_at = timestamp
        db_session.commit()

        return True
    except SolomonAIConversationStoreError:
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()
        raise SolomonAIConversationStoreError(
            "The SolomonAI conversation could not be deleted."
        ) from exc
    finally:
        SessionLocal.remove()


def set_solomon_ai_conversation_public_web(
    *,
    user_id: int,
    conversation_id: str,
    selected: bool,
) -> dict:
    """Persist whether Public Web is an allowed source for one conversation."""

    clean_user_id = int(user_id or 0)
    clean_conversation_id = _clean_conversation_id(
        conversation_id
    )

    if not clean_user_id or not clean_conversation_id:
        raise SolomonAIConversationStoreError(
            "A valid owned SolomonAI conversation is required."
        )

    if not isinstance(selected, bool):
        raise SolomonAIConversationStoreError(
            "Public Web source selection must be true or false."
        )

    _ensure_solomon_ai_conversation_schema()

    db_session = SessionLocal()

    try:
        conversation = (
            _conversation_query(
                db_session,
                include_messages=False,
            )
            .filter(
                SolomonAIConversation.conversation_id
                == clean_conversation_id,
                SolomonAIConversation.user_id
                == clean_user_id,
                SolomonAIConversation.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )

        if not conversation:
            raise SolomonAIConversationStoreError(
                "The SolomonAI conversation was not found."
            )

        conversation.public_web_selected = selected
        conversation.updated_at = utc_now()
        db_session.flush()

        packet = _serialize_conversation(
            db_session,
            conversation,
            include_messages=False,
        )
        db_session.commit()

        return packet
    except SolomonAIConversationStoreError:
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()
        raise SolomonAIConversationStoreError(
            "Public Web source selection could not be updated."
        ) from exc
    finally:
        SessionLocal.remove()


def replace_solomon_ai_conversation_sources(
    *,
    user_id: int,
    conversation_id: str,
    documents: list,
) -> dict:
    """Replace sources while preserving one durable group context."""

    clean_user_id = int(user_id or 0)
    clean_conversation_id = _clean_conversation_id(
        conversation_id
    )

    if not clean_user_id or not clean_conversation_id:
        raise SolomonAIConversationStoreError(
            "A valid owned SolomonAI conversation is required."
        )

    _ensure_solomon_ai_conversation_schema()

    db_session = SessionLocal()

    try:
        conversation = (
            db_session.query(
                SolomonAIConversation
            )
            .filter(
                SolomonAIConversation.conversation_id
                == clean_conversation_id,
                SolomonAIConversation.user_id
                == clean_user_id,
                SolomonAIConversation.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )

        if not conversation:
            raise SolomonAIConversationStoreError(
                "The SolomonAI conversation was not found."
            )

        context = (
            db_session.query(
                SolomonAIConversationOrganizationContext
            )
            .filter(
                SolomonAIConversationOrganizationContext.conversation_id
                == clean_conversation_id
            )
            .with_for_update()
            .first()
        )
        context_state = _resolve_context_state(
            db_session,
            context,
            clean_user_id,
            lock_authority=True,
        )
        desired_sources = []
        seen_document_ids = set()

        for document in documents or []:
            if not isinstance(document, dict):
                raise SolomonAIConversationStoreError(
                    "One or more selected documents were invalid."
                )

            identifier = _clean_value(
                document.get("document_id")
                or document.get("random_name")
                or document.get("file_id")
            )

            if not identifier:
                raise SolomonAIConversationStoreError(
                    "One or more selected documents were invalid."
                )

            record = resolve_file_record_by_identifier(
                db_session,
                identifier,
            )

            if not record:
                raise SolomonAIConversationStoreError(
                    (
                        "One or more selected documents are missing "
                        "or are not authorized."
                    )
                )

            access_decision = resolve_file_access_decision(
                db_session,
                record,
                clean_user_id,
                action=QUERY_ACTION,
            )

            if not access_decision:
                raise SolomonAIConversationStoreError(
                    (
                        "One or more selected documents are missing "
                        "or are not authorized."
                    )
                )

            document_id = _clean_value(
                record.random_name
            )

            if not document_id:
                raise SolomonAIConversationStoreError(
                    "One or more selected documents were invalid."
                )

            if document_id in seen_document_ids:
                continue

            seen_document_ids.add(document_id)
            desired_sources.append({
                "document_id": document_id,
                "file_registry_id": record.id,
                "source_name": (
                    _clean_value(record.original_name)
                    or document_id
                ),
                "organization_id": _clean_organization_id(
                    access_decision.get("organization_id")
                ),
                "membership_id": access_decision.get(
                    "membership_id"
                ),
            })

        desired_organization_ids = {
            source["organization_id"]
            for source in desired_sources
            if source["organization_id"]
        }

        if len(desired_organization_ids) > 1:
            raise SolomonAIConversationStoreError(
                (
                    "A SolomonAI conversation cannot combine "
                    "documents from different groups."
                )
            )

        desired_organization_id = (
            next(iter(desired_organization_ids))
            if desired_organization_ids
            else ""
        )

        if context:
            if desired_organization_id:
                if not context_state["is_active"]:
                    raise SolomonAIConversationStoreError(
                        (
                            "The SolomonAI conversation group "
                            "context is no longer active."
                        )
                    )

                if (
                    desired_organization_id
                    != context_state["organization_id"]
                ):
                    raise SolomonAIConversationStoreError(
                        (
                            "The selected documents do not match the "
                            "SolomonAI conversation group."
                        )
                    )
        elif desired_organization_id:
            organization = (
                db_session.query(
                    Organization
                )
                .filter(
                    Organization.organization_id
                    == desired_organization_id,
                    Organization.status
                    == ACTIVE_STATUS,
                    Organization.suspended_at.is_(None),
                )
                .with_for_update()
                .first()
            )

            if not organization:
                raise SolomonAIConversationStoreError(
                    (
                        "The selected document group is no "
                        "longer active."
                    )
                )

            membership_ids = {
                int(source["membership_id"])
                for source in desired_sources
                if source["organization_id"]
                == desired_organization_id
                and source["membership_id"]
            }

            if len(membership_ids) > 1:
                raise SolomonAIConversationStoreError(
                    (
                        "The selected documents returned conflicting "
                        "group memberships."
                    )
                )

            membership_id = (
                next(iter(membership_ids))
                if membership_ids
                else None
            )

            if membership_id:
                membership = (
                    db_session.query(
                        OrganizationMembership
                    )
                    .filter(
                        OrganizationMembership.id
                        == membership_id,
                        OrganizationMembership.organization_id
                        == desired_organization_id,
                        OrganizationMembership.user_id
                        == clean_user_id,
                        OrganizationMembership.status
                        == ACTIVE_STATUS,
                        OrganizationMembership.removed_at.is_(None),
                    )
                    .with_for_update()
                    .first()
                )

                if not membership:
                    raise SolomonAIConversationStoreError(
                        (
                            "The selected document membership is no "
                            "longer active."
                        )
                    )

            context = SolomonAIConversationOrganizationContext(
                conversation_id=clean_conversation_id,
                organization_id=desired_organization_id,
                membership_id=membership_id,
                bound_by_user_id=clean_user_id,
            )
            db_session.add(context)
            db_session.flush()

        existing_sources = {
            source.source_document_id: source
            for source in db_session.query(
                SolomonAIConversationSource
            ).filter(
                SolomonAIConversationSource.conversation_id
                == clean_conversation_id
            ).with_for_update().all()
        }
        desired_ids = {
            source["document_id"]
            for source in desired_sources
        }

        for document_id, existing_source in existing_sources.items():
            if document_id not in desired_ids:
                db_session.delete(existing_source)

        for source_order, source in enumerate(desired_sources):
            existing_source = existing_sources.get(
                source["document_id"]
            )

            if existing_source:
                existing_source.file_registry_id = (
                    source["file_registry_id"]
                )
                existing_source.source_name = (
                    source["source_name"]
                )
                existing_source.source_order = source_order
                continue

            db_session.add(
                SolomonAIConversationSource(
                    conversation_id=clean_conversation_id,
                    file_registry_id=source["file_registry_id"],
                    source_document_id=source["document_id"],
                    source_name=source["source_name"],
                    source_order=source_order,
                )
            )

        timestamp = utc_now()
        conversation.updated_at = timestamp

        if context:
            context.updated_at = timestamp

        db_session.commit()

        return get_solomon_ai_conversation(
            user_id=clean_user_id,
            conversation_id=clean_conversation_id,
            include_messages=True,
        )
    except SolomonAIConversationStoreError:
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()
        raise SolomonAIConversationStoreError(
            "Conversation sources could not be saved."
        ) from exc
    finally:
        SessionLocal.remove()


def record_solomon_ai_exchange(
    *,
    user_id: int,
    conversation_id: str,
    user_content: str,
    assistant_content: str,
    bridge: str = "",
    suggestions: list | None = None,
    request_id: str = "",
    status: str = "complete",
) -> bool:
    """Atomically persist one user-and-assistant conversation exchange."""

    clean_user_id = int(user_id or 0)
    clean_conversation_id = _clean_conversation_id(
        conversation_id
    )
    clean_user_content = str(user_content or "").strip()
    clean_assistant_content = str(
        assistant_content or ""
    ).strip()
    clean_request_id = _clean_value(request_id)[:64]

    if (
        not clean_user_id
        or not clean_conversation_id
        or not clean_user_content
        or not clean_assistant_content
    ):
        return False

    _ensure_solomon_ai_conversation_schema()

    db_session = SessionLocal()

    try:
        conversation = (
            db_session.query(
                SolomonAIConversation
            )
            .filter(
                SolomonAIConversation.conversation_id
                == clean_conversation_id,
                SolomonAIConversation.user_id
                == clean_user_id,
                SolomonAIConversation.deleted_at.is_(None),
            )
            .with_for_update()
            .first()
        )

        if not conversation:
            return False

        if clean_request_id:
            existing_response = (
                db_session.query(
                    SolomonAIConversationMessage.id
                )
                .filter(
                    SolomonAIConversationMessage.conversation_id
                    == clean_conversation_id,
                    SolomonAIConversationMessage.role
                    == "assistant",
                    SolomonAIConversationMessage.request_id
                    == clean_request_id,
                )
                .first()
            )

            if existing_response:
                return True

        highest_order = (
            db_session.query(
                func.max(
                    SolomonAIConversationMessage.message_order
                )
            )
            .filter(
                SolomonAIConversationMessage.conversation_id
                == clean_conversation_id
            )
            .scalar()
            or 0
        )
        message_status = (
            _clean_value(status)[:32]
            or "complete"
        )

        db_session.add_all([
            SolomonAIConversationMessage(
                conversation_id=clean_conversation_id,
                role="user",
                content=clean_user_content,
                bridge="",
                suggestions=[],
                request_id=clean_request_id or None,
                message_order=highest_order + 1,
                status=message_status,
            ),
            SolomonAIConversationMessage(
                conversation_id=clean_conversation_id,
                role="assistant",
                content=clean_assistant_content,
                bridge=str(bridge or "").strip(),
                suggestions=_normalize_suggestions(
                    suggestions
                ),
                request_id=clean_request_id or None,
                message_order=highest_order + 2,
                status=message_status,
            ),
        ])

        if (
            highest_order == 0
            and _is_automatic_conversation_title(
                conversation.title
            )
        ):
            conversation.title = _build_title(
                clean_user_content
            )

        timestamp = utc_now()
        conversation.last_message_at = timestamp
        conversation.updated_at = timestamp
        db_session.commit()

        return True
    except Exception as exc:
        db_session.rollback()
        raise SolomonAIConversationStoreError(
            "The SolomonAI exchange could not be saved."
        ) from exc
    finally:
        SessionLocal.remove()


__all__ = [
    "SOLOMON_AI_CONVERSATION_CONTRACT",
    "SOLOMON_AI_SOURCE_MEMBERSHIP_CONTRACT",
    "SOLOMON_AI_OPERATION_KEY",
    "SOLOMON_AI_OPERATION_LABEL",
    "SolomonAIConversationStoreError",
    "create_solomon_ai_conversation",
    "delete_solomon_ai_conversation",
    "get_solomon_ai_conversation",
    "get_solomon_ai_conversation_source_membership_count",
    "get_latest_solomon_ai_conversation",
    "list_solomon_ai_conversation_history",
    "rename_solomon_ai_conversation",
    "replace_solomon_ai_conversation_sources",
    "set_solomon_ai_conversation_public_web",
    "record_solomon_ai_exchange",
]