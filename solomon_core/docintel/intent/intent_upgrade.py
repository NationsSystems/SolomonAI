"""
intent_upgrade.py
CBIC → Explicit Intent Upgrade Path
Phase 55 — Explicit Intent Materialization
Phase 56 — Lawful Intent Materialization (Cardinality Collapse)
Phase 60 — ECB Continuation Acknowledgement (NON-AUTHORITATIVE)

AUTHORITATIVE NOTES
-------------------
• This is the ONLY lawful path from CBIC(s) to ExplicitIntent
• Phase 55 path requires explicit user confirmation
• Phase 56 path permits automatic materialization ONLY when
  exactly one lawful, sufficient CBIC exists
• Phase 60 permits reuse of a previously materialized operation
  within the same ECB conversation as ADVISORY CONTEXT ONLY
• No inference, no mutation, no retries
• Failure to upgrade is NOT an error condition
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
from typing import Iterable, Optional

from solomon_core.docintel.intent.cbic_models import (
    ConstraintBoundIntentCandidate,
    CBICSufficiencyState,
)
from solomon_core.docintel.intent.explicit_intent import ExplicitIntent
from solomon_core.logger import get_logger

logger = get_logger("intent_upgrade")


# ---------------------------------------------------------------------------
# Phase 55 — Explicit, User-Confirmed Upgrade (UNCHANGED)
# ---------------------------------------------------------------------------

def upgrade_cbic_to_explicit_intent(
    *,
    cbic: ConstraintBoundIntentCandidate,
    user_confirmed: bool,
    operation_version: str,
) -> ExplicitIntent:
    """
    Perform the ONLY lawful upgrade from CBIC to ExplicitIntent
    requiring explicit user confirmation.
    """

    if not user_confirmed:
        raise PermissionError("Explicit user confirmation is required")

    if cbic.sufficiency_state != CBICSufficiencyState.SUFFICIENT:
        raise PermissionError("CBIC is not sufficient for execution")

    if not cbic.candidate_operation.name:
        raise PermissionError("No operation specified in CBIC")

    if cbic.constraints.unresolved:
        raise PermissionError("CBIC contains unresolved constraints")

    intent = ExplicitIntent(
        intent_id=f"intent-{uuid4()}",
        created_at=datetime.utcnow(),
        operation=cbic.candidate_operation.name,
        operation_version=operation_version,
        document_ids=[doc.document_id for doc in cbic.documents],
        constraints=cbic.constraints.resolved,
        execution_id=f"exec-{uuid4()}",
    )

    intent.assert_authoritative()
    return intent


# ---------------------------------------------------------------------------
# Phase 56 — Lawful Intent Materialization (REFINED)
# Phase 60 — ECB Continuation Acknowledgement
# ---------------------------------------------------------------------------

def materialize_intent_from_cbics(
    *,
    cbics: Iterable[ConstraintBoundIntentCandidate],
    operation_version: str,
) -> Optional[ExplicitIntent]:
    """
    Deterministically materialize ExplicitIntent if and only if
    exactly one lawful, sufficient CBIC exists.

    Phase 56 (Refined):
    • Multi-document operations are ONLY blocked when BOTH:
        - the operation is non-compare AND
        - the intent is non-explicit (i.e., interrogative / vague)

    Phase 60 (ECB):
    • A CBIC whose candidate operation originates from a prior
      explicit intent within the same ECB conversation is lawful
      IF mediation has declared sufficiency.
    • ECB reuse is ADVISORY CONTEXT ONLY — no authority transfer.
    """

    cbics = list(cbics)

    sufficient_cbics = [
        cbic for cbic in cbics
        if cbic.sufficiency_state == CBICSufficiencyState.SUFFICIENT
        and not cbic.constraints.unresolved
        and cbic.candidate_operation.name
    ]

    logger.info(
        "[INTENT][MATERIALIZATION_CHECK]",
        extra={
            "total_cbics": len(cbics),
            "sufficient_cbics": len(sufficient_cbics),
        },
    )

    if len(sufficient_cbics) != 1:
        logger.info(
            "[INTENT][NOT_MATERIALIZED]",
            extra={
                "reason": "non_unique_or_missing_sufficient_cbic",
                "count": len(sufficient_cbics),
            },
        )
        return None

    cbic = sufficient_cbics[0]

    # -----------------------------------------------------------
    # Phase 56 / 60 — AMBIGUITY GUARD WITH ECB ACKNOWLEDGEMENT
    # -----------------------------------------------------------

    explicit_operations = {
        "extract",
        "summarize",
        "summary",
        "list",
        "price",
        "total",
        "cost",
        "scope",
        "analyze",
        "compare",
    }

    is_ecb_continuation = getattr(cbic, "operation_source", None) == "ecb"

    if (
        len(cbic.documents) > 1
        and cbic.candidate_operation.name not in explicit_operations
        and not cbic.constraints.resolved
        and not is_ecb_continuation
    ):
        logger.info(
            "[INTENT][NOT_MATERIALIZED]",
            extra={
                "reason": "multi_document_ambiguous_non_explicit_operation",
                "operation": cbic.candidate_operation.name,
                "document_count": len(cbic.documents),
            },
        )
        return None

    # -----------------------------------------------------------
    # STRUCTURAL CONSTRAINT INJECTION (UNCHANGED)
    # -----------------------------------------------------------

    constraints = dict(cbic.constraints.resolved)

    if not constraints:
        constraints["_structural"] = "implicit"

        logger.info(
            "[INTENT][STRUCTURAL_CONSTRAINT_INJECTED]",
            extra={
                "reason": "no_semantic_constraints_required",
                "operation": cbic.candidate_operation.name,
            },
        )

    intent = ExplicitIntent(
        intent_id=f"intent-{uuid4()}",
        created_at=datetime.utcnow(),
        operation=cbic.candidate_operation.name,
        operation_version=operation_version,
        document_ids=[doc.document_id for doc in cbic.documents],
        constraints=constraints,
        execution_id=f"exec-{uuid4()}",
    )

    intent.assert_authoritative()

    logger.info(
        "[INTENT][MATERIALIZED]",
        extra={
            "intent_id": intent.intent_id,
            "operation": intent.operation,
            "document_ids": intent.document_ids,
            "constraints": list(constraints.keys()),
        },
    )

    return intent
