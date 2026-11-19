# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_presentation.py
# ---------------------------------------------------------------------------
# BEI Presentation Helpers — Deterministic
#
# Purpose:
#   Provide structured, professional formatting helpers for BEI output.
#   No narration, no inference, no authority.
# ---------------------------------------------------------------------------

from typing import List


# ---------------------------------------------------------------------------
# Bullet helper (legacy compatible)
# ---------------------------------------------------------------------------
def bulletize(items: List[str], limit: int = 6) -> List[str]:
    """
    Legacy bullet renderer.

    NOTE:
      - Preserved for backward compatibility
      - Does NOT enforce minimum count rule
    """
    cleaned = [x for x in items[:limit] if x]
    return [f"• {x}" for x in cleaned]


# ---------------------------------------------------------------------------
# Phase 88 — Smart list renderer (SEMANTIC UPGRADE — HARDENED)
# ---------------------------------------------------------------------------
def render_structured_block(
    items: List[str],
    *,
    min_bullets: int = 3,
    limit: int = 6,
) -> List[str]:
    """
    Deterministic presentation rule:

    • If item count >= min_bullets → semantic HTML list
    • If item count < min_bullets → single paragraph sentence

    Returns list of HTML blocks ready for join.

    HARDENING:
      - No <br> reliance
      - Emits fully-formed block HTML
      - Prevents UI newline inflation
      - Provides CSS hook via .bei-list
    """

    cleaned = [x.strip() for x in items[:limit] if x and x.strip()]

    if not cleaned:
        return []

    # -------------------------------------------------------
    # Paragraph mode (preferred for small sets)
    # -------------------------------------------------------
    if len(cleaned) < min_bullets:
        if len(cleaned) == 1:
            sentence = cleaned[0]
        else:
            sentence = "; ".join(cleaned)

        if not sentence.endswith("."):
            sentence += "."

        # IMPORTANT: return as a single atomic block
        return [f"<p>{sentence}</p>"]

    # -------------------------------------------------------
    # Semantic list mode (atomic block)
    # -------------------------------------------------------
    list_items = "".join(f"<li>{item}</li>" for item in cleaned)
    html_block = f'<ul class="bei-list">{list_items}</ul>'

    return [html_block]


# ============================================================================
# Deterministic Bid Summary Builder
# ============================================================================
def build_bid_summary(*, bid_date: str | None) -> str:
    """
    Construct a minimal, professional bid summary.

    Rules:
      - Deterministic
      - No advisory language
      - No LLM narration
      - Safe for estimator-facing UI
    """

    lines: List[str] = []

    if bid_date:
        lines.append(f"The bid is dated {bid_date}")
    else:
        lines.append("Bid date was not detected")

    rendered = render_structured_block(lines)

    return "\n".join(rendered)