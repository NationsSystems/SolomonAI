# -------------------------------------------------------------------
# FILE: solomon_file_actions.py
# DIRECTORY: solomon_core/actions/
# -------------------------------------------------------------------
# Canonical Solomon Actions matrix for governed file capabilities.
# Actions are productized operations, distinct from ordinary file-management
# commands such as Open Reader, Share, Details, Move, and Trash.
# -------------------------------------------------------------------

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Dict, Iterable, Optional, Tuple


ACTION_STATE_AVAILABLE = "available"
ACTION_STATE_PROCESSING = "processing"
ACTION_STATE_UNAVAILABLE = "unavailable"
ACTION_STATE_NOT_AUTHORIZED = "not_authorized"
ACTION_STATE_DISABLED = "disabled"

ACTION_FAMILY_UNDERSTAND = "understand"
ACTION_FAMILY_EXTRACT = "extract"

ACTION_ROLLOUT_ACTIVE = "active"
ACTION_PERSISTENCE_DURABLE = "durable"

ACTION_RESULT_FORMAT_PLAIN_TEXT_V1 = "plain_text_v1"
ACTION_RESULT_FORMAT_SOLOMON_MARKDOWN_V1 = "solomon_markdown_v1"
SOLOMON_FILE_ACTION_REGISTRY_CONTRACT = "solomon_file_action_registry_v1"
SOLOMON_FILE_ACTION_APPLICABILITY_CONTRACT = "solomon_file_action_applicability_v1"

SUPPORTED_DOCUMENT_ACTION_EXTENSIONS = (
    ".pdf",
    ".docx",
    ".txt",
    ".csv",
    ".xlsx",
    ".xls",
)


@dataclass(frozen=True)
class SolomonFileActionDefinition:
    action_id: str
    label: str
    family: str
    capability_key: str
    menu_command: str
    icon_name: str
    target_kind: str
    permission_requirement: str
    execution_kind: str
    result_surface: str
    action_contract_version: str
    result_type: str
    result_format: str
    persistence_policy: str
    processor_key: str
    processor_version: str
    execution_priority: str
    supported_extensions: Tuple[str, ...]
    selection_policy: str = "single"
    tutorial_eligible: bool = False
    requires_web: bool = False
    enabled: bool = True
    rollout_state: str = ACTION_ROLLOUT_ACTIVE
    prerequisites: Tuple[str, ...] = ()
    parameter_schema: Tuple[str, ...] = ()
    applicability_version: str = "1"

    def public_payload(self, state: str) -> Dict[str, Any]:
        """Return the bounded client contract for one resolved Action."""

        return {
            "action_id": self.action_id,
            "label": self.label,
            "family": self.family,
            "state": state,
            "command": self.menu_command,
            "icon": self.icon_name,
            "target_kind": self.target_kind,
            "permission_requirement": self.permission_requirement,
            "execution_kind": self.execution_kind,
            "result_surface": self.result_surface,
            "action_contract_version": self.action_contract_version,
            "result_type": self.result_type,
            "result_format": self.result_format,
            "persistence_policy": self.persistence_policy,
            "selection_policy": self.selection_policy,
            "tutorial_eligible": self.tutorial_eligible,
            "requires_web": self.requires_web,
            "rollout_state": self.rollout_state,
            "parameter_schema": list(self.parameter_schema),
            "applicability_version": self.applicability_version,
        }


