# -------------------------------------------------------------------
# FILE: packet_observer.py
# DIRECTORY: solomon_core/observability/
# -------------------------------------------------------------------
# Header-only packet observability for Solomon runtime boundaries.
#
# Responsibilities:
# - Log emitted packet headers without reading packet payloads.
# - Preserve request and conversation correlation identifiers.
# - Support explicit per-packet observability flags when present.
# - Consume code-owned packet observability defaults from config.py.
#
# Authority constraints:
# - Read-only observation.
# - No routing or execution influence.
# - No payload, prompt, evidence, or ECB-content access.
# - Observability failures never interrupt runtime execution.
# -------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict

from config import settings
from solomon_core.logger import get_logger


logger = get_logger("packet_observer")


# =============================================================================
# CONFIG CONTROLS
# =============================================================================

def _default_packet_logging_enabled() -> bool:
    return bool(
        settings.PACKET_LOGGING_ENABLED
    )


def _default_packet_tracing_enabled() -> bool:
    return bool(
        settings.PACKET_TRACING_ENABLED
    )


# =============================================================================
# HEADER NORMALIZATION
# =============================================================================

def _safe_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value

    return {}


def _observability_flags(
    packet_header: Dict[str, Any],
) -> Dict[str, Any]:
    extended = _safe_dict(
        packet_header.get("extended")
    )

    return _safe_dict(
        extended.get("observability_flags")
    )


def _header_log_fields(
    packet_header: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "packet_id": packet_header.get("packet_id"),
        "packet_type": packet_header.get("packet_type"),
        "origin": packet_header.get("origin"),
        "destination": packet_header.get("destination"),
        "authority_level": packet_header.get(
            "authority_level"
        ),
        "presentation_mode": packet_header.get(
            "presentation_mode"
        ),
        "phase_tag": packet_header.get("phase_tag"),
        "timestamp": packet_header.get("timestamp"),
        "request_id": packet_header.get("request_id"),
        "conversation_id": packet_header.get(
            "conversation_id"
        ),
    }


# =============================================================================
# PACKET OBSERVATION
# =============================================================================

def observe_packet(
    *,
    packet_header: Dict[str, Any],
) -> None:
    """
    Observe a packet at an emission boundary using header data only.

    Minimal packet headers are logged by default because the constitutional
    Orchestrator does not require an extended observability block. Explicit
    packet flags can still independently enable logging, tracing, or snapshots.
    """

    try:
        if not isinstance(packet_header, dict):
            return

        flags = _observability_flags(
            packet_header
        )

        trace_enabled = (
            flags.get("trace") is True
            or _default_packet_tracing_enabled()
        )

        log_enabled = (
            flags.get("log") is True
            or _default_packet_logging_enabled()
        )

        if trace_enabled:
            _trace(packet_header)

        if log_enabled:
            _log(packet_header)

        if flags.get("snapshot") is True:
            _snapshot(packet_header)

    except Exception:
        # Observability must never affect constitutional execution.
        return


# =============================================================================
# HEADER-ONLY HOOKS
# =============================================================================

def _trace(
    packet_header: Dict[str, Any],
) -> None:
    logger.debug(
        "[COURT][PACKET_TRACE]",
        extra=_header_log_fields(
            packet_header
        ),
    )


def _log(
    packet_header: Dict[str, Any],
) -> None:
    logger.info(
        "[COURT][PACKET_EMITTED]",
        extra=_header_log_fields(
            packet_header
        ),
    )


def _snapshot(
    packet_header: Dict[str, Any],
) -> None:
    """
    Reserved header-only snapshot boundary.

    The hook intentionally performs no persistence until a governed snapshot
    store is connected.
    """

    del packet_header
