/* ==========================================================================
   FILE: webui/static/js/app.state.js
   DIRECTORY: webui/static/js/
   Solomon GUI State Management
   ========================================================================== */

(function () {

const GUI_STATES = {
    IDLE: "IDLE",
    EXECUTION_IN_PROGRESS: "EXECUTION_IN_PROGRESS",
    ANSWER_RENDERED: "ANSWER_RENDERED",
    ERROR_RECOVERABLE: "ERROR_RECOVERABLE"
};

let guiState = GUI_STATES.IDLE;

function isExecutionAllowed() {
    return guiState !== GUI_STATES.EXECUTION_IN_PROGRESS;
}

function hasTextInput() {
    const input = document.getElementById("taskInput");
    return Boolean(input && input.value.trim());
}

function hasAttachedDocuments() {
    const fileList = document.getElementById("uploadedFileList");
    const fileInput = document.getElementById("fileInput");

    if (fileList && fileList.children.length > 0) {
        return true;
    }

    return Boolean(fileInput?.files && fileInput.files.length > 0);
}

function setGuiState(next) {
    if (!Object.values(GUI_STATES).includes(next)) {
        console.warn("[STATE] Ignored invalid GUI state:", next);
        return;
    }

    guiState = next;
    updateRunButtonAvailability();
    updateDomState();
}

function updateDomState() {
    const root = document.getElementById("portal-root");
    const form = document.getElementById("taskForm");
    const isBusy = guiState === GUI_STATES.EXECUTION_IN_PROGRESS;

    if (root) {
        root.dataset.guiState = guiState;
    }

    if (form) {
        form.dataset.guiState = guiState;
        form.setAttribute("aria-busy", isBusy ? "true" : "false");
    }
}

function updateRunButtonAvailability() {
    const btn = document.getElementById("runButton");
    if (!btn) return;

    const hasRunnableInput = hasTextInput() || hasAttachedDocuments();
    btn.disabled = !hasRunnableInput || !isExecutionAllowed();
}

window.SolomonState = {
    GUI_STATES,
    isExecutionAllowed,
    setGuiState,
    updateRunButtonAvailability
};

updateDomState();
updateRunButtonAvailability();

})();