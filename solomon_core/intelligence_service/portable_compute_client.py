# -------------------------------------------------------------------
# FILE: portable_compute_client.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Bounded transport from the local Solomon Intelligence Service coordinator
# to an optional Portable SIS compute node. This client carries computation
# only; it never carries database credentials, authorization state, or durable
# product ownership.
# -------------------------------------------------------------------

from __future__ import annotations

import json
import socket
import time
import uuid
from typing import Callable, Iterable
from urllib import error as urllib_error
from urllib import request as urllib_request

from config import settings
from solomon_core.logger import get_logger
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionFailure,
    LLMExecutionInput,
    LLMExecutionResult,
    LLMFailureReason,
)

from .intelligence_service_contract import (
    IntelligencePriority,
    deserialize_embedding_result,
    deserialize_llm_result,
    serialize_compute_scheduling,
    serialize_embedding_input,
    serialize_llm_input,
)
from .compute_capacity_repository import (
    persist_compute_execution_telemetry,
    persist_compute_request_event,
)


logger = get_logger("intelligence_service.portable_compute_client")
_COMPUTE_KEY_HEADER = "X-Solomon-SIS-Compute-Key"


def _new_compute_attempt_id() -> str:
    return uuid.uuid4().hex


def _transport_failure_code(exc: Exception) -> str:
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "transport_timeout"
    text = str(exc or "").strip().lower()
    if "timed out" in text or "timeout" in text:
        return "transport_timeout"
    return "transport_unavailable"


def _http_failure_code(status_code: int) -> str:
    status = int(status_code or 0)
    if status == 429:
        return "admission_rejected"
    if status == 503:
        return "service_unavailable"
    if 400 <= status < 500:
        return "http_client_error"
    if status >= 500:
        return "http_server_error"
    return "http_failure"


def _telemetry_outcome(telemetry: object) -> str:
    if isinstance(telemetry, dict) and telemetry:
        return "success" if bool(telemetry.get("success")) else "remote_failure"
    return "response_without_execution"


def _failure(reason: LLMFailureReason, message: str) -> LLMExecutionResult:
    return LLMExecutionResult(
        failure=LLMExecutionFailure(
            reason=reason,
            message=message,
        )
    )


def _compute_url(path: str) -> str:
    base_url = str(settings.SIS_COMPUTE_BASE_URL or "").strip().rstrip("/")
    if not base_url:
        raise RuntimeError(
            "Portable SIS remote compute URL is not configured in config.py."
        )
    clean_path = "/" + str(path or "").strip().lstrip("/")
    return f"{base_url}{clean_path}"


def _headers(*, accept: str = "application/json") -> dict[str, str]:
    secret = str(settings.SIS_COMPUTE_SHARED_SECRET or "")
    if not secret:
        raise RuntimeError(
            "Portable SIS remote compute credential is not configured."
        )
    return {
        "Content-Type": "application/json",
        "Accept": accept,
        _COMPUTE_KEY_HEADER: secret,
    }


