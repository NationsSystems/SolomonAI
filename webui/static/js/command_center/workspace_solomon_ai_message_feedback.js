/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_message_feedback.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI response-feedback transport.

   Persists Helpful and Not helpful selections for a saved assistant
   response. The browser submits durable message identifiers supplied by
   the server; feedback ownership and validation remain server-authoritative.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before message feedback."
        );
    }

    const contract = modules.requireModule("contract");
    const navigation = modules.requireModule(
        "conversation_navigation"
    );
    const content = modules.requireModule(
        "message_content"
    );
    const messageActions = modules.requireModule(
        "message_actions"
    );
    const {
        constants,
        cleanValue,
        readJsonResponse
    } = contract;

    const VALID_FEEDBACK_VALUES = new Set([
        "helpful",
        "not_helpful"
    ]);

    function getFeedbackEndpoint() {
        return cleanValue(
            constants.FEEDBACK_ENDPOINT
        ) || "/api/task/feedback";
    }

    function getFeedbackButtons(actionRow) {
        return Array.from(
            actionRow?.querySelectorAll(
                "[data-solomon-ai-feedback-value]"
            ) || []
        );
    }

    function setFeedbackButtonsDisabled(
        actionRow,
        disabled
    ) {
        getFeedbackButtons(actionRow).forEach(
            function (button) {
                button.disabled = disabled === true;
            }
        );
    }

    function setFeedbackSelection(
        actionRow,
        selectedValue
    ) {
        const cleanSelectedValue = cleanValue(
            selectedValue
        ).toLowerCase();

        getFeedbackButtons(actionRow).forEach(
            function (button) {
                const value = cleanValue(
                    button.getAttribute(
                        "data-solomon-ai-feedback-value"
                    )
                ).toLowerCase();
                const selected = (
                    value === cleanSelectedValue
                );

                button.classList.toggle(
                    "is-active",
                    selected
                );
                button.setAttribute(
                    "aria-pressed",
                    selected ? "true" : "false"
                );
            }
        );
    }

    function getFeedbackIdentity(
        message,
        elements
    ) {
        const identity = content.getMessageIdentity(
            message
        );

        return {
            conversationId:
                navigation.getConversationId(
                    elements
                ),
            messageId: cleanValue(
                identity.messageId
            ),
            requestId: cleanValue(
                identity.requestId
            )
        };
    }

    function canSubmitFeedback(
        identity,
        feedbackValue
    ) {
        return Boolean(
            identity?.conversationId &&
            VALID_FEEDBACK_VALUES.has(
                feedbackValue
            ) &&
            (
                identity.messageId ||
                identity.requestId
            )
        );
    }

    function buildFeedbackPayload(
        identity,
        feedbackValue
    ) {
        return {
            conversation_id:
                identity.conversationId,
            message_id:
                identity.messageId,
            request_id:
                identity.requestId,
            feedback:
                feedbackValue
        };
    }

    async function requestFeedback(payload) {
        const response = await fetch(
            getFeedbackEndpoint(),
            {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify(payload)
            }
        );
        const packet = await readJsonResponse(
            response
        );

        if (
            !response.ok ||
            packet?.ok === false
        ) {
            throw new Error(
                cleanValue(
                    packet?.user_output ||
                    packet?.error
                ) ||
                "Feedback could not be saved."
            );
        }

        return packet;
    }

    function getSavedFeedbackStatus(
        feedbackValue
    ) {
        return feedbackValue === "helpful"
            ? "Marked as helpful."
            : "Marked as not helpful.";
    }

    async function submitMessageFeedback(
        message,
        elements,
        actionRow,
        feedbackValue
    ) {
        const cleanFeedbackValue = cleanValue(
            feedbackValue
        ).toLowerCase();
        const identity = getFeedbackIdentity(
            message,
            elements
        );

        if (
            !canSubmitFeedback(
                identity,
                cleanFeedbackValue
            )
        ) {
            messageActions.setMessageActionStatus(
                actionRow,
                "Feedback is available after the response is saved."
            );
            return false;
        }

        setFeedbackButtonsDisabled(
            actionRow,
            true
        );
        messageActions.setMessageActionStatus(
            actionRow,
            "Saving feedback."
        );

        try {
            await requestFeedback(
                buildFeedbackPayload(
                    identity,
                    cleanFeedbackValue
                )
            );

            setFeedbackSelection(
                actionRow,
                cleanFeedbackValue
            );
            messageActions.setMessageActionStatus(
                actionRow,
                getSavedFeedbackStatus(
                    cleanFeedbackValue
                )
            );

            return true;
        } catch (error) {
            messageActions.setMessageActionStatus(
                actionRow,
                cleanValue(error?.message) ||
                "Feedback could not be saved."
            );

            return false;
        } finally {
            setFeedbackButtonsDisabled(
                actionRow,
                false
            );
        }
    }

    modules.registerModule(
        "message_feedback",
        {
            buildFeedbackPayload,
            canSubmitFeedback,
            getFeedbackButtons,
            getFeedbackEndpoint,
            getFeedbackIdentity,
            getSavedFeedbackStatus,
            requestFeedback,
            setFeedbackButtonsDisabled,
            setFeedbackSelection,
            submitMessageFeedback
        }
    );
})(window);