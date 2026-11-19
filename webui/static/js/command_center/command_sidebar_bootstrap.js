/* -------------------------------------------------------------------
   FILE: command_sidebar_bootstrap.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const api = window.NationsCommandSidebar =
        window.NationsCommandSidebar || {};

    const DOCUMENTS_MODULE_ID = "documents";
    const DOCUMENTS_PATH = "/";
    const SOLOMON_AI_MODULE_ID = "solomon_ai";
    const SOLOMON_AI_PATH = "/ai";
    const PEOPLE_MODULE_ID = "people";
    const PEOPLE_PATH = "/people";
    const SEARCH_MODULE_ID = "search";
    const SEARCH_PATH = "/search";
    const READER_ROUTE_PATTERN = /^\/workspace\/(?:file|document)\/[^/]+\/reader\/?$/;
    const READER_FRAGMENT_ROUTE_PATTERN = /^\/workspace\/(?:file|document)\/[^/]+\/reader\/fragment\/?$/;
    const CONTEXT_RAIL_SELECTOR = ".solomon-context-rail";
    const DOCUMENT_INSPECTOR_CLEAR_EVENT =
        "solomon:document-inspector-clear";
    const WORKSPACE_LOADED_EVENT =
        "solomon:workspace-loaded";
    const WORKSPACE_WINDOW_CLOSE_SELECTOR =
        "[data-command-window-close='true']";
    const NAVBAR_UTILITY_TRIGGER_SELECTOR = [
        "[data-command-help-trigger]",
        "[data-command-account-trigger]"
    ].join(", ");
    const NAVBAR_UTILITY_MENU_SELECTOR = [
        "[data-command-help-menu]",
        "[data-command-account-menu]"
    ].join(", ");
    const NAVBAR_MENU_ITEM_SELECTOR = [
        "a[href]",
        "button:not([disabled])",
        "[role='menuitem']",
        "[tabindex]:not([tabindex='-1'])"
    ].join(", ");
    const COMMAND_SIDEBAR_SELECTOR = "#commandSidebar";
    const DOCUMENT_WORKSPACE_PATHS = new Set([
        "/",
        "/reports",
        "/recent",
        "/trash"
    ]);

    function shouldSubmitInputEvent(event) {
        return (
            event.key === "Enter" &&
            !event.isComposing &&
            !event.altKey &&
            !event.ctrlKey &&
            !event.metaKey &&
            !event.shiftKey
        );
    }

    function getFormTaskInput(form) {
        return form?.querySelector("input[name='task']") || null;
    }

    function getFormSendButton(form) {
        return form?.querySelector("button[type='submit']") || null;
    }

    function markFormHasValue(form, input) {
        if (!form || !input) {
            return;
        }

        form.setAttribute(
            "data-solomon-has-value",
            String(input.value || "").trim() ? "true" : "false"
        );
    }

    function prepareInputElement(input, placeholder) {
        if (!input) {
            return;
        }

        input.disabled = false;
        input.setAttribute("spellcheck", "false");
        input.setAttribute("autocapitalize", "off");
        input.setAttribute("autocomplete", "off");
        input.setAttribute("autocorrect", "off");

        if (placeholder) {
            input.placeholder = placeholder;
        }
    }

    function prepareSendButton(send) {
        if (!send) {
            return;
        }

        send.disabled = false;
        send.setAttribute(
            "aria-label",
            "Send message to AI assistant"
        );
        send.setAttribute(
            "title",
            "Send message to AI assistant"
        );
    }

    function submitCurrentFormCommand(form) {
        const liveInput = getFormTaskInput(form);

        if (!form || !liveInput) {
            return;
        }

        api.submitSolomonCommand(form, liveInput);
    }

    function isWorkspaceViewControl(explorer, element) {
        if (!explorer || !element || element === explorer) {
            return false;
        }

        if (!explorer.contains(element)) {
            return false;
        }

        return (
            element.classList.contains(
                "workspace-document-view-button"
            ) ||
            element.hasAttribute(
                "data-solomon-conversation-resume"
            )
        );
    }

    function initializeContextRail() {
        if (typeof api.initializeContextRail !== "function") {
            return null;
        }

        return api.initializeContextRail();
    }

    function dispatchWorkspaceLoaded(root, moduleId, url, options) {
        const eventRoot = root && typeof root.querySelectorAll === "function"
            ? root
            : document;
        const cleanOptions = options || {};
        const detail = {
            source: cleanOptionValue(cleanOptions.source) ||
                "command_sidebar_bootstrap",
            moduleId: cleanOptionValue(moduleId) || DOCUMENTS_MODULE_ID,
            launchMode: cleanOptionValue(cleanOptions.launchMode),
            async: cleanOptions.async !== false,
            root: eventRoot,
            mount: eventRoot,
            url: url instanceof URL
                ? getBrowserRelativeUrl(url)
                : cleanOptionValue(url)
        };

        document.dispatchEvent(
            new CustomEvent(
                WORKSPACE_LOADED_EVENT,
                { detail }
            )
        );
    }

    function normalizeRoutePath(pathname) {
        const cleanPath = String(pathname || "/")
            .trim()
            .replace(/\/+$/, "");

        return cleanPath || "/";
    }

    function isSolomonAiWorkspacePath(pathname) {
        const cleanPath = normalizeRoutePath(pathname);

        return (
            cleanPath === SOLOMON_AI_PATH ||
            cleanPath.startsWith(
                `${SOLOMON_AI_PATH}/c/`
            )
        );
    }

    function isPeopleWorkspacePath(pathname) {
        const cleanPath = normalizeRoutePath(pathname);

        return (
            cleanPath === PEOPLE_PATH ||
            cleanPath.startsWith(`${PEOPLE_PATH}/`)
        );
    }

    function isWorkspaceShellPath(pathname) {
        const cleanPath = normalizeRoutePath(pathname);

        return (
            DOCUMENT_WORKSPACE_PATHS.has(cleanPath) ||
            cleanPath === SEARCH_PATH ||
            isSolomonAiWorkspacePath(cleanPath) ||
            isPeopleWorkspacePath(cleanPath) ||
            cleanPath.startsWith("/workspace/file/") ||
            cleanPath.startsWith("/workspace/document/")
        );
    }

    function getNavbarUtilityMenu(trigger) {
        const menuId = String(
            trigger?.getAttribute("aria-controls") || ""
        ).trim();

        if (!menuId) {
            return null;
        }

        return document.getElementById(menuId);
    }

    function getNavbarUtilityTrigger(menu) {
        const menuId = String(menu?.id || "").trim();

        if (!menuId) {
            return null;
        }

        return document.querySelector(
            `${NAVBAR_UTILITY_TRIGGER_SELECTOR}[aria-controls="${CSS.escape(menuId)}"]`
        );
    }

    function getNavbarMenuItems(menu) {
        return Array.from(
            menu?.querySelectorAll(
                NAVBAR_MENU_ITEM_SELECTOR
            ) || []
        ).filter(function (item) {
            return (
                !item.hidden &&
                item.getAttribute("aria-hidden") !== "true" &&
                item.getAttribute("aria-disabled") !== "true"
            );
        });
    }

    function isNavbarUtilityExpanded(trigger, menu) {
        return Boolean(
            trigger &&
            menu &&
            trigger.getAttribute("aria-expanded") === "true" &&
            !menu.hidden
        );
    }

    function closeNavbarUtility(trigger, options) {
        const menu = getNavbarUtilityMenu(trigger);

        if (!trigger || !menu) {
            return false;
        }

        trigger.setAttribute("aria-expanded", "false");
        menu.hidden = true;
        menu.setAttribute("aria-hidden", "true");

        if (options?.restoreFocus === true) {
            trigger.focus({
                preventScroll: true
            });
        }

        return true;
    }

    function closeAllNavbarUtilities(options) {
        const exceptTrigger =
            options?.exceptTrigger || null;
        const restoreTrigger =
            options?.restoreTrigger || null;

        document.querySelectorAll(
            NAVBAR_UTILITY_TRIGGER_SELECTOR
        ).forEach(function (trigger) {
            if (trigger === exceptTrigger) {
                return;
            }

            closeNavbarUtility(trigger, {
                restoreFocus:
                    trigger === restoreTrigger
            });
        });
    }

    function focusNavbarUtilityMenu(menu) {
        if (!menu) {
            return;
        }

        const menuItems = getNavbarMenuItems(menu);

        window.requestAnimationFrame(function () {
            if (menu.hidden) {
                return;
            }

            if (menuItems.length) {
                menuItems[0].focus({
                    preventScroll: true
                });
                return;
            }

            if (!menu.hasAttribute("tabindex")) {
                menu.setAttribute("tabindex", "-1");
            }

            menu.focus({
                preventScroll: true
            });
        });
    }

    function openNavbarUtility(trigger, options) {
        const menu = getNavbarUtilityMenu(trigger);

        if (!trigger || !menu) {
            return false;
        }

        closeAllNavbarUtilities({
            exceptTrigger: trigger
        });

        trigger.setAttribute("aria-expanded", "true");
        menu.hidden = false;
        menu.setAttribute("aria-hidden", "false");

        if (options?.focusMenu === true) {
            focusNavbarUtilityMenu(menu);
        }

        return true;
    }

    function toggleNavbarUtility(trigger, options) {
        const menu = getNavbarUtilityMenu(trigger);

        if (!trigger || !menu) {
            return false;
        }

        if (isNavbarUtilityExpanded(trigger, menu)) {
            return closeNavbarUtility(trigger, {
                restoreFocus:
                    options?.restoreFocus === true
            });
        }

        return openNavbarUtility(trigger, {
            focusMenu:
                options?.focusMenu === true
        });
    }

    function handleNavbarMenuKeyboard(event, menu) {
        const menuItems = getNavbarMenuItems(menu);

        if (event.key === "Escape") {
            const trigger =
                getNavbarUtilityTrigger(menu);

            event.preventDefault();
            event.stopPropagation();

            if (trigger) {
                closeNavbarUtility(trigger, {
                    restoreFocus: true
                });
            }

            return;
        }

        if (!menuItems.length) {
            return;
        }

        const currentIndex = menuItems.indexOf(
            document.activeElement
        );

        if (
            event.key !== "ArrowDown" &&
            event.key !== "ArrowUp" &&
            event.key !== "Home" &&
            event.key !== "End"
        ) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        let nextIndex = currentIndex;

        if (event.key === "Home") {
            nextIndex = 0;
        } else if (event.key === "End") {
            nextIndex = menuItems.length - 1;
        } else if (event.key === "ArrowDown") {
            nextIndex =
                currentIndex >= menuItems.length - 1
                    ? 0
                    : currentIndex + 1;
        } else {
            nextIndex =
                currentIndex <= 0
                    ? menuItems.length - 1
                    : currentIndex - 1;
        }

        menuItems[nextIndex].focus({
            preventScroll: true
        });
    }

    function getWorkspaceModuleForUrl(
        url,
        fallbackModuleId
    ) {
        const targetUrl = new URL(
            url,
            window.location.origin
        );
        const pathname = normalizeRoutePath(
            targetUrl.pathname
        );
        const cleanFallback = String(
            fallbackModuleId || ""
        )
            .trim()
            .toLowerCase();

        if (isSolomonAiWorkspacePath(pathname)) {
            return SOLOMON_AI_MODULE_ID;
        }

        if (isPeopleWorkspacePath(pathname)) {
            return PEOPLE_MODULE_ID;
        }

        if (pathname === SEARCH_PATH) {
            return SEARCH_MODULE_ID;
        }

        if (
            DOCUMENT_WORKSPACE_PATHS.has(pathname) ||
            pathname.startsWith("/workspace/file/") ||
            pathname.startsWith("/workspace/document/")
        ) {
            return DOCUMENTS_MODULE_ID;
        }

        if (
            cleanFallback === "home" ||
            cleanFallback === "docs" ||
            cleanFallback === DOCUMENTS_MODULE_ID
        ) {
            return DOCUMENTS_MODULE_ID;
        }

        if (cleanFallback === SOLOMON_AI_MODULE_ID) {
            return SOLOMON_AI_MODULE_ID;
        }

        if (cleanFallback === PEOPLE_MODULE_ID) {
            return PEOPLE_MODULE_ID;
        }

        if (cleanFallback === SEARCH_MODULE_ID) {
            return SEARCH_MODULE_ID;
        }

        return cleanFallback || DOCUMENTS_MODULE_ID;
    }

    function getCanonicalWorkspaceUrl(
        response,
        fallbackUrl
    ) {
        const responseUrl = new URL(
            response?.url || fallbackUrl.href,
            window.location.origin
        );

        responseUrl.searchParams.delete("partial");

        return responseUrl;
    }

    function getWorkspaceRequestUrl(url) {
        const requestUrl = new URL(
            url,
            window.location.origin
        );

        requestUrl.searchParams.delete("partial");

        return requestUrl;
    }

    function getBrowserRelativeUrl(url) {
        return (
            `${url.pathname}` +
            `${url.search}` +
            `${url.hash}`
        );
    }

    function getCurrentBrowserRelativeUrl() {
        return (
            `${window.location.pathname}` +
            `${window.location.search}` +
            `${window.location.hash}`
        );
    }

    function cleanOptionValue(value) {
        return String(value || "").trim();
    }

    function isReaderWorkspaceUrl(url) {
        const targetUrl = new URL(
            url,
            window.location.origin
        );
        const pathname = normalizeRoutePath(
            targetUrl.pathname
        );

        return (
            READER_ROUTE_PATTERN.test(pathname) ||
            READER_FRAGMENT_ROUTE_PATTERN.test(pathname)
        );
    }

    function normalizeRightPaneBackRoute(route) {
        const cleanRoute = cleanOptionValue(route);
        let targetUrl = null;

        if (!cleanRoute) {
            return "";
        }

        try {
            targetUrl = new URL(
                cleanRoute,
                window.location.origin
            );
        } catch (_error) {
            return "";
        }

        if (
            targetUrl.origin !==
            window.location.origin
        ) {
            return "";
        }

        if (isReaderWorkspaceUrl(targetUrl)) {
            return "";
        }

        return getBrowserRelativeUrl(targetUrl);
    }

    function getRightPaneContentMode(url, options) {
        const launchMode = cleanOptionValue(options?.launchMode);

        if (launchMode === "reader" || isReaderWorkspaceUrl(url)) {
            return "reader";
        }

        if (launchMode) {
            return launchMode;
        }

        return "workspace";
    }

    function buildWorkspaceHistoryState(moduleId, canonicalUrl, options) {
        const cleanOptions = options || {};
        const historyState = Object.assign(
            {},
            window.history?.state || {},
            {
                moduleId,
                solomonWorkspaceNavigation: true,
                rightPaneContent: getRightPaneContentMode(
                    canonicalUrl,
                    cleanOptions
                ),
                async: true
            }
        );
        const source = cleanOptionValue(cleanOptions.source);
        const launchMode = cleanOptionValue(cleanOptions.launchMode);
        const backRoute = normalizeRightPaneBackRoute(
            cleanOptions.backRoute
        );

        if (source) {
            historyState.source = source;
        }

        if (launchMode) {
            historyState.launchMode = launchMode;
        }

        if (backRoute) {
            historyState.backRoute = backRoute;
        }

        return historyState;
    }

    function fallbackToWorkspaceUrl(url, reason) {
        const fallbackUrl = getWorkspaceRequestUrl(url);

        if (api.state.workspaceHardNavigationCommitted === true) {
            return false;
        }

        api.state.workspaceHardNavigationCommitted = true;

        if (reason) {
            console.warn(
                "[WORKSPACE_NAVIGATION] Falling back to hard navigation.",
                reason
            );
        }

        window.location.assign(
            fallbackUrl.href
        );

        return false;
    }

    function syncRightPaneContentState(url, options) {
        const contentMode = getRightPaneContentMode(
            url,
            options
        );

        document.documentElement.setAttribute(
            "data-right-pane-content",
            contentMode
        );

        if (contentMode === "reader") {
            document.documentElement.setAttribute(
                "data-right-pane-reader-active",
                "true"
            );
            return;
        }

        document.documentElement.setAttribute(
            "data-right-pane-reader-active",
            "false"
        );
    }

    function shouldPreserveDocumentInspectorForNavigation(
        url,
        options
    ) {
        return (
            getRightPaneContentMode(
                url,
                options
            ) === "reader"
        );
    }


    function dispatchDocumentInspectorClear(reason) {
        document.dispatchEvent(
            new CustomEvent(
                DOCUMENT_INSPECTOR_CLEAR_EVENT,
                {
                    detail: {
                        source: "command_sidebar_bootstrap",
                        reason,
                        clearSelection: true
                    }
                }
            )
        );
    }


    function clearDocumentInspectorForNavigation(
        url,
        options
    ) {
        const reason =
            cleanOptionValue(options?.source) ||
            "workspace_navigation";
        let handledByContextRail = false;

        if (
            shouldPreserveDocumentInspectorForNavigation(
                url,
                options
            )
        ) {
            return;
        }

        if (typeof api.closeContextRail === "function") {
            try {
                api.closeContextRail({
                    reason,
                    clearSource: true,
                    clearSelection: true
                });
                handledByContextRail = true;
            } catch (error) {
                console.warn(
                    "[WORKSPACE_NAVIGATION] Unable to close document inspector rail.",
                    error
                );
            }
        }

        if (
            !handledByContextRail &&
            typeof api.clearContextRailSource === "function"
        ) {
            try {
                api.clearContextRailSource({
                    reason,
                    clearSelection: true
                });
                handledByContextRail = true;
            } catch (error) {
                console.warn(
                    "[WORKSPACE_NAVIGATION] Unable to clear document inspector source.",
                    error
                );
            }
        }

        if (!handledByContextRail) {
            dispatchDocumentInspectorClear(reason);
        }
    }


    function syncSolomonLauncherState(moduleId) {
        const launcher = document.getElementById(
            "commandSolomonLauncher"
        );
        const isActive =
            moduleId === SOLOMON_AI_MODULE_ID;

        if (!launcher) {
            return;
        }

        launcher.classList.toggle(
            "is-active",
            isActive
        );
        launcher.setAttribute(
            "data-command-navigation-state",
            isActive ? "active" : "available"
        );
        launcher.setAttribute(
            "data-solomon-toggle-state",
            isActive ? "open" : "closed"
        );
        launcher.setAttribute(
            "href",
            isActive
                ? DOCUMENTS_PATH
                : SOLOMON_AI_PATH
        );
        launcher.setAttribute(
            "data-command-module",
            isActive
                ? DOCUMENTS_MODULE_ID
                : SOLOMON_AI_MODULE_ID
        );

        launcher.removeAttribute("aria-disabled");
        launcher.removeAttribute("tabindex");

        if (isActive) {
            launcher.setAttribute(
                "aria-current",
                "page"
            );
            launcher.setAttribute(
                "title",
                "Close AI"
            );
            launcher.setAttribute(
                "aria-label",
                "Close AI"
            );
            return;
        }

        launcher.removeAttribute("aria-current");
        launcher.setAttribute("title", "Ask AI");
        launcher.setAttribute(
            "aria-label",
            "Ask AI"
        );
    }

    function suspendContextRailForWorkspace(rail) {
        if (!rail) {
            return;
        }

        if (
            rail.getAttribute(
                "data-workspace-route-hidden"
            ) !== "true"
        ) {
            rail.setAttribute(
                "data-workspace-route-hidden",
                "true"
            );
            rail.setAttribute(
                "data-workspace-route-previous-hidden",
                rail.hidden ? "true" : "false"
            );
            rail.setAttribute(
                "data-workspace-route-previous-inert",
                rail.hasAttribute("inert")
                    ? "true"
                    : "false"
            );
        }

        rail.hidden = true;
        rail.setAttribute("inert", "");
    }

    function restoreContextRailForWorkspace(rail) {
        if (
            !rail ||
            rail.getAttribute(
                "data-workspace-route-hidden"
            ) !== "true"
        ) {
            return;
        }

        const wasHidden =
            rail.getAttribute(
                "data-workspace-route-previous-hidden"
            ) === "true";
        const wasInert =
            rail.getAttribute(
                "data-workspace-route-previous-inert"
            ) === "true";

        rail.hidden = wasHidden;

        if (wasInert) {
            rail.setAttribute("inert", "");
        } else {
            rail.removeAttribute("inert");
        }

        rail.removeAttribute(
            "data-workspace-route-hidden"
        );
        rail.removeAttribute(
            "data-workspace-route-previous-hidden"
        );
        rail.removeAttribute(
            "data-workspace-route-previous-inert"
        );
    }

    function supportsDocumentInspectorRail(moduleId) {
        return (
            moduleId === DOCUMENTS_MODULE_ID ||
            moduleId === SEARCH_MODULE_ID
        );
    }

    function syncContextRailAvailability(moduleId) {
        const inspectorRailAvailable =
            supportsDocumentInspectorRail(moduleId);

        document.querySelectorAll(
            CONTEXT_RAIL_SELECTOR
        ).forEach(function (rail) {
            if (inspectorRailAvailable) {
                restoreContextRailForWorkspace(rail);
                return;
            }

            suspendContextRailForWorkspace(rail);
        });
    }

    function syncPersistentShellState(moduleId) {
        const inspectorRailAvailable =
            supportsDocumentInspectorRail(moduleId);
        const railState = inspectorRailAvailable
            ? "collapsed"
            : "unavailable";
        const portalRoot =
            document.getElementById("portal-root");
        const commandLayout = document.querySelector(
            ".command-center-layout"
        );
        const commandContentLayer =
            document.querySelector(
                "[data-command-content-layer]"
            );

        [
            portalRoot,
            commandLayout,
            commandContentLayer
        ].forEach(function (element) {
            if (!element) {
                return;
            }

            element.setAttribute(
                "data-solomon-rail-state",
                railState
            );
        });

        document.documentElement.setAttribute(
            "data-solomon-ai-workspace-active",
            moduleId === SOLOMON_AI_MODULE_ID
                ? "true"
                : "false"
        );

        syncContextRailAvailability(moduleId);
        syncSolomonLauncherState(moduleId);
    }

    function shouldUseViewTransition() {
        if (
            typeof document.startViewTransition !==
            "function"
        ) {
            return false;
        }

        if (document.hidden === true) {
            return false;
        }

        if (
            typeof document.visibilityState === "string" &&
            document.visibilityState !== "visible"
        ) {
            return false;
        }

        return !window.matchMedia(
            "(prefers-reduced-motion: reduce)"
        ).matches;
    }

    async function replaceWorkspaceWithTransition(
        html,
        moduleId,
        options
    ) {
        let replaced = false;

        const replaceContent = function () {
            replaced = api.replaceWorkspaceContent(
                html,
                moduleId,
                options
            );
        };

        if (!shouldUseViewTransition()) {
            replaceContent();
            return replaced;
        }

        try {
            const transition =
                document.startViewTransition(
                    replaceContent
                );

            await transition.updateCallbackDone;
        } catch (_error) {
            if (!replaced) {
                replaceContent();
            }
        }

        return replaced;
    }

    function isSolomonAiNavigationAnchor(link) {
        if (!(link instanceof HTMLAnchorElement)) {
            return false;
        }

        const targetUrl = new URL(
            link.href,
            window.location.origin
        );
        const pathname = normalizeRoutePath(
            targetUrl.pathname
        );

        return (
            isSolomonAiWorkspacePath(pathname) ||
            link.classList.contains(
                "solomon-ai-workspace__close"
            ) ||
            link.hasAttribute(
                "data-solomon-ai-navigation"
            )
        );
    }

    function isCommandSidebarNavigationAnchor(link) {
        return Boolean(
            link instanceof HTMLAnchorElement &&
            link.closest(COMMAND_SIDEBAR_SELECTOR)
        );
    }

    function isWorkspaceShellNavigationAnchor(link) {
        if (!(link instanceof HTMLAnchorElement)) {
            return false;
        }

        const targetUrl = new URL(
            link.href,
            window.location.origin
        );
        const pathname = normalizeRoutePath(
            targetUrl.pathname
        );
        const moduleId = String(
            link.getAttribute(
                "data-command-module"
            ) || ""
        )
            .trim()
            .toLowerCase();
        const shellNavigation =
            link.getAttribute(
                "data-command-shell-navigation"
            ) === "true";

        if (isSolomonAiNavigationAnchor(link)) {
            return true;
        }

        if (!isWorkspaceShellPath(pathname)) {
            return false;
        }

        if (isCommandSidebarNavigationAnchor(link)) {
            return true;
        }

        if (shellNavigation) {
            return true;
        }

        if (
            pathname === DOCUMENTS_PATH &&
            (
                moduleId === DOCUMENTS_MODULE_ID ||
                moduleId === "home" ||
                moduleId === "docs"
            )
        ) {
            return true;
        }

        if (
            isPeopleWorkspacePath(pathname) &&
            (
                moduleId === PEOPLE_MODULE_ID ||
                moduleId === PEOPLE_MODULE_ID
            )
        ) {
            return true;
        }

        return false;
    }

    function hasMountedDocumentExplorer() {
        return Boolean(
            document.querySelector(
                api.constants
                    .DOCUMENT_EXPLORER_SELECTOR
            )
        );
    }

    function initializeDocumentNewMenus(scope) {
        const sectionNavigation =
            window.SolomonWorkspaceDocumentSectionNavigation;
        const root = scope && typeof scope.querySelectorAll === "function"
            ? scope
            : document;

        if (
            !sectionNavigation ||
            typeof sectionNavigation.bindDocumentNewMenu !== "function"
        ) {
            return false;
        }

        const explorers = Array.from(
            root.querySelectorAll(
                "[data-document-explorer], .workspace-document-explorer"
            ) || []
        );

        if (
            root instanceof Element &&
            (
                root.matches("[data-document-explorer]") ||
                root.matches(".workspace-document-explorer")
            )
        ) {
            explorers.unshift(root);
        }

        let didBind = false;

        explorers.forEach(function (explorer) {
            if (!explorer.querySelector("[data-document-new-menu]")) {
                return;
            }

            sectionNavigation.bindDocumentNewMenu(explorer);
            didBind = true;
        });

        return didBind;
    }

    function initializeMountedWorkspaceControls(scope) {
        const root = scope && typeof scope.querySelectorAll === "function"
            ? scope
            : document;

        initializeDocumentNewMenus(root);

        if (
            typeof api.initializeWorkspaceListingControls ===
            "function"
        ) {
            api.initializeWorkspaceListingControls(root);
        }

        if (
            typeof api.refreshWorkspaceListingControls ===
            "function"
        ) {
            api.refreshWorkspaceListingControls(root);
        }

        if (typeof api.initializeGlobalSearch === "function") {
            api.initializeGlobalSearch();
        }

        if (typeof api.initializeWorkspaceViewControls === "function") {
            api.initializeWorkspaceViewControls();
        }

        if (typeof api.bindWorkspaceConversationSurface === "function") {
            api.bindWorkspaceConversationSurface();
        }

        if (typeof api.syncSolomonHistoryState === "function") {
            api.syncSolomonHistoryState();
        }

        if (
            window.NationsPeople &&
            typeof window.NationsPeople.initialize === "function"
        ) {
            window.NationsPeople.initialize(root);
        }

        return true;
    }

    function handleWorkspaceWindowCloseClick(event) {
        if (
            api.isModifiedNavigationEvent(
                event
            )
        ) {
            return false;
        }

        const target =
            event.target instanceof Element
                ? event.target
                : null;
        const closeControl =
            target?.closest(
                WORKSPACE_WINDOW_CLOSE_SELECTOR
            ) || null;

        if (!closeControl) {
            return false;
        }

        event.preventDefault();
        event.stopPropagation();

        if (
            typeof event.stopImmediatePropagation ===
            "function"
        ) {
            event.stopImmediatePropagation();
        }

        api.loadWorkspace(
            DOCUMENTS_PATH,
            DOCUMENTS_MODULE_ID,
            {
                push: true,
                async: true,
                launchMode: "workspace_window_close",
                source: "command_sidebar_bootstrap"
            }
        );

        return true;
    }

    function handleWorkspaceShellNavigationClick(event) {
        if (
            api.isModifiedNavigationEvent(
                event
            )
        ) {
            return false;
        }

        const target =
            event.target instanceof Element
                ? event.target
                : null;
        const link =
            target?.closest(
                "a[href][data-command-shell-navigation='true']"
            ) || null;

        if (
            !link ||
            !api.isEligibleWorkspaceLink(
                link
            ) ||
            !isWorkspaceShellNavigationAnchor(
                link
            ) ||
            isCommandSidebarNavigationAnchor(
                link
            )
        ) {
            return false;
        }

        event.preventDefault();
        event.stopPropagation();

        if (
            typeof event.stopImmediatePropagation ===
            "function"
        ) {
            event.stopImmediatePropagation();
        }

        api.loadWorkspace(
            link.href,
            getWorkspaceModuleForUrl(
                link.href,
                link.getAttribute(
                    "data-command-module"
                )
            ),
            {
                push: true,
                async: true,
                launchMode: getRightPaneContentMode(
                    link.href,
                    {
                        launchMode: link.getAttribute(
                            "data-right-pane-content-launch"
                        )
                    }
                ),
                source: "command_sidebar_bootstrap"
            }
        );

        return true;
    }

    api.initializeTaskbarInputInteraction =
        function () {
            const c = api.constants;
            const form = document.querySelector(
                c.TASKBAR_FORM_SELECTOR
            );
            const input = form?.querySelector(
                c.TASKBAR_INPUT_SELECTOR
            );
            const send = getFormSendButton(form);

            if (!form || !input) {
                return input || null;
            }

            api.applyTaskbarContractAttributes(form);
            form.removeAttribute("inert");
            prepareInputElement(
                input,
                c.TASKBAR_PLACEHOLDER
            );
            prepareSendButton(send);

            if (
                form.getAttribute(
                    "data-solomon-taskbar-bound"
                ) === "true"
            ) {
                return input;
            }

            form.setAttribute(
                "data-solomon-taskbar-bound",
                "true"
            );

            form.addEventListener(
                "pointerdown",
                function (event) {
                    const liveInput =
                        getFormTaskInput(form);

                    if (
                        !liveInput ||
                        api.isTaskbarPending(form) ||
                        event.target.closest("button")
                    ) {
                        return;
                    }

                    if (event.target !== liveInput) {
                        event.preventDefault();
                    }

                    form.setAttribute(
                        "data-solomon-command-interacting",
                        "true"
                    );

                    window.requestAnimationFrame(
                        function () {
                            api.focusTaskbarInput({
                                select: false
                            });
                        }
                    );
                }
            );

            form.addEventListener(
                "focusin",
                function () {
                    form.setAttribute(
                        "data-solomon-command-interacting",
                        "true"
                    );
                }
            );

            form.addEventListener(
                "focusout",
                function () {
                    window.setTimeout(function () {
                        if (
                            !form.contains(
                                document.activeElement
                            )
                        ) {
                            form.setAttribute(
                                "data-solomon-command-interacting",
                                "false"
                            );
                        }
                    }, 0);
                }
            );

            form.addEventListener(
                "submit",
                function (event) {
                    event.preventDefault();
                    event.stopPropagation();
                    submitCurrentFormCommand(form);
                }
            );

            input.addEventListener(
                "input",
                function (event) {
                    event.stopPropagation();
                    markFormHasValue(
                        form,
                        event.currentTarget
                    );
                }
            );

            input.addEventListener(
                "keydown",
                function (event) {
                    event.stopPropagation();

                    if (shouldSubmitInputEvent(event)) {
                        event.preventDefault();
                        submitCurrentFormCommand(form);
                        return;
                    }

                    if (event.key !== "Escape") {
                        return;
                    }

                    const liveInput =
                        event.currentTarget;

                    if (liveInput.value) {
                        liveInput.value = "";
                        markFormHasValue(
                            form,
                            liveInput
                        );
                        return;
                    }

                    liveInput.blur();
                }
            );

            [
                "beforeinput",
                "keyup",
                "keypress"
            ].forEach(function (eventName) {
                input.addEventListener(
                    eventName,
                    function (event) {
                        event.stopPropagation();
                    }
                );
            });

            return input;
        };

    api.initializeWorkspaceConversationInputInteraction =
        function () {
            const elements =
                api.getWorkspaceConversationElements();
            const form = elements.form;
            const input = elements.input;
            const send = getFormSendButton(form);

            if (!form || !input) {
                return input || null;
            }

            prepareInputElement(input);
            prepareSendButton(send);

            if (
                form.getAttribute(
                    "data-solomon-workspace-form-bound"
                ) === "true"
            ) {
                return input;
            }

            form.setAttribute(
                "data-solomon-workspace-form-bound",
                "true"
            );

            form.addEventListener(
                "submit",
                function (event) {
                    event.preventDefault();
                    event.stopPropagation();
                    submitCurrentFormCommand(form);
                }
            );

            input.addEventListener(
                "input",
                function (event) {
                    event.stopPropagation();
                    markFormHasValue(
                        form,
                        event.currentTarget
                    );
                }
            );

            input.addEventListener(
                "keydown",
                function (event) {
                    event.stopPropagation();

                    if (
                        shouldSubmitInputEvent(event)
                    ) {
                        event.preventDefault();
                        submitCurrentFormCommand(form);
                        return;
                    }

                    if (event.key !== "Escape") {
                        return;
                    }

                    const liveInput =
                        event.currentTarget;

                    if (liveInput.value) {
                        liveInput.value = "";
                        markFormHasValue(
                            form,
                            liveInput
                        );
                        return;
                    }

                    api.focusTaskbarInput({
                        select: false
                    });
                }
            );

            [
                "beforeinput",
                "keyup",
                "keypress"
            ].forEach(function (eventName) {
                input.addEventListener(
                    eventName,
                    function (event) {
                        event.stopPropagation();
                    }
                );
            });

            return input;
        };

    api.initializeTaskbarOutputContract =
        function () {
            const output = document.querySelector(
                api.constants
                    .TASKBAR_OUTPUT_SELECTOR
            );

            if (!output) {
                return null;
            }

            output.setAttribute(
                "data-solomon-output-contract",
                api.constants
                    .HOME_CONVERSATION_CONTRACT
            );
            api.clearTaskbarOutput();

            return output;
        };

    api.initializeWorkspaceViewControls =
        function () {
            const c = api.constants;
            const viewElements =
                api.getWorkspaceViewElements();

            if (
                !viewElements.explorer ||
                viewElements.explorer.getAttribute(
                    "data-workspace-view-controls-bound"
                ) === "true"
            ) {
                return;
            }

            viewElements.explorer.setAttribute(
                "data-workspace-view-controls-bound",
                "true"
            );

            viewElements.explorer.addEventListener(
                "click",
                function (event) {
                    const button =
                        event.target.closest(
                            c.WORKSPACE_VIEW_BUTTON_SELECTOR
                        );

                    if (
                        !isWorkspaceViewControl(
                            viewElements.explorer,
                            button
                        )
                    ) {
                        return;
                    }

                    const targetView = String(
                        button.getAttribute(
                            "data-workspace-view"
                        ) || "files"
                    )
                        .trim()
                        .toLowerCase();

                    event.preventDefault();

                    if (targetView === "chat") {
                        api.openWorkspaceConversation({
                            focusInput: true
                        });
                        return;
                    }

                    if (targetView === "files") {
                        api.restoreWorkspaceSnapshot();
                        return;
                    }

                    if (targetView === "preview") {
                        api.setWorkspaceView("preview");
                    }
                }
            );

            api.setWorkspaceView("files");
        };

    api.initializeReturnToFilesControls =
        function () {
            if (api.state.returnToFilesBound) {
                return;
            }

            api.state.returnToFilesBound = true;

            document.addEventListener(
                "click",
                function (event) {
                    const button =
                        event.target.closest(
                            api.constants
                                .TASKBAR_RETURN_TO_FILES_SELECTOR
                        );

                    if (!button) {
                        return;
                    }

                    event.preventDefault();
                    api.restoreWorkspaceSnapshot();
                }
            );
        };

    api.initializeNavbarUtilities = function () {
        const triggers = Array.from(
            document.querySelectorAll(
                NAVBAR_UTILITY_TRIGGER_SELECTOR
            )
        );

        if (!triggers.length) {
            return false;
        }

        triggers.forEach(function (trigger) {
            const menu = getNavbarUtilityMenu(trigger);

            if (!menu) {
                return;
            }

            trigger.setAttribute(
                "aria-expanded",
                isNavbarUtilityExpanded(
                    trigger,
                    menu
                )
                    ? "true"
                    : "false"
            );
            menu.setAttribute(
                "aria-hidden",
                menu.hidden ? "true" : "false"
            );

            if (
                trigger.getAttribute(
                    "data-command-utility-bound"
                ) === "true"
            ) {
                return;
            }

            trigger.setAttribute(
                "data-command-utility-bound",
                "true"
            );

            trigger.addEventListener(
                "click",
                function (event) {
                    event.preventDefault();
                    event.stopPropagation();

                    toggleNavbarUtility(trigger, {
                        focusMenu: false
                    });
                }
            );

            trigger.addEventListener(
                "keydown",
                function (event) {
                    if (event.key === "Escape") {
                        if (
                            isNavbarUtilityExpanded(
                                trigger,
                                menu
                            )
                        ) {
                            event.preventDefault();
                            event.stopPropagation();

                            closeNavbarUtility(
                                trigger,
                                {
                                    restoreFocus: true
                                }
                            );
                        }

                        return;
                    }

                    if (
                        event.key !== "ArrowDown" &&
                        event.key !== "ArrowUp"
                    ) {
                        return;
                    }

                    event.preventDefault();
                    event.stopPropagation();

                    openNavbarUtility(trigger, {
                        focusMenu: true
                    });
                }
            );

            menu.addEventListener(
                "click",
                function (event) {
                    event.stopPropagation();

                    if (
                        event.target.closest(
                            "a[href], [role='menuitem']"
                        )
                    ) {
                        closeNavbarUtility(trigger);
                    }
                }
            );

            menu.addEventListener(
                "keydown",
                function (event) {
                    handleNavbarMenuKeyboard(
                        event,
                        menu
                    );
                }
            );
        });

        if (!api.state.navbarUtilityDocumentBound) {
            api.state.navbarUtilityDocumentBound = true;

            document.addEventListener(
                "pointerdown",
                function (event) {
                    const utility =
                        event.target.closest(
                            "[data-command-utility]"
                        );

                    if (utility) {
                        return;
                    }

                    closeAllNavbarUtilities();
                }
            );

            document.addEventListener(
                "keydown",
                function (event) {
                    if (event.key !== "Escape") {
                        return;
                    }

                    const expandedTrigger =
                        document.querySelector(
                            `${NAVBAR_UTILITY_TRIGGER_SELECTOR}[aria-expanded="true"]`
                        );

                    if (!expandedTrigger) {
                        return;
                    }

                    event.preventDefault();
                    closeNavbarUtility(
                        expandedTrigger,
                        {
                            restoreFocus: true
                        }
                    );
                }
            );

            document.addEventListener(
                "focusin",
                function (event) {
                    const activeUtility =
                        event.target.closest(
                            "[data-command-utility]"
                        );

                    if (activeUtility) {
                        return;
                    }

                    closeAllNavbarUtilities();
                }
            );
        }

        return true;
    };

    api.loadWorkspace = async function (
        url,
        moduleId,
        options
    ) {
        const cleanOptions = options || {};
        const shouldPush =
            cleanOptions.push !== false;
        const fallbackUrl =
            getWorkspaceRequestUrl(url);
        const requestUrl =
            getWorkspaceRequestUrl(
                fallbackUrl.href
            );
        const mount = document.querySelector(
            api.constants
                .WORKSPACE_MOUNT_SELECTOR
        );

        if (api.state.workspaceHardNavigationCommitted === true) {
            return false;
        }

        if (
            fallbackUrl.origin !==
            window.location.origin
        ) {
            return fallbackToWorkspaceUrl(
                fallbackUrl.href,
                "External workspace route"
            );
        }

        if (!mount) {
            return fallbackToWorkspaceUrl(
                fallbackUrl.href,
                "Workspace mount unavailable"
            );
        }

        closeAllNavbarUtilities();

        if (
            api.state.workspaceNavigationController &&
            typeof api.state
                .workspaceNavigationController
                .abort === "function"
        ) {
            api.state
                .workspaceNavigationController
                .abort();
        }

        const navigationController =
            new AbortController();

        api.state.workspaceNavigationController =
            navigationController;
        api.state.workspaceNavigationActive = true;

        mount.setAttribute(
            "data-workspace-loading",
            "true"
        );
        mount.setAttribute("aria-busy", "true");

        try {
            const response = await fetch(
                requestUrl.href,
                {
                    method: "GET",
                    credentials: "same-origin",
                    headers: {
                        [api.constants
                            .RENDER_MODE_HEADER]:
                            api.constants
                                .WORKSPACE_RENDER_MODE,
                        "X-Requested-With":
                            "XMLHttpRequest"
                    },
                    signal:
                        navigationController.signal
                }
            );

            if (!response.ok) {
                throw new Error(
                    `Workspace request failed: ${response.status}`
                );
            }

            const html = await response.text();
            const canonicalUrl =
                getCanonicalWorkspaceUrl(
                    response,
                    fallbackUrl
                );
            const resolvedModuleId =
                getWorkspaceModuleForUrl(
                    canonicalUrl,
                    moduleId
                );
            const workspaceNavigationOptions = Object.assign(
                {},
                cleanOptions,
                {
                    url: canonicalUrl.href
                }
            );

            if (api.state.workspaceHardNavigationCommitted === true) {
                return false;
            }

            clearDocumentInspectorForNavigation(
                canonicalUrl,
                workspaceNavigationOptions
            );

            const replaced =
                await replaceWorkspaceWithTransition(
                    html,
                    resolvedModuleId,
                    workspaceNavigationOptions
                );

            if (!replaced) {
                throw new Error(
                    "Workspace response was empty."
                );
            }

            syncPersistentShellState(
                resolvedModuleId
            );
            syncRightPaneContentState(
                canonicalUrl,
                cleanOptions
            );
            initializeMountedWorkspaceControls(mount);

            const canonicalHref =
                getBrowserRelativeUrl(
                    canonicalUrl
                );
            const currentHref =
                getCurrentBrowserRelativeUrl();
            const historyState =
                buildWorkspaceHistoryState(
                    resolvedModuleId,
                    canonicalUrl,
                    cleanOptions
                );

            if (
                shouldPush &&
                canonicalHref !== currentHref
            ) {
                window.history.pushState(
                    historyState,
                    "",
                    canonicalHref
                );
            } else if (
                !shouldPush &&
                canonicalHref !== currentHref
            ) {
                window.history.replaceState(
                    historyState,
                    "",
                    canonicalHref
                );
            }

            dispatchWorkspaceLoaded(
                mount,
                resolvedModuleId,
                canonicalUrl,
                workspaceNavigationOptions
            );

            return true;
        } catch (error) {
            if (error?.name === "AbortError") {
                return false;
            }

            console.warn(
                "[WORKSPACE_NAVIGATION] Workspace transition failed.",
                error
            );

            return fallbackToWorkspaceUrl(
                fallbackUrl.href,
                error
            );
        } finally {
            if (
                api.state
                    .workspaceNavigationController ===
                navigationController
            ) {
                mount.removeAttribute(
                    "data-workspace-loading"
                );
                mount.removeAttribute(
                    "aria-busy"
                );
                api.state.workspaceNavigationActive =
                    false;
                api.state
                    .workspaceNavigationController =
                    null;
            }
        }
    };

    api.initializeWorkspaceNavigation =
        function () {
            if (
                api.state.workspaceNavigationBound
            ) {
                return;
            }

            api.state.workspaceNavigationBound =
                true;

            const currentModule =
                getWorkspaceModuleForUrl(
                    window.location.href,
                    api.readCurrentModule()
                );

            const currentPublicUrl =
                getWorkspaceRequestUrl(
                    window.location.href
                );

            window.history.replaceState(
                buildWorkspaceHistoryState(
                    currentModule,
                    currentPublicUrl,
                    {
                        push: false,
                        async: true,
                        launchMode: getRightPaneContentMode(
                            currentPublicUrl,
                            window.history.state || {}
                        ),
                        source: "command_sidebar_bootstrap"
                    }
                ),
                "",
                getBrowserRelativeUrl(
                    currentPublicUrl
                )
            );

            syncPersistentShellState(
                currentModule
            );
            syncRightPaneContentState(
                currentPublicUrl,
                window.history.state || {}
            );

            document.addEventListener(
                "click",
                handleWorkspaceWindowCloseClick,
                true
            );

            document.addEventListener(
                "click",
                handleWorkspaceShellNavigationClick,
                true
            );

            document.addEventListener(
                "click",
                function (event) {
                    if (
                        api.isModifiedNavigationEvent(
                            event
                        )
                    ) {
                        return;
                    }

                    const commandLink =
                        event.target.closest(
                            api.constants
                                .COMMAND_LINK_SELECTOR
                        );

                    if (
                        commandLink &&
                        api.isEligibleWorkspaceLink(
                            commandLink
                        )
                    ) {
                        if (
                            isCommandSidebarNavigationAnchor(
                                commandLink
                            )
                        ) {
                            return;
                        }

                        const isShellNavigationCommandLink =
                            isWorkspaceShellNavigationAnchor(
                                commandLink
                            );
                        const shouldRemainInDocumentNavigation =
                            !isShellNavigationCommandLink &&
                            !isCommandSidebarNavigationAnchor(
                                commandLink
                            ) &&
                            api.shouldUseDocumentNavigation(
                                commandLink
                            ) &&
                            hasMountedDocumentExplorer();

                        if (
                            shouldRemainInDocumentNavigation
                        ) {
                            return;
                        }

                        event.preventDefault();

                        const requestedModule =
                            commandLink.getAttribute(
                                "data-command-module"
                            ) ||
                            DOCUMENTS_MODULE_ID;
                        const resolvedModule =
                            getWorkspaceModuleForUrl(
                                commandLink.href,
                                requestedModule
                            );

                        api.loadWorkspace(
                            commandLink.href,
                            resolvedModule,
                            {
                                push: true,
                                async: true,
                                launchMode: getRightPaneContentMode(
                                    commandLink.href,
                                    {
                                        launchMode: commandLink.getAttribute(
                                            "data-right-pane-content-launch"
                                        )
                                    }
                                ),
                                source: "command_sidebar_bootstrap"
                            }
                        );
                        return;
                    }

                    const link =
                        event.target.closest(
                            "a[href]"
                        );

                    if (
                        !link ||
                        !api.isEligibleWorkspaceLink(
                            link
                        ) ||
                        !isWorkspaceShellNavigationAnchor(
                            link
                        ) ||
                        isCommandSidebarNavigationAnchor(
                            link
                        )
                    ) {
                        return;
                    }

                    event.preventDefault();

                    api.loadWorkspace(
                        link.href,
                        getWorkspaceModuleForUrl(
                            link.href,
                            link.getAttribute(
                                "data-command-module"
                            )
                        ),
                        {
                            push: true,
                            async: true,
                            launchMode: getRightPaneContentMode(
                                link.href,
                                {
                                    launchMode: link.getAttribute(
                                        "data-right-pane-content-launch"
                                    )
                                }
                            ),
                            source: "command_sidebar_bootstrap"
                        }
                    );
                }
            );

            window.addEventListener(
                "popstate",
                function (event) {
                    api.loadWorkspace(
                        window.location.href,
                        getWorkspaceModuleForUrl(
                            window.location.href,
                            event.state?.moduleId
                        ),
                        {
                            push: false,
                            async: true,
                            launchMode: "history_pop",
                            source: "command_sidebar_bootstrap"
                        }
                    );
                }
            );
        };

    api.initializeSolomonLauncher = function () {
        return document.getElementById(
            "commandSolomonLauncher"
        );
    };

    api.initializeCommandSidebar = function () {
        if (api.state.initialized) {
            initializeContextRail();
            api.initializeNavbarUtilities();
            initializeMountedWorkspaceControls(document);
            document.documentElement.setAttribute(
                "data-command-center-ready",
                "true"
            );
            return true;
        }

        const sidebar =
            document.getElementById(
                "commandSidebar"
            );

        if (!sidebar) {
            return false;
        }

        api.state.initialized = true;
        api.applyLockedTaskbarPosition(sidebar);
        api.updateWorkspaceShellState(
            api.readCurrentModule()
        );
        initializeContextRail();
        api.initializeSolomonLauncher();
        api.initializeNavbarUtilities();
        initializeMountedWorkspaceControls(document);
        api.initializeTaskbarInputInteraction();
        api.initializeTaskbarOutputContract();
        api.initializeWorkspaceViewControls();
        api.initializeReturnToFilesControls();
        api.bindWorkspaceConversationSurface();
        api.syncSolomonHistoryState();
        document.documentElement.setAttribute(
            "data-command-center-ready",
            "true"
        );
        api.initializeWorkspaceNavigation();

        return true;
    };

    if (!api.initializeCommandSidebar()) {
        document.addEventListener(
            "DOMContentLoaded",
            api.initializeCommandSidebar,
            { once: true }
        );
    }
})();