# -------------------------------------------------------------------
# FILE: schema_migrator.py
# DIRECTORY: solomon_core/solomon_tools/
# -------------------------------------------------------------------
# Non-destructive Solomon database schema upgrade utilities.
#
# This module applies additive production schema changes and explicit
# symbolic-value normalizations against the same SQLAlchemy database
# authority used by the Solomon runtime.
# -------------------------------------------------------------------

from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Iterable

from sqlalchemy import inspect, text


# -------------------------------------------------------------------
# Project Import Path
# -------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from solomon_core.db import Base, engine  # noqa: E402


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_identifier(identifier: str) -> str:
    """
    Return a safely quoted SQL identifier.

    Identifiers are internal constants only. Validation prevents accidental
    SQL injection if this helper is reused incorrectly later.
    """

    if not _IDENTIFIER_PATTERN.match(identifier or ""):
        raise ValueError(f"Unsafe SQL identifier: {identifier!r}")

    return f"`{identifier}`"


def _current_database_name(connection) -> str:
    result = connection.execute(
        text("SELECT DATABASE()")
    ).scalar()

    return str(result or "").strip()


def table_exists(connection, table_name: str) -> bool:
    """Return True when the active database contains the table."""

    database_name = _current_database_name(connection)

    if not database_name:
        return False

    result = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = :database_name
              AND table_name = :table_name
            """
        ),
        {
            "database_name": database_name,
            "table_name": table_name,
        },
    ).scalar()

    return bool(result)


def column_exists(connection, table_name: str, column_name: str) -> bool:
    """Return True when the active database table contains the column."""

    database_name = _current_database_name(connection)

    if not database_name:
        return False

    result = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM information_schema.columns
            WHERE table_schema = :database_name
              AND table_name = :table_name
              AND column_name = :column_name
            """
        ),
        {
            "database_name": database_name,
            "table_name": table_name,
            "column_name": column_name,
        },
    ).scalar()

    return bool(result)


