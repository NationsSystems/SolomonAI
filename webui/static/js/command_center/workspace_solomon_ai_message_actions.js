/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_message_actions.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI completed-response action controls.

   Renders Copy, Helpful, Not helpful, and Retry controls for completed
   assistant messages. Feedback persistence is delegated to the focused
   feedback module; browser controls do not determine server authority.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before message actions."
        );
    }

    const contract = modules.requireModule("contract");
    const content = modules.requireModule("message_content");
    const composerState = modules.requireModule("composer_state");
    const composerLayout = modules.requireModule("composer_layout");
    const {
        constants,
        cleanValue
    } = contract;

    function setMessageActionStatus(actionRow, message) {
        const status = actionRow?.querySelector(
            "[data-solomon-ai-message-action-status]"
        );

        if (status) {
            status.textContent = cleanValue(message);
        }
    }

    function setMessageActionIcon(button, iconName) {
        const icon = button?.querySelector(".icon");

        if (icon) {
            icon.textContent = cleanValue(iconName);
        }
    }

    function createMessageActionButton(
        action,
        iconName,
        label
    ) {
        const button = document.createElement("button");
        const icon = document.createElement("span");

        button.type = "button";
        button.className = "solomon-ai-message__action";
        button.setAttribute(
            "data-solomon-ai-message-action",
            action
        );
        button.setAttribute(
            "aria-label",
            label
        );
        button.title = label;

        icon.className = "icon";
        icon.setAttribute(
            "aria-hidden",
            "true"
        );
        icon.textContent = iconName;
        button.append(icon);

        return button;
    }

    async function copyMessageText(text) {
        const cleanText = cleanValue(
            text
        );

        if (!cleanText) {
            return false;
        }

        if (
            typeof navigator.clipboard?.writeText ===
            "function"
        ) {
            try {
                await navigator.clipboard.writeText(
                    cleanText
                );
                return true;
            } catch (error) {
                // Continue to the legacy browser copy path.
            }
        }

        const copyBuffer = document.createElement(
            "textarea"
        );

        copyBuffer.value = cleanText;
        copyBuffer.setAttribute(
            "readonly",
            ""
        );
        copyBuffer.setAttribute(
            "aria-hidden",
            "true"
        );
        copyBuffer.className = (
            "solomon-ai-clipboard-buffer"
        );
        document.body.append(
            copyBuffer
        );
        copyBuffer.select();
        copyBuffer.setSelectionRange(
            0,
            copyBuffer.value.length
        );

        let copied = false;

        try {
            copied = document.execCommand(
                "copy"
            );
        } catch (error) {
            copied = false;
        } finally {
            copyBuffer.remove();
        }

        return copied;
    }

    function bindCopyAction(
        button,
        message,
        actionRow
    ) {
        button.addEventListener(
            "click",
            async function () {
                const copied = await copyMessageText(
                    content.getAssistantMessageText(
                        message
                    )
                );

                if (!copied) {
                    setMessageActionStatus(
                        actionRow,
                        "The response could not be copied."
                    );
                    return;
                }

                button.classList.add(
                    "is-confirmed"
                );
                setMessageActionIcon(
                    button,
                    "check"
                );
                button.setAttribute(
                    "aria-label",
                    "Response copied"
                );
                button.title = "Copied";
                setMessageActionStatus(
                    actionRow,
                    "Response copied."
                );

                window.setTimeout(
                    function () {
                        if (!button.isConnected) {
                            return;
                        }

                        button.classList.remove(
                            "is-confirmed"
                        );
                        setMessageActionIcon(
                            button,
                            "content_copy"
                        );
                        button.setAttribute(
                            "aria-label",
                            "Copy response"
                        );
                        button.title = "Copy response";
                    },
                    constants.MESSAGE_ACTION_COPY_RESET_MS
                );
            }
        );
    }

    function retryAssistantMessage(
        message,
        elements,
        actionRow
    ) {
        const userPrompt = (
            content.getPreviousUserMessageText(
                message
            )
        );

        if (
            !userPrompt ||
            !elements?.input ||
            !elements?.composer ||
            elements.input.disabled ||
            composerState.isPending(
                elements
            )
        ) {
            setMessageActionStatus(
                actionRow,
                "The previous prompt is not available to retry."
            );
            return false;
        }

        elements.input.value = userPrompt;

        composerLayout.resizeInput(
            elements.input,
            elements
        );

        setMessageActionStatus(
            actionRow,
            "Retrying the previous prompt."
        );

        elements.composer.requestSubmit();

        return true;
    }

    function bindFeedbackAction(
        button,
        message,
        elements,
        actionRow,
        feedbackValue
    ) {
        button.addEventListener(
            "click",
            function () {
                modules.requireModule(
                    "message_feedback"
                ).submitMessageFeedback(
                    message,
                    elements,
                    actionRow,
                    feedbackValue
                );
            }
        );
    }

    function createActionRow(
        message,
        elements
    ) {
        const actionRow = document.createElement(
            "div"
        );
        const copyButton = createMessageActionButton(
            "copy",
            "content_copy",
            "Copy response"
        );
        const helpfulButton = createMessageActionButton(
            "helpful",
            "thumb_up",
            "Mark response as helpful"
        );
        const notHelpfulButton = (
            createMessageActionButton(
                "not_helpful",
                "thumb_down",
                "Mark response as not helpful"
            )
        );
        const retryButton = createMessageActionButton(
            "retry",
            "refresh",
            "Retry response"
        );
        const status = document.createElement(
            "span"
        );

        actionRow.className = (
            "solomon-ai-message__actions"
        );
        actionRow.setAttribute(
            "data-solomon-ai-message-actions",
            ""
        );
        actionRow.setAttribute(
            "aria-label",
            "Response actions"
        );

        helpfulButton.setAttribute(
            "data-solomon-ai-feedback-value",
            "helpful"
        );
        helpfulButton.setAttribute(
            "aria-pressed",
            "false"
        );
        notHelpfulButton.setAttribute(
            "data-solomon-ai-feedback-value",
            "not_helpful"
        );
        notHelpfulButton.setAttribute(
            "aria-pressed",
            "false"
        );

        status.className = "visually-hidden";
        status.setAttribute(
            "data-solomon-ai-message-action-status",
            ""
        );
        status.setAttribute(
            "role",
            "status"
        );
        status.setAttribute(
            "aria-live",
            "polite"
        );

        bindCopyAction(
            copyButton,
            message,
            actionRow
        );
        bindFeedbackAction(
            helpfulButton,
            message,
            elements,
            actionRow,
            "helpful"
        );
        bindFeedbackAction(
            notHelpfulButton,
            message,
            elements,
            actionRow,
            "not_helpful"
        );

        retryButton.addEventListener(
            "click",
            function () {
                retryAssistantMessage(
                    message,
                    elements,
                    actionRow
                );
            }
        );

        actionRow.append(
            copyButton,
            helpfulButton,
            notHelpfulButton,
            retryButton,
            status
        );

        return actionRow;
    }

    function renderMessageActions(
        message,
        elements
    ) {
        if (
            !message ||
            !elements ||
            content.getMessageRole(
                message
            ) !== "assistant" ||
            message.classList.contains(
                "solomon-ai-message--pending"
            ) ||
            message.classList.contains(
                "solomon-ai-message--error"
            )
        ) {
            message?.querySelector(
                "[data-solomon-ai-message-actions]"
            )?.remove();

            return false;
        }

        if (
            !cleanValue(
                content.getAssistantMessageText(
                    message
                )
            )
        ) {
            return false;
        }

        message.querySelector(
            "[data-solomon-ai-message-actions]"
        )?.remove();

        message.append(
            createActionRow(
                message,
                elements
            )
        );

        return true;
    }

    modules.registerModule(
        "message_actions",
        {
            bindCopyAction,
            bindFeedbackAction,
            copyMessageText,
            createActionRow,
            createMessageActionButton,
            renderMessageActions,
            retryAssistantMessage,
            setMessageActionIcon,
            setMessageActionStatus
        }
    );
})(window, document);