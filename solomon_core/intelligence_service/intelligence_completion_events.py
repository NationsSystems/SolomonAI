# -------------------------------------------------------------------
# FILE: intelligence_completion_events.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Process-local event broker for durable SIS job completion signals.
#
# Durable IntelligenceJob state remains authoritative in the database. These
# events are change notifications only: consumers must re-read and reauthorize
# canonical state before exposing any user capability.
# -------------------------------------------------------------------

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Condition, RLock
import time
from typing import Any, Deque, Dict, Optional

from config import settings
from solomon_core.logger import get_logger


logger = get_logger("intelligence_service.completion_events")

INTELLIGENCE_COMPLETION_EVENT_TYPE = "intelligence_job_completed"
INTELLIGENCE_RESYNC_EVENT_TYPE = "intelligence_resync_required"

_EVENT_LOCK = RLock()
_EVENT_CONDITION = Condition(_EVENT_LOCK)
_EVENT_HISTORY: Deque[Dict[str, Any]] = deque(
    maxlen=max(32, int(settings.SIS_EVENT_HISTORY_LIMIT))
)
_LATEST_EVENT_ID = 0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_event_id(value: Any) -> int:
    try:
        return max(0, int(str(value or "0").strip() or "0"))
    except (TypeError, ValueError):
        return 0


def _next_event_id_locked() -> int:
    global _LATEST_EVENT_ID

    candidate = int(time.time_ns())
    _LATEST_EVENT_ID = max(candidate, _LATEST_EVENT_ID + 1)
    return _LATEST_EVENT_ID


def get_intelligence_completion_event_cursor() -> str:
    """Return the latest process-local completion event id."""

    with _EVENT_LOCK:
        return str(_LATEST_EVENT_ID)


def publish_intelligence_completion_event(
    *,
    job_id: str,
    job_type: str,
    document_id: str,
    intelligence_object_id: Optional[int] = None,
    stage: str = "completed",
) -> Optional[Dict[str, Any]]:
    """Publish one post-commit completion signal for a durable succeeded job."""

    clean_job_id = str(job_id or "").strip()
    clean_job_type = str(job_type or "").strip()
    clean_document_id = str(document_id or "").strip()
    clean_stage = str(stage or "completed").strip() or "completed"

    if not clean_job_id or not clean_job_type or not clean_document_id:
        logger.warning(
            "[SIS][COMPLETION_EVENT_SKIPPED] job_id=%s job_type=%s document_id=%s",
            clean_job_id or "-",
            clean_job_type or "-",
            clean_document_id or "-",
        )
        return None

    with _EVENT_CONDITION:
        event_id = _next_event_id_locked()
        event = {
            "event_id": str(event_id),
            "type": INTELLIGENCE_COMPLETION_EVENT_TYPE,
            "status": "succeeded",
            "job_id": clean_job_id,
            "job_type": clean_job_type,
            "document_id": clean_document_id,
            "intelligence_object_id": (
                int(intelligence_object_id)
                if intelligence_object_id is not None
                else None
            ),
            "stage": clean_stage,
            "completed_at": _utc_now_iso(),
        }
        _EVENT_HISTORY.append(event)
        _EVENT_CONDITION.notify_all()

    logger.info(
        "[SIS][COMPLETION_EVENT_PUBLISHED] event_id=%s job_id=%s job_type=%s document_id=%s stage=%s",
        event["event_id"],
        clean_job_id,
        clean_job_type,
        clean_document_id,
        clean_stage,
    )
    return dict(event)


def wait_for_intelligence_completion_events(
    after_event_id: Any,
    *,
    timeout_seconds: float,
) -> Dict[str, Any]:
    """Wait for buffered completion events newer than ``after_event_id``.

    The returned ``resync_required`` flag means the requested cursor is older
    than the retained process-local history. Consumers should re-read canonical
    state rather than infer what was missed.
    """

    after_id = _normalize_event_id(after_event_id)
    timeout = max(0.1, float(timeout_seconds))

    with _EVENT_CONDITION:
        oldest_id = (
            _normalize_event_id(_EVENT_HISTORY[0].get("event_id"))
            if _EVENT_HISTORY
            else 0
        )
        resync_required = bool(
            after_id
            and oldest_id
            and after_id < oldest_id
        )

        events = [
            dict(event)
            for event in _EVENT_HISTORY
            if _normalize_event_id(event.get("event_id")) > after_id
        ]

        if not events and not resync_required:
            _EVENT_CONDITION.wait(timeout=timeout)
            oldest_id = (
                _normalize_event_id(_EVENT_HISTORY[0].get("event_id"))
                if _EVENT_HISTORY
                else 0
            )
            resync_required = bool(
                after_id
                and oldest_id
                and after_id < oldest_id
            )
            events = [
                dict(event)
                for event in _EVENT_HISTORY
                if _normalize_event_id(event.get("event_id")) > after_id
            ]

        return {
            "events": events,
            "resync_required": resync_required,
            "latest_event_id": str(_LATEST_EVENT_ID),
        }


__all__ = [
    "INTELLIGENCE_COMPLETION_EVENT_TYPE",
    "INTELLIGENCE_RESYNC_EVENT_TYPE",
    "get_intelligence_completion_event_cursor",
    "publish_intelligence_completion_event",
    "wait_for_intelligence_completion_events",
]
