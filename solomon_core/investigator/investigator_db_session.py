# solomon_core/investigator/investigator_db_session.py
# ------------------------------------------------------------------
# Investigator Database Session (Append-Only Authority)
#
# Location:
#   solomon_core/investigator/investigator_db_session.py
#
# Purpose:
#   Defines the dedicated SQLAlchemy engine and session bound to the
#   solomon_investigator DB user, enforcing append-only guarantees
#   at the database authority layer.
#
# Guarantees:
#   - Uses investigator-only DB credentials
#   - No UPDATE / DELETE / ALTER privileges possible
#   - Isolated from main application DB engine
#
# IMPORTANT:
#   This module is the ONLY source of DB sessions for Investigator
#   persistence. No other module may derive or modify credentials.
# ------------------------------------------------------------------

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from config import settings


# ------------------------------------------------------------------
# Investigator Engine (Append-Only)
# ------------------------------------------------------------------

investigator_engine = create_engine(
    settings.INVESTIGATOR_SQLALCHEMY_DATABASE_URL,
    echo=False,
    future=True,
    pool_pre_ping=True,
)


InvestigatorSession = sessionmaker(
    bind=investigator_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    future=True,
)
