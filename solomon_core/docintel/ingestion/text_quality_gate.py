# solomon_core/docintel/ingestion/text_quality_gate.py
# ---------------------------------------------------------------------------
# Text Quality Gate — Deterministic Intake Health Assessment
# ---------------------------------------------------------------------------

from typing import Dict
import re


# ---------------------------------------------------------------------------
# Tunable Thresholds (v2 — reduced false positives on vector PDFs)
# ---------------------------------------------------------------------------

_MIN_TEXT_LEN = 200
_FRACTURE_RATIO_THRESHOLD = 0.03          # raised (was 0.015)
_SHORT_TOKEN_RATIO_THRESHOLD = 0.18
_GLUED_PATTERN_THRESHOLD = 0.005
_STRONG_SIGNAL_MULTIPLIER = 3             # stronger bar for hard fail


# ---------------------------------------------------------------------------
# Precompiled patterns (performance + stability)
# ---------------------------------------------------------------------------

# split-word artifacts like: "exis tin g"
_FRACTURE_PATTERN = re.compile(r"\b[a-z]{3,}\s+[a-z]{1,2}\b")

# glued continuation artifacts like: "mobilizationsin cluded"
_GLUED_PATTERN = re.compile(r"\b[a-z]{7,}\s+[a-z]{3,}\b")

_TOKEN_PATTERN = re.compile(r"\b[a-zA-Z]{2,}\b")
_WORD_PATTERN = re.compile(r"\b\w+\b")

# lines that should be ignored for fracture scoring
_BULLET_LINE = re.compile(r"^\s*[\u2022\-\*\u00ab]")  # bullets and guillemets
_HEADING_LINE = re.compile(r"^[A-Z][A-Za-z\s/]{2,40}$")


# ---------------------------------------------------------------------------
# Signal Helpers
# ---------------------------------------------------------------------------

def _filtered_text_for_fracture(text: str) -> str:
    """
    Remove lines that commonly create false positives in clean vector PDFs.
    Deterministic and cosmetic only.
    """
    lines = text.splitlines()
    kept = []

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue
        if _BULLET_LINE.match(stripped):
            continue
        if _HEADING_LINE.match(stripped):
            continue

        kept.append(stripped)

    return "\n".join(kept)


def _compute_intra_word_fracture_ratio(text: str) -> float:
    """
    Detect split-word artifacts like:
        'exis tin g'
        'sur faces'
    """
    if not text:
        return 0.0

    working = _filtered_text_for_fracture(text)

    matches = _FRACTURE_PATTERN.findall(working)

    tokens = _TOKEN_PATTERN.findall(working)
    denom = max(len(tokens), 1)

    return len(matches) / denom


def _compute_short_token_ratio(text: str) -> float:
    """
    Detect chains of very short tokens.
    """
    tokens = _WORD_PATTERN.findall(text)
    if not tokens:
        return 0.0

    short_tokens = [t for t in tokens if len(t) == 1]
    return len(short_tokens) / len(tokens)


def _compute_glued_continuation_ratio(text: str) -> float:
    """
    Detect patterns like:
        'mobilizationsin cluded'
    """
    if not text:
        return 0.0

    matches = _GLUED_PATTERN.findall(text)

    tokens = _TOKEN_PATTERN.findall(text)
    denom = max(len(tokens), 1)

    return len(matches) / denom


# ---------------------------------------------------------------------------
# Public EQG API
# ---------------------------------------------------------------------------

def evaluate_text_quality(
    text: str,
    *,
    afr_hint: Dict | None = None,
) -> Dict:
    """
    Deterministically assess extracted text integrity.
    """

    if not text or len(text.strip()) < _MIN_TEXT_LEN:
        return {
            "text_health": "SUSPECT",
            "fallback_recommended": True,
            "signals": {
                "reason": "insufficient_text",
            },
            "extraction_method": "vector",
        }

    fracture_ratio = _compute_intra_word_fracture_ratio(text)
    short_ratio = _compute_short_token_ratio(text)
    glued_ratio = _compute_glued_continuation_ratio(text)

    # -------------------------------------------------------
    # Phase 85 tuning — reduce false positives
    # -------------------------------------------------------

    strong_signal = fracture_ratio > (_FRACTURE_RATIO_THRESHOLD * _STRONG_SIGNAL_MULTIPLIER)

    moderate_hits = sum(
        [
            fracture_ratio > _FRACTURE_RATIO_THRESHOLD,
            short_ratio > _SHORT_TOKEN_RATIO_THRESHOLD,
            glued_ratio > _GLUED_PATTERN_THRESHOLD,
        ]
    )

    # require stronger evidence before fallback
    suspect = strong_signal or (moderate_hits >= 2)

    # AFR is advisory only — never authoritative
    afr_flag = False
    if isinstance(afr_hint, dict):
        afr_flag = bool(afr_hint.get("ocr_required"))

    if afr_flag:
        suspect = True

    return {
        "text_health": "SUSPECT" if suspect else "HEALTHY",
        "fallback_recommended": bool(suspect),
        "signals": {
            "fracture_ratio": round(fracture_ratio, 6),
            "short_token_ratio": round(short_ratio, 6),
            "glued_ratio": round(glued_ratio, 6),
            "afr_hint": afr_flag,
            "moderate_hits": moderate_hits,
            "strong_signal": strong_signal,
        },
        "extraction_method": "vector",
    }