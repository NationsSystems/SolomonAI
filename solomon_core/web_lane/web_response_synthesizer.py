# ------------------------------------------------------------------
# FILE: solomon_core/web_lane/web_response_synthesizer.py
# ------------------------------------------------------------------
# WEB RESPONSE SYNTHESIZER
#
# Purpose:
# Convert raw web lane text into structured response data.
#
# Contract:
# - Non-authoritative formatting layer
# - Never alters underlying data
# - Never suppresses information
# - Never generates HTML
# - Backend returns TEXT only (BEI contract alignment)
# ------------------------------------------------------------------

import re
from typing import List, Dict, Any
from solomon_core.logger import get_logger

logger = get_logger("solomon_core.web_lane.web_response_synthesizer")


# ------------------------------------------------------------------
# Sentence splitting
# ------------------------------------------------------------------
_SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')


# ------------------------------------------------------------------
# Summary selection helpers
# ------------------------------------------------------------------
_NUMBER_RE = re.compile(r"\d")

_BAD_SUMMARY_PHRASES = {
    "tickets",
    "experience",
    "community",
    "showtimes",
    "movie club",
    "refine search",
    "watch trailers",
}


# ------------------------------------------------------------------
# HTML guard (legacy safety)
# ------------------------------------------------------------------
_HTML_WEB_SUMMARY_RE = re.compile(r"<div\s+class=\"web-summary\">", re.IGNORECASE)


def _already_rendered_html(text: Any) -> bool:
    if not isinstance(text, str):
        return False
    return bool(_HTML_WEB_SUMMARY_RE.search(text))


# ------------------------------------------------------------------
# HTML stripper (safety fallback)
# ------------------------------------------------------------------
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def _strip_html(text: str) -> str:
    if not text:
        return ""
    return _HTML_TAG_RE.sub("", text).strip()


# ------------------------------------------------------------------
# Input normalization
# ------------------------------------------------------------------
def _normalize_input_text(data: Any) -> str:

    if isinstance(data, str):
        return data

    if isinstance(data, dict):

        parts = []

        if isinstance(data.get("text"), str):
            parts.append(data["text"])

        snippets = data.get("snippets")
        if isinstance(snippets, list):
            parts.extend([s for s in snippets if isinstance(s, str)])

        extras = data.get("extras")
        if isinstance(extras, list):
            parts.extend([e for e in extras if isinstance(e, str)])

        return "\n".join(parts)

    return ""


# ------------------------------------------------------------------
# Sentence utilities
# ------------------------------------------------------------------
def _split_sentences(text: str) -> List[str]:
    if not text:
        return []

    parts = _SENTENCE_SPLIT_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


# ------------------------------------------------------------------
# Paragraph rule enforcement (Phase 88 spec)
# ------------------------------------------------------------------
def _enforce_summary_limits(text: str) -> str:

    if not text:
        return text

    sentences = _split_sentences(text)

    sentences = sentences[:2]

    combined = " ".join(sentences)

    words = combined.split()

    if len(words) > 75:
        combined = " ".join(words[:75])

    return combined


# ------------------------------------------------------------------
# List rule enforcement (Phase 88 spec)
# ------------------------------------------------------------------
def _enforce_list_limits(items: List[str]) -> List[str]:

    if not items:
        return []

    cleaned = [i for i in items if isinstance(i, str) and len(i) > 10]

    if len(cleaned) < 3:
        return cleaned

    return cleaned[:5]


# ------------------------------------------------------------------
# Summary selector
# ------------------------------------------------------------------
def _choose_best_summary(sentences: List[str]) -> str:

    if not sentences:
        return ""

    scored = []

    for s in sentences[:8]:

        score = 0
        lower = s.lower()

        if _NUMBER_RE.search(s):
            score += 2

        if len(s) > 60:
            score += 1

        if any(p in lower for p in _BAD_SUMMARY_PHRASES):
            score -= 2

        scored.append((score, s))

    scored.sort(reverse=True)

    return scored[0][1]


