# ------------------------------------------------------------------
# FILE: solomon_core/web_lane/processors/entertainment_processor.py
# ------------------------------------------------------------------

from typing import List, Dict
import re


# ------------------------------------------------------------------
# Noise Filters
# ------------------------------------------------------------------

_PROMO_TERMS = (
    "earn points",
    "rewards",
    "scan at the box office",
    "movie club",
    "unlock rewards",
    "sign up",
    "fanalert",
    "promotional code",
    "purchase two imax tickets",
    "redeem",
    "fandango",
    "account",
    "terms apply",
)

_NAV_TERMS = (
    "showtimes & tickets",
    "tickets at",
    "movies in theaters now",
    "featured movies",
    "coming soon",
    "filter by",
    "premium offerings",
    "private theatre rentals",
    "imax",
    "dolby cinema",
    "4dx",
    "prime at amc",
    "eventscoming soon",
)

_SEPARATOR_PATTERN = re.compile(r"[·|]")

_MAX_LENGTH = 80


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _is_noise(text: str) -> bool:

    s = text.lower()

    if _SEPARATOR_PATTERN.search(text):
        return True

    for term in _PROMO_TERMS:
        if term in s:
            return True

    for term in _NAV_TERMS:
        if term in s:
            return True

    return False


def _looks_like_narrative(text: str) -> bool:
    """
    Reject descriptive sentences instead of titles.
    """

    s = text.lower()

    narrative_words = (
        "bring",
        "features",
        "includes",
        "offers",
        "delivers",
        "experience",
        "stories",
        "adventure",
        "thrills",
        "plots",
        "twists",
        "premieres",
    )

    for w in narrative_words:
        if w in s:
            return True

    return False


def _clean_points(points: List[str]) -> List[str]:

    clean = []

    for p in points:

        if not isinstance(p, str):
            continue

        s = p.strip()

        if not s:
            continue

        if len(s) > _MAX_LENGTH:
            continue

        if _is_noise(s):
            continue

        if _looks_like_narrative(s):
            continue

        clean.append(s)

    result = []
    seen = set()

    for c in clean:

        key = c.lower()

        if key not in seen:
            seen.add(key)
            result.append(c)

    return result[:9]


# ------------------------------------------------------------------
# Movie title extraction
# ------------------------------------------------------------------

_TITLE_PATTERN = re.compile(
    r"\b[A-Z][A-Za-z0-9:!'\-]{2,}(?:\s+[A-Z][A-Za-z0-9:!'\-]{1,}){0,4}\b"
)

_INVALID_TITLE_WORDS = (
    "featured",
    "movies",
    "showtimes",
    "tickets",
    "filter",
    "offerings",
    "events",
)


def _extract_titles(points: List[str]) -> List[str]:

    titles = []

    for p in points:

        matches = _TITLE_PATTERN.findall(p)

        for m in matches:

            s = m.strip()

            if len(s.split()) < 2:
                continue

            if any(bad in s.lower() for bad in _INVALID_TITLE_WORDS):
                continue

            if len(s.split()) > 5:
                continue

            titles.append(s)

    result = []
    seen = set()

    for t in titles:

        key = t.lower()

        if key not in seen:
            seen.add(key)
            result.append(t)

    return result[:5]


# ------------------------------------------------------------------
# Summary Builder
# ------------------------------------------------------------------

def _build_summary(points: List[str]) -> str:

    titles = _extract_titles(points)

    if titles:

        title_list = ", ".join(titles[:3])

        return (
            f"Here are some movies currently playing in theaters or opening soon, "
            f"including {title_list}. Availability may vary by theater and location."
        )

    return (
        "Here are some movies currently playing in theaters or opening soon. "
        "Availability varies depending on your location."
    )


# ------------------------------------------------------------------
# Section Builder (Gold Standard Layout)
# ------------------------------------------------------------------

def _build_sections(points: List[str]) -> List[Dict]:

    if not points:
        return []

    major = points[:3]
    upcoming = points[3:6]
    indie = points[6:9]

    sections = []

    if major:
        sections.append(
            {
                "title": "Major or wide releases",
                "items": major
            }
        )

    if upcoming:
        sections.append(
            {
                "title": "Notable upcoming releases",
                "items": upcoming
            }
        )

    if indie:
        sections.append(
            {
                "title": "Limited or indie releases",
                "items": indie
            }
        )

    return sections


# ------------------------------------------------------------------
# Public Processor
# ------------------------------------------------------------------

def process_entertainment(summary: str, points: List[str]) -> Dict:

    clean_points = _clean_points(points)

    if not clean_points:

        synthesized_summary = _build_summary([])

        return {
            "summary": synthesized_summary,
            "sections": [],
        }

    synthesized_summary = _build_summary(clean_points)

    sections = _build_sections(clean_points)

    return {
        "summary": synthesized_summary,
        "sections": sections,
    }