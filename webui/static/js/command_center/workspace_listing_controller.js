/* -------------------------------------------------------------------
   FILE: workspace_listing_controller.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const api = window.NationsCommandSidebar =
        window.NationsCommandSidebar || {};

    api.state = api.state || {};

    const CONTRACT_ATTRIBUTE = "data-workspace-listing-contract";
    const CONTROLLER_ATTRIBUTE = "data-workspace-listing-controller";
    const BOUND_ATTRIBUTE = "data-workspace-listing-bound";
    const ACTION_MENU_PORTAL_ATTRIBUTE = "data-workspace-listing-action-menu-portal";
    const ACTION_MENU_PORTAL_ITEM_ATTRIBUTE = "data-workspace-listing-action-menu-portal-item";
    const ACTION_SUBMENU_TRIGGER_ATTRIBUTE = "data-workspace-listing-action-submenu-trigger";
    const ACTION_SUBMENU_SOURCE_ATTRIBUTE = "data-workspace-listing-action-submenu-source";
    const ACTION_SUBMENU_PORTAL_ATTRIBUTE = "data-workspace-listing-action-submenu-portal";
    const ACTION_MENU_EDGE_GUTTER = 14;
    const ACTION_MENU_VERTICAL_OFFSET = 8;
    const ACTION_SUBMENU_GAP = 6;
    const ACTIVE_CLASS = "is-active";
    const SELECTED_CLASS = "is-selected";
    const OPEN_CLASS = "is-open";
    const SELECT_EVENT = "nations:workspace-listing-select";
    const OPEN_EVENT = "nations:workspace-listing-open";
    const READER_LAUNCH_EVENT = "nations:workspace-listing-reader-launch";
    const ACTION_EVENT = "nations:workspace-listing-action";
    const MENU_EVENT = "nations:workspace-listing-menu";
    const DOCUMENT_INSPECTOR_CLEAR_EVENT = "solomon:document-inspector-clear";
    const DEFAULT_SELECTION_INTENT = "programmatic_selection";
    const ROW_MUTATION_OBSERVER_KEY = "__nationsWorkspaceListingObserver";

    let activeActionMenu = null;
    let actionMenuPortalControllerReady = false;
    let documentInspectorClearControllerReady = false;

    function createSubmenuPointerIntentGuard() {
        const pointerIntent = window.SolomonSubmenuPointerIntent;

        return typeof pointerIntent?.createGuard === "function"
            ? pointerIntent.createGuard()
            : null;
    }

    function cancelActiveSubmenuPointerIntentClose() {
        activeActionMenu?.submenuPointerIntentGuard?.cancelClose?.();
    }

    function requestActiveSubmenuClose() {
        if (!activeActionMenu?.submenuPortal) {
            return;
        }

        const trigger = activeActionMenu.submenuTrigger;
        const portal = activeActionMenu.submenuPortal;
        const guard = activeActionMenu.submenuPointerIntentGuard;
        const close = function () {
            if (
                activeActionMenu?.submenuPortal === portal &&
                activeActionMenu?.submenuTrigger === trigger
            ) {
                closeActiveActionSubmenu();
            }
        };

        if (guard?.requestClose?.(trigger, portal, close)) {
            return;
        }

        if (!guard) {
            close();
        }
    }

    function getConstants() {
        return api.constants || {};
    }

    function buildOptInSelector() {
        const contract = getConstants()
            .WORKSPACE_LISTING_CONTRACT ||
            "nations_workspace_listing_v1";

        return [
            `[${CONTRACT_ATTRIBUTE}="${contract}"]`,
            `[${CONTROLLER_ATTRIBUTE}="true"]`
        ].join(", ");
    }

    function getActionMenuSelector() {
        const c = getConstants();

        return [
            c.WORKSPACE_OBJECT_ACTION_MENU_SELECTOR ||
                "[data-workspace-object-action-menu]",
            "[data-document-action-menu]"
        ].filter(Boolean).join(", ");
    }

    function getActionMenuButtonSelector() {
        const c = getConstants();

        return [
            c.WORKSPACE_OBJECT_ACTION_MENU_BUTTON_SELECTOR ||
                "[data-workspace-object-action-menu-button]",
            "[data-document-action-menu-button]"
        ].filter(Boolean).join(", ");
    }

    function getActionMenuItemSelector() {
        const c = getConstants();

        return [
            c.WORKSPACE_OBJECT_ACTION_MENU_ITEM_SELECTOR ||
                "[data-workspace-object-action-menu-item]",
            "[data-document-action-menu-item]",
            "[data-search-result-action]"
        ].filter(Boolean).join(", ");
    }

    function isElement(value) {
        return value instanceof Element;
    }

    function getEventTarget(event) {
        return isElement(event?.target)
            ? event.target
            : null;
    }

    function normalizeText(value) {
        return String(value || "").trim();
    }

    function normalizeAction(value) {
        return normalizeText(value)
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "_")
            .replace(/^_+|_+$/g, "");
    }

    function normalizeBooleanAttribute(value, fallback) {
        const cleanValue = normalizeText(value).toLowerCase();

        if (!cleanValue) {
            return fallback;
        }

        if (
            cleanValue === "true" ||
            cleanValue === "1" ||
            cleanValue === "yes"
        ) {
            return true;
        }

        if (
            cleanValue === "false" ||
            cleanValue === "0" ||
            cleanValue === "no"
        ) {
            return false;
        }

        return fallback;
    }

    function readAttribute(element, names) {
        if (!element) {
            return "";
        }

        for (const name of names) {
            const value = normalizeText(
                element.getAttribute(name)
            );

            if (value) {
                return value;
            }
        }

        return "";
    }

    function readObjectId(row) {
        const c = getConstants();

        return readAttribute(row, [
            c.WORKSPACE_OBJECT_ID_ATTRIBUTE,
            c.WORKSPACE_LEGACY_DOCUMENT_ID_ATTRIBUTE,
            "data-search-result-id",
            "data-random-name"
        ]);
    }

    function readObjectType(row) {
        const c = getConstants();

        return readAttribute(row, [
            c.WORKSPACE_OBJECT_TYPE_ATTRIBUTE,
            "data-search-result-type",
            "data-document-type-label",
            "data-workspace-object-kind",
            "data-search-result-kind"
        ]);
    }

    function readObjectKind(row) {
        const c = getConstants();

        return readAttribute(row, [
            "data-workspace-object-kind",
            c.WORKSPACE_OBJECT_TYPE_ATTRIBUTE,
            "data-workspace-item-type",
            "data-workspace-item-kind",
            "data-document-kind",
            "data-document-type",
            "data-document-resource-type",
            "data-document-type-label",
            "data-search-result-kind",
            "data-search-result-type"
        ]);
    }

    function isFolderObjectRow(row) {
        const objectKind = normalizeAction(readObjectKind(row));
        const folderId = readAttribute(row, [
            "data-workspace-folder-id",
            "data-folder-id",
            "data-workspace-object-folder-id"
        ]);
        const folderFlag = normalizeBooleanAttribute(
            readAttribute(row, [
                "data-workspace-object-folder",
                "data-document-folder",
                "data-is-folder",
                "data-folder"
            ]),
            false
        );

        return Boolean(
            folderFlag ||
            folderId ||
            objectKind === "folder"
        );
    }

    function readObjectRoute(row) {
        const c = getConstants();

        return readAttribute(row, [
            "data-workspace-folder-url",
            "data-folder-url",
            "data-canonical-url",
            c.WORKSPACE_OBJECT_ROUTE_ATTRIBUTE,
            c.WORKSPACE_LEGACY_DOCUMENT_ROUTE_ATTRIBUTE,
            c.WORKSPACE_LEGACY_SEARCH_ROUTE_ATTRIBUTE,
            "data-document-route",
            "data-search-result-route",
            "data-command-route",
            "href"
        ]);
    }

    function readFolderOpenRoute(row) {
        const c = getConstants();

        return readAttribute(row, [
            "data-workspace-folder-open-route",
            "data-workspace-folder-url",
            "data-folder-open-route",
            "data-folder-url",
            "data-canonical-url",
            "data-workspace-object-open-route",
            "data-document-open-route",
            "data-search-result-open-route",
            c.WORKSPACE_OBJECT_ROUTE_ATTRIBUTE,
            c.WORKSPACE_LEGACY_SEARCH_ROUTE_ATTRIBUTE,
            "data-command-route",
            "href"
        ]);
    }

    function readObjectOpenRoute(row) {
        const c = getConstants();

        if (isFolderObjectRow(row)) {
            return readFolderOpenRoute(row);
        }

        return readAttribute(row, [
            "data-document-reader-url",
            "data-workspace-object-open-route",
            "data-document-open-route",
            "data-search-result-open-route",
            c.WORKSPACE_OBJECT_ROUTE_ATTRIBUTE,
            c.WORKSPACE_LEGACY_DOCUMENT_ROUTE_ATTRIBUTE,
            c.WORKSPACE_LEGACY_SEARCH_ROUTE_ATTRIBUTE,
            "data-command-route",
            "href"
        ]);
    }

    function readObjectModule(row) {
        const c = getConstants();

        return readAttribute(row, [
            c.WORKSPACE_OBJECT_MODULE_ATTRIBUTE,
            c.WORKSPACE_LEGACY_SEARCH_MODULE_ATTRIBUTE,
            "data-command-module"
        ]);
    }

    function readObjectName(row) {
        const explicitName = readAttribute(row, [
            "data-workspace-object-name",
            "data-document-name",
            "data-search-result-title",
            "data-workspace-object-title",
            "aria-label",
            "title"
        ]);

        if (explicitName) {
            return explicitName;
        }

        return normalizeText(row?.textContent)
            .replace(/\s+/g, " ");
    }

    function readObjectMime(row) {
        return readAttribute(row, [
            "data-workspace-object-mime",
            "data-document-mime",
            "data-search-result-mime"
        ]);
    }

    function readObjectSurface(explorer) {
        return readAttribute(explorer, [
            "data-workspace-listing-surface",
            "data-document-surface",
            "data-search-surface",
            "data-command-surface",
            "data-right-pane-content-surface"
        ]);
    }

    function readObjectBackRoute(row, explorer) {
        const listing = row?.closest?.("[data-workspace-listing]");
        const resolvedExplorer = explorer || row?.closest?.(buildOptInSelector());
        const route = readAttribute(row, [
            "data-right-pane-content-back-route",
            "data-workspace-object-back-route",
            "data-document-back-route",
            "data-search-result-back-route"
        ]) || readAttribute(listing, [
            "data-workspace-reader-back-route",
            "data-right-pane-content-route",
            "data-workspace-route"
        ]) || readAttribute(resolvedExplorer, [
            "data-workspace-reader-back-route",
            "data-right-pane-content-route",
            "data-workspace-route"
        ]);

        return normalizeBackRoute(route);
    }

    function isObjectDeleted(row) {
        return normalizeBooleanAttribute(
            readAttribute(row, [
                "data-workspace-object-deleted",
                "data-document-deleted",
                "data-search-result-deleted"
            ]),
            false
        );
    }

    function isOpenEnabled(row) {
        const explicitState = normalizeBooleanAttribute(
            readAttribute(row, [
                "data-workspace-folder-open-enabled",
                "data-workspace-folder-can-open",
                "data-workspace-object-open-enabled",
                "data-workspace-object-can-open",
                "data-document-open-enabled",
                "data-document-can-open",
                "data-search-result-open-enabled"
            ]),
            null
        );

        if (explicitState === false) {
            return false;
        }

        const route = readObjectOpenRoute(row);

        if (!route || route === "#") {
            return false;
        }

        if (isFolderObjectRow(row) && isWorkspaceReaderRoute(route)) {
            return false;
        }

        return explicitState !== false;
    }

    function getRoot(scope) {
        return scope && typeof scope.querySelectorAll === "function"
            ? scope
            : document;
    }

    function findOptInExplorers(scope) {
        const root = getRoot(scope);
        const selector = buildOptInSelector();
        const explorers = Array.from(
            root.querySelectorAll(selector) || []
        );

        if (
            isElement(root) &&
            root.matches(selector)
        ) {
            explorers.unshift(root);
        }

        return explorers.filter(function (
            explorer,
            index,
            collection
        ) {
            return (
                explorer &&
                collection.indexOf(explorer) === index
            );
        });
    }

    function getListingForExplorer(explorer) {
        const c = getConstants();

        if (!explorer) {
            return null;
        }

        if (explorer.matches(c.WORKSPACE_LISTING_SELECTOR || "")) {
            return explorer;
        }

        return explorer.querySelector(
            c.WORKSPACE_LISTING_SELECTOR ||
            "[data-workspace-listing]"
        );
    }

    function getRows(explorer) {
        const c = getConstants();
        const listing = getListingForExplorer(explorer);

        if (!listing) {
            return [];
        }

        return Array.from(
            listing.querySelectorAll(
                c.WORKSPACE_OBJECT_SELECTOR ||
                "[data-workspace-object]"
            ) || []
        ).filter(function (row) {
            return (
                !row.hidden &&
                row.getAttribute("aria-hidden") !== "true"
            );
        });
    }

    function getRowFromTarget(explorer, target) {
        const c = getConstants();

        if (!explorer || !target) {
            return null;
        }

        const row = target.closest(
            c.WORKSPACE_OBJECT_SELECTOR ||
            "[data-workspace-object]"
        );

        if (!row || !explorer.contains(row)) {
            return null;
        }

        return row;
    }

    function isActionControlTarget(target) {
        return Boolean(
            target?.closest?.(
                [
                    "button",
                    "input",
                    "select",
                    "textarea",
                    "label",
                    "summary",
                    "[contenteditable='true']",
                    "[role='button']",
                    "[role='menuitem']",
                    "[data-workspace-object-action-menu]",
                    "[data-document-action-menu]",
                    "[data-workspace-object-action-menu-button]",
                    "[data-document-action-menu-button]",
                    "[data-workspace-object-action-menu-item]",
                    "[data-document-action-menu-item]",
                    "[data-search-result-action]"
                ].join(", ")
            )
        );
    }

    function isInteractiveTarget(target, row) {
        if (!target) {
            return false;
        }

        if (isActionControlTarget(target)) {
            return true;
        }

        const anchor = target.closest("a[href]");

        if (!anchor) {
            return false;
        }

        if (!row) {
            return true;
        }

        if (anchor === row) {
            return false;
        }

        if (
            anchor.hasAttribute("data-workspace-object") ||
            anchor.hasAttribute("data-document-id") ||
            anchor.hasAttribute("data-search-result-id") ||
            anchor.hasAttribute("data-command-route")
        ) {
            return false;
        }

        return Boolean(
            anchor.closest(
                [
                    "[data-workspace-object-action-menu]",
                    "[data-document-action-menu]",
                    "[role='menu']"
                ].join(", ")
            )
        );
    }

    function setRowSelected(row, selected) {
        const c = getConstants();
        const value = selected ? "true" : "false";

        row.classList.toggle(SELECTED_CLASS, selected);
        row.classList.toggle(ACTIVE_CLASS, selected);
        row.setAttribute("aria-selected", value);

        if (c.WORKSPACE_OBJECT_SELECTED_ATTRIBUTE) {
            row.setAttribute(
                c.WORKSPACE_OBJECT_SELECTED_ATTRIBUTE,
                value
            );
        }

        if (
            c.WORKSPACE_LEGACY_DOCUMENT_SELECTED_ATTRIBUTE &&
            row.hasAttribute(
                c.WORKSPACE_LEGACY_DOCUMENT_SELECTED_ATTRIBUTE
            )
        ) {
            row.setAttribute(
                c.WORKSPACE_LEGACY_DOCUMENT_SELECTED_ATTRIBUTE,
                value
            );
        }

        if (!row.hasAttribute("tabindex")) {
            row.setAttribute("tabindex", "0");
        }
    }

    function selectRow(explorer, row, options) {
        const cleanOptions = options || {};

        if (!explorer || !row) {
            return false;
        }

        getRows(explorer).forEach(function (candidate) {
            setRowSelected(candidate, candidate === row);
        });

        api.state.workspaceListingActiveObjectId =
            readObjectId(row);
        api.state.workspaceListingActiveObjectType =
            readObjectType(row);
        explorer.setAttribute(
            "data-workspace-listing-active-object-id",
            api.state.workspaceListingActiveObjectId || ""
        );
        explorer.setAttribute(
            "data-workspace-listing-active-object-type",
            api.state.workspaceListingActiveObjectType || ""
        );

        if (cleanOptions.silent !== true) {
            emitSelectEvent(explorer, row, cleanOptions);
        }

        if (cleanOptions.focus === true) {
            row.focus({
                preventScroll:
                    cleanOptions.preventScroll === true
            });
        }

        return true;
    }

    function rowHasSelectedState(row) {
        const c = getConstants();

        return Boolean(
            row?.classList?.contains(SELECTED_CLASS) ||
            row?.classList?.contains(ACTIVE_CLASS) ||
            row?.getAttribute?.("aria-selected") === "true" ||
            (
                c.WORKSPACE_OBJECT_SELECTED_ATTRIBUTE &&
                row?.getAttribute?.(c.WORKSPACE_OBJECT_SELECTED_ATTRIBUTE) === "true"
            ) ||
            (
                c.WORKSPACE_LEGACY_DOCUMENT_SELECTED_ATTRIBUTE &&
                row?.getAttribute?.(c.WORKSPACE_LEGACY_DOCUMENT_SELECTED_ATTRIBUTE) === "true"
            )
        );
    }

    function clearExplorerSelection(explorer, options) {
        if (!explorer) {
            return false;
        }

        const cleanOptions = options || {};
        let didClear = false;

        if (cleanOptions.closeMenus !== false) {
            closeActionMenus(explorer);
        }

        getRows(explorer).forEach(function (row) {
            if (rowHasSelectedState(row)) {
                didClear = true;
            }

            setRowSelected(row, false);
        });

        if (
            explorer.getAttribute("data-workspace-listing-active-object-id") ||
            explorer.getAttribute("data-workspace-listing-active-object-type")
        ) {
            didClear = true;
        }

        explorer.setAttribute(
            "data-workspace-listing-active-object-id",
            ""
        );
        explorer.setAttribute(
            "data-workspace-listing-active-object-type",
            ""
        );

        api.state.workspaceListingActiveObjectId = "";
        api.state.workspaceListingActiveObjectType = "";

        return didClear;
    }

    function clearWorkspaceListingSelection(scope, options) {
        return findOptInExplorers(scope).reduce(function (didClear, explorer) {
            return clearExplorerSelection(explorer, options) || didClear;
        }, false);
    }

    function focusRow(explorer, row) {
        if (!row) {
            return false;
        }

        selectRow(explorer, row, {
            focus: true,
            preventScroll: true,
            selectionIntent: "keyboard_navigation",
            openInspector: true
        });

        return true;
    }

    function focusAdjacentRow(explorer, currentRow, direction) {
        const rows = getRows(explorer);

        if (!rows.length) {
            return false;
        }

        const currentIndex = rows.indexOf(currentRow);
        let nextIndex = currentIndex;

        if (direction === "first") {
            nextIndex = 0;
        } else if (direction === "last") {
            nextIndex = rows.length - 1;
        } else if (direction === "previous") {
            nextIndex = currentIndex <= 0
                ? rows.length - 1
                : currentIndex - 1;
        } else {
            nextIndex = currentIndex >= rows.length - 1
                ? 0
                : currentIndex + 1;
        }

        return focusRow(
            explorer,
            rows[nextIndex]
        );
    }

    function getSameOriginUrl(value) {
        const cleanValue = normalizeText(value);

        if (!cleanValue) {
            return null;
        }

        try {
            const url = new URL(cleanValue, window.location.origin);

            return url.origin === window.location.origin
                ? url
                : null;
        } catch (_error) {
            return null;
        }
    }

    function getRelativeUrl(url) {
        if (!url) {
            return "";
        }

        return `${url.pathname}${url.search}${url.hash}`;
    }

    function getSameOriginRelativeRoute(value) {
        return getRelativeUrl(
            getSameOriginUrl(value)
        );
    }

    function isWorkspaceReaderRoute(route) {
        const parsedUrl = getSameOriginUrl(route);

        if (!parsedUrl) {
            return false;
        }

        const pathParts = parsedUrl.pathname
            .split("/")
            .filter(Boolean);

        return (
            pathParts.length >= 4 &&
            pathParts[0] === "workspace" &&
            (pathParts[1] === "file" || pathParts[1] === "document") &&
            pathParts[3] === "reader"
        );
    }

    function normalizeBackRoute(route) {
        const cleanRoute = normalizeText(route);

        if (
            !cleanRoute ||
            !cleanRoute.startsWith("/") ||
            isWorkspaceReaderRoute(cleanRoute)
        ) {
            return "";
        }

        return cleanRoute;
    }

    function getCurrentBackRoute() {
        try {
            const currentUrl = new URL(window.location.href);
            const route = getRelativeUrl(currentUrl);

            if (isWorkspaceReaderRoute(route)) {
                return normalizeBackRoute(
                    currentUrl.searchParams.get("back") || ""
                ) || "/";
            }

            return route || "/";
        } catch (_error) {
            return "/";
        }
    }

    function appendReaderBackRoute(route, backRoute) {
        const parsedUrl = getSameOriginUrl(route);
        const resolvedBackRoute = normalizeBackRoute(backRoute) || getCurrentBackRoute();

        if (!parsedUrl) {
            return normalizeText(route);
        }

        if (!isWorkspaceReaderRoute(getRelativeUrl(parsedUrl))) {
            return getRelativeUrl(parsedUrl);
        }

        if (parsedUrl.searchParams.has("back")) {
            return getRelativeUrl(parsedUrl);
        }

        parsedUrl.searchParams.set(
            "back",
            resolvedBackRoute
        );

        return getRelativeUrl(parsedUrl);
    }

    function getOpenRoute(row, explorer) {
        return appendReaderBackRoute(
            readObjectOpenRoute(row),
            readObjectBackRoute(row, explorer)
        );
    }

    function getOpenModule(row, route) {
        const moduleId = readObjectModule(row);

        if (isWorkspaceReaderRoute(route)) {
            return "documents";
        }

        return moduleId || "documents";
    }

    function getLaunchMode(route, row) {
        if (isWorkspaceReaderRoute(route)) {
            return "reader";
        }

        return isFolderObjectRow(row)
            ? "workspace_folder"
            : "workspace_object";
    }

    function buildWorkspaceLoadOptions(row, route, options) {
        const cleanOptions = options || {};
        const explorer = row?.closest?.(buildOptInSelector());
        const launchMode = getLaunchMode(route, row);
        const backRoute = readObjectBackRoute(row, explorer) || getCurrentBackRoute();

        return Object.assign(
            {},
            cleanOptions.loadOptions || {},
            {
                push: cleanOptions.push !== false,
                async: true,
                launchMode,
                source: cleanOptions.source || "workspace_listing_controller",
                backRoute,
                objectId: readObjectId(row),
                objectType: readObjectType(row),
                objectKind: readObjectKind(row),
                objectName: readObjectName(row),
                objectRoute: readObjectRoute(row),
                openRoute: route,
                isFolder: isFolderObjectRow(row),
                folderId: readAttribute(row, [
                    "data-workspace-folder-id",
                    "data-folder-id",
                    "data-workspace-object-folder-id"
                ]),
                surface: readObjectSurface(explorer)
            }
        );
    }

    function openRouteWithBrowserFallback(route) {
        const cleanRoute = normalizeText(route);

        if (!cleanRoute) {
            return false;
        }

        const anchor = document.createElement("a");

        anchor.href = cleanRoute;
        anchor.rel = "noopener";
        anchor.style.display = "none";

        if (!getSameOriginUrl(cleanRoute)) {
            anchor.target = "_blank";
        }

        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();

        return true;
    }

    function launchReaderRoute(row, route, options) {
        if (isFolderObjectRow(row)) {
            return false;
        }

        const explorer = row?.closest(buildOptInSelector());
        const relativeRoute = getSameOriginRelativeRoute(route);
        const cleanRoute = relativeRoute || normalizeText(route);
        const readerEvent = emitReaderLaunchEvent(
            explorer,
            row,
            cleanRoute,
            options
        );

        if (readerEvent?.defaultPrevented) {
            return true;
        }

        if (
            relativeRoute &&
            typeof api.loadWorkspace === "function"
        ) {
            try {
                const result = api.loadWorkspace(
                    relativeRoute,
                    getOpenModule(row, relativeRoute),
                    buildWorkspaceLoadOptions(
                        row,
                        relativeRoute,
                        options
                    )
                );

                if (
                    result &&
                    typeof result.then === "function"
                ) {
                    result.catch(function (error) {
                        console.warn(
                            "[WORKSPACE_LISTING] Async Reader launch failed; falling back to browser navigation.",
                            error
                        );
                        openRouteWithBrowserFallback(relativeRoute);
                    });
                } else if (result === false) {
                    openRouteWithBrowserFallback(relativeRoute);
                }

                return true;
            } catch (error) {
                console.warn(
                    "[WORKSPACE_LISTING] Async Reader launch failed; falling back to browser navigation.",
                    error
                );
                openRouteWithBrowserFallback(relativeRoute);
                return true;
            }
        }

        return openRouteWithBrowserFallback(cleanRoute);
    }

    function loadWorkspaceRoute(row, route, options) {
        const relativeRoute = getSameOriginRelativeRoute(route);
        const cleanRoute = relativeRoute || normalizeText(route);

        if (!cleanRoute) {
            return false;
        }

        if (isWorkspaceReaderRoute(cleanRoute)) {
            return launchReaderRoute(
                row,
                cleanRoute,
                options
            );
        }

        if (
            relativeRoute &&
            typeof api.loadWorkspace === "function"
        ) {
            try {
                const result = api.loadWorkspace(
                    relativeRoute,
                    getOpenModule(row, relativeRoute),
                    buildWorkspaceLoadOptions(
                        row,
                        relativeRoute,
                        options
                    )
                );

                if (
                    result &&
                    typeof result.then === "function"
                ) {
                    result.catch(function (error) {
                        console.warn(
                            "[WORKSPACE_LISTING] Async right-pane launch failed; falling back to browser navigation.",
                            error
                        );
                        openRouteWithBrowserFallback(relativeRoute);
                    });
                } else if (result === false) {
                    openRouteWithBrowserFallback(relativeRoute);
                }

                return true;
            } catch (error) {
                console.warn(
                    "[WORKSPACE_LISTING] Async right-pane launch failed; falling back to browser navigation.",
                    error
                );

                openRouteWithBrowserFallback(relativeRoute);
                return true;
            }
        }

        return openRouteWithBrowserFallback(cleanRoute);
    }

    function buildRowContract(explorer, row, extraDetail) {
        const route = readObjectRoute(row);
        const openRoute = getOpenRoute(row, explorer);
        const launchMode = getLaunchMode(openRoute, row);
        const backRoute = readObjectBackRoute(row, explorer) || getCurrentBackRoute();
        const detail = Object.assign(
            {},
            extraDetail || {}
        );

        return Object.assign(
            {
                id: readObjectId(row),
                type: readObjectType(row),
                kind: readObjectKind(row),
                name: readObjectName(row),
                mime: readObjectMime(row),
                module: getOpenModule(row, openRoute),
                route,
                openRoute,
                launchMode,
                async: true,
                backRoute,
                surface: readObjectSurface(explorer),
                isDeleted: isObjectDeleted(row),
                isFolder: isFolderObjectRow(row),
                canOpen: isOpenEnabled(row),
                row,
                explorer
            },
            detail
        );
    }

    function dispatchListingEvent(explorer, row, eventName, extraDetail, options) {
        if (!row) {
            return null;
        }

        const cleanOptions = options || {};
        const event = new CustomEvent(
            eventName,
            {
                bubbles: true,
                cancelable: cleanOptions.cancelable === true,
                detail: buildRowContract(
                    explorer,
                    row,
                    extraDetail
                )
            }
        );

        row.dispatchEvent(event);

        return event;
    }

    function emitSelectEvent(explorer, row, options) {
        const cleanOptions = options || {};

        dispatchListingEvent(
            explorer,
            row,
            SELECT_EVENT,
            {
                selected: true,
                selectionIntent:
                    normalizeAction(cleanOptions.selectionIntent) ||
                    DEFAULT_SELECTION_INTENT,
                openInspector: cleanOptions.openInspector === true
            }
        );
    }

    function emitMenuEvent(explorer, row, action, item, mode) {
        dispatchListingEvent(
            explorer,
            row,
            MENU_EVENT,
            {
                action,
                actionElement: item || null,
                mode: mode || "button"
            }
        );
    }

    function emitActionEvent(explorer, row, action, item, mode) {
        return dispatchListingEvent(
            explorer,
            row,
            ACTION_EVENT,
            {
                action,
                actionElement: item || null,
                mode: mode || "button"
            },
            {
                cancelable: true
            }
        );
    }

    function emitOpenEvent(explorer, row, mode) {
        return dispatchListingEvent(
            explorer,
            row,
            OPEN_EVENT,
            {
                mode: mode || "default"
            },
            {
                cancelable: true
            }
        );
    }

    function emitReaderLaunchEvent(explorer, row, route, options) {
        return dispatchListingEvent(
            explorer,
            row,
            READER_LAUNCH_EVENT,
            {
                mode: options?.mode || "default",
                route,
                openRoute: route,
                launchMode: "reader",
                backRoute: readObjectBackRoute(row, explorer) || getCurrentBackRoute()
            },
            {
                cancelable: true
            }
        );
    }

    function openRow(row, explorer, options) {
        const effectiveExplorer = explorer || row?.closest(buildOptInSelector());
        const route = getOpenRoute(row, effectiveExplorer);
        const cleanOptions = options || {};

        if (!isOpenEnabled(row)) {
            return false;
        }

        const openEvent = emitOpenEvent(
            effectiveExplorer,
            row,
            cleanOptions.mode
        );

        if (openEvent?.defaultPrevented) {
            return true;
        }

        return loadWorkspaceRoute(
            row,
            route,
            cleanOptions
        ) !== false;
    }

    function getActionMenuFromTarget(explorer, target) {
        if (!explorer || !target) {
            return null;
        }

        const menu = target.closest(getActionMenuSelector());

        if (!menu || !explorer.contains(menu)) {
            return null;
        }

        return menu;
    }

    function getActionMenuButtonFromTarget(explorer, target) {
        if (!explorer || !target) {
            return null;
        }

        const button = target.closest(getActionMenuButtonSelector());

        if (!button || !explorer.contains(button)) {
            return null;
        }

        return button;
    }

    function getActionMenuItemFromTarget(explorer, target) {
        if (!explorer || !target) {
            return null;
        }

        const item = target.closest(getActionMenuItemSelector());

        if (!item || !explorer.contains(item)) {
            return null;
        }

        return item;
    }

    function getActionMenuFromRow(row) {
        if (!row) {
            return null;
        }

        return row.querySelector(getActionMenuSelector());
    }

    function getActionMenuButton(menu) {
        if (!menu) {
            return null;
        }

        return menu.querySelector(getActionMenuButtonSelector());
    }

    function getActionPopover(menu, button) {
        const popoverId = normalizeText(
            button?.getAttribute("aria-controls")
        );

        if (popoverId) {
            const popover = document.getElementById(popoverId);

            if (popover && menu.contains(popover)) {
                return popover;
            }
        }

        return menu.querySelector(
            [
                "[data-workspace-object-action-popover]",
                ".workspace-document-file-action-popover",
                "[role='menu']"
            ].join(", ")
        );
    }

    function readMenuAction(item) {
        return normalizeAction(
            readAttribute(item, [
                "data-workspace-object-action-menu-item",
                "data-workspace-object-action",
                "data-document-action-menu-item",
                "data-search-result-action"
            ])
        );
    }

    function isOpenAction(action, item) {
        return Boolean(
            action === "open" ||
            action === "open_reader" ||
            action === "reader" ||
            item?.hasAttribute("data-search-result-open-trigger") ||
            item?.hasAttribute("data-workspace-object-open-trigger") ||
            item?.hasAttribute("data-document-open-trigger")
        );
    }

    function clampMenuCoordinate(value, minimum, maximum) {
        return Math.max(minimum, Math.min(value, maximum));
    }

    function getActionMenuContextPoint(options) {
        const cleanOptions = options || {};
        const clientX = Number(cleanOptions.clientX);
        const clientY = Number(cleanOptions.clientY);

        if (
            cleanOptions.mode !== "context" ||
            !Number.isFinite(clientX) ||
            !Number.isFinite(clientY)
        ) {
            return null;
        }

        return {
            clientX,
            clientY
        };
    }

    function positionActionMenuPortal() {
        if (!activeActionMenu?.portal || !activeActionMenu?.button) {
            return;
        }

        const {
            button,
            contextPoint,
            portal
        } = activeActionMenu;
        const buttonRect = button.getBoundingClientRect();
        const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;

        portal.style.left = "0px";
        portal.style.top = "0px";
        portal.style.maxWidth = `${Math.max(180, viewportWidth - (ACTION_MENU_EDGE_GUTTER * 2))}px`;

        const portalRect = portal.getBoundingClientRect();
        const portalWidth = portalRect.width || 220;
        const portalHeight = portalRect.height || 1;
        const maxLeft = viewportWidth - portalWidth - ACTION_MENU_EDGE_GUTTER;
        const maxTop = viewportHeight - portalHeight - ACTION_MENU_EDGE_GUTTER;
        let preferredLeft = buttonRect.right - portalWidth;
        let preferredTop = buttonRect.bottom + ACTION_MENU_VERTICAL_OFFSET;
        let resolvedLeft = ACTION_MENU_EDGE_GUTTER;
        let resolvedTop = ACTION_MENU_EDGE_GUTTER;

        if (contextPoint) {
            preferredLeft = contextPoint.clientX;
            preferredTop = contextPoint.clientY;
            resolvedLeft = clampMenuCoordinate(
                preferredLeft,
                ACTION_MENU_EDGE_GUTTER,
                maxLeft
            );
            resolvedTop = clampMenuCoordinate(
                preferredTop,
                ACTION_MENU_EDGE_GUTTER,
                maxTop
            );
        } else {
            const fallbackTop = buttonRect.top - portalHeight - ACTION_MENU_VERTICAL_OFFSET;

            resolvedLeft = clampMenuCoordinate(
                preferredLeft,
                ACTION_MENU_EDGE_GUTTER,
                maxLeft
            );
            resolvedTop = preferredTop > maxTop
                ? Math.max(ACTION_MENU_EDGE_GUTTER, fallbackTop)
                : Math.max(ACTION_MENU_EDGE_GUTTER, preferredTop);
        }

        portal.style.left = `${resolvedLeft}px`;
        portal.style.top = `${resolvedTop}px`;
        positionActionSubmenuPortal();
    }

    function buildActionMenuPortal(popover, options) {
        const portal = popover.cloneNode(true);
        const cleanOptions = options || {};
        const isContextMenu = cleanOptions.mode === "context";

        portal.hidden = false;
        portal.removeAttribute("id");
        portal.setAttribute(ACTION_MENU_PORTAL_ATTRIBUTE, "");
        portal.setAttribute("aria-hidden", "false");
        portal.setAttribute("data-workspace-object-action-popover", "");
        portal.classList.add("workspace-document-file-action-popover--portal", OPEN_CLASS);
        portal.classList.toggle("workspace-document-file-action-popover--context", isContextMenu);
        portal.setAttribute("data-document-menu-position", isContextMenu ? "context" : "button");
        portal.style.display = "grid";
        portal.style.position = "fixed";
        portal.style.left = "0px";
        portal.style.top = "0px";
        portal.style.right = "auto";
        portal.style.bottom = "auto";
        portal.style.zIndex = "10000";
        portal.style.maxHeight = "calc(100vh - 28px)";
        portal.style.overflowY = "auto";
        portal.style.pointerEvents = "auto";
        portal.style.visibility = "hidden";

        portal.querySelectorAll(getActionMenuItemSelector()).forEach(function (item) {
            item.setAttribute(ACTION_MENU_PORTAL_ITEM_ATTRIBUTE, "");
            item.setAttribute("tabindex", item.disabled ? "-1" : "0");
        });

        document.body.appendChild(portal);

        requestAnimationFrame(function () {
            if (!activeActionMenu || activeActionMenu.portal !== portal) {
                return;
            }

            positionActionMenuPortal();
            portal.style.visibility = "visible";
        });

        return portal;
    }

    function getActionSubmenuTriggerFromTarget(target) {
        if (!target || !activeActionMenu?.portal) {
            return null;
        }

        const trigger = target.closest(
            `[${ACTION_SUBMENU_TRIGGER_ATTRIBUTE}]`
        );

        return trigger && activeActionMenu.portal.contains(trigger)
            ? trigger
            : null;
    }

    function getActionSubmenuSource(trigger) {
        const owner = trigger?.parentElement;

        if (!owner) {
            return null;
        }

        return owner.querySelector(
            `[${ACTION_SUBMENU_SOURCE_ATTRIBUTE}]`
        );
    }

    function closeActiveActionSubmenu(options) {
        cancelActiveSubmenuPointerIntentClose();

        if (!activeActionMenu?.submenuPortal) {
            return false;
        }

        const cleanOptions = options || {};
        const trigger = activeActionMenu.submenuTrigger;
        const portal = activeActionMenu.submenuPortal;

        if (trigger) {
            trigger.setAttribute("aria-expanded", "false");
        }

        if (portal?.parentNode) {
            portal.parentNode.removeChild(portal);
        }

        activeActionMenu.submenuPortal = null;
        activeActionMenu.submenuTrigger = null;

        if (
            cleanOptions.restoreFocus === true &&
            trigger instanceof HTMLElement
        ) {
            trigger.focus({ preventScroll: true });
        }

        return true;
    }

    function positionActionSubmenuPortal() {
        if (
            !activeActionMenu?.submenuPortal ||
            !activeActionMenu?.submenuTrigger
        ) {
            return;
        }

        const portal = activeActionMenu.submenuPortal;
        const trigger = activeActionMenu.submenuTrigger;
        const triggerRect = trigger.getBoundingClientRect();
        const viewportWidth =
            window.innerWidth ||
            document.documentElement.clientWidth ||
            0;
        const viewportHeight =
            window.innerHeight ||
            document.documentElement.clientHeight ||
            0;

        portal.style.left = "0px";
        portal.style.top = "0px";
        portal.style.maxWidth =
            `${Math.max(180, viewportWidth - (ACTION_MENU_EDGE_GUTTER * 2))}px`;
        portal.style.maxHeight =
            `${Math.max(120, viewportHeight - (ACTION_MENU_EDGE_GUTTER * 2))}px`;

        const portalRect = portal.getBoundingClientRect();
        const portalWidth = portalRect.width || 220;
        const portalHeight = portalRect.height || 1;
        const preferredRight = triggerRect.right + ACTION_SUBMENU_GAP;
        const preferredLeft =
            triggerRect.left - portalWidth - ACTION_SUBMENU_GAP;
        const fitsRight =
            preferredRight + portalWidth <=
            viewportWidth - ACTION_MENU_EDGE_GUTTER;
        const maxTop =
            viewportHeight - portalHeight - ACTION_MENU_EDGE_GUTTER;
        const resolvedLeft = fitsRight
            ? preferredRight
            : Math.max(ACTION_MENU_EDGE_GUTTER, preferredLeft);
        const resolvedTop = clampMenuCoordinate(
            triggerRect.top,
            ACTION_MENU_EDGE_GUTTER,
            maxTop
        );

        portal.style.left = `${resolvedLeft}px`;
        portal.style.top = `${resolvedTop}px`;
    }

    function buildActionSubmenuPortal(trigger) {
        const source = getActionSubmenuSource(trigger);

        if (!source) {
            return null;
        }

        const portal = source.cloneNode(true);

        portal.hidden = false;
        portal.removeAttribute("id");
        portal.removeAttribute(ACTION_SUBMENU_SOURCE_ATTRIBUTE);
        portal.setAttribute(ACTION_SUBMENU_PORTAL_ATTRIBUTE, "");
        portal.setAttribute("aria-hidden", "false");
        portal.classList.add(
            "workspace-document-file-action-popover--portal",
            OPEN_CLASS
        );
        portal.style.display = "grid";
        portal.style.position = "fixed";
        portal.style.left = "0px";
        portal.style.top = "0px";
        portal.style.right = "auto";
        portal.style.bottom = "auto";
        portal.style.zIndex = "10020";
        portal.style.overflowY = "auto";
        portal.style.pointerEvents = "auto";
        portal.style.visibility = "hidden";

        portal.querySelectorAll(
            getActionMenuItemSelector()
        ).forEach(function (item) {
            item.setAttribute(
                ACTION_MENU_PORTAL_ITEM_ATTRIBUTE,
                ""
            );
            item.setAttribute(
                "tabindex",
                item.disabled ? "-1" : "0"
            );
        });

        document.body.appendChild(portal);

        return portal;
    }

    function openActionSubmenu(trigger) {
        cancelActiveSubmenuPointerIntentClose();

        if (
            !activeActionMenu ||
            !trigger ||
            !activeActionMenu.portal?.contains(trigger)
        ) {
            return false;
        }

        if (
            activeActionMenu.submenuPortal &&
            activeActionMenu.submenuTrigger === trigger
        ) {
            return true;
        }

        closeActiveActionSubmenu();

        const portal = buildActionSubmenuPortal(trigger);

        if (!portal) {
            return false;
        }

        activeActionMenu.submenuPortal = portal;
        activeActionMenu.submenuTrigger = trigger;
        trigger.setAttribute("aria-expanded", "true");
        positionActionSubmenuPortal();
        portal.style.visibility = "visible";

        return true;
    }

    function focusFirstActionSubmenuItem() {
        window.requestAnimationFrame(function () {
            const firstItem =
                activeActionMenu?.submenuPortal?.querySelector(
                    `${getActionMenuItemSelector()}:not([disabled]):not([aria-disabled='true'])`
                );

            if (firstItem instanceof HTMLElement) {
                firstItem.focus({ preventScroll: true });
            }
        });
    }

    function findSourceActionMenuItem(menu, portalItem) {
        const action = readMenuAction(portalItem);

        if (!menu || !action) {
            return null;
        }

        return Array.from(menu.querySelectorAll(getActionMenuItemSelector())).find(function (item) {
            return readMenuAction(item) === action;
        }) || null;
    }

    function closeActiveActionMenu() {
        if (!activeActionMenu) {
            return false;
        }

        closeActiveActionSubmenu();

        const {
            button,
            menu,
            portal,
            sourcePopover
        } = activeActionMenu;

        menu?.classList.remove(OPEN_CLASS);

        if (button) {
            button.setAttribute("aria-expanded", "false");
        }

        if (sourcePopover) {
            sourcePopover.classList.remove(OPEN_CLASS);
            sourcePopover.hidden = true;
            sourcePopover.setAttribute("aria-hidden", "true");
        }

        if (portal?.parentNode) {
            portal.parentNode.removeChild(portal);
        }

        activeActionMenu.submenuPointerIntentGuard?.dispose?.();
        activeActionMenu = null;

        return true;
    }

    function closeActionMenu(menu) {
        if (!menu) {
            return false;
        }

        if (activeActionMenu?.menu === menu) {
            return closeActiveActionMenu();
        }

        const button = getActionMenuButton(menu);
        const popover = getActionPopover(menu, button);

        menu.classList.remove(OPEN_CLASS);

        if (button) {
            button.setAttribute("aria-expanded", "false");
        }

        if (popover) {
            popover.classList.remove(OPEN_CLASS);
            popover.hidden = true;
            popover.setAttribute("aria-hidden", "true");
        }

        return true;
    }

    function closeActionMenus(explorer, exceptMenu) {
        if (
            activeActionMenu &&
            activeActionMenu.menu !== exceptMenu
        ) {
            closeActiveActionMenu();
        }

        Array.from(
            explorer?.querySelectorAll(getActionMenuSelector()) || []
        ).forEach(function (menu) {
            if (menu === exceptMenu) {
                return;
            }

            closeActionMenu(menu);
        });
    }

    function openActionMenu(explorer, menu, button, options) {
        const popover = getActionPopover(menu, button);
        const cleanOptions = options || {};

        if (!explorer || !menu || !button || !popover) {
            return false;
        }

        closeActionMenus(explorer, menu);

        menu.classList.add(OPEN_CLASS);
        button.setAttribute("aria-expanded", "true");
        popover.classList.remove(OPEN_CLASS);
        popover.hidden = true;
        popover.setAttribute("aria-hidden", "true");

        activeActionMenu = {
            explorer,
            menu,
            button,
            sourcePopover: popover,
            contextPoint: getActionMenuContextPoint(cleanOptions),
            portal: null,
            submenuPortal: null,
            submenuTrigger: null,
            submenuPointerIntentGuard: createSubmenuPointerIntentGuard()
        };
        const row = getRowFromTarget(explorer, menu);
        emitMenuEvent(
            explorer,
            row,
            "",
            button,
            cleanOptions.mode
        );

        activeActionMenu.portal = buildActionMenuPortal(popover, cleanOptions);

        return true;
    }

    function toggleActionMenu(explorer, menu, button, options) {
        if (!menu || !button) {
            return false;
        }

        if (
            activeActionMenu?.menu === menu ||
            button.getAttribute("aria-expanded") === "true"
        ) {
            return closeActionMenu(menu);
        }

        return openActionMenu(explorer, menu, button, options);
    }

    function handleActionMenuItem(explorer, item, options) {
        const row = getRowFromTarget(explorer, item);
        const action = readMenuAction(item);
        const cleanOptions = options || {};
        const mode = cleanOptions.mode || "button";

        if (row) {
            selectRow(explorer, row, {
                selectionIntent: "action_menu",
                openInspector: false
            });
        }

        if (!row) {
            closeActionMenus(explorer);
            return false;
        }

        const actionEvent = emitActionEvent(
            explorer,
            row,
            action,
            item,
            mode
        );

        closeActionMenus(explorer);

        if (actionEvent?.defaultPrevented) {
            return true;
        }

        if (isOpenAction(action, item)) {
            return openRow(
                row,
                explorer,
                {
                    mode
                }
            );
        }

        return false;
    }

    function handleActionMenuPortalClick(event) {
        if (!activeActionMenu) {
            return;
        }

        const target = getEventTarget(event);

        if (!target) {
            return;
        }

        const submenuTrigger =
            getActionSubmenuTriggerFromTarget(target);

        if (submenuTrigger) {
            event.preventDefault();
            event.stopPropagation();
            openActionSubmenu(submenuTrigger);
            return;
        }

        const submenuPortal = target.closest(
            `[${ACTION_SUBMENU_PORTAL_ATTRIBUTE}]`
        );

        if (
            submenuPortal &&
            activeActionMenu.submenuPortal === submenuPortal
        ) {
            const portalItem = target.closest(
                `[${ACTION_MENU_PORTAL_ITEM_ATTRIBUTE}]`
            );

            event.preventDefault();
            event.stopPropagation();

            if (!portalItem) {
                return;
            }

            const sourceItem = findSourceActionMenuItem(
                activeActionMenu.menu,
                portalItem
            );

            if (sourceItem) {
                handleActionMenuItem(
                    activeActionMenu.explorer,
                    sourceItem,
                    {
                        mode: activeActionMenu.contextPoint
                            ? "context"
                            : "button"
                    }
                );
                return;
            }

            closeActiveActionMenu();
            return;
        }

        const portalItem = target.closest(
            `[${ACTION_MENU_PORTAL_ITEM_ATTRIBUTE}]`
        );

        if (
            portalItem &&
            activeActionMenu.portal?.contains(portalItem)
        ) {
            const sourceItem = findSourceActionMenuItem(
                activeActionMenu.menu,
                portalItem
            );

            event.preventDefault();
            event.stopPropagation();

            if (sourceItem) {
                handleActionMenuItem(
                    activeActionMenu.explorer,
                    sourceItem,
                    {
                        mode: activeActionMenu.contextPoint
                            ? "context"
                            : "button"
                    }
                );
                return;
            }

            closeActiveActionMenu();
            return;
        }

        if (target.closest(`[${ACTION_MENU_PORTAL_ATTRIBUTE}]`)) {
            event.preventDefault();
            event.stopPropagation();
            return;
        }

        if (!target.closest(getActionMenuSelector())) {
            closeActiveActionMenu();
        }
    }

    function handleActionMenuPortalPointerOver(event) {
        if (!activeActionMenu) {
            return;
        }

        const target = getEventTarget(event);

        if (!target) {
            return;
        }

        const submenuTrigger =
            getActionSubmenuTriggerFromTarget(target);

        if (submenuTrigger) {
            cancelActiveSubmenuPointerIntentClose();
            openActionSubmenu(submenuTrigger);
            return;
        }

        if (
            activeActionMenu.submenuPortal &&
            target.closest(`[${ACTION_SUBMENU_PORTAL_ATTRIBUTE}]`)
        ) {
            cancelActiveSubmenuPointerIntentClose();
            return;
        }

        if (activeActionMenu.submenuPortal) {
            requestActiveSubmenuClose();
        }
    }

    function handleActionMenuPortalKeydown(event) {
        if (!activeActionMenu) {
            return;
        }

        const target = getEventTarget(event);
        const submenuTrigger =
            getActionSubmenuTriggerFromTarget(target);

        if (
            submenuTrigger &&
            ["Enter", " ", "ArrowRight"].includes(event.key)
        ) {
            event.preventDefault();
            event.stopPropagation();
            openActionSubmenu(submenuTrigger);
            focusFirstActionSubmenuItem();
            return;
        }

        if (
            activeActionMenu.submenuPortal &&
            target?.closest(`[${ACTION_SUBMENU_PORTAL_ATTRIBUTE}]`) &&
            event.key === "ArrowLeft"
        ) {
            event.preventDefault();
            event.stopPropagation();
            closeActiveActionSubmenu({
                restoreFocus: true
            });
            return;
        }

        if (
            event.key === "Escape" &&
            activeActionMenu.submenuPortal
        ) {
            event.preventDefault();
            event.stopPropagation();
            closeActiveActionSubmenu({
                restoreFocus: true
            });
            return;
        }

        if (event.key !== "Escape") {
            return;
        }

        const returnFocus = activeActionMenu.button;

        event.preventDefault();
        event.stopPropagation();
        closeActiveActionMenu();
        returnFocus?.focus({ preventScroll: true });
    }

    function handleActionMenuViewportChange() {
        if (activeActionMenu) {
            positionActionMenuPortal();
        }
    }

    function ensureActionMenuPortalController() {
        if (actionMenuPortalControllerReady) {
            return;
        }

        actionMenuPortalControllerReady = true;
        document.addEventListener(
            "click",
            handleActionMenuPortalClick,
            true
        );
        document.addEventListener(
            "pointerover",
            handleActionMenuPortalPointerOver,
            true
        );
        document.addEventListener(
            "keydown",
            handleActionMenuPortalKeydown,
            true
        );
        window.addEventListener(
            "resize",
            handleActionMenuViewportChange
        );
        window.addEventListener(
            "scroll",
            handleActionMenuViewportChange,
            true
        );
    }

    function handleDocumentInspectorClear(event) {
        const detail = event?.detail || {};

        if (detail.clearSelection === false) {
            return;
        }

        clearWorkspaceListingSelection(
            document,
            {
                closeMenus: true,
                reason: normalizeText(detail.reason) || "document_inspector_clear"
            }
        );
    }

    function ensureDocumentInspectorClearController() {
        if (documentInspectorClearControllerReady) {
            return;
        }

        documentInspectorClearControllerReady = true;
        document.addEventListener(
            DOCUMENT_INSPECTOR_CLEAR_EVENT,
            handleDocumentInspectorClear
        );
    }

    function setLayout(explorer, layout) {
        const c = getConstants();
        const cleanLayout =
            layout === "grid" ? "grid" : "list";
        const listing = getListingForExplorer(explorer);

        explorer.setAttribute(
            c.WORKSPACE_LISTING_LAYOUT_ATTRIBUTE,
            cleanLayout
        );

        if (
            c.WORKSPACE_LEGACY_DOCUMENT_LAYOUT_ATTRIBUTE &&
            explorer.hasAttribute(
                c.WORKSPACE_LEGACY_DOCUMENT_LAYOUT_ATTRIBUTE
            )
        ) {
            explorer.setAttribute(
                c.WORKSPACE_LEGACY_DOCUMENT_LAYOUT_ATTRIBUTE,
                cleanLayout
            );
        }

        if (listing) {
            listing.setAttribute(
                c.WORKSPACE_LISTING_LAYOUT_ATTRIBUTE,
                cleanLayout
            );

            if (
                c.WORKSPACE_LEGACY_DOCUMENT_LAYOUT_ATTRIBUTE &&
                listing.hasAttribute(
                    c.WORKSPACE_LEGACY_DOCUMENT_LAYOUT_ATTRIBUTE
                )
            ) {
                listing.setAttribute(
                    c.WORKSPACE_LEGACY_DOCUMENT_LAYOUT_ATTRIBUTE,
                    cleanLayout
                );
            }
        }

        Array.from(
            explorer.querySelectorAll(
                c.WORKSPACE_LISTING_LAYOUT_BUTTON_SELECTOR ||
                "[data-workspace-listing-layout-option]"
            ) || []
        ).forEach(function (button) {
            const option = readAttribute(button, [
                "data-workspace-listing-layout-option",
                "data-document-layout-option"
            ]);
            const active = option === cleanLayout;

            button.classList.toggle(ACTIVE_CLASS, active);
            button.setAttribute(
                "aria-pressed",
                active ? "true" : "false"
            );
        });
    }

    function getLayoutButtonFromTarget(explorer, target) {
        const c = getConstants();

        if (!explorer || !target) {
            return null;
        }

        const button = target.closest(
            c.WORKSPACE_LISTING_LAYOUT_BUTTON_SELECTOR ||
            "[data-workspace-listing-layout-option]"
        );

        if (!button || !explorer.contains(button)) {
            return null;
        }

        return button;
    }

    function handleClick(event, explorer) {
        const target = getEventTarget(event);
        const layoutButton = getLayoutButtonFromTarget(
            explorer,
            target
        );

        if (layoutButton) {
            event.preventDefault();
            event.stopPropagation();

            setLayout(
                explorer,
                readAttribute(layoutButton, [
                    "data-workspace-listing-layout-option",
                    "data-document-layout-option"
                ])
            );

            return;
        }

        const actionButton = getActionMenuButtonFromTarget(
            explorer,
            target
        );

        if (actionButton) {
            event.preventDefault();
            event.stopPropagation();

            const menu = getActionMenuFromTarget(
                explorer,
                actionButton
            );

            toggleActionMenu(
                explorer,
                menu,
                actionButton,
                {
                    mode: "button"
                }
            );

            return;
        }

        const actionItem = getActionMenuItemFromTarget(
            explorer,
            target
        );

        if (actionItem) {
            event.preventDefault();
            event.stopPropagation();

            handleActionMenuItem(
                explorer,
                actionItem,
                {
                    mode: "button"
                }
            );

            return;
        }

        const row = getRowFromTarget(
            explorer,
            target
        );

        if (!row || isInteractiveTarget(target, row)) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        closeActionMenus(explorer);
        selectRow(explorer, row, {
            selectionIntent: "primary_selection",
            openInspector: true
        });
    }

    function handleDoubleClick(event, explorer) {
        const target = getEventTarget(event);
        const row = getRowFromTarget(
            explorer,
            target
        );

        if (!row || isInteractiveTarget(target, row)) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        closeActionMenus(explorer);
        selectRow(explorer, row, {
            selectionIntent: "primary_open",
            openInspector: false
        });
        openRow(
            row,
            explorer,
            {
                mode: "double_click"
            }
        );
    }

    function handleContextMenu(event, explorer) {
        const target = getEventTarget(event);
        const row = getRowFromTarget(
            explorer,
            target
        );

        if (!row) {
            closeActionMenus(explorer);
            return;
        }

        const menu = getActionMenuFromRow(row);
        const button = getActionMenuButton(menu);

        event.preventDefault();
        event.stopPropagation();

        selectRow(explorer, row, {
            focus: true,
            preventScroll: true,
            selectionIntent: "context_menu",
            openInspector: false
        });

        if (!menu || !button) {
            closeActionMenus(explorer);
            return;
        }

        openActionMenu(
            explorer,
            menu,
            button,
            {
                mode: "context",
                clientX: event.clientX,
                clientY: event.clientY
            }
        );
    }

    function handleKeyDown(event, explorer) {
        const target = getEventTarget(event);
        const row = getRowFromTarget(
            explorer,
            target
        );

        if (!row) {
            return;
        }

        if (event.key === "Enter") {
            event.preventDefault();
            event.stopPropagation();

            closeActionMenus(explorer);
            selectRow(explorer, row, {
                selectionIntent: "keyboard_open",
                openInspector: false
            });
            openRow(
                row,
                explorer,
                {
                    mode: "keyboard"
                }
            );
            return;
        }

        if (event.key === " ") {
            event.preventDefault();
            event.stopPropagation();

            closeActionMenus(explorer);
            selectRow(explorer, row, {
                selectionIntent: "keyboard_selection",
                openInspector: true
            });
            return;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();
            event.stopPropagation();

            focusAdjacentRow(
                explorer,
                row,
                "next"
            );
            return;
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();
            event.stopPropagation();

            focusAdjacentRow(
                explorer,
                row,
                "previous"
            );
            return;
        }

        if (event.key === "Home") {
            event.preventDefault();
            event.stopPropagation();

            focusAdjacentRow(
                explorer,
                row,
                "first"
            );
            return;
        }

        if (event.key === "End") {
            event.preventDefault();
            event.stopPropagation();

            focusAdjacentRow(
                explorer,
                row,
                "last"
            );
            return;
        }

        if ((event.key === "F10" && event.shiftKey) || event.key === "ContextMenu") {
            const menu = getActionMenuFromRow(row);
            const button = getActionMenuButton(menu);

            if (!menu || !button) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();

            selectRow(explorer, row, {
                focus: true,
                preventScroll: true,
                selectionIntent: "context_menu",
                openInspector: false
            });
            openActionMenu(
                explorer,
                menu,
                button,
                {
                    mode: "button"
                }
            );
            return;
        }

        if (event.key === "Escape") {
            closeActionMenus(explorer);
        }
    }

    function initializeRows(explorer) {
        getRows(explorer).forEach(function (row) {
            if (!row.hasAttribute("role")) {
                row.setAttribute("role", "option");
            }

            if (!row.hasAttribute("tabindex")) {
                row.setAttribute("tabindex", "0");
            }

            if (!row.hasAttribute("aria-selected")) {
                row.setAttribute("aria-selected", "false");
            }
        });
    }

    function observeListingRows(explorer) {
        const listing = getListingForExplorer(explorer);

        if (!listing || explorer[ROW_MUTATION_OBSERVER_KEY]) {
            return;
        }

        const observer = new MutationObserver(function () {
            initializeRows(explorer);
        });

        observer.observe(
            listing,
            {
                childList: true,
                subtree: true
            }
        );

        explorer[ROW_MUTATION_OBSERVER_KEY] = observer;
    }

    function bindExplorer(explorer) {
        if (
            !explorer ||
            explorer.getAttribute(BOUND_ATTRIBUTE) === "true"
        ) {
            return false;
        }

        const listing = getListingForExplorer(explorer);

        if (!listing) {
            return false;
        }

        explorer.setAttribute(BOUND_ATTRIBUTE, "true");

        if (!explorer.hasAttribute(CONTRACT_ATTRIBUTE)) {
            explorer.setAttribute(
                CONTRACT_ATTRIBUTE,
                getConstants().WORKSPACE_LISTING_CONTRACT ||
                "nations_workspace_listing_v1"
            );
        }

        ensureActionMenuPortalController();
        ensureDocumentInspectorClearController();
        initializeRows(explorer);
        observeListingRows(explorer);

        explorer.addEventListener(
            "click",
            function (event) {
                handleClick(event, explorer);
            }
        );

        explorer.addEventListener(
            "dblclick",
            function (event) {
                handleDoubleClick(event, explorer);
            }
        );

        explorer.addEventListener(
            "contextmenu",
            function (event) {
                handleContextMenu(event, explorer);
            }
        );

        explorer.addEventListener(
            "keydown",
            function (event) {
                handleKeyDown(event, explorer);
            }
        );

        return true;
    }

    api.getWorkspaceListingObjectContract =
        function (row) {
            const explorer = row?.closest
                ? row.closest(buildOptInSelector())
                : null;

            return row
                ? buildRowContract(explorer, row)
                : null;
        };

    api.openWorkspaceListingObject =
        function (row, options) {
            const explorer = row?.closest
                ? row.closest(buildOptInSelector())
                : null;

            return row
                ? openRow(row, explorer, options)
                : false;
        };

    api.refreshWorkspaceListingControls =
        function (scope) {
            findOptInExplorers(scope).forEach(function (explorer) {
                initializeRows(explorer);
            });
        };

    api.clearWorkspaceListingSelection =
        function (scope, options) {
            return clearWorkspaceListingSelection(scope || document, options);
        };

    api.initializeWorkspaceListingControls =
        function (scope) {
            const explorers = findOptInExplorers(scope);
            let didBind = false;

            explorers.forEach(function (explorer) {
                if (bindExplorer(explorer)) {
                    didBind = true;
                }
            });

            return didBind;
        };
}());