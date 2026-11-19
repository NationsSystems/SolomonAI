# ---------------------------------------------------------------------------
# FILE: solomon_core/intent_parser.py
# DIRECTORY: solomon_core/
# ---------------------------------------------------------------------------
# PURPOSE:
#   Evidence-only signal extraction for Investigator layer.
#
# GUARANTEES:
#   • NO behavioral authority
#   • NO routing influence
#   • NO execution influence
#   • Emits observational signals ONLY
#
# CONSTITUTIONAL COMPLIANCE:
#   • Produces evidence, NOT decisions
#   • No intent assignment
#   • No fallback classification
#   • No keyword-driven routing
# ---------------------------------------------------------------------------

import math
from typing import Optional, Dict, Any, List

from solomon_core.logger import get_logger
from solomon_core.solomon_tools.prototype_store import get_intent_prototypes
from solomon_core.solomon_tools.embedding_client import embed_text

logger = get_logger("intent_parser")


# ============================================================================
# Prototype Similarity (OBSERVATION ONLY)
# ============================================================================

def _cosine_similarity(a, b) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _collect_prototype_telemetry(user_text: str) -> Optional[Dict[str, Any]]:
    try:
        query_vec = embed_text(user_text)
    except Exception:
        return None

    prototypes = get_intent_prototypes()
    if not prototypes:
        return None

    scores = []
    for proto in prototypes:
        vec = proto.get("vector")
        if not vec:
            continue
        try:
            score = _cosine_similarity(query_vec, vec)
        except Exception:
            continue
        scores.append({"id": proto.get("id"), "score": score})

    if not scores:
        return None

    scores.sort(key=lambda x: x["score"], reverse=True)

    return {
        "best_id": scores[0]["id"],
        "best_score": scores[0]["score"],
        "scores": scores,
    }


# ============================================================================
# Basic Structural Signal Extraction (NON-AUTHORITATIVE)
# ============================================================================

def _extract_tokens(text: str) -> List[str]:
    return [t for t in text.lower().strip().split() if t]


def _extract_basic_signals(tokens: List[str]) -> Dict[str, Any]:
    return {
        "token_count": len(tokens),
        "has_multiple_tokens": len(tokens) > 1,
        "has_single_token": len(tokens) == 1,
    }


# ============================================================================
# Parser Entrypoint (EVIDENCE ONLY)
# ============================================================================

def parse_task_with_embeddings(user_text: str):
    if not isinstance(user_text, str):
        user_text = str(user_text or "")

    raw_text = user_text
    text_clean = user_text.strip()

    tokens = _extract_tokens(text_clean)
    task_present = bool(text_clean)

    # ----------------------------------------------------------------------
    # Observational Signals (NO DECISIONS)
    # ----------------------------------------------------------------------
    structural_signals = _extract_basic_signals(tokens)

    # Prototype telemetry (purely advisory)
    prototype_telemetry = _collect_prototype_telemetry(text_clean)

    # ----------------------------------------------------------------------
    # Logging (OBSERVATION ONLY)
    # ----------------------------------------------------------------------
    logger.info(
        "Parser signals emitted",
        extra={
            "task_present": task_present,
            "token_count": len(tokens),
        },
    )

    # ----------------------------------------------------------------------
    # CaseFile-compatible evidence output
    # ----------------------------------------------------------------------
    evidence = {
        "raw_text": raw_text,
        "tokens": tokens,
        "task_present": task_present,
        "signals": structural_signals,
    }

    if prototype_telemetry:
        evidence["prototype_telemetry"] = prototype_telemetry

    return {
        "evidence": evidence,
        "confidence": 1.0,
        "reasoning_source": "parser",
    }