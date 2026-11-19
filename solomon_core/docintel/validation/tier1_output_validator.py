# solomon_core/docintel/validation/tier1_output_validator.py
# ---------------------------------------------------------------------------
# Tier-1 Output Validator — Admissibility Gate
# ---------------------------------------------------------------------------
#
# Purpose:
#   Decide whether BEI Tier-1 output is legally admissible for
#   reconciliation and certification.
#
# Authority:
#   • Structural validation only
#   • No interpretation
#   • No enrichment
#
# If this module fails → evidence does not exist.
# ---------------------------------------------------------------------------

from typing import Dict, Any, List

from solomon_core.logger import get_logger

logger = get_logger("tier1_output_validator")


# ---------------------------------------------------------------------------
# Approved vocabulary (expand only by charter)
# ---------------------------------------------------------------------------

ALLOWED_FIELDS = {
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


# ---------------------------------------------------------------------------
# Conversational contamination patterns
# ---------------------------------------------------------------------------

BANNED_PHRASES = (
    "here is",
    "the document states",
    "please note",
    "it appears",
    "you should",
    "we recommend",
    "summary",
)


# ---------------------------------------------------------------------------

def _contains_banned_language(value: Any) -> bool:
    if not isinstance(value, str):
        return False

    v = value.lower()
    return any(p in v for p in BANNED_PHRASES)


# ---------------------------------------------------------------------------

def validate(packet: Dict[str, Any]) -> Dict[str, Any]:
    failures: List[Dict[str, Any]] = []

    if not isinstance(packet, dict):
        return {
            "passed": False,
            "failure_count": 1,
            "failures": [{"type": "packet_not_dict"}],
        }

    if packet.get("packet_type") != "docintel":
        failures.append({"type": "wrong_packet_type"})

    payload = packet.get("payload") or {}
    evidence = payload.get("evidence")

    if not isinstance(evidence, dict):
        failures.append({"type": "missing_evidence_dict"})
        evidence = {}

    # -----------------------------------------------------------
    # Vocabulary enforcement
    # -----------------------------------------------------------
    for key in evidence.keys():
        if key not in ALLOWED_FIELDS:
            failures.append(
                {
                    "type": "unknown_field",
                    "field": key,
                }
            )

    # -----------------------------------------------------------
    # Conversational contamination
    # -----------------------------------------------------------
    for key, value in evidence.items():
        if isinstance(value, list):
            for v in value:
                if _contains_banned_language(v):
                    failures.append(
                        {
                            "type": "conversational_language",
                            "field": key,
                            "value": v,
                        }
                    )
        else:
            if _contains_banned_language(value):
                failures.append(
                    {
                        "type": "conversational_language",
                        "field": key,
                        "value": value,
                    }
                )

    passed = len(failures) == 0

    logger.info(
        "[TIER1 VALIDATOR] passed=%s failures=%s",
        passed,
        len(failures),
    )

    return {
        "passed": passed,
        "failure_count": len(failures),
        "failures": failures,
    }