SOLOMON_FILE_ACTION_MATRIX = (
    SolomonFileActionDefinition(
        action_id="summary.view",
        label="View Summary",
        family=ACTION_FAMILY_UNDERSTAND,
        capability_key="can_view_summary",
        menu_command="summary",
        icon_name="summarize",
        target_kind="file",
        permission_requirement="read",
        execution_kind="precomputed",
        result_surface="action_result",
        action_contract_version="1",
        result_type="summary",
        result_format=ACTION_RESULT_FORMAT_PLAIN_TEXT_V1,
        persistence_policy=ACTION_PERSISTENCE_DURABLE,
        processor_key="generate_document_summary",
        processor_version="2.4",
        execution_priority="P3",
        supported_extensions=SUPPORTED_DOCUMENT_ACTION_EXTENSIONS,
        selection_policy="single",
        tutorial_eligible=True,
        requires_web=False,
        enabled=True,
        prerequisites=("current_summary",),
    ),
    SolomonFileActionDefinition(
        action_id="key_points.extract",
        label="Extract Key Points",
        family=ACTION_FAMILY_UNDERSTAND,
        capability_key="can_run_document_operation",
        menu_command="key_points",
        icon_name="format_list_bulleted",
        target_kind="file",
        permission_requirement="query",
        execution_kind="on_demand",
        result_surface="action_result",
        # v4 adds adaptive large-resource context qualification and lazy preparation.
        action_contract_version="4",
        result_type="bullet_list",
        result_format=ACTION_RESULT_FORMAT_SOLOMON_MARKDOWN_V1,
        persistence_policy=ACTION_PERSISTENCE_DURABLE,
        processor_key="solomon_file_action_intelligence",
        processor_version="4",
        execution_priority="P1",
        supported_extensions=SUPPORTED_DOCUMENT_ACTION_EXTENSIONS,
        prerequisites=("source_text",),
    ),
    SolomonFileActionDefinition(
        action_id="dates_deadlines.extract",
        label="Find Dates & Deadlines",
        family=ACTION_FAMILY_EXTRACT,
        capability_key="can_run_document_operation",
        menu_command="dates_deadlines",
        icon_name="event",
        target_kind="file",
        permission_requirement="query",
        execution_kind="on_demand",
        result_surface="action_result",
        # v4 adds exhaustive large-resource context qualification and lazy preparation.
        action_contract_version="4",
        result_type="dated_items",
        result_format=ACTION_RESULT_FORMAT_SOLOMON_MARKDOWN_V1,
        persistence_policy=ACTION_PERSISTENCE_DURABLE,
        processor_key="solomon_file_action_intelligence",
        processor_version="4",
        execution_priority="P1",
        supported_extensions=SUPPORTED_DOCUMENT_ACTION_EXTENSIONS,
        prerequisites=("source_text",),
    ),
    SolomonFileActionDefinition(
        action_id="action_items.extract",
        label="Extract Action Items",
        family=ACTION_FAMILY_EXTRACT,
        capability_key="can_run_document_operation",
        menu_command="action_items",
        icon_name="task_alt",
        target_kind="file",
        permission_requirement="query",
        execution_kind="on_demand",
        result_surface="action_result",
        # v4 adds exhaustive large-resource context qualification and lazy preparation.
        action_contract_version="4",
        result_type="action_items",
        result_format=ACTION_RESULT_FORMAT_SOLOMON_MARKDOWN_V1,
        persistence_policy=ACTION_PERSISTENCE_DURABLE,
        processor_key="solomon_file_action_intelligence",
        processor_version="4",
        execution_priority="P1",
        supported_extensions=SUPPORTED_DOCUMENT_ACTION_EXTENSIONS,
        prerequisites=("source_text",),
    ),
    SolomonFileActionDefinition(
        action_id="document.explain",
        label="Explain This Document",
        family=ACTION_FAMILY_UNDERSTAND,
        capability_key="can_run_document_operation",
        menu_command="explain_document",
        icon_name="lightbulb",
        target_kind="file",
        permission_requirement="query",
        execution_kind="on_demand",
        result_surface="action_result",
        # v4 adds hierarchical large-resource context qualification and lazy preparation.
        action_contract_version="4",
        result_type="explanation",
        result_format=ACTION_RESULT_FORMAT_SOLOMON_MARKDOWN_V1,
        persistence_policy=ACTION_PERSISTENCE_DURABLE,
        processor_key="solomon_file_action_intelligence",
        processor_version="4",
        execution_priority="P1",
        supported_extensions=SUPPORTED_DOCUMENT_ACTION_EXTENSIONS,
        prerequisites=("source_text",),
    ),
)

_SOLOMON_FILE_ACTIONS_BY_ID = {
    definition.action_id: definition
    for definition in SOLOMON_FILE_ACTION_MATRIX
}


def _clean_action_id(value: Any) -> str:
    return str(value or "").strip().lower()


def _clean_extension(value: Any) -> str:
    extension = str(value or "").strip().lower()

    if extension and not extension.startswith("."):
        extension = f".{extension}"

    return extension


def _resource_extension(resource: Optional[dict]) -> str:
    resolved_resource = resource if isinstance(resource, dict) else {}
    extension = _clean_extension(resolved_resource.get("extension"))

    if extension:
        return extension

    name = str(
        resolved_resource.get("original_name")
        or resolved_resource.get("name")
        or ""
    ).strip()

    if "." not in name:
        return ""

    return _clean_extension(name.rsplit(".", 1)[-1])


def _resource_supports_action(
    definition: SolomonFileActionDefinition,
    resource: Optional[dict],
) -> bool:
    if not definition.supported_extensions:
        return True

    extension = _resource_extension(resource)

    if not extension:
        return resource is None

    return extension in definition.supported_extensions


def _clean_action_ids(values: Optional[Iterable[Any]]) -> Optional[frozenset[str]]:
    if values is None:
        return None

    return frozenset(
        clean_id
        for clean_id in (
            _clean_action_id(value)
            for value in values
        )
        if clean_id
    )


def _definition_supports_single_file_profile(
    definition: SolomonFileActionDefinition,
) -> bool:
    selection_policy = str(definition.selection_policy or "").strip().lower()
    return bool(
        definition.target_kind == "file"
        and selection_policy in {"single", "single_or_multi", "any"}
    )


