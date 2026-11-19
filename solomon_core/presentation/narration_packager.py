# ---------------------------------------------------------------------------
# FILE: solomon_core/presentation/narration_packager.py
# ---------------------------------------------------------------------------
# Narration Packager
#
# Builds the bounded packet that the narrator is permitted to see.
# ---------------------------------------------------------------------------

from typing import Dict, Any, List


# ============================================================================
# Public API
# ============================================================================

def build_narration_packet(
    posture: str,
    implications: List[str],
    visibility: Dict[str, Any],
    decision_object: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Construct the narration contract.

    The narrator receives:
        - posture
        - visible findings
        - implication tokens
        - constraints
        - certified derivations
        - certified commercials

    It NEVER receives raw reasoning or hidden material.
    """

    return {
        "posture": posture,
        "implications": implications,
        "documents": visibility.get("documents"),
        "findings": visibility.get("findings"),
        "critical_present": visibility.get("critical_present"),
        "constraints": {
            "no_inference": True,
            "no_recommendation": True,
            "must_preserve_meaning": True,
            "critical_must_surface": True,
        },
        "decision_id": decision_object.get("decision_id"),

        # ---------------------------------------------------------------
        # Phase 80 – visibility expansion
        # ---------------------------------------------------------------
        "commercials": decision_object.get("commercials"),
        "derivations": visibility.get("derivations"),
    }
