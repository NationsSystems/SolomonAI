# ---------------------------------------------------------------------------
# FILE: llm_transport.py
# DIRECTORY: solomon_core/llm/
# ---------------------------------------------------------------------------
# LLM Runtime Transport Configuration
#
# PURPOSE
#   Centralize SIS transport selection, proprietary local-model runtime controls,
#   and proof metadata.
#
# CONTRACT
#   - Normal application callers use the separately running Solomon Intelligence
#     Service when SIS is enabled.
#   - Only SIS owns heavy direct Transformers/Torch execution in that mode.
#   - Local direct execution remains an explicit compatibility path when SIS is
#     disabled.
#   - This module does not load models or perform generation.
# ---------------------------------------------------------------------------

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

from config import settings


# ---------------------------------------------------------------------------
# Coercion Helpers
# ---------------------------------------------------------------------------

def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {"1", "true", "yes", "y", "on", "enabled"}:
            return True

        if normalized in {"0", "false", "no", "n", "off", "disabled"}:
            return False

    if value is None:
        return default

    return bool(value)


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _coerce_path_candidates(value: Any) -> list[Path]:
    if value is None:
        return []

    if isinstance(value, (str, Path)):
        return [Path(value)]

    if isinstance(value, Iterable):
        paths: list[Path] = []

        for item in value:
            if isinstance(item, (str, Path)) and str(item).strip():
                paths.append(Path(item))

        return paths

    return []


def _normalize_attention_implementation(value: Any) -> str:
    clean_value = str(value or "sdpa").strip().lower()

    if clean_value in {"", "auto", "default"}:
        return "sdpa"

    if clean_value in {"none", "off", "false", "disabled"}:
        return ""

    if clean_value in {
        "sdpa",
        "flash_attention_2",
        "flash-attention-2",
        "eager",
    }:
        if clean_value == "flash-attention-2":
            return "flash_attention_2"

        return clean_value

    return clean_value


def _normalize_compile_mode(value: Any) -> str:
    clean_value = str(value or "reduce-overhead").strip()
    return clean_value or "reduce-overhead"


# ---------------------------------------------------------------------------
# Solomon Intelligence Service Transport Controls
# ---------------------------------------------------------------------------

SIS_ENABLED = _coerce_bool(
    getattr(settings, "SIS_ENABLED", True),
    default=True,
)
SIS_BASE_URL = str(
    getattr(settings, "SIS_BASE_URL", "http://127.0.0.1:8091")
).strip().rstrip("/")


# ---------------------------------------------------------------------------
# Proprietary Direct Runtime Controls
# ---------------------------------------------------------------------------

LLM_DIRECT_MODEL_ENABLED = _coerce_bool(
    getattr(settings, "LLM_DIRECT_MODEL_ENABLED", True),
    default=True,
)

LLM_BACKEND = (
    "transformers_direct"
    if LLM_DIRECT_MODEL_ENABLED
    else "disabled"
)

# A first-time installation selects its model explicitly through the launcher.
# Never embed any developer-specific filesystem paths in the public source.
_RELEASE_ROOT = Path(__file__).resolve().parents[2]
_RELEASE_MODEL_DEFAULT = _RELEASE_ROOT / "models" / "generation"

LLM_DIRECT_MODEL_NAME = (
    os.environ.get("SOLOMONAI_LOCAL_MODEL_NAME", "").strip()
    or str(getattr(settings, "LLM_DIRECT_MODEL_NAME", "solomon_custom_llm_v1")).strip()
    or "solomon_custom_llm_v1"
)

LLM_DIRECT_MODEL_PATH_CANDIDATES = _coerce_path_candidates(
    getattr(settings, "LLM_DIRECT_MODEL_PATH_CANDIDATES", None)
) or [_RELEASE_MODEL_DEFAULT]

LLM_DIRECT_DEVICE = str(
    getattr(settings, "LLM_DIRECT_DEVICE", "auto")
).strip() or "auto"

LLM_DIRECT_DTYPE = str(
    getattr(settings, "LLM_DIRECT_DTYPE", "auto")
).strip() or "auto"

LLM_DIRECT_TRUST_REMOTE_CODE = _coerce_bool(
    getattr(settings, "LLM_DIRECT_TRUST_REMOTE_CODE", False),
    default=False,
)

