"""
Lexicon Subsystem — Deterministic Presentation Renderer

Location: solomon_core/presentation/lexicon/lexicon_deterministic_renderer.py
Status: Phase 43 — UX-Optimized Deterministic Presentation
Authority: NON-AUTHORITATIVE (SASE-Governed)

This module provides a deterministic, presentation-only renderer that
**preserves the LLM's natural language output by default**.

Phase 43 Change:
- Lexicon no longer injects framing or disclosures by default
- LLM output is treated as user-facing language
- Determinism is preserved through ordering and opt-in rules only

NO inference, recommendation, or authority is introduced.
"""

from typing import List

from .lexicon_interface_contracts import (
    LexiconInterface,
    LexiconInputPayload,
    LexiconOutputPayload,
)
from .lexicon_presentation_policy import (
    BASE_LEXICON_PACK,
    DOCINTEL_LEXICON_PACK,
    REVIEWER_LEXICON_PACK,
)
from .lexicon_phrase_bank import (
    EVIDENCE_STATE_HEADERS,
    SCOPE_LIMITATION_PHRASE,
    UNCERTAINTY_DISCLOSURE_PHRASE,
    REVIEWER_MODE_FRAMING_PHRASE,
)


# ---------------------------------------------------------------------------
# Deterministic Helpers (PURE FUNCTIONS ONLY)
# ---------------------------------------------------------------------------

def _normalize_whitespace(text: str) -> str:
    """Normalize spacing without altering meaning."""
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def _is_atomic_output(text: str) -> bool:
    """
    Atomic output = trivial factual answer.
    Used ONLY to suppress visual noise.
    """
    if "\n" in text:
        return False
    words = text.split()
    return len(words) <= 3


def _apply_evidence_header(text: str, evidence_state: str) -> str:
    header = EVIDENCE_STATE_HEADERS.get(evidence_state)
    return f"{header}\n\n{text}" if header else text


def _apply_scope_notice(text: str) -> str:
    return f"{text}\n\n{SCOPE_LIMITATION_PHRASE}"


def _apply_uncertainty_disclosure(text: str) -> str:
    return f"{text}\n\n{UNCERTAINTY_DISCLOSURE_PHRASE}"


def _apply_reviewer_framing(text: str) -> str:
    return f"{REVIEWER_MODE_FRAMING_PHRASE}\n\n{text}"


def _structure_sections(text: str) -> str:
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return "\n\n".join(paragraphs)


# ---------------------------------------------------------------------------
# Rule Application (MINIMAL & OPT-IN)
# ---------------------------------------------------------------------------

def _apply_rules(
    text: str,
    rule_ids: List[str],
    payload: LexiconInputPayload,
    *,
    suppress_framing: bool,
) -> str:
    """
    Phase 43:
    Rules are applied ONLY when explicitly requested.
    Default behavior is pass-through.
    """
    result = text

    for rule_id in rule_ids:
        if suppress_framing:
            continue

        if rule_id == "evidence_state_header":
            result = _apply_evidence_header(result, payload["evidence_state"])

        elif rule_id == "scope_boundary_notice":
            result = _apply_scope_notice(result)

        elif rule_id == "explicit_uncertainty_callout":
            result = _apply_uncertainty_disclosure(result)

        elif rule_id == "structural_section_normalization":
            result = _structure_sections(result)

        else:
            # Unknown rules are ignored deterministically
            result = result

    return result


# ---------------------------------------------------------------------------
# Concrete Lexicon Implementation
# ---------------------------------------------------------------------------

class DeterministicLexiconRenderer(LexiconInterface):
    """
    Phase 43 Deterministic Renderer

    PRINCIPLE:
    - LLM language is primary
    - Lexicon only formats, never rewrites
    - Framing is opt-in, not automatic
    """

    def apply(self, payload: LexiconInputPayload) -> LexiconOutputPayload:
        original_text = payload["user_output"]
        text = _normalize_whitespace(original_text)

        atomic = _is_atomic_output(text)

        task_type = payload.get("task_type", "general")
        reviewer_mode = payload.get("reviewer_mode", False)

        # -------------------------------
        # Policy selection (unchanged)
        # -------------------------------
        if reviewer_mode:
            pack = REVIEWER_LEXICON_PACK
            text = _apply_reviewer_framing(text)
            suppress_framing = False

        elif task_type == "docintel":
            pack = DOCINTEL_LEXICON_PACK
            suppress_framing = False

        else:
            pack = BASE_LEXICON_PACK
            suppress_framing = atomic

        # -------------------------------
        # Apply rules (light touch)
        # -------------------------------
        transformed = _apply_rules(
            text,
            pack["rule_ids"],
            payload,
            suppress_framing=suppress_framing,
        )

        return {
            "user_output": transformed,
            "presentation": {
                "lexicon_pack": pack["pack_id"],
                "applied_rules": list(pack["rule_ids"]),
                "mode": "pass_through_first",
            },
        }


# ---------------------------------------------------------------------------
# Canonical Statement
# ---------------------------------------------------------------------------

# Phase 43 Canonical Guarantee:
# - The LLM is no longer linguistically constrained
# - Lexicon formatting is non-invasive
# - Authority remains unchanged
# - UX is restored without sacrificing compliance
