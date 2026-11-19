# ------------------------------------------------------------------
# FILE: solomon_core/web_lane/processors/business_processor.py
# ------------------------------------------------------------------
# BUSINESS / MARKETS PROCESSOR
#
# Purpose:
#   Clean Brave fragments and produce a readable market briefing
#   aligned to the Web Lane Gold Standard presentation.
#
# Design constraints:
#   • Deterministic
#   • No LLM usage
#   • No inference or forecasting
#   • Only organize and summarize signals already present
#
# Output contract:
#   {
#       "summary": "...",
#       "sections": [
#           {"title": "...", "items": [...]}
#       ]
#   }
# ------------------------------------------------------------------

import re


# ------------------------------------------------------------------
# Noise filters
# ------------------------------------------------------------------

_PROMO_TERMS = (
    "subscribe",
    "newsletter",
    "sign in",
    "create your account",
    "enter your email",
)

_NAV_TERMS = (
    "stock market data",
    "view us markets",
    "market cap",
    "filter lets you",
)

# NEW: publisher tagline noise
_PUBLISHER_TAGLINES = (
    "exclusive news",
    "data and analytics",
    "financial market professionals",
    "for financial professionals",
    "trusted by professionals",
)

_MAX_ITEMS = 12


# ------------------------------------------------------------------
# Sanitization
# ------------------------------------------------------------------

def _clean_points(points):

    clean = []

    if not isinstance(points, list):
        return clean

    for p in points:

        if not isinstance(p, str):
            continue

        s = p.strip()

        if not s:
            continue

        s_lower = s.lower()

        if any(term in s_lower for term in _PROMO_TERMS):
            continue

        if any(term in s_lower for term in _NAV_TERMS):
            continue

        # filter publisher taglines
        if any(term in s_lower for term in _PUBLISHER_TAGLINES):
            continue

        clean.append(s)

    return clean[:_MAX_ITEMS]


# ------------------------------------------------------------------
# Headline extraction
# ------------------------------------------------------------------

def _extract_headlines(points):

    headlines = []

    for p in points:

        if len(p) > 200:
            continue

        headlines.append(p)

        if len(headlines) >= _MAX_ITEMS:
            break

    return headlines


# ------------------------------------------------------------------
# Narrative builder
# ------------------------------------------------------------------

def _build_summary(summary, headlines):

    # Ignore publisher marketing summaries
    if summary:

        s_lower = summary.lower()

        if not any(term in s_lower for term in _PUBLISHER_TAGLINES):
            return summary.strip()

    if not headlines:
        return "Financial markets are seeing activity today across major indices and global markets."

    return headlines[0]


# ------------------------------------------------------------------
# Section Builder (Gold Standard structure)
# ------------------------------------------------------------------

def _build_sections(points):

    if not points:
        return []

    # Deterministic positional partition
    volatility = points[0:3]
    drivers = points[3:6]
    sectors = points[6:9]
    risks = points[9:12]

    sections = []

    if volatility:
        sections.append(
            {
                "title": "Markets are volatile",
                "items": volatility,
            }
        )

    if drivers:
        sections.append(
            {
                "title": "Main driver affecting markets",
                "items": drivers,
            }
        )

    if sectors:
        sections.append(
            {
                "title": "Sector impact",
                "items": sectors,
            }
        )

    if risks:
        sections.append(
            {
                "title": "What investors are watching",
                "items": risks,
            }
        )

    return sections


# ------------------------------------------------------------------
# Processor
# ------------------------------------------------------------------

def process_business(summary: str, points: list[str]):

    clean_points = _clean_points(points)

    headlines = _extract_headlines(clean_points)

    narrative = _build_summary(summary, headlines)

    sections = _build_sections(headlines)

    return {
        "summary": narrative,
        "sections": sections
    }