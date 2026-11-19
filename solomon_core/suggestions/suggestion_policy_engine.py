# ------------------------------------------------------------------
# FILE: solomon_core/suggestions/suggestion_policy_engine.py
# ------------------------------------------------------------------
# Solomon Suggestion Policy Engine
#
# Phase 86 — Deterministic chip policy layer
#
# Design constraints:
#   • Pure function
#   • Deterministic
#   • No side effects
#   • No database access
#   • No LLM calls
#   • <5 ms target
#   • Transport safe
#
# Future seam:
#   Phase 87 — Chip Intelligence Layer (ranking/personalization)
# ------------------------------------------------------------------

from typing import Dict, List, Optional


# ============================================================================
# Types
# ============================================================================

Suggestion = Dict[str, object]


# ============================================================================
# Priority constants (Phase 86 baseline)
# ============================================================================

PRIORITY_PRIMARY = 0.95
PRIORITY_HIGH = 0.85
PRIORITY_MEDIUM = 0.65
PRIORITY_LOW = 0.45
PRIORITY_FALLBACK = 0.25

# Minimum chips to emit (UX floor) — applied only when we decide to emit chips
MIN_SUGGESTIONS = 4


# ============================================================================
# Phase 87A — Deterministic priority shaping constants (small magnitude)
# ============================================================================

BOOST_STRONG = 0.08
BOOST_MEDIUM = 0.05
BOOST_LIGHT = 0.03


# ============================================================================
# Suggestion factories (pure, deterministic)
# ============================================================================

def _s_upload() -> Suggestion:
    return {
        "id": "upload_document",
        "label": "Upload a document",
        "action": "upload",
        "priority": PRIORITY_PRIMARY,
    }


def _s_compare() -> Suggestion:
    return {
        "id": "compare_documents",
        "label": "Compare documents",
        "action": "compare",
        "priority": PRIORITY_HIGH,
    }


def _s_summarize() -> Suggestion:
    return {
        "id": "summarize_document",
        "label": "Summarize document",
        "action": "summarize",
        "priority": PRIORITY_HIGH,
    }


def _s_extract() -> Suggestion:
    return {
        "id": "extract_information",
        "label": "Extract key information",
        "action": "extract",
        "priority": PRIORITY_MEDIUM,
    }


def _s_analyze() -> Suggestion:
    return {
        "id": "analyze_document",
        "label": "Analyze document",
        "action": "analyze",
        "priority": PRIORITY_MEDIUM,
    }


def _s_ask() -> Suggestion:
    return {
        "id": "ask_question",
        "label": "Ask a question",
        "action": "ask",
        "priority": PRIORITY_LOW,
    }


def _s_web() -> Suggestion:
    return {
        "id": "search_web",
        "label": "Search the web",
        "action": "open_web",
        "priority": PRIORITY_HIGH,
    }


def _fallback_pool() -> List[Suggestion]:
    """
    Deterministic global fallback pool.
    Order here is intentional and stable.
    """
    return [
        _s_upload(),
        _s_compare(),
        _s_summarize(),
        _s_extract(),
        _s_analyze(),
        _s_ask(),
        _s_web(),
    ]


# ============================================================================
# Emission gate (prevents repeated/noisy chips on general Q&A)
# ============================================================================

def _is_actionable_intent(value: Optional[str]) -> bool:
    """
    Recognizes intents/operations that imply a next-step action.
    This function is intentionally conservative.
    """
    if not value:
        return False

    v = str(value).strip().lower()

    actionable = {
        "upload",
        "upload_document",
        "compare",
        "compare_documents",
        "summarize",
        "summarize_document",
        "extract",
        "extract_information",
        "analyze",
        "analyze_document",
    }

    return v in actionable


def _should_emit_chips(
    lane: Optional[str],
    document_count: int,
    parsed_intent: Optional[str],
    canonical_operation: Optional[str],
) -> bool:
    """
    Determines whether chips should be emitted at all.
    """

    if lane == "web":
        return True

    if lane == "clarification":
        return True

    if document_count >= 1:
        return True

    if _is_actionable_intent(parsed_intent):
        return True

    if _is_actionable_intent(canonical_operation):
        return True

    return False


