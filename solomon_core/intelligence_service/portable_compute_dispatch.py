# -------------------------------------------------------------------
# FILE: portable_compute_dispatch.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Single location-selection boundary for Portable SIS compute. Local Solomon
# state and spool ownership remain outside this module; only already-bounded
# LLM and embedding work crosses to a configured remote node.
# -------------------------------------------------------------------

from __future__ import annotations

from typing import Callable, Iterable

from config import settings
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionInput,
    LLMExecutionResult,
)

from .intelligence_service_contract import IntelligencePriority
from .portable_compute_client import (
    execute_embeddings_on_remote_compute,
    execute_llm_on_remote_compute,
    get_remote_compute_health,
    warm_remote_compute_runtime,
)


def get_portable_compute_mode() -> str:
    return str(settings.SIS_COMPUTE_MODE or "local").strip().lower()


def remote_compute_enabled() -> bool:
    return get_portable_compute_mode() == "remote"


def get_configured_compute_health() -> dict:
    if not remote_compute_enabled():
        return {
            "ok": True,
            "status": "local",
            "interactive_ready": True,
            "mode": "local",
        }

    payload = get_remote_compute_health()
    payload = dict(payload) if isinstance(payload, dict) else {}
    payload["mode"] = "remote"
    return payload


def warm_configured_compute_runtime() -> dict:
    if not remote_compute_enabled():
        return {
            "ok": True,
            "status": "local",
            "interactive_ready": True,
            "mode": "local",
        }

    payload = warm_remote_compute_runtime()
    payload = dict(payload) if isinstance(payload, dict) else {}
    payload["mode"] = "remote"
    return payload


def execute_embeddings_on_configured_compute(
    texts: Iterable[str],
    *,
    call_site: str | None = None,
    priority: str | IntelligencePriority = IntelligencePriority.P0,
    request_id: str | None = None,
    fairness_bucket: str | None = None,
    request_class: str | None = None,
) -> list[list[float]]:
    effective_priority = (
        "P3"
        if str(request_class or "").strip().lower() == "background"
        else priority
    )
    if remote_compute_enabled():
        return execute_embeddings_on_remote_compute(
            texts,
            call_site=call_site,
            priority=effective_priority,
            request_id=request_id,
            fairness_bucket=fairness_bucket,
        )

    from .embedding_executor import execute_embeddings_on_local_runtime

    return execute_embeddings_on_local_runtime(texts)


def execute_llm_on_configured_compute(
    input_packet: LLMExecutionInput,
    *,
    stream_callback: Callable[[str], None] | None = None,
    priority: str | IntelligencePriority = IntelligencePriority.P0,
    request_id: str | None = None,
    fairness_bucket: str | None = None,
    request_class: str | None = None,
) -> LLMExecutionResult:
    effective_priority = (
        "P3"
        if str(request_class or "").strip().lower() == "background"
        else priority
    )
    if remote_compute_enabled():
        return execute_llm_on_remote_compute(
            input_packet,
            stream_callback=stream_callback,
            priority=effective_priority,
            request_id=request_id,
            fairness_bucket=fairness_bucket,
        )

    from solomon_core.llm.llm_executor import execute_llm_on_local_runtime

    normalized_priority = str(getattr(effective_priority, "value", effective_priority)).strip().upper()
    return execute_llm_on_local_runtime(
        input_packet,
        stream_callback=stream_callback,
        request_class=(
            "background"
            if normalized_priority in {"P2", "P3"}
            else "interactive"
        ),
    )
