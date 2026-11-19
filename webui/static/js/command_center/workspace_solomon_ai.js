/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI workspace public entrypoint.

   Starts the focused workspace modules after the page or workspace shell
   is ready and preserves the existing public initialization API. Browser
   coordination remains presentation-only; all durable authority stays on
   the server.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before the entrypoint."
        );
    }

    const { constants } = modules.requireModule("contract");
    const workspaceBootstrap = modules.requireModule(
        "workspace_bootstrap"
    );

    function initializeWorkspace(workspace) {
        return workspaceBootstrap.initializeWorkspace(
            workspace
        );
    }

    function initialize() {
        return workspaceBootstrap.initialize();
    }

    document.addEventListener(
        constants.WORKSPACE_LOADED_EVENT,
        initialize
    );

    window.SolomonWorkspaceSolomonAI = Object.freeze({
        initialize,
        initializeWorkspace
    });

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initialize,
            { once: true }
        );
    } else {
        initialize();
    }
})(window, document);