# ============================================================================
# NEW: Intent-sensitive deterministic diversification (Phase 86 safe)
# ============================================================================

def _intent_seed(parsed_intent: Optional[str]) -> str:
    """
    Provides a deterministic coarse intent bucket.
    This adds variety WITHOUT randomness or memory.
    """
    if not parsed_intent:
        return "generic"

    v = parsed_intent.lower()

    if "factual" in v or "question" in v:
        return "informational"

    if "summarize" in v:
        return "summarization"

    if "extract" in v:
        return "extraction"

    return "generic"


# ============================================================================
# Phase 87A — Deterministic priority shaping (PURE)
# ============================================================================

def _apply_priority_shaping(
    suggestions: List[Suggestion],
    signal_bundle: Dict[str, object],
) -> List[Suggestion]:
    """
    Deterministically adjusts suggestion priority weights using only existing signals.

    Guardrails:
      • no randomness
      • no new chips
      • no schema changes
      • no side effects (copy-safe)
      • small magnitude only
    """

    # Copy-safe: new list + shallow-copy dicts (factories already return new dicts,
    # but we avoid coupling to caller expectations).
    shaped: List[Suggestion] = [dict(s) for s in suggestions]

    by_id: Dict[str, Suggestion] = {}
    for s in shaped:
        sid = s.get("id")
        if isinstance(sid, str):
            by_id[sid] = s

    def _boost(sid: str, amount: float) -> None:
        s = by_id.get(sid)
        if not s:
            return
        try:
            s["priority"] = float(s.get("priority", 0.0)) + float(amount)
        except Exception:
            # Transport safety: if priority is malformed, do not alter it.
            return

    lane = signal_bundle.get("lane")
    parsed_intent = signal_bundle.get("parsed_intent")
    canonical_operation = signal_bundle.get("canonical_operation")
    document_count = int(signal_bundle.get("document_count") or 0)

    lane_s = str(lane).strip().lower() if lane is not None else ""
    op_s = str(canonical_operation).strip().lower() if canonical_operation is not None else ""
    intent_s = str(parsed_intent).strip().lower() if parsed_intent is not None else ""

    # --- Rule Group 1: Lane shaping (small, deterministic) ---
    if lane_s == "web":
        _boost("search_web", BOOST_MEDIUM)
    elif lane_s == "clarification":
        _boost("ask_question", BOOST_MEDIUM)
    else:
        # Treat all non-web/non-clarification lanes defensively (e.g., commonly "llm")
        _boost("upload_document", BOOST_LIGHT)

    # --- Rule Group 2: Document count shaping ---
    if document_count <= 0:
        _boost("upload_document", BOOST_MEDIUM)
    elif document_count == 1:
        _boost("summarize_document", BOOST_LIGHT)
    else:  # >= 2
        _boost("compare_documents", BOOST_MEDIUM)

    # --- Rule Group 3: Operation shaping (strongest) ---
    if op_s == "summarize":
        _boost("summarize_document", BOOST_STRONG)
    elif op_s == "extract":
        _boost("extract_information", BOOST_STRONG)
    elif op_s == "analyze":
        _boost("analyze_document", BOOST_STRONG)
    elif op_s == "compare":
        _boost("compare_documents", BOOST_STRONG)
    else:
        # Parsed intent shaping (lightweight, only when canonical_operation is not decisive)
        if "summarize" in intent_s:
            _boost("summarize_document", BOOST_MEDIUM)
        elif "extract" in intent_s:
            _boost("extract_information", BOOST_MEDIUM)
        elif "analy" in intent_s:  # matches "analyze"/"analysis"
            _boost("analyze_document", BOOST_MEDIUM)
        elif "compare" in intent_s:
            _boost("compare_documents", BOOST_MEDIUM)

    return shaped


# ============================================================================
# Core policy engine (PURE)
# ============================================================================

