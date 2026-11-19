# solomon_core/packets/packet_envelope.py
# ---------------------------------------------------------------------------
# Phase 44 — Canonical PacketEnvelope (STRUCTURE ONLY)
# ---------------------------------------------------------------------------
# PURPOSE:
#   Define the immutable container that binds a PacketHeader to an opaque
#   payload. No inspection, no mutation, no routing logic.
#
# GUARANTEES:
#   • Header governs control plane
#   • Payload remains opaque
#   • Envelope is pass-through safe
#   • No authority, no decisions
#
# PHASE 47.1 ADDITION:
#   • Diagnostic Isolation Invariant
#   • Diagnostic material is never permitted in packet payloads
# ---------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from solomon_core.logger import get_logger
from solomon_core.packets.packet_header import PacketHeader

logger = get_logger("packet_envelope")

PayloadT = TypeVar("PayloadT")

# ------------------------------------------------------------
# Phase 47.1 — Diagnostic Isolation (Packet Boundary)
# ------------------------------------------------------------
DIAGNOSTIC_MARKERS = {
    "__diagnostic__",
    "__diagnostics__",
    "diagnostic",
    "diagnostics",
    "operator_only",
    "admin_only",
}

def _contains_diagnostic_material(obj: Any) -> bool:
    """
    Deterministically detect diagnostic-tagged material.
    This guard is structural and non-authoritative.
    """
    try:
        if obj is None:
            return False

        # Explicit attribute flag
        if hasattr(obj, "is_diagnostic") and bool(getattr(obj, "is_diagnostic")):
            return True

        # Mapping scan
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(k, str) and k.lower() in DIAGNOSTIC_MARKERS:
                    return True
                if _contains_diagnostic_material(v):
                    return True
            return False

        # Sequence scan
        if isinstance(obj, (list, tuple, set)):
            return any(_contains_diagnostic_material(x) for x in obj)

        # String scan (conservative)
        if isinstance(obj, str):
            lowered = obj.lower()
            return any(marker in lowered for marker in DIAGNOSTIC_MARKERS)

        return False

    except Exception:
        # Fail-safe: treat inspection failure as diagnostic presence
        return True


@dataclass(frozen=True)
class PacketEnvelope(Generic[PayloadT]):
    header: PacketHeader
    payload: PayloadT

    def __post_init__(self) -> None:
        # --------------------------------------------------------
        # Phase 47.1 Guard: Diagnostics Never Enter Packets
        # --------------------------------------------------------
        if _contains_diagnostic_material(self.payload):
            logger.error(
                "PacketEnvelope construction blocked: diagnostic material in payload",
                extra={"isolation": "diagnostic"},
            )
            raise ValueError(
                "Diagnostic material is not permitted in packet payloads"
            )
