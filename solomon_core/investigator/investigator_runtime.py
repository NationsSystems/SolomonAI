# ------------------------------------------------------------------
# FILE: investigator_runtime.py
# DIRECTORY: solomon_core/investigator/
# ------------------------------------------------------------------
# Investigator Runtime Boundary
#
# PURPOSE
#   Invoke the canonical Investigator, preserve single-emission CaseFile
#   integrity, and provide bounded runtime observability.
#
# CONTRACT
#   - No CaseFile mutation after emission
#   - No duplicate evidence interpretation
#   - No routing or execution authority
#   - Returned CaseFile must match the persisted CaseFile
# ------------------------------------------------------------------

from __future__ import annotations

import threading
from collections import deque
from typing import Optional

from solomon_core.investigator.investigator import investigate
from solomon_core.investigator.investigator_casefile_types import CaseFile
from solomon_core.investigator.investigator_logging import (
    log_investigator_event,
)


_seen_lock = threading.Lock()
_seen_keys: set[str] = set()
_seen_ring: deque[str] = deque(maxlen=1024)


def _key_for_invocation(
    case_id: str | None,
    session_id: str | None,
) -> str:
    return f"{session_id or 'no_session'}::{case_id or 'no_case'}"


def _mark_seen(key: str) -> bool:
    """
    Record bounded duplicate invocation diagnostics.

    Duplicate detection is observational only and does not suppress or alter
    Investigator execution.
    """

    with _seen_lock:
        if key in _seen_keys:
            return True

        _seen_keys.add(key)
        _seen_ring.append(key)

        if len(_seen_keys) > _seen_ring.maxlen:
            _seen_keys.clear()
            _seen_keys.update(_seen_ring)

        return False


def run_investigator(
    *,
    request_context,
    evidence_inputs,
    prior_casefile: Optional[CaseFile] = None,
) -> Optional[CaseFile]:
    """
    Invoke the Investigator and return its emitted immutable CaseFile unchanged.
    """

    case_id = getattr(request_context, "case_id", None)
    archetype_id = getattr(request_context, "archetype_id", None)
    session_id = getattr(request_context, "session_id", None)
    request_id = getattr(request_context, "request_id", None)

    invocation_key = _key_for_invocation(
        case_id,
        session_id,
    )
    duplicate_invocation = _mark_seen(
        invocation_key
    )

    log_investigator_event(
        "INVESTIGATOR_START",
        {
            "request_id": request_id,
            "case_id": case_id,
            "archetype_id": archetype_id,
            "session_id": session_id,
            "duplicate_invocation": duplicate_invocation,
        },
    )

    try:
        casefile = investigate(
            request_context=request_context,
            evidence_inputs=evidence_inputs,
            prior_casefile=prior_casefile,
        )

        log_investigator_event(
            "CASEFILE_EMITTED",
            {
                "request_id": request_id,
                "case_id": getattr(
                    casefile,
                    "case_id",
                    None,
                ),
                "session_id": session_id,
                "casefile_version": getattr(
                    casefile,
                    "casefile_version",
                    None,
                ),
                "duplicate_invocation": duplicate_invocation,
            },
        )

        return casefile

    except Exception as exc:
        log_investigator_event(
            "INVESTIGATOR_FAILURE",
            {
                "request_id": request_id,
                "case_id": case_id,
                "session_id": session_id,
                "error_type": type(exc).__name__,
            },
        )

        return None