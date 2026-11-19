/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_message_content.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI persisted message-content access.

   Reads and writes browser presentation metadata already supplied by
   the server, recovers source text from existing message DOM, and finds
   adjacent conversation prompts for message actions. JavaScript does
   not create authoritative conversation content.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before message content."
        );
    }

    const { cleanValue } = modules.requireModule(
        "contract"
    );

    const MESSAGE_SELECTOR =
        "[data-solomon-ai-message]";
    const MESSAGE_BODY_SELECTOR =
        ".solomon-ai-message__body";
    const CONTINUATION_SELECTOR =
        "[data-solomon-ai-message-continuation]";
    const PERSISTED_CONTENT_ATTRIBUTE =
        "data-solomon-ai-persisted-content";

    function getMessageBody(message) {
        return message?.querySelector(
            MESSAGE_BODY_SELECTOR
        ) || null;
    }

    function getMessageRole(message) {
        return cleanValue(
            message?.getAttribute(
                "data-solomon-ai-message-role"
            )
        ).toLowerCase();
    }

    function getPersistedMessageContent(body) {
        if (!body) {
            return "";
        }

        const serializedContent = body.getAttribute(
            PERSISTED_CONTENT_ATTRIBUTE
        );

        if (!serializedContent) {
            return "";
        }

        try {
            const parsedContent = JSON.parse(
                serializedContent
            );

            if (typeof parsedContent === "string") {
                return parsedContent;
            }

            return String(
                parsedContent || ""
            );
        } catch (error) {
            return serializedContent;
        }
    }

    function setPersistedMessageContent(
        body,
        content
    ) {
        if (!body) {
            return false;
        }

        body.setAttribute(
            PERSISTED_CONTENT_ATTRIBUTE,
            JSON.stringify(
                String(content || "")
            )
        );

        return true;
    }

    function clearPersistedMessageContent(body) {
        if (!body) {
            return false;
        }

        body.removeAttribute(
            PERSISTED_CONTENT_ATTRIBUTE
        );

        return true;
    }

    function isPresentationOnlyChild(child) {
        return Boolean(
            child?.matches?.(
                ".solomon-ai-thinking"
            ) ||
            child?.matches?.(
                CONTINUATION_SELECTOR
            )
        );
    }

    function getExistingMessageBodySource(body) {
        if (!body) {
            return "";
        }

        const persistedContent =
            getPersistedMessageContent(
                body
            );

        if (cleanValue(persistedContent)) {
            return persistedContent;
        }

        const blocks = Array.from(
            body.children
        )
            .filter(function (child) {
                return !isPresentationOnlyChild(
                    child
                );
            })
            .map(function (child) {
                return cleanValue(
                    child.textContent
                );
            })
            .filter(Boolean);

        if (blocks.length) {
            return blocks.join("\n\n");
        }

        return cleanValue(
            body.textContent
        );
    }

    function getExistingMessagePresentation(body) {
        if (!body) {
            return {
                bridge: "",
                suggestions: []
            };
        }

        const bridge = cleanValue(
            body.querySelector(
                "[data-solomon-ai-message-bridge]"
            )?.textContent
        );
        const suggestions = Array.from(
            body.querySelectorAll(
                "[data-solomon-ai-message-suggestions] " +
                "[data-solomon-ai-prompt]"
            )
        ).map(function (button) {
            return cleanValue(
                button.getAttribute(
                    "data-solomon-ai-prompt"
                ) ||
                button.textContent
            );
        });

        return {
            bridge,
            suggestions
        };
    }

    function getMessageText(message) {
        return getExistingMessageBodySource(
            getMessageBody(message)
        );
    }

    function getAssistantMessageText(message) {
        return getMessageText(message);
    }

    function findPreviousMessageByRole(
        message,
        role
    ) {
        const expectedRole = cleanValue(
            role
        ).toLowerCase();
        let candidate =
            message?.previousElementSibling ||
            null;

        while (candidate) {
            if (
                candidate.matches?.(
                    MESSAGE_SELECTOR
                ) &&
                getMessageRole(candidate) ===
                    expectedRole
            ) {
                return candidate;
            }

            candidate =
                candidate.previousElementSibling;
        }

        return null;
    }

    function getPreviousUserMessageText(message) {
        return getMessageText(
            findPreviousMessageByRole(
                message,
                "user"
            )
        );
    }

    function getMessageIdentity(message) {
        return {
            messageId: cleanValue(
                message?.getAttribute(
                    "data-solomon-ai-message-id"
                )
            ),
            requestId: cleanValue(
                message?.getAttribute(
                    "data-solomon-ai-request-id"
                )
            ),
            role: getMessageRole(message)
        };
    }

    modules.registerModule(
        "message_content",
        {
            clearPersistedMessageContent,
            findPreviousMessageByRole,
            getAssistantMessageText,
            getExistingMessageBodySource,
            getExistingMessagePresentation,
            getMessageBody,
            getMessageIdentity,
            getMessageRole,
            getMessageText,
            getPersistedMessageContent,
            getPreviousUserMessageText,
            isPresentationOnlyChild,
            setPersistedMessageContent
        }
    );
})(window);