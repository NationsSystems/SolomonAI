/* ==========================================================================
   FILE: admin_errors.js
   DIRECTORY: SolomonV3/webui/static/js/admin/
   ========================================================================== */

(function () {
    "use strict";

    const ERRORS_DATA_ENDPOINT = "/admin/errors/data";
    const ERRORS_CLEAR_ENDPOINT = "/admin/errors/clear";

    const errorsContainer = () => document.getElementById("errors");
    const notice = () => document.getElementById("adminErrorsNotice");
    const loadButton = () => document.getElementById("loadErrorsBtn");
    const clearButton = () => document.getElementById("clearErrorsBtn");

    function textOrDash(value) {
        return value === null || value === undefined || value === "" ? "—" : String(value);
    }

    function setNotice(message, isError) {
        const element = notice();
        if (!element) return;

        element.hidden = !message;
        element.textContent = message || "";
        element.dataset.noticeType = isError ? "error" : "info";
    }

    function showToast(message, type) {
        if (typeof window.adminToast === "function") {
            window.adminToast(message, type || "info");
            return;
        }

        setNotice(message, type === "error");
    }

    async function confirmAction(message, mode) {
        if (typeof window.adminConfirm === "function") {
            return window.adminConfirm(message, mode);
        }

        showToast("Confirmation control is unavailable.", "error");
        return false;
    }

    async function requestJson(url, options) {
        const response = await fetch(url, options || {});
        const data = await response.json().catch(() => null);

        if (!response.ok || !data) {
            throw new Error("Request failed");
        }

        return data;
    }

    function clearErrorsContainer(message) {
        const container = errorsContainer();
        if (!container) return;

        container.innerHTML = "";

        const empty = document.createElement("div");
        empty.className = "admin-empty-state";
        empty.textContent = message;

        container.appendChild(empty);
    }

    function createMetaRow(label, value) {
        const row = document.createElement("div");
        const labelElement = document.createElement("strong");
        const valueElement = document.createElement("span");

        row.className = "admin-record-row";

        labelElement.textContent = `${label}: `;
        valueElement.textContent = textOrDash(value);

        row.appendChild(labelElement);
        row.appendChild(valueElement);

        return row;
    }

    function createTraceback(traceback) {
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        const pre = document.createElement("pre");

        details.className = "admin-record-details";
        summary.textContent = "Traceback";
        pre.className = "diagnostic-pre";
        pre.textContent = traceback;

        details.appendChild(summary);
        details.appendChild(pre);

        return details;
    }

    function createDeleteButton(errorId) {
        const button = document.createElement("button");

        button.type = "button";
        button.className = "admin-action admin-action-danger";
        button.textContent = "Delete";
        button.addEventListener("click", () => confirmDelete(errorId));

        return button;
    }

    function createErrorCard(errorEvent) {
        const card = document.createElement("article");
        const header = document.createElement("div");
        const title = document.createElement("h3");
        const timestamp = document.createElement("span");
        const body = document.createElement("div");
        const actions = document.createElement("div");

        card.className = "admin-record-card";
        card.id = `error-${errorEvent.id}`;

        header.className = "admin-record-header";
        title.className = "admin-record-title";
        timestamp.className = "admin-record-meta";
        body.className = "admin-record-body";
        actions.className = "admin-action-row";

        title.textContent = textOrDash(errorEvent.error_type || "System Error");
        timestamp.textContent = textOrDash(errorEvent.created_at);

        header.appendChild(title);
        header.appendChild(timestamp);

        body.appendChild(createMetaRow("Phase", errorEvent.phase || "unknown"));
        body.appendChild(createMetaRow("Occurrences", errorEvent.count ?? 1));
        body.appendChild(createMetaRow("Message", errorEvent.message || "(no message)"));

        if (errorEvent.traceback) {
            body.appendChild(createTraceback(errorEvent.traceback));
        }

        actions.appendChild(createDeleteButton(errorEvent.id));

        card.appendChild(header);
        card.appendChild(body);
        card.appendChild(actions);

        return card;
    }

    function renderErrors(errors) {
        const container = errorsContainer();
        if (!container) return;

        container.innerHTML = "";

        if (!Array.isArray(errors) || errors.length === 0) {
            clearErrorsContainer("No errors recorded.");
            return;
        }

        errors.forEach((errorEvent) => {
            container.appendChild(createErrorCard(errorEvent));
        });
    }

    async function loadErrors() {
        setNotice("");
        clearErrorsContainer("Loading errors...");

        try {
            const data = await requestJson(ERRORS_DATA_ENDPOINT);

            if (!data || data.status !== "ok") {
                clearErrorsContainer("Unable to load error events.");
                showToast("Unable to load error events.", "error");
                return;
            }

            renderErrors(data.errors);
            showToast("Error events loaded.", "success");
        } catch {
            clearErrorsContainer("Error loading the error list.");
            showToast("Error loading the error list.", "error");
        }
    }

    async function confirmDelete(errorId) {
        const confirmed = await confirmAction(
            "Delete this error entry permanently?",
            "danger"
        );

        if (!confirmed) return;

        try {
            const data = await requestJson(
                `/admin/errors/delete/${errorId}`,
                { method: "POST" }
            );

            if (data.status !== "ok") {
                showToast("Unable to delete error entry.", "error");
                return;
            }

            document.getElementById(`error-${errorId}`)?.remove();

            const container = errorsContainer();
            if (container && container.children.length === 0) {
                clearErrorsContainer("No errors recorded.");
            }

            showToast("Error entry deleted.", "success");
        } catch {
            showToast("Unable to delete error entry.", "error");
        }
    }

    async function confirmClearAll() {
        const confirmed = await confirmAction(
            "This will permanently remove all error entries. Continue?",
            "danger"
        );

        if (!confirmed) return;

        try {
            const data = await requestJson(ERRORS_CLEAR_ENDPOINT, { method: "POST" });

            if (data.status !== "ok") {
                showToast("Unable to clear errors.", "error");
                return;
            }

            clearErrorsContainer("No errors recorded.");
            showToast("All error entries cleared.", "success");
        } catch {
            showToast("Unable to clear errors.", "error");
        }
    }

    function bindEvents() {
        const load = loadButton();
        const clear = clearButton();

        if (load) load.addEventListener("click", loadErrors);
        if (clear) clear.addEventListener("click", confirmClearAll);
    }

    document.addEventListener("DOMContentLoaded", () => {
        bindEvents();
    });

    window.loadAdminErrors = loadErrors;
}());