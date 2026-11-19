/* -------------------------------------------------------------------
   FILE: workspace_document_conversation.js
   DIRECTORY: webui/static/js/command_center/
   Solomon Documents conversation focus, workspace view, and taskbar state
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentConversation";

    const EXPLORER_SELECTOR = "[data-document-explorer]";
    const DOCUMENT_COLLECTION_SELECTOR = "[data-document-collection]";
    const WORKSPACE_VIEW_BUTTON_SELECTOR = ".workspace-document-view-button[data-workspace-view]";
    const WORKSPACE_VIEW_PANEL_SELECTOR = "[data-workspace-view-panel]";
    const WORKSPACE_READER_PANEL_SELECTOR = "[data-workspace-reader-panel]";
    const SOLOMON_CONVERSATION_RESUME_SELECTOR = "[data-solomon-conversation-resume]";
    const SOLOMON_ASSISTANT_FORM_SELECTOR = "#solomonAssistantForm";
    const SOLOMON_ASSISTANT_INPUT_SELECTOR = "#solomonAssistantInput";
    const SOLOMON_ASSISTANT_THREAD_SELECTOR = "[data-solomon-assistant-thread]";
    const WORKSPACE_CONVERSATION_THREAD_SELECTOR = "[data-solomon-workspace-conversation-thread]";
    const WORKSPACE_CONVERSATION_FORM_SELECTOR = "#solomonWorkspaceConversationForm";
    const WORKSPACE_CONVERSATION_INPUT_SELECTOR = "#solomonWorkspaceConversationInput";
    const WORKSPACE_CONVERSATION_SEND_SELECTOR = "#solomonWorkspaceConversationSend";
    const TASKBAR_SHELL_SELECTOR = "#commandSidebar";
    const TASKBAR_COMMAND_SELECTOR = "[data-solomon-taskbar-command]";
    const TASKBAR_COMMAND_FALLBACK_SELECTOR = "#commandTaskbarSolomonForm";
    const TASKBAR_BREADCRUMB_SELECTOR = "[data-solomon-taskbar-breadcrumb]";

    const DEFAULT_WORKSPACE_VIEW = "files";
    const READER_WORKSPACE_VIEW = "reader";
    const DEFAULT_DOCUMENT_COLLECTION = "all";
    const SOLOMON_FOCUS_BODY_CLASS = "solomon-focus-mode-active";
    const WORKSPACE_CHAT_TOPBAR_CLASS = "is-workspace-chat-open";
    const WORKSPACE_CONVERSATION_PENDING_TIMEOUT_MS = 45000;
    const READER_ROUTE_PATTERN = /^\/workspace\/(?:file|document)\/[^/]+\/reader\/?$/;

    const MESSAGE_DECORATED_ATTR = "data-solomon-workspace-message-decorated";
    const MESSAGE_TIMESTAMP_ATTR = "data-solomon-workspace-message-created-at";
    const MESSAGE_AUTHOR_ATTR = "data-solomon-workspace-message-author";
    const MESSAGE_TIMESTAMP_CLASS = "solomon-workspace-message-timestamp";
    const MESSAGE_AUTHOR_HIDDEN_ATTR = "data-solomon-workspace-author-hidden";
    const MESSAGE_AUTHOR_LABELS = new Set(["SolomonAI", "Solomon", "You"]);
    const MESSAGE_AUTHOR_LABEL_SELECTOR = [
        ".solomon-workspace-conversation-message-label",
        "[data-solomon-message-author]",
        "[data-solomon-message-speaker]",
        "[data-solomon-author]",
        "[data-solomon-speaker]",
        "[data-message-author]",
        "[data-message-speaker]",
        ".solomon-message-author",
        ".solomon-message-speaker",
        ".solomon-assistant-message-author",
        ".solomon-assistant-message-speaker",
        ".solomon-conversation-message-author",
        ".solomon-conversation-message-speaker",
        ".workspace-conversation-message-author",
        ".workspace-conversation-message-speaker",
        ".workspace-chat-message-author",
        ".workspace-chat-message-speaker",
        ".assistant-message-author",
        ".assistant-message-speaker",
        ".message-author",
        ".message-speaker"
    ].join(",");

    const MESSAGE_SELECTOR = [
        ".solomon-workspace-conversation-message",
        "[data-solomon-message]",
        "[data-solomon-message-role]",
        "[data-message-role]",
        ".solomon-assistant-message",
        ".solomon-conversation-message",
        ".solomon-workspace-message",
        ".workspace-conversation-message"
    ].join(",");

    if (window[API_NAME]) {
        return;
    }

    function getOptions(explorer, overrides) {
        return Object.assign(
            {},
            explorer?.__solomonDocumentConversationOptions || {},
            overrides || {}
        );
    }

    function setOptions(explorer, options) {
        if (!explorer) {
            return {};
        }

        explorer.__solomonDocumentConversationOptions = getOptions(explorer, options);
        return explorer.__solomonDocumentConversationOptions;
    }

    function isReaderRoute() {
        return READER_ROUTE_PATTERN.test(String(window.location?.pathname || ""));
    }

    function hasReaderPanel(explorer) {
        return Boolean(explorer?.querySelector(WORKSPACE_READER_PANEL_SELECTOR));
    }

    function shouldUseReaderRouteView(explorer) {
        return Boolean(hasReaderPanel(explorer) && isReaderRoute());
    }

    function lockInitialReaderView(explorer) {
        if (!explorer || !hasReaderPanel(explorer)) {
            return;
        }

        const currentView = String(explorer.getAttribute("data-workspace-view") || "").trim();

        if (currentView !== READER_WORKSPACE_VIEW && !shouldUseReaderRouteView(explorer)) {
            return;
        }

        explorer.__solomonReaderViewLocked = true;
        explorer.__solomonReaderRouteActive = shouldUseReaderRouteView(explorer);
        explorer.setAttribute("data-workspace-view", READER_WORKSPACE_VIEW);
    }

    function clearReaderViewLock(explorer) {
        if (!explorer) {
            return;
        }

        explorer.__solomonReaderViewLocked = false;
        explorer.__solomonReaderRouteActive = false;
    }

    function shouldPreserveReaderView(explorer, nextView, options) {
        return Boolean(
            (explorer?.__solomonReaderViewLocked || shouldUseReaderRouteView(explorer)) &&
            nextView !== READER_WORKSPACE_VIEW &&
            !hasFilesViewIntent(explorer) &&
            options?.allowReaderExit !== true
        );
    }

    function getAvailableWorkspaceViews(explorer) {
        const views = new Set([DEFAULT_WORKSPACE_VIEW]);

        explorer.querySelectorAll(WORKSPACE_VIEW_BUTTON_SELECTOR).forEach(function (button) {
            const view = String(button.getAttribute("data-workspace-view") || "").trim();

            if (view) {
                views.add(view);
            }
        });

        explorer.querySelectorAll(WORKSPACE_VIEW_PANEL_SELECTOR).forEach(function (panel) {
            const view = String(panel.getAttribute("data-workspace-view-panel") || "").trim();

            if (view) {
                views.add(view);
            }
        });

        return Array.from(views);
    }

    function normalizeWorkspaceView(explorer, view) {
        const cleanView = String(view || DEFAULT_WORKSPACE_VIEW).trim() || DEFAULT_WORKSPACE_VIEW;
        const availableViews = getAvailableWorkspaceViews(explorer);

        return availableViews.includes(cleanView) ? cleanView : DEFAULT_WORKSPACE_VIEW;
    }

    function getSolomonThread(explorer) {
        return (
            explorer.querySelector(WORKSPACE_CONVERSATION_THREAD_SELECTOR) ||
            explorer.querySelector(SOLOMON_ASSISTANT_THREAD_SELECTOR)
        );
    }

    function hasConversationContent(explorer) {
        const thread = getSolomonThread(explorer);

        return Boolean(
            explorer.__solomonConversationStarted ||
            thread?.children?.length ||
            String(thread?.textContent || "").trim()
        );
    }

    function getMessageTimestampIso(message) {
        const existingTimestamp = String(message.getAttribute(MESSAGE_TIMESTAMP_ATTR) || "").trim();
        const explicitTimestamp = String(
            message.getAttribute("data-solomon-message-created-at") ||
            message.getAttribute("data-message-created-at") ||
            message.getAttribute("data-created-at") ||
            message.getAttribute("data-timestamp") ||
            ""
        ).trim();
        const timeElementTimestamp = String(message.querySelector("time[datetime]")?.getAttribute("datetime") || "").trim();
        const timestampCandidate = existingTimestamp || explicitTimestamp || timeElementTimestamp;
        const parsedDate = timestampCandidate ? new Date(timestampCandidate) : new Date();

        if (Number.isNaN(parsedDate.getTime())) {
            return new Date().toISOString();
        }

        return parsedDate.toISOString();
    }

    function formatMessageTimestamp(timestampIso) {
        const parsedDate = new Date(timestampIso);

        if (Number.isNaN(parsedDate.getTime())) {
            return "";
        }

        return parsedDate.toLocaleTimeString([], {
            hour: "numeric",
            minute: "2-digit"
        });
    }

    function normalizeMessageAuthor(value) {
        const cleanValue = String(value || "").trim().toLowerCase();

        if (["user", "human", "you", "owner"].includes(cleanValue)) {
            return "user";
        }

        if (["assistant", "ai", "solomon", "solomonai"].includes(cleanValue)) {
            return "assistant";
        }

        return "";
    }

    function inferMessageAuthor(message) {
        const explicitAuthor = normalizeMessageAuthor(
            message.getAttribute("data-solomon-message-author") ||
            message.getAttribute("data-solomon-message-role") ||
            message.getAttribute("data-message-author") ||
            message.getAttribute("data-message-role") ||
            message.getAttribute("data-role") ||
            message.getAttribute("role")
        );

        if (explicitAuthor) {
            return explicitAuthor;
        }

        const className = String(message.className || "").toLowerCase();

        if (className.includes("user") || className.includes("human")) {
            return "user";
        }

        if (className.includes("assistant") || className.includes("solomon")) {
            return "assistant";
        }

        return "";
    }

    function hideElementFromInterface(element) {
        if (!element || element.getAttribute(MESSAGE_AUTHOR_HIDDEN_ATTR) === "true") {
            return false;
        }

        element.hidden = true;
        element.setAttribute("aria-hidden", "true");
        element.setAttribute(MESSAGE_AUTHOR_HIDDEN_ATTR, "true");
        return true;
    }

    function hideLeadingAuthorLabel(message) {
        let firstElement = message.firstElementChild;

        while (firstElement && firstElement.classList?.contains(MESSAGE_TIMESTAMP_CLASS)) {
            firstElement = firstElement.nextElementSibling;
        }

        if (!firstElement) {
            return false;
        }

        const label = String(firstElement.textContent || "").replace(/\s+/g, " ").trim();

        if (!MESSAGE_AUTHOR_LABELS.has(label)) {
            return false;
        }

        if (firstElement.childElementCount > 1 || label.length > 16) {
            return false;
        }

        return hideElementFromInterface(firstElement);
    }

    function hideMessageAuthorLabels(message) {
        let didMutate = false;

        message.querySelectorAll(MESSAGE_AUTHOR_LABEL_SELECTOR).forEach(function (labelElement) {
            const label = String(labelElement.textContent || "").replace(/\s+/g, " ").trim();

            if (MESSAGE_AUTHOR_LABELS.has(label)) {
                didMutate = hideElementFromInterface(labelElement) || didMutate;
            }
        });

        return hideLeadingAuthorLabel(message) || didMutate;
    }

    function getExistingMessageTimestampElement(message) {
        let child = message.firstElementChild;

        while (child) {
            if (child.classList?.contains(MESSAGE_TIMESTAMP_CLASS)) {
                return child;
            }

            child = child.nextElementSibling;
        }

        return null;
    }

    function ensureMessageTimestamp(message) {
        const timestampIso = getMessageTimestampIso(message);
        const timestampText = formatMessageTimestamp(timestampIso);

        if (!timestampText) {
            return false;
        }

        let didMutate = false;
        let timestampElement = getExistingMessageTimestampElement(message);

        if (!timestampElement) {
            timestampElement = document.createElement("span");
            timestampElement.className = MESSAGE_TIMESTAMP_CLASS;
            timestampElement.setAttribute("aria-label", "Message timestamp");
            message.insertBefore(timestampElement, message.firstChild);
            didMutate = true;
        }

        if (message.getAttribute(MESSAGE_TIMESTAMP_ATTR) !== timestampIso) {
            message.setAttribute(MESSAGE_TIMESTAMP_ATTR, timestampIso);
            didMutate = true;
        }

        if (timestampElement.textContent !== timestampText) {
            timestampElement.textContent = timestampText;
            didMutate = true;
        }

        if (timestampElement.getAttribute("title") !== timestampIso) {
            timestampElement.setAttribute("title", timestampIso);
            didMutate = true;
        }

        if (timestampElement.getAttribute("data-solomon-workspace-message-time") !== timestampIso) {
            timestampElement.setAttribute("data-solomon-workspace-message-time", timestampIso);
            didMutate = true;
        }

        return didMutate;
    }

    function isDecoratableMessageNode(node) {
        return Boolean(
            node instanceof HTMLElement &&
            !node.classList.contains(MESSAGE_TIMESTAMP_CLASS) &&
            String(node.textContent || "").trim()
        );
    }

    function getConversationMessageNodes(thread) {
        const specificMessages = Array.from(thread.querySelectorAll(".solomon-workspace-conversation-message")).filter(isDecoratableMessageNode);

        if (specificMessages.length) {
            return specificMessages;
        }

        const directMessages = Array.from(thread.children || []).filter(isDecoratableMessageNode);

        if (directMessages.length) {
            return directMessages;
        }

        return Array.from(thread.querySelectorAll(MESSAGE_SELECTOR)).filter(isDecoratableMessageNode);
    }

    function decorateConversationMessages(explorer) {
        const thread = getSolomonThread(explorer);

        if (!thread || explorer.__solomonConversationDecorating) {
            return;
        }

        explorer.__solomonConversationDecorating = true;

        try {
            getConversationMessageNodes(thread).forEach(function (message) {
                if (message.getAttribute(MESSAGE_DECORATED_ATTR) === "true") {
                    return;
                }

                const author = inferMessageAuthor(message);

                if (author && message.getAttribute(MESSAGE_AUTHOR_ATTR) !== author) {
                    message.setAttribute(MESSAGE_AUTHOR_ATTR, author);
                }

                hideMessageAuthorLabels(message);
                ensureMessageTimestamp(message);
                message.setAttribute(MESSAGE_DECORATED_ATTR, "true");
            });
        } finally {
            explorer.__solomonConversationDecorating = false;
        }
    }

    function requestDecorateConversationMessages(explorer) {
        if (!explorer || explorer.__solomonConversationDecorateQueued) {
            return;
        }

        explorer.__solomonConversationDecorateQueued = true;

        window.requestAnimationFrame(function () {
            explorer.__solomonConversationDecorateQueued = false;
            decorateConversationMessages(explorer);
        });
    }

    function resolveTaskbarCommandForm() {
        return (
            document.querySelector(TASKBAR_COMMAND_SELECTOR) ||
            document.querySelector(TASKBAR_COMMAND_FALLBACK_SELECTOR)
        );
    }

    function isWorkspaceChatOpen() {
        return Boolean(document.querySelector(`${EXPLORER_SELECTOR}[data-workspace-view="chat"]`));
    }

    function scheduleChatViewAfterCommandSubmit(explorer) {
        if (!explorer || explorer.__solomonCommandSubmitChatQueued) {
            return;
        }

        explorer.__solomonCommandSubmitChatQueued = true;

        window.setTimeout(function () {
            explorer.__solomonCommandSubmitChatQueued = false;
            activateFocusMode(explorer, {
                focusInput: false,
                force: true
            });
        }, 0);
    }

    function setTaskbarCommandChildVisibility(commandForm, isVisible) {
        if (!commandForm) {
            return;
        }

        commandForm.querySelectorAll("input, textarea, select, button").forEach(function (control) {
            if (isVisible) {
                control.setAttribute("aria-hidden", "false");
                control.removeAttribute("data-solomon-workspace-chat-hidden");

                if (control.getAttribute("data-solomon-workspace-original-tabindex") !== null) {
                    const originalTabIndex = control.getAttribute("data-solomon-workspace-original-tabindex");

                    if (originalTabIndex) {
                        control.setAttribute("tabindex", originalTabIndex);
                    } else {
                        control.removeAttribute("tabindex");
                    }

                    control.removeAttribute("data-solomon-workspace-original-tabindex");
                }

                return;
            }

            if (control.getAttribute("data-solomon-workspace-original-tabindex") === null) {
                control.setAttribute(
                    "data-solomon-workspace-original-tabindex",
                    control.getAttribute("tabindex") || ""
                );
            }

            control.setAttribute("aria-hidden", "true");
            control.setAttribute("tabindex", "-1");
            control.setAttribute("data-solomon-workspace-chat-hidden", "true");
        });
    }

    function setTaskbarCommandVisibility(commandForm, isVisible) {
        if (!commandForm) {
            return;
        }

        if (isVisible) {
            commandForm.hidden = false;
            commandForm.setAttribute("aria-hidden", "false");
            commandForm.setAttribute("data-solomon-command-visible", "true");
            commandForm.removeAttribute("data-solomon-workspace-chat-hidden");
            commandForm.style.removeProperty("display");
            commandForm.style.removeProperty("visibility");
            setTaskbarCommandChildVisibility(commandForm, true);
            return;
        }

        commandForm.hidden = true;
        commandForm.setAttribute("aria-hidden", "true");
        commandForm.setAttribute("data-solomon-command-visible", "false");
        commandForm.setAttribute("data-solomon-workspace-chat-hidden", "true");
        commandForm.style.setProperty("display", "none", "important");
        commandForm.style.setProperty("visibility", "hidden", "important");
        commandForm.removeAttribute("inert");
        setTaskbarCommandChildVisibility(commandForm, false);
    }

    function setConversationAvailable(explorer, isAvailable) {
        const resumeButtons = explorer.querySelectorAll(SOLOMON_CONVERSATION_RESUME_SELECTOR);

        explorer.__solomonConversationStarted = Boolean(isAvailable);

        resumeButtons.forEach(function (resumeButton) {
            const label = resumeButton.querySelector("em");

            resumeButton.hidden = false;
            resumeButton.setAttribute("aria-hidden", "false");

            if (label) {
                label.textContent = isAvailable ? "Resume" : "Open";
            }
        });
    }

    function markFilesViewIntent(explorer) {
        if (!explorer) {
            return;
        }

        explorer.__solomonFilesViewIntent = true;
    }

    function clearFilesViewIntent(explorer) {
        if (!explorer) {
            return;
        }

        explorer.__solomonFilesViewIntent = false;
    }

    function hasFilesViewIntent(explorer) {
        return Boolean(explorer?.__solomonFilesViewIntent);
    }

    function syncConversationState(explorer) {
        decorateConversationMessages(explorer);

        if (hasConversationContent(explorer)) {
            setConversationAvailable(explorer, true);
            return;
        }

        setConversationAvailable(explorer, false);
    }

    function syncTaskbarSlot(isChatOpen) {
        const shell = document.querySelector(TASKBAR_SHELL_SELECTOR) || document.querySelector(".command-taskbar");
        const commandForm = resolveTaskbarCommandForm();
        const breadcrumb = document.querySelector(TASKBAR_BREADCRUMB_SELECTOR);
        const showBreadcrumb = Boolean(isChatOpen || isWorkspaceChatOpen());

        if (shell) {
            shell.classList.toggle(WORKSPACE_CHAT_TOPBAR_CLASS, showBreadcrumb);
            shell.setAttribute("data-solomon-topbar-state", showBreadcrumb ? "workspace_chat" : "command");
        }

        setTaskbarCommandVisibility(commandForm, !showBreadcrumb);

        if (breadcrumb) {
            breadcrumb.hidden = !showBreadcrumb;
            breadcrumb.setAttribute("aria-hidden", showBreadcrumb ? "false" : "true");

            if (showBreadcrumb) {
                breadcrumb.style.setProperty("display", "inline-flex", "important");
            } else {
                breadcrumb.style.setProperty("display", "none", "important");
            }
        }
    }

    function syncTaskbarSlotDeferred(isChatOpen) {
        const runSync = function () {
            syncTaskbarSlot(isChatOpen);
        };

        window.setTimeout(runSync, 0);
        window.requestAnimationFrame(runSync);
        window.setTimeout(runSync, 80);
    }

    function clearSolomonFocusShellState(explorer) {
        const root = document.body || document.documentElement;

        if (root) {
            root.classList.remove(SOLOMON_FOCUS_BODY_CLASS);
        }

        if (explorer) {
            explorer.setAttribute("data-solomon-focus-mode", "idle");
        }
    }

    function setSolomonFocusBodyState(explorer, view) {
        clearSolomonFocusShellState(explorer);
        syncTaskbarSlot(view === "chat");
        syncTaskbarSlotDeferred(view === "chat");
    }

    function getActiveCollection(explorer) {
        return explorer.querySelector(`${DOCUMENT_COLLECTION_SELECTOR}.is-active`)?.getAttribute("data-document-collection") || DEFAULT_DOCUMENT_COLLECTION;
    }

    function setActiveCollection(explorer, collection) {
        const cleanCollection = String(collection || "").trim();

        if (!cleanCollection) {
            return;
        }

        explorer.querySelectorAll(DOCUMENT_COLLECTION_SELECTOR).forEach(function (button) {
            const isActive = button.getAttribute("data-document-collection") === cleanCollection;

            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
    }

    function hasSelectedDocument(explorer, options) {
        if (typeof options?.hasSelectedDocument === "function") {
            return Boolean(options.hasSelectedDocument(explorer));
        }

        return Boolean(explorer?.__selectedDocument);
    }

    function renderPreviewEmpty(explorer, options) {
        if (typeof options?.renderPreviewEmpty === "function") {
            options.renderPreviewEmpty(explorer);
        }
    }

    function setWorkspaceButtonState(explorer, nextView) {
        explorer.querySelectorAll(WORKSPACE_VIEW_BUTTON_SELECTOR).forEach(function (button) {
            const isActive = button.getAttribute("data-workspace-view") === nextView;

            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });
    }

    function setView(explorer, view, overrides) {
        if (!explorer) {
            return;
        }

        const options = getOptions(explorer, overrides);
        let nextView = normalizeWorkspaceView(explorer, view);

        if (shouldPreserveReaderView(explorer, nextView, options)) {
            nextView = READER_WORKSPACE_VIEW;
            explorer.__solomonReaderViewLocked = true;
        }

        if (nextView === "chat") {
            setConversationAvailable(explorer, true);
        }

        explorer.setAttribute("data-workspace-view", nextView);
        setSolomonFocusBodyState(explorer, nextView);
        setWorkspaceButtonState(explorer, nextView);
        requestDecorateConversationMessages(explorer);

        explorer.querySelectorAll(WORKSPACE_VIEW_PANEL_SELECTOR).forEach(function (panel) {
            const isActive = panel.getAttribute("data-workspace-view-panel") === nextView;

            panel.hidden = !isActive;
            panel.setAttribute("aria-hidden", isActive ? "false" : "true");
        });

        if (nextView === "preview" && !hasSelectedDocument(explorer, options)) {
            renderPreviewEmpty(explorer, options);
        }
    }

    function activateFocusMode(explorer, options) {
        if (!explorer) {
            return;
        }

        if ((explorer.__solomonReaderViewLocked || shouldUseReaderRouteView(explorer)) && options?.force !== true) {
            return;
        }

        if (hasFilesViewIntent(explorer) && options?.force !== true) {
            return;
        }

        clearFilesViewIntent(explorer);
        setConversationAvailable(explorer, true);
        setView(explorer, "chat");

        if (options?.focusInput === false) {
            return;
        }

        window.requestAnimationFrame(function () {
            const input = explorer.querySelector(WORKSPACE_CONVERSATION_INPUT_SELECTOR) ||
                explorer.querySelector(SOLOMON_ASSISTANT_INPUT_SELECTOR);

            if (input && typeof input.focus === "function") {
                input.focus();
            }
        });
    }

    function focusFilesViewButton(explorer) {
        window.requestAnimationFrame(function () {
            const activeCollectionButton = explorer?.querySelector(`${DOCUMENT_COLLECTION_SELECTOR}.is-active`);
            const allFilesButton = explorer?.querySelector(`${DOCUMENT_COLLECTION_SELECTOR}[data-document-collection='${DEFAULT_DOCUMENT_COLLECTION}']`);
            const focusTarget = activeCollectionButton || allFilesButton;

            if (focusTarget && typeof focusTarget.focus === "function" && !focusTarget.disabled && !focusTarget.hidden) {
                focusTarget.focus({ preventScroll: true });
            }
        });
    }

    function focusWorkspaceConversationInput(explorer) {
        if (!explorer || explorer.getAttribute("data-workspace-view") !== "chat") {
            return;
        }

        window.requestAnimationFrame(function () {
            const input = explorer.querySelector(WORKSPACE_CONVERSATION_INPUT_SELECTOR);

            if (input && typeof input.focus === "function" && !input.disabled && !input.hidden) {
                input.focus();
            }
        });
    }

    function clearPending(explorer) {
        if (!explorer) {
            return;
        }

        const form = explorer.querySelector(WORKSPACE_CONVERSATION_FORM_SELECTOR);
        const input = explorer.querySelector(WORKSPACE_CONVERSATION_INPUT_SELECTOR);
        const sendButton = explorer.querySelector(WORKSPACE_CONVERSATION_SEND_SELECTOR);

        if (explorer.__workspaceConversationPendingTimer) {
            window.clearTimeout(explorer.__workspaceConversationPendingTimer);
            explorer.__workspaceConversationPendingTimer = null;
        }

        if (form) {
            form.setAttribute("data-solomon-workspace-pending", "false");
        }

        if (input) {
            input.disabled = false;
            input.removeAttribute("aria-busy");
        }

        if (sendButton) {
            sendButton.disabled = false;
            sendButton.removeAttribute("aria-busy");
        }
    }

    function setPending(explorer) {
        const form = explorer.querySelector(WORKSPACE_CONVERSATION_FORM_SELECTOR);
        const input = explorer.querySelector(WORKSPACE_CONVERSATION_INPUT_SELECTOR);
        const sendButton = explorer.querySelector(WORKSPACE_CONVERSATION_SEND_SELECTOR);

        if (form) {
            form.setAttribute("data-solomon-workspace-pending", "true");
        }

        if (input) {
            input.disabled = true;
            input.setAttribute("aria-busy", "true");
        }

        if (sendButton) {
            sendButton.disabled = true;
            sendButton.setAttribute("aria-busy", "true");
        }

        if (explorer.__workspaceConversationPendingTimer) {
            window.clearTimeout(explorer.__workspaceConversationPendingTimer);
        }

        explorer.__workspaceConversationPendingTimer = window.setTimeout(function () {
            clearPending(explorer);
        }, WORKSPACE_CONVERSATION_PENDING_TIMEOUT_MS);
    }

    function returnToFiles(explorer) {
        if (!explorer) {
            return;
        }

        clearReaderViewLock(explorer);
        markFilesViewIntent(explorer);
        clearPending(explorer);
        clearSolomonFocusShellState(explorer);
        setActiveCollection(explorer, DEFAULT_DOCUMENT_COLLECTION);
        setView(explorer, "files", { allowReaderExit: true });

        window.requestAnimationFrame(function () {
            clearSolomonFocusShellState(explorer);
            syncTaskbarSlot(false);

            if (hasFilesViewIntent(explorer) && explorer.getAttribute("data-workspace-view") !== "files") {
                setView(explorer, "files", { allowReaderExit: true });
            }
        });

        focusFilesViewButton(explorer);
    }

    function getCanonicalSolomonForm(explorer) {
        return (
            explorer.querySelector(SOLOMON_ASSISTANT_FORM_SELECTOR) ||
            resolveTaskbarCommandForm() ||
            document.querySelector(SOLOMON_ASSISTANT_FORM_SELECTOR)
        );
    }

    function getCanonicalSolomonInput(explorer) {
        const form = getCanonicalSolomonForm(explorer);

        return (
            form?.querySelector(SOLOMON_ASSISTANT_INPUT_SELECTOR) ||
            form?.querySelector("[data-solomon-command-input]") ||
            explorer.querySelector(SOLOMON_ASSISTANT_INPUT_SELECTOR) ||
            document.querySelector(SOLOMON_ASSISTANT_INPUT_SELECTOR) ||
            document.querySelector("[data-solomon-command-input]")
        );
    }

    function submitCanonicalSolomonForm(form) {
        if (!form) {
            return false;
        }

        if (typeof form.requestSubmit === "function") {
            form.requestSubmit();
            return true;
        }

        return form.dispatchEvent(new Event("submit", {
            bubbles: true,
            cancelable: true
        }));
    }

    function submitWorkspaceConversationMessage(explorer) {
        const workspaceInput = explorer.querySelector(WORKSPACE_CONVERSATION_INPUT_SELECTOR);
        const canonicalForm = getCanonicalSolomonForm(explorer);
        const canonicalInput = getCanonicalSolomonInput(explorer);
        const message = String(workspaceInput?.value || "").trim();

        if (!workspaceInput || !message) {
            workspaceInput?.focus();
            return;
        }

        if (!canonicalForm || !canonicalInput) {
            console.error("[DOCUMENT_CONVERSATION] Missing canonical SolomonAI form.");
            workspaceInput.focus();
            return;
        }

        canonicalInput.value = message;
        workspaceInput.value = "";
        setPending(explorer);
        activateFocusMode(explorer, { focusInput: false, force: true });

        window.requestAnimationFrame(function () {
            submitCanonicalSolomonForm(canonicalForm);
        });
    }

    function bindWorkspaceNavigation(explorer) {
        if (!explorer || explorer.__solomonWorkspaceNavigationBound) {
            return;
        }

        explorer.__solomonWorkspaceNavigationBound = true;

        explorer.addEventListener("click", function (event) {
            const viewButton = event.target.closest(WORKSPACE_VIEW_BUTTON_SELECTOR);

            if (!viewButton || !explorer.contains(viewButton)) {
                return;
            }

            const requestedView = viewButton.getAttribute("data-workspace-view") || DEFAULT_WORKSPACE_VIEW;

            event.preventDefault();
            clearSolomonFocusShellState(explorer);
            clearFilesViewIntent(explorer);

            if (requestedView !== READER_WORKSPACE_VIEW) {
                clearReaderViewLock(explorer);
                setView(explorer, requestedView, { allowReaderExit: true });
            } else {
                setView(explorer, requestedView);
            }

            if (requestedView === "chat") {
                focusWorkspaceConversationInput(explorer);
            }
        });
    }

    function bindDocumentCollectionNavigation(explorer) {
        if (!explorer || explorer.__solomonDocumentCollectionNavigationBound) {
            return;
        }

        explorer.__solomonDocumentCollectionNavigationBound = true;

        explorer.addEventListener("click", function (event) {
            const collectionButton = event.target.closest(DOCUMENT_COLLECTION_SELECTOR);

            if (!collectionButton || !explorer.contains(collectionButton)) {
                return;
            }

            const requestedCollection = collectionButton.getAttribute("data-document-collection") || "";

            if (!requestedCollection) {
                return;
            }

            clearReaderViewLock(explorer);
            clearSolomonFocusShellState(explorer);
            markFilesViewIntent(explorer);
            clearPending(explorer);
            setActiveCollection(explorer, requestedCollection);
            setView(explorer, "files", { allowReaderExit: true });
            focusFilesViewButton(explorer);
        });
    }

    function bindWorkspaceConversationFormProxy(explorer) {
        const form = explorer.querySelector(WORKSPACE_CONVERSATION_FORM_SELECTOR);
        const input = explorer.querySelector(WORKSPACE_CONVERSATION_INPUT_SELECTOR);
        const sendButton = explorer.querySelector(WORKSPACE_CONVERSATION_SEND_SELECTOR);

        if (!form || !input || form.getAttribute("data-solomon-workspace-proxy-bound") === "true") {
            return;
        }

        form.setAttribute("data-solomon-workspace-proxy-bound", "true");

        form.addEventListener("submit", function (event) {
            event.preventDefault();
            event.stopPropagation();
            submitWorkspaceConversationMessage(explorer);
        });

        if (sendButton && sendButton.getAttribute("data-solomon-workspace-send-bound") !== "true") {
            sendButton.setAttribute("data-solomon-workspace-send-bound", "true");

            sendButton.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                submitWorkspaceConversationMessage(explorer);
            });
        }

        [
            "solomon:assistant-response",
            "solomon:assistant-history-updated"
        ].forEach(function (eventName) {
            document.addEventListener(eventName, function () {
                clearPending(explorer);
                clearSolomonFocusShellState(explorer);
                requestDecorateConversationMessages(explorer);
                syncTaskbarSlot(explorer.getAttribute("data-workspace-view") === "chat");
                focusWorkspaceConversationInput(explorer);
            });
        });
    }

    function bindConversationObserver(explorer) {
        const thread = getSolomonThread(explorer);

        if (!thread || explorer.__solomonConversationObserver) {
            syncConversationState(explorer);
            return;
        }

        const observer = new MutationObserver(function () {
            requestDecorateConversationMessages(explorer);

            if (!hasConversationContent(explorer)) {
                return;
            }

            setConversationAvailable(explorer, true);

            if (explorer.getAttribute("data-workspace-view") !== "chat" && !hasFilesViewIntent(explorer)) {
                setView(explorer, "chat");
            } else {
                syncTaskbarSlot(explorer.getAttribute("data-workspace-view") === "chat");
            }
        });

        observer.observe(thread, {
            childList: true,
            subtree: true
        });

        explorer.__solomonConversationObserver = observer;
        syncConversationState(explorer);
    }

    function bindSolomonFormLaunch(explorer) {
        const form = explorer.querySelector(SOLOMON_ASSISTANT_FORM_SELECTOR) || resolveTaskbarCommandForm();

        if (!form || form.getAttribute("data-solomon-focus-form-bound") === "true") {
            return;
        }

        form.setAttribute("data-solomon-focus-form-bound", "true");

        form.addEventListener("submit", function () {
            scheduleChatViewAfterCommandSubmit(explorer);
        }, true);
    }

    function bindGlobalSolomonLaunch(explorer) {
        if (!explorer || explorer.__solomonGlobalLaunchBound) {
            return;
        }

        explorer.__solomonGlobalLaunchBound = true;

        document.addEventListener("submit", function (event) {
            const form = event.target;

            if (!(form instanceof HTMLFormElement) || form.closest(EXPLORER_SELECTOR)) {
                return;
            }

            const hasSolomonInput = Boolean(
                form.querySelector("[data-solomon-global-command-input]") ||
                form.querySelector("[data-solomon-command-input]") ||
                form.querySelector(".solomon-command-input") ||
                form.querySelector("input[placeholder*='SolomonAI']")
            );

            if (!hasSolomonInput) {
                return;
            }

            scheduleChatViewAfterCommandSubmit(explorer);
        }, true);

        [
            "solomon:assistant-submitted",
            "solomon:assistant-message",
            "solomon:assistant-response",
            "solomon:assistant-history-updated"
        ].forEach(function (eventName) {
            document.addEventListener(eventName, function () {
                const isUserLaunchEvent = eventName === "solomon:assistant-submitted";

                activateFocusMode(explorer, {
                    focusInput: false,
                    force: isUserLaunchEvent
                });
            });
        });
    }

    function bind(explorer, options) {
        if (!explorer) {
            return;
        }

        setOptions(explorer, options);
        lockInitialReaderView(explorer);

        bindWorkspaceNavigation(explorer);
        bindDocumentCollectionNavigation(explorer);
        bindSolomonFormLaunch(explorer);
        bindWorkspaceConversationFormProxy(explorer);
        bindConversationObserver(explorer);
        bindGlobalSolomonLaunch(explorer);

        setConversationAvailable(explorer, hasConversationContent(explorer));
        clearSolomonFocusShellState(explorer);
        setView(
            explorer,
            explorer.getAttribute("data-workspace-view") ||
            options?.defaultView ||
            DEFAULT_WORKSPACE_VIEW
        );
        requestDecorateConversationMessages(explorer);
        syncTaskbarSlot(explorer.getAttribute("data-workspace-view") === "chat");
    }

    window[API_NAME] = Object.freeze({
        bind,
        setOptions,
        setView,
        activateFocusMode,
        returnToFiles,
        markFilesViewIntent,
        clearFilesViewIntent,
        hasFilesViewIntent,
        setConversationAvailable,
        hasConversationContent,
        clearPending,
        focusFilesViewButton,
        focusWorkspaceConversationInput
    });
})();