def index_exists(connection, table_name: str, index_name: str) -> bool:
    """Return True when the active database table contains the index."""

    database_name = _current_database_name(connection)

    if not database_name:
        return False

    result = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM information_schema.statistics
            WHERE table_schema = :database_name
              AND table_name = :table_name
              AND index_name = :index_name
            """
        ),
        {
            "database_name": database_name,
            "table_name": table_name,
            "index_name": index_name,
        },
    ).scalar()

    return bool(result)


def add_column_if_missing(
    connection,
    table_name: str,
    column_name: str,
    column_def: str,
) -> str:
    """
    Add a nullable or defaulted column if it does not already exist.

    This function never drops, renames, narrows, or rewrites existing data.
    """

    if not table_exists(connection, table_name):
        return f"Table '{table_name}' not found; skipped column '{column_name}'."

    if column_exists(connection, table_name, column_name):
        return f"Column '{column_name}' already exists in '{table_name}'."

    table_sql = _quote_identifier(table_name)
    column_sql = _quote_identifier(column_name)

    connection.execute(
        text(
            f"ALTER TABLE {table_sql} "
            f"ADD COLUMN {column_sql} {column_def}"
        )
    )

    return f"Added column '{column_name}' to '{table_name}'."


def add_index_if_missing(
    connection,
    table_name: str,
    index_name: str,
    column_names: Iterable[str],
) -> str:
    """Create a non-unique index if the table and columns exist."""

    clean_columns = [
        str(column_name or "").strip()
        for column_name in column_names
        if str(column_name or "").strip()
    ]

    if not clean_columns:
        return f"Index '{index_name}' skipped; no columns provided."

    if not table_exists(connection, table_name):
        return f"Table '{table_name}' not found; skipped index '{index_name}'."

    missing_columns = [
        column_name
        for column_name in clean_columns
        if not column_exists(connection, table_name, column_name)
    ]

    if missing_columns:
        return (
            f"Index '{index_name}' skipped; missing columns on "
            f"'{table_name}': {', '.join(missing_columns)}."
        )

    if index_exists(connection, table_name, index_name):
        return f"Index '{index_name}' already exists on '{table_name}'."

    table_sql = _quote_identifier(table_name)
    index_sql = _quote_identifier(index_name)
    columns_sql = ", ".join(
        _quote_identifier(column_name)
        for column_name in clean_columns
    )

    connection.execute(
        text(
            f"CREATE INDEX {index_sql} "
            f"ON {table_sql} ({columns_sql})"
        )
    )

    return f"Added index '{index_name}' to '{table_name}'."


def add_unique_index_if_missing(
    connection,
    table_name: str,
    index_name: str,
    column_names: Iterable[str],
) -> str:
    """
    Create a unique index if the table and columns exist.

    This is additive and idempotent. Existing duplicate data can still cause
    the database to reject the unique index; that failure should remain visible
    because silently weakening identity constraints is unsafe.
    """

    clean_columns = [
        str(column_name or "").strip()
        for column_name in column_names
        if str(column_name or "").strip()
    ]

    if not clean_columns:
        return f"Unique index '{index_name}' skipped; no columns provided."

    if not table_exists(connection, table_name):
        return (
            f"Table '{table_name}' not found; "
            f"skipped unique index '{index_name}'."
        )

    missing_columns = [
        column_name
        for column_name in clean_columns
        if not column_exists(connection, table_name, column_name)
    ]

    if missing_columns:
        return (
            f"Unique index '{index_name}' skipped; missing columns on "
            f"'{table_name}': {', '.join(missing_columns)}."
        )

    if index_exists(connection, table_name, index_name):
        return f"Unique index '{index_name}' already exists on '{table_name}'."

    table_sql = _quote_identifier(table_name)
    index_sql = _quote_identifier(index_name)
    columns_sql = ", ".join(
        _quote_identifier(column_name)
        for column_name in clean_columns
    )

    connection.execute(
        text(
            f"CREATE UNIQUE INDEX {index_sql} "
            f"ON {table_sql} ({columns_sql})"
        )
    )

    return f"Added unique index '{index_name}' to '{table_name}'."


def _sql_string_literal(value: str) -> str:
    """Return a single-quoted SQL literal for trusted internal strings."""

    clean_value = str(value or "")
    return "'" + clean_value.replace("'", "''") + "'"


def set_column_default_if_present(
    connection,
    table_name: str,
    column_name: str,
    default_value: str,
) -> str:
    """
    Set a column default when the table and column already exist.

    This is a metadata-only alignment step for canonical symbolic defaults.
    """

    if not table_exists(connection, table_name):
        return (
            f"Table '{table_name}' not found; "
            f"skipped default for '{column_name}'."
        )

    if not column_exists(connection, table_name, column_name):
        return (
            f"Column '{column_name}' not found in '{table_name}'; "
            "skipped default update."
        )

    table_sql = _quote_identifier(table_name)
    column_sql = _quote_identifier(column_name)
    default_sql = _sql_string_literal(default_value)

    connection.execute(
        text(
            f"ALTER TABLE {table_sql} "
            f"ALTER COLUMN {column_sql} SET DEFAULT {default_sql}"
        )
    )

    return (
        f"Set default for '{table_name}.{column_name}' "
        f"to '{default_value}'."
    )


def update_exact_value_if_present(
    connection,
    table_name: str,
    column_name: str,
    old_value: str,
    new_value: str,
) -> str:
    """
    Normalize an exact retired symbolic value when the column exists.

    Only exact controlled enum-like labels are updated. Free-form data is not
    rewritten by this helper.
    """

    if not table_exists(connection, table_name):
        return (
            f"Table '{table_name}' not found; skipped value normalization "
            f"for '{column_name}'."
        )

    if not column_exists(connection, table_name, column_name):
        return (
            f"Column '{column_name}' not found in '{table_name}'; "
            "skipped value normalization."
        )

    table_sql = _quote_identifier(table_name)
    column_sql = _quote_identifier(column_name)

    result = connection.execute(
        text(
            f"UPDATE {table_sql} "
            f"SET {column_sql} = :new_value "
            f"WHERE {column_sql} = :old_value"
        ),
        {
            "old_value": old_value,
            "new_value": new_value,
        },
    )

    return (
        f"Normalized {result.rowcount or 0} row(s) in "
        f"'{table_name}.{column_name}' from '{old_value}' "
        f"to '{new_value}'."
    )


def _ensure_model_tables() -> str:
    """
    Create any missing ORM tables.

    Existing tables are left untouched here; missing columns are handled by
    the explicit additive column checks below.
    """

    import solomon_core.models  # noqa: F401

    inspector = inspect(engine)
    known_tables_before = set(inspector.get_table_names())

    Base.metadata.create_all(bind=engine)

    refreshed_inspector = inspect(engine)
    known_tables_after = set(refreshed_inspector.get_table_names())

    created_tables = sorted(
        known_tables_after - known_tables_before
    )

    if not created_tables:
        return "No missing ORM tables found."

    return "Created missing ORM tables: " + ", ".join(created_tables) + "."


def _apply_user_account_updates(connection) -> list[str]:
    actions: list[str] = []

    actions.append(
        add_column_if_missing(
            connection,
            "users",
            "account_package",
            "VARCHAR(32) NOT NULL DEFAULT 'personal'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "users",
            "account_package_updated_at",
            "DATETIME NULL",
        )
    )

    actions.append(
        add_index_if_missing(
            connection,
            "users",
            "ix_users_account_package",
            ["account_package"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "users",
            "ix_users_account_package_updated_at",
            ["account_package_updated_at"],
        )
    )

    return actions


def _apply_file_registry_updates(connection) -> list[str]:
    actions: list[str] = []

    actions.append(
        add_column_if_missing(
            connection,
            "file_registry",
            "status",
            "VARCHAR(32) NOT NULL DEFAULT 'active'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_registry",
            "classification",
            "VARCHAR(32) NOT NULL DEFAULT 'internal'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_registry",
            "version_number",
            "INT NOT NULL DEFAULT 1",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_registry",
            "archived_at",
            "DATETIME NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_registry",
            "deleted_at",
            "DATETIME NULL",
        )
    )

    actions.append(
        add_index_if_missing(
            connection,
            "file_registry",
            "ix_file_registry_status",
            ["status"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_registry",
            "ix_file_registry_classification",
            ["classification"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_registry",
            "ix_file_registry_archived_at",
            ["archived_at"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_registry",
            "ix_file_registry_deleted_at",
            ["deleted_at"],
        )
    )

    return actions


def _apply_organization_updates(connection) -> list[str]:
    actions: list[str] = []

    actions.append(
        add_column_if_missing(
            connection,
            "organizations",
            "legal_name",
            "VARCHAR(255) NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organizations",
            "verified_domain",
            "VARCHAR(255) NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organizations",
            "verification_status",
            "VARCHAR(32) NOT NULL DEFAULT 'unverified'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organizations",
            "verification_updated_at",
            "DATETIME NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organizations",
            "authorization_policy_version",
            "VARCHAR(64) NOT NULL "
            "DEFAULT 'group_file_permissions_v1'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organizations",
            "default_file_visibility",
            "VARCHAR(64) NOT NULL DEFAULT 'group_library'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organizations",
            "ai_query_enabled",
            "TINYINT(1) NOT NULL DEFAULT 1",
        )
    )

    actions.append(
        set_column_default_if_present(
            connection,
            "organizations",
            "authorization_policy_version",
            "group_file_permissions_v1",
        )
    )
    actions.append(
        set_column_default_if_present(
            connection,
            "organizations",
            "default_file_visibility",
            "group_library",
        )
    )

    actions.append(
        add_index_if_missing(
            connection,
            "organizations",
            "ix_organizations_verified_domain",
            ["verified_domain"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organizations",
            "ix_organizations_verification_status",
            ["verification_status"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organizations",
            "ix_organizations_default_file_visibility",
            ["default_file_visibility"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organizations",
            "ix_organizations_ai_query_enabled",
            ["ai_query_enabled"],
        )
    )

    return actions


def _apply_organization_invitation_updates(connection) -> list[str]:
    actions: list[str] = []

    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "invitation_id",
            "VARCHAR(64) NOT NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "organization_id",
            "VARCHAR(64) NOT NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "membership_id",
            "INT NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "email",
            "VARCHAR(255) NOT NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "normalized_email",
            "VARCHAR(255) NOT NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "role",
            "VARCHAR(32) NOT NULL DEFAULT 'member'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "status",
            "VARCHAR(32) NOT NULL DEFAULT 'pending'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "token_hash",
            "VARCHAR(128) NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "invitation_contract",
            "VARCHAR(128) NOT NULL "
            "DEFAULT 'group_membership_invitation_v1'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "invited_by_user_id",
            "INT NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "accepted_by_user_id",
            "INT NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "revoked_by_user_id",
            "INT NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "expires_at",
            "DATETIME NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "accepted_at",
            "DATETIME NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "revoked_at",
            "DATETIME NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "revocation_reason",
            "VARCHAR(255) NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "created_at",
            "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_invitations",
            "updated_at",
            "DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP",
        )
    )

    actions.append(
        set_column_default_if_present(
            connection,
            "organization_invitations",
            "invitation_contract",
            "group_membership_invitation_v1",
        )
    )

    actions.append(
        add_unique_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitations_invitation_id",
            ["invitation_id"],
        )
    )
    actions.append(
        add_unique_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitations_token_hash",
            ["token_hash"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitation_org_email_status",
            ["organization_id", "normalized_email", "status"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitation_email_status",
            ["normalized_email", "status"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitation_token_status",
            ["token_hash", "status"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitations_membership_id",
            ["membership_id"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitations_invited_by_user_id",
            ["invited_by_user_id"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitations_accepted_by_user_id",
            ["accepted_by_user_id"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitations_revoked_by_user_id",
            ["revoked_by_user_id"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitations_expires_at",
            ["expires_at"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitations_accepted_at",
            ["accepted_at"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitations_revoked_at",
            ["revoked_at"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_invitations",
            "ix_organization_invitations_created_at",
            ["created_at"],
        )
    )

    return actions


def _apply_organization_file_custody_updates(connection) -> list[str]:
    actions: list[str] = []

    actions.append(
        add_column_if_missing(
            connection,
            "organization_file_custody",
            "custody_mode",
            "VARCHAR(64) NOT NULL DEFAULT 'group_controlled'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_file_custody",
            "library_scope",
            "VARCHAR(64) NOT NULL DEFAULT 'group_library'",
        )
    )

    actions.append(
        add_column_if_missing(
            connection,
            "organization_file_custody",
            "is_discoverable",
            "TINYINT(1) NOT NULL DEFAULT 1",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_file_custody",
            "allow_ai_query",
            "TINYINT(1) NOT NULL DEFAULT 1",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_file_custody",
            "classification",
            "VARCHAR(32) NOT NULL DEFAULT 'internal'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "organization_file_custody",
            "policy_version",
            "VARCHAR(64) NOT NULL "
            "DEFAULT 'group_file_permissions_v1'",
        )
    )

    actions.append(
        set_column_default_if_present(
            connection,
            "organization_file_custody",
            "custody_mode",
            "group_controlled",
        )
    )
    actions.append(
        set_column_default_if_present(
            connection,
            "organization_file_custody",
            "library_scope",
            "group_library",
        )
    )
    actions.append(
        set_column_default_if_present(
            connection,
            "organization_file_custody",
            "policy_version",
            "group_file_permissions_v1",
        )
    )

    actions.append(
        add_index_if_missing(
            connection,
            "organization_file_custody",
            "ix_organization_file_custody_is_discoverable",
            ["is_discoverable"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_file_custody",
            "ix_organization_file_custody_allow_ai_query",
            ["allow_ai_query"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_file_custody",
            "ix_organization_file_custody_classification",
            ["classification"],
        )
    )

    return actions


def _apply_file_access_grant_updates(connection) -> list[str]:
    actions: list[str] = []

    actions.append(
        add_column_if_missing(
            connection,
            "file_access_grants",
            "is_discoverable",
            "TINYINT(1) NOT NULL DEFAULT 1",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_access_grants",
            "allow_ai_query",
            "TINYINT(1) NOT NULL DEFAULT 1",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_access_grants",
            "policy_version",
            "VARCHAR(64) NOT NULL "
            "DEFAULT 'group_file_permissions_v1'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_access_grants",
            "expires_at",
            "DATETIME NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_access_grants",
            "revoked_by_user_id",
            "INT NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_access_grants",
            "revocation_reason",
            "VARCHAR(255) NULL",
        )
    )

    actions.append(
        set_column_default_if_present(
            connection,
            "file_access_grants",
            "policy_version",
            "group_file_permissions_v1",
        )
    )

    actions.append(
        add_index_if_missing(
            connection,
            "file_access_grants",
            "ix_file_access_grants_is_discoverable",
            ["is_discoverable"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_access_grants",
            "ix_file_access_grants_allow_ai_query",
            ["allow_ai_query"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_access_grants",
            "ix_file_access_grants_expires_at",
            ["expires_at"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_access_grants",
            "ix_file_access_grants_revoked_by_user_id",
            ["revoked_by_user_id"],
        )
    )

    return actions


def _apply_file_group_access_grant_updates(connection) -> list[str]:
    actions: list[str] = []

    actions.append(
        add_column_if_missing(
            connection,
            "file_group_access_grants",
            "is_discoverable",
            "TINYINT(1) NOT NULL DEFAULT 1",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_group_access_grants",
            "allow_ai_query",
            "TINYINT(1) NOT NULL DEFAULT 1",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_group_access_grants",
            "policy_version",
            "VARCHAR(64) NOT NULL "
            "DEFAULT 'group_file_permissions_v1'",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_group_access_grants",
            "expires_at",
            "DATETIME NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_group_access_grants",
            "revoked_at",
            "DATETIME NULL",
        )
    )
    actions.append(
        add_column_if_missing(
            connection,
            "file_group_access_grants",
            "revocation_reason",
            "VARCHAR(255) NULL",
        )
    )

    actions.append(
        set_column_default_if_present(
            connection,
            "file_group_access_grants",
            "policy_version",
            "group_file_permissions_v1",
        )
    )

    actions.append(
        add_index_if_missing(
            connection,
            "file_group_access_grants",
            "ix_file_group_access_grants_is_discoverable",
            ["is_discoverable"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_group_access_grants",
            "ix_file_group_access_grants_allow_ai_query",
            ["allow_ai_query"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_group_access_grants",
            "ix_file_group_access_grants_expires_at",
            ["expires_at"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_group_access_grants",
            "ix_file_group_access_grants_revoked_at",
            ["revoked_at"],
        )
    )

    return actions


def _apply_group_table_safety_indexes(connection) -> list[str]:
    actions: list[str] = []

    actions.append(
        add_index_if_missing(
            connection,
            "organization_groups",
            "ix_organization_group_org_status",
            ["organization_id", "status"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "organization_group_memberships",
            "ix_organization_group_membership_user_status",
            ["user_id", "status"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_group_access_grants",
            "ix_file_group_access_grant_group_status",
            ["group_id", "status"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_group_access_grants",
            "ix_file_group_access_grant_org_status",
            ["organization_id", "status"],
        )
    )

    return actions


def _apply_authorization_audit_indexes(connection) -> list[str]:
    actions: list[str] = []

    actions.append(
        add_index_if_missing(
            connection,
            "file_authorization_decisions",
            "ix_file_authorization_actor_action_created",
            ["actor_user_id", "action", "created_at"],
        )
    )
    actions.append(
        add_index_if_missing(
            connection,
            "file_authorization_decisions",
            "ix_file_authorization_resource_action_created",
            ["file_registry_id", "action", "created_at"],
        )
    )

    return actions


def _apply_group_bridge_value_updates(connection) -> list[str]:
    actions: list[str] = []

    group_default_columns = [
        (
            "organizations",
            "default_file_visibility",
            "group_library",
        ),
        (
            "organization_file_custody",
            "library_scope",
            "group_library",
        ),
    ]

    group_policy_columns = [
        (
            "organizations",
            "authorization_policy_version",
            "group_file_permissions_v1",
        ),
        (
            "organization_file_custody",
            "policy_version",
            "group_file_permissions_v1",
        ),
        (
            "file_access_grants",
            "policy_version",
            "group_file_permissions_v1",
        ),
        (
            "file_group_access_grants",
            "policy_version",
            "group_file_permissions_v1",
        ),
        (
            "file_authorization_decisions",
            "policy_version",
            "group_file_permissions_v1",
        ),
    ]

    for table_name, column_name, default_value in group_default_columns:
        actions.append(
            set_column_default_if_present(
                connection,
                table_name,
                column_name,
                default_value,
            )
        )

    for table_name, column_name, default_value in group_policy_columns:
        actions.append(
            set_column_default_if_present(
                connection,
                table_name,
                column_name,
                default_value,
            )
        )

    actions.append(
        set_column_default_if_present(
            connection,
            "organization_invitations",
            "invitation_contract",
            "group_membership_invitation_v1",
        )
    )

    actions.append(
        update_exact_value_if_present(
            connection,
            "organizations",
            "default_file_visibility",
            "company_library",
            "group_library",
        )
    )
    actions.append(
        update_exact_value_if_present(
            connection,
            "organization_file_custody",
            "library_scope",
            "company_library",
            "group_library",
        )
    )

    for table_name, column_name, _default_value in group_policy_columns:
        actions.append(
            update_exact_value_if_present(
                connection,
                table_name,
                column_name,
                "organization_file_permissions_v1",
                "group_file_permissions_v1",
            )
        )

    actions.append(
        update_exact_value_if_present(
            connection,
            "organization_invitations",
            "invitation_contract",
            "organization_membership_invitation_v1",
            "group_membership_invitation_v1",
        )
    )
    actions.append(
        update_exact_value_if_present(
            connection,
            "organization_file_custody",
            "custody_mode",
            "organization_controlled",
            "group_controlled",
        )
    )
    actions.append(
        update_exact_value_if_present(
            connection,
            "file_group_access_grants",
            "grant_type",
            "organization_group",
            "group",
        )
    )
    actions.append(
        update_exact_value_if_present(
            connection,
            "file_authorization_decisions",
            "access_scope",
            "company_library",
            "group_library",
        )
    )

    return actions


def run_migrations() -> list[str]:
    """
    Run additive schema migrations against Solomon's active SQL database.

    This function is safe to call repeatedly. It creates missing ORM tables,
    adds missing columns, creates missing non-unique indexes, and normalizes
    exact retired symbolic values into the canonical People/Groups vocabulary.
    It never drops tables, drops columns, or renames physical database objects.
    """

    actions: list[str] = []

    try:
        actions.append(_ensure_model_tables())

        with engine.begin() as connection:
            actions.extend(
                _apply_user_account_updates(connection)
            )
            actions.extend(
                _apply_file_registry_updates(connection)
            )
            actions.extend(
                _apply_organization_updates(connection)
            )
            actions.extend(
                _apply_organization_invitation_updates(connection)
            )
            actions.extend(
                _apply_organization_file_custody_updates(connection)
            )
            actions.extend(
                _apply_file_access_grant_updates(connection)
            )
            actions.extend(
                _apply_file_group_access_grant_updates(connection)
            )
            actions.extend(
                _apply_group_table_safety_indexes(connection)
            )
            actions.extend(
                _apply_authorization_audit_indexes(connection)
            )
            actions.extend(
                _apply_group_bridge_value_updates(connection)
            )

        actions.append("Schema migrations completed successfully.")

    except Exception as exc:
        actions.append(f"Migration error: {exc}")

    return actions


if __name__ == "__main__":
    print("\n".join(run_migrations()))