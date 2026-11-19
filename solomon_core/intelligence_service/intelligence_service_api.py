# -------------------------------------------------------------------
# FILE: intelligence_service_api.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# HTTP boundary for the separately running Solomon Intelligence Service.
# The service owns heavy model execution. It owns no user/file authority.
# -------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, timezone
import json
from queue import Queue
import secrets
import time
from threading import RLock, Thread
from typing import Any

from flask import Flask, Response, jsonify, request, stream_with_context

from config import settings
from solomon_core.logger import get_logger
from solomon_core.llm.llm_executor import (
    get_llm_capacity_snapshot,
    warm_direct_model_worker,
    warm_direct_runtime_profile_worker,
)
from solomon_core.llm.llm_transport import direct_model_files_available

from .embedding_executor import get_embedding_capacity_snapshot
from .portable_compute_dispatch import (
    execute_embeddings_on_configured_compute,
    execute_llm_on_configured_compute,
    get_configured_compute_health,
    remote_compute_enabled,
    warm_configured_compute_runtime,
)
from .intelligence_service_contract import (
    IntelligenceRequestClass,
    IntelligenceServiceStatus,
    deserialize_embedding_input,
    deserialize_llm_input,
    parse_intelligence_request_class,
    serialize_embedding_result,
    serialize_llm_result,
)
from .intelligence_completion_events import (
    INTELLIGENCE_RESYNC_EVENT_TYPE,
    get_intelligence_completion_event_cursor,
    wait_for_intelligence_completion_events,
)


logger = get_logger("intelligence_service.api")
_SIS_KEY_HEADER = "X-Solomon-SIS-Key"

