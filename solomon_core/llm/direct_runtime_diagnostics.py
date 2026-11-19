# ---------------------------------------------------------------------------
# FILE: solomon_core/llm/direct_runtime_diagnostics.py
# DIRECTORY: solomon_core/llm/
# ---------------------------------------------------------------------------
# Direct Runtime Diagnostics
#
# PURPOSE
#   Diagnose whether the local Transformers runtime can safely use CUDA,
#   Triton, Torch Inductor, static KV cache, and benchmark-gated compiled
#   generation outside the Flask/Home request path.
#
# CONTRACT
#   - Does not patch live Home behavior.
#   - Runs runtime probes in child processes so compile/static-cache stalls do
#     not lock the app server.
#   - Splits model load, tokenization, raw generation, static cache generation,
#     static cache shape reuse, compiled generation, and no-CUDAGraph compiled
#     generation into separate proof points.
#   - Prints machine-readable JSON proof for each probe.
#   - Uses existing Solomon runtime settings and model path resolution.
#
# USAGE
#   python -m solomon_core.llm.direct_runtime_diagnostics
#
# OPTIONAL
#   python -m solomon_core.llm.direct_runtime_diagnostics --timeout 120
#   python -m solomon_core.llm.direct_runtime_diagnostics --only raw_generate
#   python -m solomon_core.llm.direct_runtime_diagnostics --only static_cache_shape_reuse
#   python -m solomon_core.llm.direct_runtime_diagnostics --only compiled_static_no_cudagraphs
# ---------------------------------------------------------------------------

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import subprocess
import sys
import traceback
from pathlib import Path
from time import perf_counter
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_GENERATION_TOKENS = 24
DEFAULT_PROMPT = "Reply with one short JSON object explaining what SolomonAI can help with."

JSON_BEGIN_MARKER = "__SOLOMON_DIRECT_DIAGNOSTIC_JSON_BEGIN__"
JSON_END_MARKER = "__SOLOMON_DIRECT_DIAGNOSTIC_JSON_END__"

HOME_JSON_PREFILL = '{"answer":"'
HOME_JSON_COMPLETION_INSTRUCTION = (
    "Complete one valid JSON object now. Fill answer, bridge, and exactly "
    "three suggestions. Do not leave bridge or suggestions empty unless the "
    "user only greeted or thanked you."
)

STATIC_CACHE_SHAPE_PROMPTS = (
    ("default", DEFAULT_PROMPT),
    ("default_repeat", DEFAULT_PROMPT),
    ("short", "What can you do?"),
    (
        "medium",
        "A user is on the Nations Systems Home screen and asks where to upload "
        "a bid package. Reply with one short JSON object.",
    ),
    (
        "longer",
        "A construction user is reviewing the Nations Systems Home workspace. "
        "They want to know whether SolomonAI can help with documents, bid review, "
        "scope control, governed workflows, and workspace guidance. Reply with "
        "one short JSON object only.",
    ),
    ("default_final_repeat", DEFAULT_PROMPT),
)

PARENT_PROBES: tuple[tuple[str, bool], ...] = (
    ("environment", False),
    ("simple_compile", False),
    ("tokenizer_load", False),
    ("model_load", False),
    ("home_tokenize", False),
    ("raw_generate", False),
    ("static_cache_generate", False),
    ("static_cache_shape_reuse", False),
    ("compiled_static_generate", True),
    ("compiled_static_no_cudagraphs", True),
)


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 2)


def _json_default(value: Any) -> str:
    try:
        return str(value)
    except Exception:
        return "<unprintable>"


def _print_json(payload: dict[str, Any], *, sentinel: bool = False) -> None:
    if sentinel:
        print(JSON_BEGIN_MARKER, flush=True)

    print(json.dumps(payload, indent=2, sort_keys=True, default=_json_default), flush=True)

    if sentinel:
        print(JSON_END_MARKER, flush=True)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _tail(value: Any, limit: int = 4000) -> str:
    if value is None:
        return ""

    if isinstance(value, bytes):
        return value.decode(errors="replace")[-limit:]

    return str(value)[-limit:]


def _model_file_status(model_path: str | Path) -> dict[str, Any]:
    path = Path(model_path)

    return {
        "model_path": str(path),
        "exists": path.exists(),
        "is_dir": path.is_dir(),
        "has_config": (path / "config.json").exists(),
        "has_tokenizer": (
            (path / "tokenizer.json").exists()
            or (path / "tokenizer_config.json").exists()
        ),
        "safetensors_count": len(list(path.glob("*.safetensors"))) if path.exists() else 0,
        "bin_count": len(list(path.glob("*.bin"))) if path.exists() else 0,
    }


