# solomon_core/packets/header_authority.py
# ---------------------------------------------------------------------------
# Phase 44 — Header Authority Guardrails (STRUCTURE ONLY)
# Phase 47.2 — Structural Awareness Clarification
# ---------------------------------------------------------------------------
# PURPOSE:
#   Declare and centralize the invariant that ONLY the Orchestrator
#   may author PacketHeader instances.
#
# STRUCTURAL STATUS (Phase 47.2):
#   • This file is the CANONICAL authority declaration for header authorship
#   • Absence of enforcement is INTENTIONAL, not missing functionality
#   • All enforcement (if ever introduced) must layer on top of this contract
#
# NON-GOALS:
#   • No runtime checks
#   • No decorators
#   • No execution logic
#   • No authority expansion
#
# NOTES:
#   • This file is declarative by design
#   • Additive-only evolution is permitted
# ---------------------------------------------------------------------------

from __future__ import annotations
from typing import Final

# ---------------------------------------------------------------------------
# Canonical Authority Identity
# ---------------------------------------------------------------------------
# String-literal stable by design.
# Used by PacketHeaderMinimal.authority_level.
ORCHESTRATOR_AUTHORITY: Final[str] = "orchestrator_only"

# ---------------------------------------------------------------------------
# Canonical Header Author Registry (DECLARATIVE)
# ---------------------------------------------------------------------------
# This allowlist is intentionally minimal.
# Expansion (if ever required) must be explicit and reviewed.
HEADER_AUTHORS_ALLOWLIST: Final[tuple[str, ...]] = (
    ORCHESTRATOR_AUTHORITY,
)

# ---------------------------------------------------------------------------
# Documentation-Only Structural Rule
# ---------------------------------------------------------------------------
# This rule is authoritative as documentation and schema intent.
# It is NOT an enforcement hook.
HEADER_AUTHORING_RULE: Final[str] = (
    "PacketHeader instances are authored exclusively by the Orchestrator. "
    "All other subsystems must treat headers as immutable and opaque. "
    "Lack of runtime enforcement is intentional and compliant with design."
)
