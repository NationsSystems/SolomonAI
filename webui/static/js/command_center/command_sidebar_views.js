/* -------------------------------------------------------------------
   FILE: command_sidebar_views.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const api = window.NationsCommandSidebar = window.NationsCommandSidebar || {};

    api.setWorkspaceView = function (viewName, options) {
        const targetView = String(viewName || "files").trim().toLowerCase();
        const nextView = targetView === "chat" ? "chat" : "files";
        const viewElements = api.getWorkspaceViewElements();

        if (!viewElements.explorer || !viewElements.browser || !viewElements.panels.length) {
            return false;
        }

        viewElements.explorer.setAttribute("data-workspace-view", nextView);
        viewElements.browser.setAttribute("data-workspace-view", nextView);
        viewElements.mount?.setAttribute("data-workspace-view", nextView);
        document.documentElement.setAttribute("data-solomon-workspace-view", nextView);

        if (nextView === "chat") {
            viewElements.explorer.setAttribute("data-solomon-workspace-mode", "conversation");
            viewElements.browser.setAttribute("data-solomon-workspace-mode", "conversation");
            viewElements.mount?.setAttribute("data-solomon-workspace-mode", "conversation");
            document.documentElement.setAttribute("data-solomon-workspace-conversation-open", "true");
        } else {
            viewElements.explorer.removeAttribute("data-solomon-workspace-mode");
            viewElements.browser.removeAttribute("data-solomon-workspace-mode");
            viewElements.mount?.removeAttribute("data-solomon-workspace-mode");
            document.documentElement.setAttribute("data-solomon-workspace-conversation-open", "false");
        }

        viewElements.panels.forEach(function (panel) {
            const panelView = String(panel.getAttribute("data-workspace-view-panel") || "")
                .trim()
                .toLowerCase();
            const isActive = panelView === nextView;

            panel.hidden = !isActive;
            panel.setAttribute("aria-hidden", isActive ? "false" : "true");
            panel.classList.toggle("is-active", isActive);
        });

        viewElements.buttons.forEach(function (button) {
            const buttonView = String(button.getAttribute("data-workspace-view") || "")
                .trim()
                .toLowerCase();
            const isActive = buttonView === nextView;

            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });

        api.syncSolomonHistoryState();

        if (options?.focusInput && nextView === "chat") {
            window.requestAnimationFrame(function () {
                api.focusWorkspaceConversationInput?.({
                    select: false
                });
            });
        }

        if (options?.focusTaskbar && nextView === "files") {
            window.requestAnimationFrame(function () {
                api.focusTaskbarInput?.({
                    select: false
                });
            });
        }

        return true;
    };
})();