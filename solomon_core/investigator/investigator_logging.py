# solomon_core/investigator/investigator_logging.py
# -------------------------------------------------------------
# Investigator Runtime Logging Helper
# -------------------------------------------------------------
# Purpose:
# - Provide a single, deterministic logging entrypoint for all
#   Investigator runtime events (Phase 70)
# - Enforce consistent formatting and visibility
#
# This module:
# - Does NOT import orchestrator logic
# - Does NOT influence execution
# - Emits INFO-level, grep-friendly logs only
# -------------------------------------------------------------

import logging

_LOGGER_NAME = "Solomon.investigator.runtime"

_logger = logging.getLogger(_LOGGER_NAME)
_logger.setLevel(logging.INFO)


def log_investigator_event(event: str, payload: dict | None = None) -> None:
    """
    Emit a structured Investigator runtime log event.

    Logs are:
    - INFO level
    - Single-line
    - Deterministic key=value format
    """

    parts = [f"event={event}"]

    if payload:
        for key, value in payload.items():
            if value is None:
                continue
            parts.append(f"{key}={value}")

    message = "[INVESTIGATOR] " + " ".join(parts)
    _logger.info(message)
