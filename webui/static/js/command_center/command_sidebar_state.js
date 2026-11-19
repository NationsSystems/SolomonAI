/* -------------------------------------------------------------------
   FILE: command_sidebar_state.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const api = window.NationsCommandSidebar = window.NationsCommandSidebar || {};

    api.constants = Object.freeze({
        HOME_CONVERSATION_ID_KEY: "nations.solomonHomeConversation.id",
        LOCKED_TASKBAR_POSITION: "top",
        LEGACY_TASKBAR_POSITION_KEY: "nations.commandTaskbar.position",
        RENDER_MODE_HEADER: "X-Solomon-Render-Mode",
        WORKSPACE_RENDER_MODE: "workspace",
        PARTIAL_HEADER: "X-Solomon-Render-Mode",
        WORKSPACE_MOUNT_SELECTOR: "[data-workspace-mount]",
        WORKSPACE_LISTING_CONTRACT: "nations_workspace_listing_v1",
        WORKSPACE_OBJECT_CONTRACT: "nations_workspace_object_v1",
        WORKSPACE_EXPLORER_SELECTOR: [
            "[data-workspace-explorer]",
            "[data-document-explorer]"
        ].join(", "),
        WORKSPACE_LISTING_SELECTOR: [
            "[data-workspace-listing]",
            "[data-document-list]"
        ].join(", "),
        WORKSPACE_OBJECT_SELECTOR: [
            "[data-workspace-object]",
            "[data-workspace-object-row]",
            "[data-document-list-row]"
        ].join(", "),
        WORKSPACE_OBJECT_KEYBOARD_SELECTOR: [
            "[data-workspace-object-keyboard-row]",
            "[data-document-keyboard-row]"
        ].join(", "),
        WORKSPACE_OBJECT_ACTION_MENU_SELECTOR: [
            "[data-workspace-object-action-menu]",
            "[data-document-action-menu]"
        ].join(", "),
        WORKSPACE_OBJECT_ACTION_MENU_BUTTON_SELECTOR: [
            "[data-workspace-object-action-menu-button]",
            "[data-document-action-menu-button]"
        ].join(", "),
        WORKSPACE_OBJECT_ACTION_MENU_ITEM_SELECTOR: [
            "[data-workspace-object-action-menu-item]",
            "[data-document-action-menu-item]"
        ].join(", "),
        WORKSPACE_LISTING_LAYOUT_BUTTON_SELECTOR: [
            "[data-workspace-listing-layout-option]",
            "[data-document-layout-option]"
        ].join(", "),
        WORKSPACE_LISTING_LAYOUT_ATTRIBUTE: "data-workspace-listing-layout",
        WORKSPACE_LEGACY_DOCUMENT_LAYOUT_ATTRIBUTE: "data-document-layout",
        WORKSPACE_OBJECT_ID_ATTRIBUTE: "data-workspace-object-id",
        WORKSPACE_OBJECT_TYPE_ATTRIBUTE: "data-workspace-object-type",
        WORKSPACE_OBJECT_ROUTE_ATTRIBUTE: "data-workspace-object-route",
        WORKSPACE_OBJECT_MODULE_ATTRIBUTE: "data-workspace-object-module",
        WORKSPACE_OBJECT_SELECTED_ATTRIBUTE: "data-workspace-object-selected",
        WORKSPACE_LEGACY_DOCUMENT_ID_ATTRIBUTE: "data-document-id",
        WORKSPACE_LEGACY_DOCUMENT_ROUTE_ATTRIBUTE: "data-document-open-route",
        WORKSPACE_LEGACY_DOCUMENT_SELECTED_ATTRIBUTE: "data-document-selected",
        WORKSPACE_LEGACY_SEARCH_ROUTE_ATTRIBUTE: "data-search-result-open-route",
        WORKSPACE_LEGACY_SEARCH_MODULE_ATTRIBUTE: "data-search-result-open-module",
        COMMAND_LINK_SELECTOR: "a.command-nav-item[href][data-command-module]",
        DOCUMENT_EXPLORER_SELECTOR: "[data-document-explorer]",
        DOCUMENT_COLLECTIONS_SELECTOR: ".workspace-document-collections",
        DOCUMENT_BROWSER_SELECTOR: ".workspace-document-browser",
        DOCUMENT_INSPECTOR_SELECTOR: ".workspace-document-inspector",
        WORKSPACE_VIEW_BUTTON_SELECTOR: "[data-workspace-view]",
        WORKSPACE_VIEW_PANEL_SELECTOR: "[data-workspace-view-panel]",
        WORKSPACE_CHAT_RESUME_SELECTOR: "[data-solomon-conversation-resume]",
        TASKBAR_FOCUS_STATE_SELECTOR: "[data-solomon-taskbar-focus-state]",
        TASKBAR_RETURN_TO_FILES_SELECTOR: "[data-solomon-return-to-files]",
        TASKBAR_FORM_SELECTOR: "[data-solomon-taskbar-command]",
        TASKBAR_INPUT_SELECTOR: "[data-solomon-command-input]",
        TASKBAR_OUTPUT_SELECTOR: "[data-solomon-taskbar-output]",
        TASKBAR_PLACEHOLDER: "Ask SolomonAI",
        TASKBAR_COMMAND_ENDPOINT: "/api/task/execute",
        GLOBAL_SEARCH_FORM_SELECTOR: "[data-command-global-search]",
        GLOBAL_SEARCH_INPUT_SELECTOR: "[data-command-global-search-input]",
        GLOBAL_SEARCH_CLEAR_SELECTOR: "[data-command-global-search-clear]",
        GLOBAL_SEARCH_STATUS_SELECTOR: "[data-command-global-search-status]",
        GLOBAL_SEARCH_RESULTS_SELECTOR: "[data-command-global-search-results]",
        GLOBAL_SEARCH_CONTROL_SELECTOR: "[data-command-global-search-control]",
        GLOBAL_SEARCH_SCOPE_SELECTOR: "[data-command-global-search-scope]",
        GLOBAL_SEARCH_CONTRACT: "nations_global_search_v1",
        GLOBAL_SEARCH_ENDPOINT: "/api/workspace/search",
        GLOBAL_SEARCH_RESULTS_ROUTE: "/search",
        GLOBAL_SEARCH_MIN_QUERY_LENGTH: 2,
        GLOBAL_SEARCH_DEBOUNCE_MS: 180,
        GLOBAL_SEARCH_MAX_DROPDOWN_RESULTS: 8,
        GLOBAL_SEARCH_DEFAULT_SUGGESTION_LIMIT: 5,
        WORKSPACE_CONVERSATION_ID: "solomonWorkspaceConversation",
        WORKSPACE_CONVERSATION_SELECTOR: "[data-solomon-workspace-conversation]",
        WORKSPACE_CONVERSATION_THREAD_SELECTOR: "[data-solomon-workspace-conversation-thread]",
        WORKSPACE_CONVERSATION_EMPTY_SELECTOR: "[data-solomon-workspace-conversation-empty]",
        WORKSPACE_CONVERSATION_STATUS_SELECTOR: "[data-solomon-workspace-conversation-status]",
        WORKSPACE_CONVERSATION_FORM_SELECTOR: "[data-solomon-workspace-conversation-form]",
        WORKSPACE_CONVERSATION_INPUT_SELECTOR: "[data-solomon-workspace-conversation-input]",
        WORKSPACE_CONVERSATION_CLEAR_SELECTOR: "[data-solomon-workspace-conversation-clear]",
        WORKSPACE_CONVERSATION_CLOSE_SELECTOR: "[data-solomon-workspace-conversation-close]",
        HOME_CONVERSATION_DISPATCH_SOURCE: "command_center_conversation",
        HOME_CONVERSATION_RESPONSE_SOURCE: "v3_home_conversation",
        HOME_CONVERSATION_MODE: "conversation",
        HOME_CONVERSATION_CONTRACT: "home_conversation",
        HOME_CONVERSATION_RESPONSE_MODE: "workspace_conversation"
    });

    api.workflowByModule = Object.freeze({
        preconstruction_review: "pre_award_risk_review"
    });

    api.state = api.state || {
        initialized: false,
        workspaceNavigationActive: false,
        workspaceNavigationBound: false,
        returnToFilesBound: false,
        workspaceListingBound: false,
        workspaceListingActiveObjectId: "",
        workspaceListingActiveObjectType: "",
        globalSearchBound: false,
        globalSearchController: null,
        globalSearchRequestGeneration: 0,
        globalSearchPendingQuery: "",
        globalSearchRecentController: null,
        globalSearchRecentFiles: [],
        globalSearchRecentFilesLoaded: false,
        globalSearchRecentFilesLoading: false,
        globalSearchRecentFilesUnavailable: false,
        globalSearchResults: [],
        globalSearchActiveIndex: -1,
        globalSearchType: "all",
        globalSearchPanelState: "idle",
        solomonConversationState: "empty",
        solomonPendingMessage: null,
        solomonWorkspaceSnapshot: null,
        solomonConversationMessages: []
    };

    api.readStorage = function (key) {
        try {
            return window.localStorage.getItem(key);
        } catch (error) {
            return null;
        }
    };

    api.writeStorage = function (key, value) {
        try {
            window.localStorage.setItem(key, value);
        } catch (error) {
            return;
        }
    };

    api.removeStorage = function (key) {
        try {
            window.localStorage.removeItem(key);
        } catch (error) {
            return;
        }
    };

    api.createConversationId = function () {
        if (window.crypto?.randomUUID) {
            return window.crypto.randomUUID();
        }

        return `solomon-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    };

    api.getHomeConversationId = function () {
        const existingId = api.readStorage(api.constants.HOME_CONVERSATION_ID_KEY);

        if (existingId) {
            return existingId;
        }

        const conversationId = api.createConversationId();
        api.writeStorage(api.constants.HOME_CONVERSATION_ID_KEY, conversationId);

        return conversationId;
    };

    api.resetHomeConversationId = function () {
        const conversationId = api.createConversationId();

        api.writeStorage(api.constants.HOME_CONVERSATION_ID_KEY, conversationId);
        return conversationId;
    };

    api.getWorkflowForModule = function (moduleId) {
        return api.workflowByModule[moduleId] || "";
    };

    api.readCurrentModule = function () {
        return document
            .getElementById("portal-root")
            ?.getAttribute("data-active-module") || "home";
    };

    api.createIcon = function (name) {
        const icon = document.createElement("span");

        icon.className = "icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = name;

        return icon;
    };

    api.getCommandShellElements = function (sidebar) {
        return {
            sidebar,
            layout: document.querySelector(".command-center-layout"),
            deck: document.querySelector(".command-center-deck"),
            root: document.documentElement,
            body: document.body
        };
    };

    api.getWorkspaceListingElements = function (scope) {
        const c = api.constants;
        const root =
            scope && typeof scope.querySelectorAll === "function"
                ? scope
                : document;
        const explorers = Array.from(
            root.querySelectorAll(c.WORKSPACE_EXPLORER_SELECTOR) || []
        );

        if (
            root instanceof Element &&
            root.matches(c.WORKSPACE_EXPLORER_SELECTOR)
        ) {
            explorers.unshift(root);
        }

        const explorer = explorers[0] || null;
        const listing = explorer?.querySelector(c.WORKSPACE_LISTING_SELECTOR) || null;

        return {
            root,
            explorer,
            explorers,
            listing,
            rows: listing
                ? Array.from(
                    listing.querySelectorAll(c.WORKSPACE_OBJECT_SELECTOR) || []
                )
                : [],
            keyboardRows: listing
                ? Array.from(
                    listing.querySelectorAll(c.WORKSPACE_OBJECT_KEYBOARD_SELECTOR) || []
                )
                : [],
            actionMenus: explorer
                ? Array.from(
                    explorer.querySelectorAll(
                        c.WORKSPACE_OBJECT_ACTION_MENU_SELECTOR
                    ) || []
                )
                : [],
            actionMenuButtons: explorer
                ? Array.from(
                    explorer.querySelectorAll(
                        c.WORKSPACE_OBJECT_ACTION_MENU_BUTTON_SELECTOR
                    ) || []
                )
                : [],
            layoutButtons: explorer
                ? Array.from(
                    explorer.querySelectorAll(
                        c.WORKSPACE_LISTING_LAYOUT_BUTTON_SELECTOR
                    ) || []
                )
                : []
        };
    };

    api.getDocumentExplorerElements = function () {
        const c = api.constants;
        const explorer = document.querySelector(c.DOCUMENT_EXPLORER_SELECTOR);

        return {
            explorer,
            collections: explorer?.querySelector(c.DOCUMENT_COLLECTIONS_SELECTOR) || null,
            browser: explorer?.querySelector(c.DOCUMENT_BROWSER_SELECTOR) || null,
            inspector: explorer?.querySelector(c.DOCUMENT_INSPECTOR_SELECTOR) || null
        };
    };

    api.getWorkspaceViewElements = function () {
        const c = api.constants;
        const explorer = document.querySelector(c.DOCUMENT_EXPLORER_SELECTOR);
        const browser = explorer?.querySelector(c.DOCUMENT_BROWSER_SELECTOR) || null;

        return {
            explorer,
            browser,
            panels: browser ? Array.from(browser.querySelectorAll(c.WORKSPACE_VIEW_PANEL_SELECTOR)) : [],
            buttons: explorer ? Array.from(explorer.querySelectorAll(c.WORKSPACE_VIEW_BUTTON_SELECTOR)) : [],
            chatResumeButton: explorer?.querySelector(c.WORKSPACE_CHAT_RESUME_SELECTOR) || null,
            mount: document.querySelector(c.WORKSPACE_MOUNT_SELECTOR)
        };
    };

    api.getWorkspaceConversationElements = function () {
        const c = api.constants;
        const surface = document.querySelector(c.WORKSPACE_CONVERSATION_SELECTOR);

        return {
            surface,
            thread: surface?.querySelector(c.WORKSPACE_CONVERSATION_THREAD_SELECTOR) || null,
            empty: surface?.querySelector(c.WORKSPACE_CONVERSATION_EMPTY_SELECTOR) || null,
            status: surface?.querySelector(c.WORKSPACE_CONVERSATION_STATUS_SELECTOR) || null,
            form: surface?.querySelector(c.WORKSPACE_CONVERSATION_FORM_SELECTOR) || null,
            input: surface?.querySelector(c.WORKSPACE_CONVERSATION_INPUT_SELECTOR) || null,
            clear: surface?.querySelector(c.WORKSPACE_CONVERSATION_CLEAR_SELECTOR) || null,
            close: surface?.querySelector(c.WORKSPACE_CONVERSATION_CLOSE_SELECTOR) || null
        };
    };

    api.setWorkspaceConversationStatus = function (message) {
        const elements = api.getWorkspaceConversationElements();

        if (elements.status) {
            elements.status.textContent = message || "Ready for SolomonAI";
        }
    };

    api.clearTaskbarOutput = function () {
        const output = document.querySelector(api.constants.TASKBAR_OUTPUT_SELECTOR);

        if (!output) {
            return;
        }

        output.replaceChildren();
        output.hidden = true;
        output.removeAttribute("data-solomon-output-state");
    };

    api.hasSolomonHistory = function () {
        return (
            api.state.solomonConversationState !== "empty" ||
            api.state.solomonConversationMessages.length > 0
        );
    };

    api.isWorkspaceConversationOpen = function () {
        const surface = document.querySelector(api.constants.WORKSPACE_CONVERSATION_SELECTOR);

        return Boolean(
            surface &&
            surface.hidden !== true &&
            surface.getAttribute("aria-hidden") !== "true"
        );
    };

    api.syncSolomonHistoryState = function () {
        const c = api.constants;
        const hasHistory = api.hasSolomonHistory();
        const isOpen = api.isWorkspaceConversationOpen();
        const taskbarForm = document.querySelector(c.TASKBAR_FORM_SELECTOR);
        const focusState = document.querySelector(c.TASKBAR_FOCUS_STATE_SELECTOR);
        const clearButton = document.querySelector(c.WORKSPACE_CONVERSATION_CLEAR_SELECTOR);
        const viewElements = api.getWorkspaceViewElements();

        document.documentElement.setAttribute("data-solomon-conversation-has-history", hasHistory ? "true" : "false");
        document.documentElement.setAttribute("data-solomon-workspace-conversation-open", isOpen ? "true" : "false");
        document.documentElement.setAttribute("data-solomon-response-surface", isOpen ? c.HOME_CONVERSATION_RESPONSE_MODE : "taskbar");

        const surface = document.querySelector(c.WORKSPACE_CONVERSATION_SELECTOR);

        if (surface) {
            surface.setAttribute("data-solomon-has-history", hasHistory ? "true" : "false");
        }

        if (taskbarForm) {
            taskbarForm.hidden = hasHistory || isOpen;
        }

        if (focusState) {
            focusState.hidden = !isOpen;
        }

        if (clearButton) {
            clearButton.hidden = !hasHistory;
            clearButton.setAttribute("aria-hidden", hasHistory ? "false" : "true");
        }

        if (viewElements.chatResumeButton) {
            viewElements.chatResumeButton.hidden = !(hasHistory || isOpen);
        }

        return hasHistory;
    };

    api.removeTaskbarPositionToggleControls = function () {
        document.querySelectorAll("[data-taskbar-position-toggle], .command-taskbar-controls")
            .forEach(function (element) {
                element.remove();
            });
    };

    api.applyLockedTaskbarPosition = function (sidebar) {
        const c = api.constants;

        Object.values(api.getCommandShellElements(sidebar)).forEach(function (element) {
            if (!element) {
                return;
            }

            element.setAttribute("data-taskbar-position", c.LOCKED_TASKBAR_POSITION);
            element.setAttribute("data-taskbar-locked", c.LOCKED_TASKBAR_POSITION);
        });

        if (sidebar) {
            sidebar.setAttribute("data-sidebar-state", "expanded");
            sidebar.setAttribute("data-taskbar-position", c.LOCKED_TASKBAR_POSITION);
            sidebar.setAttribute("data-taskbar-locked", c.LOCKED_TASKBAR_POSITION);
        }

        api.removeStorage(c.LEGACY_TASKBAR_POSITION_KEY);
        api.removeTaskbarPositionToggleControls();
    };
})();