def _safe_version(module_name: str) -> str:
    try:
        module = __import__(module_name)
        return str(getattr(module, "__version__", "unknown"))
    except Exception as exc:
        return f"unavailable: {exc}"


def _tokens_per_second(token_count: int, elapsed_ms: float) -> float:
    if token_count <= 0 or elapsed_ms <= 0:
        return 0.0

    return round(token_count / (elapsed_ms / 1000), 2)


def _environment_probe() -> dict[str, Any]:
    started_at = perf_counter()
    payload: dict[str, Any] = {
        "probe": "environment",
        "ok": False,
        "python_executable": sys.executable,
        "python_version": sys.version.replace("\n", " "),
        "platform": platform.platform(),
        "cwd": os.getcwd(),
        "repo_root": str(_repo_root()),
        "torch_version": _safe_version("torch"),
        "triton_version": _safe_version("triton"),
        "transformers_version": _safe_version("transformers"),
        "triton_spec_available": importlib.util.find_spec("triton") is not None,
    }

    try:
        import torch

        payload.update(
            {
                "cuda_available": bool(torch.cuda.is_available()),
                "cuda_device_count": int(torch.cuda.device_count())
                if torch.cuda.is_available()
                else 0,
                "torch_compile_available": hasattr(torch, "compile"),
            }
        )

        if torch.cuda.is_available():
            device_index = torch.cuda.current_device()
            payload.update(
                {
                    "cuda_current_device": int(device_index),
                    "cuda_device_name": torch.cuda.get_device_name(device_index),
                    "cuda_capability": ".".join(
                        str(part) for part in torch.cuda.get_device_capability(device_index)
                    ),
                }
            )

        from config import settings
        from solomon_core.llm import llm_transport

        payload.update(
            {
                "settings_compile_enabled": bool(settings.LLM_DIRECT_ENABLE_TORCH_COMPILE),
                "transport_compile_enabled": bool(
                    llm_transport.LLM_DIRECT_ENABLE_TORCH_COMPILE
                ),
                "compile_mode": str(llm_transport.LLM_DIRECT_TORCH_COMPILE_MODE),
                "attention_implementation": (
                    llm_transport.LLM_DIRECT_ATTN_IMPLEMENTATION or "default"
                ),
                "direct_device_setting": str(llm_transport.LLM_DIRECT_DEVICE),
                "direct_dtype_setting": str(llm_transport.LLM_DIRECT_DTYPE),
                "direct_model_available": bool(
                    llm_transport.direct_model_files_available()
                ),
                "model_files": _model_file_status(llm_transport.LLM_DIRECT_MODEL_PATH),
            }
        )

        payload["ok"] = True
    except Exception as exc:
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()

    payload["elapsed_ms"] = _elapsed_ms(started_at)
    return payload


def _simple_compile_probe() -> dict[str, Any]:
    started_at = perf_counter()
    payload: dict[str, Any] = {
        "probe": "simple_torch_compile",
        "ok": False,
    }

    try:
        import torch

        payload.update(
            {
                "torch_compile_available": hasattr(torch, "compile"),
                "triton_spec_available": importlib.util.find_spec("triton") is not None,
                "cuda_available": bool(torch.cuda.is_available()),
            }
        )

        if not torch.cuda.is_available():
            payload["error"] = "CUDA is unavailable."
            payload["elapsed_ms"] = _elapsed_ms(started_at)
            return payload

        if not hasattr(torch, "compile"):
            payload["error"] = "torch.compile is unavailable."
            payload["elapsed_ms"] = _elapsed_ms(started_at)
            return payload

        device = "cuda"
        dtype = torch.float16

        def _matmul(left: Any, right: Any) -> Any:
            return left @ right

        compiled = torch.compile(_matmul, mode="reduce-overhead")
        left = torch.randn((128, 128), device=device, dtype=dtype)
        right = torch.randn((128, 128), device=device, dtype=dtype)

        warm_started_at = perf_counter()
        output = compiled(left, right)
        torch.cuda.synchronize()
        warm_elapsed_ms = _elapsed_ms(warm_started_at)

        repeat_started_at = perf_counter()
        output = compiled(left, right)
        torch.cuda.synchronize()
        repeat_elapsed_ms = _elapsed_ms(repeat_started_at)

        payload.update(
            {
                "ok": True,
                "output_shape": list(output.shape),
                "warm_compile_call_ms": warm_elapsed_ms,
                "repeat_compiled_call_ms": repeat_elapsed_ms,
            }
        )
    except Exception as exc:
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()

    payload["elapsed_ms"] = _elapsed_ms(started_at)
    return payload


