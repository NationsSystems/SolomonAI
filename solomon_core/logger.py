# -------------------------------------------------------------------
# FILE: logger.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# Centralized structured logging for Solomon.
# Logging policy is owned exclusively by the project-root config.py file.
# Console diagnostics remain enabled for local commercial development.
# File logging uses safe Windows rotation.
# -------------------------------------------------------------------

import logging
import os
import sys
import traceback

from concurrent_log_handler import ConcurrentRotatingFileHandler
from sqlalchemy import text

from config import settings
from solomon_core.db import SessionLocal


LOG_FILE = os.path.join(settings.LOG_DIR, "solomon.log")
_ROOT_LOGGER_NAME = "Solomon"
_DEFAULT_CONSOLE_LOG_LEVEL = "DEBUG"
_DEFAULT_FILE_LOG_LEVEL = "DEBUG"


# =============================================================================
# SAFE FORMATTER
# =============================================================================

class SolomonFormatter(logging.Formatter):
    """
    Preserve existing format while safely surfacing `extra` fields.

    Rules:
    - Never break existing logs.
    - Only append when extras exist.
    - Ignore reserved LogRecord attributes.
    - Keep output backward compatible.
    """

    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime",
    }

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)

        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in self._RESERVED and not key.startswith("_")
        }

        if not extras:
            return base

        try:
            return f"{base} | extra={extras}"
        except Exception:
            return base


# =============================================================================
# LOG LEVEL RESOLUTION
# =============================================================================

def _normalize_log_level_name(value, *, fallback: str) -> str:
    clean_value = str(value or "").strip().upper()

    if clean_value in {
        "CRITICAL",
        "ERROR",
        "WARNING",
        "WARN",
        "INFO",
        "DEBUG",
        "NOTSET",
    }:
        return "WARNING" if clean_value == "WARN" else clean_value

    return fallback


def _resolve_log_level(value, *, fallback: str) -> int:
    clean_level_name = _normalize_log_level_name(
        value,
        fallback=fallback,
    )

    return getattr(
        logging,
        clean_level_name,
        getattr(logging, fallback, logging.DEBUG),
    )


def _resolve_console_log_level() -> int:
    return _resolve_log_level(
        getattr(
            settings,
            "CONSOLE_LOG_LEVEL",
            _DEFAULT_CONSOLE_LOG_LEVEL,
        ),
        fallback=_DEFAULT_CONSOLE_LOG_LEVEL,
    )


def _resolve_file_log_level() -> int:
    return _resolve_log_level(
        getattr(
            settings,
            "FILE_LOG_LEVEL",
            _DEFAULT_FILE_LOG_LEVEL,
        ),
        fallback=_DEFAULT_FILE_LOG_LEVEL,
    )


def _build_solomon_formatter() -> SolomonFormatter:
    return SolomonFormatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _configure_existing_solomon_handlers(
    root_logger: logging.Logger,
) -> None:
    console_level = _resolve_console_log_level()
    file_level = _resolve_file_log_level()

    root_logger.setLevel(logging.DEBUG)
    root_logger.propagate = False

    for handler in root_logger.handlers:
        if getattr(handler, "_solomon_file_handler", False):
            handler.setLevel(file_level)
            continue

        if getattr(handler, "_solomon_console_handler", False):
            handler.setLevel(console_level)


# =============================================================================
# CREATE ROOT LOGGER
# =============================================================================

root_logger = logging.getLogger(_ROOT_LOGGER_NAME)

if not getattr(root_logger, "_solomon_initialized", False):
    os.makedirs(settings.LOG_DIR, exist_ok=True)

    # -------------------------------------------------------------------------
    # FILE HANDLER
    # -------------------------------------------------------------------------
    file_handler = ConcurrentRotatingFileHandler(
        LOG_FILE,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler._solomon_file_handler = True
    file_handler.setFormatter(_build_solomon_formatter())
    file_handler.setLevel(_resolve_file_log_level())

    # -------------------------------------------------------------------------
    # CONSOLE HANDLER
    # -------------------------------------------------------------------------
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler._solomon_console_handler = True
    console_handler.setFormatter(_build_solomon_formatter())
    console_handler.setLevel(_resolve_console_log_level())

    # -------------------------------------------------------------------------
    # REGISTER HANDLERS
    # -------------------------------------------------------------------------
    root_logger.setLevel(logging.DEBUG)
    root_logger.propagate = False
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    root_logger._solomon_initialized = True

_configure_existing_solomon_handlers(root_logger)


# =============================================================================
# MODULE-LEVEL LOG CONTROL
# =============================================================================

module_log_levels = getattr(
    settings,
    "MODULE_LOG_LEVELS",
    {},
)

if isinstance(module_log_levels, dict):
    for module_name, level_name in module_log_levels.items():
        try:
            clean_module_name = str(module_name or "").strip()

            if not clean_module_name:
                continue

            level = _resolve_log_level(
                level_name,
                fallback="WARNING",
            )

            module_logger = logging.getLogger(
                f"{_ROOT_LOGGER_NAME}.{clean_module_name}"
            )
            module_logger.setLevel(level)
            module_logger.propagate = True
        except Exception:
            pass


# =============================================================================
# ECB-SAFE LOGGING HELPERS
# =============================================================================

def _with_ecb(
    extra: dict | None,
    conversation_id: str | None,
    turn_index: int | None,
):
    if not extra:
        extra = {}

    if conversation_id:
        extra.setdefault("conversation_id", conversation_id)

    if turn_index is not None:
        extra.setdefault("turn_index", turn_index)

    return extra


# =============================================================================
# SENTINEL ERROR WRITER
# =============================================================================

def write_sentinel_error(
    phase: str,
    error_type: str,
    message: str,
    stacktrace: str = None,
):
    try:
        db = SessionLocal()
        db.execute(
            text("""
                INSERT INTO error_sentinel (
                    timestamp,
                    phase,
                    error_type,
                    message,
                    stacktrace
                )
                VALUES (
                    NOW(),
                    :phase,
                    :error_type,
                    :message,
                    :stacktrace
                )
            """),
            {
                "phase": phase,
                "error_type": error_type,
                "message": message,
                "stacktrace": stacktrace,
            },
        )
        db.commit()
        db.close()
    except Exception:
        pass


# =============================================================================
# EXCEPTION UTILITIES
# =============================================================================

def format_exception_context(
    exc: Exception,
    phase: str = None,
) -> str:
    exc_type = type(exc).__name__
    message = str(exc)
    tb = traceback.format_exc(limit=6)

    header = (
        f"[{phase}] {exc_type}: {message}"
        if phase
        else f"{exc_type}: {message}"
    )
    body = "\n".join(
        line.strip()
        for line in tb.splitlines()[-8:]
    )

    return f"{header}\n{body}"


def log_exception(
    logger_obj: logging.Logger,
    exc: Exception,
    phase: str = None,
    *,
    conversation_id: str | None = None,
    turn_index: int | None = None,
):
    trace_text = format_exception_context(exc, phase)

    logger_obj.error(
        trace_text,
        extra=_with_ecb(
            None,
            conversation_id,
            turn_index,
        ),
    )

    write_sentinel_error(
        phase=phase or "unknown",
        error_type=type(exc).__name__,
        message=str(exc),
        stacktrace=trace_text,
    )

    return trace_text


# =============================================================================
# LOGGER GETTER
# =============================================================================

def get_logger(name: str) -> logging.Logger:
    if not isinstance(name, str):
        name = str(name)

    return logging.getLogger(
        f"{_ROOT_LOGGER_NAME}.{name}"
    )