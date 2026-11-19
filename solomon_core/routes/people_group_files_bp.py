# -------------------------------------------------------------------
# FILE: people_group_files_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Canonical internal resource-sharing controls.
#
# Organization is the invisible installation/tenant boundary. Resource Owners
# may create explicit direct-User or Group grants. All GUI share entry points
# converge here; Group role or membership never grants authority to share,
# change, or revoke another Owner's resource grant.
# -------------------------------------------------------------------

from __future__ import annotations

import os

from flask import Blueprint, jsonify, render_template, request, session

from solomon_core.auth import resolve_account_context_for_user
from solomon_core.auth_utils import login_required
from solomon_core.db import SessionLocal
from solomon_core.models import (
    FileAccessGrant,
    FileGroupAccessGrant,
    FileRegistry,
    Organization,
    OrganizationGroup,
    OrganizationMembership,
    User,
    utc_now,
)


people_group_files_bp = Blueprint(
    "people_group_files_bp",
    __name__,
)


ACTIVE_STATUS = "active"
REVOKED_STATUS = "revoked"
DEFAULT_PERMISSION = "view"
VALID_PERMISSIONS = {"view", "edit"}
DEFAULT_POLICY_VERSION = "group_file_permissions_v1"
DEFAULT_DIRECT_POLICY_VERSION = "direct_file_permissions_v1"
MAX_SHARE_FILES = 100
DEFAULT_CLASSIFICATION = "internal"


