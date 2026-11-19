# ------------------------------------------------------------------
# FILE: solomon_core/fis/fis_types.py
# DIRECTORY: solomon_core/fis/
# ------------------------------------------------------------------
# Fingerprint Identity System (FIS) Type Definitions
#
# Purpose:
#   Defines the canonical data contracts used by the isolated
#   Fingerprint Identity System subsystem.
#
# Design Rules:
#   - Structure only (no behavior)
#   - Deterministic, transport-safe contracts
#   - No hidden defaults beyond safe primitive initialization
#   - No dependency on Investigator, Judge, LLM, or UI layers
# ------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Tuple


def _utc_now_iso() -> str:
    """
    Generate a UTC ISO-8601 timestamp with timezone information.

    This is used only for safe record initialization inside FIS-local
    structures and does not introduce external side effects.
    """
    return datetime.now(timezone.utc).isoformat()


class FISTokenStatus(str, Enum):
    """
    Result of FIS admissibility handling for a token.
    """

    VALID = "VALID"
    REJECTED = "REJECTED"


class FISIdentifierStatus(str, Enum):
    """
    Registry state for an admitted identifier.
    """

    BOUND = "BOUND"
    UNBOUND = "UNBOUND"


@dataclass(frozen=True)
class FISToken:
    """
    Raw and normalized token representation produced by FIS intake.
    """

    raw: str
    normalized: str


@dataclass(frozen=True)
class FISValidationResult:
    """
    Admissibility decision for a single token.
    """

    token: FISToken
    status: FISTokenStatus
    reason: Optional[str] = None


@dataclass(frozen=True)
class FISFingerprintResult:
    """
    Fingerprint generated for a validated token.
    """

    token: FISToken
    fingerprint: str


@dataclass(frozen=True)
class FISRegistryRecord:
    """
    Persistent or in-memory identity record stored by the FIS registry.
    """

    fingerprint: str
    canonical_value: str
    status: FISIdentifierStatus
    seen_count: int
    first_seen: str
    last_seen: str


@dataclass(frozen=True)
class FISIdentifierResult:
    """
    Final token-level output returned by the FIS pipeline.
    """

    token: FISToken
    status: FISTokenStatus
    fingerprint: Optional[str] = None
    identifier_status: Optional[FISIdentifierStatus] = None
    record: Optional[FISRegistryRecord] = None
    reason: Optional[str] = None


@dataclass(frozen=True)
class FISSummary:
    """
    Aggregate summary for a full FIS pipeline run.
    """

    total_tokens: int
    valid_tokens: int
    rejected_tokens: int
    bound_identifiers: int
    unbound_identifiers: int


@dataclass(frozen=True)
class FISPipelineResult:
    """
    Full output contract for the isolated FIS pipeline.
    """

    raw_input: str
    tokens: Tuple[FISIdentifierResult, ...]
    summary: FISSummary


@dataclass
class FISRegistryMutation:
    """
    Internal mutable helper contract describing an upsert action before
    it is committed into an immutable FISRegistryRecord.

    This is intentionally scoped to FIS internals and can be removed later
    if persistence requirements evolve.
    """

    fingerprint: str
    canonical_value: str
    status: FISIdentifierStatus
    seen_count: int = 1
    first_seen: str = field(default_factory=_utc_now_iso)
    last_seen: str = field(default_factory=_utc_now_iso)