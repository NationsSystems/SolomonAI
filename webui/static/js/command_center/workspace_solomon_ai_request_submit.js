/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_request_submit.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   Orchestrates browser submission, governed progressive response reveal,
   and final packet presentation. Server execution and persistence remain
   authoritative.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before request submission."
        );
    }

    const { cleanValue } = modules.requireModule("contract");
    const requestPayload = modules.requireModule("request_payload");
    const composerState = modules.requireModule("composer_state");
    const messageRenderer = modules.requireModule("message_renderer");
    const messagePending = modules.requireModule("message_pending");
    const executionTransport = modules.requireModule("execution_transport");
    const responsePacket = modules.requireModule("response_packet");

    const AUTOMATIC_CONVERSATION_TITLES = new Set([
        "Untitled chat",
        "New conversation"
    ]);
    const AUTOMATIC_TITLE_MAX_LENGTH = 64;
    const PROGRESSIVE_REVEAL_MINIMUM_LENGTH = 40;
    const PROGRESSIVE_REVEAL_MINIMUM_DURATION = 420;
    const PROGRESSIVE_REVEAL_MAXIMUM_DURATION = 1200;
    const PROGRESSIVE_REVEAL_TARGET_CHARACTERS = 24;
    const PROGRESSIVE_REVEAL_MINIMUM_FRAMES = 8;
    const PROGRESSIVE_REVEAL_MAXIMUM_FRAMES = 42;
    const DOCINTEL_SUMMARY_STREAM_STAGE =
        "docintel_summary_stream";
    const REDUCED_MOTION_QUERY =
        "(prefers-reduced-motion: reduce)";
    const HISTORY_ROW_SELECTOR =
        "[data-solomon-ai-history-row]";
    const HISTORY_ITEM_SELECTOR =
        "[data-solomon-ai-history-item]";
    const HISTORY_TITLE_SELECTOR =
        "[data-solomon-ai-history-item-title]";
    const HISTORY_OPTIONS_SELECTOR =
        "[data-solomon-ai-history-options]";
    const HISTORY_MENU_SELECTOR =
        "[data-solomon-ai-history-menu]";
    const HISTORY_EDITOR_SELECTOR =
        "[data-solomon-ai-history-rename-editor]";
    const HISTORY_INPUT_SELECTOR =
        "[data-solomon-ai-history-rename-input]";

    function createSubmissionState() {
        return {
            answerRendered: false,
            streamedAnswer: "",
            incrementalAnswerActive: false,
            lastStreamSequence: 0,
            finalPacketRendered: false,
            submissionFailed: false,
            titlePreview: null,
            progressiveReveal: null,
            progressiveRevealComplete: false,
            progressiveRevealGeneration: 0,
            pendingFinalPacket: null,
            pendingFinalStatus: 0
        };
    }

    function normalizeTitleText(value) {
        return String(value || "")
            .replace(/\s+/g, " ")
            .trim();
    }

    function buildAutomaticConversationTitle(message) {
        const cleanMessage = normalizeTitleText(message);

        if (!cleanMessage) {
            return "Untitled chat";
        }

        if (
            cleanMessage.length <=
            AUTOMATIC_TITLE_MAX_LENGTH
        ) {
            return cleanMessage;
        }

        let candidate = cleanMessage.slice(
            0,
            AUTOMATIC_TITLE_MAX_LENGTH
        );
        const wordBoundary = candidate.lastIndexOf(" ");

        if (
            wordBoundary >=
            AUTOMATIC_TITLE_MAX_LENGTH / 2
        ) {
            candidate = candidate.slice(
                0,
                wordBoundary
            );
        }

        const shortened = candidate.replace(
            /[ ,.;:!?-]+$/,
            ""
        );

        return shortened
            ? `${shortened}…`
            : "Untitled chat";
    }

    function getActiveHistoryRow(elements) {
        const workspace = elements?.workspace;

        if (!workspace) {
            return null;
        }

        const activeRow = workspace.querySelector(
            `${HISTORY_ROW_SELECTOR}.is-active`
        );

        if (activeRow) {
            return activeRow;
        }

        const conversationId = cleanValue(
            workspace.getAttribute(
                "data-solomon-ai-conversation-id"
            )
        );

        if (!conversationId) {
            return null;
        }

        return Array.from(
            workspace.querySelectorAll(
                HISTORY_ROW_SELECTOR
            )
        ).find(function (row) {
            return cleanValue(
                row.getAttribute(
                    "data-conversation-id"
                )
            ) === conversationId;
        }) || null;
    }

    function getHistoryRowTitle(row) {
        return normalizeTitleText(
            row?.getAttribute(
                "data-conversation-title"
            ) ||
            row?.querySelector(
                HISTORY_TITLE_SELECTOR
            )?.textContent
        );
    }

    function setHistoryRowTitle(row, title) {
        const cleanTitle = normalizeTitleText(title);

        if (!row || !cleanTitle) {
            return false;
        }

        const item = row.querySelector(
            HISTORY_ITEM_SELECTOR
        );
        const options = row.querySelector(
            HISTORY_OPTIONS_SELECTOR
        );
        const menu = row.querySelector(
            HISTORY_MENU_SELECTOR
        );
        const editor = row.querySelector(
            HISTORY_EDITOR_SELECTOR
        );
        const input = row.querySelector(
            HISTORY_INPUT_SELECTOR
        );
        const titleElement = row.querySelector(
            HISTORY_TITLE_SELECTOR
        );

        row.setAttribute(
            "data-conversation-title",
            cleanTitle
        );

        if (item) {
            item.setAttribute(
                "data-conversation-title",
                cleanTitle
            );
            item.setAttribute(
                "title",
                cleanTitle
            );
            item.setAttribute(
                "aria-label",
                `Open ${cleanTitle}`
            );
        }

        options?.setAttribute(
            "aria-label",
            `More options for ${cleanTitle}`
        );
        menu?.setAttribute(
            "aria-label",
            `Options for ${cleanTitle}`
        );

        if (editor) {
            editor.setAttribute(
                "data-conversation-title",
                cleanTitle
            );
            editor.setAttribute(
                "aria-label",
                `Rename ${cleanTitle}`
            );
        }

        if (input) {
            input.value = cleanTitle;
        }

        if (titleElement) {
            titleElement.textContent = cleanTitle;
        }

        return true;
    }

    function applyConversationTitlePreview(
        elements,
        message
    ) {
        const row = getActiveHistoryRow(elements);
        const previousTitle = getHistoryRowTitle(row);
        const messageCount = Number(
            elements?.workspace?.getAttribute(
                "data-solomon-ai-message-count"
            ) || 0
        );

        if (
            !row ||
            messageCount !== 0 ||
            !AUTOMATIC_CONVERSATION_TITLES.has(
                previousTitle
            )
        ) {
            return null;
        }

        const proposedTitle =
            buildAutomaticConversationTitle(
                message
            );

        if (
            !proposedTitle ||
            proposedTitle === previousTitle ||
            !setHistoryRowTitle(
                row,
                proposedTitle
            )
        ) {
            return null;
        }

        return {
            row,
            previousTitle,
            proposedTitle
        };
    }

    function restoreConversationTitlePreview(
        titlePreview
    ) {
        if (
            !titlePreview?.row ||
            !window.document.contains(
                titlePreview.row
            ) ||
            getHistoryRowTitle(
                titlePreview.row
            ) !== titlePreview.proposedTitle
        ) {
            return false;
        }

        return setHistoryRowTitle(
            titlePreview.row,
            titlePreview.previousTitle
        );
    }

    function getAnswerStageText(answerStage) {
        const answerValue = answerStage?.answer;

        return typeof answerValue === "string"
            ? answerValue
            : String(answerValue || "");
    }

    function getAnswerStageSequence(answerStage) {
        const sequence = Number.parseInt(
            answerStage?.sequence,
            10
        );

        return (
            Number.isInteger(sequence) &&
            sequence > 0
        )
            ? sequence
            : 0;
    }

    function isCumulativeDocIntelSummaryStage(
        answerStage
    ) {
        return Boolean(
            cleanValue(answerStage?.stage) ===
                DOCINTEL_SUMMARY_STREAM_STAGE &&
            cleanValue(answerStage?.mode).toLowerCase() ===
                "cumulative"
        );
    }

    function userPrefersReducedMotion() {
        return Boolean(
            typeof window.matchMedia === "function" &&
            window.matchMedia(
                REDUCED_MOTION_QUERY
            ).matches
        );
    }

    function shouldUseProgressiveReveal(answer) {
        const text = String(answer || "");

        return Boolean(
            text.length >=
                PROGRESSIVE_REVEAL_MINIMUM_LENGTH &&
            !document.hidden &&
            !userPrefersReducedMotion()
        );
    }

    function isWhitespaceUnit(value) {
        return /^\s+$/.test(
            String(value || "")
        );
    }

    function buildProgressiveSegments(answer) {
        const text = String(answer || "");

        if (!text) {
            return [];
        }

        const units = text.match(
            /\s+|[^\s]+/g
        ) || [text];
        const wordCount = units.reduce(
            function (count, unit) {
                return count + (
                    isWhitespaceUnit(unit)
                        ? 0
                        : 1
                );
            },
            0
        );
        const targetFrameCount = Math.min(
            PROGRESSIVE_REVEAL_MAXIMUM_FRAMES,
            Math.max(
                PROGRESSIVE_REVEAL_MINIMUM_FRAMES,
                Math.ceil(
                    text.length /
                    PROGRESSIVE_REVEAL_TARGET_CHARACTERS
                )
            )
        );
        const wordsPerSegment = Math.max(
            1,
            Math.ceil(
                wordCount /
                targetFrameCount
            )
        );
        const segments = [];
        let segment = "";
        let segmentWordCount = 0;

        units.forEach(function (unit, index) {
            const whitespace = isWhitespaceUnit(
                unit
            );
            const finalUnit =
                index === units.length - 1;

            segment += unit;

            if (!whitespace) {
                segmentWordCount += 1;
            }

            const lineBoundary = Boolean(
                whitespace &&
                unit.includes("\n")
            );
            const wordBoundary = Boolean(
                whitespace &&
                segmentWordCount >= wordsPerSegment
            );

            if (
                finalUnit ||
                lineBoundary ||
                wordBoundary
            ) {
                if (segment) {
                    segments.push(segment);
                }

                segment = "";
                segmentWordCount = 0;
            }
        });

        if (segment) {
            segments.push(segment);
        }

        return segments;
    }

    function getProgressiveSegmentWeight(segment) {
        const text = String(segment || "");

        if (/\n\s*\n\s*$/.test(text)) {
            return 1.9;
        }

        if (
            /[.!?]["')\]]?\s*$/.test(text)
        ) {
            return 1.65;
        }

        if (
            /[,;:]["')\]]?\s*$/.test(text)
        ) {
            return 1.25;
        }

        if (/\n\s*$/.test(text)) {
            return 1.4;
        }

        return 1;
    }

    function getProgressiveRevealDuration(answer) {
        const textLength = String(
            answer || ""
        ).length;

        return Math.min(
            PROGRESSIVE_REVEAL_MAXIMUM_DURATION,
            Math.max(
                PROGRESSIVE_REVEAL_MINIMUM_DURATION,
                320 + (
                    textLength * 1.3
                )
            )
        );
    }

    function waitForProgressiveDelay(delay) {
        return new Promise(function (resolve) {
            window.setTimeout(
                resolve,
                Math.max(
                    0,
                    Math.round(delay)
                )
            );
        });
    }

    function cancelProgressiveReveal(state) {
        if (!state) {
            return false;
        }

        state.progressiveRevealGeneration += 1;
        state.progressiveReveal = null;
        state.progressiveRevealComplete = true;

        return true;
    }

    function isProgressiveRevealPending(state) {
        return Boolean(
            state?.progressiveReveal &&
            state.progressiveRevealComplete !== true
        );
    }

    async function revealPendingAnswer(
        answer,
        elements,
        pendingMessage,
        state,
        generation
    ) {
        if (
            generation !==
            state.progressiveRevealGeneration
        ) {
            return false;
        }

        if (!shouldUseProgressiveReveal(answer)) {
            return messageRenderer.updatePendingMessageText(
                elements,
                pendingMessage,
                answer
            );
        }

        const segments = buildProgressiveSegments(
            answer
        );

        if (segments.length <= 1) {
            return messageRenderer.updatePendingMessageText(
                elements,
                pendingMessage,
                answer
            );
        }

        const weights = segments.map(
            getProgressiveSegmentWeight
        );
        const totalWeight = weights.reduce(
            function (total, weight) {
                return total + weight;
            },
            0
        ) || 1;
        const baseDelay =
            getProgressiveRevealDuration(answer) /
            totalWeight;
        let visibleText = "";

        for (
            let index = 0;
            index < segments.length;
            index += 1
        ) {
            if (
                generation !==
                state.progressiveRevealGeneration
            ) {
                return false;
            }

            visibleText += segments[index];

            if (
                !messageRenderer.updatePendingMessageText(
                    elements,
                    pendingMessage,
                    visibleText
                )
            ) {
                return false;
            }

            if (index < segments.length - 1) {
                await waitForProgressiveDelay(
                    baseDelay * weights[index]
                );
            }
        }

        return (
            generation ===
            state.progressiveRevealGeneration
        );
    }

    function beginProgressiveReveal(
        answer,
        elements,
        pendingMessage,
        state
    ) {
        const generation =
            state.progressiveRevealGeneration + 1;

        state.progressiveRevealGeneration =
            generation;
        state.progressiveRevealComplete = false;

        state.progressiveReveal = revealPendingAnswer(
            answer,
            elements,
            pendingMessage,
            state,
            generation
        ).then(function (completed) {
            if (
                generation !==
                state.progressiveRevealGeneration
            ) {
                return false;
            }

            state.progressiveRevealComplete = true;
            state.answerRendered =
                completed === true;

            return completed;
        }).catch(function () {
            if (
                generation !==
                state.progressiveRevealGeneration
            ) {
                return false;
            }

            const completed =
                messageRenderer.updatePendingMessageText(
                    elements,
                    pendingMessage,
                    answer
                );

            state.progressiveRevealComplete = true;
            state.answerRendered = completed;

            return completed;
        });

        return state.progressiveReveal;
    }

    async function waitForProgressiveReveal(state) {
        if (!state?.progressiveReveal) {
            return false;
        }

        try {
            return await state.progressiveReveal;
        } catch (error) {
            return false;
        }
    }

    function renderFinalPacket(
        elements,
        pendingMessage,
        packet,
        statusCode,
        state
    ) {
        cancelProgressiveReveal(
            state
        );
        state.pendingFinalPacket = null;
        state.pendingFinalStatus = 0;

        const normalized = responsePacket.normalizeResponsePacket(
            packet,
            statusCode
        );
        const identity = normalized.identity;

        if (normalized.failed) {
            messageRenderer.replacePendingMessage(
                elements,
                pendingMessage,
                normalized.text || responsePacket.extractResponseError(
                    normalized.packet,
                    normalized.status
                ),
                {
                    error: true,
                    messageId: identity.messageId,
                    requestId: identity.requestId
                }
            );
            state.finalPacketRendered = true;
            state.submissionFailed = true;
            return false;
        }

        const displayText = responsePacket.getResponseDisplayText(
            normalized.packet,
            state.streamedAnswer
        );

        messageRenderer.replacePendingMessage(
            elements,
            pendingMessage,
            displayText,
            {
                presentation: normalized.presentation,
                messageId: identity.messageId,
                requestId: identity.requestId,
                actions: true
            }
        );
        state.streamedAnswer = displayText;
        state.answerRendered = true;
        state.finalPacketRendered = true;
        return true;
    }

    function handleCumulativeStreamAnswer(
        answerStage,
        elements,
        pendingMessage,
        state
    ) {
        const answer = getAnswerStageText(
            answerStage
        );
        const sequence = getAnswerStageSequence(
            answerStage
        );

        if (
            !cleanValue(answer) ||
            state.finalPacketRendered ||
            (
                sequence > 0 &&
                sequence <= state.lastStreamSequence
            )
        ) {
            return false;
        }

        if (isProgressiveRevealPending(state)) {
            cancelProgressiveReveal(
                state
            );
        }

        const updated =
            messageRenderer.updatePendingMessageText(
                elements,
                pendingMessage,
                answer
            );

        if (!updated) {
            return false;
        }

        state.streamedAnswer = answer;
        state.incrementalAnswerActive = true;
        state.answerRendered = true;

        if (sequence > 0) {
            state.lastStreamSequence = sequence;
        }

        return true;
    }

    function handleStreamAnswer(
        answerStage,
        elements,
        pendingMessage,
        state
    ) {
        if (
            isCumulativeDocIntelSummaryStage(
                answerStage
            )
        ) {
            return handleCumulativeStreamAnswer(
                answerStage,
                elements,
                pendingMessage,
                state
            );
        }

        const answer = getAnswerStageText(
            answerStage
        );

        if (
            !cleanValue(answer) ||
            state.finalPacketRendered
        ) {
            return false;
        }

        if (state.incrementalAnswerActive) {
            if (answer === state.streamedAnswer) {
                return true;
            }

            const updated =
                messageRenderer.updatePendingMessageText(
                    elements,
                    pendingMessage,
                    answer
                );

            if (!updated) {
                return false;
            }

            state.streamedAnswer = answer;
            state.answerRendered = true;
            return true;
        }

        if (
            state.answerRendered ||
            isProgressiveRevealPending(state)
        ) {
            return false;
        }

        state.streamedAnswer = answer;

        beginProgressiveReveal(
            answer,
            elements,
            pendingMessage,
            state
        );

        return true;
    }

    function handleStreamPacket(
        packet,
        statusCode,
        elements,
        pendingMessage,
        state
    ) {
        const normalized =
            responsePacket.normalizeResponsePacket(
                packet,
                statusCode
            );

        if (normalized.failed) {
            cancelProgressiveReveal(
                state
            );

            return renderFinalPacket(
                elements,
                pendingMessage,
                packet,
                statusCode,
                state
            );
        }

        if (isProgressiveRevealPending(state)) {
            state.pendingFinalPacket = packet;
            state.pendingFinalStatus = statusCode;
            return true;
        }

        return renderFinalPacket(
            elements,
            pendingMessage,
            packet,
            statusCode,
            state
        );
    }

    function handleStreamError(
        errorPacket,
        elements,
        pendingMessage,
        state
    ) {
        const errorText = cleanValue(
            errorPacket?.error ||
            errorPacket?.user_output ||
            errorPacket?.message
        );

        if (
            state.finalPacketRendered ||
            state.answerRendered ||
            !errorText
        ) {
            return false;
        }

        cancelProgressiveReveal(
            state
        );

        messageRenderer.replacePendingMessage(
            elements,
            pendingMessage,
            errorText,
            { error: true }
        );
        state.finalPacketRendered = true;
        state.submissionFailed = true;
        return true;
    }

    function createStreamHandlers(
        elements,
        pendingMessage,
        state
    ) {
        return {
            onAnswer: function (answerStage) {
                handleStreamAnswer(
                    answerStage,
                    elements,
                    pendingMessage,
                    state
                );
            },
            onPacket: function (
                packet,
                statusCode
            ) {
                handleStreamPacket(
                    packet,
                    statusCode,
                    elements,
                    pendingMessage,
                    state
                );
            },
            onError: function (errorPacket) {
                handleStreamError(
                    errorPacket,
                    elements,
                    pendingMessage,
                    state
                );
            }
        };
    }

    function renderSubmissionFailure(
        elements,
        pendingMessage,
        state,
        error
    ) {
        if (state.finalPacketRendered) {
            return false;
        }

        if (cleanValue(state.streamedAnswer)) {
            cancelProgressiveReveal(
                state
            );

            messageRenderer.replacePendingMessage(
                elements,
                pendingMessage,
                state.streamedAnswer,
                { actions: true }
            );
            pendingMessage?.setAttribute(
                "data-solomon-ai-message-state",
                "answer-only"
            );
            state.answerRendered = true;
            return true;
        }

        cancelProgressiveReveal(
            state
        );

        messageRenderer.replacePendingMessage(
            elements,
            pendingMessage,
            cleanValue(error?.message) ||
                "SolomonAI could not reach the server.",
            { error: true }
        );
        return true;
    }

    function canSubmitMessage(elements, message) {
        return Boolean(
            elements?.composer &&
            elements?.input &&
            elements?.thread &&
            cleanValue(message) &&
            composerState.isInteractiveReady(elements) &&
            !composerState.isPending(elements)
        );
    }

    async function submitMessage(event, elements) {
        event?.preventDefault?.();

        const message =
            composerState.getComposerValue(
                elements
            );

        if (!canSubmitMessage(elements, message)) {
            composerState.focusComposer(elements);
            return false;
        }

        const payload =
            requestPayload.buildRequestPayload(
                elements,
                message
            );

        if (
            !requestPayload.isRequestPayloadReady(
                payload
            )
        ) {
            composerState.focusComposer(elements);
            return false;
        }

        const state = createSubmissionState();

        state.titlePreview =
            applyConversationTitlePreview(
                elements,
                message
            );

        composerState.clearComposer(elements);
        messageRenderer.appendMessage(
            elements,
            "user",
            message
        );

        const pendingMessage =
            messageRenderer.appendMessage(
                elements,
                "assistant",
                "",
                {
                    pending: true,
                    pendingState: "starting"
                }
            );

        composerState.setPending(
            elements,
            true
        );

        try {
            messagePending.setPendingMessageState(
                pendingMessage,
                "running"
            );

            const streamResult =
                await executionTransport.postExecutionStream(
                    payload,
                    createStreamHandlers(
                        elements,
                        pendingMessage,
                        state
                    )
                );

            await waitForProgressiveReveal(
                state
            );

            if (!state.finalPacketRendered) {
                renderFinalPacket(
                    elements,
                    pendingMessage,
                    state.pendingFinalPacket ||
                        streamResult.packet,
                    state.pendingFinalStatus ||
                        streamResult.status ||
                        streamResult.response?.status ||
                        200,
                    state
                );
            }

            const succeeded = Boolean(
                !state.submissionFailed &&
                !pendingMessage?.classList.contains(
                    "solomon-ai-message--error"
                )
            );

            if (!succeeded) {
                restoreConversationTitlePreview(
                    state.titlePreview
                );
            }

            if (
                succeeded &&
                state.titlePreview &&
                elements?.workspace
            ) {
                elements.workspace.setAttribute(
                    "data-solomon-ai-message-count",
                    "2"
                );
            }

            return succeeded;
        } catch (error) {
            state.submissionFailed = true;
            restoreConversationTitlePreview(
                state.titlePreview
            );
            renderSubmissionFailure(
                elements,
                pendingMessage,
                state,
                error
            );
            return false;
        } finally {
            composerState.setPending(
                elements,
                false
            );
            composerState.focusComposer(
                elements
            );
        }
    }

    modules.registerModule(
        "request_submit",
        {
            applyConversationTitlePreview,
            beginProgressiveReveal,
            buildAutomaticConversationTitle,
            buildProgressiveSegments,
            canSubmitMessage,
            createStreamHandlers,
            createSubmissionState,
            getAnswerStageSequence,
            getAnswerStageText,
            handleCumulativeStreamAnswer,
            handleStreamAnswer,
            handleStreamError,
            isCumulativeDocIntelSummaryStage,
            handleStreamPacket,
            renderFinalPacket,
            renderSubmissionFailure,
            restoreConversationTitlePreview,
            shouldUseProgressiveReveal,
            submitMessage,
            userPrefersReducedMotion,
            waitForProgressiveReveal
        }
    );
})(window, document);