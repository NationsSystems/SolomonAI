"""
File: solomon_core/web_lane/web_normalization_types.py

Solomon AI — Phase 62
Universal Web Normalization — Type Contracts

This module defines ALL typed data contracts used by the
Universal Web Normalization Pipeline.

AUTHORITATIVE PHASE: 62
STATUS: LOCKED (per Phase 62 Charter)

STRICT RULES:
- Types only (NO logic)
- NO network access
- NO orchestrator imports
- NO DocIntel imports
- NO LLM imports
- Fail-closed semantics encoded via enums / literals
- This file is the single source of truth for Web Lane evidence typing
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Literal


# ===========================================================================
# RAW FETCH (INPUT BOUNDARY — PROVIDED BY PHASE 61)
# ===========================================================================

@dataclass
class RawFetch:
    """
    Represents a completed HTTP fetch performed upstream (Phase 61).

    The Phase 62 Web Normalizer NEVER performs I/O.
    """
    url: str
    status_code: Optional[int]
    headers: Dict[str, str]
    body: Optional[bytes]
    latency_ms: Optional[int]


# ===========================================================================
# DECODED DOCUMENT (INTERNAL — NEVER EXPORTED)
# ===========================================================================

@dataclass
class DecodedDocument:
    """
    Result of content-type–aware decoding.

    Exactly ONE of `text` or `decode_error` MUST be populated.
    """
    url: str
    content_type: Optional[str]
    text: Optional[str]
    decode_error: Optional[str]


# ===========================================================================
# CANDIDATE BLOCK (INTERNAL — SCORING INPUT)
# ===========================================================================

@dataclass
class CandidateBlock:
    """
    A visible text block extracted from normalized HTML.

    Used ONLY for deterministic scoring.
    """
    text: str
    char_count: int
    link_density: float
    numeric_density: float
    punctuation_density: float


# ===========================================================================
# NORMALIZED EVIDENCE BUNDLE (AUTHORITATIVE OUTPUT)
# ===========================================================================

BundleStatus = Literal[
    "OK",
    "INSUFFICIENT",
    "SOURCE_ERROR",
]

SourceOutcome = Literal[
    "OK",
    "FETCH_FAILED",
    "DECODE_ERROR",
    "NORMALIZATION_FAILED",
    "NO_USABLE_BLOCKS",
]


# ---------------------------------------------------------------------------
# SOURCE-LEVEL METRICS (OBSERVABILITY ONLY)
# ---------------------------------------------------------------------------

@dataclass
class SourceMetrics:
    """
    Observability-only metrics for a single web source.

    These metrics MUST NOT influence control flow.
    """
    char_count: int
    block_count: int
    avg_link_density: float
    query_overlap_score: float


# ---------------------------------------------------------------------------
# SOURCE EVIDENCE
# ---------------------------------------------------------------------------

@dataclass
class SourceEvidence:
    """
    Evidence (or explicit failure) derived from a single web source.
    """
    url: str
    fetch_status: Optional[int]
    content_type: Optional[str]
    outcome: SourceOutcome
    extracted_text: List[str]
    extraction_metrics: SourceMetrics
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BUNDLE-LEVEL METRICS
# ---------------------------------------------------------------------------

@dataclass
class BundleMetrics:
    """
    Aggregate observability metrics for the entire bundle.
    """
    total_sources: int
    usable_sources: int
    discarded_sources: int


# ---------------------------------------------------------------------------
# NORMALIZED EVIDENCE BUNDLE (NEB)
# ---------------------------------------------------------------------------

@dataclass
class NormalizedEvidenceBundle:
    """
    Canonical Phase 62 output.

    THIS IS THE ONLY ARTIFACT PERMITTED TO CROSS INTO
    LLM-ADJACENT CONTEXT.
    """
    query: str
    status: BundleStatus
    sources: List[SourceEvidence]
    global_warnings: List[str]
    metrics: BundleMetrics
