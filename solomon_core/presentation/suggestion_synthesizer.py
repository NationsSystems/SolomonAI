# solomon_core/presentation/suggestion_synthesizer.py
# -------------------------------------------------------------
# FILE: solomon_core/presentation/suggestion_synthesizer.py
# -------------------------------------------------------------
# Deterministic Suggestion Synthesizer
# Phase 86 — Stability & Flicker Elimination
# -------------------------------------------------------------

from typing import List, Dict, Any, Optional
import hashlib

# Import the Phase-86 policy engine (single server authority)
from solomon_core.suggestions.suggestion_policy_engine import generate_suggestions


# ------------------------------------------------------------------
# Canonical fallback sets (only used if policy engine returns empty)
# ------------------------------------------------------------------

GENERIC_NO_DOCS = [
    "Upload a document to analyze",
    "Ask a question about your project",
    "Show examples of what Solomon can do",
    "Run a quick document summary",
]

GENERIC_WITH_DOCS = [
    "Summarize the attached documents",
    "List key dates and deadlines",
    "Extract action items and requirements",
    "Identify risks, exclusions, and clarifications",
]


# ------------------------------------------------------------------
# Phase-86 count window (deterministic, context-sensitive)
# ------------------------------------------------------------------

MIN_CHIPS = 3
MAX_CHIPS = 5


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for item in items:
        s = (str(item).strip() if item is not None else "")
        if s and s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _seed_from_context(
    *,
    packet_type: str,
    payload: Dict[str, Any],
    execution_context: Dict[str, Any],
    doc_count: int,
) -> int:
    """
    Deterministic seed source.

    IMPORTANT:
    - No randomness.
    - Uses only stable, already-available values.
    - Does not require UI changes or new request fields.
    """
    user_id = execution_context.get("user_id", "")
    parsed_intent = execution_context.get("parsed_intent", "")
    selected_document = execution_context.get("selected_document", "")
    answer_prefix = str((payload or {}).get("answer", ""))[:96]

    seed_str = f"{packet_type}|{user_id}|{parsed_intent}|{doc_count}|{selected_document}|{answer_prefix}"
    h = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
    return int(h[:12], 16)


def _pick_chip_count(doc_count: int, seed: int) -> int:
    """
    Deterministically pick a chip count within [3..5].
    Slightly prefers more chips when documents exist.
    """
    window = MAX_CHIPS - MIN_CHIPS + 1
    base = MIN_CHIPS + (seed % window)

    if doc_count > 0 and base < MAX_CHIPS:
        base += 1

    if base < MIN_CHIPS:
        return MIN_CHIPS
    if base > MAX_CHIPS:
        return MAX_CHIPS
    return base


def _normalize_existing_suggestions(raw: Any) -> List[str]:
    """
    Accepts multiple historical shapes and normalizes to List[str].
    """
    if raw is None:
        return []

    if isinstance(raw, list):
        out: List[str] = []
        for x in raw:
            if x is None:
                continue
            if isinstance(x, dict):
                lbl = x.get("label")
                if isinstance(lbl, str) and lbl.strip():
                    out.append(lbl.strip())
                continue
            out.append(str(x))
        return _dedupe_preserve_order(out)

    if isinstance(raw, dict):
        inner = raw.get("suggestions")
        if isinstance(inner, list):
            return _normalize_existing_suggestions(inner)

    return []


def _fallback_for_docs(has_docs: bool) -> List[str]:
    base = GENERIC_WITH_DOCS if has_docs else GENERIC_NO_DOCS
    return _dedupe_preserve_order(base)


def _rotate(items: List[str], seed: int) -> List[str]:
    if not items:
        return items
    idx = seed % len(items)
    return items[idx:] + items[:idx]


# ------------------------------------------------------------------
# Core synthesizer
# ------------------------------------------------------------------

def synthesize_suggestions(
    payload: Dict[str, Any],
    execution_context: Dict[str, Any],
    packet_type: str,
) -> List[str]:
    """
    Deterministically produce server-authoritative suggestions (chips).
    """

    facts = execution_context.get("document_facts") or {}
    doc_count = int(facts.get("doc_count") or 0)
    has_docs = bool(facts.get("has_docs"))

    lane = packet_type or "llm"

    # Safely resolve canonical_operation
    explicit_intent = execution_context.get("explicit_intent")
    canonical_operation = None
    if explicit_intent and hasattr(explicit_intent, "operation"):
        canonical_operation = getattr(explicit_intent, "operation")

    signal_bundle = {
        "parsed_intent": execution_context.get("parsed_intent"),
        "canonical_operation": canonical_operation,
        "document_count": doc_count,
        "lane": lane,
    }

    policy_out = generate_suggestions(signal_bundle) or {}
    policy_raw = policy_out.get("suggestions")

    normalized = _normalize_existing_suggestions(policy_raw)

    if not normalized:
        normalized = _fallback_for_docs(has_docs)

    seed = _seed_from_context(
        packet_type=packet_type,
        payload=payload or {},
        execution_context=execution_context or {},
        doc_count=doc_count,
    )

    rotated = _rotate(normalized, seed)
    count = _pick_chip_count(doc_count, seed)

    return rotated[:count]


# ------------------------------------------------------------------
# Public entry
# ------------------------------------------------------------------

def ensure_suggestions(
    packet_type: str,
    payload: Dict[str, Any],
    execution_context: Dict[str, Any],
    logger=None,
) -> Dict[str, Any]:
    """
    Ensures payload["suggestions"] is always a list of strings.
    """

    if not isinstance(payload, dict):
        return payload

    pt = (packet_type or "").strip() or "llm"

    existing = _normalize_existing_suggestions(payload.get("suggestions"))
    if existing:
        payload["suggestions"] = existing
        if logger:
            logger.info(
                "[SUGGESTIONS] existing_kept packet_type=%s count=%s",
                pt,
                len(existing),
            )
        return payload

    synthesized = synthesize_suggestions(payload, execution_context or {}, pt)

    payload["suggestions"] = synthesized if synthesized else []

    if logger:
        logger.info(
            "[SUGGESTIONS] synthesized packet_type=%s doc_count=%s count=%s",
            pt,
            int((execution_context.get("document_facts") or {}).get("doc_count") or 0),
            len(payload["suggestions"]),
        )

    return payload