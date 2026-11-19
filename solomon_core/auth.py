# -------------------------------------------------------------------
# FILE: auth.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# Session-based authentication for Nations Systems.
# Users authenticate with email only.
# Legacy username values are generated internally for database compatibility.
# -------------------------------------------------------------------

from datetime import datetime, timedelta, timezone
import base64
import hashlib
import ipaddress
import logging
import re
import secrets
import time
import uuid
from urllib.parse import parse_qs, urlencode, urlparse

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from werkzeug.security import check_password_hash, generate_password_hash

from config import settings
from solomon_core.db import SessionLocal
from solomon_core.external_authentication import (
    ExternalAuthenticationError,
    ExternalIdentityResult,
    build_authorization_url,
    exchange_authorization_code,
    provider_is_enabled,
)
from solomon_core.models import (
    ExternalIdentity,
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    User,
    utc_now,
)


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
logger = logging.getLogger("Solomon.auth")


ACTIVE_STATUS = "active"
SUBDOMAIN_ROOT = "nationssystems.com"
INITIAL_ORGANIZATION_NAME = "Solomon Workspace"
INITIAL_ORGANIZATION_SLUG_PREFIX = "solomon-workspace"
OWNER_ROLE = "owner"
PASSWORD_AUTHENTICATION_METHOD = "password"
GOOGLE_AUTHENTICATION_PROVIDER = "google"
MICROSOFT_AUTHENTICATION_PROVIDER = "microsoft"
EXTERNAL_AUTH_TRANSACTION_SESSION_KEY = "external_auth_transactions"
EXTERNAL_AUTH_NOTICE_SESSION_KEY = "external_auth_notice"
PENDING_EXTERNAL_IDENTITY_SESSION_KEY = "pending_external_identity"


# ---------------------------------------------------
# Utility helpers
# ---------------------------------------------------
def _clean_value(value) -> str:
    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip()


def _normalize_email(email: str) -> str:
    if not isinstance(email, str):
        return ""

    return email.strip().lower()


def validate_email(email: str) -> bool:
    normalized = _normalize_email(email)
    return re.match(r"^[^@\s]+@[^@\s]+\.[a-zA-Z0-9]+$", normalized) is not None


def _safe_redirect_target(value) -> str:
    """
    Return a safe same-site redirect path.

    Public auth routes may receive `next` from query strings or JSON payloads.
    Only root-relative paths are accepted. Full URLs, protocol-relative URLs,
    auth escape routes, and static assets are rejected.
    """

    clean_value = str(
        value or ""
    ).strip()

    if not clean_value:
        return ""

    if not clean_value.startswith("/"):
        return ""

    if clean_value.startswith("//"):
        return ""

    parsed = urlparse(
        clean_value
    )

    if parsed.scheme or parsed.netloc:
        return ""

    path = parsed.path or "/"

    blocked_prefixes = (
        "/auth/logout",
        "/static/",
    )

    if any(
        path.startswith(prefix)
        for prefix in blocked_prefixes
    ):
        return ""

    return clean_value


def _is_invitation_redirect(value: str) -> bool:
    redirect_target = _safe_redirect_target(
        value
    )

    return redirect_target.startswith(
        "/people/invitations/accept"
    )


def _invitation_token_from_redirect(value: str) -> str:
    redirect_target = _safe_redirect_target(value)
    if not _is_invitation_redirect(redirect_target):
        return ""

    parsed = urlparse(redirect_target)
    values = parse_qs(parsed.query or "")
    token_values = values.get("token") or []
    return _clean_value(token_values[0] if token_values else "")


def _invitation_email_for_redirect(value: str) -> str:
    token = _invitation_token_from_redirect(value)
    if not token:
        return ""

    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db = SessionLocal()
    try:
        invitation = (
            db.query(OrganizationInvitation)
            .filter(
                OrganizationInvitation.token_hash == token_hash,
                OrganizationInvitation.status == "pending",
                OrganizationInvitation.accepted_at.is_(None),
                OrganizationInvitation.revoked_at.is_(None),
            )
            .first()
        )
        if not invitation:
            return ""

        expires_at = getattr(invitation, "expires_at", None)
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            else:
                expires_at = expires_at.astimezone(timezone.utc)
            if expires_at <= datetime.now(timezone.utc):
                return ""

        return _normalize_email(invitation.normalized_email or invitation.email)
    finally:
        db.close()


def _store_post_login_redirect(value) -> str:
    redirect_target = _safe_redirect_target(
        value
    )

    if redirect_target:
        session[
            "post_login_redirect"
        ] = redirect_target
        session.modified = True

    return redirect_target


def _requested_post_login_redirect(
    payload: dict | None = None,
) -> str:
    payload = (
        payload
        if isinstance(
            payload,
            dict,
        )
        else {}
    )

    redirect_target = (
        _safe_redirect_target(
            payload.get("next")
        )
        or _safe_redirect_target(
            payload.get("redirect")
        )
        or _safe_redirect_target(
            request.args.get("next")
        )
        or _safe_redirect_target(
            session.get("post_login_redirect")
        )
    )

    if redirect_target:
        _store_post_login_redirect(
            redirect_target
        )

    return redirect_target


def _consume_post_login_redirect(
    *,
    payload: dict | None = None,
    default_url: str = "/",
) -> str:
    redirect_target = _requested_post_login_redirect(
        payload
    )

    if redirect_target:
        session.pop(
            "post_login_redirect",
            None,
        )
        session.modified = True
        return redirect_target

    return default_url


def _external_authentication_context(
    redirect_target: str = "",
) -> dict:
    """Describe configured external identity providers for auth-page rendering.

    Provider availability is server-authoritative. Templates may present these
    controls, but they never infer whether a provider is usable from browser
    state. Google and Microsoft authenticate one Solomon person; they do not
    grant Organization, Group, file, role, or permission authority.
    """

    safe_target = _safe_redirect_target(redirect_target)

    google_enabled = bool(
        settings.GOOGLE_OIDC_ENABLED
        and _clean_value(settings.GOOGLE_OIDC_CLIENT_ID)
        and _clean_value(settings.GOOGLE_OIDC_CLIENT_SECRET)
        and _clean_value(settings.GOOGLE_OIDC_DISCOVERY_URL)
    )
    microsoft_enabled = bool(
        settings.MICROSOFT_OIDC_ENABLED
        and _clean_value(settings.MICROSOFT_OIDC_CLIENT_ID)
        and _clean_value(settings.MICROSOFT_OIDC_CLIENT_SECRET)
        and _clean_value(settings.MICROSOFT_OIDC_DISCOVERY_URL)
    )

    def _provider_start_url(provider: str, enabled: bool) -> str:
        if not enabled:
            return ""

        public_base_url = _clean_value(
            settings.PUBLIC_APPLICATION_BASE_URL
        ).rstrip("/")
        start_url = (
            f"{public_base_url}/auth/external/"
            f"{provider}/start"
        )

        if safe_target:
            return (
                start_url
                + "?"
                + urlencode({"next": safe_target})
            )

        return start_url

    return {
        "google": {
            "enabled": google_enabled,
            "label": "Continue with Google",
            "start_url": _provider_start_url(
                GOOGLE_AUTHENTICATION_PROVIDER,
                google_enabled,
            ),
        },
        "microsoft": {
            "enabled": microsoft_enabled,
            "label": "Continue with Microsoft",
            "start_url": _provider_start_url(
                MICROSOFT_AUTHENTICATION_PROVIDER,
                microsoft_enabled,
            ),
        },
    }



