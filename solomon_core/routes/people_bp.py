# -------------------------------------------------------------------
# FILE: people_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Canonical People workspace authority for Solomon users, Groups, and
# contextual onboarding invitations. Organization is an invisible installation/tenant boundary;
# user-visible Groups are flat OrganizationGroup principals containing users
# only. Membership changes never grant private-file or AI-source access by
# themselves.
# -------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import re
import secrets

from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from solomon_core.auth import (
    ensure_initial_organization_membership_for_user,
    resolve_account_context_for_user,
)
from solomon_core.auth_utils import login_required
from solomon_core.db import SessionLocal
from solomon_core.logger import get_logger
from solomon_core.routes.people_email import (
    build_people_invitation_accept_url,
    send_people_invitation_email,
)
from solomon_core.models import (
    FileGroupAccessGrant,
    Organization,
    OrganizationAuditEvent,
    OrganizationGroup,
    OrganizationGroupMembership,
    OrganizationInvitation,
    OrganizationInvitationIntent,
    OrganizationMembership,
    User,
    utc_now,
)


people_bp = Blueprint(
    "people_bp",
    __name__,
)

logger = get_logger(
    "Solomon.people"
)


ACTIVE_STATUS = "active"
PENDING_STATUS = "pending"
ACCEPTED_STATUS = "accepted"
REVOKED_STATUS = "revoked"
REMOVED_STATUS = "removed"
EXPIRED_STATUS = "expired"

OWNER_ROLE = "owner"
ADMIN_ROLE = "admin"
MEMBER_ROLE = "member"
GUEST_ROLE = "guest"

MANAGE_GROUP_ROLES = {
    OWNER_ROLE,
    ADMIN_ROLE,
}
INVITABLE_ROLES = {
    ADMIN_ROLE,
    MEMBER_ROLE,
    GUEST_ROLE,
}
ADMIN_ASSIGNABLE_ROLES = {
    MEMBER_ROLE,
    GUEST_ROLE,
}
GROUP_ROLES = {
    OWNER_ROLE,
    ADMIN_ROLE,
    MEMBER_ROLE,
    GUEST_ROLE,
}

DEFAULT_INVITATION_DAYS = 14
INVITATION_CONTRACT = "organization_membership_invitation_v1"
AUDIT_EVENT_CONTRACT = "group_audit_event_v1"

EVENT_INVITATION_CREATED = "group.invitation.created"
EVENT_INVITATION_REFRESHED = "group.invitation.refreshed"
EVENT_INVITATION_EMAIL_SENT = "group.invitation.email_sent"
EVENT_INVITATION_EMAIL_FAILED = "group.invitation.email_failed"
EVENT_INVITATION_REVOKED = "group.invitation.revoked"
EVENT_INVITATION_EXPIRED = "group.invitation.expired"
EVENT_INVITATION_ACCEPTED = "group.invitation.accepted"
EVENT_MEMBERSHIP_ACTIVATED = "group.membership.activated"
EVENT_ROLE_CHANGED = "group.role.changed"
EVENT_MEMBER_REMOVED = "group.member.removed"
EVENT_PRIVILEGED_ACTION_DENIED = "group.privileged_action.denied"
EVENT_GROUP_CREATED = "group.created"
EVENT_GROUP_UPDATED = "group.updated"
EVENT_GROUP_REMOVED = "group.removed"
EVENT_GROUP_MEMBER_ADDED = "group.member.added"
EVENT_INVITATION_INTENT_CREATED = "group.invitation.intent.created"
EVENT_INVITATION_INTENT_COMPLETED = "group.invitation.intent.completed"
EVENT_INVITATION_INTENT_REVOKED = "group.invitation.intent.revoked"

INVITATION_INTENT_PENDING = "pending"
INVITATION_INTENT_COMPLETED = "completed"
INVITATION_INTENT_REVOKED = "revoked"
INVITATION_INTENT_GROUP_MEMBERSHIP = "group_membership"
INVITATION_INTENT_CONTRACT = "organization_invitation_intent_v1"

TRUE_GROUP_ROLES = {
    OWNER_ROLE,
    ADMIN_ROLE,
    MEMBER_ROLE,
}
TRUE_GROUP_ASSIGNABLE_ROLES = {
    ADMIN_ROLE,
    MEMBER_ROLE,
}

CANONICAL_PEOPLE_ROUTE = "/people"


def _is_workspace_partial_request() -> bool:
    render_mode = _clean_value(
        request.headers.get("X-Solomon-Render-Mode")
        or request.headers.get("X-Workspace-Render-Mode")
        or request.headers.get("X-Command-Render-Mode")
        or request.args.get("partial")
    ).lower()
    requested_with = _clean_value(
        request.headers.get("X-Requested-With")
    ).lower()

    if render_mode in {
        "workspace",
        "workspace_partial",
        "partial",
        "shell",
    }:
        return True

    return requested_with == "xmlhttprequest"