_STATE_LOCK = RLock()
_WARMUP_THREAD: Thread | None = None
_SERVICE_STATE: dict[str, Any] = {
    "status": IntelligenceServiceStatus.STARTING.value,
    "stage": "service_starting",
    "interactive_ready": False,
    "base_model_ready": False,
    "profile_warmup_status": "pending",
    "error": "",
    "updated_at": datetime.now(timezone.utc).isoformat(),
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _authorized_request() -> bool:
    expected = str(settings.SIS_SHARED_SECRET or "")
    provided = str(request.headers.get(_SIS_KEY_HEADER) or "")
    return bool(expected) and secrets.compare_digest(expected, provided)


def _error(message: str, status_code: int, **details):
    payload = {"ok": False, "error": message}
    payload.update(details)
    return jsonify(payload), status_code


def _update_service_state(**changes: Any) -> dict[str, Any]:
    with _STATE_LOCK:
        _SERVICE_STATE.update(changes)
        _SERVICE_STATE["updated_at"] = _utc_now_iso()
        return dict(_SERVICE_STATE)


def get_intelligence_service_readiness() -> dict[str, Any]:
    """Return one thread-safe, read-only SIS readiness snapshot."""

    with _STATE_LOCK:
        return dict(_SERVICE_STATE)


def _warm_base_model() -> dict[str, Any]:
    model_result = warm_direct_model_worker(call_site="sis_boot_warmup")

    if not getattr(model_result, "ok", False):
        return {
            "ok": False,
            "stage": "model",
            "error": str(getattr(model_result, "error", "") or "warmup failed"),
        }

    return {
        "ok": True,
        "stage": "model",
    }


def _warm_optional_runtime_profile() -> dict[str, Any]:
    if not bool(settings.DIRECT_GENERATION_WARMUP_ENABLED):
        return {
            "ok": True,
            "stage": "runtime_profile",
            "profile_warmup": "disabled",
        }

    if not bool(settings.SIS_BOOT_PROFILE_WARMUP_ENABLED):
        return {
            "ok": True,
            "stage": "runtime_profile",
            "profile_warmup": "deferred",
        }

    profile_result = warm_direct_runtime_profile_worker(
        call_site=str(settings.SIS_WARMUP_CALL_SITE),
        runtime_profile=str(settings.SIS_WARMUP_RUNTIME_PROFILE),
        max_new_tokens=int(settings.SIS_WARMUP_MAX_NEW_TOKENS),
        warmup_prompt=str(settings.SIS_WARMUP_SOURCE_SEED),
        target_input_tokens=int(settings.SIS_WARMUP_TARGET_INPUT_TOKENS),
        request_class=IntelligenceRequestClass.BACKGROUND.value,
    )

    return {
        "ok": bool(getattr(profile_result, "ok", False)),
        "stage": "runtime_profile",
        "error": str(getattr(profile_result, "error", "") or ""),
    }


def _run_runtime_warmup() -> None:
    """Warm configured compute without blocking the SIS HTTP listener."""

    if remote_compute_enabled():
        _update_service_state(
            status=IntelligenceServiceStatus.WARMING.value,
            stage="remote_compute_warmup",
            interactive_ready=False,
            base_model_ready=False,
            profile_warmup_status="remote",
            error="",
        )
        warm_result = warm_configured_compute_runtime()
        if not bool(warm_result.get("ok")):
            _update_service_state(
                status=IntelligenceServiceStatus.DEGRADED.value,
                stage="remote_compute_unavailable",
                interactive_ready=False,
                base_model_ready=False,
                profile_warmup_status="remote",
                error=str(warm_result.get("error") or "Remote compute warmup failed."),
            )
            return

        deadline = time.monotonic() + max(
            1,
            int(settings.SIS_WARMUP_TIMEOUT_SECONDS),
        )
        while time.monotonic() < deadline:
            health = get_configured_compute_health()
            if bool(health.get("interactive_ready")):
                _update_service_state(
                    status=IntelligenceServiceStatus.READY.value,
                    stage="remote_compute_ready",
                    interactive_ready=True,
                    base_model_ready=bool(health.get("base_model_ready", True)),
                    profile_warmup_status=str(
                        health.get("profile_warmup_status") or "remote"
                    ),
                    error="",
                )
                logger.info("[SIS][READY] stage=remote_compute_ready")
                return
            time.sleep(0.5)

        _update_service_state(
            status=IntelligenceServiceStatus.DEGRADED.value,
            stage="remote_compute_warmup_timeout",
            interactive_ready=False,
            base_model_ready=False,
            profile_warmup_status="remote",
            error="Remote Portable SIS compute did not become ready in time.",
        )
        return

    if not bool(settings.LLM_WARMUP_ENABLED):
        _update_service_state(
            status=IntelligenceServiceStatus.READY.value,
            stage="warmup_disabled",
            interactive_ready=True,
            base_model_ready=False,
            profile_warmup_status="disabled",
            error="",
        )
        logger.info("[SIS][READY] warmup=disabled_by_configuration")
        return

    _update_service_state(
        status=IntelligenceServiceStatus.WARMING.value,
        stage="base_model_warmup",
        interactive_ready=False,
        base_model_ready=False,
        profile_warmup_status="pending",
        error="",
    )

    try:
        base_result = _warm_base_model()
    except Exception as exc:
        logger.exception("[SIS][BASE_MODEL_WARMUP_FAILURE]")
        base_result = {
            "ok": False,
            "stage": "model",
            "error": str(exc),
        }

    if not base_result.get("ok"):
        _update_service_state(
            status=IntelligenceServiceStatus.DEGRADED.value,
            stage=str(base_result.get("stage") or "model"),
            interactive_ready=False,
            base_model_ready=False,
            profile_warmup_status="not_started",
            error=str(base_result.get("error") or "Model warmup failed."),
        )
        logger.warning(
            "[SIS][DEGRADED] stage=%s error=%s",
            base_result.get("stage"),
            base_result.get("error"),
        )
        return

    # Base-model readiness is the interactive capability boundary. Optional
    # runtime-profile warmup is only an optimization and may not hold READY
    # hostage.
    if not bool(settings.DIRECT_GENERATION_WARMUP_ENABLED):
        profile_status = "disabled"
    elif not bool(settings.SIS_BOOT_PROFILE_WARMUP_ENABLED):
        profile_status = "deferred"
    else:
        profile_status = "pending"
    _update_service_state(
        status=IntelligenceServiceStatus.READY.value,
        stage="base_model_ready",
        interactive_ready=True,
        base_model_ready=True,
        profile_warmup_status=profile_status,
        error="",
    )
    logger.info("[SIS][READY] stage=base_model_ready")

    if (
        not bool(settings.DIRECT_GENERATION_WARMUP_ENABLED)
        or not bool(settings.SIS_BOOT_PROFILE_WARMUP_ENABLED)
    ):
        return

    _update_service_state(profile_warmup_status="warming")

    try:
        profile_result = _warm_optional_runtime_profile()
    except Exception as exc:
        logger.exception("[SIS][PROFILE_WARMUP_FAILURE]")
        profile_result = {
            "ok": False,
            "stage": "runtime_profile",
            "error": str(exc),
        }

    if profile_result.get("ok"):
        _update_service_state(
            profile_warmup_status="ready",
            stage="ready",
        )
        logger.info("[SIS][PROFILE_WARMUP_READY]")
        return

    # Optional profile preparation failure does not revoke base-model
    # readiness. The authorized execution path may still initialize that
    # profile lazily when it is later needed.
    _update_service_state(
        profile_warmup_status="failed",
        stage="ready",
    )
    logger.warning(
        "[SIS][PROFILE_WARMUP_DEGRADED] error=%s",
        profile_result.get("error"),
    )


def start_intelligence_service_runtime_warmup() -> dict[str, Any]:
    """Start at most one asynchronous SIS runtime warmup attempt."""

    global _WARMUP_THREAD

    with _STATE_LOCK:
        if _WARMUP_THREAD is not None and _WARMUP_THREAD.is_alive():
            snapshot = dict(_SERVICE_STATE)
            snapshot["warmup_started"] = False
            return snapshot

        if (
            _SERVICE_STATE.get("status") == IntelligenceServiceStatus.READY.value
            and _SERVICE_STATE.get("base_model_ready")
        ):
            snapshot = dict(_SERVICE_STATE)
            snapshot["warmup_started"] = False
            return snapshot

        _SERVICE_STATE.update({
            "status": IntelligenceServiceStatus.WARMING.value,
            "stage": "warmup_scheduled",
            "interactive_ready": False,
            "error": "",
            "updated_at": _utc_now_iso(),
        })

        _WARMUP_THREAD = Thread(
            target=_run_runtime_warmup,
            name="sis-runtime-warmup",
            daemon=True,
        )
        _WARMUP_THREAD.start()

        snapshot = dict(_SERVICE_STATE)
        snapshot["warmup_started"] = True
        return snapshot


def _spool_worker_health_snapshot(app: Flask) -> dict[str, Any]:
    worker = app.extensions.get("solomon_intelligence_spool_worker")
    startup_error = str(
        app.extensions.get("solomon_intelligence_spool_worker_error") or ""
    ).strip()

    if worker is not None:
        try:
            return worker.get_snapshot()
        except Exception as exc:
            logger.exception("[SIS][SPOOL_WORKER_HEALTH_FAILURE]")
            startup_error = str(exc)

    enabled = bool(getattr(settings, "SIS_SPOOL_WORKER_ENABLED", False))
    starting = bool(
        app.extensions.get("solomon_intelligence_spool_worker_starting")
    )
    return {
        "enabled": enabled,
        "running": False,
        "status": (
            "starting"
            if enabled and starting
            else ("unavailable" if enabled else "disabled")
        ),
        "worker_id": None,
        "supported_job_types": [],
        "eligible_job_types": [],
        "current_job_id": None,
        "current_job_type": None,
        "last_error": startup_error,
    }


def create_intelligence_service_app() -> Flask:
    app = Flask("solomon_intelligence_service")

    @app.before_request
    def _require_internal_key():
        if _authorized_request():
            return None
        return _error("Unauthorized SIS request.", 401)

    @app.get("/health")
    def health():
        readiness = get_intelligence_service_readiness()
        compute_health = get_configured_compute_health()
        return jsonify({
            "ok": True,
            "service": "solomon_intelligence_service",
            **readiness,
            "compute_mode": str(settings.SIS_COMPUTE_MODE or "local"),
            "compute": compute_health,
            "direct_model_files_available": (
                None
                if remote_compute_enabled()
                else direct_model_files_available()
            ),
            "capacity": (
                compute_health.get("capacity")
                if remote_compute_enabled()
                else get_llm_capacity_snapshot()
            ),
            "embedding": (
                compute_health.get("embedding")
                if remote_compute_enabled()
                else get_embedding_capacity_snapshot()
            ),
            "spool_worker": _spool_worker_health_snapshot(app),
        })

    @app.post("/warmup")
    def warmup():
        result = start_intelligence_service_runtime_warmup()
        return jsonify({"ok": True, **result}), 202

    @app.get("/v1/events/completions")
    def stream_intelligence_completion_events_api():
        """Stream post-commit SIS completion signals to authenticated web peers."""

        after_supplied = "after" in request.args
        after_event_id = str(request.args.get("after") or "").strip()
        if not after_supplied:
            after_event_id = get_intelligence_completion_event_cursor()

        heartbeat_seconds = max(
            1.0,
            float(settings.SIS_EVENT_STREAM_HEARTBEAT_SECONDS),
        )

        @stream_with_context
        def _generate_completion_events():
            cursor = after_event_id or "0"

            while True:
                batch = wait_for_intelligence_completion_events(
                    cursor,
                    timeout_seconds=heartbeat_seconds,
                )

                if batch.get("resync_required"):
                    latest_event_id = str(
                        batch.get("latest_event_id") or cursor or "0"
                    )
                    cursor = latest_event_id
                    yield json.dumps({
                        "type": INTELLIGENCE_RESYNC_EVENT_TYPE,
                        "event_id": latest_event_id,
                    }, separators=(",", ":")) + "\n"
                    continue

                events = batch.get("events") or []
                if events:
                    for event in events:
                        event_id = str(event.get("event_id") or cursor or "0")
                        cursor = event_id
                        yield json.dumps(
                            event,
                            separators=(",", ":"),
                        ) + "\n"
                    continue

                yield json.dumps({
                    "type": "heartbeat",
                    "event_id": str(batch.get("latest_event_id") or cursor or "0"),
                    "timestamp": _utc_now_iso(),
                }, separators=(",", ":")) + "\n"

        return Response(
            _generate_completion_events(),
            mimetype="application/x-ndjson",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    @app.post("/v1/embeddings/execute")
    def execute_embeddings_api():
        if not bool(settings.SIS_EMBEDDING_ENABLED):
            return _error(
                "SIS embedding execution is disabled.",
                503,
                embedding_ready=False,
            )

        readiness = get_intelligence_service_readiness()
        if not bool(readiness.get("interactive_ready")):
            status = str(
                readiness.get("status")
                or IntelligenceServiceStatus.UNAVAILABLE.value
            )
            if status == IntelligenceServiceStatus.WARMING.value:
                message = "Solomon is warming up. Please try again shortly."
            else:
                message = "Solomon intelligence is temporarily unavailable."
            return _error(
                message,
                503,
                status=status,
                embedding_ready=False,
            )

        payload = request.get_json(silent=True) or {}

        try:
            texts, call_site = deserialize_embedding_input(
                payload.get("request") or {}
            )
            request_class = parse_intelligence_request_class(
                payload.get("request_class")
            )
        except Exception as exc:
            return _error(f"Invalid SIS embedding request: {exc}", 400)

        if request_class is not IntelligenceRequestClass.INTERACTIVE:
            return _error(
                "HTTP embedding execution accepts interactive requests only.",
                400,
            )

        max_batch_size = max(1, int(settings.SIS_EMBEDDING_MAX_BATCH_SIZE))
        if len(texts) > max_batch_size:
            return _error(
                "SIS embedding request exceeds the configured batch limit.",
                400,
                max_batch_size=max_batch_size,
            )

        try:
            vectors = execute_embeddings_on_configured_compute(
                texts,
                call_site=call_site,
                request_class=request_class.value,
            )
        except Exception as exc:
            logger.exception(
                "[SIS][EMBEDDING_EXECUTION_FAILURE] call_site=%s count=%s",
                call_site or "unspecified",
                len(texts),
            )
            return _error(
                f"SIS embedding execution failed: {exc}",
                503,
                embedding_ready=False,
            )

        return jsonify({
            "ok": True,
            "result": serialize_embedding_result(
                vectors,
                model_name=settings.WORKSPACE_ACTION_SELECTOR_MODEL_NAME,
                dimension=int(settings.EMBED_DIM),
            ),
        })

    @app.post("/v1/llm/execute")
    def execute_llm_api():
        readiness = get_intelligence_service_readiness()
        if not bool(readiness.get("interactive_ready")):
            status = str(
                readiness.get("status")
                or IntelligenceServiceStatus.UNAVAILABLE.value
            )
            if status == IntelligenceServiceStatus.WARMING.value:
                message = "Solomon is warming up. Please try again shortly."
            else:
                message = "Solomon intelligence is temporarily unavailable."
            return _error(
                message,
                503,
                status=status,
                interactive_ready=False,
            )

        payload = request.get_json(silent=True) or {}

        try:
            input_packet = deserialize_llm_input(payload.get("request") or {})
            request_class = parse_intelligence_request_class(
                payload.get("request_class")
            )
        except Exception as exc:
            return _error(f"Invalid SIS LLM request: {exc}", 400)

        if not bool(payload.get("stream")):
            result = execute_llm_on_configured_compute(
                input_packet,
                request_class=request_class.value,
            )
            return jsonify({
                "ok": result.is_success(),
                "result": serialize_llm_result(result),
            })

        event_queue: Queue[dict] = Queue()
        done_marker = object()

        def _stream_callback(chunk: str) -> None:
            if chunk:
                event_queue.put({"type": "chunk", "text": chunk})

        def _run_execution() -> None:
            try:
                result = execute_llm_on_configured_compute(
                    input_packet,
                    stream_callback=_stream_callback,
                    request_class=request_class.value,
                )
                event_queue.put({
                    "type": "result",
                    "result": serialize_llm_result(result),
                })
            except Exception as exc:
                logger.exception("[SIS][STREAM_EXECUTION_FAILURE]")
                event_queue.put({
                    "type": "result",
                    "result": {
                        "output": None,
                        "failure": {
                            "reason": "internal_error",
                            "message": str(exc),
                        },
                    },
                })
            finally:
                event_queue.put(done_marker)

        worker = Thread(
            target=_run_execution,
            name="sis-llm-http-stream",
            daemon=True,
        )
        worker.start()

        @stream_with_context
        def _generate():
            while True:
                event = event_queue.get()
                if event is done_marker:
                    break
                yield json.dumps(event, separators=(",", ":")) + "\n"

        return Response(
            _generate(),
            mimetype="application/x-ndjson",
            headers={"Cache-Control": "no-cache, no-transform"},
        )

    return app


def warm_intelligence_service_runtime() -> dict[str, Any]:
    """Compatibility wrapper for callers that need one warmup attempt."""

    return start_intelligence_service_runtime_warmup()