def _external_provider_label(provider: str) -> str:
    clean_provider = _clean_value(provider).lower()
    if clean_provider == GOOGLE_AUTHENTICATION_PROVIDER:
        return "Google"
    if clean_provider == MICROSOFT_AUTHENTICATION_PROVIDER:
        return "Microsoft"
    return "External provider"


def _external_callback_url(provider: str) -> str:
    clean_provider = _clean_value(provider).lower()
    public_base_url = _clean_value(
        settings.PUBLIC_APPLICATION_BASE_URL
    ).rstrip("/")
    return (
        f"{public_base_url}/auth/external/"
        f"{clean_provider}/callback"
    )


def _base64url_sha256(value: str) -> str:
    digest = hashlib.sha256(
        str(value or "").encode("ascii")
    ).digest()
    return base64.urlsafe_b64encode(
        digest
    ).decode("ascii").rstrip("=")


def _prune_external_auth_transactions() -> dict:
    raw_transactions = session.get(
        EXTERNAL_AUTH_TRANSACTION_SESSION_KEY
    )
    transactions = (
        dict(raw_transactions)
        if isinstance(raw_transactions, dict)
        else {}
    )
    now = time.time()
    cleaned: dict[str, dict] = {}

    for state, transaction in transactions.items():
        if not isinstance(transaction, dict):
            continue

        try:
            expires_at = float(
                transaction.get("expires_at") or 0
            )
        except (TypeError, ValueError):
            continue

        if expires_at <= now:
            continue

        cleaned[str(state)] = dict(transaction)

    max_transactions = max(
        1,
        int(settings.OIDC_MAX_PENDING_TRANSACTIONS),
    )
    if len(cleaned) > max_transactions:
        sorted_items = sorted(
            cleaned.items(),
            key=lambda item: float(
                item[1].get("created_at") or 0
            ),
            reverse=True,
        )[:max_transactions]
        cleaned = dict(sorted_items)

    session[
        EXTERNAL_AUTH_TRANSACTION_SESSION_KEY
    ] = cleaned
    session.modified = True
    return cleaned


def _create_external_auth_transaction(
    *,
    provider: str,
    redirect_target: str,
) -> dict:
    clean_provider = _clean_value(provider).lower()
    now = time.time()
    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    code_verifier = secrets.token_urlsafe(64)

    transaction = {
        "provider": clean_provider,
        "redirect_target": _safe_redirect_target(
            redirect_target
        ),
        "nonce": nonce,
        "code_verifier": code_verifier,
        "created_at": now,
        "expires_at": (
            now
            + float(settings.OIDC_TRANSACTION_TTL_SECONDS)
        ),
    }

    transactions = _prune_external_auth_transactions()
    transactions[state] = transaction
    session[
        EXTERNAL_AUTH_TRANSACTION_SESSION_KEY
    ] = transactions
    session.modified = True

    return {
        "state": state,
        "nonce": nonce,
        "code_verifier": code_verifier,
        "code_challenge": _base64url_sha256(
            code_verifier
        ),
        "redirect_target": transaction[
            "redirect_target"
        ],
    }


def _consume_external_auth_transaction(
    *,
    provider: str,
    state: str,
) -> dict | None:
    clean_provider = _clean_value(provider).lower()
    clean_state = _clean_value(state)
    if not clean_state:
        return None

    transactions = _prune_external_auth_transactions()
    transaction = transactions.pop(
        clean_state,
        None,
    )
    session[
        EXTERNAL_AUTH_TRANSACTION_SESSION_KEY
    ] = transactions
    session.modified = True

    if not isinstance(transaction, dict):
        return None

    if _clean_value(
        transaction.get("provider")
    ).lower() != clean_provider:
        return None

    return transaction


def _set_external_auth_notice(message: str) -> None:
    clean_message = _clean_value(message)
    if clean_message:
        session[
            EXTERNAL_AUTH_NOTICE_SESSION_KEY
        ] = clean_message
        session.modified = True


def _consume_external_auth_notice() -> str:
    notice = _clean_value(
        session.pop(
            EXTERNAL_AUTH_NOTICE_SESSION_KEY,
            "",
        )
    )
    if notice:
        session.modified = True
    return notice


def _pending_external_identity() -> dict | None:
    pending = session.get(
        PENDING_EXTERNAL_IDENTITY_SESSION_KEY
    )
    if not isinstance(pending, dict):
        return None

    try:
        expires_at = float(
            pending.get("expires_at") or 0
        )
    except (TypeError, ValueError):
        expires_at = 0

    if expires_at <= time.time():
        session.pop(
            PENDING_EXTERNAL_IDENTITY_SESSION_KEY,
            None,
        )
        session.modified = True
        return None

    return dict(pending)


def _store_pending_external_identity(
    identity: ExternalIdentityResult,
) -> None:
    now = time.time()
    session[
        PENDING_EXTERNAL_IDENTITY_SESSION_KEY
    ] = {
        "provider": identity.provider,
        "issuer": identity.issuer,
        "provider_subject": identity.provider_subject,
        "provider_email": identity.provider_email,
        "normalized_email": identity.normalized_email,
        "email_verified": bool(
            identity.email_verified
        ),
        "tenant_id": identity.tenant_id,
        "created_at": now,
        "expires_at": (
            now
            + float(settings.OIDC_TRANSACTION_TTL_SECONDS)
        ),
    }
    session.modified = True


def _apply_external_identity_values(
    external_identity: ExternalIdentity,
    *,
    provider: str,
    issuer: str,
    provider_subject: str,
    provider_email: str,
    normalized_email: str,
    email_verified: bool,
    tenant_id: str,
) -> None:
    external_identity.provider = _clean_value(
        provider
    ).lower()
    external_identity.issuer = _clean_value(
        issuer
    )
    external_identity.provider_subject = _clean_value(
        provider_subject
    )
    external_identity.provider_email = _normalize_email(
        provider_email
    ) or None
    external_identity.normalized_email = _normalize_email(
        normalized_email
    ) or None
    external_identity.email_verified = bool(
        email_verified
    )
    external_identity.tenant_id = _clean_value(
        tenant_id
    ) or None
    external_identity.last_authenticated_at = utc_now()


