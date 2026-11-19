# -------------------------------------------------------------------
# FILE: workspace_reader_file_access.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# Central SQL authorization for workspace file access.
# FileRegistry remains canonical identity. Resource ownership plus explicit
# direct and Group grants are the only V1 file authorization authorities.
# -------------------------------------------------------------------

from datetime import datetime, timezone
import json
import os
from threading import Lock
from typing import Any, Dict, Optional

from solomon_core.actions.solomon_file_action_applicability import (
    ensure_solomon_file_action_applicability_profiles,
)
from solomon_core.actions.solomon_file_actions import (
    build_solomon_file_action_projection,
)
from solomon_core.db import SessionLocal
from solomon_core.logger import get_logger
from solomon_core.intelligence_service.document_summary_contract import (
    AUTO_SUMMARY_SOURCE,
    AUTO_SUMMARY_TARGET_TYPE,
)
from solomon_core.models import (
    FileAccessGrant,
    FileGroupAccessGrant,
    FolderAccessGrant,
    FolderGroupAccessGrant,
    FileRecentActivity,
    FileRegistry,
    Organization,
    OrganizationFileCustody,
    OrganizationGroup,
    OrganizationGroupMembership,
    OrganizationMembership,
    User,
    WorkspaceFolder,
    WorkspaceIntelligenceObject,
)
from solomon_core.workspace_reader.workspace_reader_urls import (
    normalize_document_id,
)


logger = get_logger("workspace_reader.file_access")

_FILE_RECENT_ACTIVITY_TABLE_READY = False
_FILE_RECENT_ACTIVITY_TABLE_LOCK = Lock()

ACTIVE_STATUS = "active"
GROUP_LIBRARY_SCOPE = "group_library"
LEGACY_LIBRARY_SCOPE = "company" + "_library"
GROUP_LIBRARY_SCOPES = (
    GROUP_LIBRARY_SCOPE,
    LEGACY_LIBRARY_SCOPE,
)
GROUP_FILE_POLICY_VERSION = "group_file_permissions_v1"
LEGACY_ORGANIZATION_FILE_POLICY_VERSION = "organization" + "_file_permissions_v1"
PERSONAL_ACCESS_SCOPE = "my_files"
OWNER_TRASH_ACCESS_SCOPE = "my_trash"
DIRECT_GRANT_SCOPE = "shared_with_me"
GROUP_GRANT_SCOPE = "shared_with_group"
FOLDER_DIRECT_GRANT_SCOPE = "shared_via_folder"
FOLDER_GROUP_GRANT_SCOPE = "shared_via_group_folder"

FILE_DOCUMENT_STATUS_ACTIVE = "active"
FILE_DOCUMENT_STATUS_TRASH = "trash"

FILE_SURFACE_DEFAULT = "default"
FILE_SURFACE_SEARCH = "search"
FILE_SURFACE_RECENT = "recent"
FILE_SURFACE_TRASH = "trash"

FILE_ACTION_CAPABILITY_KEYS = {
    "open": "can_open_reader",
    "rename": "can_rename",
    "ask_solomon_ai": "can_select_for_solomon_ai",
    "share": "can_share",
    "share_visibility": "can_share_visibility",
    "move": "can_move",
    "view_summary": "can_view_summary",
    "view_details": "can_view_details",
    "move_to_trash": "can_move_to_trash",
    "restore": "can_restore",
    "permanent_delete": "can_permanently_delete",
}
FILE_SURFACE_ACTION_ORDER = {
    FILE_SURFACE_DEFAULT: (
        "open",
        "rename",
        "ask_solomon_ai",
        "move",
        "view_summary",
        "share",
        "view_details",
        "move_to_trash",
        "restore",
        "permanent_delete",
    ),
    FILE_SURFACE_SEARCH: (
        "open",
        "rename",
        "ask_solomon_ai",
        "move",
        "view_summary",
        "share",
        "view_details",
        "move_to_trash",
    ),
    FILE_SURFACE_RECENT: (
        "open",
        "rename",
        "ask_solomon_ai",
        "move",
        "view_summary",
        "share",
        "view_details",
        "move_to_trash",
    ),
    FILE_SURFACE_TRASH: (
        "open",
        "view_details",
        "restore",
        "permanent_delete",
    ),
}

OWNER_FILE_ACCESS_SCOPES = frozenset({
    PERSONAL_ACCESS_SCOPE,
    OWNER_TRASH_ACCESS_SCOPE,
})

READ_ACTION = "read"
QUERY_ACTION = "query"
DISCOVER_ACTION = "discover"
EDIT_ACTION = "edit"
SHARE_ACTION = "share"
DOWNLOAD_ACTION = "download"
DELETE_ACTION = "delete"

READ_PERMISSIONS = {
    "view",
    "edit",
    "owner",
}
EDIT_PERMISSIONS = {
    "edit",
    "owner",
}
OWNER_PERMISSIONS = {
    "owner",
}
QUERY_PERMISSIONS = set(READ_PERMISSIONS)
PERMISSION_RANK = {
    "view": 10,
    "edit": 20,
    "owner": 30,
}

GUEST_GROUP_LIBRARY_ROLES = {
    "guest",
    "external",
    "contractor",
}

TRASH_STATUS_VALUES = {
    "trash",
    "trashed",
    "deleted",
}

BLOCKED_FILE_STATUS_VALUES = {
    "archived",
    "deleted",
    "disabled",
    "inactive",
    "quarantined",
    "suspended",
    "trash",
    "trashed",
}

AUTHORIZED_ACTIONS = {
    "read",
    "query",
    "discover",
    "edit",
    "share",
    "download",
    "delete",
}


def _safe_meta_payload(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)

    if not isinstance(value, str):
        return {}

    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return {}

    return parsed if isinstance(parsed, dict) else {}


