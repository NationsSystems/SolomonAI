/* -------------------------------------------------------------------
   FILE: command_sidebar_taskbar.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const api = window.NationsCommandSidebar = window.NationsCommandSidebar || {};

    const DOCUMENTS_MODULE_ID = "documents";
    const SOLOMON_AI_MODULE_ID = "solomon_ai";
    const PEOPLE_MODULE_ID = "people";
    const SEARCH_MODULE_ID = "search";

    api.isTaskbarPending = function (form) {
        return form?.getAttribute("data-solomon-taskbar-pending") === "true";
    };

    api.setFormPending = function (form, isPending) {
        const input = form?.querySelector("input[name='task']");
        const send = form?.querySelector("button[type='submit']");

        if (!form) {
            return;
        }

        form.setAttribute("data-solomon-taskbar-pending", isPending ? "true" : "false");
        form.setAttribute("data-solomon-command-state", isPending ? "busy" : "idle");

        if (input) {
            input.disabled = isPending;
        }

        if (send) {
            send.disabled = isPending;
        }
    };

    api.setConversationPending = function (isPending) {
        const c = api.constants;

        api.setFormPending(document.querySelector(c.TASKBAR_FORM_SELECTOR), isPending);
        api.setFormPending(document.querySelector(c.WORKSPACE_CONVERSATION_FORM_SELECTOR), isPending);

        document.documentElement.setAttribute("data-solomon-response-pending", isPending ? "true" : "false");
    };

    api.focusInput = function (input, options) {
        if (!input || input.disabled) {
            return false;
        }

        input.focus({ preventScroll: true });

        if (options?.select) {
            input.select?.();
        }

        return true;
    };

    api.focusTaskbarInput = function (options) {
        return api.focusInput(document.querySelector(api.constants.TASKBAR_INPUT_SELECTOR), options);
    };

    api.focusWorkspaceConversationInput = function (options) {
        return api.focusInput(document.querySelector(api.constants.WORKSPACE_CONVERSATION_INPUT_SELECTOR), options);
    };

    function getSameOriginUrl(value) {
        const cleanUrl = String(value || "").trim();

        if (!cleanUrl) {
            return null;
        }

        try {
            const parsedUrl = new URL(cleanUrl, window.location.origin);

            return parsedUrl.origin === window.location.origin
                ? parsedUrl
                : null;
        } catch (_error) {
            return null;
        }
    }

    function getRelativeUrl(parsedUrl) {
        if (!parsedUrl) {
            return "";
        }

        return `${parsedUrl.pathname}${parsedUrl.search}${parsedUrl.hash}`;
    }

    function getActionModuleForRoute(route) {
        const parsedUrl = getSameOriginUrl(route);

        if (!parsedUrl) {
            return DOCUMENTS_MODULE_ID;
        }

        if (
            parsedUrl.pathname === "/ai" ||
            parsedUrl.pathname.startsWith("/ai/")
        ) {
            return SOLOMON_AI_MODULE_ID;
        }

        if (
            parsedUrl.pathname === "/people" ||
            parsedUrl.pathname.startsWith("/people/")
        ) {
            return PEOPLE_MODULE_ID;
        }

        if (parsedUrl.pathname === "/search") {
            return SEARCH_MODULE_ID;
        }

        return DOCUMENTS_MODULE_ID;
    }

    function isWorkspaceShellActionRoute(route) {
        const parsedUrl = getSameOriginUrl(route);
        const path = parsedUrl?.pathname || "";

        return Boolean(
            parsedUrl &&
            (
                path === "/" ||
                path === "/reports" ||
                path === "/recent" ||
                path === "/shared" ||
                path === "/trash" ||
                path === "/search" ||
                path === "/ai" ||
                path.startsWith("/ai/") ||
                path === "/people" ||
                path.startsWith("/people/") ||
                path.startsWith("/workspace/file/") ||
                path.startsWith("/workspace/document/")
            )
        );
    }

    function openActionTargetFallback(target) {
        const cleanTarget = String(target || "").trim();

        if (!cleanTarget) {
            return false;
        }

        const anchor = document.createElement("a");

        anchor.href = cleanTarget;
        anchor.rel = "noopener";
        anchor.style.display = "none";

        if (!getSameOriginUrl(cleanTarget)) {
            anchor.target = "_blank";
        }

        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();

        return true;
    }

    async function loadActionRoute(action) {
        const target = String(action?.target || "").trim();
        const sameOriginUrl = getSameOriginUrl(target);
        const cleanRoute = getRelativeUrl(sameOriginUrl);

        if (!target) {
            return false;
        }

        if (
            cleanRoute &&
            isWorkspaceShellActionRoute(cleanRoute) &&
            typeof api.loadWorkspace === "function"
        ) {
            try {
                const result = await api.loadWorkspace(
                    cleanRoute,
                    getActionModuleForRoute(cleanRoute),
                    {
                        push: true,
                        async: true,
                        launchMode: "assistant_action",
                        source: "command_sidebar_taskbar",
                        actionType: String(action?.type || "").trim().toLowerCase(),
                        actionLabel: String(action?.label || "").trim()
                    }
                );

                if (result !== false) {
                    return true;
                }
            } catch (error) {
                console.warn(
                    "[TASKBAR_ACTION] Async action route failed; using fallback navigation.",
                    error
                );
            }
        }

        return openActionTargetFallback(cleanRoute || target);
    }

    api.normalizeSolomonAction = function (action) {
        if (typeof action === "string") {
            const cleanLabel = action.trim();

            return cleanLabel ? {
                label: cleanLabel,
                target: cleanLabel,
                type: "prompt",
                raw: action
            } : null;
        }

        if (!action || typeof action !== "object") {
            return null;
        }

        const label = String(action.label || action.title || action.name || "").trim();
        const type = String(action.type || action.kind || "prompt").trim().toLowerCase();
        let target = String(action.target || action.href || action.url || "").trim();

        if (!label) {
            return null;
        }

        if (type === "prompt" && !target) {
            target = label;
        }

        return { label, target, type, raw: action };
    };

    api.normalizeSolomonPacket = function (packet) {
        const c = api.constants;
        const payload = packet?.payload && typeof packet.payload === "object" ? packet.payload : packet || {};
        const answer = String(payload.answer || payload.message || payload.response || payload.text || packet?.answer || packet?.message || "").trim();
        const bridge = String(payload.bridge || payload.next_step || payload.follow_up || packet?.bridge || "").trim();

        const actionCandidates = []
            .concat(Array.isArray(payload.suggestion_actions) ? payload.suggestion_actions : [])
            .concat(Array.isArray(payload.ui_actions) ? payload.ui_actions : [])
            .concat(Array.isArray(payload.actions) ? payload.actions : [])
            .concat(Array.isArray(payload.suggestions) ? payload.suggestions : [])
            .concat(Array.isArray(packet?.suggestion_actions) ? packet.suggestion_actions : [])
            .concat(Array.isArray(packet?.ui_actions) ? packet.ui_actions : [])
            .concat(Array.isArray(packet?.actions) ? packet.actions : [])
            .concat(Array.isArray(packet?.suggestions) ? packet.suggestions : []);

        const actions = [];
        const seenActions = new Set();

        actionCandidates.forEach(function (candidate) {
            const action = api.normalizeSolomonAction(candidate);

            if (!action) {
                return;
            }

            const key = `${action.type}:${action.label}:${action.target}`;

            if (!seenActions.has(key)) {
                seenActions.add(key);
                actions.push(action);
            }
        });

        return {
            ok: packet?.ok !== false,
            packetType: String(packet?.packet_type || payload.packet_type || "llm").trim(),
            payload,
            answer: answer || "SolomonAI returned a response.",
            bridge,
            intent: String(payload.intent || packet?.intent || "workspace").trim(),
            source: String(payload.source || packet?.source || c.HOME_CONVERSATION_RESPONSE_SOURCE).trim(),
            actions: actions.slice(0, 4)
        };
    };

    api.createSolomonActionButton = function (action) {
        const button = document.createElement("button");

        button.type = "button";
        button.className = "solomon-workspace-conversation-action";
        button.textContent = action.label;

        if (action.type === "prompt") {
            button.setAttribute("data-solomon-prompt-chip", "");
        }

        button.addEventListener("click", function () {
            api.handleSolomonAction(action);
        });

        return button;
    };

    api.handleSolomonAction = function (action) {
        const type = String(action?.type || "").toLowerCase();

        if (!action) {
            return;
        }

        if (type === "prompt") {
            const promptText = String(action.target || action.label || "").trim();

            if (!promptText) {
                return;
            }

            api.openWorkspaceConversation({ focusInput: false });

            const workspaceInput = document.querySelector(api.constants.WORKSPACE_CONVERSATION_INPUT_SELECTOR);

            if (workspaceInput) {
                workspaceInput.value = promptText;
                workspaceInput.closest("form")?.setAttribute("data-solomon-has-value", "true");
                api.focusWorkspaceConversationInput({ select: false });
                return;
            }

            const taskbarInput = document.querySelector(api.constants.TASKBAR_INPUT_SELECTOR);
            const taskbarForm = taskbarInput?.closest("form");

            if (taskbarInput && taskbarForm) {
                taskbarInput.value = promptText;
                taskbarForm.setAttribute("data-solomon-has-value", "true");
                api.focusTaskbarInput({ select: false });
            }

            return;
        }

        if (!action.target) {
            return;
        }

        if (type === "route" || type === "link" || type === "open") {
            void loadActionRoute(action);
            return;
        }

        if (type === "focus" || type === "collection") {
            const target = document.querySelector(action.target);

            if (target instanceof HTMLElement) {
                target.focus({ preventScroll: false });
                target.scrollIntoView({ block: "center", behavior: "smooth" });
            }
        }
    };

    api.getHomeConversationEndpoint = function (form) {
        return form?.getAttribute("data-assistant-endpoint") || api.constants.TASKBAR_COMMAND_ENDPOINT;
    };

    api.buildCommandPayload = function (inputValue) {
        const c = api.constants;
        const moduleId = api.readCurrentModule();
        const workflowId = api.getWorkflowForModule(moduleId);

        return {
            task: inputValue,
            conversation_id: api.getHomeConversationId(),
            command_context: {
                module: moduleId,
                active_module: moduleId,
                workflow: workflowId,
                command_surface: "home",
                input_surface: "taskbar_workspace_conversation",
                response_surface: c.HOME_CONVERSATION_RESPONSE_MODE,
                command_contract: c.HOME_CONVERSATION_CONTRACT
            },
            workspace_context: {
                source: c.HOME_CONVERSATION_DISPATCH_SOURCE,
                command_mode: c.HOME_CONVERSATION_MODE,
                module: moduleId,
                active_module: moduleId,
                command_surface: "home",
                input_surface: "taskbar_workspace_conversation",
                response_target: c.HOME_CONVERSATION_RESPONSE_MODE,
                assistant_surface: c.HOME_CONVERSATION_RESPONSE_MODE
            },
            command_surface: "home",
            command_mode: c.HOME_CONVERSATION_MODE,
            command_contract: c.HOME_CONVERSATION_CONTRACT,
            response_mode: c.HOME_CONVERSATION_RESPONSE_MODE,
            workspace_response_target: c.HOME_CONVERSATION_RESPONSE_MODE,
            source: c.HOME_CONVERSATION_DISPATCH_SOURCE,
            request_source: c.HOME_CONVERSATION_DISPATCH_SOURCE,
            expected_response_source: c.HOME_CONVERSATION_RESPONSE_SOURCE,
            origin_surface: "taskbar_workspace_conversation",
            assistant_surface: c.HOME_CONVERSATION_RESPONSE_MODE
        };
    };

    api.dispatchSolomonConversationEvent = function (eventName, detail) {
        window.dispatchEvent(new CustomEvent(eventName, {
            bubbles: false,
            cancelable: false,
            detail: detail || {}
        }));
    };

    api.readJsonResponse = async function (response) {
        const contentType = response.headers.get("content-type") || "";

        if (contentType.includes("application/json")) {
            return response.json();
        }

        const text = await response.text();

        try {
            return JSON.parse(text);
        } catch (error) {
            return {
                ok: false,
                packet_type: "parse_error",
                payload: {
                    answer: text || "The server did not return a valid SolomonAI packet."
                }
            };
        }
    };

    api.postSolomonCommandPacket = async function (endpoint, payload) {
        const response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify(payload)
        });

        const packet = await api.readJsonResponse(response);

        if (!response.ok && packet?.ok !== false) {
            packet.ok = false;
            packet.packet_type = packet.packet_type || "request_error";
            packet.payload = packet.payload && typeof packet.payload === "object"
                ? packet.payload
                : {};
            packet.payload.answer = packet.payload.answer || `Request failed: ${response.status}`;
        }

        return packet;
    };

    api.submitSolomonCommand = async function (form, input) {
        const value = String(input?.value || "").trim();

        if (!form || !input || !value || api.isTaskbarPending(form)) {
            return false;
        }

        const endpoint = api.getHomeConversationEndpoint(form);
        const payload = api.buildCommandPayload(value);

        api.clearTaskbarOutput();

        input.value = "";
        form.setAttribute("data-solomon-has-value", "false");
        api.setConversationPending(true);

        api.dispatchSolomonConversationEvent("solomon:assistant-submitted", {
            form,
            input,
            prompt: value,
            payload,
            endpoint,
            source: "taskbar_workspace_conversation"
        });

        api.openWorkspaceConversation({ focusInput: false });
        api.renderPendingConversation(value);

        try {
            const packet = await api.postSolomonCommandPacket(endpoint, payload);

            if (packet?.ok === false) {
                const normalizedPacket = api.normalizeSolomonPacket(packet);
                throw new Error(normalizedPacket.answer || "SolomonAI could not complete that message.");
            }

            api.dispatchSolomonConversationEvent("solomon:assistant-response", {
                packet,
                prompt: value,
                source: "taskbar_workspace_conversation"
            });

            api.renderConversationResponse(packet);
            api.dispatchSolomonConversationEvent("solomon:assistant-history-updated", {
                packet,
                source: "taskbar_workspace_conversation"
            });
        } catch (error) {
            api.renderConversationError(error?.message || "SolomonAI could not complete that message.");
            api.dispatchSolomonConversationEvent("solomon:assistant-history-updated", {
                error,
                source: "taskbar_workspace_conversation"
            });
        } finally {
            api.setConversationPending(false);

            if (api.isWorkspaceConversationOpen()) {
                api.focusWorkspaceConversationInput({ select: false });
            }
        }

        return true;
    };

    api.applyTaskbarContractAttributes = function (form) {
        const c = api.constants;

        if (!form) {
            return;
        }

        form.setAttribute("data-solomon-command-contract", c.HOME_CONVERSATION_CONTRACT);
        form.setAttribute("data-solomon-command-response-mode", c.HOME_CONVERSATION_RESPONSE_MODE);
        form.setAttribute("data-solomon-command-authority", c.HOME_CONVERSATION_DISPATCH_SOURCE);
        form.setAttribute("data-solomon-command-ready", "true");
    };
})();