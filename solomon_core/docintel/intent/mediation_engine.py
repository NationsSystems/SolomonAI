"""
mediation_engine.py
Profiling-Style Mediation Engine
Phase 55 — Explicit Intent Materialization
Phase 56 — Lawful Sufficiency Refinement
Phase 62 — CBIC Emission Correction
Phase 64 — Deterministic Guidance Signals (Read-Only)

FILE: solomon_core/docintel/intent/mediation_engine.py

AUTHORITATIVE NOTES
-------------------
• Mediation is pre-authority and non-executing
• Mediation produces CBICs only when document authority is plausible
• Mediation constrains possibility space without collapsing it
• Phase 56 collapse is EXTERNAL to mediation
• No inference, no defaults, no execution
• Phase 64 guidance signals are observational only
"""

from __future__ import annotations

from typing import Dict, List, Optional
from uuid import uuid4

from solomon_core.logger import get_logger

# ⛔ CBICFactory removed from top-level import to break circular dependency
from solomon_core.docintel.intent.cbic_models import (
    CBICSufficiencyState,
    ConstraintSource,
    DocumentArtifact,
    ConstraintBoundIntentCandidate,
)

logger = get_logger("docintel.mediation")


# ---------------------------------------------------------------------------
# Mediation Engine
# ---------------------------------------------------------------------------

