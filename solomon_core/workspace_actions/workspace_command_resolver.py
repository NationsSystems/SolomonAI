# -------------------------------------------------------------
# FILE: workspace_command_resolver.py
# DIRECTORY: solomon_core/workspace_actions/
# -------------------------------------------------------------
# Workspace Command Resolver
#
# PURPOSE
#   Resolve compact SolomonAI workspace commands into server-owned
#   response packets without placing static response authority inside
#   route handlers or presentation JavaScript.
# -------------------------------------------------------------

WORKSPACE_COMMAND_PACKET_TYPE = "workspace_command"
WORKSPACE_COMMAND_SOURCE = "v3_workspace_command"

DEFAULT_SUGGESTIONS = [
    "Open document library",
    "Show available workflows",
    "Start Document Analysis",
]

WORKSPACE_GUIDANCE = {
    "home": {
        "answer": (
            "Use Home for general guidance. Open a workspace when you are ready "
            "to handle documents, reviews, records, or governed actions."
        ),
        "suggestions": [
            "Open document library",
            "Show available workflows",
            "Start Document Analysis",
        ],
    },
    "documents": {
        "answer": (
            "Upload, preview, organize, and select company files here. Analysis "
            "starts only after a selected file is handed to a governed workflow."
        ),
        "suggestions": [
            "Upload company documents",
            "Start Document Analysis",
            "Show available workflows",
        ],
    },
    "document_analysis": {
        "answer": (
            "Use Document Analysis for selected files, pasted text, key details, "
            "missing information, notable issues, and decision-ready risk signals."
        ),
        "suggestions": [
            "Open document library",
            "Upload company documents",
            "Show available workflows",
        ],
    },
    "management": {
        "answer": (
            "Use Management for operational visibility, records, open items, "
            "blocked activity, and management summaries as workflows come online."
        ),
        "suggestions": [
            "Open document library",
            "Show available workflows",
        ],
    },
    "activity": {
        "answer": (
            "Use Activity for operational updates, status movement, recent events, "
            "and workspace activity as those workflows come online."
        ),
        "suggestions": [
            "Open document library",
            "Show available workflows",
        ],
    },
    "quality": {
        "answer": (
            "Use Quality for issues, checks, exceptions, and follow-up tracking "
            "as those workflows come online."
        ),
        "suggestions": [
            "Open document library",
            "Show available workflows",
        ],
    },
    "communication": {
        "answer": (
            "Use Communication for messages, meeting notes, action items, "
            "summaries, and coordination support as workflows come online."
        ),
        "suggestions": [
            "Open document library",
            "Show available workflows",
        ],
    },
    "finance": {
        "answer": (
            "Use Finance for cost, billing, commercial records, and financial "
            "review support as those workflows come online."
        ),
        "suggestions": [
            "Open document library",
            "Show available workflows",
        ],
    },
    "people": {
        "answer": (
            "Use People for members, roles, groups, access visibility, and "
            "people-centered coordination."
        ),
        "suggestions": [
            "Open document library",
            "Show available workflows",
        ],
    },
}


def _normalize_command_text(task_text):
    clean_text = str(task_text or "").strip().lower()
    clean_text = clean_text.replace("&", " and ")
    clean_text = clean_text.replace("/", " ")
    clean_text = clean_text.replace("-", " ")

    return " ".join(clean_text.split())


def _text_has_any(text, phrases):
    return any(phrase in text for phrase in phrases)


def _read_context_value(*contexts, key):
    for context in contexts:
        if isinstance(context, dict):
            value = context.get(key)

            if isinstance(value, str) and value.strip():
                return value.strip()

    return ""


def _current_module(command_context, workspace_context):
    module_id = _read_context_value(
        workspace_context,
        command_context,
        key="module",
    ).lower()

    if module_id:
        return module_id

    route = _read_context_value(
        workspace_context,
        command_context,
        key="route",
    ).lower()

    if route.startswith("/docs"):
        return "documents"

    if route.startswith("/workspace/document-operation"):
        return "document_analysis"

    if route.startswith("/document-analysis"):
        return "document_analysis"

    if route.startswith("/activity"):
        return "activity"

    if route.startswith("/quality"):
        return "quality"

    if route.startswith("/comms"):
        return "communication"

    if route.startswith("/finance"):
        return "finance"

    if route.startswith("/people"):
        return "people"

    return "home"


