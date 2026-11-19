# ------------------------------------------------------------------
# FILE: solomon_core/web_lane/web_api_adapter.py
# ------------------------------------------------------------------
# Brave Web Lane Adapter (NON-AUTH, OPT-IN)
#
# Contract:
# - Transparent augmentation only
# - Never default, never blocking
# - Never throws; returns None on any failure
# - Single request per invocation (no retries)
# - No persistence, no caching, no memory writes
# ------------------------------------------------------------------

from typing import Optional, Dict, Any, List, Union
import requests
from datetime import datetime
import re
import html

from config import settings
from solomon_core.logger import get_logger

logger = get_logger("web_lane.brave")

# 🔒 Safety caps
_MAX_CLEAN_CHARS = 12000
_FULLPAGE_CHAR_CAP = 20000  # debug mode cap


# ============================================================================
# 🔒 Gate
# ============================================================================
def _disabled() -> bool:
    enabled = getattr(settings, "WEB_LANE_ENABLED", False)
    brave_enabled = getattr(settings, "BRAVE_SEARCH_ENABLED", False)
    key_present = bool(getattr(settings, "BRAVE_SEARCH_API_KEY", ""))

    logger.info(
        "[BRAVE][DEBUG_GATE] web_lane=%s brave_enabled=%s key_present=%s",
        enabled,
        brave_enabled,
        key_present,
    )

    return not (enabled and brave_enabled and key_present)


def _build_headers() -> Dict[str, str]:
    return {
        "X-Subscription-Token": settings.BRAVE_SEARCH_API_KEY,
        "Accept": "application/json",
        "User-Agent": "Solomon/WebLane (Brave Adapter)",
    }


# ============================================================================
# 🔧 HTML → readable text sanitizer
# ============================================================================
_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>", re.IGNORECASE)
_STYLE_RE = re.compile(r"<style[\s\S]*?</style>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def _clean_html_to_text(raw: str) -> str:
    if not raw or "<" not in raw:
        return raw or ""

    try:
        text = _SCRIPT_RE.sub(" ", raw)
        text = _STYLE_RE.sub(" ", text)
        text = _TAG_RE.sub(" ", text)
        text = html.unescape(text)
        text = _WS_RE.sub(" ", text).strip()

        if len(text) > _MAX_CLEAN_CHARS:
            text = text[:_MAX_CLEAN_CHARS].rstrip() + "…"

        return text

    except Exception:
        return raw[:_MAX_CLEAN_CHARS]


# ============================================================================
# 🆕 Full page fetch (diagnostic mode)
# ============================================================================
def _fetch_full_page_text(url: str) -> Optional[str]:
    """Fetch first result page and rip readable text."""
    if not url or not isinstance(url, str):
        return None

    try:
        resp = requests.get(
            url,
            headers={"User-Agent": "Solomon/WebLane (FullPage)"},
            timeout=8,
        )

        if resp.status_code != 200:
            logger.warning("[BRAVE][FULLPAGE_NON_200] code=%s", resp.status_code)
            return None

        cleaned = _clean_html_to_text(resp.text or "")

        if len(cleaned) > _FULLPAGE_CHAR_CAP:
            cleaned = cleaned[:_FULLPAGE_CHAR_CAP].rstrip() + "…"

        logger.info("[BRAVE][FULLPAGE_OK] bytes=%d", len(cleaned))
        return cleaned

    except Exception as e:
        logger.warning("[BRAVE][FULLPAGE_FAIL] %s", str(e))
        return None


# ============================================================================
# 🔄 Brave normalization
# ============================================================================
def _normalize_response(
    raw: Dict[str, Any],
    *,
    debug_fullpage: bool = False,
) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        return {}

    web = raw.get("web", {})
    results = web.get("results") if isinstance(web, dict) else None

    if not isinstance(results, list) or not results:
        logger.warning("[BRAVE][NORMALIZE_EMPTY]")
        return {}

    # ------------------------------------------------------------------
    # 🆕 Diagnostic full-page mode (first result only)
    # ------------------------------------------------------------------
    if debug_fullpage:
        first = results[0] if results else None
        if isinstance(first, dict):
            first_url = first.get("url")
            page_text = _fetch_full_page_text(first_url)
            if page_text:
                return {
                    "provider": "brave",
                    "mode": "fullpage",
                    "timestamp": datetime.utcnow().isoformat(),
                    "content": page_text,
                    "sources": [first_url] if first_url else [],
                }

    # ------------------------------------------------------------------
    # Normal snippet mode
    # ------------------------------------------------------------------
    content_chunks: List[str] = []
    sources: List[str] = []

    for item in results[:3]:
        if not isinstance(item, dict):
            continue

        title = item.get("title")
        desc = item.get("description")
        url = item.get("url")

        chunk_parts = []

        if isinstance(title, str) and title.strip():
            chunk_parts.append(title.strip())

        if isinstance(desc, str) and desc.strip():
            chunk_parts.append(desc.strip())

        if chunk_parts:
            content_chunks.append(" — ".join(chunk_parts))

        if isinstance(url, str):
            sources.append(url)

    if not content_chunks:
        return {}

    cleaned_chunks = [_clean_html_to_text(c) for c in content_chunks]

    return {
        "provider": "brave",
        "mode": "search",
        "timestamp": datetime.utcnow().isoformat(),
        "content": "\n\n".join(cleaned_chunks),
        "sources": sources[:3],
    }


# ============================================================================
# 🌐 Public entry
# ============================================================================
def fetch_live_data(
    query_or_url: Union[str, List[str]],
    mode: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Fetch live data via Brave Search.
    mode="fullpage" enables first-result HTML rip (diagnostic).
    """

    if _disabled():
        return None

    if not isinstance(query_or_url, str) or not query_or_url.strip():
        return None

    try:
        base = settings.BRAVE_SEARCH_BASE_URL.rstrip("/")
        endpoint = settings.BRAVE_SEARCH_ENDPOINT
        url = f"{base}{endpoint}"

        headers = _build_headers()

        params = {
            "q": query_or_url,
            "count": int(settings.BRAVE_SEARCH_MAX_RESULTS),
        }

        timeout_seconds = max(
            int(settings.BRAVE_SEARCH_TIMEOUT_SECONDS),
            5,
        )

        resp = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=timeout_seconds,
        )

        if resp.status_code != 200:
            logger.warning("[BRAVE][HTTP_NON_200] code=%s", resp.status_code)
            return None

        data = resp.json()

        logger.info("[BRAVE][HTTP_200]")

        normalized = _normalize_response(
            data,
            debug_fullpage=(mode == "fullpage"),
        )

        if normalized:
            logger.info("[BRAVE][NORMALIZED_OK]")

        return normalized if normalized else None

    except Exception as e:
        if getattr(settings, "WEB_LANE_LOG_FAILURES", False):
            logger.warning(
                "[BRAVE][FAILURE] Silent fallback",
                extra={"error": str(e)},
            )
        return None