"""
solomon_core.docintel.intent
Intent Mediation & Materialization Layer

AUTHORITATIVE NOTES
-------------------
• This package defines the ONLY lawful path from user prompt → execution intent
• All artifacts here are either:
    - pre-authoritative (CBIC, mediation)
    - authoritative (ExplicitIntent)
• No execution logic exists in this layer
• No inference, no defaults, no retries
• Orchestrator consumes ExplicitIntent ONLY

PHASES
------
• Phase 55 — Explicit Intent Materialization (user-confirmed)
• Phase 56 — Lawful Intent Materialization (cardinality collapse)
"""

# ---------------------------------------------------------------------------
# Mediation (Pre-Authority)
# ---------------------------------------------------------------------------

from solomon_core.docintel.intent.mediation_engine import MediationEngine

# ---------------------------------------------------------------------------
# CBIC Models (Pre-Authority Artifacts)
# ---------------------------------------------------------------------------

from solomon_core.docintel.intent.cbic_models import (
    ConstraintBoundIntentCandidate,
    CBICSufficiencyState,
    DocumentArtifact,
)

# ---------------------------------------------------------------------------
# Explicit Intent (Authoritative Artifact)
# ---------------------------------------------------------------------------

from solomon_core.docintel.intent.explicit_intent import ExplicitIntent

# ---------------------------------------------------------------------------
# Intent Upgrade Paths (ONLY lawful authority transitions)
# ---------------------------------------------------------------------------

from solomon_core.docintel.intent.intent_upgrade import (
    upgrade_cbic_to_explicit_intent,     # Phase 55 (user-confirmed)
    materialize_intent_from_cbics,        # Phase 56 (cardinality collapse)
)

# ---------------------------------------------------------------------------
# Public Contract
# ---------------------------------------------------------------------------

__all__ = [
    # Mediation
    "MediationEngine",

    # CBIC
    "ConstraintBoundIntentCandidate",
    "CBICSufficiencyState",
    "DocumentArtifact",

    # Explicit Intent
    "ExplicitIntent",

    # Upgrade paths
    "upgrade_cbic_to_explicit_intent",
    "materialize_intent_from_cbics",
]
