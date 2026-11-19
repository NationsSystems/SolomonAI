# -------------------------------------------------------------------
# FILE: workspace_reader_file_access.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# Central SQL authorization for workspace file access.
# FileRegistry remains canonical identity while group custody,
# membership, direct grants, and group grants determine access authority.
# -------------------------------------------------------------------

from datetime import datetime, timezone
import json
import os
from typing import Any, Dict, Optional

from solomon_core.db import SessionLocal
from solomon_core.logger import get_logger
from solomon_core.models import (
    FileAccessGrant,
    FileGroupAccessGrant,
    FileRegistry,
    Organization,
    OrganizationFileCustody,
    OrganizationGroup,
    OrganizationGroupMembership,
    OrganizationMembership,
    User,
)
from solomon_core.workspace_reader.workspace_reader_urls import (
    normalize_document_id,
)


logger = get_logger("workspace_reader.file_access")

ACTIVE_STATUS = "active"
GROUP_LIBRARY_SCOPE = "group_library"
LEGACY_COMPANY_LIBRARY_SCOPE = "company_library"
GROUP_LIBRARY_SCOPES = (
    GROUP_LIBRARY_SCOPE,
    LEGACY_COMPANY_LIBRARY_SCOPE,
)
GROUP_FILE_POLICY_VERSION = "group_file_permissions_v1"
LEGACY_ORGANIZATION_FILE_POLICY_VERSION = "organization_file_permissions_v1"
PERSONAL_ACCESS_SCOPE = "my_files"
DIRECT_GRANT_SCOPE = "shared_with_me"
GROUP_GRANT_SCOPE = "shared_with_group"

READ_ACTION = "read"
QUERY_ACTION = "query"
DISCOVER_ACTION = "discover"

READ_PERMISSIONS = {
    "view",
    "read",
    "comment",
    "edit",
    "manage",
    "owner",
}
MANAGE_PERMISSIONS = {
    "edit",
    "manage",
    "owner",
}
QUERY_PERMISSIONS = set(READ_PERMISSIONS)

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
    READ_ACTION,
    QUERY_ACTION,
    DISCOVER_ACTION,
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
    action = str(value or READ_ACTION).strip().lower()

    if action not in AUTHORIZED_ACTIONS:
        return READ_ACTION

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

    if clean_action == QUERY_ACTION:
        return (
            clean_permission in QUERY_PERMISSIONS
            and _enabled_flag(allow_ai_query)
        )

    if clean_action == DISCOVER_ACTION:
        return clean_permission in READ_PERMISSIONS

    return clean_permission in READ_PERMISSIONS


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
    clean_action = _clean_action(action)

    result = (
        db_session.query(
            OrganizationFileCustody,
            OrganizationMembership,
            Organization,
        )
        .join(
            Organization,
            Organization.organization_id
            == OrganizationFileCustody.organization_id,
        )
        .join(
            OrganizationMembership,
            OrganizationMembership.organization_id
            == OrganizationFileCustody.organization_id,
        )
        .filter(
            OrganizationFileCustody.file_registry_id
            == record.id,
            OrganizationFileCustody.library_scope
            .in_(GROUP_LIBRARY_SCOPES),
            OrganizationMembership.user_id
            == user_id,
        )
        .order_by(
            OrganizationMembership.is_primary.desc(),
            OrganizationMembership.id.asc(),
        )
        .first()
    )

    if not result:
        return None

    custody, membership, organization = result

    if not _is_active_organization(
        organization,
        action=clean_action,
    ):
        return None

    if (
        membership.status != ACTIVE_STATUS
        or membership.removed_at is not None
    ):
        return None

    if _is_group_library_guest_role(
        membership.role
    ):
        return None

    if not _group_custody_allows_action(
        custody,
        clean_action,
    ):
        return None

    return {
        "access_scope": GROUP_LIBRARY_SCOPE,
        "permission": "view",
        "authorized_action": clean_action,
        "organization_id": custody.organization_id,
        "membership_id": membership.id,
        "membership_role": membership.role,
        "custody_id": custody.id,
        "custody_mode": custody.custody_mode,
        "library_scope": _canonical_library_scope(
            custody.library_scope
        ),
        "authority_basis": "group_membership",
        "policy_version": _canonical_policy_version(
            getattr(
                custody,
                "policy_version",
                None,
            )
        ),
        "is_discoverable": _enabled_flag(
            getattr(
                custody,
                "is_discoverable",
                True,
            )
        ),
        "allow_ai_query": _enabled_flag(
            getattr(
                custody,
                "allow_ai_query",
                True,
            )
        ),
    }


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

    result = (
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
            FileGroupAccessGrant.file_registry_id
            == record.id,
            FileGroupAccessGrant.status
            == ACTIVE_STATUS,
            FileGroupAccessGrant.revoked_at.is_(None),
            OrganizationGroup.status == ACTIVE_STATUS,
            OrganizationGroup.removed_at.is_(None),
            OrganizationGroupMembership.user_id == user_id,
            OrganizationGroupMembership.status == ACTIVE_STATUS,
            OrganizationGroupMembership.removed_at.is_(None),
        )
        .order_by(
            FileGroupAccessGrant.id.asc(),
        )
        .first()
    )

    if not result:
        return None

    grant, group, group_membership, organization = result

    if not _is_active_organization(
        organization,
        action=clean_action,
    ):
        return None

    if not _active_organization_membership(
        db_session,
        user_id,
        organization.organization_id,
    ):
        return None

    if not _group_grant_allows_action(
        grant,
        clean_action,
    ):
        return None

    permission = str(
        grant.permission or ""
    ).strip().lower()

    return {
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
    }


