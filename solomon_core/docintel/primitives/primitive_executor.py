"""
File: solomon_core/docintel/primitives/primitive_executor.py
Phase: 72 — Evidence Binding Enablement
Purpose: Controlled execution adapter for certified DocIntel primitives

This module defines PrimitiveExecutor, the only mechanism allowed to invoke
primitive logic. It now ALSO performs evidence binding using certified
primitive declarations.

CRITICAL INVARIANTS:
- Primitives execute exactly once per invocation
- No primitive-to-primitive calls
- No retries, recovery, or fallback
- No access to authorization or control logic
- Evidence binding is mandatory and fail-closed
"""

from __future__ import annotations

from typing import Callable, Any

from solomon_core.docintel.primitives.primitive_context import PrimitiveContext
from solomon_core.docintel.evidence.evidence_binding import EvidenceBinding
from solomon_core.docintel.certified_primitives import REGISTRY


class PrimitiveExecutionError(Exception):
    """Raised when primitive execution fails."""


class PrimitiveExecutor:
    """
    Executes a certified primitive in a controlled context
    and binds evidence to its result.
    """

    @staticmethod
    def execute(
        *,
        context: PrimitiveContext,
        primitive_fn: Callable[[PrimitiveContext], Any],
        primitive_name: str,
        primitive_version: str,
    ) -> Any:
        """
        Execute a primitive function with a validated context
        and bind evidence according to its certification.

        Args:
            context: PrimitiveContext containing documents and evidence
            primitive_fn: Callable implementing primitive logic
            primitive_name: Certified primitive name
            primitive_version: Certified primitive version

        Returns:
            Evidence-bound primitive result

        Raises:
            PrimitiveExecutionError on failure
        """

        if context is None:
            raise PrimitiveExecutionError("Missing PrimitiveContext")
        if primitive_fn is None:
            raise PrimitiveExecutionError("Missing primitive function")

        context.assert_valid()

        # ------------------------------------------------------------------
        # Certification Lookup (Fail-Closed)
        # ------------------------------------------------------------------
        try:
            record = REGISTRY.assert_certified(
                name=primitive_name,
                version=primitive_version,
            )
        except Exception as exc:
            raise PrimitiveExecutionError(
                "Primitive not certified for execution"
            ) from exc

        # ------------------------------------------------------------------
        # Primitive Execution (Single-Shot)
        # ------------------------------------------------------------------
        try:
            result = primitive_fn(context)
        except Exception as exc:
            raise PrimitiveExecutionError(
                "Primitive execution failed"
            ) from exc

        # ------------------------------------------------------------------
        # Evidence Binding (Mandatory)
        # ------------------------------------------------------------------
        try:
            bound_evidence = EvidenceBinding.bind(
                evidence=context.evidence,
                policy=record.evidence,
            )
        except Exception as exc:
            raise PrimitiveExecutionError(
                "Evidence binding failed"
            ) from exc

        # ------------------------------------------------------------------
        # Attach Evidence (No Formatting / No Presentation)
        # ------------------------------------------------------------------
        if hasattr(result, "bind_evidence"):
            result = result.bind_evidence(bound_evidence)
        else:
            # Minimal, non-invasive attachment
            setattr(result, "evidence", bound_evidence)

        return result
