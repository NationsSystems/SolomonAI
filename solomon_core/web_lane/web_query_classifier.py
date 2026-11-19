# ------------------------------------------------------------------
# FILE: solomon_core/web_lane/web_query_classifier.py
# ------------------------------------------------------------------
# WEB QUERY CLASSIFIER
#
# Deterministic query classifier for Web Lane routing.
#
# Design constraints:
#   • No LLM calls
#   • Deterministic
#   • O(1) keyword checks
#   • <1 ms execution target
#
# Output categories (enum):
#   WebCategory.WEATHER
#   WebCategory.CURRENT_EVENTS
#   WebCategory.SPORTS
#   WebCategory.MARKETS
# ------------------------------------------------------------------

import re
from enum import Enum


# ------------------------------------------------------------------
# Category Enum
# ------------------------------------------------------------------
class WebCategory(Enum):
    WEATHER = 1
    CURRENT_EVENTS = 2
    SPORTS = 3
    MARKETS = 4


# ------------------------------------------------------------------
# Keyword dictionaries
# ------------------------------------------------------------------

_WEATHER_TERMS = {
    "weather",
    "forecast",
    "temperature",
    "rain",
    "snow",
    "wind",
    "humidity",
    "storm",
    "degrees",
}

_NEWS_TERMS = {
    "news",
    "update",
    "war",
    "conflict",
    "crisis",
    "situation",
    "latest",
}

_SPORTS_TERMS = {
    "score",
    "scores",
    "game",
    "games",
    "match",
    "matches",
    "nba",
    "nfl",
    "mlb",
    "nhl",
    "soccer",
    "football",
    "basketball",
    "baseball",
    "standings",
    "playoffs",
    "team",
    "teams",
}

_BUSINESS_TERMS = {
    "stock",
    "stocks",
    "market",
    "dow",
    "nasdaq",
    "economy",
    "inflation",
    "earnings",
}


# ------------------------------------------------------------------
# Sanitization
# ------------------------------------------------------------------

_SPACE_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _normalize_query(query: str) -> str:

    if not query:
        return ""

    q = query.lower()
    q = _SPACE_RE.sub(" ", q).strip()
    return q


def _tokenize(query: str) -> set[str]:
    """
    Token-based matching prevents substring false positives.
    Example:
        'rainforest' will not match 'rain'
    """
    return set(_TOKEN_RE.findall(query))


# ------------------------------------------------------------------
# Classifier
# ------------------------------------------------------------------

def classify_web_query(query: str) -> WebCategory:
    """
    Returns WebCategory enum for Web Lane routing.
    """

    q = _normalize_query(query)

    if not q:
        return WebCategory.CURRENT_EVENTS

    tokens = _tokenize(q)

    # Weather
    if tokens & _WEATHER_TERMS:
        return WebCategory.WEATHER

    # Business / markets
    if tokens & _BUSINESS_TERMS:
        return WebCategory.MARKETS

    # Current events / news
    if tokens & _NEWS_TERMS:
        return WebCategory.CURRENT_EVENTS

    # Sports
    if tokens & _SPORTS_TERMS:
        return WebCategory.SPORTS

    # Default deterministic fallback
    return WebCategory.CURRENT_EVENTS