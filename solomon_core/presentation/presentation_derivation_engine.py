# ---------------------------------------------------------------------------
# FILE: solomon_core/presentation/presentation_derivation_engine.py
# ---------------------------------------------------------------------------
# Presentation Derivation Engine
#
# Purpose:
#   Compute deterministic business signals used by executive narration.
#
# Authority Model:
#   • This module computes facts.
#   • It does NOT narrate.
#   • It does NOT interpret.
#   • It does NOT recommend.
#
# Inputs:
#   narration_packet (post visibility, post implications)
#
# Output:
#   dict → presentation_derivations
#
# If data cannot be proven → return None.
# ---------------------------------------------------------------------------

from typing import Dict, Any, List, Optional, Set
import re


# ============================================================================
# Public API
# ============================================================================

def compute_presentation_derivations(
    narration_packet: Dict[str, Any]
) -> Dict[str, Any]:

    return {
        "price": _derive_price(narration_packet),
        "exclusions": _derive_exclusion_counts(narration_packet),
        "verification_targets": _derive_verification_targets(narration_packet),
        "mobilization": _derive_mobilization(narration_packet),
    }


# ============================================================================
# Price
# ============================================================================

def _derive_price(packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Determine spread and orientation.

    NEVER invent numbers.

    Phase 85/87:
        • Multi-bid → compute spread
        • Single-bid → surface explicit amount
        • Supports BOTH commercials path and BEI findings fallback
    """

    # --------------------------------------------------
    # Primary path (future structured commercials)
    # --------------------------------------------------
    commercials = (packet.get("commercials") or {}).get("base_bids") or []

    valid = [
        c for c in commercials
        if isinstance(c.get("amount"), (int, float))
    ]

    # --------------------------------------------------
    # 🔵 Phase 87 fallback — derive from BEI findings
    # --------------------------------------------------
    if not valid:
        findings = packet.get("findings") or []

        derived = []

        for f in findings:
            if f.get("signal_type") != "base_bid":
                continue

            for fact in f.get("facts") or []:
                raw_val = fact.get("value")

                if isinstance(raw_val, str):
                    m = re.search(r"[\d,]+(?:\.\d+)?", raw_val)
                    if m:
                        try:
                            amt = float(m.group(0).replace(",", ""))
                            derived.append({
                                "amount": amt,
                                "display_name": fact.get("source_display_name"),
                            })
                        except Exception:
                            pass

        valid = derived

    if not valid:
        return None

    # ---- single bid case ----
    if len(valid) == 1:
        only = valid[0]
        return {
            "single_bid_amount": only.get("amount"),
            "bidder": only.get("display_name"),
        }

    # ------------------------------------------------------------------
    # Multi-bid logic
    # ------------------------------------------------------------------

    sorted_bids = sorted(valid, key=lambda x: x["amount"])

    low = sorted_bids[0]
    high = sorted_bids[-1]

    spread = high["amount"] - low["amount"]

    if low["amount"] == 0:
        percent = None
    else:
        percent = (spread / low["amount"]) * 100.0

    return {
        "spread_amount": spread,
        "spread_percent": percent,
        "low_bidder": low.get("display_name"),
        "high_bidder": high.get("display_name"),
    }


# ============================================================================
# Exclusion Counts
# ============================================================================

def _derive_exclusion_counts(packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:

    findings = packet.get("findings") or []
    documents = packet.get("documents") or []

    if not findings or not documents:
        return None

    counts: Dict[str, int] = {
        doc.get("document_id"): 0 for doc in documents if doc.get("document_id")
    }

    if not counts:
        return None

    for finding in findings:
        if finding.get("signal_type") != "exclusions":
            continue

        facts = finding.get("facts") or []
        for fact in facts:
            doc_id = fact.get("source_document_id")
            if doc_id in counts:
                counts[doc_id] += 1

    return counts


# ============================================================================
# Verification Targets
# ============================================================================

def _derive_verification_targets(packet: Dict[str, Any]) -> Optional[List[str]]:

    findings = packet.get("findings") or []
    documents = packet.get("documents") or []

    if not findings or len(documents) < 2:
        return None

    presence: Dict[str, Set[str]] = {}

    for finding in findings:
        signal_type = finding.get("signal_type")
        if not signal_type:
            continue

        facts = finding.get("facts") or []
        for fact in facts:
            doc_id = fact.get("source_document_id")
            if not doc_id:
                continue

            presence.setdefault(signal_type, set()).add(doc_id)

    all_docs = {
        doc.get("document_id")
        for doc in documents
        if doc.get("document_id")
    }

    if not all_docs:
        return None

    asymmetric: List[str] = []

    for signal_type, seen_docs in presence.items():
        if seen_docs != all_docs:
            asymmetric.append(signal_type)

    if not asymmetric:
        return None

    return sorted(asymmetric)


# ============================================================================
# Mobilization
# ============================================================================

def _derive_mobilization(packet: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    return None