def _enable_runtime_speed_flags(torch: Any) -> None:
    try:
        if hasattr(torch, "set_float32_matmul_precision"):
            torch.set_float32_matmul_precision("high")

        if hasattr(torch.backends, "cuda") and hasattr(torch.backends.cuda, "matmul"):
            torch.backends.cuda.matmul.allow_tf32 = True

        if hasattr(torch.backends, "cudnn"):
            torch.backends.cudnn.allow_tf32 = True
            torch.backends.cudnn.benchmark = True
    except Exception:
        pass


def _enable_dynamo_safety(torch: Any) -> None:
    try:
        dynamo = getattr(torch, "_dynamo", None)
        config = getattr(dynamo, "config", None)

        if config is not None and hasattr(config, "suppress_errors"):
            config.suppress_errors = True
    except Exception:
        pass


def _configure_compile_without_cudagraphs(torch: Any) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "requested": True,
        "settings_applied": [],
        "settings_missing": [],
        "mark_step_available": False,
    }

    try:
        compiler = getattr(torch, "compiler", None)
        meta["mark_step_available"] = bool(
            compiler is not None and hasattr(compiler, "cudagraph_mark_step_begin")
        )
    except Exception:
        meta["mark_step_available"] = False

    try:
        import torch._inductor.config as inductor_config

        candidate_settings: tuple[tuple[str, Any, str], ...] = (
            ("torch._inductor.config", inductor_config, "use_cudagraphs"),
            ("torch._inductor.config", inductor_config, "cudagraphs"),
            (
                "torch._inductor.config.triton",
                getattr(inductor_config, "triton", None),
                "cudagraphs",
            ),
            (
                "torch._inductor.config.triton",
                getattr(inductor_config, "triton", None),
                "cudagraph_trees",
            ),
        )

        for owner_name, owner, attr_name in candidate_settings:
            if owner is None:
                meta["settings_missing"].append(f"{owner_name}.{attr_name}")
                continue

            try:
                current_value = getattr(owner, attr_name)
            except Exception:
                meta["settings_missing"].append(f"{owner_name}.{attr_name}")
                continue

            try:
                setattr(owner, attr_name, False)
                meta["settings_applied"].append(
                    {
                        "setting": f"{owner_name}.{attr_name}",
                        "previous_value": current_value,
                        "new_value": False,
                    }
                )
            except Exception as exc:
                meta["settings_missing"].append(
                    f"{owner_name}.{attr_name}: set_failed={exc}"
                )
    except Exception as exc:
        meta["config_error"] = str(exc)

    return meta


def _mark_cudagraph_step_if_available(torch: Any) -> bool:
    try:
        compiler = getattr(torch, "compiler", None)

        if compiler is None or not hasattr(compiler, "cudagraph_mark_step_begin"):
            return False

        compiler.cudagraph_mark_step_begin()
        return True
    except Exception:
        return False


def _cuda_memory_snapshot(torch: Any) -> dict[str, Any]:
    if not torch.cuda.is_available():
        return {
            "cuda_available": False,
        }

    try:
        return {
            "cuda_available": True,
            "memory_allocated_mb": round(torch.cuda.memory_allocated() / 1024 / 1024, 2),
            "memory_reserved_mb": round(torch.cuda.memory_reserved() / 1024 / 1024, 2),
            "max_memory_allocated_mb": round(
                torch.cuda.max_memory_allocated() / 1024 / 1024,
                2,
            ),
            "max_memory_reserved_mb": round(
                torch.cuda.max_memory_reserved() / 1024 / 1024,
                2,
            ),
        }
    except Exception as exc:
        return {
            "cuda_available": True,
            "memory_error": str(exc),
        }


def _supports_modern_dtype_kwarg() -> bool:
    try:
        import transformers

        version_text = str(getattr(transformers, "__version__", "")).strip()
        major_text = version_text.split(".", 1)[0]

        return int(major_text) >= 5
    except Exception:
        return False


def _resolve_dtype(torch: Any, dtype_setting: str) -> Any:
    clean_value = str(dtype_setting or "auto").strip().lower()

    if clean_value in {"float16", "fp16"}:
        return torch.float16

    if clean_value in {"bfloat16", "bf16"}:
        return torch.bfloat16

    if clean_value in {"float32", "fp32"}:
        return torch.float32

    return "auto"


def _select_device(torch: Any, requested_device: str) -> str:
    clean_device = str(requested_device or "auto").strip().lower()

    if clean_device == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"

    if clean_device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA was requested, but CUDA is unavailable.")

    if clean_device in {"cuda", "cpu"}:
        return clean_device

    return "cuda" if torch.cuda.is_available() else "cpu"


