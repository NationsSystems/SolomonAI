"""
Phase 49 — Context ↔ RSM Adapter (Read-Only)

Consumes RSM classifications as inputs and annotates how they
should be interpreted relative to the current Context Lifecycle state.

This module:
- Observes RSM output only
- Does not modify routing decisions
- Does not infer intent
- Does not alter context state
- Does not trigger execution
"""

from dataclasses import dataclass
from typing import Optional

from solomon_core.context.context_state import ContextState


@dataclass(frozen=True)
class ContextRsmInterpretation:
    """
    Immutable annotation describing how an RSM classification
    should be interpreted under the current context state.
    """
    context_state: ContextState
    rsm_classification: str
    scoped: bool
    allowed: bool
    note: Optional[str] = None


class ContextRsmAdapter:
    """
    Read-only adapter that annotates RSM classifications with
    context-aware interpretation.

    This class never:
    - Changes RSM output
    - Changes context state
    - Infers intent
    - Applies heuristics
    """

    def interpret(
        self,
        *,
        context_state: ContextState,
        rsm_classification: str
    ) -> ContextRsmInterpretation:
        """
        Produce a context-aware interpretation of an RSM classification.

        Parameters:
        - context_state: Current ContextState
        - rsm_classification: RSM output (opaque string)

        Returns:
        - ContextRsmInterpretation (annotation only)
        """

        # Stateless mode: always allowed, never scoped
        if context_state == ContextState.NO_CONTEXT:
            return ContextRsmInterpretation(
                context_state=context_state,
                rsm_classification=rsm_classification,
                scoped=False,
                allowed=True,
                note="Stateless interpretation"
            )

        # Active context: scoped handling applies
        if context_state == ContextState.CONTEXT_ACTIVE:
            return ContextRsmInterpretation(
                context_state=context_state,
                rsm_classification=rsm_classification,
                scoped=True,
                allowed=True,
                note="Scoped to active context"
            )

        # Context in transition states: conservative posture
        return ContextRsmInterpretation(
            context_state=context_state,
            rsm_classification=rsm_classification,
            scoped=False,
            allowed=False,
            note="Context transition in progress; interpretation deferred"
        )