LLM_DIRECT_PROOF_LOGGING = _coerce_bool(
    getattr(settings, "LLM_DIRECT_PROOF_LOGGING", True),
    default=True,
)

LLM_DIRECT_REQUIRE_LOCAL_FILES = _coerce_bool(
    getattr(settings, "LLM_DIRECT_REQUIRE_LOCAL_FILES", True),
    default=True,
)

LLM_DIRECT_ATTN_IMPLEMENTATION = _normalize_attention_implementation(
    getattr(settings, "LLM_DIRECT_ATTN_IMPLEMENTATION", "sdpa")
)

LLM_DIRECT_ENABLE_TORCH_COMPILE = _coerce_bool(
    getattr(settings, "LLM_DIRECT_ENABLE_TORCH_COMPILE", False),
    default=False,
)

LLM_DIRECT_TORCH_COMPILE_MODE = _normalize_compile_mode(
    getattr(settings, "LLM_DIRECT_TORCH_COMPILE_MODE", "reduce-overhead")
)

MAX_LLM_INPUT_CHARS = max(
    1,
    _coerce_int(
        getattr(settings, "LLM_MAX_INPUT_CHARS", 12000),
        12000,
    ),
)

LLM_TEMPERATURE = max(
    0.0,
    float(getattr(settings, "LLM_TEMPERATURE", 0.2)),
)


# ---------------------------------------------------------------------------
# Call-Site Generation Budgets
# ---------------------------------------------------------------------------

LLM_DIRECT_VISUAL_CONDUCTOR_MAX_NEW_TOKENS = max(
    8,
    _coerce_int(
        getattr(
            settings,
            "LLM_DIRECT_VISUAL_CONDUCTOR_MAX_NEW_TOKENS",
            24,
        ),
        24,
    ),
)

LLM_DIRECT_HOME_MAX_NEW_TOKENS = max(
    24,
    _coerce_int(
        getattr(settings, "LLM_DIRECT_HOME_MAX_NEW_TOKENS", 72),
        72,
    ),
)

LLM_DIRECT_HOME_JSON_MAX_NEW_TOKENS = max(
    32,
    _coerce_int(
        getattr(
            settings,
            "LLM_DIRECT_HOME_JSON_MAX_NEW_TOKENS",
            LLM_DIRECT_HOME_MAX_NEW_TOKENS,
        ),
        LLM_DIRECT_HOME_MAX_NEW_TOKENS,
    ),
)

LLM_DIRECT_HOME_ANSWER_MAX_NEW_TOKENS = max(
    12,
    _coerce_int(
        getattr(
            settings,
            "LLM_DIRECT_HOME_ANSWER_MAX_NEW_TOKENS",
            28,
        ),
        28,
    ),
)

LLM_DIRECT_BEI_MAX_NEW_TOKENS = max(
    64,
    _coerce_int(
        getattr(
            settings,
            "LLM_DIRECT_BEI_MAX_NEW_TOKENS",
            getattr(settings, "LLM_MAX_OUTPUT_TOKENS", 900),
        ),
        900,
    ),
)

LLM_DIRECT_ASSISTANT_MAX_NEW_TOKENS = max(
    64,
    _coerce_int(
        getattr(settings, "LLM_DIRECT_ASSISTANT_MAX_NEW_TOKENS", 420),
        420,
    ),
)

LLM_DIRECT_DOCINTEL_MAX_NEW_TOKENS = max(
    256,
    _coerce_int(
        getattr(
            settings,
            "LLM_DIRECT_DOCINTEL_MAX_NEW_TOKENS",
            640,
        ),
        640,
    ),
)


# ---------------------------------------------------------------------------
# Model Path and Availability
# ---------------------------------------------------------------------------

def resolve_direct_model_path() -> Path:
    # This explicit launch-time selection takes precedence over the imported
    # configuration's historical model-path defaults. The launcher supplies
    # this only after validating the chosen local model directory.
    selected = os.environ.get("SOLOMONAI_LOCAL_MODEL_DIR", "").strip()
    if selected:
        return Path(selected).expanduser()

    configured = getattr(settings, "LLM_DIRECT_MODEL_PATH", None)

    if isinstance(configured, (str, Path)) and str(configured).strip():
        return Path(configured)

    for candidate in LLM_DIRECT_MODEL_PATH_CANDIDATES:
        if candidate.exists():
            return candidate

    return LLM_DIRECT_MODEL_PATH_CANDIDATES[0]


