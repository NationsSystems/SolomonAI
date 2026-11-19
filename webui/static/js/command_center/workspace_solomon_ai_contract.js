/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_contract.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   Shared browser contract for the dedicated SolomonAI workspace.

   Establishes the module registry, stable workspace constants, common
   DOM resolution, and transport-response parsing used by focused
   SolomonAI presentation modules. Server-side ownership, routing,
   authorization, execution, and response authority remain outside
   JavaScript.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const MODULE_NAMESPACE = "SolomonAIWorkspaceModules";
    const moduleRegistry = Object.create(null);
    const requestActions = new Set([
        "summarize_sources",
        "identify_key_details",
        "compare_sources"
    ]);

    const constants = Object.freeze({
        WORKSPACE_SELECTOR: "[data-solomon-ai-workspace]",
        EXECUTION_ENDPOINT: "/api/task/execute",
        EXECUTION_STREAM_ENDPOINT: "/api/task/execute/stream",
        INTELLIGENCE_READINESS_ENDPOINT:
            "/workspace/solomon/intelligence/readiness",
        INTELLIGENCE_READINESS_READY_POLL_MS: 30000,
        INTELLIGENCE_READINESS_WARMING_POLL_MS: 2000,
        INTELLIGENCE_READINESS_UNAVAILABLE_POLL_MS: 5000,
        INTELLIGENCE_READINESS_HIDDEN_POLL_MS: 60000,
        INTELLIGENCE_READINESS_FETCH_TIMEOUT_MS: 4000,
        FEEDBACK_ENDPOINT: "/api/task/feedback",
        MESSAGE_ACTION_COPY_RESET_MS: 1600,
        COMPOSER_BOTTOM_STICK_THRESHOLD_PX: 96,
        COMPOSER_RESERVE_BREATHING_ROOM_PX: 40,
        COMPOSER_RESERVE_MOBILE_BREATHING_ROOM_PX: 28,
        COMPOSER_MOBILE_BREAKPOINT_PX: 560,
        COMPOSER_PLACEHOLDER: "Ask SolomonAI",
        CONVERSATION_TITLE_MAX_LENGTH: 96,
        DOCUMENTS_URL: "/",
        DOCUMENTS_MODULE_ID: "documents",
        SOLOMON_AI_MODULE_ID: "solomon_ai",
        SOLOMON_AI_WORKSPACE_SOURCE: "solomon_ai_workspace",
        WORKSPACE_CONTEXT_SCHEMA: "solomon_workspace_context_v1",
        SOURCE_MEMBERSHIP_CONTRACT:
            "solomon_ai_conversation_source_membership_v1",
        SOURCE_PICKER_DEFAULT_SCOPE: "",
        SOURCE_PICKER_SEARCH_DEBOUNCE_MS: 220,
        SOURCE_PICKER_SCOPES: Object.freeze([
            "",
            "my_files",
            "company_library",
            "shared_with_me"
        ]),
        WORKSPACE_LOADED_EVENT: "solomon:workspace-loaded",
        SOURCE_PREVIEW_ID: "solomon-ai-source-preview"
    });

    const messageDateFormatter = new Intl.DateTimeFormat(
        undefined,
        {
            month: "short",
            day: "numeric",
            year: "numeric"
        }
    );

    function cleanValue(value) {
        return String(value || "").trim();
    }

    function normalizeModuleName(value) {
        return cleanValue(value).toLowerCase();
    }

    function registerModule(name, api) {
        const moduleName = normalizeModuleName(name);

        if (!moduleName) {
            throw new Error(
                "A SolomonAI workspace module name is required."
            );
        }

        if (
            !api ||
            typeof api !== "object" ||
            Array.isArray(api)
        ) {
            throw new TypeError(
                `SolomonAI workspace module "${moduleName}" ` +
                "must expose an object API."
            );
        }

        if (moduleRegistry[moduleName]) {
            throw new Error(
                `SolomonAI workspace module "${moduleName}" ` +
                "is already registered."
            );
        }

        moduleRegistry[moduleName] = Object.freeze({
            ...api
        });

        return moduleRegistry[moduleName];
    }

    function getModule(name) {
        return (
            moduleRegistry[
                normalizeModuleName(name)
            ] || null
        );
    }

    function requireModule(name) {
        const moduleName = normalizeModuleName(name);
        const moduleApi = getModule(moduleName);

        if (!moduleApi) {
            throw new Error(
                `Required SolomonAI workspace module ` +
                `"${moduleName}" is not available.`
            );
        }

        return moduleApi;
    }

    function hasModule(name) {
        return Boolean(
            getModule(name)
        );
    }

    function getElements(workspace) {
        if (
            !workspace ||
            typeof workspace.querySelector !== "function"
        ) {
            return {};
        }

        return {
            workspace,
            pageClose: workspace.querySelector(
                ".solomon-ai-workspace__page-close"
            ),
            tabs: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-tab]"
                )
            ),
            panels: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-panel]"
                )
            ),
            history: workspace.querySelector(
                "[data-solomon-ai-history]"
            ),
            historyRows: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-history-row]"
                )
            ),
            historyItems: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-history-item]"
                )
            ),
            historyOptions: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-history-options]"
                )
            ),
            historyMenus: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-history-menu]"
                )
            ),
            historyRenameButtons: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-history-rename]"
                )
            ),
            historyDeleteButtons: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-history-delete]"
                )
            ),
            historyRenameEditors: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-history-rename-editor]"
                )
            ),
            historyRenameInputs: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-history-rename-input]"
                )
            ),
            historyRenameSaveButtons: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-history-rename-save]"
                )
            ),
            historyRenameCancelButtons: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-history-rename-cancel]"
                )
            ),
            historyManagementStatus: workspace.querySelector(
                "[data-solomon-ai-history-management-status]"
            ),
            newChat: workspace.querySelector(
                "[data-solomon-ai-new-chat]"
            ),
            newChatStatus: workspace.querySelector(
                "[data-solomon-ai-new-chat-status]"
            ),
            sourceList: workspace.querySelector(
                "[data-solomon-ai-source-list]"
            ),
            sourceToolbar: workspace.querySelector(
                ".solomon-ai-sources__toolbar"
            ),
            sourcePreview: workspace.querySelector(
                "[data-solomon-ai-source-preview]"
            ),
            sourcesEmpty: workspace.querySelector(
                "[data-solomon-ai-sources-empty]"
            ),
            sourceTab: workspace.querySelector(
                "[data-solomon-ai-tab='sources']"
            ),
            sourceCount: workspace.querySelector(
                ".solomon-ai-sources__count"
            ),
            publicWebToggle: workspace.querySelector(
                "[data-solomon-ai-public-web-toggle]"
            ),
            publicWebStatus: workspace.querySelector(
                "[data-solomon-ai-public-web-status]"
            ),
            addSourceButtons: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-add-sources]"
                )
            ),
            sourcePicker: workspace.querySelector(
                "[data-solomon-ai-source-picker]"
            ),
            sourcePickerDialog: workspace.querySelector(
                "[data-solomon-ai-source-picker-dialog]"
            ),
            sourcePickerCloseButtons: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-source-picker-close]"
                )
            ),
            sourcePickerScopes: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-source-picker-scope]"
                )
            ),
            sourcePickerSearch: workspace.querySelector(
                "[data-solomon-ai-source-picker-search]"
            ),
            sourcePickerStatus: workspace.querySelector(
                "[data-solomon-ai-source-picker-status]"
            ),
            sourcePickerList: workspace.querySelector(
                "[data-solomon-ai-source-picker-list]"
            ),
            sourcePickerEmpty: workspace.querySelector(
                "[data-solomon-ai-source-picker-empty]"
            ),
            sourcePickerEmptyMessage: workspace.querySelector(
                "[data-solomon-ai-source-picker-empty-message]"
            ),
            sourcePickerSelection: workspace.querySelector(
                "[data-solomon-ai-source-picker-selection]"
            ),
            sourcePickerAttach: workspace.querySelector(
                "[data-solomon-ai-source-picker-attach]"
            ),
            suggestions: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-suggestion]"
                )
            ),
            multiSourceSuggestions: Array.from(
                workspace.querySelectorAll(
                    "[data-solomon-ai-multi-source-suggestion]"
                )
            ),
            composer: workspace.querySelector(
                "[data-solomon-ai-composer]"
            ),
            composerShell: workspace.querySelector(
                ".solomon-ai-composer-shell"
            ),
            intelligenceStatus: workspace.querySelector(
                "[data-solomon-ai-intelligence-status]"
            ),
            input: workspace.querySelector(
                "[data-solomon-ai-input]"
            ),
            composerSource: workspace.querySelector(
                ".solomon-ai-composer [data-solomon-ai-upload-files]"
            ),
            submit: workspace.querySelector(
                "[data-solomon-ai-submit]"
            ),
            composerSourceState: workspace.querySelector(
                "[data-solomon-ai-composer-source-state]"
            ),
            thread: workspace.querySelector(
                "[data-solomon-ai-thread]"
            ),
            welcome: workspace.querySelector(
                "[data-solomon-ai-welcome]"
            ),
            scroll: workspace.querySelector(
                "[data-solomon-ai-conversation-scroll]"
            )
        };
    }

    function setElementVisibility(element, visible) {
        if (!element) {
            return;
        }

        element.hidden = !visible;
        element.setAttribute(
            "aria-hidden",
            visible ? "false" : "true"
        );
    }

    function normalizeRequestAction(value) {
        const action = cleanValue(
            value
        ).toLowerCase();

        if (requestActions.has(action)) {
            return action;
        }

        return "";
    }

    async function readJsonResponse(response) {
        if (
            !response ||
            typeof response.text !== "function"
        ) {
            return {};
        }

        const responseText = await response.text();

        if (!responseText) {
            return {};
        }

        try {
            return JSON.parse(responseText);
        } catch (error) {
            return {
                ok: response.ok,
                user_output: responseText
            };
        }
    }

    const namespace = Object.freeze({
        constants,
        messageDateFormatter,
        registerModule,
        getModule,
        requireModule,
        hasModule
    });

    registerModule(
        "contract",
        {
            constants,
            messageDateFormatter,
            cleanValue,
            getElements,
            normalizeRequestAction,
            readJsonResponse,
            setElementVisibility
        }
    );

    Object.defineProperty(
        window,
        MODULE_NAMESPACE,
        {
            configurable: false,
            enumerable: false,
            writable: false,
            value: namespace
        }
    );
})(window);