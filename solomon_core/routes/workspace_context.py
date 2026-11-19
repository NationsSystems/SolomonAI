# -------------------------------------------------------------
# FILE: solomon_core/routes/workspace_context.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------
# Workspace Context Helpers
#
# PURPOSE
#   Clean and attach neutral workspace hints for Workspace-Aware SolomonAI.
#
# CONTRACT
#   - Domain/module neutral.
#   - Browser payload is a hint envelope, not authority.
#   - No BEI-specific loading or review-record coupling.
#   - CaseFile/Investigator/Orchestrator remain the authority path for
#     explicit governed workflow execution.
# -------------------------------------------------------------

from dataclasses import replace

from solomon_core.logger import get_logger

logger = get_logger("workspace_context")

_WORKSPACE_CONTEXT_SCHEMA = "solomon_workspace_context_v1"
_MAX_SELECTED_TEXT_CHARS = 1200
_MAX_SECTION_CHARS = 240
_MAX_CONTEXT_VALUE_CHARS = 180


def _clean_string(value, fallback="", max_chars=_MAX_CONTEXT_VALUE_CHARS):
    if not isinstance(value, str):
        return fallback

    return value.strip()[:max_chars]


def _clean_bool(value, fallback=True):
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False

    return fallback


def _clean_workspace_context(value):
    if not isinstance(value, dict):
        return {}

    return {
        "schema": _clean_string(
            value.get("schema"),
            _WORKSPACE_CONTEXT_SCHEMA,
            80,
        ),
        "source": _clean_string(value.get("source"), "command_center_assistant", 80),
        "route": _clean_string(value.get("route"), "/", 180),
        "pro_library": _clean_string(value.get("pro_library"), "", 120),
        "module": _clean_string(value.get("module"), "", 120),
        "module_label": _clean_string(value.get("module_label"), "", 160),
        "module_status": _clean_string(value.get("module_status"), "", 80),
        "live_workflow": _clean_string(value.get("live_workflow"), "", 120),
        "workspace_mode": _clean_string(value.get("workspace_mode"), "", 120),
        "command_surface": _clean_string(value.get("command_surface"), "", 120),
        "command_mode": _clean_string(value.get("command_mode"), "", 120),
        "active_record_id": _clean_string(value.get("active_record_id"), "", 120),
        "active_record_kind": _clean_string(value.get("active_record_kind"), "", 120),
        "review_id": _clean_string(value.get("review_id"), "", 80),
        "active_section": _clean_string(
            value.get("active_section"),
            "",
            _MAX_SECTION_CHARS,
        ),
        "selected_text": _clean_string(
            value.get("selected_text"),
            "",
            _MAX_SELECTED_TEXT_CHARS,
        ),
        "trusted_context_required": _clean_bool(
            value.get("trusted_context_required"),
            True,
        ),
    }


def _workspace_context_has_hints(workspace_context):
    if not isinstance(workspace_context, dict):
        return False

    meaningful_keys = (
        "route",
        "pro_library",
        "module",
        "module_label",
        "live_workflow",
        "workspace_mode",
        "command_surface",
        "command_mode",
        "active_record_id",
        "active_record_kind",
        "review_id",
        "active_section",
        "selected_text",
    )

    for key in meaningful_keys:
        value = workspace_context.get(key)
        if isinstance(value, str) and value.strip():
            return True

    return False


def _attach_workspace_context(casefile, workspace_context):
    if casefile is None:
        return None

    if not _workspace_context_has_hints(workspace_context):
        return casefile

    current_snapshot = getattr(casefile, "intent_snapshot", None)
    if not isinstance(current_snapshot, dict):
        current_snapshot = {}

    next_snapshot = {
        **current_snapshot,
        "workspace_context": workspace_context,
    }

    try:
        return replace(casefile, intent_snapshot=next_snapshot)
    except Exception:
        logger.warning("[API][WORKSPACE_CONTEXT_ATTACH_FAILED]")
        return casefile