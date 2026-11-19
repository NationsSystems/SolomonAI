# -------------------------------------------------------------------
# FILE: group_account_bootstrap.py
# DIRECTORY: solomon_core/solomon_tools/
# -------------------------------------------------------------------
# Internal additive bootstrap utility for group-account permissions.
#
# Creates or reuses one group authority record, makes a user an active
# group owner, and optionally places existing FileRegistry records into
# group-library custody for controlled local validation.
# -------------------------------------------------------------------

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import uuid


# -------------------------------------------------------------------
# Project Import Path
# -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from solomon_core.db import SessionLocal  # noqa: E402
from solomon_core.models import (  # noqa: E402
    FileRegistry,
    Organization,
    OrganizationFileCustody,
    OrganizationMembership,
    User,
    utc_now,
)
from solomon_core.workspace_reader.workspace_reader_file_access import (  # noqa: E402
    is_file_record_trashed,
    resolve_file_record_by_identifier,
)


ACTIVE_STATUS = "active"
GROUP_LIBRARY_SCOPE = "group_library"
LEGACY_LIBRARY_SCOPE = "company" + "_library"
DEFAULT_GROUP_NAME = "Nations Systems"
DEFAULT_POLICY_VERSION = "group_file_permissions_v1"
LEGACY_POLICY_VERSION = "organization" + "_file_permissions_v1"


# -------------------------------------------------------------------
# Normalization
# -------------------------------------------------------------------
def _clean_value(value) -> str:
    return str(value or "").strip()


def _slugify(value: str) -> str:
    candidate = re.sub(
        r"[^a-z0-9]+",
        "-",
        _clean_value(value).lower(),
    ).strip("-")

    return candidate or "group"


def _new_group_authority_id(slug: str) -> str:
    safe_slug = _slugify(slug)[:24] or "group"
    return f"grp_{safe_slug}_{uuid.uuid4().hex[:10]}"


def _canonical_policy_version(value) -> str:
    clean_value = _clean_value(value)

    if not clean_value or clean_value == LEGACY_POLICY_VERSION:
        return DEFAULT_POLICY_VERSION

    return clean_value


def _canonical_library_scope(value) -> str:
    clean_value = _clean_value(value)

    if not clean_value or clean_value == LEGACY_LIBRARY_SCOPE:
        return GROUP_LIBRARY_SCOPE

    return clean_value


def _user_is_active(user: User | None) -> bool:
    return bool(
        user
        and bool(getattr(user, "is_active", True))
    )


# -------------------------------------------------------------------
# Group Authority
# -------------------------------------------------------------------
def _get_or_create_group_authority(
    db_session,
    *,
    group_name: str,
    group_slug: str,
    user_id: int,
) -> Organization:
    clean_name = _clean_value(group_name) or DEFAULT_GROUP_NAME
    clean_slug = _slugify(group_slug or clean_name)

    group_authority = (
        db_session.query(Organization)
        .filter(Organization.slug == clean_slug)
        .first()
    )

    if group_authority:
        changed = False

        if group_authority.status != ACTIVE_STATUS:
            group_authority.status = ACTIVE_STATUS
            changed = True

        if group_authority.suspended_at is not None:
            group_authority.suspended_at = None
            changed = True

        if not _clean_value(group_authority.name):
            group_authority.name = clean_name
            changed = True

        if hasattr(group_authority, "authorization_policy_version"):
            next_policy_version = _canonical_policy_version(
                group_authority.authorization_policy_version
            )

            if group_authority.authorization_policy_version != next_policy_version:
                group_authority.authorization_policy_version = next_policy_version
                changed = True

        if hasattr(group_authority, "default_file_visibility"):
            next_visibility = _canonical_library_scope(
                group_authority.default_file_visibility
            )

            if group_authority.default_file_visibility != next_visibility:
                group_authority.default_file_visibility = next_visibility
                changed = True

        if hasattr(group_authority, "ai_query_enabled"):
            if not bool(group_authority.ai_query_enabled):
                group_authority.ai_query_enabled = True
                changed = True

        if changed:
            group_authority.updated_at = utc_now()

        return group_authority

    group_authority = Organization(
        organization_id=_new_group_authority_id(clean_slug),
        name=clean_name,
        slug=clean_slug,
        status=ACTIVE_STATUS,
        created_by_user_id=user_id,
        authorization_policy_version=DEFAULT_POLICY_VERSION,
        default_file_visibility=GROUP_LIBRARY_SCOPE,
        ai_query_enabled=True,
    )
    db_session.add(group_authority)
    db_session.flush()

    return group_authority


def _get_or_create_owner_membership(
    db_session,
    *,
    group_authority: Organization,
    user_id: int,
) -> OrganizationMembership:
    membership = (
        db_session.query(OrganizationMembership)
        .filter(
            OrganizationMembership.organization_id
            == group_authority.organization_id,
            OrganizationMembership.user_id == user_id,
        )
        .first()
    )

    if membership:
        membership.role = "owner"
        membership.status = ACTIVE_STATUS
        membership.is_primary = True
        membership.removed_at = None
        membership.updated_at = utc_now()
        return membership

    membership = OrganizationMembership(
        organization_id=group_authority.organization_id,
        user_id=user_id,
        role="owner",
        status=ACTIVE_STATUS,
        is_primary=True,
        invited_by_user_id=user_id,
        joined_at=utc_now(),
    )
    db_session.add(membership)
    db_session.flush()

    return membership


