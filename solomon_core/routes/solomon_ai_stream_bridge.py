# -------------------------------------------------------------------
# FILE: solomon_ai_stream_bridge.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# SolomonAI Request-Scoped Streaming Bridge
#
# PURPOSE
#   Connect governed execution running on worker threads to the active
#   SolomonAI server-sent-event transport callback for the same request.
#
# AUTHORITY
#   - Transport registration and delivery only
#   - No routing, execution, persistence, synthesis, or response authority
#
# CONTRACT
#   - Registrations are isolated by request_id
#   - Callback invocation occurs outside the registry lock
#   - Transport failures never interrupt governed execution
#   - Unregistering a request prevents later bridge emissions
# -------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Callable, Dict, Optional

from solomon_core.logger import get_logger


logger = get_logger("solomon_ai_stream_bridge")


StreamCallback = Callable[[Dict[str, Any]], None]


@dataclass(frozen=True)
class _StreamRegistration:
    callback: StreamCallback
    conversation_id: str


_REGISTRY_LOCK = RLock()
_STREAM_REGISTRY: Dict[str, _StreamRegistration] = {}


def _clean_identifier(value: Any) -> str:
    return str(value or "").strip()


def register_solomon_ai_stream_callback(
    *,
    request_id: Any,
    callback: StreamCallback,
    conversation_id: Any = None,
) -> bool:
    """
    Register the active SolomonAI transport callback for one request.

    A repeated request_id replaces its previous registration. Request IDs are
    expected to be unique, but replacement prevents a stale callback from
    remaining active if a caller retries registration during setup.
    """

    clean_request_id = _clean_identifier(request_id)

    if not clean_request_id:
        logger.warning(
            "[SOLOMON_AI_STREAM_BRIDGE][REGISTER_REJECTED] "
            "reason=missing_request_id"
        )
        return False

    if not callable(callback):
        logger.warning(
            "[SOLOMON_AI_STREAM_BRIDGE][REGISTER_REJECTED] "
            "request_id=%s reason=callback_not_callable",
            clean_request_id,
        )
        return False

    registration = _StreamRegistration(
        callback=callback,
        conversation_id=_clean_identifier(
            conversation_id
        ),
    )

    with _REGISTRY_LOCK:
        replaced = clean_request_id in _STREAM_REGISTRY
        _STREAM_REGISTRY[clean_request_id] = registration

    logger.debug(
        "[SOLOMON_AI_STREAM_BRIDGE][REGISTERED] "
        "request_id=%s conversation_id=%s replaced=%s",
        clean_request_id,
        registration.conversation_id or "unbound",
        replaced,
    )

    return True


def unregister_solomon_ai_stream_callback(
    *,
    request_id: Any,
    callback: Optional[StreamCallback] = None,
) -> bool:
    """
    Remove one request-scoped callback.

    When callback is supplied, removal occurs only if the currently registered
    callback is the same object. This prevents delayed cleanup from removing a
    newer registration that reused the same request ID.
    """

    clean_request_id = _clean_identifier(request_id)

    if not clean_request_id:
        return False

    with _REGISTRY_LOCK:
        registration = _STREAM_REGISTRY.get(
            clean_request_id
        )

        if registration is None:
            return False

        if (
            callback is not None
            and registration.callback is not callback
        ):
            logger.debug(
                "[SOLOMON_AI_STREAM_BRIDGE][UNREGISTER_SKIPPED] "
                "request_id=%s reason=callback_mismatch",
                clean_request_id,
            )
            return False

        del _STREAM_REGISTRY[clean_request_id]

    logger.debug(
        "[SOLOMON_AI_STREAM_BRIDGE][UNREGISTERED] "
        "request_id=%s",
        clean_request_id,
    )

    return True


def get_solomon_ai_stream_callback(
    request_id: Any,
) -> Optional[StreamCallback]:
    """
    Return the currently registered callback for one request.

    The returned callback is a snapshot. Callers that need timeout-safe
    delivery should use emit_solomon_ai_stream_payload(), which checks the
    registry again for every emitted stage.
    """

    clean_request_id = _clean_identifier(request_id)

    if not clean_request_id:
        return None

    with _REGISTRY_LOCK:
        registration = _STREAM_REGISTRY.get(
            clean_request_id
        )

    return (
        registration.callback
        if registration is not None
        else None
    )


def emit_solomon_ai_stream_payload(
    *,
    request_id: Any,
    payload: Dict[str, Any],
) -> bool:
    """
    Deliver one transport payload to the callback registered for request_id.

    The registry is read for every emission. If the API request has timed out
    or completed and removed its registration, later model chunks are dropped.
    """

    clean_request_id = _clean_identifier(request_id)

    if (
        not clean_request_id
        or not isinstance(payload, dict)
    ):
        return False

    with _REGISTRY_LOCK:
        registration = _STREAM_REGISTRY.get(
            clean_request_id
        )

    if registration is None:
        return False

    event_payload = dict(payload)
    event_payload.setdefault(
        "request_id",
        clean_request_id,
    )

    if registration.conversation_id:
        event_payload.setdefault(
            "conversation_id",
            registration.conversation_id,
        )

    try:
        registration.callback(
            event_payload
        )
    except Exception as exc:
        logger.warning(
            "[SOLOMON_AI_STREAM_BRIDGE][EMIT_FAILED] "
            "request_id=%s stage=%s error=%s",
            clean_request_id,
            event_payload.get("stage"),
            str(exc),
        )
        return False

    return True


def is_solomon_ai_stream_registered(
    request_id: Any,
) -> bool:
    """Return whether one request currently has an active stream callback."""

    clean_request_id = _clean_identifier(request_id)

    if not clean_request_id:
        return False

    with _REGISTRY_LOCK:
        return clean_request_id in _STREAM_REGISTRY


__all__ = [
    "emit_solomon_ai_stream_payload",
    "get_solomon_ai_stream_callback",
    "is_solomon_ai_stream_registered",
    "register_solomon_ai_stream_callback",
    "unregister_solomon_ai_stream_callback",
]