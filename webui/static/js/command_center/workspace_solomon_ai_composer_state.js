/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_composer_state.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI composer interaction state.

   Owns pending presentation, prompt suggestion transfer, composer
   clearing, and focus restoration. JavaScript manages browser state
   only; operation resolution, execution, and conversation authority
   remain exclusively on the server.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before composer state."
        );
    }

    const contract = modules.requireModule("contract");
    const composerLayout = modules.requireModule(
        "composer_layout"
    );
    const {
        cleanValue
    } = contract;

    const SUGGESTION_SELECTOR = [
        "[data-solomon-ai-suggestion]",
        "[data-solomon-ai-response-suggestion]"
    ].join(", ");

    const INTERACTIVE_READINESS_STATES = new Set([
        "checking",
        "warming",
        "ready",
        "degraded",
        "unavailable"
    ]);

    function normalizeInteractiveReadinessState(value) {
        const normalized = cleanValue(value).toLowerCase();

        return INTERACTIVE_READINESS_STATES.has(normalized)
            ? normalized
            : "unavailable";
    }

    function getInteractiveReadinessState(elements) {
        return normalizeInteractiveReadinessState(
            elements?.composer?.getAttribute(
                "data-solomon-ai-intelligence-state"
            ) || "checking"
        );
    }

    function isInteractiveReady(elements) {
        return getInteractiveReadinessState(elements) === "ready";
    }

    function refreshComposerAvailability(elements) {
        const composer = elements?.composer;

        if (!composer) {
            return false;
        }

        const disabled = Boolean(
            isPending(elements) ||
            !isInteractiveReady(elements)
        );

        composer.setAttribute(
            "data-solomon-ai-composer-availability",
            disabled ? "disabled" : "enabled"
        );
        composer.setAttribute(
            "aria-disabled",
            disabled ? "true" : "false"
        );

        if (elements.input) {
            elements.input.disabled = disabled;
        }

        if (elements.composerSource) {
            elements.composerSource.disabled = disabled;
        }

        if (elements.submit) {
            elements.submit.disabled = disabled;
        }

        return !disabled;
    }

    function setInteractiveReadiness(elements, readiness = {}) {
        const composer = elements?.composer;

        if (!composer) {
            return false;
        }

        const state = normalizeInteractiveReadinessState(
            readiness.status
        );
        const canSubmit = Boolean(
            readiness.can_submit === true &&
            state === "ready"
        );
        const effectiveState = canSubmit
            ? "ready"
            : (state === "ready" ? "unavailable" : state);
        const statusElement = elements?.intelligenceStatus;
        const userMessage = cleanValue(
            readiness.user_message
        );

        composer.setAttribute(
            "data-solomon-ai-intelligence-state",
            effectiveState
        );
        elements?.workspace?.setAttribute(
            "data-solomon-ai-intelligence-state",
            effectiveState
        );

        if (statusElement) {
            statusElement.setAttribute(
                "data-solomon-ai-intelligence-status-variant",
                effectiveState
            );
            statusElement.textContent =
                effectiveState === "ready"
                    ? ""
                    : (
                        userMessage ||
                        "Solomon is temporarily unavailable. " +
                        "Your other workspace features are unaffected."
                    );
            statusElement.hidden =
                effectiveState === "ready";
        }

        const unavailableTitle = (
            userMessage ||
            "Solomon is temporarily unavailable."
        );

        if (elements.input) {
            elements.input.title =
                effectiveState === "ready"
                    ? ""
                    : unavailableTitle;
        }

        if (elements.composerSource) {
            elements.composerSource.title =
                effectiveState === "ready"
                    ? "Upload file"
                    : unavailableTitle;
        }

        if (elements.submit) {
            elements.submit.title =
                effectiveState === "ready"
                    ? "Send message to SolomonAI"
                    : unavailableTitle;
        }

        refreshComposerAvailability(elements);
        return effectiveState === "ready";
    }

    function isPending(elements) {
        return (
            elements?.composer?.getAttribute(
                "data-solomon-ai-pending"
            ) === "true"
        );
    }

    function setPending(elements, pending) {
        const composer = elements?.composer;

        if (!composer) {
            return false;
        }

        const nextPending = pending === true;

        composer.setAttribute(
            "data-solomon-ai-pending",
            nextPending ? "true" : "false"
        );
        composer.setAttribute(
            "aria-busy",
            nextPending ? "true" : "false"
        );

        refreshComposerAvailability(elements);

        return nextPending;
    }

    function getComposerValue(elements) {
        return cleanValue(
            elements?.input?.value
        );
    }

    function focusComposer(elements) {
        const input = elements?.input;

        if (
            !input ||
            input.disabled
        ) {
            return false;
        }

        input.focus({
            preventScroll: true
        });

        return true;
    }

    function placeCursorAtEnd(input) {
        if (!input) {
            return false;
        }

        const textLength = String(
            input.value || ""
        ).length;

        if (
            typeof input.setSelectionRange ===
            "function"
        ) {
            input.setSelectionRange(
                textLength,
                textLength
            );
        }

        return true;
    }

    function fillComposer(
        elements,
        prompt
    ) {
        const input = elements?.input;
        const cleanPrompt = cleanValue(
            prompt
        );

        if (
            !cleanPrompt ||
            !input ||
            input.disabled ||
            isPending(elements)
        ) {
            return false;
        }

        input.value = cleanPrompt;

        composerLayout.resizeInput(
            input,
            elements
        );

        focusComposer(elements);
        placeCursorAtEnd(input);

        return true;
    }

    function fillComposerFromSuggestion(
        suggestion,
        elements
    ) {
        if (!suggestion) {
            return false;
        }

        const prompt = cleanValue(
            suggestion.getAttribute(
                "data-solomon-ai-prompt"
            )
        );

        return fillComposer(
            elements,
            prompt
        );
    }

    function fillComposerFromResponseSuggestion(
        elements,
        prompt
    ) {
        return fillComposer(
            elements,
            prompt
        );
    }

    function clearComposer(elements) {
        const input = elements?.input;

        if (!input) {
            return false;
        }

        input.value = "";

        composerLayout.resizeInput(
            input,
            elements
        );

        return true;
    }

    function resolveSuggestion(
        event,
        elements
    ) {
        const target = event?.target;

        if (
            !target ||
            typeof target.closest !== "function"
        ) {
            return null;
        }

        const suggestion = target.closest(
            SUGGESTION_SELECTOR
        );

        if (
            !suggestion ||
            !elements?.workspace?.contains(
                suggestion
            ) ||
            suggestion.disabled ||
            suggestion.hidden
        ) {
            return null;
        }

        return suggestion;
    }

    function bindSuggestionControls(
        elements
    ) {
        const workspace =
            elements?.workspace;

        if (
            !workspace ||
            workspace.getAttribute(
                "data-solomon-ai-composer-suggestions-bound"
            ) === "true"
        ) {
            return false;
        }

        workspace.setAttribute(
            "data-solomon-ai-composer-suggestions-bound",
            "true"
        );

        workspace.addEventListener(
            "click",
            function (event) {
                const suggestion =
                    resolveSuggestion(
                        event,
                        elements
                    );

                if (!suggestion) {
                    return;
                }

                event.preventDefault();

                fillComposerFromSuggestion(
                    suggestion,
                    elements
                );
            }
        );

        return true;
    }

    function refresh(elements) {
        if (!elements?.composer) {
            return false;
        }

        refreshComposerAvailability(elements);
        return true;
    }

    function initialize(elements) {
        if (
            !elements?.workspace ||
            !elements?.composer
        ) {
            return false;
        }

        bindSuggestionControls(
            elements
        );
        refresh(elements);

        return true;
    }

    modules.registerModule(
        "composer_state",
        {
            bindSuggestionControls,
            clearComposer,
            fillComposer,
            fillComposerFromResponseSuggestion,
            fillComposerFromSuggestion,
            focusComposer,
            getComposerValue,
            getInteractiveReadinessState,
            initialize,
            isInteractiveReady,
            isPending,
            normalizeInteractiveReadinessState,
            placeCursorAtEnd,
            refresh,
            refreshComposerAvailability,
            setInteractiveReadiness,
            setPending
        }
    );
})(window);