def generate_suggestions(signal_bundle: Dict[str, object]) -> Dict[str, List[Suggestion]]:
    """
    Deterministic Suggestion Policy Engine.
    """

    parsed_intent: Optional[str] = signal_bundle.get("parsed_intent")
    canonical_operation: Optional[str] = signal_bundle.get("canonical_operation")
    document_count: int = int(signal_bundle.get("document_count") or 0)
    lane: Optional[str] = signal_bundle.get("lane")

    if not _should_emit_chips(lane, document_count, parsed_intent, canonical_operation):
        return {"suggestions": []}

    suggestions: List[Suggestion] = []

    # === WEB lane ======================================================
    if lane == "web":
        suggestions.append(_s_web())
        suggestions.append(_s_ask())
        suggestions = _apply_priority_shaping(suggestions, signal_bundle)
        return _finalize(suggestions, enforce_floor=True)

    # === CLARIFICATION lane ============================================
    if lane == "clarification":
        suggestions.append(_s_ask())
        if document_count == 0:
            suggestions.append(_s_upload())
        suggestions = _apply_priority_shaping(suggestions, signal_bundle)
        return _finalize(suggestions, enforce_floor=True)

    # === No documents ==================================================
    if document_count == 0:
        seed = _intent_seed(parsed_intent)

        # Deterministic but varied sets to avoid repetitive feel
        if seed == "informational":
            suggestions.append(_s_upload())
            suggestions.append(_s_summarize())
            suggestions.append(_s_ask())
        elif seed == "summarization":
            suggestions.append(_s_summarize())
            suggestions.append(_s_upload())
            suggestions.append(_s_ask())
        elif seed == "extraction":
            suggestions.append(_s_extract())
            suggestions.append(_s_upload())
            suggestions.append(_s_ask())
        else:
            suggestions.append(_s_upload())
            suggestions.append(_s_ask())

        suggestions = _apply_priority_shaping(suggestions, signal_bundle)
        return _finalize(suggestions, enforce_floor=True)

    # === Multi-document ===============================================
    if document_count >= 2:
        suggestions.append(_s_compare())
        suggestions.append(_s_summarize())
        suggestions.append(_s_extract())
        suggestions = _apply_priority_shaping(suggestions, signal_bundle)
        return _finalize(suggestions, enforce_floor=True)

    # === Single document ==============================================
    if document_count == 1:
        if canonical_operation == "summarize":
            suggestions.append(_s_summarize())
        elif canonical_operation == "extract":
            suggestions.append(_s_extract())
        elif canonical_operation == "analyze":
            suggestions.append(_s_analyze())
        else:
            suggestions.append(_s_summarize())
            suggestions.append(_s_extract())

        suggestions.append(_s_ask())
        suggestions = _apply_priority_shaping(suggestions, signal_bundle)
        return _finalize(suggestions, enforce_floor=True)

    # === Fallback ======================================================
    suggestions.append(_s_ask())
    suggestions = _apply_priority_shaping(suggestions, signal_bundle)
    return _finalize(suggestions, enforce_floor=True)


# ============================================================================
# Finalization (deterministic ordering + optional floor enforcement)
# ============================================================================

def _finalize(suggestions: List[Suggestion], enforce_floor: bool) -> Dict[str, List[Suggestion]]:
    """
    Ensures deterministic ordering, deduplication,
    and optionally enforces minimum chip floor.
    """

    dedup: Dict[str, Suggestion] = {}

    for s in suggestions:
        sid = s["id"]
        if sid not in dedup or s["priority"] > dedup[sid]["priority"]:
            dedup[sid] = s

    if enforce_floor and len(dedup) < MIN_SUGGESTIONS:
        for candidate in _fallback_pool():
            if candidate["id"] not in dedup:
                dedup[candidate["id"]] = candidate
            if len(dedup) >= MIN_SUGGESTIONS:
                break

    ordered = sorted(
        dedup.values(),
        key=lambda x: (-float(x["priority"]), x["id"]),
    )

    return {"suggestions": ordered}