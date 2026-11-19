# ---------------------------------------------------------------------------
# FILE: system_diagnostics.py
# DIRECTORY: solomon_core/diagnostics/
# ---------------------------------------------------------------------------
# System Diagnostics
#
# PURPOSE:
#   Expose raw system, storage, model, and dependency signals for observability
#   and presentation layers.
#
# GUARANTEES:
#   - Read-only.
#   - Signal-only; no interpretation or conclusions.
#   - No recommendations or framing.
#   - No exceptions propagated upward.
#   - Does not load or execute generation or embedding models.
# ---------------------------------------------------------------------------

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import psutil
from sqlalchemy import text

from config import settings
from solomon_core.db import SessionLocal
from solomon_core.llm.llm_transport import (
    direct_model_files_available,
)
from solomon_core.logger import get_logger
from solomon_core.solomon_tools.fileops import ensure_faiss_index

logger = get_logger("diagnostics.system")


# ---------------------------------------------------------------------------
# Mechanical Dependency Checks
# ---------------------------------------------------------------------------

def _model_files_available(
    model_path: str | Path,
) -> bool:
    """Check whether one local Transformers model folder is complete."""

    path = Path(model_path)

    if not path.exists() or not path.is_dir():
        return False

    has_config = (path / "config.json").exists()
    has_tokenizer = (
        (path / "tokenizer.json").exists()
        or (path / "tokenizer_config.json").exists()
    )
    has_weights = (
        any(path.glob("*.safetensors"))
        or any(path.glob("*.bin"))
    )

    return has_config and has_tokenizer and has_weights


def _check_direct_llm_model() -> bool:
    """Check whether the proprietary local generation model files exist."""

    try:
        return bool(direct_model_files_available())
    except Exception as exc:
        logger.error(
            "[diagnostics] Direct LLM model check failed: %s",
            exc,
        )
        return False


def _check_embedding_model() -> bool:
    """Check whether the configured local embedding model files exist."""

    try:
        return _model_files_available(
            settings.WORKSPACE_ACTION_SELECTOR_MODEL_PATH
        )
    except Exception as exc:
        logger.error(
            "[diagnostics] Embedding model check failed: %s",
            exc,
        )
        return False


def _check_database() -> bool:
    """Run a mechanical database connectivity probe."""

    db = None

    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error(
            "[diagnostics] Database check failed: %s",
            exc,
        )
        return False
    finally:
        if db is not None:
            try:
                db.close()
            except Exception:
                logger.debug(
                    "[diagnostics] Database session close failed.",
                    exc_info=True,
                )


def _check_faiss() -> bool:
    """Ensure the FAISS index exists and is readable."""

    try:
        index = ensure_faiss_index()
        return index is not None
    except Exception as exc:
        logger.error(
            "[diagnostics] FAISS check failed: %s",
            exc,
        )
        return False


def _check_uploads() -> bool:
    """Validate the configured uploads directory."""

    return os.path.isdir(settings.UPLOADS_DIR)


# ---------------------------------------------------------------------------
# Structural Awareness Checks
# ---------------------------------------------------------------------------

def _module_exists(module_path: str) -> bool:
    """Check whether a module exists without importing it."""

    try:
        spec = importlib.util.find_spec(module_path)
        return spec is not None
    except Exception:
        return False


def _check_packet_router_present() -> bool:
    """Detect the orchestrator or packet-router module surface."""

    return _module_exists("solomon_core.solomon_core")


def _check_packet_header_present() -> bool:
    """Detect the PacketHeader definition surface."""

    return _module_exists("solomon_core.packet.packet_header")


def _check_docintel_present() -> bool:
    """Detect the DocIntel skill domain."""

    return _module_exists("solomon_core.skills.semantic")


def _check_ml_hud_present() -> bool:
    """Detect the ML HUD advisory layer."""

    return _module_exists("solomon_core.hud")


# ---------------------------------------------------------------------------
# Diagnostics Entrypoint
# ---------------------------------------------------------------------------

def run(arguments=None):
    """Return raw system diagnostic signals only."""

    del arguments

    try:
        cpu_percent = psutil.cpu_percent(interval=0.3)
        memory_percent = psutil.virtual_memory().percent
        disk_percent = psutil.disk_usage("/").percent

        signals = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,
            "gpu_present": None,
            "direct_llm_model_present": (
                _check_direct_llm_model()
            ),
            "embedding_model_present": (
                _check_embedding_model()
            ),
            "database_reachable": _check_database(),
            "faiss_index_present": _check_faiss(),
            "uploads_dir_present": _check_uploads(),
            "packet_router_present": (
                _check_packet_router_present()
            ),
            "packet_header_present": (
                _check_packet_header_present()
            ),
            "docintel_present": _check_docintel_present(),
            "ml_hud_present": _check_ml_hud_present(),
            "error_sentinel_present": True,
        }

        return {
            "ok": True,
            "signals": signals,
        }

    except Exception as exc:
        logger.exception(
            "System diagnostics failure"
        )

        return {
            "ok": False,
            "signals": {},
            "error": str(exc),
        }
