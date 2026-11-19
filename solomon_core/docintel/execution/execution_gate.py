"""
File: solomon_core/docintel/execution/execution_gate.py
Phase: 54 — Document Intelligence System Completion
Purpose: Hard execution boundary enforcing authorization and constraints

The ExecutionGate is the *only* permitted entry point for execution inside
DocIntel. It verifies authorization, constraints, and evidence before
allowing any primitive to run.

CRITICAL INVARIANTS:
- Fail-closed on any violation
- No retries, recovery, or inference
- No primitive-to-primitive calls
- No execution without explicit authorization and evidence
- Execution identity is created by the gate and threaded explicitly
"""

from __future__ import annotations

from typing import Callable, Any

from solomon_core.docintel.execution.execution_authorization import ExecutionAuthorization
from solomon_core.docintel.execution.execution_constraints import ExecutionConstraints
from solomon_core.docintel.execution.execution_identity import ExecutionIdentity
from solomon_core.docintel.evidence.evidence_binding import EvidenceBinding


class ExecutionGateError(Exception):
    """Raised when execution is denied or structurally invalid."""


class ExecutionGate:
    """
    Hard boundary for all DocIntel execution.
    """

    # ------------------------------------------------------------------
    # Entry Point
    # ------------------------------------------------------------------

    @staticmethod
    def execute(
        *,
        authorization: ExecutionAuthorization,
        constraints: ExecutionConstraints,
        evidence: EvidenceBinding,
        executor: Callable[[ExecutionIdentity], Any],
    ) -> Any:
        """
        Execute a primitive through the execution gate.

        Args:
            authorization: ExecutionAuthorization issued by Orchestrator
            constraints: ExecutionConstraints restricting execution
            evidence: EvidenceBinding validated against policy
            executor: Callable accepting ExecutionIdentity and performing execution

        Returns:
            Executor result

        Raises:
            ExecutionGateError on any violation
        """

        # Defensive validation
        if authorization is None:
            raise ExecutionGateError("Execution denied: missing authorization")
        if constraints is None:
            raise ExecutionGateError("Execution denied: missing constraints")
        if evidence is None:
            raise ExecutionGateError("Execution denied: missing evidence binding")
        if executor is None:
            raise ExecutionGateError("Execution denied: missing executor")

        authorization.assert_valid()
        constraints.assert_valid()
        evidence.assert_valid()

        # Create execution identity for auditability
        execution_identity = ExecutionIdentity.create()
        execution_identity.assert_valid()

        # Delegate execution with explicit identity
        try:
            return executor(execution_identity)
        except Exception as exc:
            # No recovery, no retry — propagate
            raise ExecutionGateError(
                f"Execution failed for {execution_identity.execution_id}"
            ) from exc
