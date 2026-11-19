/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_message_pending.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI pending-response presentation.

   Normalizes browser-visible request states and renders the animated
   thinking indicator inside an assistant message. Execution state and
   response authority remain server-owned.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before message pending."
        );
    }

    const { cleanValue } = modules.requireModule(
        "contract"
    );

    const PENDING_MESSAGE_SELECTOR =
        "[data-solomon-ai-pending-message]";
    const MESSAGE_BODY_SELECTOR =
        ".solomon-ai-message__body";
    const PENDING_STATES = new Set([
        "queued",
        "running",
        "reconnecting"
    ]);

    function normalizePendingState(state) {
        const normalizedState = cleanValue(
            state
        ).toLowerCase();

        if (PENDING_STATES.has(normalizedState)) {
            return normalizedState;
        }

        return "starting";
    }

    function getPendingStateLabel(state) {
        const normalizedState =
            normalizePendingState(state);

        if (normalizedState === "queued") {
            return "SolomonAI is waiting to begin.";
        }

        if (normalizedState === "running") {
            return "SolomonAI is working.";
        }

        if (normalizedState === "reconnecting") {
            return "Reconnecting to the SolomonAI request.";
        }

        return "SolomonAI is starting.";
    }

    function createPendingIndicator(state) {
        const normalizedState =
            normalizePendingState(state);
        const indicator = document.createElement(
            "span"
        );
        const visual = document.createElement(
            "span"
        );
        const accessibleLabel =
            document.createElement("span");

        indicator.className =
            "solomon-ai-thinking";
        indicator.setAttribute(
            "data-solomon-ai-thinking-state",
            normalizedState
        );
        indicator.setAttribute(
            "role",
            "status"
        );
        indicator.setAttribute(
            "aria-live",
            "polite"
        );

        visual.className =
            "solomon-ai-thinking__visual";
        visual.setAttribute(
            "aria-hidden",
            "true"
        );

        for (let index = 0; index < 4; index += 1) {
            const segment =
                document.createElement("span");

            segment.className =
                "solomon-ai-thinking__segment";
            visual.append(segment);
        }

        accessibleLabel.className =
            "solomon-ai-thinking__label";
        accessibleLabel.textContent =
            getPendingStateLabel(
                normalizedState
            );

        indicator.append(
            visual,
            accessibleLabel
        );

        return indicator;
    }

    function renderPendingIndicator(body, state) {
        if (!body) {
            return false;
        }

        body.replaceChildren(
            createPendingIndicator(state)
        );

        return true;
    }

    function isPendingMessage(message) {
        return Boolean(
            message?.matches?.(
                PENDING_MESSAGE_SELECTOR
            ) ||
            message?.classList?.contains(
                "solomon-ai-message--pending"
            )
        );
    }

    function getPendingMessageState(message) {
        return normalizePendingState(
            message?.getAttribute(
                "data-solomon-ai-pending-state"
            )
        );
    }

    function markMessagePending(message, state) {
        if (!message) {
            return "";
        }

        const normalizedState =
            normalizePendingState(state);
        const body = message.querySelector(
            MESSAGE_BODY_SELECTOR
        );

        message.classList.add(
            "solomon-ai-message--pending"
        );
        message.setAttribute(
            "data-solomon-ai-pending-message",
            ""
        );
        message.setAttribute(
            "data-solomon-ai-pending-state",
            normalizedState
        );

        renderPendingIndicator(
            body,
            normalizedState
        );

        return normalizedState;
    }

    function clearPendingMessageState(message) {
        if (!message) {
            return false;
        }

        message.classList.remove(
            "solomon-ai-message--pending"
        );
        message.setAttribute(
            "aria-busy",
            "false"
        );
        message.removeAttribute(
            "data-solomon-ai-pending-message"
        );
        message.removeAttribute(
            "data-solomon-ai-pending-state"
        );

        return true;
    }

    function setPendingMessageState(
        pendingMessage,
        state
    ) {
        if (
            !pendingMessage?.isConnected ||
            !isPendingMessage(pendingMessage)
        ) {
            return false;
        }

        const normalizedState =
            normalizePendingState(state);
        const body = pendingMessage.querySelector(
            MESSAGE_BODY_SELECTOR
        );

        pendingMessage.setAttribute(
            "data-solomon-ai-pending-state",
            normalizedState
        );
        renderPendingIndicator(
            body,
            normalizedState
        );

        return true;
    }

    function hydratePendingMessages(elements) {
        const thread = elements?.thread;

        if (!thread) {
            return 0;
        }

        let hydratedCount = 0;

        thread.querySelectorAll(
            PENDING_MESSAGE_SELECTOR
        ).forEach(function (message) {
            const body = message.querySelector(
                MESSAGE_BODY_SELECTOR
            );

            if (
                renderPendingIndicator(
                    body,
                    getPendingMessageState(message)
                )
            ) {
                hydratedCount += 1;
            }
        });

        return hydratedCount;
    }

    function initialize(elements) {
        if (!elements?.thread) {
            return false;
        }

        hydratePendingMessages(elements);
        return true;
    }

    modules.registerModule(
        "message_pending",
        {
            clearPendingMessageState,
            createPendingIndicator,
            getPendingMessageState,
            getPendingStateLabel,
            hydratePendingMessages,
            initialize,
            isPendingMessage,
            markMessagePending,
            normalizePendingState,
            renderPendingIndicator,
            setPendingMessageState
        }
    );
})(window, document);