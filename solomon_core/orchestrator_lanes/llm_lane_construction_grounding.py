# ------------------------------------------------------------------
# FILE: llm_lane_construction_grounding.py
# DIRECTORY: solomon_core/orchestrator_lanes/
# ------------------------------------------------------------------
# LLM Lane Construction Grounding
#
# PURPOSE
#   Supply compact factual construction anchors when the user's request
#   explicitly references the corresponding construction concept.
#
# CONTRACT
#   - Factual grounding only
#   - Does not classify or select an execution lane
#   - Does not generate visible answer language
#   - Does not generate bridges or suggestion chips
#   - Does not authorize actions or workflows
#   - Does not inspect unavailable document content
#   - Returns only facts relevant to explicit request terminology
# ------------------------------------------------------------------

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import FrozenSet, Tuple


_MAX_GROUNDING_FACTS = 4

_TOKEN_PATTERN = re.compile(
    r"[a-z0-9]+"
)


@dataclass(
    frozen=True
)
class ConstructionGroundingRule:
    """
    Bind explicit request terminology to one compact factual anchor.
    """

    required_tokens: FrozenSet[str]
    fact: str


_CONSTRUCTION_GROUNDING_RULES: Tuple[
    ConstructionGroundingRule,
    ...,
] = (
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "allowance",
            }
        ),
        fact=(
            "A construction allowance is a placeholder amount for scope, "
            "materials, or selections not fully defined when pricing is set."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "owner",
                "allowance",
            }
        ),
        fact=(
            "An owner allowance reduces budget certainty until actual scope "
            "and cost are reconciled, and unresolved selections can delay "
            "procurement."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "alternate",
            }
        ),
        fact=(
            "An alternate is a separately priced addition to or deduction "
            "from the base bid that the owner may accept or reject."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "unit",
                "price",
            }
        ),
        fact=(
            "A unit-price contract applies an agreed rate to the actual "
            "measured quantity of work performed."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "lump",
                "sum",
            }
        ),
        fact=(
            "A lump-sum contract establishes one fixed price for a defined "
            "scope, subject to authorized contract changes."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "retainage",
            }
        ),
        fact=(
            "Retainage is money withheld from progress payments to secure "
            "completion and correction; it primarily protects the party "
            "withholding payment, not the contractor."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "change",
                "order",
            }
        ),
        fact=(
            "A change order is an agreed contract modification documenting "
            "the accepted change to scope, price, time, or other terms."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "construction",
                "change",
                "directive",
            }
        ),
        fact=(
            "A construction change directive directs changed work before "
            "the parties have agreed on the resulting price or time impact."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "ccd",
            }
        ),
        fact=(
            "A construction change directive directs changed work before "
            "the parties have agreed on the resulting price or time impact."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "rfi",
            }
        ),
        fact=(
            "An RFI is a request for clarification of the contract "
            "documents, design intent, or field condition."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "submittal",
            }
        ),
        fact=(
            "A submittal presents proposed materials, equipment, product "
            "data, shop drawings, samples, or work information for review."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "proposal",
                "valid",
                "award",
            }
        ),
        fact=(
            "An award after proposal validity expires requires written "
            "extension, reconfirmation, or repricing because price, labor, "
            "materials, and schedule assumptions may no longer hold."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "proposal",
                "validity",
            }
        ),
        fact=(
            "An award after proposal validity expires requires written "
            "extension, reconfirmation, or repricing because price, labor, "
            "materials, and schedule assumptions may no longer hold."
        ),
    ),
    ConstructionGroundingRule(
        required_tokens=frozenset(
            {
                "subcontractor",
                "exclusions",
            }
        ),
        fact=(
            "Subcontractor exclusions identify omitted scope and can create "
            "coverage gaps, pricing mismatches, coordination exposure, and "
            "unbudgeted cost before award."
        ),
    ),
)


def _request_tokens(
    user_input: str,
) -> FrozenSet[str]:
    return frozenset(
        _TOKEN_PATTERN.findall(
            str(
                user_input or ""
            ).lower()
        )
    )


def construction_grounding_facts(
    user_input: str,
) -> list[str]:
    """
    Return unique factual anchors relevant to explicit request terminology.
    """

    tokens = _request_tokens(
        user_input
    )

    if not tokens:
        return []

    facts: list[str] = []

    for rule in _CONSTRUCTION_GROUNDING_RULES:
        if not rule.required_tokens.issubset(
            tokens
        ):
            continue

        if rule.fact in facts:
            continue

        facts.append(
            rule.fact
        )

        if len(
            facts
        ) >= _MAX_GROUNDING_FACTS:
            break

    return facts