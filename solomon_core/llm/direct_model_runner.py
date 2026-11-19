# ---------------------------------------------------------------------------
# FILE: direct_model_runner.py
# DIRECTORY: solomon_core/llm/
# ---------------------------------------------------------------------------
# Direct Custom Model Runner
#
# PURPOSE
#   Execute local merged-model generation through Python/Transformers without
#   adapter sidecars or external model runtime services.
#
# CONTRACT
#   - Loads the configured merged model folder lazily.
#   - Reuses the loaded model for subsequent requests.
#   - Does not route, classify, decide workflow, or interpret BEI facts.
#   - Returns generated text plus backend proof metadata.
#
# SPEED CONTRACT
#   - Visual conductor calls use an ultra-short deterministic sequence profile.
#   - Home assistant calls use a short deterministic guidance profile.
#   - Workspace source-operation calls use caller-governed deterministic response profiles.
#   - Assistant calls use a fast deterministic generation profile.
#   - SolomonAI assistant JSON carries the substantive answer only.
#   - SolomonAI response synthesis uses a deterministic bounded continuation profile.
#   - Ordinary DocIntel calls use a bounded deterministic summary profile.
#   - DocIntel summary narration uses a caller-governed static-cache profile.
#   - BEI report-writing calls use a bounded deterministic polish profile.
#   - Other calls keep the general generation profile.
#   - Live Home JSON uses compact keys plus balanced JSON stopping to avoid
#     wasting decode time.
#   - Static cache is portable for approved source-operation and DocIntel call sites.
#   - Prompt lookup remains isolated to a dedicated DocIntel benchmark call site.
#   - Torch compilation remains isolated to benchmark call sites only.
#   - Boot warmup loads and primes only the shared model before user traffic.
# ---------------------------------------------------------------------------

from __future__ import annotations

import importlib.util
import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

from config import settings
from solomon_core.logger import get_logger

from .llm_transport import (
    LLM_DIRECT_ASSISTANT_MAX_NEW_TOKENS,
    LLM_DIRECT_ATTN_IMPLEMENTATION,
    LLM_DIRECT_BEI_MAX_NEW_TOKENS,
    LLM_DIRECT_DEVICE,
    LLM_DIRECT_DOCINTEL_MAX_NEW_TOKENS,
    LLM_DIRECT_DTYPE,
    LLM_DIRECT_ENABLE_TORCH_COMPILE,
    LLM_DIRECT_HOME_JSON_MAX_NEW_TOKENS,
    LLM_DIRECT_HOME_MAX_NEW_TOKENS,
    LLM_DIRECT_MODEL_NAME,
    LLM_DIRECT_MODEL_PATH,
    LLM_DIRECT_REQUIRE_LOCAL_FILES,
    LLM_DIRECT_TORCH_COMPILE_MODE,
    LLM_DIRECT_TRUST_REMOTE_CODE,
    LLM_DIRECT_VISUAL_CONDUCTOR_MAX_NEW_TOKENS,
    LLM_TEMPERATURE,
    MAX_LLM_INPUT_CHARS,
    build_transport_proof,
    select_max_new_tokens,
)

logger = get_logger("direct_model_runner")

LLM_DIRECT_DEFAULT_TOP_P = float(
    getattr(
        settings,
        "LLM_DIRECT_TOP_P",
        0.92,
    )
)
LLM_DIRECT_DEFAULT_REPEAT_PENALTY = float(
    getattr(
        settings,
        "LLM_DIRECT_REPEAT_PENALTY",
        1.12,
    )
)

_MODEL: Any = None
_TOKENIZER: Any = None
_MODEL_PATH_KEY = ""
_MODEL_LOCK = threading.Lock()
_PRIME_LOCK = threading.Lock()
_RUNTIME_PRIME_LOCK = threading.Lock()
_COMPILE_LOCK = threading.Lock()
_COMPILED_FORWARD_CACHE: dict[str, Any] = {}
_COMPILE_ATTEMPTED_CALL_SITES: set[str] = set()
_PRIMED_MODEL_PATH_KEY = ""
_PRIMED_RUNTIME_PROFILE_SHAPES: dict[
    str,
    set[tuple[int, int, bool]],
] = {}

_RUNTIME_PROFILE_DEFAULT = "default"
_RUNTIME_PROFILE_STATIC_CACHE = "static_cache"
_RUNTIME_PROFILE_STATIC_CACHE_COMPILE = "static_cache_compile"
_RUNTIME_PROFILES = frozenset(
    {
        _RUNTIME_PROFILE_DEFAULT,
        _RUNTIME_PROFILE_STATIC_CACHE,
        _RUNTIME_PROFILE_STATIC_CACHE_COMPILE,
    }
)
_WORKSPACE_SOURCE_RUNTIME_BENCHMARK_CALL_SITE = (
    "workspace_solomon_source_operation_runtime_benchmark"
)
_DOCINTEL_PROMPT_LOOKUP_BENCHMARK_CALL_SITE = (
    "solomon_docintel_prompt_lookup_benchmark"
)
_DOCINTEL_SUMMARY_NARRATION_CALL_SITE = "docintel_summary_narration"
_DOCINTEL_SUMMARY_NARRATION_MAX_NEW_TOKENS = 480
_PROMPT_LOOKUP_BENCHMARK_NUM_TOKENS = 3

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.I | re.S)
_THINK_OPEN_RE = re.compile(r"<think>.*$", re.I | re.S)

_STATIC_COMPILE_BENCHMARK_CALL_SITES = frozenset(
    {
        "solomon_home_static_compile_benchmark",
        "solomon_static_compile_benchmark",
        "bei_report_static_compile_benchmark",
    }
)

_WORKSPACE_SOURCE_OPERATION_CALL_SITES = frozenset(
    {
        "workspace_solomon_source_operation",
        _WORKSPACE_SOURCE_RUNTIME_BENCHMARK_CALL_SITE,
    }
)

_DOCINTEL_CALL_SITES = frozenset(
    {
        "llm_executor:informational_only",
        _DOCINTEL_PROMPT_LOOKUP_BENCHMARK_CALL_SITE,
    }
)

_WORKSPACE_SOURCE_OPERATION_DEFAULT_MAX_NEW_TOKENS = (
    LLM_DIRECT_DOCINTEL_MAX_NEW_TOKENS
)
_BOOT_WARMUP_PROMPT = "Respond with one word: ready."
_BOOT_WARMUP_MAX_NEW_TOKENS = 1
_HOME_JSON_RUNTIME_MAX_NEW_TOKENS = 48
_HOME_JSON_PREFILL = "{"
_HOME_JSON_COMPLETION_INSTRUCTION = (
    'Complete compact JSON after the opening brace only: '
    '"a":"answer","b":"bridge","s":["chip","chip","chip"]}. No extra text.'
)

_SOLOMON_ASSISTANT_CALL_SITE = "solomon_assistant"
_SOLOMON_ASSISTANT_JSON_PREFILL = "{"
_SOLOMON_ASSISTANT_JSON_COMPLETION_INSTRUCTION = (
    'The opening brace is already supplied. Continue immediately with exactly '
    'one complete object using only the key a: "a":"complete answer"}. '
    'The answer must follow the caller prompt exactly. Do not generate bridge '
    'text, suggestions, UI actions, or continuation language. Do not invent '
    'facts, quantities, project details, or source content that the prompt does '
    'not provide. Do not repeat the opening brace, add markdown, or write text '
    'after the closing brace.'
)

_SOLOMON_AI_RESPONSE_SYNTHESIS_CALL_SITE = (
    "solomon_ai_response_synthesis"
)
_SOLOMON_AI_RESPONSE_SYNTHESIS_MAX_NEW_TOKENS = 80
_SOLOMON_AI_RESPONSE_SYNTHESIS_JSON_PREFILL = "{"
_SOLOMON_AI_RESPONSE_SYNTHESIS_COMPLETION_INSTRUCTION = (
    'Complete JSON after the opening brace only using the keys bridge and '
    'suggestions in that order. Follow the caller prompt for whether bridge is '
    'empty and for a suggestion count between one and three. Do not add facts '
    'or extra fields, repeat the opening brace, add markdown, or write text '
    'after the closing brace.'
)


@dataclass(frozen=True)
class DirectModelResult:
    ok: bool
    text: str
    proof: dict[str, Any]
    error: str = ""
    metrics: dict[str, Any] | None = None


