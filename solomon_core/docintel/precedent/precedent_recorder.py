# solomon_core/docintel/precedent/precedent_recorder.py
# ---------------------------------------------------------------------------
# Precedent Recorder (Advisory Memory Only)
#
# Purpose:
#   Persist human-reviewed reconciliation outcomes so future runs
#   can surface advisory guidance.
#
# Authority:
#   • RECORD ONLY
#   • NEVER auto-apply
#   • NEVER modify reconciliation
#   • NEVER influence certification
#
# This is institutional memory, not execution authority.
# ---------------------------------------------------------------------------

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, DateTime, Text

from solomon_core.db import Base, SessionLocal
from solomon_core.logger import get_logger

logger = get_logger("precedent_recorder")


# ---------------------------------------------------------------------------
# ORM Model
# ---------------------------------------------------------------------------


class BEIPrecedent(Base):
    __tablename__ = "bei_precedents"

    id = Column(Integer, primary_key=True)

    fingerprint = Column(String(255), index=True, nullable=False)
    signal_type = Column(String(255), index=True, nullable=False)

    chosen_resolution = Column(Text, nullable=False)
    rationale = Column(Text)

    source_case = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Recorder
# ---------------------------------------------------------------------------


def record_precedent(
    fingerprint: str,
    signal_type: str,
    chosen_resolution: str,
    rationale: Optional[str] = None,
    source_case: Optional[str] = None,
):
    """
    Append a precedent record.

    This does NOT affect current execution.
    It exists purely for future advisory surfacing.
    """

    session = SessionLocal()

    try:
        record = BEIPrecedent(
            fingerprint=fingerprint,
            signal_type=signal_type,
            chosen_resolution=chosen_resolution,
            rationale=rationale,
            source_case=source_case,
        )

        session.add(record)
        session.commit()

        logger.info(
            "[PRECEDENT] recorded fingerprint=%s signal=%s",
            fingerprint,
            signal_type,
        )

    except Exception as e:
        session.rollback()
        logger.exception("[PRECEDENT] failed: %s", e)

    finally:
        session.close()
