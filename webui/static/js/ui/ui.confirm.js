/* -------------------------------------------------------------------
   FILE: ui.confirm.js
   DIRECTORY: webui/static/js/ui/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonUIConfirm";
    const modal = document.querySelector("[data-confirm-modal]");

    if (window[API_NAME]) {
        return;
    }

    function fallbackConfirm(options) {
        const title = String(options?.title || "Confirm action").trim();
        const message = String(options?.message || "Are you sure you want to continue?").trim();

        return Promise.resolve(window.confirm(`${title}\n\n${message}`));
    }

    if (!modal) {
        window[API_NAME] = Object.freeze({
            confirm: fallbackConfirm
        });
        return;
    }

    const titleEl = modal.querySelector("#app-confirm-title");
    const messageEl = modal.querySelector("#app-confirm-message");
    const cancelButton = modal.querySelector("[data-confirm-cancel]");
    const acceptButton = modal.querySelector("[data-confirm-accept]");

    let activeForm = null;
    let activeResolver = null;
    let previousFocus = null;
    let isSubmitting = false;

    function normalizeConfirmOptions(options) {
        return {
            title: String(options?.title || "Confirm action").trim(),
            message: String(options?.message || "Are you sure you want to continue?").trim(),
            action: String(options?.action || options?.acceptLabel || "Confirm").trim(),
            cancel: String(options?.cancel || options?.cancelLabel || "Cancel").trim(),
            variant: String(options?.variant || "default").trim().toLowerCase()
        };
    }

    function applyConfirmContent(options) {
        const config = normalizeConfirmOptions(options);

        if (titleEl) {
            titleEl.textContent = config.title;
        }

        if (messageEl) {
            messageEl.textContent = config.message;
        }

        if (acceptButton) {
            acceptButton.textContent = config.action;
        }

        if (cancelButton) {
            cancelButton.textContent = config.cancel;
        }

        modal.setAttribute("data-confirm-variant", config.variant || "default");
    }

    function showConfirm() {
        modal.classList.add("is-visible");
        modal.setAttribute("aria-hidden", "false");

        if (acceptButton) {
            acceptButton.focus();
        }
    }

    function resolveProgrammaticConfirm(accepted) {
        const resolver = activeResolver;

        activeResolver = null;

        if (typeof resolver === "function") {
            resolver(Boolean(accepted));
        }
    }

    function closeConfirm(result) {
        modal.classList.remove("is-visible");
        modal.setAttribute("aria-hidden", "true");
        modal.removeAttribute("data-confirm-variant");

        activeForm = null;
        isSubmitting = false;

        resolveProgrammaticConfirm(Boolean(result));

        if (previousFocus && typeof previousFocus.focus === "function") {
            previousFocus.focus();
        }

        previousFocus = null;
    }

    function openFormConfirm(form) {
        activeForm = form;
        activeResolver = null;
        previousFocus = document.activeElement;
        isSubmitting = false;

        applyConfirmContent({
            title: form.getAttribute("data-confirm-title") || "Confirm action",
            message: form.getAttribute("data-confirm-message") || "Are you sure you want to continue?",
            action: form.getAttribute("data-confirm-action") || "Confirm",
            cancel: form.getAttribute("data-confirm-cancel-label") || "Cancel",
            variant: form.getAttribute("data-confirm-variant") || "default"
        });
        showConfirm();
    }

    function requestConfirm(options) {
        if (modal.classList.contains("is-visible")) {
            closeConfirm(false);
        }

        activeForm = null;
        previousFocus = document.activeElement;
        isSubmitting = false;

        applyConfirmContent(options);

        return new Promise(function (resolve) {
            activeResolver = resolve;
            showConfirm();
        });
    }

    function submitActiveForm() {
        if (activeResolver) {
            closeConfirm(true);
            return;
        }

        if (!activeForm || isSubmitting) {
            return;
        }

        isSubmitting = true;
        activeForm.setAttribute("data-confirm-accepted", "true");
        activeForm.submit();
    }

    document.addEventListener("submit", function (event) {
        const form = event.target;

        if (!form || !form.matches("[data-confirm-form]")) {
            return;
        }

        if (form.getAttribute("data-confirm-accepted") === "true") {
            return;
        }

        event.preventDefault();
        openFormConfirm(form);
    });

    if (cancelButton) {
        cancelButton.addEventListener("click", function () {
            closeConfirm(false);
        });
    }

    if (acceptButton) {
        acceptButton.addEventListener("click", submitActiveForm);
    }

    modal.addEventListener("click", function (event) {
        if (event.target === modal) {
            closeConfirm(false);
        }
    });

    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && modal.classList.contains("is-visible")) {
            closeConfirm(false);
        }
    });

    window[API_NAME] = Object.freeze({
        confirm: requestConfirm,
        close: function () {
            closeConfirm(false);
        }
    });
})();