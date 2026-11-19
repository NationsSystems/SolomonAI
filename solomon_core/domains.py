# solomon_core/domains.py
# ---------------------------------------------------------------
# Phase 23.5 — Centralized Domain Definitions (Final Standard)
#
# Purpose:
#   • Provide a single authoritative source for ALL domain constants.
#   • Eliminate string drift and cross-module inconsistencies.
#   • Power strict-schema DocIntel workflows (Phase 23 → Phase 24).
#   • Backwards-compatible with all earlier DOMAIN_* references.
#
# Zero dependencies — safe to import anywhere in Solomon.
# ---------------------------------------------------------------

# =========================
# Core Domains
# =========================
CORE = "core"
DIAGNOSTICS = "diagnostics"
GENERIC = "generic"
DOCUMENT_INTELLIGENCE = "document_intelligence"


# =========================
# DocIntel — Expanded Domain Set (Option B)
# =========================
BID = "bid"
PROPOSAL = "proposal"
ESTIMATE = "estimate"
CONTRACT = "contract"
INVOICE = "invoice"
SPECIFICATION = "specification"
PROCUREMENT = "procurement"

# Catch-all category for documents that cannot be categorized
GENERIC_DOCUMENT = "generic_document"


# =========================
# Compatibility Layer (Phase 23.5)
# These aliases maintain compatibility with older modules
# expecting DOMAIN_* names. No code elsewhere must change.
# =========================
DOMAIN_CORE = CORE
DOMAIN_DIAGNOSTICS = DIAGNOSTICS
DOMAIN_GENERIC = GENERIC
DOMAIN_DOCINTEL = DOCUMENT_INTELLIGENCE

DOMAIN_BID = BID
DOMAIN_PROPOSAL = PROPOSAL
DOMAIN_ESTIMATE = ESTIMATE
DOMAIN_CONTRACT = CONTRACT
DOMAIN_INVOICE = INVOICE
DOMAIN_SPECIFICATION = SPECIFICATION
DOMAIN_PROCUREMENT = PROCUREMENT
DOMAIN_GENERIC_DOCUMENT = GENERIC_DOCUMENT


# =========================
# Export List
# =========================
__all__ = [
    # Core domains
    "CORE",
    "DIAGNOSTICS",
    "GENERIC",
    "DOCUMENT_INTELLIGENCE",

    # DocIntel domains (Option B)
    "BID",
    "PROPOSAL",
    "ESTIMATE",
    "CONTRACT",
    "INVOICE",
    "SPECIFICATION",
    "PROCUREMENT",
    "GENERIC_DOCUMENT",

    # Compatibility alias names
    "DOMAIN_CORE",
    "DOMAIN_DIAGNOSTICS",
    "DOMAIN_GENERIC",
    "DOMAIN_DOCINTEL",
    "DOMAIN_BID",
    "DOMAIN_PROPOSAL",
    "DOMAIN_ESTIMATE",
    "DOMAIN_CONTRACT",
    "DOMAIN_INVOICE",
    "DOMAIN_SPECIFICATION",
    "DOMAIN_PROCUREMENT",
    "DOMAIN_GENERIC_DOCUMENT",
]