def _build_model_load_kwargs(torch: Any) -> dict[str, Any]:
    from solomon_core.llm.llm_transport import (
        LLM_DIRECT_ATTN_IMPLEMENTATION,
        LLM_DIRECT_DTYPE,
        LLM_DIRECT_REQUIRE_LOCAL_FILES,
        LLM_DIRECT_TRUST_REMOTE_CODE,
    )

    dtype_key = "dtype" if _supports_modern_dtype_kwarg() else "torch_dtype"
    load_kwargs: dict[str, Any] = {
        dtype_key: _resolve_dtype(torch, LLM_DIRECT_DTYPE),
        "local_files_only": LLM_DIRECT_REQUIRE_LOCAL_FILES,
        "trust_remote_code": LLM_DIRECT_TRUST_REMOTE_CODE,
        "low_cpu_mem_usage": True,
    }

    if LLM_DIRECT_ATTN_IMPLEMENTATION:
        load_kwargs["attn_implementation"] = LLM_DIRECT_ATTN_IMPLEMENTATION

    return load_kwargs


def _load_model_with_fallback(
    *,
    auto_model: Any,
    model_path: Path,
    load_kwargs: dict[str, Any],
) -> tuple[Any, dict[str, Any]]:
    fallback_meta: dict[str, Any] = {
        "dtype_fallback_used": False,
        "attention_fallback_used": False,
        "attention_fallback_reason": "",
    }

    try:
        return auto_model.from_pretrained(str(model_path), **load_kwargs), fallback_meta
    except TypeError as exc:
        if "dtype" not in load_kwargs:
            raise

        fallback_kwargs = dict(load_kwargs)
        fallback_kwargs["torch_dtype"] = fallback_kwargs.pop("dtype")
        fallback_meta["dtype_fallback_used"] = True
        fallback_meta["dtype_fallback_reason"] = str(exc)

        try:
            return auto_model.from_pretrained(str(model_path), **fallback_kwargs), fallback_meta
        except Exception as fallback_exc:
            if "attn_implementation" not in fallback_kwargs:
                raise

            clean_message = str(fallback_exc).lower()
            attention_related = (
                "attn" in clean_message
                or "attention" in clean_message
                or "sdpa" in clean_message
                or "flash" in clean_message
            )

            if not attention_related:
                raise

            attention_kwargs = dict(fallback_kwargs)
            attention_kwargs.pop("attn_implementation", None)
            fallback_meta["attention_fallback_used"] = True
            fallback_meta["attention_fallback_reason"] = str(fallback_exc)

            return auto_model.from_pretrained(str(model_path), **attention_kwargs), fallback_meta
    except Exception as exc:
        if "attn_implementation" not in load_kwargs:
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
        fallback_kwargs.pop("attn_implementation", None)
        fallback_meta["attention_fallback_used"] = True
        fallback_meta["attention_fallback_reason"] = str(exc)

        return auto_model.from_pretrained(str(model_path), **fallback_kwargs), fallback_meta


def _load_tokenizer_only() -> tuple[Any, dict[str, Any]]:
    from transformers import AutoTokenizer

    from solomon_core.llm.llm_transport import (
        LLM_DIRECT_MODEL_PATH,
        LLM_DIRECT_REQUIRE_LOCAL_FILES,
        LLM_DIRECT_TRUST_REMOTE_CODE,
    )

    started_at = perf_counter()
    model_path = Path(LLM_DIRECT_MODEL_PATH)
    tokenizer = AutoTokenizer.from_pretrained(
        str(model_path),
        local_files_only=LLM_DIRECT_REQUIRE_LOCAL_FILES,
        trust_remote_code=LLM_DIRECT_TRUST_REMOTE_CODE,
    )

    if getattr(tokenizer, "pad_token", None) is None and getattr(tokenizer, "eos_token", None):
        tokenizer.pad_token = tokenizer.eos_token

    try:
        tokenizer.padding_side = "left"
    except Exception:
        pass

    return tokenizer, {
        "tokenizer_load_ms": _elapsed_ms(started_at),
        "model_files": _model_file_status(model_path),
        "tokenizer_class": tokenizer.__class__.__name__,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
        "padding_side": getattr(tokenizer, "padding_side", ""),
    }