# -------------------------------------------------------------------
# File Selection / Custody
# -------------------------------------------------------------------
def _resolve_requested_files(
    db_session,
    *,
    user_id: int,
    include_user_files: bool,
    file_ids: list[int],
    document_ids: list[str],
) -> list[FileRegistry]:
    records: list[FileRegistry] = []
    seen_ids: set[int] = set()

    def add_record(record: FileRegistry | None) -> None:
        if not record or not record.id:
            return

        if record.id in seen_ids:
            return

        if is_file_record_trashed(record):
            return

        seen_ids.add(record.id)
        records.append(record)

    if include_user_files:
        for record in (
            db_session.query(FileRegistry)
            .filter(FileRegistry.uploader_id == user_id)
            .order_by(FileRegistry.id.asc())
            .all()
        ):
            add_record(record)

    for file_id in file_ids:
        add_record(
            db_session.get(
                FileRegistry,
                int(file_id),
            )
        )

    for document_id in document_ids:
        add_record(
            resolve_file_record_by_identifier(
                db_session,
                document_id,
            )
        )

    return records


def _place_file_in_group_library(
    db_session,
    *,
    group_authority: Organization,
    record: FileRegistry,
    user_id: int,
) -> OrganizationFileCustody:
    custody = (
        db_session.query(OrganizationFileCustody)
        .filter(
            OrganizationFileCustody.organization_id
            == group_authority.organization_id,
            OrganizationFileCustody.file_registry_id == record.id,
        )
        .first()
    )

    if custody:
        custody.custody_mode = "group_library"
        custody.library_scope = GROUP_LIBRARY_SCOPE
        custody.status = ACTIVE_STATUS
        custody.removed_at = None

        if hasattr(custody, "is_discoverable"):
            custody.is_discoverable = True

        if hasattr(custody, "allow_ai_query"):
            custody.allow_ai_query = True

        if hasattr(custody, "classification"):
            custody.classification = (
                custody.classification
                or getattr(record, "classification", None)
                or "internal"
            )

        if hasattr(custody, "policy_version"):
            custody.policy_version = _canonical_policy_version(
                custody.policy_version
            )

        custody.updated_at = utc_now()
        return custody

    custody = OrganizationFileCustody(
        organization_id=group_authority.organization_id,
        file_registry_id=record.id,
        custody_mode="group_library",
        library_scope=GROUP_LIBRARY_SCOPE,
        status=ACTIVE_STATUS,
        added_by_user_id=user_id,
        is_discoverable=True,
        allow_ai_query=True,
        classification=(
            getattr(record, "classification", None)
            or "internal"
        ),
        policy_version=DEFAULT_POLICY_VERSION,
    )
    db_session.add(custody)
    db_session.flush()

    return custody


# -------------------------------------------------------------------
# Public Bootstrap API
# -------------------------------------------------------------------
def bootstrap_group_account(
    *,
    user_id: int,
    group_name: str,
    group_slug: str,
    include_user_files: bool,
    file_ids: list[int],
    document_ids: list[str],
) -> dict:
    clean_user_id = int(user_id or 0)

    if not clean_user_id:
        raise RuntimeError("A valid user id is required.")

    db_session = SessionLocal()

    try:
        user = db_session.get(User, clean_user_id)

        if not _user_is_active(user):
            raise RuntimeError(
                f"User {clean_user_id} was not found or is inactive."
            )

        group_authority = _get_or_create_group_authority(
            db_session,
            group_name=group_name,
            group_slug=group_slug,
            user_id=clean_user_id,
        )
        membership = _get_or_create_owner_membership(
            db_session,
            group_authority=group_authority,
            user_id=clean_user_id,
        )
        records = _resolve_requested_files(
            db_session,
            user_id=clean_user_id,
            include_user_files=include_user_files,
            file_ids=file_ids,
            document_ids=document_ids,
        )

        custody_rows = [
            _place_file_in_group_library(
                db_session,
                group_authority=group_authority,
                record=record,
                user_id=clean_user_id,
            )
            for record in records
        ]

        db_session.commit()

        return {
            "group_id": group_authority.organization_id,
            "group_name": group_authority.name,
            "group_slug": group_authority.slug,
            "organization_id": group_authority.organization_id,
            "membership_id": membership.id,
            "membership_role": membership.role,
            "custody_count": len(custody_rows),
            "custody_file_ids": [
                custody.file_registry_id
                for custody in custody_rows
            ],
        }

    except Exception:
        db_session.rollback()
        raise
    finally:
        SessionLocal.remove()


# -------------------------------------------------------------------
# Command Line Interface
# -------------------------------------------------------------------
def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Create or repair one group account, owner membership, "
            "and optional group-library file custody."
        )
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--group-name",
        default=DEFAULT_GROUP_NAME,
    )
    parser.add_argument(
        "--group-slug",
        default="",
    )
    parser.add_argument(
        "--include-user-files",
        action="store_true",
        help=(
            "Place all active files uploaded by the user into the "
            "group library."
        ),
    )
    parser.add_argument(
        "--file-id",
        action="append",
        type=int,
        default=[],
        help="FileRegistry integer id to place into group custody.",
    )
    parser.add_argument(
        "--document-id",
        action="append",
        default=[],
        help=(
            "FileRegistry random_name/document id to place into "
            "group custody."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    result = bootstrap_group_account(
        user_id=args.user_id,
        group_name=args.group_name,
        group_slug=args.group_slug,
        include_user_files=args.include_user_files,
        file_ids=args.file_id,
        document_ids=args.document_id,
    )

    print("Group account bootstrap completed.")
    print(f"group_id={result['group_id']}")
    print(f"group_name={result['group_name']}")
    print(f"group_slug={result['group_slug']}")
    print(f"membership_id={result['membership_id']}")
    print(f"membership_role={result['membership_role']}")
    print(f"custody_count={result['custody_count']}")
    print(f"custody_file_ids={result['custody_file_ids']}")


if __name__ == "__main__":
    main()
