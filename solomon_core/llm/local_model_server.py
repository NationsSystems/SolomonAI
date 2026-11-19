# ---------------------------------------------------------------------------
# FILE: solomon_core/llm/local_model_server.py
# DIRECTORY: solomon_core/llm/
# ---------------------------------------------------------------------------
# Local Model Server
#
# PURPOSE
#   Provide a self-hosted HTTP boundary for Solomon-owned local model execution.
#
# CONTRACT
#   - This process owns local model execution directly.
#   - This process does not route, classify, decide workflow, or interpret
#     governed business facts.
#   - The caller sends an already-authorized prompt and receives generated text.
#   - The default bind address is loopback only.
#   - Private-host deployment must be explicit in config.py.
# ---------------------------------------------------------------------------

from __future__ import annotations

import sys
import time
from pathlib import Path
from threading import Lock
from typing import Any

from flask import Flask, jsonify, request


# ---------------------------------------------------------------------------
# Direct Execution Guard
# ---------------------------------------------------------------------------

if __package__ in {None, ""}:
    project_root = Path(__file__).resolve().parents[2]
    project_root_text = str(project_root)
    if project_root_text not in sys.path:
        sys.path.insert(0, project_root_text)

from config import settings  # noqa: E402
from solomon_core.llm.direct_model_runner import run_direct_generation  # noqa: E402
from solomon_core.logger import get_logger  # noqa: E402

logger = get_logger("local_model_server")


# ---------------------------------------------------------------------------
# Server Constants
# ---------------------------------------------------------------------------

SERVICE_NAME = "solomon_local_model_server"
TRANSPORT_CONTRACT = "solomon_local_model_server_v1"
DEFAULT_BIND_HOST = "127.0.0.1"
DEFAULT_BIND_PORT = 8765
_ALLOWED_RESPONSE_FORMATS = frozenset({"text", "json_object"})
_GENERATION_LOCK = Lock()


# ---------------------------------------------------------------------------
# Config Helpers
# ---------------------------------------------------------------------------

def _server_bind_host() -> str:
    requested_host = str(
        getattr(settings, "LLM_LOCAL_MODEL_SERVER_BIND_HOST", DEFAULT_BIND_HOST)
    ).strip()

    return requested_host or DEFAULT_BIND_HOST


def _server_bind_port() -> int:
    try:
        port = int(getattr(settings, "LLM_LOCAL_MODEL_SERVER_BIND_PORT", DEFAULT_BIND_PORT))
    except Exception:
        port = DEFAULT_BIND_PORT

    return max(1, min(port, 65535))


def _max_prompt_chars() -> int:
    try:
        prompt_limit = int(
            getattr(settings, "LLM_LOCAL_MODEL_SERVER_MAX_PROMPT_CHARS", 12000)
        )
    except Exception:
        prompt_limit = 12000

    return max(1, prompt_limit)


def _allow_non_loopback_bind() -> bool:
    return bool(
        getattr(settings, "LLM_LOCAL_MODEL_SERVER_ALLOW_NON_LOOPBACK_BIND", False)
    )


def _warm_on_boot() -> bool:
    return bool(getattr(settings, "LLM_LOCAL_MODEL_SERVER_WARM_ON_BOOT", True))


def _warmup_prompt() -> str:
    prompt = str(getattr(settings, "LLM_LOCAL_MODEL_SERVER_WARMUP_PROMPT", "ready")).strip()

    return prompt or "ready"


def _warmup_call_site() -> str:
    call_site = str(
        getattr(
            settings,
            "LLM_LOCAL_MODEL_SERVER_WARMUP_CALL_SITE",
            "solomon_visual_conductor",
        )
    ).strip()

    return call_site or "solomon_visual_conductor"


# ---------------------------------------------------------------------------
# Payload Helpers
# ---------------------------------------------------------------------------

def _json_error(message: str, status_code: int):
    return jsonify(
        {
            "ok": False,
            "service": SERVICE_NAME,
            "error": message,
        }
    ), status_code


def _request_json() -> dict[str, Any] | None:
    try:
        data = request.get_json(silent=True)
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    return data


def _clean_prompt(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    return value.strip()


def _clean_response_format(value: Any) -> str:
    clean_value = str(value or "text").strip().lower()

    if clean_value not in _ALLOWED_RESPONSE_FORMATS:
        return "text"

    return clean_value


def _clean_call_site(value: Any) -> str:
    clean_value = str(value or "local_model_server").strip()

    return clean_value or "local_model_server"


def _clean_model_name(value: Any) -> str:
    clean_value = str(value or "").strip()

    if clean_value:
        return clean_value

    return str(getattr(settings, "LLM_DIRECT_MODEL_NAME", "solomon_custom_llm_v1"))


def _requested_stream(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on", "enabled"}

    return bool(value)


# ---------------------------------------------------------------------------
# Flask App
# ---------------------------------------------------------------------------

app = Flask(__name__)


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "service": SERVICE_NAME,
            "transport_contract": TRANSPORT_CONTRACT,
            "model": str(getattr(settings, "LLM_DIRECT_MODEL_NAME", "solomon_custom_llm_v1")),
            "bind_host": _safe_bind_host(),
            "bind_port": _server_bind_port(),
            "warm_on_boot": _warm_on_boot(),
        }
    )