def _attach_pending_external_identity(
    db,
    *,
    user: User,
) -> str:
    pending = _pending_external_identity()
    if not pending or not user:
        return ""

    normalized_email = _normalize_email(
        pending.get("normalized_email")
    )
    if (
        not normalized_email
        or normalized_email
        != _normalize_email(user.email)
    ):
        return ""

    provider = _clean_value(
        pending.get("provider")
    ).lower()
    issuer = _clean_value(
        pending.get("issuer")
    )
    provider_subject = _clean_value(
        pending.get("provider_subject")
    )

    if (
        provider not in {
            GOOGLE_AUTHENTICATION_PROVIDER,
            MICROSOFT_AUTHENTICATION_PROVIDER,
        }
        or not issuer
        or not provider_subject
    ):
        return ""

    tuple_identity = (
        db.query(ExternalIdentity)
        .filter(
            ExternalIdentity.provider == provider,
            ExternalIdentity.issuer == issuer,
            ExternalIdentity.provider_subject
            == provider_subject,
        )
        .first()
    )

    if tuple_identity and tuple_identity.user_id != user.id:
        return ""

    provider_identity = (
        db.query(ExternalIdentity)
        .filter(
            ExternalIdentity.user_id == user.id,
            ExternalIdentity.provider == provider,
        )
        .first()
    )

    if (
        provider_identity
        and provider_identity.provider_subject
        != provider_subject
    ):
        return ""

    external_identity = (
        tuple_identity
        or provider_identity
        or ExternalIdentity(
            user_id=user.id,
            provider=provider,
            issuer=issuer,
            provider_subject=provider_subject,
        )
    )

    if external_identity.id is None:
        db.add(external_identity)

    _apply_external_identity_values(
        external_identity,
        provider=provider,
        issuer=issuer,
        provider_subject=provider_subject,
        provider_email=pending.get(
            "provider_email"
        ),
        normalized_email=normalized_email,
        email_verified=bool(
            pending.get("email_verified")
        ),
        tenant_id=pending.get("tenant_id"),
    )
    db.flush()

    return _external_provider_label(provider)


def _provider_can_prove_invitation_email(
    identity: ExternalIdentityResult,
) -> bool:
    if identity.provider == GOOGLE_AUTHENTICATION_PROVIDER:
        return bool(
            identity.email_verified
            and identity.authoritative_email
        )

    if identity.provider == MICROSOFT_AUTHENTICATION_PROVIDER:
        return bool(
            identity.authoritative_email
            and identity.tenant_id
        )

    return False


def _external_identity_can_auto_link_password_user(
    identity: ExternalIdentityResult,
    *,
    user: User,
) -> bool:
    """Allow one-time provider bootstrap only when identity proof is strong.

    The email/organizational username is used only to establish the first link.
    Subsequent sign-ins resolve from provider + issuer + subject and never from
    mutable provider email claims. Social-only accounts continue through the
    explicit existing-authentication linking path rather than silent merging.
    """

    if not user or not _clean_value(getattr(user, "password_hash", "")):
        return False

    normalized_email = _normalize_email(identity.normalized_email)
    if (
        not normalized_email
        or normalized_email != _normalize_email(user.email)
    ):
        return False

    if identity.provider == GOOGLE_AUTHENTICATION_PROVIDER:
        return bool(
            identity.email_verified
            and identity.authoritative_email
        )

    if identity.provider == MICROSOFT_AUTHENTICATION_PROVIDER:
        # Entra's generic email claim is mutable. external_authentication marks
        # authoritative_email only when the address came from the authenticated
        # organizational username/UPN under a valid organizational tenant.
        return bool(
            identity.authoritative_email
            and identity.tenant_id
        )

    return False


def _external_login_redirect(
    redirect_target: str = "",
) -> str:
    return _build_login_redirect_url(
        _safe_redirect_target(redirect_target)
    )


def _auth_page_context(
    redirect_target: str = "",
) -> dict:
    safe_target = _safe_redirect_target(
        redirect_target
    )

    is_invitation_flow = _is_invitation_redirect(
        safe_target
    )
    invited_email = (
        _invitation_email_for_redirect(safe_target)
        if is_invitation_flow
        else ""
    )

    pending_external_identity = _pending_external_identity()
    suggested_email = (
        _normalize_email(
            pending_external_identity.get("normalized_email")
        )
        if pending_external_identity
        else ""
    )

    return {
        "post_login_redirect": safe_target,
        "is_invitation_flow": is_invitation_flow,
        "invited_email": invited_email,
        "suggested_email": suggested_email,
        "external_link_pending": bool(
            pending_external_identity
        ),
        "external_notice": _consume_external_auth_notice(),
        "external_authentication": _external_authentication_context(
            safe_target
        ),
    }


def _build_login_redirect_url(
    redirect_target: str = "",
) -> str:
    safe_target = _safe_redirect_target(
        redirect_target
    )

    if safe_target:
        return url_for(
            "auth.login_page",
            next=safe_target,
        )

    return url_for(
        "auth.login_page"
    )


def _find_user_by_email(
    db,
    email: str,
) -> User | None:
    normalized_email = _normalize_email(
        email
    )

    if not normalized_email:
        return None

    return (
        db.query(User)
        .filter(
            func.lower(
                func.trim(User.email)
            ) == normalized_email
        )
        .first()
    )


def _find_unique_user_by_email(
    db,
    email: str,
) -> tuple[User | None, bool]:
    """Resolve exactly one normalized email match for identity bootstrap.

    Returns (user, ambiguous). The live schema is intended to enforce one user
    per normalized email, but external-account linking fails closed if historical
    data ever violates that invariant instead of selecting an arbitrary row.
    """

    normalized_email = _normalize_email(email)
    if not normalized_email:
        return None, False

    matches = (
        db.query(User)
        .filter(
            func.lower(
                func.trim(User.email)
            ) == normalized_email
        )
        .order_by(User.id.asc())
        .limit(2)
        .all()
    )

    if len(matches) > 1:
        return None, True

    return (matches[0] if matches else None), False


def _account_exists_response(
    *,
    email: str,
    redirect_target: str = "",
):
    safe_target = _safe_redirect_target(
        redirect_target
    )
    login_redirect = _build_login_redirect_url(
        safe_target
    )

    message = (
        "An account already exists for this email. Sign in to continue."
        if _is_invitation_redirect(safe_target)
        else "An account already exists for this email. Sign in instead."
    )

    return jsonify(
        {
            "ok": False,
            "error": message,
            "error_code": "ACCOUNT_EMAIL_EXISTS",
            "action": "sign_in",
            "email": _normalize_email(email),
            "redirect": login_redirect,
            "login_redirect": login_redirect,
            "post_login_redirect": safe_target,
        }
    ), 409


