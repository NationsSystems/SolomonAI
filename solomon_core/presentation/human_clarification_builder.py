# solomon_core/presentation/human_clarification_builder.py
# ---------------------------------------------------------------------------
# Human Clarification Instruction Builder
# ---------------------------------------------------------------------------
#
# PURPOSE:
#   Convert a reconciliation artifact into deterministic user instructions.
#
# AUTHORITY:
#   • Presentation only
#   • No inference
#   • No ranking
#   • No recommendation
#
# DESIGN:
#   Global numbering across all buckets.
#   Stable ordering = sorted bucket type → insertion order of facts.
#
# SAFE FOR FUTURE UX REPLACEMENT.
# ---------------------------------------------------------------------------

from typing import Dict, List, Tuple


# ============================================================================
# Public API
# ============================================================================

def build_human_clarification_message(
    reconciliation_artifact: Dict,
) -> Tuple[str, Dict[int, Dict]]:
    """
    Returns:
        message_text: str
        option_map: {index -> fact}

    option_map is returned for future routing but NOT used in Phase 76.
    """

    if not reconciliation_artifact:
        return (
            "Human review required, but reconciliation data is missing.",
            {},
        )

    buckets = reconciliation_artifact.get("buckets") or []

    # Only buckets requiring intervention
    actionable = [
        b for b in buckets
        if b.get("conflict") or b.get("multiplicity")
    ]

    if not actionable:
        return (
            "Human review requested, but no selectable conflicts were found.",
            {},
        )

    # Stable deterministic ordering
    actionable = sorted(actionable, key=lambda b: b.get("signal_type") or "")

    lines: List[str] = []
    option_map: Dict[int, Dict] = {}

    lines.append("Human decision required.")
    lines.append("")
    lines.append("Multiple admissible facts exist.")
    lines.append("Select one of the following options.")
    lines.append("")

    counter = 1

    for bucket in actionable:
        signal_type = bucket.get("signal_type")

        lines.append(f"{signal_type.upper()}:")
        for fact in bucket.get("facts") or []:
            doc = fact.get("source_document_id")
            value = fact.get("value")

            option_map[counter] = fact

            lines.append(f"  {counter}) From {doc}")
            counter += 1

        lines.append("")

    lines.append("Type the option number or provide clarification text.")

    return "\n".join(lines), option_map
