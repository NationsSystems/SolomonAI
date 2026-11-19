# ------------------------------------------------------------------
# FILE: web_api_adapter.py
# DIRECTORY: solomon_core/web_lane/
# ------------------------------------------------------------------
# Brave LLM Context Adapter
#
# PURPOSE
#   Retrieve bounded public Web evidence for an already-authorized Web Lane
#   request and normalize provider-native data into Solomon-owned evidence.
#
# CONTRACT
#   - Retrieval only; never answers the user
#   - Exactly one Brave request per invocation
#   - Uses Brave /res/v1/llm/context only
#   - Never returns provider-native response payloads to callers
#   - Never receives internal files, RAG excerpts, conversation history, or
#     authorization metadata
#   - Never throws provider/network errors across the adapter boundary
# ------------------------------------------------------------------

from __future__ import annotations

from datetime import date, timedelta
import re
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import requests

from config import settings
from solomon_core.logger import get_logger

logger = get_logger("web_lane.brave_context")

_PROVIDER = "brave_llm_context"
_QUERY_MAX_CHARS = 400
_QUERY_MAX_WORDS = 50
_QUERY_RELEVANCE_IGNORED_TERMS = frozenset({
    "about",
    "after",
    "also",
    "and",
    "announce",
    "announced",
    "announcement",
    "announcements",
    "are",
    "before",
    "can",
    "conditions",
    "current",
    "currently",
    "did",
    "does",
    "for",
    "forecast",
    "forecasting",
    "forecasts",
    "from",
    "give",
    "has",
    "have",
    "how",
    "information",
    "into",
    "latest",
    "news",
    "now",
    "outlook",
    "please",
    "public",
    "recent",
    "recently",
    "report",
    "reports",
    "said",
    "show",
    "tell",
    "that",
    "the",
    "their",
    "there",
    "they",
    "this",
    "today",
    "tomorrow",
    "update",
    "updates",
    "was",
    "weather",
    "week",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "with",
    "would",
    "yesterday",
})


# ------------------------------------------------------------------
# Provider gate
# ------------------------------------------------------------------
def _disabled() -> bool:
    enabled = bool(
        getattr(
            settings,
            "WEB_LANE_ENABLED",
            False,
        )
    )
    context_enabled = bool(
        getattr(
            settings,
            "BRAVE_CONTEXT_ENABLED",
            False,
        )
    )
    key_present = bool(
        str(
            getattr(
                settings,
                "BRAVE_SEARCH_API_KEY",
                "",
            )
            or ""
        ).strip()
    )

    return not (
        enabled
        and context_enabled
        and key_present
    )


# ------------------------------------------------------------------
# Request helpers
# ------------------------------------------------------------------
def _build_headers() -> Dict[str, str]:
    return {
        "X-Subscription-Token": settings.BRAVE_SEARCH_API_KEY,
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "User-Agent": "Solomon/WebLaneContext",
    }


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def _normalize_query(query: str) -> str:
    clean = _clean_text(query)

    if not clean:
        return ""

    words = clean.split()

    if len(words) > _QUERY_MAX_WORDS:
        clean = " ".join(
            words[:_QUERY_MAX_WORDS]
        )

    return clean[:_QUERY_MAX_CHARS].strip()


def _custom_freshness(days: int) -> str:
    safe_days = max(1, int(days))
    end_date = date.today()
    start_date = end_date - timedelta(
        days=safe_days,
    )

    return (
        f"{start_date.isoformat()}"
        f"to{end_date.isoformat()}"
    )


def _resolve_freshness(query: str) -> str:
    lower = _clean_text(query).lower()

    if not lower:
        return ""

    if any(
        phrase in lower
        for phrase in (
            "today",
            "last 24 hours",
            "past 24 hours",
        )
    ):
        return "pd"

    if any(
        phrase in lower
        for phrase in (
            "this week",
            "last 7 days",
            "past 7 days",
            "past week",
            "last week",
        )
    ):
        return "pw"

    if any(
        phrase in lower
        for phrase in (
            "this month",
            "last 30 days",
            "past 30 days",
            "last 31 days",
            "past 31 days",
        )
    ):
        return "pm"

    if any(
        phrase in lower
        for phrase in (
            "this year",
            "last 365 days",
            "past 365 days",
            "past year",
            "last year",
        )
    ):
        return "py"

    day_match = re.search(
        r"\b(?:last|past)\s+(\d{1,3})\s+days?\b",
        lower,
    )

    if day_match:
        return _custom_freshness(
            int(day_match.group(1))
        )

    week_match = re.search(
        r"\b(?:last|past)\s+(\d{1,2})\s+weeks?\b",
        lower,
    )

    if week_match:
        return _custom_freshness(
            int(week_match.group(1)) * 7
        )

    return ""


