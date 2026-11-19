"""
Phase 49 — Context Lifecycle Orchestrator

Authoritative, system-governed context lifecycle state machine.

Responsibilities:
- Maintain explicit context state
- Enforce legal state transitions
- Reject illegal transitions
- Provide auditable transition results

This module contains NO planner, model, execution, or UX logic.
"""

from dataclasses import dataclass
from typing import Optional

from solomon_core.context.context_state import ContextState
from solomon_core.context.context_events import ContextEvent


@dataclass(frozen=True)
class ContextTransitionResult:
    """
    Immutable record of a context lifecycle transition attempt.
    """
    prior_state: ContextState
    event: ContextEvent
    next_state: ContextState
    allowed: bool
    reason: Optional[str] = None


class ContextLifecycle:
    """
    Authoritative context lifecycle state machine.

    This class enforces the locked Phase 49 state machine.
    It does not infer intent, guess transitions, or consume signals.
    """

    def __init__(self) -> None:
        self._state: ContextState = ContextState.NO_CONTEXT

    @property
    def state(self) -> ContextState:
        """
        Current context lifecycle state.
        """
        return self._state

    # ---------------------------------------------------------------------
    # Public Transition Interface
    # ---------------------------------------------------------------------

    def handle_event(self, event: ContextEvent) -> ContextTransitionResult:
        """
        Attempt to apply a context lifecycle event.

        Returns a ContextTransitionResult describing the outcome.
        """
        prior = self._state

        # Forced reset is always legal and terminal
        if event == ContextEvent.FORCE_RESET:
            self._state = ContextState.CONTEXT_TERMINATED
            self._state = ContextState.NO_CONTEXT
            return ContextTransitionResult(
                prior_state=prior,
                event=event,
                next_state=self._state,
                allowed=True,
                reason="Forced reset applied"
            )

        # Dispatch based on current state
        handler = self._get_state_handler(self._state)
        result = handler(event)

        if result.allowed:
            self._state = result.next_state

        return result

    # ---------------------------------------------------------------------
    # State Handlers (Explicit, No Heuristics)
    # ---------------------------------------------------------------------

    def _get_state_handler(self, state: ContextState):
        return {
            ContextState.NO_CONTEXT: self._handle_no_context,
            ContextState.CONTEXT_REQUESTED: self._handle_context_requested,
            ContextState.CONTEXT_ESTABLISHED: self._handle_context_established,
            ContextState.CONTEXT_ACTIVE: self._handle_context_active,
            ContextState.CONTEXT_EXIT_PENDING: self._handle_context_exit_pending,
            ContextState.CONTEXT_TERMINATED: self._handle_context_terminated,
        }[state]

    def _handle_no_context(self, event: ContextEvent) -> ContextTransitionResult:
        if event == ContextEvent.REQUEST_CONTEXT:
            return ContextTransitionResult(
                prior_state=ContextState.NO_CONTEXT,
                event=event,
                next_state=ContextState.CONTEXT_REQUESTED,
                allowed=True
            )

        return self._reject(ContextState.NO_CONTEXT, event)

    def _handle_context_requested(self, event: ContextEvent) -> ContextTransitionResult:
        if event == ContextEvent.ACK_CONTEXT:
            return ContextTransitionResult(
                prior_state=ContextState.CONTEXT_REQUESTED,
                event=event,
                next_state=ContextState.CONTEXT_ESTABLISHED,
                allowed=True
            )

        return self._reject(ContextState.CONTEXT_REQUESTED, event)

    def _handle_context_established(self, event: ContextEvent) -> ContextTransitionResult:
        if event == ContextEvent.CONTEXT_INTERACTION:
            return ContextTransitionResult(
                prior_state=ContextState.CONTEXT_ESTABLISHED,
                event=event,
                next_state=ContextState.CONTEXT_ACTIVE,
                allowed=True
            )

        return self._reject(ContextState.CONTEXT_ESTABLISHED, event)

    def _handle_context_active(self, event: ContextEvent) -> ContextTransitionResult:
        if event == ContextEvent.CONTEXT_INTERACTION:
            return ContextTransitionResult(
                prior_state=ContextState.CONTEXT_ACTIVE,
                event=event,
                next_state=ContextState.CONTEXT_ACTIVE,
                allowed=True
            )

        if event == ContextEvent.REQUEST_EXIT:
            return ContextTransitionResult(
                prior_state=ContextState.CONTEXT_ACTIVE,
                event=event,
                next_state=ContextState.CONTEXT_EXIT_PENDING,
                allowed=True
            )

        if event == ContextEvent.TIMEOUT:
            return ContextTransitionResult(
                prior_state=ContextState.CONTEXT_ACTIVE,
                event=event,
                next_state=ContextState.CONTEXT_EXIT_PENDING,
                allowed=True,
                reason="Timeout triggered exit pending"
            )

        return self._reject(ContextState.CONTEXT_ACTIVE, event)

    def _handle_context_exit_pending(self, event: ContextEvent) -> ContextTransitionResult:
        if event == ContextEvent.CONFIRM_EXIT:
            return ContextTransitionResult(
                prior_state=ContextState.CONTEXT_EXIT_PENDING,
                event=event,
                next_state=ContextState.CONTEXT_TERMINATED,
                allowed=True
            )

        return self._reject(ContextState.CONTEXT_EXIT_PENDING, event)

    def _handle_context_terminated(self, event: ContextEvent) -> ContextTransitionResult:
        # CONTEXT_TERMINATED always resolves to NO_CONTEXT on next ingress
        return ContextTransitionResult(
            prior_state=ContextState.CONTEXT_TERMINATED,
            event=event,
            next_state=ContextState.NO_CONTEXT,
            allowed=True,
            reason="Context terminated; reverting to NO_CONTEXT"
        )

    # ---------------------------------------------------------------------
    # Rejection Helper
    # ---------------------------------------------------------------------

    def _reject(self, state: ContextState, event: ContextEvent) -> ContextTransitionResult:
        return ContextTransitionResult(
            prior_state=state,
            event=event,
            next_state=state,
            allowed=False,
            reason=f"Illegal transition from {state.name} via {event.name}"
        )
