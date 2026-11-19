# solomon_core/docintel/validation/evidence_validator.py
# ---------------------------------------------------------------------------
# Tier-1 Evidence Validator
#
# Purpose:
#   Deterministically verify that Tier-1 outputs are admissible before
#   conversion into BEI facts and reconciliation.
#
# Authority:
#   • Validation only
#   • No mutation
#   • No enrichment
#   • No inference
#
# If validation fails → caller must halt downstream processing.
# ---------------------------------------------------------------------------

from typing import Dict, Any, List

from solomon_core.logger import get_logger

logger = get_logger("evidence_validator")


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

ALLOWED_TOP_LEVEL_FIELDS = {
    "bid_name",
    "bid_date",
    "issuing_party",
    "base_bid_amount",
    "scope_of_work_summary",
    "inclusions",
    "exclusions",
    "alternates",
    "assumptions_and_clarifications",
    "schedule_or_duration_terms",
    "pricing_validity_window",
    "special_conditions_or_risks",
}


FORBIDDEN_PHRASES = {
    "it appears",
    "it seems",
    "likely",
    "probably",
    "may indicate",
    "suggests",
    "could be",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_atomic(value: Any) -> bool:
    """
    Atomic means:
      • scalar
      • list of scalars
      • deterministic small dict containers (ex: {"raw": "$123"})
    """
    if value is None:
        return True

    if isinstance(value, (str, int, float, bool)):
        return True

    if isinstance(value, list):
        return all(isinstance(v, (str, int, float, bool)) for v in value)

    # ⭐ NEW — allow small structured primitives
    if isinstance(value, dict):
        return all(isinstance(v, (str, int, float, bool, type(None))) for v in value.values())

    return False


def _contains_forbidden_language(value: Any) -> bool:
    if isinstance(value, str):
        lower = value.lower()
        return any(p in lower for p in FORBIDDEN_PHRASES)

    if isinstance(value, list):
        return any(_contains_forbidden_language(v) for v in value)

    if isinstance(value, dict):
        return any(_contains_forbidden_language(v) for v in value.values())

    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate(evidence: Dict[str, Any]) -> Dict[str, Any]:
    violations: List[Dict[str, Any]] = []

    if not isinstance(evidence, dict):
        return {
            "passed": False,
            "violations": [{"type": "not_dict"}],
        }

    # -----------------------------------------------------------
    # Unknown fields
    # -----------------------------------------------------------
    for field in evidence.keys():
        if field not in ALLOWED_TOP_LEVEL_FIELDS:
            violations.append(
                {
                    "type": "unknown_field",
                    "field": field,
                }
            )

    # -----------------------------------------------------------
    # Atomicity
    # -----------------------------------------------------------
    for field, value in evidence.items():
        if not _is_atomic(value):
            violations.append(
                {
                    "type": "non_atomic",
                    "field": field,
                }
            )

    # -----------------------------------------------------------
    # Conversational / speculative language
    # -----------------------------------------------------------
    for field, value in evidence.items():
        if _contains_forbidden_language(value):
            violations.append(
                {
                    "type": "forbidden_language",
                    "field": field,
                }
            )

    passed = len(violations) == 0

    logger.info(
        "[VALIDATOR] passed=%s violations=%s",
        passed,
        len(violations),
    )

    return {
        "passed": passed,
        "violations": violations,
    }
