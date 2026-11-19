# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_text_probes.py
# ---------------------------------------------------------------------------
# Phase-safe extraction
# Paragraph formatting + deterministic text probes
# PURE FUNCTIONS — DETERMINISTIC SUPPORT HELPERS
# ---------------------------------------------------------------------------

import re
from typing import List, Optional


# ============================================================================
# Paragraph formatting (deterministic)
# ============================================================================
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_into_paragraphs(text: str) -> List[str]:
    if not text:
        return []

    sentences = _SENTENCE_SPLIT_RE.split(text.strip())
    paragraphs: List[str] = []
    current: List[str] = []

    def flush():
        if current:
            paragraphs.append(" ".join(current).strip())
            current.clear()

    for sentence in sentences:
        if not sentence:
            continue

        candidate = current + [sentence]
        word_count = len(" ".join(candidate).split())

        if len(candidate) > 2 or word_count > 75:
            flush()
            current.append(sentence)
        else:
            current.append(sentence)

    flush()
    return paragraphs


def _p_block(text: str) -> List[str]:
    parts = _split_into_paragraphs(text)
    return [f"<p>{p}</p>" for p in parts if p]


# ============================================================================
# Deterministic text probes (no inference)
# ============================================================================
_BELOW_GRADE_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*'?[\s-]*below\s*grade",
    re.IGNORECASE,
)

_WORK_WEEK_RE = re.compile(
    r"(\d{2})\s*[- ]?hour\s*work\s*week|(\d+)\s*[- ]?hour\s*work\s*week",
    re.IGNORECASE,
)

_MOBILIZATION_TERM_RE = re.compile(
    r"mobilization(?:s)?",
    re.IGNORECASE,
)

_EXTRA_MOBILIZATION_PRICE_RE = re.compile(
    r"\$\s*([\d,]+(?:\.\d{2})?)\s*/\s*ea",
    re.IGNORECASE,
)

_LOOSE_EXTRA_MOBILIZATION_PRICE_RE = re.compile(
    r"\$?([\d,]+(?:\.\d{2})?)\s*/\s*ea",
    re.IGNORECASE,
)


def _extract_below_grade_limit(text: str) -> Optional[str]:
    if not isinstance(text, str) or not text.strip():
        return None
    m = _BELOW_GRADE_RE.search(text)
    if not m:
        return None
    raw = m.group(1)
    if not raw:
        return None
    return f"{raw}' below grade"


def _extract_work_week_assumption(text: str) -> Optional[str]:
    if not isinstance(text, str) or not text.strip():
        return None
    m = _WORK_WEEK_RE.search(text)
    if not m:
        return None
    val = m.group(1) or m.group(2)
    if not val:
        return None
    return f"{val}-hour work week"


def _extract_mobilization_count(text: str) -> Optional[int]:
    """
    Deterministically extract a mobilization count.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    m = re.search(r"\(\s*(\d+)\s*\)\s*mobilization", text, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            return None

    m2 = re.search(r"\b(\d+)\s*mobilization", text, re.IGNORECASE)
    if m2:
        try:
            return int(m2.group(1))
        except Exception:
            return None

    return None


def _extract_extra_mobilization_price(text: str) -> Optional[str]:
    """
    Deterministically extract extra mobilization unit price.

    This probe remains narrow:
    - it only looks in local windows around explicit mobilization mentions
    - it only admits values expressed as /ea
    - it does not infer totals, counts, or pricing conclusions
    """
    if not isinstance(text, str) or not text.strip():
        return None

    for term_match in _MOBILIZATION_TERM_RE.finditer(text):
        start = max(0, term_match.start() - 240)
        end = min(len(text), term_match.end() + 360)
        window = text[start:end]

        m = _EXTRA_MOBILIZATION_PRICE_RE.search(window)
        if m:
            return f"${m.group(1)} each"

        m2 = _LOOSE_EXTRA_MOBILIZATION_PRICE_RE.search(window)
        if m2:
            return f"${m2.group(1)} each"

    return None


def _contains_phrase(text: str, phrase: str) -> bool:
    if not isinstance(text, str) or not phrase:
        return False
    return phrase.lower() in text.lower()


def _bulletize_excerpt(excerpt: Optional[str]) -> List[str]:
    """
    Deterministically turn an excerpt into bullet items.
    HARDENED: only allow true list-like structures.
    """
    if not isinstance(excerpt, str) or not excerpt.strip():
        return []

    from .bei_presentation import bulletize  # local import to avoid cycles

    ex = excerpt.strip()

    if len(ex) > 2000:
        ex = ex[:2000].rstrip() + "\n[Excerpt truncated]"

    has_newlines = "\n" in ex
    has_bullet_markers = any(sym in ex for sym in ("•", "-", "–", "—"))

    if not (has_newlines or has_bullet_markers):
        return []

    try:
        items = bulletize(ex)
    except Exception:
        items = None

    if isinstance(items, list) and items:
        cleaned = [str(i).strip() for i in items if str(i).strip()]

        vetted: List[str] = []

        for item in cleaned:
            t = item.strip()

            if (
                t.endswith(":")
                and t.upper() == t
                and len(t.split()) <= 6
            ):
                continue

            if len(t) <= 2:
                continue

            alpha = sum(c.isalpha() for c in t)
            if len(t) == 0 or (alpha / len(t)) < 0.35:
                continue

            t = re.sub(r"\b([a-zA-Z])\s+([a-zA-Z])\b", r"\1\2", t)

            vetted.append(t)

        if len(vetted) >= 2:
            return vetted[:18]

    lines: List[str] = []

    for ln in ex.splitlines():
        t = ln.strip().lstrip("•").strip()
        if not t:
            continue

        if (
            t.endswith(":")
            and t.upper() == t
            and len(t.split()) <= 6
        ):
            continue

        alpha_chars = sum(c.isalpha() for c in t)
        if alpha_chars < 4:
            continue

        t = re.sub(r"\b([a-zA-Z])\s+([a-zA-Z])\b", r"\1\2", t)

        lines.append(t)

    if len(lines) <= 1:
        return []

    return lines[:18]