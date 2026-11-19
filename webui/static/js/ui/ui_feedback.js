/* -------------------------------------------------------------------
   FILE: ui_feedback.js
   DIRECTORY: webui/static/js/ui/
   Nations Systems site-wide feedback, notification, and confirmation contract
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "NationsFeedback";

    if (window[API_NAME]) {
        return;
    }

    const FEEDBACK_REGION_ID = "nations-feedback-region";
    const FEEDBACK_REGION_SELECTOR = "[data-feedback-region]";
    const TOAST_CLASS = "nations-feedback-toast";
    const TOAST_VISIBLE_CLASS = "is-visible";
    const TOAST_CLOSING_CLASS = "is-closing";
    const TOAST_REMOVE_DELAY_MS = 180;
    const TOAST_DUPLICATE_WINDOW_MS = 4800;
    const TOAST_PROGRESS_STEP = 5;
    const TOAST_MAX_VISIBLE = 3;
    const FEEDBACK_STORAGE_KEY = "nations.feedback.v1";

    const CONFIRM_MODAL_ID = "nations-feedback-confirm";
    const CONFIRM_MODAL_SELECTOR = "[data-feedback-confirm]";
    const CONFIRM_VISIBLE_CLASS = "is-visible";

    const DEFAULT_DURATIONS = Object.freeze({
        success: 4000,
        info: 5000,
        warning: 7000,
        error: 9000,
        danger: 9000
    });

    const ICONS = Object.freeze({
        success: "check_circle",
        info: "info",
        warning: "warning",
        error: "error",
        danger: "error"
    });

    const state = {
        activeConfirm: null,
        confirmBound: false,
        formBindingReady: false,
        lastToastSignature: "",
        lastToastAt: 0,
        lastToastProgress: null
    };

    function normalizeTone(value) {
        const tone = String(value || "info").trim().toLowerCase();

        if (tone === "danger") {
            return "danger";
        }

        if (tone === "error") {
            return "error";
        }

        if (tone === "warning" || tone === "warn") {
            return "warning";
        }

        if (tone === "success" || tone === "saved") {
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

    function normalizeNotificationOptions(options) {
        if (typeof options === "string") {
            return {
                type: "info",
                message: options,
                detail: "",
                actionLabel: "",
                action: "",
                onAction: null,
                durationMs: undefined,
                progressPercent: undefined,
                dismissible: true,
                emit: true,
                source: "nations_feedback",
                documentId: "",
                fileName: "",
                dedupe: true,
                force: false
            };
        }

        const cleanOptions = options && typeof options === "object" ? options : {};
        const type = normalizeTone(cleanOptions.type || cleanOptions.variant || cleanOptions.tone);

        return {
            type,
            message: String(cleanOptions.message || "Updated.").trim() || "Updated.",
            detail: String(cleanOptions.detail || "").trim(),
            actionLabel: String(cleanOptions.actionLabel || "").trim(),
            action: String(cleanOptions.action || "").trim(),
            onAction: cleanOptions.onAction,
            durationMs: cleanOptions.durationMs,
            progressPercent: cleanOptions.progressPercent,
            dismissible: cleanOptions.dismissible !== false,
            emit: cleanOptions.emit !== false,
            source: String(cleanOptions.source || "nations_feedback").trim(),
            documentId: cleanOptions.documentId || "",
            fileName: cleanOptions.fileName || "",
            dedupe: cleanOptions.dedupe !== false,
            force: Boolean(cleanOptions.force)
        };
    }

    function normalizeConfirmOptions(options) {
        const cleanOptions = options && typeof options === "object" ? options : {};

        return {
            tone: normalizeTone(cleanOptions.tone || cleanOptions.type || cleanOptions.variant || "danger"),
            title: String(cleanOptions.title || "Confirm action").trim() || "Confirm action",
            message: String(cleanOptions.message || "Are you sure you want to continue?").trim(),
            confirmLabel: String(cleanOptions.confirmLabel || cleanOptions.actionLabel || "Confirm").trim() || "Confirm",
            cancelLabel: String(cleanOptions.cancelLabel || "Cancel").trim() || "Cancel",
            onConfirm: cleanOptions.onConfirm,
            onCancel: cleanOptions.onCancel,
            form: cleanOptions.form || null
        };
    }

    function buildToastSignature(options) {
        const cleanOptions = options || {};

        return [
            cleanOptions.source || "nations_feedback",
            cleanOptions.action || "",
            cleanOptions.type || "info",
            cleanOptions.message || "",
            cleanOptions.detail || "",
            cleanOptions.documentId || "",
            cleanOptions.fileName || "",
            cleanOptions.actionLabel || ""
        ].join("\u241f");
    }

    function rememberToastSignature(signature, progressPercent) {
        state.lastToastSignature = String(signature || "");
        state.lastToastAt = Date.now();
        state.lastToastProgress = progressPercent;
    }

    function hasMeaningfulProgressChange(progressPercent) {
        if (progressPercent === null) {
            return false;
        }

        if (state.lastToastProgress === null) {
            return true;
        }

        return (
            Math.abs(progressPercent - state.lastToastProgress) >= TOAST_PROGRESS_STEP ||
            progressPercent === 0 ||
            progressPercent === 100
        );
    }

    function shouldSuppressDuplicateToast(options, signature, progressPercent) {
        const cleanOptions = options || {};
        const now = Date.now();
        const ageMs = now - state.lastToastAt;

        if (cleanOptions.force || cleanOptions.dedupe === false) {
            rememberToastSignature(signature, progressPercent);
            return false;
        }

        if (signature !== state.lastToastSignature) {
            rememberToastSignature(signature, progressPercent);
            return false;
        }

        if (hasMeaningfulProgressChange(progressPercent)) {
            rememberToastSignature(signature, progressPercent);
            return false;
        }

        if (ageMs <= TOAST_DUPLICATE_WINDOW_MS) {
            rememberToastSignature(signature, progressPercent);
            return true;
        }

        rememberToastSignature(signature, progressPercent);
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

    function iconElement(iconName) {
        const icon = document.createElement("span");

        icon.className = "icon nations-feedback-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = iconName;

        return icon;
    }

    function getDuration(options) {
        if (Object.prototype.hasOwnProperty.call(options, "durationMs")) {
            const customDuration = Number(options.durationMs);

            return Number.isFinite(customDuration) ? customDuration : DEFAULT_DURATIONS[options.type];
        }

        return DEFAULT_DURATIONS[options.type] || DEFAULT_DURATIONS.info;
    }

    function dispatchFeedbackEvent(eventName, detail) {
        document.dispatchEvent(new CustomEvent(eventName, {
            bubbles: true,
            cancelable: false,
            detail: detail || {}
        }));
    }

    function getFeedbackRegion() {
        let region = document.querySelector(FEEDBACK_REGION_SELECTOR) || document.getElementById(FEEDBACK_REGION_ID);

        if (region) {
            return region;
        }

        region = document.createElement("aside");
        region.id = FEEDBACK_REGION_ID;
        region.className = "nations-feedback-region";
        region.setAttribute("data-feedback-region", "");
        region.setAttribute("aria-label", "Notifications");
        region.setAttribute("aria-live", "polite");
        region.setAttribute("aria-atomic", "false");

        document.body.appendChild(region);
        return region;
    }

    function limitVisibleToasts(region) {
        const toasts = Array.from(region.querySelectorAll(`.${TOAST_CLASS}`));

        while (toasts.length > TOAST_MAX_VISIBLE) {
            dismiss(toasts.shift(), { immediate: true });
        }
    }

    function dismiss(toast, options) {
        const target = toast || document.querySelector(`.${TOAST_CLASS}`);

        if (!target) {
            return;
        }

        if (target.__nationsFeedbackTimer) {
            window.clearTimeout(target.__nationsFeedbackTimer);
            target.__nationsFeedbackTimer = null;
        }

        if (options?.immediate) {
            target.remove();
            return;
        }

        target.classList.remove(TOAST_VISIBLE_CLASS);
        target.classList.add(TOAST_CLOSING_CLASS);
        target.setAttribute("data-feedback-state", "closing");

        window.setTimeout(function () {
            target.remove();
        }, TOAST_REMOVE_DELAY_MS);
    }

    function setToastTimer(toast, durationMs) {
        if (toast.__nationsFeedbackTimer) {
            window.clearTimeout(toast.__nationsFeedbackTimer);
            toast.__nationsFeedbackTimer = null;
        }

        if (Number.isFinite(durationMs) && durationMs > 0) {
            toast.__nationsFeedbackTimer = window.setTimeout(function () {
                dismiss(toast);
            }, durationMs);
        }
    }

    function findMatchingToast(region, signature) {
        if (!region || !signature) {
            return null;
        }

        return region.querySelector(`.${TOAST_CLASS}[data-feedback-signature="${CSS.escape(signature)}"]`);
    }

    function syncToastProgress(toast, progressPercent) {
        const cleanProgress = normalizeProgressPercent(progressPercent);
        const existingProgress = toast.querySelector(".nations-feedback-progress");

        if (cleanProgress === null) {
            existingProgress?.remove();
            toast.setAttribute("data-feedback-has-progress", "false");
            return;
        }

        let progress = existingProgress;
        let progressBar = progress?.querySelector("span");

        if (!progress) {
            progress = document.createElement("div");
            progress.className = "nations-feedback-progress";
            progress.setAttribute("aria-hidden", "true");
            progressBar = document.createElement("span");
            progress.append(progressBar);
            toast.append(progress);
        }

        if (progressBar) {
            progressBar.style.width = `${cleanProgress}%`;
        }

        toast.setAttribute("data-feedback-has-progress", "true");
    }

    function updateMatchingToast(toast, options, durationMs) {
        const cleanOptions = options || {};
        const message = toast.querySelector(".nations-feedback-message");
        const detail = toast.querySelector(".nations-feedback-detail");

        toast.classList.remove(TOAST_CLOSING_CLASS);
        toast.classList.add(TOAST_VISIBLE_CLASS);
        toast.setAttribute("data-feedback-state", "open");

        if (message) {
            message.textContent = cleanOptions.message;
        }

        if (detail) {
            if (cleanOptions.detail) {
                detail.textContent = cleanOptions.detail;
            } else {
                detail.remove();
            }
        }

        syncToastProgress(toast, cleanOptions.progressPercent);
        setToastTimer(toast, durationMs);

        return toast;
    }

    function notify(options) {
        const cleanOptions = normalizeNotificationOptions(options);
        const region = getFeedbackRegion();
        const durationMs = getDuration(cleanOptions);
        const signature = buildToastSignature(cleanOptions);
        const progressPercent = normalizeProgressPercent(cleanOptions.progressPercent);
        const matchingToast = cleanOptions.dedupe && !cleanOptions.force
            ? findMatchingToast(region, signature)
            : null;

        if (matchingToast) {
            rememberToastSignature(signature, progressPercent);
            return updateMatchingToast(matchingToast, cleanOptions, durationMs);
        }

        if (shouldSuppressDuplicateToast(cleanOptions, signature, progressPercent)) {
            return null;
        }

        const toast = document.createElement("article");
        const assertive = ["danger", "error", "warning"].includes(cleanOptions.type);
        const hasProgress = progressPercent !== null;

        toast.className = `${TOAST_CLASS} ${TOAST_CLASS}--${cleanOptions.type}`;
        toast.setAttribute("data-feedback-toast", "");
        toast.setAttribute("data-feedback-state", "open");
        toast.setAttribute("data-feedback-type", cleanOptions.type);
        toast.setAttribute("data-feedback-source", cleanOptions.source);
        toast.setAttribute("data-feedback-action", cleanOptions.action);
        toast.setAttribute("data-feedback-signature", signature);
        toast.setAttribute("data-feedback-document-id", String(cleanOptions.documentId || ""));
        toast.setAttribute("data-feedback-file-name", String(cleanOptions.fileName || ""));
        toast.setAttribute("data-feedback-has-progress", hasProgress ? "true" : "false");
        toast.setAttribute("role", assertive ? "alert" : "status");
        toast.setAttribute("aria-live", assertive ? "assertive" : "polite");
        toast.setAttribute("aria-atomic", "true");

        toast.append(iconElement(ICONS[cleanOptions.type] || ICONS.info));

        const copy = document.createElement("div");
        copy.className = "nations-feedback-copy";
        copy.append(textElement("strong", "nations-feedback-message", cleanOptions.message));

        if (cleanOptions.detail) {
            copy.append(textElement("span", "nations-feedback-detail", cleanOptions.detail));
        }

        toast.append(copy);

        if (cleanOptions.actionLabel) {
            const action = document.createElement("button");

            action.type = "button";
            action.className = "nations-feedback-action";
            action.textContent = cleanOptions.actionLabel;
            action.addEventListener("click", function () {
                if (typeof cleanOptions.onAction === "function") {
                    cleanOptions.onAction();
                }

                dismiss(toast);
            });

            toast.append(action);
        }

        if (cleanOptions.dismissible) {
            const close = document.createElement("button");

            close.type = "button";
            close.className = "nations-feedback-close";
            close.setAttribute("aria-label", "Dismiss notification");
            close.append(iconElement("close"));
            close.addEventListener("click", function () {
                dismiss(toast);
            });

            toast.append(close);
        }

        if (hasProgress) {
            syncToastProgress(toast, progressPercent);
        }

        region.append(toast);
        limitVisibleToasts(region);

        window.requestAnimationFrame(function () {
            toast.classList.add(TOAST_VISIBLE_CLASS);
        });

        setToastTimer(toast, durationMs);

        if (cleanOptions.emit) {
            dispatchFeedbackEvent("nations:feedback:notify", {
                type: cleanOptions.type,
                action: cleanOptions.action,
                message: cleanOptions.message,
                detail: cleanOptions.detail,
                source: cleanOptions.source,
                document_id: cleanOptions.documentId,
                file_name: cleanOptions.fileName
            });
        }

        return toast;
    }

    function createConfirmModal() {
        const backdrop = document.createElement("div");

        backdrop.id = CONFIRM_MODAL_ID;
        backdrop.className = "nations-feedback-modal-backdrop";
        backdrop.setAttribute("aria-hidden", "true");
        backdrop.setAttribute("data-feedback-confirm", "");

        backdrop.innerHTML = [
            '<div class="nations-feedback-modal" role="dialog" aria-modal="true" aria-labelledby="nations-feedback-confirm-title" aria-describedby="nations-feedback-confirm-message">',
            '    <div class="nations-feedback-modal-header">',
            '        <span class="icon nations-feedback-modal-icon" aria-hidden="true" data-feedback-confirm-icon>warning</span>',
            '        <h2 id="nations-feedback-confirm-title" class="nations-feedback-modal-title" data-feedback-confirm-title>Confirm action</h2>',
            "    </div>",
            '    <div class="nations-feedback-modal-body">',
            '        <p id="nations-feedback-confirm-message" class="nations-feedback-modal-message" data-feedback-confirm-message>Are you sure you want to continue?</p>',
            "    </div>",
            '    <div class="nations-feedback-modal-actions">',
            '        <button type="button" class="nations-feedback-modal-button nations-feedback-modal-button--secondary" data-feedback-confirm-cancel>Cancel</button>',
            '        <button type="button" class="nations-feedback-modal-button nations-feedback-modal-button--primary" data-feedback-confirm-accept>Confirm</button>',
            "    </div>",
            "</div>"
        ].join("");

        document.body.appendChild(backdrop);
        return backdrop;
    }

    function getConfirmModal() {
        return (
            document.querySelector(CONFIRM_MODAL_SELECTOR) ||
            document.querySelector("[data-confirm-modal]") ||
            createConfirmModal()
        );
    }

    function getConfirmElements() {
        const modal = getConfirmModal();

        return {
            modal,
            title: modal.querySelector("[data-feedback-confirm-title]") || modal.querySelector("#app-confirm-title"),
            message: modal.querySelector("[data-feedback-confirm-message]") || modal.querySelector("#app-confirm-message"),
            icon: modal.querySelector("[data-feedback-confirm-icon]"),
            cancel: modal.querySelector("[data-feedback-confirm-cancel]") || modal.querySelector("[data-confirm-cancel]"),
            accept: modal.querySelector("[data-feedback-confirm-accept]") || modal.querySelector("[data-confirm-accept]")
        };
    }

    function closeConfirm(result) {
        const active = state.activeConfirm;
        const elements = getConfirmElements();

        elements.modal.classList.remove(CONFIRM_VISIBLE_CLASS);
        elements.modal.classList.remove("is-visible");
        elements.modal.setAttribute("aria-hidden", "true");

        state.activeConfirm = null;

        if (active?.previousFocus && typeof active.previousFocus.focus === "function") {
            active.previousFocus.focus({ preventScroll: true });
        }

        if (result === true) {
            if (typeof active?.options?.onConfirm === "function") {
                active.options.onConfirm();
            }

            active?.resolve?.(true);
            return;
        }

        if (typeof active?.options?.onCancel === "function") {
            active.options.onCancel();
        }

        active?.resolve?.(false);
    }

    function openConfirm(options) {
        const cleanOptions = normalizeConfirmOptions(options);
        const elements = getConfirmElements();

        state.activeConfirm = {
            options: cleanOptions,
            previousFocus: document.activeElement,
            resolve: null
        };

        if (elements.title) {
            elements.title.textContent = cleanOptions.title;
        }

        if (elements.message) {
            elements.message.textContent = cleanOptions.message;
        }

        if (elements.icon) {
            elements.icon.textContent = ICONS[cleanOptions.tone] || ICONS.warning;
        }

        if (elements.cancel) {
            elements.cancel.textContent = cleanOptions.cancelLabel;
        }

        if (elements.accept) {
            elements.accept.textContent = cleanOptions.confirmLabel;
        }

        elements.modal.setAttribute("data-feedback-tone", cleanOptions.tone);
        elements.modal.classList.add(CONFIRM_VISIBLE_CLASS);
        elements.modal.classList.add("is-visible");
        elements.modal.setAttribute("aria-hidden", "false");

        window.requestAnimationFrame(function () {
            elements.accept?.focus({ preventScroll: true });
        });

        return new Promise(function (resolve) {
            state.activeConfirm.resolve = resolve;
        });
    }

    function bindConfirmModal() {
        if (state.confirmBound) {
            return;
        }

        const elements = getConfirmElements();

        if (!elements.modal || !elements.cancel || !elements.accept) {
            return;
        }

        state.confirmBound = true;

        elements.cancel.addEventListener("click", function () {
            closeConfirm(false);
        });

        elements.accept.addEventListener("click", function () {
            closeConfirm(true);
        });

        elements.modal.addEventListener("click", function (event) {
            if (event.target === elements.modal) {
                closeConfirm(false);
            }
        });

        document.addEventListener("keydown", function (event) {
            if (!state.activeConfirm) {
                return;
            }

            if (event.key === "Escape") {
                event.preventDefault();
                closeConfirm(false);
            }
        });
    }

    function confirm(options) {
        bindConfirmModal();
        return openConfirm(options);
    }

    function bindConfirmForms() {
        if (state.formBindingReady) {
            return;
        }

        state.formBindingReady = true;

        document.addEventListener("submit", function (event) {
            const form = event.target;

            if (!(form instanceof HTMLFormElement) || !form.matches("[data-confirm-form]")) {
                return;
            }

            if (form.getAttribute("data-confirm-accepted") === "true") {
                return;
            }

            event.preventDefault();

            confirm({
                form,
                tone: form.getAttribute("data-confirm-tone") || "danger",
                title: form.getAttribute("data-confirm-title") || "Confirm action",
                message: form.getAttribute("data-confirm-message") || "Are you sure you want to continue?",
                confirmLabel: form.getAttribute("data-confirm-action") || "Confirm",
                cancelLabel: form.getAttribute("data-confirm-cancel-label") || "Cancel",
                onConfirm: function () {
                    form.setAttribute("data-confirm-accepted", "true");
                    form.submit();
                }
            });
        });
    }

    function store(options) {
        if (!window.sessionStorage || !options) {
            return;
        }

        try {
            const cleanOptions = normalizeNotificationOptions(options);

            window.sessionStorage.setItem(FEEDBACK_STORAGE_KEY, JSON.stringify({
                type: cleanOptions.type,
                message: cleanOptions.message,
                detail: cleanOptions.detail,
                actionLabel: cleanOptions.actionLabel,
                action: cleanOptions.action,
                documentId: cleanOptions.documentId,
                fileName: cleanOptions.fileName,
                source: cleanOptions.source
            }));
        } catch (error) {
            console.warn("[FEEDBACK] Unable to persist notification.", error);
        }
    }

    function consume() {
        if (!window.sessionStorage) {
            return;
        }

        let storedMessage = null;

        try {
            storedMessage = window.sessionStorage.getItem(FEEDBACK_STORAGE_KEY);
            window.sessionStorage.removeItem(FEEDBACK_STORAGE_KEY);
        } catch (error) {
            console.warn("[FEEDBACK] Unable to read persisted notification.", error);
            return;
        }

        if (!storedMessage) {
            return;
        }

        try {
            notify(JSON.parse(storedMessage));
        } catch (error) {
            console.warn("[FEEDBACK] Unable to render persisted notification.", error);
        }
    }

    function clear() {
        document.querySelectorAll(`.${TOAST_CLASS}`).forEach(function (toast) {
            dismiss(toast, { immediate: true });
        });
    }

    window[API_NAME] = Object.freeze({
        notify,
        dismiss,
        clear,
        store,
        consume,
        confirm,
        bindConfirmForms
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            bindConfirmForms();
            consume();
        }, { once: true });
    } else {
        bindConfirmForms();
        consume();
    }
})();