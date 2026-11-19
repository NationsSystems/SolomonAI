# solomon_core/interaction/presentation_renderer.py
# ---------------------------------------------------------------------
# Phase 31 — Presentation Renderer (Hybrid Interaction Layer)
#
# PURPOSE:
#   • Convert semantic interaction contracts into human-facing text
#   • Provide a non-robotic, intentional interaction surface
#   • Enforce brevity, motivation, and consistency
#
# GUARANTEES:
#   • No business logic
#   • No intent mutation
#   • No inference or guessing
#   • Deterministic phrasing selection
#   • DB-backed phrase source (admin-ready)
#
# IMPORTANT:
#   • Core logic MUST NEVER call this module
#   • UI / API layer ONLY
# ---------------------------------------------------------------------

from typing import Dict, Any, List
import hashlib

from solomon_core.interaction.interaction_contract import (
    validate_interaction_contract,
    INTERACTION_FOLLOWUP,
)

from solomon_core.interaction.phrase_store import PhraseStore


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

def render_interaction(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Render a semantic interaction contract into a user-facing prompt.

    Returns:
        Dict[str, Any] suitable for UI / API response.
    """

    # Validate contract first — fail fast
    validate_interaction_contract(payload)

    interaction_type = payload["interaction_type"]

    if interaction_type == INTERACTION_FOLLOWUP:
        return _render_followup(payload)

    raise ValueError(f"Unsupported interaction_type: {interaction_type}")


# ---------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------

def _render_followup(payload: Dict[str, Any]) -> Dict[str, Any]:
    intent = payload["intent"]
    field = payload["field"]

    # Fetch phrase variants from DB (authoritative)
    variants = PhraseStore.get_variants(intent=intent, field=field)

    if not variants:
        raise ValueError(f"No active phrase variants for {intent}.{field}")

    # Deterministic variant selection
    variant = _select_variant_deterministic(
        variants,
        seed=f"{payload['conversation_id']}:{payload['turn_index']}:{field}",
    )

    question = _assemble_question(
        variant["template"],
        variant["options"],
    )

    return {
        "type": "followup",
        "question": question,
        "options": variant["options"],
    }


def _select_variant_deterministic(
    variants: List[Dict[str, Any]],
    seed: str,
) -> Dict[str, Any]:
    """
    Select a phrase variant deterministically using a hash seed.
    """

    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    index = int(digest, 16) % len(variants)
    return variants[index]


def _assemble_question(template: str, options: List[str]) -> str:
    """
    Assemble the final question string.

    Enforces:
      • Single sentence
      • No verbosity
      • Human-natural pacing
    """

    if not options or len(options) < 2:
        raise ValueError("At least two options are required for a follow-up")

    opts = ", ".join(options[:-1]) + f", or {options[-1]}"
    return f"{template} — {opts}?"