def _load_model_only() -> tuple[Any, str, dict[str, Any]]:
    import torch
    from transformers import AutoModelForCausalLM

    from solomon_core.llm.llm_transport import (
        LLM_DIRECT_ATTN_IMPLEMENTATION,
        LLM_DIRECT_DEVICE,
        LLM_DIRECT_MODEL_PATH,
    )

    _enable_runtime_speed_flags(torch)
    model_path = Path(LLM_DIRECT_MODEL_PATH)
    device = _select_device(torch, LLM_DIRECT_DEVICE)
    load_kwargs = _build_model_load_kwargs(torch)

    load_started_at = perf_counter()
    model, fallback_meta = _load_model_with_fallback(
        auto_model=AutoModelForCausalLM,
        model_path=model_path,
        load_kwargs=load_kwargs,
    )
    load_elapsed_ms = _elapsed_ms(load_started_at)

    move_started_at = perf_counter()
    model.to(device)
    model.eval()

    if device == "cuda":
        torch.cuda.synchronize()

    move_elapsed_ms = _elapsed_ms(move_started_at)

    return model, device, {
        "device": device,
        "model_class": model.__class__.__name__,
        "model_files": _model_file_status(model_path),
        "attention_implementation_requested": LLM_DIRECT_ATTN_IMPLEMENTATION or "default",
        "model_load_ms": load_elapsed_ms,
        "model_to_device_ms": move_elapsed_ms,
        "load_kwargs_keys": sorted(load_kwargs.keys()),
        "fallback": fallback_meta,
        "cuda_memory": _cuda_memory_snapshot(torch),
    }


