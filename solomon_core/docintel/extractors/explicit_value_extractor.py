# solomon_core/docintel/extractors/explicit_value_extractor.py
# ---------------------------------------------------------------------------
# DocIntel Explicit Value Extractor — Explicit Numeric Signals Only
#
# PURPOSE:
#   Detect explicitly stated numeric values in bid documents.
#
# SCOPE (EXPLICIT ONLY):
#   • Lump sum / base bid amounts
#   • Alternates (add / deduct) when labeled
#   • Allowance values
#   • Unit prices ONLY when explicitly labeled
#
# HARD PROHIBITIONS:
#   • NO math
#   • NO totals
#   • NO inference
#   • NO normalization
#   • NO estimating logic
#
# OUTPUT:
#   Structured value signals with direct text evidence.
#
# Absence is a valid and required outcome.
# ---------------------------------------------------------------------------

from typing import List, Dict
import re


# ---------------------------------------------------------------------------
# Canonical Explicit Value Patterns (STRICT)
# ---------------------------------------------------------------------------

# Support BOTH:
#   $396,795.00
#   396,795.00 $
CURRENCY_PATTERN = re.compile(
    r"""
    (?:\$\s?\d{1,3}(?:,\d{3})*(?:\.\d{2})?)      # $123,456.78
    |
    (?:\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s?\$)      # 123,456.78 $
    """,
    re.VERBOSE,
)

UNIT_PRICE_PATTERN = re.compile(
    r"""
    \$\s?
    \d{1,3}(?:,\d{3})*(?:\.\d+)?     # $4,500 or $4500.00
    \s*/\s*
    (sf|lf|sy|ea|hr)
    """,
    re.IGNORECASE | re.VERBOSE,
)

PLAIN_NUMERIC_PATTERN = re.compile(
    r"\b\d{1,3}(?:,\d{3})*(?:\.\d{2})?\b"
)

VALUE_CONTEXT_PATTERNS = {
    "base_bid": [
        "base bid",
        "lump sum",
        "total bid",
    ],
    "allowance": [
        "allowance",
        "allowances",
    ],
    "alternate_add": [
        "add alternate",
        "additive alternate",
    ],
    "alternate_deduct": [
        "deduct alternate",
        "deductive alternate",
    ],
}

EXPLICIT_TOTAL_PHRASES = (
    "total",
    "contract total",
    "estimate total",
    "proposal total",
    "bid total",
)

VALUE_TYPE_NORMALIZATION = {
    "alternate_add": "alternates",
    "alternate_deduct": "alternates",
}

PROXIMITY_FORWARD_LINES = 3
PROXIMITY_BACKWARD_LINES = 1

# ---------------------------------------------------------------------------
# Structural Admission Controls
# ---------------------------------------------------------------------------

_MAX_STRUCTURAL_LINE_LEN = 120
_MIN_STRUCTURAL_LINE_LEN = 3

_UNIT_TOKENS = (
    "/",
    " per ",
    " each",
)

# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _looks_like_unit_price(line_lower: str) -> bool:
    """Deterministic guard to prevent unit-price leakage."""
    if "/" in line_lower:
        return True
    if " per " in line_lower:
        return True
    if " each" in line_lower:
        return True
    return False


