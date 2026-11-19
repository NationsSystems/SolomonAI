# ---------------------------------------------------------------------------
# Precedent Lookup (Read-Only Intelligence Surface)
# solomon_core/investigator/precedent_lookup.py
#
# Purpose:
#   Retrieve historical human-confirmed resolutions for a fingerprint.
#
# Authority Model:
#   • Read-only
#   • Advisory only
#   • NEVER auto-applies
#
# This module does NOT:
#   • decide
#   • rank
#   • filter
#   • infer
# ---------------------------------------------------------------------------

from sqlalchemy import text

from solomon_core.logger import get_logger
from solomon_core.db import engine

logger = get_logger("precedent_lookup")


# ---------------------------------------------------------------------------

def lookup_precedents(fingerprint: str):
    """
    Return historical resolutions for this fingerprint.

    Always safe.
    Always advisory.
    """

    try:
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                    SELECT fingerprint, resolution, case_id, authority_actor, created_at
                    FROM precedent_records
                    WHERE fingerprint = :fingerprint
                    ORDER BY created_at DESC
                    """
                ),
                {"fingerprint": fingerprint},
            )

            rows = [dict(r._mapping) for r in result]

        logger.info(
            "[PRECEDENT LOOKUP] fingerprint=%s results=%s",
            fingerprint,
            len(rows),
        )

        return rows

    except Exception as e:
        logger.error(
            "[PRECEDENT LOOKUP] failed (non-blocking): %s",
            e,
        )
        return []
