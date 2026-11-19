/* -------------------------------------------------------------------
   FILE: workspace_document_reader_lifecycle.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const DEFAULT_WORKSPACE_VIEW = "files";
    const READER_WORKSPACE_VIEW = "reader";
    const DEFAULT_DOCUMENTS_MODULE_ID = "documents";
    const DEFAULT_VALID_WORKSPACE_VIEWS = Object.freeze(["files", "chat", "preview", "reader"]);
    const READER_CLOSE_ARM_DELAY_MS = 280;

    const DEFAULT_WORKSPACE_VIEW_BUTTON_SELECTOR = ".workspace-document-view-button[data-workspace-view]";
    const DEFAULT_WORKSPACE_VIEW_PANEL_SELECTOR = "[data-workspace-view-panel]";
    const DEFAULT_WORKSPACE_READER_PANEL_SELECTOR = "[data-workspace-reader-panel]";
    const DEFAULT_READER_CONTROLLER_SELECTOR = "[data-reader-controller]";

    const DEFAULT_READER_ROUTE_PATTERN = /^\/workspace\/(?:file|document)\/[^/]+\/reader\/?$/;
    const DEFAULT_READER_FRAGMENT_ROUTE_PATTERN = /^\/workspace\/(?:file|document)\/[^/]+\/reader\/fragment\/?$/;

    function cleanValue(value) {
        return String(value || "").trim();
    }

    function getConversationApi(options) {
        return options?.Conversation || window.SolomonWorkspaceDocumentConversation || null;
    }

    function getSelector(options, key, fallback) {
        return cleanValue(options?.selectors?.[key]) || fallback;
    }

    function getReaderRoutePattern(options) {
        return options?.readerRoutePattern || DEFAULT_READER_ROUTE_PATTERN;
    }

    function getReaderFragmentRoutePattern(options) {
        return options?.readerFragmentRoutePattern || DEFAULT_READER_FRAGMENT_ROUTE_PATTERN;
    }

    function normalizeWorkspaceView(viewName, options) {
        const validViews = Array.isArray(options?.validWorkspaceViews) && options.validWorkspaceViews.length
            ? options.validWorkspaceViews
            : DEFAULT_VALID_WORKSPACE_VIEWS;
        const defaultView = cleanValue(options?.defaultWorkspaceView) || DEFAULT_WORKSPACE_VIEW;
        const cleanView = cleanValue(viewName || defaultView).toLowerCase();

        return validViews.includes(cleanView) ? cleanView : defaultView;
    }

    function getSameOriginUrl(value) {
        const cleanUrl = cleanValue(value);

        if (!cleanUrl) {
            return null;
        }

        try {
            const parsedUrl = new URL(cleanUrl, window.location.origin);

            return parsedUrl.origin === window.location.origin
                ? parsedUrl
                : null;
        } catch (_error) {
            return null;
        }
    }

    function getRelativeUrl(parsedUrl) {
        if (!parsedUrl) {
            return "";
        }

        return `${parsedUrl.pathname}${parsedUrl.search}${parsedUrl.hash}`;
    }

    function getSameOriginRelativeRoute(value) {
        return getRelativeUrl(
            getSameOriginUrl(value)
        );
    }

    function getCurrentRelativeRoute() {
        return [
            window.location.pathname || "/",
            window.location.search || "",
            window.location.hash || ""
        ].join("");
    }

    function isReaderRoutePath(pathname, options) {
        const cleanPath = cleanValue(pathname)
            .replace(/\/+$/, "") || "/";

        return (
            getReaderRoutePattern(options).test(cleanPath) ||
            getReaderFragmentRoutePattern(options).test(cleanPath)
        );
    }

    function isReaderRoute(options) {
        return getReaderRoutePattern(options).test(String(window.location?.pathname || ""));
    }

    function isWorkspaceReaderRoute(route, options) {
        const parsedUrl = getSameOriginUrl(route);

        if (!parsedUrl) {
            return false;
        }

        return isReaderRoutePath(parsedUrl.pathname, options);
    }

    function normalizeSafeRightPaneRoute(route, options) {
        const parsedUrl = getSameOriginUrl(route);

        if (!parsedUrl || !parsedUrl.pathname.startsWith("/")) {
            return "";
        }

        if (isReaderRoutePath(parsedUrl.pathname, options)) {
            return "";
        }

        return getRelativeUrl(parsedUrl);
    }

    function getReaderBackRouteFromLocation(options) {
        const currentUrl = getSameOriginUrl(window.location.href);

        if (!currentUrl) {
            return "";
        }

        return normalizeSafeRightPaneRoute(
            currentUrl.searchParams.get("back") || "",
            options
        );
    }

    function getReaderBackRouteFromRoute(route, options) {
        const readerUrl = getSameOriginUrl(route);

        if (!readerUrl) {
            return "";
        }

        return normalizeSafeRightPaneRoute(
            readerUrl.searchParams.get("back") || "",
            options
        );
    }

    function getStoredReaderBackRoute(explorer, options) {
        const readerPanel = getReaderPanel(explorer, options);

        return normalizeSafeRightPaneRoute(
            explorer?.dataset?.workspaceReaderBackRoute ||
            explorer?.getAttribute("data-workspace-reader-back-route") ||
            explorer?.getAttribute("data-right-pane-content-back-route") ||
            readerPanel?.getAttribute("data-workspace-reader-back-route") ||
            readerPanel?.getAttribute("data-right-pane-content-back-route") ||
            window.history?.state?.readerBackRoute ||
            window.history?.state?.backRoute ||
            "",
            options
        );
    }

    function resolveReaderBackRoute(readerUrl, options, explorer) {
        return (
            normalizeSafeRightPaneRoute(options?.backRoute, options) ||
            getReaderBackRouteFromRoute(readerUrl, options) ||
            getReaderBackRouteFromLocation(options) ||
            getStoredReaderBackRoute(explorer, options)
        );
    }

    function buildReaderRouteWithBack(readerUrl, backRoute, options) {
        const parsedUrl = getSameOriginUrl(readerUrl);
        const safeBackRoute = normalizeSafeRightPaneRoute(backRoute, options);

        if (!parsedUrl) {
            return cleanValue(readerUrl);
        }

        if (!isReaderRoutePath(parsedUrl.pathname, options)) {
            return getRelativeUrl(parsedUrl);
        }

        if (safeBackRoute && !parsedUrl.searchParams.has("back")) {
            parsedUrl.searchParams.set("back", safeBackRoute);
        }

        return getRelativeUrl(parsedUrl);
    }

    function getReaderCloseBackRoute(explorer, options) {
        return resolveReaderBackRoute(
            options?.readerUrl,
            options,
            explorer
        );
    }

    function getRightPaneModuleForRoute(route) {
        const parsedUrl = getSameOriginUrl(route);

        if (!parsedUrl) {
            return DEFAULT_DOCUMENTS_MODULE_ID;
        }

        if (parsedUrl.pathname === "/search") {
            return "search";
        }

        if (
            parsedUrl.pathname === "/ai" ||
            parsedUrl.pathname.startsWith("/ai/")
        ) {
            return "solomon_ai";
        }

        if (
            parsedUrl.pathname === "/people" ||
            parsedUrl.pathname.startsWith("/people/")
        ) {
            return "people";
        }

        return DEFAULT_DOCUMENTS_MODULE_ID;
    }

    function fallbackToRoute(route) {
        const cleanRoute = getSameOriginRelativeRoute(route) || cleanValue(route);

        if (!cleanRoute) {
            return false;
        }

        window.location.assign(cleanRoute);
        return false;
    }

    function loadRightPaneRoute(route, options) {
        const cleanRoute = getSameOriginRelativeRoute(route);
        const moduleId = cleanValue(options?.moduleId) || getRightPaneModuleForRoute(cleanRoute);
        const payload = Object.assign(
            {
                push: true,
                async: true,
                launchMode: "right_pane_restore",
                source: "workspace_document_reader_lifecycle"
            },
            options?.loadOptions || {}
        );
        const customLoader = options?.loadRightPaneRoute || options?.navigateToRightPaneRoute;
        const sidebarApi = window.NationsCommandSidebar || null;
        let result = null;

        if (!cleanRoute) {
            return false;
        }

        try {
            if (typeof customLoader === "function") {
                result = customLoader(cleanRoute, moduleId, payload);
            } else if (sidebarApi && typeof sidebarApi.loadWorkspace === "function") {
                result = sidebarApi.loadWorkspace(cleanRoute, moduleId, payload);
            } else {
                return fallbackToRoute(cleanRoute);
            }

            if (result && typeof result.then === "function") {
                result.then(function (resolved) {
                    if (resolved === false) {
                        fallbackToRoute(cleanRoute);
                    }
                }).catch(function (error) {
                    console.warn(
                        "[DOCUMENT_READER_LIFECYCLE] Async right-pane route load failed; falling back to hard navigation.",
                        error
                    );
                    fallbackToRoute(cleanRoute);
                });
            } else if (result === false) {
                fallbackToRoute(cleanRoute);
            }

            return true;
        } catch (error) {
            console.warn(
                "[DOCUMENT_READER_LIFECYCLE] Async right-pane route load failed; falling back to hard navigation.",
                error
            );
            fallbackToRoute(cleanRoute);
            return true;
        }
    }

    function getReaderPanel(explorer, options) {
        const readerPanelSelector = getSelector(
            options,
            "readerPanel",
            DEFAULT_WORKSPACE_READER_PANEL_SELECTOR
        );

        return explorer?.querySelector(readerPanelSelector) || null;
    }

    function hasEmbeddedReaderSurface(explorer, options) {
        const readerControllerSelector = getSelector(
            options,
            "readerController",
            DEFAULT_READER_CONTROLLER_SELECTOR
        );

        return Boolean(
            getReaderPanel(explorer, options) &&
            explorer?.querySelector(readerControllerSelector)
        );
    }

    function shouldUseServerReaderView(explorer, options) {
        return Boolean(isReaderRoute(options) && hasEmbeddedReaderSurface(explorer, options));
    }

    function getCurrentWorkspaceView(explorer, options) {
        return normalizeWorkspaceView(explorer?.getAttribute("data-workspace-view"), options);
    }

    function getInitialWorkspaceView(explorer, options) {
        if (shouldUseServerReaderView(explorer, options)) {
            return cleanValue(options?.readerWorkspaceView) || READER_WORKSPACE_VIEW;
        }

        return normalizeWorkspaceView(explorer?.getAttribute("data-workspace-view"), options);
    }

    function clearReaderRouteHash() {
        if (!window.history || typeof window.history.replaceState !== "function") {
            return;
        }

        const hash = String(window.location.hash || "");

        if (!/^#reader-(?:page|sheet)-\d+$/.test(hash)) {
            return;
        }

        window.history.replaceState(
            window.history.state,
            "",
            `${window.location.pathname}${window.location.search}`
        );
    }

    function setReaderCloseArmed(explorer, readerPanel, armed) {
        const value = armed ? "true" : "false";

        if (explorer) {
            explorer.setAttribute("data-workspace-reader-close-armed", value);
        }

        if (readerPanel) {
            readerPanel.setAttribute("data-workspace-reader-close-armed", value);
        }
    }

    function clearReaderCloseArmTimer(explorer) {
        if (!explorer?.__solomonReaderCloseArmTimer) {
            return;
        }

        window.clearTimeout(explorer.__solomonReaderCloseArmTimer);
        explorer.__solomonReaderCloseArmTimer = null;
    }

    function disarmReaderClose(explorer, readerPanel) {
        clearReaderCloseArmTimer(explorer);
        setReaderCloseArmed(explorer, readerPanel, false);
    }

    function scheduleReaderCloseArm(explorer, readerPanel) {
        if (!explorer) {
            return;
        }

        clearReaderCloseArmTimer(explorer);

        explorer.__solomonReaderCloseArmTimer = window.setTimeout(function () {
            if (!document.contains(explorer)) {
                return;
            }

            setReaderCloseArmed(
                explorer,
                readerPanel || getReaderPanel(explorer, {}),
                true
            );

            explorer.__solomonReaderCloseArmTimer = null;
        }, READER_CLOSE_ARM_DELAY_MS);
    }

    function hasExplicitReaderCloseIntent(options) {
        const source = cleanValue(options?.source).toLowerCase();
        const mode = cleanValue(options?.mode).toLowerCase();
        const launchMode = cleanValue(options?.launchMode).toLowerCase();
        const intent = cleanValue(options?.intent).toLowerCase();
        const action = cleanValue(options?.action).toLowerCase();

        return Boolean(
            options?.explicitClose === true ||
            options?.readerClose === true ||
            options?.closeReader === true ||
            options?.close === true ||
            launchMode === "reader_close" ||
            intent === "reader_close" ||
            intent === "close_reader" ||
            intent === "close" ||
            mode === "reader_close" ||
            mode === "close" ||
            action === "reader_close" ||
            action === "close_reader" ||
            action === "close" ||
            source.includes("reader_close") ||
            source.includes("close_reader") ||
            source.includes("reader_lifecycle_close")
        );
    }

    function isReaderCloseDisarmed(explorer, readerPanel) {
        return (
            explorer?.getAttribute("data-workspace-reader-close-armed") === "false" ||
            readerPanel?.getAttribute("data-workspace-reader-close-armed") === "false"
        );
    }

    function isReaderOpeningState(explorer, readerPanel) {
        const explorerState = cleanValue(
            explorer?.getAttribute("data-workspace-reader-state")
        ).toLowerCase();
        const panelState = cleanValue(
            readerPanel?.getAttribute("data-workspace-reader-state")
        ).toLowerCase();
        const openingStates = ["opening", "loading", "rendering"];

        return (
            openingStates.includes(explorerState) ||
            openingStates.includes(panelState)
        );
    }

    function shouldIgnoreReaderClose(explorer, readerPanel, options) {
        if (hasExplicitReaderCloseIntent(options)) {
            return false;
        }

        return (
            isReaderOpeningState(explorer, readerPanel) ||
            isReaderCloseDisarmed(explorer, readerPanel)
        );
    }

    function applyReaderRouteView(explorer, options) {
        const readerView = cleanValue(options?.readerWorkspaceView) || READER_WORKSPACE_VIEW;
        const viewPanelSelector = getSelector(options, "viewPanel", DEFAULT_WORKSPACE_VIEW_PANEL_SELECTOR);
        const viewButtonSelector = getSelector(options, "viewButton", DEFAULT_WORKSPACE_VIEW_BUTTON_SELECTOR);
        const readerPanel = getReaderPanel(explorer, options);

        if (!shouldUseServerReaderView(explorer, options)) {
            return;
        }

        explorer.setAttribute("data-workspace-view", readerView);

        explorer.querySelectorAll(viewPanelSelector).forEach(function (panel) {
            const isReaderPanel = panel.getAttribute("data-workspace-view-panel") === readerView;

            panel.hidden = !isReaderPanel;
            panel.setAttribute("aria-hidden", isReaderPanel ? "false" : "true");
        });

        explorer.querySelectorAll(viewButtonSelector).forEach(function (button) {
            const isActive = button.getAttribute("data-workspace-view") === readerView;

            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });

        setReaderCloseArmed(explorer, readerPanel, true);
    }

    function markReaderClosed(explorer, options) {
        const Conversation = getConversationApi(options);
        const readerPanel = getReaderPanel(explorer, options);

        clearReaderCloseArmTimer(explorer);

        if (Conversation && typeof Conversation.returnToFiles === "function") {
            Conversation.returnToFiles(explorer);
        }

        if (readerPanel) {
            readerPanel.setAttribute("data-workspace-reader-state", "closed");
            readerPanel.setAttribute("data-workspace-reader-close-armed", "false");
        }

        if (explorer?.getAttribute("data-workspace-reader-state") === "loading") {
            explorer.setAttribute("data-workspace-reader-state", "idle");
        } else if (explorer) {
            explorer.setAttribute("data-workspace-reader-state", "closed");
            explorer.setAttribute("data-workspace-reader-close-armed", "false");
        }
    }

    function closeReaderView(explorer, options) {
        const readerPanel = getReaderPanel(explorer, options);
        const backRoute = getReaderCloseBackRoute(explorer, options);

        if (!explorer) {
            return false;
        }

        if (shouldIgnoreReaderClose(explorer, readerPanel, options)) {
            return false;
        }

        clearReaderRouteHash();

        if (backRoute) {
            explorer.setAttribute("data-workspace-reader-state", "closing");

            if (readerPanel) {
                readerPanel.setAttribute("data-workspace-reader-state", "closing");
            }

            return loadRightPaneRoute(
                backRoute,
                Object.assign({}, options || {}, {
                    loadOptions: Object.assign(
                        {},
                        options?.loadOptions || {},
                        {
                            push: true,
                            async: true,
                            launchMode: "reader_close",
                            source: "workspace_document_reader_lifecycle",
                            backRoute
                        }
                    )
                })
            );
        }

        markReaderClosed(explorer, options);
        return true;
    }

    function restoreWorkspaceView(explorer, viewName, options) {
        const Conversation = getConversationApi(options);
        const readerView = cleanValue(options?.readerWorkspaceView) || READER_WORKSPACE_VIEW;
        const cleanView = shouldUseServerReaderView(explorer, options)
            ? readerView
            : normalizeWorkspaceView(viewName, options);

        if (!explorer) {
            return;
        }

        if (cleanView === readerView) {
            applyReaderRouteView(explorer, options);

            if (getCurrentWorkspaceView(explorer, options) === readerView) {
                return;
            }
        }

        if (getCurrentWorkspaceView(explorer, options) === cleanView) {
            return;
        }

        if (Conversation && typeof Conversation.setView === "function") {
            Conversation.setView(explorer, cleanView);
        }
    }

    function isReaderWorkspaceView(explorer, options) {
        const readerView = cleanValue(options?.readerWorkspaceView) || READER_WORKSPACE_VIEW;

        return getCurrentWorkspaceView(explorer, options) === readerView;
    }

    function buildReaderFragmentUrl(readerUrl, options) {
        const cleanReaderUrl = cleanValue(readerUrl);
        const readerRoutePattern = getReaderRoutePattern(options);
        const fragmentRoutePattern = getReaderFragmentRoutePattern(options);

        if (!cleanReaderUrl) {
            return "";
        }

        const parsedUrl = new URL(cleanReaderUrl, window.location.origin);

        if (parsedUrl.origin !== window.location.origin) {
            throw new Error("The reader URL is outside the current Solomon workspace.");
        }

        if (fragmentRoutePattern.test(parsedUrl.pathname)) {
            return `${parsedUrl.pathname}${parsedUrl.search}`;
        }

        if (!readerRoutePattern.test(parsedUrl.pathname)) {
            throw new Error("The server returned an unsupported reader route.");
        }

        return `${parsedUrl.pathname.replace(/\/+$/, "")}/fragment${parsedUrl.search}`;
    }

    async function fetchHtml(url) {
        const response = await fetch(url, {
            method: "GET",
            credentials: "same-origin",
            headers: {
                "Accept": "text/html",
                "X-Requested-With": "XMLHttpRequest"
            }
        });

        const text = await response.text();

        if (!response.ok) {
            throw new Error(text || "The reader fragment could not be loaded.");
        }

        return text;
    }

    function clearNode(node) {
        while (node?.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function storeReaderLaunchState(explorer, readerUrl, options) {
        const readerPanel = getReaderPanel(explorer, options);
        const backRoute = resolveReaderBackRoute(
            readerUrl,
            options,
            explorer
        );
        const cleanReaderUrl = buildReaderRouteWithBack(
            readerUrl,
            backRoute,
            options
        );

        if (!explorer) {
            return;
        }

        disarmReaderClose(explorer, readerPanel);

        if (cleanReaderUrl) {
            explorer.setAttribute("data-workspace-reader-url", cleanReaderUrl);
        }

        if (backRoute) {
            explorer.dataset.workspaceReaderBackRoute = backRoute;
            explorer.setAttribute("data-workspace-reader-back-route", backRoute);
            explorer.setAttribute("data-right-pane-content-back-route", backRoute);
        }

        explorer.setAttribute("data-right-pane-content-launch", "reader");

        if (readerPanel) {
            if (cleanReaderUrl) {
                readerPanel.setAttribute("data-workspace-reader-url", cleanReaderUrl);
            }

            if (backRoute) {
                readerPanel.setAttribute("data-workspace-reader-back-route", backRoute);
                readerPanel.setAttribute("data-right-pane-content-back-route", backRoute);
            }

            readerPanel.setAttribute("data-right-pane-content-launch", "reader");
        }
    }

    function syncReaderHistory(readerUrl, options) {
        const readerBackRoute = resolveReaderBackRoute(
            readerUrl,
            options,
            null
        );
        const cleanReaderRoute = buildReaderRouteWithBack(
            readerUrl,
            readerBackRoute,
            options
        );
        const historyMode = cleanValue(options?.historyMode || "push");
        const currentRoute = getCurrentRelativeRoute();
        const historyState = Object.assign(
            {},
            window.history?.state || {},
            {
                rightPaneContent: "reader",
                workspaceView: cleanValue(options?.readerWorkspaceView) || READER_WORKSPACE_VIEW,
                readerBackRoute
            }
        );

        if (
            !cleanReaderRoute ||
            !isWorkspaceReaderRoute(cleanReaderRoute, options) ||
            options?.updateHistory === false ||
            currentRoute === cleanReaderRoute ||
            !window.history
        ) {
            return false;
        }

        if (
            historyMode === "replace" &&
            typeof window.history.replaceState === "function"
        ) {
            window.history.replaceState(
                historyState,
                "",
                cleanReaderRoute
            );
            return true;
        }

        if (typeof window.history.pushState === "function") {
            window.history.pushState(
                historyState,
                "",
                cleanReaderRoute
            );
            return true;
        }

        return false;
    }

    function emitReaderFragmentLoaded(explorer, readerPanel, options) {
        const readerLoadedEvent = new CustomEvent("solomon:reader-fragment-loaded", {
            bubbles: true,
            detail: {
                explorer,
                readerPanel,
                readerUrl: getSameOriginRelativeRoute(options?.readerUrl),
                backRoute: resolveReaderBackRoute(
                    options?.readerUrl,
                    options,
                    explorer
                ),
                launchMode: cleanValue(options?.launchMode) || "reader"
            }
        });

        readerPanel.dispatchEvent(readerLoadedEvent);
        document.dispatchEvent(readerLoadedEvent);
    }

    function initializeInjectedReader(readerPanel, options) {
        const readerApi = options?.ReaderControls || window.SolomonWorkspaceDocumentReaderControls;

        if (!readerApi) {
            return;
        }

        if (typeof readerApi.initialize === "function") {
            readerApi.initialize(readerPanel);
            return;
        }

        if (typeof readerApi.bind === "function") {
            readerApi.bind(readerPanel);
            return;
        }

        if (typeof readerApi.bootstrap === "function") {
            readerApi.bootstrap();
        }
    }

    async function runReaderFragmentScripts(scripts) {
        for (const sourceScript of scripts) {
            await new Promise(function (resolve) {
                const script = document.createElement("script");

                Array.from(sourceScript.attributes).forEach(function (attribute) {
                    script.setAttribute(attribute.name, attribute.value);
                });

                script.async = false;

                if (sourceScript.src) {
                    script.onload = resolve;
                    script.onerror = resolve;
                }

                script.textContent = sourceScript.textContent || "";
                document.body.appendChild(script);

                if (!sourceScript.src) {
                    resolve();
                }
            });
        }
    }

    async function renderReaderFragmentIntoPanel(explorer, html, options) {
        const Conversation = getConversationApi(options);
        const readerPanel = getReaderPanel(explorer, options);
        const readerView = cleanValue(options?.readerWorkspaceView) || READER_WORKSPACE_VIEW;
        const template = document.createElement("template");

        if (!readerPanel) {
            throw new Error("The Documents workspace does not have a reader panel.");
        }

        disarmReaderClose(explorer, readerPanel);
        readerPanel.setAttribute("data-workspace-reader-state", "rendering");
        explorer.setAttribute("data-workspace-reader-state", "rendering");

        template.innerHTML = cleanValue(html);

        const scripts = Array.from(template.content.querySelectorAll("script"));

        scripts.forEach(function (script) {
            script.remove();
        });

        clearNode(readerPanel);
        readerPanel.appendChild(template.content);

        storeReaderLaunchState(explorer, options?.readerUrl, options);
        readerPanel.setAttribute("data-workspace-reader-state", "loaded");
        readerPanel.setAttribute("data-workspace-reader-document-id", cleanValue(options?.documentId));
        explorer.setAttribute("data-workspace-reader-state", "loaded");

        if (Conversation && typeof Conversation.clearFilesViewIntent === "function") {
            Conversation.clearFilesViewIntent(explorer);
        }

        if (Conversation && typeof Conversation.setView === "function") {
            Conversation.setView(explorer, readerView);
        }

        await runReaderFragmentScripts(scripts);
        initializeInjectedReader(readerPanel, options);
        emitReaderFragmentLoaded(explorer, readerPanel, options);

        window.requestAnimationFrame(function () {
            if (Conversation && typeof Conversation.setView === "function") {
                Conversation.setView(explorer, readerView);
            }

            scheduleReaderCloseArm(explorer, readerPanel);
        });
    }

    async function loadReaderFragment(explorer, readerUrl, options) {
        const readerPanel = getReaderPanel(explorer, options);
        const resolvedBackRoute = resolveReaderBackRoute(
            readerUrl,
            options,
            explorer
        );
        const cleanReaderUrl = buildReaderRouteWithBack(
            readerUrl,
            resolvedBackRoute,
            options
        );
        const readerFragmentUrl = buildReaderFragmentUrl(
            cleanReaderUrl || readerUrl,
            options
        );
        const loadOptions = Object.assign(
            {},
            options || {},
            {
                readerUrl: cleanReaderUrl || cleanValue(readerUrl),
                backRoute: resolvedBackRoute,
                launchMode: cleanValue(options?.launchMode) || "reader"
            }
        );

        clearReaderRouteHash();
        storeReaderLaunchState(explorer, cleanReaderUrl || readerUrl, loadOptions);
        explorer.setAttribute("data-workspace-reader-state", "loading");

        if (readerPanel) {
            readerPanel.setAttribute("data-workspace-reader-state", "loading");
        }

        const fragmentHtml = await fetchHtml(readerFragmentUrl);

        await renderReaderFragmentIntoPanel(explorer, fragmentHtml, loadOptions);
        syncReaderHistory(cleanReaderUrl || readerUrl, loadOptions);
    }

    function getServerReaderUrl(payload) {
        const viewerPacket = (
            payload?.result?.viewer_packet ||
            payload?.result?.panel?.payload ||
            payload?.workspace_context?.panels?.focused_panel?.payload ||
            null
        );

        return cleanValue(
            payload?.result?.reader_url ||
            payload?.result?.workspace_reader_url ||
            viewerPacket?.reader_url ||
            viewerPacket?.display?.reader_url ||
            viewerPacket?.display?.full_reader_url ||
            viewerPacket?.metadata?.extra?.reader_url ||
            viewerPacket?.metadata?.extra?.workspace_reader_url ||
            ""
        );
    }

    window.SolomonWorkspaceDocumentReaderLifecycle = Object.freeze({
        applyReaderRouteView,
        buildReaderFragmentUrl,
        clearReaderRouteHash,
        closeReaderView,
        emitReaderFragmentLoaded,
        fetchHtml,
        getCurrentWorkspaceView,
        getInitialWorkspaceView,
        getReaderCloseBackRoute,
        getReaderPanel,
        getServerReaderUrl,
        hasEmbeddedReaderSurface,
        initializeInjectedReader,
        isReaderRoute,
        isReaderWorkspaceView,
        isWorkspaceReaderRoute,
        loadReaderFragment,
        loadRightPaneRoute,
        normalizeSafeRightPaneRoute,
        normalizeWorkspaceView,
        renderReaderFragmentIntoPanel,
        restoreWorkspaceView,
        runReaderFragmentScripts,
        shouldUseServerReaderView,
        syncReaderHistory
    });
})();