def resolve_file_access_decision(
    db_session,
    record: FileRegistry,
    user_id: int,
    *,
    action: str = READ_ACTION,
) -> Optional[dict]:
    clean_user_id = _clean_user_id(
        user_id
    )
    clean_action = _clean_action(
        action
    )

    if (
        not record
        or not clean_user_id
        or is_file_record_trashed(
            record
        )
        or not _is_active_user(
            db_session,
            clean_user_id,
        )
    ):
        return None

    direct_access = _resolve_direct_grant_access(
        db_session,
        record,
        clean_user_id,
        action=clean_action,
    )

    if direct_access:
        return direct_access

    group_access = _resolve_group_grant_access(
        db_session,
        record,
        clean_user_id,
        action=clean_action,
    )

    if group_access:
        return group_access

    group_library_access = (
        _resolve_group_library_access(
            db_session,
            record,
            clean_user_id,
            action=clean_action,
        )
    )

    if group_library_access:
        return group_library_access

    has_organization_custody = (
        _has_active_organization_custody(
            db_session,
            record,
        )
    )

    if (
        not has_organization_custody
        and is_owned_file_record(
            record,
            clean_user_id,
        )
    ):
        return {
            "access_scope": PERSONAL_ACCESS_SCOPE,
            "permission": "manage",
            "authorized_action": clean_action,
            "organization_id": None,
            "authority_basis": "personal_owner",
            "policy_version": "personal_file_permissions_v1",
            "is_discoverable": True,
            "allow_ai_query": True,
        }

    return None


def build_registry_payload_from_record(
    record: FileRegistry,
    *,
    access_decision: dict,
) -> Optional[dict]:
    if not record or not record.path:
        return None

    if is_file_record_trashed(
        record
    ):
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
        **access_decision,
    }


