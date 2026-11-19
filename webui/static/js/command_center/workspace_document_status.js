/* -------------------------------------------------------------------
   FILE: workspace_document_status.js
   DIRECTORY: webui/static/js/command_center/
   Solomon Documents workspace status compatibility wrapper
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentStatus";

    if (window[API_NAME]) {
        return;
    }

    const SNACKBAR_CLASS = "workspace-document-snackbar";
    const SNACKBAR_COPY_CLASS = "workspace-document-snackbar-copy";
    const SNACKBAR_ACTION_CLASS = "workspace-document-snackbar-action";
    const SNACKBAR_CLOSE_CLASS = "workspace-document-snackbar-close";
    const SNACKBAR_VISIBLE_MS = 5200;
    const SNACKBAR_ERROR_VISIBLE_MS = 7600;
    const SNACKBAR_REMOVE_DELAY_MS = 180;
    const SNACKBAR_DUPLICATE_WINDOW_MS = 4800;
    const SNACKBAR_PROGRESS_STEP = 5;
    const WORKSPACE_STATUS_STORAGE_KEY = "solomon.workspaceStatus.v1";

    let lastNoticeSignature = "";
    let lastNoticeAt = 0;
    let lastNoticeProgress = null;

    function getFeedbackApi() {
        return window.NationsFeedback || null;
    }

    function normalizeVariant(value) {
        const variant = String(value || "info").trim().toLowerCase();

        if (variant === "danger") {
            return "danger";
        }

        if (variant === "error") {
            return "error";
        }

        if (variant === "warning" || variant === "warn") {
            return "warning";
        }

        if (variant === "success" || variant === "saved") {
            return "success";
        }

        return "info";
    }

    function normalizeProgressPercent(value) {
        const progress = Number(value);

        if (!Number.isFinite(progress)) {
            return null;
        }

        return Math.max(0, Math.min(100, progress));
    }

    function buildNoticeSignature(options) {
        const cleanOptions = options || {};

        return [
            cleanOptions.source || "workspace_document_status",
            cleanOptions.action || "document_action",
            cleanOptions.type || cleanOptions.variant || "info",
            cleanOptions.message || "",
            cleanOptions.documentId || "",
            cleanOptions.fileName || "",
            cleanOptions.actionLabel || ""
        ].join("\u241f");
    }

    function rememberNotice(signature, progressPercent) {
        lastNoticeSignature = signature;
        lastNoticeAt = Date.now();
        lastNoticeProgress = progressPercent;
    }

    function shouldSuppressDuplicateNotice(options) {
        const cleanOptions = options || {};
        const signature = buildNoticeSignature(cleanOptions);
        const progressPercent = normalizeProgressPercent(cleanOptions.progressPercent);
        const now = Date.now();
        const ageMs = now - lastNoticeAt;

        if (cleanOptions.dedupe === false || cleanOptions.force === true) {
            rememberNotice(signature, progressPercent);
            return false;
        }

        if (signature !== lastNoticeSignature) {
            rememberNotice(signature, progressPercent);
            return false;
        }

        if (progressPercent !== null) {
            if (
                lastNoticeProgress === null ||
                Math.abs(progressPercent - lastNoticeProgress) >= SNACKBAR_PROGRESS_STEP ||
                progressPercent === 0 ||
                progressPercent === 100
            ) {
                rememberNotice(signature, progressPercent);
                return false;
            }
        }

        if (ageMs <= SNACKBAR_DUPLICATE_WINDOW_MS) {
            rememberNotice(signature, progressPercent);
            return true;
        }

        rememberNotice(signature, progressPercent);
        return false;
    }

    function clearNode(node) {
        while (node?.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function textElement(tagName, className, text) {
        const element = document.createElement(tagName);

        if (className) {
            element.className = className;
        }

        element.textContent = text || "";
        return element;
    }

    function emitWorkspaceDocumentAction(explorer, detail) {
        document.dispatchEvent(new CustomEvent("solomon:workspace-document-action", {
            detail: {
                source: "workspace_document_status",
                workspace_id: explorer?.id || "",
                action: detail?.action || "document_action",
                status: detail?.status || "info",
                document_id: detail?.document_id || "",
                file_name: detail?.file_name || "",
                message: detail?.message || ""
            }
        }));
    }

    function getWorkspaceSnackbar() {
        let snackbar = document.querySelector(`.${SNACKBAR_CLASS}`);

        if (snackbar) {
            return snackbar;
        }

        snackbar = document.createElement("aside");
        snackbar.className = `${SNACKBAR_CLASS} d-none`;
        snackbar.setAttribute("role", "status");
        snackbar.setAttribute("aria-live", "polite");
        snackbar.setAttribute("aria-atomic", "true");
        snackbar.setAttribute("data-snackbar-state", "closed");

        document.body.appendChild(snackbar);
        return snackbar;
    }

    function dismissLegacy(snackbar) {
        const statusNode = snackbar || document.querySelector(`.${SNACKBAR_CLASS}`);

        if (!statusNode || statusNode.classList.contains("d-none")) {
            return;
        }

        statusNode.setAttribute("data-snackbar-state", "closing");

        if (statusNode.__solomonSnackbarTimer) {
            window.clearTimeout(statusNode.__solomonSnackbarTimer);
            statusNode.__solomonSnackbarTimer = null;
        }

        window.setTimeout(function () {
            statusNode.classList.add("d-none");
            statusNode.setAttribute("data-snackbar-state", "closed");
            clearNode(statusNode);
        }, SNACKBAR_REMOVE_DELAY_MS);
    }

    function showLegacy(explorer, options) {
        const snackbar = getWorkspaceSnackbar();
        const cleanOptions = options || {};
        const variant = normalizeVariant(cleanOptions.variant || cleanOptions.type);
        const assertive = ["danger", "error", "warning"].includes(variant);
        const hasCustomDuration = Object.prototype.hasOwnProperty.call(cleanOptions, "durationMs");
        const visibleMs = Number(hasCustomDuration
            ? cleanOptions.durationMs
            : (assertive ? SNACKBAR_ERROR_VISIBLE_MS : SNACKBAR_VISIBLE_MS)
        );
        const message = String(cleanOptions.message || "Workspace updated.").trim();
        const actionLabel = String(cleanOptions.actionLabel || "").trim();
        const actionName = String(cleanOptions.action || "document_action").trim() || "document_action";
        const progressPercent = Number(cleanOptions.progressPercent);
        const hasProgress = Number.isFinite(progressPercent);

        if (snackbar.__solomonSnackbarTimer) {
            window.clearTimeout(snackbar.__solomonSnackbarTimer);
            snackbar.__solomonSnackbarTimer = null;
        }

        clearNode(snackbar);
        snackbar.className = `${SNACKBAR_CLASS} ${SNACKBAR_CLASS}--${variant}`;
        snackbar.setAttribute("data-snackbar-state", "open");
        snackbar.setAttribute("data-snackbar-action", actionName);
        snackbar.setAttribute("data-snackbar-variant", variant);
        snackbar.setAttribute("data-snackbar-has-progress", hasProgress ? "true" : "false");
        snackbar.setAttribute("role", assertive ? "alert" : "status");

        snackbar.append(textElement("span", SNACKBAR_COPY_CLASS, message));

        if (actionLabel) {
            const action = document.createElement("button");

            action.type = "button";
            action.className = SNACKBAR_ACTION_CLASS;
            action.textContent = actionLabel;
            action.addEventListener("click", function () {
                if (typeof cleanOptions.onAction === "function") {
                    cleanOptions.onAction();
                    return;
                }

                dismissLegacy(snackbar);
            });

            snackbar.append(action);
        }

        const close = document.createElement("button");

        close.type = "button";
        close.className = SNACKBAR_CLOSE_CLASS;
        close.setAttribute("aria-label", "Dismiss notification");
        close.append(textElement("span", "icon", "close"));
        close.addEventListener("click", function () {
            dismissLegacy(snackbar);
        });

        snackbar.append(close);

        if (hasProgress) {
            const progress = document.createElement("div");
            const progressBar = document.createElement("span");
            const cleanProgress = Math.max(0, Math.min(100, progressPercent));

            progress.className = "workspace-document-snackbar-progress";
            progress.setAttribute("aria-hidden", "true");
            progressBar.style.width = `${cleanProgress}%`;
            progress.append(progressBar);
            snackbar.append(progress);
        }

        if (Number.isFinite(visibleMs) && visibleMs > 0) {
            snackbar.__solomonSnackbarTimer = window.setTimeout(function () {
                dismissLegacy(snackbar);
            }, visibleMs);
        }

        if (cleanOptions.emit !== false) {
            emitWorkspaceDocumentAction(explorer, {
                action: actionName,
                status: variant,
                document_id: cleanOptions.documentId || "",
                file_name: cleanOptions.fileName || "",
                message
            });
        }

        return snackbar;
    }

    function buildFeedbackOptions(options) {
        const cleanOptions = options || {};
        const type = normalizeVariant(cleanOptions.variant || cleanOptions.type);
        const message = String(cleanOptions.message || "Workspace updated.").trim();
        const actionName = String(cleanOptions.action || "document_action").trim() || "document_action";

        return {
            type,
            message,
            detail: cleanOptions.detail || "",
            action: actionName,
            actionLabel: cleanOptions.actionLabel || "",
            onAction: cleanOptions.onAction,
            durationMs: cleanOptions.durationMs,
            progressPercent: cleanOptions.progressPercent,
            documentId: cleanOptions.documentId || "",
            fileName: cleanOptions.fileName || "",
            source: "workspace_document_status",
            dedupe: cleanOptions.dedupe !== false,
            force: Boolean(cleanOptions.force),
            emit: cleanOptions.emit !== false
        };
    }

    function show(explorer, options) {
        const feedback = getFeedbackApi();
        const feedbackOptions = buildFeedbackOptions(options);

        if (shouldSuppressDuplicateNotice(feedbackOptions)) {
            return null;
        }

        const renderOptions = Object.assign({}, feedbackOptions, {
            emit: false
        });

        const toast = typeof feedback?.notify === "function"
            ? feedback.notify(renderOptions)
            : showLegacy(explorer, renderOptions);

        if (feedbackOptions.emit) {
            emitWorkspaceDocumentAction(explorer, {
                action: feedbackOptions.action,
                status: feedbackOptions.type,
                document_id: feedbackOptions.documentId,
                file_name: feedbackOptions.fileName,
                message: feedbackOptions.message
            });
        }

        return toast;
    }

    function dismiss(snackbar) {
        const feedback = getFeedbackApi();

        if (typeof feedback?.dismiss === "function") {
            feedback.dismiss(snackbar);
            return;
        }

        dismissLegacy(snackbar);
    }

    function store(options) {
        if (!window.sessionStorage || !options) {
            return;
        }

        const feedback = getFeedbackApi();

        if (typeof feedback?.store === "function") {
            feedback.store(buildFeedbackOptions(options));
            return;
        }

        try {
            window.sessionStorage.setItem(WORKSPACE_STATUS_STORAGE_KEY, JSON.stringify({
                action: options.action || "document_action",
                variant: options.variant || options.type || "info",
                message: options.message || "Workspace updated.",
                actionLabel: options.actionLabel || "",
                documentId: options.documentId || "",
                fileName: options.fileName || ""
            }));
        } catch (error) {
            console.warn("[DOCUMENT_STATUS] Unable to persist workspace status.", error);
        }
    }

    function consume(explorer) {
        if (!window.sessionStorage) {
            return;
        }

        let storedMessage = null;

        try {
            storedMessage = window.sessionStorage.getItem(WORKSPACE_STATUS_STORAGE_KEY);
            window.sessionStorage.removeItem(WORKSPACE_STATUS_STORAGE_KEY);
        } catch (error) {
            console.warn("[DOCUMENT_STATUS] Unable to read workspace status.", error);
            return;
        }

        if (!storedMessage) {
            const feedback = getFeedbackApi();

            if (typeof feedback?.consume === "function") {
                feedback.consume();
            }

            return;
        }

        try {
            show(explorer, JSON.parse(storedMessage));
        } catch (error) {
            console.warn("[DOCUMENT_STATUS] Unable to render workspace status.", error);
        }
    }

    window[API_NAME] = Object.freeze({
        show,
        dismiss,
        store,
        consume
    });
})();