def _render_home_json_prompt(tokenizer: Any, prompt: str = DEFAULT_PROMPT) -> tuple[str, str]:
    rendered_prompt = str(prompt or DEFAULT_PROMPT).strip()

    if hasattr(tokenizer, "apply_chat_template"):
        try:
            rendered_prompt = tokenizer.apply_chat_template(
                [{"role": "user", "content": rendered_prompt}],
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:
            pass

    return (
        f"{rendered_prompt}\n{HOME_JSON_COMPLETION_INSTRUCTION}\n{HOME_JSON_PREFILL}",
        HOME_JSON_PREFILL,
    )


def _tokenize_home_prompt(
    tokenizer: Any,
    device: str | None = None,
    prompt: str = DEFAULT_PROMPT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    started_at = perf_counter()
    rendered_prompt, response_prefix = _render_home_json_prompt(tokenizer, prompt)

    inputs = tokenizer(
        rendered_prompt,
        return_tensors="pt",
        truncation=True,
        padding=False,
    )

    if device:
        inputs = {key: value.to(device) for key, value in inputs.items()}

    return inputs, {
        "prompt_chars": len(str(prompt or "")),
        "rendered_prompt_chars": len(rendered_prompt),
        "response_prefix": response_prefix,
        "response_prefix_chars": len(response_prefix),
        "input_tokens": int(inputs["input_ids"].shape[-1]),
        "tokenize_ms": _elapsed_ms(started_at),
    }


def _decode_generated_tokens(tokenizer: Any, generated_tokens: Any) -> str:
    try:
        return tokenizer.decode(
            generated_tokens,
            skip_special_tokens=True,
            clean_up_tokenization_spaces=False,
        ).strip()
    except TypeError:
        return tokenizer.decode(
            generated_tokens,
            skip_special_tokens=True,
        ).strip()


def _generate_once(
    *,
    torch: Any,
    model: Any,
    tokenizer: Any,
    inputs: dict[str, Any],
    device: str,
    generate_kwargs: dict[str, Any],
    response_prefix: str,
    run_label: str,
    mark_cudagraph_step: bool = False,
) -> dict[str, Any]:
    input_tokens = int(inputs["input_ids"].shape[-1])

    marked_step = False
    if mark_cudagraph_step:
        marked_step = _mark_cudagraph_step_if_available(torch)

    started_at = perf_counter()

    with torch.inference_mode():
        generated = model.generate(**inputs, **generate_kwargs)

    if device == "cuda":
        torch.cuda.synchronize()

    generate_elapsed_ms = _elapsed_ms(started_at)
    generated_tokens = generated[0][input_tokens:]
    generated_token_count = int(generated_tokens.shape[-1])
    text = _decode_generated_tokens(tokenizer, generated_tokens)

    if response_prefix and text and not text.startswith(response_prefix) and not text.startswith("{"):
        text = f"{response_prefix}{text}"

    return {
        "run_label": run_label,
        "cudagraph_step_marked": marked_step,
        "input_tokens": input_tokens,
        "generate_ms": generate_elapsed_ms,
        "generated_tokens": generated_token_count,
        "generated_tps": _tokens_per_second(generated_token_count, generate_elapsed_ms),
        "text_chars": len(text),
        "text_preview": text[:400],
    }


def _tokenizer_load_probe() -> dict[str, Any]:
    started_at = perf_counter()
    payload: dict[str, Any] = {
        "probe": "tokenizer_load",
        "ok": False,
    }

    try:
        _, meta = _load_tokenizer_only()
        payload.update(meta)
        payload["ok"] = True
    except Exception as exc:
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()

    payload["elapsed_ms"] = _elapsed_ms(started_at)
    return payload


def _model_load_probe() -> dict[str, Any]:
    started_at = perf_counter()
    payload: dict[str, Any] = {
        "probe": "model_load",
        "ok": False,
    }

    try:
        _, _, meta = _load_model_only()
        payload.update(meta)
        payload["ok"] = True
    except Exception as exc:
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()

    payload["elapsed_ms"] = _elapsed_ms(started_at)
    return payload


def _home_tokenize_probe() -> dict[str, Any]:
    started_at = perf_counter()
    payload: dict[str, Any] = {
        "probe": "home_tokenize",
        "ok": False,
    }

    try:
        tokenizer, tokenizer_meta = _load_tokenizer_only()
        _, tokenize_meta = _tokenize_home_prompt(tokenizer)
        payload.update(tokenizer_meta)
        payload.update(tokenize_meta)
        payload["ok"] = True
    except Exception as exc:
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()

    payload["elapsed_ms"] = _elapsed_ms(started_at)
    return payload


def _generation_probe(
    *,
    probe_name: str,
    use_static_cache: bool,
    compile_forward: bool,
    max_new_tokens: int,
    disable_cudagraphs: bool = False,
    mark_cudagraph_step: bool = False,
) -> dict[str, Any]:
    started_at = perf_counter()
    payload: dict[str, Any] = {
        "probe": probe_name,
        "ok": False,
        "compile_forward": compile_forward,
        "static_cache": use_static_cache,
        "disable_cudagraphs": disable_cudagraphs,
        "mark_cudagraph_step": mark_cudagraph_step,
        "max_new_tokens": max_new_tokens,
    }

    try:
        import torch

        from solomon_core.llm.llm_transport import LLM_DIRECT_TORCH_COMPILE_MODE

        _enable_runtime_speed_flags(torch)

        if disable_cudagraphs:
            payload["cudagraph_config"] = _configure_compile_without_cudagraphs(torch)

        tokenizer, tokenizer_meta = _load_tokenizer_only()
        model, device, model_meta = _load_model_only()
        inputs, tokenize_meta = _tokenize_home_prompt(tokenizer, device=device)

        payload.update(
            {
                "tokenizer": tokenizer_meta,
                "model": model_meta,
                "tokenize": tokenize_meta,
                "cuda_memory_before_generate": _cuda_memory_snapshot(torch),
            }
        )

        generate_kwargs: dict[str, Any] = {
            "max_new_tokens": max_new_tokens,
            "do_sample": False,
            "num_beams": 1,
            "repetition_penalty": 1.0,
            "use_cache": True,
            "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
            "eos_token_id": tokenizer.eos_token_id,
        }

        if use_static_cache:
            generate_kwargs["cache_implementation"] = "static"

        if compile_forward:
            if device != "cuda":
                raise RuntimeError(f"Compiled generation requires CUDA; selected device={device}.")

            if not hasattr(torch, "compile"):
                raise RuntimeError("torch.compile is unavailable.")

            if importlib.util.find_spec("triton") is None:
                raise RuntimeError("Triton is not importable in this runtime.")

            _enable_dynamo_safety(torch)
            compile_started_at = perf_counter()
            model.forward = torch.compile(
                model.forward,
                mode=LLM_DIRECT_TORCH_COMPILE_MODE,
            )
            payload["compile_install_ms"] = _elapsed_ms(compile_started_at)
            payload["compile_mode"] = LLM_DIRECT_TORCH_COMPILE_MODE

        first_run = _generate_once(
            torch=torch,
            model=model,
            tokenizer=tokenizer,
            inputs=inputs,
            device=device,
            generate_kwargs=generate_kwargs,
            response_prefix=tokenize_meta["response_prefix"],
            run_label="first",
            mark_cudagraph_step=mark_cudagraph_step,
        )

        second_run = _generate_once(
            torch=torch,
            model=model,
            tokenizer=tokenizer,
            inputs=inputs,
            device=device,
            generate_kwargs=generate_kwargs,
            response_prefix=tokenize_meta["response_prefix"],
            run_label="repeat",
            mark_cudagraph_step=mark_cudagraph_step,
        )

        payload.update(
            {
                "ok": True,
                "generate_kwargs_keys": sorted(generate_kwargs.keys()),
                "runs": [first_run, second_run],
                "cuda_memory_after_generate": _cuda_memory_snapshot(torch),
            }
        )
    except Exception as exc:
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()

    payload["elapsed_ms"] = _elapsed_ms(started_at)
    return payload


def _static_cache_shape_reuse_probe() -> dict[str, Any]:
    started_at = perf_counter()
    payload: dict[str, Any] = {
        "probe": "static_cache_shape_reuse",
        "ok": False,
        "static_cache": True,
        "compile_forward": False,
        "max_new_tokens": DEFAULT_GENERATION_TOKENS,
    }

    try:
        import torch

        _enable_runtime_speed_flags(torch)

        tokenizer, tokenizer_meta = _load_tokenizer_only()
        model, device, model_meta = _load_model_only()

        generate_kwargs: dict[str, Any] = {
            "max_new_tokens": DEFAULT_GENERATION_TOKENS,
            "do_sample": False,
            "num_beams": 1,
            "repetition_penalty": 1.0,
            "use_cache": True,
            "cache_implementation": "static",
            "pad_token_id": tokenizer.pad_token_id or tokenizer.eos_token_id,
            "eos_token_id": tokenizer.eos_token_id,
        }

        runs: list[dict[str, Any]] = []

        for label, prompt in STATIC_CACHE_SHAPE_PROMPTS:
            inputs, tokenize_meta = _tokenize_home_prompt(
                tokenizer,
                device=device,
                prompt=prompt,
            )
            run = _generate_once(
                torch=torch,
                model=model,
                tokenizer=tokenizer,
                inputs=inputs,
                device=device,
                generate_kwargs=generate_kwargs,
                response_prefix=tokenize_meta["response_prefix"],
                run_label=label,
            )
            run["tokenize"] = tokenize_meta
            runs.append(run)

        payload.update(
            {
                "ok": True,
                "tokenizer": tokenizer_meta,
                "model": model_meta,
                "generate_kwargs_keys": sorted(generate_kwargs.keys()),
                "runs": runs,
                "cuda_memory_after_generate": _cuda_memory_snapshot(torch),
            }
        )
    except Exception as exc:
        payload["error"] = str(exc)
        payload["traceback"] = traceback.format_exc()

    payload["elapsed_ms"] = _elapsed_ms(started_at)
    return payload


def _raw_generate_probe() -> dict[str, Any]:
    return _generation_probe(
        probe_name="raw_generate",
        use_static_cache=False,
        compile_forward=False,
        max_new_tokens=DEFAULT_GENERATION_TOKENS,
    )


def _static_cache_generate_probe() -> dict[str, Any]:
    return _generation_probe(
        probe_name="static_cache_generate",
        use_static_cache=True,
        compile_forward=False,
        max_new_tokens=DEFAULT_GENERATION_TOKENS,
    )


def _compiled_static_generate_probe() -> dict[str, Any]:
    return _generation_probe(
        probe_name="compiled_static_generate",
        use_static_cache=True,
        compile_forward=True,
        max_new_tokens=DEFAULT_GENERATION_TOKENS,
    )


def _compiled_static_no_cudagraphs_probe() -> dict[str, Any]:
    return _generation_probe(
        probe_name="compiled_static_no_cudagraphs",
        use_static_cache=True,
        compile_forward=True,
        max_new_tokens=DEFAULT_GENERATION_TOKENS,
        disable_cudagraphs=True,
        mark_cudagraph_step=True,
    )


def _run_child_probe(probe: str) -> dict[str, Any]:
    if probe == "environment":
        return _environment_probe()

    if probe == "simple_compile":
        return _simple_compile_probe()

    if probe == "tokenizer_load":
        return _tokenizer_load_probe()

    if probe == "model_load":
        return _model_load_probe()

    if probe == "home_tokenize":
        return _home_tokenize_probe()

    if probe == "raw_generate":
        return _raw_generate_probe()

    if probe == "static_cache_generate":
        return _static_cache_generate_probe()

    if probe == "static_cache_shape_reuse":
        return _static_cache_shape_reuse_probe()

    if probe == "compiled_static_generate":
        return _compiled_static_generate_probe()

    if probe == "compiled_static_no_cudagraphs":
        return _compiled_static_no_cudagraphs_probe()

    return {
        "probe": probe,
        "ok": False,
        "error": f"Unknown child probe: {probe}",
    }


def _child_main(args: argparse.Namespace) -> int:
    _print_json(_run_child_probe(args.child_probe), sentinel=True)
    return 0


def _extract_json_from_output(output: str) -> dict[str, Any]:
    clean_output = str(output or "").strip()

    if not clean_output:
        return {
            "ok": False,
            "error": "Child process returned no stdout.",
        }

    if JSON_BEGIN_MARKER in clean_output and JSON_END_MARKER in clean_output:
        start_index = clean_output.rfind(JSON_BEGIN_MARKER)
        end_index = clean_output.rfind(JSON_END_MARKER)

        if start_index >= 0 and end_index > start_index:
            json_text = clean_output[start_index + len(JSON_BEGIN_MARKER) : end_index].strip()

            try:
                return json.loads(json_text)
            except Exception as exc:
                return {
                    "ok": False,
                    "error": f"Could not parse marked child process JSON: {exc}",
                    "stdout": clean_output[-4000:],
                }

    start_index = clean_output.find("{")
    end_index = clean_output.rfind("}")

    if start_index < 0 or end_index < start_index:
        return {
            "ok": False,
            "error": "Child process stdout did not contain a JSON object.",
            "stdout": clean_output[-4000:],
        }

    try:
        return json.loads(clean_output[start_index : end_index + 1])
    except Exception as exc:
        return {
            "ok": False,
            "error": f"Could not parse child process JSON: {exc}",
            "stdout": clean_output[-4000:],
        }


def _run_parent_probe(
    *,
    probe: str,
    timeout_seconds: int,
    compile_enabled: bool = False,
) -> dict[str, Any]:
    command = [
        sys.executable,
        "-m",
        "solomon_core.llm.direct_runtime_diagnostics",
        "--child-probe",
        probe,
    ]

    started_at = perf_counter()

    try:
        completed = subprocess.run(
            command,
            cwd=str(_repo_root()),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )

        payload = _extract_json_from_output(completed.stdout)
        payload.update(
            {
                "parent_probe": probe,
                "child_returncode": completed.returncode,
                "child_timed_out": False,
                "child_stderr_tail": _tail(completed.stderr),
                "parent_elapsed_ms": _elapsed_ms(started_at),
            }
        )

        if completed.returncode != 0 and payload.get("ok") is True:
            payload["ok"] = False
            payload["error"] = (
                payload.get("error")
                or f"Child process exited with return code {completed.returncode}."
            )

        return payload
    except subprocess.TimeoutExpired as exc:
        return {
            "probe": probe,
            "parent_probe": probe,
            "ok": False,
            "child_timed_out": True,
            "timeout_seconds": timeout_seconds,
            "stdout_tail": _tail(exc.stdout),
            "stderr_tail": _tail(exc.stderr),
            "parent_elapsed_ms": _elapsed_ms(started_at),
            "error": "Child process timed out.",
        }
    except Exception as exc:
        return {
            "probe": probe,
            "parent_probe": probe,
            "ok": False,
            "child_timed_out": False,
            "parent_elapsed_ms": _elapsed_ms(started_at),
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }


def _selected_parent_probes(only_values: list[str]) -> list[tuple[str, bool]]:
    if not only_values:
        return list(PARENT_PROBES)

    selected = set(only_values)
    known = {probe for probe, _ in PARENT_PROBES}
    unknown = sorted(selected - known)

    if unknown:
        raise ValueError(f"Unknown probe(s): {', '.join(unknown)}")

    return [(probe, compile_enabled) for probe, compile_enabled in PARENT_PROBES if probe in selected]


def _parent_main(args: argparse.Namespace) -> int:
    started_at = perf_counter()
    timeout_seconds = max(30, int(args.timeout))
    probes = _selected_parent_probes(args.only or [])
    results: list[dict[str, Any]] = []

    for probe, compile_enabled in probes:
        print(
            f"[DIRECT_RUNTIME_DIAGNOSTICS] starting probe={probe} "
            f"compile_enabled={compile_enabled}",
            flush=True,
        )
        result = _run_parent_probe(
            probe=probe,
            timeout_seconds=timeout_seconds,
            compile_enabled=compile_enabled,
        )
        results.append(result)
        _print_json(result)

    summary = {
        "probe": "summary",
        "ok": all(bool(result.get("ok")) for result in results),
        "timeout_seconds": timeout_seconds,
        "python_executable": sys.executable,
        "elapsed_ms": _elapsed_ms(started_at),
        "results": [
            {
                "probe": result.get("probe") or result.get("parent_probe"),
                "ok": bool(result.get("ok")),
                "timed_out": bool(result.get("child_timed_out")),
                "error": result.get("error", ""),
            }
            for result in results
        ],
    }

    print("[DIRECT_RUNTIME_DIAGNOSTICS] summary", flush=True)
    _print_json(summary)

    return 0 if summary["ok"] else 1


def _parse_args() -> argparse.Namespace:
    child_choices = [probe for probe, _ in PARENT_PROBES]
    parser = argparse.ArgumentParser(
        description="Run isolated SolomonAI direct model runtime diagnostics."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Seconds allowed for each child probe.",
    )
    parser.add_argument(
        "--only",
        action="append",
        choices=child_choices,
        default=[],
        help="Run only the named parent probe. May be provided multiple times.",
    )
    parser.add_argument(
        "--child-probe",
        choices=child_choices,
        default="",
        help=argparse.SUPPRESS,
    )

    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    if args.child_probe:
        return _child_main(args)

    return _parent_main(args)


if __name__ == "__main__":
    raise SystemExit(main())