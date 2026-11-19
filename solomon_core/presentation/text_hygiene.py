# solomon_core/presentation/text_hygiene.py
# ---------------------------------------------------------------------------
# Global Presentation Hygiene Layer (GPCL)
# ---------------------------------------------------------------------------
# Purpose:
#   Provide lossless, estimator-safe cosmetic cleanup of working text
#   prior to UI presentation.
#
# Authority:
#   • GLOBAL — applies to all Solomon domains
#   • PRESENTATION ONLY — never used for evidence extraction
#   • LOSSLESS ONLY — no semantic mutation permitted
#   • NUMERIC SAFE — preserves monetary and quantitative fidelity
#
# Design Guarantees:
#   • No changes to original uploaded files
#   • No changes to BEI evidence payloads
#   • No inference or semantic rewriting
#   • Deterministic and auditable
#
# Phase Alignment:
#   Phase 85.A — Estimator-Safe Presentation Contract
#   Phase 85.A-G — Globalization Patch
#   Phase 87.B — Conservative Fracture Hardening
#   Phase 87.C — OCR-Gated Fracture Repair (minimal patch)
# ---------------------------------------------------------------------------

from __future__ import annotations

import re
from typing import Dict, Optional

from solomon_core.logger import get_logger

logger = get_logger("text_hygiene")


# ---------------------------------------------------------------------------
# Encoding cleanup (common OCR artifacts)
# ---------------------------------------------------------------------------

_ENCODING_FIXES = {
    "Â«": "•",
    "Â»": "•",
    "Â ": " ",
    "â€¢": "•",
}


def _cleanup_encoding(text: str) -> str:
    if not text:
        return text

    for bad, good in _ENCODING_FIXES.items():
        text = text.replace(bad, good)

    return text


# ---------------------------------------------------------------------------
# Intra-word fracture repair (HARDENED — Phase 87.B)
# Phase 87.C — now OCR-gated
# ---------------------------------------------------------------------------

"""
Previous behavior was too permissive and could collapse
legitimate word boundaries.

Phase 87.C change:

Fracture repair is now ONLY allowed when explicitly enabled
by upstream execution context (OCR / fractured-text scenarios).

This prevents clean LLM output from being mutated.
"""

_FRACTURE_PATTERN = re.compile(r"\b([A-Za-z]{3,})\s+([a-z]{2,})\b")


def _repair_intra_word_fractures(text: str) -> str:
    if not text:
        return text

    def _join(match: re.Match) -> str:
        left = match.group(1)
        right = match.group(2)

        # Combined length guard (prevents long phrase collapse)
        combined_len = len(left) + len(right)
        if combined_len > 18:
            return match.group(0)

        return left + right

    return _FRACTURE_PATTERN.sub(_join, text)


# ---------------------------------------------------------------------------
# Numeric spacing normalization (STRICTLY SAFE)
# ---------------------------------------------------------------------------

_CURRENCY_SPACE_PATTERN = re.compile(r"\$\s+(?=\d)")
_THOUSAND_SPACE_PATTERN = re.compile(r"(?<=\d)\s+,(?=\d{3}\b)")
_COMMA_GROUP_SPACE_PATTERN = re.compile(r"(?<=\d),(?=\s+\d{3}\b)")


def _normalize_numeric_spacing(text: str) -> str:
    if not text:
        return text

    text = _CURRENCY_SPACE_PATTERN.sub("$", text)
    text = _THOUSAND_SPACE_PATTERN.sub(",", text)
    text = _COMMA_GROUP_SPACE_PATTERN.sub(",", text)

    return text


# ---------------------------------------------------------------------------
# Whitespace normalization
# ---------------------------------------------------------------------------

_MULTI_SPACE_PATTERN = re.compile(r"[ \t]{2,}")


def _normalize_whitespace(text: str) -> str:
    if not text:
        return text

    text = _MULTI_SPACE_PATTERN.sub(" ", text)
    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def apply_presentation_hygiene(
    text: str,
    *,
    enable_fracture_repair: bool = False,
) -> str:
    """
    Global, lossless presentation cleanup.

    Phase 87.C:
        Fracture repair is now explicitly gated.

    External callers should normally rely on the default
    (fracture repair OFF) unless upstream OCR evidence exists.
    """

    if not text:
        return text

    # 🔍 Phase 87 instrumentation — input probe
    try:
        logger.info(
            "[PHASE87][GPCL_INPUT]",
            extra={
                "preview": text[:200],
                "chars": len(text),
                "fracture_enabled": enable_fracture_repair,
            },
        )
    except Exception:
        pass

    original = text

    text = _cleanup_encoding(text)

    # ------------------------------------------------------------------
    # Phase 87.C — gated fracture repair (minimal, deterministic)
    # ------------------------------------------------------------------
    if enable_fracture_repair:
        text = _repair_intra_word_fractures(text)

    text = _normalize_numeric_spacing(text)
    text = _normalize_whitespace(text)

    # 🔍 Phase 87 instrumentation — output probe
    try:
        logger.info(
            "[PHASE87][GPCL_OUTPUT]",
            extra={"preview": text[:200], "chars": len(text)},
        )
    except Exception:
        pass

    return text