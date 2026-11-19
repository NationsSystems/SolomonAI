# -------------------------------------------------------------------
# FILE: db.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# Central SQLAlchemy engine and session manager for Solomon.
#
# Provides the unified SQLAlchemy engine, scoped session factory,
# ORM base, and legacy task-history compatibility helpers.
#
# IMPORTANT:
#   This file must NOT import solomon_core.models at top level.
#   Models import Base from here, so application models are imported
#   inside init_db() only.
# -------------------------------------------------------------------

from datetime import datetime
import json
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    text,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import (
    declarative_base,
    scoped_session,
    sessionmaker,
)

from config import settings


# ---------------------------------------------------
# Engine Configuration
# ---------------------------------------------------
engine = create_engine(
    settings.SQLALCHEMY_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT_SECONDS,
    pool_recycle=settings.DB_POOL_RECYCLE_SECONDS,
    pool_use_lifo=settings.DB_POOL_USE_LIFO,
    pool_reset_on_return="rollback",
)


# Thread-local scoped session factory.
#
# Each request or worker thread receives its own current session. The
# scoped registry must be removed after use so connections return to
# the bounded pool and ORM state cannot leak into another request.
SessionLocal = scoped_session(
    sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )
)


# ORM base class
Base = declarative_base()


# ---------------------------------------------------
# Legacy Task History Compatibility Surface
# ---------------------------------------------------
_task_history_legacy_metadata = MetaData()
_task_history_legacy_table = Table(
    "task_history",
    _task_history_legacy_metadata,
    Column("id", Integer, primary_key=True),
    Column("task_id", String(64)),
    Column("user", String(64)),
    Column("intent", String(255)),
    Column("entities", JSON),
    Column("result", Text),
    Column("success", Boolean),
    Column("error_type", String(255)),
    Column("reasoning_source", String(255)),
    Column("confidence", Float),
    Column("duration_ms", Integer),
    Column("created_at", DateTime),
    Column("updated_at", DateTime),
)


class TaskHistory:
    """Legacy query facade for task_history without owning ORM metadata."""

    id = _task_history_legacy_table.c.id
    task_id = _task_history_legacy_table.c.task_id
    user = _task_history_legacy_table.c.user
    intent = _task_history_legacy_table.c.intent
    entities = _task_history_legacy_table.c.entities
    result = _task_history_legacy_table.c.result
    success = _task_history_legacy_table.c.success
    error_type = _task_history_legacy_table.c.error_type
    reasoning_source = _task_history_legacy_table.c.reasoning_source
    confidence = _task_history_legacy_table.c.confidence
    duration_ms = _task_history_legacy_table.c.duration_ms
    created_at = _task_history_legacy_table.c.created_at
    updated_at = _task_history_legacy_table.c.updated_at


# ---------------------------------------------------
# Skill ORM — Legacy Persistent Skill Table
# ---------------------------------------------------
class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, index=True)
    code = Column(Text)
    description = Column(Text)
    origin = Column(String(64))
    created_at = Column(DateTime, default=datetime.utcnow)

    last_used = Column(DateTime)
    usage_count = Column(Integer, default=0)

    version = Column(Integer, default=1)
    upgrade_available = Column(Boolean, default=False)


# ---------------------------------------------------
# Database Integrity Helpers
# ---------------------------------------------------
def _table_exists(table_name: str) -> bool:
    inspector = inspect(engine)
    return bool(
        inspector.has_table(table_name)
    )


def _index_exists(
    *,
    table_name: str,
    index_name: str,
) -> bool:
    inspector = inspect(engine)

    try:
        indexes = inspector.get_indexes(table_name)
    except SQLAlchemyError:
        return False

    return any(
        str(index.get("name") or "") == index_name
        for index in indexes
    )


def _constraint_exists(
    *,
    table_name: str,
    constraint_name: str,
) -> bool:
    inspector = inspect(engine)

    try:
        constraints = inspector.get_unique_constraints(table_name)
    except SQLAlchemyError:
        return False

    return any(
        str(constraint.get("name") or "") == constraint_name
        for constraint in constraints
    )