LLM_DIRECT_MODEL_PATH = resolve_direct_model_path()


def direct_model_files_available(path: str | Path | None = None) -> bool:
    model_path = Path(path) if path else LLM_DIRECT_MODEL_PATH

    if not model_path.exists() or not model_path.is_dir():
        return False

    has_config = (model_path / "config.json").exists()
    has_tokenizer = (
        (model_path / "tokenizer.json").exists()
        or (model_path / "tokenizer_config.json").exists()
    )
    has_weights = (
        any(model_path.glob("*.safetensors"))
        or any(model_path.glob("*.bin"))
    )

    return has_config and has_tokenizer and has_weights


# ---------------------------------------------------------------------------
# Direct Runtime Resolution
# ---------------------------------------------------------------------------

def select_backend() -> str:
    if SIS_ENABLED:
        return "sis"

    return select_local_runtime_backend()


def select_local_runtime_backend() -> str:
    """Return the backend owned by the current heavy-compute process."""

    if LLM_DIRECT_MODEL_ENABLED:
        return "transformers_direct"

    return "disabled"


def select_model_name() -> str:
    return LLM_DIRECT_MODEL_NAME


def select_timeout_seconds() -> int:
    return _coerce_int(
        getattr(settings, "LLM_TIMEOUT_SECONDS", None)
        or getattr(settings, "EXECUTION_TIMEOUT_SECONDS", None)
        or 60,
        60,
    )


def select_max_new_tokens(call_site: str | None = None) -> int:
    normalized = str(call_site or "").strip().lower()

    if normalized == "solomon_visual_conductor":
        return LLM_DIRECT_VISUAL_CONDUCTOR_MAX_NEW_TOKENS

    if normalized == "solomon_home_answer_assistant":
        return LLM_DIRECT_HOME_ANSWER_MAX_NEW_TOKENS

    if normalized == "solomon_home_assistant":
        return LLM_DIRECT_HOME_JSON_MAX_NEW_TOKENS

    if "assistant" in normalized:
        return LLM_DIRECT_ASSISTANT_MAX_NEW_TOKENS

    if (
        "docintel" in normalized
        or "informational_only" in normalized
    ):
        return LLM_DIRECT_DOCINTEL_MAX_NEW_TOKENS

    if "bei" in normalized or "report" in normalized:
        return LLM_DIRECT_BEI_MAX_NEW_TOKENS

    return _coerce_int(
        getattr(settings, "LLM_MAX_OUTPUT_TOKENS", 900),
        900,
    )


def build_transport_proof(
    call_site: str,
    *,
    local_runtime: bool = False,
) -> dict[str, Any]:
    selected_backend = (
        select_local_runtime_backend()
        if local_runtime
        else select_backend()
    )

    return {
        "call_site": str(call_site or "unknown"),
        "llm_backend": selected_backend,
        "model_source": (
            "merged_model_folder"
            if selected_backend == "transformers_direct"
            else "solomon_intelligence_service"
            if selected_backend == "sis"
            else "unavailable"
        ),
        "sis_base_url": SIS_BASE_URL if selected_backend == "sis" else "",
        "model_name": select_model_name(),
        "model_path": (
            str(LLM_DIRECT_MODEL_PATH)
            if selected_backend == "transformers_direct"
            else ""
        ),
        "direct_model_available": direct_model_files_available(),
        "direct_attention_implementation": (
            LLM_DIRECT_ATTN_IMPLEMENTATION or "default"
        ),
        "direct_torch_compile_enabled": (
            LLM_DIRECT_ENABLE_TORCH_COMPILE
        ),
        "direct_torch_compile_mode": (
            LLM_DIRECT_TORCH_COMPILE_MODE
        ),
        "home_answer_max_new_tokens": (
            LLM_DIRECT_HOME_ANSWER_MAX_NEW_TOKENS
        ),
        "home_max_new_tokens": (
            LLM_DIRECT_HOME_JSON_MAX_NEW_TOKENS
        ),
        "assistant_max_new_tokens": (
            LLM_DIRECT_ASSISTANT_MAX_NEW_TOKENS
        ),
        "docintel_max_new_tokens": (
            LLM_DIRECT_DOCINTEL_MAX_NEW_TOKENS
        ),
        "bei_max_new_tokens": (
            LLM_DIRECT_BEI_MAX_NEW_TOKENS
        ),
    }