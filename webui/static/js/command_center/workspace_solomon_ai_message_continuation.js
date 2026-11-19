/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_message_continuation.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI assistant-response continuation presentation.

   Renders server-provided bridge text and suggested follow-up prompts
   beneath an assistant message. JavaScript may normalize duplicate UI
   values, but it does not generate suggestions or own response authority.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before message continuation."
        );
    }

    const { cleanValue } = modules.requireModule(
        "contract"
    );

    const CONTINUATION_SELECTOR =
        "[data-solomon-ai-message-continuation]";
    const BRIDGE_SELECTOR =
        "[data-solomon-ai-message-bridge]";
    const SUGGESTIONS_SELECTOR =
        "[data-solomon-ai-message-suggestions]";

    function normalizeResponseSuggestions(value) {
        if (!Array.isArray(value)) {
            return [];
        }

        const seen = new Set();
        const suggestions = [];

        value.forEach(function (item) {
            const suggestion = cleanValue(item);
            const normalizedSuggestion =
                suggestion.toLowerCase();

            if (
                !suggestion ||
                seen.has(normalizedSuggestion)
            ) {
                return;
            }

            seen.add(normalizedSuggestion);
            suggestions.push(suggestion);
        });

        return suggestions;
    }

    function normalizePresentation(presentation) {
        return {
            bridge: cleanValue(
                presentation?.bridge
            ),
            suggestions:
                normalizeResponseSuggestions(
                    presentation?.suggestions
                )
        };
    }

    function getMessageBody(message) {
        return message?.querySelector(
            ".solomon-ai-message__body"
        ) || null;
    }

    function getMessageContinuation(message) {
        return getMessageBody(
            message
        )?.querySelector(
            CONTINUATION_SELECTOR
        ) || null;
    }

    function removeMessageContinuation(message) {
        const continuation =
            getMessageContinuation(
                message
            );

        if (!continuation) {
            return false;
        }

        continuation.remove();

        return true;
    }

    function createBridgeElement(bridge) {
        const element =
            document.createElement("p");

        element.className =
            "solomon-ai-message__bridge";
        element.setAttribute(
            "data-solomon-ai-message-bridge",
            ""
        );
        element.textContent = bridge;

        return element;
    }

    function createSuggestionButton(
        suggestion
    ) {
        const button =
            document.createElement("button");

        button.type = "button";
        button.className = [
            "solomon-ai-suggestion",
            "solomon-ai-message__suggestion"
        ].join(" ");
        button.setAttribute(
            "data-solomon-ai-response-suggestion",
            ""
        );
        button.setAttribute(
            "data-solomon-ai-prompt",
            suggestion
        );
        button.textContent = suggestion;

        return button;
    }

    function createSuggestionList(
        suggestions
    ) {
        const list =
            document.createElement("div");

        list.className =
            "solomon-ai-message__suggestions";
        list.setAttribute(
            "data-solomon-ai-message-suggestions",
            ""
        );
        list.setAttribute(
            "aria-label",
            "Suggested follow-up prompts"
        );

        suggestions.forEach(
            function (suggestion) {
                list.append(
                    createSuggestionButton(
                        suggestion
                    )
                );
            }
        );

        return list;
    }

    function createMessageContinuation(
        presentation
    ) {
        const normalized =
            normalizePresentation(
                presentation
            );

        if (
            !normalized.bridge &&
            !normalized.suggestions.length
        ) {
            return null;
        }

        const continuation =
            document.createElement(
                "section"
            );

        continuation.className =
            "solomon-ai-message__continuation";
        continuation.setAttribute(
            "data-solomon-ai-message-continuation",
            ""
        );

        if (normalized.bridge) {
            continuation.append(
                createBridgeElement(
                    normalized.bridge
                )
            );
        }

        if (
            normalized.suggestions.length
        ) {
            continuation.append(
                createSuggestionList(
                    normalized.suggestions
                )
            );
        }

        return continuation;
    }

    function renderMessageContinuation(
        message,
        elements,
        presentation
    ) {
        const body = getMessageBody(
            message
        );

        removeMessageContinuation(
            message
        );

        if (!body) {
            return false;
        }

        const continuation =
            createMessageContinuation(
                presentation
            );

        if (!continuation) {
            return false;
        }

        body.append(
            continuation
        );

        return true;
    }

    function getRenderedPresentation(
        message
    ) {
        const continuation =
            getMessageContinuation(
                message
            );

        if (!continuation) {
            return {
                bridge: "",
                suggestions: []
            };
        }

        return {
            bridge: cleanValue(
                continuation.querySelector(
                    BRIDGE_SELECTOR
                )?.textContent
            ),
            suggestions: Array.from(
                continuation.querySelectorAll(
                    `${SUGGESTIONS_SELECTOR} ` +
                    "[data-solomon-ai-prompt]"
                )
            ).map(function (button) {
                return cleanValue(
                    button.getAttribute(
                        "data-solomon-ai-prompt"
                    ) ||
                    button.textContent
                );
            })
        };
    }

    modules.registerModule(
        "message_continuation",
        {
            createBridgeElement,
            createMessageContinuation,
            createSuggestionButton,
            createSuggestionList,
            getMessageContinuation,
            getRenderedPresentation,
            normalizePresentation,
            normalizeResponseSuggestions,
            removeMessageContinuation,
            renderMessageContinuation
        }
    );
})(window, document);