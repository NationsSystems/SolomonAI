# -------------------------------------------------------------------
# FILE: env.py
# DIRECTORY: migrations/
# -------------------------------------------------------------------
# Alembic environment for Solomon.
#
# Connects Alembic to the same database configuration, ORM base, and
# application model metadata used by the Solomon runtime.
# -------------------------------------------------------------------

from logging.config import fileConfig
import os
import sys

from alembic import context
from sqlalchemy import engine_from_config, pool


# -------------------------------------------------------------------
# Project Import Path
# -------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# -------------------------------------------------------------------
# Solomon Configuration and Model Metadata
# -------------------------------------------------------------------
from config import settings
from solomon_core.db import Base
import solomon_core.models  # noqa: F401, E402


# Alembic configuration object.
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# All Solomon application models must be imported before this assignment.
target_metadata = Base.metadata

# Use the same authoritative database URL as the Solomon runtime.
config.set_main_option(
    "sqlalchemy.url",
    settings.SQLALCHEMY_DATABASE_URL,
)


# -------------------------------------------------------------------
# Offline Migration Execution
# -------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Generate or execute migrations without opening a DB connection."""

    context.configure(
        url=settings.SQLALCHEMY_DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# -------------------------------------------------------------------
# Online Migration Execution
# -------------------------------------------------------------------
def run_migrations_online() -> None:
    """Execute migrations using a dedicated non-pooled DB connection."""

    connectable = engine_from_config(
        {
            "sqlalchemy.url": settings.SQLALCHEMY_DATABASE_URL,
        },
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


# -------------------------------------------------------------------
# Alembic Entry Point
# -------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()