def solomon_file_action_registry_fingerprint() -> str:
    """Return the deterministic fingerprint for file Action applicability rules."""

    registry_payload = {
        "contract": SOLOMON_FILE_ACTION_REGISTRY_CONTRACT,
        "actions": [
            {
                "action_id": definition.action_id,
                "action_contract_version": definition.action_contract_version,
                "applicability_version": definition.applicability_version,
                "target_kind": definition.target_kind,
                "selection_policy": definition.selection_policy,
                "supported_extensions": list(definition.supported_extensions),
            }
            for definition in SOLOMON_FILE_ACTION_MATRIX
        ],
    }
    encoded = json.dumps(
        registry_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_solomon_file_action_applicability(
    resource: Optional[dict],
) -> dict:
    """Evaluate deterministic single-file applicability from the canonical registry."""

    resolved_resource = resource if isinstance(resource, dict) else {}
    applicable_action_ids = [
        definition.action_id
        for definition in SOLOMON_FILE_ACTION_MATRIX
        if _definition_supports_single_file_profile(definition)
        and _resource_supports_action(definition, resolved_resource)
    ]

    return {
        "contract": SOLOMON_FILE_ACTION_APPLICABILITY_CONTRACT,
        "registry_fingerprint": solomon_file_action_registry_fingerprint(),
        "applicable_action_ids": applicable_action_ids,
        "resource_characteristics": {
            "target_kind": "file",
            "extension": _resource_extension(resolved_resource),
        },
    }


def get_solomon_file_action_definition(
    action_id: Any,
) -> Optional[SolomonFileActionDefinition]:
    """Return one registered Action definition by stable id."""

    return _SOLOMON_FILE_ACTIONS_BY_ID.get(
        _clean_action_id(action_id)
    )


def _resolve_action_state(
    definition: SolomonFileActionDefinition,
    capabilities: Optional[dict],
    resource: Optional[dict] = None,
    applicable_action_ids: Optional[Iterable[Any]] = None,
) -> str:
    """Resolve one Action from server-owned capability and resource state."""

    if not definition.enabled or definition.rollout_state != ACTION_ROLLOUT_ACTIVE:
        return ACTION_STATE_DISABLED

    if not _resource_supports_action(definition, resource):
        return ACTION_STATE_UNAVAILABLE

    resolved_applicable_ids = _clean_action_ids(applicable_action_ids)

    if (
        resolved_applicable_ids is not None
        and definition.action_id not in resolved_applicable_ids
    ):
        return ACTION_STATE_UNAVAILABLE

    resolved_capabilities = (
        capabilities
        if isinstance(capabilities, dict)
        else {}
    )

    if resolved_capabilities.get(definition.capability_key) is True:
        return ACTION_STATE_AVAILABLE

    if definition.action_id == "summary.view" and isinstance(resource, dict):
        summary_status = str(
            resource.get("workspace_intelligence_summary_status")
            or resource.get("summary_status")
            or ""
        ).strip().lower()

        if summary_status in {"pending", "processing", "running", "queued"}:
            return ACTION_STATE_PROCESSING

    return ACTION_STATE_UNAVAILABLE


def resolve_solomon_file_action(
    action_id: Any,
    capabilities: Optional[dict],
    resource: Optional[dict] = None,
    applicable_action_ids: Optional[Iterable[Any]] = None,
) -> Optional[dict]:
    """Resolve one registered Action against authoritative runtime state."""

    definition = get_solomon_file_action_definition(
        action_id
    )

    if not definition:
        return None

    return definition.public_payload(
        _resolve_action_state(
            definition,
            capabilities,
            resource,
            applicable_action_ids,
        )
    )


def resolve_solomon_file_action_matrix(
    capabilities: Optional[dict],
    resource: Optional[dict] = None,
    applicable_action_ids: Optional[Iterable[Any]] = None,
) -> list[dict]:
    """Resolve every registered file Action against authoritative runtime state."""

    return [
        definition.public_payload(
            _resolve_action_state(
                definition,
                capabilities,
                resource,
                applicable_action_ids,
            )
        )
        for definition in SOLOMON_FILE_ACTION_MATRIX
    ]


def build_available_solomon_file_actions(
    capabilities: Optional[dict],
    resource: Optional[dict] = None,
    applicable_action_ids: Optional[Iterable[Any]] = None,
) -> list[dict]:
    """Return only Solomon Actions that the current resource can perform now."""

    return [
        action
        for action in resolve_solomon_file_action_matrix(
            capabilities,
            resource,
            applicable_action_ids,
        )
        if action.get("state") == ACTION_STATE_AVAILABLE
    ]


def build_solomon_file_action_projection(
    capabilities: Optional[dict],
    resource: Optional[dict] = None,
    applicable_action_ids: Optional[Iterable[Any]] = None,
) -> dict:
    """Return the single authoritative Action projection consumed by file surfaces."""

    available_actions = build_available_solomon_file_actions(
        capabilities,
        resource,
        applicable_action_ids,
    )

    return {
        "solomon_actions_authoritative": True,
        "solomon_actions": available_actions,
        "solomon_action_count": len(available_actions),
    }
