/* -------------------------------------------------------------------
   FILE: workspace_ui_confirm.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonUIConfirm";
    const OVERLAY_CLASS = "solomon-ui-confirm-overlay";
    const DIALOG_CLASS = "solomon-ui-confirm-dialog";
    const OPEN_ATTRIBUTE = "data-solomon-confirm-open";

    if (window[API_NAME]) {
        return;
    }

    let activeDialog = null;
    let lastFocusedElement = null;

    function cleanText(value, fallback) {
        const text = String(value || "").trim();

        return text || fallback || "";
    }

    function createElement(tagName, className, text) {
        const element = document.createElement(tagName);

        if (className) {
            element.className = className;
        }

        if (text) {
            element.textContent = text;
        }

        return element;
    }

    function getFocusableElements(root) {
        return Array.from(root.querySelectorAll([
            "button:not([disabled])",
            "a[href]",
            "input:not([disabled])",
            "select:not([disabled])",
            "textarea:not([disabled])",
            "[tabindex]:not([tabindex='-1'])"
        ].join(","))).filter(function (element) {
            return Boolean(
                element.offsetWidth ||
                element.offsetHeight ||
                element.getClientRects().length
            );
        });
    }

    function restoreFocus() {
        if (
            lastFocusedElement &&
            document.contains(lastFocusedElement) &&
            typeof lastFocusedElement.focus === "function"
        ) {
            lastFocusedElement.focus({ preventScroll: true });
        }

        lastFocusedElement = null;
    }

    function settleDialog(dialog, confirmed) {
        if (!dialog || dialog.settled) {
            return;
        }

        dialog.settled = true;

        if (typeof dialog.resolve === "function") {
            dialog.resolve(Boolean(confirmed));
        }

        if (confirmed && typeof dialog.onConfirm === "function") {
            dialog.onConfirm();
        }

        if (!confirmed && typeof dialog.onCancel === "function") {
            dialog.onCancel();
        }
    }

    function closeDialog(result) {
        const dialog = activeDialog;
        const confirmed = result === "confirm";

        if (!dialog) {
            return false;
        }

        activeDialog = null;
        document.documentElement.removeAttribute(OPEN_ATTRIBUTE);
        document.removeEventListener("keydown", handleDocumentKeydown, true);

        if (dialog.overlay && dialog.overlay.parentNode) {
            dialog.overlay.parentNode.removeChild(dialog.overlay);
        }

        restoreFocus();
        settleDialog(dialog, confirmed);

        return confirmed;
    }

    function handleDocumentKeydown(event) {
        if (!activeDialog) {
            return;
        }

        if (event.key === "Escape") {
            event.preventDefault();
            closeDialog("cancel");
            return;
        }

        if (event.key !== "Tab") {
            return;
        }

        const focusableElements = getFocusableElements(activeDialog.overlay);

        if (!focusableElements.length) {
            event.preventDefault();
            return;
        }

        const firstElement = focusableElements[0];
        const lastElement = focusableElements[focusableElements.length - 1];
        const activeElement = document.activeElement;

        if (event.shiftKey && activeElement === firstElement) {
            event.preventDefault();
            lastElement.focus();
            return;
        }

        if (!event.shiftKey && activeElement === lastElement) {
            event.preventDefault();
            firstElement.focus();
        }
    }

    function bindDialogEvents(overlay, cancelButton, confirmButton) {
        overlay.addEventListener("click", function (event) {
            if (event.target === overlay) {
                closeDialog("cancel");
            }
        });

        cancelButton.addEventListener("click", function () {
            closeDialog("cancel");
        });

        confirmButton.addEventListener("click", function () {
            cancelButton.disabled = true;
            confirmButton.disabled = true;
            closeDialog("confirm");
        });
    }

    function getDialogIconName(tone) {
        if (tone === "danger") {
            return "delete_outline";
        }

        return "help_outline";
    }

    function buildDialog(options) {
        const eyebrowLabel = cleanText(options?.eyebrow, "Documents");
        const title = cleanText(options?.title, "Confirm action");
        const message = cleanText(
            options?.message,
            "Are you sure you want to continue?"
        );
        const confirmLabel = cleanText(options?.confirmLabel, "Confirm");
        const cancelLabel = cleanText(options?.cancelLabel, "Cancel");
        const tone = options?.danger ? "danger" : "standard";
        const overlay = createElement("div", OVERLAY_CLASS);
        const dialog = createElement("section", DIALOG_CLASS);
        const shell = createElement("div", "solomon-ui-confirm-shell");
        const iconWrap = createElement("div", "solomon-ui-confirm-icon");
        const icon = createElement("span", "icon", getDialogIconName(tone));
        const content = createElement("div", "solomon-ui-confirm-content");
        const eyebrow = createElement(
            "p",
            "solomon-ui-confirm-eyebrow",
            eyebrowLabel
        );
        const heading = createElement("h2", "solomon-ui-confirm-title", title);
        const body = createElement("p", "solomon-ui-confirm-message", message);
        const actions = createElement("div", "solomon-ui-confirm-actions");
        const cancelButton = createElement(
            "button",
            "solomon-ui-confirm-button solomon-ui-confirm-button-secondary",
            cancelLabel
        );
        const confirmButton = createElement(
            "button",
            tone === "danger"
                ? "solomon-ui-confirm-button solomon-ui-confirm-button-danger"
                : "solomon-ui-confirm-button solomon-ui-confirm-button-primary",
            confirmLabel
        );
        const titleId = "solomon-confirm-title";
        const messageId = "solomon-confirm-message";

        overlay.setAttribute("data-confirm-tone", tone);
        dialog.setAttribute("role", "dialog");
        dialog.setAttribute("aria-modal", "true");
        dialog.setAttribute("aria-labelledby", titleId);
        dialog.setAttribute("aria-describedby", messageId);

        heading.id = titleId;
        body.id = messageId;

        icon.setAttribute("aria-hidden", "true");
        iconWrap.setAttribute("aria-hidden", "true");
        iconWrap.appendChild(icon);

        cancelButton.type = "button";
        confirmButton.type = "button";

        content.append(eyebrow, heading, body);
        actions.append(cancelButton, confirmButton);
        shell.append(iconWrap, content);
        dialog.append(shell, actions);
        overlay.appendChild(dialog);

        bindDialogEvents(overlay, cancelButton, confirmButton);

        return {
            overlay,
            cancelButton,
            confirmButton
        };
    }

    function open(options) {
        const cleanOptions = options || {};

        if (activeDialog) {
            closeDialog("cancel");
        }

        lastFocusedElement = document.activeElement;

        return new Promise(function (resolve) {
            const dialog = buildDialog(cleanOptions);

            activeDialog = {
                overlay: dialog.overlay,
                onConfirm: cleanOptions.onConfirm,
                onCancel: cleanOptions.onCancel,
                resolve,
                settled: false
            };

            document.body.appendChild(dialog.overlay);
            document.documentElement.setAttribute(OPEN_ATTRIBUTE, "true");
            document.addEventListener("keydown", handleDocumentKeydown, true);

            window.requestAnimationFrame(function () {
                if (
                    activeDialog &&
                    dialog.cancelButton &&
                    typeof dialog.cancelButton.focus === "function"
                ) {
                    dialog.cancelButton.focus({
                        preventScroll: true
                    });
                }
            });
        });
    }

    function show(options) {
        return open(options);
    }

    function confirm(options) {
        return open(options);
    }

    function close() {
        return closeDialog("cancel");
    }

    function isOpen() {
        return Boolean(activeDialog);
    }

    window[API_NAME] = Object.freeze({
        show,
        open,
        confirm,
        close,
        isOpen
    });
})();