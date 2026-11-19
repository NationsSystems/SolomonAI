# ------------------------------------------------------------------
# FILE: solomon_core/web_lane/processors/sports_processor.py
# ------------------------------------------------------------------
# SPORTS PROCESSOR
#
# Purpose:
#   Organize sports-related fragments into structured sections
#   aligned with the Web Lane presentation standard.
#
# Design constraints:
#   • Deterministic
#   • No LLM usage
#   • No inference or forecasting
#   • Only organize signals already present
#
# Output contract:
#   {
#       "summary": "...",
#       "sections": [
#           {"title": "...", "items": [...]}
#       ]
#   }
# ------------------------------------------------------------------

from typing import List, Dict
import re


# ------------------------------------------------------------------
# Noise Filters
# ------------------------------------------------------------------

_PROMO_TERMS = (
    "subscribe",
    "sign up",
    "newsletter",
    "watch live",
    "stream now",
    "tickets",
)

_NAV_TERMS = (
    "standings",
    "schedule",
    "teams",
    "players",
    "stats",
)

_MAX_ITEMS = 12


# ------------------------------------------------------------------
# Sanitization
# ------------------------------------------------------------------

def _clean_points(points: List[str]) -> List[str]:

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

        clean.append(s)

    return clean[:_MAX_ITEMS]


# ------------------------------------------------------------------
# Summary Builder
# ------------------------------------------------------------------

def _build_summary(summary: str, points: List[str]) -> str:

    if summary and summary.strip():
        return summary.strip()

    if not points:
        return "Latest sports updates and game results from major leagues."

    return points[0]


# ------------------------------------------------------------------
# Section Builder (deterministic partition)
# ------------------------------------------------------------------

def _build_sections(points: List[str]) -> List[Dict]:

    if not points:
        return []

    results = points[0:3]
    highlights = points[3:6]
    upcoming = points[6:9]
    notes = points[9:12]

    sections = []

    if results:
        sections.append(
            {
                "title": "Latest Results",
                "items": results,
            }
        )

    if highlights:
        sections.append(
            {
                "title": "Game Highlights",
                "items": highlights,
            }
        )

    if upcoming:
        sections.append(
            {
                "title": "Upcoming Games",
                "items": upcoming,
            }
        )

    if notes:
        sections.append(
            {
                "title": "Additional Notes",
                "items": notes,
            }
        )

    return sections


# ------------------------------------------------------------------
# Public Processor
# ------------------------------------------------------------------

def process_sports(summary: str, points: List[str]) -> Dict:

    clean_points = _clean_points(points)

    narrative = _build_summary(summary, clean_points)

    sections = _build_sections(clean_points)

    return {
        "summary": narrative,
        "sections": sections
    }