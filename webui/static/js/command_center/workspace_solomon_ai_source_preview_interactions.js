/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_source_preview_interactions.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI attached-file preview interactions.

   Prepares server-rendered source controls and binds delegated mouse,
   keyboard, close, outside-click, Escape, and asynchronous Reader launch
   interactions. File access, source membership, and Reader authority
   remain server-owned.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before source " +
            "preview interactions."
        );
    }

    const contract = modules.requireModule("contract");
    const sourcePreview = modules.requireModule(
        "source_preview"
    );
    const {
        constants,
        cleanValue,
        getElements
    } = contract;
    const {
        buildReaderThumbnailUrl,
        closeSourcePreview,
        getSourceItemName,
        getSourceItemReaderUrl,
        getSourceItems,
        openSourcePreview
    } = sourcePreview;

    const DOCUMENTS_MODULE_ID = "documents";
    const PREVIEW_READER_LAUNCH_SELECTOR = [
        "[data-solomon-ai-source-preview]",
        "[data-solomon-ai-source-reader-url][href]"
    ].join(" ");

    let globalDismissalBound = false;

    function getClosestElement(
        eventTarget,
        selector
    ) {
        if (
            !eventTarget ||
            typeof eventTarget.closest !== "function"
        ) {
            return null;
        }

        return eventTarget.closest(selector);
    }

    function getSameOriginRelativeRoute(value) {
        const cleanRoute = cleanValue(value);

        if (!cleanRoute) {
            return "";
        }

        try {
            const url = new URL(
                cleanRoute,
                window.location.origin
            );

            if (url.origin !== window.location.origin) {
                return "";
            }

            return `${url.pathname}${url.search}${url.hash}`;
        } catch (_error) {
            return "";
        }
    }

    function getReaderLaunchRoute(control) {
        return getSameOriginRelativeRoute(
            control?.getAttribute("data-workspace-object-route") ||
            control?.getAttribute("data-document-route") ||
            control?.getAttribute("data-command-route") ||
            control?.getAttribute("href")
        );
    }

    function getSidebarApi() {
        return window.NationsCommandSidebar || null;
    }

    async function launchReaderRoute(route) {
        const cleanRoute = getSameOriginRelativeRoute(route);
        const sidebarApi = getSidebarApi();

        if (!cleanRoute) {
            return false;
        }

        if (
            sidebarApi &&
            typeof sidebarApi.loadWorkspace === "function"
        ) {
            try {
                const result = await sidebarApi.loadWorkspace(
                    cleanRoute,
                    DOCUMENTS_MODULE_ID,
                    {
                        push: true,
                        launchMode: "reader",
                        source: "solomon_ai_source_preview",
                        async: true
                    }
                );

                if (result !== false) {
                    return true;
                }
            } catch (error) {
                console.warn(
                    "[SOLOMON_AI_SOURCE_PREVIEW] Async Reader launch failed; falling back to hard navigation.",
                    error
                );
            }
        }

        window.location.assign(cleanRoute);
        return false;
    }

    function preparePreviewControl(
        control,
        sourceName
    ) {
        if (!control) {
            return;
        }

        control.setAttribute(
            "data-solomon-ai-source-preview-trigger",
            ""
        );
        control.setAttribute(
            "aria-haspopup",
            "dialog"
        );
        control.setAttribute(
            "aria-controls",
            constants.SOURCE_PREVIEW_ID
        );

        if (
            !control.hasAttribute(
                "aria-expanded"
            )
        ) {
            control.setAttribute(
                "aria-expanded",
                "false"
            );
        }

        if (
            control.tagName !== "BUTTON" &&
            control.tagName !== "A"
        ) {
            control.setAttribute(
                "role",
                "button"
            );

            if (!control.hasAttribute("tabindex")) {
                control.tabIndex = 0;
            }
        }

        control.setAttribute(
            "aria-label",
            `Preview ${sourceName}`
        );
    }

    function prepareSourceItem(item) {
        if (!item) {
            return;
        }

        const sourceName =
            getSourceItemName(item);
        const readerUrl =
            getSourceItemReaderUrl(item);
        const copyControl = item.querySelector(
            ".solomon-ai-source-item__copy"
        );
        const openControl = item.querySelector(
            ".solomon-ai-source-item__open"
        );

        item.setAttribute(
            "data-solomon-ai-source-name",
            sourceName
        );

        if (readerUrl) {
            item.setAttribute(
                "data-solomon-ai-source-reader-url",
                readerUrl
            );
            item.setAttribute(
                "data-solomon-ai-source-thumbnail-url",
                buildReaderThumbnailUrl(
                    readerUrl
                )
            );
        } else {
            item.removeAttribute(
                "data-solomon-ai-source-reader-url"
            );
            item.removeAttribute(
                "data-solomon-ai-source-thumbnail-url"
            );
        }

        preparePreviewControl(
            copyControl,
            sourceName
        );
        preparePreviewControl(
            openControl,
            sourceName
        );

        if (openControl) {
            openControl.title = "Preview file";

            const icon = openControl.querySelector(
                ".icon"
            );

            if (icon) {
                icon.textContent = "visibility";
            }
        }

        item.setAttribute(
            "data-solomon-ai-source-preview-prepared",
            "true"
        );
    }

    function prepareSourceItems(elements) {
        getSourceItems(elements).forEach(
            prepareSourceItem
        );
    }

    function resolvePreviewInteraction(
        event,
        elements
    ) {
        const trigger = getClosestElement(
            event.target,
            "[data-solomon-ai-source-preview-trigger]"
        );
        const item = trigger?.closest(
            "[data-solomon-ai-source]"
        );

        if (
            !trigger ||
            !item ||
            !elements.sourceList ||
            !elements.sourceList.contains(
                trigger
            ) ||
            !elements.sourceList.contains(
                item
            )
        ) {
            return null;
        }

        return {
            trigger,
            item
        };
    }

    function handleSourceListClick(
        event,
        elements
    ) {
        const interaction =
            resolvePreviewInteraction(
                event,
                elements
            );

        if (!interaction) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        openSourcePreview(
            elements,
            interaction.item,
            interaction.trigger
        );
    }

    function handleSourceListKeydown(
        event,
        elements
    ) {
        if (
            event.key !== "Enter" &&
            event.key !== " "
        ) {
            return;
        }

        const interaction =
            resolvePreviewInteraction(
                event,
                elements
            );

        if (!interaction) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        openSourcePreview(
            elements,
            interaction.item,
            interaction.trigger
        );
    }

    function bindSourceListInteractions(
        elements
    ) {
        const sourceList =
            elements.sourceList;

        if (
            !sourceList ||
            sourceList.getAttribute(
                "data-solomon-ai-source-preview-list-bound"
            ) === "true"
        ) {
            return;
        }

        sourceList.setAttribute(
            "data-solomon-ai-source-preview-list-bound",
            "true"
        );

        sourceList.addEventListener(
            "click",
            function (event) {
                handleSourceListClick(
                    event,
                    elements
                );
            }
        );

        sourceList.addEventListener(
            "keydown",
            function (event) {
                handleSourceListKeydown(
                    event,
                    elements
                );
            }
        );
    }

    function bindPreviewCloseInteraction(
        elements
    ) {
        const workspace =
            elements.workspace;

        if (
            !workspace ||
            workspace.getAttribute(
                "data-solomon-ai-source-preview-close-bound"
            ) === "true"
        ) {
            return;
        }

        workspace.setAttribute(
            "data-solomon-ai-source-preview-close-bound",
            "true"
        );

        workspace.addEventListener(
            "click",
            function (event) {
                const closeButton =
                    getClosestElement(
                        event.target,
                        "[data-solomon-ai-source-preview-close]"
                    );

                if (
                    !closeButton ||
                    !workspace.contains(
                        closeButton
                    )
                ) {
                    return;
                }

                event.preventDefault();

                closeSourcePreview(
                    elements,
                    {
                        focus: true
                    }
                );
            }
        );
    }

    function bindPreviewReaderLaunchInteraction(
        elements
    ) {
        const workspace =
            elements.workspace;

        if (
            !workspace ||
            workspace.getAttribute(
                "data-solomon-ai-source-preview-reader-launch-bound"
            ) === "true"
        ) {
            return;
        }

        workspace.setAttribute(
            "data-solomon-ai-source-preview-reader-launch-bound",
            "true"
        );

        workspace.addEventListener(
            "click",
            function (event) {
                const launchControl =
                    getClosestElement(
                        event.target,
                        PREVIEW_READER_LAUNCH_SELECTOR
                    );

                if (
                    !launchControl ||
                    !workspace.contains(launchControl)
                ) {
                    return;
                }

                const route = getReaderLaunchRoute(
                    launchControl
                );

                if (!route) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                launchReaderRoute(route);
            }
        );
    }

    function getOpenPreview() {
        return document.querySelector(
            "[data-solomon-ai-source-preview]" +
            ":not([hidden])"
        );
    }

    function closeOpenPreview(options) {
        const preview = getOpenPreview();
        const workspace = preview?.closest(
            constants.WORKSPACE_SELECTOR
        );

        if (!workspace) {
            return false;
        }

        return closeSourcePreview(
            getElements(workspace),
            options
        );
    }

    function bindGlobalDismissal() {
        if (globalDismissalBound) {
            return;
        }

        globalDismissalBound = true;

        document.addEventListener(
            "click",
            function (event) {
                const preview =
                    getOpenPreview();

                if (
                    !preview ||
                    preview.contains(
                        event.target
                    ) ||
                    getClosestElement(
                        event.target,
                        "[data-solomon-ai-source-preview-trigger]"
                    )
                ) {
                    return;
                }

                closeOpenPreview();
            }
        );

        document.addEventListener(
            "keydown",
            function (event) {
                if (
                    event.key !== "Escape" ||
                    !getOpenPreview()
                ) {
                    return;
                }

                event.preventDefault();

                closeOpenPreview({
                    focus: true
                });
            }
        );
    }

    function refresh(elements) {
        if (!elements?.workspace) {
            return false;
        }

        prepareSourceItems(elements);

        return true;
    }

    function initialize(elements) {
        if (!elements?.workspace) {
            return false;
        }

        refresh(elements);
        bindSourceListInteractions(
            elements
        );
        bindPreviewCloseInteraction(
            elements
        );
        bindPreviewReaderLaunchInteraction(
            elements
        );
        bindGlobalDismissal();

        return true;
    }

    modules.registerModule(
        "source_preview_interactions",
        {
            bindGlobalDismissal,
            bindPreviewCloseInteraction,
            bindPreviewReaderLaunchInteraction,
            bindSourceListInteractions,
            closeOpenPreview,
            initialize,
            launchReaderRoute,
            prepareSourceItem,
            prepareSourceItems,
            refresh
        }
    );
})(window, document);