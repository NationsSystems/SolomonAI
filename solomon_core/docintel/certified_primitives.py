"""
Solomon AI — Certified DocIntel Primitive Declarations
Phase: 72 — BEI Enablement
Status: STATIC · CONTROL-ONLY · FAIL-CLOSED

This module declares Certified Analysis Primitives for DocIntel.
It is the ONLY location where primitives are certified.

HARD CONSTRAINTS:
- No execution
- No inference
- No intent logic
- No formatting or presentation
- Static, inspectable declarations only
"""

from solomon_core.docintel.certified_primitive_registry import (
    CertifiedPrimitiveRegistry,
    CertifiedPrimitiveRecord,
    PrimitiveIdentity,
    CertificationStatus,
    EvidenceRequirements,
    IOContract,
)

# ---------------------------------------------------------------------------
# Registry Instance (Singleton by import)
# ---------------------------------------------------------------------------

REGISTRY = CertifiedPrimitiveRegistry()

# ---------------------------------------------------------------------------
# BEI — Bid Evidence Intelligence
# ---------------------------------------------------------------------------

REGISTRY.register(
    CertifiedPrimitiveRecord(
        identity=PrimitiveIdentity(
            name="BEI.Document.Extract",
            version="v1",
        ),
        status=CertificationStatus.CERTIFIED,
        io_contract=IOContract(
            input_schema_id="bei.document.extract.input.v1",
            output_schema_id="bei.document.extract.output.v1",
        ),
        evidence=EvidenceRequirements(
            # Evidence sources are declarative identifiers only
            required_sources=(
                "document_text",
                "structural_sections",
            ),
            allow_ambiguity=False,
        ),
        metadata={
            "domain": "bei",
            "description": "Extract bid-relevant evidence from construction documents",
        },
    )
)

# ---------------------------------------------------------------------------
# Explicit Non-Capabilities
# ---------------------------------------------------------------------------

def __getattr__(name: str):
    raise AttributeError(
        f"certified_primitives has no capability '{name}'. "
        "This module is declaration-only."
    )
