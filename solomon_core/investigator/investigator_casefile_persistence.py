# solomon_core/investigator/investigator_casefile_persistence.py
# ------------------------------------------------------------------
# Investigator CaseFile Persistence Adapter (Append-Only)
#
# Location:
#   solomon_core/investigator/investigator_casefile_persistence.py
#
# Purpose:
#   Writes immutable Investigator CaseFiles to durable storage.
#
# Guarantees:
#   - Uses investigator-only DB session
#   - Enforces append-only behavior at DB authority layer
#   - Isolated from the main application DB engine
# ------------------------------------------------------------------

import json
from datetime import datetime

from sqlalchemy import text

from solomon_core.investigator.investigator_casefile_types import CaseFile
from solomon_core.investigator.investigator_db_session import InvestigatorSession
from solomon_core.logger import get_logger

logger = get_logger("investigator.persistence")


# ------------------------------------------------------------------
# Serialization (Deterministic, Explicit)
# ------------------------------------------------------------------

def _serialize(obj):
    """
    Deterministic JSON serializer for CaseFile graphs.

    Rules:
    - datetime → ISO-8601 string
    - objects with __dict__ → dict (shallow)
    - lists / tuples → list
    - primitives pass through
    """
    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, (list, tuple)):
        return [_serialize(v) for v in obj]

    if hasattr(obj, "__dict__"):
        return {k: _serialize(v) for k, v in obj.__dict__.items()}

    return obj


def _resolve_request_id(casefile: CaseFile):
    request_id = getattr(casefile, "request_id", None)

    if request_id:
        return request_id

    request_context = getattr(casefile, "request_context", None)
    return getattr(request_context, "request_id", None)


# ------------------------------------------------------------------
# Persistence API
# ------------------------------------------------------------------

def persist_casefile(*, casefile: CaseFile) -> None:
    """
    Persist a single immutable CaseFile.

    Hard guarantees:
    - Exactly one INSERT
    - No UPDATE / DELETE possible at DB layer
    """

    request_id = _resolve_request_id(casefile)

    logger.debug(
        "[CASEFILE][PERSIST_ATTEMPT] request_id=%s case_id=%s archetype_id=%s",
        request_id,
        casefile.case_id,
        casefile.archetype_id,
    )

    casefile_json = json.dumps(
        _serialize(casefile),
        sort_keys=True,
        separators=(",", ":"),
    )

    db = InvestigatorSession()

    try:
        db.execute(
            text(
                """
                INSERT INTO investigator_casefiles (
                    case_id,
                    prior_case_id,
                    archetype_id,
                    casefile_version,
                    timestamp_emitted,
                    casefile_json
                )
                VALUES (
                    :case_id,
                    :prior_case_id,
                    :archetype_id,
                    :casefile_version,
                    :timestamp_emitted,
                    :casefile_json
                )
                """
            ),
            {
                "case_id": casefile.case_id,
                "prior_case_id": casefile.prior_case_id,
                "archetype_id": casefile.archetype_id,
                "casefile_version": casefile.casefile_version,
                "timestamp_emitted": casefile.timestamp_emitted,
                "casefile_json": casefile_json,
            },
        )
        db.commit()

        logger.info(
            "[CASEFILE][PERSISTED] request_id=%s case_id=%s",
            request_id,
            casefile.case_id,
        )

    except Exception as e:
        db.rollback()
        logger.error(
            "[CASEFILE][PERSIST_ERROR] request_id=%s case_id=%s error=%s",
            request_id,
            casefile.case_id,
            type(e).__name__,
        )
        raise

    finally:
        db.close()