def _truthy_flag(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    return bool(value)


def _enabled_flag(value: Any) -> bool:
    if value is None:
        return True

    return _truthy_flag(value)


def _clean_authority_value(value: Any) -> str:
    return str(value or "").strip()


def _canonical_library_scope(value: Any) -> str:
    clean_value = _clean_authority_value(
        value
    ).lower()

    if clean_value in GROUP_LIBRARY_SCOPES:
        return GROUP_LIBRARY_SCOPE

    return clean_value or GROUP_LIBRARY_SCOPE


def _canonical_policy_version(value: Any) -> str:
    clean_value = _clean_authority_value(
        value
    )

    if clean_value == LEGACY_ORGANIZATION_FILE_POLICY_VERSION:
        return GROUP_FILE_POLICY_VERSION

    return clean_value or GROUP_FILE_POLICY_VERSION


def _clean_action(value: Any) -> str:
    """Return a canonical authorization action and fail closed on unknown input."""

    action = str(value or READ_ACTION).strip().lower()

    if action not in AUTHORIZED_ACTIONS:
        return ""

    return action


def _clean_user_id(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _bounded_corpus_limit(value: Any) -> int:
    try:
        limit = int(value or 75)
    except (TypeError, ValueError):
        limit = 75

    return max(
        1,
        min(limit, 200),
    )


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(value: Any) -> bool:
    if not value:
        return False

    if not isinstance(value, datetime):
        return False

    if value.tzinfo is None:
        return value <= datetime.utcnow()

    return value <= _utc_now()


def _permission_allows_action(
    permission: Any,
    action: str,
    *,
    allow_ai_query: Any = True,
) -> bool:
    clean_permission = str(
        permission or ""
    ).strip().lower()
    clean_action = _clean_action(action)

    if not clean_action:
        return False

    if clean_action == QUERY_ACTION:
        return (
            clean_permission in QUERY_PERMISSIONS
            and _enabled_flag(allow_ai_query)
        )

    if clean_action in {
        READ_ACTION,
        DISCOVER_ACTION,
        DOWNLOAD_ACTION,
    }:
        return clean_permission in READ_PERMISSIONS

    if clean_action == EDIT_ACTION:
        return clean_permission in EDIT_PERMISSIONS

    if clean_action in {
        SHARE_ACTION,
        DELETE_ACTION,
    }:
        return clean_permission in OWNER_PERMISSIONS

    return False


def _stronger_access_decision(
    first: Optional[dict],
    second: Optional[dict],
) -> Optional[dict]:
    """Return strongest use level while preserving additive grant capabilities."""

    candidates = [
        decision
        for decision in (first, second)
        if isinstance(decision, dict) and decision
    ]

    if not candidates:
        return None

    strongest = dict(
        max(
            candidates,
            key=lambda decision: PERMISSION_RANK.get(
                str(decision.get("permission") or "").strip().lower(),
                0,
            ),
        )
    )

    # Independent grants are additive. A restriction on one grant does not
    # globally deny a capability that another current grant explicitly allows.
    for flag_name in (
        "is_discoverable",
        "allow_ai_query",
        "allow_download",
    ):
        strongest[flag_name] = any(
            _enabled_flag(candidate.get(flag_name, True))
            for candidate in candidates
        )

    return strongest


def _requires_discoverability(action: str) -> bool:
    return _clean_action(action) in {
        QUERY_ACTION,
        DISCOVER_ACTION,
    }


def _is_group_library_guest_role(role: Any) -> bool:
    return str(
        role or ""
    ).strip().lower() in GUEST_GROUP_LIBRARY_ROLES


def _is_active_user(
    db_session,
    user_id: int,
) -> bool:
    clean_user_id = _clean_user_id(user_id)

    if not clean_user_id:
        return False

    user = db_session.get(
        User,
        clean_user_id,
    )

    return bool(
        user
        and _truthy_flag(
            getattr(
                user,
                "is_active",
                True,
            )
        )
    )


def _is_active_organization(
    organization: Optional[Organization],
    *,
    action: str = READ_ACTION,
) -> bool:
    if not organization:
        return False

    if organization.status != ACTIVE_STATUS:
        return False

    if organization.suspended_at is not None:
        return False

    if (
        _clean_action(action) == QUERY_ACTION
        and not _enabled_flag(
            getattr(
                organization,
                "ai_query_enabled",
                True,
            )
        )
    ):
        return False

    return True


def _active_organization_membership(
    db_session,
    user_id: int,
    organization_id: str,
) -> Optional[OrganizationMembership]:
    clean_user_id = _clean_user_id(user_id)
    clean_organization_id = _clean_authority_value(
        organization_id
    )

    if not clean_user_id or not clean_organization_id:
        return None

    return (
        db_session.query(
            OrganizationMembership
        )
        .join(
            Organization,
            Organization.organization_id
            == OrganizationMembership.organization_id,
        )
        .filter(
            OrganizationMembership.organization_id
            == clean_organization_id,
            OrganizationMembership.user_id
            == clean_user_id,
            OrganizationMembership.status
            == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
            Organization.status == ACTIVE_STATUS,
            Organization.suspended_at.is_(None),
        )
        .order_by(
            OrganizationMembership.is_primary.desc(),
            OrganizationMembership.id.asc(),
        )
        .first()
    )


def is_file_record_trashed(record: FileRegistry) -> bool:
    if not record:
        return True

    metadata = _safe_meta_payload(record.meta)

    metadata_status = str(
        metadata.get("document_status")
        or metadata.get("library_status")
        or metadata.get("storage_status")
        or ""
    ).strip().lower()

    registry_status = str(
        getattr(
            record,
            "status",
            ACTIVE_STATUS,
        )
        or ACTIVE_STATUS
    ).strip().lower()

    return bool(
        registry_status in BLOCKED_FILE_STATUS_VALUES
        or metadata_status in TRASH_STATUS_VALUES
        or _truthy_flag(metadata.get("trashed"))
        or _truthy_flag(metadata.get("deleted"))
        or metadata.get("trashed_at")
        or metadata.get("deleted_at")
        or getattr(record, "deleted_at", None)
        or getattr(record, "archived_at", None)
    )


def is_owned_file_record(
    record: FileRegistry,
    user_id: int,
) -> bool:
    return str(
        record.uploader_id or ""
    ) == str(
        user_id or ""
    )


def resolve_file_document_status(
    record: FileRegistry,
) -> str:
    """Return the canonical document lifecycle state for a file."""

    if is_file_record_trashed(
        record
    ):
        return FILE_DOCUMENT_STATUS_TRASH

    return FILE_DOCUMENT_STATUS_ACTIVE


def _access_decision_is_owner(
    record: FileRegistry,
    access_decision: Optional[dict],
    requesting_user_id: int = 0,
) -> bool:
    """Return whether the current authority represents file ownership."""

    clean_user_id = _clean_user_id(
        requesting_user_id
    )

    if (
        clean_user_id
        and is_owned_file_record(
            record,
            clean_user_id,
        )
    ):
        return True

    if not isinstance(
        access_decision,
        dict,
    ):
        return False

    access_scope = _clean_authority_value(
        access_decision.get(
            "access_scope"
        )
    ).lower()
    authority_basis = _clean_authority_value(
        access_decision.get(
            "authority_basis"
        )
    ).lower()

    return bool(
        access_scope in OWNER_FILE_ACCESS_SCOPES
        or authority_basis in {
            "personal_owner",
            "personal_owner_trash",
        }
    )


def build_file_capabilities(
    record: FileRegistry,
    access_decision: Optional[dict],
    *,
    requesting_user_id: int = 0,
) -> Dict[str, bool]:
    """Return server-owned file capabilities for every document surface."""

    decision = (
        dict(access_decision)
        if isinstance(
            access_decision,
            dict,
        )
        else {}
    )
    document_status = resolve_file_document_status(
        record
    )
    is_trashed = (
        document_status
        == FILE_DOCUMENT_STATUS_TRASH
    )
    has_access_decision = bool(
        decision
    )
    is_owner = bool(
        has_access_decision
        and _access_decision_is_owner(
            record,
            decision,
            requesting_user_id,
        )
    )
    can_read = _permission_allows_action(
        decision.get(
            "permission"
        ),
        READ_ACTION,
        allow_ai_query=decision.get(
            "allow_ai_query",
            True,
        ),
    )
    can_query = _permission_allows_action(
        decision.get(
            "permission"
        ),
        QUERY_ACTION,
        allow_ai_query=decision.get(
            "allow_ai_query",
            True,
        ),
    )
    can_edit = _permission_allows_action(
        decision.get(
            "permission"
        ),
        EDIT_ACTION,
        allow_ai_query=decision.get(
            "allow_ai_query",
            True,
        ),
    )

    return {
        "can_open": bool(
            can_read
        ),
        "can_view_details": bool(
            can_read
        ),
        "can_download": bool(
            can_read
            and _enabled_flag(
                decision.get("allow_download", True)
            )
        ),
        "can_edit": bool(
            can_edit
        ),
        "can_upload_version": bool(
            can_edit
        ),
        # Derived-intelligence actions fail closed here. Read authority alone
        # never implies that a current summary artifact exists. The registry
        # resolver promotes this capability only after validating durable
        # summary state against the current source checksum/version.
        "can_view_summary": False,
        "can_rename": bool(
            is_owner
            and not is_trashed
        ),
        "can_move": bool(
            is_owner
            and not is_trashed
        ),
        "can_share": bool(
            is_owner
            and not is_trashed
        ),
        "can_share_visibility": False,
        "can_move_to_trash": bool(
            is_owner
            and not is_trashed
        ),
        "can_restore": bool(
            is_owner
            and is_trashed
        ),
        "can_permanently_delete": bool(
            is_owner
            and is_trashed
        ),
        "can_open_reader": bool(
            can_read
        ),
        "can_run_document_operation": bool(
            can_query
        ),
        "can_select_for_solomon_ai": bool(
            can_query
        ),
        "file_authority_inherited": False,
    }


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _isoformat_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()

    return ""


def _build_current_summary_artifact_payload(
    entry: dict,
    intelligence_object: WorkspaceIntelligenceObject,
) -> Optional[dict]:
    """Return a bounded current-summary payload when provenance still matches."""

    if not isinstance(entry, dict) or not intelligence_object:
        return None

    source_hash = _clean_authority_value(
        entry.get("checksum")
    )
    source_version = _safe_int(
        entry.get("version_number"),
        1,
    )
    object_source_hash = _clean_authority_value(
        intelligence_object.source_hash
    )
    detailed_summary = _clean_authority_value(
        intelligence_object.detailed_summary
    )
    summary_hash = _clean_authority_value(
        intelligence_object.summary_hash
    )
    metadata = _safe_meta_payload(
        intelligence_object.metadata_json
    )
    metadata_source = _clean_authority_value(
        metadata.get("summary_source")
    )
    metadata_source_hash = _clean_authority_value(
        metadata.get("summary_source_hash")
    )
    metadata_target_version = _safe_int(
        metadata.get("summary_target_version")
    )

    if not (
        source_hash
        and object_source_hash == source_hash
        and metadata_source == AUTO_SUMMARY_SOURCE
        and metadata_source_hash == source_hash
        and metadata_target_version == source_version
        and detailed_summary
        and summary_hash
    ):
        return None

    generated_at = (
        _isoformat_datetime(
            getattr(
                intelligence_object,
                "updated_at",
                None,
            )
        )
        or _isoformat_datetime(
            getattr(
                intelligence_object,
                "created_at",
                None,
            )
        )
    )

    return {
        "summary": detailed_summary,
        "summary_hash": summary_hash,
        "source_hash": object_source_hash,
        "source_version": source_version,
        "summary_source": metadata_source,
        "generated_at": generated_at,
    }


def resolve_current_summary_artifact(
    entry: dict,
    *,
    request_id: str = "untracked",
) -> Optional[dict]:
    """Resolve the current durable Auto Summary for one authorized file entry."""

    file_id = _safe_int(
        entry.get("file_id")
        if isinstance(entry, dict)
        else None
    )

    if not file_id:
        return None

    db_session = SessionLocal()

    try:
        intelligence_objects = (
            db_session.query(
                WorkspaceIntelligenceObject
            )
            .filter(
                WorkspaceIntelligenceObject.file_registry_id
                == file_id,
                WorkspaceIntelligenceObject.object_type
                == AUTO_SUMMARY_TARGET_TYPE,
                WorkspaceIntelligenceObject.status
                == ACTIVE_STATUS,
                WorkspaceIntelligenceObject.summary_status
                == "ready",
            )
            .all()
        )

        for intelligence_object in intelligence_objects:
            artifact = _build_current_summary_artifact_payload(
                entry,
                intelligence_object,
            )

            if artifact:
                return artifact

        return None
    except Exception as exc:
        logger.warning(
            "[workspace.reader.summary_artifact_resolve_failed] "
            "request_id=%s file_id=%s error=%s",
            request_id,
            file_id,
            exc,
        )
        return None
    finally:
        db_session.close()


def _current_ready_summary_file_ids(
    db_session,
    entries: list[dict],
) -> set[int]:
    """Return file ids whose canonical Auto Summary is current and ready."""

    entries_by_file_id: Dict[int, dict] = {}

    for entry in entries:
        file_id = _safe_int(
            entry.get("file_id")
        )

        if file_id:
            entries_by_file_id[file_id] = entry

    if not entries_by_file_id:
        return set()

    try:
        intelligence_objects = (
            db_session.query(
                WorkspaceIntelligenceObject
            )
            .filter(
                WorkspaceIntelligenceObject.file_registry_id.in_(
                    tuple(entries_by_file_id)
                ),
                WorkspaceIntelligenceObject.object_type
                == AUTO_SUMMARY_TARGET_TYPE,
                WorkspaceIntelligenceObject.status
                == ACTIVE_STATUS,
                WorkspaceIntelligenceObject.summary_status
                == "ready",
            )
            .all()
        )
    except Exception as exc:
        logger.warning(
            "[workspace.reader.summary_capability_resolve_failed] "
            "file_count=%s error=%s",
            len(entries_by_file_id),
            exc,
        )
        return set()

    ready_file_ids: set[int] = set()

    for intelligence_object in intelligence_objects:
        file_id = _safe_int(
            intelligence_object.file_registry_id
        )
        entry = entries_by_file_id.get(
            file_id
        )

        if not entry:
            continue

        if not _build_current_summary_artifact_payload(
            entry,
            intelligence_object,
        ):
            continue

        ready_file_ids.add(file_id)

    return ready_file_ids


def _apply_current_summary_capabilities(
    db_session,
    entries: list[dict],
) -> list[dict]:
    """Promote View Summary only for current durable ready artifacts."""

    if not entries:
        return entries

    ready_file_ids = _current_ready_summary_file_ids(
        db_session,
        entries,
    )
    applicability_by_file_id: dict[int, dict] = {}

    try:
        (
            applicability_by_file_id,
            applicability_changed,
        ) = ensure_solomon_file_action_applicability_profiles(
            db_session,
            entries,
        )

        if applicability_changed:
            db_session.commit()
    except Exception as exc:
        db_session.rollback()
        applicability_by_file_id = {}
        logger.warning(
            "[workspace.reader.action_applicability_refresh_failed] error=%s",
            exc,
        )

    for entry in entries:
        capabilities = dict(
            entry.get("capabilities")
            or {}
        )
        file_id = _safe_int(
            entry.get("file_id")
        )
        can_read_active_file = bool(
            capabilities.get("can_view_details")
            and not entry.get("trashed")
        )
        capabilities["can_view_summary"] = bool(
            can_read_active_file
            and file_id in ready_file_ids
        )
        entry["capabilities"] = capabilities
        entry["available_actions"] = (
            build_file_available_actions(
                capabilities
            )
        )
        applicability_profile = applicability_by_file_id.get(
            file_id,
            {},
        )
        applicable_action_ids = (
            applicability_profile.get("applicable_action_ids")
            if isinstance(applicability_profile, dict)
            else None
        )
        entry.update(
            build_solomon_file_action_projection(
                capabilities,
                entry,
                applicable_action_ids,
            )
        )

    return entries


def build_file_surface_actions(
    capabilities: Optional[dict],
    *,
    surface: str,
) -> list[str]:
    """Return server-approved actions for one explicit file surface."""

    resolved = (
        capabilities
        if isinstance(
            capabilities,
            dict,
        )
        else {}
    )
    clean_surface = str(
        surface or ""
    ).strip().lower()
    action_order = (
        FILE_SURFACE_ACTION_ORDER.get(
            clean_surface,
            (),
        )
    )

    return [
        action
        for action in action_order
        if resolved.get(
            FILE_ACTION_CAPABILITY_KEYS[
                action
            ]
        )
    ]


def build_file_available_actions(
    capabilities: Optional[dict],
) -> list[str]:
    """Return lifecycle-wide compatibility actions, not surface authority."""

    return build_file_surface_actions(
        capabilities,
        surface=FILE_SURFACE_DEFAULT,
    )


def ensure_file_recent_activity_table(db_session) -> None:
    """Create the per-user Recent activity table once per process."""

    global _FILE_RECENT_ACTIVITY_TABLE_READY

    if _FILE_RECENT_ACTIVITY_TABLE_READY:
        return

    with _FILE_RECENT_ACTIVITY_TABLE_LOCK:
        if _FILE_RECENT_ACTIVITY_TABLE_READY:
            return

        bind = db_session.get_bind()
        FileRecentActivity.__table__.create(
            bind=bind,
            checkfirst=True,
        )
        _FILE_RECENT_ACTIVITY_TABLE_READY = True


def record_file_recent_activity(
    user_id: int,
    document_id: str,
    *,
    activity_kind: str = "opened",
) -> bool:
    """Record one validated per-user activity event for an active file."""

    clean_user_id = _clean_user_id(user_id)
    clean_document_id = normalize_document_id(document_id)
    clean_activity_kind = (
        _clean_authority_value(activity_kind).lower()
        or "opened"
    )[:32]

    if not clean_user_id or not clean_document_id:
        return False

    db_session = SessionLocal()

    try:
        ensure_file_recent_activity_table(db_session)
        record = (
            db_session.query(FileRegistry)
            .filter(FileRegistry.random_name == clean_document_id)
            .first()
        )

        if not record or is_file_record_trashed(record):
            return False

        activity = (
            db_session.query(FileRecentActivity)
            .filter(
                FileRecentActivity.user_id == clean_user_id,
                FileRecentActivity.file_id == record.id,
            )
            .first()
        )
        now = datetime.now(timezone.utc)

        if activity:
            activity.activity_kind = clean_activity_kind
            activity.activity_at = now
        else:
            activity = FileRecentActivity(
                user_id=clean_user_id,
                file_id=record.id,
                activity_kind=clean_activity_kind,
                activity_at=now,
            )
            db_session.add(activity)

        db_session.commit()
        return True
    except Exception as exc:
        db_session.rollback()
        logger.warning(
            "[workspace.file_recent_activity_failed] user_id=%s "
            "document_id=%s activity=%s error=%s",
            clean_user_id,
            clean_document_id,
            clean_activity_kind,
            exc,
        )
        return False
    finally:
        db_session.close()


def build_owned_trash_access_decision(
    record: FileRegistry,
    user_id: int,
    action: str,
) -> Optional[dict]:
    """Return owner-only read authority for recoverable Trash preview."""

    clean_action = _clean_action(action)

    if clean_action != READ_ACTION:
        return None

    if not is_owned_file_record(
        record,
        user_id,
    ):
        return None

    return {
        "access_scope": OWNER_TRASH_ACCESS_SCOPE,
        "permission": "owner",
        "authorized_action": clean_action,
        "organization_id": None,
        "authority_basis": "personal_owner_trash",
        "policy_version": "personal_file_trash_permissions_v1",
        "is_discoverable": False,
        "allow_ai_query": False,
    }


def resolve_file_record_by_identifier(
    db_session,
    identifier: str,
) -> Optional[FileRegistry]:
    clean_identifier = normalize_document_id(
        identifier
    )

    if not clean_identifier:
        return None

    if clean_identifier.isdigit():
        record = db_session.get(
            FileRegistry,
            int(clean_identifier),
        )

        if record:
            return record

    return (
        db_session.query(FileRegistry)
        .filter(
            FileRegistry.random_name
            == clean_identifier
        )
        .first()
    )


def _group_custody_allows_action(
    custody: OrganizationFileCustody,
    action: str,
) -> bool:
    clean_action = _clean_action(action)

    if custody.status != ACTIVE_STATUS:
        return False

    if custody.removed_at is not None:
        return False

    if (
        _requires_discoverability(clean_action)
        and not _enabled_flag(
            getattr(
                custody,
                "is_discoverable",
                True,
            )
        )
    ):
        return False

    if (
        clean_action == QUERY_ACTION
        and not _enabled_flag(
            getattr(
                custody,
                "allow_ai_query",
                True,
            )
        )
    ):
        return False

    return True


def _direct_grant_allows_action(
    grant: FileAccessGrant,
    action: str,
) -> bool:
    clean_action = _clean_action(action)

    if grant.status != ACTIVE_STATUS:
        return False

    if grant.revoked_at is not None:
        return False

    if _is_expired(
        getattr(
            grant,
            "expires_at",
            None,
        )
    ):
        return False

    if (
        _requires_discoverability(clean_action)
        and not _enabled_flag(
            getattr(
                grant,
                "is_discoverable",
                True,
            )
        )
    ):
        return False

    if (
        clean_action == DOWNLOAD_ACTION
        and not _enabled_flag(
            getattr(
                grant,
                "allow_download",
                True,
            )
        )
    ):
        return False

    return _permission_allows_action(
        grant.permission,
        clean_action,
        allow_ai_query=getattr(
            grant,
            "allow_ai_query",
            True,
        ),
    )


def _group_grant_allows_action(
    grant: FileGroupAccessGrant,
    action: str,
) -> bool:
    clean_action = _clean_action(action)

    if grant.status != ACTIVE_STATUS:
        return False

    if grant.revoked_at is not None:
        return False

    if _is_expired(
        getattr(
            grant,
            "expires_at",
            None,
        )
    ):
        return False

    if (
        _requires_discoverability(clean_action)
        and not _enabled_flag(
            getattr(
                grant,
                "is_discoverable",
                True,
            )
        )
    ):
        return False

    if (
        clean_action == DOWNLOAD_ACTION
        and not _enabled_flag(
            getattr(
                grant,
                "allow_download",
                True,
            )
        )
    ):
        return False

    return _permission_allows_action(
        grant.permission,
        clean_action,
        allow_ai_query=getattr(
            grant,
            "allow_ai_query",
            True,
        ),
    )


def _resolve_group_library_access(
    db_session,
    record: FileRegistry,
    user_id: int,
    *,
    action: str = READ_ACTION,
) -> Optional[dict]:
    """Legacy custody is metadata only and never grants V1 resource access."""

    return None

def _has_active_group_custody(
    db_session,
    record: FileRegistry,
) -> bool:
    custody = (
        db_session.query(
            OrganizationFileCustody.id
        )
        .join(
            Organization,
            Organization.organization_id
            == OrganizationFileCustody.organization_id,
        )
        .filter(
            OrganizationFileCustody.file_registry_id
            == record.id,
            OrganizationFileCustody.status
            == ACTIVE_STATUS,
            OrganizationFileCustody.removed_at.is_(
                None
            ),
            OrganizationFileCustody.library_scope
            .in_(GROUP_LIBRARY_SCOPES),
            Organization.status
            == ACTIVE_STATUS,
            Organization.suspended_at.is_(
                None
            ),
        )
        .first()
    )

    return custody is not None


def _has_active_organization_custody(
    db_session,
    record: FileRegistry,
) -> bool:
    custody = (
        db_session.query(
            OrganizationFileCustody.id
        )
        .join(
            Organization,
            Organization.organization_id
            == OrganizationFileCustody.organization_id,
        )
        .filter(
            OrganizationFileCustody.file_registry_id
            == record.id,
            OrganizationFileCustody.status
            == ACTIVE_STATUS,
            OrganizationFileCustody.removed_at.is_(None),
            Organization.status == ACTIVE_STATUS,
            Organization.suspended_at.is_(None),
        )
        .first()
    )

    return custody is not None


def _resolve_direct_grant_access(
    db_session,
    record: FileRegistry,
    user_id: int,
    *,
    action: str = READ_ACTION,
) -> Optional[dict]:
    clean_action = _clean_action(action)

    grant = (
        db_session.query(
            FileAccessGrant
        )
        .filter(
            FileAccessGrant.file_registry_id
            == record.id,
            FileAccessGrant.granted_to_user_id
            == user_id,
            FileAccessGrant.status
            == ACTIVE_STATUS,
            FileAccessGrant.revoked_at.is_(
                None
            ),
        )
        .first()
    )

    if not grant:
        return None

    if not _direct_grant_allows_action(
        grant,
        clean_action,
    ):
        return None

    organization_id = _clean_authority_value(
        grant.organization_id
    )

    if organization_id:
        organization = db_session.get(
            Organization,
            organization_id,
        )

        if not _is_active_organization(
            organization,
            action=clean_action,
        ):
            return None

        if not _active_organization_membership(
            db_session,
            user_id,
            organization_id,
        ):
            return None

    permission = str(
        grant.permission or ""
    ).strip().lower()

    return {
        "access_scope": DIRECT_GRANT_SCOPE,
        "permission": permission,
        "authorized_action": clean_action,
        "organization_id": grant.organization_id,
        "grant_id": grant.id,
        "grant_type": grant.grant_type,
        "authority_basis": "direct_user_grant",
        "policy_version": _canonical_policy_version(
            getattr(
                grant,
                "policy_version",
                None,
            )
        ),
        "is_discoverable": _enabled_flag(
            getattr(
                grant,
                "is_discoverable",
                True,
            )
        ),
        "allow_ai_query": _enabled_flag(
            getattr(
                grant,
                "allow_ai_query",
                True,
            )
        ),
        "allow_download": _enabled_flag(
            getattr(
                grant,
                "allow_download",
                True,
            )
        ),
        "expires_at": getattr(
            grant,
            "expires_at",
            None,
        ),
    }


def _resolve_group_grant_access(
    db_session,
    record: FileRegistry,
    user_id: int,
    *,
    action: str = READ_ACTION,
) -> Optional[dict]:
    clean_action = _clean_action(action)

    if not clean_action:
        return None

    rows = (
        db_session.query(
            FileGroupAccessGrant,
            OrganizationGroup,
            OrganizationGroupMembership,
            Organization,
        )
        .join(
            OrganizationGroup,
            OrganizationGroup.group_id
            == FileGroupAccessGrant.group_id,
        )
        .join(
            OrganizationGroupMembership,
            OrganizationGroupMembership.group_id
            == OrganizationGroup.group_id,
        )
        .join(
            Organization,
            Organization.organization_id
            == FileGroupAccessGrant.organization_id,
        )
        .filter(
            FileGroupAccessGrant.file_registry_id == record.id,
            FileGroupAccessGrant.status == ACTIVE_STATUS,
            FileGroupAccessGrant.revoked_at.is_(None),
            OrganizationGroup.status == ACTIVE_STATUS,
            OrganizationGroup.removed_at.is_(None),
            OrganizationGroupMembership.user_id == user_id,
            OrganizationGroupMembership.status == ACTIVE_STATUS,
            OrganizationGroupMembership.removed_at.is_(None),
        )
        .order_by(FileGroupAccessGrant.id.asc())
        .all()
    )

    strongest: Optional[dict] = None

    for grant, group, group_membership, organization in rows:
        if not _is_active_organization(
            organization,
            action=clean_action,
        ):
            continue

        if not _active_organization_membership(
            db_session,
            user_id,
            organization.organization_id,
        ):
            continue

        if not _group_grant_allows_action(
            grant,
            clean_action,
        ):
            continue

        permission = str(
            grant.permission or ""
        ).strip().lower()

        decision = {
            "access_scope": GROUP_GRANT_SCOPE,
            "permission": permission,
            "authorized_action": clean_action,
            "organization_id": grant.organization_id,
            "group_id": group.group_id,
            "group_membership_id": group_membership.id,
            "group_grant_id": grant.id,
            "grant_type": grant.grant_type,
            "authority_basis": "group_grant",
            "policy_version": _canonical_policy_version(
                getattr(grant, "policy_version", None)
            ),
            "is_discoverable": _enabled_flag(
                getattr(grant, "is_discoverable", True)
            ),
            "allow_ai_query": _enabled_flag(
                getattr(grant, "allow_ai_query", True)
            ),
            "allow_download": _enabled_flag(
                getattr(grant, "allow_download", True)
            ),
            "expires_at": getattr(grant, "expires_at", None),
        }
        strongest = _stronger_access_decision(
            strongest,
            decision,
        )

    return strongest

def _workspace_folder_ancestor_chain(
    db_session,
    folder: WorkspaceFolder,
) -> list[WorkspaceFolder]:
    """Return the folder and its ancestors, stopping safely on malformed cycles."""

    chain = []
    cursor = folder
    seen = set()

    while cursor and len(chain) < 64:
        folder_id = _clean_authority_value(
            getattr(cursor, "folder_id", "")
        )

        if not folder_id or folder_id in seen:
            break

        seen.add(folder_id)
        chain.append(cursor)
        parent_id = _clean_authority_value(
            getattr(cursor, "parent_folder_id", "")
        )

        if not parent_id:
            break

        cursor = (
            db_session.query(WorkspaceFolder)
            .filter(WorkspaceFolder.folder_id == parent_id)
            .first()
        )

    return chain


def _active_workspace_folder(folder: WorkspaceFolder) -> bool:
    """Return whether a folder may participate in current authorization."""

    if not folder or getattr(folder, "deleted_at", None) is not None:
        return False

    status = str(getattr(folder, "status", "") or "active").strip().lower()
    return status == ACTIVE_STATUS


def _folder_direct_grant_allows_action(
    grant: FolderAccessGrant,
    action: str,
) -> bool:
    """Apply canonical Viewer/Editor restrictions to a direct folder grant."""

    clean_action = _clean_action(action)

    if grant.status != ACTIVE_STATUS or grant.revoked_at is not None:
        return False

    if _is_expired(getattr(grant, "expires_at", None)):
        return False

    if (
        _requires_discoverability(clean_action)
        and not _enabled_flag(getattr(grant, "is_discoverable", True))
    ):
        return False

    if (
        clean_action == DOWNLOAD_ACTION
        and not _enabled_flag(getattr(grant, "allow_download", True))
    ):
        return False

    return _permission_allows_action(
        grant.permission,
        clean_action,
        allow_ai_query=getattr(grant, "allow_ai_query", True),
    )


def _folder_group_grant_allows_action(
    grant: FolderGroupAccessGrant,
    action: str,
) -> bool:
    """Apply canonical Viewer/Editor restrictions to a Group folder grant."""

    clean_action = _clean_action(action)

    if grant.status != ACTIVE_STATUS or grant.revoked_at is not None:
        return False

    if _is_expired(getattr(grant, "expires_at", None)):
        return False

    if (
        _requires_discoverability(clean_action)
        and not _enabled_flag(getattr(grant, "is_discoverable", True))
    ):
        return False

    if (
        clean_action == DOWNLOAD_ACTION
        and not _enabled_flag(getattr(grant, "allow_download", True))
    ):
        return False

    return _permission_allows_action(
        grant.permission,
        clean_action,
        allow_ai_query=getattr(grant, "allow_ai_query", True),
    )


def resolve_workspace_folder_access_decision(
    db_session,
    folder: WorkspaceFolder,
    user_id: int,
    *,
    action: str = DISCOVER_ACTION,
) -> Optional[dict]:
    """Resolve owner/direct/Group folder authority with dynamic descendant inheritance."""

    clean_user_id = _clean_user_id(user_id)
    clean_action = _clean_action(action)

    if (
        not folder
        or not clean_user_id
        or not clean_action
        or not _is_active_user(db_session, clean_user_id)
        or not _active_workspace_folder(folder)
    ):
        return None

    if str(getattr(folder, "user_id", "")) == str(clean_user_id):
        if not _permission_allows_action("owner", clean_action, allow_ai_query=True):
            return None

        return {
            "access_scope": PERSONAL_ACCESS_SCOPE,
            "permission": "owner",
            "authorized_action": clean_action,
            "authority_basis": "workspace_folder_owner",
            "policy_version": "workspace_folder_permissions_v1",
            "is_discoverable": True,
            "allow_ai_query": True,
            "allow_download": True,
            "folder_id": getattr(folder, "folder_id", None),
            "inherited_from_folder_id": getattr(folder, "folder_id", None),
        }

    strongest = None

    for ancestor in _workspace_folder_ancestor_chain(db_session, folder):
        if not _active_workspace_folder(ancestor):
            break

        ancestor_id = _clean_authority_value(
            getattr(ancestor, "folder_id", "")
        )

        direct_grant = (
            db_session.query(FolderAccessGrant)
            .filter(
                FolderAccessGrant.workspace_folder_id == ancestor_id,
                FolderAccessGrant.granted_to_user_id == clean_user_id,
                FolderAccessGrant.status == ACTIVE_STATUS,
                FolderAccessGrant.revoked_at.is_(None),
            )
            .first()
        )

        if direct_grant and not _folder_direct_grant_allows_action(
            direct_grant,
            clean_action,
        ):
            direct_grant = None

        if direct_grant:
            organization_id = _clean_authority_value(
                direct_grant.organization_id
            )
            if organization_id:
                organization = db_session.get(
                    Organization,
                    organization_id,
                )
                if not _is_active_organization(
                    organization,
                    action=clean_action,
                ):
                    direct_grant = None
                elif not _active_organization_membership(
                    db_session,
                    clean_user_id,
                    organization_id,
                ):
                    direct_grant = None

        if direct_grant:
            direct_decision = {
                "access_scope": FOLDER_DIRECT_GRANT_SCOPE,
                "permission": str(direct_grant.permission or "").strip().lower(),
                "authorized_action": clean_action,
                "organization_id": direct_grant.organization_id,
                "folder_grant_id": direct_grant.id,
                "grant_type": direct_grant.grant_type,
                "authority_basis": "direct_folder_grant",
                "policy_version": _canonical_policy_version(
                    getattr(direct_grant, "policy_version", None)
                ),
                "is_discoverable": _enabled_flag(
                    getattr(direct_grant, "is_discoverable", True)
                ),
                "allow_ai_query": _enabled_flag(
                    getattr(direct_grant, "allow_ai_query", True)
                ),
                "allow_download": _enabled_flag(
                    getattr(direct_grant, "allow_download", True)
                ),
                "expires_at": getattr(direct_grant, "expires_at", None),
                "folder_id": getattr(folder, "folder_id", None),
                "inherited_from_folder_id": ancestor_id,
            }
            strongest = _stronger_access_decision(strongest, direct_decision)

        group_rows = (
            db_session.query(
                FolderGroupAccessGrant,
                OrganizationGroup,
                OrganizationGroupMembership,
                Organization,
            )
            .join(
                OrganizationGroup,
                OrganizationGroup.group_id == FolderGroupAccessGrant.group_id,
            )
            .join(
                OrganizationGroupMembership,
                OrganizationGroupMembership.group_id == OrganizationGroup.group_id,
            )
            .join(
                Organization,
                Organization.organization_id == FolderGroupAccessGrant.organization_id,
            )
            .filter(
                FolderGroupAccessGrant.workspace_folder_id == ancestor_id,
                FolderGroupAccessGrant.status == ACTIVE_STATUS,
                FolderGroupAccessGrant.revoked_at.is_(None),
                OrganizationGroup.status == ACTIVE_STATUS,
                OrganizationGroup.removed_at.is_(None),
                OrganizationGroupMembership.user_id == clean_user_id,
                OrganizationGroupMembership.status == ACTIVE_STATUS,
                OrganizationGroupMembership.removed_at.is_(None),
            )
            .all()
        )

        for group_grant, group, membership, organization in group_rows:
            if not _is_active_organization(organization, action=clean_action):
                continue
            if not _active_organization_membership(
                db_session,
                clean_user_id,
                organization.organization_id,
            ):
                continue
            if not _folder_group_grant_allows_action(group_grant, clean_action):
                continue

            group_decision = {
                "access_scope": FOLDER_GROUP_GRANT_SCOPE,
                "permission": str(group_grant.permission or "").strip().lower(),
                "authorized_action": clean_action,
                "organization_id": group_grant.organization_id,
                "group_id": group.group_id,
                "group_membership_id": membership.id,
                "folder_group_grant_id": group_grant.id,
                "grant_type": group_grant.grant_type,
                "authority_basis": "group_folder_grant",
                "policy_version": _canonical_policy_version(
                    getattr(group_grant, "policy_version", None)
                ),
                "is_discoverable": _enabled_flag(
                    getattr(group_grant, "is_discoverable", True)
                ),
                "allow_ai_query": _enabled_flag(
                    getattr(group_grant, "allow_ai_query", True)
                ),
                "allow_download": _enabled_flag(
                    getattr(group_grant, "allow_download", True)
                ),
                "expires_at": getattr(group_grant, "expires_at", None),
                "folder_id": getattr(folder, "folder_id", None),
                "inherited_from_folder_id": ancestor_id,
            }
            strongest = _stronger_access_decision(strongest, group_decision)

    return strongest


def _resolve_inherited_folder_file_access(
    db_session,
    record: FileRegistry,
    user_id: int,
    *,
    action: str,
) -> Optional[dict]:
    """Resolve file-use authority inherited dynamically from its folder boundary."""

    folder_id = _clean_authority_value(getattr(record, "workspace_folder_id", ""))
    if not folder_id:
        return None

    folder = (
        db_session.query(WorkspaceFolder)
        .filter(WorkspaceFolder.folder_id == folder_id)
        .first()
    )
    if not folder:
        return None

    decision = resolve_workspace_folder_access_decision(
        db_session,
        folder,
        user_id,
        action=action,
    )
    if not decision or decision.get("permission") == "owner":
        return None

    inherited = dict(decision)
    inherited["authority_basis"] = (
        "file_inherited_from_" + str(decision.get("authority_basis") or "folder_grant")
    )
    inherited["file_registry_id"] = record.id
    return inherited


def resolve_file_access_decision(
    db_session,
    record: FileRegistry,
    user_id: int,
    *,
    action: str = READ_ACTION,
    allow_trashed_owner_read: bool = False,
) -> Optional[dict]:
    """Resolve current server-authoritative file access under canonical V1 rules."""

    clean_user_id = _clean_user_id(user_id)
    clean_action = _clean_action(action)

    if (
        not record
        or not clean_user_id
        or not clean_action
        or not _is_active_user(
            db_session,
            clean_user_id,
        )
    ):
        return None

    if is_file_record_trashed(record):
        if not allow_trashed_owner_read:
            return None

        return build_owned_trash_access_decision(
            record,
            clean_user_id,
            clean_action,
        )

    if is_owned_file_record(
        record,
        clean_user_id,
    ):
        if not _permission_allows_action(
            "owner",
            clean_action,
            allow_ai_query=True,
        ):
            return None

        return {
            "access_scope": PERSONAL_ACCESS_SCOPE,
            "permission": "owner",
            "authorized_action": clean_action,
            "organization_id": None,
            "authority_basis": "personal_owner",
            "policy_version": "personal_file_permissions_v1",
            "is_discoverable": True,
            "allow_ai_query": True,
            "allow_download": True,
        }

    direct_access = _resolve_direct_grant_access(
        db_session,
        record,
        clean_user_id,
        action=clean_action,
    )
    group_access = _resolve_group_grant_access(
        db_session,
        record,
        clean_user_id,
        action=clean_action,
    )
    inherited_folder_access = _resolve_inherited_folder_file_access(
        db_session,
        record,
        clean_user_id,
        action=clean_action,
    )

    return _stronger_access_decision(
        _stronger_access_decision(
            direct_access,
            group_access,
        ),
        inherited_folder_access,
    )

def build_registry_payload_from_record(
    record: FileRegistry,
    *,
    access_decision: dict,
    include_trashed: bool = False,
    requesting_user_id: int = 0,
) -> Optional[dict]:
    if not record or not record.path:
        return None

    record_is_trashed = is_file_record_trashed(
        record
    )

    if record_is_trashed and not include_trashed:
        return None

    source_path = os.path.abspath(
        str(record.path)
    )

    if not os.path.isfile(
        source_path
    ):
        return None

    public_handle = str(
        record.random_name or ""
    ).strip()

    if not public_handle:
        return None

    try:
        size_bytes = int(
            record.size_bytes
            or os.path.getsize(
                source_path
            )
        )
    except (
        TypeError,
        OSError,
        ValueError,
    ):
        size_bytes = None

    document_status = resolve_file_document_status(
        record
    )
    capabilities = build_file_capabilities(
        record,
        access_decision,
        requesting_user_id=requesting_user_id,
    )
    available_actions = build_file_available_actions(
        capabilities
    )
    solomon_action_projection = (
        build_solomon_file_action_projection(
            capabilities,
            {
                "extension": record.extension,
                "original_name": record.original_name,
            },
        )
    )

    return {
        "document_id": public_handle,
        "file_id": str(record.id),
        "original_name": (
            record.original_name
            or public_handle
        ),
        "random_name": public_handle,
        "path": source_path,
        "size_bytes": size_bytes,
        "checksum": record.checksum,
        "extension": record.extension,
        "uploaded_at": record.upload_time,
        "updated_at": record.updated_at,
        "status": getattr(
            record,
            "status",
            ACTIVE_STATUS,
        ),
        "classification": getattr(
            record,
            "classification",
            "internal",
        ),
        "version_number": getattr(
            record,
            "version_number",
            1,
        ),
        "active": False,
        "trashed": record_is_trashed,
        "document_status": document_status,
        "storage_status": document_status,
        "library_status": document_status,
        "action_context": document_status,
        "capabilities": capabilities,
        "available_actions": available_actions,
        **solomon_action_projection,
        **access_decision,
    }


def _append_corpus_entry(
    entries: list[dict],
    seen_document_ids: set[str],
    record: FileRegistry,
    access_decision: dict,
    requesting_user_id: int,
    limit: int,
) -> bool:
    if len(entries) >= limit:
        return False

    if not record or is_file_record_trashed(record):
        return True

    payload = build_registry_payload_from_record(
        record,
        access_decision=access_decision,
        requesting_user_id=requesting_user_id,
    )

    if not payload:
        return True

    document_id = str(
        payload.get("document_id")
        or payload.get("random_name")
        or payload.get("file_id")
        or ""
    ).strip()

    if not document_id or document_id in seen_document_ids:
        return True

    payload["active"] = False
    entries.append(payload)
    seen_document_ids.add(document_id)

    return len(entries) < limit


def _group_library_corpus_records(
    db_session,
    user_id: int,
    organization_id: str,
    limit: int,
    *,
    action: str = QUERY_ACTION,
) -> list[tuple[FileRegistry, dict]]:
    """Legacy organization custody never contributes to the authorized corpus."""

    return []

def _direct_grant_corpus_records(
    db_session,
    user_id: int,
    organization_id: str,
    limit: int,
    *,
    action: str = QUERY_ACTION,
) -> list[tuple[FileRegistry, dict]]:
    clean_action = _clean_action(action)

    query = (
        db_session.query(
            FileRegistry,
            FileAccessGrant,
        )
        .join(
            FileAccessGrant,
            FileAccessGrant.file_registry_id
            == FileRegistry.id,
        )
        .filter(
            FileAccessGrant.granted_to_user_id
            == user_id,
            FileAccessGrant.status
            == ACTIVE_STATUS,
            FileAccessGrant.revoked_at.is_(None),
        )
    )

    if clean_action == QUERY_ACTION:
        query = query.filter(
            FileAccessGrant.allow_ai_query.is_(True),
            FileAccessGrant.is_discoverable.is_(True),
        )

    if organization_id:
        query = query.filter(
            FileAccessGrant.organization_id
            == organization_id
        )

    rows = (
        query.order_by(
            FileRegistry.updated_at.desc(),
            FileRegistry.upload_time.desc(),
            FileRegistry.id.desc(),
        )
        .limit(limit * 3)
        .all()
    )

    records: list[tuple[FileRegistry, dict]] = []

    for record, grant in rows:
        if is_file_record_trashed(
            record
        ):
            continue

        if not _direct_grant_allows_action(
            grant,
            clean_action,
        ):
            continue

        grant_organization_id = _clean_authority_value(
            grant.organization_id
        )

        if grant_organization_id:
            organization = db_session.get(
                Organization,
                grant_organization_id,
            )

            if not _is_active_organization(
                organization,
                action=clean_action,
            ):
                continue

            if not _active_organization_membership(
                db_session,
                user_id,
                grant_organization_id,
            ):
                continue

        permission = str(
            grant.permission or ""
        ).strip().lower()

        records.append(
            (
                record,
                {
                    "access_scope": DIRECT_GRANT_SCOPE,
                    "permission": permission,
                    "authorized_action": clean_action,
                    "organization_id": grant.organization_id,
                    "grant_id": grant.id,
                    "grant_type": grant.grant_type,
                    "authority_basis": "direct_user_grant",
                    "policy_version": _canonical_policy_version(
                        getattr(
                            grant,
                            "policy_version",
                            None,
                        )
                    ),
                    "is_discoverable": _enabled_flag(
                        getattr(
                            grant,
                            "is_discoverable",
                            True,
                        )
                    ),
                    "allow_ai_query": _enabled_flag(
                        getattr(
                            grant,
                            "allow_ai_query",
                            True,
                        )
                    ),
                    "expires_at": getattr(
                        grant,
                        "expires_at",
                        None,
                    ),
                },
            )
        )

    return records


def _group_grant_corpus_records(
    db_session,
    user_id: int,
    organization_id: str,
    limit: int,
    *,
    action: str = QUERY_ACTION,
) -> list[tuple[FileRegistry, dict]]:
    clean_action = _clean_action(action)

    query = (
        db_session.query(
            FileRegistry,
            FileGroupAccessGrant,
            OrganizationGroup,
            OrganizationGroupMembership,
            Organization,
        )
        .join(
            FileGroupAccessGrant,
            FileGroupAccessGrant.file_registry_id
            == FileRegistry.id,
        )
        .join(
            OrganizationGroup,
            OrganizationGroup.group_id
            == FileGroupAccessGrant.group_id,
        )
        .join(
            OrganizationGroupMembership,
            OrganizationGroupMembership.group_id
            == OrganizationGroup.group_id,
        )
        .join(
            Organization,
            Organization.organization_id
            == FileGroupAccessGrant.organization_id,
        )
        .filter(
            FileGroupAccessGrant.status
            == ACTIVE_STATUS,
            FileGroupAccessGrant.revoked_at.is_(None),
            OrganizationGroup.status == ACTIVE_STATUS,
            OrganizationGroup.removed_at.is_(None),
            OrganizationGroupMembership.user_id == user_id,
            OrganizationGroupMembership.status == ACTIVE_STATUS,
            OrganizationGroupMembership.removed_at.is_(None),
            Organization.status == ACTIVE_STATUS,
            Organization.suspended_at.is_(None),
        )
    )

    if clean_action == QUERY_ACTION:
        query = query.filter(
            Organization.ai_query_enabled.is_(True),
            FileGroupAccessGrant.allow_ai_query.is_(True),
            FileGroupAccessGrant.is_discoverable.is_(True),
        )

    if organization_id:
        query = query.filter(
            FileGroupAccessGrant.organization_id
            == organization_id
        )

    rows = (
        query.order_by(
            FileRegistry.updated_at.desc(),
            FileRegistry.upload_time.desc(),
            FileRegistry.id.desc(),
        )
        .limit(limit * 3)
        .all()
    )

    records: list[tuple[FileRegistry, dict]] = []

    for (
        record,
        grant,
        group,
        group_membership,
        organization,
    ) in rows:
        if is_file_record_trashed(
            record
        ):
            continue

        if not _is_active_organization(
            organization,
            action=clean_action,
        ):
            continue

        if not _active_organization_membership(
            db_session,
            user_id,
            organization.organization_id,
        ):
            continue

        if not _group_grant_allows_action(
            grant,
            clean_action,
        ):
            continue

        permission = str(
            grant.permission or ""
        ).strip().lower()

        records.append(
            (
                record,
                {
                    "access_scope": GROUP_GRANT_SCOPE,
                    "permission": permission,
                    "authorized_action": clean_action,
                    "organization_id": grant.organization_id,
                    "group_id": group.group_id,
                    "group_membership_id": group_membership.id,
                    "group_grant_id": grant.id,
                    "grant_type": grant.grant_type,
                    "authority_basis": "group_grant",
                    "policy_version": _canonical_policy_version(
                        getattr(
                            grant,
                            "policy_version",
                            None,
                        )
                    ),
                    "is_discoverable": _enabled_flag(
                        getattr(
                            grant,
                            "is_discoverable",
                            True,
                        )
                    ),
                    "allow_ai_query": _enabled_flag(
                        getattr(
                            grant,
                            "allow_ai_query",
                            True,
                        )
                    ),
                    "expires_at": getattr(
                        grant,
                        "expires_at",
                        None,
                    ),
                },
            )
        )

    return records


def _owned_file_corpus_records(
    db_session,
    user_id: int,
    limit: int,
    *,
    action: str = QUERY_ACTION,
) -> list[tuple[FileRegistry, dict]]:
    clean_action = _clean_action(action)

    rows = (
        db_session.query(
            FileRegistry
        )
        .filter(
            FileRegistry.uploader_id == user_id
        )
        .order_by(
            FileRegistry.updated_at.desc(),
            FileRegistry.upload_time.desc(),
            FileRegistry.id.desc(),
        )
        .limit(limit * 3)
        .all()
    )

    records: list[tuple[FileRegistry, dict]] = []

    for record in rows:
        if is_file_record_trashed(
            record
        ):
            continue

        records.append(
            (
                record,
                {
                    "access_scope": PERSONAL_ACCESS_SCOPE,
                    "permission": "owner",
                    "authorized_action": clean_action,
                    "organization_id": None,
                    "authority_basis": "personal_owner",
                    "policy_version": "personal_file_permissions_v1",
                    "is_discoverable": True,
                    "allow_ai_query": True,
                },
            )
        )

    return records


def resolve_authorized_file_registry_corpus(
    user_id: int,
    *,
    organization_id: str = "",
    request_id: str = "untracked",
    limit: int = 75,
    action: str = QUERY_ACTION,
) -> list[dict]:
    """
    Return the user's searchable file corpus under SQL authorization.

    When an organization_id is supplied, the corpus is constrained to that
    active persistence authority. When it is omitted, the corpus includes
    explicit Group grants, direct file grants, and personal owned files.
    Legacy organization custody is never an authorization source.
    """

    clean_user_id = _clean_user_id(
        user_id
    )
    clean_organization_id = _clean_authority_value(
        organization_id
    )
    clean_action = _clean_action(
        action
    )
    safe_limit = _bounded_corpus_limit(limit)

    if not clean_user_id:
        return []

    db_session = SessionLocal()

    try:
        if not _is_active_user(
            db_session,
            clean_user_id,
        ):
            return []

        entries: list[dict] = []
        seen_document_ids: set[str] = set()

        for record, access_decision in _group_grant_corpus_records(
            db_session,
            clean_user_id,
            clean_organization_id,
            safe_limit,
            action=clean_action,
        ):
            if not _append_corpus_entry(
                entries,
                seen_document_ids,
                record,
                access_decision,
                clean_user_id,
                safe_limit,
            ):
                return _apply_current_summary_capabilities(
                    db_session,
                    entries,
                )

        for record, access_decision in _direct_grant_corpus_records(
            db_session,
            clean_user_id,
            clean_organization_id,
            safe_limit,
            action=clean_action,
        ):
            if not _append_corpus_entry(
                entries,
                seen_document_ids,
                record,
                access_decision,
                clean_user_id,
                safe_limit,
            ):
                return _apply_current_summary_capabilities(
                    db_session,
                    entries,
                )

        if not clean_organization_id:
            for record, access_decision in _owned_file_corpus_records(
                db_session,
                clean_user_id,
                safe_limit,
                action=clean_action,
            ):
                if not _append_corpus_entry(
                    entries,
                    seen_document_ids,
                    record,
                    access_decision,
                    clean_user_id,
                    safe_limit,
                ):
                    return _apply_current_summary_capabilities(
                    db_session,
                    entries,
                )

        return _apply_current_summary_capabilities(
            db_session,
            entries,
        )

    except Exception as exc:
        logger.warning(
            "[workspace.reader.corpus_resolve_failed] "
            "request_id=%s user_id=%s organization_id=%s action=%s error=%s",
            request_id,
            clean_user_id,
            clean_organization_id,
            clean_action,
            exc,
        )
        return []
    finally:
        db_session.close()


def resolve_authorized_file_registry_entry(
    user_id: int,
    identifier: str,
    *,
    request_id: str = "untracked",
    action: str = READ_ACTION,
    allow_trashed_owner_read: bool = False,
) -> Optional[dict]:
    clean_identifier = normalize_document_id(
        identifier
    )
    clean_user_id = _clean_user_id(
        user_id
    )
    clean_action = _clean_action(
        action
    )

    if (
        not clean_identifier
        or not clean_user_id
    ):
        return None

    db_session = SessionLocal()

    try:
        if not _is_active_user(
            db_session,
            clean_user_id,
        ):
            return None

        record = (
            resolve_file_record_by_identifier(
                db_session,
                clean_identifier,
            )
        )

        if not record:
            return None

        access_decision = (
            resolve_file_access_decision(
                db_session,
                record,
                clean_user_id,
                action=clean_action,
                allow_trashed_owner_read=allow_trashed_owner_read,
            )
        )

        if not access_decision:
            return None

        payload = build_registry_payload_from_record(
            record,
            access_decision=(
                access_decision
            ),
            include_trashed=allow_trashed_owner_read,
            requesting_user_id=clean_user_id,
        )

        if not payload:
            return None

        return _apply_current_summary_capabilities(
            db_session,
            [payload],
        )[0]
    except Exception as exc:
        logger.warning(
            "[workspace.reader.file_resolve_failed] "
            "request_id=%s identifier=%s action=%s error=%s",
            request_id,
            clean_identifier,
            clean_action,
            exc,
        )
        return None
    finally:
        db_session.close()


def resolve_owned_file_registry_entry(
    user_id: int,
    identifier: str,
    *,
    request_id: str = "untracked",
) -> Optional[dict]:
    return resolve_authorized_file_registry_entry(
        user_id,
        identifier,
        request_id=request_id,
        action=READ_ACTION,
    )


def resolve_owned_workspace_file(
    user_id: int,
    identifier: str,
    *,
    request_id: str = "untracked",
    allow_trashed_owner_read: bool = True,
) -> Optional[dict]:
    return resolve_authorized_file_registry_entry(
        user_id,
        identifier,
        request_id=request_id,
        action=READ_ACTION,
        allow_trashed_owner_read=allow_trashed_owner_read,
    )