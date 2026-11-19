# solomon_core/due_process/evidence.py
# ------------------------------------------------------------------
# Solomon AI — Due Process Engine (DPE)
# Evidence Packet Primitives (Deterministic / Declarative Only)
#
# PURPOSE:
#   Provide stable, explicit, non-inferential evidence primitives for DPE.
#   This module defines data structures only — NO heuristics, NO defaults,
#   NO I/O, NO runtime mutation, NO implicit inference.
#
# CONTRACT:
#   • Evidence is an explicit packet of facts.
#   • Facts are tri-state: TRUE | FALSE | UNKNOWN (never assumed).
#   • All fields are optional unless explicitly marked required by caller.
#   • This file is safe to import anywhere (no side effects).
#
# NOTE:
#   The DPE will evaluate Laws against Evidence. Evidence generation is a
#   separate concern (classifier/intake pipeline), and must remain explicit.
# ------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Mapping, Optional


# ============================================================================
# Tri-State Primitive (Explicit / No Defaults)
# ============================================================================

class TriState(str, Enum):
    """
    Explicit truth primitive for Due Process facts.

    Rules:
      - TRUE means affirmatively established
      - FALSE means affirmatively negated
      - UNKNOWN means not established (insufficient evidence / not provided)

    UNKNOWN is not FALSE. It must never be treated as a denial.
    """
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


# ============================================================================
# Evidence Packet
# ============================================================================

@dataclass(frozen=True, slots=True)
class EvidencePacket:
    """
    Immutable evidence packet for DPE evaluation.

    Design goals:
      - Stable shape for hashing/auditing
      - Explicit tri-state facts
      - Extensible without breaking old laws

    Conventions:
      - `facts` is the primary law-matching surface area.
      - `meta` is non-matching context (auditing, provenance, version tags).
      - `raw` may include redacted/summary artifacts for audit, but MUST NOT be
        used for law matching (laws match only on `facts`).
    """

    # Deterministic fact surface for law evaluation (ONLY this should match)
    facts: Mapping[str, TriState]

    # Non-matching metadata (provenance, classifier version, timestamps, etc.)
    meta: Mapping[str, Any] = field(default_factory=dict)

    # Optional non-matching raw artifacts (summaries, traces, redacted text, etc.)
    raw: Mapping[str, Any] = field(default_factory=dict)

    def fact(self, key: str) -> TriState:
        """
        Strict fact getter.

        If the key is missing, returns UNKNOWN (explicit non-assertion).
        This is not a 'default truth' — it preserves tri-state semantics.
        """
        v = self.facts.get(key)
        if v is None:
            return TriState.UNKNOWN
        if isinstance(v, TriState):
            return v
        try:
            return TriState(str(v))
        except Exception:
            return TriState.UNKNOWN


# ============================================================================
# Canonical Fact Keys (Namespace Guidance)
# ============================================================================

class EvidenceKeys:
    """
    Canonical namespaces to prevent key sprawl.

    Convention:
      domain.subdomain.fact_name

    Examples:
      - web.external_state_required
      - execution.requires_user_confirmation
      - content.contains_secrets
      - docs.present
      - docs.operation.compare
    """

    WEB_EXTERNAL_STATE_REQUIRED = "web.external_state_required"
    WEB_MUTABLE_EXTERNAL_ACTION = "web.mutable_external_action"

    EXEC_REQUIRES_USER_CONFIRMATION = "execution.requires_user_confirmation"
    EXEC_HAS_IMPLICIT_SIDE_EFFECTS = "execution.has_implicit_side_effects"

    CONTENT_CONTAINS_SECRETS = "content.contains_secrets"
    CONTENT_CONTAINS_PII = "content.contains_pii"

    DOCS_PRESENT = "docs.present"
    DOCS_OPERATION_SUMMARIZE = "docs.operation.summarize"
    DOCS_OPERATION_COMPARE = "docs.operation.compare"
    DOCS_OPERATION_EXTRACT = "docs.operation.extract"
    DOCS_OPERATION_ANALYZE = "docs.operation.analyze"


# ============================================================================
# Builder Helpers (Explicit Only — No Inference)
# ============================================================================

def build_evidence_packet(
    *,
    facts: Mapping[str, TriState],
    meta: Optional[Mapping[str, Any]] = None,
    raw: Optional[Mapping[str, Any]] = None,
) -> EvidencePacket:
    """
    Construct an EvidencePacket with explicit caller-provided facts.

    This function performs no inference and no enrichment.
    It only normalizes containers and preserves explicit tri-state facts.
    """
    meta_out: Dict[str, Any] = dict(meta) if meta else {}
    raw_out: Dict[str, Any] = dict(raw) if raw else {}

    facts_out: Dict[str, TriState] = {}
    for k, v in facts.items():
        if isinstance(v, TriState):
            facts_out[k] = v
        else:
            facts_out[k] = TriState(str(v))

    return EvidencePacket(facts=facts_out, meta=meta_out, raw=raw_out)
