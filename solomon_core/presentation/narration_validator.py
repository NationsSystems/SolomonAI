# ---------------------------------------------------------------------------
# FILE: solomon_core/presentation/narration_validator.py
# ---------------------------------------------------------------------------
# Narration Validator
#
# Purpose:
#   Deterministically validate narrator (LLM) output against the bounded
#   narration contract (narration_packet).
#
# Rules:
#   - Validator is a judge, not an editor.
#   - No mutation of narrator text.
#   - No retries, no prompt tuning, no post-editing.
#   - Deterministic checks only (explicit patterns and required surfacing).
# ---------------------------------------------------------------------------

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List


# ============================================================================
# Result Types
# ============================================================================

@dataclass(frozen=True)
class NarrationValidationResult:
    verdict: str  # "PASS" | "FAIL"
    violations: List[str]

    def is_pass(self) -> bool:
        return self.verdict == "PASS"


# ============================================================================
# Deterministic Violation Checks
# ============================================================================

_RECOMMENDATION_PATTERNS = [
    r"\bwe recommend\b",
    r"\bi recommend\b",
    r"\byou should\b",
    r"\bwe should\b",
    r"\byou need to\b",
    r"\bwe need to\b",
    r"\bour recommendation\b",
    r"\bnext steps\b",
    r"\baction items\b",
    r"\bplan of action\b",
]

_SPECULATION_PATTERNS = [
    r"\bmaybe\b",
    r"\bperhaps\b",
    r"\bprobably\b",
    r"\blikely\b",
    r"\bpossibly\b",
    r"\bit seems\b",
    r"\bit appears\b",
    r"\bI think\b",
    r"\bI believe\b",
    r"\bI suspect\b",
]

_PREFERENCE_PATTERNS = [
    r"\bbetter than\b",
    r"\bworse than\b",
    r"\bbest\b",
    r"\bworst\b",
    r"\bprefer\b",
    r"\bpreference\b",
    r"\brank\b",
    r"\branking\b",
    r"\baward\b",
    r"\bselect\b",
    r"\bchoose\b",
]

_READINESS_POSITIVE_PATTERNS = [
    r"\breadiness is established\b",
    r"\bready to proceed\b",
    r"\bcleared to proceed\b",
    r"\bno blockers\b",
    r"\ball clear\b",
]

_REQUIRED_READINESS_PHRASE = "Readiness is not established."
_REQUIRED_HIGH_EXPOSURE_PHRASE = "High exposure"


# ============================================================================
# Helpers
# ============================================================================

def _norm(text: str) -> str:
    return (text or "").strip()


def _lower(text: str) -> str:
    return _norm(text).lower()


def _matches_any(text: str, patterns: List[str]) -> bool:
    if not text:
        return False
    for p in patterns:
        if re.search(p, text, flags=re.IGNORECASE):
            return True
    return False


def _critical_signal_types(packet: Dict[str, Any]) -> List[str]:
    findings = packet.get("findings") or []
    crits: List[str] = []
    for f in findings:
        if isinstance(f, dict) and f.get("severity") == "CRITICAL":
            st = f.get("signal_type")
            if isinstance(st, str) and st.strip():
                crits.append(st.strip())
    return crits


def _get_suggestions(packet: Dict[str, Any]) -> List[str]:
    """
    Server is authoritative for 'chips/suggestions'. We support a few key names
    to avoid brittle coupling while still enforcing the contract.
    """
    raw = (
        packet.get("suggestions")
        or packet.get("chips")
        or packet.get("chip_suggestions")
        or packet.get("chip_bank_suggestions")
        or []
    )
    if not isinstance(raw, list):
        return []
    out: List[str] = []
    for s in raw:
        if isinstance(s, str) and s.strip():
            out.append(s.strip())
    return out


def _get_bridge(packet: Dict[str, Any]) -> str:
    """
    Bridge is mandatory when suggestions/chips exist.
    """
    raw = (
        packet.get("bridge")
        or packet.get("bridge_text")
        or packet.get("suggestions_bridge")
        or packet.get("chips_bridge")
        or ""
    )
    return _norm(raw) if isinstance(raw, str) else ""


# ============================================================================
# Public API
# ============================================================================

