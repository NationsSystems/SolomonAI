"""
solomon_core/ingress/unknown_collapse.py

Phase 48 — Unknown Collapse Resolver (Pure, Declarative)

PURPOSE
-------
Provide a deterministic collapse posture for any ingress request
classified as UNKNOWN by the RSM classifier.

This module:
- DOES NOT route
- DOES NOT execute
- DOES NOT invoke planners or skills
- DOES NOT modify UX
- DOES NOT persist state
- DOES NOT infer or retry classification

Unknowns collapse; they do not branch.
"""

from typing import Dict

# ---------------------------------------------------------------------------
# Canonical collapsed posture (LOCKED)
# ---------------------------------------------------------------------------

COLLAPSED_UNKNOWN_POSTURE: Dict[str, object] = {
    "authority": "assistive",
    "determinism": "open",
    "presentation": "raw",
    "execution_eligible": False,
    "collapsed": True,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def collapse_unknown() -> Dict[str, object]:
    """
    Return the canonical collapsed posture for UNKNOWN ingress cases.

    This function:
    - Is deterministic
    - Has no side effects
    - Does not inspect payloads
    - Does not escalate authority
    - Does not permit execution

    Returns a new dict instance on each call to prevent mutation leakage.
    """
    return dict(COLLAPSED_UNKNOWN_POSTURE)