def _import_runtime() -> tuple[Any, Any, Any]:
    try:
        import torch
    except Exception as exc:
        raise RuntimeError(
            "PyTorch failed to initialize for the direct model runtime: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:
        raise RuntimeError(
            "Transformers failed to initialize for the direct model runtime: "
            f"{type(exc).__name__}: {exc}"
        ) from exc

    return torch, AutoModelForCausalLM, AutoTokenizer


def _elapsed_ms(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000


def _resolve_torch_dtype(torch: Any) -> Any:
    dtype = str(LLM_DIRECT_DTYPE or "auto").strip().lower()

    if dtype in {"", "auto"}:
        return "auto"

    if dtype in {"float16", "fp16"}:
        return torch.float16

    if dtype in {"bfloat16", "bf16"}:
        return torch.bfloat16

    if dtype in {"float32", "fp32"}:
        return torch.float32

    return "auto"


def _select_device(torch: Any) -> str:
    requested = str(LLM_DIRECT_DEVICE or "auto").strip().lower()

    if requested == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"

    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError(
            "Direct model device was set to CUDA, but CUDA is unavailable."
        )

    if requested in {"cuda", "cpu"}:
        return requested

    return "cuda" if torch.cuda.is_available() else "cpu"


def _enable_runtime_speed_flags(torch: Any) -> None:
    try:
        if hasattr(torch, "set_float32_matmul_precision"):
            torch.set_float32_matmul_precision("high")

        if (
            hasattr(torch.backends, "cuda")
            and hasattr(torch.backends.cuda, "matmul")
        ):
            torch.backends.cuda.matmul.allow_tf32 = True

        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.allow_tf32 = True
            torch.backends.cudnn.benchmark = True
    except Exception:
        logger.debug("[LLM_DIRECT][SPEED_FLAGS_SKIPPED]")


def _enable_dynamo_safety(torch: Any) -> None:
    try:
        dynamo = getattr(torch, "_dynamo", None)
        config = getattr(dynamo, "config", None)

        if config is not None and hasattr(config, "suppress_errors"):
            config.suppress_errors = True
    except Exception:
        logger.debug("[LLM_DIRECT][DYNAMO_SAFETY_SKIPPED]")


def _triton_available() -> bool:
    return importlib.util.find_spec("triton") is not None


def _requested_attention_implementation() -> str:
    clean_value = str(
        LLM_DIRECT_ATTN_IMPLEMENTATION or ""
    ).strip().lower()

    if clean_value in {
        "",
        "auto",
        "none",
        "default",
        "off",
        "false",
    }:
        return ""

    return clean_value


def _supports_modern_dtype_kwarg() -> bool:
    try:
        import transformers

        version_text = str(
            getattr(
                transformers,
                "__version__",
                "",
            )
        ).strip()
        major_text = version_text.split(
            ".",
            1,
        )[0]

        return int(major_text) >= 5
    except Exception:
        return False


def _build_model_load_kwargs(torch: Any) -> dict[str, Any]:
    resolved_dtype = _resolve_torch_dtype(torch)
    dtype_key = (
        "dtype"
        if _supports_modern_dtype_kwarg()
        else "torch_dtype"
    )

    load_kwargs = {
        dtype_key: resolved_dtype,
        "local_files_only": LLM_DIRECT_REQUIRE_LOCAL_FILES,
        "trust_remote_code": LLM_DIRECT_TRUST_REMOTE_CODE,
        "low_cpu_mem_usage": True,
    }
    attention_implementation = (
        _requested_attention_implementation()
    )

    if attention_implementation:
        load_kwargs["attn_implementation"] = (
            attention_implementation
        )

    return load_kwargs


def _load_model_from_pretrained(
    *,
    auto_model: Any,
    model_path: Path,
    load_kwargs: dict[str, Any],
) -> Any:
    try:
        return auto_model.from_pretrained(
            str(model_path),
            **load_kwargs,
        )
    except TypeError as exc:
        if "dtype" not in load_kwargs:
            raise

        fallback_kwargs = dict(load_kwargs)
        fallback_kwargs["torch_dtype"] = (
            fallback_kwargs.pop("dtype")
        )

        logger.warning(
            "[LLM_DIRECT][DTYPE_FALLBACK] reason=%s",
            exc,
        )

        return auto_model.from_pretrained(
            str(model_path),
            **fallback_kwargs,
        )


def _load_model_with_attention_fallback(
    *,
    auto_model: Any,
    model_path: Path,
    load_kwargs: dict[str, Any],
) -> Any:
    try:
        return _load_model_from_pretrained(
            auto_model=auto_model,
            model_path=model_path,
            load_kwargs=load_kwargs,
        )
    except Exception as exc:
        attention_implementation = load_kwargs.get(
            "attn_implementation"
        )

        if not attention_implementation:
            raise

        clean_message = str(exc).lower()
        attention_related = (
            "attn" in clean_message
            or "attention" in clean_message
            or "sdpa" in clean_message
            or "flash" in clean_message
        )

        if not attention_related:
            raise

        fallback_kwargs = dict(load_kwargs)
        fallback_kwargs.pop(
            "attn_implementation",
            None,
        )

        logger.warning(
            "[LLM_DIRECT][ATTN_FALLBACK] requested=%s reason=%s",
            attention_implementation,
            exc,
        )

        return _load_model_from_pretrained(
            auto_model=auto_model,
            model_path=model_path,
            load_kwargs=fallback_kwargs,
        )


def _is_static_compile_benchmark_call(
    call_site: str,
) -> bool:
    return (
        _normalized_call_site(call_site)
        in _STATIC_COMPILE_BENCHMARK_CALL_SITES
    )


def _is_workspace_source_runtime_benchmark_call(
    call_site: str,
) -> bool:
    return (
        _normalized_call_site(call_site)
        == _WORKSPACE_SOURCE_RUNTIME_BENCHMARK_CALL_SITE
    )


def _runtime_profile_allowed_for_call_site(
    call_site: str,
    runtime_profile: str,
) -> bool:
    if runtime_profile == _RUNTIME_PROFILE_DEFAULT:
        return True

    if runtime_profile == _RUNTIME_PROFILE_STATIC_CACHE:
        return (
            _is_workspace_source_operation_call(call_site)
            or _is_docintel_call(call_site)
        )

    if (
        runtime_profile
        == _RUNTIME_PROFILE_STATIC_CACHE_COMPILE
    ):
        return _is_workspace_source_runtime_benchmark_call(
            call_site
        )

    return False


def _compile_allowed_for_call_site(
    call_site: str,
    runtime_profile: str,
) -> bool:
    if (
        runtime_profile
        == _RUNTIME_PROFILE_STATIC_CACHE_COMPILE
    ):
        return _is_workspace_source_runtime_benchmark_call(
            call_site
        )

    if not LLM_DIRECT_ENABLE_TORCH_COMPILE:
        return False

    return _is_static_compile_benchmark_call(
        call_site
    )


def _static_cache_allowed_for_call_site(
    call_site: str,
    runtime_profile: str,
) -> bool:
    if runtime_profile == _RUNTIME_PROFILE_STATIC_CACHE:
        permitted = (
            _is_workspace_source_operation_call(call_site)
            or _is_docintel_call(call_site)
        )
        # On Windows, Transformers may internally compile StaticCache
        # generation even when explicit torch.compile is disabled.
        # Preserve local CUDA inference without requiring Triton.
        if permitted and not _triton_available():
            logger.warning(
                "[LLM_DIRECT][STATIC_CACHE_SKIPPED] "
                "call_site=%s reason=triton_unavailable "
                "fallback=dynamic_cache",
                call_site,
            )
            return False
        return permitted

    if (
        runtime_profile
        == _RUNTIME_PROFILE_STATIC_CACHE_COMPILE
    ):
        return _is_workspace_source_runtime_benchmark_call(
            call_site
        )

    return _compile_allowed_for_call_site(
        call_site,
        runtime_profile,
    )


def _maybe_install_compiled_forward_for_call(
    *,
    torch: Any,
    model: Any,
    device: str,
    call_site: str,
    runtime_profile: str,
) -> tuple[bool, Any | None]:
    normalized = _normalized_call_site(
        call_site
    )
    compile_cache_key = (
        f"{normalized}:{runtime_profile}"
    )

    if not _compile_allowed_for_call_site(
        call_site,
        runtime_profile,
    ):
        return False, None

    if device != "cuda":
        logger.warning(
            "[LLM_DIRECT][COMPILE_SKIPPED] "
            "reason=non_cuda_device device=%s call_site=%s",
            device,
            call_site,
        )
        return False, None

    if not hasattr(torch, "compile"):
        logger.warning(
            "[LLM_DIRECT][COMPILE_SKIPPED] "
            "reason=torch_compile_unavailable call_site=%s",
            call_site,
        )
        return False, None

    if not _triton_available():
        logger.warning(
            "[LLM_DIRECT][COMPILE_SKIPPED] "
            "reason=triton_unavailable call_site=%s",
            call_site,
        )
        return False, None

    with _COMPILE_LOCK:
        original_forward = model.forward
        compiled_forward = (
            _COMPILED_FORWARD_CACHE.get(
                compile_cache_key
            )
        )

        if compiled_forward is not None:
            model.forward = compiled_forward
            logger.info(
                "[LLM_DIRECT][COMPILE_REUSED] "
                "target=forward mode=%s call_site=%s",
                LLM_DIRECT_TORCH_COMPILE_MODE,
                call_site,
            )
            return True, original_forward

        if (
            compile_cache_key
            in _COMPILE_ATTEMPTED_CALL_SITES
        ):
            return False, None

        _COMPILE_ATTEMPTED_CALL_SITES.add(
            compile_cache_key
        )

        try:
            _enable_dynamo_safety(torch)
            compiled_forward = torch.compile(
                original_forward,
                mode=LLM_DIRECT_TORCH_COMPILE_MODE,
            )
            _COMPILED_FORWARD_CACHE[
                compile_cache_key
            ] = compiled_forward
            model.forward = compiled_forward

            logger.info(
                "[LLM_DIRECT][COMPILE_OK] "
                "target=forward mode=%s call_site=%s "
                "strategy=static_cache_benchmark",
                LLM_DIRECT_TORCH_COMPILE_MODE,
                call_site,
            )

            return True, original_forward
        except Exception as exc:
            logger.warning(
                "[LLM_DIRECT][COMPILE_SKIPPED] "
                "call_site=%s reason=%s",
                call_site,
                exc,
            )
            return False, None


def _restore_forward_if_needed(
    *,
    model: Any,
    original_forward: Any | None,
    call_site: str,
) -> None:
    if original_forward is None:
        return

    try:
        model.forward = original_forward
        logger.info(
            "[LLM_DIRECT][COMPILE_RESTORED] "
            "call_site=%s target=forward",
            call_site,
        )
    except Exception:
        logger.warning(
            "[LLM_DIRECT][COMPILE_RESTORE_FAILED] "
            "call_site=%s",
            call_site,
        )


def _model_files_available(
    model_path: Path,
) -> bool:
    if (
        not model_path.exists()
        or not model_path.is_dir()
    ):
        return False

    has_config = (
        model_path
        / "config.json"
    ).exists()
    has_tokenizer = (
        (
            model_path
            / "tokenizer.json"
        ).exists()
        or (
            model_path
            / "tokenizer_config.json"
        ).exists()
    )
    has_weights = (
        any(
            model_path.glob(
                "*.safetensors"
            )
        )
        or any(
            model_path.glob(
                "*.bin"
            )
        )
    )

    return (
        has_config
        and has_tokenizer
        and has_weights
    )


def _load_model() -> tuple[Any, Any, str]:
    global _MODEL
    global _TOKENIZER
    global _MODEL_PATH_KEY
    global _COMPILED_FORWARD_CACHE
    global _COMPILE_ATTEMPTED_CALL_SITES
    global _PRIMED_MODEL_PATH_KEY
    global _PRIMED_RUNTIME_PROFILE_SHAPES

    torch, auto_model, auto_tokenizer = (
        _import_runtime()
    )
    _enable_runtime_speed_flags(torch)

    model_path = Path(
        LLM_DIRECT_MODEL_PATH
    )
    path_key = (
        str(model_path.resolve())
        if model_path.exists()
        else str(model_path)
    )

    if (
        LLM_DIRECT_REQUIRE_LOCAL_FILES
        and not _model_files_available(
            model_path
        )
    ):
        raise FileNotFoundError(
            "Direct model files are not available "
            f"at configured path: {model_path}"
        )

    with _MODEL_LOCK:
        if (
            _MODEL is not None
            and _TOKENIZER is not None
            and _MODEL_PATH_KEY == path_key
        ):
            return (
                _MODEL,
                _TOKENIZER,
                _select_device(torch),
            )

        logger.info(
            "[LLM_DIRECT][LOAD_START] "
            "model=%s path=%s local_files_only=%s "
            "attn=%s compile_setting=%s "
            "compile_at_load=false",
            LLM_DIRECT_MODEL_NAME,
            model_path,
            LLM_DIRECT_REQUIRE_LOCAL_FILES,
            (
                _requested_attention_implementation()
                or "default"
            ),
            LLM_DIRECT_ENABLE_TORCH_COMPILE,
        )

        tokenizer = (
            auto_tokenizer.from_pretrained(
                str(model_path),
                local_files_only=(
                    LLM_DIRECT_REQUIRE_LOCAL_FILES
                ),
                trust_remote_code=(
                    LLM_DIRECT_TRUST_REMOTE_CODE
                ),
            )
        )

        if (
            getattr(
                tokenizer,
                "pad_token",
                None,
            )
            is None
            and getattr(
                tokenizer,
                "eos_token",
                None,
            )
        ):
            tokenizer.pad_token = (
                tokenizer.eos_token
            )

        try:
            tokenizer.padding_side = "left"
        except Exception:
            logger.debug(
                "[LLM_DIRECT]"
                "[PADDING_SIDE_UNCHANGED]"
            )

        load_kwargs = (
            _build_model_load_kwargs(torch)
        )
        model = (
            _load_model_with_attention_fallback(
                auto_model=auto_model,
                model_path=model_path,
                load_kwargs=load_kwargs,
            )
        )

        device = _select_device(torch)
        model.to(device)
        model.eval()

        _MODEL = model
        _TOKENIZER = tokenizer
        _MODEL_PATH_KEY = path_key
        _COMPILED_FORWARD_CACHE = {}
        _COMPILE_ATTEMPTED_CALL_SITES = set()
        _PRIMED_MODEL_PATH_KEY = ""
        _PRIMED_RUNTIME_PROFILE_SHAPES = {}

        logger.info(
            "[LLM_DIRECT][LOAD_OK] "
            "model=%s path=%s device=%s attn=%s "
            "compile_setting=%s compiled=false",
            LLM_DIRECT_MODEL_NAME,
            model_path,
            device,
            (
                load_kwargs.get(
                    "attn_implementation"
                )
                or "default"
            ),
            LLM_DIRECT_ENABLE_TORCH_COMPILE,
        )

        return (
            _MODEL,
            _TOKENIZER,
            device,
        )


def _render_prompt(
    tokenizer: Any,
    prompt: str,
    *,
    disable_thinking: bool = False,
) -> str:
    cleaned = prompt.strip()

    if hasattr(
        tokenizer,
        "apply_chat_template",
    ):
        messages = [
            {
                "role": "user",
                "content": cleaned,
            }
        ]

        if disable_thinking:
            try:
                return tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                logger.info(
                    "[LLM_DIRECT]"
                    "[THINKING_CONTROL_UNSUPPORTED] "
                    "falling_back_to_default_chat_template"
                )
            except Exception:
                logger.warning(
                    "[LLM_DIRECT]"
                    "[THINKING_CONTROL_FALLBACK]",
                    exc_info=True,
                )

        try:
            return tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:
            logger.warning(
                "[LLM_DIRECT]"
                "[CHAT_TEMPLATE_FALLBACK]"
            )

    return cleaned


def _sanitize_generated_text(
    value: str,
) -> str:
    cleaned = (
        value
        .replace(
            "<|im_end|>",
            "",
        )
        .replace(
            "<|endoftext|>",
            "",
        )
        .strip()
    )
    cleaned = _THINK_BLOCK_RE.sub(
        "",
        cleaned,
    ).strip()
    cleaned = _THINK_OPEN_RE.sub(
        "",
        cleaned,
    ).strip()

    return cleaned


def _decode_generated_tokens(
    tokenizer: Any,
    generated_tokens: Any,
) -> str:
    try:
        return tokenizer.decode(
            generated_tokens,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        )
    except TypeError:
        return tokenizer.decode(
            generated_tokens,
            skip_special_tokens=True,
        )


def _count_text_tokens(
    tokenizer: Any,
    text: str,
) -> int:
    clean_text = str(text or "")

    if not clean_text:
        return 0

    try:
        tokenized = tokenizer(
            clean_text,
            add_special_tokens=False,
            return_attention_mask=False,
        )
        input_ids = tokenized.get(
            "input_ids",
            [],
        )

        return len(input_ids)
    except Exception:
        return 0


def _generated_tokens_count(
    generated_tokens: Any,
) -> int:
    try:
        return int(
            generated_tokens.shape[-1]
        )
    except Exception:
        pass

    try:
        return len(generated_tokens)
    except Exception:
        return 0


def _tokens_per_second(
    token_count: int,
    elapsed_ms: float,
) -> float:
    if (
        token_count <= 0
        or elapsed_ms <= 0
    ):
        return 0.0

    return token_count / (
        elapsed_ms / 1000
    )


def _normalized_call_site(
    call_site: str,
) -> str:
    return str(
        call_site or ""
    ).strip().lower()


def _normalized_response_format(
    response_format: str,
) -> str:
    return str(
        response_format or "text"
    ).strip().lower()


def _normalize_runtime_profile(
    runtime_profile: str | None,
) -> str:
    clean_value = str(
        runtime_profile
        or _RUNTIME_PROFILE_DEFAULT
    ).strip().lower()

    if clean_value not in _RUNTIME_PROFILES:
        allowed = ", ".join(
            sorted(
                _RUNTIME_PROFILES
            )
        )
        raise ValueError(
            "Unsupported direct-model runtime profile "
            f"'{clean_value}'. Allowed profiles: {allowed}."
        )

    return clean_value


def _runtime_profile_thread_key(
    *,
    call_site: str,
    runtime_profile: str,
) -> str:
    """Return one process-local runtime key bound to the current thread."""

    return (
        f"{_MODEL_PATH_KEY}:"
        f"{_normalized_call_site(call_site)}:"
        f"{runtime_profile}:"
        f"{threading.get_ident()}"
    )


def _runtime_profile_warmed_shapes(
    *,
    call_site: str,
    runtime_profile: str,
) -> set[tuple[int, int, bool]]:
    """Return exact input/output/streaming shapes primed on this thread."""

    key = _runtime_profile_thread_key(
        call_site=call_site,
        runtime_profile=runtime_profile,
    )

    return set(
        _PRIMED_RUNTIME_PROFILE_SHAPES.get(
            key,
            set(),
        )
    )


def _runtime_profile_warmed_budget(
    *,
    call_site: str,
    runtime_profile: str,
) -> int:
    """Return the largest output budget primed on the current thread."""

    warmed_shapes = (
        _runtime_profile_warmed_shapes(
            call_site=call_site,
            runtime_profile=runtime_profile,
        )
    )

    return max(
        (
            output_budget
            for _, output_budget, _
            in warmed_shapes
        ),
        default=0,
    )


def _runtime_profile_warmed_input_tokens(
    *,
    call_site: str,
    runtime_profile: str,
) -> int:
    """Return the largest rendered input shape primed on the current thread."""

    warmed_shapes = (
        _runtime_profile_warmed_shapes(
            call_site=call_site,
            runtime_profile=runtime_profile,
        )
    )

    return max(
        (
            input_tokens
            for input_tokens, _, _
            in warmed_shapes
        ),
        default=0,
    )


def _is_json_object_response(
    response_format: str,
) -> bool:
    return (
        _normalized_response_format(
            response_format
        )
        in {
            "json",
            "json_object",
            "application/json",
        }
    )


def _is_visual_conductor_call(
    call_site: str,
) -> bool:
    return (
        _normalized_call_site(
            call_site
        )
        == "solomon_visual_conductor"
    )


def _is_home_assistant_call(
    call_site: str,
) -> bool:
    return (
        _normalized_call_site(
            call_site
        )
        in {
            "solomon_home_answer_assistant",
            "solomon_home_assistant",
            "solomon_home_static_compile_benchmark",
            "solomon_static_compile_benchmark",
        }
    )


def _is_home_json_call(
    call_site: str,
    response_format: str,
) -> bool:
    return (
        _is_home_assistant_call(
            call_site
        )
        and _is_json_object_response(
            response_format
        )
    )


def _is_solomon_assistant_json_call(
    call_site: str,
    response_format: str,
) -> bool:
    return (
        _normalized_call_site(call_site)
        == _SOLOMON_ASSISTANT_CALL_SITE
        and _is_json_object_response(
            response_format
        )
    )


def _is_solomon_ai_response_synthesis_call(
    call_site: str,
    response_format: str | None = None,
) -> bool:
    if (
        _normalized_call_site(call_site)
        != _SOLOMON_AI_RESPONSE_SYNTHESIS_CALL_SITE
    ):
        return False

    if response_format is None:
        return True

    return _is_json_object_response(
        response_format
    )


def _is_workspace_source_operation_call(
    call_site: str,
) -> bool:
    return (
        _normalized_call_site(
            call_site
        )
        in _WORKSPACE_SOURCE_OPERATION_CALL_SITES
    )


def _is_docintel_summary_narration_call(
    call_site: str,
) -> bool:
    return (
        _normalized_call_site(call_site)
        == _DOCINTEL_SUMMARY_NARRATION_CALL_SITE
    )


def _is_assistant_call(
    call_site: str,
) -> bool:
    return (
        "assistant"
        in _normalized_call_site(
            call_site
        )
    )


def _is_docintel_call(
    call_site: str,
) -> bool:
    normalized = _normalized_call_site(
        call_site
    )

    return (
        normalized in _DOCINTEL_CALL_SITES
        or "docintel" in normalized
        or "informational_only" in normalized
    )


def _is_bei_report_call(
    call_site: str,
) -> bool:
    return (
        _normalized_call_site(
            call_site
        )
        in {
            "bei_report_writer",
            "bei_report_static_compile_benchmark",
        }
    )


def _prompt_lookup_num_tokens(
    call_site: str,
) -> int:
    if (
        _normalized_call_site(call_site)
        == _DOCINTEL_PROMPT_LOOKUP_BENCHMARK_CALL_SITE
    ):
        return (
            _PROMPT_LOOKUP_BENCHMARK_NUM_TOKENS
        )

    return 0


def _resolve_generation_profile(
    call_site: str,
    response_format: str,
    *,
    max_new_tokens: int | None = None,
) -> dict[str, Any]:
    selected_tokens = int(
        select_max_new_tokens(
            call_site
        )
    )

    if (
        max_new_tokens is not None
        and not _is_workspace_source_operation_call(
            call_site
        )
        and not _is_docintel_summary_narration_call(
            call_site
        )
    ):
        selected_tokens = min(
            selected_tokens,
            max_new_tokens,
        )

    if _is_visual_conductor_call(
        call_site
    ):
        return {
            "max_new_tokens": min(
                selected_tokens,
                LLM_DIRECT_VISUAL_CONDUCTOR_MAX_NEW_TOKENS,
            ),
            "do_sample": False,
            "temperature": 0.0,
            "top_p": None,
            "repetition_penalty": 1.0,
            "num_beams": 1,
        }

    if _is_home_json_call(
        call_site,
        response_format,
    ):
        return {
            "max_new_tokens": min(
                selected_tokens,
                LLM_DIRECT_HOME_JSON_MAX_NEW_TOKENS,
                _HOME_JSON_RUNTIME_MAX_NEW_TOKENS,
            ),
            "do_sample": False,
            "temperature": 0.0,
            "top_p": None,
            "repetition_penalty": 1.0,
            "num_beams": 1,
        }

    if _is_solomon_assistant_json_call(
        call_site,
        response_format,
    ):
        return {
            "max_new_tokens": min(
                selected_tokens,
                LLM_DIRECT_ASSISTANT_MAX_NEW_TOKENS,
            ),
            "do_sample": False,
            "temperature": 0.0,
            "top_p": None,
            "repetition_penalty": 1.0,
            "renormalize_logits": True,
            "remove_invalid_values": True,
            "num_beams": 1,
        }

    if _is_solomon_ai_response_synthesis_call(
        call_site,
        response_format,
    ):
        return {
            "max_new_tokens": min(
                selected_tokens,
                _SOLOMON_AI_RESPONSE_SYNTHESIS_MAX_NEW_TOKENS,
            ),
            "do_sample": False,
            "temperature": 0.0,
            "top_p": None,
            "repetition_penalty": 1.0,
            "num_beams": 1,
        }

    if _is_home_assistant_call(
        call_site
    ):
        return {
            "max_new_tokens": min(
                selected_tokens,
                LLM_DIRECT_HOME_MAX_NEW_TOKENS,
            ),
            "do_sample": False,
            "temperature": 0.0,
            "top_p": None,
            "repetition_penalty": 1.0,
            "num_beams": 1,
        }

    if _is_workspace_source_operation_call(
        call_site
    ):
        source_operation_tokens = (
            max_new_tokens
            if max_new_tokens is not None
            else min(
                selected_tokens,
                _WORKSPACE_SOURCE_OPERATION_DEFAULT_MAX_NEW_TOKENS,
            )
        )

        return {
            "max_new_tokens": source_operation_tokens,
            "do_sample": False,
            "temperature": 0.0,
            "top_p": None,
            "repetition_penalty": 1.06,
            "num_beams": 1,
        }

    if _is_docintel_summary_narration_call(
        call_site
    ):
        narration_tokens = (
            max_new_tokens
            if max_new_tokens is not None
            else selected_tokens
        )

        return {
            "max_new_tokens": min(
                narration_tokens,
                _DOCINTEL_SUMMARY_NARRATION_MAX_NEW_TOKENS,
            ),
            "do_sample": False,
            "temperature": 0.0,
            "top_p": None,
            "repetition_penalty": 1.0,
            "num_beams": 1,
        }

    if _is_docintel_call(
        call_site
    ):
        return {
            "max_new_tokens": min(
                selected_tokens,
                LLM_DIRECT_DOCINTEL_MAX_NEW_TOKENS,
            ),
            "do_sample": False,
            "temperature": 0.0,
            "top_p": None,
            "repetition_penalty": 1.06,
            "num_beams": 1,
        }

    if _is_assistant_call(
        call_site
    ):
        return {
            "max_new_tokens": min(
                selected_tokens,
                LLM_DIRECT_ASSISTANT_MAX_NEW_TOKENS,
            ),
            "do_sample": False,
            "temperature": 0.0,
            "top_p": None,
            "repetition_penalty": 1.0,
            "no_repeat_ngram_size": 3,
            "renormalize_logits": True,
            "remove_invalid_values": True,
            "num_beams": 1,
        }

    if _is_bei_report_call(
        call_site
    ):
        return {
            "max_new_tokens": min(
                selected_tokens,
                LLM_DIRECT_BEI_MAX_NEW_TOKENS,
            ),
            "do_sample": False,
            "temperature": 0.0,
            "top_p": None,
            "repetition_penalty": 1.08,
            "num_beams": 1,
        }

    temperature = max(
        float(LLM_TEMPERATURE),
        0.0,
    )

    return {
        "max_new_tokens": selected_tokens,
        "do_sample": temperature > 0,
        "temperature": temperature,
        "top_p": LLM_DIRECT_DEFAULT_TOP_P,
        "repetition_penalty": (
            LLM_DIRECT_DEFAULT_REPEAT_PENALTY
        ),
        "num_beams": 1,
    }


def _build_generate_kwargs(
    tokenizer: Any,
    profile: dict[str, Any],
    *,
    use_static_cache: bool = False,
    prompt_lookup_num_tokens: int = 0,
) -> dict[str, Any]:
    kwargs = {
        "max_new_tokens": (
            profile["max_new_tokens"]
        ),
        "do_sample": profile["do_sample"],
        "num_beams": profile["num_beams"],
        "repetition_penalty": (
            profile["repetition_penalty"]
        ),
        "use_cache": True,
        "pad_token_id": (
            tokenizer.pad_token_id
            or tokenizer.eos_token_id
        ),
        "eos_token_id": (
            tokenizer.eos_token_id
        ),
    }

    if use_static_cache:
        kwargs["cache_implementation"] = (
            "static"
        )

    if prompt_lookup_num_tokens > 0:
        kwargs["prompt_lookup_num_tokens"] = (
            prompt_lookup_num_tokens
        )

    no_repeat_ngram_size = int(
        profile.get(
            "no_repeat_ngram_size",
            0,
        )
        or 0
    )

    if no_repeat_ngram_size > 0:
        kwargs["no_repeat_ngram_size"] = (
            no_repeat_ngram_size
        )

    if profile.get(
        "renormalize_logits",
        False,
    ):
        kwargs["renormalize_logits"] = True

    if profile.get(
        "remove_invalid_values",
        False,
    ):
        kwargs["remove_invalid_values"] = True

    if profile["do_sample"]:
        kwargs["temperature"] = (
            profile["temperature"]
        )
        kwargs["top_p"] = (
            profile["top_p"]
        )

    return kwargs


def _generate_with_static_cache_fallback(
    *,
    model: Any,
    inputs: dict[str, Any],
    generate_kwargs: dict[str, Any],
    call_site: str,
    runtime_state: dict[str, Any] | None = None,
) -> Any:
    working_kwargs = dict(
        generate_kwargs
    )
    static_cache_requested = (
        "cache_implementation"
        in working_kwargs
    )
    prompt_lookup_requested = int(
        working_kwargs.get(
            "prompt_lookup_num_tokens",
            0,
        )
        or 0
    )

    if runtime_state is not None:
        runtime_state[
            "static_cache_requested"
        ] = static_cache_requested
        runtime_state[
            "static_cache_effective"
        ] = static_cache_requested
        runtime_state[
            "prompt_lookup_requested"
        ] = (
            prompt_lookup_requested > 0
        )
        runtime_state[
            "prompt_lookup_effective"
        ] = (
            prompt_lookup_requested > 0
        )
        runtime_state[
            "prompt_lookup_num_tokens"
        ] = prompt_lookup_requested

    for _ in range(3):
        try:
            return model.generate(
                **inputs,
                **working_kwargs,
            )
        except Exception as exc:
            clean_message = str(exc).lower()

            cache_related = (
                "cache_implementation"
                in clean_message
                or "static" in clean_message
                or "cache" in clean_message
            )
            # Transformers can invoke Inductor for StaticCache
            # despite the application's explicit compile setting.
            # Treat only a confirmed missing-Triton compiler error
            # as a reason to retry with the default dynamic cache.
            triton_missing = (
                "tritonmissing" in type(exc).__name__.lower()
                or "cannot find a working triton installation"
                in clean_message
            )
            prompt_lookup_related = (
                "prompt_lookup"
                in clean_message
                or "assisted" in clean_message
                or "candidate" in clean_message
                or "n-gram" in clean_message
                or "ngram" in clean_message
            )

            if (
                "cache_implementation"
                in working_kwargs
                and (cache_related or triton_missing)
            ):
                working_kwargs.pop(
                    "cache_implementation",
                    None,
                )

                if runtime_state is not None:
                    runtime_state[
                        "static_cache_effective"
                    ] = False

                logger.warning(
                    "[LLM_DIRECT]"
                    "[STATIC_CACHE_FALLBACK] "
                    "call_site=%s reason=%s",
                    call_site,
                    exc,
                )
                continue

            if (
                "prompt_lookup_num_tokens"
                in working_kwargs
                and prompt_lookup_related
            ):
                working_kwargs.pop(
                    "prompt_lookup_num_tokens",
                    None,
                )

                if runtime_state is not None:
                    runtime_state[
                        "prompt_lookup_effective"
                    ] = False

                logger.warning(
                    "[LLM_DIRECT]"
                    "[PROMPT_LOOKUP_FALLBACK] "
                    "call_site=%s reason=%s",
                    call_site,
                    exc,
                )
                continue

            raise

    raise RuntimeError(
        "Direct generation exhausted "
        "runtime fallbacks."
    )


def _json_response_scaffold(
    call_site: str,
    response_format: str,
) -> tuple[str, str]:
    if _is_home_json_call(
        call_site,
        response_format,
    ):
        return (
            _HOME_JSON_COMPLETION_INSTRUCTION,
            _HOME_JSON_PREFILL,
        )

    if _is_solomon_assistant_json_call(
        call_site,
        response_format,
    ):
        return (
            _SOLOMON_ASSISTANT_JSON_COMPLETION_INSTRUCTION,
            _SOLOMON_ASSISTANT_JSON_PREFILL,
        )

    if _is_solomon_ai_response_synthesis_call(
        call_site,
        response_format,
    ):
        return (
            _SOLOMON_AI_RESPONSE_SYNTHESIS_COMPLETION_INSTRUCTION,
            _SOLOMON_AI_RESPONSE_SYNTHESIS_JSON_PREFILL,
        )

    return "", ""


def _render_generation_prompt(
    *,
    tokenizer: Any,
    prompt: str,
    call_site: str,
    response_format: str,
) -> tuple[str, str]:
    """
    Render runtime instructions inside the user turn and prefill only JSON.

    The chat template's generation marker starts the assistant turn. Runtime
    completion instructions must therefore be included before rendering;
    appending them afterward makes those instructions look like assistant
    output and can cause the model to repeat them verbatim.
    """

    completion_instruction, json_prefill = (
        _json_response_scaffold(
            call_site,
            response_format,
        )
    )
    render_source = prompt

    if completion_instruction:
        render_source = (
            f"{prompt.rstrip()}\n\n"
            "RUNTIME OUTPUT BOUNDARY\n"
            f"{completion_instruction}"
        )

    rendered_prompt = _render_prompt(
        tokenizer,
        render_source,
        disable_thinking=(
            _is_workspace_source_operation_call(
                call_site
            )
            or _is_docintel_call(
                call_site
            )
            or _is_assistant_call(
                call_site
            )
            or _is_solomon_ai_response_synthesis_call(
                call_site
            )
        ),
    )

    if not json_prefill:
        return rendered_prompt, ""

    return (
        f"{rendered_prompt}{json_prefill}",
        json_prefill,
    )


def _compose_prefilled_response(
    model_text: str,
    response_prefix: str,
) -> str:
    clean_text = _sanitize_generated_text(
        model_text
    )

    if not response_prefix:
        return clean_text

    if (
        clean_text.startswith(
            response_prefix
        )
        or clean_text.startswith("{")
    ):
        return clean_text

    return _sanitize_generated_text(
        f"{response_prefix}{clean_text}"
    )


def _extract_complete_json_object(
    value: str,
) -> str:
    candidate = _sanitize_generated_text(
        value
    )

    if not candidate.startswith("{"):
        return ""

    try:
        decoded, end_index = (
            json.JSONDecoder().raw_decode(
                candidate
            )
        )
    except (TypeError, ValueError):
        return ""

    if not isinstance(decoded, dict):
        return ""

    return candidate[
        :end_index
    ].strip()


def _build_json_stopping_criteria(
    *,
    tokenizer: Any,
    input_length: int,
    response_prefix: str,
) -> Any:
    try:
        from transformers import (
            StoppingCriteria,
            StoppingCriteriaList,
        )
    except Exception:
        return None

    class _CompleteJsonObjectStop(
        StoppingCriteria
    ):
        def __call__(
            self,
            input_ids: Any,
            scores: Any,
            **kwargs: Any,
        ) -> bool:
            del scores
            del kwargs

            try:
                generated_tokens = (
                    input_ids[0][
                        input_length:
                    ]
                )
                generated_text = (
                    _decode_generated_tokens(
                        tokenizer,
                        generated_tokens,
                    )
                )
                candidate = (
                    _compose_prefilled_response(
                        generated_text,
                        response_prefix,
                    )
                )

                return bool(
                    _extract_complete_json_object(
                        candidate
                    )
                )
            except Exception:
                return False

    return StoppingCriteriaList(
        [
            _CompleteJsonObjectStop()
        ]
    )


def _json_stop_allowed(
    *,
    response_prefix: str,
    use_static_cache: bool,
) -> bool:
    if not response_prefix:
        return False

    if use_static_cache:
        return False

    return True


def _apply_response_prefix(
    model_text: str,
    response_prefix: str,
) -> str:
    return _compose_prefilled_response(
        model_text,
        response_prefix,
    )


def _run_streamed_generation(
    *,
    model: Any,
    tokenizer: Any,
    inputs: dict[str, Any],
    generate_kwargs: dict[str, Any],
    stream_callback: Callable[[str], None],
    call_site: str,
    runtime_state: dict[str, Any],
    response_prefix: str = "",
) -> str:
    try:
        from transformers import (
            TextIteratorStreamer,
        )
    except Exception as exc:
        raise RuntimeError(
            "Streaming requires "
            "TextIteratorStreamer from transformers."
        ) from exc

    if response_prefix:
        stream_callback(
            response_prefix
        )

    streamer = TextIteratorStreamer(
        tokenizer,
        skip_prompt=True,
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    streamed_kwargs = dict(
        generate_kwargs
    )
    streamed_kwargs["streamer"] = streamer

    generated_error: list[
        BaseException
    ] = []

    def _generate() -> None:
        try:
            _generate_with_static_cache_fallback(
                model=model,
                inputs=inputs,
                generate_kwargs=streamed_kwargs,
                call_site=call_site,
                runtime_state=runtime_state,
            )
        except BaseException as exc:
            generated_error.append(exc)

            try:
                streamer.end()
            except Exception:
                logger.debug(
                    "[LLM_DIRECT]"
                    "[STREAM_ERROR_END_SKIPPED] "
                    "call_site=%s",
                    call_site,
                )

    stream_started_at = perf_counter()

    generation_thread = threading.Thread(
        target=_generate,
        name=(
            "solomon_direct_generation_stream"
        ),
        daemon=True,
    )
    generation_thread.start()

    chunks: list[str] = []

    for chunk in streamer:
        clean_chunk = (
            chunk
            .replace(
                "<|im_end|>",
                "",
            )
            .replace(
                "<|endoftext|>",
                "",
            )
        )

        if not clean_chunk:
            continue

        if (
            runtime_state.get(
                "first_stream_chunk_ms"
            )
            is None
        ):
            first_chunk_ms = _elapsed_ms(
                stream_started_at
            )
            runtime_state[
                "first_stream_chunk_ms"
            ] = first_chunk_ms

            logger.info(
                "[LLM_DIRECT]"
                "[STREAM_FIRST_CHUNK] "
                "call_site=%s elapsed_ms=%.2f",
                call_site,
                first_chunk_ms,
            )

        chunks.append(
            clean_chunk
        )
        stream_callback(
            clean_chunk
        )

    generation_thread.join()

    if generated_error:
        raise generated_error[0]

    return "".join(chunks)


def run_direct_generation(
    *,
    prompt: str,
    call_site: str,
    response_format: str = "text",
    max_new_tokens: int | None = None,
    stream_callback: (
        Callable[[str], None]
        | None
    ) = None,
    runtime_profile: str = (
        _RUNTIME_PROFILE_DEFAULT
    ),
) -> DirectModelResult:
    proof = build_transport_proof(
        call_site
    )
    total_started_at = perf_counter()

    try:
        clean_prompt = (
            prompt or ""
        ).strip()
        resolved_runtime_profile = (
            _normalize_runtime_profile(
                runtime_profile
            )
        )

        if (
            resolved_runtime_profile
            == _RUNTIME_PROFILE_DEFAULT
            and _is_docintel_call(
                call_site
            )
            and not _is_docintel_summary_narration_call(
                call_site
            )
        ):
            resolved_runtime_profile = (
                _RUNTIME_PROFILE_STATIC_CACHE
            )

        if not _runtime_profile_allowed_for_call_site(
            call_site,
            resolved_runtime_profile,
        ):
            return DirectModelResult(
                ok=False,
                text="",
                proof=proof,
                error=(
                    "The requested direct-model "
                    "runtime profile is not approved "
                    "for this call site."
                ),
            )

        if max_new_tokens is not None:
            if (
                isinstance(
                    max_new_tokens,
                    bool,
                )
                or not isinstance(
                    max_new_tokens,
                    int,
                )
                or max_new_tokens < 1
            ):
                return DirectModelResult(
                    ok=False,
                    text="",
                    proof=proof,
                    error=(
                        "Direct model max_new_tokens "
                        "must be a positive integer "
                        "or None."
                    ),
                )

        if not clean_prompt:
            return DirectModelResult(
                ok=False,
                text="",
                proof=proof,
                error=(
                    "Direct model prompt was empty."
                ),
            )

        if (
            len(clean_prompt)
            > MAX_LLM_INPUT_CHARS
        ):
            clean_prompt = clean_prompt[
                :MAX_LLM_INPUT_CHARS
            ].strip()

        load_started_at = perf_counter()
        model, tokenizer, device = (
            _load_model()
        )
        load_elapsed_ms = _elapsed_ms(
            load_started_at
        )

        runtime, _, _ = _import_runtime()

        render_started_at = perf_counter()
        (
            rendered_prompt,
            response_prefix,
        ) = _render_generation_prompt(
            tokenizer=tokenizer,
            prompt=clean_prompt,
            call_site=call_site,
            response_format=response_format,
        )
        render_elapsed_ms = _elapsed_ms(
            render_started_at
        )

        tokenize_started_at = perf_counter()
        inputs = tokenizer(
            rendered_prompt,
            return_tensors="pt",
            truncation=True,
            padding=False,
        )
        inputs = {
            key: value.to(device)
            for key, value
            in inputs.items()
        }
        tokenize_elapsed_ms = _elapsed_ms(
            tokenize_started_at
        )
        input_token_count = int(
            inputs["input_ids"].shape[-1]
        )

        profile = _resolve_generation_profile(
            call_site,
            response_format,
            max_new_tokens=max_new_tokens,
        )
        use_static_cache = (
            _static_cache_allowed_for_call_site(
                call_site,
                resolved_runtime_profile,
            )
        )
        prompt_lookup_tokens = (
            _prompt_lookup_num_tokens(
                call_site
            )
        )
        generate_kwargs = (
            _build_generate_kwargs(
                tokenizer,
                profile,
                use_static_cache=(
                    use_static_cache
                ),
                prompt_lookup_num_tokens=(
                    prompt_lookup_tokens
                ),
            )
        )
        stopping_criteria = None
        use_json_stop = (
            _json_stop_allowed(
                response_prefix=(
                    response_prefix
                ),
                use_static_cache=(
                    use_static_cache
                ),
            )
        )

        if use_json_stop:
            stopping_criteria = (
                _build_json_stopping_criteria(
                    tokenizer=tokenizer,
                    input_length=(
                        input_token_count
                    ),
                    response_prefix=(
                        response_prefix
                    ),
                )
            )

        if stopping_criteria is not None:
            generate_kwargs[
                "stopping_criteria"
            ] = stopping_criteria

        (
            compiled_for_call,
            original_forward,
        ) = (
            _maybe_install_compiled_forward_for_call(
                torch=runtime,
                model=model,
                device=device,
                call_site=call_site,
                runtime_profile=(
                    resolved_runtime_profile
                ),
            )
        )

        logger.info(
            "[LLM_DIRECT][REQUEST] "
            "call_site=%s response_format=%s "
            "prompt_chars=%s "
            "rendered_prompt_chars=%s "
            "input_tokens=%s "
            "requested_max_new_tokens=%s "
            "max_new_tokens=%s do_sample=%s "
            "repetition_penalty=%s "
            "no_repeat_ngram_size=%s "
            "renormalize_logits=%s "
            "remove_invalid_values=%s "
            "device=%s json_scaffold=%s "
            "json_stop=%s runtime_profile=%s "
            "static_cache=%s "
            "prompt_lookup_tokens=%s "
            "streaming=%s "
            "thinking_disabled=%s attn=%s "
            "compile_setting=%s compiled=%s "
            "worker_thread=%s "
            "runtime_warmed_budget=%s "
            "runtime_warmed_input_tokens=%s",
            call_site,
            response_format,
            len(clean_prompt),
            len(rendered_prompt),
            input_token_count,
            max_new_tokens,
            profile["max_new_tokens"],
            profile["do_sample"],
            profile["repetition_penalty"],
            int(
                profile.get(
                    "no_repeat_ngram_size",
                    0,
                )
                or 0
            ),
            bool(
                profile.get(
                    "renormalize_logits",
                    False,
                )
            ),
            bool(
                profile.get(
                    "remove_invalid_values",
                    False,
                )
            ),
            device,
            bool(response_prefix),
            stopping_criteria is not None,
            resolved_runtime_profile,
            use_static_cache,
            prompt_lookup_tokens,
            stream_callback is not None,
            (
                _is_workspace_source_operation_call(
                    call_site
                )
                or _is_docintel_call(
                    call_site
                )
                or _is_assistant_call(
                    call_site
                )
                or (
                    _is_solomon_ai_response_synthesis_call(
                        call_site
                    )
                )
            ),
            (
                _requested_attention_implementation()
                or "default"
            ),
            LLM_DIRECT_ENABLE_TORCH_COMPILE,
            compiled_for_call,
            threading.current_thread().name,
            _runtime_profile_warmed_budget(
                call_site=call_site,
                runtime_profile=(
                    resolved_runtime_profile
                ),
            ),
            _runtime_profile_warmed_input_tokens(
                call_site=call_site,
                runtime_profile=(
                    resolved_runtime_profile
                ),
            ),
        )

        generated_token_count = 0
        generation_state: dict[
            str,
            Any,
        ] = {
            "static_cache_requested": (
                use_static_cache
            ),
            "static_cache_effective": (
                use_static_cache
            ),
            "prompt_lookup_requested": (
                prompt_lookup_tokens > 0
            ),
            "prompt_lookup_effective": (
                prompt_lookup_tokens > 0
            ),
            "prompt_lookup_num_tokens": (
                prompt_lookup_tokens
            ),
            "first_stream_chunk_ms": None,
        }
        generate_started_at = perf_counter()

        try:
            if stream_callback is not None:
                with runtime.inference_mode():
                    model_text = (
                        _run_streamed_generation(
                            model=model,
                            tokenizer=tokenizer,
                            inputs=inputs,
                            generate_kwargs=(
                                generate_kwargs
                            ),
                            stream_callback=(
                                stream_callback
                            ),
                            call_site=call_site,
                            runtime_state=(
                                generation_state
                            ),
                            response_prefix=(
                                response_prefix
                            ),
                        )
                    )
                generate_elapsed_ms = (
                    _elapsed_ms(
                        generate_started_at
                    )
                )
                generated_token_count = (
                    _count_text_tokens(
                        tokenizer,
                        model_text,
                    )
                )
            else:
                with runtime.inference_mode():
                    generated = (
                        _generate_with_static_cache_fallback(
                            model=model,
                            inputs=inputs,
                            generate_kwargs=(
                                generate_kwargs
                            ),
                            call_site=call_site,
                            runtime_state=(
                                generation_state
                            ),
                        )
                    )
                generate_elapsed_ms = (
                    _elapsed_ms(
                        generate_started_at
                    )
                )

                input_length = (
                    inputs[
                        "input_ids"
                    ].shape[-1]
                )
                generated_tokens = (
                    generated[0][
                        input_length:
                    ]
                )
                generated_token_count = (
                    _generated_tokens_count(
                        generated_tokens
                    )
                )

                decode_started_at = (
                    perf_counter()
                )
                model_text = (
                    _decode_generated_tokens(
                        tokenizer,
                        generated_tokens,
                    )
                )
                decode_elapsed_ms = (
                    _elapsed_ms(
                        decode_started_at
                    )
                )

                logger.debug(
                    "[LLM_DIRECT]"
                    "[DECODE_TIMING] "
                    "call_site=%s decode_ms=%.2f "
                    "generated_tokens=%s",
                    call_site,
                    decode_elapsed_ms,
                    generated_token_count,
                )
        finally:
            _restore_forward_if_needed(
                model=model,
                original_forward=original_forward,
                call_site=call_site,
            )

        model_text = _apply_response_prefix(
            model_text,
            response_prefix,
        )

        if _is_json_object_response(
            response_format
        ):
            complete_json_object = (
                _extract_complete_json_object(
                    model_text
                )
            )

            if complete_json_object:
                if (
                    complete_json_object
                    != model_text
                ):
                    logger.info(
                        "[LLM_DIRECT]"
                        "[JSON_OBJECT_TRUNCATED] "
                        "call_site=%s original_chars=%s "
                        "bounded_chars=%s",
                        call_site,
                        len(model_text),
                        len(complete_json_object),
                    )

                model_text = (
                    complete_json_object
                )
            else:
                logger.warning(
                    "[LLM_DIRECT]"
                    "[JSON_OBJECT_INCOMPLETE] "
                    "call_site=%s output_chars=%s",
                    call_site,
                    len(model_text),
                )

        if not model_text:
            return DirectModelResult(
                ok=False,
                text="",
                proof=proof,
                error=(
                    "Direct model returned empty text."
                ),
            )

        final_output_token_count = (
            _count_text_tokens(
                tokenizer,
                model_text,
            )
        )
        total_elapsed_ms = _elapsed_ms(
            total_started_at
        )

        logger.info(
            "[LLM_DIRECT][TIMING] "
            "call_site=%s load_ms=%.2f "
            "render_ms=%.2f tokenize_ms=%.2f "
            "generate_ms=%.2f total_ms=%.2f "
            "input_tokens=%s generated_tokens=%s "
            "final_output_tokens=%s "
            "generated_tps=%.2f compiled=%s "
            "runtime_profile=%s "
            "static_cache_requested=%s "
            "static_cache_effective=%s "
            "prompt_lookup_requested=%s "
            "prompt_lookup_effective=%s "
            "prompt_lookup_tokens=%s "
            "first_stream_chunk_ms=%s",
            call_site,
            load_elapsed_ms,
            render_elapsed_ms,
            tokenize_elapsed_ms,
            generate_elapsed_ms,
            total_elapsed_ms,
            input_token_count,
            generated_token_count,
            final_output_token_count,
            _tokens_per_second(
                generated_token_count,
                generate_elapsed_ms,
            ),
            compiled_for_call,
            resolved_runtime_profile,
            generation_state[
                "static_cache_requested"
            ],
            generation_state[
                "static_cache_effective"
            ],
            generation_state[
                "prompt_lookup_requested"
            ],
            generation_state[
                "prompt_lookup_effective"
            ],
            generation_state[
                "prompt_lookup_num_tokens"
            ],
            (
                round(
                    float(
                        generation_state[
                            "first_stream_chunk_ms"
                        ]
                    ),
                    2,
                )
                if generation_state[
                    "first_stream_chunk_ms"
                ]
                is not None
                else None
            ),
        )

        logger.info(
            "[LLM_DIRECT][OK] "
            "call_site=%s output_chars=%s "
            "runtime=transformers_direct",
            call_site,
            len(model_text),
        )

        return DirectModelResult(
            ok=True,
            text=model_text,
            proof=proof,
            metrics={
                "call_site": call_site,
                "runtime_profile": (
                    resolved_runtime_profile
                ),
                "device": device,
                "load_ms": round(
                    load_elapsed_ms,
                    2,
                ),
                "render_ms": round(
                    render_elapsed_ms,
                    2,
                ),
                "tokenize_ms": round(
                    tokenize_elapsed_ms,
                    2,
                ),
                "generate_ms": round(
                    generate_elapsed_ms,
                    2,
                ),
                "total_ms": round(
                    total_elapsed_ms,
                    2,
                ),
                "input_tokens": (
                    input_token_count
                ),
                "generated_tokens": (
                    generated_token_count
                ),
                "final_output_tokens": (
                    final_output_token_count
                ),
                "generated_tps": round(
                    _tokens_per_second(
                        generated_token_count,
                        generate_elapsed_ms,
                    ),
                    2,
                ),
                "compiled": (
                    compiled_for_call
                ),
                "static_cache_requested": (
                    generation_state[
                        "static_cache_requested"
                    ]
                ),
                "static_cache_effective": (
                    generation_state[
                        "static_cache_effective"
                    ]
                ),
                "prompt_lookup_requested": (
                    generation_state[
                        "prompt_lookup_requested"
                    ]
                ),
                "prompt_lookup_effective": (
                    generation_state[
                        "prompt_lookup_effective"
                    ]
                ),
                "prompt_lookup_num_tokens": (
                    generation_state[
                        "prompt_lookup_num_tokens"
                    ]
                ),
                "streaming": (
                    stream_callback is not None
                ),
                "first_stream_chunk_ms": (
                    round(
                        float(
                            generation_state[
                                "first_stream_chunk_ms"
                            ]
                        ),
                        2,
                    )
                    if generation_state[
                        "first_stream_chunk_ms"
                    ]
                    is not None
                    else None
                ),
                "worker_thread": (
                    threading.current_thread().name
                ),
                "worker_thread_id": (
                    threading.get_ident()
                ),
                "runtime_warmed_budget": (
                    _runtime_profile_warmed_budget(
                        call_site=call_site,
                        runtime_profile=(
                            resolved_runtime_profile
                        ),
                    )
                ),
                "runtime_warmed_input_tokens": (
                    _runtime_profile_warmed_input_tokens(
                        call_site=call_site,
                        runtime_profile=(
                            resolved_runtime_profile
                        ),
                    )
                ),
            },
        )

    except Exception as exc:
        logger.exception(
            "[LLM_DIRECT][FAIL] "
            "call_site=%s",
            call_site,
        )
        return DirectModelResult(
            ok=False,
            text="",
            proof=proof,
            error=str(exc),
        )


def warm_direct_runtime_profile(
    *,
    call_site: str,
    runtime_profile: str,
    max_new_tokens: int,
    warmup_prompt: str | None = None,
    target_input_tokens: int | None = None,
    streaming: bool = False,
) -> DirectModelResult:
    """
    Prime one approved portable runtime shape before user traffic.

    Static-cache execution can specialize against the rendered input length,
    generation budget, and streamed versus non-streamed execution path. Callers
    may therefore supply a synthetic, non-user representative prompt for each
    production request class. Exact shapes are tracked per worker thread so
    repeated warmups remain idempotent without treating one execution path as
    proof that another path has already been prepared.
    """

    global _PRIMED_RUNTIME_PROFILE_SHAPES

    proof = build_transport_proof(
        call_site
    )
    resolved_runtime_profile = (
        _normalize_runtime_profile(
            runtime_profile
        )
    )

    if (
        isinstance(
            max_new_tokens,
            bool,
        )
        or not isinstance(
            max_new_tokens,
            int,
        )
        or max_new_tokens < 1
    ):
        return DirectModelResult(
            ok=False,
            text="",
            proof=proof,
            error=(
                "Runtime-profile warmup "
                "max_new_tokens must be "
                "a positive integer."
            ),
        )

    if not isinstance(
        streaming,
        bool,
    ):
        return DirectModelResult(
            ok=False,
            text="",
            proof=proof,
            error=(
                "Runtime-profile warmup streaming "
                "must be a boolean."
            ),
        )

    if (
        target_input_tokens is not None
        and (
            isinstance(
                target_input_tokens,
                bool,
            )
            or not isinstance(
                target_input_tokens,
                int,
            )
            or target_input_tokens < 1
        )
    ):
        return DirectModelResult(
            ok=False,
            text="",
            proof=proof,
            error=(
                "Runtime-profile warmup "
                "target_input_tokens must be "
                "a positive integer when provided."
            ),
        )

    if not _runtime_profile_allowed_for_call_site(
        call_site,
        resolved_runtime_profile,
    ):
        return DirectModelResult(
            ok=False,
            text="",
            proof=proof,
            error=(
                "The requested runtime-profile "
                "warmup is not approved for "
                "this call site."
            ),
        )

    if warmup_prompt is None:
        clean_warmup_prompt = (
            _BOOT_WARMUP_PROMPT
        )
    else:
        clean_warmup_prompt = str(
            warmup_prompt
        ).strip()

        if not clean_warmup_prompt:
            return DirectModelResult(
                ok=False,
                text="",
                proof=proof,
                error=(
                    "Runtime-profile warmup "
                    "prompt must contain "
                    "non-whitespace text when "
                    "provided."
                ),
            )

    if (
        len(clean_warmup_prompt)
        > MAX_LLM_INPUT_CHARS
    ):
        clean_warmup_prompt = (
            clean_warmup_prompt[
                :MAX_LLM_INPUT_CHARS
            ].strip()
        )

    base_warmup = warm_direct_model(
        call_site=(
            f"{call_site}_model_warmup"
        )
    )

    if not base_warmup.ok:
        return base_warmup

    try:
        _, tokenizer, _ = _load_model()

        def _measure_warmup_prompt(
            prompt_text: str,
        ) -> tuple[int, str]:
            (
                rendered_prompt,
                _,
            ) = _render_generation_prompt(
                tokenizer=tokenizer,
                prompt=prompt_text,
                call_site=call_site,
                response_format="text",
            )
            tokenized_prompt = tokenizer(
                rendered_prompt,
                return_tensors="pt",
                truncation=True,
                padding=False,
            )
            return (
                int(
                    tokenized_prompt[
                        "input_ids"
                    ].shape[-1]
                ),
                rendered_prompt,
            )

        (
            warmup_input_tokens,
            rendered_warmup_prompt,
        ) = _measure_warmup_prompt(
            clean_warmup_prompt
        )

        if target_input_tokens is not None:
            if warmup_input_tokens > target_input_tokens:
                return DirectModelResult(
                    ok=False,
                    text="",
                    proof=proof,
                    error=(
                        "Runtime-profile warmup prompt "
                        "already exceeds the requested "
                        "target_input_tokens."
                    ),
                )

            initial_input_tokens = (
                warmup_input_tokens
            )
            padding_piece = ""

            for candidate in (
                " item",
                " detail",
                " note",
                " scope",
                " value",
                " x",
            ):
                candidate_ids = tokenizer(
                    candidate,
                    add_special_tokens=False,
                ).get(
                    "input_ids",
                    [],
                )

                if len(candidate_ids) == 1:
                    padding_piece = candidate
                    break

            if not padding_piece:
                return DirectModelResult(
                    ok=False,
                    text="",
                    proof=proof,
                    error=(
                        "No stable one-token padding "
                        "piece was available for exact "
                        "runtime-profile warmup fitting."
                    ),
                )

            padding_count = (
                target_input_tokens
                - warmup_input_tokens
            )

            if padding_count:
                clean_warmup_prompt = (
                    clean_warmup_prompt
                    + (
                        padding_piece
                        * padding_count
                    )
                )
                (
                    warmup_input_tokens,
                    rendered_warmup_prompt,
                ) = _measure_warmup_prompt(
                    clean_warmup_prompt
                )

            correction_count = 0

            while (
                warmup_input_tokens
                < target_input_tokens
                and correction_count < 4096
            ):
                clean_warmup_prompt += (
                    padding_piece
                )
                (
                    warmup_input_tokens,
                    rendered_warmup_prompt,
                ) = _measure_warmup_prompt(
                    clean_warmup_prompt
                )
                correction_count += 1

            while (
                warmup_input_tokens
                > target_input_tokens
                and clean_warmup_prompt.endswith(
                    padding_piece
                )
                and correction_count < 8192
            ):
                clean_warmup_prompt = (
                    clean_warmup_prompt[
                        :-len(padding_piece)
                    ]
                )
                (
                    warmup_input_tokens,
                    rendered_warmup_prompt,
                ) = _measure_warmup_prompt(
                    clean_warmup_prompt
                )
                correction_count += 1

            if (
                warmup_input_tokens
                != target_input_tokens
            ):
                return DirectModelResult(
                    ok=False,
                    text="",
                    proof=proof,
                    error=(
                        "Runtime-profile warmup could "
                        "not fit the requested exact "
                        "input-token shape."
                    ),
                )

            logger.info(
                "[LLM_DIRECT]"
                "[RUNTIME_WARMUP_PROMPT_FIT] "
                "call_site=%s runtime_profile=%s "
                "initial_input_tokens=%s "
                "target_input_tokens=%s "
                "final_input_tokens=%s "
                "prompt_chars=%s",
                call_site,
                resolved_runtime_profile,
                initial_input_tokens,
                target_input_tokens,
                warmup_input_tokens,
                len(clean_warmup_prompt),
            )
    except Exception as exc:
        logger.exception(
            "[LLM_DIRECT]"
            "[RUNTIME_WARMUP_SHAPE_FAIL] "
            "call_site=%s runtime_profile=%s",
            call_site,
            resolved_runtime_profile,
        )
        return DirectModelResult(
            ok=False,
            text="",
            proof=proof,
            error=str(exc),
        )

    runtime_key = (
        _runtime_profile_thread_key(
            call_site=call_site,
            runtime_profile=(
                resolved_runtime_profile
            ),
        )
    )
    requested_shape = (
        warmup_input_tokens,
        max_new_tokens,
        streaming,
    )

    with _RUNTIME_PRIME_LOCK:
        warmed_shapes = set(
            _PRIMED_RUNTIME_PROFILE_SHAPES.get(
                runtime_key,
                set(),
            )
        )

        if requested_shape in warmed_shapes:
            logger.info(
                "[LLM_DIRECT]"
                "[RUNTIME_WARMUP_REUSED] "
                "call_site=%s "
                "runtime_profile=%s "
                "input_tokens=%s "
                "max_new_tokens=%s streaming=%s "
                "worker_thread=%s "
                "worker_thread_id=%s",
                call_site,
                resolved_runtime_profile,
                warmup_input_tokens,
                max_new_tokens,
                streaming,
                threading.current_thread().name,
                threading.get_ident(),
            )
            return DirectModelResult(
                ok=True,
                text="ready",
                proof=proof,
                metrics={
                    "call_site": call_site,
                    "runtime_profile": (
                        resolved_runtime_profile
                    ),
                    "input_tokens": (
                        warmup_input_tokens
                    ),
                    "max_new_tokens": (
                        max_new_tokens
                    ),
                    "worker_thread": (
                        threading.current_thread().name
                    ),
                    "worker_thread_id": (
                        threading.get_ident()
                    ),
                    "runtime_warmup_reused": True,
                    "runtime_warmup_target_input_tokens": (
                        target_input_tokens
                    ),
                    "runtime_warmup_streaming": (
                        streaming
                    ),
                },
            )

        result = run_direct_generation(
            prompt=clean_warmup_prompt,
            call_site=call_site,
            response_format="text",
            max_new_tokens=max_new_tokens,
            runtime_profile=(
                resolved_runtime_profile
            ),
            stream_callback=(
                (lambda _chunk: None)
                if streaming
                else None
            ),
        )

        if not result.ok:
            logger.warning(
                "[LLM_DIRECT]"
                "[RUNTIME_WARMUP_FAILED] "
                "call_site=%s "
                "runtime_profile=%s "
                "input_tokens=%s "
                "max_new_tokens=%s streaming=%s "
                "error=%s",
                call_site,
                resolved_runtime_profile,
                warmup_input_tokens,
                max_new_tokens,
                streaming,
                (
                    result.error
                    or (
                        "Unknown runtime "
                        "warmup failure."
                    )
                ),
            )
            return result

        actual_input_tokens = int(
            (
                result.metrics
                or {}
            ).get(
                "input_tokens",
                warmup_input_tokens,
            )
        )
        warmed_shapes.add(
            (
                actual_input_tokens,
                max_new_tokens,
                streaming,
            )
        )
        _PRIMED_RUNTIME_PROFILE_SHAPES[
            runtime_key
        ] = warmed_shapes

        logger.info(
            "[LLM_DIRECT]"
            "[RUNTIME_WARMUP_OK] "
            "call_site=%s runtime_profile=%s "
            "input_tokens=%s "
            "max_new_tokens=%s streaming=%s "
            "generate_ms=%s "
            "generated_tps=%s "
            "worker_thread=%s "
            "worker_thread_id=%s",
            call_site,
            resolved_runtime_profile,
            actual_input_tokens,
            max_new_tokens,
            streaming,
            (
                result.metrics
                or {}
            ).get(
                "generate_ms"
            ),
            (
                result.metrics
                or {}
            ).get(
                "generated_tps"
            ),
            threading.current_thread().name,
            threading.get_ident(),
        )

        result_metrics = dict(
            result.metrics or {}
        )
        result_metrics.update(
            {
                "runtime_warmup_input_tokens": (
                    actual_input_tokens
                ),
                "runtime_warmup_max_new_tokens": (
                    max_new_tokens
                ),
                "runtime_warmup_reused": False,
                "runtime_warmup_target_input_tokens": (
                    target_input_tokens
                ),
                "runtime_warmup_streaming": (
                    streaming
                ),
            }
        )

        return DirectModelResult(
            ok=True,
            text="ready",
            proof=proof,
            metrics=result_metrics,
        )


def warm_direct_model(
    *,
    call_site: str = "solomon_boot_warmup",
) -> DirectModelResult:
    """
    Load and prime the configured direct model before user traffic begins.

    The warmup performs one bounded token of non-user-visible generation so
    shared model loading and first-generation runtime initialization do not fall
    on the first SolomonAI request. Lane-specific runtime profiles remain lazy
    and are initialized only by their authorized execution paths. Repeated calls
    for the same loaded model are idempotent within the current process.
    """

    global _PRIMED_MODEL_PATH_KEY

    proof = build_transport_proof(
        call_site
    )
    total_started_at = perf_counter()

    try:
        load_started_at = perf_counter()
        model, tokenizer, device = (
            _load_model()
        )
        load_elapsed_ms = _elapsed_ms(
            load_started_at
        )

        runtime, _, _ = _import_runtime()

        with _PRIME_LOCK:
            if (
                _PRIMED_MODEL_PATH_KEY
                and (
                    _PRIMED_MODEL_PATH_KEY
                    == _MODEL_PATH_KEY
                )
            ):
                logger.info(
                    "[LLM_DIRECT]"
                    "[WARMUP_REUSED] "
                    "call_site=%s model=%s "
                    "device=%s",
                    call_site,
                    LLM_DIRECT_MODEL_NAME,
                    device,
                )

                return DirectModelResult(
                    ok=True,
                    text="ready",
                    proof=proof,
                )

            rendered_prompt = _render_prompt(
                tokenizer,
                _BOOT_WARMUP_PROMPT,
                disable_thinking=True,
            )

            inputs = tokenizer(
                rendered_prompt,
                return_tensors="pt",
                truncation=True,
                padding=False,
            )
            inputs = {
                key: value.to(device)
                for key, value
                in inputs.items()
            }

            generate_kwargs = {
                "max_new_tokens": (
                    _BOOT_WARMUP_MAX_NEW_TOKENS
                ),
                "do_sample": False,
                "num_beams": 1,
                "repetition_penalty": 1.0,
                "use_cache": True,
                "pad_token_id": (
                    tokenizer.pad_token_id
                    if (
                        tokenizer.pad_token_id
                        is not None
                    )
                    else tokenizer.eos_token_id
                ),
                "eos_token_id": (
                    tokenizer.eos_token_id
                ),
            }

            prime_started_at = (
                perf_counter()
            )

            with runtime.inference_mode():
                model.generate(
                    **inputs,
                    **generate_kwargs,
                )

            if (
                device == "cuda"
                and runtime.cuda.is_available()
            ):
                runtime.cuda.synchronize()

            prime_elapsed_ms = _elapsed_ms(
                prime_started_at
            )
            _PRIMED_MODEL_PATH_KEY = (
                _MODEL_PATH_KEY
            )

        total_elapsed_ms = _elapsed_ms(
            total_started_at
        )

        logger.info(
            "[LLM_DIRECT][WARMUP_OK] "
            "call_site=%s model=%s "
            "device=%s load_ms=%.2f "
            "prime_ms=%.2f total_ms=%.2f "
            "input_tokens=%s "
            "generated_tokens=%s",
            call_site,
            LLM_DIRECT_MODEL_NAME,
            device,
            load_elapsed_ms,
            prime_elapsed_ms,
            total_elapsed_ms,
            int(
                inputs[
                    "input_ids"
                ].shape[-1]
            ),
            _BOOT_WARMUP_MAX_NEW_TOKENS,
        )

        return DirectModelResult(
            ok=True,
            text="ready",
            proof=proof,
        )

    except Exception as exc:
        logger.exception(
            "[LLM_DIRECT][WARMUP_FAIL] "
            "call_site=%s",
            call_site,
        )

        return DirectModelResult(
            ok=False,
            text="",
            proof=proof,
            error=str(exc),
        )