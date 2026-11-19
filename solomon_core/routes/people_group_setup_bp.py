# -------------------------------------------------------------------
# FILE: people_group_setup_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Compatibility routes for the retired first-group setup flow.
#
# The installation Organization is now an invisible tenant/security
# boundary. User-visible Groups are created from /people and are backed by
# OrganizationGroup / OrganizationGroupMembership. These routes remain only
# so stale bookmarks or older clients fail safely instead of recreating the
# legacy Organization-as-Group model.
# -------------------------------------------------------------------

from __future__ import annotations

from flask import Blueprint, jsonify, redirect

from solomon_core.auth_utils import login_required


people_group_setup_bp = Blueprint(
    "people_group_setup_bp",
    __name__,
)


PEOPLE_ROUTE = "/people"
PEOPLE_GROUPS_ROUTE = "/people/groups"
PEOPLE_GROUP_SETUP_ROUTE = "/people/groups/setup"


@people_group_setup_bp.route(
    PEOPLE_GROUP_SETUP_ROUTE,
    methods=["GET"],
)
@login_required
def people_group_setup_page():
    """Retire the legacy setup screen and return to canonical People."""

    return redirect(
        PEOPLE_ROUTE,
        code=302,
    )


@people_group_setup_bp.route(
    PEOPLE_GROUPS_ROUTE,
    methods=["POST"],
)
@login_required
def people_group_setup_submit():
    """Reject legacy Organization-as-Group creation under server authority."""

    return jsonify(
        {
            "ok": False,
            "error": (
                "The legacy first-group setup flow has been retired. "
                "Create and manage Groups from People > Groups."
            ),
            "redirect": PEOPLE_ROUTE,
        }
    ), 409


__all__ = [
    "people_group_setup_bp",
]