class PeopleGroupsError(Exception):
    """Raised when people and group controls cannot complete safely."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
    ):
        super().__init__(message)
        self.status_code = status_code


def _current_user_id() -> int:
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


def _clean_value(value) -> str:
    return str(
        value or ""
    ).strip()


def _people_redirect(
    path_suffix: str = "",
):
    clean_suffix = "/" + _clean_value(
        path_suffix
    ).lstrip("/") if path_suffix else ""
    target = f"{CANONICAL_PEOPLE_ROUTE}{clean_suffix}"

    if request.query_string:
        target = f"{target}?{request.query_string.decode('utf-8', 'ignore')}"

    return redirect(
        target,
        code=308,
    )


def _normalize_email(value) -> str:
    return _clean_value(value).lower()


def _utc_datetime(value) -> datetime | None:
    if not value:
        return None

    if value.tzinfo is None:
        return value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    )


def _hash_invitation_token(token: str) -> str:
    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


def _new_invitation_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)

    return token, _hash_invitation_token(
        token
    )


def _invitation_is_expired(
    invitation: OrganizationInvitation,
) -> bool:
    expires_at = _utc_datetime(
        getattr(
            invitation,
            "expires_at",
            None,
        )
    )

    if not expires_at:
        return False

    return expires_at <= utc_now()


def _safe_iso(value) -> str | None:
    if not value:
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value.isoformat()

    return str(value)


def _audit_details(
    **values,
) -> dict:
    return {
        key: value
        for key, value in values.items()
        if value is not None
    }


def _record_organization_audit_event(
    db_session,
    *,
    event_type: str,
    organization_id: str | None = None,
    actor_user_id: int | None = None,
    target_user_id: int | None = None,
    target_email: str | None = None,
    invitation_id: str | None = None,
    membership_id: int | None = None,
    file_registry_id: int | None = None,
    role_before: str | None = None,
    role_after: str | None = None,
    decision: str = "recorded",
    reason_code: str | None = None,
    request_id: str | None = None,
    source: str = "people_groups",
    details_json: dict | None = None,
) -> OrganizationAuditEvent:
    """Append one organization audit event without granting authority."""

    audit_event = OrganizationAuditEvent(
        organization_id=_clean_value(
            organization_id
        ) or None,
        event_type=_clean_value(
            event_type
        ),
        event_contract=AUDIT_EVENT_CONTRACT,
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        target_email=(
            _normalize_email(
                target_email
            )
            or None
        ),
        invitation_id=_clean_value(
            invitation_id
        ) or None,
        membership_id=membership_id,
        file_registry_id=file_registry_id,
        role_before=(
            _clean_value(
                role_before
            ).lower()
            or None
        ),
        role_after=(
            _clean_value(
                role_after
            ).lower()
            or None
        ),
        decision=_clean_value(
            decision
        ) or "recorded",
        reason_code=_clean_value(
            reason_code
        ) or None,
        request_id=_clean_value(
            request_id
        ) or None,
        source=_clean_value(
            source
        ) or "people_groups",
        details_json=details_json or None,
    )

    db_session.add(
        audit_event
    )

    return audit_event


def _record_failed_people_action(
    db_session,
    context: dict,
    *,
    action: str,
    exc: PeopleGroupsError,
    target_email: str | None = None,
    target_user_id: int | None = None,
    invitation_id: str | None = None,
    membership_id: int | None = None,
    role_after: str | None = None,
) -> None:
    """Best-effort audit for denied privileged group actions."""

    try:
        _record_organization_audit_event(
            db_session,
            event_type=EVENT_PRIVILEGED_ACTION_DENIED,
            organization_id=context.get("organization_id"),
            actor_user_id=context.get("user_id"),
            target_user_id=target_user_id,
            target_email=target_email,
            invitation_id=invitation_id,
            membership_id=membership_id,
            role_after=role_after,
            decision="denied",
            reason_code=f"http_{exc.status_code}",
            details_json=_audit_details(
                action=action,
                error=str(exc),
                status_code=exc.status_code,
            ),
        )
        db_session.commit()
    except Exception:
        db_session.rollback()


def _require_group_manager() -> dict:
    user_id = _current_user_id()

    if not user_id:
        raise PeopleGroupsError(
            "Authentication required.",
            401,
        )

    account_context = resolve_account_context_for_user(
        user_id
    )

    organization = (
        account_context.get("organization")
        if isinstance(
            account_context,
            dict,
        )
        else None
    )
    membership = (
        account_context.get("membership")
        if isinstance(
            account_context,
            dict,
        )
        else None
    )

    organization_id = _clean_value(
        organization.get("organization_id")
        if isinstance(
            organization,
            dict,
        )
        else ""
    )
    membership_id = (
        membership.get("membership_id")
        if isinstance(
            membership,
            dict,
        )
        else None
    )
    role = _clean_value(
        membership.get("role")
        if isinstance(
            membership,
            dict,
        )
        else ""
    ).lower()

    if (
        not organization_id
        or not membership_id
        or role not in MANAGE_GROUP_ROLES
    ):
        raise PeopleGroupsError(
            "People and group controls are available to group owners and admins.",
            403,
        )

    return {
        "user_id": user_id,
        "organization_id": organization_id,
        "membership_id": int(
            membership_id
        ),
        "role": role,
        "account_context": account_context,
    }


def _verify_group_manager(
    db_session,
    *,
    user_id: int,
    organization_id: str,
    membership_id: int,
) -> tuple[Organization, OrganizationMembership]:
    organization = (
        db_session.query(Organization)
        .filter(
            Organization.organization_id == organization_id,
            Organization.status == ACTIVE_STATUS,
            Organization.suspended_at.is_(None),
        )
        .first()
    )

    membership = (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
        )
        .first()
    )

    role = _clean_value(
        getattr(
            membership,
            "role",
            "",
        )
    ).lower()

    if (
        not organization
        or not membership
        or role not in MANAGE_GROUP_ROLES
    ):
        raise PeopleGroupsError(
            "People and group controls are not available for this account.",
            403,
        )

    return organization, membership


def _validate_invitation_role(
    role: str,
    *,
    manager_role: str,
) -> str:
    clean_role = _clean_value(role).lower()

    if clean_role not in INVITABLE_ROLES:
        raise PeopleGroupsError(
            "Choose a valid group role: admin, member, or guest.",
            400,
        )

    if (
        manager_role == ADMIN_ROLE
        and clean_role not in ADMIN_ASSIGNABLE_ROLES
    ):
        raise PeopleGroupsError(
            "Admins can invite members and guests only.",
            403,
        )

    return clean_role


def _validate_membership_role_update(
    role: str,
    *,
    manager_role: str,
    target_role: str,
) -> str:
    clean_role = _clean_value(role).lower()
    clean_target_role = _clean_value(target_role).lower()

    if clean_role not in INVITABLE_ROLES:
        raise PeopleGroupsError(
            "Choose a valid group role: admin, member, or guest.",
            400,
        )

    if clean_target_role == OWNER_ROLE:
        raise PeopleGroupsError(
            "Owner authority cannot be changed from this screen.",
            403,
        )

    if manager_role == ADMIN_ROLE:
        if clean_target_role == ADMIN_ROLE:
            raise PeopleGroupsError(
                "Admins cannot change another admin.",
                403,
            )

        if clean_role not in ADMIN_ASSIGNABLE_ROLES:
            raise PeopleGroupsError(
                "Admins can assign member and guest roles only.",
                403,
            )

    return clean_role


def _serialize_group(
    group_record: Organization,
) -> dict:
    return {
        "group_id": group_record.organization_id,
        "name": group_record.name,
        "slug": group_record.slug,
        "status": group_record.status,
        "legal_name": getattr(
            group_record,
            "legal_name",
            None,
        ),
        "verified_domain": getattr(
            group_record,
            "verified_domain",
            None,
        ),
        "verification_status": getattr(
            group_record,
            "verification_status",
            "unverified",
        ),
    }


def _serialize_membership(
    membership: OrganizationMembership,
    user: User | None,
    *,
    manager_user_id: int,
    manager_role: str,
) -> dict:
    role = _clean_value(
        getattr(
            membership,
            "role",
            "",
        )
    ).lower()
    is_self = int(
        membership.user_id or 0
    ) == int(
        manager_user_id
    )

    can_change_role = False
    can_remove = False

    if not is_self and role != OWNER_ROLE:
        if manager_role == OWNER_ROLE:
            can_change_role = True
            can_remove = True
        elif (
            manager_role == ADMIN_ROLE
            and role in {
                MEMBER_ROLE,
                GUEST_ROLE,
            }
        ):
            can_change_role = True
            can_remove = True

    return {
        "membership_id": membership.id,
        "organization_id": membership.organization_id,
        "user_id": membership.user_id,
        "email": getattr(
            user,
            "email",
            "",
        ),
        "username": getattr(
            user,
            "username",
            "",
        ),
        "role": role,
        "status": membership.status,
        "is_primary": bool(
            getattr(
                membership,
                "is_primary",
                False,
            )
        ),
        "joined_at": _safe_iso(
            getattr(
                membership,
                "joined_at",
                None,
            )
        ),
        "created_at": _safe_iso(
            getattr(
                membership,
                "created_at",
                None,
            )
        ),
        "removed_at": _safe_iso(
            getattr(
                membership,
                "removed_at",
                None,
            )
        ),
        "is_self": is_self,
        "can_change_role": can_change_role,
        "can_remove": can_remove,
    }


def _serialize_invitation(
    invitation: OrganizationInvitation,
) -> dict:
    is_expired = _invitation_is_expired(
        invitation
    )

    return {
        "id": invitation.id,
        "invitation_id": invitation.invitation_id,
        "organization_id": invitation.organization_id,
        "membership_id": invitation.membership_id,
        "email": invitation.email,
        "normalized_email": invitation.normalized_email,
        "role": invitation.role,
        "status": invitation.status,
        "is_expired": is_expired,
        "expires_at": _safe_iso(
            invitation.expires_at
        ),
        "accepted_at": _safe_iso(
            invitation.accepted_at
        ),
        "revoked_at": _safe_iso(
            invitation.revoked_at
        ),
        "created_at": _safe_iso(
            invitation.created_at
        ),
        "updated_at": _safe_iso(
            invitation.updated_at
        ),
    }


def _active_membership_query(
    db_session,
    *,
    organization_id: str,
):
    return (
        db_session.query(
            OrganizationMembership,
            User,
        )
        .join(
            User,
            User.id == OrganizationMembership.user_id,
        )
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
        )
    )


def _list_active_memberships(
    db_session,
    *,
    organization_id: str,
    manager_user_id: int,
    manager_role: str,
) -> list[dict]:
    rows = (
        _active_membership_query(
            db_session,
            organization_id=organization_id,
        )
        .order_by(
            OrganizationMembership.created_at.asc()
        )
        .all()
    )

    serialized = [
        _serialize_membership(
            membership,
            user,
            manager_user_id=manager_user_id,
            manager_role=manager_role,
        )
        for membership, user in rows
    ]

    role_order = {
        OWNER_ROLE: 0,
        ADMIN_ROLE: 1,
        MEMBER_ROLE: 2,
        GUEST_ROLE: 3,
    }

    return sorted(
        serialized,
        key=lambda item: (
            role_order.get(
                item.get("role"),
                99,
            ),
            item.get("email") or "",
        ),
    )


def _list_pending_invitations(
    db_session,
    *,
    organization_id: str,
) -> list[dict]:
    invitations = (
        db_session.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.status == PENDING_STATUS,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        .order_by(
            OrganizationInvitation.created_at.desc()
        )
        .all()
    )

    return [
        _serialize_invitation(
            invitation
        )
        for invitation in invitations
    ]


def _find_user_by_normalized_email(
    db_session,
    *,
    normalized_email: str,
) -> User | None:
    if not normalized_email:
        return None

    return (
        db_session.query(User)
        .filter(
            User.email == normalized_email
        )
        .first()
    )


def _find_membership_for_user(
    db_session,
    *,
    organization_id: str,
    user_id: int,
) -> OrganizationMembership | None:
    return (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user_id,
        )
        .order_by(
            OrganizationMembership.id.desc()
        )
        .first()
    )


def _active_membership_exists_for_email(
    db_session,
    *,
    organization_id: str,
    normalized_email: str,
) -> bool:
    user = _find_user_by_normalized_email(
        db_session,
        normalized_email=normalized_email,
    )

    if not user:
        return False

    membership = _find_membership_for_user(
        db_session,
        organization_id=organization_id,
        user_id=user.id,
    )

    return bool(
        membership
        and membership.status == ACTIVE_STATUS
        and not membership.removed_at
    )


def _find_pending_invitation_for_email(
    db_session,
    *,
    organization_id: str,
    normalized_email: str,
) -> OrganizationInvitation | None:
    return (
        db_session.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.normalized_email == normalized_email,
            OrganizationInvitation.status == PENDING_STATUS,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        .order_by(
            OrganizationInvitation.created_at.desc()
        )
        .first()
    )


def _find_reusable_invitation_for_email(
    db_session,
    *,
    organization_id: str,
    normalized_email: str,
) -> OrganizationInvitation | None:
    """Return the newest unaccepted invitation whose intents can be preserved."""

    return (
        db_session.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.organization_id == organization_id,
            OrganizationInvitation.normalized_email == normalized_email,
            OrganizationInvitation.status.in_({
                PENDING_STATUS,
                EXPIRED_STATUS,
            }),
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        .order_by(
            OrganizationInvitation.created_at.desc()
        )
        .first()
    )


def _find_invitation_by_token(
    db_session,
    *,
    token: str,
) -> OrganizationInvitation | None:
    token_hash = _hash_invitation_token(
        token
    )

    return (
        db_session.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.token_hash == token_hash,
            OrganizationInvitation.status == PENDING_STATUS,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        .first()
    )


def _create_or_refresh_invitation(
    db_session,
    *,
    organization_id: str,
    email: str,
    role: str,
    invited_by_user_id: int,
) -> tuple[OrganizationInvitation, str, bool]:
    normalized_email = _normalize_email(
        email
    )

    if (
        not normalized_email
        or "@" not in normalized_email
        or normalized_email.startswith("@")
        or normalized_email.endswith("@")
    ):
        raise PeopleGroupsError(
            "Enter a valid email address.",
            400,
        )

    if _active_membership_exists_for_email(
        db_session,
        organization_id=organization_id,
        normalized_email=normalized_email,
    ):
        raise PeopleGroupsError(
            "That person already has access to this Solomon workspace.",
            409,
        )

    token, token_hash = _new_invitation_token()
    expires_at = utc_now() + timedelta(
        days=DEFAULT_INVITATION_DAYS
    )

    invitation = _find_reusable_invitation_for_email(
        db_session,
        organization_id=organization_id,
        normalized_email=normalized_email,
    )
    was_refreshed = bool(
        invitation
    )

    if invitation:
        invitation.email = email
        invitation.role = role
        invitation.status = PENDING_STATUS
        invitation.token_hash = token_hash
        invitation.invited_by_user_id = invited_by_user_id
        invitation.expires_at = expires_at
        invitation.updated_at = utc_now()
        invitation.invitation_contract = INVITATION_CONTRACT
        return invitation, token, was_refreshed

    invitation = OrganizationInvitation(
        organization_id=organization_id,
        email=email,
        normalized_email=normalized_email,
        role=role,
        status=PENDING_STATUS,
        token_hash=token_hash,
        invitation_contract=INVITATION_CONTRACT,
        invited_by_user_id=invited_by_user_id,
        expires_at=expires_at,
    )
    db_session.add(
        invitation
    )

    return invitation, token, was_refreshed


def _mark_invitation_revoked(
    invitation: OrganizationInvitation,
    *,
    revoked_by_user_id: int,
    reason: str,
) -> None:
    invitation.status = REVOKED_STATUS
    invitation.token_hash = None
    invitation.revoked_by_user_id = revoked_by_user_id
    invitation.revoked_at = utc_now()
    invitation.revocation_reason = (
        reason
        or "Revoked from the People workspace."
    )
    invitation.updated_at = utc_now()

    for intent in list(getattr(invitation, "intents", []) or []):
        if _clean_value(getattr(intent, "status", "")).lower() != INVITATION_INTENT_PENDING:
            continue
        intent.status = INVITATION_INTENT_REVOKED
        intent.revoked_at = utc_now()
        intent.updated_at = utc_now()


def _mark_invitation_expired(
    invitation: OrganizationInvitation,
) -> None:
    invitation.status = EXPIRED_STATUS
    invitation.token_hash = None
    invitation.updated_at = utc_now()


def _active_owner_count(
    db_session,
    *,
    organization_id: str,
) -> int:
    return (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.role == OWNER_ROLE,
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
        )
        .count()
    )


def _user_active_membership_count(
    db_session,
    *,
    user_id: int,
) -> int:
    return (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
        )
        .count()
    )


def _target_membership_with_user(
    db_session,
    *,
    organization_id: str,
    membership_id: int,
) -> tuple[OrganizationMembership, User]:
    result = (
        db_session.query(
            OrganizationMembership,
            User,
        )
        .join(
            User,
            User.id == OrganizationMembership.user_id,
        )
        .filter(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
        )
        .first()
    )

    if not result:
        raise PeopleGroupsError(
            "The selected group member was not found.",
            404,
        )

    return result


def _remove_membership(
    membership: OrganizationMembership,
) -> None:
    membership.status = REMOVED_STATUS
    membership.removed_at = utc_now()
    membership.is_primary = False
    membership.updated_at = utc_now()


def _activate_membership_from_invitation(
    db_session,
    *,
    invitation: OrganizationInvitation,
    user: User,
) -> OrganizationMembership:
    membership = _find_membership_for_user(
        db_session,
        organization_id=invitation.organization_id,
        user_id=user.id,
    )

    if (
        membership
        and membership.status == ACTIVE_STATUS
        and membership.removed_at is None
    ):
        # Admission is idempotent. Never demote an already-active owner/admin
        # merely because a stale workspace invitation carries the default
        # member role.
        return membership

    if membership:
        membership.role = MEMBER_ROLE
        membership.status = ACTIVE_STATUS
        membership.removed_at = None
        membership.invited_by_user_id = invitation.invited_by_user_id
        membership.joined_at = membership.joined_at or utc_now()
        membership.updated_at = utc_now()
        return membership

    membership = OrganizationMembership(
        organization_id=invitation.organization_id,
        user_id=user.id,
        role=MEMBER_ROLE,
        status=ACTIVE_STATUS,
        invited_by_user_id=invitation.invited_by_user_id,
        is_primary=(
            _user_active_membership_count(
                db_session,
                user_id=user.id,
            ) == 0
        ),
        joined_at=utc_now(),
    )
    db_session.add(
        membership
    )

    return membership





def _resolve_people_page_context() -> dict:
    """Resolve signed-in account context for the People workspace shell."""

    user_id = _current_user_id()

    if not user_id:
        return {
            "user_id": 0,
            "account_context": {},
        }

    account_context = resolve_account_context_for_user(
        user_id
    )

    if not isinstance(
        account_context,
        dict,
    ):
        account_context = {}

    return {
        "user_id": user_id,
        "account_context": account_context,
    }


def _require_organization_member() -> dict:
    """Resolve the active organization membership for the signed-in user."""

    user_id = _current_user_id()

    if not user_id:
        raise PeopleGroupsError(
            "Authentication required.",
            401,
        )

    account_context = resolve_account_context_for_user(
        user_id
    )

    if not isinstance(account_context, dict):
        account_context = {}

    organization = account_context.get("organization")
    membership = account_context.get("membership")

    if not isinstance(organization, dict) or not isinstance(membership, dict):
        account_context = ensure_initial_organization_membership_for_user(
            user_id
        )
        organization = account_context.get("organization")
        membership = account_context.get("membership")

    organization_id = _clean_value(
        organization.get("organization_id")
        if isinstance(organization, dict)
        else ""
    )
    membership_id = (
        membership.get("membership_id")
        if isinstance(membership, dict)
        else None
    )
    role = _clean_value(
        membership.get("role")
        if isinstance(membership, dict)
        else ""
    ).lower()

    if not organization_id or not membership_id:
        raise PeopleGroupsError(
            "Your Solomon access is not active.",
            403,
        )

    return {
        "user_id": user_id,
        "organization_id": organization_id,
        "membership_id": int(membership_id),
        "role": role or MEMBER_ROLE,
        "can_manage_people": role in MANAGE_GROUP_ROLES,
        "account_context": account_context,
    }


def _verify_organization_member(
    db_session,
    *,
    context: dict,
) -> tuple[Organization, OrganizationMembership]:
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
        raise PeopleGroupsError(
            "Your Solomon access is not active.",
            403,
        )

    return organization, membership


def _clean_group_name(value) -> str:
    name = _clean_value(value)

    if len(name) < 2:
        raise PeopleGroupsError(
            "Enter a group name.",
            400,
        )

    if len(name) > 255:
        raise PeopleGroupsError(
            "Group names cannot exceed 255 characters.",
            400,
        )

    return name


def _clean_group_description(value) -> str:
    description = _clean_value(value)

    if len(description) > 1024:
        raise PeopleGroupsError(
            "Group descriptions cannot exceed 1024 characters.",
            400,
        )

    return description


def _group_slug_base(name: str) -> str:
    slug = re.sub(
        r"[^a-z0-9]+",
        "-",
        name.lower(),
    ).strip("-")

    return (slug or "group")[:96]


def _unique_group_slug(
    db_session,
    *,
    organization_id: str,
    name: str,
) -> str:
    base = _group_slug_base(name)
    candidate = base
    suffix = 2

    while (
        db_session.query(OrganizationGroup.group_id)
        .filter(
            OrganizationGroup.organization_id == organization_id,
            OrganizationGroup.slug == candidate,
        )
        .first()
    ):
        candidate = f"{base[:88]}-{suffix}"
        suffix += 1

    return candidate


def _load_true_group(
    db_session,
    *,
    organization_id: str,
    group_id: str,
) -> OrganizationGroup:
    group = (
        db_session.query(OrganizationGroup)
        .filter(
            OrganizationGroup.group_id == _clean_value(group_id),
            OrganizationGroup.organization_id == organization_id,
            OrganizationGroup.status == ACTIVE_STATUS,
            OrganizationGroup.removed_at.is_(None),
        )
        .first()
    )

    if not group:
        raise PeopleGroupsError(
            "The selected group was not found.",
            404,
        )

    return group


def _active_true_group_membership(
    db_session,
    *,
    group_id: str,
    user_id: int,
) -> OrganizationGroupMembership | None:
    return (
        db_session.query(OrganizationGroupMembership)
        .filter(
            OrganizationGroupMembership.group_id == group_id,
            OrganizationGroupMembership.user_id == user_id,
            OrganizationGroupMembership.status == ACTIVE_STATUS,
            OrganizationGroupMembership.removed_at.is_(None),
        )
        .first()
    )


def _can_manage_true_group(
    db_session,
    *,
    context: dict,
    group: OrganizationGroup,
) -> tuple[bool, str]:
    membership = _active_true_group_membership(
        db_session,
        group_id=group.group_id,
        user_id=context["user_id"],
    )
    group_role = _clean_value(
        getattr(membership, "role", "")
    ).lower()

    if group_role in MANAGE_GROUP_ROLES:
        return True, group_role

    if context.get("can_manage_people"):
        return True, context.get("role") or ADMIN_ROLE

    return False, group_role


def _require_true_group_manager(
    db_session,
    *,
    context: dict,
    group_id: str,
) -> tuple[OrganizationGroup, str]:
    group = _load_true_group(
        db_session,
        organization_id=context["organization_id"],
        group_id=group_id,
    )
    can_manage, manager_role = _can_manage_true_group(
        db_session,
        context=context,
        group=group,
    )

    if not can_manage:
        raise PeopleGroupsError(
            "You do not have permission to manage this group.",
            403,
        )

    return group, manager_role


def _serialize_true_group_membership(
    membership: OrganizationGroupMembership,
    user: User,
    *,
    current_user_id: int,
    can_manage_group: bool,
    manager_role: str,
) -> dict:
    role = _clean_value(membership.role).lower() or MEMBER_ROLE
    is_self = int(membership.user_id) == int(current_user_id)

    # Owner is the only role that can appoint/demote Group admins. Admins can
    # add/remove ordinary members but cannot mutate admin authority.
    assignable_roles = []
    if (
        can_manage_group
        and manager_role == OWNER_ROLE
        and not is_self
        and role != OWNER_ROLE
    ):
        assignable_roles = [MEMBER_ROLE, ADMIN_ROLE]

    can_change_role = bool(
        assignable_roles
        and any(candidate != role for candidate in assignable_roles)
    )
    can_remove = bool(
        can_manage_group
        and not is_self
        and role != OWNER_ROLE
        and not (
            manager_role == ADMIN_ROLE
            and role == ADMIN_ROLE
        )
    )

    return {
        "membership_id": membership.id,
        "user_id": membership.user_id,
        "username": getattr(user, "username", ""),
        "email": getattr(user, "email", ""),
        "role": role,
        "status": membership.status,
        "joined_at": _safe_iso(membership.joined_at),
        "created_at": _safe_iso(membership.created_at),
        "is_self": is_self,
        "can_change_role": can_change_role,
        "can_remove": can_remove,
        "assignable_roles": assignable_roles,
    }



def _find_group_membership_invitation_intent(
    db_session,
    *,
    invitation_id: int,
    group_id: str,
) -> OrganizationInvitationIntent | None:
    return (
        db_session.query(OrganizationInvitationIntent)
        .filter(
            OrganizationInvitationIntent.invitation_id == invitation_id,
            OrganizationInvitationIntent.intent_type == INVITATION_INTENT_GROUP_MEMBERSHIP,
            OrganizationInvitationIntent.group_id == group_id,
            OrganizationInvitationIntent.status == INVITATION_INTENT_PENDING,
            OrganizationInvitationIntent.revoked_at.is_(None),
        )
        .order_by(OrganizationInvitationIntent.id.desc())
        .first()
    )


def _ensure_group_membership_invitation_intent(
    db_session,
    *,
    invitation: OrganizationInvitation,
    group: OrganizationGroup,
    group_role: str,
    created_by_user_id: int,
) -> tuple[OrganizationInvitationIntent, bool]:
    """Persist the specific Group action to complete after admission."""

    existing = _find_group_membership_invitation_intent(
        db_session,
        invitation_id=int(invitation.id),
        group_id=group.group_id,
    )
    normalized_role = _clean_value(group_role).lower()
    if normalized_role not in TRUE_GROUP_ASSIGNABLE_ROLES:
        normalized_role = MEMBER_ROLE

    if existing:
        existing.group_role = normalized_role
        existing.created_by_user_id = created_by_user_id
        existing.updated_at = utc_now()
        return existing, False

    intent = OrganizationInvitationIntent(
        invitation_id=int(invitation.id),
        organization_id=group.organization_id,
        intent_type=INVITATION_INTENT_GROUP_MEMBERSHIP,
        intent_contract=INVITATION_INTENT_CONTRACT,
        status=INVITATION_INTENT_PENDING,
        group_id=group.group_id,
        group_role=normalized_role,
        created_by_user_id=created_by_user_id,
    )
    db_session.add(intent)
    return intent, True


def _serialize_group_invitation_intents(
    db_session,
    *,
    group: OrganizationGroup,
) -> list[dict]:
    rows = (
        db_session.query(OrganizationInvitationIntent, OrganizationInvitation)
        .join(
            OrganizationInvitation,
            OrganizationInvitation.id == OrganizationInvitationIntent.invitation_id,
        )
        .filter(
            OrganizationInvitationIntent.organization_id == group.organization_id,
            OrganizationInvitationIntent.group_id == group.group_id,
            OrganizationInvitationIntent.intent_type == INVITATION_INTENT_GROUP_MEMBERSHIP,
            OrganizationInvitationIntent.status == INVITATION_INTENT_PENDING,
            OrganizationInvitationIntent.revoked_at.is_(None),
            OrganizationInvitation.status.in_({
                PENDING_STATUS,
                EXPIRED_STATUS,
            }),
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        .order_by(
            OrganizationInvitation.created_at.asc(),
            OrganizationInvitation.id.asc(),
        )
        .all()
    )

    serialized = []
    for intent, invitation in rows:
        serialized.append({
            "intent_id": intent.intent_id,
            "invitation_row_id": invitation.id,
            "invitation_id": invitation.invitation_id,
            "email": invitation.email,
            "normalized_email": invitation.normalized_email,
            "role": _clean_value(intent.group_role).lower() or MEMBER_ROLE,
            "status": (
                EXPIRED_STATUS
                if _invitation_is_expired(invitation)
                else PENDING_STATUS
            ),
            "expires_at": _safe_iso(invitation.expires_at),
        })

    return serialized


def _serialize_invitation_intents(
    invitation: OrganizationInvitation,
) -> list[dict]:
    serialized = []

    for intent in list(getattr(invitation, "intents", []) or []):
        group = getattr(intent, "group", None)
        serialized.append({
            "intent_id": getattr(intent, "intent_id", ""),
            "intent_type": _clean_value(getattr(intent, "intent_type", "")),
            "status": _clean_value(getattr(intent, "status", "")),
            "group_id": _clean_value(getattr(intent, "group_id", "")) or None,
            "group_name": _clean_value(getattr(group, "name", "")) or None,
            "group_role": _clean_value(getattr(intent, "group_role", "")) or None,
            "file_registry_id": getattr(intent, "file_registry_id", None),
            "completed_at": _safe_iso(getattr(intent, "completed_at", None)),
            "revoked_at": _safe_iso(getattr(intent, "revoked_at", None)),
        })

    return serialized


def _complete_invitation_intents(
    db_session,
    *,
    invitation: OrganizationInvitation,
    user: User,
) -> dict:
    """Atomically complete pending contextual actions after identity admission."""

    completed = []
    unavailable = []

    intents = (
        db_session.query(OrganizationInvitationIntent)
        .filter(
            OrganizationInvitationIntent.invitation_id == invitation.id,
            OrganizationInvitationIntent.organization_id == invitation.organization_id,
            OrganizationInvitationIntent.status == INVITATION_INTENT_PENDING,
            OrganizationInvitationIntent.revoked_at.is_(None),
        )
        .order_by(OrganizationInvitationIntent.id.asc())
        .all()
    )

    for intent in intents:
        if intent.intent_type != INVITATION_INTENT_GROUP_MEMBERSHIP:
            intent.status = INVITATION_INTENT_REVOKED
            intent.revoked_at = utc_now()
            intent.updated_at = utc_now()
            unavailable.append({
                "intent_type": intent.intent_type,
                "reason": "unsupported_intent",
            })
            continue

        group = (
            db_session.query(OrganizationGroup)
            .filter(
                OrganizationGroup.group_id == intent.group_id,
                OrganizationGroup.organization_id == invitation.organization_id,
                OrganizationGroup.status == ACTIVE_STATUS,
                OrganizationGroup.removed_at.is_(None),
            )
            .first()
        )
        if not group:
            intent.status = INVITATION_INTENT_REVOKED
            intent.revoked_at = utc_now()
            intent.updated_at = utc_now()
            unavailable.append({
                "intent_type": intent.intent_type,
                "group_id": intent.group_id,
                "reason": "group_unavailable",
            })
            continue

        requested_role = _clean_value(intent.group_role).lower()
        if requested_role not in TRUE_GROUP_ASSIGNABLE_ROLES:
            requested_role = MEMBER_ROLE

        group_membership = (
            db_session.query(OrganizationGroupMembership)
            .filter(
                OrganizationGroupMembership.group_id == group.group_id,
                OrganizationGroupMembership.user_id == user.id,
            )
            .first()
        )
        membership_changed = False

        if (
            group_membership
            and group_membership.status == ACTIVE_STATUS
            and group_membership.removed_at is None
        ):
            final_role = _clean_value(group_membership.role).lower() or MEMBER_ROLE
        elif group_membership:
            group_membership.role = requested_role
            group_membership.status = ACTIVE_STATUS
            group_membership.added_by_user_id = intent.created_by_user_id
            group_membership.joined_at = utc_now()
            group_membership.removed_at = None
            group_membership.updated_at = utc_now()
            final_role = requested_role
            membership_changed = True
        else:
            group_membership = OrganizationGroupMembership(
                group_id=group.group_id,
                user_id=user.id,
                role=requested_role,
                status=ACTIVE_STATUS,
                added_by_user_id=intent.created_by_user_id,
                joined_at=utc_now(),
            )
            db_session.add(group_membership)
            final_role = requested_role
            membership_changed = True

        db_session.flush()

        if membership_changed:
            _record_organization_audit_event(
                db_session,
                event_type=EVENT_GROUP_MEMBER_ADDED,
                organization_id=invitation.organization_id,
                actor_user_id=intent.created_by_user_id,
                target_user_id=user.id,
                target_email=getattr(user, "email", ""),
                role_after=final_role,
                decision="recorded",
                reason_code="group_member_added_from_invitation",
                details_json={
                    "group_id": group.group_id,
                    "group_name": group.name,
                    "invitation_id": invitation.invitation_id,
                    "intent_id": intent.intent_id,
                    "group_membership_id": group_membership.id,
                },
            )

        intent.status = INVITATION_INTENT_COMPLETED
        intent.completed_by_user_id = user.id
        intent.completed_at = utc_now()
        intent.updated_at = utc_now()

        _record_organization_audit_event(
            db_session,
            event_type=EVENT_INVITATION_INTENT_COMPLETED,
            organization_id=invitation.organization_id,
            actor_user_id=user.id,
            target_user_id=user.id,
            target_email=getattr(user, "email", ""),
            invitation_id=invitation.invitation_id,
            role_after=final_role,
            decision="recorded",
            reason_code="group_membership_intent_completed",
            details_json={
                "group_id": group.group_id,
                "group_name": group.name,
                "intent_id": intent.intent_id,
                "group_membership_id": group_membership.id,
                "membership_changed": membership_changed,
            },
        )
        completed.append({
            "intent_type": intent.intent_type,
            "group_id": group.group_id,
            "group_name": group.name,
            "role": final_role,
            "membership_changed": membership_changed,
        })

    return {
        "completed": completed,
        "unavailable": unavailable,
    }


def _serialize_true_group(
    db_session,
    *,
    group: OrganizationGroup,
    context: dict,
) -> dict:
    can_manage_group, manager_role = _can_manage_true_group(
        db_session,
        context=context,
        group=group,
    )
    rows = (
        db_session.query(OrganizationGroupMembership, User)
        .join(User, User.id == OrganizationGroupMembership.user_id)
        .filter(
            OrganizationGroupMembership.group_id == group.group_id,
            OrganizationGroupMembership.status == ACTIVE_STATUS,
            OrganizationGroupMembership.removed_at.is_(None),
            User.is_active.is_(True),
        )
        .order_by(
            OrganizationGroupMembership.created_at.asc(),
            User.email.asc(),
        )
        .all()
    )
    members = [
        _serialize_true_group_membership(
            membership,
            user,
            current_user_id=context["user_id"],
            can_manage_group=can_manage_group,
            manager_role=manager_role,
        )
        for membership, user in rows
    ]
    current_membership = next(
        (
            member
            for member in members
            if member.get("is_self")
        ),
        None,
    )
    pending_member_invitations = (
        _serialize_group_invitation_intents(
            db_session,
            group=group,
        )
        if can_manage_group
        else []
    )

    return {
        "group_id": group.group_id,
        "organization_id": group.organization_id,
        "name": group.name,
        "description": getattr(group, "description", None) or "",
        "slug": group.slug,
        "status": group.status,
        "created_at": _safe_iso(group.created_at),
        "updated_at": _safe_iso(group.updated_at),
        "member_count": len(members),
        "members": members,
        "pending_member_invitations": pending_member_invitations,
        "pending_member_count": len(pending_member_invitations),
        "current_membership": current_membership,
        "can_manage": can_manage_group,
        "can_edit": can_manage_group,
        "can_add_members": can_manage_group,
        "can_delete": bool(can_manage_group and manager_role == OWNER_ROLE),
        "manager_role": manager_role or "",
    }


def _list_true_groups(
    db_session,
    *,
    context: dict,
) -> list[dict]:
    query = (
        db_session.query(OrganizationGroup)
        .filter(
            OrganizationGroup.organization_id == context["organization_id"],
            OrganizationGroup.status == ACTIVE_STATUS,
            OrganizationGroup.removed_at.is_(None),
        )
    )

    if not context.get("can_manage_people"):
        query = (
            query.join(
                OrganizationGroupMembership,
                OrganizationGroupMembership.group_id == OrganizationGroup.group_id,
            )
            .filter(
                OrganizationGroupMembership.user_id == context["user_id"],
                OrganizationGroupMembership.status == ACTIVE_STATUS,
                OrganizationGroupMembership.removed_at.is_(None),
            )
        )

    groups = query.order_by(OrganizationGroup.name.asc()).all()

    return [
        _serialize_true_group(
            db_session,
            group=group,
            context=context,
        )
        for group in groups
    ]


def _list_people_directory(
    db_session,
    *,
    context: dict,
) -> list[dict]:
    rows = (
        db_session.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(
            OrganizationMembership.organization_id == context["organization_id"],
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
            User.is_active.is_(True),
        )
        .order_by(User.email.asc())
        .all()
    )
    group_rows = (
        db_session.query(
            OrganizationGroupMembership.user_id,
            OrganizationGroup.name,
        )
        .join(
            OrganizationGroup,
            OrganizationGroup.group_id == OrganizationGroupMembership.group_id,
        )
        .filter(
            OrganizationGroup.organization_id == context["organization_id"],
            OrganizationGroup.status == ACTIVE_STATUS,
            OrganizationGroup.removed_at.is_(None),
            OrganizationGroupMembership.status == ACTIVE_STATUS,
            OrganizationGroupMembership.removed_at.is_(None),
        )
        .all()
    )
    groups_by_user: dict[int, list[str]] = {}

    for user_id, group_name in group_rows:
        groups_by_user.setdefault(int(user_id), []).append(group_name)

    return [
        {
            "membership_id": membership.id,
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "status": membership.status,
            "joined_at": _safe_iso(membership.joined_at),
            "groups": sorted(groups_by_user.get(int(user.id), [])),
            "group_count": len(groups_by_user.get(int(user.id), [])),
            "is_self": int(user.id) == int(context["user_id"]),
        }
        for membership, user in rows
    ]


def _active_organization_user(
    db_session,
    *,
    organization_id: str,
    user_id: int,
) -> User:
    row = (
        db_session.query(User)
        .join(
            OrganizationMembership,
            OrganizationMembership.user_id == User.id,
        )
        .filter(
            User.id == int(user_id),
            User.is_active.is_(True),
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
        )
        .first()
    )

    if not row:
        raise PeopleGroupsError(
            "The selected person is not available in this Solomon workspace.",
            404,
        )

    return row


def _directory_payload(
    db_session,
    *,
    context: dict,
    organization: Organization,
    organization_membership: OrganizationMembership,
) -> dict:
    manager_role = _clean_value(organization_membership.role).lower()

    return {
        "ok": True,
        "organization": {
            "organization_id": organization.organization_id,
            "name": organization.name,
            "status": organization.status,
        },
        "current_user": {
            "user_id": context["user_id"],
            "role": manager_role or MEMBER_ROLE,
            "can_manage_people": bool(context.get("can_manage_people")),
            "can_create_group": bool(context.get("can_manage_people")),
        },
        "people": _list_people_directory(
            db_session,
            context=context,
        ),
        "groups": _list_true_groups(
            db_session,
            context=context,
        ),
        "roles": {
            "group_assignable": sorted(TRUE_GROUP_ASSIGNABLE_ROLES),
        },
    }


@people_bp.route(
    CANONICAL_PEOPLE_ROUTE,
    methods=["GET"],
)
@login_required
def people_page():
    page_context = _resolve_people_page_context()

    template_context = {
        "active_module": "people",
        "account_context": page_context["account_context"],
        "people_page_context": page_context,
    }

    if _is_workspace_partial_request():
        return render_template(
            "components/people_workspace.html",
            **template_context,
        )

    return render_template(
        "index.html",
        workspace_surface_template="components/people_workspace.html",
        **template_context,
    )


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/data",
    methods=["GET"],
)
@login_required
def people_data():
    try:
        context = _require_organization_member()
    except PeopleGroupsError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), exc.status_code

    db_session = SessionLocal()

    try:
        organization, organization_membership = _verify_organization_member(
            db_session,
            context=context,
        )
        return jsonify(
            _directory_payload(
                db_session,
                context=context,
                organization=organization,
                organization_membership=organization_membership,
            )
        ), 200
    except PeopleGroupsError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), exc.status_code
    except Exception:
        return jsonify({
            "ok": False,
            "error": "People and groups could not be loaded.",
        }), 500
    finally:
        db_session.close()


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/group-directory",
    methods=["POST"],
)
@login_required
def people_create_true_group():
    try:
        context = _require_organization_member()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    if not context.get("can_manage_people"):
        return jsonify({
            "ok": False,
            "error": "You do not have permission to create groups.",
        }), 403

    payload = request.get_json(silent=True) or {}
    db_session = SessionLocal()

    try:
        _organization, _membership = _verify_organization_member(
            db_session,
            context=context,
        )
        name = _clean_group_name(payload.get("name"))
        description = _clean_group_description(payload.get("description"))
        slug = _unique_group_slug(
            db_session,
            organization_id=context["organization_id"],
            name=name,
        )
        group = OrganizationGroup(
            organization_id=context["organization_id"],
            name=name,
            description=description or None,
            slug=slug,
            status=ACTIVE_STATUS,
            created_by_user_id=context["user_id"],
        )
        db_session.add(group)
        db_session.flush()
        owner_membership = OrganizationGroupMembership(
            group_id=group.group_id,
            user_id=context["user_id"],
            role=OWNER_ROLE,
            status=ACTIVE_STATUS,
            added_by_user_id=context["user_id"],
            joined_at=utc_now(),
        )
        db_session.add(owner_membership)
        _record_organization_audit_event(
            db_session,
            event_type=EVENT_GROUP_CREATED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            decision="recorded",
            reason_code="group_created",
            details_json={
                "group_id": group.group_id,
                "group_name": group.name,
            },
        )
        db_session.commit()
        db_session.refresh(group)

        return jsonify({
            "ok": True,
            "message": "Group created.",
            "group": _serialize_true_group(
                db_session,
                group=group,
                context=context,
            ),
        }), 201
    except PeopleGroupsError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The group could not be created.",
        }), 500
    finally:
        db_session.close()


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/group-directory/<group_id>",
    methods=["PATCH", "DELETE"],
)
@login_required
def people_update_true_group(group_id: str):
    try:
        context = _require_organization_member()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    db_session = SessionLocal()

    try:
        _organization, _membership = _verify_organization_member(
            db_session,
            context=context,
        )
        group, manager_role = _require_true_group_manager(
            db_session,
            context=context,
            group_id=group_id,
        )

        if request.method == "PATCH":
            payload = request.get_json(silent=True) or {}
            if "name" in payload:
                group.name = _clean_group_name(payload.get("name"))
            if "description" in payload:
                group.description = _clean_group_description(
                    payload.get("description")
                ) or None
            group.updated_at = utc_now()
            _record_organization_audit_event(
                db_session,
                event_type=EVENT_GROUP_UPDATED,
                organization_id=context["organization_id"],
                actor_user_id=context["user_id"],
                decision="recorded",
                reason_code="group_updated",
                details_json={
                    "group_id": group.group_id,
                    "group_name": group.name,
                },
            )
            db_session.commit()
            db_session.refresh(group)
            return jsonify({
                "ok": True,
                "message": "Group updated.",
                "group": _serialize_true_group(
                    db_session,
                    group=group,
                    context=context,
                ),
            }), 200

        if manager_role != OWNER_ROLE:
            raise PeopleGroupsError(
                "Only a Group owner can delete this group.",
                403,
            )

        now = utc_now()
        group.status = REMOVED_STATUS
        group.removed_at = now
        group.updated_at = now

        memberships = (
            db_session.query(OrganizationGroupMembership)
            .filter(
                OrganizationGroupMembership.group_id == group.group_id,
                OrganizationGroupMembership.status == ACTIVE_STATUS,
                OrganizationGroupMembership.removed_at.is_(None),
            )
            .all()
        )
        for membership in memberships:
            membership.status = REMOVED_STATUS
            membership.removed_at = now
            membership.updated_at = now

        grants = (
            db_session.query(FileGroupAccessGrant)
            .filter(
                FileGroupAccessGrant.group_id == group.group_id,
                FileGroupAccessGrant.status == ACTIVE_STATUS,
                FileGroupAccessGrant.revoked_at.is_(None),
            )
            .all()
        )
        for grant in grants:
            grant.status = REVOKED_STATUS
            grant.revoked_by_user_id = context["user_id"]
            grant.revoked_at = now
            grant.revocation_reason = "Group removed."
            grant.updated_at = now

        _record_organization_audit_event(
            db_session,
            event_type=EVENT_GROUP_REMOVED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            decision="recorded",
            reason_code="group_removed",
            details_json={
                "group_id": group.group_id,
                "group_name": group.name,
                "members_removed": len(memberships),
                "group_file_grants_revoked": len(grants),
            },
        )
        db_session.commit()

        return jsonify({
            "ok": True,
            "message": "Group deleted. Shared files were not deleted.",
            "group_id": group.group_id,
            "group_file_grants_revoked": len(grants),
        }), 200
    except PeopleGroupsError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The group could not be updated.",
        }), 500
    finally:
        db_session.close()


def _add_active_user_to_true_group(
    db_session,
    *,
    context: dict,
    group: OrganizationGroup,
    user: User,
    requested_role: str,
) -> tuple[OrganizationGroupMembership, bool]:
    membership = (
        db_session.query(OrganizationGroupMembership)
        .filter(
            OrganizationGroupMembership.group_id == group.group_id,
            OrganizationGroupMembership.user_id == user.id,
        )
        .first()
    )

    if (
        membership
        and membership.status == ACTIVE_STATUS
        and membership.removed_at is None
    ):
        return membership, False

    if membership:
        membership.role = requested_role
        membership.status = ACTIVE_STATUS
        membership.added_by_user_id = context["user_id"]
        membership.joined_at = utc_now()
        membership.removed_at = None
        membership.updated_at = utc_now()
    else:
        membership = OrganizationGroupMembership(
            group_id=group.group_id,
            user_id=user.id,
            role=requested_role,
            status=ACTIVE_STATUS,
            added_by_user_id=context["user_id"],
            joined_at=utc_now(),
        )
        db_session.add(membership)

    db_session.flush()

    _record_organization_audit_event(
        db_session,
        event_type=EVENT_GROUP_MEMBER_ADDED,
        organization_id=context["organization_id"],
        actor_user_id=context["user_id"],
        target_user_id=user.id,
        target_email=user.email,
        role_after=requested_role,
        decision="recorded",
        reason_code="group_member_added",
        details_json={
            "group_id": group.group_id,
            "group_name": group.name,
            "group_membership_id": membership.id,
        },
    )

    return membership, True


def _create_group_membership_invitation(
    db_session,
    *,
    context: dict,
    organization: Organization,
    group: OrganizationGroup,
    email: str,
    requested_role: str,
    manager_user: User | None,
) -> dict:
    normalized_email = _normalize_email(email)

    if (
        not normalized_email
        or "@" not in normalized_email
        or normalized_email.startswith("@")
        or normalized_email.endswith("@")
    ):
        raise PeopleGroupsError(
            "Enter a valid email address.",
            400,
        )

    existing_user = _find_user_by_normalized_email(
        db_session,
        normalized_email=normalized_email,
    )
    if existing_user:
        existing_membership = _find_membership_for_user(
            db_session,
            organization_id=context["organization_id"],
            user_id=existing_user.id,
        )
        if (
            existing_membership
            and existing_membership.status == ACTIVE_STATUS
            and existing_membership.removed_at is None
        ):
            _membership, was_added = _add_active_user_to_true_group(
                db_session,
                context=context,
                group=group,
                user=existing_user,
                requested_role=requested_role,
            )
            return {
                "mode": "added",
                "user_id": existing_user.id,
                "email": existing_user.email,
                "was_added": was_added,
            }

    invitation, token, was_refreshed = _create_or_refresh_invitation(
        db_session,
        organization_id=context["organization_id"],
        email=normalized_email,
        role=MEMBER_ROLE,
        invited_by_user_id=context["user_id"],
    )
    db_session.flush()

    intent, intent_created = _ensure_group_membership_invitation_intent(
        db_session,
        invitation=invitation,
        group=group,
        group_role=requested_role,
        created_by_user_id=context["user_id"],
    )
    db_session.flush()

    _record_organization_audit_event(
        db_session,
        event_type=(
            EVENT_INVITATION_REFRESHED
            if was_refreshed
            else EVENT_INVITATION_CREATED
        ),
        organization_id=context["organization_id"],
        actor_user_id=context["user_id"],
        target_email=invitation.normalized_email,
        invitation_id=invitation.invitation_id,
        role_after=MEMBER_ROLE,
        decision="recorded",
        reason_code=(
            "invitation_refreshed_for_group"
            if was_refreshed
            else "invitation_created_for_group"
        ),
        details_json={
            "group_id": group.group_id,
            "group_name": group.name,
            "intent_id": intent.intent_id,
            "intent_created": intent_created,
            "file_access_granted": False,
        },
    )
    if intent_created:
        _record_organization_audit_event(
            db_session,
            event_type=EVENT_INVITATION_INTENT_CREATED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_email=invitation.normalized_email,
            invitation_id=invitation.invitation_id,
            role_after=requested_role,
            decision="recorded",
            reason_code="group_membership_intent_created",
            details_json={
                "group_id": group.group_id,
                "group_name": group.name,
                "intent_id": intent.intent_id,
            },
        )

    db_session.commit()
    db_session.refresh(invitation)

    accept_url, absolute_accept_url, email_delivery = _send_workspace_invitation(
        organization=organization,
        invitation=invitation,
        token=token,
        invited_by_email=(
            getattr(manager_user, "email", "")
            or session.get("user_email")
            or ""
        ),
        was_refreshed=was_refreshed,
        target_group_name=group.name,
    )

    if email_delivery.get("enabled"):
        _record_organization_audit_event(
            db_session,
            event_type=(
                EVENT_INVITATION_EMAIL_SENT
                if email_delivery.get("sent")
                else EVENT_INVITATION_EMAIL_FAILED
            ),
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_email=invitation.normalized_email,
            invitation_id=invitation.invitation_id,
            role_after=requested_role,
            decision="sent" if email_delivery.get("sent") else "failed",
            reason_code=_clean_value(email_delivery.get("reason")) or "unknown_email_result",
            details_json={
                "group_id": group.group_id,
                "group_name": group.name,
                "provider": email_delivery.get("provider"),
                "attempted": email_delivery.get("attempted"),
                "sent": email_delivery.get("sent"),
                "reason": email_delivery.get("reason"),
                "missing_settings": email_delivery.get("missing_settings"),
            },
        )
        db_session.commit()

    if email_delivery.get("sent"):
        message = f"Invite sent to {invitation.email}."
    elif email_delivery.get("enabled"):
        message = (
            f"Invite ready for {invitation.email}. Email delivery failed; "
            "copy the link and send it directly."
        )
    else:
        message = (
            f"Invite ready for {invitation.email}. "
            "Copy the link and send it directly."
        )

    return {
        "mode": "invited",
        "email": invitation.email,
        "message": message,
        "invitation": _serialize_invitation(invitation),
        "intent": {
            "intent_id": intent.intent_id,
            "intent_type": intent.intent_type,
            "group_id": group.group_id,
            "group_name": group.name,
            "role": requested_role,
        },
        "accept_url": accept_url,
        "absolute_accept_url": absolute_accept_url,
        "email_delivery": email_delivery,
    }


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/group-directory/<group_id>/members",
    methods=["POST"],
)
@login_required
def people_add_true_group_members(group_id: str):
    try:
        context = _require_organization_member()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    payload = request.get_json(silent=True) or {}
    requested_ids = payload.get("user_ids")
    if not isinstance(requested_ids, list):
        requested_ids = [payload.get("user_id")]

    user_ids = []
    for value in requested_ids:
        try:
            user_id = int(value)
        except (TypeError, ValueError):
            continue
        if user_id > 0 and user_id not in user_ids:
            user_ids.append(user_id)

    email = _clean_value(
        payload.get("email")
    )
    requested_role = _clean_value(
        payload.get("role") or MEMBER_ROLE
    ).lower()
    if requested_role not in TRUE_GROUP_ASSIGNABLE_ROLES:
        return jsonify({
            "ok": False,
            "error": "Choose Member or Admin for new group members.",
        }), 400

    if not user_ids and not email:
        return jsonify({
            "ok": False,
            "error": "Select a person already in Solomon or enter an email address.",
        }), 400

    db_session = SessionLocal()

    try:
        organization, _membership = _verify_organization_member(
            db_session,
            context=context,
        )
        group, manager_role = _require_true_group_manager(
            db_session,
            context=context,
            group_id=group_id,
        )
        if manager_role == ADMIN_ROLE and requested_role == ADMIN_ROLE:
            raise PeopleGroupsError(
                "Group admins can add members, but cannot appoint another admin.",
                403,
            )

        manager_user = db_session.get(
            User,
            context["user_id"],
        )
        added_user_ids = []

        for user_id in user_ids:
            user = _active_organization_user(
                db_session,
                organization_id=context["organization_id"],
                user_id=user_id,
            )
            _group_membership, was_added = _add_active_user_to_true_group(
                db_session,
                context=context,
                group=group,
                user=user,
                requested_role=requested_role,
            )
            if was_added:
                added_user_ids.append(user.id)

        invitation_result = None
        if email:
            invitation_result = _create_group_membership_invitation(
                db_session,
                context=context,
                organization=organization,
                group=group,
                email=email,
                requested_role=requested_role,
                manager_user=manager_user,
            )

            if (
                invitation_result.get("mode") == "added"
                and invitation_result.get("was_added")
            ):
                invited_user_id = int(invitation_result.get("user_id") or 0)
                if invited_user_id and invited_user_id not in added_user_ids:
                    added_user_ids.append(invited_user_id)

        db_session.commit()

        if invitation_result and invitation_result.get("mode") == "invited":
            message = invitation_result.get("message") or "Invitation created."
        elif added_user_ids:
            count = len(added_user_ids)
            message = f"{count} member{'s' if count != 1 else ''} added."
        else:
            message = "Everyone selected is already in this group."

        return jsonify({
            "ok": True,
            "message": message,
            "added_user_ids": added_user_ids,
            "invitation": (
                invitation_result
                if invitation_result and invitation_result.get("mode") == "invited"
                else None
            ),
            "group": _serialize_true_group(
                db_session,
                group=group,
                context=context,
            ),
        }), 200
    except PeopleGroupsError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The selected people could not be added to the group.",
        }), 500
    finally:
        db_session.close()


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/group-directory/<group_id>/invitations/<int:invitation_row_id>/cancel",
    methods=["PATCH"],
)
@login_required
def people_cancel_true_group_invitation(
    group_id: str,
    invitation_row_id: int,
):
    """Cancel one pending contextual Group invitation without deleting the Group."""

    try:
        context = _require_organization_member()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    db_session = SessionLocal()

    try:
        _organization, _membership = _verify_organization_member(
            db_session,
            context=context,
        )
        group, _manager_role = _require_true_group_manager(
            db_session,
            context=context,
            group_id=group_id,
        )

        row = (
            db_session.query(
                OrganizationInvitationIntent,
                OrganizationInvitation,
            )
            .join(
                OrganizationInvitation,
                OrganizationInvitation.id
                == OrganizationInvitationIntent.invitation_id,
            )
            .filter(
                OrganizationInvitation.id == invitation_row_id,
                OrganizationInvitation.organization_id
                == context["organization_id"],
                OrganizationInvitation.accepted_at.is_(None),
                OrganizationInvitation.revoked_at.is_(None),
                OrganizationInvitationIntent.organization_id
                == context["organization_id"],
                OrganizationInvitationIntent.group_id == group.group_id,
                OrganizationInvitationIntent.intent_type
                == INVITATION_INTENT_GROUP_MEMBERSHIP,
                OrganizationInvitationIntent.status
                == INVITATION_INTENT_PENDING,
                OrganizationInvitationIntent.revoked_at.is_(None),
            )
            .first()
        )

        if not row:
            raise PeopleGroupsError(
                "The selected pending invitation was not found.",
                404,
            )

        intent, invitation = row
        now = utc_now()
        intent.status = INVITATION_INTENT_REVOKED
        intent.revoked_at = now
        intent.updated_at = now

        remaining_pending_intents = (
            db_session.query(OrganizationInvitationIntent.id)
            .filter(
                OrganizationInvitationIntent.invitation_id == invitation.id,
                OrganizationInvitationIntent.id != intent.id,
                OrganizationInvitationIntent.status
                == INVITATION_INTENT_PENDING,
                OrganizationInvitationIntent.revoked_at.is_(None),
            )
            .count()
        )

        if remaining_pending_intents == 0:
            _mark_invitation_revoked(
                invitation,
                revoked_by_user_id=context["user_id"],
                reason="Pending Group invitation cancelled.",
            )

        _record_organization_audit_event(
            db_session,
            event_type=EVENT_INVITATION_INTENT_REVOKED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_email=invitation.normalized_email,
            invitation_id=invitation.invitation_id,
            role_after=_clean_value(intent.group_role).lower() or MEMBER_ROLE,
            decision="recorded",
            reason_code="group_invitation_cancelled",
            details_json={
                "group_id": group.group_id,
                "group_name": group.name,
                "intent_id": intent.intent_id,
            },
        )

        db_session.commit()
        return jsonify({
            "ok": True,
            "message": "Invitation cancelled.",
            "group_id": group.group_id,
            "invitation_id": invitation.invitation_id,
            "intent_id": intent.intent_id,
        }), 200
    except PeopleGroupsError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The pending invitation could not be cancelled.",
        }), 500
    finally:
        db_session.close()


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/group-directory/<group_id>/members/<int:membership_id>/role",
    methods=["PATCH"],
)
@login_required
def people_update_true_group_member_role(group_id: str, membership_id: int):
    try:
        context = _require_organization_member()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    requested_role = _clean_value(
        (request.get_json(silent=True) or {}).get("role")
    ).lower()
    if requested_role not in TRUE_GROUP_ASSIGNABLE_ROLES:
        return jsonify({
            "ok": False,
            "error": "Choose Member or Admin.",
        }), 400

    db_session = SessionLocal()

    try:
        _organization, _membership = _verify_organization_member(
            db_session,
            context=context,
        )
        group, manager_role = _require_true_group_manager(
            db_session,
            context=context,
            group_id=group_id,
        )
        membership = (
            db_session.query(OrganizationGroupMembership)
            .filter(
                OrganizationGroupMembership.id == membership_id,
                OrganizationGroupMembership.group_id == group.group_id,
                OrganizationGroupMembership.status == ACTIVE_STATUS,
                OrganizationGroupMembership.removed_at.is_(None),
            )
            .first()
        )
        if not membership:
            raise PeopleGroupsError("The selected group member was not found.", 404)
        if int(membership.user_id) == int(context["user_id"]):
            raise PeopleGroupsError("You cannot change your own group role here.", 403)
        if _clean_value(membership.role).lower() == OWNER_ROLE:
            raise PeopleGroupsError("Owner authority cannot be changed here.", 403)
        if manager_role == ADMIN_ROLE:
            if _clean_value(membership.role).lower() == ADMIN_ROLE or requested_role == ADMIN_ROLE:
                raise PeopleGroupsError("Group admins cannot change admin authority.", 403)

        old_role = _clean_value(membership.role).lower()
        membership.role = requested_role
        membership.updated_at = utc_now()
        user = db_session.get(User, membership.user_id)
        _record_organization_audit_event(
            db_session,
            event_type=EVENT_ROLE_CHANGED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_user_id=membership.user_id,
            target_email=getattr(user, "email", ""),
            role_before=old_role,
            role_after=requested_role,
            decision="recorded",
            reason_code="group_role_changed",
            details_json={
                "group_id": group.group_id,
                "group_name": group.name,
                "group_membership_id": membership.id,
            },
        )
        db_session.commit()

        return jsonify({
            "ok": True,
            "message": "Group role updated.",
            "group": _serialize_true_group(
                db_session,
                group=group,
                context=context,
            ),
        }), 200
    except PeopleGroupsError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({"ok": False, "error": "The group role could not be updated."}), 500
    finally:
        db_session.close()


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/group-directory/<group_id>/members/<int:membership_id>",
    methods=["DELETE"],
)
@login_required
def people_remove_true_group_member(group_id: str, membership_id: int):
    try:
        context = _require_organization_member()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    db_session = SessionLocal()

    try:
        _organization, _membership = _verify_organization_member(
            db_session,
            context=context,
        )
        group, manager_role = _require_true_group_manager(
            db_session,
            context=context,
            group_id=group_id,
        )
        membership = (
            db_session.query(OrganizationGroupMembership)
            .filter(
                OrganizationGroupMembership.id == membership_id,
                OrganizationGroupMembership.group_id == group.group_id,
                OrganizationGroupMembership.status == ACTIVE_STATUS,
                OrganizationGroupMembership.removed_at.is_(None),
            )
            .first()
        )
        if not membership:
            raise PeopleGroupsError("The selected group member was not found.", 404)
        if int(membership.user_id) == int(context["user_id"]):
            raise PeopleGroupsError("You cannot remove yourself from this screen.", 403)
        role = _clean_value(membership.role).lower()
        if role == OWNER_ROLE:
            raise PeopleGroupsError("Group owners cannot be removed here.", 403)
        if manager_role == ADMIN_ROLE and role == ADMIN_ROLE:
            raise PeopleGroupsError("Group admins cannot remove another admin.", 403)

        membership.status = REMOVED_STATUS
        membership.removed_at = utc_now()
        membership.updated_at = utc_now()
        user = db_session.get(User, membership.user_id)
        _record_organization_audit_event(
            db_session,
            event_type=EVENT_MEMBER_REMOVED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_user_id=membership.user_id,
            target_email=getattr(user, "email", ""),
            role_before=role,
            decision="recorded",
            reason_code="group_member_removed",
            details_json={
                "group_id": group.group_id,
                "group_name": group.name,
                "group_membership_id": membership.id,
                "group_derived_access_revoked": True,
            },
        )
        db_session.commit()

        return jsonify({
            "ok": True,
            "message": "Member removed from group.",
            "group": _serialize_true_group(
                db_session,
                group=group,
                context=context,
            ),
        }), 200
    except PeopleGroupsError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({"ok": False, "error": "The member could not be removed from the group."}), 500
    finally:
        db_session.close()


def _require_people_manager() -> dict:
    context = _require_organization_member()
    if not context.get("can_manage_people"):
        raise PeopleGroupsError(
            "You do not have permission to manage workspace invitations.",
            403,
        )
    return context


def _refresh_invitation_token(
    invitation: OrganizationInvitation,
) -> str:
    token, token_hash = _new_invitation_token()
    invitation.role = MEMBER_ROLE
    invitation.token_hash = token_hash
    invitation.expires_at = utc_now() + timedelta(days=DEFAULT_INVITATION_DAYS)
    invitation.updated_at = utc_now()
    invitation.invitation_contract = INVITATION_CONTRACT
    return token


def _invitation_accept_urls(token: str) -> tuple[str, str]:
    accept_url = f"{CANONICAL_PEOPLE_ROUTE}/invitations/accept?token={token}"
    absolute_accept_url = build_people_invitation_accept_url(
        request_base_url=request.url_root,
        relative_accept_url=accept_url,
    )
    return accept_url, absolute_accept_url


def _send_workspace_invitation(
    *,
    organization: Organization,
    invitation: OrganizationInvitation,
    token: str,
    invited_by_email: str,
    was_refreshed: bool,
    target_group_name: str = "",
) -> tuple[str, str, dict]:
    accept_url, absolute_accept_url = _invitation_accept_urls(token)
    delivery = send_people_invitation_email(
        recipient_email=invitation.email,
        role=MEMBER_ROLE,
        group_name=getattr(organization, "name", ""),
        target_group_name=target_group_name,
        invited_by_email=invited_by_email,
        accept_url=absolute_accept_url,
        expires_at=invitation.expires_at,
        was_refreshed=was_refreshed,
    )
    return accept_url, absolute_accept_url, delivery


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/invitations",
    methods=["POST"],
)
@login_required
def people_create_workspace_invitation():
    try:
        context = _require_people_manager()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    payload = request.get_json(silent=True) or {}
    email = _clean_value(payload.get("email"))
    db_session = SessionLocal()

    try:
        organization, _manager_membership = _verify_organization_member(
            db_session,
            context=context,
        )
        manager_user = db_session.get(User, context["user_id"])
        invitation, token, was_refreshed = _create_or_refresh_invitation(
            db_session,
            organization_id=context["organization_id"],
            email=email,
            role=MEMBER_ROLE,
            invited_by_user_id=context["user_id"],
        )
        db_session.flush()

        _record_organization_audit_event(
            db_session,
            event_type=(
                EVENT_INVITATION_REFRESHED
                if was_refreshed
                else EVENT_INVITATION_CREATED
            ),
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_email=invitation.normalized_email,
            invitation_id=invitation.invitation_id,
            role_after=MEMBER_ROLE,
            decision="recorded",
            reason_code=(
                "invitation_refreshed"
                if was_refreshed
                else "invitation_created"
            ),
            details_json=_audit_details(
                email=invitation.email,
                normalized_email=invitation.normalized_email,
                expires_at=_safe_iso(invitation.expires_at),
                file_access_granted=False,
            ),
        )
        db_session.commit()
        db_session.refresh(invitation)

        accept_url, absolute_accept_url, email_delivery = _send_workspace_invitation(
            organization=organization,
            invitation=invitation,
            token=token,
            invited_by_email=(
                getattr(manager_user, "email", "")
                or session.get("user_email")
                or ""
            ),
            was_refreshed=was_refreshed,
        )

        if email_delivery.get("enabled"):
            _record_organization_audit_event(
                db_session,
                event_type=(
                    EVENT_INVITATION_EMAIL_SENT
                    if email_delivery.get("sent")
                    else EVENT_INVITATION_EMAIL_FAILED
                ),
                organization_id=context["organization_id"],
                actor_user_id=context["user_id"],
                target_email=invitation.normalized_email,
                invitation_id=invitation.invitation_id,
                role_after=MEMBER_ROLE,
                decision="sent" if email_delivery.get("sent") else "failed",
                reason_code=_clean_value(email_delivery.get("reason")) or "unknown_email_result",
                details_json=_audit_details(
                    provider=email_delivery.get("provider"),
                    attempted=email_delivery.get("attempted"),
                    sent=email_delivery.get("sent"),
                    reason=email_delivery.get("reason"),
                    missing_settings=email_delivery.get("missing_settings"),
                ),
            )
            db_session.commit()

        action_text = "refreshed" if was_refreshed else "created"
        if email_delivery.get("sent"):
            message = f"Invitation {action_text} and email sent."
        elif email_delivery.get("enabled"):
            message = (
                f"Invitation {action_text}. Email delivery failed; "
                "copy and send the link manually."
            )
        else:
            message = f"Invitation {action_text}."

        return jsonify({
            "ok": True,
            "message": message,
            "invitation": _serialize_invitation(invitation),
            "accept_url": accept_url,
            "absolute_accept_url": absolute_accept_url,
            "email_delivery": email_delivery,
            "file_access_granted": False,
        }), 200
    except PeopleGroupsError as exc:
        db_session.rollback()
        _record_failed_people_action(
            db_session,
            context,
            action="people.invitations.create",
            exc=exc,
            target_email=email,
            role_after=MEMBER_ROLE,
        )
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The workspace invitation could not be created.",
        }), 500
    finally:
        db_session.close()


# Compatibility bridge for older clients that still include the tenant id in
# the invitation path. The tenant id is validated but is not a user-visible
# Group identifier.
@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/groups/<group_id>/invitations",
    methods=["POST"],
)
@login_required
def people_create_group_invitation(group_id: str):
    try:
        context = _require_people_manager()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    if _clean_value(group_id) != _clean_value(context["organization_id"]):
        return jsonify({"ok": False, "error": "The requested workspace is not available."}), 403
    return people_create_workspace_invitation()


def _pending_invitation_for_manager(
    db_session,
    *,
    context: dict,
    invitation_row_id: int,
) -> OrganizationInvitation:
    invitation = (
        db_session.query(OrganizationInvitation)
        .filter(
            OrganizationInvitation.id == invitation_row_id,
            OrganizationInvitation.organization_id == context["organization_id"],
            OrganizationInvitation.status == PENDING_STATUS,
            OrganizationInvitation.accepted_at.is_(None),
            OrganizationInvitation.revoked_at.is_(None),
        )
        .first()
    )
    if not invitation:
        raise PeopleGroupsError(
            "The selected pending invitation was not found.",
            404,
        )
    # Expired pending invitations remain manageable: generating a new link or
    # resending rotates the token and extends expiry, while revoke can close
    # the stale invitation explicitly.
    return invitation


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/invitations/<int:invitation_row_id>/revoke",
    methods=["PATCH"],
)
@login_required
def people_revoke_workspace_invitation(invitation_row_id: int):
    try:
        context = _require_people_manager()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    payload = request.get_json(silent=True) or {}
    reason = _clean_value(payload.get("reason"))
    db_session = SessionLocal()
    try:
        _verify_organization_member(db_session, context=context)
        invitation = _pending_invitation_for_manager(
            db_session,
            context=context,
            invitation_row_id=invitation_row_id,
        )
        _mark_invitation_revoked(
            invitation,
            revoked_by_user_id=context["user_id"],
            reason=reason,
        )
        _record_organization_audit_event(
            db_session,
            event_type=EVENT_INVITATION_REVOKED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_email=invitation.normalized_email,
            invitation_id=invitation.invitation_id,
            role_after=MEMBER_ROLE,
            decision="recorded",
            reason_code="invitation_revoked",
            details_json=_audit_details(
                revocation_reason=invitation.revocation_reason,
            ),
        )
        db_session.commit()
        return jsonify({
            "ok": True,
            "message": "Invitation revoked.",
            "invitation_id": invitation.invitation_id,
        }), 200
    except PeopleGroupsError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({"ok": False, "error": "The invitation could not be revoked."}), 500
    finally:
        db_session.close()


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/invitations/<int:invitation_row_id>/link",
    methods=["POST"],
)
@login_required
def people_refresh_workspace_invitation_link(invitation_row_id: int):
    try:
        context = _require_people_manager()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    db_session = SessionLocal()
    try:
        _verify_organization_member(db_session, context=context)
        invitation = _pending_invitation_for_manager(
            db_session,
            context=context,
            invitation_row_id=invitation_row_id,
        )
        token = _refresh_invitation_token(invitation)
        _record_organization_audit_event(
            db_session,
            event_type=EVENT_INVITATION_REFRESHED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_email=invitation.normalized_email,
            invitation_id=invitation.invitation_id,
            role_after=MEMBER_ROLE,
            decision="recorded",
            reason_code="invitation_link_refreshed",
            details_json=_audit_details(expires_at=_safe_iso(invitation.expires_at)),
        )
        db_session.commit()
        accept_url, absolute_accept_url = _invitation_accept_urls(token)
        return jsonify({
            "ok": True,
            "message": "A new invitation link was generated. The previous link is no longer valid.",
            "invitation": _serialize_invitation(invitation),
            "accept_url": accept_url,
            "absolute_accept_url": absolute_accept_url,
        }), 200
    except PeopleGroupsError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({"ok": False, "error": "A new invitation link could not be generated."}), 500
    finally:
        db_session.close()


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/invitations/<int:invitation_row_id>/resend",
    methods=["POST"],
)
@login_required
def people_resend_workspace_invitation(invitation_row_id: int):
    try:
        context = _require_people_manager()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code

    db_session = SessionLocal()
    try:
        organization, _membership = _verify_organization_member(db_session, context=context)
        invitation = _pending_invitation_for_manager(
            db_session,
            context=context,
            invitation_row_id=invitation_row_id,
        )
        manager_user = db_session.get(User, context["user_id"])
        token = _refresh_invitation_token(invitation)
        _record_organization_audit_event(
            db_session,
            event_type=EVENT_INVITATION_REFRESHED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_email=invitation.normalized_email,
            invitation_id=invitation.invitation_id,
            role_after=MEMBER_ROLE,
            decision="recorded",
            reason_code="invitation_resent",
            details_json=_audit_details(expires_at=_safe_iso(invitation.expires_at)),
        )
        db_session.commit()
        accept_url, absolute_accept_url, email_delivery = _send_workspace_invitation(
            organization=organization,
            invitation=invitation,
            token=token,
            invited_by_email=getattr(manager_user, "email", "") or "",
            was_refreshed=True,
        )
        if email_delivery.get("enabled"):
            _record_organization_audit_event(
                db_session,
                event_type=(
                    EVENT_INVITATION_EMAIL_SENT
                    if email_delivery.get("sent")
                    else EVENT_INVITATION_EMAIL_FAILED
                ),
                organization_id=context["organization_id"],
                actor_user_id=context["user_id"],
                target_email=invitation.normalized_email,
                invitation_id=invitation.invitation_id,
                role_after=MEMBER_ROLE,
                decision="sent" if email_delivery.get("sent") else "failed",
                reason_code=_clean_value(email_delivery.get("reason")) or "unknown_email_result",
            )
            db_session.commit()
        message = (
            "Invitation email resent."
            if email_delivery.get("sent")
            else "Invitation refreshed. Copy the new link if email delivery is unavailable."
        )
        return jsonify({
            "ok": True,
            "message": message,
            "invitation": _serialize_invitation(invitation),
            "accept_url": accept_url,
            "absolute_accept_url": absolute_accept_url,
            "email_delivery": email_delivery,
        }), 200
    except PeopleGroupsError as exc:
        db_session.rollback()
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({"ok": False, "error": "The invitation could not be resent."}), 500
    finally:
        db_session.close()


# Legacy revoke path retained for compatibility with older browser assets.
@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/groups/<group_id>/invitations/<int:invitation_row_id>/revoke",
    methods=["PATCH"],
)
@login_required
def people_revoke_group_invitation(group_id: str, invitation_row_id: int):
    try:
        context = _require_people_manager()
    except PeopleGroupsError as exc:
        return jsonify({"ok": False, "error": str(exc)}), exc.status_code
    if _clean_value(group_id) != _clean_value(context["organization_id"]):
        return jsonify({"ok": False, "error": "The requested workspace is not available."}), 403
    return people_revoke_workspace_invitation(invitation_row_id)


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/groups/<group_id>/members/<int:membership_id>/role",
    methods=["PATCH"],
)
@login_required
def people_update_member_role(
    group_id: str,
    membership_id: int,
):
    try:
        context = _require_group_manager()
    except PeopleGroupsError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), exc.status_code

    payload = request.get_json(
        silent=True
    ) or {}
    requested_role = _clean_value(
        payload.get("role")
    ).lower()

    if _clean_value(group_id) != _clean_value(context["organization_id"]):
        return jsonify({
            "ok": False,
            "error": "The requested group does not match the active group.",
        }), 403

    db_session = SessionLocal()

    try:
        _organization, manager_membership = _verify_group_manager(
            db_session,
            user_id=context["user_id"],
            organization_id=context["organization_id"],
            membership_id=context["membership_id"],
        )

        manager_role = _clean_value(
            manager_membership.role
        ).lower()

        target_membership, target_user = _target_membership_with_user(
            db_session,
            organization_id=context["organization_id"],
            membership_id=membership_id,
        )

        if int(
            target_membership.user_id
        ) == int(
            context["user_id"]
        ):
            raise PeopleGroupsError(
                "You cannot change your own role from this screen.",
                403,
            )

        old_role = _clean_value(
            target_membership.role
        ).lower()

        new_role = _validate_membership_role_update(
            requested_role,
            manager_role=manager_role,
            target_role=target_membership.role,
        )

        target_membership.role = new_role
        target_membership.updated_at = utc_now()

        _record_organization_audit_event(
            db_session,
            event_type=EVENT_ROLE_CHANGED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_user_id=target_membership.user_id,
            target_email=getattr(
                target_user,
                "email",
                "",
            ),
            membership_id=target_membership.id,
            role_before=old_role,
            role_after=new_role,
            decision="recorded",
            reason_code="role_changed",
            details_json=_audit_details(
                manager_role=manager_role,
                file_access_granted=False,
            ),
        )

        db_session.commit()
        db_session.refresh(
            target_membership
        )

        return jsonify({
            "ok": True,
            "message": "Member role updated.",
            "membership": _serialize_membership(
                target_membership,
                target_user,
                manager_user_id=context["user_id"],
                manager_role=manager_role,
            ),
            "file_access_granted": False,
        }), 200

    except PeopleGroupsError as exc:
        db_session.rollback()
        _record_failed_people_action(
            db_session,
            context,
            action="people.groups.members.update_role",
            exc=exc,
            membership_id=membership_id,
            role_after=requested_role,
        )
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The member role could not be updated.",
        }), 500
    finally:
        db_session.close()


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/groups/<group_id>/members/<int:membership_id>",
    methods=["DELETE"],
)
@login_required
def people_remove_member(
    group_id: str,
    membership_id: int,
):
    try:
        context = _require_group_manager()
    except PeopleGroupsError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), exc.status_code

    if _clean_value(group_id) != _clean_value(context["organization_id"]):
        return jsonify({
            "ok": False,
            "error": "The requested group does not match the active group.",
        }), 403

    db_session = SessionLocal()

    try:
        _organization, manager_membership = _verify_group_manager(
            db_session,
            user_id=context["user_id"],
            organization_id=context["organization_id"],
            membership_id=context["membership_id"],
        )

        manager_role = _clean_value(
            manager_membership.role
        ).lower()

        target_membership, target_user = _target_membership_with_user(
            db_session,
            organization_id=context["organization_id"],
            membership_id=membership_id,
        )

        target_role = _clean_value(
            target_membership.role
        ).lower()

        if int(
            target_membership.user_id
        ) == int(
            context["user_id"]
        ):
            raise PeopleGroupsError(
                "You cannot remove yourself from this screen.",
                403,
            )

        if target_role == OWNER_ROLE:
            if _active_owner_count(
                db_session,
                organization_id=context["organization_id"],
            ) <= 1:
                raise PeopleGroupsError(
                    "The only owner cannot be removed.",
                    403,
                )

            raise PeopleGroupsError(
                "Owner removal requires an ownership-transfer workflow.",
                403,
            )

        if (
            manager_role == ADMIN_ROLE
            and target_role == ADMIN_ROLE
        ):
            raise PeopleGroupsError(
                "Admins cannot remove another admin.",
                403,
            )

        _remove_membership(
            target_membership
        )

        _record_organization_audit_event(
            db_session,
            event_type=EVENT_MEMBER_REMOVED,
            organization_id=context["organization_id"],
            actor_user_id=context["user_id"],
            target_user_id=target_membership.user_id,
            target_email=getattr(
                target_user,
                "email",
                "",
            ),
            membership_id=target_membership.id,
            role_before=target_role,
            decision="recorded",
            reason_code="member_removed",
            details_json=_audit_details(
                manager_role=manager_role,
                file_access_revoked=True,
            ),
        )

        db_session.commit()

        return jsonify({
            "ok": True,
            "message": "Member removed.",
            "membership_id": membership_id,
            "file_access_revoked": True,
        }), 200

    except PeopleGroupsError as exc:
        db_session.rollback()
        _record_failed_people_action(
            db_session,
            context,
            action="people.groups.members.remove",
            exc=exc,
            membership_id=membership_id,
        )
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), exc.status_code
    except Exception:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "The member could not be removed.",
        }), 500
    finally:
        db_session.close()


def _invitation_acceptance_payload(
    *,
    ok: bool,
    token: str,
    message: str = "",
    error: str = "",
    group: Organization | None = None,
    invitation: OrganizationInvitation | None = None,
    membership: OrganizationMembership | None = None,
    user: User | None = None,
    accepted: bool = False,
    file_access_granted: bool = False,
) -> dict:
    payload = {
        "ok": ok,
        "accepted": accepted,
        "token": token,
        "message": message,
        "error": error,
        "file_access_granted": file_access_granted,
    }

    if group:
        serialized_workspace = _serialize_group(
            group
        )
        payload["workspace"] = serialized_workspace
        payload["group"] = serialized_workspace

    if invitation:
        payload["invitation"] = _serialize_invitation(
            invitation
        )
        payload["intents"] = _serialize_invitation_intents(
            invitation
        )

    if membership and user:
        payload["membership"] = _serialize_membership(
            membership,
            user,
            manager_user_id=user.id,
            manager_role=membership.role,
        )

    if user:
        payload["current_user"] = {
            "user_id": user.id,
            "email": getattr(
                user,
                "email",
                "",
            ),
            "username": getattr(
                user,
                "username",
                "",
            ),
        }

    return payload


def _render_invitation_acceptance(
    payload: dict,
    status_code: int = 200,
):
    return render_template(
        "people_invitation_accept.html",
        invitation_acceptance=payload,
    ), status_code


def _should_return_json_acceptance() -> bool:
    if request.is_json:
        return True

    accept_header = _clean_value(
        request.headers.get("Accept")
    ).lower()

    return (
        "application/json" in accept_header
        and "text/html" not in accept_header
    )


def _token_from_acceptance_request() -> str:
    payload = request.get_json(
        silent=True
    ) or {}

    return _clean_value(
        payload.get("token")
        or request.form.get("token")
        or request.args.get("token")
    )


def _load_invitation_acceptance_record(
    db_session,
    *,
    token: str,
    user_id: int,
) -> tuple[Organization, OrganizationInvitation, User]:
    if not token:
        raise PeopleGroupsError(
            "Invitation token is required.",
            400,
        )

    user = db_session.get(
        User,
        user_id,
    )

    if not user:
        raise PeopleGroupsError(
            "User account was not found.",
            404,
        )

    invitation = _find_invitation_by_token(
        db_session,
        token=token,
    )

    if not invitation:
        raise PeopleGroupsError(
            "The invitation was not found or is no longer active.",
            404,
        )

    if _invitation_is_expired(
        invitation
    ):
        raise PeopleGroupsError(
            "The invitation has expired.",
            410,
        )

    organization = (
        db_session.query(Organization)
        .filter(
            Organization.organization_id == invitation.organization_id,
            Organization.status == ACTIVE_STATUS,
            Organization.suspended_at.is_(None),
        )
        .first()
    )

    if not organization:
        raise PeopleGroupsError(
            "The Solomon workspace for this invitation is not available.",
            404,
        )

    user_email = _normalize_email(
        getattr(
            user,
            "email",
            "",
        )
    )

    if user_email != invitation.normalized_email:
        raise PeopleGroupsError(
            "This invitation belongs to a different email address.",
            403,
        )

    return organization, invitation, user


@login_required
def people_legacy_accept_invitation():
    return _people_redirect(
        "accept"
    )


@people_bp.route(
    f"{CANONICAL_PEOPLE_ROUTE}/invitations/accept",
    methods=["GET", "POST"],
)
def people_accept_invitation():
    """Complete a contextual invitation as soon as the invited identity is known.

    The invitation link is the user's acceptance intent. Authentication or
    registration with the matching invited email proves identity, so there is
    no second confirmation step in the normal browser flow.
    """

    user_id = _current_user_id()
    token = _token_from_acceptance_request()

    # Public invitation links may be opened on a hostname that still carries
    # an older signed Solomon session cookie. A session user id is not enough
    # to prove that the corresponding account still exists in the current
    # server database. Fail back to the normal authentication branch instead
    # of turning a stale browser cookie into a dead invitation experience.
    if user_id:
        session_probe = SessionLocal()
        try:
            session_user = session_probe.get(
                User,
                user_id,
            )
            if not session_user or not getattr(
                session_user,
                "is_active",
                False,
            ):
                logger.warning(
                    "[people.invitation.stale_session_cleared] user_id=%s",
                    user_id,
                )
                session.clear()
                session.modified = True
                user_id = 0
        finally:
            session_probe.close()

    if not user_id:
        db_session = SessionLocal()
        try:
            if not token:
                raise PeopleGroupsError("Invitation token is required.", 400)
            invitation = _find_invitation_by_token(db_session, token=token)
            if not invitation:
                raise PeopleGroupsError(
                    "This invitation link is no longer active.",
                    404,
                )
            if _invitation_is_expired(invitation):
                raise PeopleGroupsError("This invitation link has expired.", 410)

            invited_user = _find_user_by_normalized_email(
                db_session,
                normalized_email=invitation.normalized_email,
            )
            accept_target = (
                f"{CANONICAL_PEOPLE_ROUTE}/invitations/accept?token={token}"
            )
            endpoint = "auth.login_page" if invited_user else "auth.register_page"
            return redirect(
                url_for(endpoint, next=accept_target),
                code=302,
            )
        except PeopleGroupsError as exc:
            payload = _invitation_acceptance_payload(
                ok=False,
                token=token,
                error=str(exc),
            )
            if _should_return_json_acceptance():
                return jsonify(payload), exc.status_code
            return _render_invitation_acceptance(payload, exc.status_code)
        finally:
            db_session.close()

    db_session = SessionLocal()

    try:
        organization, invitation, user = _load_invitation_acceptance_record(
            db_session,
            token=token,
            user_id=user_id,
        )

        membership = _activate_membership_from_invitation(
            db_session,
            invitation=invitation,
            user=user,
        )
        db_session.flush()

        intent_result = _complete_invitation_intents(
            db_session,
            invitation=invitation,
            user=user,
        )
        db_session.flush()

        invitation.status = ACCEPTED_STATUS
        invitation.token_hash = None
        invitation.membership_id = membership.id
        invitation.accepted_by_user_id = user.id
        invitation.accepted_at = utc_now()
        invitation.updated_at = utc_now()

        _record_organization_audit_event(
            db_session,
            event_type=EVENT_MEMBERSHIP_ACTIVATED,
            organization_id=invitation.organization_id,
            actor_user_id=user.id,
            target_user_id=user.id,
            target_email=getattr(
                user,
                "email",
                "",
            ),
            invitation_id=invitation.invitation_id,
            membership_id=membership.id,
            role_after=membership.role,
            decision="recorded",
            reason_code="membership_activated_from_invitation",
            details_json=_audit_details(
                invited_by_user_id=invitation.invited_by_user_id,
                file_access_granted=False,
                completed_intents=intent_result.get("completed"),
                unavailable_intents=intent_result.get("unavailable"),
            ),
        )

        _record_organization_audit_event(
            db_session,
            event_type=EVENT_INVITATION_ACCEPTED,
            organization_id=invitation.organization_id,
            actor_user_id=user.id,
            target_user_id=user.id,
            target_email=getattr(
                user,
                "email",
                "",
            ),
            invitation_id=invitation.invitation_id,
            membership_id=membership.id,
            role_after=membership.role,
            decision="recorded",
            reason_code="invitation_accepted",
            details_json=_audit_details(
                invited_by_user_id=invitation.invited_by_user_id,
                file_access_granted=False,
                completed_intents=intent_result.get("completed"),
                unavailable_intents=intent_result.get("unavailable"),
            ),
        )

        # Serialize the accepted invitation while its ORM graph is still
        # attached to this request's database session. SQLAlchemy expires
        # relationship state on commit; serializing invitation.intents after
        # that boundary can trigger a detached lazy-load during the public
        # invitation redirect flow.
        completed_groups = [
            item
            for item in intent_result.get("completed", [])
            if item.get("group_id")
        ]
        completed_group_names = [
            item.get("group_name")
            for item in completed_groups
            if item.get("group_name")
        ]
        accepted_message = (
            f"Joined {completed_group_names[0]}."
            if len(completed_group_names) == 1
            else (
                "Your groups are ready."
                if completed_group_names
                else "You're ready to use Solomon."
            )
        )

        payload = _invitation_acceptance_payload(
            ok=True,
            token=token,
            message=accepted_message,
            group=organization,
            invitation=invitation,
            membership=membership,
            user=user,
            accepted=True,
            file_access_granted=False,
        )
        payload["completed_intents"] = intent_result.get("completed", [])
        payload["unavailable_intents"] = intent_result.get("unavailable", [])

        db_session.commit()
        db_session.refresh(membership)

        refreshed_account_context = resolve_account_context_for_user(user.id)
        session["account_context"] = refreshed_account_context
        if isinstance(session.get("user"), dict):
            session["user"]["group_id"] = (
                (refreshed_account_context.get("group") or {}).get("group_id")
                or ""
            )
        session.modified = True

        if _should_return_json_acceptance():
            return jsonify(payload), 200

        if completed_groups:
            return redirect(
                url_for(
                    "people_bp.people_page",
                    view="groups",
                    group=completed_groups[0]["group_id"],
                    joined="1",
                ),
                code=303,
            )

        return redirect(
            url_for("people_bp.people_page"),
            code=303,
        )

    except PeopleGroupsError as exc:
        if (
            exc.status_code == 410
            and "expired" in str(exc).lower()
        ):
            invitation = _find_invitation_by_token(
                db_session,
                token=token,
            )

            if invitation:
                _mark_invitation_expired(
                    invitation
                )
                _record_organization_audit_event(
                    db_session,
                    event_type=EVENT_INVITATION_EXPIRED,
                    organization_id=invitation.organization_id,
                    target_email=invitation.normalized_email,
                    invitation_id=invitation.invitation_id,
                    role_after=invitation.role,
                    decision="expired",
                    reason_code="invitation_expired",
                    details_json=_audit_details(
                        expires_at=_safe_iso(
                            invitation.expires_at
                        ),
                    ),
                )
                db_session.commit()
            else:
                db_session.rollback()
        else:
            db_session.rollback()

            try:
                denied_invitation = _find_invitation_by_token(
                    db_session,
                    token=token,
                )
                if denied_invitation:
                    _record_organization_audit_event(
                        db_session,
                        event_type=EVENT_PRIVILEGED_ACTION_DENIED,
                        organization_id=denied_invitation.organization_id,
                        actor_user_id=user_id,
                        target_email=denied_invitation.normalized_email,
                        invitation_id=denied_invitation.invitation_id,
                        role_after=denied_invitation.role,
                        decision="denied",
                        reason_code=f"http_{exc.status_code}",
                        details_json=_audit_details(
                            action="people.invitations.accept",
                            error=str(exc),
                            status_code=exc.status_code,
                        ),
                    )
                    db_session.commit()
            except Exception:
                db_session.rollback()

        payload = _invitation_acceptance_payload(
            ok=False,
            token=token,
            error=str(exc),
        )

        if _should_return_json_acceptance():
            return jsonify(payload), exc.status_code

        return _render_invitation_acceptance(
            payload,
            exc.status_code,
        )

    except Exception:
        db_session.rollback()
        logger.exception(
            "[people.invitation.accept_failed] user_id=%s",
            user_id,
        )

        payload = _invitation_acceptance_payload(
            ok=False,
            token=token,
            error="This invitation could not be completed.",
        )

        if _should_return_json_acceptance():
            return jsonify(payload), 500

        return _render_invitation_acceptance(
            payload,
            500,
        )

    finally:
        db_session.close()


__all__ = [
    "people_bp",
]