def _has_duplicate_user_emails() -> bool:
    """
    Detect duplicate normalized user emails before adding identity indexes.

    This check intentionally lowercases and trims email values so historical
    data cannot bypass the professional identity rule through case or whitespace.
    """

    if not _table_exists("users"):
        return False

    with engine.connect() as connection:
        result = connection.execute(
            text(
                """
                SELECT LOWER(TRIM(email)) AS normalized_email, COUNT(*) AS row_count
                FROM users
                WHERE email IS NOT NULL AND TRIM(email) <> ''
                GROUP BY LOWER(TRIM(email))
                HAVING COUNT(*) > 1
                LIMIT 1
                """
            )
        ).first()

    return result is not None


def _ensure_users_email_unique_index() -> None:
    """
    Ensure the live database enforces one user account per email address.

    SQLAlchemy create_all() does not retrofit indexes onto existing tables.
    This helper closes that gap for the already-running SolomonV3 database.
    """

    if not _table_exists("users"):
        return

    # Existing model-generated names may vary by database backend, so accept
    # either the expected explicit index or any unique constraint on email.
    if (
        _index_exists(
            table_name="users",
            index_name="uq_users_email_identity",
        )
        or _constraint_exists(
            table_name="users",
            constraint_name="email",
        )
    ):
        return

    inspector = inspect(engine)

    try:
        existing_indexes = inspector.get_indexes("users")
        for existing_index in existing_indexes:
            column_names = list(
                existing_index.get("column_names")
                or []
            )

            if (
                existing_index.get("unique")
                and column_names == ["email"]
            ):
                return
    except SQLAlchemyError:
        pass

    if _has_duplicate_user_emails():
        print(
            "[DB][IDENTITY] Duplicate user emails were found. "
            "The unique email index was not created. Resolve duplicates, "
            "then restart Solomon."
        )
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                CREATE UNIQUE INDEX uq_users_email_identity
                ON users (email)
                """
            )
        )

    print(
        "[DB][IDENTITY] users.email unique identity index verified/created."
    )


def _ensure_users_password_hash_nullable() -> None:
    """Allow a Solomon person to exist without a password credential.

    External authentication providers attach to the same users row. Existing
    password users keep their hashes; this migration only permits NULL for a
    future provider-only identity.
    """

    if not _table_exists("users"):
        return

    inspector = inspect(engine)
    columns = {
        str(column.get("name") or ""): column
        for column in inspector.get_columns("users")
    }
    password_column = columns.get("password_hash")

    if not password_column or bool(password_column.get("nullable")):
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE users
                MODIFY COLUMN password_hash VARCHAR(255) NULL
                """
            )
        )

    print(
        "[DB][IDENTITY] users.password_hash now permits provider-only identities."
    )


def _ensure_identity_constraints() -> None:
    """
    Verify identity constraints required by professional authentication.

    Identity rule:
      - one normalized email should map to one users row
      - password is an optional credential, not the person identity
      - organizations are attached through memberships, not duplicate users
    """

    try:
        _ensure_users_email_unique_index()
    except SQLAlchemyError as exc:
        print(
            "[DB][IDENTITY] Warning: Could not verify users.email "
            f"unique identity index: {exc}"
        )

    try:
        _ensure_users_password_hash_nullable()
    except SQLAlchemyError as exc:
        print(
            "[DB][IDENTITY] Warning: Could not make users.password_hash "
            f"nullable for provider-only identities: {exc}"
        )