def _request_params(query: str) -> Dict[str, Any]:
    params: Dict[str, Any] = {
        "q": query,
        "country": str(
            getattr(
                settings,
                "SYSTEM_DEFAULT_COUNTRY",
                "US",
            )
            or "US"
        ).upper()[:2],
        "search_lang": "en",
        "count": int(
            settings.BRAVE_CONTEXT_MAX_RESULTS
        ),
        "maximum_number_of_urls": int(
            settings.BRAVE_CONTEXT_MAX_URLS
        ),
        "maximum_number_of_tokens": int(
            settings.BRAVE_CONTEXT_MAX_TOKENS
        ),
        "maximum_number_of_tokens_per_url": int(
            settings.BRAVE_CONTEXT_MAX_TOKENS_PER_URL
        ),
        "maximum_number_of_snippets": int(
            settings.BRAVE_CONTEXT_MAX_SNIPPETS
        ),
        "maximum_number_of_snippets_per_url": int(
            settings.BRAVE_CONTEXT_MAX_SNIPPETS_PER_URL
        ),
        "context_threshold_mode": str(
            settings.BRAVE_CONTEXT_THRESHOLD_MODE
        ),
        "safesearch": str(
            settings.BRAVE_CONTEXT_SAFESEARCH
        ),
        "enable_source_metadata": "true",
    }
    freshness = _resolve_freshness(
        query
    )

    if freshness:
        params["freshness"] = freshness

    return params


# ------------------------------------------------------------------
# Normalization helpers
# ------------------------------------------------------------------
def _valid_public_url(value: Any) -> str:
    url = _clean_text(value)

    if not url:
        return ""

    try:
        parsed = urlparse(url)
    except Exception:
        return ""

    if parsed.scheme not in {"http", "https"}:
        return ""

    if not parsed.netloc:
        return ""

    return url


def _age_fields(metadata: Dict[str, Any]) -> tuple[str, str]:
    age = metadata.get("age")

    if not isinstance(age, list):
        return "", ""

    published_at = ""
    relative_age = ""

    if len(age) > 3:
        published_at = _clean_text(
            age[3]
        )

    if not published_at and len(age) > 1:
        published_at = _clean_text(
            age[1]
        )

    if len(age) > 2:
        relative_age = _clean_text(
            age[2]
        )

    return published_at, relative_age


def _published_date(value: str) -> Optional[date]:
    clean = _clean_text(value)

    if not clean:
        return None

    try:
        return date.fromisoformat(
            clean[:10]
        )
    except Exception:
        return None


def _freshness_bounds(
    freshness: str,
) -> tuple[Optional[date], Optional[date]]:
    clean = _clean_text(
        freshness
    ).lower()
    today = date.today()

    if clean == "pd":
        return today - timedelta(days=1), today

    if clean == "pw":
        return today - timedelta(days=7), today

    if clean == "pm":
        return today - timedelta(days=31), today

    if clean == "py":
        return today - timedelta(days=365), today

    match = re.fullmatch(
        r"(\d{4}-\d{2}-\d{2})to(\d{4}-\d{2}-\d{2})",
        clean,
    )

    if not match:
        return None, None

    try:
        return (
            date.fromisoformat(match.group(1)),
            date.fromisoformat(match.group(2)),
        )
    except Exception:
        return None, None


def _outside_requested_freshness(
    published_at: str,
    freshness: str,
) -> bool:
    published = _published_date(
        published_at
    )
    start_date, end_date = _freshness_bounds(
        freshness
    )

    if not published or not start_date or not end_date:
        return False

    return not (
        start_date <= published <= end_date
    )


def _source_metadata(
    source_map: Dict[str, Any],
    url: str,
) -> Dict[str, Any]:
    metadata = source_map.get(url)

    return (
        metadata
        if isinstance(metadata, dict)
        else {}
    )


def _query_relevance_terms(query: str) -> set[str]:
    clean = _clean_text(query).lower()

    if not clean:
        return set()

    terms = {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            clean,
        )
        if (
            len(token) >= 3
            and token not in _QUERY_RELEVANCE_IGNORED_TERMS
        )
    }

    return terms


def _source_matches_query(
    *,
    query_terms: set[str],
    title: str,
    url: str,
    hostname: str,
    metadata: Dict[str, Any],
    raw_snippets: List[Any],
) -> bool:
    if not query_terms:
        return True

    candidate_parts = [
        title,
        url,
        hostname,
        _clean_text(metadata.get("description")),
        _clean_text(metadata.get("site_name")),
    ]
    candidate_parts.extend(
        _clean_text(snippet)
        for snippet in raw_snippets
    )
    candidate_tokens = set(
        re.findall(
            r"[a-z0-9]+",
            " ".join(candidate_parts).lower(),
        )
    )

    return bool(
        query_terms.intersection(
            candidate_tokens
        )
    )


