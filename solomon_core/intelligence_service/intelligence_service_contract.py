# -------------------------------------------------------------------
# FILE: intelligence_service_contract.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Wire contract between the Solomon web application and the separately
# running Solomon Intelligence Service (SIS).
# -------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
from typing import Any, Iterable

from solomon_core.llm.llm_execution_contract import (
    LLMExecutionFailure,
    LLMExecutionInput,
    LLMExecutionMode,
    LLMExecutionOutput,
    LLMExecutionResult,
    LLMFailureReason,
    LLMResponseFormat,
    LLMRuntimeProfile,
)


class IntelligenceServiceStatus(str, Enum):
    """Canonical externally observable SIS service/readiness states."""

    STARTING = "starting"
    WARMING = "warming"
    READY = "ready"
    DEGRADED = "degraded"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"


class IntelligenceRequestClass(str, Enum):
    """Legacy two-class scheduling surface retained for compatibility."""

    INTERACTIVE = "interactive"
    BACKGROUND = "background"


class IntelligencePriority(str, Enum):
    """Canonical Portable SIS compute-admission priority.

    Priority describes compute urgency only. It never grants file, permission,
    CaseFile, retrieval, orchestration, or durable-state authority.
    """

    P0 = "P0"
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


@dataclass(frozen=True)
class ComputeSchedulingMetadata:
    """Bounded compute-only scheduling metadata carried to Portable SIS."""

    priority: IntelligencePriority
    request_id: str | None = None
    fairness_bucket: str = "unbound"
    attempt_id: str | None = None


@dataclass(frozen=True)
class ComputeExecutionTelemetry:
    """Content-free execution evidence returned by Portable SIS.

    Telemetry describes compute behavior only. It must never contain prompts,
    generated text, retrieved evidence, file names, user identity, Group names,
    permissions, or other organizational business state.
    """

    observed_at: str
    node: str
    workload_type: str
    priority: IntelligencePriority
    request_id: str | None
    fairness_bucket: str
    call_site: str | None
    queue_wait_ms: float
    execution_ms: float
    queue_depth_at_admission: int
    active_requests_at_admission: int
    max_concurrent_requests: int
    input_units: int | None
    output_units: int | None
    success: bool
    attempt_id: str | None = None
    failure_code: str | None = None
    model_name: str | None = None
    runtime_profile: str | None = None
    runtime_fingerprint: str | None = None


def parse_intelligence_request_class(value: Any) -> IntelligenceRequestClass:
    """Return the legacy SIS scheduling class for compatibility endpoints."""

    if isinstance(value, IntelligenceRequestClass):
        return value

    normalized = str(
        value or IntelligenceRequestClass.INTERACTIVE.value
    ).strip().lower()

    try:
        return IntelligenceRequestClass(normalized)
    except ValueError as exc:
        raise ValueError(
            f"Unsupported SIS request class: {normalized!r}."
        ) from exc


def parse_intelligence_priority(
    value: Any,
    *,
    legacy_request_class: Any = None,
) -> IntelligencePriority:
    """Return canonical P0/P1/P2/P3 priority with legacy compatibility."""

    if isinstance(value, IntelligencePriority):
        return value

    normalized = str(value or "").strip().upper()
    if normalized:
        try:
            return IntelligencePriority(normalized)
        except ValueError as exc:
            raise ValueError(
                f"Unsupported SIS compute priority: {normalized!r}."
            ) from exc

    legacy = str(legacy_request_class or "").strip().lower()
    if legacy == IntelligenceRequestClass.BACKGROUND.value:
        return IntelligencePriority.P3
    return IntelligencePriority.P0


def build_opaque_fairness_bucket(
    seed: Any,
    *,
    namespace: str = "compute",
) -> str:
    """Derive opaque compute metadata without exporting caller identity."""

    clean_seed = str(seed or "").strip()
    if not clean_seed:
        return "unbound"

    clean_namespace = str(namespace or "compute").strip().lower() or "compute"
    digest = hashlib.sha256(
        f"{clean_namespace}:{clean_seed}".encode("utf-8")
    ).hexdigest()
    return digest[:32]


def serialize_compute_scheduling(
    *,
    priority: Any = IntelligencePriority.P0,
    request_id: Any = None,
    fairness_bucket: Any = None,
    attempt_id: Any = None,
) -> dict[str, Any]:
    """Return bounded JSON-safe scheduling metadata for remote compute."""

    normalized_priority = parse_intelligence_priority(priority)
    clean_request_id = str(request_id or "").strip()[:128] or None
    clean_bucket = str(fairness_bucket or "unbound").strip()[:128] or "unbound"
    clean_attempt_id = str(attempt_id or "").strip()[:64] or None
    return {
        "priority": normalized_priority.value,
        "request_id": clean_request_id,
        "fairness_bucket": clean_bucket,
        "attempt_id": clean_attempt_id,
    }