def _ensure_organization_group_description_column() -> None:
    """
    Ensure existing databases expose the commercial Group description field.

    SQLAlchemy create_all() creates the column for new installations but does
    not alter an already-existing organization_groups table.
    """

    if not _table_exists("organization_groups"):
        return

    inspector = inspect(engine)

    try:
        existing_columns = {
            str(column.get("name") or "")
            for column in inspector.get_columns("organization_groups")
        }
    except SQLAlchemyError:
        return

    if "description" in existing_columns:
        return

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                ALTER TABLE organization_groups
                ADD COLUMN description VARCHAR(1024) NULL
                """
            )
        )

    print(
        "[DB][PEOPLE] organization_groups.description verified/created."
    )


def _ensure_people_group_schema() -> None:
    """Verify additive schema required by the People and Groups workspace."""

    try:
        _ensure_organization_group_description_column()
    except SQLAlchemyError as exc:
        print(
            "[DB][PEOPLE] Warning: Could not verify organization group "
            f"description column: {exc}"
        )


def _ensure_file_grant_download_columns() -> None:
    """Ensure existing grant tables expose Owner-controlled download policy."""

    for table_name in (
        "file_access_grants",
        "file_group_access_grants",
    ):
        if not _table_exists(table_name):
            continue

        inspector = inspect(engine)
        try:
            existing_columns = {
                str(column.get("name") or "")
                for column in inspector.get_columns(table_name)
            }
        except SQLAlchemyError:
            continue

        if "allow_download" in existing_columns:
            continue

        with engine.begin() as connection:
            connection.execute(
                text(
                    f"""
                    ALTER TABLE {table_name}
                    ADD COLUMN allow_download BOOLEAN NOT NULL DEFAULT 1
                    """
                )
            )

        print(
            f"[DB][PERMISSIONS] {table_name}.allow_download verified/created."
        )


def _ensure_file_version_provenance_schema() -> None:
    """Ensure durable file-version lineage and actor attribution exist."""

    if not _table_exists("file_registry"):
        return

    inspector = inspect(engine)
    existing_columns = {
        str(column.get("name") or "")
        for column in inspector.get_columns("file_registry")
    }
    existing_indexes = {
        str(index.get("name") or "")
        for index in inspector.get_indexes("file_registry")
    }

    with engine.begin() as connection:
        if "version_lineage_id" not in existing_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE file_registry
                    ADD COLUMN version_lineage_id VARCHAR(64) NULL
                    """
                )
            )

        if "version_created_by_user_id" not in existing_columns:
            connection.execute(
                text(
                    """
                    ALTER TABLE file_registry
                    ADD COLUMN version_created_by_user_id INT NULL
                    """
                )
            )

        connection.execute(
            text(
                """
                UPDATE file_registry
                SET version_lineage_id = CASE
                        WHEN version_lineage_id IS NULL
                             OR version_lineage_id = ''
                            THEN random_name
                        ELSE version_lineage_id
                    END,
                    version_created_by_user_id = COALESCE(
                        version_created_by_user_id,
                        uploader_id
                    )
                WHERE version_lineage_id IS NULL
                   OR version_lineage_id = ''
                   OR version_created_by_user_id IS NULL
                """
            )
        )

        connection.execute(
            text(
                """
                ALTER TABLE file_registry
                MODIFY COLUMN version_lineage_id VARCHAR(64) NOT NULL
                """
            )
        )

        if "ix_file_registry_version_lineage_id" not in existing_indexes:
            connection.execute(
                text(
                    """
                    CREATE INDEX ix_file_registry_version_lineage_id
                    ON file_registry (version_lineage_id)
                    """
                )
            )

        if (
            "ix_file_registry_version_created_by_user_id"
            not in existing_indexes
        ):
            connection.execute(
                text(
                    """
                    CREATE INDEX ix_file_registry_version_created_by_user_id
                    ON file_registry (version_created_by_user_id)
                    """
                )
            )

        if _table_exists("file_version_history"):
            connection.execute(
                text(
                    """
                    INSERT INTO file_version_history (
                        file_registry_id,
                        version_lineage_id,
                        version_number,
                        original_name,
                        extension,
                        path,
                        size_bytes,
                        checksum,
                        version_created_by_user_id,
                        version_created_at
                    )
                    SELECT
                        fr.id,
                        fr.version_lineage_id,
                        fr.version_number,
                        fr.original_name,
                        fr.extension,
                        fr.path,
                        fr.size_bytes,
                        fr.checksum,
                        fr.version_created_by_user_id,
                        COALESCE(fr.updated_at, fr.upload_time, UTC_TIMESTAMP())
                    FROM file_registry AS fr
                    WHERE NOT EXISTS (
                        SELECT 1
                        FROM file_version_history AS fvh
                        WHERE fvh.file_registry_id = fr.id
                          AND fvh.version_number = fr.version_number
                    )
                    """
                )
            )

    print("[DB][PERMISSIONS] File version provenance verified/seeded.")