def validate_narration(
    packet: Dict[str, Any],
    narrator_text: str,
) -> NarrationValidationResult:

    violations: List[str] = []

    text = _norm(narrator_text)
    if not text:
        return NarrationValidationResult(verdict="FAIL", violations=["EMPTY_NARRATION"])

    constraints = (packet.get("constraints") or {}) if isinstance(packet, dict) else {}
    no_recommendation = bool(constraints.get("no_recommendation", False))
    no_inference = bool(constraints.get("no_inference", False))
    must_preserve = bool(constraints.get("must_preserve_meaning", False))
    critical_must_surface = bool(constraints.get("critical_must_surface", False))

    implications = packet.get("implications") or []
    implications = [i for i in implications if isinstance(i, str)]

    # ------------------------------------------------------------------
    # Recommendation ban
    # ------------------------------------------------------------------
    if no_recommendation and _matches_any(text, _RECOMMENDATION_PATTERNS):
        violations.append("RECOMMENDATION_LANGUAGE_DETECTED")

    # ------------------------------------------------------------------
    # Speculation ban
    # ------------------------------------------------------------------
    if no_inference and _matches_any(text, _SPECULATION_PATTERNS):
        violations.append("SPECULATION_LANGUAGE_DETECTED")

    # ------------------------------------------------------------------
    # Preference / ranking ban
    # ------------------------------------------------------------------
    if _matches_any(text, _PREFERENCE_PATTERNS):
        violations.append("PREFERENCE_OR_RANKING_LANGUAGE_DETECTED")

    # ------------------------------------------------------------------
    # Readiness
    # ------------------------------------------------------------------
    if "READINESS_NOT_ESTABLISHED" in implications:
        if _REQUIRED_READINESS_PHRASE.lower() not in _lower(text):
            violations.append("READINESS_REQUIRED_NOT_SURFACED")

        if must_preserve and _matches_any(text, _READINESS_POSITIVE_PATTERNS):
            violations.append("READINESS_CONTRADICTION_DETECTED")

    # ------------------------------------------------------------------
    # High exposure
    # ------------------------------------------------------------------
    if "HIGH_EXPOSURE" in implications:
        if _REQUIRED_HIGH_EXPOSURE_PHRASE.lower() not in _lower(text):
            violations.append("HIGH_EXPOSURE_REQUIRED_NOT_SURFACED")

    # ------------------------------------------------------------------
    # Critical surfacing
    # ------------------------------------------------------------------
    critical_present_flag = bool(packet.get("critical_present"))
    crit_types = _critical_signal_types(packet)
    if critical_must_surface and (critical_present_flag or crit_types):
        if "critical" not in _lower(text):
            violations.append("CRITICAL_REQUIRED_NOT_SURFACED")

        for st in crit_types:
            if st.lower() not in _lower(text):
                violations.append(f"CRITICAL_SIGNAL_NOT_NAMED:{st}")

    # ------------------------------------------------------------------
    # Phase 80 Derivation Surfacing
    # ------------------------------------------------------------------
    derivations = packet.get("derivations") or {}

    if derivations.get("price"):
        if "spread" not in _lower(text):
            violations.append("PRICE_DERIVATION_NOT_SURFACED")

    if derivations.get("exclusions"):
        if "exclusion" not in _lower(text):
            violations.append("EXCLUSION_DERIVATION_NOT_SURFACED")

    if derivations.get("verification_targets"):
        if "verification" not in _lower(text):
            violations.append("VERIFICATION_TARGETS_NOT_SURFACED")

    # ------------------------------------------------------------------
    # Phase 86 — Chips/Suggestions Contract (Server-Truth Enforcement)
    #
    # User-locked policy:
    #   - Suggestions/Chips: 3–5 items when present
    #   - Bridge: mandatory whenever suggestions/chips exist
    #
    # Notes:
    #   - Validator does NOT generate or trim content.
    #   - We only fail if the server packet violates the contract.
    # ------------------------------------------------------------------
    suggestions = _get_suggestions(packet)
    if suggestions:
        if len(suggestions) < 3 or len(suggestions) > 5:
            violations.append(f"CHIPS_COUNT_OUT_OF_RANGE:{len(suggestions)}")

        # Bridge is mandatory if chips are present
        bridge = _get_bridge(packet)
        if not bridge:
            violations.append("BRIDGE_REQUIRED_MISSING")

    # ------------------------------------------------------------------
    # Verdict
    # ------------------------------------------------------------------
    verdict = "PASS" if not violations else "FAIL"
    return NarrationValidationResult(verdict=verdict, violations=violations)


def validate_narration_as_dict(packet: Dict[str, Any], narrator_text: str) -> Dict[str, Any]:
    result = validate_narration(packet, narrator_text)
    return {
        "verdict": result.verdict,
        "violations": result.violations,
    }