# ---------------------------------------------------------------------------
# FILE: solomon_core/presentation/posture_resolver.py
# ---------------------------------------------------------------------------
# Posture Resolver
#
# Determines presentation posture from authoritative context.
# NO user-language interpretation permitted.
# ---------------------------------------------------------------------------


POSTURES = {
    "FORENSIC",
    "EXECUTIVE",
    "TIME_PRESSURE",
    "BINARY",
    "TOPIC_FOCUS",
    "WALKTHROUGH",
}


def resolve_posture(execution_context: dict | None) -> str:
    """
    Lawful posture resolution.

    Priority:
        1) Explicit posture provided by authority.
        2) Deterministic default.

    This module MUST NOT interpret user text.
    """

    if not execution_context:
        return "EXECUTIVE"

    posture = execution_context.get("presentation_posture")

    if posture in POSTURES:
        return posture

    return "EXECUTIVE"
