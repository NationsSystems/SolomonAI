# -------------------------------------------------------------------
# FILE: solomon_file_action_execution.py
# DIRECTORY: solomon_core/actions/
# -------------------------------------------------------------------
# Canonical server execution contract for governed Solomon file Actions.
# This layer binds a registered Action to current file authority and returns
# a bounded result packet for product surfaces such as the workspace rail.
# -------------------------------------------------------------------

from typing import Any, Callable, Dict, Optional

from solomon_core.actions.solomon_file_action_applicability import (
    resolve_solomon_file_action_applicability_for_entry,
)
from solomon_core.actions.solomon_file_actions import (
    ACTION_RESULT_FORMAT_PLAIN_TEXT_V1,
    ACTION_STATE_AVAILABLE,
    ACTION_STATE_PROCESSING,
    get_solomon_file_action_definition,
    resolve_solomon_file_action,
)
from solomon_core.workspace_reader.workspace_reader_file_access import (
    resolve_authorized_file_registry_entry,
    resolve_current_summary_artifact,
)

from .solomon_file_action_intelligence import (
    SolomonFileActionIntelligenceError,
    execute_on_demand_solomon_file_action,
)
from .solomon_file_action_results import (
    link_ready_solomon_file_action_result,
    persist_ready_solomon_file_action_result,
    resolve_ready_solomon_file_action_result,
)


SOLOMON_FILE_ACTION_EXECUTION_CONTRACT = "solomon_file_action_execution_v1"
SOLOMON_FILE_ACTION_PACKET_TYPE = "solomon_action_result"

ACTION_EXECUTION_STATUS_SUCCEEDED = "succeeded"
ACTION_EXECUTION_STATUS_PROCESSING = "processing"
ACTION_EXECUTION_STATUS_FAILED = "failed"


class SolomonFileActionExecutionError(Exception):
    """Raised when a governed Solomon file Action cannot execute safely."""

    def __init__(
        self,
        error_code: str,
        user_output: str,
        *,
        status_code: int = 400,
        action_id: str = "",
        document_id: str = "",
        action_state: str = "",
    ):
        super().__init__(user_output)
        self.error_code = str(error_code or "action_execution_failed").strip()
        self.user_output = str(
            user_output
            or "The requested Action could not be completed."
        ).strip()
        self.status_code = int(status_code or 400)
        self.action_id = str(action_id or "").strip()
        self.document_id = str(document_id or "").strip()
        self.action_state = str(action_state or "").strip()


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _bounded_resource_payload(entry: dict) -> dict:
    return {
        "document_id": _clean_text(entry.get("document_id")),
        "file_id": _clean_text(entry.get("file_id")),
        "name": _clean_text(entry.get("original_name")),
        "extension": _clean_text(entry.get("extension")),
        "version_number": entry.get("version_number") or 1,
    }


def build_solomon_file_action_error_packet(
    error: SolomonFileActionExecutionError,
    *,
    request_id: str,
) -> dict:
    """Return the canonical bounded error packet for one Action request."""

    return {
        "ok": False,
        "packet_type": SOLOMON_FILE_ACTION_PACKET_TYPE,
        "contract": SOLOMON_FILE_ACTION_EXECUTION_CONTRACT,
        "request_id": _clean_text(request_id),
        "action": {
            "action_id": error.action_id,
            "state": error.action_state,
        },
        "resource": {
            "document_id": error.document_id,
        },
        "execution": {
            "status": ACTION_EXECUTION_STATUS_FAILED,
            "progress_percent": 0,
            "stage": "failed",
        },
        "result": None,
        "provenance": {},
        "error": {
            "code": error.error_code,
            "message": error.user_output,
        },
    }


def _build_success_packet(
    *,
    request_id: str,
    action: dict,
    resource: dict,
    result: dict,
    provenance: dict,
    reused: bool = False,
) -> dict:
    return {
        "ok": True,
        "packet_type": SOLOMON_FILE_ACTION_PACKET_TYPE,
        "contract": SOLOMON_FILE_ACTION_EXECUTION_CONTRACT,
        "request_id": _clean_text(request_id),
        "action": action,
        "resource": resource,
        "execution": {
            "status": ACTION_EXECUTION_STATUS_SUCCEEDED,
            "progress_percent": 100,
            "stage": "ready",
            "reused": bool(reused),
        },
        "result": result,
        "provenance": provenance,
        "error": None,
    }


def _stored_result_packet_payload(
    stored: dict,
    *,
    fallback_title: str,
    fallback_format: str = ACTION_RESULT_FORMAT_PLAIN_TEXT_V1,
) -> dict:
    result = dict(stored.get("result") or {})
    result["type"] = _clean_text(
        result.get("type") or stored.get("result_type")
    )
    result["format"] = _clean_text(
        result.get("format") or fallback_format or ACTION_RESULT_FORMAT_PLAIN_TEXT_V1
    )
    result["title"] = _clean_text(
        result.get("title") or fallback_title
    )
    result["content"] = _clean_text(
        result.get("content") or stored.get("result_text")
    )
    result["generated_at"] = _clean_text(
        result.get("generated_at") or stored.get("completed_at")
    )
    result["result_id"] = _clean_text(stored.get("result_id"))
    return result