def _is_high_confidence_structural_money(line: str, match_text: str) -> bool:
    """
    Deterministic structural admission check.

    Strictly mechanical:
    - no semantics
    - no ML
    - no inference
    """

    if not line:
        return False

    line_stripped = line.strip()
    line_lower = line_stripped.lower()

    # --------------------------------------------------------------
    # Length sanity (reject long narrative prose)
    # --------------------------------------------------------------
    if len(line_stripped) > _MAX_STRUCTURAL_LINE_LEN:
        return False

    if len(line_stripped) < _MIN_STRUCTURAL_LINE_LEN:
        return False

    # --------------------------------------------------------------
    # Must contain exactly one currency occurrence
    # (helps avoid dense narrative sentences)
    # --------------------------------------------------------------
    if len(list(CURRENCY_PATTERN.finditer(line_stripped))) != 1:
        return False

    # --------------------------------------------------------------
    # Unit price exclusion (critical safety)
    # --------------------------------------------------------------
    if UNIT_PRICE_PATTERN.search(line_stripped):
        return False

    if _looks_like_unit_price(line_lower):
        return False

    # --------------------------------------------------------------
    # Reject obvious paragraph-style lines
    # (many words typically indicates narrative)
    # --------------------------------------------------------------
    word_count = len(line_stripped.split())
    if word_count > 12:
        return False

    # --------------------------------------------------------------
    # Require some non-numeric context (label-like)
    # --------------------------------------------------------------
    non_currency = CURRENCY_PATTERN.sub("", line_stripped).strip()
    if not non_currency:
        return False

    return True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_explicit_values(
    *,
    document_id: str,
    document_text: str,
) -> List[Dict]:

    if not document_text or not isinstance(document_text, str):
        return []

    results: List[Dict] = []
    emitted_keys = set()
    lines = document_text.splitlines()

    # ------------------------------------------------------------------
    # PASS 1 — Unit prices
    # ------------------------------------------------------------------
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        for match in UNIT_PRICE_PATTERN.finditer(line):
            key = ("unit_price", idx, match.group())
            if key in emitted_keys:
                continue

            results.append({
                "value_type": "unit_price",
                "document_id": document_id,
                "raw_value": match.group().strip(),
                "context": line,
                "line_index": idx,
            })
            emitted_keys.add(key)

    # ------------------------------------------------------------------
    # PASS 2 — Context labeled currency
    # ------------------------------------------------------------------
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        line_lower = line.lower()

        for value_type, context_phrases in VALUE_CONTEXT_PATTERNS.items():
            if not any(p in line_lower for p in context_phrases):
                continue

            normalized_type = VALUE_TYPE_NORMALIZATION.get(value_type, value_type)

            for match in CURRENCY_PATTERN.finditer(line):
                if UNIT_PRICE_PATTERN.search(match.group()):
                    continue

                key = (normalized_type, idx, match.group())
                if key in emitted_keys:
                    continue

                results.append({
                    "value_type": normalized_type,
                    "document_id": document_id,
                    "raw_value": match.group().strip(),
                    "context": line,
                    "line_index": idx,
                })
                emitted_keys.add(key)

            # forward proximity
            for offset in range(1, PROXIMITY_FORWARD_LINES + 1):
                scan_idx = idx + offset
                if scan_idx >= len(lines):
                    break

                scan_line = lines[scan_idx].strip()
                if not scan_line:
                    continue

                for match in CURRENCY_PATTERN.finditer(scan_line):
                    if UNIT_PRICE_PATTERN.search(match.group()):
                        continue

                    key = (normalized_type, scan_idx, match.group())
                    if key in emitted_keys:
                        continue

                    results.append({
                        "value_type": normalized_type,
                        "document_id": document_id,
                        "raw_value": match.group().strip(),
                        "context": scan_line,
                        "line_index": scan_idx,
                        "proximity_anchor_line": idx,
                    })
                    emitted_keys.add(key)

    # ------------------------------------------------------------------
    # PASS 3 — Explicit totals
    # ------------------------------------------------------------------
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        line_lower = line.lower()

        if not any(p in line_lower for p in EXPLICIT_TOTAL_PHRASES):
            continue

        for match in CURRENCY_PATTERN.finditer(line):
            if UNIT_PRICE_PATTERN.search(match.group()):
                continue

            key = ("base_bid", idx, match.group())
            if key in emitted_keys:
                continue

            results.append({
                "value_type": "base_bid",
                "document_id": document_id,
                "raw_value": match.group().strip(),
                "context": line,
                "line_index": idx,
                "explicit_total_detected": True,
            })
            emitted_keys.add(key)

    # ------------------------------------------------------------------
    # PASS 4 — Guarded standalone currency (existing behavior)
    # ------------------------------------------------------------------
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        matches = list(CURRENCY_PATTERN.finditer(line))
        if not matches:
            continue

        if UNIT_PRICE_PATTERN.search(line):
            continue

        non_currency = CURRENCY_PATTERN.sub("", line).strip()

        if len(non_currency) > 12:
            continue

        for match in matches:
            key = ("base_bid", idx, match.group())
            if key in emitted_keys:
                continue

            results.append({
                "value_type": "base_bid",
                "document_id": document_id,
                "raw_value": match.group().strip(),
                "context": line,
                "line_index": idx,
                "standalone_currency": True,
            })
            emitted_keys.add(key)

    # ------------------------------------------------------------------
    # PASS 5 — Structural admission additive
    # ------------------------------------------------------------------
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        matches = list(CURRENCY_PATTERN.finditer(line))
        if not matches:
            continue

        for match in matches:
            key = ("base_bid", idx, match.group())
            if key in emitted_keys:
                continue

            if not _is_high_confidence_structural_money(line, match.group()):
                continue

            print(
                "[VALUE_EXTRACTOR][STRUCTURAL_ADMIT]",
                f"doc={document_id} line={idx} value={match.group().strip()}",
            )

            results.append({
                "value_type": "base_bid",
                "document_id": document_id,
                "raw_value": match.group().strip(),
                "context": line,
                "line_index": idx,
                "structural_admit": True,
            })
            emitted_keys.add(key)

    return results