/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_workspace_bootstrap.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI workspace module bootstrap.

   Coordinates focused presentation and transport modules for one rendered
   SolomonAI workspace. Each module retains its bounded browser role while
   conversation, source, persistence, and execution authority remain server-owned.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before workspace bootstrap."
        );
    }

    const contract = modules.requireModule("contract");
    const { constants, getElements } = contract;

    const REQUIRED_MODULES = Object.freeze([
        "conversation_navigation",
        "source_preview",
        "source_preview_interactions",
        "source_membership",
        "source_list",
        "source_welcome",
        "source_state",
        "source_transport",
        "source_picker",
        "source_controls",
        "composer_layout",
        "composer_state",
        "composer_controls",
        "message_text",
        "message_markdown",
        "message_content",
        "message_continuation",
        "message_timeline",
        "message_pending",
        "message_actions",
        "message_feedback",
        "message_renderer",
        "response_packet",
        "request_payload",
        "stream_parser",
        "execution_transport",
        "request_submit"
    ]);

    function requireWorkspaceModules() {
        return REQUIRED_MODULES.reduce(
            function (resolved, moduleName) {
                resolved[moduleName] = modules.requireModule(
                    moduleName
                );
                return resolved;
            },
            {}
        );
    }

    function getWorkspace() {
        return document.querySelector(
            constants.WORKSPACE_SELECTOR
        );
    }

    function markWorkspaceState(workspace, state) {
        if (!workspace) {
            return "";
        }

        const normalizedState = String(
            state || ""
        ).trim() || "ready";

        workspace.setAttribute(
            "data-solomon-ai-bootstrap-state",
            normalizedState
        );

        return normalizedState;
    }

    function initializeMessagePresentation(
        elements,
        workspaceModules
    ) {
        workspaceModules.message_timeline
            .hydrateMessageTimeline(elements);
        workspaceModules.message_pending
            .initialize(elements);
        workspaceModules.message_renderer
            .initialize(elements);
    }

    function initializeSourcePresentation(
        elements,
        workspaceModules
    ) {
        workspaceModules.source_preview_interactions
            .initialize(elements);
        workspaceModules.conversation_navigation
            .initialize(elements);
        workspaceModules.source_picker
            .initialize(elements);
        workspaceModules.source_controls
            .initialize(elements);
        workspaceModules.source_state
            .initialize(elements);
        workspaceModules.source_transport
            .initialize(elements);
    }

    function initializeComposer(
        elements,
        workspaceModules
    ) {
        workspaceModules.composer_layout
            .initialize(elements);
        workspaceModules.composer_state
            .initialize(elements);
        workspaceModules.composer_controls
            .initialize(elements);
    }

    function finalizeWorkspace(
        elements,
        workspaceModules
    ) {
        workspaceModules.message_timeline
            .restoreConversationPosition(elements);
        workspaceModules.composer_layout
            .refresh(elements, {
                stickToBottom: false
            });
    }

    function initializeWorkspace(workspace) {
        if (
            !workspace ||
            workspace.getAttribute(
                "data-solomon-ai-bound"
            ) === "true"
        ) {
            return false;
        }

        workspace.setAttribute(
            "data-solomon-ai-bound",
            "true"
        );
        markWorkspaceState(
            workspace,
            "initializing"
        );

        try {
            const workspaceModules =
                requireWorkspaceModules();
            const elements = getElements(
                workspace
            );

            initializeMessagePresentation(
                elements,
                workspaceModules
            );
            initializeSourcePresentation(
                elements,
                workspaceModules
            );
            initializeComposer(
                elements,
                workspaceModules
            );
            finalizeWorkspace(
                elements,
                workspaceModules
            );

            markWorkspaceState(
                workspace,
                "ready"
            );
            return true;
        } catch (error) {
            workspace.removeAttribute(
                "data-solomon-ai-bound"
            );
            markWorkspaceState(
                workspace,
                "failed"
            );
            throw error;
        }
    }

    function initialize() {
        const workspace = getWorkspace();

        if (!workspace) {
            return false;
        }

        return initializeWorkspace(
            workspace
        );
    }

    modules.registerModule(
        "workspace_bootstrap",
        {
            REQUIRED_MODULES,
            finalizeWorkspace,
            getWorkspace,
            initialize,
            initializeComposer,
            initializeMessagePresentation,
            initializeSourcePresentation,
            initializeWorkspace,
            markWorkspaceState,
            requireWorkspaceModules
        }
    );
})(window, document);