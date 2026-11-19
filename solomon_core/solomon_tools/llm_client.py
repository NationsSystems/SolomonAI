# ---------------------------------------------------------------------------
# FILE: llm_client.py
# DIRECTORY: solomon_core/solomon_tools/
# ---------------------------------------------------------------------------
# Governed Signal-Only LLM Compatibility Surface
#
# PURPOSE:
#   Preserve legacy signal-only helper interfaces without granting execution
#   authority or invoking any model runtime directly.
#
# AUTHORITY CONTRACT:
#   - This module has no task or execution authority.
#   - The Orchestrator must authorize all LLM execution.
#   - Production generation uses Solomon's proprietary direct
#     Transformers/Torch runtime through the canonical LLM executor.
# ---------------------------------------------------------------------------

from __future__ import annotations

import json
import logging
import os

from config import settings

logger = logging.getLogger("llm_client")


# ---------------------------------------------------------------------------
# Authority Declarations
# ---------------------------------------------------------------------------

EXECUTION_AUTHORITY = False
SIGNAL_ONLY_MODULE = True
AUTHORITY_SCOPE = "signal_only"


# ---------------------------------------------------------------------------
# Canonical Local Model Identity
# ---------------------------------------------------------------------------

DEFAULT_MODEL = settings.LLM_MODEL_NAME

EMBED_MODEL = settings.WORKSPACE_ACTION_SELECTOR_MODEL_NAME

CACHE_DIR = os.path.join(
    settings.RUNTIME_DIR,
    "llm_cache",
)
os.makedirs(
    CACHE_DIR,
    exist_ok=True,
)


# ---------------------------------------------------------------------------
# Output Sanitizer
# ---------------------------------------------------------------------------

_META_PATTERNS = [
    r"\bi used\b",
    r"\bi analyzed\b",
    r"\bmachine learning\b",
    r"\bnatural language\b",
    r"\bmy training\b",
    r"\bas an ai\b",
    r"\bi leveraged\b",
    r"\bthis response was generated\b",
]


def _sanitize_output(text: str) -> str:
    return text if isinstance(text, str) else ""


# ---------------------------------------------------------------------------
# Embeddings Compatibility Surface
# ---------------------------------------------------------------------------

def embed_text(text: str) -> list[float]:
    """
    Return the existing deterministic signal-only placeholder vector.

    This compatibility helper does not load or invoke the embedding model.
    """

    del text
    return [0.0] * 768


# ---------------------------------------------------------------------------
# LLM Compatibility Wrappers
# ---------------------------------------------------------------------------

def query_llm(*args, **kwargs) -> str:
    """
    Preserve the legacy signal-only interface without executing a model.
    """

    del args, kwargs

    logger.info(
        "[llm_client] query_llm called; execution remains "
        "deferred to the governed Orchestrator path."
    )

    return "[Signal-only compatibility: execution deferred]"


def orchestrator_task_prompt(*args, **kwargs) -> str:
    del args, kwargs
    return "[Signal-only compatibility: orchestrator authority required]"


def query_planner_llm(*args, **kwargs) -> str:
    del args, kwargs

    return json.dumps(
        {
            "ok": True,
            "reason": "Signal-only compatibility placeholder",
        }
    )


def explain_task_concept(*args, **kwargs) -> str:
    del args, kwargs
    return "[Signal-only compatibility]"


def summarize_text(*args, **kwargs) -> str:
    del args, kwargs
    return "[Signal-only compatibility]"


def query_reasoning_llm(*args, **kwargs) -> dict[str, object]:
    del args, kwargs

    return {
        "ok": True,
        "text": "[Signal-only compatibility]",
        "raw": "[Signal-only compatibility]",
    }
