# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei_single_summary.py
# ---------------------------------------------------------------------------

from typing import Dict, List

from .bei.bei_helpers import resolve_doc_name, safe_text
from .bei.bei_extractors import (
    extract_salvage_rights,
    extract_schedule_basis,
    extract_pricing_validity_days,
    extract_mobilization_notes,
    extract_drawing_references,
)
from .bei.bei_presentation import render_structured_block


def build_single_summary(
    doc: dict,
    evidence: dict,
    reconciliation: dict | None,
    scout: dict | None,
    metrics: dict,
    critical_list: List[str],
    has_critical: bool,
    base_bid,
    has_signal_fn,
    p_block_fn,
):
    display_name = resolve_doc_name(doc) or "Document"
    bid_date = evidence.get("bid_date")
    text = safe_text(doc) or ""

    salvage_present = extract_salvage_rights(text)
    schedule_basis = extract_schedule_basis(text)
    validity_days = extract_pricing_validity_days(text)
    mobilization_present = extract_mobilization_notes(text)
    drawing_refs = extract_drawing_references(text)

    narrative_parts: List[str] = []
    narrative_parts.append(
        "This submission is a construction proposal with defined scope, pricing structure, and commercial qualifiers."
    )

    if drawing_refs:
        narrative_parts.append(
            "The proposal references multiple drawing sheets that should be reviewed for coordination and completeness."
        )

    if base_bid:
        narrative_parts.append(
            f"The contractor proposes a base bid of {base_bid}, which should be validated against the formal bid form and any addenda prior to leveling."
        )

    if salvage_present:
        narrative_parts.append("The contractor retains salvage rights to materials unless otherwise noted.")

    if metrics.get("exclusions") or has_signal_fn(reconciliation, doc, "exclusions"):
        narrative_parts.append(
            "Broad exclusion language is present and should be reviewed to confirm scope boundaries and responsibility alignment."
        )

    if has_critical:
        narrative_parts.append(
            "Risk indicators are present within the submission and warrant focused estimator review prior to award consideration."
        )

    executive_paragraph = " ".join(narrative_parts)

    included_items: List[str] = []
    if bid_date:
        included_items.append(f"The bid is dated {bid_date}")
    if drawing_refs:
        included_items.append("The proposal includes drawing references")
    if schedule_basis:
        included_items.append(f"Work is based on a standard schedule of {schedule_basis}")

    commercial_items: List[str] = []
    if base_bid:
        commercial_items.append(f"Base Bid: {base_bid}")
    if validity_days:
        commercial_items.append(f"Pricing validity is limited to {validity_days} days")
    if mobilization_present:
        commercial_items.append("Mobilization assumptions are included")

    exclusion_paragraph = None
    if metrics.get("exclusions") or has_signal_fn(reconciliation, doc, "exclusions"):
        exclusion_paragraph = (
            "The proposal contains stated exclusions that should be cross-checked against the specifications and scope matrix "
            "to confirm that no material scope gaps are introduced."
        )

    overall_parts = [
        "Overall: The proposal appears commercially structured; however, the noted exclusions, qualifications, and any flagged risk signals "
        "should be carefully evaluated during bid leveling prior to final award."
    ]

    if metrics.get("structural"):
        overall_parts.append("Structural scope indicators suggest elevated coordination review may be warranted.")

    overall_paragraph = " ".join(overall_parts)

    lines: List[str] = ['<div class="bei-single-summary">']
    lines.append(f"<b>Bid Summary — {display_name}</b>")
    lines.extend(p_block_fn(executive_paragraph))

    if included_items:
        lines.append("<b>Included Operational Items:</b>")
        lines.extend(render_structured_block(included_items))

    if commercial_items:
        lines.append("<b>Key Commercial Conditions:</b>")
        lines.extend(render_structured_block(commercial_items))

    if exclusion_paragraph:
        lines.append("<b>Major Exclusions:</b>")
        lines.extend(p_block_fn(exclusion_paragraph))

    if has_critical and critical_list:
        lines.append("<b>Immediate Risk Signals:</b>")
        lines.extend(render_structured_block(critical_list))

    lines.extend(p_block_fn(overall_paragraph))

    lines.append('<hr class="bei-divider" />')
    lines.append("</div>")

    return "\n".join(lines).strip()