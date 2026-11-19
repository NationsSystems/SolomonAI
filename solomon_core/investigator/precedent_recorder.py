# solomon_core/investigator/precedent_recorder.py
# ---------------------------------------------------------------------------
# Precedent Recorder (Append-Only)
#
# Purpose:
#   Persist human-confirmed conflict resolutions as historical records.
#
# Authority Model:
#   • Write-only
#   • Immutable
#   • Never blocks runtime authority
#
# This module does NOT:
#   • interpret
#   • recommend
#   • apply precedent
# ---------------------------------------------------------------------------

from datetime import datetime

from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal
from sqlalchemy import text

logger = get_logger("precedent_recorder")


# ---------------------------------------------------------------------------

def record_precedent(
    fingerprint: str,
    resolution: str,
    case_id: str,
    authority_actor: str,
):
    """
    Append a new precedent record.

    Failure to write must NEVER block the caller.
    """

    session = SessionLocal()

    try:
        session.execute(
            text(
                """
                INSERT INTO precedent_records
                    (fingerprint, resolution, case_id, authority_actor, created_at)
                VALUES
                    (:fingerprint, :resolution, :case_id, :authority_actor, :created_at)
                """
            ),
            {
                "fingerprint": fingerprint,
                "resolution": resolution,
                "case_id": case_id,
                "authority_actor": authority_actor,
                "created_at": datetime.utcnow(),
            },
        )

        session.commit()

        logger.info(
            "[PRECEDENT] recorded fingerprint=%s resolution=%s case=%s",
            fingerprint,
            resolution,
            case_id,
        )

    except Exception as e:
        session.rollback()

        # NEVER BLOCK AUTHORITY FLOW
        logger.error(
            "[PRECEDENT] failed to record (non-blocking): %s",
            e,
        )

    finally:
        session.close()