def _normalize_grounding(
    data: Dict[str, Any],
    *,
    freshness: str,
    query: str,
) -> tuple[List[Dict[str, Any]], int, int, int]:
    grounding = data.get("grounding")
    source_map = data.get("sources")

    if not isinstance(grounding, dict):
        return [], 0, 0, 0

    generic = grounding.get("generic")

    if not isinstance(generic, list):
        return [], 0, 0, 0

    if not isinstance(source_map, dict):
        source_map = {}

    max_urls = max(
        1,
        int(
            settings.BRAVE_CONTEXT_MAX_URLS
        ),
    )
    max_snippets = max(
        1,
        int(
            settings.BRAVE_CONTEXT_MAX_SNIPPETS
        ),
    )
    max_snippets_per_url = max(
        1,
        int(
            settings.BRAVE_CONTEXT_MAX_SNIPPETS_PER_URL
        ),
    )
    max_chars = max(
        1000,
        int(
            settings.WEB_LANE_MAX_EVIDENCE_CHARS
        ),
    )
    query_terms = _query_relevance_terms(
        query
    )
    evidence: List[Dict[str, Any]] = []
    evidence_chars = 0
    evidence_snippets = 0
    rejected_out_of_window = 0
    rejected_query_irrelevant = 0

    for item in generic:
        if (
            len(evidence) >= max_urls
            or evidence_snippets >= max_snippets
        ):
            break

        if not isinstance(item, dict):
            continue

        url = _valid_public_url(
            item.get("url")
        )

        if not url:
            continue

        metadata = _source_metadata(
            source_map,
            url,
        )
        title = (
            _clean_text(item.get("title"))
            or _clean_text(metadata.get("title"))
            or urlparse(url).netloc
        )
        hostname = (
            _clean_text(metadata.get("hostname"))
            or urlparse(url).netloc
        )
        published_at, relative_age = (
            _age_fields(metadata)
        )

        if _outside_requested_freshness(
            published_at,
            freshness,
        ):
            rejected_out_of_window += 1
            continue

        raw_snippets = item.get("snippets")

        if not isinstance(raw_snippets, list):
            continue

        if not _source_matches_query(
            query_terms=query_terms,
            title=title,
            url=url,
            hostname=hostname,
            metadata=metadata,
            raw_snippets=raw_snippets,
        ):
            rejected_query_irrelevant += 1
            continue

        snippets: List[str] = []

        for raw_snippet in raw_snippets:
            if (
                len(snippets) >= max_snippets_per_url
                or evidence_snippets >= max_snippets
            ):
                break

            snippet = _clean_text(
                raw_snippet
            )

            if not snippet:
                continue

            remaining = (
                max_chars
                - evidence_chars
            )

            if remaining <= 0:
                break

            snippet = snippet[:remaining].strip()

            if not snippet:
                break

            snippets.append(
                snippet
            )
            evidence_chars += len(
                snippet
            )
            evidence_snippets += 1

        if not snippets:
            if (
                evidence_chars >= max_chars
                or evidence_snippets >= max_snippets
            ):
                break
            continue

        source_id = f"W{len(evidence) + 1}"
        evidence.append({
            "source_id": source_id,
            "title": title,
            "url": url,
            "hostname": hostname,
            "published_at": published_at,
            "relative_age": relative_age,
            "snippets": snippets,
        })

        if evidence_chars >= max_chars:
            break

    return (
        evidence,
        evidence_chars,
        rejected_out_of_window,
        rejected_query_irrelevant,
    )


