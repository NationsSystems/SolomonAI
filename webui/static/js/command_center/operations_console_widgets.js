/* ==========================================================================
   FILE: operations_console_widgets.js
   DIRECTORY: webui/static/js/command_center/
   ========================================================================== */

(function () {
    "use strict";

    const WIDGET_SELECTOR = "[data-console-widget]";
    const CLOSE_SELECTOR = "[data-console-widget-close]";
    const RESTORE_SELECTOR = "[data-console-restore-widgets]";
    const STORAGE_PREFIX = "nations.operationsConsole.hiddenWidgets";

    let hiddenWidgetIds = new Set();

    function getPortalRoot() {
        return document.getElementById("portal-root");
    }

    function getActiveModule() {
        const root = getPortalRoot();
        return root?.dataset?.activeModule || "home";
    }

    function getStorageKey() {
        return `${STORAGE_PREFIX}.${getActiveModule()}`;
    }

    function getWidgets() {
        return Array.from(document.querySelectorAll(WIDGET_SELECTOR));
    }

    function getRestoreButton() {
        return document.querySelector(RESTORE_SELECTOR);
    }

    function getWidgetId(widget) {
        return widget?.dataset?.consoleWidget || "";
    }

    function readStoredHiddenWidgets() {
        try {
            const rawValue = sessionStorage.getItem(getStorageKey());
            const parsedValue = rawValue ? JSON.parse(rawValue) : [];

            if (!Array.isArray(parsedValue)) {
                return new Set();
            }

            return new Set(
                parsedValue
                    .map((value) => String(value || "").trim())
                    .filter(Boolean)
            );
        } catch {
            return new Set();
        }
    }

    function writeStoredHiddenWidgets() {
        try {
            sessionStorage.setItem(
                getStorageKey(),
                JSON.stringify(Array.from(hiddenWidgetIds))
            );
        } catch {
            // Non-critical UI preference only.
        }
    }

    function updateRestoreButton() {
        const button = getRestoreButton();
        if (!button) return;

        const hasHiddenWidgets = hiddenWidgetIds.size > 0;

        button.hidden = !hasHiddenWidgets;
        button.setAttribute("aria-hidden", hasHiddenWidgets ? "false" : "true");

        if (hasHiddenWidgets) {
            button.textContent = "";
            button.appendChild(document.createTextNode("Restore Panels"));

            const icon = document.createElement("span");
            icon.className = "icon";
            icon.setAttribute("aria-hidden", "true");
            icon.textContent = "refresh";

            button.appendChild(icon);
        }
    }

    function updateRootState() {
        const root = getPortalRoot();
        if (!root) return;

        root.dataset.hiddenWidgetCount = String(hiddenWidgetIds.size);
        root.dataset.consoleWidgetState = hiddenWidgetIds.size > 0
            ? "customized"
            : "default";
    }

    function applyWidgetVisibility(widget) {
        const widgetId = getWidgetId(widget);
        if (!widgetId) return;

        const shouldHide = hiddenWidgetIds.has(widgetId);

        widget.hidden = shouldHide;
        widget.classList.toggle("is-console-widget-hidden", shouldHide);
        widget.setAttribute("aria-hidden", shouldHide ? "true" : "false");
    }

    function applyAllWidgetVisibility() {
        getWidgets().forEach(applyWidgetVisibility);
        updateRestoreButton();
        updateRootState();
    }

    function hideWidget(widget) {
        const widgetId = getWidgetId(widget);
        if (!widgetId) return;

        hiddenWidgetIds.add(widgetId);
        writeStoredHiddenWidgets();
        applyAllWidgetVisibility();
    }

    function restoreWidgets() {
        hiddenWidgetIds.clear();
        writeStoredHiddenWidgets();
        applyAllWidgetVisibility();
    }

    function bindCloseButtons() {
        document.querySelectorAll(CLOSE_SELECTOR).forEach((button) => {
            button.addEventListener("click", (event) => {
                event.preventDefault();
                event.stopPropagation();

                const widget = button.closest(WIDGET_SELECTOR);
                if (!widget) return;

                hideWidget(widget);
            });
        });
    }

    function bindRestoreButton() {
        const button = getRestoreButton();
        if (!button) return;

        button.addEventListener("click", (event) => {
            event.preventDefault();
            restoreWidgets();
        });
    }

    function initializeWidgetControls() {
        hiddenWidgetIds = readStoredHiddenWidgets();

        bindCloseButtons();
        bindRestoreButton();
        applyAllWidgetVisibility();
    }

    document.addEventListener("DOMContentLoaded", initializeWidgetControls);

    window.NationsOperationsConsoleWidgets = {
        restore: restoreWidgets,
        refresh: applyAllWidgetVisibility,
    };
}());