# ------------------------------------------------------------------
# Bullet extraction
# ------------------------------------------------------------------
def _extract_points(sentences: List[str]) -> List[str]:

    points = []

    for s in sentences[1:]:

        if len(points) >= 5:
            break

        if len(s) < 20:
            continue

        points.append(s)

    return points


# ------------------------------------------------------------------
# Archetype renderers
# ------------------------------------------------------------------
def _render_universal(summary: str, points: List[str]) -> str:

    output = []

    output.append("Quick Summary")
    output.append(summary)
    output.append("")

    if points:
        output.append("Key Information")
        for p in points[:5]:
            output.append(f"• {p}")
        output.append("")

    output.append("Additional Context")
    output.append("Information sourced from live web results.")
    output.append("")

    output.append("Related Details")
    output.append("Additional information may be available from the source query.")

    return "\n".join(output)


def _render_weather(summary: str, points: List[str]) -> str:

    output = []

    output.append("Weather Summary")
    output.append(summary)
    output.append("")

    if points:
        output.append("Forecast Details")
        for p in points[:5]:
            output.append(f"• {p}")

    return "\n".join(output)


def _render_business(summary: str, points: List[str]) -> str:

    output = []

    output.append("Market Summary")
    output.append(summary)
    output.append("")

    if points:
        output.append("Key Market Signals")
        for p in points[:5]:
            output.append(f"• {p}")

    return "\n".join(output)


def _render_entertainment(summary: str, points: List[str]) -> str:

    output = []

    output.append("Entertainment Overview")
    output.append(summary)
    output.append("")

    if points:
        output.append("Highlights")
        for p in points[:5]:
            output.append(f"• {p}")

    return "\n".join(output)


def _render_current_events(summary: str, points: List[str]) -> str:

    output = []

    output.append("Current Events Summary")
    output.append(summary)
    output.append("")

    if points:
        output.append("Key Developments")
        for p in points[:5]:
            output.append(f"• {p}")

    return "\n".join(output)


# ------------------------------------------------------------------
# Response synthesizer
# ------------------------------------------------------------------
def synthesize_web_response(
    text: Any,
    *,
    category: str = "general",
) -> Dict:

    logger.info(
        "[WEB_SYNTH][ENTRY] category=%s type=%s",
        category,
        type(text).__name__,
    )

    if _already_rendered_html(text):
        logger.warning("[WEB_SYNTH][HTML_DETECTED] stripping legacy html")
        text = _strip_html(text)

    normalized_text = _normalize_input_text(text)

    logger.info(
        "[WEB_SYNTH][NORMALIZED] chars=%d preview=%s",
        len(normalized_text),
        normalized_text[:120] if normalized_text else None,
    )

    sentences = _split_sentences(normalized_text)

    logger.info(
        "[WEB_SYNTH][SENTENCE_SPLIT] count=%d",
        len(sentences),
    )

    if not sentences:
        logger.warning("[WEB_SYNTH][EMPTY_SENTENCES]")
        return {
            "answer": "No web information available.",
            "points": [],
            "category": category,
        }

    summary = _choose_best_summary(sentences)

    summary = _enforce_summary_limits(summary)

    logger.info(
        "[WEB_SYNTH][SUMMARY_SELECTED] preview=%s",
        summary[:120] if summary else None,
    )

    points = _extract_points(sentences)

    points = _enforce_list_limits(points)

    logger.info(
        "[WEB_SYNTH][POINTS_EXTRACTED] count=%d",
        len(points),
    )

    # ------------------------------------------------------------------
    # Archetype routing
    # ------------------------------------------------------------------

    if category == "weather":
        answer = _render_weather(summary, points)

    elif category == "current_events":
        answer = _render_current_events(summary, points)

    elif category == "entertainment":
        answer = _render_entertainment(summary, points)

    elif category == "business":
        answer = _render_business(summary, points)

    else:
        answer = _render_universal(summary, points)

    return {
        "answer": answer,
        "points": points,
        "category": category,
    }