class MediationEngine:
    """
    Deterministic profiling-style mediation engine.

    This engine inspects artifacts and prompt signals to determine:
    • what operations are possible
    • what operations are impossible
    • what constraints are missing

    It NEVER:
    • infers intent
    • selects defaults
    • authorizes execution
    """

    PHRASE_ALIASES: Dict[str, List[str]] = {
        "summarize": [
            "summary",
            "summarize",
            "quick rundown",
            "overview",
            "high level",
            "in a nutshell",
            "what's in this document",
            "what is in this document",
            "whats in this document",
            "what's in the document",
            "what is in the document",
            "whats in the document",
            "what does this document say",
            "what does the document say",
            "tell me about this document",
            "tell me about the document",
            "describe this document",
            "describe the document",
        ],
        "extract": [
            "extract",
            "pull out",
            "list",
            "what's included",
            "what is included",
            "what's excluded",
            "what is excluded",
            "clarifications",
            "exclusions",
        ],
        "analyze": [
            "analyze",
            "risk",
            "hidden cost",
            "issues",
            "concerns",
        ],
        "compare": [
            "compare",
            "difference",
            "differences",
            "versus",
            "vs",
        ],
    }

    # ------------------------------------------------------------------
    # Phase 64 — Deterministic Guidance (Read-Only)
    # ------------------------------------------------------------------

    def build_guidance_signals(
        self,
        *,
        documents: List[DocumentArtifact],
        candidate_operation: Optional[str],
    ) -> List[Dict[str, str]]:

        signals: List[Dict[str, str]] = []

        if len(documents) >= 2:
            signals.append({"type": "compare_ready"})

        if candidate_operation == "extract":
            signals.append({"type": "extraction_possible"})

        if candidate_operation == "summarize":
            signals.append({"type": "summary_possible"})

        return signals

    # ------------------------------------------------------------------
    # Single-Doc Deictic Fallback (kept as deep fallback)
    # ------------------------------------------------------------------

    def _single_doc_deictic_fallback(
        self,
        *,
        documents: List[DocumentArtifact],
        prompt_text: str,
        eligible_operations: List[str],
    ) -> tuple[Optional[str], Optional[ConstraintSource]]:

        if len(documents) != 1:
            return None, None

        if "summarize" not in eligible_operations:
            return None, None

        p = prompt_text.lower().strip()

        deictic_markers = [
            "this",
            "this?",
            "this doc",
            "this document",
            "the document",
            "the doc",
        ]

        if any(m in p for m in deictic_markers):
            logger.info("[MEDIATION][SINGLE_DOC_DEICTIC_SUMMARY]")
            return "summarize", ConstraintSource.USER_PROMPT

        return None, None

    # ------------------------------------------------------------------

    def _profile_operation_from_prompt(
        self,
        prompt_text: str,
        eligible_operations: List[str],
    ) -> tuple[Optional[str], Optional[ConstraintSource]]:

        prompt_lower = prompt_text.lower()

        for op in eligible_operations:

            if op in prompt_lower:
                return op, ConstraintSource.USER_PROMPT

            for phrase in self.PHRASE_ALIASES.get(op, []):
                if phrase in prompt_lower:
                    return op, ConstraintSource.USER_PROMPT

        return None, None

    # ------------------------------------------------------------------

    def _is_deictic_plural_compare(self, prompt_text: str) -> bool:
        p = prompt_text.lower()
        markers = [
            "these",
            "these documents",
            "these docs",
            "these files",
            "all of these",
            "all these",
        ]
        return any(m in p for m in markers)

    def mediate(
        self,
        *,
        documents: List[DocumentArtifact],
        prompt_text: str,
        eligible_operations: List[str],
        required_constraints: Dict[str, List[str]],
        resolved_constraints: Dict[str, object],
    ) -> Optional[ConstraintBoundIntentCandidate]:

        from solomon_core.docintel.intent.cbic_models import CBICFactory

        cbic_id = f"cbic-{uuid4()}"

        logger.info(
            "[MEDIATION][ENTER]",
            extra={
                "cbic_id": cbic_id,
                "document_count": len(documents),
                "eligible_operations": eligible_operations,
                "resolved_constraint_keys": list(resolved_constraints.keys()),
            },
        )

        if not documents:
            logger.info(
                "[MEDIATION][EXIT_NO_DOCS]",
                extra={"cbic_id": cbic_id},
            )
            return None

        # ------------------------------------------------------------------
        # 🔥 Phase 82 — Investigator is PRIMARY witness
        # ------------------------------------------------------------------

        candidate_operation = None
        operation_source = None

        investigator_op = resolved_constraints.get("investigator_operation")
        if investigator_op and investigator_op in eligible_operations:
            candidate_operation = investigator_op
            operation_source = ConstraintSource.USER_PROMPT
            logger.info(
                "[MEDIATION][INVESTIGATOR_PRIMARY]",
                extra={"cbic_id": cbic_id, "candidate_operation": candidate_operation},
            )

        # ------------------------------------------------------------------
        # Fallback → prompt profiling
        # ------------------------------------------------------------------

        if not candidate_operation:
            candidate_operation, operation_source = self._profile_operation_from_prompt(
                prompt_text,
                eligible_operations,
            )

        # ------------------------------------------------------------------
        # Deep fallback → deictic
        # ------------------------------------------------------------------

        if not candidate_operation:
            candidate_operation, operation_source = self._single_doc_deictic_fallback(
                documents=documents,
                prompt_text=prompt_text,
                eligible_operations=eligible_operations,
            )

        guidance = self.build_guidance_signals(
            documents=documents,
            candidate_operation=candidate_operation,
        )

        logger.info(
            "[MEDIATION][GUIDANCE_SIGNALS]",
            extra={"cbic_id": cbic_id, "signals": guidance},
        )

        logger.info(
            "[MEDIATION][OPERATION_PROFILED]",
            extra={
                "cbic_id": cbic_id,
                "candidate_operation": candidate_operation,
                "operation_source": operation_source.name if operation_source else None,
            },
        )

        if not candidate_operation:
            logger.info(
                "[MEDIATION][EXIT_NO_OPERATION]",
                extra={"cbic_id": cbic_id},
            )
            return None

        unresolved_constraints: Dict[str, List[object]] = {}

        for constraint in required_constraints.get(candidate_operation, []):
            if constraint not in resolved_constraints:
                unresolved_constraints[constraint] = []

        # ------------------------------------------------------------------
        # Structural binding for exactly 2 docs
        # ------------------------------------------------------------------
        if (
            candidate_operation == "compare"
            and len(documents) == 2
            and set(unresolved_constraints.keys()) == {"left_doc", "right_doc"}
        ):
            resolved_constraints = {
                "left_doc": documents[0].document_id,
                "right_doc": documents[1].document_id,
            }
            unresolved_constraints = {}

            logger.info(
                "[MEDIATION][STRUCTURAL_COMPARE_BINDING]",
                extra={
                    "cbic_id": cbic_id,
                    "left_doc": documents[0].document_id,
                    "right_doc": documents[1].document_id,
                },
            )

        # ------------------------------------------------------------------
        # Compare-All for 3+ docs
        # ------------------------------------------------------------------
        if (
            candidate_operation == "compare"
            and len(documents) >= 3
            and self._is_deictic_plural_compare(prompt_text)
        ):
            unresolved_constraints = {}
            logger.info(
                "[MEDIATION][COMPARE_ALL_BINDING]",
                extra={
                    "cbic_id": cbic_id,
                    "doc_count": len(documents),
                },
            )

        # ------------------------------------------------------------------
        # Sufficiency determination
        # ------------------------------------------------------------------
        if unresolved_constraints:
            sufficiency = CBICSufficiencyState.SALVAGEABLE
            explanation = "Operation identified but required constraints are missing."
            blocking = list(unresolved_constraints.keys())
        else:
            sufficiency = CBICSufficiencyState.SUFFICIENT
            explanation = "All required constraints resolved."
            blocking = []

        logger.info(
            "[MEDIATION][SUFFICIENCY]",
            extra={
                "cbic_id": cbic_id,
                "sufficiency": sufficiency.name,
                "blocking_reasons": blocking,
            },
        )

        cbic = CBICFactory.create(
            cbic_id=cbic_id,
            documents=documents,
            prompt_text=prompt_text,
            candidate_operation=candidate_operation,
            operation_source=operation_source,
            resolved_constraints=resolved_constraints,
            unresolved_constraints=unresolved_constraints,
            eligible_operations=eligible_operations,
            ineligible_operations={},
            sufficiency_state=sufficiency,
            explanation=explanation,
            blocking_reasons=blocking,
            clarification_requests=list(unresolved_constraints.keys()),
        )

        logger.info("[MEDIATION][CBIC_EMITTED]", extra={"cbic_id": cbic_id})
        return cbic
