# solomon_domains/registry.py
# ---------------------------------------------------------------
# Domain Registry — Declarative Boundary Layer
#
# PURPOSE:
#   • Provide a centralized, non-core registry of domain identifiers
#   • Decouple business/domain vocabulary from solomon_core
#   • Prepare for future JSON-backed domain declarations
#
# GUARANTEES:
#   • No logic
#   • No heuristics
#   • No regex
#   • No routing
#   • Safe to import anywhere
#
# Phase Status:
#   • Introduced post-Phase 26 (non-breaking)
#   • Shadow registry only (no migration yet)
# ---------------------------------------------------------------


# =========================
# Domain Identifiers
# =========================

BID = "bid"
PROPOSAL = "proposal"
ESTIMATE = "estimate"
CONTRACT = "contract"
INVOICE = "invoice"
SPECIFICATION = "specification"
PROCUREMENT = "procurement"

# Catch-all document classification
GENERIC_DOCUMENT = "generic_document"


# =========================
# Registry Export
# =========================

ALL_DOMAINS = {
    BID,
    PROPOSAL,
    ESTIMATE,
    CONTRACT,
    INVOICE,
    SPECIFICATION,
    PROCUREMENT,
    GENERIC_DOCUMENT,
}


def is_valid_domain(value: str) -> bool:
    """
    Lightweight guardrail.
    Ensures domain checks do not rely on string comparisons scattered in code.
    """
    return value in ALL_DOMAINS


__all__ = [
    "BID",
    "PROPOSAL",
    "ESTIMATE",
    "CONTRACT",
    "INVOICE",
    "SPECIFICATION",
    "PROCUREMENT",
    "GENERIC_DOCUMENT",
    "ALL_DOMAINS",
    "is_valid_domain",
]
