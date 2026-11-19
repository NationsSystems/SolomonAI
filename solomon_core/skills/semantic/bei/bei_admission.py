# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_admission.py
# DIRECTORY: solomon_core/skills/semantic/bei/
# ---------------------------------------------------------------------------
# BEI Admission
#
# PURPOSE
#   Evaluate whether already-authorized Bid & Scope Review inputs contain
#   enough explicit estimator-grade evidence to support BEI execution.
#
# CONTRACT
#   This module is not a router.
#   This module does not authorize execution.
#   This module does not inspect workflow intent.
#   This module only evaluates BEI evidence sufficiency after the V3 module
#   contract and Orchestrator have already selected the BEI execution path.
# ---------------------------------------------------------------------------

from __future__ import annotations

import re
from html import escape
from typing import Any, Dict


_OCR_PREFIX_RE = re.compile(
    r"^(?:ao|o&|aÂ«|oÂ«|Â©|Â«|[ao]|&|@|•|-|–|—)\s+",
    re.I,
)


def clean_evidence_line(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    cleaned = value.replace("\u00a0", " ").strip()

    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = _OCR_PREFIX_RE.sub("", cleaned).strip()

    cleaned = cleaned.replace("Â©", "").replace("Â«", "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def has_meaningful_evidence_list(value: Any) -> bool:
    return isinstance(value, list) and any(clean_evidence_line(item) for item in value)


def has_reviewable_bei_evidence(packet: Dict[str, Any]) -> bool:
    facts = packet.get("facts") or {}
    evidence = packet.get("evidence") or {}

    strong_signals = 0
    support_signals = 0

    if facts.get("base_bid"):
        strong_signals += 1

    if has_meaningful_evidence_list(evidence.get("scope")):
        strong_signals += 1

    if has_meaningful_evidence_list(evidence.get("exclusions")):
        strong_signals += 1

    if has_meaningful_evidence_list(evidence.get("clarifications")):
        strong_signals += 1

    if has_meaningful_evidence_list(evidence.get("included")):
        support_signals += 1

    if facts.get("drawing_references_present"):
        support_signals += 1

    if facts.get("schedule_basis") or facts.get("work_week"):
        support_signals += 1

    if facts.get("pricing_validity_days"):
        support_signals += 1

    if facts.get("mobilizations_included") or facts.get("mobilization_language_present"):
        support_signals += 1

    if facts.get("additional_mobilization_price"):
        support_signals += 1

    if facts.get("below_grade_limit"):
        support_signals += 1

    if facts.get("salvage_rights_present"):
        support_signals += 1

    for key in (
        "gpr_included",
        "gpr_excluded",
        "make_safe",
        "hidden_or_hazardous",
        "floor_preparation",
        "temporary_protection",
    ):
        if has_meaningful_evidence_list(evidence.get(key)):
            support_signals += 1

    return strong_signals >= 1 and (strong_signals + support_signals) >= 2


def build_requires_action_packet(document_name: str) -> dict:
    safe_name = escape(document_name or "Document", quote=False)

    answer = (
        '<div class="bei-single-summary">'
        f"<b>Bid & Scope Review Requires Action — {safe_name}</b>"
        "<p>These documents do not contain enough explicit bid, proposal, scope, "
        "pricing, exclusions, alternates, allowances, or estimating evidence to "
        "support an advanced Bid & Scope Review.</p>"
        "<p>Upload construction bid, proposal, scope, exclusions, alternates, "
        "allowances, pricing, addenda, or related preconstruction documents to continue.</p>"
        "</div>"
    )

    return {
        "ok": False,
        "packet_type": "docintel",
        "payload": {
            "answer": answer,
            "bridge": "",
            "report_kind": "bid_scope_review",
            "suggestions": [],
        },
        "verdict": "REQUIRES_ACTION",
    }