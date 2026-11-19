/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_message_renderer.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI conversation-message renderer.

   Creates browser message elements, hydrates persisted assistant content,
   appends new turns, progressively updates pending assistant text in place,
   and replaces pending responses. Durable message content, ordering, identity,
   and execution state remain server-owned.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before message renderer."
        );
    }

    const { cleanValue } = modules.requireModule("contract");
    const markdown = modules.requireModule("message_markdown");
    const content = modules.requireModule("message_content");
    const continuation = modules.requireModule("message_continuation");
    const pending = modules.requireModule("message_pending");
    const timeline = modules.requireModule("message_timeline");
    const MESSAGE_SELECTOR = "[data-solomon-ai-message]";
    const ACTIONS_SELECTOR = "[data-solomon-ai-message-actions]";
    const PROGRESSIVE_RENDER_ATTRIBUTE =
        "data-solomon-ai-progressive-render";

    function renderMessageActions(message, elements) {
        const actions = modules.getModule("message_actions");

        if (typeof actions?.renderMessageActions !== "function") {
            return false;
        }

        return actions.renderMessageActions(message, elements);
    }

    function applyMessageIdentity(message, options) {
        const messageId = cleanValue(options?.messageId);
        const requestId = cleanValue(options?.requestId);

        if (messageId) {
            message.setAttribute(
                "data-solomon-ai-message-id",
                messageId
            );
        }

        if (requestId) {
            message.setAttribute(
                "data-solomon-ai-request-id",
                requestId
            );
        }
    }

    function setCompletedMessageState(message, error) {
        if (!message) {
            return false;
        }

        message.classList.toggle(
            "solomon-ai-message--error",
            error === true
        );
        message.setAttribute(
            "data-solomon-ai-message-state",
            error === true ? "error" : "complete"
        );

        return true;
    }

    function createMessage(role, text, options) {
        const normalizedRole = role === "user" ? "user" : "assistant";
        const message = document.createElement("article");
        const label = document.createElement("div");
        const body = document.createElement("div");
        const timestamp = (
            timeline.parseMessageTimestamp(options?.createdAt) ||
            new Date()
        ).toISOString();

        message.className = [
            "solomon-ai-message",
            `solomon-ai-message--${normalizedRole}`
        ].join(" ");
        message.setAttribute("data-solomon-ai-message", "");
        message.setAttribute(
            "data-solomon-ai-message-role",
            normalizedRole
        );
        message.setAttribute(
            "data-solomon-ai-message-created-at",
            timestamp
        );

        applyMessageIdentity(message, options);

        label.className = "solomon-ai-message__label";
        label.textContent = normalizedRole === "user"
            ? "You"
            : "SolomonAI";

        body.className = "solomon-ai-message__body";
        message.append(label, body);

        if (options?.pending === true) {
            message.setAttribute("aria-busy", "true");
            pending.markMessagePending(
                message,
                options?.pendingState
            );
        } else {
            setCompletedMessageState(
                message,
                options?.error === true
            );
            markdown.renderMessageBody(
                body,
                text,
                {
                    markdown: normalizedRole === "assistant"
                }
            );
            content.setPersistedMessageContent(
                body,
                text
            );
        }

        return message;
    }

    function hydrateExistingAssistantMessages(elements) {
        if (!elements?.thread) {
            return 0;
        }

        let hydratedCount = 0;

        elements.thread.querySelectorAll(
            ".solomon-ai-message--assistant .solomon-ai-message__body"
        ).forEach(function (body) {
            const message = body.closest(MESSAGE_SELECTOR);

            if (
                !message ||
                pending.isPendingMessage(message)
            ) {
                return;
            }

            const presentation =
                content.getExistingMessagePresentation(
                    body
                );
            const persistedText =
                content.getPersistedMessageContent(
                    body
                );

            if (cleanValue(persistedText)) {
                markdown.renderMessageBody(
                    body,
                    persistedText,
                    { markdown: true }
                );
                continuation.renderMessageContinuation(
                    message,
                    elements,
                    presentation
                );
                renderMessageActions(
                    message,
                    elements
                );
                hydratedCount += 1;
                return;
            }

            if (
                body.getAttribute(
                    "data-solomon-ai-content-rendered"
                ) === "true"
            ) {
                renderMessageActions(
                    message,
                    elements
                );
                hydratedCount += 1;
                return;
            }

            if (
                body.querySelector(
                    "h2, h3, h4, ul, ol, blockquote, pre"
                )
            ) {
                body.setAttribute(
                    "data-solomon-ai-content-format",
                    "markdown"
                );
                body.setAttribute(
                    "data-solomon-ai-content-rendered",
                    "true"
                );
                renderMessageActions(
                    message,
                    elements
                );
                hydratedCount += 1;
                return;
            }

            const sourceText =
                content.getExistingMessageBodySource(
                    body
                );

            if (sourceText) {
                markdown.renderMessageBody(
                    body,
                    sourceText,
                    { markdown: true }
                );
                content.setPersistedMessageContent(
                    body,
                    sourceText
                );
            }

            continuation.renderMessageContinuation(
                message,
                elements,
                presentation
            );
            renderMessageActions(
                message,
                elements
            );
            hydratedCount += 1;
        });

        return hydratedCount;
    }

    function renderProgressiveMessageBody(body, text) {
        if (!body) {
            return false;
        }

        const fragment = document.createDocumentFragment();
        const lines = String(text || "").split("\n");

        lines.forEach(function (line, index) {
            if (index > 0) {
                fragment.append(
                    document.createElement("br")
                );
            }

            fragment.append(
                document.createTextNode(line)
            );
        });

        body.replaceChildren(fragment);
        body.setAttribute(
            PROGRESSIVE_RENDER_ATTRIBUTE,
            "true"
        );

        return true;
    }

    function updatePendingMessageText(
        elements,
        message,
        text
    ) {
        if (
            !message?.isConnected ||
            !pending.isPendingMessage(message)
        ) {
            return false;
        }

        const body = content.getMessageBody(
            message
        );

        if (!renderProgressiveMessageBody(body, text)) {
            return false;
        }

        timeline.scrollConversation(
            elements
        );

        return true;
    }

    function appendMessage(
        elements,
        role,
        text,
        options
    ) {
        if (!elements?.thread) {
            return null;
        }

        timeline.removeWelcome(elements);

        const message = createMessage(
            role,
            text,
            options
        );

        elements.thread.append(message);
        timeline.hydrateMessageTimeline(
            elements
        );

        if (
            role !== "user" &&
            options?.error !== true
        ) {
            continuation.renderMessageContinuation(
                message,
                elements,
                options?.presentation
            );

            if (options?.pending !== true) {
                renderMessageActions(
                    message,
                    elements
                );
            }
        }

        timeline.scrollConversation(
            elements
        );

        return message;
    }

    function replacePendingMessage(
        elements,
        message,
        text,
        options
    ) {
        if (!message?.isConnected) {
            return appendMessage(
                elements,
                "assistant",
                text,
                options
            );
        }

        const body =
            content.getMessageBody(
                message
            );
        const isError =
            options?.error === true;

        pending.clearPendingMessageState(
            message
        );
        applyMessageIdentity(
            message,
            options
        );
        setCompletedMessageState(
            message,
            isError
        );

        if (body) {
            body.removeAttribute(
                PROGRESSIVE_RENDER_ATTRIBUTE
            );
            markdown.renderMessageBody(
                body,
                text,
                { markdown: true }
            );
            content.setPersistedMessageContent(
                body,
                text
            );
        }

        if (isError) {
            continuation.removeMessageContinuation(
                message
            );
            message.querySelector(
                ACTIONS_SELECTOR
            )?.remove();
        } else {
            continuation.renderMessageContinuation(
                message,
                elements,
                options?.presentation
            );

            if (options?.actions === true) {
                renderMessageActions(
                    message,
                    elements
                );
            }
        }

        timeline.hydrateMessageTimeline(
            elements
        );
        timeline.scrollConversation(
            elements
        );

        return message;
    }

    function initialize(elements) {
        if (!elements?.thread) {
            return false;
        }

        hydrateExistingAssistantMessages(
            elements
        );

        return true;
    }

    modules.registerModule(
        "message_renderer",
        {
            appendMessage,
            applyMessageIdentity,
            createMessage,
            hydrateExistingAssistantMessages,
            initialize,
            renderMessageActions,
            replacePendingMessage,
            setCompletedMessageState,
            updatePendingMessageText
        }
    );
})(window, document);