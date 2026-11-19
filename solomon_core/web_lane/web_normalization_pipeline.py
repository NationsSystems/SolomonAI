"""
File: solomon_core/web_lane/web_normalization_pipeline.py

Solomon AI — Phase 62
Universal Web Normalization Pipeline

AUTHORITATIVE PHASE: 62
STATUS: IMPLEMENTATION (per locked Phase 62 Charter)
"""

import math
import re
from typing import List

from solomon_core.web_lane.web_normalization_types import (
    RawFetch,
    DecodedDocument,
    CandidateBlock,
    NormalizedEvidenceBundle,
    SourceEvidence,
    SourceMetrics,
    BundleMetrics,
)

# ===========================================================================
# CONSTANTS (LOCKED FOR PHASE 62)
# ===========================================================================

MIN_CHARS = 80
TOP_K_BLOCKS = 3

QUERY_WEIGHT = 3.0
LINK_WEIGHT = 2.5
NUMERIC_WEIGHT = 1.5
PUNCT_WEIGHT = 1.0

NUMERIC_DENSITY_THRESHOLD = 0.25

STOPWORDS = {
    "the", "and", "or", "of", "to", "in", "on", "for", "with", "by", "at",
    "from", "as", "is", "are", "was", "were", "be", "this", "that",
}

RELATIVE_TIME_TOKENS = {
    "today", "tonight", "now", "currently", "this morning",
    "this afternoon", "this evening",
}

DATE_PATTERNS = [
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b",
]

TIME_PATTERNS = [
    r"\b\d{1,2}:\d{2}\b",
    r"\b\d{1,2}\s?(?:am|pm)\b",
]

TEMPORAL_QUERY_TOKENS = {
    "today", "now", "current", "currently",
    "tonight", "latest", "right now",
}

NUMERIC_FACT_PATTERNS = [
    r"\b\d+\.\d+\b",
    r"\b\d+\s?%\b",
    r"\b\d+\s?°\s?[cCfF]\b",
    r"\b\d+°[cCfF]\b",
    r"\b\d+\s?(?:km/h|kph|mph)\b",
]

URL_TOKEN_RE = re.compile(r"(https?://|www\.)", re.IGNORECASE)
DOMAINISH_RE = re.compile(r"\b[a-z0-9-]+\.[a-z]{2,}\b", re.IGNORECASE)

MAX_URLISH_RATIO = 0.18
MIN_ALPHA_RATIO = 0.45
MAX_DOMAIN_TOKENS = 2


# ===========================================================================
# PUBLIC ENTRY POINT
# ===========================================================================

def normalize_web_sources(query: str, raw_fetches: List[RawFetch]) -> NormalizedEvidenceBundle:
    sources: List[SourceEvidence] = []
    temporal_query = _is_temporal_query(query)

    for raw in raw_fetches:
        sources.append(_process_single_source(raw, query, temporal_query=temporal_query))

    status = _resolve_bundle_status(sources)

    return NormalizedEvidenceBundle(
        query=query,
        status=status,
        sources=sources,
        global_warnings=[],
        metrics=BundleMetrics(
            total_sources=len(sources),
            usable_sources=sum(1 for s in sources if s.outcome == "OK"),
            discarded_sources=sum(1 for s in sources if s.outcome != "OK"),
        ),
    )


# ===========================================================================
# SOURCE PROCESSING
# ===========================================================================

def _process_single_source(raw: RawFetch, query: str, *, temporal_query: bool) -> SourceEvidence:
    if raw.status_code is None or raw.body is None:
        return _emit_failure(raw, "FETCH_FAILED")

    decoded = _decode_raw_fetch(raw)
    if decoded.decode_error:
        return _emit_failure(raw, "DECODE_ERROR")

    blocks = _extract_plain_text_blocks(decoded.text or "")
    if not blocks:
        return _emit_failure(raw, "NORMALIZATION_FAILED")

    scored_blocks = _score_blocks(blocks, query, temporal_query=temporal_query)
    if not scored_blocks:
        return _emit_failure(raw, "NO_USABLE_BLOCKS")

    extracted_text = [b.text for b in scored_blocks]

    if temporal_query:
        if not _contains_explicit_time(extracted_text):
            return _emit_failure(raw, "NO_USABLE_BLOCKS")
        if not _contains_measurable_fact(extracted_text):
            return _emit_failure(raw, "NO_USABLE_BLOCKS")

    return SourceEvidence(
        url=raw.url,
        fetch_status=raw.status_code,
        content_type=decoded.content_type,
        outcome="OK",
        extracted_text=extracted_text,
        extraction_metrics=SourceMetrics(
            char_count=sum(b.char_count for b in scored_blocks),
            block_count=len(scored_blocks),
            avg_link_density=sum(b.link_density for b in scored_blocks) / len(scored_blocks),
            query_overlap_score=_aggregate_query_overlap(scored_blocks, query),
        ),
        warnings=[],
    )


