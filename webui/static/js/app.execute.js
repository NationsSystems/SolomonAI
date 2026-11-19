/* ==========================================================================
   FILE: webui/static/js/app.execute.js
   DIRECTORY: webui/static/js/
   Solomon Explicit Workflow Transport
   ========================================================================== */

(function () {

const DEFAULT_WORKFLOW_ID = "pre_award_risk_review";
const DEFAULT_WORKFLOW_ENDPOINT = "/api/task/execute";

function getTaskInput() {
    return document.getElementById("taskInput");
}

function getTaskForm() {
    return document.getElementById("taskForm");
}

function getUploadedFileList() {
    return document.getElementById("uploadedFileList");
}

function getFileInput() {
    return document.getElementById("fileInput");
}

function cleanValue(value) {
    return String(value || "").trim();
}

function getWorkflowId() {
    const form = getTaskForm();
    const hiddenWorkflow = document.getElementById("workflowId");

    return cleanValue(
        hiddenWorkflow?.value ||
        form?.dataset?.workflowId ||
        DEFAULT_WORKFLOW_ID
    );
}

function getWorkflowEndpoint() {
    const form = getTaskForm();

    return cleanValue(
        form?.dataset?.workflowEndpoint ||
        DEFAULT_WORKFLOW_ENDPOINT
    );
}

function hasPendingFileInputDocuments() {
    const fileInput = getFileInput();
    return Boolean(fileInput?.files && fileInput.files.length > 0);
}

function normalizeAttachedDocument(node) {
    if (!node) {
        return null;
    }

    const dataset = node.dataset || {};
    const visibleName = cleanValue(node.textContent);

    const documentId = cleanValue(
        dataset.documentId ||
        dataset.uploadId ||
        dataset.fileId ||
        dataset.id
    );

    const originalName = cleanValue(
        dataset.originalName ||
        dataset.filename ||
        dataset.fileName ||
        dataset.name ||
        visibleName
    );

    const randomName = cleanValue(
        dataset.randomName ||
        dataset.storageName ||
        dataset.savedName
    );

    if (!documentId && !originalName && !randomName) {
        return null;
    }

    return {
        document_id: documentId,
        upload_id: cleanValue(dataset.uploadId || documentId),
        file_id: cleanValue(dataset.fileId || documentId),
        original_name: originalName,
        filename: originalName,
        random_name: randomName
    };
}

function getAttachedDocuments() {
    const fileList = getUploadedFileList();

    if (!fileList || fileList.children.length === 0) {
        return [];
    }

    return Array.from(fileList.children)
        .map(normalizeAttachedDocument)
        .filter(Boolean);
}

function getAttachmentIds(attachedDocuments) {
    return attachedDocuments
        .map((document) => (
            document.document_id ||
            document.upload_id ||
            document.file_id ||
            document.random_name
        ))
        .filter(Boolean);
}

function hasAttachedDocuments() {
    return getAttachedDocuments().length > 0 || hasPendingFileInputDocuments();
}

function getInputMode(rawText, attachedDocuments) {
    if (rawText && attachedDocuments.length > 0) {
        return "documents_and_text";
    }

    if (attachedDocuments.length > 0 || hasPendingFileInputDocuments()) {
        return "documents";
    }

    return "paste_text";
}

function getActiveModule() {
    const path = window.location.pathname || "/";

    if (path.startsWith("/preconstruction")) {
        return {
            module: "preconstruction",
            module_label: "Preconstruction Intelligence",
            module_status: "live",
            live_workflow: "Bid & Scope Review"
        };
    }

    return {
        module: "home",
        module_label: "Operations Console",
        module_status: "live",
        live_workflow: ""
    };
}

function buildCommandContext() {
    const activeModule = getActiveModule();

    return {
        route: window.location.pathname || "/",
        module: activeModule.module,
        module_label: activeModule.module_label,
        module_status: activeModule.module_status,
        live_workflow: activeModule.live_workflow,
        workspace_mode: "operations_console"
    };
}

function buildTaskText(rawText, workflowId, attachedDocuments) {
    if (rawText) {
        return rawText;
    }

    if (attachedDocuments.length > 0 || hasPendingFileInputDocuments()) {
        return workflowId;
    }

    return "";
}

function buildWorkflowPayload(rawText) {
    const attachedDocuments = getAttachedDocuments();
    const attachmentIds = getAttachmentIds(attachedDocuments);
    const workflowId = getWorkflowId();

    return {
        task: buildTaskText(rawText, workflowId, attachedDocuments),
        workflow_id: workflowId,
        input_mode: getInputMode(rawText, attachedDocuments),
        command_context: buildCommandContext(),
        workflow: {
            id: workflowId,
            module: "preconstruction",
            requested_action: "document_review"
        },
        documents: attachedDocuments,
        uploaded_documents: attachedDocuments,
        attachment_ids: attachmentIds
    };
}

function showInputRequiredMessage() {
    window.Solomon?.ui?.appendSystemMessage?.(
        "Paste review text or add documents before building a workspace.",
        "info"
    );
}

function showExecutionStartedState() {
    if (window.SolomonRender?.showProcessingState) {
        window.SolomonRender.showProcessingState();
        return;
    }

    window.Solomon?.ui?.showThinkingIndicator?.();
}

async function readJsonResponse(response) {
    try {
        return await response.json();
    } catch {
        return {
            ok: false,
            error: "InvalidServerResponse",
            user_output: "The server returned an unreadable response."
        };
    }
}

async function executeTask() {
    const taskInput = getTaskInput();
    const raw = cleanValue(taskInput?.value);
    const hasDocuments = hasAttachedDocuments();

    if (!raw && !hasDocuments) {
        showInputRequiredMessage();
        return;
    }

    if (!window.SolomonState.isExecutionAllowed()) {
        console.warn("[CORE] Execution blocked by GUI state.");
        return;
    }

    const workflowId = getWorkflowId();
    const endpoint = getWorkflowEndpoint();

    showExecutionStartedState();

    window.SolomonState.setGuiState(
        window.SolomonState.GUI_STATES.EXECUTION_IN_PROGRESS
    );

    if (taskInput) {
        taskInput.value = "";
    }

    try {
        const response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(buildWorkflowPayload(raw))
        });

        const data = await readJsonResponse(response);

        if (!response.ok && !data.error) {
            data.error = "WorkflowRequestFailed";
            data.user_output = "The workflow request failed.";
        }

        data.workflow_id = data.workflow_id || workflowId;

        window.SolomonRender.renderExecutionResponse(data);

    } catch {
        window.Solomon?.ui?.appendSystemMessage?.(
            "Workflow execution timed out or failed. You can retry.",
            "error"
        );

        window.SolomonState.setGuiState(
            window.SolomonState.GUI_STATES.ERROR_RECOVERABLE
        );
    }
}

window.SolomonCore = {
    executeTask
};

})();