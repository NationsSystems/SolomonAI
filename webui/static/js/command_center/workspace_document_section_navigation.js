/* -------------------------------------------------------------------
   FILE: workspace_document_section_navigation.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const DEFAULT_FILE_LIST_SELECTOR = "[data-document-list]";
    const DEFAULT_DOCUMENT_EXPLORER_SELECTOR = "[data-document-explorer]";
    const DEFAULT_DOCUMENT_SECTION_LINK_SELECTOR = "[data-document-section-link]";
    const DEFAULT_DOCUMENT_STATIC_LINK_SELECTOR = ".workspace-document-static-link[href], .workspace-document-collection[href]";
    const DEFAULT_DOCUMENT_SECTION_TITLE_SELECTOR = "[data-document-section-title]";
    const DEFAULT_DOCUMENT_REFRESH_BUTTON_SELECTOR = "[data-document-refresh]";
    const DEFAULT_EMPTY_TRASH_BUTTON_SELECTOR = "[data-document-empty-trash-trigger]";
    const DEFAULT_UPLOAD_TRIGGER_SELECTOR = "[data-document-upload-placeholder], [data-document-upload-trigger]";
    const DEFAULT_DOCUMENT_SECTION_CONTROL_SELECTOR = "[data-document-section-control]";
    const DEFAULT_DOCUMENT_DEFAULT_UTILITY_SELECTOR = "[data-document-default-utility-row]";
    const DEFAULT_DOCUMENT_ROW_SELECTOR = ".workspace-document-file[data-document-id]";
    const DEFAULT_DOCUMENT_ACTION_MENU_SELECTOR = "[data-document-action-menu]";
    const DEFAULT_DOCUMENT_ACTION_MENU_BUTTON_SELECTOR = "[data-document-action-menu-button]";
    const DEFAULT_DOCUMENT_ACTION_MENU_POPOVER_SELECTOR = ".workspace-document-file-action-popover";
    const DEFAULT_DOCUMENT_NEW_MENU_SELECTOR = "[data-document-new-menu]";
    const DEFAULT_DOCUMENT_NEW_MENU_TRIGGER_SELECTOR = "[data-document-new-menu-trigger]";
    const DEFAULT_DOCUMENT_NEW_MENU_PANEL_SELECTOR = "[data-document-new-menu-panel]";
    const DEFAULT_DOCUMENT_NEW_MENU_ACTION_SELECTOR = "[data-workspace-new-action]";
    const DEFAULT_DOCUMENT_NEW_MENU_CLOSE_SELECTOR = "[data-document-new-menu-close]";
    const DEFAULT_DOCUMENT_BACKGROUND_CONTEXT_SURFACE_SELECTOR = "[data-workspace-view-panel='files']";
    const DEFAULT_DOCUMENT_BACKGROUND_CONTEXT_MENU_SELECTOR = "[data-document-background-context-menu]";
    const DEFAULT_DOCUMENT_BACKGROUND_CONTEXT_MENU_ITEM_SELECTOR = "[data-document-background-context-menu-item]";
    const DEFAULT_DOCUMENT_BACKGROUND_CONTEXT_BLOCKED_SELECTOR = [
        "button",
        "a",
        "input",
        "select",
        "textarea",
        "[role='button']",
        "[role='menuitem']",
        "[data-document-action-menu]",
        "[data-document-new-menu]",
        "[data-document-section-link]",
        "[data-document-section-control]",
        "[data-document-upload-status]",
        "[data-document-drop-overlay]",
        ".workspace-document-browser-toolbar",
        ".workspace-document-selection-row",
        ".workspace-document-file[data-document-id]"
    ].join(", ");

    const DEFAULT_NEW_FOLDER_ACTION = "new_folder";
    const DEFAULT_FOLDER_CREATE_ENDPOINT = "/uploads/me/folders";
    const DEFAULT_FOLDER_NAME_MAX_LENGTH = 120;
    const FOLDER_CREATE_MODE_CURRENT_CONTAINER = "current_container";
    const FOLDER_CREATE_MODE_LOCATION_REQUIRED = "location_required";
    const FOLDER_CREATE_MODE_UNAVAILABLE = "unavailable";
    const DEFAULT_FOLDER_CREATE_ACTION_SELECTOR =
        `[data-workspace-new-action="${DEFAULT_NEW_FOLDER_ACTION}"]`;
    const BACKGROUND_CONTEXT_ACTION_NEW_FOLDER = "new_folder";
    const BACKGROUND_CONTEXT_ACTION_UPLOAD_FILE = "upload_file";
    const BACKGROUND_CONTEXT_ACTION_REFRESH = "refresh";

    const DEFAULT_DOCUMENT_SECTION = "files";
    const DOCUMENTS_MODULE_ALIASES = new Set([
        "",
        "documents",
        "home",
        "docs"
    ]);
    const DEFAULT_SECTION_ROUTES = Object.freeze({
        files: "/",
        reports: "/reports",
        recent: "/recent",
        shared: "/shared",
        trash: "/trash"
    });
    const DEFAULT_RENDERABLE_FILE_SECTIONS = Object.freeze([
        "files",
        "shared",
        "recent"
    ]);
    const DEFAULT_SECTION_UTILITY_LABELS = Object.freeze({
        files: "My Files controls",
        reports: "Reports controls",
        recent: "Recent controls",
        shared: "Shared with me controls",
        trash: "Trash controls"
    });
    const DEFAULT_FOLDER_CREATE_MODES_BY_SECTION = Object.freeze({
        files: FOLDER_CREATE_MODE_CURRENT_CONTAINER,
        reports: FOLDER_CREATE_MODE_LOCATION_REQUIRED,
        recent: FOLDER_CREATE_MODE_LOCATION_REQUIRED,
        shared: FOLDER_CREATE_MODE_UNAVAILABLE,
        trash: FOLDER_CREATE_MODE_UNAVAILABLE
    });
    const WORKSPACE_NAVIGATION_CONTRACT =
        "workspace_module_section_route";
    const WORKSPACE_RETURN_ROUTE_ATTRIBUTE =
        "data-workspace-return-route";
    const WORKSPACE_FOLDER_RETURN_PATHS = new Set([
        "/",
        "/recent",
        "/search",
        "/shared",
        "/trash"
    ]);
    const WORKSPACE_CONTEXT_MENU_OPEN_EVENT =
        "nations:workspace-context-menu-open";
    const WORKSPACE_CONTEXT_MENU_CLOSE_EVENT =
        "nations:workspace-context-menu-close";
    const WORKSPACE_CONTEXT_OBJECT = "object";
    const WORKSPACE_CONTEXT_LOCATION = "location";
    const BACKGROUND_CONTEXT_COORDINATOR_BOUND_KEY =
        "__solomonDocumentBackgroundContextCoordinatorBound";

    let sectionHistoryBound = false;
    let documentNewMenuGlobalBound = false;
    let documentNewMenuDelegationBound = false;
    let documentBackgroundContextGlobalBound = false;
    let activeFolderDialogCleanup = null;
    let activeBackgroundContextMenu = null;

    function cleanValue(value) {
        return String(value || "").trim();
    }

    function normalizeContextName(value) {
        return cleanValue(value)
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "_")
            .replace(/^_+|_+$/g, "");
    }

    function getWorkspaceModuleValue(explorer) {
        const explicitModule = cleanValue(
            explorer?.getAttribute("data-workspace-module")
        ).toLowerCase();
        const ownerModule = cleanValue(
            explorer
                ?.closest("[data-workspace-module]")
                ?.getAttribute("data-workspace-module")
        ).toLowerCase();

        return explicitModule || ownerModule;
    }

    function getSectionsApi(options) {
        return options?.Sections || window.SolomonWorkspaceDocumentSections || null;
    }

    function getConversationApi(options) {
        return options?.Conversation || window.SolomonWorkspaceDocumentConversation || null;
    }

    function getStatusApi(options) {
        return options?.Status || window.SolomonWorkspaceDocumentStatus || null;
    }

    function getSelector(options, key, fallback) {
        return cleanValue(options?.selectors?.[key]) || fallback;
    }

    function getConfig(options) {
        const cleanOptions = options || {};

        return {
            Sections: getSectionsApi(cleanOptions),
            Conversation: getConversationApi(cleanOptions),
            Status: getStatusApi(cleanOptions),
            routes: Object.assign({}, DEFAULT_SECTION_ROUTES, cleanOptions.routes || {}),
            selectors: Object.assign({}, cleanOptions.selectors || {}),
            defaultSection: cleanValue(cleanOptions.defaultSection) || DEFAULT_DOCUMENT_SECTION,
            createFolderEndpoint: cleanValue(cleanOptions.createFolderEndpoint) || DEFAULT_FOLDER_CREATE_ENDPOINT,
            backgroundContextMenuAction: cleanValue(cleanOptions.backgroundContextMenuAction) || DEFAULT_DOCUMENT_BACKGROUND_CONTEXT_MENU_ITEM_SELECTOR,
            backgroundContextSurface: cleanValue(cleanOptions.backgroundContextSurface) || DEFAULT_DOCUMENT_BACKGROUND_CONTEXT_SURFACE_SELECTOR,
            backgroundContextBlocked: cleanValue(cleanOptions.backgroundContextBlocked) || DEFAULT_DOCUMENT_BACKGROUND_CONTEXT_BLOCKED_SELECTOR,
            resetDocumentSelection: typeof cleanOptions.resetDocumentSelection === "function"
                ? cleanOptions.resetDocumentSelection
                : null,
            renderPreviewEmpty: typeof cleanOptions.renderPreviewEmpty === "function"
                ? cleanOptions.renderPreviewEmpty
                : null,
            renderEmptyFiles: typeof cleanOptions.renderEmptyFiles === "function"
                ? cleanOptions.renderEmptyFiles
                : null,
            renderFiles: typeof cleanOptions.renderFiles === "function"
                ? cleanOptions.renderFiles
                : null,
            renderTrashFiles: typeof cleanOptions.renderTrashFiles === "function"
                ? cleanOptions.renderTrashFiles
                : null,
            refreshFiles: typeof cleanOptions.refreshFiles === "function"
                ? cleanOptions.refreshFiles
                : null,
            cacheDocuments: typeof cleanOptions.cacheDocuments === "function"
                ? cleanOptions.cacheDocuments
                : null,
            getCachedDocumentSection: typeof cleanOptions.getCachedDocumentSection === "function"
                ? cleanOptions.getCachedDocumentSection
                : null,
            getFallbackDocuments: typeof cleanOptions.getFallbackDocuments === "function"
                ? cleanOptions.getFallbackDocuments
                : null,
            getInitialDocuments: typeof cleanOptions.getInitialDocuments === "function"
                ? cleanOptions.getInitialDocuments
                : null,
            openUploadPicker: typeof cleanOptions.openUploadPicker === "function"
                ? cleanOptions.openUploadPicker
                : null,
            syncDocumentUploadControls: typeof cleanOptions.syncDocumentUploadControls === "function"
                ? cleanOptions.syncDocumentUploadControls
                : null,
            syncDocumentRefreshControls: typeof cleanOptions.syncDocumentRefreshControls === "function"
                ? cleanOptions.syncDocumentRefreshControls
                : null,
            syncDocumentSectionControls: typeof cleanOptions.syncDocumentSectionControls === "function"
                ? cleanOptions.syncDocumentSectionControls
                : null,
            syncEmptyTrashControls: typeof cleanOptions.syncEmptyTrashControls === "function"
                ? cleanOptions.syncEmptyTrashControls
                : null,
            setDocumentListState: typeof cleanOptions.setDocumentListState === "function"
                ? cleanOptions.setDocumentListState
                : null,
            normalizeDocumentSection: typeof cleanOptions.normalizeDocumentSection === "function"
                ? cleanOptions.normalizeDocumentSection
                : null,
            isFetchableDocumentSection: typeof cleanOptions.isFetchableDocumentSection === "function"
                ? cleanOptions.isFetchableDocumentSection
                : null,
            getDocumentSectionLabel: typeof cleanOptions.getDocumentSectionLabel === "function"
                ? cleanOptions.getDocumentSectionLabel
                : null,
            getDocumentSectionIcon: typeof cleanOptions.getDocumentSectionIcon === "function"
                ? cleanOptions.getDocumentSectionIcon
                : null,
            getDocumentSectionEmptyState: typeof cleanOptions.getDocumentSectionEmptyState === "function"
                ? cleanOptions.getDocumentSectionEmptyState
                : null,
            getDocumentSectionEmptyCopy: typeof cleanOptions.getDocumentSectionEmptyCopy === "function"
                ? cleanOptions.getDocumentSectionEmptyCopy
                : null
        };
    }

    function clearNode(node) {
        while (node?.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function textElement(tagName, className, text) {
        const element = document.createElement(tagName);

        if (className) {
            element.className = className;
        }

        element.textContent = String(text || "");

        return element;
    }

    function normalizeDocumentSection(section, options) {
        const config = getConfig(options);

        if (config.normalizeDocumentSection) {
            return config.normalizeDocumentSection(section);
        }

        if (config.Sections && typeof config.Sections.normalizeDocumentSection === "function") {
            return config.Sections.normalizeDocumentSection(section);
        }

        return cleanValue(section).toLowerCase() || config.defaultSection;
    }

    function isFetchableDocumentSection(section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);

        if (config.isFetchableDocumentSection) {
            return config.isFetchableDocumentSection(cleanSection);
        }

        if (config.Sections && typeof config.Sections.isFetchableDocumentSection === "function") {
            return config.Sections.isFetchableDocumentSection(cleanSection);
        }

        return cleanSection === "files" || cleanSection === "trash";
    }

    function isRenderableFileSection(section, options) {
        const cleanSection = normalizeDocumentSection(section, options);

        return DEFAULT_RENDERABLE_FILE_SECTIONS.includes(cleanSection);
    }

    function getDocumentSectionLabel(section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);

        if (config.getDocumentSectionLabel) {
            return config.getDocumentSectionLabel(cleanSection);
        }

        if (config.Sections && typeof config.Sections.getDocumentSectionLabel === "function") {
            return config.Sections.getDocumentSectionLabel(cleanSection);
        }

        if (cleanSection === "trash") {
            return "Trash";
        }

        if (cleanSection === "reports") {
            return "Reports";
        }

        if (cleanSection === "recent") {
            return "Recent";
        }

        return "My Files";
    }

    function getDocumentSectionUtilityLabel(section, options) {
        const cleanSection = normalizeDocumentSection(section, options);

        return DEFAULT_SECTION_UTILITY_LABELS[cleanSection] || "Document controls";
    }

    function getDocumentSectionIcon(section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);

        if (config.getDocumentSectionIcon) {
            return config.getDocumentSectionIcon(cleanSection);
        }

        if (config.Sections && typeof config.Sections.getDocumentSectionIcon === "function") {
            return config.Sections.getDocumentSectionIcon(cleanSection);
        }

        if (cleanSection === "trash") {
            return "delete";
        }

        if (cleanSection === "reports") {
            return "article";
        }

        if (cleanSection === "recent") {
            return "schedule";
        }

        return "folder_open";
    }

    function getDocumentSectionEmptyState(section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);

        if (config.getDocumentSectionEmptyState) {
            return config.getDocumentSectionEmptyState(cleanSection) || {};
        }

        if (config.Sections && typeof config.Sections.getDocumentSectionEmptyState === "function") {
            return config.Sections.getDocumentSectionEmptyState(cleanSection) || {};
        }

        return {};
    }

    function getDocumentSectionEmptyCopy(section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);

        if (config.getDocumentSectionEmptyCopy) {
            return config.getDocumentSectionEmptyCopy(cleanSection);
        }

        if (config.Sections && typeof config.Sections.getDocumentSectionEmptyCopy === "function") {
            return config.Sections.getDocumentSectionEmptyCopy(cleanSection);
        }

        return "";
    }

    function normalizeWorkspaceRoutePath(pathname, options) {
        const config = getConfig(options);

        if (config.Sections && typeof config.Sections.normalizeRoutePath === "function") {
            return config.Sections.normalizeRoutePath(pathname);
        }

        const cleanPath = String(pathname || "/")
            .trim()
            .split("?")[0]
            .replace(/\/+$/, "");

        return cleanPath || "/";
    }

    function getWorkspaceSectionPath(section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);

        return cleanValue(config.routes[cleanSection]) || config.routes.files || "/";
    }

    function getWorkspaceSectionFromPath(pathname, options) {
        const config = getConfig(options);
        const cleanPath = normalizeWorkspaceRoutePath(pathname, config);
        let matchedSection = config.defaultSection;

        Object.entries(config.routes).some(function (entry) {
            if (normalizeWorkspaceRoutePath(entry[1], config) !== cleanPath) {
                return false;
            }

            matchedSection = normalizeDocumentSection(entry[0], config);
            return true;
        });

        return matchedSection;
    }

    function getWorkspaceNavigationContractRoot(explorer) {
        if (!explorer) {
            return null;
        }

        return explorer.closest(
            `[data-workspace-navigation-contract="${WORKSPACE_NAVIGATION_CONTRACT}"]`
        );
    }

    function getInitialWorkspaceRoutePath(explorer, options) {
        const config = getConfig(options);
        const explorerRoute = cleanValue(
            explorer?.getAttribute("data-workspace-route")
        );
        const contractRoot = getWorkspaceNavigationContractRoot(explorer);
        const contractRoute = cleanValue(
            contractRoot?.getAttribute("data-workspace-route")
        );
        const renderedRoute = explorerRoute || contractRoute;

        if (renderedRoute && isWorkspaceSectionPath(renderedRoute, config)) {
            return normalizeWorkspaceRoutePath(renderedRoute, config);
        }

        return normalizeWorkspaceRoutePath(
            window.location.pathname,
            config
        );
    }

    function isShellNavigationOwnedLink(link) {
        return Boolean(
            link?.getAttribute("data-command-shell-navigation") === "true" ||
            link?.getAttribute("data-command-navigation-contract") ===
                WORKSPACE_NAVIGATION_CONTRACT
        );
    }

    function syncWorkspaceNavigationContract(explorer, section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);

        if (!explorer || !isKnownDocumentSection(cleanSection, config)) {
            return;
        }

        const routePath = normalizeWorkspaceRoutePath(
            getWorkspaceSectionPath(cleanSection, config),
            config
        );
        const contractRoot = getWorkspaceNavigationContractRoot(explorer);
        const workspaceRoot = contractRoot || explorer?.closest(
            ".workspace-command-app, .precon-app-page"
        );

        explorer.setAttribute("data-workspace-section", cleanSection);
        explorer.setAttribute("data-workspace-route", routePath);
        explorer.setAttribute(
            "data-workspace-navigation-contract",
            WORKSPACE_NAVIGATION_CONTRACT
        );

        if (workspaceRoot && workspaceRoot !== explorer) {
            workspaceRoot.setAttribute("data-workspace-section", cleanSection);
            workspaceRoot.setAttribute("data-workspace-route", routePath);
            workspaceRoot.setAttribute(
                "data-workspace-navigation-contract",
                WORKSPACE_NAVIGATION_CONTRACT
            );
        }
    }

    function isWorkspaceSectionPath(pathname, options) {
        const config = getConfig(options);
        const cleanPath = normalizeWorkspaceRoutePath(pathname, config);

        return Object.values(config.routes).some(function (routePath) {
            return normalizeWorkspaceRoutePath(routePath, config) === cleanPath;
        });
    }

    function isKnownDocumentSection(section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);

        return Object.prototype.hasOwnProperty.call(
            config.routes,
            cleanSection
        );
    }

    function isDocumentSectionExplorer(explorer, options) {
        const config = getConfig(options);
        const moduleId = getWorkspaceModuleValue(explorer);

        if (!explorer) {
            return false;
        }

        if (!DOCUMENTS_MODULE_ALIASES.has(moduleId)) {
            return false;
        }

        if (isKnownDocumentSection(
            explorer.getAttribute("data-workspace-section"),
            config
        )) {
            return true;
        }

        return isWorkspaceSectionPath(
            getInitialWorkspaceRoutePath(explorer, config),
            config
        );
    }

    function setDocumentListState(explorer, section, state, options) {
        const config = getConfig(options);

        if (config.setDocumentListState) {
            config.setDocumentListState(explorer, section, state);
            return;
        }

        const listSelector = getSelector(config, "fileList", DEFAULT_FILE_LIST_SELECTOR);
        const list = explorer?.querySelector(listSelector);
        const cleanSection = normalizeDocumentSection(section, config);
        const cleanState = cleanValue(state).toLowerCase() || "idle";

        if (!explorer || !list) {
            return;
        }

        explorer.setAttribute("data-document-section-state", cleanState);
        explorer.setAttribute("data-document-section-state-for", cleanSection);
        list.setAttribute("data-document-list-state", cleanState);
        list.setAttribute("data-document-list-section", cleanSection);
        list.setAttribute("aria-busy", ["loading", "refreshing"].includes(cleanState) ? "true" : "false");

        syncEmptyTrashControls(explorer, cleanSection, Object.assign({}, config, {
            state: cleanState
        }));
    }

    function sectionControlMatchesTarget(target, section, options) {
        const config = getConfig(options);
        const cleanTarget = cleanValue(target).toLowerCase();
        const cleanSection = normalizeDocumentSection(section, config);

        if (!cleanTarget || cleanTarget === "all") {
            return true;
        }

        if (cleanTarget === "not-trash") {
            return cleanSection !== "trash";
        }

        if (cleanTarget === "fetchable") {
            return isFetchableDocumentSection(cleanSection, config);
        }

        if (cleanTarget === "non-fetchable") {
            return !isFetchableDocumentSection(cleanSection, config);
        }

        return cleanTarget
            .split(",")
            .map(function (entry) {
                return normalizeDocumentSection(entry, config);
            })
            .includes(cleanSection);
    }

    function setSectionControlVisibility(control, shouldShow) {
        if (!control) {
            return;
        }

        control.hidden = !shouldShow;

        if (shouldShow) {
            control.removeAttribute("hidden");
            control.setAttribute("aria-hidden", "false");
        } else {
            control.setAttribute("aria-hidden", "true");
        }

        if (control.tagName === "BUTTON") {
            control.disabled = !shouldShow;
        }
    }

    function hasRenderedDocumentRows(explorer, options) {
        const config = getConfig(options);
        const rowSelector = getSelector(config, "documentRow", DEFAULT_DOCUMENT_ROW_SELECTOR);
        const listSelector = getSelector(config, "fileList", DEFAULT_FILE_LIST_SELECTOR);
        const list = explorer?.querySelector(listSelector);

        if (!explorer || !list) {
            return false;
        }

        return Array.from(list.querySelectorAll(rowSelector)).some(function (row) {
            return !row.hidden && row.getAttribute("aria-hidden") !== "true";
        });
    }

    function getEmptyTrashState(explorer, section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);
        const explicitState = cleanValue(options?.state).toLowerCase();
        const sectionState = explicitState || cleanValue(explorer?.getAttribute("data-document-section-state")).toLowerCase();

        if (cleanSection !== "trash") {
            return "hidden";
        }

        if (["loading", "refreshing", "syncing"].includes(sectionState)) {
            return "loading";
        }

        if (sectionState === "error") {
            return "error";
        }

        if (hasRenderedDocumentRows(explorer, config)) {
            return "ready";
        }

        return "empty";
    }

    function setEmptyTrashButtonState(button, state) {
        const cleanState = cleanValue(state).toLowerCase() || "empty";
        const isReady = cleanState === "ready";
        const label = isReady
            ? "Empty trash"
            : cleanState === "loading"
                ? "Trash is still loading."
                : cleanState === "error"
                    ? "Trash could not be loaded."
                    : "Trash is empty.";

        button.disabled = !isReady;
        button.setAttribute("aria-disabled", isReady ? "false" : "true");
        button.setAttribute("data-document-empty-trash-state", cleanState);
        button.setAttribute("title", label);
        button.setAttribute("aria-label", label);
    }

    function syncEmptyTrashControls(explorer, section, options) {
        const config = getConfig(options);

        if (config.syncEmptyTrashControls) {
            config.syncEmptyTrashControls(explorer, section);
            return;
        }

        const emptyTrashSelector = getSelector(config, "emptyTrashButton", DEFAULT_EMPTY_TRASH_BUTTON_SELECTOR);
        const cleanSection = normalizeDocumentSection(section, config);
        const emptyTrashState = getEmptyTrashState(explorer, cleanSection, config);

        explorer?.querySelectorAll(emptyTrashSelector).forEach(function (button) {
            const isVisibleBySection = sectionControlMatchesTarget(
                button.getAttribute("data-document-section-control") || "trash",
                cleanSection,
                config
            );

            setSectionControlVisibility(button, isVisibleBySection);

            if (!isVisibleBySection) {
                button.setAttribute("aria-disabled", "true");
                button.setAttribute("data-document-empty-trash-state", "hidden");
                return;
            }

            setEmptyTrashButtonState(button, emptyTrashState);
        });
    }

    function isElementUnavailable(element) {
        if (!element) {
            return true;
        }

        return Boolean(
            element.hidden ||
            element.disabled ||
            element.getAttribute("aria-hidden") === "true" ||
            element.getAttribute("aria-disabled") === "true"
        );
    }

    function isNewFolderAction(action) {
        return cleanValue(
            action?.getAttribute("data-workspace-new-action")
        ) === DEFAULT_NEW_FOLDER_ACTION;
    }

    function normalizeFolderName(value) {
        return String(value || "")
            .replace(/\s+/g, " ")
            .trim();
    }

    function normalizeFolderCreateMode(value) {
        const cleanMode = cleanValue(value).toLowerCase();

        if (
            cleanMode === FOLDER_CREATE_MODE_CURRENT_CONTAINER ||
            cleanMode === FOLDER_CREATE_MODE_LOCATION_REQUIRED ||
            cleanMode === FOLDER_CREATE_MODE_UNAVAILABLE
        ) {
            return cleanMode;
        }

        return "";
    }

    function getNearestDataValue(source, attributeNames) {
        const cleanNames = Array.isArray(attributeNames)
            ? attributeNames
            : [];
        let current = source || null;

        while (current && current !== document.documentElement) {
            for (const attributeName of cleanNames) {
                const value = cleanValue(
                    current.getAttribute?.(attributeName)
                );

                if (value) {
                    return value;
                }
            }

            current = current.parentElement || null;
        }

        return "";
    }

    function getSectionFolderCreateMode(section, options) {
        const cleanSection = normalizeDocumentSection(section, options);

        return (
            DEFAULT_FOLDER_CREATE_MODES_BY_SECTION[cleanSection] ||
            FOLDER_CREATE_MODE_LOCATION_REQUIRED
        );
    }

    function getFolderCreateMode(explorer, action, options) {
        const explicitMode = (
            getNearestDataValue(action, [
                "data-workspace-folder-create-mode",
                "data-folder-create-mode",
                "data-document-folder-create-mode"
            ]) ||
            getNearestDataValue(explorer, [
                "data-workspace-folder-create-mode",
                "data-folder-create-mode",
                "data-document-folder-create-mode"
            ])
        );
        const cleanMode = normalizeFolderCreateMode(explicitMode);

        if (cleanMode) {
            return cleanMode;
        }

        return getSectionFolderCreateMode(
            explorer?.getAttribute("data-workspace-section"),
            options
        );
    }

    function isFolderCreateEnabled(explorer, action, options) {
        const mode = getFolderCreateMode(explorer, action, options);
        const enabledValue = cleanValue(
            getNearestDataValue(action, [
                "data-workspace-folder-create-enabled",
                "data-folder-create-enabled",
                "data-document-folder-create-enabled"
            ]) ||
            getNearestDataValue(explorer, [
                "data-workspace-folder-create-enabled",
                "data-folder-create-enabled",
                "data-document-folder-create-enabled"
            ])
        ).toLowerCase();

        if (enabledValue === "false") {
            return false;
        }

        return mode === FOLDER_CREATE_MODE_CURRENT_CONTAINER;
    }

    function getFolderCreateBlockedMessage(mode) {
        if (mode === FOLDER_CREATE_MODE_UNAVAILABLE) {
            return "Folder creation is not available here.";
        }

        if (mode === FOLDER_CREATE_MODE_LOCATION_REQUIRED) {
            return "Open My Files to choose a folder destination.";
        }

        return "Folder creation is not available from this view.";
    }

    function getFolderCreateSummary(mode, currentFolderId) {
        if (mode === FOLDER_CREATE_MODE_CURRENT_CONTAINER) {
            return currentFolderId
                ? "Create a folder here."
                : "Create a folder in My Files.";
        }

        if (mode === FOLDER_CREATE_MODE_LOCATION_REQUIRED) {
            return "Open My Files to choose a destination.";
        }

        return "Folder creation is unavailable here.";
    }

    function getFolderDialogDescription(explorer, action, options) {
        const currentFolderId = getCurrentFolderId(explorer, action);
        const mode = getFolderCreateMode(explorer, action, options);

        return getFolderCreateSummary(mode, currentFolderId);
    }

    function getFolderCreateEndpoint(explorer, action, options) {
        const config = getConfig(options);
        const endpoint = (
            getNearestDataValue(action, [
                "data-folder-create-endpoint",
                "data-workspace-folder-create-endpoint",
                "data-document-folder-create-endpoint"
            ]) ||
            getNearestDataValue(explorer, [
                "data-folder-create-endpoint",
                "data-workspace-folder-create-endpoint",
                "data-document-folder-create-endpoint"
            ]) ||
            config.createFolderEndpoint ||
            DEFAULT_FOLDER_CREATE_ENDPOINT
        );

        return cleanValue(endpoint) || DEFAULT_FOLDER_CREATE_ENDPOINT;
    }

    function getCurrentFolderId(explorer, action) {
        return (
            getNearestDataValue(action, [
                "data-workspace-current-folder-id",
                "data-current-folder-id",
                "data-folder-id",
                "data-parent-folder-id"
            ]) ||
            getNearestDataValue(explorer, [
                "data-workspace-current-folder-id",
                "data-current-folder-id",
                "data-folder-id",
                "data-parent-folder-id"
            ])
        );
    }

    function getOrCreateDocumentActionStatus(explorer) {
        if (!explorer) {
            return null;
        }

        let status = explorer.querySelector(
            "[data-document-action-status]"
        );

        if (status) {
            return status;
        }

        status = document.createElement("div");
        status.className = "workspace-document-action-status";
        status.setAttribute("data-document-action-status", "");
        status.setAttribute("role", "status");
        status.setAttribute("aria-live", "polite");
        status.setAttribute("aria-atomic", "true");

        explorer.insertBefore(status, explorer.firstChild);

        return status;
    }

    function announceDocumentAction(explorer, message, state) {
        const cleanMessage = cleanValue(message);
        const cleanState = cleanValue(state).toLowerCase() || "info";
        const status = getOrCreateDocumentActionStatus(explorer);

        if (!cleanMessage) {
            return;
        }

        if (status) {
            status.textContent = cleanMessage;
            status.setAttribute("data-document-action-status-state", cleanState);
        }

        explorer?.dispatchEvent(new CustomEvent("solomon:document-action-status", {
            bubbles: true,
            detail: {
                message: cleanMessage,
                state: cleanState
            }
        }));
    }

    function setActionBusy(action, isBusy) {
        if (!action) {
            return;
        }

        if (isBusy) {
            action.__solomonPreviousDisabled = Boolean(action.disabled);
            action.__solomonPreviousAriaDisabled = cleanValue(
                action.getAttribute("aria-disabled")
            );

            action.setAttribute("aria-busy", "true");
            action.setAttribute("aria-disabled", "true");

            if (action.tagName === "BUTTON") {
                action.disabled = true;
            }

            return;
        }

        action.setAttribute("aria-busy", "false");

        if (action.__solomonPreviousAriaDisabled) {
            action.setAttribute(
                "aria-disabled",
                action.__solomonPreviousAriaDisabled
            );
        } else {
            action.setAttribute("aria-disabled", "false");
        }

        if (action.tagName === "BUTTON") {
            action.disabled = action.__solomonPreviousDisabled === true;
        }

        delete action.__solomonPreviousDisabled;
        delete action.__solomonPreviousAriaDisabled;
    }

    function closeActiveFolderDialog() {
        if (typeof activeFolderDialogCleanup === "function") {
            activeFolderDialogCleanup();
        }

        activeFolderDialogCleanup = null;
    }

    function createFolderDialogElement(dialogOptions) {
        const cleanOptions = dialogOptions || {};
        const descriptionText = (
            cleanValue(cleanOptions.description) ||
            "Create a folder in My Files."
        );
        const maxNameLength = Number.isFinite(cleanOptions.maxNameLength)
            ? cleanOptions.maxNameLength
            : DEFAULT_FOLDER_NAME_MAX_LENGTH;
        const overlay = document.createElement("div");
        const dialog = document.createElement("section");
        const title = textElement(
            "h2",
            "workspace-folder-dialog-title",
            "New folder"
        );
        const description = textElement(
            "p",
            "workspace-folder-dialog-description",
            descriptionText
        );
        const form = document.createElement("form");
        const label = textElement(
            "label",
            "workspace-folder-dialog-label",
            "Folder name"
        );
        const input = document.createElement("input");
        const error = textElement(
            "p",
            "workspace-folder-dialog-error",
            ""
        );
        const actions = document.createElement("div");
        const cancelButton = document.createElement("button");
        const createButton = document.createElement("button");
        const dialogId = `workspace-folder-dialog-${Date.now()}`;
        const titleId = `${dialogId}-title`;
        const descriptionId = `${dialogId}-description`;
        const errorId = `${dialogId}-error`;

        overlay.className = "workspace-folder-dialog-backdrop";
        overlay.setAttribute("data-document-folder-dialog", "");

        dialog.className = "workspace-folder-dialog";
        dialog.setAttribute("role", "dialog");
        dialog.setAttribute("aria-modal", "true");
        dialog.setAttribute("aria-labelledby", titleId);
        dialog.setAttribute("aria-describedby", `${descriptionId} ${errorId}`);

        title.id = titleId;
        description.id = descriptionId;
        error.id = errorId;
        error.setAttribute("aria-live", "polite");

        form.className = "workspace-folder-dialog-form";
        form.setAttribute("novalidate", "");

        input.type = "text";
        input.className = "workspace-folder-dialog-input";
        input.name = "folder_name";
        input.maxLength = maxNameLength;
        input.required = true;
        input.autocomplete = "off";
        input.setAttribute("aria-describedby", errorId);

        label.appendChild(input);

        actions.className = "workspace-folder-dialog-actions";

        cancelButton.type = "button";
        cancelButton.className = "workspace-folder-dialog-button workspace-folder-dialog-button-secondary";
        cancelButton.textContent = "Cancel";

        createButton.type = "submit";
        createButton.className = "workspace-folder-dialog-button workspace-folder-dialog-button-primary";
        createButton.textContent = "Create";

        actions.append(cancelButton, createButton);
        form.append(label, error, actions);
        dialog.append(title, description, form);
        overlay.appendChild(dialog);

        return {
            overlay,
            dialog,
            form,
            input,
            error,
            cancelButton,
            createButton
        };
    }

    function requestWorkspaceFolderName(dialogOptions) {
        return new Promise(function (resolve) {
            const previousFocus = document.activeElement;
            const parts = createFolderDialogElement(dialogOptions);
            let resolved = false;

            function cleanup(value) {
                if (resolved) {
                    return;
                }

                resolved = true;
                parts.overlay.remove();
                document.removeEventListener("keydown", handleKeydown);
                activeFolderDialogCleanup = null;

                if (previousFocus && typeof previousFocus.focus === "function") {
                    previousFocus.focus();
                }

                resolve(value);
            }

            function setError(message) {
                parts.error.textContent = cleanValue(message);

                if (parts.error.textContent) {
                    parts.input.setAttribute("aria-invalid", "true");
                } else {
                    parts.input.removeAttribute("aria-invalid");
                }
            }

            function handleSubmit(event) {
                event.preventDefault();

                const folderName = normalizeFolderName(parts.input.value);

                if (!folderName) {
                    setError("Enter a folder name.");
                    parts.input.focus();
                    return;
                }

                cleanup(folderName);
            }

            function handleKeydown(event) {
                if (event.key === "Escape") {
                    event.preventDefault();
                    cleanup("");
                }
            }

            closeActiveFolderDialog();
            activeFolderDialogCleanup = function () {
                cleanup("");
            };

            parts.form.addEventListener("submit", handleSubmit);
            parts.cancelButton.addEventListener("click", function () {
                cleanup("");
            });
            parts.overlay.addEventListener("click", function (event) {
                if (event.target === parts.overlay) {
                    cleanup("");
                }
            });
            parts.input.addEventListener("input", function () {
                setError("");
            });
            document.addEventListener("keydown", handleKeydown);

            document.body.appendChild(parts.overlay);
            parts.input.focus();
        });
    }

    async function postWorkspaceFolderCreate(explorer, action, folderName, options) {
        const config = getConfig(options);
        const endpoint = getFolderCreateEndpoint(explorer, action, config);
        const parentFolderId = getCurrentFolderId(explorer, action);
        const payload = {
            name: folderName
        };

        if (parentFolderId) {
            payload.parent_folder_id = parentFolderId;
        }

        const response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify(payload)
        });
        const data = await response.json().catch(function () {
            return {};
        });

        if (!response.ok || data.ok === false) {
            throw new Error(
                data.error ||
                data.detail ||
                "Folder could not be created."
            );
        }

        return data;
    }

    function getRefreshSectionAfterFolderCreate(explorer, options) {
        const config = getConfig(options);
        const section = normalizeDocumentSection(
            explorer?.getAttribute("data-workspace-section"),
            config
        );

        if (section === "trash" || section === "reports") {
            return DEFAULT_DOCUMENT_SECTION;
        }

        return isFetchableDocumentSection(section, config)
            ? section
            : DEFAULT_DOCUMENT_SECTION;
    }

    async function createWorkspaceFolderFromAction(explorer, action, options) {
        const config = getConfig(options);

        if (!explorer || !action || action.__solomonFolderCreateInFlight) {
            return;
        }

        const createMode = getFolderCreateMode(explorer, action, config);

        if (!isFolderCreateEnabled(explorer, action, config)) {
            announceDocumentAction(
                explorer,
                getFolderCreateBlockedMessage(createMode),
                "info"
            );
            return;
        }

        const folderName = await requestWorkspaceFolderName({
            description: getFolderDialogDescription(
                explorer,
                action,
                config
            ),
            maxNameLength: DEFAULT_FOLDER_NAME_MAX_LENGTH
        });

        if (!folderName) {
            return;
        }

        action.__solomonFolderCreateInFlight = true;
        setActionBusy(action, true);
        announceDocumentAction(explorer, `Creating “${folderName}”.`, "loading");

        try {
            const response = await postWorkspaceFolderCreate(
                explorer,
                action,
                folderName,
                config
            );
            const folder = response.folder || response.item || null;
            const refreshSection = getRefreshSectionAfterFolderCreate(
                explorer,
                config
            );

            explorer.dispatchEvent(new CustomEvent("solomon:workspace-folder-created", {
                bubbles: true,
                detail: {
                    folder,
                    response,
                    section: refreshSection
                }
            }));

            announceDocumentAction(explorer, `Created folder “${folderName}”.`, "success");

            if (config.refreshFiles) {
                config.refreshFiles(explorer, {
                    quiet: true,
                    section: refreshSection,
                    source: "folder_create_sync"
                });
            }

            refreshWorkspaceFolderTreeCurrentContainer(explorer);
        } catch (error) {
            console.warn("[DOCUMENT_SECTIONS][FOLDER] Folder creation failed.", error);
            announceDocumentAction(
                explorer,
                error?.message || "Folder could not be created.",
                "error"
            );
        } finally {
            action.__solomonFolderCreateInFlight = false;
            setActionBusy(action, false);
        }
    }

    function dispatchWorkspaceContextMenuOpen(explorer, context, detail) {
        const cleanContext = normalizeContextName(context);

        if (!explorer || !cleanContext) {
            return;
        }

        explorer.dispatchEvent(new CustomEvent(WORKSPACE_CONTEXT_MENU_OPEN_EVENT, {
            bubbles: true,
            detail: Object.assign(
                {
                    context: cleanContext,
                    explorer
                },
                detail || {}
            )
        }));
    }

    function dispatchWorkspaceContextMenuClose(explorer, reason) {
        if (!explorer) {
            return;
        }

        explorer.dispatchEvent(new CustomEvent(WORKSPACE_CONTEXT_MENU_CLOSE_EVENT, {
            bubbles: true,
            detail: {
                reason: cleanValue(reason) || "dismiss",
                explorer
            }
        }));
    }

    function getWorkspaceContextMenuEventContext(event) {
        return normalizeContextName(event?.detail?.context);
    }

    function getWorkspaceInteractionsApi() {
        return window.SolomonWorkspaceDocumentInteractions || null;
    }

    function getWorkspaceContextRoots(explorer) {
        const roots = [];

        if (explorer) {
            roots.push(explorer);
        }

        if (document && !roots.includes(document)) {
            roots.push(document);
        }

        return roots;
    }

    function closeDocumentObjectActionPopover(popover) {
        if (!popover) {
            return;
        }

        popover.classList.remove("is-open");
        popover.hidden = true;
        popover.setAttribute("hidden", "");
        popover.setAttribute("aria-hidden", "true");
    }

    function closeDocumentObjectActionMenuElement(menu) {
        if (!menu) {
            return;
        }

        const button = menu.querySelector(DEFAULT_DOCUMENT_ACTION_MENU_BUTTON_SELECTOR);
        const popover = menu.querySelector(DEFAULT_DOCUMENT_ACTION_MENU_POPOVER_SELECTOR);

        menu.classList.remove("is-open");
        menu.setAttribute("data-document-action-menu-state", "closed");

        if (button) {
            button.setAttribute("aria-expanded", "false");
            button.setAttribute("data-document-action-menu-button-state", "closed");
        }

        closeDocumentObjectActionPopover(popover);
    }

    function closeDocumentObjectActionMenus(explorer) {
        const closedMenus = new Set();
        const closedPopovers = new Set();

        getWorkspaceContextRoots(explorer).forEach(function (root) {
            root.querySelectorAll?.(DEFAULT_DOCUMENT_ACTION_MENU_SELECTOR)
                .forEach(function (menu) {
                    if (closedMenus.has(menu)) {
                        return;
                    }

                    closedMenus.add(menu);
                    closeDocumentObjectActionMenuElement(menu);
                });
        });

        getWorkspaceContextRoots(explorer).forEach(function (root) {
            root.querySelectorAll?.(DEFAULT_DOCUMENT_ACTION_MENU_POPOVER_SELECTOR)
                .forEach(function (popover) {
                    if (closedPopovers.has(popover)) {
                        return;
                    }

                    closedPopovers.add(popover);
                    closeDocumentObjectActionPopover(popover);
                });
        });
    }

    function closeDocumentObjectContext(explorer, options) {
        const config = getConfig(options);
        const interactions = getWorkspaceInteractionsApi();

        if (interactions && typeof interactions.closeDocumentActionMenus === "function") {
            interactions.closeDocumentActionMenus(explorer, null);
        }

        closeDocumentObjectActionMenus(explorer);

        if (config.resetDocumentSelection) {
            config.resetDocumentSelection(explorer);
        }

        if (config.renderPreviewEmpty) {
            config.renderPreviewEmpty(explorer);
        }
    }

    function bindWorkspaceContextMenuCoordinator(explorer, options) {
        const config = getConfig(options);

        if (!explorer || explorer[BACKGROUND_CONTEXT_COORDINATOR_BOUND_KEY] === true) {
            return;
        }

        explorer[BACKGROUND_CONTEXT_COORDINATOR_BOUND_KEY] = true;

        explorer.addEventListener(WORKSPACE_CONTEXT_MENU_OPEN_EVENT, function (event) {
            const context = getWorkspaceContextMenuEventContext(event);

            if (context === WORKSPACE_CONTEXT_OBJECT) {
                closeDocumentBackgroundContextMenu(explorer);
            }
        });

        explorer.addEventListener(WORKSPACE_CONTEXT_MENU_CLOSE_EVENT, function () {
            closeDocumentBackgroundContextMenu(explorer);
        });

        const interactions = getWorkspaceInteractionsApi();

        if (interactions && typeof interactions.bindWorkspaceContextMenuCoordinator === "function") {
            interactions.bindWorkspaceContextMenuCoordinator(explorer, config);
        }
    }

    function closeDocumentBackgroundContextMenu(scope) {
        const removedMenus = new Set();

        if (activeBackgroundContextMenu) {
            removedMenus.add(activeBackgroundContextMenu);
            activeBackgroundContextMenu.remove();
            activeBackgroundContextMenu = null;
        }

        getWorkspaceContextRoots(scope).forEach(function (root) {
            root.querySelectorAll?.(DEFAULT_DOCUMENT_BACKGROUND_CONTEXT_MENU_SELECTOR)
                .forEach(function (menu) {
                    if (removedMenus.has(menu)) {
                        return;
                    }

                    removedMenus.add(menu);
                    menu.remove();
                });
        });
    }

    function closeWorkspaceContextMenus(explorer, options) {
        const config = getConfig(options);

        closeDocumentBackgroundContextMenu(explorer);
        closeDocumentObjectContext(explorer, config);
        closeDocumentNewMenus(explorer, config);
    }

    function createBackgroundContextMenuButton(actionName, iconName, label, summary, isDisabled) {
        const button = document.createElement("button");
        const icon = document.createElement("span");
        const copy = document.createElement("span");
        const labelNode = document.createElement("strong");
        const summaryNode = document.createElement("small");

        button.type = "button";
        button.className = "workspace-document-background-menu-action";
        button.setAttribute("role", "menuitem");
        button.setAttribute("data-document-background-context-menu-item", actionName);
        button.setAttribute("data-workspace-new-authority", "server");

        if (actionName === BACKGROUND_CONTEXT_ACTION_NEW_FOLDER) {
            button.setAttribute("data-workspace-new-action", DEFAULT_NEW_FOLDER_ACTION);
        }

        if (isDisabled) {
            button.disabled = true;
            button.setAttribute("aria-disabled", "true");
        } else {
            button.setAttribute("aria-disabled", "false");
        }

        icon.className = "icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = iconName;

        labelNode.textContent = label;
        summaryNode.textContent = summary;

        copy.append(labelNode, summaryNode);
        button.append(icon, copy);

        return button;
    }

    function getBackgroundContextMenuActions(explorer, options) {
        const config = getConfig(options);
        const section = normalizeDocumentSection(
            explorer?.getAttribute("data-workspace-section"),
            config
        );
        const currentFolderId = getCurrentFolderId(explorer, null);
        const folderMode = getFolderCreateMode(explorer, null, config);
        const folderEnabled = isFolderCreateEnabled(explorer, null, config);
        const actions = [];

        if (section !== "files" || !folderEnabled) {
            return actions;
        }

        actions.push({
            action: BACKGROUND_CONTEXT_ACTION_NEW_FOLDER,
            icon: "create_new_folder",
            label: "New folder",
            summary: getFolderCreateSummary(folderMode, currentFolderId),
            disabled: false
        });

        if (config.openUploadPicker) {
            actions.push({
                action: BACKGROUND_CONTEXT_ACTION_UPLOAD_FILE,
                icon: "upload_file",
                label: "Upload file",
                summary: "Store files in this location.",
                disabled: false
            });
        }

        if (config.refreshFiles && isFetchableDocumentSection(section, config)) {
            actions.push({
                action: BACKGROUND_CONTEXT_ACTION_REFRESH,
                icon: "refresh",
                label: "Refresh",
                summary: `Refresh ${getDocumentSectionLabel(section, config)}.`,
                disabled: false
            });
        }

        return actions;
    }

    function createBackgroundFolderActionProxy(explorer, action) {
        const proxy = document.createElement("button");
        const attributes = [
            "data-workspace-new-action",
            "data-workspace-new-authority",
            "data-workspace-folder-contract",
            "data-workspace-folder-create-contract",
            "data-workspace-folder-create-endpoint",
            "data-workspace-folder-create-mode",
            "data-workspace-folder-create-enabled",
            "data-workspace-folder-location-required",
            "data-workspace-current-folder-id"
        ];

        attributes.forEach(function (attributeName) {
            const value = (
                cleanValue(action?.getAttribute(attributeName)) ||
                cleanValue(explorer?.getAttribute(attributeName))
            );

            if (value) {
                proxy.setAttribute(attributeName, value);
            }
        });

        proxy.setAttribute("data-workspace-new-action", DEFAULT_NEW_FOLDER_ACTION);
        proxy.setAttribute("data-workspace-new-authority", "server");

        return proxy;
    }

    function runDocumentBackgroundContextAction(explorer, action, menu, options) {
        const config = getConfig(options);
        const actionName = cleanValue(
            action?.getAttribute("data-document-background-context-menu-item")
        );

        if (!explorer || !actionName || action?.disabled || action?.getAttribute("aria-disabled") === "true") {
            return false;
        }

        if (actionName === BACKGROUND_CONTEXT_ACTION_NEW_FOLDER) {
            const folderAction = createBackgroundFolderActionProxy(explorer, action);

            closeDocumentBackgroundContextMenu();
            createWorkspaceFolderFromAction(explorer, folderAction, config);

            return true;
        }

        if (actionName === BACKGROUND_CONTEXT_ACTION_UPLOAD_FILE) {
            closeDocumentBackgroundContextMenu();

            if (config.openUploadPicker) {
                config.openUploadPicker(explorer);
            }

            return true;
        }

        if (actionName === BACKGROUND_CONTEXT_ACTION_REFRESH) {
            const section = normalizeDocumentSection(
                explorer.getAttribute("data-workspace-section"),
                config
            );

            closeDocumentBackgroundContextMenu();

            if (config.refreshFiles && isFetchableDocumentSection(section, config)) {
                config.refreshFiles(explorer, {
                    forceRender: true,
                    quiet: false,
                    section,
                    source: "manual_refresh"
                });
            }

            return true;
        }

        return false;
    }

    function createDocumentBackgroundContextMenu(explorer, actions, event, options) {
        const config = getConfig(options);

        closeDocumentBackgroundContextMenu(explorer);
        closeDocumentObjectActionMenus(explorer);

        const menu = document.createElement("section");
        const title = document.createElement("p");
        const menuId = `workspace-document-background-menu-${Date.now()}`;

        menu.id = menuId;
        menu.className = "workspace-document-background-menu";
        menu.setAttribute("data-document-background-context-menu", "");
        menu.setAttribute("role", "menu");
        menu.setAttribute("aria-label", "Folder location actions");
        menu.hidden = true;

        title.className = "workspace-document-background-menu-label";
        title.setAttribute("role", "presentation");
        title.textContent = "Location";

        menu.appendChild(title);

        actions.forEach(function (entry) {
            const action = createBackgroundContextMenuButton(
                entry.action,
                entry.icon,
                entry.label,
                entry.summary,
                entry.disabled
            );

            if (entry.action === BACKGROUND_CONTEXT_ACTION_NEW_FOLDER) {
                action.setAttribute(
                    "data-workspace-folder-create-mode",
                    getFolderCreateMode(explorer, null, config)
                );
                action.setAttribute(
                    "data-workspace-folder-create-enabled",
                    isFolderCreateEnabled(explorer, null, config) ? "true" : "false"
                );
                action.setAttribute(
                    "data-workspace-folder-location-required",
                    getFolderCreateMode(explorer, null, config) === FOLDER_CREATE_MODE_LOCATION_REQUIRED
                        ? "true"
                        : "false"
                );
                action.setAttribute(
                    "data-workspace-folder-create-endpoint",
                    getFolderCreateEndpoint(explorer, null, config)
                );
                action.setAttribute(
                    "data-workspace-current-folder-id",
                    getCurrentFolderId(explorer, null)
                );
            }

            menu.appendChild(action);
        });

        menu.addEventListener("click", function (clickEvent) {
            const action = clickEvent.target?.closest?.(config.backgroundContextMenuAction);

            if (!action || !menu.contains(action)) {
                return;
            }

            clickEvent.preventDefault();
            clickEvent.stopPropagation();
            runDocumentBackgroundContextAction(explorer, action, menu, config);
        });

        menu.addEventListener("keydown", function (keydownEvent) {
            const enabledActions = Array.from(
                menu.querySelectorAll(config.backgroundContextMenuAction)
            ).filter(function (action) {
                return !isElementUnavailable(action);
            });
            const currentIndex = enabledActions.indexOf(document.activeElement);

            if (keydownEvent.key === "Escape") {
                keydownEvent.preventDefault();
                closeDocumentBackgroundContextMenu();
                return;
            }

            if (keydownEvent.key === "ArrowDown" && enabledActions.length) {
                keydownEvent.preventDefault();
                enabledActions[(currentIndex + 1 + enabledActions.length) % enabledActions.length].focus();
                return;
            }

            if (keydownEvent.key === "ArrowUp" && enabledActions.length) {
                keydownEvent.preventDefault();
                enabledActions[(currentIndex - 1 + enabledActions.length) % enabledActions.length].focus();
                return;
            }
        });

        document.body.appendChild(menu);
        menu.hidden = false;
        menu.removeAttribute("hidden");
        positionDocumentBackgroundContextMenu(menu, event);

        const firstAction = menu.querySelector(config.backgroundContextMenuAction);

        firstAction?.focus?.({ preventScroll: true });

        return menu;
    }

    function positionDocumentBackgroundContextMenu(menu, event) {
        const viewportPadding = 12;
        const requestedX = Number(event?.clientX || 0);
        const requestedY = Number(event?.clientY || 0);
        const rect = menu.getBoundingClientRect();
        const maxX = Math.max(viewportPadding, window.innerWidth - rect.width - viewportPadding);
        const maxY = Math.max(viewportPadding, window.innerHeight - rect.height - viewportPadding);
        const x = Math.min(Math.max(requestedX, viewportPadding), maxX);
        const y = Math.min(Math.max(requestedY, viewportPadding), maxY);

        menu.style.setProperty("--workspace-document-background-menu-x", `${x}px`);
        menu.style.setProperty("--workspace-document-background-menu-y", `${y}px`);
    }

    function isDocumentBackgroundContextTarget(event, explorer, options) {
        const config = getConfig(options);
        const target = event?.target;
        const surface = target?.closest?.(config.backgroundContextSurface);

        if (!explorer || !target || !surface || !explorer.contains(surface)) {
            return false;
        }

        if (target.closest?.(DEFAULT_DOCUMENT_ROW_SELECTOR)) {
            return false;
        }

        return !target.closest?.(config.backgroundContextBlocked);
    }

    function getDocumentContextMenuIntent(event, explorer, options) {
        const config = getConfig(options);
        const target = event?.target;

        if (!explorer || !target) {
            return {
                context: ""
            };
        }

        if (target.closest?.(DEFAULT_DOCUMENT_BACKGROUND_CONTEXT_MENU_SELECTOR)) {
            return {
                context: "active_menu"
            };
        }

        const row = target.closest?.(DEFAULT_DOCUMENT_ROW_SELECTOR) || null;

        if (row && explorer.contains(row)) {
            return {
                context: WORKSPACE_CONTEXT_OBJECT,
                row
            };
        }

        if (isDocumentBackgroundContextTarget(event, explorer, config)) {
            return {
                context: WORKSPACE_CONTEXT_LOCATION,
                surface: target.closest?.(config.backgroundContextSurface) || null
            };
        }

        return {
            context: ""
        };
    }

    function handleDocumentBackgroundContextMenu(event, explorer, options) {
        const config = getConfig(options);
        const intent = getDocumentContextMenuIntent(event, explorer, config);

        if (event.defaultPrevented || !intent.context) {
            return false;
        }

        if (intent.context === "active_menu") {
            return false;
        }

        if (intent.context === WORKSPACE_CONTEXT_OBJECT) {
            closeDocumentBackgroundContextMenu(explorer);
            closeDocumentObjectActionMenus(explorer);
            closeDocumentNewMenus(explorer, config);
            dispatchWorkspaceContextMenuOpen(explorer, WORKSPACE_CONTEXT_OBJECT, {
                source: "document_context_router",
                row: intent.row || null
            });

            return false;
        }

        if (intent.context !== WORKSPACE_CONTEXT_LOCATION) {
            return false;
        }

        const actions = getBackgroundContextMenuActions(explorer, config);

        if (!actions.length) {
            return false;
        }

        event.preventDefault();
        event.stopImmediatePropagation();
        closeWorkspaceContextMenus(explorer, config);
        dispatchWorkspaceContextMenuOpen(explorer, WORKSPACE_CONTEXT_LOCATION, {
            source: "document_context_router",
            surface: intent.surface || null
        });
        closeDocumentBackgroundContextMenu(explorer);
        closeDocumentObjectActionMenus(explorer);

        activeBackgroundContextMenu = createDocumentBackgroundContextMenu(
            explorer,
            actions,
            event,
            config
        );

        return true;
    }

    function bindDocumentBackgroundContextMenuGlobalDismiss() {
        if (documentBackgroundContextGlobalBound) {
            return;
        }

        documentBackgroundContextGlobalBound = true;

        document.addEventListener("click", function (event) {
            if (event.target?.closest?.(DEFAULT_DOCUMENT_BACKGROUND_CONTEXT_MENU_SELECTOR)) {
                return;
            }

            closeDocumentBackgroundContextMenu();
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape") {
                closeDocumentBackgroundContextMenu();
            }
        });

        window.addEventListener("resize", closeDocumentBackgroundContextMenu);
        window.addEventListener("scroll", closeDocumentBackgroundContextMenu, true);
    }

    function bindDocumentBackgroundContextMenu(explorer, options) {
        const config = getConfig(options);

        if (!explorer || explorer.__solomonDocumentBackgroundContextMenuBound === true) {
            return;
        }

        explorer.__solomonDocumentBackgroundContextMenuBound = true;

        bindWorkspaceContextMenuCoordinator(explorer, config);

        explorer.addEventListener("contextmenu", function (event) {
            handleDocumentBackgroundContextMenu(event, explorer, config);
        }, true);

        bindDocumentBackgroundContextMenuGlobalDismiss();
    }

    function getDocumentNewMenuParts(menu, options) {
        const config = getConfig(options);
        const triggerSelector = getSelector(config, "newMenuTrigger", DEFAULT_DOCUMENT_NEW_MENU_TRIGGER_SELECTOR);
        const panelSelector = getSelector(config, "newMenuPanel", DEFAULT_DOCUMENT_NEW_MENU_PANEL_SELECTOR);

        return {
            trigger: menu?.querySelector(triggerSelector) || null,
            panel: menu?.querySelector(panelSelector) || null
        };
    }

    function isDocumentNewMenuOpen(menu, options) {
        const parts = getDocumentNewMenuParts(menu, options);

        return Boolean(
            menu &&
            parts.panel &&
            !parts.panel.hidden &&
            parts.trigger?.getAttribute("aria-expanded") === "true"
        );
    }

    function setDocumentNewMenuState(menu, shouldOpen, options) {
        const parts = getDocumentNewMenuParts(menu, options);

        if (!menu || !parts.trigger || !parts.panel) {
            return;
        }

        if (shouldOpen) {
            parts.panel.hidden = false;
            parts.panel.removeAttribute("hidden");
            parts.panel.setAttribute("aria-hidden", "false");
            parts.trigger.setAttribute("aria-expanded", "true");
            menu.setAttribute("data-document-new-menu-state", "open");
            return;
        }

        parts.panel.hidden = true;
        parts.panel.setAttribute("hidden", "");
        parts.panel.setAttribute("aria-hidden", "true");
        parts.trigger.setAttribute("aria-expanded", "false");
        menu.setAttribute("data-document-new-menu-state", "closed");
    }

    function closeDocumentNewMenus(scope, options) {
        const config = getConfig(options);
        const menuSelector = getSelector(config, "newMenu", DEFAULT_DOCUMENT_NEW_MENU_SELECTOR);
        const root = scope || document;

        root.querySelectorAll?.(menuSelector).forEach(function (menu) {
            setDocumentNewMenuState(menu, false, config);
        });
    }

    function closeOtherDocumentNewMenus(activeMenu, options) {
        const config = getConfig(options);
        const menuSelector = getSelector(config, "newMenu", DEFAULT_DOCUMENT_NEW_MENU_SELECTOR);

        document.querySelectorAll(menuSelector).forEach(function (menu) {
            if (menu !== activeMenu) {
                setDocumentNewMenuState(menu, false, config);
            }
        });
    }

    function focusFirstDocumentNewMenuAction(menu, options) {
        const config = getConfig(options);
        const actionSelector = getSelector(config, "newMenuAction", DEFAULT_DOCUMENT_NEW_MENU_ACTION_SELECTOR);
        const closeSelector = getSelector(config, "newMenuClose", DEFAULT_DOCUMENT_NEW_MENU_CLOSE_SELECTOR);
        const parts = getDocumentNewMenuParts(menu, config);
        const actions = Array.from(parts.panel?.querySelectorAll(`${actionSelector}, ${closeSelector}`) || [])
            .filter(function (action) {
                return !isElementUnavailable(action);
            });

        actions[0]?.focus?.();
    }

    function moveDocumentNewMenuFocus(event, menu, direction, options) {
        const config = getConfig(options);
        const actionSelector = getSelector(config, "newMenuAction", DEFAULT_DOCUMENT_NEW_MENU_ACTION_SELECTOR);
        const closeSelector = getSelector(config, "newMenuClose", DEFAULT_DOCUMENT_NEW_MENU_CLOSE_SELECTOR);
        const parts = getDocumentNewMenuParts(menu, config);
        const actions = Array.from(parts.panel?.querySelectorAll(`${actionSelector}, ${closeSelector}`) || [])
            .filter(function (action) {
                return !isElementUnavailable(action);
            });

        if (!actions.length) {
            return;
        }

        const currentIndex = actions.indexOf(document.activeElement);
        const fallbackIndex = direction > 0 ? -1 : 0;
        const nextIndex = (currentIndex >= 0 ? currentIndex : fallbackIndex) + direction;
        const wrappedIndex = (nextIndex + actions.length) % actions.length;

        event.preventDefault();
        actions[wrappedIndex].focus();
    }

    function dispatchDocumentNewAction(explorer, action) {
        const actionName = cleanValue(action?.getAttribute("data-workspace-new-action"));
        const authority = cleanValue(action?.getAttribute("data-workspace-new-authority"));
        const href = cleanValue(action?.getAttribute("href"));

        if (!actionName) {
            return false;
        }

        const actionEvent = new CustomEvent("solomon:document-new-action", {
            bubbles: true,
            cancelable: true,
            detail: {
                action: actionName,
                authority,
                href,
                explorer,
                source: action
            }
        });

        action.dispatchEvent(actionEvent);

        return actionEvent.defaultPrevented;
    }

    function handleDocumentNewMenuClick(event, explorer, options) {
        const config = getConfig(options);
        const menuSelector = getSelector(config, "newMenu", DEFAULT_DOCUMENT_NEW_MENU_SELECTOR);
        const triggerSelector = getSelector(config, "newMenuTrigger", DEFAULT_DOCUMENT_NEW_MENU_TRIGGER_SELECTOR);
        const actionSelector = getSelector(config, "newMenuAction", DEFAULT_DOCUMENT_NEW_MENU_ACTION_SELECTOR);
        const closeSelector = getSelector(config, "newMenuClose", DEFAULT_DOCUMENT_NEW_MENU_CLOSE_SELECTOR);
        const target = event?.target;

        if (!explorer || !target) {
            return false;
        }

        const trigger = target.closest?.(triggerSelector);

        if (trigger && explorer.contains(trigger)) {
            const menu = trigger.closest(menuSelector);

            if (!menu || isElementUnavailable(trigger)) {
                return true;
            }

            event.preventDefault();
            closeOtherDocumentNewMenus(menu, config);
            setDocumentNewMenuState(menu, !isDocumentNewMenuOpen(menu, config), config);

            if (isDocumentNewMenuOpen(menu, config)) {
                focusFirstDocumentNewMenuAction(menu, config);
            }

            return true;
        }

        const closeSource = target.closest?.(closeSelector);

        if (closeSource && explorer.contains(closeSource)) {
            const menu = closeSource.closest(menuSelector);

            setDocumentNewMenuState(menu, false, config);
            return false;
        }

        const action = target.closest?.(actionSelector);

        if (!action || !explorer.contains(action)) {
            return false;
        }

        const menu = action.closest(menuSelector);
        const isAnchor = action.tagName === "A";
        const isUploadTrigger = action.matches(DEFAULT_UPLOAD_TRIGGER_SELECTOR);

        setDocumentNewMenuState(menu, false, config);

        if (isElementUnavailable(action)) {
            event.preventDefault();
            return true;
        }

        const actionHandled = dispatchDocumentNewAction(explorer, action);

        if (actionHandled) {
            event.preventDefault();
            return true;
        }

        if (isNewFolderAction(action)) {
            event.preventDefault();
            createWorkspaceFolderFromAction(explorer, action, config);
            return true;
        }

        if (isAnchor || isUploadTrigger) {
            return false;
        }

        event.preventDefault();
        return true;
    }

    function handleDocumentNewMenuKeydown(event, explorer, options) {
        const config = getConfig(options);
        const menuSelector = getSelector(config, "newMenu", DEFAULT_DOCUMENT_NEW_MENU_SELECTOR);
        const triggerSelector = getSelector(config, "newMenuTrigger", DEFAULT_DOCUMENT_NEW_MENU_TRIGGER_SELECTOR);
        const target = event?.target;
        const menu = target?.closest?.(menuSelector);

        if (!explorer || !menu || !explorer.contains(menu)) {
            return false;
        }

        if (event.key === "Escape") {
            const parts = getDocumentNewMenuParts(menu, config);

            event.preventDefault();
            setDocumentNewMenuState(menu, false, config);
            parts.trigger?.focus?.();

            return true;
        }

        if (event.key === "ArrowDown") {
            moveDocumentNewMenuFocus(event, menu, 1, config);
            return true;
        }

        if (event.key === "ArrowUp") {
            moveDocumentNewMenuFocus(event, menu, -1, config);
            return true;
        }

        if (event.key === "Tab") {
            setDocumentNewMenuState(menu, false, config);
            return false;
        }

        if (
            (event.key === "Enter" || event.key === " ") &&
            target?.matches?.(triggerSelector)
        ) {
            return handleDocumentNewMenuClick(event, explorer, config);
        }

        return false;
    }

    function bindDocumentNewMenuGlobalDismiss(options) {
        const config = getConfig(options);
        const menuSelector = getSelector(config, "newMenu", DEFAULT_DOCUMENT_NEW_MENU_SELECTOR);

        if (documentNewMenuGlobalBound) {
            return;
        }

        documentNewMenuGlobalBound = true;

        document.addEventListener("click", function (event) {
            if (event.target?.closest?.(menuSelector)) {
                return;
            }

            closeDocumentNewMenus(document, config);
        });
    }

    function getDocumentNewMenuEventExplorer(event, options) {
        const config = getConfig(options);
        const menuSelector = getSelector(config, "newMenu", DEFAULT_DOCUMENT_NEW_MENU_SELECTOR);
        const target = event?.target;
        const menu = target?.closest?.(menuSelector) || null;

        return (
            menu?.closest?.(DEFAULT_DOCUMENT_EXPLORER_SELECTOR) ||
            target?.closest?.(DEFAULT_DOCUMENT_EXPLORER_SELECTOR) ||
            null
        );
    }

    function isDocumentNewMenuEvent(event, options) {
        const config = getConfig(options);
        const triggerSelector = getSelector(config, "newMenuTrigger", DEFAULT_DOCUMENT_NEW_MENU_TRIGGER_SELECTOR);
        const actionSelector = getSelector(config, "newMenuAction", DEFAULT_DOCUMENT_NEW_MENU_ACTION_SELECTOR);
        const closeSelector = getSelector(config, "newMenuClose", DEFAULT_DOCUMENT_NEW_MENU_CLOSE_SELECTOR);
        const target = event?.target;

        return Boolean(
            target?.closest?.(
                `${triggerSelector}, ${actionSelector}, ${closeSelector}`
            )
        );
    }

    function bindDocumentNewMenuGlobalDelegation(options) {
        const config = getConfig(options);

        if (documentNewMenuDelegationBound) {
            return;
        }

        documentNewMenuDelegationBound = true;

        document.addEventListener("click", function (event) {
            if (event.defaultPrevented || !isDocumentNewMenuEvent(event, config)) {
                return;
            }

            const explorer = getDocumentNewMenuEventExplorer(event, config);

            if (!explorer) {
                return;
            }

            handleDocumentNewMenuClick(event, explorer, config);
        });

        document.addEventListener("keydown", function (event) {
            if (event.defaultPrevented || !isDocumentNewMenuEvent(event, config)) {
                return;
            }

            const explorer = getDocumentNewMenuEventExplorer(event, config);

            if (!explorer) {
                return;
            }

            handleDocumentNewMenuKeydown(event, explorer, config);
        });

        bindDocumentNewMenuGlobalDismiss(config);
    }

    function bindDocumentNewMenu(explorer, options) {
        const config = getConfig(options);

        if (!explorer || explorer.__solomonDocumentNewMenuBound === true) {
            return;
        }

        explorer.__solomonDocumentNewMenuBound = true;

        explorer.addEventListener("click", function (event) {
            handleDocumentNewMenuClick(event, explorer, config);
        });

        explorer.addEventListener("keydown", function (event) {
            handleDocumentNewMenuKeydown(event, explorer, config);
        });

        bindDocumentNewMenuGlobalDelegation(config);
    }

    function syncWorkspaceFolderCreateControls(explorer, section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);
        const mode = getSectionFolderCreateMode(cleanSection, config);
        const isEnabled = mode === FOLDER_CREATE_MODE_CURRENT_CONTAINER;
        const isLocationRequired = mode === FOLDER_CREATE_MODE_LOCATION_REQUIRED;
        const currentFolderId = cleanValue(
            explorer?.getAttribute("data-workspace-current-folder-id")
        );

        if (!explorer) {
            return;
        }

        explorer.setAttribute("data-workspace-folder-create-mode", mode);
        explorer.setAttribute(
            "data-workspace-folder-create-enabled",
            isEnabled ? "true" : "false"
        );
        explorer.setAttribute(
            "data-workspace-folder-location-required",
            isLocationRequired ? "true" : "false"
        );

        explorer.querySelectorAll(DEFAULT_FOLDER_CREATE_ACTION_SELECTOR)
            .forEach(function (action) {
                const summary = getFolderCreateSummary(
                    mode,
                    currentFolderId
                );
                const summaryNode = action.querySelector("small");

                action.setAttribute(
                    "data-workspace-folder-create-mode",
                    mode
                );
                action.setAttribute(
                    "data-workspace-folder-create-enabled",
                    isEnabled ? "true" : "false"
                );
                action.setAttribute(
                    "data-workspace-folder-location-required",
                    isLocationRequired ? "true" : "false"
                );
                action.setAttribute(
                    "data-workspace-current-folder-id",
                    currentFolderId
                );

                if (summaryNode) {
                    summaryNode.textContent = summary;
                }

                if (mode === FOLDER_CREATE_MODE_UNAVAILABLE) {
                    action.hidden = true;
                    action.setAttribute("hidden", "");
                    action.setAttribute("aria-hidden", "true");
                    action.setAttribute("aria-disabled", "true");
                } else {
                    action.hidden = false;
                    action.removeAttribute("hidden");
                    action.setAttribute("aria-hidden", "false");
                    action.setAttribute(
                        "aria-disabled",
                        isEnabled ? "false" : "true"
                    );
                }

                if (action.tagName === "BUTTON") {
                    action.disabled = !isEnabled;
                }
            });
    }

    function syncDocumentSectionControls(explorer, section, options) {
        const config = getConfig(options);

        if (config.syncDocumentSectionControls) {
            config.syncDocumentSectionControls(explorer, section);
            return;
        }

        const controlSelector = getSelector(config, "sectionControl", DEFAULT_DOCUMENT_SECTION_CONTROL_SELECTOR);
        const utilitySelector = getSelector(config, "defaultUtility", DEFAULT_DOCUMENT_DEFAULT_UTILITY_SELECTOR);
        const cleanSection = normalizeDocumentSection(section, config);
        const utility = explorer?.querySelector(utilitySelector);

        if (!explorer) {
            return;
        }

        explorer.querySelectorAll(controlSelector).forEach(function (control) {
            const target = control.getAttribute("data-document-section-control");
            const shouldShow = sectionControlMatchesTarget(target, cleanSection, config);

            setSectionControlVisibility(control, shouldShow);
        });

        if (utility) {
            utility.setAttribute("aria-label", getDocumentSectionUtilityLabel(cleanSection, config));
        }

        syncEmptyTrashControls(explorer, cleanSection, config);
    }

    function syncDocumentRefreshControls(explorer, section, options) {
        const config = getConfig(options);

        if (config.syncDocumentRefreshControls) {
            config.syncDocumentRefreshControls(explorer, section);
            return;
        }

        const refreshSelector = getSelector(config, "refreshButton", DEFAULT_DOCUMENT_REFRESH_BUTTON_SELECTOR);
        const cleanSection = normalizeDocumentSection(section, config);
        const sectionLabel = getDocumentSectionLabel(cleanSection, config);
        const isRefreshableSection = isFetchableDocumentSection(cleanSection, config);
        const isRefreshing = explorer?.__solomonDocumentRefreshInFlight === true;
        const isDisabled = !isRefreshableSection || isRefreshing;
        const refreshTitle = isRefreshableSection
            ? (isRefreshing ? `Syncing ${sectionLabel}` : `Refresh ${sectionLabel}`)
            : `Refresh is not available for ${sectionLabel}.`;

        explorer?.querySelectorAll(refreshSelector).forEach(function (button) {
            const isVisibleBySection = sectionControlMatchesTarget(
                button.getAttribute("data-document-section-control") || "files",
                cleanSection,
                config
            );

            if (!isVisibleBySection) {
                setSectionControlVisibility(button, false);
                button.setAttribute("aria-disabled", "true");
                button.setAttribute("aria-busy", "false");
                button.setAttribute("data-document-refresh-state", "hidden");
                button.setAttribute("title", refreshTitle);
                button.setAttribute("aria-label", refreshTitle);
                return;
            }

            setSectionControlVisibility(button, true);
            button.setAttribute("aria-disabled", isDisabled ? "true" : "false");
            button.setAttribute("aria-busy", isRefreshing ? "true" : "false");
            button.setAttribute(
                "data-document-refresh-state",
                isRefreshing ? "syncing" : (isRefreshableSection ? "idle" : "unavailable")
            );
            button.setAttribute("title", refreshTitle);
            button.setAttribute("aria-label", refreshTitle);

            if (button.tagName === "BUTTON") {
                button.disabled = isDisabled;
            }
        });
    }

    function syncDocumentUploadControls(explorer, section, options) {
        const config = getConfig(options);

        if (config.syncDocumentUploadControls) {
            config.syncDocumentUploadControls(explorer, section);
            return;
        }

        const uploadSelector = getSelector(config, "uploadTrigger", DEFAULT_UPLOAD_TRIGGER_SELECTOR);
        const cleanSection = normalizeDocumentSection(section, config);
        const isFilesSection = cleanSection === "files";

        explorer?.querySelectorAll(uploadSelector).forEach(function (trigger) {
            const sectionControl = trigger.hasAttribute("data-document-section-control")
                ? trigger
                : trigger.closest(DEFAULT_DOCUMENT_SECTION_CONTROL_SELECTOR);

            if (!sectionControl) {
                return;
            }

            const sectionControlTarget = sectionControl.getAttribute("data-document-section-control") || "files";
            const isGlobalUploadTrigger = cleanValue(sectionControlTarget).toLowerCase() === "all";
            const shouldShow = sectionControlMatchesTarget(
                sectionControlTarget,
                cleanSection,
                config
            );
            const shouldEnable = shouldShow && (isFilesSection || isGlobalUploadTrigger);

            setSectionControlVisibility(trigger, shouldEnable);

            if (trigger.tagName === "BUTTON") {
                trigger.disabled = !shouldEnable;
            }
        });
    }

    function getWorkspaceFolderTree(explorer) {
        return explorer?.querySelector("[data-workspace-folder-tree]") || null;
    }

    function getWorkspaceFolderTreeScope(value) {
        return cleanValue(value).toLowerCase() === "shared"
            ? "shared"
            : "personal";
    }

    function getWorkspaceFolderTreeRoot(explorer, scope) {
        const cleanScope = getWorkspaceFolderTreeScope(scope);

        return getWorkspaceFolderTree(explorer)?.querySelector(
            `[data-workspace-folder-tree-node][data-workspace-folder-tree-scope="${cleanScope}"][data-workspace-folder-id=""]`
        ) || null;
    }

    function getWorkspaceFolderTreeEndpoint(explorer, scope, parentFolderId) {
        const cleanScope = getWorkspaceFolderTreeScope(scope);
        const attributeName = cleanScope === "shared"
            ? "data-workspace-folder-tree-shared-endpoint"
            : "data-workspace-folder-tree-personal-endpoint";
        const baseEndpoint = cleanValue(explorer?.getAttribute(attributeName));

        if (!baseEndpoint) {
            return "";
        }

        try {
            const url = new URL(baseEndpoint, window.location.origin);
            const cleanParentId = cleanValue(parentFolderId);

            url.searchParams.set("scope", cleanScope);

            if (cleanParentId) {
                url.searchParams.set("parent_folder_id", cleanParentId);
            } else {
                url.searchParams.delete("parent_folder_id");
            }

            return `${url.pathname}${url.search}`;
        } catch (_error) {
            return "";
        }
    }

    function getWorkspaceFolderTreeChildren(node) {
        return node?.querySelector(":scope > [data-workspace-folder-tree-children]") || null;
    }

    function setWorkspaceFolderTreeExpanded(node, expanded) {
        const toggle = node?.querySelector(":scope > .workspace-folder-tree-row [data-workspace-folder-tree-toggle]");
        const children = getWorkspaceFolderTreeChildren(node);
        const icon = toggle?.querySelector(".icon");
        const label = cleanValue(
            node?.querySelector(":scope > .workspace-folder-tree-row .workspace-folder-tree-link span:not(.icon)")?.textContent
        ) || "folder";

        if (!toggle || !children) {
            return;
        }

        toggle.setAttribute("aria-expanded", expanded ? "true" : "false");
        toggle.setAttribute("aria-label", `${expanded ? "Collapse" : "Expand"} ${label}`);
        children.hidden = !expanded;
        node.classList.toggle("is-expanded", expanded);

        if (icon) {
            icon.textContent = expanded ? "expand_more" : "chevron_right";
        }
    }

    function createWorkspaceFolderTreeNode(folder, scope, depth) {
        const folderId = cleanValue(folder?.folder_id || folder?.workspace_item_id);
        const name = cleanValue(folder?.display_name || folder?.name || folder?.original_name) || "Untitled folder";
        const route = cleanValue(folder?.folder_url || folder?.canonical_url || folder?.open_url);
        const hasChildren = folder?.has_authorized_children === true;
        const node = document.createElement("div");
        const row = document.createElement("div");
        const toggle = document.createElement("button");
        const toggleIcon = document.createElement("span");
        const link = document.createElement("a");
        const folderIcon = document.createElement("span");
        const label = document.createElement("span");
        const children = document.createElement("div");

        node.className = "workspace-folder-tree-node";
        node.setAttribute("data-workspace-folder-tree-node", "");
        const cleanScope = getWorkspaceFolderTreeScope(scope);

        node.setAttribute("data-workspace-folder-tree-scope", cleanScope);
        node.setAttribute("data-workspace-folder-id", folderId);
        node.setAttribute("data-workspace-folder-depth", String(Math.max(1, Number(depth || 1))));
        node.style.setProperty("--workspace-folder-tree-depth", String(Math.max(1, Number(depth || 1))));

        if (cleanScope === "personal") {
            node.setAttribute("data-document-drop-folder-target", "true");
            node.setAttribute("data-document-drop-label", name);
        }

        row.className = "workspace-folder-tree-row";

        toggle.type = "button";
        toggle.className = "workspace-folder-tree-toggle";
        toggle.setAttribute("data-workspace-folder-tree-toggle", "");
        toggle.setAttribute("aria-expanded", "false");
        toggle.setAttribute("aria-label", `${hasChildren ? "Expand" : "No subfolders in"} ${name}`);
        toggle.disabled = !hasChildren;
        toggle.setAttribute("aria-disabled", hasChildren ? "false" : "true");

        toggleIcon.className = "icon";
        toggleIcon.setAttribute("aria-hidden", "true");
        toggleIcon.textContent = hasChildren ? "chevron_right" : "";
        toggle.appendChild(toggleIcon);

        link.className = "workspace-folder-tree-link";
        link.href = route || "#";
        link.setAttribute("data-command-shell-navigation", "true");
        link.setAttribute("data-command-navigation-contract", WORKSPACE_NAVIGATION_CONTRACT);
        link.setAttribute("data-command-route", route || "#");
        link.setAttribute("data-command-module", "documents");
        link.setAttribute("data-workspace-folder-tree-link", "");
        link.setAttribute("data-workspace-folder-id", folderId);

        folderIcon.className = "icon";
        folderIcon.setAttribute("aria-hidden", "true");
        folderIcon.textContent = "folder";
        label.textContent = name;
        link.append(folderIcon, label);

        children.className = "workspace-folder-tree-children";
        children.setAttribute("data-workspace-folder-tree-children", "");
        children.setAttribute("data-workspace-folder-tree-scope", getWorkspaceFolderTreeScope(scope));
        children.setAttribute("data-workspace-folder-tree-parent-id", folderId);
        children.setAttribute("role", "group");
        children.hidden = true;

        row.append(toggle, link);
        node.append(row, children);

        return node;
    }

    function renderWorkspaceFolderTreeChildren(container, folders, scope, depth) {
        if (!container) {
            return;
        }

        container.replaceChildren();
        const records = Array.isArray(folders) ? folders : [];

        records.forEach(function (folder) {
            container.appendChild(
                createWorkspaceFolderTreeNode(folder, scope, depth)
            );
        });

        container.setAttribute("data-workspace-folder-tree-loaded", "true");
        container.setAttribute("data-workspace-folder-tree-count", String(records.length));
    }

    async function loadWorkspaceFolderTreeChildren(explorer, node, options) {
        const cleanOptions = options || {};
        const scope = getWorkspaceFolderTreeScope(
            node?.getAttribute("data-workspace-folder-tree-scope")
        );
        const parentFolderId = cleanValue(
            node?.getAttribute("data-workspace-folder-id")
        );
        const children = getWorkspaceFolderTreeChildren(node);

        if (!explorer || !node || !children) {
            return [];
        }

        if (
            children.getAttribute("data-workspace-folder-tree-loaded") === "true"
            && cleanOptions.force !== true
        ) {
            return Array.from(children.querySelectorAll(":scope > [data-workspace-folder-tree-node]"));
        }

        const endpoint = getWorkspaceFolderTreeEndpoint(
            explorer,
            scope,
            parentFolderId
        );

        if (!endpoint) {
            return [];
        }

        const requestId = String(Number(children.dataset.workspaceFolderTreeRequestId || 0) + 1);
        children.dataset.workspaceFolderTreeRequestId = requestId;
        children.setAttribute("aria-busy", "true");
        node.classList.add("is-loading");

        try {
            const response = await fetch(endpoint, {
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                }
            });
            const payload = await response.json();

            if (!response.ok || payload?.ok === false) {
                throw new Error(payload?.error || "Folder navigation is unavailable.");
            }

            if (children.dataset.workspaceFolderTreeRequestId !== requestId) {
                return [];
            }

            renderWorkspaceFolderTreeChildren(
                children,
                payload?.folders,
                scope,
                Number(node.getAttribute("data-workspace-folder-depth") || 0) + 1
            );
            return Array.from(children.querySelectorAll(":scope > [data-workspace-folder-tree-node]"));
        } catch (error) {
            if (children.dataset.workspaceFolderTreeRequestId === requestId) {
                children.replaceChildren();
                children.setAttribute("data-workspace-folder-tree-loaded", "false");
                children.setAttribute("data-workspace-folder-tree-error", cleanValue(error?.message) || "Unable to load folders.");
            }
            return [];
        } finally {
            if (children.dataset.workspaceFolderTreeRequestId === requestId) {
                children.setAttribute("aria-busy", "false");
                node.classList.remove("is-loading");
            }
        }
    }

    async function toggleWorkspaceFolderTreeNode(explorer, node) {
        const toggle = node?.querySelector(":scope > .workspace-folder-tree-row [data-workspace-folder-tree-toggle]");

        if (!toggle || toggle.disabled || toggle.getAttribute("aria-disabled") === "true") {
            return;
        }

        const shouldExpand = toggle.getAttribute("aria-expanded") !== "true";
        setWorkspaceFolderTreeExpanded(node, shouldExpand);

        if (shouldExpand) {
            await loadWorkspaceFolderTreeChildren(explorer, node);
        }
    }

    function handleWorkspaceFolderTreeClick(event, explorer) {
        const toggle = event?.target?.closest?.("[data-workspace-folder-tree-toggle]");

        if (!toggle || !explorer?.contains(toggle)) {
            return false;
        }

        const node = toggle.closest("[data-workspace-folder-tree-node]");
        event.preventDefault();
        event.stopPropagation();
        toggleWorkspaceFolderTreeNode(explorer, node);
        return true;
    }

    function renderWorkspaceFolderBreadcrumbs(explorer, payload) {
        const container = explorer?.querySelector("[data-workspace-folder-breadcrumbs]");
        const breadcrumbs = Array.isArray(payload?.breadcrumbs) ? payload.breadcrumbs : [];
        const currentFolder = payload?.current_folder && typeof payload.current_folder === "object"
            ? payload.current_folder
            : null;
        const title = explorer?.querySelector(DEFAULT_DOCUMENT_SECTION_TITLE_SELECTOR);
        const heading = container?.closest(".workspace-document-browser-heading");

        if (title) {
            title.textContent = cleanValue(
                currentFolder?.display_name || currentFolder?.name
            ) || (
                getWorkspaceFolderTreeScope(payload?.root_scope) === "shared"
                    ? "Shared with me"
                    : "My Files"
            );
        }

        if (!container) {
            return;
        }

        container.replaceChildren();

        if (breadcrumbs.length <= 1) {
            container.hidden = true;
            container.setAttribute("aria-hidden", "true");
            heading?.setAttribute("data-workspace-folder-heading-state", "root");

            if (title) {
                title.hidden = false;
                title.setAttribute("aria-hidden", "false");
            }

            return;
        }

        container.hidden = false;
        container.setAttribute("aria-hidden", "false");
        heading?.setAttribute("data-workspace-folder-heading-state", "breadcrumbs");

        if (title) {
            title.hidden = true;
            title.setAttribute("aria-hidden", "true");
        }

        breadcrumbs.forEach(function (crumb, index) {
            const name = cleanValue(crumb?.name);
            const route = cleanValue(crumb?.route);
            const isCurrent = index === breadcrumbs.length - 1;

            if (!name) {
                return;
            }

            if (index > 0) {
                const separator = document.createElement("span");
                separator.className = "workspace-folder-breadcrumb-separator icon";
                separator.setAttribute("aria-hidden", "true");
                separator.textContent = "chevron_right";
                container.appendChild(separator);
            }

            if (isCurrent || !route) {
                const current = document.createElement("span");
                current.className = "workspace-folder-breadcrumb is-current";
                current.textContent = name;
                current.title = name;
                current.setAttribute("aria-current", "page");
                container.appendChild(current);
                return;
            }

            const link = document.createElement("a");
            link.className = "workspace-folder-breadcrumb";
            link.href = route;
            link.textContent = name;
            link.title = name;
            link.setAttribute("data-command-shell-navigation", "true");
            link.setAttribute("data-command-navigation-contract", WORKSPACE_NAVIGATION_CONTRACT);
            link.setAttribute("data-command-route", route);
            link.setAttribute("data-command-module", "documents");
            container.appendChild(link);
        });

        const hasBreadcrumbs = Boolean(container.childElementCount);

        container.hidden = !hasBreadcrumbs;
        container.setAttribute(
            "aria-hidden",
            hasBreadcrumbs ? "false" : "true"
        );

        if (!hasBreadcrumbs) {
            heading?.setAttribute("data-workspace-folder-heading-state", "root");

            if (title) {
                title.hidden = false;
                title.setAttribute("aria-hidden", "false");
            }
        }
    }

    function setWorkspaceFolderTreeActiveState(explorer, scope, folderId) {
        const cleanScope = getWorkspaceFolderTreeScope(scope);
        const cleanFolderId = cleanValue(folderId);

        getWorkspaceFolderTree(explorer)?.querySelectorAll("[data-workspace-folder-tree-node]").forEach(function (node) {
            const nodeScope = getWorkspaceFolderTreeScope(
                node.getAttribute("data-workspace-folder-tree-scope")
            );
            const nodeFolderId = cleanValue(
                node.getAttribute("data-workspace-folder-id")
            );
            const personalRootIsHome = (
                cleanScope === "personal"
                && !cleanFolderId
                && nodeScope === "personal"
                && !nodeFolderId
            );
            const isActive = (
                !personalRootIsHome
                && nodeScope === cleanScope
                && nodeFolderId === cleanFolderId
            );
            const link = node.querySelector(":scope > .workspace-folder-tree-row .workspace-folder-tree-link");

            node.classList.toggle("is-active", isActive);
            link?.classList.toggle("is-active", isActive);

            if (isActive) {
                link?.setAttribute("aria-current", "page");
            } else {
                link?.removeAttribute("aria-current");
            }
        });
    }

    async function revealWorkspaceFolderTreePath(explorer, payload) {
        const scope = getWorkspaceFolderTreeScope(payload?.root_scope);
        const breadcrumbs = Array.isArray(payload?.breadcrumbs) ? payload.breadcrumbs : [];
        const folderCrumbs = breadcrumbs.filter(function (crumb) {
            return cleanValue(crumb?.folder_id);
        });
        let node = getWorkspaceFolderTreeRoot(explorer, scope);

        if (!node) {
            return;
        }

        setWorkspaceFolderTreeExpanded(node, true);
        await loadWorkspaceFolderTreeChildren(explorer, node);

        for (let index = 0; index < folderCrumbs.length; index += 1) {
            const folderId = cleanValue(folderCrumbs[index]?.folder_id);
            const children = getWorkspaceFolderTreeChildren(node);
            const nextNode = Array.from(children?.children || []).find(function (candidate) {
                return cleanValue(candidate.getAttribute("data-workspace-folder-id")) === folderId;
            });

            if (!nextNode) {
                break;
            }

            node = nextNode;

            if (index < folderCrumbs.length - 1) {
                setWorkspaceFolderTreeExpanded(node, true);
                await loadWorkspaceFolderTreeChildren(explorer, node);
            }
        }

        setWorkspaceFolderTreeActiveState(
            explorer,
            scope,
            cleanValue(payload?.current_folder_id || payload?.folder_id)
        );
    }

    function normalizeWorkspaceFolderReturnRoute(value, fallback) {
        const cleanFallback = cleanValue(fallback) || "/";

        try {
            const url = new URL(
                cleanValue(value) || cleanFallback,
                window.location.origin
            );
            const path = cleanValue(url.pathname) || "/";

            if (
                url.origin !== window.location.origin
                || !WORKSPACE_FOLDER_RETURN_PATHS.has(path)
            ) {
                return cleanFallback;
            }

            return `${url.pathname}${url.search}${url.hash}`;
        } catch (_error) {
            return cleanFallback;
        }
    }

    function getWorkspaceFolderParentRoute(payload) {
        const breadcrumbs = Array.isArray(payload?.breadcrumbs)
            ? payload.breadcrumbs
            : [];

        if (breadcrumbs.length < 2) {
            return "";
        }

        return cleanValue(
            breadcrumbs[breadcrumbs.length - 2]?.route
        );
    }

    function resolveWorkspaceFolderReturnRoute(
        explorer,
        payload,
        scope,
        folderId,
        previousFolderId
    ) {
        const fallback = scope === "shared"
            ? "/shared"
            : "/";
        const explicitRoute = cleanValue(
            payload?.return_route
            || payload?.return_to
        );
        const existingRoute = cleanValue(
            explorer?.getAttribute(
                WORKSPACE_RETURN_ROUTE_ATTRIBUTE
            )
        );
        const parentRoute = getWorkspaceFolderParentRoute(
            payload
        );
        let candidate = explicitRoute;

        if (!candidate && previousFolderId && previousFolderId !== folderId) {
            candidate = parentRoute;
        }

        if (!candidate) {
            candidate = existingRoute || parentRoute || fallback;
        }

        return normalizeWorkspaceFolderReturnRoute(
            candidate,
            fallback
        );
    }

    function syncWorkspaceFolderWindowChrome(explorer) {
        const sidebarApi = window.NationsCommandSidebar;

        if (
            !explorer
            || typeof sidebarApi?.syncWorkspaceWindowChrome !== "function"
        ) {
            return;
        }

        sidebarApi.syncWorkspaceWindowChrome(
            "documents",
            {
                url: window.location.href
            }
        );
    }

    function syncWorkspaceFolderNavigation(explorer, payload) {
        if (!explorer || !payload || typeof payload !== "object") {
            return;
        }

        const previousFolderId = cleanValue(
            explorer.getAttribute("data-workspace-current-folder-id")
        );
        const scope = getWorkspaceFolderTreeScope(
            payload.root_scope || explorer.getAttribute("data-workspace-folder-navigation-scope")
        );
        const folderId = cleanValue(payload.current_folder_id || payload.folder_id);
        const returnRoute = resolveWorkspaceFolderReturnRoute(
            explorer,
            payload,
            scope,
            folderId,
            previousFolderId
        );

        explorer.setAttribute("data-workspace-folder-navigation-scope", scope);
        explorer.setAttribute("data-workspace-current-folder-id", folderId);

        if (folderId) {
            explorer.setAttribute(
                WORKSPACE_RETURN_ROUTE_ATTRIBUTE,
                returnRoute
            );
        } else {
            explorer.removeAttribute(
                WORKSPACE_RETURN_ROUTE_ATTRIBUTE
            );
        }

        renderWorkspaceFolderBreadcrumbs(explorer, payload);
        setWorkspaceFolderTreeActiveState(explorer, scope, folderId);
        revealWorkspaceFolderTreePath(explorer, payload);
        syncWorkspaceFolderWindowChrome(explorer);
    }

    function refreshWorkspaceFolderTreeCurrentContainer(explorer) {
        const scope = getWorkspaceFolderTreeScope(
            explorer?.getAttribute("data-workspace-folder-navigation-scope")
        );
        const currentFolderId = cleanValue(
            explorer?.getAttribute("data-workspace-current-folder-id")
        );
        const tree = getWorkspaceFolderTree(explorer);
        const node = currentFolderId
            ? Array.from(tree?.querySelectorAll("[data-workspace-folder-tree-node]") || []).find(function (candidate) {
                return (
                    getWorkspaceFolderTreeScope(candidate.getAttribute("data-workspace-folder-tree-scope")) === scope
                    && cleanValue(candidate.getAttribute("data-workspace-folder-id")) === currentFolderId
                );
            })
            : getWorkspaceFolderTreeRoot(explorer, scope);
        const children = getWorkspaceFolderTreeChildren(node);

        if (!node || !children) {
            return;
        }

        children.setAttribute("data-workspace-folder-tree-loaded", "false");
        setWorkspaceFolderTreeExpanded(node, true);
        loadWorkspaceFolderTreeChildren(explorer, node, { force: true });
    }

    function initializeWorkspaceFolderNavigation(explorer) {
        const tree = getWorkspaceFolderTree(explorer);

        if (!explorer || !tree) {
            return;
        }

        if (explorer.dataset.workspaceFolderMutationRefreshBound !== "true") {
            explorer.dataset.workspaceFolderMutationRefreshBound = "true";
            explorer.addEventListener("solomon:workspace-folder-mutated", function () {
                Promise.resolve(
                    refreshWorkspaceFolderTreeCurrentContainer(explorer)
                ).catch(function (error) {
                    console.warn(
                        "[DOCUMENT_SECTIONS][FOLDER_TREE] Mutation refresh failed.",
                        error
                    );
                });
            });
        }

        if (tree.dataset.workspaceFolderTreeInitialized === "true") {
            return;
        }

        tree.dataset.workspaceFolderTreeInitialized = "true";
        tree.querySelectorAll("[data-workspace-folder-tree-node][data-workspace-folder-id='']").forEach(function (rootNode) {
            const toggle = rootNode.querySelector(":scope > .workspace-folder-tree-row [data-workspace-folder-tree-toggle]");

            if (toggle?.getAttribute("aria-expanded") === "true") {
                setWorkspaceFolderTreeExpanded(rootNode, true);
                loadWorkspaceFolderTreeChildren(explorer, rootNode);
            }
        });
    }

    function getNavigationLinkSection(link, options) {
        const config = getConfig(options);
        const explicitSection = cleanValue(link?.getAttribute("data-document-section"));

        if (explicitSection) {
            return normalizeDocumentSection(explicitSection, config);
        }

        const rawRoute = (
            cleanValue(link?.getAttribute("data-command-route")) ||
            cleanValue(link?.getAttribute("href"))
        );

        if (!rawRoute) {
            return "";
        }

        try {
            const url = new URL(rawRoute, window.location.origin);

            if (!isWorkspaceSectionPath(url.pathname, config)) {
                return "";
            }

            return getWorkspaceSectionFromPath(url.pathname, config);
        } catch (error) {
            console.warn("[DOCUMENT_SECTIONS][NAV] Invalid static navigation route.", error);
            return "";
        }
    }

    function syncDocumentNavigationLinkState(link, section, options) {
        const linkSection = getNavigationLinkSection(link, options);
        const explorer = link?.closest(DEFAULT_DOCUMENT_EXPLORER_SELECTOR);
        const currentFolderId = cleanValue(
            explorer?.getAttribute("data-workspace-current-folder-id")
        );
        const isNestedPersonalFolder = Boolean(
            currentFolderId
            && section === "files"
            && link?.hasAttribute("data-workspace-home-link")
        );
        const isActive = Boolean(
            linkSection
            && linkSection === section
            && !isNestedPersonalFolder
        );

        link.classList.toggle("is-active", isActive);

        if (isActive) {
            link.setAttribute("aria-current", "page");
        } else {
            link.removeAttribute("aria-current");
        }
    }

    function updateDocumentSectionChrome(explorer, section, options) {
        const config = getConfig(options);
        const sectionLinkSelector = getSelector(config, "sectionLink", DEFAULT_DOCUMENT_SECTION_LINK_SELECTOR);
        const staticLinkSelector = getSelector(config, "staticLink", DEFAULT_DOCUMENT_STATIC_LINK_SELECTOR);
        const titleSelector = getSelector(config, "sectionTitle", DEFAULT_DOCUMENT_SECTION_TITLE_SELECTOR);
        const cleanSection = normalizeDocumentSection(section, config);
        const sectionLabel = getDocumentSectionLabel(cleanSection, config);
        const title = explorer?.querySelector(titleSelector);

        if (!explorer || !isKnownDocumentSection(cleanSection, config)) {
            return;
        }

        syncWorkspaceNavigationContract(
            explorer,
            cleanSection,
            config
        );

        if (title) {
            title.textContent = sectionLabel;
        }

        Array.from(
            new Set([
                ...explorer.querySelectorAll(sectionLinkSelector),
                ...explorer.querySelectorAll(staticLinkSelector)
            ])
        ).forEach(function (link) {
            syncDocumentNavigationLinkState(link, cleanSection, config);
        });

        closeDocumentNewMenus(explorer, config);
        closeDocumentBackgroundContextMenu();
        syncDocumentSectionControls(explorer, cleanSection, config);
        syncDocumentUploadControls(explorer, cleanSection, config);
        syncWorkspaceFolderCreateControls(explorer, cleanSection, config);
        syncDocumentRefreshControls(explorer, cleanSection, config);
        syncEmptyTrashControls(explorer, cleanSection, config);
    }

    function renderDocumentSectionStatus(explorer, section, message, options) {
        const config = getConfig(options);
        const listSelector = getSelector(config, "fileList", DEFAULT_FILE_LIST_SELECTOR);
        const list = explorer?.querySelector(listSelector);
        const cleanSection = normalizeDocumentSection(section, config);
        const emptyState = getDocumentSectionEmptyState(cleanSection, config);
        const label = emptyState.label || getDocumentSectionLabel(cleanSection, config);
        const icon = emptyState.icon || getDocumentSectionIcon(cleanSection, config);
        const statusMessage = cleanValue(message) || getDocumentSectionEmptyCopy(cleanSection, config) || `${label} is not available in this view.`;

        if (!list) {
            return;
        }

        if (typeof config.renderEmptyFiles === "function") {
            config.renderEmptyFiles(list, cleanSection);
            setDocumentListState(explorer, cleanSection, "empty", config);
            return;
        }

        clearNode(list);

        const empty = document.createElement("article");
        const iconNode = document.createElement("span");
        const title = document.createElement("strong");
        const copy = document.createElement("p");

        empty.className = "workspace-document-empty-state";
        empty.setAttribute("role", "status");
        empty.setAttribute("aria-live", "polite");

        iconNode.className = "icon";
        iconNode.setAttribute("aria-hidden", "true");
        iconNode.textContent = icon;

        title.textContent = label;
        copy.textContent = statusMessage;

        empty.append(iconNode, title, copy);
        list.appendChild(empty);

        setDocumentListState(explorer, cleanSection, "empty", config);
    }

    function renderDocumentSectionPlaceholder(explorer, section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);
        const message = getDocumentSectionEmptyCopy(cleanSection, config);

        renderDocumentSectionStatus(
            explorer,
            cleanSection,
            message,
            config
        );
    }

    function renderDocumentSectionLoading(explorer, section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);
        const listSelector = getSelector(config, "fileList", DEFAULT_FILE_LIST_SELECTOR);
        const list = explorer?.querySelector(listSelector);
        const sectionLabel = getDocumentSectionLabel(cleanSection, config);

        if (!list) {
            return;
        }

        setDocumentListState(explorer, cleanSection, "loading", config);
        clearNode(list);

        const loading = document.createElement("article");
        const visual = document.createElement("span");
        const iconNode = document.createElement("span");
        const copy = document.createElement("div");
        const title = document.createElement("strong");
        const message = document.createElement("p");

        loading.className = "workspace-document-loading-state";
        loading.setAttribute("data-document-loading-state", "");
        loading.setAttribute("role", "status");
        loading.setAttribute("aria-live", "polite");
        loading.setAttribute("aria-label", `Loading ${sectionLabel}`);

        visual.className = "workspace-document-loading-visual";
        visual.setAttribute("aria-hidden", "true");

        iconNode.className = "icon workspace-document-loading-icon";
        iconNode.textContent = "sync";

        copy.className = "workspace-document-loading-copy";
        title.textContent = `Loading ${sectionLabel}`;
        message.textContent = "Checking the latest workspace records.";

        visual.appendChild(iconNode);
        copy.append(title, message);
        loading.append(visual, copy);
        list.appendChild(loading);
    }

    function renderDocumentSectionError(explorer, section, message, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);
        const listSelector = getSelector(config, "fileList", DEFAULT_FILE_LIST_SELECTOR);
        const list = explorer?.querySelector(listSelector);
        const sectionLabel = getDocumentSectionLabel(cleanSection, config);
        const errorMessage = cleanValue(message) || `Unable to load ${sectionLabel}.`;

        if (!list) {
            return;
        }

        setDocumentListState(explorer, cleanSection, "error", config);
        clearNode(list);

        const errorState = document.createElement("article");
        const visual = document.createElement("span");
        const iconNode = document.createElement("span");
        const copy = document.createElement("div");
        const title = document.createElement("strong");
        const detail = document.createElement("p");

        errorState.className = "workspace-document-error-state";
        errorState.setAttribute("data-document-error-state", "");
        errorState.setAttribute("role", "alert");
        errorState.setAttribute("aria-live", "assertive");

        visual.className = "workspace-document-error-visual";
        visual.setAttribute("aria-hidden", "true");

        iconNode.className = "icon";
        iconNode.textContent = "cloud_off";

        copy.className = "workspace-document-error-copy";
        title.textContent = `${sectionLabel} could not be loaded`;
        detail.textContent = `${errorMessage} Refresh the page to try again.`;

        visual.appendChild(iconNode);
        copy.append(title, detail);
        errorState.append(visual, copy);
        list.appendChild(errorState);
    }

    function renderCurrentDocumentSection(explorer, docs, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(
            options?.section ||
            explorer?.getAttribute("data-workspace-section") ||
            config.defaultSection,
            config
        );

        if (!explorer) {
            return;
        }

        if (cleanSection === "trash" && config.renderTrashFiles) {
            config.renderTrashFiles(explorer, docs, {
                forceRender: options?.forceRender === true,
                renderOrigin: cleanValue(options?.renderOrigin || options?.source),
                section: cleanSection
            });
            syncEmptyTrashControls(explorer, cleanSection, config);
            return;
        }

        if (isRenderableFileSection(cleanSection, config) && config.renderFiles) {
            config.renderFiles(explorer, docs, {
                forceRender: options?.forceRender === true,
                renderOrigin: cleanValue(options?.renderOrigin || options?.source),
                section: cleanSection
            });
            syncEmptyTrashControls(explorer, cleanSection, config);
            return;
        }

        renderDocumentSectionPlaceholder(explorer, cleanSection, config);
    }

    function shouldHandleDocumentSectionLink(event, link, options) {
        const config = getConfig(options);

        if (!link || event.defaultPrevented) {
            return false;
        }

        if (
            event.metaKey ||
            event.ctrlKey ||
            event.shiftKey ||
            event.altKey ||
            event.button !== 0
        ) {
            return false;
        }

        if (isShellNavigationOwnedLink(link)) {
            return false;
        }

        return Boolean(
            getNavigationLinkSection(link, config) &&
            isWorkspaceSectionPath(
                link.getAttribute("href"),
                config
            )
        );
    }

    function applyDocumentSection(explorer, section, options) {
        const config = getConfig(options);
        const cleanSection = normalizeDocumentSection(section, config);

        if (!explorer || !isKnownDocumentSection(cleanSection, config)) {
            return;
        }

        updateDocumentSectionChrome(explorer, cleanSection, config);

        if (config.resetDocumentSelection) {
            config.resetDocumentSelection(explorer);
        }

        if (config.renderPreviewEmpty) {
            config.renderPreviewEmpty(explorer);
        }

        if (!isFetchableDocumentSection(cleanSection, config)) {
            renderDocumentSectionPlaceholder(explorer, cleanSection, config);
        }
    }

    function navigateDocumentSection(explorer, link, options) {
        const config = getConfig(options);
        const section = getNavigationLinkSection(link, config);

        if (!section || !isKnownDocumentSection(section, config)) {
            return;
        }

        const routePath = normalizeWorkspaceRoutePath(
            getWorkspaceSectionPath(section, config),
            config
        );

        applyDocumentSection(explorer, section, config);

        if (window.location.pathname !== routePath && window.history?.pushState) {
            window.history.pushState(
                {
                    workspaceSection: section,
                    workspaceRoute: routePath
                },
                "",
                routePath
            );
        }

        if (isFetchableDocumentSection(section, config) && config.refreshFiles) {
            config.refreshFiles(explorer, {
                quiet: true,
                section
            });
        }
    }

    function handleSectionLinkClick(event, explorer, options) {
        const config = getConfig(options);

        if (handleWorkspaceFolderTreeClick(event, explorer)) {
            return true;
        }
        const sectionLinkSelector = getSelector(config, "sectionLink", DEFAULT_DOCUMENT_SECTION_LINK_SELECTOR);
        const staticLinkSelector = getSelector(config, "staticLink", DEFAULT_DOCUMENT_STATIC_LINK_SELECTOR);
        const link = event?.target?.closest(`${sectionLinkSelector}, ${staticLinkSelector}`);

        if (!link || !explorer?.contains(link)) {
            return false;
        }

        if (!shouldHandleDocumentSectionLink(event, link, config)) {
            return false;
        }

        event.preventDefault();
        navigateDocumentSection(explorer, link, config);

        return true;
    }

    function getCurrentExplorerForHistory(selector, options) {
        const config = getConfig(options);
        const explorerSelector = cleanValue(selector) || DEFAULT_DOCUMENT_EXPLORER_SELECTOR;

        return Array.from(document.querySelectorAll(explorerSelector))
            .find(function (explorer) {
                return isDocumentSectionExplorer(explorer, config);
            }) || null;
    }

    function bindDocumentSectionHistory(selector, options) {
        const config = getConfig(options);

        if (sectionHistoryBound) {
            return;
        }

        sectionHistoryBound = true;

        window.addEventListener("popstate", function () {
            const explorer = getCurrentExplorerForHistory(selector, config);

            if (!explorer) {
                return;
            }

            const pathSection = getWorkspaceSectionFromPath(
                window.location.pathname,
                config
            );

            if (!isKnownDocumentSection(pathSection, config)) {
                return;
            }

            applyDocumentSection(explorer, pathSection, config);

            if (isFetchableDocumentSection(pathSection, config) && config.refreshFiles) {
                config.refreshFiles(explorer, {
                    quiet: true,
                    section: pathSection
                });
            }
        });
    }

    function handleDocumentRefreshClick(event, explorer, options) {
        const config = getConfig(options);
        const refreshSelector = getSelector(config, "refreshButton", DEFAULT_DOCUMENT_REFRESH_BUTTON_SELECTOR);
        const refreshButton = event?.target?.closest(refreshSelector);

        if (!refreshButton || !explorer?.contains(refreshButton)) {
            return false;
        }

        if (
            refreshButton.hidden ||
            refreshButton.disabled ||
            refreshButton.getAttribute("aria-hidden") === "true" ||
            refreshButton.getAttribute("aria-disabled") === "true"
        ) {
            return true;
        }

        event.preventDefault();
        event.stopPropagation();

        if (config.refreshFiles) {
            const section = normalizeDocumentSection(
                options?.section ||
                explorer.getAttribute("data-workspace-section") ||
                config.defaultSection,
                config
            );

            if (!isFetchableDocumentSection(section, config)) {
                renderCurrentDocumentSection(explorer, [], Object.assign({}, config, {
                    section
                }));
                syncDocumentRefreshControls(explorer, section, config);
                return true;
            }

            config.refreshFiles(explorer, {
                forceRender: true,
                quiet: false,
                section,
                source: "manual_refresh"
            });
        }

        return true;
    }

    function handleUploadClick(event, explorer, options) {
        const config = getConfig(options);
        const uploadSelector = getSelector(config, "uploadTrigger", DEFAULT_UPLOAD_TRIGGER_SELECTOR);
        const uploadTrigger = event?.target?.closest(uploadSelector);

        if (!uploadTrigger || !explorer?.contains(uploadTrigger)) {
            return false;
        }

        if (
            uploadTrigger.hidden ||
            uploadTrigger.disabled ||
            uploadTrigger.getAttribute("aria-hidden") === "true" ||
            uploadTrigger.getAttribute("aria-disabled") === "true"
        ) {
            return true;
        }

        event.preventDefault();

        if (config.openUploadPicker) {
            config.openUploadPicker(explorer);
        }

        return true;
    }

    function getInitialSectionDocuments(explorer, config) {
        if (!explorer) {
            return [];
        }

        if (config.getInitialDocuments) {
            const initialDocs = config.getInitialDocuments(explorer);

            if (Array.isArray(initialDocs) && initialDocs.length) {
                return initialDocs;
            }
        }

        if (config.getFallbackDocuments) {
            const fallbackDocs = config.getFallbackDocuments(explorer);

            if (Array.isArray(fallbackDocs) && fallbackDocs.length) {
                return fallbackDocs;
            }
        }

        return [];
    }

    function refreshInitialSection(explorer, section, config) {
        if (!isFetchableDocumentSection(section, config) || !config.refreshFiles) {
            return false;
        }

        renderDocumentSectionLoading(explorer, section, config);
        config.refreshFiles(explorer, {
            quiet: true,
            section
        });

        return true;
    }

    function initializeDocumentSection(explorer, options) {
        const config = getConfig(options);

        if (!explorer) {
            return;
        }

        bindDocumentNewMenu(explorer, config);
        bindDocumentBackgroundContextMenu(explorer, config);
        initializeWorkspaceFolderNavigation(explorer);

        if (!isDocumentSectionExplorer(explorer, config)) {
            return;
        }

        const initialRoutePath = getInitialWorkspaceRoutePath(explorer, config);
        const initialSection = getWorkspaceSectionFromPath(initialRoutePath, config);
        const shouldApplyRouteSection = isWorkspaceSectionPath(initialRoutePath, config);
        const currentSection = normalizeDocumentSection(explorer.getAttribute("data-workspace-section"), config);
        const activeSection = shouldApplyRouteSection ? initialSection : currentSection;

        if (!isKnownDocumentSection(activeSection, config)) {
            return;
        }

        updateDocumentSectionChrome(explorer, activeSection, config);

        if (activeSection === "trash") {
            if (!refreshInitialSection(explorer, "trash", config) && config.renderTrashFiles) {
                config.renderTrashFiles(explorer, []);
                syncEmptyTrashControls(explorer, "trash", config);
            }
        } else if (isRenderableFileSection(activeSection, config)) {
            const initialDocs = getInitialSectionDocuments(explorer, config);

            if (initialDocs.length && config.renderFiles) {
                config.renderFiles(explorer, initialDocs, {
                    section: activeSection
                });
                syncEmptyTrashControls(explorer, activeSection, config);
            } else if (!refreshInitialSection(explorer, activeSection, config) && config.renderFiles) {
                config.renderFiles(explorer, [], {
                    section: activeSection
                });
                syncEmptyTrashControls(explorer, activeSection, config);
            }
        } else if (!refreshInitialSection(explorer, activeSection, config)) {
            renderDocumentSectionPlaceholder(explorer, activeSection, config);
        }

        syncDocumentSectionControls(
            explorer,
            normalizeDocumentSection(explorer.getAttribute("data-workspace-section"), config),
            config
        );

        syncDocumentUploadControls(
            explorer,
            normalizeDocumentSection(explorer.getAttribute("data-workspace-section"), config),
            config
        );

        syncWorkspaceFolderCreateControls(
            explorer,
            normalizeDocumentSection(explorer.getAttribute("data-workspace-section"), config),
            config
        );

        syncDocumentRefreshControls(
            explorer,
            normalizeDocumentSection(explorer.getAttribute("data-workspace-section"), config),
            config
        );

        syncEmptyTrashControls(
            explorer,
            normalizeDocumentSection(explorer.getAttribute("data-workspace-section"), config),
            config
        );
    }

    window.SolomonWorkspaceDocumentSectionNavigation = Object.freeze({
        applyDocumentSection,
        createWorkspaceFolderFromAction,
        bindDocumentBackgroundContextMenu,
        bindDocumentNewMenu,
        bindDocumentNewMenuGlobalDelegation,
        bindDocumentSectionHistory,
        bindWorkspaceContextMenuCoordinator,
        closeDocumentBackgroundContextMenu,
        closeDocumentObjectActionMenus,
        closeDocumentObjectContext,
        closeWorkspaceContextMenus,
        closeDocumentNewMenus,
        getDocumentSectionEmptyCopy,
        getDocumentSectionEmptyState,
        getDocumentContextMenuIntent,
        getDocumentSectionIcon,
        getDocumentSectionLabel,
        getInitialWorkspaceRoutePath,
        getWorkspaceSectionFromPath,
        getWorkspaceSectionPath,
        handleDocumentNewMenuClick,
        handleDocumentBackgroundContextMenu,
        handleDocumentNewMenuKeydown,
        handleDocumentRefreshClick,
        handleSectionLinkClick,
        dispatchWorkspaceContextMenuClose,
        dispatchWorkspaceContextMenuOpen,
        handleUploadClick,
        initializeDocumentSection,
        isFetchableDocumentSection,
        isRenderableFileSection,
        isWorkspaceSectionPath,
        navigateDocumentSection,
        normalizeDocumentSection,
        normalizeWorkspaceRoutePath,
        renderCurrentDocumentSection,
        renderDocumentSectionError,
        renderDocumentSectionLoading,
        renderDocumentSectionPlaceholder,
        renderDocumentSectionStatus,
        setDocumentListState,
        shouldHandleDocumentSectionLink,
        syncDocumentRefreshControls,
        syncWorkspaceFolderNavigation,
        syncWorkspaceNavigationContract,
        syncDocumentSectionControls,
        syncDocumentUploadControls,
        syncWorkspaceFolderCreateControls,
        syncEmptyTrashControls,
        updateDocumentSectionChrome
    });

    bindDocumentNewMenuGlobalDelegation({});
})();