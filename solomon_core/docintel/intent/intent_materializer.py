# solomon_core/docintel/intent/intent_materializer.py
# ------------------------------------------------------------------
# PHASE 56 — LAWFUL INTENT MATERIALIZATION
#
# PURPOSE:
#   • Deterministically materialize ExplicitIntent when and only when
#     exactly one lawful interpretation exists.
#   • Perform authority-collapse ONLY (no mediation, no inference).
#
# GUARANTEES:
#   • Single canonical ExplicitIntent schema
#   • No intent guessing
#   • No heuristic ranking
#   • No UI authority
#   • Fully auditable
#
# NOTE:
#   This module emits ONLY the runtime ExplicitIntent model.
# ------------------------------------------------------------------

from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from solomon_core.logger import get_logger
from solomon_core.docintel.intent.explicit_intent import ExplicitIntent

logger = get_logger("intent_materializer")


class LawfulInterpretation:
    """
    Minimal structural contract expected from mediation.

    This is a documentation-only interface describing what mediation
    must already have produced. This class is NOT authoritative.
    """

    def __init__(
        self,
        operation: str,
        document_ids: List[str],
        constraints: dict,
        operation_version: str,
    ):
        self.operation = operation
        self.document_ids = document_ids
        self.constraints = constraints
        self.operation_version = operation_version


def materialize_intent(
    lawful_interpretations: List[LawfulInterpretation],
) -> Optional[ExplicitIntent]:
    """
    Deterministically materialize an ExplicitIntent if and only if
    exactly one lawful interpretation exists.

    This function performs NO inference and NO selection.
    """

    count = len(lawful_interpretations)

    logger.info(
        "[INTENT][MATERIALIZATION_CHECK]",
        extra={"lawful_interpretation_count": count},
    )

    if count != 1:
        logger.info(
            "[INTENT][NOT_MATERIALIZED]",
            extra={
                "reason": "non_unique_lawful_set",
                "lawful_interpretation_count": count,
            },
        )
        return None

    interpretation = lawful_interpretations[0]

    intent = ExplicitIntent(
        intent_id=f"intent-{uuid4()}",
        created_at=datetime.utcnow(),
        operation=interpretation.operation,
        operation_version=interpretation.operation_version,
        document_ids=interpretation.document_ids,
        constraints=interpretation.constraints,
        execution_id=f"exec-{uuid4()}",
    )

    intent.assert_authoritative()

    logger.info(
        "[INTENT][MATERIALIZED]",
        extra={
            "intent_id": intent.intent_id,
            "operation": intent.operation,
            "document_ids": intent.document_ids,
        },
    )

    return intent