def _stored_provenance(stored: dict, entry: dict) -> dict:
    provenance = dict(stored.get("provenance") or {})

    # Canonical results may be reused across distinct governed file records with
    # identical content. Never expose resource identity captured by the file
    # that originally caused the computation.
    for unsafe_key in (
        "source_document_id",
        "source_name",
        "source_file_id",
        "source_version",
    ):
        provenance.pop(unsafe_key, None)

    provenance.update({
        "source_hash": _clean_text(entry.get("checksum")),
        "source_version": _safe_int(entry.get("version_number"), 1),
        "source_document_id": _clean_text(entry.get("document_id")),
        "result_hash": _clean_text(stored.get("result_hash")),
        "result_id": _clean_text(stored.get("result_id")),
    })
    return provenance


def _execute_precomputed_action(
    *,
    request_id: str,
    action: dict,
    entry: dict,
    user_id: int,
    parameters: Optional[dict] = None,
) -> dict:
    definition = get_solomon_file_action_definition(
        action.get("action_id")
    )
    source_hash = _clean_text(entry.get("checksum"))
    source_version = _safe_int(entry.get("version_number"), 1)
    file_registry_id = _safe_int(entry.get("file_id"))
    clean_parameters = dict(parameters) if isinstance(parameters, dict) else {}

    if definition and source_hash:
        stored = resolve_ready_solomon_file_action_result(
            action_id=definition.action_id,
            action_contract_version=definition.action_contract_version,
            source_hash=source_hash,
            parameters=clean_parameters,
        )

        if stored:
            link_ready_solomon_file_action_result(
                result_id=stored.get("result_id", ""),
                file_registry_id=file_registry_id,
                source_version=source_version,
                source_hash=source_hash,
                linked_by_user_id=user_id,
                trigger_type="summary_view_reuse",
                request_id=request_id,
            )
            return _build_success_packet(
                request_id=request_id,
                action=action,
                resource=_bounded_resource_payload(entry),
                result=_stored_result_packet_payload(
                    stored,
                    fallback_title="Summary",
                    fallback_format=(
                        definition.result_format
                        if definition is not None
                        else ACTION_RESULT_FORMAT_PLAIN_TEXT_V1
                    ),
                ),
                provenance=_stored_provenance(stored, entry),
                reused=True,
            )

    if definition is None or definition.action_id != "summary.view":
        raise SolomonFileActionExecutionError(
            "action_not_ready",
            "That prepared Action result is not ready yet.",
            status_code=409,
            action_id=_clean_text(action.get("action_id")),
            document_id=_clean_text(entry.get("document_id")),
            action_state="processing",
        )

    # Summary predates the generic Action Result Store. Preserve the current
    # WorkspaceIntelligenceObject as a compatibility source and adopt it into
    # the canonical result store the first time it is requested.
    artifact = resolve_current_summary_artifact(
        entry,
        request_id=request_id,
    )

    if not artifact:
        raise SolomonFileActionExecutionError(
            "action_not_ready",
            "The current Summary is not ready yet.",
            status_code=409,
            action_id=_clean_text(action.get("action_id")),
            document_id=_clean_text(entry.get("document_id")),
            action_state="processing",
        )

    content = _clean_text(artifact.get("summary"))
    generated_at = _clean_text(artifact.get("generated_at"))

    if definition and source_hash and content:
        stored = persist_ready_solomon_file_action_result(
            action_id=definition.action_id,
            action_contract_version=definition.action_contract_version,
            source_hash=source_hash,
            result_type=definition.result_type,
            result_text=content,
            result_json={
                "type": definition.result_type,
                "format": definition.result_format,
                "title": "Summary",
                "content": content,
                "generated_at": generated_at,
            },
            parameters=clean_parameters,
            processor_key=definition.processor_key,
            processor_version=definition.processor_version,
            provenance={
                "source_hash": source_hash,
                "source": _clean_text(artifact.get("summary_source")),
                "legacy_summary_hash": _clean_text(artifact.get("summary_hash")),
            },
            metadata={"adopted_from": "workspace_intelligence_summary"},
            file_registry_id=file_registry_id,
            source_version=source_version,
            linked_by_user_id=user_id,
            trigger_type="summary_view_adoption",
            request_id=request_id,
        )
        return _build_success_packet(
            request_id=request_id,
            action=action,
            resource=_bounded_resource_payload(entry),
            result=_stored_result_packet_payload(
                stored,
                fallback_title="Summary",
                fallback_format=definition.result_format,
            ),
            provenance=_stored_provenance(stored, entry),
            reused=bool(stored.get("reused")),
        )

    return _build_success_packet(
        request_id=request_id,
        action=action,
        resource=_bounded_resource_payload(entry),
        result={
            "type": "summary",
            "format": definition.result_format if definition else ACTION_RESULT_FORMAT_PLAIN_TEXT_V1,
            "title": "Summary",
            "content": content,
            "generated_at": generated_at,
        },
        provenance={
            "source_hash": _clean_text(artifact.get("source_hash")),
            "source_version": artifact.get("source_version") or 1,
            "result_hash": _clean_text(artifact.get("summary_hash")),
            "source": _clean_text(artifact.get("summary_source")),
        },
    )


