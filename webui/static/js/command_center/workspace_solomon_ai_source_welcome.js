/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_source_welcome.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI welcome-state presentation for attached files.

   Updates empty-conversation copy and prompt suggestions from files
   already authorized and rendered by the server. JavaScript does not
   decide source membership, request operations, routing, or execution.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before source welcome."
        );
    }

    const {
        cleanValue
    } = modules.requireModule("contract");

    function updateWelcomeSuggestion(button, options) {
        if (!button) {
            return;
        }

        const icon = button.querySelector(".icon");
        const label = button.querySelector("span:last-child");
        const prompt = cleanValue(
            options?.prompt
        );
        const visible = options?.visible !== false;

        if (icon) {
            icon.textContent = cleanValue(
                options?.icon
            );
        }

        if (label) {
            label.textContent = cleanValue(
                options?.label
            );
        }

        if (prompt) {
            button.setAttribute(
                "data-solomon-ai-prompt",
                prompt
            );
        } else {
            button.removeAttribute(
                "data-solomon-ai-prompt"
            );
        }

        if (options?.multiSource === true) {
            button.setAttribute(
                "data-solomon-ai-multi-source-suggestion",
                ""
            );
        } else {
            button.removeAttribute(
                "data-solomon-ai-multi-source-suggestion"
            );
        }

        button.hidden = !visible;
        button.disabled = !visible;
        button.setAttribute(
            "aria-hidden",
            visible ? "false" : "true"
        );
    }

    function getSuggestionButtons(welcome) {
        return Array.from(
            welcome?.querySelectorAll(
                "[data-solomon-ai-suggestions] " +
                "[data-solomon-ai-suggestion]"
            ) || []
        );
    }

    function updateWithSources(
        heading,
        copy,
        buttons,
        sourceCount
    ) {
        if (heading) {
            heading.textContent = sourceCount === 1
                ? "Ask questions about this file"
                : "Ask questions about your files";
        }

        if (copy) {
            copy.textContent = sourceCount === 1
                ? (
                    "Summarize it, find details, or ask " +
                    "about anything inside."
                )
                : (
                    "Compare them, find details, or ask " +
                    "about anything inside."
                );
        }

        updateWelcomeSuggestion(
            buttons[0],
            {
                icon: "summarize",
                label: sourceCount === 1
                    ? "Summarize this document"
                    : "Summarize attached files",
                prompt: sourceCount === 1
                    ? (
                        "Summarize this document and explain " +
                        "its main points."
                    )
                    : (
                        "Summarize the attached files and explain " +
                        "their main points."
                    )
            }
        );

        updateWelcomeSuggestion(
            buttons[1],
            {
                icon: "fact_check",
                label: "Identify key details",
                prompt: sourceCount === 1
                    ? (
                        "Identify the key facts, dates, obligations, " +
                        "risks, and open questions in this document."
                    )
                    : (
                        "Identify the key facts, dates, obligations, " +
                        "risks, and open questions across the attached files."
                    )
            }
        );

        updateWelcomeSuggestion(
            buttons[2],
            {
                icon: "compare_arrows",
                label: "Compare attached files",
                prompt: (
                    "Compare the attached files and explain their most " +
                    "important differences."
                ),
                multiSource: true,
                visible: sourceCount >= 2
            }
        );
    }

    function updateWithoutSources(
        heading,
        copy,
        buttons
    ) {
        if (heading) {
            heading.textContent = "What can I help with?";
        }

        if (copy) {
            copy.textContent = (
                "Ask a question or add sources to focus this chat."
            );
        }

        updateWelcomeSuggestion(
            buttons[0],
            {
                icon: "summarize",
                label: "Summarize a file",
                prompt: (
                    "Summarize a file and explain the main points."
                )
            }
        );

        updateWelcomeSuggestion(
            buttons[1],
            {
                icon: "compare_arrows",
                label: "Compare documents",
                prompt: (
                    "Compare documents and explain the important differences."
                )
            }
        );

        updateWelcomeSuggestion(
            buttons[2],
            {
                icon: "checklist",
                label: "Organize information",
                prompt: (
                    "Help me organize this information clearly."
                )
            }
        );
    }

    function updateWelcomeSourceState(
        elements,
        sourceCount
    ) {
        const welcome = elements?.welcome;

        if (
            !welcome?.isConnected ||
            elements.thread?.querySelector(
                "[data-solomon-ai-message]"
            )
        ) {
            return false;
        }

        const heading = welcome.querySelector("h2");
        const copy = welcome.querySelector(
            ".solomon-ai-conversation__welcome-copy"
        );
        const buttons = getSuggestionButtons(
            welcome
        );
        let kicker = welcome.querySelector(
            ".solomon-ai-conversation__kicker"
        );

        if (sourceCount > 0) {
            if (!kicker && heading) {
                kicker = document.createElement("p");
                kicker.className = (
                    "solomon-ai-conversation__kicker"
                );
                heading.before(kicker);
            }

            if (kicker) {
                kicker.textContent = sourceCount === 1
                    ? "1 source added"
                    : `${sourceCount} sources added`;
            }

            updateWithSources(
                heading,
                copy,
                buttons,
                sourceCount
            );
        } else {
            kicker?.remove();

            updateWithoutSources(
                heading,
                copy,
                buttons
            );
        }

        elements.suggestions = buttons;
        elements.multiSourceSuggestions = buttons.filter(
            function (button) {
                return button.hasAttribute(
                    "data-solomon-ai-multi-source-suggestion"
                );
            }
        );

        return true;
    }

    function updateSourceSuggestionCopy(
        elements,
        sourceCount
    ) {
        const welcome = elements?.welcome;

        if (!welcome) {
            return false;
        }

        const buttons = getSuggestionButtons(
            welcome
        );
        const summary = buttons[0] || null;
        const details = buttons[1] || null;
        const compare = buttons[2] || null;
        const summaryLabel = summary?.querySelector(
            "span:last-child"
        );

        if (summary) {
            summary.setAttribute(
                "data-solomon-ai-prompt",
                sourceCount === 1
                    ? (
                        "Summarize this document and explain " +
                        "its main points."
                    )
                    : (
                        "Summarize the attached files and explain " +
                        "their main points."
                    )
            );
        }

        if (summaryLabel) {
            summaryLabel.textContent = sourceCount === 1
                ? "Summarize this document"
                : "Summarize attached files";
        }

        if (details) {
            details.setAttribute(
                "data-solomon-ai-prompt",
                sourceCount === 1
                    ? (
                        "Identify the key facts, dates, obligations, " +
                        "risks, and open questions in this document."
                    )
                    : (
                        "Identify the key facts, dates, obligations, " +
                        "risks, and open questions across the attached files."
                    )
            );
        }

        if (compare) {
            compare.setAttribute(
                "data-solomon-ai-prompt",
                (
                    "Compare the attached files and explain their " +
                    "most important differences."
                )
            );
        }

        return true;
    }

    modules.registerModule(
        "source_welcome",
        {
            getSuggestionButtons,
            updateSourceSuggestionCopy,
            updateWelcomeSourceState,
            updateWelcomeSuggestion
        }
    );
})(window, document);