@app.post("/generate")
def generate():
    payload = _request_json()

    if payload is None:
        return _json_error("Request body must be a JSON object.", 400)

    prompt = _clean_prompt(payload.get("prompt"))

    if not prompt:
        return _json_error("Prompt is required.", 400)

    prompt_limit = _max_prompt_chars()

    if len(prompt) > prompt_limit:
        return _json_error(
            f"Prompt exceeds local server limit of {prompt_limit} characters.",
            413,
        )

    if _requested_stream(payload.get("stream", False)):
        return _json_error("Streaming is not enabled for this local server endpoint.", 400)

    model_name = _clean_model_name(payload.get("model"))
    response_format = _clean_response_format(payload.get("response_format"))
    call_site = _clean_call_site(payload.get("call_site"))
    started_at = time.perf_counter()

    logger.info(
        "[LOCAL_MODEL_SERVER][REQUEST] model=%s call_site=%s response_format=%s "
        "prompt_chars=%s contract=%s",
        model_name,
        call_site,
        response_format,
        len(prompt),
        payload.get("transport_contract", ""),
    )

    with _GENERATION_LOCK:
        result = run_direct_generation(
            prompt=prompt,
            call_site=call_site,
            response_format=response_format,
        )

    elapsed_ms = (time.perf_counter() - started_at) * 1000.0

    if not result.ok:
        logger.error(
            "[LOCAL_MODEL_SERVER][FAIL] call_site=%s elapsed_ms=%.2f error=%s",
            call_site,
            elapsed_ms,
            result.error,
        )
        return jsonify(
            {
                "ok": False,
                "service": SERVICE_NAME,
                "error": result.error or "Local model generation failed.",
                "elapsed_ms": round(elapsed_ms, 2),
            }
        ), 500

    text = (result.text or "").strip()

    if not text:
        logger.warning(
            "[LOCAL_MODEL_SERVER][EMPTY] call_site=%s elapsed_ms=%.2f",
            call_site,
            elapsed_ms,
        )
        return jsonify(
            {
                "ok": False,
                "service": SERVICE_NAME,
                "error": "Local model returned empty text.",
                "elapsed_ms": round(elapsed_ms, 2),
            }
        ), 502

    logger.info(
        "[LOCAL_MODEL_SERVER][OK] call_site=%s elapsed_ms=%.2f output_chars=%s",
        call_site,
        elapsed_ms,
        len(text),
    )

    return jsonify(
        {
            "ok": True,
            "service": SERVICE_NAME,
            "transport_contract": TRANSPORT_CONTRACT,
            "model": model_name,
            "text": text,
            "elapsed_ms": round(elapsed_ms, 2),
            "proof": result.proof,
        }
    )


# ---------------------------------------------------------------------------
# Warmup + Entrypoint
# ---------------------------------------------------------------------------

def _safe_bind_host() -> str:
    host = _server_bind_host()

    if host in {"127.0.0.1", "localhost", "::1"}:
        return host

    if _allow_non_loopback_bind():
        logger.warning(
            "[LOCAL_MODEL_SERVER][PRIVATE_BIND_ENABLED] host=%s",
            host,
        )
        return host

    logger.warning(
        "[LOCAL_MODEL_SERVER][BIND_RESTRICTED] requested_host=%s fallback_host=%s",
        host,
        DEFAULT_BIND_HOST,
    )
    return DEFAULT_BIND_HOST


def _warm_model() -> None:
    if not _warm_on_boot():
        logger.info("[LOCAL_MODEL_SERVER][WARMUP_SKIPPED] config_disabled")
        return

    prompt = _warmup_prompt()
    call_site = _warmup_call_site()
    started_at = time.perf_counter()

    logger.info(
        "[LOCAL_MODEL_SERVER][WARMUP_START] call_site=%s prompt_chars=%s",
        call_site,
        len(prompt),
    )

    with _GENERATION_LOCK:
        result = run_direct_generation(
            prompt=prompt,
            call_site=call_site,
            response_format="text",
        )

    elapsed_ms = (time.perf_counter() - started_at) * 1000.0

    if not result.ok:
        logger.error(
            "[LOCAL_MODEL_SERVER][WARMUP_FAIL] elapsed_ms=%.2f error=%s",
            elapsed_ms,
            result.error,
        )
        return

    logger.info(
        "[LOCAL_MODEL_SERVER][WARMUP_OK] elapsed_ms=%.2f output_chars=%s",
        elapsed_ms,
        len((result.text or "").strip()),
    )


def main() -> None:
    host = _safe_bind_host()
    port = _server_bind_port()

    logger.info(
        "[LOCAL_MODEL_SERVER][BOOT] host=%s port=%s contract=%s",
        host,
        port,
        TRANSPORT_CONTRACT,
    )

    _warm_model()

    app.run(
        host=host,
        port=port,
        debug=False,
        threaded=True,
        use_reloader=False,
    )


if __name__ == "__main__":
    main()