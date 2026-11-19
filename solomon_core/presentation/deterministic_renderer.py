# ---------------------------------------------------------------------------
# FILE: solomon_core/presentation/deterministic_renderer.py
# ---------------------------------------------------------------------------
# Deterministic Renderer
#
# Produces guaranteed narration without LLM participation.
# Used for fallback, replay, and safety.
# ---------------------------------------------------------------------------

from typing import Dict, Any, List


# ============================================================================
# Helpers
# ============================================================================

def _render_readiness(implications: List[str]) -> str:
    if "READINESS_NOT_ESTABLISHED" in implications:
        return "Readiness is not established."
    return "No blocking conditions detected."


def _render_exposure(implications: List[str]) -> str:
    if "HIGH_EXPOSURE" in implications:
        return "High exposure items are present."
    return ""


# ============================================================================
# Public API
# ============================================================================

def render_without_llm(packet: Dict[str, Any]) -> str:
    """
    Deterministic narration.

    No style.
    No inference.
    No expansion.
    """

    implications = packet.get("implications") or []
    findings = packet.get("findings") or []
    documents = packet.get("documents") or []

    lines: List[str] = []

    # ------------------------------------------------------------------
    # Readiness
    # ------------------------------------------------------------------
    lines.append(_render_readiness(implications))

    # ------------------------------------------------------------------
    # Exposure
    # ------------------------------------------------------------------
    exposure = _render_exposure(implications)
    if exposure:
        lines.append(exposure)

    # ------------------------------------------------------------------
    # CRITICAL items
    # ------------------------------------------------------------------
    criticals = [f for f in findings if f.get("severity") == "CRITICAL"]

    if criticals:
        lines.append("Critical differences detected.")

        for c in criticals:
            lines.append(f"- {c.get('signal_type')}")

    return "\n".join(lines)
