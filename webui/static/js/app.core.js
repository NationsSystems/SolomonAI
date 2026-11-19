/* ==========================================================================
   FILE: webui/static/js/app.core.js
   DIRECTORY: webui/static/js/
   Solomon Portal — Explicit Workflow Core Orchestrator
   ========================================================================== */

(function () {

console.log("[CORE] app.core.js loaded");

/* ---------------------------------------------------------------------------
   ELEMENT REFERENCES
--------------------------------------------------------------------------- */
const form = document.getElementById("taskForm");
const taskInput = document.getElementById("taskInput");
const runButton = document.getElementById("runButton");
const fileInput = document.getElementById("fileInput");

/* ---------------------------------------------------------------------------
   SAFETY GUARD
--------------------------------------------------------------------------- */
if (!form || !taskInput || !runButton) {
    console.debug("[CORE] Portal DOM not present — core logic skipped.");
    return;
}

if (!window.SolomonCore || typeof window.SolomonCore.executeTask !== "function") {
    console.error("[CORE] SolomonCore.executeTask is unavailable.");
    return;
}

if (!window.SolomonState) {
    console.error("[CORE] SolomonState is unavailable.");
    return;
}

/* ---------------------------------------------------------------------------
   EVENT HELPERS
--------------------------------------------------------------------------- */
function executeCurrentWorkflow() {
    window.SolomonCore.executeTask();
}

function updateAvailability() {
    if (typeof window.SolomonState.updateRunButtonAvailability === "function") {
        window.SolomonState.updateRunButtonAvailability();
    }
}

/* ---------------------------------------------------------------------------
   EVENT WIRING
--------------------------------------------------------------------------- */
taskInput.addEventListener("keydown", e => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        executeCurrentWorkflow();
    }
});

taskInput.addEventListener("input", updateAvailability);

if (fileInput) {
    fileInput.addEventListener("change", updateAvailability);
}

form.addEventListener("submit", e => {
    e.preventDefault();
    e.stopPropagation();
    executeCurrentWorkflow();
});

/* ---------------------------------------------------------------------------
   INIT
--------------------------------------------------------------------------- */
updateAvailability();

})();