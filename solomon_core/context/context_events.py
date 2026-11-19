"""
Phase 49 — Context Lifecycle Events

Defines the closed set of events that may trigger
context lifecycle state transitions.

No logic. No dispatch. No side effects.
"""

from enum import Enum, auto


class ContextEvent(Enum):
    """
    Authoritative context lifecycle events.

    This enum is CLOSED for Phase 49.
    New events may not be added without reopening the phase.
    """

    REQUEST_CONTEXT = auto()
    ACK_CONTEXT = auto()
    CONTEXT_INTERACTION = auto()
    REQUEST_EXIT = auto()
    CONFIRM_EXIT = auto()
    TIMEOUT = auto()
    FORCE_RESET = auto()