def _workspace_workflow_items(command_manifest):
    workflows = {}

    if isinstance(command_manifest, dict):
        workflows = (
            command_manifest.get("supported_workflows")
            or command_manifest.get("workflows")
            or {}
        )

    items = []

    if isinstance(workflows, dict):
        for workflow_id, workflow in workflows.items():
            if isinstance(workflow, dict):
                label = str(workflow.get("label") or workflow_id or "").strip()
                description = str(workflow.get("description") or "").strip()
            else:
                label = str(workflow_id or "").strip()
                description = ""

            if label:
                items.append({
                    "label": label,
                    "description": description,
                })

    if items:
        return items

    return [{
        "label": "Document Analysis",
        "description": (
            "Review selected files, pasted text, key details, missing information, "
            "notable issues, and decision-ready risk signals through a governed "
            "document workflow."
        ),
    }]


def _workspace_command_packet(command_id, answer, *, suggestions=None, ui_actions=None):
    return {
        "ok": True,
        "packet_type": WORKSPACE_COMMAND_PACKET_TYPE,
        "payload": {
            "type": "response",
            "source": WORKSPACE_COMMAND_SOURCE,
            "command_id": command_id,
            "answer": answer,
            "bridge": "",
            "suggestions": suggestions or [],
            "ui_actions": ui_actions or [],
        },
    }


def _workflow_list_answer(command_manifest):
    workflow_items = _workspace_workflow_items(command_manifest)
    labels = [item["label"] for item in workflow_items]
    joined_labels = ", ".join(labels)

    if len(workflow_items) == 1:
        return f"Available workflow: {labels[0]}."

    return f"Available workflows: {joined_labels}."


def _workspace_help_packet(command_context, workspace_context):
    module_id = _current_module(command_context, workspace_context)
    guidance = WORKSPACE_GUIDANCE.get(module_id) or WORKSPACE_GUIDANCE["home"]

    return _workspace_command_packet(
        "workspace_help",
        guidance["answer"],
        suggestions=guidance.get("suggestions") or DEFAULT_SUGGESTIONS,
    )


def resolve_workspace_command(
    *,
    task_text,
    command_manifest,
    command_context=None,
    workspace_context=None,
):
    normalized_text = _normalize_command_text(task_text)

    if not normalized_text:
        return _workspace_command_packet(
            "empty_workspace_command",
            "Ask for a workspace action, document path, or next step.",
            suggestions=DEFAULT_SUGGESTIONS,
        )

    if (
        "workflow" in normalized_text
        and _text_has_any(normalized_text, ("available", "show", "list", "what"))
    ):
        return _workspace_command_packet(
            "available_workflows",
            _workflow_list_answer(command_manifest),
            suggestions=[
                "Start Document Analysis",
                "Open document library",
                "Upload company documents",
            ],
        )

    if _text_has_any(normalized_text, ("what can i do", "help", "how do i use")):
        return _workspace_help_packet(command_context, workspace_context)

    if _text_has_any(normalized_text, ("file type", "file format", "supported files")):
        return _workspace_command_packet(
            "supported_document_formats",
            "Supported previews include PDF, DOCX, XLSX, TXT, CSV, PNG, JPG, and JPEG.",
            suggestions=[
                "Open document library",
                "Upload company documents",
            ],
        )

    if _text_has_any(normalized_text, ("document", "docs", "library", "uploads", "files")):
        return _workspace_command_packet(
            "documents_guidance",
            (
                "Documents stores, previews, organizes, and selects files. "
                "Analysis starts only from an explicit governed workflow."
            ),
            suggestions=[
                "Open document library",
                "Upload company documents",
                "Start Document Analysis",
            ],
        )

    if _text_has_any(
        normalized_text,
        (
            "analysis",
            "analyze",
            "analyse",
            "review",
            "summarize",
            "extract",
            "issues",
            "missing information",
            "risk signals",
        ),
    ):
        return _workspace_command_packet(
            "document_analysis_guidance",
            (
                "Document Analysis starts from selected files or prepared text "
                "and returns governed review output."
            ),
            suggestions=[
                "Start Document Analysis",
                "Upload company documents",
                "Open document library",
            ],
        )

    return _workspace_command_packet(
        "bounded_workspace_command",
        "I can point you to the right workspace or explain the next governed step.",
        suggestions=DEFAULT_SUGGESTIONS,
    )