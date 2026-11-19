# -------------------------------------------------------------
# FILE: solomon_core/routes/command_center_context.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------
# Command Center Context Helpers
#
# PURPOSE
#   Keep Operations Console command/workflow context cleaning and CaseFile
#   snapshot attachment outside the task execution route.
# -------------------------------------------------------------

from dataclasses import replace

from solomon_core.logger import get_logger

logger = get_logger("command_center_context")


COMMAND_CENTER_MODULES = [
    {
        "id": "home",
        "label": "Operations Console",
        "route": "/",
        "status": "live",
        "purpose": "Operational overview, activity awareness, and module selection.",
        "primary_action": "Review system status and choose the next module.",
    },
    {
        "id": "documents",
        "label": "Documents",
        "route": "/docs",
        "status": "live",
        "purpose": (
            "Company file storage, browsing, upload, deletion, inspection, "
            "folder navigation, and first-party document reading through "
            "canonical FileRegistry records."
        ),
        "primary_action": (
            "Open the Documents workspace to store, browse, inspect, read, "
            "organize, or select company files before any explicit governed "
            "workflow activation."
        ),
    },
    {
        "id": "solomon_ai",
        "label": "SolomonAI",
        "route": "/ai",
        "status": "live",
        "purpose": (
            "Permission-aware document conversation, file-source selection, "
            "and operational guidance inside governed company workspaces."
        ),
        "primary_action": (
            "Open SolomonAI to ask questions using authorized company files "
            "and conversation-specific sources."
        ),
    },
    {
        "id": "people",
        "label": "People",
        "route": "/people",
        "status": "live",
        "purpose": (
            "Organization members, groups, workspace access visibility, "
            "and people-centered coordination."
        ),
        "primary_action": (
            "Review people and groups when access context or collaboration "
            "visibility matters."
        ),
    },
    {
        "id": "workflows",
        "label": "Workflows",
        "route": "/workflows",
        "status": "building",
        "purpose": (
            "Governed document actions, approvals, reviews, and repeatable "
            "business processes."
        ),
        "primary_action": "Review available workflows when the module is activated.",
    },
    {
        "id": "activity",
        "label": "Activity",
        "route": "/activity",
        "status": "building",
        "purpose": (
            "Operational activity, updates, status movement, and recent "
            "workspace events."
        ),
        "primary_action": "Review activity when the module is activated.",
    },
    {
        "id": "quality",
        "label": "Quality & Issue Control",
        "route": "/quality",
        "status": "building",
        "purpose": (
            "Issues, checks, deficiencies, exceptions, and follow-up tracking."
        ),
        "primary_action": "Review quality activity when the module is activated.",
    },
    {
        "id": "communication",
        "label": "Communication",
        "route": "/comms",
        "status": "building",
        "purpose": (
            "Meeting records, action items, summaries, and coordination support."
        ),
        "primary_action": "Review communication activity when the module is activated.",
    },
    {
        "id": "management",
        "label": "Management Dashboard",
        "route": "/management",
        "status": "building",
        "purpose": (
            "Operational visibility, open items, aging issues, blocked activity, "
            "and management summaries."
        ),
        "primary_action": "Review management activity when the module is activated.",
    },
]


def _clean_string(value, fallback="", max_chars=160):
    if not isinstance(value, str):
        return fallback

    return value.strip()[:max_chars]


def _clean_command_context(value):
    if not isinstance(value, dict):
        return {}

    return {
        "route": _clean_string(value.get("route"), "/"),
        "module": _clean_string(value.get("module"), "home"),
        "module_label": _clean_string(value.get("module_label"), "Operations Console"),
        "module_status": _clean_string(value.get("module_status"), "unknown"),
        "live_workflow": _clean_string(value.get("live_workflow"), ""),
        "workspace_mode": _clean_string(value.get("workspace_mode"), "operations_console"),
    }


def _clean_workflow_context(payload):
    workflow = payload.get("workflow")

    if not isinstance(workflow, dict):
        workflow = {}

    return {
        "workflow_id": _clean_string(payload.get("workflow_id"), ""),
        "input_mode": _clean_string(payload.get("input_mode"), ""),
        "workflow": {
            "id": _clean_string(workflow.get("id"), ""),
            "module": _clean_string(workflow.get("module"), ""),
            "requested_action": _clean_string(workflow.get("requested_action"), ""),
        },
    }


def _build_command_center_manifest(active_module):
    modules = []

    for item in COMMAND_CENTER_MODULES:
        modules.append({
            "id": item["id"],
            "label": item["label"],
            "route": item["route"],
            "status": item["status"],
            "purpose": item["purpose"],
            "primary_action": item["primary_action"],
            "is_current": item["id"] == active_module,
        })

    live_modules = [
        item for item in modules
        if item["status"] == "live"
    ]

    return {
        "company": "Nations Systems",
        "product": "Enterprise Operations Suite",
        "interface": "Operations Console",
        "intelligence_layer": "SolomonAI",
        "assistant_role": (
            "SolomonAI is the docked operational guide inside the Operations "
            "Console. It explains the current workspace, recommends the next "
            "relevant action, and routes users toward available modules without "
            "inventing unavailable features."
        ),
        "modules": modules,
        "live_modules": live_modules,
        "rules": [
            "Recommend live modules before unavailable modules.",
            "Do not claim building modules are fully available.",
            "Use the current route and selected module when answering.",
            "Prefer concise operational guidance over generic chatbot answers.",
            "Treat Documents as the live storage and file-management substrate.",
            "Treat Document Analysis as an explicit governed review workflow.",
            "Do not imply that uploading a document automatically starts analysis.",
            "Only describe workflow activation as explicit user-directed action.",
        ],
    }


def _attach_snapshot_context(casefile, key, value, failure_log_code):
    if casefile is None:
        return None

    current_snapshot = getattr(casefile, "intent_snapshot", None)
    if not isinstance(current_snapshot, dict):
        current_snapshot = {}

    next_snapshot = {
        **current_snapshot,
        key: value,
    }

    try:
        return replace(casefile, intent_snapshot=next_snapshot)
    except Exception:
        logger.warning(failure_log_code)
        return casefile


def _attach_command_center_context(casefile, command_context, manifest):
    return _attach_snapshot_context(
        casefile=casefile,
        key="command_context",
        value=command_context,
        failure_log_code="[API][CONTEXT_ATTACH_FAILED]",
    ) if casefile is not None else None


def _attach_command_center_manifest(casefile, manifest):
    return _attach_snapshot_context(
        casefile=casefile,
        key="command_center_manifest",
        value=manifest,
        failure_log_code="[API][MANIFEST_ATTACH_FAILED]",
    ) if casefile is not None else None


def _attach_workflow_context(casefile, workflow_context):
    if casefile is None:
        return None

    if not any(workflow_context.values()):
        return casefile

    return _attach_snapshot_context(
        casefile=casefile,
        key="workflow_context",
        value=workflow_context,
        failure_log_code="[API][WORKFLOW_CONTEXT_ATTACH_FAILED]",
    )