/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_source_state.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI attached-file presentation state.

   Updates file counts, empty states, composer labels, and source-item
   presentation from the source list already authorized by the server.
   JavaScript does not decide file access or conversation membership.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before source state."
        );
    }

    const contract = modules.requireModule("contract");
    const membership = modules.requireModule("source_membership");
    const {
        constants,
        setElementVisibility
    } = contract;

    function updateSourceTab(elements, sourceCount) {
        if (!elements.sourceTab) {
            return;
        }

        elements.sourceTab.textContent = sourceCount
            ? `Sources (${sourceCount})`
            : "Sources";
    }

    function updateSourceLabels(elements, sourceLabel) {
        if (elements.sourceCount) {
            elements.sourceCount.textContent = sourceLabel;
        }

        if (elements.composerSourceState) {
            elements.composerSourceState.textContent = sourceLabel;
        }

        if (elements.input) {
            elements.input.placeholder =
                constants.COMPOSER_PLACEHOLDER;
        }
    }

    function updateSourceVisibility(elements, sourceCount) {
        setElementVisibility(
            elements.sourceToolbar,
            sourceCount > 0
        );
        setElementVisibility(
            elements.sourceList,
            sourceCount > 0
        );
        setElementVisibility(
            elements.sourcesEmpty,
            sourceCount === 0
        );
    }

    function updateMultiSourceSuggestions(
        elements,
        sourceCount
    ) {
        const available = sourceCount >= 2;

        elements.multiSourceSuggestions.forEach(
            function (suggestion) {
                suggestion.hidden = !available;
                suggestion.disabled = !available;
                suggestion.setAttribute(
                    "aria-hidden",
                    available ? "false" : "true"
                );

                if (
                    !available &&
                    document.activeElement === suggestion
                ) {
                    elements.input?.focus({
                        preventScroll: true
                    });
                }
            }
        );
    }

    function markRenderedSourcesAttached(elements) {
        membership.getSourceItems(elements).forEach(
            function (item) {
                item.setAttribute(
                    "data-solomon-ai-source-state",
                    "attached"
                );
            }
        );
    }

    function updateSourceState(elements) {
        if (!elements?.workspace) {
            return 0;
        }

        const sourceCount = membership.getAttachedSourceIds(
            elements
        ).length;
        const publicWebSelected = (
            membership.isPublicWebSelected(elements)
        );
        const visibleSourceCount = (
            sourceCount + (publicWebSelected ? 1 : 0)
        );
        const sourceLabel = membership.getSourceCountLabel(
            visibleSourceCount
        );

        elements.workspace.setAttribute(
            "data-solomon-ai-source-count",
            String(sourceCount)
        );
        elements.workspace.setAttribute(
            "data-solomon-ai-source-state",
            sourceCount ? "ready" : "empty"
        );

        updateSourceTab(
            elements,
            visibleSourceCount
        );
        updateSourceLabels(
            elements,
            sourceLabel
        );
        updateSourceVisibility(
            elements,
            sourceCount
        );

        modules.requireModule("source_welcome")
            .updateWelcomeSourceState(
                elements,
                sourceCount
            );

        updateMultiSourceSuggestions(
            elements,
            sourceCount
        );
        markRenderedSourcesAttached(
            elements
        );

        modules.requireModule("source_welcome")
            .updateSourceSuggestionCopy(
                elements,
                sourceCount
            );

        return sourceCount;
    }

    function initialize(elements) {
        if (!elements?.workspace) {
            return false;
        }

        updateSourceState(elements);
        return true;
    }

    modules.registerModule(
        "source_state",
        {
            initialize,
            markRenderedSourcesAttached,
            updateMultiSourceSuggestions,
            updateSourceLabels,
            updateSourceState,
            updateSourceTab,
            updateSourceVisibility
        }
    );
})(window, document);