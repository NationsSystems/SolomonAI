# -------------------------------------------------------------------
# FILE: admin_resource_usage_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Installation-admin resource diagnostics backed by Solomon's authoritative
# compute, transport, capacity, service-health, and attribution history.
# This is a read-only internal diagnostics API; customer reporting is exposed
# separately through the tenant-authorized resource_usage_bp boundary.
# -------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, request

from solomon_core.auth_utils import admin_required, login_required
from solomon_core.intelligence_service.compute_capacity_repository import (
    get_internal_resource_usage_report,
)


admin_resource_usage_bp = Blueprint(
    "admin_resource_usage",
    __name__,
    url_prefix="/admin/resource-usage",
)


DEFAULT_WINDOW_HOURS = 24
MAX_WINDOW_HOURS = 720
DEFAULT_EVENT_LIMIT = 200
MAX_EVENT_LIMIT = 500


def _bounded_integer(value, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _report_window() -> tuple[datetime, datetime, int]:
    hours = _bounded_integer(
        request.args.get("hours"),
        default=DEFAULT_WINDOW_HOURS,
        minimum=1,
        maximum=MAX_WINDOW_HOURS,
    )
    end_at = datetime.now(timezone.utc)
    start_at = end_at - timedelta(hours=hours)
    return start_at, end_at, hours


@admin_resource_usage_bp.route("/data", methods=["GET"])
@login_required
@admin_required
def admin_resource_usage_data():
    start_at, end_at, hours = _report_window()
    event_limit = _bounded_integer(
        request.args.get("limit"),
        default=DEFAULT_EVENT_LIMIT,
        minimum=1,
        maximum=MAX_EVENT_LIMIT,
    )

    try:
        report = get_internal_resource_usage_report(
            start_at=start_at,
            end_at=end_at,
            event_limit=event_limit,
        )
        report["ok"] = True
        report["window"]["hours"] = hours
        report["event_limit"] = event_limit
        return jsonify(report), 200
    except Exception:
        current_app.logger.exception(
            "Admin resource diagnostics report build failed"
        )
        return jsonify({
            "ok": False,
            "error": "Resource diagnostics could not be loaded.",
        }), 500


__all__ = [
    "admin_resource_usage_bp",
]
