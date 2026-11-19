# ------------------------------------------------------------------
# FILE: runtime_fetcher.py
# DIRECTORY: solomon_core/web_lane/
# ------------------------------------------------------------------
# Web Lane Runtime Fetcher
#
# PURPOSE
#   Cross the configured external-evidence provider boundary only after the
#   Web Lane has already been authorized to execute.
#
# CONTRACT
#   - Retrieval only; no routing or answer generation
#   - Exactly one provider request per user request
#   - Returns Solomon-normalized evidence packets only
#   - Never falls through to another provider or legacy Web Search path
# ------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict

from config import settings
from solomon_core.logger import get_logger
from solomon_core.web_lane.web_api_adapter import (
    fetch_web_context,
)

logger = get_logger(
    "solomon_core.web_lane.runtime_fetcher"
)


def _empty_packet(
    status: str,
) -> Dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "provider": "brave_llm_context",
        "query": "",
        "freshness": "",
        "evidence": [],
        "sources": [],
        "evidence_char_count": 0,
    }


# ------------------------------------------------------------------
# Public entry
# ------------------------------------------------------------------
def perform_web_context_fetch(
    normalized_query: str,
    *,
    network_context: dict | None = None,
    client_network_context: dict | None = None,
    system_context: dict | None = None,
) -> Dict[str, Any]:
    """Fetch one bounded public-evidence packet from Brave LLM Context."""

    del network_context
    del client_network_context
    del system_context

    if not bool(
        getattr(
            settings,
            "WEB_LANE_ENABLED",
            False,
        )
    ):
        logger.info(
            "[WEB_LANE][FETCH_SKIPPED] web_lane_disabled"
        )
        return _empty_packet(
            "web_lane_disabled"
        )

    if not isinstance(
        normalized_query,
        str,
    ) or not normalized_query.strip():
        logger.info(
            "[WEB_LANE][FETCH_SKIPPED] empty_query"
        )
        return _empty_packet(
            "empty_query"
        )

    logger.info(
        "[WEB_LANE][CONTEXT_FETCH] query=%r",
        normalized_query.strip(),
    )

    return fetch_web_context(
        normalized_query.strip()
    )


# Compatibility alias for any stale call site. It no longer performs the old
# Phase 61 Web Search behavior.
def perform_phase61_web_fetches(
    normalized_query: str,
    *,
    network_context: dict | None = None,
    client_network_context: dict | None = None,
    system_context: dict | None = None,
) -> Dict[str, Any]:
    return perform_web_context_fetch(
        normalized_query,
        network_context=network_context,
        client_network_context=client_network_context,
        system_context=system_context,
    )
