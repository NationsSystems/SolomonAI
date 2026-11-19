/* -------------------------------------------------------------------
   FILE: command_sidebar_conversation.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const api = window.NationsCommandSidebar = window.NationsCommandSidebar || {};

    api.captureWorkspaceSnapshot = function () {
        const mount = document.querySelector(api.constants.WORKSPACE_MOUNT_SELECTOR);

        if (!mount || api.state.solomonWorkspaceSnapshot || api.isWorkspaceConversationOpen()) {
            return;
        }

        const documentExplorer = api.getDocumentExplorerElements();

        if (documentExplorer.explorer && documentExplorer.collections && documentExplorer.browser && documentExplorer.inspector) {
            api.state.solomonWorkspaceSnapshot = {
                type: "document_explorer",
                moduleId: api.readCurrentModule(),
                browserHtml: documentExplorer.browser.outerHTML,
                inspectorHtml: documentExplorer.inspector.outerHTML
            };
            return;
        }

        api.state.solomonWorkspaceSnapshot = {
            type: "workspace_mount",
            html: mount.innerHTML,
            moduleId: api.readCurrentModule()
        };
    };

    api.createWorkspaceConversationSurface = function () {
        const c = api.constants;
        const surface = document.createElement("section");

        surface.id = c.WORKSPACE_CONVERSATION_ID;
        surface.className = "solomon-workspace-conversation";
        surface.setAttribute("aria-label", "SolomonAI workspace conversation");
        surface.setAttribute("data-solomon-workspace-conversation", "");
        surface.setAttribute("data-solomon-has-history", api.hasSolomonHistory() ? "true" : "false");

        const header = document.createElement("header");
        header.className = "solomon-workspace-conversation-header";

        const titleBlock = document.createElement("div");
        titleBlock.className = "solomon-workspace-conversation-titleblock";
        titleBlock.innerHTML = [
            '<p class="solomon-workspace-conversation-kicker">Nations Systems</p>',
            "<h1>SolomonAI</h1>",
            '<p class="solomon-workspace-conversation-subtitle">Workspace conversation results</p>'
        ].join("");

        const actions = document.createElement("div");
        actions.className = "solomon-workspace-conversation-controls";

        const clearButton = document.createElement("button");
        clearButton.type = "button";
        clearButton.className = "solomon-workspace-conversation-control";
        clearButton.setAttribute("aria-label", "Clear SolomonAI conversation");
        clearButton.setAttribute("title", "Clear SolomonAI conversation");
        clearButton.setAttribute("data-solomon-workspace-conversation-clear", "");
        clearButton.append(api.createIcon("delete_sweep"));

        const closeButton = document.createElement("button");
        closeButton.type = "button";
        closeButton.className = "solomon-workspace-conversation-control";
        closeButton.setAttribute("aria-label", "Return to workspace");
        closeButton.setAttribute("title", "Return to workspace");
        closeButton.setAttribute("data-solomon-workspace-conversation-close", "");
        closeButton.append(api.createIcon("close"));

        actions.append(clearButton, closeButton);
        header.append(titleBlock, actions);

        const body = document.createElement("div");
        body.className = "solomon-workspace-conversation-body";

        const empty = document.createElement("article");
        empty.className = "solomon-workspace-conversation-empty";
        empty.setAttribute("data-solomon-workspace-conversation-empty", "");

        const emptyIcon = document.createElement("div");
        emptyIcon.className = "solomon-workspace-conversation-empty-mark";
        emptyIcon.setAttribute("aria-hidden", "true");
        emptyIcon.append(api.createIcon("auto_awesome"));

        const emptyText = document.createElement("div");
        emptyText.innerHTML = [
            "<strong>Ask SolomonAI from the command bar.</strong>",
            "<p>The Library remains available while this workspace area becomes the long-form SolomonAI conversation surface.</p>"
        ].join("");

        empty.append(emptyIcon, emptyText);

        const thread = document.createElement("div");
        thread.className = "solomon-workspace-conversation-thread";
        thread.setAttribute("data-solomon-workspace-conversation-thread", "");
        thread.setAttribute("aria-label", "SolomonAI conversation");

        body.append(empty, thread);

        const form = document.createElement("form");
        form.id = "solomonWorkspaceConversationForm";
        form.className = "solomon-workspace-conversation-form";
        form.setAttribute("aria-label", "Continue SolomonAI conversation");
        form.setAttribute("autocomplete", "off");
        form.setAttribute("novalidate", "");
        form.setAttribute("data-solomon-workspace-conversation-form", "");

        form.innerHTML = [
            '<label class="visually-hidden" for="solomonWorkspaceConversationInput">Continue SolomonAI conversation</label>',
            '<input type="text" id="solomonWorkspaceConversationInput" name="task" class="solomon-workspace-conversation-input" placeholder="Continue with SolomonAI..." autocomplete="off" spellcheck="false" autocapitalize="off" autocorrect="off" data-solomon-workspace-conversation-input>',
            '<button type="submit" class="solomon-workspace-conversation-send" aria-label="Send message to SolomonAI" title="Send message to SolomonAI"><span class="icon" aria-hidden="true">arrow_forward</span></button>'
        ].join("");

        const status = document.createElement("div");
        status.className = "solomon-workspace-conversation-status";
        status.setAttribute("aria-label", "SolomonAI conversation status");
        status.innerHTML = '<span data-solomon-workspace-conversation-status>Ready for SolomonAI</span>';

        surface.append(header, body, form, status);
        return surface;
    };

    api.bindWorkspaceConversationSurface = function () {
        const elements = api.getWorkspaceConversationElements();

        if (!elements.surface || elements.surface.getAttribute("data-solomon-workspace-bound") === "true") {
            return;
        }

        elements.surface.setAttribute("data-solomon-workspace-bound", "true");

        if (elements.clear) {
            elements.clear.addEventListener("click", api.resetSolomonConversation);
        }

        if (elements.close) {
            elements.close.addEventListener("click", api.restoreWorkspaceSnapshot);
        }

        api.initializeWorkspaceConversationInputInteraction();
    };

    api.renderStoredConversationMessages = function () {
        const elements = api.getWorkspaceConversationElements();

        if (!elements.thread) {
            return;
        }

        elements.thread
            .querySelectorAll("[data-solomon-workspace-conversation-message]")
            .forEach(function (message) {
                message.remove();
            });

        if (elements.empty) {
            elements.empty.hidden = api.state.solomonConversationMessages.length > 0;
        }

        api.state.solomonConversationMessages.forEach(function (message) {
            api.appendSolomonMessage(message.role, message.content, {
                ...message.options,
                store: false
            });
        });
    };

    api.prepareWorkspaceConversationSurface = function () {
        api.bindWorkspaceConversationSurface();
        api.renderStoredConversationMessages();
        api.syncSolomonHistoryState();
        api.scrollWorkspaceConversationThread();
    };

    api.revealWorkspaceConversation = function (options) {
        const opened = api.setWorkspaceView("chat", {
            focusInput: false
        });

        if (!opened) {
            return false;
        }

        window.requestAnimationFrame(function () {
            api.scrollWorkspaceConversationThread();

            if (options?.focusInput) {
                api.focusWorkspaceConversationInput({
                    select: false
                });
            }
        });

        return true;
    };

    api.openWorkspaceConversation = function (options) {
        const mount = document.querySelector(api.constants.WORKSPACE_MOUNT_SELECTOR);

        if (!mount) {
            return false;
        }

        const staticSurface = document.querySelector(api.constants.WORKSPACE_CONVERSATION_SELECTOR);

        if (staticSurface) {
            staticSurface.setAttribute("data-solomon-workspace-transition", "preparing");
            api.prepareWorkspaceConversationSurface();

            window.requestAnimationFrame(function () {
                api.revealWorkspaceConversation(options);

                window.requestAnimationFrame(function () {
                    staticSurface.removeAttribute("data-solomon-workspace-transition");
                });
            });

            return true;
        }

        api.captureWorkspaceSnapshot();

        const documentExplorer = api.getDocumentExplorerElements();

        if (documentExplorer.explorer && documentExplorer.browser && documentExplorer.inspector) {
            const surface = api.createWorkspaceConversationSurface();

            surface.classList.add("solomon-workspace-conversation--explorer-main");
            surface.setAttribute("data-solomon-workspace-conversation-scope", "document_explorer");
            surface.setAttribute("data-solomon-workspace-transition", "preparing");
            documentExplorer.browser.remove();
            documentExplorer.inspector.remove();
            documentExplorer.explorer.append(surface);
            documentExplorer.explorer.setAttribute("data-solomon-workspace-mode", "conversation");
            mount.setAttribute("data-solomon-workspace-mode", "conversation");

            api.prepareWorkspaceConversationSurface();

            window.requestAnimationFrame(function () {
                surface.removeAttribute("data-solomon-workspace-transition");
            });
        } else {
            const surface = api.createWorkspaceConversationSurface();

            surface.setAttribute("data-solomon-workspace-transition", "preparing");
            mount.replaceChildren(surface);
            mount.setAttribute("data-solomon-workspace-mode", "conversation");

            api.prepareWorkspaceConversationSurface();

            window.requestAnimationFrame(function () {
                surface.removeAttribute("data-solomon-workspace-transition");
            });
        }

        document.documentElement.setAttribute("data-solomon-workspace-conversation-open", "true");

        if (options?.focusInput) {
            window.requestAnimationFrame(function () {
                api.focusWorkspaceConversationInput({ select: false });
            });
        }

        return true;
    };

    api.restoreWorkspaceSnapshot = function () {
        const mount = document.querySelector(api.constants.WORKSPACE_MOUNT_SELECTOR);
        const staticSurface = document.querySelector(api.constants.WORKSPACE_CONVERSATION_SELECTOR);

        if (staticSurface && api.setWorkspaceView("files", { focusTaskbar: true })) {
            api.syncSolomonHistoryState();
            return;
        }

        const snapshot = api.state.solomonWorkspaceSnapshot;

        if (!mount || !snapshot) {
            document.documentElement.setAttribute("data-solomon-workspace-conversation-open", "false");
            api.syncSolomonHistoryState();
            return;
        }

        let restored = false;

        if (snapshot.type === "document_explorer") {
            const explorerElements = api.getDocumentExplorerElements();
            const surface = explorerElements.explorer?.querySelector(api.constants.WORKSPACE_CONVERSATION_SELECTOR);

            if (explorerElements.explorer && snapshot.browserHtml && snapshot.inspectorHtml) {
                surface?.remove();
                explorerElements.explorer.insertAdjacentHTML("beforeend", snapshot.browserHtml);
                explorerElements.explorer.insertAdjacentHTML("beforeend", snapshot.inspectorHtml);
                explorerElements.explorer.removeAttribute("data-solomon-workspace-mode");
                mount.removeAttribute("data-solomon-workspace-mode");
                restored = true;
            }
        } else if (snapshot.html) {
            mount.innerHTML = snapshot.html;
            mount.removeAttribute("data-solomon-workspace-mode");
            restored = true;
        }

        if (!restored) {
            return;
        }

        document.documentElement.setAttribute("data-solomon-workspace-conversation-open", "false");
        api.state.solomonWorkspaceSnapshot = null;

        const moduleId = snapshot.moduleId || "home";
        const activeWorkflow = api.updateWorkspaceShellState(moduleId);

        api.dispatchWorkspaceLoaded(moduleId, activeWorkflow, mount);
        api.syncSolomonHistoryState();
        api.focusTaskbarInput({ select: false });
    };

    api.restoreWorkspaceConversationFromHistory = function (options) {
        if (!api.hasSolomonHistory()) {
            return false;
        }

        return api.openWorkspaceConversation({
            focusInput: options?.focusInput !== false
        });
    };

    api.scrollWorkspaceConversationThread = function () {
        const elements = api.getWorkspaceConversationElements();

        if (elements.thread) {
            elements.thread.scrollTop = elements.thread.scrollHeight;
        }
    };

    api.createSolomonStreamPendingMessage = function () {
        const message = document.createElement("article");

        message.className = [
            "solomon-workspace-conversation-message",
            "solomon-workspace-conversation-message--assistant",
            "solomon-workspace-conversation-message--pending",
            "is-streaming"
        ].join(" ");
        message.setAttribute("data-solomon-workspace-conversation-message", "");
        message.setAttribute("data-solomon-stream-pending-message", "");
        message.setAttribute("aria-live", "polite");

        const meta = document.createElement("div");
        meta.className = "solomon-workspace-conversation-message-meta";
        meta.textContent = "SolomonAI";

        const content = document.createElement("div");
        content.className = "solomon-workspace-conversation-message-content";
        content.innerHTML = [
            '<p><span class="solomon-streaming-dot" aria-hidden="true"></span>',
            '<span data-solomon-stream-pending-text>SolomonAI is drafting…</span></p>'
        ].join("");

        message.append(meta, content);
        return message;
    };

    api.showSolomonStreamPendingMessage = function (label) {
        const opened = api.openWorkspaceConversation({
            focusInput: false
        });

        if (!opened && !api.isWorkspaceConversationOpen()) {
            return;
        }

        const elements = api.getWorkspaceConversationElements();

        if (!elements.thread) {
            return;
        }

        if (elements.empty) {
            elements.empty.hidden = true;
        }

        if (!api.state.solomonPendingMessage || !api.state.solomonPendingMessage.isConnected) {
            api.state.solomonPendingMessage = api.createSolomonStreamPendingMessage();
            elements.thread.append(api.state.solomonPendingMessage);
        }

        const pendingText = api.state.solomonPendingMessage.querySelector("[data-solomon-stream-pending-text]");

        if (pendingText) {
            pendingText.textContent = label || "SolomonAI is drafting…";
        }

        api.state.solomonConversationState = "streaming";
        document.documentElement.setAttribute("data-solomon-response-unread", "false");
        document.documentElement.setAttribute("data-solomon-workspace-streaming", "true");
        api.setWorkspaceConversationStatus(label || "SolomonAI is drafting…");
        api.scrollWorkspaceConversationThread();
    };

    api.removePendingMessage = function () {
        if (api.state.solomonPendingMessage && api.state.solomonPendingMessage.isConnected) {
            api.state.solomonPendingMessage.remove();
        }

        api.state.solomonPendingMessage = null;
    };

    api.clearSolomonStreamingState = function () {
        document.documentElement.setAttribute("data-solomon-workspace-streaming", "false");
    };

    api.handleSolomonAssistantStreamRequest = function () {
        api.showSolomonStreamPendingMessage("Connecting to SolomonAI…");
    };

    api.handleSolomonAssistantStreamOpen = function () {
        api.showSolomonStreamPendingMessage("SolomonAI is drafting…");
    };

    api.handleSolomonAssistantStreamPacket = function () {
        api.removePendingMessage();
        api.clearSolomonStreamingState();
        api.setWorkspaceConversationStatus("Rendering SolomonAI response…");
    };

    api.handleSolomonAssistantStreamDone = function () {
        api.clearSolomonStreamingState();
    };

    api.handleSolomonAssistantStreamError = function () {
        api.removePendingMessage();
        api.clearSolomonStreamingState();
        api.setWorkspaceConversationStatus("SolomonAI could not complete the stream.");
    };

    api.bindSolomonAssistantStreamEvents = function () {
        if (api.state.solomonStreamEventsBound === true) {
            return;
        }

        api.state.solomonStreamEventsBound = true;

        window.addEventListener("solomon:assistant:stream-request", api.handleSolomonAssistantStreamRequest);
        window.addEventListener("solomon:assistant:stream-open", api.handleSolomonAssistantStreamOpen);
        window.addEventListener("solomon:assistant:stream-packet", api.handleSolomonAssistantStreamPacket);
        window.addEventListener("solomon:assistant:stream-done", api.handleSolomonAssistantStreamDone);
        window.addEventListener("solomon:assistant:stream-error", api.handleSolomonAssistantStreamError);
    };

    api.clearSolomonMessages = function (options) {
        const elements = api.getWorkspaceConversationElements();

        api.state.solomonPendingMessage = null;
        api.state.solomonConversationMessages = [];

        elements.thread
            ?.querySelectorAll("[data-solomon-workspace-conversation-message]")
            .forEach(function (message) {
                message.remove();
            });

        if (elements.empty) {
            elements.empty.hidden = options?.showEmpty === true ? false : true;
        }

        api.state.solomonConversationState = "empty";
        document.documentElement.setAttribute("data-solomon-response-unread", "false");
        api.clearSolomonStreamingState();
        api.syncSolomonHistoryState();
        api.setWorkspaceConversationStatus("Ready for SolomonAI");
    };

    api.resetSolomonConversation = function () {
        api.clearSolomonMessages({ showEmpty: true });
        api.resetHomeConversationId();
        api.openWorkspaceConversation({ focusInput: true });
    };

    api.bindSolomonAssistantStreamEvents();
})();