def deserialize_compute_scheduling(
    payload: Any,
    *,
    legacy_request_class: Any = None,
) -> ComputeSchedulingMetadata:
    """Validate and normalize one Portable SIS scheduling packet."""

    data = payload if isinstance(payload, dict) else {}
    priority = parse_intelligence_priority(
        data.get("priority"),
        legacy_request_class=legacy_request_class,
    )
    request_id = str(data.get("request_id") or "").strip()[:128] or None
    fairness_bucket = (
        str(data.get("fairness_bucket") or "unbound").strip()[:128]
        or "unbound"
    )
    attempt_id = str(data.get("attempt_id") or "").strip()[:64] or None
    return ComputeSchedulingMetadata(
        priority=priority,
        request_id=request_id,
        fairness_bucket=fairness_bucket,
        attempt_id=attempt_id,
    )


def deserialize_compute_execution_telemetry(
    payload: Any,
) -> ComputeExecutionTelemetry:
    """Validate bounded Portable SIS telemetry for LOCAL persistence."""

    if not isinstance(payload, dict):
        raise ValueError("Portable SIS compute telemetry must be a JSON object.")

    observed_at = str(payload.get("observed_at") or "").strip()[:64]
    node = str(payload.get("node") or "").strip()[:128]
    workload_type = str(payload.get("workload_type") or "").strip()[:64]
    if not observed_at:
        raise ValueError("Portable SIS compute telemetry must include observed_at.")
    if not node:
        raise ValueError("Portable SIS compute telemetry must include node.")
    if not workload_type:
        raise ValueError("Portable SIS compute telemetry must include workload_type.")

    priority = parse_intelligence_priority(payload.get("priority"))
    request_id = str(payload.get("request_id") or "").strip()[:128] or None
    fairness_bucket = (
        str(payload.get("fairness_bucket") or "unbound").strip()[:128]
        or "unbound"
    )
    call_site = str(payload.get("call_site") or "").strip()[:128] or None
    attempt_id = str(payload.get("attempt_id") or "").strip()[:64] or None
    failure_code = str(payload.get("failure_code") or "").strip()[:64] or None
    model_name = str(payload.get("model_name") or "").strip()[:128] or None
    runtime_profile = (
        str(payload.get("runtime_profile") or "").strip()[:64] or None
    )
    runtime_fingerprint = (
        str(payload.get("runtime_fingerprint") or "").strip()[:64] or None
    )

    def _nonnegative_float(name: str) -> float:
        value = float(payload.get(name) or 0.0)
        if value < 0:
            raise ValueError(f"Portable SIS compute telemetry {name} must be nonnegative.")
        return round(value, 3)

    def _nonnegative_int(name: str) -> int:
        value = int(payload.get(name) or 0)
        if value < 0:
            raise ValueError(f"Portable SIS compute telemetry {name} must be nonnegative.")
        return value

    max_concurrent_requests = int(payload.get("max_concurrent_requests") or 1)
    if max_concurrent_requests <= 0:
        raise ValueError(
            "Portable SIS compute telemetry max_concurrent_requests must be greater than 0."
        )

    def _optional_nonnegative_int(name: str) -> int | None:
        raw = payload.get(name)
        if raw is None:
            return None
        value = int(raw)
        if value < 0:
            raise ValueError(f"Portable SIS compute telemetry {name} must be nonnegative.")
        return value

    return ComputeExecutionTelemetry(
        observed_at=observed_at,
        node=node,
        workload_type=workload_type,
        priority=priority,
        request_id=request_id,
        fairness_bucket=fairness_bucket,
        call_site=call_site,
        queue_wait_ms=_nonnegative_float("queue_wait_ms"),
        execution_ms=_nonnegative_float("execution_ms"),
        queue_depth_at_admission=_nonnegative_int("queue_depth_at_admission"),
        active_requests_at_admission=_nonnegative_int(
            "active_requests_at_admission"
        ),
        max_concurrent_requests=max_concurrent_requests,
        input_units=_optional_nonnegative_int("input_units"),
        output_units=_optional_nonnegative_int("output_units"),
        success=bool(payload.get("success")),
        attempt_id=attempt_id,
        failure_code=failure_code,
        model_name=model_name,
        runtime_profile=runtime_profile,
        runtime_fingerprint=runtime_fingerprint,
    )


@dataclass(frozen=True)
class EmbeddingExecutionResult:
    """Canonical JSON-safe result metadata for one SIS embedding execution."""

    vectors: list[list[float]]
    model_name: str
    dimension: int


def serialize_embedding_input(
    texts: Iterable[str],
    *,
    call_site: str | None = None,
) -> dict[str, Any]:
    """Return a JSON-safe representation of one SIS embedding request."""

    return {
        "texts": [str(text or "") for text in texts],
        "call_site": str(call_site or "").strip() or None,
    }


def deserialize_embedding_input(
    payload: dict[str, Any],
) -> tuple[list[str], str | None]:
    """Validate and normalize one SIS embedding wire payload."""

    if not isinstance(payload, dict):
        raise ValueError("SIS embedding payload must be a JSON object.")

    raw_texts = payload.get("texts")
    if not isinstance(raw_texts, list):
        raise ValueError("SIS embedding payload must include a texts array.")

    texts = [str(text or "").strip() for text in raw_texts]
    if not texts:
        raise ValueError("SIS embedding payload must include at least one text.")
    if any(not text for text in texts):
        raise ValueError("SIS embedding texts must be non-empty strings.")

    call_site = str(payload.get("call_site") or "").strip() or None
    return texts, call_site