def _build_internal_username(email: str) -> str:
    """
    Builds a stable internal username for legacy database compatibility.

    This value is not part of the user-facing authentication flow.
    Users log in with email only.
    """
    normalized = _normalize_email(email)
    local_part = normalized.split("@", 1)[0] if "@" in normalized else "user"
    safe_local = re.sub(r"[^a-z0-9._-]+", "-", local_part).strip(".-_") or "user"
    safe_local = safe_local[:70]

    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{safe_local}-{digest}"[:100]



def _reserved_subdomain(slug: str) -> str:
    clean_slug = _clean_value(slug)

    if not clean_slug:
        return ""

    return f"{clean_slug}.{SUBDOMAIN_ROOT}"


def _extract_client_network_context():
    """
    Extract client network context without trust or geo resolution.
    Returns a dict or None.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        ip = forwarded_for.split(",")[0].strip()
        source = "proxy"
    else:
        ip = request.remote_addr
        source = "direct"

    if not ip:
        return None

    try:
        ip_obj = ipaddress.ip_address(ip)
        return {
            "ip": ip,
            "version": "ipv4" if ip_obj.version == 4 else "ipv6",
            "source": source,
            "is_public": not (
                ip_obj.is_private
                or ip_obj.is_loopback
                or ip_obj.is_reserved
                or ip_obj.is_link_local
            ),
        }
    except ValueError:
        return None



def _serialize_unbound_account_context() -> dict:
    """Serialize a Solomon person with no active Organization membership."""

    return {
        "is_group_account": False,
        "requires_group_setup": False,
        "organization": None,
        "group": None,
        "membership": None,
        "reserved_subdomain": "",
    }


def _serialize_organization_account_context(
    *,
    organization: Organization,
    membership: OrganizationMembership,
) -> dict:
    """Serialize the active Organization relationship with legacy aliases.

    Organization is tenant/security authority, not a user-facing Solomon Group.
    The legacy ``group`` and ``is_group_account`` payload keys remain during the
    compatibility bridge for older consumers that still resolve the invisible
    installation boundary through those names. They are derived only from the
    user's current Organization membership and never from a signup account type.
    """

    slug = _clean_value(organization.slug)
    organization_payload = {
        "organization_id": organization.organization_id,
        "group_id": organization.organization_id,
        "name": organization.name,
        "slug": slug,
        "status": organization.status,
    }

    return {
        "is_group_account": True,
        "requires_group_setup": False,
        "organization": dict(organization_payload),
        "group": dict(organization_payload),
        "membership": {
            "membership_id": membership.id,
            "role": membership.role,
            "status": membership.status,
            "is_primary": bool(membership.is_primary),
        },
        "reserved_subdomain": _reserved_subdomain(slug),
    }


def _ensure_initial_organization_membership(
    db,
    *,
    user: User,
) -> bool:
    """Idempotently bootstrap the first installation administrator.

    This is installation commissioning, not Group creation. It never admits an
    arbitrary user into an existing tenant. A missing membership is repaired
    only when the initial administrator created an existing active Organization
    record, or when the installation has no active organization memberships at
    all.
    """

    if not user or not bool(getattr(user, "is_active", False)):
        return False

    if _clean_value(getattr(user, "role", "")).lower() != "admin":
        return False

    existing_membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == ACTIVE_STATUS,
            OrganizationMembership.removed_at.is_(None),
        )
        .first()
    )

    if existing_membership:
        return False

    organization = (
        db.query(Organization)
        .filter(
            Organization.created_by_user_id == user.id,
            Organization.status == ACTIVE_STATUS,
            Organization.suspended_at.is_(None),
        )
        .order_by(Organization.created_at.asc())
        .first()
    )

    if organization is None:
        active_membership_count = (
            db.query(OrganizationMembership.id)
            .join(
                Organization,
                Organization.organization_id
                == OrganizationMembership.organization_id,
            )
            .filter(
                OrganizationMembership.status == ACTIVE_STATUS,
                OrganizationMembership.removed_at.is_(None),
                Organization.status == ACTIVE_STATUS,
                Organization.suspended_at.is_(None),
            )
            .count()
        )

        if active_membership_count:
            return False

        active_organizations = (
            db.query(Organization)
            .filter(
                Organization.status == ACTIVE_STATUS,
                Organization.suspended_at.is_(None),
            )
            .order_by(Organization.created_at.asc())
            .all()
        )

        if len(active_organizations) == 1:
            organization = active_organizations[0]
        else:
            organization = Organization(
                name=INITIAL_ORGANIZATION_NAME,
                slug=(
                    f"{INITIAL_ORGANIZATION_SLUG_PREFIX}-"
                    f"{uuid.uuid4().hex[:10]}"
                ),
                status=ACTIVE_STATUS,
                created_by_user_id=user.id,
            )
            db.add(organization)
            db.flush()

    membership = (
        db.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id
            == organization.organization_id,
            OrganizationMembership.user_id == user.id,
        )
        .first()
    )

    if membership is None:
        membership = OrganizationMembership(
            organization_id=organization.organization_id,
            user_id=user.id,
            role=OWNER_ROLE,
            status=ACTIVE_STATUS,
            is_primary=True,
            invited_by_user_id=user.id,
            joined_at=datetime.utcnow(),
        )
        db.add(membership)
    else:
        membership.role = OWNER_ROLE
        membership.status = ACTIVE_STATUS
        membership.is_primary = True
        membership.removed_at = None
        membership.invited_by_user_id = (
            membership.invited_by_user_id or user.id
        )
        membership.joined_at = membership.joined_at or datetime.utcnow()

    db.flush()
    return True


def _serialize_primary_account_context(
    db,
    user_id: int,
) -> dict:
    clean_user_id = int(user_id or 0)

    if not clean_user_id:
        return _serialize_unbound_account_context()

    result = (
        db.query(
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
        .first()
    )

    if not result:
        return _serialize_unbound_account_context()

    membership, group_record = result

    return _serialize_organization_account_context(
        organization=group_record,
        membership=membership,
    )


def ensure_initial_organization_membership_for_user(user_id: int) -> dict:
    """Commission the first installation administrator when still unbound.

    The operation is intentionally narrow and idempotent. It cannot admit a
    normal user into an existing tenant and it never creates a user-visible
    Group.
    """

    clean_user_id = int(user_id or 0)

    if not clean_user_id:
        return _serialize_unbound_account_context()

    db = SessionLocal()
    try:
        user = db.get(User, clean_user_id)

        if not user:
            return _serialize_unbound_account_context()

        changed = _ensure_initial_organization_membership(
            db,
            user=user,
        )

        if changed:
            db.commit()

        return _serialize_primary_account_context(
            db,
            clean_user_id,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def resolve_account_context_for_user(user_id: int) -> dict:
    """
    Public helper for routes that need Organization relationship context.

    This is intentionally read-only and does not grant Group or file access.
    Current membership persistence remains the temporary Organization bridge.
    """

    clean_user_id = int(user_id or 0)

    if not clean_user_id:
        return _serialize_unbound_account_context()

    db = SessionLocal()
    try:
        return _serialize_primary_account_context(
            db,
            clean_user_id,
        )
    finally:
        db.close()


def _establish_authenticated_session(
    *,
    user_id: int,
    user_email: str,
    user_role: str,
    account_context: dict,
    authentication_method: str,
    network_context: dict | None = None,
    post_login_redirect: str = "",
) -> None:
    """Create the canonical Solomon session after any verified authentication.

    Password, Google, and Microsoft must all converge here. Authentication
    method metadata is informational only; authorization continues to resolve
    from Solomon-owned user, Organization, Group, share, and permission state.
    """

    clean_redirect = _safe_redirect_target(post_login_redirect)
    clean_method = _clean_value(authentication_method).lower() or "unknown"

    session.clear()
    session["user_id"] = int(user_id)
    session["user"] = {
        "email": user_email,
        "username": user_email,
        "role": user_role,
        "group_id": (
            account_context["group"]["group_id"]
            if account_context.get("group")
            else ""
        ),
        "requires_group_setup": bool(
            account_context.get("requires_group_setup")
        ),
    }
    session["account_context"] = account_context
    session["authentication_context"] = {
        "method": clean_method,
    }

    if network_context:
        session["network_context"] = network_context

    if clean_redirect:
        session["post_login_redirect"] = clean_redirect

    session.permanent = True
    session["last_active"] = datetime.utcnow().isoformat()
    session.modified = True


def _current_authentication_method() -> str:
    """Return the active authentication method, defaulting legacy sessions."""

    authentication_context = session.get("authentication_context")
    if isinstance(authentication_context, dict):
        method = _clean_value(
            authentication_context.get("method")
        ).lower()
        if method:
            return method

    return PASSWORD_AUTHENTICATION_METHOD


def _requires_password_change_for_session(user: User | None) -> bool:
    return bool(
        user
        and getattr(user, "must_change_password", 0)
        and _current_authentication_method()
        == PASSWORD_AUTHENTICATION_METHOD
    )


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        return user if user and user.is_active else None
    finally:
        db.close()


# ---------------------------------------------------
# External Authentication Start / Callback
# ---------------------------------------------------
@auth_bp.route("/external/<provider>/start", methods=["GET"])
def external_authentication_start(provider: str):
    """Start a provider-neutral authorization-code OIDC transaction."""

    clean_provider = _clean_value(provider).lower()
    redirect_target = _requested_post_login_redirect()

    if clean_provider not in {
        GOOGLE_AUTHENTICATION_PROVIDER,
        MICROSOFT_AUTHENTICATION_PROVIDER,
    }:
        return jsonify({
            "ok": False,
            "error": "Unsupported authentication provider.",
        }), 404

    if not provider_is_enabled(clean_provider):
        return jsonify({
            "ok": False,
            "error": (
                f"{_external_provider_label(clean_provider)} sign-in "
                "is not configured yet."
            ),
            "provider": clean_provider,
        }), 503

    transaction = _create_external_auth_transaction(
        provider=clean_provider,
        redirect_target=redirect_target,
    )
    invitation_email = (
        _invitation_email_for_redirect(redirect_target)
        if _is_invitation_redirect(redirect_target)
        else ""
    )

    try:
        authorization_url = build_authorization_url(
            provider=clean_provider,
            redirect_uri=_external_callback_url(clean_provider),
            state=transaction["state"],
            nonce=transaction["nonce"],
            code_challenge=transaction["code_challenge"],
            login_hint=invitation_email,
        )
    except ExternalAuthenticationError as exc:
        logger.warning(
            "[auth.external.start_failed] provider=%s error_code=%s",
            clean_provider,
            exc.error_code,
        )
        _set_external_auth_notice(str(exc))
        return redirect(
            _external_login_redirect(redirect_target)
        )

    return redirect(authorization_url, code=302)


@auth_bp.route("/external/<provider>/callback", methods=["GET"])
def external_authentication_callback(provider: str):
    """Complete OIDC authentication and resolve one Solomon person identity."""

    clean_provider = _clean_value(provider).lower()
    if clean_provider not in {
        GOOGLE_AUTHENTICATION_PROVIDER,
        MICROSOFT_AUTHENTICATION_PROVIDER,
    }:
        return jsonify({
            "ok": False,
            "error": "Unsupported authentication provider.",
        }), 404

    state = _clean_value(request.args.get("state"))
    transaction = _consume_external_auth_transaction(
        provider=clean_provider,
        state=state,
    )

    if not transaction:
        _set_external_auth_notice(
            "This authentication request expired or could not be verified. "
            "Please try again."
        )
        return redirect(
            _external_login_redirect()
        )

    redirect_target = _safe_redirect_target(
        transaction.get("redirect_target")
    )

    provider_error = _clean_value(
        request.args.get("error")
    )
    if provider_error:
        _set_external_auth_notice(
            f"{_external_provider_label(clean_provider)} sign-in was not "
            "completed. You can try again or use another sign-in method."
        )
        return redirect(
            _external_login_redirect(redirect_target)
        )

    authorization_code = _clean_value(
        request.args.get("code")
    )
    if not authorization_code:
        _set_external_auth_notice(
            "The authentication provider did not return a sign-in code. "
            "Please try again."
        )
        return redirect(
            _external_login_redirect(redirect_target)
        )

    try:
        identity_result = exchange_authorization_code(
            provider=clean_provider,
            authorization_code=authorization_code,
            redirect_uri=_external_callback_url(clean_provider),
            code_verifier=_clean_value(
                transaction.get("code_verifier")
            ),
            expected_nonce=_clean_value(
                transaction.get("nonce")
            ),
        )
    except ExternalAuthenticationError as exc:
        logger.warning(
            "[auth.external.callback_failed] provider=%s error_code=%s",
            clean_provider,
            exc.error_code,
        )
        _set_external_auth_notice(str(exc))
        return redirect(
            _external_login_redirect(redirect_target)
        )

    normalized_email = _normalize_email(
        identity_result.normalized_email
    )

    if (
        clean_provider == GOOGLE_AUTHENTICATION_PROVIDER
        and not identity_result.email_verified
    ):
        _set_external_auth_notice(
            "Google did not provide a verified email address for this account. "
            "Use another sign-in method."
        )
        return redirect(
            _external_login_redirect(redirect_target)
        )

    if (
        clean_provider == MICROSOFT_AUTHENTICATION_PROVIDER
        and not identity_result.authoritative_email
    ):
        _set_external_auth_notice(
            "Microsoft did not provide a usable organizational sign-in address "
            "for this account. Use another sign-in method."
        )
        return redirect(
            _external_login_redirect(redirect_target)
        )

    if not normalized_email or not validate_email(normalized_email):
        _set_external_auth_notice(
            f"{_external_provider_label(clean_provider)} did not provide a "
            "usable email address for this account. Use another sign-in method."
        )
        return redirect(
            _external_login_redirect(redirect_target)
        )

    if _is_invitation_redirect(redirect_target):
        invitation_email = _invitation_email_for_redirect(
            redirect_target
        )
        if not invitation_email:
            _set_external_auth_notice(
                "This invitation is no longer active."
            )
            return redirect(
                _external_login_redirect()
            )

        if normalized_email != invitation_email:
            _set_external_auth_notice(
                "Sign in with the account that matches the email address "
                "that received this invitation."
            )
            return redirect(
                _external_login_redirect(redirect_target)
            )

        if not _provider_can_prove_invitation_email(
            identity_result
        ):
            _set_external_auth_notice(
                f"{_external_provider_label(clean_provider)} cannot verify "
                "current control of this invitation email. Use the Nations "
                "Systems password sign-in method for this invitation."
            )
            return redirect(
                _external_login_redirect(redirect_target)
            )

    network_context = _extract_client_network_context()
    db = SessionLocal()

    try:
        external_identity = (
            db.query(ExternalIdentity)
            .filter(
                ExternalIdentity.provider
                == identity_result.provider,
                ExternalIdentity.issuer
                == identity_result.issuer,
                ExternalIdentity.provider_subject
                == identity_result.provider_subject,
            )
            .first()
        )

        if external_identity:
            user = db.get(
                User,
                external_identity.user_id,
            )
            if not user or not user.is_active:
                _set_external_auth_notice(
                    "This Nations Systems account is inactive."
                )
                return redirect(
                    _external_login_redirect(redirect_target)
                )

            _apply_external_identity_values(
                external_identity,
                provider=identity_result.provider,
                issuer=identity_result.issuer,
                provider_subject=identity_result.provider_subject,
                provider_email=identity_result.provider_email,
                normalized_email=identity_result.normalized_email,
                email_verified=identity_result.email_verified,
                tenant_id=identity_result.tenant_id,
            )

            _attach_pending_external_identity(
                db,
                user=user,
            )
        else:
            existing_user, email_ambiguous = _find_unique_user_by_email(
                db,
                normalized_email,
            )

            if email_ambiguous:
                logger.error(
                    "[auth.external.email_identity_ambiguous] provider=%s",
                    clean_provider,
                )
                _set_external_auth_notice(
                    "This email is associated with conflicting Nations Systems "
                    "identity records. Sign in using your existing Nations "
                    "Systems authentication method and contact support."
                )
                return redirect(
                    _external_login_redirect(redirect_target)
                )

            if existing_user:
                if not existing_user.is_active:
                    _set_external_auth_notice(
                        "This Nations Systems account is inactive."
                    )
                    return redirect(
                        _external_login_redirect(redirect_target)
                    )

                provider_identity = (
                    db.query(ExternalIdentity)
                    .filter(
                        ExternalIdentity.user_id == existing_user.id,
                        ExternalIdentity.provider == identity_result.provider,
                    )
                    .first()
                )

                if provider_identity:
                    _set_external_auth_notice(
                        f"Your Nations Systems account already has a different "
                        f"{_external_provider_label(clean_provider)} identity. "
                        "No account changes were made; sign in using an existing "
                        "authentication method."
                    )
                    return redirect(
                        _external_login_redirect(redirect_target)
                    )

                if _external_identity_can_auto_link_password_user(
                    identity_result,
                    user=existing_user,
                ):
                    # Serialize first-link decisions for this person so concurrent
                    # callbacks cannot silently attach two identities for the same
                    # provider. Re-check after taking the row lock because another
                    # callback may have completed while this request was waiting.
                    user = (
                        db.query(User)
                        .filter(User.id == existing_user.id)
                        .with_for_update()
                        .one()
                    )
                    provider_identity = (
                        db.query(ExternalIdentity)
                        .filter(
                            ExternalIdentity.user_id == user.id,
                            ExternalIdentity.provider == identity_result.provider,
                        )
                        .first()
                    )

                    if provider_identity:
                        same_identity = (
                            provider_identity.issuer == identity_result.issuer
                            and provider_identity.provider_subject
                            == identity_result.provider_subject
                        )
                        if not same_identity:
                            _set_external_auth_notice(
                                f"Your Nations Systems account already has a "
                                f"different {_external_provider_label(clean_provider)} "
                                "identity. No account changes were made; sign in "
                                "using an existing authentication method."
                            )
                            return redirect(
                                _external_login_redirect(redirect_target)
                            )
                        external_identity = provider_identity
                    else:
                        external_identity = ExternalIdentity(
                            user_id=user.id,
                            provider=identity_result.provider,
                            issuer=identity_result.issuer,
                            provider_subject=identity_result.provider_subject,
                        )
                        db.add(external_identity)

                    _apply_external_identity_values(
                        external_identity,
                        provider=identity_result.provider,
                        issuer=identity_result.issuer,
                        provider_subject=identity_result.provider_subject,
                        provider_email=identity_result.provider_email,
                        normalized_email=identity_result.normalized_email,
                        email_verified=identity_result.email_verified,
                        tenant_id=identity_result.tenant_id,
                    )
                    logger.info(
                        "[auth.external.identity_auto_linked] provider=%s user_id=%s",
                        clean_provider,
                        user.id,
                    )
                else:
                    _store_pending_external_identity(
                        identity_result
                    )
                    _set_external_auth_notice(
                        f"A Nations Systems account already exists for "
                        f"{normalized_email}. Sign in using your existing "
                        f"authentication method to connect "
                        f"{_external_provider_label(clean_provider)}."
                    )
                    return redirect(
                        _external_login_redirect(redirect_target)
                    )

            else:
                existing_users = db.query(User).count()
                assigned_role = (
                    "admin"
                    if existing_users == 0
                    else "user"
                )
                user = User(
                    username=_build_internal_username(
                        normalized_email
                    ),
                    email=normalized_email,
                    password_hash=None,
                    role=assigned_role,
                )
                db.add(user)
                db.flush()

                external_identity = ExternalIdentity(
                    user_id=user.id,
                    provider=identity_result.provider,
                    issuer=identity_result.issuer,
                    provider_subject=(
                        identity_result.provider_subject
                    ),
                )
                db.add(external_identity)
                _apply_external_identity_values(
                    external_identity,
                    provider=identity_result.provider,
                    issuer=identity_result.issuer,
                    provider_subject=identity_result.provider_subject,
                    provider_email=identity_result.provider_email,
                    normalized_email=identity_result.normalized_email,
                    email_verified=identity_result.email_verified,
                    tenant_id=identity_result.tenant_id,
                )

                _ensure_initial_organization_membership(
                    db,
                    user=user,
                )

        user.last_login_at = datetime.utcnow()

        if network_context:
            if hasattr(user, "last_login_ip"):
                user.last_login_ip = network_context["ip"]
            if hasattr(user, "last_login_ip_version"):
                user.last_login_ip_version = network_context["version"]
            if hasattr(user, "last_login_ip_source"):
                user.last_login_ip_source = network_context["source"]

        account_context = _serialize_primary_account_context(
            db,
            user.id,
        )
        user_id = int(user.id)
        user_email = str(user.email)
        user_role = str(user.role)
        db.commit()

    except IntegrityError as exc:
        db.rollback()
        logger.warning(
            "[auth.external.identity_conflict] provider=%s error=%s",
            clean_provider,
            type(exc).__name__,
        )
        _set_external_auth_notice(
            "That external identity could not be connected safely. Sign in "
            "using your existing Nations Systems authentication method."
        )
        return redirect(
            _external_login_redirect(redirect_target)
        )
    except Exception:
        db.rollback()
        logger.exception(
            "[auth.external.callback_exception] provider=%s",
            clean_provider,
        )
        _set_external_auth_notice(
            "External sign-in could not be completed. Please try again."
        )
        return redirect(
            _external_login_redirect(redirect_target)
        )
    finally:
        db.close()

    default_redirect_url = (
        "/admin"
        if user_role.lower() == "admin"
        else "/"
    )
    final_redirect = (
        redirect_target
        or default_redirect_url
    )

    _establish_authenticated_session(
        user_id=user_id,
        user_email=user_email,
        user_role=user_role,
        account_context=account_context,
        authentication_method=clean_provider,
        network_context=network_context,
    )

    return redirect(final_redirect, code=302)


# ---------------------------------------------------
# Registration Page (GET)
# ---------------------------------------------------
@auth_bp.route("/register", methods=["GET"])
def register_page():
    redirect_target = _requested_post_login_redirect()
    user = current_user()

    # Forced-change user hitting register = escape loop
    if _requires_password_change_for_session(user):
        session.clear()

    elif user:
        return redirect(
            redirect_target
            or "/"
        )

    return render_template(
        "register.html",
        auth_context=_auth_page_context(
            redirect_target
        ),
        post_login_redirect=redirect_target,
    )


# ---------------------------------------------------
# Registration (POST)
# ---------------------------------------------------
@auth_bp.route("/register", methods=["POST"])
def register_user():
    data = request.get_json(silent=True) or {}
    redirect_target = _requested_post_login_redirect(
        data
    )

    email = _normalize_email(data.get("email") or data.get("username"))
    password = data.get("password")
    invitation_email = (
        _invitation_email_for_redirect(redirect_target)
        if _is_invitation_redirect(redirect_target)
        else ""
    )

    if _is_invitation_redirect(redirect_target):
        if not invitation_email:
            return jsonify({
                "ok": False,
                "error": "This invitation is no longer active.",
            }), 410
        if email != invitation_email:
            return jsonify({
                "ok": False,
                "error": "Create the account using the email address that received the invitation.",
            }), 403

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password required."}), 400

    if not validate_email(email):
        return jsonify({"ok": False, "error": "Enter a valid email address."}), 400

    if len(password) < 8:
        return jsonify({"ok": False, "error": "Password must be at least 8 characters."}), 400

    hashed = generate_password_hash(password)
    internal_username = _build_internal_username(email)

    db = SessionLocal()
    try:
        existing_email = _find_user_by_email(
            db,
            email,
        )

        if existing_email:
            return _account_exists_response(
                email=email,
                redirect_target=redirect_target,
            )

        existing_users = db.query(User).count()
        assigned_role = "admin" if existing_users == 0 else "user"

        new_user = User(
            username=internal_username,
            email=email,
            password_hash=hashed,
            role=assigned_role,
        )
        db.add(new_user)
        db.flush()

        # Registration creates one Solomon person. The only automatic tenant
        # relationship is installation commissioning for the first administrator;
        # every other Organization relationship is established by normal
        # membership or invitation authority.
        _ensure_initial_organization_membership(
            db,
            user=new_user,
        )
        account_context = _serialize_primary_account_context(
            db,
            new_user.id,
        )

        if _is_invitation_redirect(redirect_target):
            new_user.last_login_at = datetime.utcnow()

        db.commit()

        message = "Account created successfully."

        if _is_invitation_redirect(redirect_target):
            # The invitation link already established the user's intent and
            # registration with the invited email has just authenticated that
            # identity. Keep the browser in one continuous flow: establish the
            # session now and let the preserved invitation route complete the
            # pending contextual action automatically.
            _establish_authenticated_session(
                user_id=new_user.id,
                user_email=new_user.email,
                user_role=assigned_role,
                account_context=account_context,
                authentication_method=PASSWORD_AUTHENTICATION_METHOD,
            )

            return jsonify(
                {
                    "ok": True,
                    "message": message,
                    "assigned_role": assigned_role,
                    "account_context": account_context,
                    "redirect": redirect_target,
                    "post_login_redirect": redirect_target,
                    "authenticated": True,
                }
            ), 201

        login_redirect = _build_login_redirect_url(
            redirect_target
        )

        return jsonify(
            {
                "ok": True,
                "message": message,
                "assigned_role": assigned_role,
                "account_context": account_context,
                "redirect": login_redirect,
                "post_login_redirect": redirect_target,
            }
        ), 201

    except IntegrityError:
        db.rollback()
        return _account_exists_response(
            email=email,
            redirect_target=redirect_target,
        )
    except Exception:
        db.rollback()
        return jsonify({"ok": False, "error": "Account registration could not be completed."}), 500
    finally:
        db.close()


# ---------------------------------------------------
# Login Page (GET)
# ---------------------------------------------------
@auth_bp.route("/login", methods=["GET"])
def login_page():
    redirect_target = _requested_post_login_redirect()
    user = current_user()

    if _requires_password_change_for_session(user):
        session.clear()

    elif user:
        return redirect(
            redirect_target
            or "/"
        )

    return render_template(
        "login.html",
        auth_context=_auth_page_context(
            redirect_target
        ),
        post_login_redirect=redirect_target,
    )


# ---------------------------------------------------
# Login (POST)
# ---------------------------------------------------
@auth_bp.route("/login", methods=["POST"])
def login_user():
    data = request.get_json(silent=True) or {}
    post_login_redirect = _requested_post_login_redirect(
        data
    )

    email = _normalize_email(data.get("email") or data.get("username"))
    password = data.get("password")
    invitation_email = (
        _invitation_email_for_redirect(post_login_redirect)
        if _is_invitation_redirect(post_login_redirect)
        else ""
    )

    if _is_invitation_redirect(post_login_redirect):
        if not invitation_email:
            return jsonify({
                "ok": False,
                "error": "This invitation is no longer active.",
            }), 410
        if email != invitation_email:
            return jsonify({
                "ok": False,
                "error": "Sign in with the email address that received the invitation.",
            }), 403

    if not email or not password:
        return jsonify({"ok": False, "error": "Email and password required."}), 400

    if not validate_email(email):
        return jsonify({"ok": False, "error": "Enter a valid email address."}), 400

    network_context = _extract_client_network_context()

    db = SessionLocal()
    try:
        user = _find_user_by_email(
            db,
            email,
        )

        password_hash = str(
            getattr(user, "password_hash", "") or ""
        ).strip()

        if (
            not user
            or not password_hash
            or not check_password_hash(password_hash, password)
        ):
            return jsonify({"ok": False, "error": "Invalid credentials."}), 401

        if not user.is_active:
            return jsonify({"ok": False, "error": "Account is inactive."}), 403

        linked_provider = _attach_pending_external_identity(
            db,
            user=user,
        )
        user.last_login_at = datetime.utcnow()

        # Persist only raw, non-authoritative signals if fields exist
        if network_context:
            if hasattr(user, "last_login_ip"):
                user.last_login_ip = network_context["ip"]
            if hasattr(user, "last_login_ip_version"):
                user.last_login_ip_version = network_context["version"]
            if hasattr(user, "last_login_ip_source"):
                user.last_login_ip_source = network_context["source"]

        must_change = bool(getattr(user, "must_change_password", 0))

        user_id = user.id
        user_email = user.email
        user_role = user.role

        _ensure_initial_organization_membership(
            db,
            user=user,
        )
        account_context = _serialize_primary_account_context(
            db,
            user_id,
        )

        db.commit()

    finally:
        db.close()

    default_redirect_url = "/admin" if user_role.lower() == "admin" else "/"
    redirect_url = (
        post_login_redirect
        or default_redirect_url
    )

    _establish_authenticated_session(
        user_id=user_id,
        user_email=user_email,
        user_role=user_role,
        account_context=account_context,
        authentication_method=PASSWORD_AUTHENTICATION_METHOD,
        network_context=network_context,
        post_login_redirect=(
            post_login_redirect
            if must_change
            else ""
        ),
    )

    if must_change:

        return jsonify(
            {
                "ok": True,
                "force_password_change": True,
                "redirect": "/auth/change-password",
                "post_login_redirect": post_login_redirect,
            }
        ), 200

    return jsonify(
        {
            "ok": True,
            "message": (
                f"{linked_provider} connected. Welcome back."
                if linked_provider
                else "Welcome back."
            ),
            "role": user_role,
            "account_context": account_context,
            "redirect": redirect_url,
            "post_login_redirect": post_login_redirect,
        }
    ), 200


# ---------------------------------------------------
# Change Password Page (GET)
# ---------------------------------------------------
@auth_bp.route("/change-password", methods=["GET"])
def change_password_page():
    user = current_user()

    if not user:
        redirect_target = _requested_post_login_redirect()
        return redirect(
            url_for(
                "auth.login_page",
                next=redirect_target,
            )
            if redirect_target
            else url_for("auth.login_page")
        )

    return render_template("change_password.html")


# ---------------------------------------------------
# Change Password (POST)
# ---------------------------------------------------
@auth_bp.route("/change-password", methods=["POST"])
def change_password():
    user = current_user()
    if not user:
        return jsonify({"ok": False, "error": "Not authenticated."}), 401

    data = request.get_json(silent=True) or {}
    new_pw = data.get("new_password") or data.get("password")

    if not new_pw:
        return jsonify({"ok": False, "error": "New password required."}), 400

    if len(new_pw) < 8:
        return jsonify({"ok": False, "error": "Password must be at least 8 characters."}), 400

    db = SessionLocal()
    try:
        db_user = db.get(User, user.id)

        if not db_user:
            return jsonify({"ok": False, "error": "Account not found."}), 404

        current_password_hash = str(
            db_user.password_hash or ""
        ).strip()

        if (
            current_password_hash
            and check_password_hash(current_password_hash, new_pw)
        ):
            return jsonify(
                {
                    "ok": False,
                    "error": "New password must be different from your current password.",
                }
            ), 400

        db_user.password_hash = generate_password_hash(new_pw)

        if hasattr(db_user, "must_change_password"):
            db_user.must_change_password = 0
        if hasattr(db_user, "temp_password_issued_at"):
            db_user.temp_password_issued_at = None

        db.commit()

        redirect_url = _safe_redirect_target(
            session.pop(
                "post_login_redirect",
                "",
            )
        ) or "/"

        return jsonify(
            {
                "ok": True,
                "message": "Password updated successfully.",
                "redirect": redirect_url,
            }
        )

    finally:
        db.close()


# ---------------------------------------------------
# Logout
# ---------------------------------------------------
@auth_bp.route("/logout", methods=["GET"])
def logout_user():
    redirect_target = _safe_redirect_target(
        request.args.get("next")
    )
    session.clear()
    if redirect_target:
        return redirect(
            url_for(
                "auth.login_page",
                next=redirect_target,
            )
        )
    return redirect(url_for("auth.login_page"))


# ---------------------------------------------------
# Session heartbeat
# ---------------------------------------------------
@auth_bp.route("/session-check", methods=["GET"])
def session_check():
    user = current_user()
    if not user:
        session.clear()
        return jsonify({"ok": False, "expired": True}), 401

    try:
        last_active_str = session.get("last_active")
        if last_active_str:
            last_active = datetime.fromisoformat(last_active_str)
            if datetime.utcnow() - last_active > timedelta(minutes=30):
                session.clear()
                return jsonify({"ok": False, "expired": True}), 401

        session["last_active"] = datetime.utcnow().isoformat()

    except Exception:
        session.clear()
        return jsonify({"ok": False, "expired": True}), 401

    return jsonify({"ok": True}), 200


# ---------------------------------------------------
# Current user
# ---------------------------------------------------
@auth_bp.route("/me", methods=["GET"])
def get_current_user():
    user = current_user()
    if not user:
        return jsonify({"ok": False, "authenticated": False}), 401

    db = SessionLocal()
    try:
        account_context = _serialize_primary_account_context(
            db,
            user.id,
        )
    finally:
        db.close()

    return jsonify(
        {
            "ok": True,
            "authenticated": True,
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.email,
                "display_name": user.email,
                "role": user.role,
                "is_active": user.is_active,
                "requires_group_setup": bool(
                    account_context.get("requires_group_setup")
                ),
                "account_context": account_context,
                "created_at": user.created_at.isoformat(),
                "last_login_at": (user.last_login_at.isoformat() if user.last_login_at else None),
            },
        }
    ), 200