# solomon_core/docintel/extractors/explicit_structural_signal_extractor.py
# ---------------------------------------------------------------------------
# DocIntel Structural Signal Extractor — Explicit Layout Signals Only
#
# PURPOSE:
#   Detect non-semantic structural signals in bid documents that are
#   explicitly observable from text layout and content density.
#
# SCOPE (SIGNALS ONLY — INFORMATIONAL):
#   • Presence of table-like structures
#   • Line-item style rows (count only)
#   • Numeric density indicators
#
# HARD PROHIBITIONS:
#   • NO inference
#   • NO interpretation
#   • NO estimating logic
#   • NO semantic grouping
#
# OUTPUT:
#   Informational structural signals only.
#   Absence is a valid and expected result.
# ---------------------------------------------------------------------------

from typing import List, Dict
import re


# ---------------------------------------------------------------------------
# Explicit Structural Indicators (STRICT)
# ---------------------------------------------------------------------------

NUMERIC_TOKEN_PATTERN = re.compile(r"\d")
PIPE_TABLE_PATTERN = re.compile(r"\|.+\|")
MULTI_SPACE_PATTERN = re.compile(r"\s{4,}")  # tightened to reduce prose noise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_structural_signals(
    *,
    document_id: str,
    document_text: str,
) -> List[Dict]:
    """
    Extract explicit, non-semantic structural signals from document text.

    These signals are informational only and do not imply meaning.
    """

    if not document_text or not isinstance(document_text, str):
        return []

    results: List[Dict] = []

    lines = document_text.splitlines()

    numeric_lines = 0
    table_like_lines = 0
    line_item_candidates = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # ------------------------------------------------------------
        # Pipe-delimited tables (highest-confidence structural signal)
        # ------------------------------------------------------------
        if PIPE_TABLE_PATTERN.search(stripped):
            table_like_lines += 1
            continue  # prevent double-counting this line

        # ------------------------------------------------------------
        # Multi-column spacing (line-item candidate)
        # ------------------------------------------------------------
        if MULTI_SPACE_PATTERN.search(stripped):
            line_item_candidates += 1

        # ------------------------------------------------------------
        # Numeric density (lowest-confidence, informational)
        # ------------------------------------------------------------
        if NUMERIC_TOKEN_PATTERN.search(stripped):
            numeric_lines += 1

    # ------------------------------------------------------------
    # Emit signals only if present
    # ------------------------------------------------------------

    if table_like_lines > 0:
        results.append({
            "signal_type": "table_structure_present",
            "document_id": document_id,
            "line_count": table_like_lines,
        })

    if line_item_candidates > 0:
        results.append({
            "signal_type": "line_item_like_rows",
            "document_id": document_id,
            "line_count": line_item_candidates,
        })

    if numeric_lines > 0:
        results.append({
            "signal_type": "numeric_density_present",
            "document_id": document_id,
            "line_count": numeric_lines,
        })

    return results
