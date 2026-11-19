# solomon_core/packets/packet_header.py
# ---------------------------------------------------------------------------
# Phase 44 — Canonical PacketHeader Schema (STRUCTURE ONLY)
# Phase 47.2 — Structural Awareness Clarification
# Phase 60  — ECB (Ephemeral Context Buffer) Observability
# Phase 71  — Request Correlation (NON-AUTHORITATIVE)
# ---------------------------------------------------------------------------
# PURPOSE:
#   Define the immutable data contract for packet headers used by the
#   Orchestrator (Packet Router).
#
# STRUCTURAL STATUS (Phase 47.2):
#   • PacketHeader is a FIRST-CLASS STRUCTURAL ARTIFACT
#   • Presence is REQUIRED at packet construction time
#   • Absence in diagnostics indicates implicit handling, not missing code
#
# NON-GOALS:
#   • No logic
#   • No validation
#   • No routing
#   • No authority
#
# GUARANTEES:
#   • Header-only control plane
#   • Payload remains opaque
#   • Authority remains centralized
#   • Additive-only evolution (Extended fields are optional)
# ---------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional
from datetime import datetime


# ---------------------------------------------------------------------------
# Minimal PacketHeader (REQUIRED — FIRST-CLASS)
# ---------------------------------------------------------------------------

PacketType = Literal[
    "llm",
    "deterministic",
    "skill",
    "diagnostic",   # Explicitly observational; never executable
]

OriginType = Literal[
    "user",
    "system",
    "planner",
    "hflo",
]

DestinationType = Literal[
    "llm",
    "skill_executor",
    "lexicon",
    "ui",
]

AuthorityLevel = Literal[
    "orchestrator_only",
]

PresentationMode = Literal[
    "emitted",
    "constructed",
    "suppressed",
]


@dataclass(frozen=True)
class PacketHeaderMinimal:
    """
    REQUIRED control-plane header.
    This structure is intentionally minimal and universally present.

    Phase 71:
      • request_id is a NON-AUTHORITATIVE correlation identifier
      • Used for tracing, observability, and investigator alignment
      • Absence MUST NOT affect execution semantics
    """
    packet_id: str
    packet_type: PacketType
    origin: OriginType
    destination: DestinationType
    authority_level: AuthorityLevel
    presentation_mode: PresentationMode
    phase_tag: str
    timestamp: str  # ISO-8601 UTC string
    request_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Extended PacketHeader (OPTIONAL / ADDITIVE)
# ---------------------------------------------------------------------------
# NOTE:
#   Extended fields are *structural affordances*, not guarantees.
#   Their absence MUST NOT be interpreted as missing functionality.
# ---------------------------------------------------------------------------

ExecutionMode = Literal[
    "informational",
    "constructed",
    "blocked",
]

RoutingHint = Literal[
    "fast_path",
    "default",
    "isolation",
]

SafetyState = Literal[
    "clear",
    "constrained",
    "blocked",
]

EvidenceState = Literal[
    "explicit",
    "inferred",
    "none",
]

PriorityLevel = Literal[
    "low",
    "normal",
    "high",
]


@dataclass(frozen=True)
class ObservabilityFlags:
    """
    Optional observability signals.
    Absence implies intentional silence.

    Phase 60:
      • ecb_active indicates Ephemeral Context Buffer participation
        (presence-only signal, no content, no authority).
    """
    trace: bool = False
    log: bool = False
    snapshot: bool = False
    ecb_active: bool = False


@dataclass(frozen=True)
class PacketHeaderExtended:
    """
    OPTIONAL extension surface.
    Consumers MUST safely ignore None or missing fields.
    """
    execution_mode: Optional[ExecutionMode] = None
    routing_hint: Optional[RoutingHint] = None
    safety_state: Optional[SafetyState] = None
    evidence_state: Optional[EvidenceState] = None
    observability_flags: Optional[ObservabilityFlags] = None
    timeout_ms: Optional[int] = None
    priority: Optional[PriorityLevel] = None
    # Unknown fields are intentionally unsupported at the schema level
    # and must be ignored safely by consumers.


# ---------------------------------------------------------------------------
# Composite Header (Minimal + Optional Extended)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PacketHeader:
    """
    Canonical packet header.
    This is the sole control-plane artifact for packet routing and observation.
    """
    minimal: PacketHeaderMinimal
    extended: Optional[PacketHeaderExtended] = None