def _ensure_permission_schema() -> None:
    """Verify additive schema required by the canonical permission matrix."""

    try:
        _ensure_file_grant_download_columns()
        _ensure_file_version_provenance_schema()
    except SQLAlchemyError as exc:
        print(
            "[DB][PERMISSIONS] Warning: Could not verify canonical permission "
            f"schema: {exc}"
        )


# ---------------------------------------------------
# Database Initialization
# ---------------------------------------------------
def init_db() -> None:
    """
    Create application tables that do not already exist.

    Importing solomon_core.models inside this function prevents the
    circular import that would occur if application models were loaded
    before Base was defined.
    """

    import solomon_core.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_identity_constraints()
    _ensure_people_group_schema()
    _ensure_permission_schema()


# ---------------------------------------------------
# Scoped Session Cleanup
# ---------------------------------------------------
def remove_db_session(_exception: Optional[BaseException] = None) -> None:
    """
    Remove the current scoped session and return its connection to the pool.

    This function is compatible with Flask teardown callbacks. SQLAlchemy
    rolls back any uncommitted transaction before the pooled connection is
    made available to another request.
    """

    SessionLocal.remove()


def register_database_teardown(app: Any) -> None:
    """
    Register request-context database cleanup on a Flask application.

    Registration is idempotent so repeated application bootstrap calls do
    not install duplicate teardown handlers.
    """

    extension_key = "solomon_database_teardown"

    if app.extensions.get(extension_key):
        return

    app.teardown_appcontext(remove_db_session)
    app.extensions[extension_key] = True


# ---------------------------------------------------
# Task Logging Utility
# ---------------------------------------------------
def log_task_to_db(
    task_id: str,
    user: str,
    intent: str,
    entities: dict,
    result: str,
    success: bool,
    error_type: Optional[str] = None,
    reasoning_source: Optional[str] = None,
    confidence: Optional[float] = None,
    duration_ms: Optional[int] = None,
) -> None:
    """Insert one legacy task execution record without ORM table ownership."""

    session = SessionLocal()

    try:
        session.execute(
            text(
                """
                INSERT INTO task_history (
                    task_id,
                    user,
                    intent,
                    entities,
                    result,
                    success,
                    error_type,
                    reasoning_source,
                    confidence,
                    duration_ms,
                    created_at,
                    updated_at
                )
                VALUES (
                    :task_id,
                    :user,
                    :intent,
                    :entities,
                    :result,
                    :success,
                    :error_type,
                    :reasoning_source,
                    :confidence,
                    :duration_ms,
                    :created_at,
                    :updated_at
                )
                """
            ),
            {
                "task_id": task_id,
                "user": str(user or "0"),
                "intent": intent,
                "entities": json.dumps(
                    entities or {},
                    ensure_ascii=False,
                ),
                "result": result,
                "success": bool(success),
                "error_type": error_type,
                "reasoning_source": reasoning_source,
                "confidence": confidence,
                "duration_ms": duration_ms,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            },
        )
        session.commit()
    except Exception as exc:
        session.rollback()
        print(
            f"[DB] Warning: Failed to log task {task_id}: {exc}"
        )
    finally:
        SessionLocal.remove()


# ---------------------------------------------------
# Dependency Helper
# ---------------------------------------------------
def get_db():
    """
    Yield the current scoped database session.

    The scoped registry is removed after the caller finishes so the
    connection and ORM identity state cannot remain attached to the
    current worker thread.
    """

    db = SessionLocal()

    try:
        yield db
    finally:
        SessionLocal.remove()