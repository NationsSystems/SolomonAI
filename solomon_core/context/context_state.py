"""
Phase 49 — Context Lifecycle State Definitions

Defines the authoritative context lifecycle states.
No logic. No transitions. No side effects.
"""

from enum import Enum, auto


class ContextState(Enum):
    """
    Authoritative context lifecycle states.

    This enum is CLOSED for Phase 49.
    New states may not be added without reopening the phase.
    """

    NO_CONTEXT = auto()
    CONTEXT_REQUESTED = auto()
    CONTEXT_ESTABLISHED = auto()
    CONTEXT_ACTIVE = auto()
    CONTEXT_EXIT_PENDING = auto()
    CONTEXT_TERMINATED = auto()