def _execute_on_demand_action(
    *,
    request_id: str,
    action: dict,
    entry: dict,
    user_id: int,
    parameters: Optional[dict] = None,
) -> dict:
    definition = get_solomon_file_action_definition(
        action.get("action_id")
    )

    if definition is None:
        raise SolomonFileActionExecutionError(
            "unknown_action",
            "That Action is not registered in Solomon.",
            status_code=404,
            action_id=_clean_text(action.get("action_id")),
            document_id=_clean_text(entry.get("document_id")),
        )

    try:
        stored = execute_on_demand_solomon_file_action(
            definition=definition,
            entry=entry,
            user_id=user_id,
            request_id=request_id,
            parameters=parameters,
        )
    except SolomonFileActionIntelligenceError as exc:
        action_state = (
            ACTION_STATE_PROCESSING
            if exc.error_code == "action_context_preparing"
            else ACTION_STATE_AVAILABLE
        )
        raise SolomonFileActionExecutionError(
            exc.error_code,
            exc.user_output,
            status_code=exc.status_code,
            action_id=definition.action_id,
            document_id=_clean_text(entry.get("document_id")),
            action_state=action_state,
        ) from exc

    return _build_success_packet(
        request_id=request_id,
        action=action,
        resource=_bounded_resource_payload(entry),
        result=_stored_result_packet_payload(
            stored,
            fallback_title=definition.label,
            fallback_format=definition.result_format,
        ),
        provenance=_stored_provenance(stored, entry),
        reused=bool(stored.get("reused")),
    )


_FILE_ACTION_EXECUTORS_BY_KIND: Dict[str, Callable[..., dict]] = {
    "precomputed": _execute_precomputed_action,
    "on_demand": _execute_on_demand_action,
}


def execute_solomon_file_action(
    *,
    user_id: int,
    document_id: Any,
    action_id: Any,
    request_id: str = "untracked",
    parameters: Optional[dict] = None,
) -> dict:
    """Execute one registered Action against a freshly authorized file entry."""

    clean_action_id = _clean_text(action_id).lower()
    clean_document_id = _clean_text(document_id)
    definition = get_solomon_file_action_definition(
        clean_action_id
    )

    if not definition:
        raise SolomonFileActionExecutionError(
            "unknown_action",
            "That Action is not registered in Solomon.",
            status_code=404,
            action_id=clean_action_id,
            document_id=clean_document_id,
        )

    if not definition.enabled:
        raise SolomonFileActionExecutionError(
            "action_disabled",
            "That Action is not currently available.",
            status_code=409,
            action_id=definition.action_id,
            document_id=clean_document_id,
            action_state="disabled",
        )

    entry = resolve_authorized_file_registry_entry(
        user_id,
        clean_document_id,
        request_id=request_id,
        action=definition.permission_requirement,
    )

    if not entry:
        raise SolomonFileActionExecutionError(
            "resource_unavailable",
            "That file is unavailable or you no longer have access to it.",
            status_code=404,
            action_id=definition.action_id,
            document_id=clean_document_id,
            action_state="not_authorized",
        )

    applicability_profile = resolve_solomon_file_action_applicability_for_entry(
        entry
    )
    applicable_action_ids = (
        applicability_profile.get("applicable_action_ids")
        if isinstance(applicability_profile, dict)
        else None
    )
    action = resolve_solomon_file_action(
        definition.action_id,
        entry.get("capabilities"),
        entry,
        applicable_action_ids,
    )

    if not action:
        raise SolomonFileActionExecutionError(
            "action_resolution_failed",
            "Solomon could not resolve that Action for this file.",
            status_code=409,
            action_id=definition.action_id,
            document_id=clean_document_id,
        )

    if action.get("state") != ACTION_STATE_AVAILABLE:
        raise SolomonFileActionExecutionError(
            "action_unavailable",
            "That Action is not currently available for this file.",
            status_code=409,
            action_id=definition.action_id,
            document_id=clean_document_id,
            action_state=_clean_text(action.get("state")),
        )

    executor = _FILE_ACTION_EXECUTORS_BY_KIND.get(
        definition.execution_kind
    )

    if not executor:
        raise SolomonFileActionExecutionError(
            "action_executor_unavailable",
            "That Action is registered but cannot execute yet.",
            status_code=409,
            action_id=definition.action_id,
            document_id=clean_document_id,
            action_state=_clean_text(action.get("state")),
        )

    clean_parameters = dict(parameters) if isinstance(parameters, dict) else {}

    return executor(
        request_id=request_id,
        action=action,
        entry=entry,
        user_id=int(user_id),
        parameters=clean_parameters,
    )
