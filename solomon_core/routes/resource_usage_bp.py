# -------------------------------------------------------------------
# FILE: resource_usage_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Customer-safe resource usage reporting for the active Solomon tenant.
# Raw history remains authoritative in Solomon's database; this route exposes
# only bounded, server-authorized operational summaries for tenant owners and
# admins. It never grants reporting authority from database visibility alone.
# -------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import (
    Blueprint,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    session,
)

from solomon_core.auth import resolve_account_context_for_user
from solomon_core.auth_utils import login_required
from solomon_core.db import SessionLocal
from solomon_core.intelligence_service.compute_capacity_repository import (
    get_organization_resource_usage_report,
)
from solomon_core.models import Organization, OrganizationMembership


resource_usage_bp = Blueprint(
    "resource_usage",
    __name__,
    url_prefix="/resource-usage",
)


ACTIVE_STATUS = "active"
TENANT_REPORTING_ROLES = {
    "owner",
    "admin",
}
DEFAULT_WINDOW_HOURS = 24
MAX_WINDOW_HOURS = 168


class ResourceUsageAccessError(Exception):
    """Raised when tenant resource-usage reporting is not authorized."""

    def __init__(self, message: str, status_code: int = 403):
        super().__init__(message)
        self.status_code = status_code


def _clean_value(value) -> str:
    return str(value or "").strip()


def _current_user_id() -> int:
    try:
        return int(session.get("user_id") or 0)
    except (TypeError, ValueError):
        return 0


def _report_window() -> tuple[datetime, datetime, int]:
    raw_hours = request.args.get("hours", DEFAULT_WINDOW_HOURS)
    try:
        hours = int(raw_hours)
    except (TypeError, ValueError):
        hours = DEFAULT_WINDOW_HOURS

    hours = max(1, min(MAX_WINDOW_HOURS, hours))
    end_at = datetime.now(timezone.utc)
    start_at = end_at - timedelta(hours=hours)
    return start_at, end_at, hours


def _require_tenant_reporting_admin() -> dict:
    user_id = _current_user_id()
    if user_id <= 0:
        raise ResourceUsageAccessError(
            "Authentication required.",
            401,
        )

    account_context = resolve_account_context_for_user(user_id)
    organization = (
        account_context.get("organization")
        if isinstance(account_context, dict)
        else None
    )
    membership = (
        account_context.get("membership")
        if isinstance(account_context, dict)
        else None
    )

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

    if (
        not organization_id
        or not membership_id
        or role not in TENANT_REPORTING_ROLES
    ):
        raise ResourceUsageAccessError(
            "Resource usage reporting is available to workspace owners and admins.",
            403,
        )

    db_session = SessionLocal()
    try:
        organization_record = (
            db_session.query(Organization)
            .filter(
                Organization.organization_id == organization_id,
                Organization.status == ACTIVE_STATUS,
                Organization.suspended_at.is_(None),
            )
            .first()
        )
        membership_record = (
            db_session.query(OrganizationMembership)
            .filter(
                OrganizationMembership.id == int(membership_id),
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.status == ACTIVE_STATUS,
                OrganizationMembership.removed_at.is_(None),
            )
            .first()
        )
        verified_role = _clean_value(
            getattr(membership_record, "role", "")
        ).lower()

        if (
            not organization_record
            or not membership_record
            or verified_role not in TENANT_REPORTING_ROLES
        ):
            raise ResourceUsageAccessError(
                "Resource usage reporting is not available for this account.",
                403,
            )

        active_organization_ids = [
            row[0]
            for row in (
                db_session.query(Organization.organization_id)
                .filter(
                    Organization.status == ACTIVE_STATUS,
                    Organization.suspended_at.is_(None),
                )
                .all()
            )
        ]
        installation_is_exclusive = (
            len(active_organization_ids) == 1
            and active_organization_ids[0] == organization_id
        )

        return {
            "user_id": user_id,
            "organization_id": organization_id,
            "organization_name": _clean_value(
                getattr(organization_record, "name", "")
            ) or "Workspace",
            "role": verified_role,
            "installation_is_exclusive": installation_is_exclusive,
            "account_context": account_context,
        }
    finally:
        db_session.close()


@resource_usage_bp.route("/", methods=["GET"], strict_slashes=False)
@login_required
def resource_usage_page():
    try:
        authority = _require_tenant_reporting_admin()
    except ResourceUsageAccessError as exc:
        abort(exc.status_code, description=str(exc))

    return render_template(
        "resource_usage.html",
        active_module="resource_usage",
        account_context=authority.get("account_context") or {},
        resource_usage_authority=authority,
        resource_usage_organization_name=authority["organization_name"],
        resource_usage_reporting_role=authority["role"],
        resource_usage_default_hours=DEFAULT_WINDOW_HOURS,
        workspace_surface_template="components/resource_usage_workspace.html",
    )


@resource_usage_bp.route("/data", methods=["GET"])
@login_required
def resource_usage_data():
    try:
        authority = _require_tenant_reporting_admin()
        start_at, end_at, hours = _report_window()
        report = get_organization_resource_usage_report(
            organization_id=authority["organization_id"],
            start_at=start_at,
            end_at=end_at,
            include_installation_capacity=bool(
                authority["installation_is_exclusive"]
            ),
        )
        report["ok"] = True
        report["window"]["hours"] = hours
        report["reporting_role"] = authority["role"]
        return jsonify(report), 200
    except ResourceUsageAccessError as exc:
        return jsonify({
            "ok": False,
            "error": str(exc),
        }), exc.status_code
    except Exception:
        current_app.logger.exception(
            "Tenant resource usage report build failed"
        )
        return jsonify({
            "ok": False,
            "error": "Resource usage history could not be loaded.",
        }), 500


__all__ = [
    "resource_usage_bp",
]