def get_remote_compute_health() -> dict:
    request_packet = urllib_request.Request(
        _compute_url("/health"),
        headers=_headers(),
        method="GET",
    )
    timeout = max(1, int(settings.SIS_COMPUTE_HEALTH_TIMEOUT_SECONDS))

    try:
        with urllib_request.urlopen(request_packet, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            if isinstance(payload, dict):
                return payload
    except Exception as exc:
        logger.debug("[SIS][REMOTE_COMPUTE_HEALTH_UNAVAILABLE] error=%s", exc)
        return {
            "ok": False,
            "status": "unavailable",
            "interactive_ready": False,
            "error": str(exc),
        }

    return {
        "ok": False,
        "status": "unavailable",
        "interactive_ready": False,
    }


def warm_remote_compute_runtime() -> dict:
    request_packet = urllib_request.Request(
        _compute_url("/warmup"),
        data=b"{}",
        headers=_headers(),
        method="POST",
    )
    timeout = max(1, int(settings.SIS_COMPUTE_CONNECT_TIMEOUT_SECONDS)) + max(
        1,
        int(settings.SIS_COMPUTE_HEALTH_TIMEOUT_SECONDS),
    )

    try:
        with urllib_request.urlopen(request_packet, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, dict) else {"ok": False}
    except Exception as exc:
        logger.warning("[SIS][REMOTE_COMPUTE_WARMUP_FAILURE] error=%s", exc)
        return {
            "ok": False,
            "status": "unavailable",
            "interactive_ready": False,
            "error": str(exc),
        }


def execute_embeddings_on_remote_compute(
    texts: Iterable[str],
    *,
    call_site: str | None = None,
    priority: str | IntelligencePriority = IntelligencePriority.P0,
    request_id: str | None = None,
    fairness_bucket: str | None = None,
) -> list[list[float]]:
    text_list = [str(text or "").strip() for text in texts]
    if not text_list:
        return []
    if any(not text for text in text_list):
        raise ValueError("Embedding requests must contain non-empty text.")

    function_started_at = time.perf_counter()
    normalized_priority = str(getattr(priority, "value", priority)).strip().upper() or "P0"
    batch_size = max(1, int(settings.SIS_EMBEDDING_MAX_BATCH_SIZE))
    timeout = max(1, int(settings.SIS_COMPUTE_REQUEST_TIMEOUT_SECONDS)) + max(
        1,
        int(settings.SIS_COMPUTE_CONNECT_TIMEOUT_SECONDS),
    )
    output: list[list[float]] = []

    for start in range(0, len(text_list), batch_size):
        batch_started_at = time.perf_counter()
        batch = text_list[start:start + batch_size]
        attempt_id = _new_compute_attempt_id()
        payload = {
            "request": serialize_embedding_input(batch, call_site=call_site),
            "scheduling": serialize_compute_scheduling(
                priority=priority,
                request_id=request_id,
                fairness_bucket=fairness_bucket,
                attempt_id=attempt_id,
            ),
        }
        request_body = json.dumps(payload).encode("utf-8")
        request_packet = urllib_request.Request(
            _compute_url("/v1/embeddings/execute"),
            data=request_body,
            headers=_headers(),
            method="POST",
        )
        prepared_at = time.perf_counter()
        logger.info(
            "[SIS][LOCAL_EMBEDDING_DISPATCH_TIMING] phase=prepared transport=portable_compute_client "
            "priority=%s request_id=%s call_site=%s batch=%s chars=%s bytes=%s prepare_ms=%.3f",
            normalized_priority,
            str(request_id or "unbound"),
            str(call_site or "unknown"),
            len(batch),
            sum(len(item) for item in batch),
            len(request_body),
            (prepared_at - batch_started_at) * 1000.0,
        )

        try:
            transport_started_at = time.perf_counter()
            with urllib_request.urlopen(request_packet, timeout=timeout) as response:
                response_bytes = response.read()
                transport_completed_at = time.perf_counter()
                http_status = int(getattr(response, "status", 200) or 200)
                response_payload = json.loads(response_bytes.decode("utf-8"))
                telemetry_payload = response_payload.get("telemetry")
                telemetry_started_at = time.perf_counter()
                persist_compute_execution_telemetry(
                    telemetry_payload,
                    transport_path="portable_compute_client",
                )
                persist_compute_request_event(
                    attempt_id=attempt_id,
                    request_id=request_id,
                    workload_type="embedding",
                    priority=priority,
                    call_site=call_site,
                    transport_path="portable_compute_client",
                    request_bytes=len(request_body),
                    response_bytes=len(response_bytes),
                    round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
                    http_status=http_status,
                    outcome_class=_telemetry_outcome(telemetry_payload),
                    telemetry_payload=telemetry_payload,
                )
                telemetry_completed_at = time.perf_counter()
                logger.info(
                    "[SIS][LOCAL_EMBEDDING_DISPATCH_TIMING] phase=response transport=portable_compute_client "
                    "priority=%s request_id=%s call_site=%s batch=%s transport_ms=%.3f telemetry_ms=%.3f response_bytes=%s",
                    normalized_priority,
                    str(request_id or "unbound"),
                    str(call_site or "unknown"),
                    len(batch),
                    (transport_completed_at - transport_started_at) * 1000.0,
                    (telemetry_completed_at - telemetry_started_at) * 1000.0,
                    len(response_bytes),
                )
                result = deserialize_embedding_result(
                    response_payload.get("result") or {}
                )
        except urllib_error.HTTPError as exc:
            transport_completed_at = time.perf_counter()
            message = f"Portable SIS compute returned HTTP {exc.code}."
            error_bytes = b""
            telemetry_payload = None
            try:
                error_bytes = exc.read()
                response_payload = json.loads(error_bytes.decode("utf-8"))
                telemetry_payload = response_payload.get("telemetry")
                persist_compute_execution_telemetry(
                    telemetry_payload,
                    transport_path="portable_compute_client",
                )
                message = str(response_payload.get("error") or message)
            except Exception:
                pass
            persist_compute_request_event(
                attempt_id=attempt_id,
                request_id=request_id,
                workload_type="embedding",
                priority=priority,
                call_site=call_site,
                transport_path="portable_compute_client",
                request_bytes=len(request_body),
                response_bytes=len(error_bytes),
                round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
                http_status=exc.code,
                outcome_class=(
                    _telemetry_outcome(telemetry_payload)
                    if telemetry_payload
                    else "http_failure"
                ),
                failure_code=_http_failure_code(exc.code),
                telemetry_payload=telemetry_payload,
            )
            raise RuntimeError(message) from exc
        except (urllib_error.URLError, socket.timeout, TimeoutError) as exc:
            persist_compute_request_event(
                attempt_id=attempt_id,
                request_id=request_id,
                workload_type="embedding",
                priority=priority,
                call_site=call_site,
                transport_path="portable_compute_client",
                request_bytes=len(request_body),
                response_bytes=0,
                round_trip_ms=(time.perf_counter() - transport_started_at) * 1000.0,
                outcome_class="transport_failure",
                failure_code=_transport_failure_code(exc),
            )
            raise RuntimeError(
                "Portable SIS embedding compute is unavailable or timed out."
            ) from exc

        if len(result.vectors) != len(batch):
            raise RuntimeError(
                "Portable SIS embedding response returned an unexpected vector count."
            )
        if int(result.dimension) != int(settings.EMBED_DIM):
            raise RuntimeError(
                "Portable SIS embedding dimension does not match config.py."
            )
        output.extend(result.vectors)

    logger.info(
        "[SIS][LOCAL_EMBEDDING_DISPATCH_TIMING] phase=complete transport=portable_compute_client "
        "priority=%s request_id=%s call_site=%s batches=%s vectors=%s total_ms=%.3f",
        normalized_priority,
        str(request_id or "unbound"),
        str(call_site or "unknown"),
        max(1, (len(text_list) + batch_size - 1) // batch_size),
        len(output),
        (time.perf_counter() - function_started_at) * 1000.0,
    )
    return output


def execute_llm_on_remote_compute(
    input_packet: LLMExecutionInput,
    *,
    stream_callback: Callable[[str], None] | None = None,
    priority: str | IntelligencePriority = IntelligencePriority.P0,
    request_id: str | None = None,
    fairness_bucket: str | None = None,
) -> LLMExecutionResult:
    attempt_id = _new_compute_attempt_id()
    payload = {
        "request": serialize_llm_input(input_packet),
        "scheduling": serialize_compute_scheduling(
            priority=priority,
            request_id=request_id,
            fairness_bucket=fairness_bucket,
            attempt_id=attempt_id,
        ),
        "stream": bool(stream_callback),
    }
    request_body = json.dumps(payload).encode("utf-8")
    request_packet = urllib_request.Request(
        _compute_url("/v1/llm/execute"),
        data=request_body,
        headers=_headers(),
        method="POST",
    )
    timeout = max(
        1,
        int(
            input_packet.timeout_seconds
            or settings.SIS_COMPUTE_REQUEST_TIMEOUT_SECONDS
        ),
    ) + max(1, int(settings.SIS_COMPUTE_CONNECT_TIMEOUT_SECONDS))

    transport_started_at = time.perf_counter()
    try:
        with urllib_request.urlopen(request_packet, timeout=timeout) as response:
            content_type = str(response.headers.get("Content-Type") or "")

            if "application/x-ndjson" in content_type:
                final_result = None
                telemetry_payload = None
                response_bytes_count = 0
                for raw_line in response:
                    response_bytes_count += len(raw_line)
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue
                    event = json.loads(line)
                    event_type = str(event.get("type") or "")
                    if event_type == "chunk":
                        chunk = str(event.get("text") or "")
                        if chunk and stream_callback:
                            stream_callback(chunk)
                    elif event_type == "result":
                        telemetry_payload = event.get("telemetry")
                        persist_compute_execution_telemetry(
                            telemetry_payload,
                            transport_path="portable_compute_client",
                        )
                        final_result = deserialize_llm_result(
                            event.get("result") or {}
                        )

                transport_completed_at = time.perf_counter()
                if final_result is None:
                    persist_compute_request_event(
                        attempt_id=attempt_id,
                        request_id=request_id,
                        workload_type="llm",
                        priority=priority,
                        call_site=input_packet.call_site,
                        transport_path="portable_compute_client",
                        request_bytes=len(request_body),
                        response_bytes=response_bytes_count,
                        round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
                        http_status=int(getattr(response, "status", 200) or 200),
                        outcome_class="client_failure",
                        failure_code="stream_missing_result",
                        telemetry_payload=telemetry_payload,
                    )
                    return _failure(
                        LLMFailureReason.INTERNAL_ERROR,
                        "Portable SIS stream ended without a final result.",
                    )
                persist_compute_request_event(
                    attempt_id=attempt_id,
                    request_id=request_id,
                    workload_type="llm",
                    priority=priority,
                    call_site=input_packet.call_site,
                    transport_path="portable_compute_client",
                    request_bytes=len(request_body),
                    response_bytes=response_bytes_count,
                    round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
                    http_status=int(getattr(response, "status", 200) or 200),
                    outcome_class=_telemetry_outcome(telemetry_payload),
                    telemetry_payload=telemetry_payload,
                )
                return final_result

            response_bytes = response.read()
            transport_completed_at = time.perf_counter()
            response_payload = json.loads(response_bytes.decode("utf-8"))
            telemetry_payload = response_payload.get("telemetry")
            persist_compute_execution_telemetry(
                telemetry_payload,
                transport_path="portable_compute_client",
            )
            persist_compute_request_event(
                attempt_id=attempt_id,
                request_id=request_id,
                workload_type="llm",
                priority=priority,
                call_site=input_packet.call_site,
                transport_path="portable_compute_client",
                request_bytes=len(request_body),
                response_bytes=len(response_bytes),
                round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
                http_status=int(getattr(response, "status", 200) or 200),
                outcome_class=_telemetry_outcome(telemetry_payload),
                telemetry_payload=telemetry_payload,
            )
            return deserialize_llm_result(response_payload.get("result") or {})
    except urllib_error.HTTPError as exc:
        transport_completed_at = time.perf_counter()
        message = f"Portable SIS compute returned HTTP {exc.code}."
        error_bytes = b""
        telemetry_payload = None
        try:
            error_bytes = exc.read()
            response_payload = json.loads(error_bytes.decode("utf-8"))
            telemetry_payload = response_payload.get("telemetry")
            persist_compute_execution_telemetry(
                telemetry_payload,
                transport_path="portable_compute_client",
            )
            message = str(response_payload.get("error") or message)
        except Exception:
            pass
        persist_compute_request_event(
            attempt_id=attempt_id,
            request_id=request_id,
            workload_type="llm",
            priority=priority,
            call_site=input_packet.call_site,
            transport_path="portable_compute_client",
            request_bytes=len(request_body),
            response_bytes=len(error_bytes),
            round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
            http_status=exc.code,
            outcome_class=(
                _telemetry_outcome(telemetry_payload)
                if telemetry_payload
                else "http_failure"
            ),
            failure_code=_http_failure_code(exc.code),
            telemetry_payload=telemetry_payload,
        )
        logger.warning(
            "[SIS][REMOTE_COMPUTE_LLM_HTTP_FAILURE] status=%s error=%s",
            exc.code,
            message,
        )
        return _failure(
            LLMFailureReason.TIMEOUT
            if exc.code == 429
            else LLMFailureReason.INTERNAL_ERROR,
            message,
        )
    except (urllib_error.URLError, socket.timeout, TimeoutError) as exc:
        persist_compute_request_event(
            attempt_id=attempt_id,
            request_id=request_id,
            workload_type="llm",
            priority=priority,
            call_site=input_packet.call_site,
            transport_path="portable_compute_client",
            request_bytes=len(request_body),
            response_bytes=0,
            round_trip_ms=(time.perf_counter() - transport_started_at) * 1000.0,
            outcome_class="transport_failure",
            failure_code=_transport_failure_code(exc),
        )
        logger.warning("[SIS][REMOTE_COMPUTE_LLM_UNAVAILABLE] error=%s", exc)
        return _failure(
            LLMFailureReason.TIMEOUT,
            "Portable SIS compute is unavailable or timed out.",
        )
    except Exception as exc:
        persist_compute_request_event(
            attempt_id=attempt_id,
            request_id=request_id,
            workload_type="llm",
            priority=priority,
            call_site=input_packet.call_site,
            transport_path="portable_compute_client",
            request_bytes=len(request_body),
            response_bytes=0,
            round_trip_ms=(time.perf_counter() - transport_started_at) * 1000.0,
            outcome_class="client_failure",
            failure_code="client_error",
        )
        logger.exception("[SIS][REMOTE_COMPUTE_LLM_CLIENT_FAILURE]")
        return _failure(
            LLMFailureReason.INTERNAL_ERROR,
            f"Portable SIS compute request failed: {exc}",
        )
