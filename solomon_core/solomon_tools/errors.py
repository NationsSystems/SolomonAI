# errors.py — Phase 21 Strict Deterministic Error Layer
# ------------------------------------------------------
# Phase 38 GUARANTEES:
#   • SIGNAL / DATA ONLY
#   • NO execution authority
#   • NO task lifecycle control
#   • Orchestrator is sole execution authority
# ------------------------------------------------------

# ---------------------------------------------------------------------------
# Phase-38 Authority Declaration
# ---------------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # Error layer may NEVER execute tasks


# ======================================================
# Base Error Classes — Phase 21 Safe Exceptions
# ======================================================
class SolomonError(Exception):
    """
    Base class for all Solomon-specific errors.
    These errors MUST NOT execute logic or trigger tasks.
    """
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InputError(SolomonError):
    """User input / parsing errors."""
    pass


class FileError(SolomonError):
    """File read/resolve errors."""
    pass


class ParseError(SolomonError):
    """Parsing or JSON extraction failure."""
    pass


class ExecutionError(SolomonError):
    """Skill or executor runtime failure."""
    pass


class InternalError(SolomonError):
    """Internal invariant/logic violation."""
    pass


class ValidationError(SolomonError):
    """Planner / schema validation error."""
    pass


# ======================================================
# Deterministic Normalizers (Phase 21, Phase-38 Safe)
# ======================================================
def safe_message(err: Exception) -> str:
    """
    Convert ANY exception into a safe deterministic string.
    INSPECTION ONLY — no execution side effects.
    """
    if err is None:
        return "Unknown error"

    try:
        msg = str(err).strip()
        return msg if msg else err.__class__.__name__
    except Exception:
        return "Unprintable error"


def safe_return_error(message: str, err_type: str = "InternalError") -> dict:
    """
    Produce a deterministic error packet.

    Never raises.
    Never executes.
    Always returns a dict.
    """
    if not message:
        message = "Unspecified error"

    return {
        "ok": False,
        "error": message,
        "type": err_type,
    }


def wrap_exception(e: Exception, err_type: str = None) -> dict:
    """
    Convert an exception into a deterministic error packet.
    NO execution, NO side effects.
    """
    msg = safe_message(e)
    err_type = err_type or e.__class__.__name__

    return {
        "ok": False,
        "error": msg,
        "type": err_type,
    }
