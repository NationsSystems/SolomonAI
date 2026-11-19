/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_source_controls.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI source-panel controls.

   Owns Sources/History tab presentation and existing-source selection.
   Source-panel entry points open the shared in-workspace picker, while
   membership and file authority remain server-owned.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before source controls."
        );
    }

    const { cleanValue } = modules.requireModule("contract");
    const membership = modules.requireModule(
        "source_membership"
    );
    const sourceTransport = modules.requireModule(
        "source_transport"
    );

    function closePreviewOutsideSources(
        elements,
        tabName
    ) {
        if (tabName === "sources") {
            return;
        }

        modules.getModule("source_preview")
            ?.closeSourcePreview?.(elements);
    }

    function setActiveTab(
        elements,
        tabName,
        options
    ) {
        const cleanTabName = cleanValue(tabName);
        let activeTab = null;

        if (
            !elements?.workspace ||
            !cleanTabName
        ) {
            return false;
        }

        closePreviewOutsideSources(
            elements,
            cleanTabName
        );

        elements.tabs.forEach(function (tab) {
            const isActive = (
                tab.getAttribute(
                    "data-solomon-ai-tab"
                ) === cleanTabName
            );

            tab.classList.toggle(
                "is-active",
                isActive
            );
            tab.setAttribute(
                "aria-selected",
                isActive ? "true" : "false"
            );
            tab.tabIndex = isActive ? 0 : -1;

            if (isActive) {
                activeTab = tab;
            }
        });

        elements.panels.forEach(function (panel) {
            const isActive = (
                panel.getAttribute(
                    "data-solomon-ai-panel"
                ) === cleanTabName
            );

            panel.hidden = !isActive;
        });

        if (
            options?.focus === true &&
            activeTab
        ) {
            activeTab.focus({
                preventScroll: true
            });
        }

        return Boolean(activeTab);
    }

    function handleTabKeydown(
        event,
        elements
    ) {
        const currentIndex = elements.tabs.indexOf(
            event.currentTarget
        );

        if (currentIndex < 0) {
            return false;
        }

        let nextIndex = currentIndex;

        if (event.key === "ArrowRight") {
            nextIndex = (
                currentIndex + 1
            ) % elements.tabs.length;
        } else if (event.key === "ArrowLeft") {
            nextIndex = (
                currentIndex - 1 +
                elements.tabs.length
            ) % elements.tabs.length;
        } else if (event.key === "Home") {
            nextIndex = 0;
        } else if (event.key === "End") {
            nextIndex = elements.tabs.length - 1;
        } else {
            return false;
        }

        event.preventDefault();

        const nextTab = elements.tabs[nextIndex];
        const nextTabName = nextTab?.getAttribute(
            "data-solomon-ai-tab"
        );

        if (!nextTabName) {
            return false;
        }

        return setActiveTab(
            elements,
            nextTabName,
            { focus: true }
        );
    }

    function bindTabs(elements) {
        if (!elements?.workspace) {
            return false;
        }

        let bound = false;

        elements.tabs.forEach(function (tab) {
            if (
                tab.getAttribute(
                    "data-solomon-ai-tab-control-bound"
                ) === "true"
            ) {
                return;
            }

            tab.setAttribute(
                "data-solomon-ai-tab-control-bound",
                "true"
            );

            tab.addEventListener(
                "click",
                function () {
                    const tabName = tab.getAttribute(
                        "data-solomon-ai-tab"
                    );

                    if (tabName) {
                        setActiveTab(
                            elements,
                            tabName
                        );
                    }
                }
            );

            tab.addEventListener(
                "keydown",
                function (event) {
                    handleTabKeydown(
                        event,
                        elements
                    );
                }
            );

            bound = true;
        });

        return bound;
    }

    function openSourcePicker(elements) {
        const sourcePicker = modules.getModule(
            "source_picker"
        );

        if (
            !sourcePicker ||
            typeof sourcePicker.open !== "function"
        ) {
            membership.setSourceStatus(
                elements,
                "Source selection is temporarily unavailable.",
                "error"
            );
            return false;
        }

        return sourcePicker.open(elements);
    }

    function handleAddSource(
        event,
        elements
    ) {
        event.preventDefault();

        if (event?.currentTarget?.disabled) {
            return false;
        }

        if (sourceTransport.isPending(elements)) {
            membership.setSourceStatus(
                elements,
                "Wait for the current response to finish before adding sources.",
                "info"
            );
            return false;
        }

        return openSourcePicker(elements);
    }

    function bindAddSourceButtons(elements) {
        if (!elements?.workspace) {
            return false;
        }

        let bound = false;

        elements.addSourceButtons.forEach(function (button) {
            if (
                button.getAttribute(
                    "data-solomon-ai-add-source-control-bound"
                ) === "true"
            ) {
                return;
            }

            button.setAttribute(
                "data-solomon-ai-add-source-control-bound",
                "true"
            );

            button.addEventListener(
                "click",
                function (event) {
                    handleAddSource(
                        event,
                        elements
                    );
                }
            );

            bound = true;
        });

        return bound;
    }

    function initialize(elements) {
        if (!elements?.workspace) {
            return false;
        }

        bindTabs(elements);
        bindAddSourceButtons(elements);

        return true;
    }

    modules.registerModule(
        "source_controls",
        {
            bindAddSourceButtons,
            bindTabs,
            handleAddSource,
            handleTabKeydown,
            initialize,
            openSourcePicker,
            setActiveTab
        }
    );
})(window);