class PeopleGroupFilesError(Exception):
    """Raised when explicit Group file sharing cannot complete safely."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
    ):
        super().__init__(message)
        self.status_code = status_code


def _current_user_id() -> int:
    try:
        return int(session.get("user_id") or 0)
    except (TypeError, ValueError):
        return 0


def _clean_value(value) -> str:
    return str(value or "").strip()


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value == 1
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
            "enabled",
        }
    return False


def _normalize_permission(value) -> str:
    permission = _clean_value(value).lower() or DEFAULT_PERMISSION
    if permission not in VALID_PERMISSIONS:
        raise PeopleGroupFilesError(
            "File permission must be Viewer or Editor.",
            400,
        )
    return permission


def _record_is_available(record: FileRegistry) -> bool:
    if not record:
        return False

    status = _clean_value(getattr(record, "status", ACTIVE_STATUS)).lower()
    if status not in {"", ACTIVE_STATUS}:
        return False
    if getattr(record, "archived_at", None) is not None:
        return False
    if getattr(record, "deleted_at", None) is not None:
        return False

    path = _clean_value(record.path)
    return bool(path and os.path.isfile(path))


def _reader_url(record: FileRegistry) -> str:
    random_name = _clean_value(record.random_name)
    return f"/workspace/file/{random_name}/reader" if random_name else ""


def _serialize_file_record(record: FileRegistry) -> dict:
    return {
        "file_id": record.id,
        "document_id": record.random_name,
        "random_name": record.random_name,
        "original_name": record.original_name,
        "extension": record.extension,
        "size_bytes": record.size_bytes,
        "reader_url": _reader_url(record),
    }


def _serialize_group(group: OrganizationGroup) -> dict:
    return {
        "group_id": group.group_id,
        "organization_id": group.organization_id,
        "name": group.name,
        "description": getattr(group, "description", None),
        "slug": group.slug,
        "status": group.status,
    }


def _share_person_display_name(user: User) -> str:
    email = _clean_value(user.email)
    username = _clean_value(user.username)
    if not username:
        return email

    _prefix, separator, suffix = username.rpartition("-")
    generated_suffix = (
        bool(separator)
        and len(suffix) == 16
        and all(char in "0123456789abcdefABCDEF" for char in suffix)
    )
    if generated_suffix:
        return email

    return username


def _serialize_share_person(user: User) -> dict:
    return {
        "principal_type": "user",
        "principal_id": user.id,
        "user_id": user.id,
        "name": _share_person_display_name(user),
        "email": _clean_value(user.email),
    }


def _serialize_share_group(group: OrganizationGroup) -> dict:
    return {
        "principal_type": "group",
        "principal_id": group.group_id,
        **_serialize_group(group),
    }


def _serialize_direct_grant(
    grant: FileAccessGrant,
    record: FileRegistry,
    user: User,
) -> dict:
    return {
        **_serialize_file_record(record),
        "grant_id": grant.id,
        "principal_type": "user",
        "principal_id": user.id,
        "principal_name": _share_person_display_name(user),
        "principal_email": _clean_value(user.email),
        "permission": _clean_value(grant.permission).lower() or DEFAULT_PERMISSION,
        "allow_download": bool(getattr(grant, "allow_download", True)),
        "status": grant.status,
        "expires_at": getattr(grant, "expires_at", None),
    }


def _serialize_group_grant(
    grant: FileGroupAccessGrant,
    record: FileRegistry,
) -> dict:
    return {
        **_serialize_file_record(record),
        "grant_id": grant.id,
        # Compatibility alias for the existing transport-only client. The
        # server authority is the FileGroupAccessGrant, never legacy custody.
        "custody_id": grant.id,
        "permission": _clean_value(grant.permission).lower() or DEFAULT_PERMISSION,
        "allow_download": bool(getattr(grant, "allow_download", True)),
        "classification": (
            getattr(record, "classification", None)
            or DEFAULT_CLASSIFICATION
        ),
        "policy_version": (
            getattr(grant, "policy_version", None)
            or DEFAULT_POLICY_VERSION
        ),
        "status": grant.status,
        "expires_at": getattr(grant, "expires_at", None),
    }


def _require_organization_context() -> dict:
    user_id = _current_user_id()
    if not user_id:
        raise PeopleGroupFilesError("Authentication required.", 401)

    account_context = resolve_account_context_for_user(user_id)
    organization_payload = (
        account_context.get("organization")
        if isinstance(account_context, dict)
        else None
    )
    membership_payload = (
        account_context.get("membership")
        if isinstance(account_context, dict)
        else None
    )

    organization_id = _clean_value(
        organization_payload.get("organization_id")
        if isinstance(organization_payload, dict)
        else ""
    )
    membership_id = (
        membership_payload.get("membership_id")
        if isinstance(membership_payload, dict)
        else None
    )

    if not organization_id or not membership_id:
        raise PeopleGroupFilesError(
            "An active organization membership is required.",
            403,
        )

    return {
        "user_id": user_id,
        "organization_id": organization_id,
        "membership_id": int(membership_id),
        "account_context": account_context,
    }


def _verify_organization_member(db_session, *, context: dict) -> Organization:
    organization = (
        db_session.query(Organization)
        .filter(
            Organization.organization_id == context["organization_id"],
            Organization.status == ACTIVE_STATUS,
            Organization.suspended_at.is_(None),
        )
        .first()
    )
    membership = (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.id == context["membership_id"],
            OrganizationMembership.organization_id == context["organization_id"],
            OrganizationMembership.user_id == context["user_id"],
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
        )
        .first()
    )

    if not organization or not membership:
        raise PeopleGroupFilesError(
            "The organization membership is no longer active.",
            403,
        )

    return organization


def _require_true_group(
    db_session,
    *,
    context: dict,
    group_id: str,
) -> OrganizationGroup:
    clean_group_id = _clean_value(group_id)
    if not clean_group_id:
        raise PeopleGroupFilesError("Group not found.", 404)

    group = (
        db_session.query(OrganizationGroup)
        .filter(
            OrganizationGroup.group_id == clean_group_id,
            OrganizationGroup.organization_id == context["organization_id"],
            OrganizationGroup.status == ACTIVE_STATUS,
            OrganizationGroup.removed_at.is_(None),
        )
        .first()
    )

    if not group:
        raise PeopleGroupFilesError("Group not found.", 404)

    return group


def _find_owned_file(
    db_session,
    *,
    user_id: int,
    identifier,
) -> FileRegistry | None:
    clean_identifier = _clean_value(identifier)
    if not clean_identifier:
        return None

    record = None
    if clean_identifier.isdigit():
        record = db_session.get(FileRegistry, int(clean_identifier))
    if not record:
        record = (
            db_session.query(FileRegistry)
            .filter(FileRegistry.random_name == clean_identifier)
            .first()
        )

    if (
        not record
        or int(record.uploader_id or 0) != int(user_id)
        or not _record_is_available(record)
    ):
        return None

    return record


def _find_group_grant(
    db_session,
    *,
    group_id: str,
    file_registry_id: int,
) -> FileGroupAccessGrant | None:
    return (
        db_session.query(FileGroupAccessGrant)
        .filter(
            FileGroupAccessGrant.group_id == group_id,
            FileGroupAccessGrant.file_registry_id == file_registry_id,
        )
        .first()
    )


def _active_group_grant_query(db_session, *, group_id: str):
    return (
        db_session.query(FileGroupAccessGrant, FileRegistry)
        .join(
            FileRegistry,
            FileRegistry.id == FileGroupAccessGrant.file_registry_id,
        )
        .filter(
            FileGroupAccessGrant.group_id == group_id,
            FileGroupAccessGrant.status == ACTIVE_STATUS,
            FileGroupAccessGrant.revoked_at.is_(None),
        )
    )


def _list_owned_group_grants(
    db_session,
    *,
    user_id: int,
    group_id: str,
) -> list[dict]:
    rows = (
        _active_group_grant_query(db_session, group_id=group_id)
        .filter(FileRegistry.uploader_id == user_id)
        .order_by(FileGroupAccessGrant.id.desc())
        .all()
    )

    return [
        _serialize_group_grant(grant, record)
        for grant, record in rows
        if _record_is_available(record)
    ]


def _list_available_owned_files(
    db_session,
    *,
    user_id: int,
    group_id: str,
) -> list[dict]:
    active_file_ids = {
        row[0]
        for row in (
            db_session.query(FileGroupAccessGrant.file_registry_id)
            .join(
                FileRegistry,
                FileRegistry.id == FileGroupAccessGrant.file_registry_id,
            )
            .filter(
                FileGroupAccessGrant.group_id == group_id,
                FileGroupAccessGrant.status == ACTIVE_STATUS,
                FileGroupAccessGrant.revoked_at.is_(None),
                FileRegistry.uploader_id == user_id,
            )
            .all()
        )
    }

    records = (
        db_session.query(FileRegistry)
        .filter(FileRegistry.uploader_id == user_id)
        .order_by(FileRegistry.id.desc())
        .limit(250)
        .all()
    )

    return [
        {
            **_serialize_file_record(record),
            "in_group_library": record.id in active_file_ids,
        }
        for record in records
        if _record_is_available(record)
    ]


def _apply_grant_payload(
    grant: FileGroupAccessGrant,
    *,
    permission: str,
    allow_download: bool,
    actor_user_id: int,
) -> None:
    now = utc_now()
    grant.permission = permission
    grant.status = ACTIVE_STATUS
    # Viewer/Editor are the canonical internal resource-use levels. Search
    # discovery and SolomonAI use follow current resource authorization and
    # are not independent Owner-configurable permission dimensions.
    grant.is_discoverable = True
    grant.allow_ai_query = True
    grant.allow_download = bool(allow_download)
    grant.policy_version = DEFAULT_POLICY_VERSION
    grant.expires_at = None
    grant.granted_by_user_id = actor_user_id
    grant.revoked_by_user_id = None
    grant.revoked_at = None
    grant.revocation_reason = None
    grant.updated_at = now


def _resolve_payload_controls(payload: dict) -> tuple[str, bool]:
    permission = _normalize_permission(payload.get("permission", DEFAULT_PERMISSION))
    allow_download = _truthy(payload.get("allow_download", True))
    return permission, allow_download


def _find_direct_grant(
    db_session,
    *,
    user_id: int,
    file_registry_id: int,
) -> FileAccessGrant | None:
    return (
        db_session.query(FileAccessGrant)
        .filter(
            FileAccessGrant.granted_to_user_id == int(user_id),
            FileAccessGrant.file_registry_id == int(file_registry_id),
        )
        .first()
    )


def _apply_direct_grant_payload(
    grant: FileAccessGrant,
    *,
    permission: str,
    allow_download: bool,
    actor_user_id: int,
    organization_id: str,
) -> None:
    now = utc_now()
    grant.organization_id = organization_id
    grant.grant_type = "direct_user"
    grant.permission = permission
    grant.status = ACTIVE_STATUS
    grant.is_discoverable = True
    grant.allow_ai_query = True
    grant.allow_download = bool(allow_download)
    grant.policy_version = DEFAULT_DIRECT_POLICY_VERSION
    grant.expires_at = None
    grant.granted_by_user_id = actor_user_id
    grant.revoked_by_user_id = None
    grant.revoked_at = None
    grant.revocation_reason = None
    grant.updated_at = now


def _require_internal_share_recipient(
    db_session,
    *,
    context: dict,
    user_id,
) -> User:
    try:
        clean_user_id = int(user_id)
    except (TypeError, ValueError):
        raise PeopleGroupFilesError("Person not found.", 404)

    if clean_user_id == int(context["user_id"]):
        raise PeopleGroupFilesError(
            "A file does not need to be shared with its Owner.",
            400,
        )

    user = (
        db_session.query(User)
        .join(
            OrganizationMembership,
            OrganizationMembership.user_id == User.id,
        )
        .filter(
            User.id == clean_user_id,
            User.is_active.is_(True),
            OrganizationMembership.organization_id == context["organization_id"],
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
        )
        .first()
    )
    if not user:
        raise PeopleGroupFilesError(
            "The selected person is not an active member of this Solomon workspace.",
            404,
        )
    return user


def _normalize_share_identifiers(payload: dict) -> list[str]:
    raw_values = payload.get("document_ids") or payload.get("file_ids") or []
    if not isinstance(raw_values, list):
        raw_values = [raw_values]

    single = (
        payload.get("document_id")
        or payload.get("file_id")
        or payload.get("random_name")
        or payload.get("identifier")
    )
    if single:
        raw_values.append(single)

    values: list[str] = []
    seen: set[str] = set()
    for value in raw_values:
        clean = _clean_value(value)
        if clean and clean not in seen:
            seen.add(clean)
            values.append(clean)

    if not values:
        raise PeopleGroupFilesError("Choose at least one file to share.", 400)
    if len(values) > MAX_SHARE_FILES:
        raise PeopleGroupFilesError(
            f"Share no more than {MAX_SHARE_FILES} files at one time.",
            400,
        )
    return values


def _require_owned_share_files(
    db_session,
    *,
    user_id: int,
    identifiers: list[str],
) -> list[FileRegistry]:
    records: list[FileRegistry] = []
    for identifier in identifiers:
        record = _find_owned_file(
            db_session,
            user_id=user_id,
            identifier=identifier,
        )
        if not record:
            raise PeopleGroupFilesError(
                "Every selected file must be an active resource owned by this account.",
                404,
            )
        records.append(record)
    return records


def _list_share_people(db_session, *, context: dict) -> list[dict]:
    rows = (
        db_session.query(User)
        .join(
            OrganizationMembership,
            OrganizationMembership.user_id == User.id,
        )
        .filter(
            OrganizationMembership.organization_id == context["organization_id"],
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
            User.is_active.is_(True),
            User.id != context["user_id"],
        )
        .order_by(User.email.asc())
        .all()
    )
    return [_serialize_share_person(user) for user in rows]


def _list_share_groups(db_session, *, context: dict) -> list[dict]:
    groups = (
        db_session.query(OrganizationGroup)
        .filter(
            OrganizationGroup.organization_id == context["organization_id"],
            OrganizationGroup.status == ACTIVE_STATUS,
            OrganizationGroup.removed_at.is_(None),
        )
        .order_by(OrganizationGroup.name.asc())
        .all()
    )
    return [_serialize_share_group(group) for group in groups]


def _list_share_owned_files(db_session, *, user_id: int) -> list[dict]:
    records = (
        db_session.query(FileRegistry)
        .filter(FileRegistry.uploader_id == user_id)
        .order_by(FileRegistry.id.desc())
        .limit(500)
        .all()
    )
    return [
        _serialize_file_record(record)
        for record in records
        if _record_is_available(record)
    ]


def _serialize_current_access(
    db_session,
    *,
    record: FileRegistry,
) -> list[dict]:
    direct_rows = (
        db_session.query(FileAccessGrant, User)
        .join(User, User.id == FileAccessGrant.granted_to_user_id)
        .filter(
            FileAccessGrant.file_registry_id == record.id,
            FileAccessGrant.status == ACTIVE_STATUS,
            FileAccessGrant.revoked_at.is_(None),
            User.is_active.is_(True),
        )
        .order_by(User.email.asc())
        .all()
    )
    group_rows = (
        db_session.query(FileGroupAccessGrant, OrganizationGroup)
        .join(
            OrganizationGroup,
            OrganizationGroup.group_id == FileGroupAccessGrant.group_id,
        )
        .filter(
            FileGroupAccessGrant.file_registry_id == record.id,
            FileGroupAccessGrant.status == ACTIVE_STATUS,
            FileGroupAccessGrant.revoked_at.is_(None),
            OrganizationGroup.status == ACTIVE_STATUS,
            OrganizationGroup.removed_at.is_(None),
        )
        .order_by(OrganizationGroup.name.asc())
        .all()
    )

    access: list[dict] = []
    now = utc_now()
    for grant, user in direct_rows:
        expires_at = getattr(grant, "expires_at", None)
        if expires_at is not None and expires_at <= now:
            continue
        access.append(_serialize_direct_grant(grant, record, user))

    for grant, group in group_rows:
        expires_at = getattr(grant, "expires_at", None)
        if expires_at is not None and expires_at <= now:
            continue
        access.append({
            **_serialize_group_grant(grant, record),
            "principal_type": "group",
            "principal_id": group.group_id,
            "principal_name": group.name,
            "principal_email": "",
        })

    return access


def _prepare_share_context(db_session) -> dict:
    context = _require_organization_context()
    _verify_organization_member(db_session, context=context)
    return context


def _prepare_request_group(db_session, group_id: str) -> tuple[dict, OrganizationGroup]:
    context = _require_organization_context()
    _verify_organization_member(db_session, context=context)
    group = _require_true_group(
        db_session,
        context=context,
        group_id=group_id,
    )
    return context, group


@people_group_files_bp.route(
    "/people/shares/files/options",
    methods=["GET"],
)
@login_required
def people_file_share_options():
    db_session = SessionLocal()
    try:
        context = _prepare_share_context(db_session)
        include_files = _truthy(request.args.get("include_files"))
        return jsonify({
            "ok": True,
            "people": _list_share_people(db_session, context=context),
            "groups": _list_share_groups(db_session, context=context),
            "owned_files": (
                _list_share_owned_files(
                    db_session,
                    user_id=context["user_id"],
                )
                if include_files
                else []
            ),
            "external_guest_enabled": False,
        }), 200
    except PeopleGroupFilesError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        return jsonify({
            "ok": False,
            "error": "Share options could not be loaded.",
        }), 500
    finally:
        db_session.close()


@people_group_files_bp.route(
    "/people/shares/files",
    methods=["POST"],
)
@login_required
def people_files_share_create():
    payload = request.get_json(silent=True) or {}
    try:
        permission, allow_download = _resolve_payload_controls(payload)
        identifiers = _normalize_share_identifiers(payload)
    except PeopleGroupFilesError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    principal_type = _clean_value(payload.get("principal_type")).lower()
    principal_id = payload.get("principal_id")
    if principal_type not in {"user", "group"}:
        return jsonify({
            "ok": False,
            "error": "Choose an internal Person or Group to share with.",
        }), 400

    db_session = SessionLocal()
    try:
        context = _prepare_share_context(db_session)
        records = _require_owned_share_files(
            db_session,
            user_id=context["user_id"],
            identifiers=identifiers,
        )

        if principal_type == "user":
            principal = _require_internal_share_recipient(
                db_session,
                context=context,
                user_id=principal_id,
            )
        else:
            principal = _require_true_group(
                db_session,
                context=context,
                group_id=_clean_value(principal_id),
            )

        results: list[dict] = []
        for record in records:
            if principal_type == "user":
                grant = _find_direct_grant(
                    db_session,
                    user_id=principal.id,
                    file_registry_id=record.id,
                )
                if not grant:
                    grant = FileAccessGrant(
                        file_registry_id=record.id,
                        organization_id=context["organization_id"],
                        granted_to_user_id=principal.id,
                        granted_by_user_id=context["user_id"],
                        grant_type="direct_user",
                        permission=permission,
                        status=ACTIVE_STATUS,
                        is_discoverable=True,
                        allow_ai_query=True,
                        allow_download=allow_download,
                        policy_version=DEFAULT_DIRECT_POLICY_VERSION,
                    )
                    db_session.add(grant)
                else:
                    _apply_direct_grant_payload(
                        grant,
                        permission=permission,
                        allow_download=allow_download,
                        actor_user_id=context["user_id"],
                        organization_id=context["organization_id"],
                    )
                db_session.flush()
                results.append(_serialize_direct_grant(grant, record, principal))
            else:
                grant = _find_group_grant(
                    db_session,
                    group_id=principal.group_id,
                    file_registry_id=record.id,
                )
                if not grant:
                    grant = FileGroupAccessGrant(
                        file_registry_id=record.id,
                        organization_id=context["organization_id"],
                        group_id=principal.group_id,
                        granted_by_user_id=context["user_id"],
                        permission=permission,
                        status=ACTIVE_STATUS,
                        is_discoverable=True,
                        allow_ai_query=True,
                        allow_download=allow_download,
                        policy_version=DEFAULT_POLICY_VERSION,
                    )
                    db_session.add(grant)
                else:
                    _apply_grant_payload(
                        grant,
                        permission=permission,
                        allow_download=allow_download,
                        actor_user_id=context["user_id"],
                    )
                db_session.flush()
                results.append({
                    **_serialize_group_grant(grant, record),
                    "principal_type": "group",
                    "principal_id": principal.group_id,
                    "principal_name": principal.name,
                    "principal_email": "",
                })

        db_session.commit()
        return jsonify({
            "ok": True,
            "message": "Files shared." if len(records) > 1 else "File shared.",
            "shares": results,
        }), 200
    except PeopleGroupFilesError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The file share could not be created.",
        }), 500
    finally:
        db_session.close()


@people_group_files_bp.route(
    "/people/shares/files/<document_id>/access",
    methods=["GET"],
)
@login_required
def people_file_share_access(document_id: str):
    db_session = SessionLocal()
    try:
        context = _prepare_share_context(db_session)
        record = _find_owned_file(
            db_session,
            user_id=context["user_id"],
            identifier=document_id,
        )
        if not record:
            raise PeopleGroupFilesError(
                "The selected file is not an active resource owned by this account.",
                404,
            )
        return jsonify({
            "ok": True,
            "file": _serialize_file_record(record),
            "access": _serialize_current_access(db_session, record=record),
        }), 200
    except PeopleGroupFilesError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        return jsonify({
            "ok": False,
            "error": "Current file access could not be loaded.",
        }), 500
    finally:
        db_session.close()


@people_group_files_bp.route(
    "/people/shares/files/<document_id>/<principal_type>/<principal_id>",
    methods=["DELETE"],
)
@login_required
def people_file_share_revoke(document_id: str, principal_type: str, principal_id: str):
    clean_principal_type = _clean_value(principal_type).lower()
    if clean_principal_type not in {"user", "group"}:
        return jsonify({"ok": False, "error": "Share not found."}), 404

    db_session = SessionLocal()
    try:
        context = _prepare_share_context(db_session)
        record = _find_owned_file(
            db_session,
            user_id=context["user_id"],
            identifier=document_id,
        )
        if not record:
            raise PeopleGroupFilesError("The selected file was not found.", 404)

        if clean_principal_type == "user":
            try:
                clean_user_id = int(principal_id)
            except (TypeError, ValueError):
                raise PeopleGroupFilesError("Share not found.", 404)
            grant = _find_direct_grant(
                db_session,
                user_id=clean_user_id,
                file_registry_id=record.id,
            )
        else:
            grant = _find_group_grant(
                db_session,
                group_id=_clean_value(principal_id),
                file_registry_id=record.id,
            )

        if not grant or grant.status != ACTIVE_STATUS or grant.revoked_at is not None:
            raise PeopleGroupFilesError("Share not found.", 404)

        now = utc_now()
        grant.status = REVOKED_STATUS
        grant.revoked_by_user_id = context["user_id"]
        grant.revoked_at = now
        grant.revocation_reason = "Resource Owner revoked share."
        grant.updated_at = now
        db_session.commit()

        return jsonify({"ok": True, "message": "Access revoked."}), 200
    except PeopleGroupFilesError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The share could not be revoked.",
        }), 500
    finally:
        db_session.close()


@people_group_files_bp.route(
    "/people/groups/<group_id>/files",
    methods=["GET"],
)
@login_required
def people_group_files_page(group_id: str):
    db_session = SessionLocal()
    try:
        context, group = _prepare_request_group(db_session, group_id)
        group_context = _serialize_group(group)
        return render_template(
            "people_group_files.html",
            active_module="people",
            account_context=context["account_context"],
            active_group=group_context,
            group_context=group_context,
        )
    except PeopleGroupFilesError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    finally:
        db_session.close()


@people_group_files_bp.route(
    "/people/groups/<group_id>/files/data",
    methods=["GET"],
)
@login_required
def people_group_files_data(group_id: str):
    db_session = SessionLocal()
    try:
        context, group = _prepare_request_group(db_session, group_id)
        return jsonify({
            "ok": True,
            "group": _serialize_group(group),
            "group_id": group.group_id,
            "owned_files": _list_available_owned_files(
                db_session,
                user_id=context["user_id"],
                group_id=group.group_id,
            ),
            # Management view is owner-scoped. It never discloses another
            # owner's Group-shared file merely because this user can open the
            # management route.
            "group_files": _list_owned_group_grants(
                db_session,
                user_id=context["user_id"],
                group_id=group.group_id,
            ),
        }), 200
    except PeopleGroupFilesError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    finally:
        db_session.close()


@people_group_files_bp.route(
    "/people/groups/<group_id>/files",
    methods=["POST"],
)
@login_required
def people_group_files_add(group_id: str):
    payload = request.get_json(silent=True) or {}
    identifier = (
        payload.get("file_id")
        or payload.get("document_id")
        or payload.get("random_name")
        or payload.get("identifier")
    )

    try:
        permission, allow_download = _resolve_payload_controls(payload)
    except PeopleGroupFilesError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    db_session = SessionLocal()
    try:
        context, group = _prepare_request_group(db_session, group_id)
        record = _find_owned_file(
            db_session,
            user_id=context["user_id"],
            identifier=identifier,
        )
        if not record:
            raise PeopleGroupFilesError(
                "The selected file is not an active resource owned by this account.",
                404,
            )

        grant = _find_group_grant(
            db_session,
            group_id=group.group_id,
            file_registry_id=record.id,
        )
        if not grant:
            grant = FileGroupAccessGrant(
                file_registry_id=record.id,
                organization_id=context["organization_id"],
                group_id=group.group_id,
                granted_by_user_id=context["user_id"],
                permission=permission,
                status=ACTIVE_STATUS,
                is_discoverable=True,
                allow_ai_query=True,
                allow_download=allow_download,
                policy_version=DEFAULT_POLICY_VERSION,
            )
            db_session.add(grant)
        else:
            _apply_grant_payload(
                grant,
                permission=permission,
                allow_download=allow_download,
                actor_user_id=context["user_id"],
            )

        db_session.flush()
        db_session.commit()
        db_session.refresh(grant)

        return jsonify({
            "ok": True,
            "message": "File shared with Group.",
            "group_file": _serialize_group_grant(grant, record),
        }), 200
    except PeopleGroupFilesError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The Group share could not be created.",
        }), 500
    finally:
        db_session.close()


@people_group_files_bp.route(
    "/people/groups/<group_id>/files/<int:grant_id>",
    methods=["PATCH"],
)
@login_required
def people_group_files_update(group_id: str, grant_id: int):
    payload = request.get_json(silent=True) or {}

    try:
        permission, allow_download = _resolve_payload_controls(payload)
    except PeopleGroupFilesError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    db_session = SessionLocal()
    try:
        context, group = _prepare_request_group(db_session, group_id)
        result = (
            db_session.query(FileGroupAccessGrant, FileRegistry)
            .join(
                FileRegistry,
                FileRegistry.id == FileGroupAccessGrant.file_registry_id,
            )
            .filter(
                FileGroupAccessGrant.id == grant_id,
                FileGroupAccessGrant.group_id == group.group_id,
                FileRegistry.uploader_id == context["user_id"],
            )
            .first()
        )
        if not result:
            raise PeopleGroupFilesError("The selected Group share was not found.", 404)

        grant, record = result
        if not _record_is_available(record):
            raise PeopleGroupFilesError(
                "The selected file is not currently available.",
                404,
            )

        _apply_grant_payload(
            grant,
            permission=permission,
            allow_download=allow_download,
            actor_user_id=context["user_id"],
        )
        db_session.commit()
        db_session.refresh(grant)

        return jsonify({
            "ok": True,
            "message": "Group share updated.",
            "group_file": _serialize_group_grant(grant, record),
        }), 200
    except PeopleGroupFilesError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The Group share could not be updated.",
        }), 500
    finally:
        db_session.close()


@people_group_files_bp.route(
    "/people/groups/<group_id>/files/<int:grant_id>",
    methods=["DELETE"],
)
@login_required
def people_group_files_remove(group_id: str, grant_id: int):
    db_session = SessionLocal()
    try:
        context, group = _prepare_request_group(db_session, group_id)
        result = (
            db_session.query(FileGroupAccessGrant, FileRegistry)
            .join(
                FileRegistry,
                FileRegistry.id == FileGroupAccessGrant.file_registry_id,
            )
            .filter(
                FileGroupAccessGrant.id == grant_id,
                FileGroupAccessGrant.group_id == group.group_id,
                FileRegistry.uploader_id == context["user_id"],
            )
            .first()
        )
        if not result:
            raise PeopleGroupFilesError("The selected Group share was not found.", 404)

        grant, _record = result
        now = utc_now()
        grant.status = REVOKED_STATUS
        grant.revoked_by_user_id = context["user_id"]
        grant.revoked_at = now
        grant.revocation_reason = "Resource Owner revoked Group share."
        grant.updated_at = now
        db_session.commit()

        return jsonify({
            "ok": True,
            "message": "File unshared from Group.",
            "grant_id": grant.id,
            "custody_id": grant.id,
        }), 200
    except PeopleGroupFilesError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The Group share could not be revoked.",
        }), 500
    finally:
        db_session.close()


__all__ = [
    "people_group_files_bp",
]