def _source_payload(
    evidence: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    sources: List[Dict[str, Any]] = []

    for entry in evidence:
        sources.append({
            "source_id": _clean_text(
                entry.get("source_id")
            ),
            "source_name": _clean_text(
                entry.get("title")
            ),
            "source_scope": "public_web",
            "url": _clean_text(
                entry.get("url")
            ),
            "hostname": _clean_text(
                entry.get("hostname")
            ),
            "published_at": _clean_text(
                entry.get("published_at")
            ),
            "relative_age": _clean_text(
                entry.get("relative_age")
            ),
            "provider": _PROVIDER,
        })

    return sources


def _empty_packet(
    *,
    status: str,
    query: str = "",
    freshness: str = "",
) -> Dict[str, Any]:
    freshness_start, freshness_end = _freshness_bounds(
        freshness
    )

    return {
        "ok": False,
        "status": status,
        "provider": _PROVIDER,
        "query": query,
        "freshness": freshness,
        "freshness_start_date": (
            freshness_start.isoformat()
            if freshness_start
            else ""
        ),
        "freshness_end_date": (
            freshness_end.isoformat()
            if freshness_end
            else ""
        ),
        "evidence": [],
        "sources": [],
        "evidence_char_count": 0,
    }


# ------------------------------------------------------------------
# Public entry
# ------------------------------------------------------------------
def fetch_web_context(
    query: str,
) -> Dict[str, Any]:
    """Retrieve one bounded Brave LLM Context evidence packet."""

    normalized_query = _normalize_query(
        query
    )

    if not normalized_query:
        return _empty_packet(
            status="empty_query",
        )

    if _disabled():
        logger.info(
            "[BRAVE_CONTEXT][SKIP] provider_disabled"
        )
        return _empty_packet(
            status="provider_disabled",
            query=normalized_query,
        )

    endpoint = str(
        settings.BRAVE_CONTEXT_ENDPOINT
        or ""
    ).strip()

    if endpoint != "/res/v1/llm/context":
        logger.error(
            "[BRAVE_CONTEXT][CONFIG_REJECTED] endpoint=%s",
            endpoint,
        )
        return _empty_packet(
            status="provider_misconfigured",
            query=normalized_query,
        )

    url = (
        f"{settings.BRAVE_SEARCH_BASE_URL.rstrip('/')}"
        f"{endpoint}"
    )
    params = _request_params(
        normalized_query
    )
    freshness = _clean_text(
        params.get("freshness")
    )

    try:
        response = requests.get(
            url,
            headers=_build_headers(),
            params=params,
            timeout=int(
                settings.BRAVE_CONTEXT_TIMEOUT_SECONDS
            ),
        )
    except Exception as exc:
        logger.warning(
            "[BRAVE_CONTEXT][REQUEST_FAILED] error=%s",
            str(exc),
        )
        return _empty_packet(
            status="provider_unavailable",
            query=normalized_query,
            freshness=freshness,
        )

    remaining = response.headers.get(
        "X-RateLimit-Remaining"
    )
    limit = response.headers.get(
        "X-RateLimit-Limit"
    )

    logger.info(
        "[BRAVE_CONTEXT][RESPONSE] status=%s remaining=%s limit=%s",
        response.status_code,
        remaining,
        limit,
    )

    if response.status_code != 200:
        return _empty_packet(
            status=(
                "rate_limited"
                if response.status_code == 429
                else "provider_unavailable"
            ),
            query=normalized_query,
            freshness=freshness,
        )

    try:
        data = response.json()
    except Exception:
        logger.warning(
            "[BRAVE_CONTEXT][INVALID_JSON]"
        )
        return _empty_packet(
            status="provider_invalid_response",
            query=normalized_query,
            freshness=freshness,
        )

    if not isinstance(data, dict):
        return _empty_packet(
            status="provider_invalid_response",
            query=normalized_query,
            freshness=freshness,
        )

    (
        evidence,
        evidence_chars,
        rejected_out_of_window,
        rejected_query_irrelevant,
    ) = _normalize_grounding(
        data,
        freshness=freshness,
        query=normalized_query,
    )

    if not evidence:
        logger.info(
            "[BRAVE_CONTEXT][EMPTY] query=%r freshness=%s",
            normalized_query,
            freshness,
        )
        return _empty_packet(
            status="no_relevant_evidence",
            query=normalized_query,
            freshness=freshness,
        )

    freshness_start, freshness_end = _freshness_bounds(
        freshness
    )
    packet = {
        "ok": True,
        "status": "ok",
        "provider": _PROVIDER,
        "query": normalized_query,
        "freshness": freshness,
        "freshness_start_date": (
            freshness_start.isoformat()
            if freshness_start
            else ""
        ),
        "freshness_end_date": (
            freshness_end.isoformat()
            if freshness_end
            else ""
        ),
        "evidence": evidence,
        "sources": _source_payload(
            evidence
        ),
        "evidence_char_count": evidence_chars,
        "rejected_out_of_window_count": rejected_out_of_window,
        "rejected_query_irrelevant_count": rejected_query_irrelevant,
    }

    logger.info(
        "[BRAVE_CONTEXT][OK] sources=%s evidence_chars=%s freshness=%s "
        "rejected_out_of_window=%s rejected_query_irrelevant=%s",
        len(evidence),
        evidence_chars,
        freshness,
        rejected_out_of_window,
        rejected_query_irrelevant,
    )

    return packet


# Backward-compatible symbol for any legacy import that has not yet been
# physically removed. The behavior is the canonical LLM Context retrieval
# contract above; the old Brave Web Search endpoint is not called.
def fetch_live_data(
    query: str,
) -> Optional[Dict[str, Any]]:
    return fetch_web_context(
        query
    )