def serialize_embedding_result(
    vectors: Iterable[Iterable[float]],
    *,
    model_name: str,
    dimension: int,
) -> dict[str, Any]:
    """Return a JSON-safe representation of normalized SIS embeddings."""

    return {
        "vectors": [
            [float(value) for value in vector]
            for vector in vectors
        ],
        "model_name": str(model_name or "").strip(),
        "dimension": int(dimension),
    }


def deserialize_embedding_result(
    payload: dict[str, Any],
) -> EmbeddingExecutionResult:
    """Build and validate one canonical SIS embedding result."""

    if not isinstance(payload, dict):
        raise ValueError("SIS embedding result must be a JSON object.")

    raw_vectors = payload.get("vectors")
    if not isinstance(raw_vectors, list):
        raise ValueError("SIS embedding result must include a vectors array.")

    dimension = int(payload.get("dimension") or 0)
    if dimension <= 0:
        raise ValueError("SIS embedding result dimension must be greater than 0.")

    vectors: list[list[float]] = []
    for raw_vector in raw_vectors:
        if not isinstance(raw_vector, list):
            raise ValueError("SIS embedding vectors must be arrays.")
        vector = [float(value) for value in raw_vector]
        if len(vector) != dimension:
            raise ValueError(
                "SIS embedding result contained a vector with an "
                "unexpected dimension."
            )
        vectors.append(vector)

    model_name = str(payload.get("model_name") or "").strip()
    if not model_name:
        raise ValueError("SIS embedding result must include model_name.")

    return EmbeddingExecutionResult(
        vectors=vectors,
        model_name=model_name,
        dimension=dimension,
    )


def serialize_llm_input(value: LLMExecutionInput) -> dict[str, Any]:
    """Return a JSON-safe representation of one governed LLM request."""

    return {
        "user_query": value.user_query,
        "mode": value.mode.value,
        "context": value.context,
        "response_format": value.response_format.value,
        "call_site": value.call_site,
        "max_new_tokens": value.max_new_tokens,
        "runtime_profile": value.runtime_profile.value,
        "timeout_seconds": value.timeout_seconds,
    }


def deserialize_llm_input(payload: dict[str, Any]) -> LLMExecutionInput:
    """Build the canonical immutable LLM input from a SIS wire payload."""

    if not isinstance(payload, dict):
        raise ValueError("SIS LLM payload must be a JSON object.")

    return LLMExecutionInput(
        user_query=str(payload.get("user_query") or ""),
        mode=LLMExecutionMode(str(payload.get("mode") or "")),
        context=(
            payload.get("context")
            if isinstance(payload.get("context"), dict)
            else None
        ),
        response_format=LLMResponseFormat(
            str(payload.get("response_format") or LLMResponseFormat.TEXT.value)
        ),
        call_site=(
            str(payload.get("call_site") or "").strip()
            or None
        ),
        max_new_tokens=(
            int(payload["max_new_tokens"])
            if payload.get("max_new_tokens") is not None
            else None
        ),
        runtime_profile=LLMRuntimeProfile(
            str(
                payload.get("runtime_profile")
                or LLMRuntimeProfile.DEFAULT.value
            )
        ),
        timeout_seconds=(
            int(payload["timeout_seconds"])
            if payload.get("timeout_seconds") is not None
            else None
        ),
    )


def serialize_llm_result(value: LLMExecutionResult) -> dict[str, Any]:
    """Return a JSON-safe representation of one canonical LLM result."""

    if value.output is not None:
        return {
            "output": {
                "text": value.output.text,
                "confidence": value.output.confidence,
                "citations": list(value.output.citations),
                "refusal": bool(value.output.refusal),
            },
            "failure": None,
        }

    failure = value.failure
    return {
        "output": None,
        "failure": {
            "reason": failure.reason.value if failure else "internal_error",
            "message": failure.message if failure else "Unknown SIS failure.",
        },
    }


def deserialize_llm_result(payload: dict[str, Any]) -> LLMExecutionResult:
    """Build the canonical immutable LLM result from a SIS wire payload."""

    if not isinstance(payload, dict):
        raise ValueError("SIS LLM result must be a JSON object.")

    output = payload.get("output")
    failure = payload.get("failure")

    if isinstance(output, dict):
        return LLMExecutionResult(
            output=LLMExecutionOutput(
                text=str(output.get("text") or ""),
                confidence=str(output.get("confidence") or "low"),
                citations=[
                    str(item)
                    for item in (output.get("citations") or [])
                ],
                refusal=bool(output.get("refusal", False)),
            )
        )

    if isinstance(failure, dict):
        return LLMExecutionResult(
            failure=LLMExecutionFailure(
                reason=LLMFailureReason(
                    str(failure.get("reason") or "internal_error")
                ),
                message=(
                    str(failure.get("message") or "").strip()
                    or None
                ),
            )
        )

    raise ValueError("SIS LLM result contained neither output nor failure.")
