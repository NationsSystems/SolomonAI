/* ==========================================================================
   FILE: webui/static/js/app.ui.render.js
   DIRECTORY: webui/static/js/
   Solomon Workspace — UI Rendering
   ========================================================================== */

window.Solomon = window.Solomon || {};
window.Solomon.ui = window.Solomon.ui || {};

(function () {

const ui = window.Solomon.ui;

/* ---------------------------------------------------------------------------
   TEXT NORMALIZATION
--------------------------------------------------------------------------- */
function normalizeDisplayText(value) {
    if (!value) return "";

    return String(value)
        .replace(/\r\n/g, "\n")
        .split("\n")
        .map(line => line.replace(/[ \t]+$/g, ""))
        .join("\n")
        .replace(/\n{3,}/g, "\n\n")
        .trim();
}

function resolveDisplayPayload(input) {
    if (!input) {
        return {
            text: "",
            html: "",
            label: "System"
        };
    }

    if (typeof input === "string") {
        return {
            text: input,
            html: "",
            label: "System"
        };
    }

    if (typeof input !== "object") {
        return {
            text: String(input),
            html: "",
            label: "System"
        };
    }

    const payload =
        input.payload && typeof input.payload === "object"
            ? input.payload
            : input;

    const html =
        typeof payload.html === "string"
            ? payload.html
            : typeof payload.report_html === "string"
            ? payload.report_html
            : "";

    const text =
        typeof payload.user_output === "string"
            ? payload.user_output
            : typeof payload.answer === "string"
            ? payload.answer
            : typeof payload.text === "string"
            ? payload.text
            : typeof input.user_output === "string"
            ? input.user_output
            : typeof input.answer === "string"
            ? input.answer
            : "";

    const label =
        typeof payload.label === "string"
            ? payload.label
            : typeof input.label === "string"
            ? input.label
            : "System";

    return {
        text,
        html,
        label
    };
}

/* ---------------------------------------------------------------------------
   EVENT LOG HELPERS
--------------------------------------------------------------------------- */
function getWorkspaceEventLog() {
    if (!ui.conversation) return null;

    let eventLog = ui.conversation.querySelector("[data-workspace-event-log]");

    if (!eventLog) {
        eventLog = document.createElement("div");
        eventLog.className = "workspace-event-log";
        eventLog.dataset.workspaceEventLog = "true";
        ui.conversation.appendChild(eventLog);
    }

    return eventLog;
}

function createWorkspaceEvent({ label, body, html, type }) {
    const event = document.createElement("article");
    event.className = `workspace-event workspace-event--${type || "system"}`;

    const header = document.createElement("header");
    header.className = "workspace-event-header";

    const labelEl = document.createElement("span");
    labelEl.className = "workspace-event-label";
    labelEl.textContent = label || "System";

    const timeEl = document.createElement("span");
    timeEl.className = "workspace-event-time";
    timeEl.textContent = ui.formatTimestamp ? ui.formatTimestamp() : "";

    header.appendChild(labelEl);
    header.appendChild(timeEl);

    const content = document.createElement("div");
    content.className = "workspace-event-body";

    if (html) {
        content.innerHTML = html;
    } else {
        content.textContent = body || "";
    }

    event.appendChild(header);
    event.appendChild(content);

    return event;
}

function appendWorkspaceEvent(event) {
    const eventLog = getWorkspaceEventLog();
    if (!eventLog || !event) return;

    eventLog.appendChild(event);
    ui.maybeAutoScroll?.();
}

/* ---------------------------------------------------------------------------
   THINKING INDICATOR
--------------------------------------------------------------------------- */
ui.showThinkingIndicator = function () {
    ui.activatePortal?.();
    ui.removeThinkingIndicator?.();

    const eventLog = getWorkspaceEventLog();
    if (!eventLog) return;

    ui.thinkingMsg = document.createElement("article");
    ui.thinkingMsg.className = "workspace-event workspace-event--thinking";

    const header = document.createElement("header");
    header.className = "workspace-event-header";

    const label = document.createElement("span");
    label.className = "workspace-event-label";
    label.textContent = "Processing";

    const time = document.createElement("span");
    time.className = "workspace-event-time";
    time.textContent = ui.formatTimestamp ? ui.formatTimestamp() : "";

    header.appendChild(label);
    header.appendChild(time);

    const body = document.createElement("div");
    body.className = "workspace-event-body";

    const dots = document.createElement("span");
    dots.className = "workspace-thinking-dots";
    dots.textContent = "Working";

    body.appendChild(dots);
    ui.thinkingMsg.appendChild(header);
    ui.thinkingMsg.appendChild(body);

    eventLog.appendChild(ui.thinkingMsg);
    ui.maybeAutoScroll?.();

    let step = 0;
    ui.thinkingInterval = setInterval(() => {
        step = (step + 1) % 4;
        dots.textContent = "Working" + ".".repeat(step || 1);
    }, 450);
};

ui.removeThinkingIndicator = function () {
    if (ui.thinkingInterval) {
        clearInterval(ui.thinkingInterval);
        ui.thinkingInterval = null;
    }

    if (ui.thinkingMsg) {
        ui.thinkingMsg.remove();
        ui.thinkingMsg = null;
    }
};

/* ---------------------------------------------------------------------------
   USER EVENT
--------------------------------------------------------------------------- */
ui.appendUserMessage = function (text) {
    const body = normalizeDisplayText(text);
    if (!body) return;

    ui.cancelInitialGreeting?.();
    ui.activatePortal?.();

    appendWorkspaceEvent(
        createWorkspaceEvent({
            label: "Workspace Request",
            body,
            html: "",
            type: "user"
        })
    );
};

/* ---------------------------------------------------------------------------
   SYSTEM EVENT
--------------------------------------------------------------------------- */
ui.appendSystemMessage = function (input, type = "answer") {
    ui.removeThinkingIndicator?.();
    ui.activatePortal?.();

    const resolved = resolveDisplayPayload(input);
    const body = normalizeDisplayText(resolved.text);
    const html = normalizeDisplayText(resolved.html);

    if (!body && !html) return;

    appendWorkspaceEvent(
        createWorkspaceEvent({
            label: type === "error" ? "System Notice" : resolved.label,
            body,
            html,
            type: type === "error" ? "error" : "system"
        })
    );
};

/* ---------------------------------------------------------------------------
   WEB LANE COMPATIBILITY ALIAS
--------------------------------------------------------------------------- */
ui.appendWebLaneMessage = function (text) {
    ui.appendSystemMessage(text, "answer");
};

})();