# ===========================================================================
# SCORING (FIX APPLIED HERE)
# ===========================================================================

def _score_blocks(blocks: List[CandidateBlock], query: str, *, temporal_query: bool):
    scored = []
    query_tokens = _tokenize_query(query)

    for block in blocks:
        has_time = _block_has_explicit_time(block.text)
        has_numeric = _looks_like_numeric_fact(block.text)

        # ✅ Phase-62 sensor exception
        is_sensor_fact = temporal_query and has_time and has_numeric

        if not is_sensor_fact:
            if block.char_count < MIN_CHARS:
                continue
            if _is_link_directory_block(block.text):
                continue

        score = math.log(max(block.char_count, 10))
        score += _query_overlap(block.text, query_tokens) * QUERY_WEIGHT
        score -= block.link_density * LINK_WEIGHT
        score -= block.punctuation_density * PUNCT_WEIGHT

        if score > 0:
            scored.append((score, block))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in scored[:TOP_K_BLOCKS]]


# ===========================================================================
# HELPERS (unchanged)
# ===========================================================================

def _decode_raw_fetch(raw: RawFetch) -> DecodedDocument:
    try:
        text = raw.body.decode("utf-8", errors="ignore")
        return DecodedDocument(raw.url, raw.headers.get("Content-Type"), text, None)
    except Exception as e:
        return DecodedDocument(raw.url, None, None, str(e))


def _extract_plain_text_blocks(text: str):
    blocks = []
    for chunk in text.split(". "):
        chunk = chunk.strip()
        if not chunk:
            continue
        blocks.append(CandidateBlock(
            text=chunk,
            char_count=len(chunk),
            link_density=chunk.count("http") / max(len(chunk), 1),
            numeric_density=sum(c.isdigit() for c in chunk) / max(len(chunk), 1),
            punctuation_density=sum(c in ",;:/()" for c in chunk) / max(len(chunk), 1),
        ))
    return blocks


def _emit_failure(raw, outcome):
    return SourceEvidence(
        url=raw.url,
        fetch_status=raw.status_code,
        content_type=None,
        outcome=outcome,
        extracted_text=[],
        extraction_metrics=SourceMetrics(0, 0, 0.0, 0.0),
        warnings=[],
    )


def _resolve_bundle_status(sources):
    if any(s.outcome == "OK" for s in sources):
        return "OK"
    return "INSUFFICIENT"


def _tokenize_query(query):
    return [t for t in re.findall(r"\w+", query.lower()) if t not in STOPWORDS]


def _query_overlap(text, tokens):
    return sum(1 for t in tokens if t in text.lower()) / max(len(tokens), 1)


def _aggregate_query_overlap(blocks, query):
    tokens = _tokenize_query(query)
    return sum(_query_overlap(b.text, tokens) for b in blocks) / max(len(blocks), 1)


def _is_temporal_query(query):
    return any(t in query.lower() for t in TEMPORAL_QUERY_TOKENS)


def _block_has_explicit_time(text):
    return any(re.search(p, text.lower()) for p in DATE_PATTERNS + TIME_PATTERNS)


def _contains_explicit_time(texts):
    return any(_block_has_explicit_time(t) for t in texts)


def _looks_like_numeric_fact(text):
    return any(re.search(p, text) for p in NUMERIC_FACT_PATTERNS)


def _contains_measurable_fact(texts):
    return any(_looks_like_numeric_fact(t) for t in texts)


def _is_link_directory_block(text):
    alpha_ratio = sum(c.isalpha() for c in text) / max(len(text), 1)
    urlish_ratio = sum(c in "/:._?&=%#-" for c in text) / max(len(text), 1)
    return alpha_ratio < MIN_ALPHA_RATIO or urlish_ratio > MAX_URLISH_RATIO
