/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_message_timeline.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI message timeline presentation.

   Normalizes persisted message timestamps, inserts date dividers, removes
   legacy per-message time elements, and keeps the conversation positioned
   at the newest message. Durable ordering and timestamps remain server-owned.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before message timeline."
        );
    }

    const {
        cleanValue,
        messageDateFormatter
    } = modules.requireModule("contract");
    const MESSAGE_SELECTOR = "[data-solomon-ai-message]";
    const DIVIDER_SELECTOR = "[data-solomon-ai-date-divider]";
    const TIME_SELECTOR = "[data-solomon-ai-message-time]";

    function normalizeMessageTimestamp(value) {
        const cleanTimestamp = cleanValue(value);

        if (!cleanTimestamp) {
            return "";
        }

        let normalizedTimestamp = cleanTimestamp.replace(" ", "T");

        if (
            /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?$/.test(
                normalizedTimestamp
            )
        ) {
            normalizedTimestamp += "Z";
        }

        return normalizedTimestamp;
    }

    function parseMessageTimestamp(value) {
        const normalizedTimestamp = normalizeMessageTimestamp(value);

        if (!normalizedTimestamp) {
            return null;
        }

        const timestamp = new Date(normalizedTimestamp);

        return Number.isNaN(timestamp.getTime()) ? null : timestamp;
    }

    function getMessageTimestampValue(message) {
        return cleanValue(
            message?.getAttribute("data-solomon-ai-message-created-at") ||
            message?.querySelector(TIME_SELECTOR)?.getAttribute("datetime")
        );
    }

    function getLocalDateKey(timestamp) {
        if (
            !(timestamp instanceof Date) ||
            Number.isNaN(timestamp.getTime())
        ) {
            return "";
        }

        const year = timestamp.getFullYear();
        const month = String(timestamp.getMonth() + 1).padStart(2, "0");
        const day = String(timestamp.getDate()).padStart(2, "0");

        return `${year}-${month}-${day}`;
    }

    function getMessageDateDividerLabel(timestamp, now) {
        const referenceTime = (
            now instanceof Date && !Number.isNaN(now.getTime())
        ) ? now : new Date();
        const messageKey = getLocalDateKey(timestamp);
        const todayKey = getLocalDateKey(referenceTime);
        const yesterday = new Date(
            referenceTime.getFullYear(),
            referenceTime.getMonth(),
            referenceTime.getDate() - 1
        );

        if (messageKey === todayKey) {
            return "Today";
        }

        if (messageKey === getLocalDateKey(yesterday)) {
            return "Yesterday";
        }

        return messageDateFormatter.format(timestamp);
    }

    function ensureMessageDateDivider(message) {
        if (!message?.parentElement) {
            return null;
        }

        let divider = message.previousElementSibling;

        if (divider?.matches(DIVIDER_SELECTOR)) {
            return divider;
        }

        divider = document.createElement("div");
        const label = document.createElement("span");

        divider.className = "solomon-ai-conversation__date-divider";
        divider.setAttribute("data-solomon-ai-date-divider", "");
        divider.setAttribute("aria-hidden", "true");
        divider.hidden = true;
        label.setAttribute("data-solomon-ai-date-divider-label", "");
        divider.append(label);
        message.before(divider);

        return divider;
    }

    function resetMessageTimePresentation(message) {
        message.querySelectorAll(TIME_SELECTOR).forEach(function (element) {
            element.remove();
        });
        message.removeAttribute("data-solomon-ai-message-time-label");
        message.removeAttribute("data-solomon-ai-message-time-state");
        message.removeAttribute("data-solomon-ai-message-time-bound");
        message.style.removeProperty("position");
    }

    function resetDateDividers(thread) {
        thread.querySelectorAll(DIVIDER_SELECTOR).forEach(function (divider) {
            divider.hidden = true;
            divider.setAttribute("aria-hidden", "true");
            divider.removeAttribute("aria-label");
        });
    }

    function showDateDivider(divider, timestamp, now) {
        const dividerLabel = getMessageDateDividerLabel(timestamp, now);
        const label = divider.querySelector(
            "[data-solomon-ai-date-divider-label]"
        );

        if (label) {
            label.textContent = dividerLabel;
        }

        divider.hidden = false;
        divider.setAttribute("aria-hidden", "false");
        divider.setAttribute("aria-label", dividerLabel);
    }

    function hydrateMessageTimeline(elements) {
        const thread = elements?.thread;

        if (!thread) {
            return 0;
        }

        const now = new Date();
        let previousDateKey = "";
        let hydratedCount = 0;

        resetDateDividers(thread);

        thread.querySelectorAll(MESSAGE_SELECTOR).forEach(function (message) {
            const timestampValue = getMessageTimestampValue(message);

            resetMessageTimePresentation(message);

            const timestamp = parseMessageTimestamp(timestampValue);
            const divider = ensureMessageDateDivider(message);

            if (!timestamp) {
                if (divider) {
                    divider.hidden = true;
                    divider.setAttribute("aria-hidden", "true");
                }
                return;
            }

            const isoTimestamp = timestamp.toISOString();
            const dateKey = getLocalDateKey(timestamp);

            message.setAttribute(
                "data-solomon-ai-message-created-at",
                isoTimestamp
            );

            if (divider) {
                divider.setAttribute(
                    "data-solomon-ai-message-created-at",
                    isoTimestamp
                );

                if (dateKey !== previousDateKey) {
                    showDateDivider(divider, timestamp, now);
                }
            }

            previousDateKey = dateKey;
            hydratedCount += 1;
        });

        return hydratedCount;
    }

    function removeWelcome(elements) {
        if (elements?.welcome?.isConnected) {
            elements.welcome.remove();
            elements.welcome = null;
        }

        elements?.thread?.setAttribute(
            "data-solomon-ai-thread-state",
            "active"
        );
    }

    function scrollConversation(elements) {
        if (!elements?.scroll) {
            return false;
        }

        window.requestAnimationFrame(function () {
            if (elements.scroll?.isConnected) {
                elements.scroll.scrollTop = elements.scroll.scrollHeight;
            }
        });
        return true;
    }

    function restoreConversationPosition(elements) {
        if (
            !elements?.scroll ||
            !elements?.thread?.querySelector(MESSAGE_SELECTOR)
        ) {
            return false;
        }

        window.requestAnimationFrame(function () {
            window.requestAnimationFrame(function () {
                if (elements.scroll?.isConnected) {
                    elements.scroll.scrollTop = elements.scroll.scrollHeight;
                }
            });
        });

        window.setTimeout(function () {
            if (elements.scroll?.isConnected) {
                elements.scroll.scrollTop = elements.scroll.scrollHeight;
            }
        }, 80);
        return true;
    }

    function initialize(elements) {
        if (!elements?.thread) {
            return false;
        }

        hydrateMessageTimeline(elements);
        restoreConversationPosition(elements);
        return true;
    }

    modules.registerModule("message_timeline", {
        ensureMessageDateDivider,
        getLocalDateKey,
        getMessageDateDividerLabel,
        getMessageTimestampValue,
        hydrateMessageTimeline,
        initialize,
        normalizeMessageTimestamp,
        parseMessageTimestamp,
        removeWelcome,
        resetDateDividers,
        resetMessageTimePresentation,
        restoreConversationPosition,
        scrollConversation,
        showDateDivider
    });
})(window, document);