def _append_corpus_entry(
    entries: list[dict],
    seen_document_ids: set[str],
    record: FileRegistry,
    access_decision: dict,
    limit: int,
) -> bool:
    if len(entries) >= limit:
        return False

    if not record or is_file_record_trashed(record):
        return True

    payload = build_registry_payload_from_record(
        record,
        access_decision=access_decision,
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
    clean_action = _clean_action(action)

    query = (
        db_session.query(
            FileRegistry,
            OrganizationFileCustody,
            OrganizationMembership,
            Organization,
        )
        .join(
            OrganizationFileCustody,
            OrganizationFileCustody.file_registry_id
            == FileRegistry.id,
        )
        .join(
            Organization,
            Organization.organization_id
            == OrganizationFileCustody.organization_id,
        )
        .join(
            OrganizationMembership,
            OrganizationMembership.organization_id
            == OrganizationFileCustody.organization_id,
        )
        .filter(
            OrganizationFileCustody.status
            == ACTIVE_STATUS,
            OrganizationFileCustody.removed_at.is_(None),
            OrganizationFileCustody.library_scope
            .in_(GROUP_LIBRARY_SCOPES),
            Organization.status == ACTIVE_STATUS,
            Organization.suspended_at.is_(None),
            OrganizationMembership.user_id
            == user_id,
            OrganizationMembership.status
            == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
        )
    )

    if clean_action == QUERY_ACTION:
        query = query.filter(
            Organization.ai_query_enabled.is_(True),
            OrganizationFileCustody.allow_ai_query.is_(True),
            OrganizationFileCustody.is_discoverable.is_(True),
        )

    if organization_id:
        query = query.filter(
            OrganizationFileCustody.organization_id
            == organization_id
        )

    rows = (
        query.order_by(
            OrganizationMembership.is_primary.desc(),
            FileRegistry.updated_at.desc(),
            FileRegistry.upload_time.desc(),
            FileRegistry.id.desc(),
        )
        .limit(limit * 3)
        .all()
    )

    records: list[tuple[FileRegistry, dict]] = []

    for record, custody, membership, organization in rows:
        if is_file_record_trashed(
            record
        ):
            continue

        if not _is_active_organization(
            organization,
            action=clean_action,
        ):
            continue

        if _is_group_library_guest_role(
            membership.role
        ):
            continue

        if not _group_custody_allows_action(
            custody,
            clean_action,
        ):
            continue

        records.append(
            (
                record,
                {
                    "access_scope": GROUP_LIBRARY_SCOPE,
                    "permission": "view",
                    "authorized_action": clean_action,
                    "organization_id": custody.organization_id,
                    "membership_id": membership.id,
                    "membership_role": membership.role,
                    "custody_id": custody.id,
                    "custody_mode": custody.custody_mode,
                    "library_scope": _canonical_library_scope(
                        custody.library_scope
                    ),
                    "authority_basis": "group_membership",
                    "policy_version": _canonical_policy_version(
                        getattr(
                            custody,
                            "policy_version",
                            None,
                        )
                    ),
                    "is_discoverable": _enabled_flag(
                        getattr(
                            custody,
                            "is_discoverable",
                            True,
                        )
                    ),
                    "allow_ai_query": _enabled_flag(
                        getattr(
                            custody,
                            "allow_ai_query",
                            True,
                        )
                    ),
                },
            )
        )

    return records


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

        if _has_active_organization_custody(
            db_session,
            record,
        ):
            continue

        records.append(
            (
                record,
                {
                    "access_scope": PERSONAL_ACCESS_SCOPE,
                    "permission": "manage",
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
    group-library files visible through active memberships, group grants,
    direct file grants, and personal files that are not under active group
    or organization custody.
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

        for record, access_decision in _group_library_corpus_records(
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
                safe_limit,
            ):
                return entries

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
                safe_limit,
            ):
                return entries

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
                safe_limit,
            ):
                return entries

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
                    safe_limit,
                ):
                    return entries

        return entries

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
            )
        )

        if not access_decision:
            return None

        return build_registry_payload_from_record(
            record,
            access_decision=(
                access_decision
            ),
        )
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
) -> Optional[dict]:
    return resolve_authorized_file_registry_entry(
        user_id,
        identifier,
        request_id=request_id,
        action=READ_ACTION,
    )