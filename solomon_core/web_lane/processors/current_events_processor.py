# ------------------------------------------------------------------
# FILE: solomon_core/web_lane/processors/current_events_processor.py
# ------------------------------------------------------------------

from typing import List, Dict
import re


# ------------------------------------------------------------------
# Filters
# ------------------------------------------------------------------

_VIDEO_PATTERNS = (
    "youtube",
    "watch",
    "video",
)

_QUESTION_PATTERNS = (
    "why",
    "what",
    "how",
    "could",
    "would",
    "should",
)

_MAX_POINT_LENGTH = 240


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _is_noise(text: str) -> bool:

    if not text:
        return True

    s = text.strip().lower()

    if not s:
        return True

    for p in _VIDEO_PATTERNS:
        if p in s:
            return True

    # Avoid embedding questions as bullets
    if s.endswith("?"):
        return True

    words = s.split()

    if words and words[0] in _QUESTION_PATTERNS:
        return True

    return False


def _dedupe(items: List[str]) -> List[str]:

    seen = set()
    result = []

    for item in items:

        key = item.lower().strip()

        if key not in seen:
            seen.add(key)
            result.append(item.strip())

    return result


# ------------------------------------------------------------------
# Fragment extraction (sentence safe)
# ------------------------------------------------------------------

def _extract_fact_fragment(text: str) -> str:

    if not text:
        return ""

    s = text.strip()
    s = re.sub(r"\s+", " ", s)

    if len(s) > _MAX_POINT_LENGTH:

        cut = s[:_MAX_POINT_LENGTH]

        sentence_break = max(
            cut.rfind("."),
            cut.rfind("!"),
            cut.rfind("?"),
        )

        if sentence_break > 80:
            s = cut[: sentence_break + 1]
        else:
            s = cut

    s = s.rstrip(" .,-")

    return s


# ------------------------------------------------------------------
# Bullet normalization
# ------------------------------------------------------------------

def _clean_points(points: List[str]) -> List[str]:

    clean = []

    for p in points:

        if not isinstance(p, str):
            continue

        s = p.strip()

        if not s:
            continue

        if _is_noise(s):
            continue

        fragment = _extract_fact_fragment(s)

        if fragment:
            clean.append(fragment)

    clean = _dedupe(clean)

    return clean[:12]


# ------------------------------------------------------------------
# Summary normalization
# ------------------------------------------------------------------

def _clean_summary(summary: str) -> str:

    if not summary:
        return ""

    s = summary.strip()
    s = re.sub(r"\s+", " ", s)

    if len(s) > 520:

        cut = s[:520]

        end = max(cut.rfind("."), cut.rfind("!"), cut.rfind("?"))

        if end > 220:
            s = cut[: end + 1]
        else:
            s = cut

    return s


# ------------------------------------------------------------------
# Deterministic summary selection
# ------------------------------------------------------------------

def _choose_summary(clean_summary: str, points: List[str]) -> str:

    if clean_summary:
        return clean_summary

    if points:
        return points[0]

    return "No current event information available."


# ------------------------------------------------------------------
# Section builder (Gold Standard structure)
# ------------------------------------------------------------------

def _build_sections(points: List[str]) -> List[Dict]:

    if not points:
        return []

    sections = []

    # Deterministic positional partition
    military = points[0:3]
    leadership = points[3:5]
    unrest = points[5:8]
    conditions = points[8:12]

    if military:
        sections.append(
            {
                "title": "Military conflict and escalation",
                "items": military,
            }
        )

    if leadership:
        sections.append(
            {
                "title": "Leadership developments",
                "items": leadership,
            }
        )

    if unrest:
        sections.append(
            {
                "title": "Civil unrest and protests",
                "items": unrest,
            }
        )

    if conditions:
        sections.append(
            {
                "title": "Conditions inside the country",
                "items": conditions,
            }
        )

    return sections


# ------------------------------------------------------------------
# Public processor
# ------------------------------------------------------------------

def process_current_events(summary: str, points: List[str]) -> Dict:

    clean_points = _clean_points(points)
    clean_summary = _clean_summary(summary)

    chosen_summary = _choose_summary(clean_summary, clean_points)

    if clean_points and chosen_summary and clean_points[0].strip().lower() == chosen_summary.strip().lower():
        clean_points = clean_points[1:]

    sections = _build_sections(clean_points)

    return {
        "summary": chosen_summary,
        "sections": sections,
    }