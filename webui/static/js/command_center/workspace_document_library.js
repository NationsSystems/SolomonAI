/* -------------------------------------------------------------------
   FILE: workspace_document_library.js
   DIRECTORY: webui/static/js/command_center/
   Solomon Documents library rendering contract
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentLibrary";
    const RECORDS_API_NAME = "SolomonWorkspaceDocumentRecords";
    const DEFAULT_COLLECTION_SELECTOR = "[data-document-collection]";
    const ACTION_MENU_PORTAL_ATTRIBUTE = "data-document-action-menu-portal";
    const ACTION_MENU_PORTAL_ITEM_ATTRIBUTE = "data-document-action-menu-portal-item";
    const ACTION_MENU_EDGE_GUTTER = 14;
    const ACTION_MENU_VERTICAL_OFFSET = 8;
    const DOCUMENT_ROW_SELECTOR = ".workspace-document-file[data-document-id]";
    const DOCUMENT_SELECTION_CHECKBOX_SELECTOR = "[data-document-select-checkbox]";
    const DOCUMENT_ACTION_MENU_BUTTON_SELECTOR = "[data-document-action-menu-button]";
    const DOCUMENT_ACTION_MENU_ITEM_SELECTOR = "[data-document-action-menu-item]";
    const SOLOMON_ACTION_SUBMENU_TRIGGER_SELECTOR = "[data-solomon-action-submenu-trigger]";
    const SOLOMON_ACTION_SUBMENU_IDS_ATTRIBUTE = "data-solomon-action-ids";
    const SOLOMON_ACTION_SUBMENU_SOURCE_SELECTOR = "[data-solomon-action-submenu-source]";
    const SOLOMON_ACTION_SUBMENU_PORTAL_ATTRIBUTE = "data-solomon-action-submenu-portal";
    const SOLOMON_ACTION_SUBMENU_EDGE_GUTTER = 14;
    const SOLOMON_ACTION_SUBMENU_GAP = 6;
    const DOCUMENT_SORT_CONTROL_SELECTOR = "[data-document-sort-control]";
    const DOCUMENT_SORT_TRIGGER_SELECTOR = "[data-document-sort-trigger]";
    const DOCUMENT_SORT_TRIGGER_HOST_SELECTOR = "[data-document-sort-trigger-host]";
    const DOCUMENT_SORT_MENU_SELECTOR = "[data-document-sort-menu]";
    const DOCUMENT_SELECTION_CHANGE_EVENT = "solomon:documents-selection-change";
    const SHARED_LISTING_CONTRACT_FALLBACK = "nations_workspace_listing_v1";
    const SHARED_LISTING_CONTRACT_ATTRIBUTE = "data-workspace-listing-contract";
    const SHARED_LISTING_CONTROLLER_ATTRIBUTE = "data-workspace-listing-controller";
    const SHARED_LISTING_ATTRIBUTE = "data-workspace-listing";
    const SHARED_LISTING_OBJECT_ATTRIBUTE = "data-workspace-object";
    const SHARED_LISTING_SELECT_EVENT = "nations:workspace-listing-select";
    const SHARED_LISTING_MENU_EVENT = "nations:workspace-listing-menu";
    const SHARED_LISTING_SELECTOR = [
        `[${SHARED_LISTING_CONTRACT_ATTRIBUTE}]`,
        `[${SHARED_LISTING_CONTROLLER_ATTRIBUTE}="true"]`
    ].join(",");
    const DOCUMENT_SELECTION_LASSO_ATTRIBUTE = "data-document-selection-lasso";
    const DOCUMENT_SELECTION_LASSO_CLASS = "workspace-document-selection-lasso";
    const DOCUMENT_SELECTION_LASSO_ACTIVE_ATTRIBUTE = "data-document-lasso-active";
    const DOCUMENT_SELECTION_LASSO_THRESHOLD = 8;
    const DOCUMENT_INTERACTIVE_SELECTOR = [
        "a",
        "button",
        "input",
        "select",
        "textarea",
        "label",
        "[role='button']",
        "[role='menuitem']",
        "[data-document-action-menu]",
        "[data-document-action-menu-button]",
        "[data-document-action-menu-item]"
    ].join(",");
    const RECENT_FILTER_CONTROL_SELECTOR = "[data-document-recent-filter-control]";
    const RECENT_FILTER_SELECT_SELECTOR = "[data-document-recent-filter]";
    const RECENT_FILTER_TRIGGER_SELECTOR = "[data-document-recent-filter-trigger]";
    const RECENT_FILTER_LABEL_SELECTOR = "[data-document-recent-filter-label]";
    const RECENT_FILTER_MENU_SELECTOR = "[data-document-recent-filter-menu]";
    const RECENT_FILTER_OPTION_SELECTOR = "[data-document-recent-filter-option]";
    const WORKSPACE_LOADED_EVENT = "solomon:workspace-loaded";
    const TRASH_STATUS_VALUES = Object.freeze(["trash", "trashed", "deleted"]);
    const DOCUMENT_EMPTY_STATES = Object.freeze({
        all: {
            kicker: "My Files",
            modifier: "files",
            primaryIcon: "folder_open",
            secondaryIcon: "description",
            accentIcon: "upload_file",
            title: "No files in My Files yet",
            message: "Upload files or drag them here to begin building your document library. Files are stored only; analysis never starts automatically.",
            actionLabel: "Upload files"
        },
        files: {
            kicker: "My Files",
            modifier: "files",
            primaryIcon: "folder_open",
            secondaryIcon: "description",
            accentIcon: "upload_file",
            title: "No files in My Files yet",
            message: "Upload files or drag them here to begin building your document library. Files are stored only; analysis never starts automatically.",
            actionLabel: "Upload files"
        },
        active: {
            kicker: "My Files",
            modifier: "files",
            primaryIcon: "folder_open",
            secondaryIcon: "rule_settings",
            accentIcon: "task_alt",
            title: "No files selected",
            message: "Select files in My Files when you are ready to prepare a document workflow."
        },
        reports: {
            kicker: "Reports",
            modifier: "reports",
            primaryIcon: "summarize",
            secondaryIcon: "description",
            accentIcon: "task_alt",
            title: "No completed reports yet",
            message: "Completed document reports and future workspace artifacts will appear here after an explicit workflow is run."
        },
        shared: {
            kicker: "Shared with me",
            modifier: "shared",
            primaryIcon: "folder_shared",
            secondaryIcon: "description",
            accentIcon: "groups",
            title: "Nothing has been shared with you",
            message: "Authorized shared folders and individually shared files will appear here without changing their original ownership."
        },
        recent: {
            kicker: "Recent",
            modifier: "recent",
            primaryIcon: "schedule",
            secondaryIcon: "description",
            accentIcon: "history",
            title: "No recent activity yet",
            message: "Recently opened, uploaded, and updated files will appear here once there is activity in the workspace."
        },
        trash: {
            kicker: "Trash",
            modifier: "trash",
            primaryIcon: "delete_outline",
            secondaryIcon: "description",
            accentIcon: "restore_from_trash",
            title: "Trash is empty",
            message: "Files moved to Trash can be restored from here until they are deleted forever."
        }
    });

    let actionMenuControllerReady = false;
    let selectionControllerReady = false;
    let sharedListingBridgeReady = false;
    let recentFilterMenuControllerReady = false;
    let activeActionMenu = null;
    let activeSelectionDrag = null;
    let activeRecentFilterControl = null;

    function createSubmenuPointerIntentGuard() {
        const pointerIntent = window.SolomonSubmenuPointerIntent;

        return typeof pointerIntent?.createGuard === "function"
            ? pointerIntent.createGuard()
            : null;
    }

    function cancelActiveSubmenuPointerIntentClose() {
        activeActionMenu?.submenuPointerIntentGuard?.cancelClose?.();
    }

    function requestActiveSolomonSubmenuClose() {
        if (!activeActionMenu?.solomonSubmenuPortal) {
            return;
        }

        const trigger = activeActionMenu.solomonSubmenuTrigger;
        const portal = activeActionMenu.solomonSubmenuPortal;
        const guard = activeActionMenu.submenuPointerIntentGuard;
        const close = function () {
            if (
                activeActionMenu?.solomonSubmenuPortal === portal &&
                activeActionMenu?.solomonSubmenuTrigger === trigger
            ) {
                closeActiveSolomonActionSubmenu();
            }
        };

        if (guard?.requestClose?.(trigger, portal, close)) {
            return;
        }

        if (!guard) {
            close();
        }
    }

    if (window[API_NAME]) {
        return;
    }

    const Records = window[RECORDS_API_NAME];

    if (!Records) {
        console.error("[DOCUMENT_LIBRARY] Missing workspace_document_records.js.");
        return;
    }

    function getSidebarApi() {
        return window.NationsCommandSidebar || {};
    }

    function getSharedListingContract() {
        return (
            getSidebarApi().constants?.WORKSPACE_LISTING_CONTRACT ||
            SHARED_LISTING_CONTRACT_FALLBACK
        );
    }

    function hasSharedListingController() {
        const sidebarApi = getSidebarApi();

        return typeof sidebarApi.initializeWorkspaceListingControls === "function";
    }

    function normalizeRouteValue(value) {
        return String(value || "").trim();
    }

    function getWorkspaceRecordField(rawDoc, normalizedDoc, keys) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);

        for (const key of keys) {
            const rawValue = cleanRawDoc[key];

            if (rawValue !== undefined && rawValue !== null && String(rawValue).trim()) {
                return rawValue;
            }

            const normalizedValue = cleanDoc[key];

            if (normalizedValue !== undefined && normalizedValue !== null && String(normalizedValue).trim()) {
                return normalizedValue;
            }
        }

        return "";
    }

    function normalizeWorkspaceObjectKind(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);
        const explicitKind = String(
            getWorkspaceRecordField(
                cleanRawDoc,
                cleanDoc,
                [
                    "workspace_item_type",
                    "item_type",
                    "resource_type",
                    "document_kind",
                    "object_type",
                    "kind"
                ]
            ) || ""
        ).trim().toLowerCase();

        if (
            explicitKind === "folder" ||
            cleanRawDoc.folder === true ||
            cleanDoc.folder === true ||
            cleanRawDoc.is_folder === true ||
            cleanDoc.is_folder === true
        ) {
            return "folder";
        }

        return "file";
    }

    function isWorkspaceFolderRecord(rawDoc, normalizedDoc) {
        return normalizeWorkspaceObjectKind(rawDoc, normalizedDoc) === "folder";
    }

    function getWorkspaceObjectId(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);
        const isFolder = isWorkspaceFolderRecord(cleanRawDoc, cleanDoc);
        const candidates = isFolder
            ? [
                "folder_id",
                "workspace_item_id",
                "object_id",
                "random_name",
                "document_id"
            ]
            : [
                "document_id",
                "random_name",
                "file_id",
                "workspace_item_id",
                "object_id"
            ];

        return normalizeRouteValue(
            getWorkspaceRecordField(cleanRawDoc, cleanDoc, candidates)
        );
    }

    function getWorkspaceObjectName(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);

        return normalizeRouteValue(
            getWorkspaceRecordField(
                cleanRawDoc,
                cleanDoc,
                [
                    "original_name",
                    "display_name",
                    "name",
                    "title",
                    "filename"
                ]
            )
        ) || (isWorkspaceFolderRecord(cleanRawDoc, cleanDoc) ? "Untitled Folder" : "Untitled Document");
    }

    function getWorkspaceObjectTypeLabel(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);

        if (isWorkspaceFolderRecord(cleanRawDoc, cleanDoc)) {
            return "Folder";
        }

        return cleanDoc.type_label || "Workspace File";
    }

    function getWorkspaceObjectIconName(rawDoc, normalizedDoc) {
        if (isWorkspaceFolderRecord(rawDoc, normalizedDoc)) {
            return "folder";
        }

        return Records.getDocumentIconName(normalizedDoc);
    }

    function getWorkspaceObjectCapabilities(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);
        const capabilities = (
            cleanRawDoc.capabilities ||
            cleanDoc.capabilities ||
            {}
        );

        return capabilities && typeof capabilities === "object"
            ? capabilities
            : {};
    }

    function isWorkspaceObjectCapabilityAllowed(rawDoc, normalizedDoc, key, fallback) {
        const capabilities = getWorkspaceObjectCapabilities(rawDoc, normalizedDoc);

        if (typeof capabilities[key] === "boolean") {
            return capabilities[key];
        }

        return Boolean(fallback);
    }

    function getWorkspaceObjectAvailableActions(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);
        const rawActions = (
            cleanRawDoc.available_actions ||
            cleanRawDoc.actions ||
            cleanDoc.available_actions ||
            cleanDoc.actions ||
            []
        );

        if (!Array.isArray(rawActions)) {
            return new Set();
        }

        return new Set(
            rawActions
                .map(function (action) {
                    return String(action || "").trim().toLowerCase();
                })
                .filter(Boolean)
        );
    }

    function normalizeSolomonActionDescriptor(action) {
        if (!action || typeof action !== "object" || Array.isArray(action)) {
            return null;
        }

        const actionId = String(action.action_id || "").trim();
        const command = String(action.command || "").trim().toLowerCase();
        const label = String(action.label || "").trim();
        const state = String(action.state || "available").trim().toLowerCase();

        if (!actionId || !command || !label || state !== "available") {
            return null;
        }

        return {
            action_id: actionId,
            label,
            family: String(action.family || "").trim().toLowerCase(),
            state,
            command,
            icon: String(action.icon || "bolt").trim() || "bolt",
            selection_policy: String(action.selection_policy || "single").trim().toLowerCase() || "single",
            result_surface: String(action.result_surface || "").trim(),
            tutorial_eligible: action.tutorial_eligible === true
        };
    }

    function getWorkspaceObjectSolomonActions(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);
        const authoritative = Boolean(
            cleanRawDoc.solomon_actions_authoritative === true ||
            cleanDoc.solomon_actions_authoritative === true
        );
        const rawActions = (
            cleanRawDoc.solomon_actions ||
            cleanDoc.solomon_actions ||
            []
        );

        if (Array.isArray(rawActions)) {
            const resolved = rawActions
                .map(normalizeSolomonActionDescriptor)
                .filter(Boolean);

            if (resolved.length || authoritative) {
                return resolved;
            }
        }

        // Solomon Actions are server-authoritative. The browser never invents
        // Action identity or eligibility when an authoritative projection is absent.
        return [];
    }

    function getWorkspaceObjectSolomonActionCount(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);
        const actions = getWorkspaceObjectSolomonActions(cleanRawDoc, cleanDoc);
        const explicitCount = Number(
            cleanRawDoc.solomon_action_count ??
            cleanDoc.solomon_action_count
        );

        if (
            Number.isInteger(explicitCount) &&
            explicitCount >= 0 &&
            explicitCount === actions.length
        ) {
            return explicitCount;
        }

        return actions.length;
    }

    function resolveWorkspaceFolderRoute(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);
        const explicitRoute = [
            cleanRawDoc.folder_url,
            cleanRawDoc.folderUrl,
            cleanRawDoc.canonical_url,
            cleanRawDoc.canonicalUrl,
            cleanRawDoc.workspace_object_route,
            cleanRawDoc.workspaceObjectRoute,
            cleanRawDoc.object_route,
            cleanRawDoc.objectRoute,
            cleanRawDoc.open_url,
            cleanRawDoc.openUrl,
            cleanRawDoc.route,
            cleanRawDoc.url,
            cleanDoc.folder_url,
            cleanDoc.folderUrl,
            cleanDoc.canonical_url,
            cleanDoc.canonicalUrl,
            cleanDoc.workspace_object_route,
            cleanDoc.workspaceObjectRoute,
            cleanDoc.object_route,
            cleanDoc.objectRoute,
            cleanDoc.open_url,
            cleanDoc.openUrl,
            cleanDoc.route,
            cleanDoc.url
        ].map(normalizeRouteValue).find(function (candidate) {
            return (
                candidate &&
                candidate !== "#" &&
                !candidate.includes("/reader")
            );
        });

        return explicitRoute || "";
    }

    function resolveDocumentReaderRoute(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);

        if (isWorkspaceFolderRecord(cleanRawDoc, cleanDoc)) {
            return "";
        }

        const explicitRoute = [
            cleanRawDoc.reader_url,
            cleanRawDoc.readerUrl,
            cleanRawDoc.document_reader_url,
            cleanRawDoc.documentReaderUrl,
            cleanRawDoc.workspace_reader_url,
            cleanRawDoc.workspaceReaderUrl,
            cleanRawDoc.viewer_url,
            cleanRawDoc.viewerUrl,
            cleanRawDoc.view_url,
            cleanRawDoc.viewUrl,
            cleanRawDoc.open_url,
            cleanRawDoc.openUrl,
            cleanRawDoc.route,
            cleanRawDoc.command_route,
            cleanDoc.reader_url,
            cleanDoc.readerUrl,
            cleanDoc.document_reader_url,
            cleanDoc.documentReaderUrl,
            cleanDoc.workspace_reader_url,
            cleanDoc.workspaceReaderUrl,
            cleanDoc.viewer_url,
            cleanDoc.viewerUrl,
            cleanDoc.view_url,
            cleanDoc.viewUrl,
            cleanDoc.open_url,
            cleanDoc.openUrl,
            cleanDoc.route,
            cleanDoc.command_route
        ].map(normalizeRouteValue).find(function (candidate) {
            return candidate && candidate !== "#";
        });

        if (explicitRoute) {
            return explicitRoute;
        }

        const opaqueId = normalizeRouteValue(
            cleanDoc.random_name ||
            cleanRawDoc.random_name ||
            cleanDoc.document_id ||
            cleanRawDoc.document_id
        );

        return opaqueId
            ? `/workspace/file/${encodeURIComponent(opaqueId)}/reader`
            : "";
    }

    function resolveWorkspaceObjectOpenRoute(rawDoc, normalizedDoc) {
        return isWorkspaceFolderRecord(rawDoc, normalizedDoc)
            ? resolveWorkspaceFolderRoute(rawDoc, normalizedDoc)
            : resolveDocumentReaderRoute(rawDoc, normalizedDoc);
    }

    function isWorkspaceObjectOpenEnabled(rawDoc, normalizedDoc, route) {
        return isWorkspaceObjectCapabilityAllowed(
            rawDoc,
            normalizedDoc,
            "can_open",
            Boolean(route)
        ) && Boolean(route);
    }

    function applySharedListingSurfaceContract(list, collection) {
        const cleanCollection = String(collection || "all").trim().toLowerCase() || "all";

        if (!list) {
            return;
        }

        list.setAttribute(SHARED_LISTING_ATTRIBUTE, "");
        list.setAttribute(SHARED_LISTING_CONTROLLER_ATTRIBUTE, "true");
        list.setAttribute(
            SHARED_LISTING_CONTRACT_ATTRIBUTE,
            getSharedListingContract()
        );
        list.setAttribute("data-workspace-listing-surface", cleanCollection);

        if (!list.hasAttribute("role")) {
            list.setAttribute("role", "listbox");
        }

        if (!list.hasAttribute("aria-label")) {
            list.setAttribute("aria-label", "Workspace files");
        }
    }

    function applySharedListingRowContract(row, rawDoc, normalizedDoc, trashed) {
        const doc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(rawDoc || {});
        const isFolder = isWorkspaceFolderRecord(rawDoc, doc);
        const objectId = getWorkspaceObjectId(rawDoc, doc);
        const randomName = doc.random_name || objectId;
        const objectName = getWorkspaceObjectName(rawDoc, doc);
        const route = resolveWorkspaceObjectOpenRoute(rawDoc, doc);
        const readerRoute = resolveDocumentReaderRoute(rawDoc, doc);
        const typeLabel = getWorkspaceObjectTypeLabel(rawDoc, doc);
        const objectKind = isFolder ? "folder" : "file";
        const canOpen = isWorkspaceObjectOpenEnabled(rawDoc, doc, route);
        const mimeType = isFolder
            ? ""
            : (
                doc.mime_type ||
                doc.mime ||
                rawDoc?.mime_type ||
                rawDoc?.mime ||
                ""
            );

        if (!row) {
            return;
        }

        row.setAttribute(SHARED_LISTING_OBJECT_ATTRIBUTE, "");
        row.setAttribute("data-workspace-object-id", objectId || randomName);
        row.setAttribute("data-workspace-object-name", objectName);
        row.setAttribute("data-workspace-object-type", objectKind);
        row.setAttribute("data-workspace-object-kind", objectKind);
        row.setAttribute("data-workspace-object-mime", mimeType);
        row.setAttribute("data-workspace-object-route", route);
        row.setAttribute("data-workspace-object-open-route", route);
        row.setAttribute("data-workspace-object-module", "documents");
        row.setAttribute("data-workspace-object-open-enabled", canOpen ? "true" : "false");
        row.setAttribute("data-workspace-object-deleted", trashed ? "true" : "false");
        row.setAttribute("data-command-route", route);
        row.setAttribute("data-command-module", "documents");
        row.setAttribute("data-document-route", route);
        row.setAttribute("data-document-open-route", route);
        row.setAttribute("data-document-reader-url", readerRoute);
        row.setAttribute("data-document-name", objectName);
        row.setAttribute("data-document-open-enabled", canOpen ? "true" : "false");
        row.setAttribute("data-document-mime", mimeType);
        row.setAttribute("data-document-type-label", typeLabel);
        row.setAttribute("data-document-folder", isFolder ? "true" : "false");

        if (isFolder) {
            row.setAttribute("data-workspace-folder-contract", "workspace_folder_v1");
            row.setAttribute("data-workspace-folder-id", objectId);
            row.setAttribute("data-folder-id", objectId);
            row.setAttribute("data-workspace-folder-open-enabled", canOpen ? "true" : "false");
            row.setAttribute("data-workspace-object-folder-visibility-only", "true");
            row.setAttribute("data-workspace-object-file-authority-inherited", "false");
            row.setAttribute("data-workspace-object-allow-ai-query", "false");
        }
    }

    function initializeSharedListingControls(list) {
        const sidebarApi = getSidebarApi();

        if (!list || typeof sidebarApi.initializeWorkspaceListingControls !== "function") {
            return;
        }

        sidebarApi.initializeWorkspaceListingControls(list);

        if (typeof sidebarApi.refreshWorkspaceListingControls === "function") {
            sidebarApi.refreshWorkspaceListingControls(list);
        }
    }

    function isInsideSharedListing(target) {
        return Boolean(
            hasSharedListingController() &&
            target?.closest?.(SHARED_LISTING_SELECTOR)
        );
    }

    function getDocumentRowFromSharedListingEvent(event) {
        const detailRow = event?.detail?.row;

        if (detailRow?.matches?.(DOCUMENT_ROW_SELECTOR)) {
            return detailRow;
        }

        return event?.target?.closest?.(DOCUMENT_ROW_SELECTOR) || null;
    }

    function syncDocumentSelectionFromSharedListing(event) {
        const row = getDocumentRowFromSharedListingEvent(event);
        const selectionRoot = getDocumentSelectionRoot(row);

        if (!row || !selectionRoot) {
            return;
        }

        getDocumentRows(selectionRoot).forEach(function (candidateRow) {
            setDocumentRowSelected(candidateRow, candidateRow === row);
        });

        selectionRoot.__solomonLastSelectedDocumentRow = row;
        dispatchDocumentSelectionChange(selectionRoot);
    }

    function applySharedListingMenuSelectionContext(event) {
        const row = getDocumentRowFromSharedListingEvent(event);
        const actionButton = (
            event?.detail?.actionElement?.closest?.(DOCUMENT_ACTION_MENU_BUTTON_SELECTOR) ||
            row?.querySelector?.(DOCUMENT_ACTION_MENU_BUTTON_SELECTOR)
        );
        const actionMenu = actionButton?.closest?.("[data-document-action-menu]");

        if (!row || !actionButton || !actionMenu) {
            return;
        }

        prepareDocumentSelectionForMenuButton(actionButton);
        applyActionMenuSelectionContext(actionMenu, actionButton);
    }

    function ensureSharedListingBridgeController() {
        if (sharedListingBridgeReady) {
            return;
        }

        sharedListingBridgeReady = true;
        document.addEventListener(
            SHARED_LISTING_SELECT_EVENT,
            syncDocumentSelectionFromSharedListing,
            true
        );
        document.addEventListener(
            SHARED_LISTING_MENU_EVENT,
            applySharedListingMenuSelectionContext,
            true
        );
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

        element.textContent = text || "";
        return element;
    }

    function safeDomId(value) {
        const cleanValue = String(value || "")
            .trim()
            .replace(/[^a-zA-Z0-9_-]+/g, "-")
            .replace(/^-+|-+$/g, "");

        return cleanValue || `document-${Date.now()}`;
    }

    function normalizeStatusValue(value) {
        return String(value || "").trim().toLowerCase();
    }

    function isTruthyPayloadFlag(value) {
        if (value === true) {
            return true;
        }

        if (typeof value === "string") {
            return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
        }

        return Boolean(value);
    }

    function isTrashedDocument(doc) {
        const rawDoc = doc && typeof doc === "object" ? doc : {};
        const normalizedDoc = Records.normalizeDocument(rawDoc);
        const status = normalizeStatusValue(
            rawDoc.document_status ||
            rawDoc.library_status ||
            rawDoc.storage_status ||
            rawDoc.status ||
            normalizedDoc.document_status ||
            normalizedDoc.library_status ||
            normalizedDoc.storage_status ||
            normalizedDoc.status
        );

        return Boolean(
            isTruthyPayloadFlag(rawDoc.trashed) ||
            isTruthyPayloadFlag(normalizedDoc.trashed) ||
            rawDoc.trashed_at ||
            normalizedDoc.trashed_at ||
            TRASH_STATUS_VALUES.includes(status)
        );
    }

    function renderMetadataGrid(doc) {
        const grid = document.createElement("div");

        grid.className = "workspace-document-metadata-grid";

        Records.buildDocumentMetadataRows(doc).forEach(function (row) {
            const item = document.createElement("div");

            item.className = "workspace-document-metadata-item";
            item.append(
                textElement("span", "", row[0]),
                textElement("strong", "", row[1])
            );
            grid.appendChild(item);
        });

        return grid;
    }

    function updateCollectionCounts(explorer, docs) {
        const viewFilesCountNode = explorer.querySelector("[data-document-active-count]");
        const allCountNode = explorer.querySelector("[data-document-total-count]");
        const activeCollection = explorer.querySelector("[data-document-collection='active'] em");
        const activeDocs = docs.filter(function (doc) {
            return !isTrashedDocument(doc);
        });
        const activeCount = activeDocs.filter(function (doc) {
            return Boolean(Records.normalizeDocument(doc).selected_for_workflow);
        }).length;

        if (viewFilesCountNode) {
            viewFilesCountNode.textContent = String(activeDocs.length);
        }

        if (allCountNode) {
            allCountNode.textContent = String(activeDocs.length);
        }

        if (activeCollection) {
            activeCollection.textContent = String(activeCount);
        }
    }

    function getActiveCollection(explorer, collectionSelector) {
        const selector = collectionSelector || DEFAULT_COLLECTION_SELECTOR;

        return explorer.querySelector(`${selector}.is-active`)?.getAttribute("data-document-collection") || "all";
    }

    function getFilteredDocuments(explorer, docs, collectionSelector) {
        const collection = getActiveCollection(explorer, collectionSelector);

        if (collection === "active") {
            return docs.filter(function (doc) {
                return Boolean(Records.normalizeDocument(doc).selected_for_workflow);
            });
        }

        return docs;
    }

    function emptyActionButton(className, attributes, iconName, label) {
        const button = document.createElement("button");

        button.type = "button";
        button.className = className;

        Object.entries(attributes || {}).forEach(function (entry) {
            button.setAttribute(entry[0], entry[1]);
        });

        button.append(
            textElement("span", "icon", iconName),
            textElement("span", "", label)
        );

        return button;
    }

    function emptyTypeCard(modifier, iconName, title, detail) {
        const card = document.createElement("article");
        const copy = document.createElement("div");

        card.className = `workspace-document-empty-type-card workspace-document-empty-type-card--${modifier}`;
        copy.append(
            textElement("strong", "", title),
            textElement("p", "", detail)
        );

        card.append(
            textElement("span", "icon", iconName),
            copy,
            textElement("em", "", "0")
        );

        return card;
    }

    function emptyAssurance(iconName, label) {
        const assurance = document.createElement("span");

        assurance.append(
            textElement("span", "icon", iconName),
            document.createTextNode(label)
        );

        return assurance;
    }

    function getDocumentSelectionRoot(row) {
        if (!row) {
            return null;
        }

        return (
            row.closest("[data-document-list]") ||
            row.closest("[data-document-browser]") ||
            row.closest("[data-document-explorer]") ||
            row.parentElement
        );
    }

    function getDocumentRows(selectionRoot) {
        if (!selectionRoot) {
            return [];
        }

        return Array.from(selectionRoot.querySelectorAll(DOCUMENT_ROW_SELECTOR));
    }

    function getSelectedDocumentRows(selectionRoot) {
        return getDocumentRows(selectionRoot).filter(function (row) {
            return row.getAttribute("data-document-selected") === "true";
        });
    }

    function getSelectedDocumentIds(selectionRoot) {
        return getSelectedDocumentRows(selectionRoot)
            .map(function (row) {
                return row.getAttribute("data-document-id") || "";
            })
            .filter(Boolean);
    }

    function getSelectedDocumentRowsForContext(row) {
        const selectionRoot = getDocumentSelectionRoot(row);
        const context = row?.getAttribute("data-document-action-context") || "active";
        const selectedRows = getSelectedDocumentRows(selectionRoot).filter(function (selectedRow) {
            return selectedRow.getAttribute("data-document-action-context") === context;
        });

        if (row?.getAttribute("data-document-selected") === "true" && selectedRows.length > 1) {
            return selectedRows;
        }

        return row ? [row] : [];
    }

    function dispatchDocumentSelectionChange(selectionRoot) {
        const selectedIds = getSelectedDocumentIds(selectionRoot);
        const selectedCount = selectedIds.length;

        if (selectionRoot) {
            selectionRoot.setAttribute("data-document-selected-count", String(selectedCount));
            selectionRoot.setAttribute("data-document-selection-active", selectedCount > 0 ? "true" : "false");
            selectionRoot.dispatchEvent(new CustomEvent(DOCUMENT_SELECTION_CHANGE_EVENT, {
                bubbles: true,
                detail: {
                    selectedCount,
                    selectedIds
                }
            }));
        }
    }

    function setDocumentRowSelected(row, selected) {
        const cleanSelected = Boolean(selected);
        const checkbox = row?.querySelector(DOCUMENT_SELECTION_CHECKBOX_SELECTOR);

        if (!row) {
            return;
        }

        row.classList.toggle("is-selected", cleanSelected);
        row.setAttribute("aria-selected", cleanSelected ? "true" : "false");
        row.setAttribute("data-document-selected", cleanSelected ? "true" : "false");

        if (checkbox) {
            checkbox.checked = cleanSelected;
            checkbox.setAttribute("aria-checked", cleanSelected ? "true" : "false");
        }
    }

    function clearDocumentSelection(selectionRoot) {
        getDocumentRows(selectionRoot).forEach(function (row) {
            setDocumentRowSelected(row, false);
        });

        dispatchDocumentSelectionChange(selectionRoot);
    }

    function selectOnlyDocumentRow(row) {
        const selectionRoot = getDocumentSelectionRoot(row);

        if (!row || !selectionRoot) {
            return;
        }

        getDocumentRows(selectionRoot).forEach(function (candidateRow) {
            setDocumentRowSelected(candidateRow, candidateRow === row);
        });

        selectionRoot.__solomonLastSelectedDocumentRow = row;
        dispatchDocumentSelectionChange(selectionRoot);
    }

    function toggleDocumentRowSelection(row) {
        const selectionRoot = getDocumentSelectionRoot(row);

        if (!row || !selectionRoot) {
            return;
        }

        setDocumentRowSelected(
            row,
            row.getAttribute("data-document-selected") !== "true"
        );

        selectionRoot.__solomonLastSelectedDocumentRow = row;
        dispatchDocumentSelectionChange(selectionRoot);
    }

    function selectDocumentRange(targetRow) {
        const selectionRoot = getDocumentSelectionRoot(targetRow);
        const rows = getDocumentRows(selectionRoot);
        const anchorRow = selectionRoot?.__solomonLastSelectedDocumentRow;
        const anchorIndex = rows.indexOf(anchorRow);
        const targetIndex = rows.indexOf(targetRow);

        if (!selectionRoot || anchorIndex < 0 || targetIndex < 0) {
            selectOnlyDocumentRow(targetRow);
            return;
        }

        const startIndex = Math.min(anchorIndex, targetIndex);
        const endIndex = Math.max(anchorIndex, targetIndex);

        rows.forEach(function (row, index) {
            setDocumentRowSelected(row, index >= startIndex && index <= endIndex);
        });

        dispatchDocumentSelectionChange(selectionRoot);
    }

    function isDocumentInteractiveTarget(target) {
        return Boolean(target?.closest(DOCUMENT_INTERACTIVE_SELECTOR));
    }

    function closeActiveSolomonActionSubmenu(options) {
        cancelActiveSubmenuPointerIntentClose();

        if (!activeActionMenu) {
            return;
        }

        const cleanOptions = options || {};
        const submenuPortal = activeActionMenu.solomonSubmenuPortal || null;
        const submenuTrigger = activeActionMenu.solomonSubmenuTrigger || null;

        submenuTrigger?.setAttribute("aria-expanded", "false");

        if (submenuPortal?.parentNode) {
            submenuPortal.parentNode.removeChild(submenuPortal);
        }

        activeActionMenu.solomonSubmenuPortal = null;
        activeActionMenu.solomonSubmenuTrigger = null;

        if (cleanOptions.restoreFocus && submenuTrigger instanceof HTMLElement) {
            submenuTrigger.focus({ preventScroll: true });
        }
    }

    function closeActiveDocumentActionMenu() {
        if (!activeActionMenu) {
            return;
        }

        const { actionMenu, actionButton, sourcePopover, portal } = activeActionMenu;

        closeActiveSolomonActionSubmenu();
        actionMenu?.classList.remove("is-open");
        actionButton?.setAttribute("aria-expanded", "false");

        if (sourcePopover) {
            sourcePopover.hidden = true;
        }

        if (portal?.parentNode) {
            portal.parentNode.removeChild(portal);
        }

        activeActionMenu.submenuPointerIntentGuard?.dispose?.();
        activeActionMenu = null;
    }

    function findSourceActionMenuItem(actionMenu, actionName) {
        if (!actionMenu || !actionName) {
            return null;
        }

        return Array.from(actionMenu.querySelectorAll(DOCUMENT_ACTION_MENU_ITEM_SELECTOR)).find(function (item) {
            return item.getAttribute("data-document-action-menu-item") === actionName;
        }) || null;
    }

    function setActionMenuItemDisabled(item, disabled) {
        if (!item) {
            return;
        }

        item.disabled = Boolean(disabled);
        item.classList.toggle("is-disabled", Boolean(disabled));
        item.setAttribute("aria-disabled", disabled ? "true" : "false");
    }

    function updateActionMenuItemLabel(item, selectedCount) {
        const label = item?.querySelector("[data-document-action-label]");
        const singleLabel = item?.getAttribute("data-document-single-label") || "";
        const multipleLabel = item?.getAttribute("data-document-multiple-label") || "";

        if (!item || !label) {
            return;
        }

        label.textContent = selectedCount > 1 && multipleLabel ? multipleLabel : singleLabel;
    }

    function applyActionMenuSelectionContext(actionMenu, actionButton) {
        const row = actionButton?.closest(DOCUMENT_ROW_SELECTOR);
        const selectedRows = getSelectedDocumentRowsForContext(row);
        const selectedIds = selectedRows.map(function (selectedRow) {
            return selectedRow.getAttribute("data-document-id") || "";
        }).filter(Boolean);
        const selectedNames = selectedRows.map(function (selectedRow) {
            return selectedRow.querySelector("strong")?.textContent || "";
        }).filter(Boolean);
        const selectedCount = Math.max(1, selectedIds.length);
        const firstSelectedId = selectedIds[0] || row?.getAttribute("data-document-id") || "";

        if (!actionMenu) {
            return;
        }

        actionMenu.setAttribute("data-document-selection-count", String(selectedCount));
        actionMenu.setAttribute("data-document-selected-ids", selectedIds.join(","));
        actionMenu.setAttribute("data-document-selected-names", selectedNames.join(" | "));

        actionMenu.querySelectorAll(DOCUMENT_ACTION_MENU_ITEM_SELECTOR).forEach(function (item) {
            const selectionPolicy = item.getAttribute("data-document-selection-policy") || "single";
            const disableForSelection = selectedCount > 1 && selectionPolicy === "single";

            item.setAttribute("data-document-id", firstSelectedId);
            item.setAttribute("data-document-selection-count", String(selectedCount));
            item.setAttribute("data-document-selected-ids", selectedIds.join(","));
            item.setAttribute("data-document-selected-names", selectedNames.join(" | "));
            setActionMenuItemDisabled(item, disableForSelection);
            updateActionMenuItemLabel(item, selectedCount);
        });
    }

    function clampMenuCoordinate(value, minimum, maximum) {
        return Math.max(minimum, Math.min(value, maximum));
    }

    function positionActiveSolomonActionSubmenu() {
        if (!activeActionMenu?.solomonSubmenuPortal || !activeActionMenu?.solomonSubmenuTrigger) {
            return;
        }

        const submenuPortal = activeActionMenu.solomonSubmenuPortal;
        const submenuTrigger = activeActionMenu.solomonSubmenuTrigger;
        const triggerRect = submenuTrigger.getBoundingClientRect();
        const viewportWidth = window.innerWidth || document.documentElement.clientWidth || 0;
        const viewportHeight = window.innerHeight || document.documentElement.clientHeight || 0;

        submenuPortal.style.left = "0px";
        submenuPortal.style.top = "0px";
        submenuPortal.style.maxWidth = `${Math.max(180, viewportWidth - (SOLOMON_ACTION_SUBMENU_EDGE_GUTTER * 2))}px`;
        submenuPortal.style.maxHeight = `${Math.max(120, viewportHeight - (SOLOMON_ACTION_SUBMENU_EDGE_GUTTER * 2))}px`;

        const submenuRect = submenuPortal.getBoundingClientRect();
        const submenuWidth = submenuRect.width || 270;
        const submenuHeight = submenuRect.height || 1;
        const rightCandidate = triggerRect.right + SOLOMON_ACTION_SUBMENU_GAP;
        const leftCandidate = triggerRect.left - submenuWidth - SOLOMON_ACTION_SUBMENU_GAP;
        const maxLeft = Math.max(
            SOLOMON_ACTION_SUBMENU_EDGE_GUTTER,
            viewportWidth - submenuWidth - SOLOMON_ACTION_SUBMENU_EDGE_GUTTER
        );
        const maxTop = Math.max(
            SOLOMON_ACTION_SUBMENU_EDGE_GUTTER,
            viewportHeight - submenuHeight - SOLOMON_ACTION_SUBMENU_EDGE_GUTTER
        );
        const resolvedLeft = rightCandidate <= maxLeft
            ? rightCandidate
            : clampMenuCoordinate(leftCandidate, SOLOMON_ACTION_SUBMENU_EDGE_GUTTER, maxLeft);
        const resolvedTop = clampMenuCoordinate(
            triggerRect.top - 7,
            SOLOMON_ACTION_SUBMENU_EDGE_GUTTER,
            maxTop
        );

        submenuPortal.style.left = `${resolvedLeft}px`;
        submenuPortal.style.top = `${resolvedTop}px`;
    }

    function getSolomonActionIdsForSubmenu(submenuTrigger) {
        if (!(submenuTrigger instanceof HTMLElement)) {
            return [];
        }

        const rawIds = submenuTrigger.getAttribute(SOLOMON_ACTION_SUBMENU_IDS_ATTRIBUTE) || "[]";

        try {
            const parsedIds = JSON.parse(rawIds);

            if (!Array.isArray(parsedIds)) {
                return [];
            }

            return parsedIds
                .map(function (actionId) {
                    return String(actionId || "").trim();
                })
                .filter(Boolean);
        } catch (error) {
            return [];
        }
    }

    function getSolomonActionSourceItems(submenuTrigger) {
        if (!activeActionMenu?.actionMenu) {
            return [];
        }

        const actionIds = new Set(getSolomonActionIdsForSubmenu(submenuTrigger));

        if (!actionIds.size) {
            return [];
        }

        return Array.from(
            activeActionMenu.actionMenu.querySelectorAll(
                `${DOCUMENT_ACTION_MENU_ITEM_SELECTOR}[data-solomon-action-id]`
            )
        ).filter(function (item) {
            return actionIds.has(item.getAttribute("data-solomon-action-id") || "");
        });
    }

    function openSolomonActionSubmenu(submenuTrigger) {
        cancelActiveSubmenuPointerIntentClose();

        if (
            !activeActionMenu ||
            !(submenuTrigger instanceof HTMLElement) ||
            !activeActionMenu.sourcePopover
        ) {
            return;
        }

        if (
            activeActionMenu.solomonSubmenuPortal &&
            activeActionMenu.solomonSubmenuTrigger === submenuTrigger
        ) {
            return;
        }

        const sourcePanel = activeActionMenu.sourcePopover.querySelector(
            SOLOMON_ACTION_SUBMENU_SOURCE_SELECTOR
        );

        if (
            !(sourcePanel instanceof HTMLElement) ||
            !sourcePanel.querySelector(
                `${DOCUMENT_ACTION_MENU_ITEM_SELECTOR}[data-solomon-action-id]`
            )
        ) {
            return;
        }

        closeActiveSolomonActionSubmenu();

        const submenuPortal = sourcePanel.cloneNode(true);

        // The original source stays hidden inside the row menu. Its clone is the
        // visible floating submenu, so remove the source marker that intentionally
        // suppresses the authoritative source panel in CSS.
        submenuPortal.removeAttribute("data-solomon-action-submenu-source");
        submenuPortal.hidden = false;
        submenuPortal.classList.add(
            "workspace-document-solomon-action-submenu-popover--portal",
            "workspace-document-file-action-popover--portal",
            "is-open"
        );
        submenuPortal.setAttribute(SOLOMON_ACTION_SUBMENU_PORTAL_ATTRIBUTE, "");
        submenuPortal.setAttribute("role", "menu");
        submenuPortal.setAttribute("aria-label", "Actions");
        submenuPortal.style.display = "grid";
        submenuPortal.style.position = "fixed";
        submenuPortal.style.inset = "auto";
        submenuPortal.style.zIndex = "10020";
        submenuPortal.style.overflowY = "auto";
        submenuPortal.style.visibility = "hidden";

        submenuPortal.querySelectorAll(DOCUMENT_ACTION_MENU_ITEM_SELECTOR).forEach(function (item) {
            item.classList.add("workspace-document-solomon-action-submenu-item--portal");
            item.setAttribute(ACTION_MENU_PORTAL_ITEM_ATTRIBUTE, "");
            item.setAttribute("tabindex", item.disabled ? "-1" : "0");
        });

        document.body.appendChild(submenuPortal);
        activeActionMenu.solomonSubmenuPortal = submenuPortal;
        activeActionMenu.solomonSubmenuTrigger = submenuTrigger;
        submenuTrigger.setAttribute("aria-expanded", "true");

        positionActiveSolomonActionSubmenu();
        submenuPortal.style.visibility = "visible";
    }

    function toggleSolomonActionSubmenu(submenuTrigger) {
        if (
            activeActionMenu?.solomonSubmenuPortal &&
            activeActionMenu?.solomonSubmenuTrigger === submenuTrigger
        ) {
            closeActiveSolomonActionSubmenu({ restoreFocus: true });
            return;
        }

        openSolomonActionSubmenu(submenuTrigger);
    }

    function focusFirstSolomonActionSubmenuItem() {
        requestAnimationFrame(function () {
            const firstItem = activeActionMenu?.solomonSubmenuPortal?.querySelector(
                `${DOCUMENT_ACTION_MENU_ITEM_SELECTOR}:not([disabled]):not([aria-disabled='true'])`
            );

            if (firstItem instanceof HTMLElement) {
                firstItem.focus({ preventScroll: true });
            }
        });
    }

    function positionDocumentActionMenuPortal() {
        if (!activeActionMenu?.portal || !activeActionMenu?.actionButton) {
            return;
        }

        const { actionButton, portal, contextPoint } = activeActionMenu;
        const buttonRect = actionButton.getBoundingClientRect();
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
            resolvedLeft = clampMenuCoordinate(preferredLeft, ACTION_MENU_EDGE_GUTTER, maxLeft);
            resolvedTop = clampMenuCoordinate(preferredTop, ACTION_MENU_EDGE_GUTTER, maxTop);
        } else {
            const fallbackTop = buttonRect.top - portalHeight - ACTION_MENU_VERTICAL_OFFSET;

            resolvedLeft = clampMenuCoordinate(preferredLeft, ACTION_MENU_EDGE_GUTTER, maxLeft);
            resolvedTop = preferredTop > maxTop
                ? Math.max(ACTION_MENU_EDGE_GUTTER, fallbackTop)
                : Math.max(ACTION_MENU_EDGE_GUTTER, preferredTop);
        }

        portal.style.left = `${resolvedLeft}px`;
        portal.style.top = `${resolvedTop}px`;
        positionActiveSolomonActionSubmenu();
    }

    function buildDocumentActionMenuPortal(actionMenu, sourcePopover, options) {
        const portal = sourcePopover.cloneNode(true);
        const cleanOptions = options || {};
        const isContextMenu = cleanOptions.mode === "context";

        portal.hidden = false;
        portal.setAttribute(ACTION_MENU_PORTAL_ATTRIBUTE, "");
        portal.classList.add("workspace-document-file-action-popover--portal", "is-open");
        portal.classList.toggle("workspace-document-file-action-popover--context", isContextMenu);
        portal.setAttribute("data-document-menu-position", isContextMenu ? "context" : "button");
        portal.style.display = "grid";
        portal.style.position = "fixed";
        portal.style.inset = "auto";
        portal.style.zIndex = "10000";
        portal.style.maxHeight = "calc(100vh - 28px)";
        portal.style.overflowY = "auto";
        portal.style.visibility = "hidden";

        // The cloned trigger carries only stable server-resolved Action IDs.
        // Keep execution-source items in the original menu and remove hidden
        // duplicate panels from the floating parent menu.
        portal.querySelectorAll(SOLOMON_ACTION_SUBMENU_SOURCE_SELECTOR).forEach(function (sourcePanel) {
            sourcePanel.remove();
        });

        portal.querySelectorAll(SOLOMON_ACTION_SUBMENU_TRIGGER_SELECTOR).forEach(function (trigger) {
            trigger.setAttribute("aria-expanded", "false");
            trigger.setAttribute("tabindex", "0");
        });

        portal.querySelectorAll(DOCUMENT_ACTION_MENU_ITEM_SELECTOR).forEach(function (item) {
            item.setAttribute(ACTION_MENU_PORTAL_ITEM_ATTRIBUTE, "");
            item.setAttribute("tabindex", item.disabled ? "-1" : "0");
        });

        document.body.appendChild(portal);

        requestAnimationFrame(function () {
            if (!activeActionMenu || activeActionMenu.portal !== portal) {
                return;
            }

            positionDocumentActionMenuPortal();
            portal.style.visibility = "visible";
        });

        return portal;
    }

    function getDocumentMenuContextPoint(options) {
        const cleanOptions = options || {};
        const clientX = Number(cleanOptions.clientX);
        const clientY = Number(cleanOptions.clientY);

        if (cleanOptions.mode !== "context" || !Number.isFinite(clientX) || !Number.isFinite(clientY)) {
            return null;
        }

        return {
            clientX,
            clientY
        };
    }

    function openDocumentActionMenu(actionMenu, actionButton, options) {
        const sourcePopover = actionMenu?.querySelector(".workspace-document-file-action-popover");
        const cleanOptions = options || {};

        if (!actionMenu || !actionButton || !sourcePopover) {
            return;
        }

        closeActiveDocumentActionMenu();
        applyActionMenuSelectionContext(actionMenu, actionButton);

        actionMenu.classList.add("is-open");
        actionButton.setAttribute("aria-expanded", "true");
        sourcePopover.hidden = true;

        activeActionMenu = {
            actionMenu,
            actionButton,
            sourcePopover,
            contextPoint: getDocumentMenuContextPoint(cleanOptions),
            portal: buildDocumentActionMenuPortal(actionMenu, sourcePopover, cleanOptions),
            solomonSubmenuPortal: null,
            solomonSubmenuTrigger: null,
            submenuPointerIntentGuard: createSubmenuPointerIntentGuard()
        };
    }

    function toggleDocumentActionMenu(actionMenu, actionButton) {
        if (activeActionMenu?.actionMenu === actionMenu) {
            closeActiveDocumentActionMenu();
            return;
        }

        openDocumentActionMenu(actionMenu, actionButton);
    }

    function dispatchSourceMenuItemClick(portalItem) {
        const actionName = portalItem?.getAttribute("data-document-action-menu-item") || "";
        const solomonActionId = portalItem?.getAttribute("data-solomon-action-id") || "";
        const sourceItem = solomonActionId
            ? Array.from(activeActionMenu?.actionMenu?.querySelectorAll(DOCUMENT_ACTION_MENU_ITEM_SELECTOR) || []).find(function (item) {
                return item.getAttribute("data-solomon-action-id") === solomonActionId;
            }) || null
            : findSourceActionMenuItem(activeActionMenu?.actionMenu, actionName);

        if (
            portalItem?.disabled ||
            portalItem?.getAttribute("aria-disabled") === "true" ||
            sourceItem?.disabled ||
            sourceItem?.getAttribute("aria-disabled") === "true"
        ) {
            return;
        }

        closeActiveDocumentActionMenu();

        if (!sourceItem) {
            return;
        }

        sourceItem.dispatchEvent(new MouseEvent("click", {
            bubbles: true,
            cancelable: true,
            view: window
        }));
    }

    function prepareDocumentSelectionForMenuButton(actionButton) {
        const row = actionButton?.closest(DOCUMENT_ROW_SELECTOR);
        const selectionRoot = getDocumentSelectionRoot(row);
        const selectedRows = getSelectedDocumentRows(selectionRoot);

        if (!row || !selectionRoot) {
            return;
        }

        if (row.getAttribute("data-document-selected") === "true" && selectedRows.length > 1) {
            return;
        }

        selectOnlyDocumentRow(row);
    }

    function handleDocumentActionMenuClick(event) {
        const submenuTrigger = event.target.closest(SOLOMON_ACTION_SUBMENU_TRIGGER_SELECTOR);

        if (submenuTrigger && submenuTrigger.closest(`[${ACTION_MENU_PORTAL_ATTRIBUTE}]`)) {
            event.preventDefault();
            event.stopPropagation();
            toggleSolomonActionSubmenu(submenuTrigger);
            return;
        }

        const portalItem = event.target.closest(`[${ACTION_MENU_PORTAL_ITEM_ATTRIBUTE}]`);

        if (portalItem) {
            event.preventDefault();
            event.stopPropagation();
            dispatchSourceMenuItemClick(portalItem);
            return;
        }

        const submenuPortal = event.target.closest(`[${SOLOMON_ACTION_SUBMENU_PORTAL_ATTRIBUTE}]`);

        if (submenuPortal) {
            event.preventDefault();
            event.stopPropagation();
            return;
        }

        const portal = event.target.closest(`[${ACTION_MENU_PORTAL_ATTRIBUTE}]`);

        if (portal) {
            event.preventDefault();
            event.stopPropagation();
            return;
        }

        const actionButton = event.target.closest(DOCUMENT_ACTION_MENU_BUTTON_SELECTOR);

        if (actionButton && isInsideSharedListing(actionButton)) {
            prepareDocumentSelectionForMenuButton(actionButton);
            return;
        }

        if (actionButton) {
            const actionMenu = actionButton.closest("[data-document-action-menu]");

            if (!actionMenu) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();
            prepareDocumentSelectionForMenuButton(actionButton);
            toggleDocumentActionMenu(actionMenu, actionButton);
            return;
        }

        if (activeActionMenu) {
            closeActiveDocumentActionMenu();
        }
    }

    function handleDocumentActionMenuKeydown(event) {
        const submenuPortal = event.target.closest(`[${SOLOMON_ACTION_SUBMENU_PORTAL_ATTRIBUTE}]`);
        const submenuTrigger = event.target.closest(SOLOMON_ACTION_SUBMENU_TRIGGER_SELECTOR);

        if (submenuPortal && event.key === "ArrowLeft") {
            event.preventDefault();
            closeActiveSolomonActionSubmenu({ restoreFocus: true });
            return;
        }

        if (submenuTrigger && ["Enter", " ", "ArrowRight"].includes(event.key)) {
            event.preventDefault();
            openSolomonActionSubmenu(submenuTrigger);
            focusFirstSolomonActionSubmenuItem();
            return;
        }

        if (event.key === "Escape" && activeActionMenu?.solomonSubmenuPortal) {
            event.preventDefault();
            closeActiveSolomonActionSubmenu({ restoreFocus: true });
            return;
        }

        if (event.key === "Escape" && activeActionMenu) {
            const returnFocus = activeActionMenu.actionButton;

            event.preventDefault();
            closeActiveDocumentActionMenu();
            returnFocus?.focus({ preventScroll: true });
            return;
        }

        const actionButton = event.target.closest(DOCUMENT_ACTION_MENU_BUTTON_SELECTOR);

        if (actionButton && (event.key === "Enter" || event.key === " ")) {
            const actionMenu = actionButton.closest("[data-document-action-menu]");

            if (!actionMenu) {
                return;
            }

            event.preventDefault();
            prepareDocumentSelectionForMenuButton(actionButton);
            toggleDocumentActionMenu(actionMenu, actionButton);
        }
    }

    function handleDocumentActionMenuPointerOver(event) {
        if (!activeActionMenu) {
            return;
        }

        const submenuTrigger = event.target.closest(SOLOMON_ACTION_SUBMENU_TRIGGER_SELECTOR);

        if (submenuTrigger && submenuTrigger.closest(`[${ACTION_MENU_PORTAL_ATTRIBUTE}]`)) {
            cancelActiveSubmenuPointerIntentClose();
            openSolomonActionSubmenu(submenuTrigger);
            return;
        }

        if (event.target.closest(`[${SOLOMON_ACTION_SUBMENU_PORTAL_ATTRIBUTE}]`)) {
            cancelActiveSubmenuPointerIntentClose();
            return;
        }

        if (activeActionMenu.solomonSubmenuPortal) {
            requestActiveSolomonSubmenuClose();
        }
    }

    function handleDocumentActionMenuViewportChange() {
        if (activeActionMenu) {
            positionDocumentActionMenuPortal();
        }
    }

    function ensureDocumentActionMenuController() {
        if (actionMenuControllerReady) {
            return;
        }

        actionMenuControllerReady = true;
        document.addEventListener("click", handleDocumentActionMenuClick, true);
        document.addEventListener("pointerover", handleDocumentActionMenuPointerOver, true);
        document.addEventListener("keydown", handleDocumentActionMenuKeydown, true);
        window.addEventListener("resize", handleDocumentActionMenuViewportChange);
        window.addEventListener("scroll", handleDocumentActionMenuViewportChange, true);
    }

    function getDocumentSelectionRootFromTarget(target) {
        const row = target?.closest?.(DOCUMENT_ROW_SELECTOR);

        if (row) {
            return getDocumentSelectionRoot(row);
        }

        return (
            target?.closest?.("[data-document-list]") ||
            target?.closest?.("[data-document-browser]") ||
            target?.closest?.("[data-document-explorer]") ||
            null
        );
    }

    function isPrimaryMousePointer(event) {
        if (!event || event.button !== 0) {
            return false;
        }

        if (event.pointerType && !["mouse", "pen"].includes(event.pointerType)) {
            return false;
        }

        return true;
    }

    function canStartDocumentSelectionLasso(event, selectionRoot) {
        if (!isPrimaryMousePointer(event) || !selectionRoot) {
            return false;
        }

        if (isDocumentInteractiveTarget(event.target)) {
            return false;
        }

        if (!getDocumentRows(selectionRoot).length) {
            return false;
        }

        return Boolean(event.target.closest?.("[data-document-list]"));
    }

    function createDocumentSelectionLasso() {
        const lasso = document.createElement("div");

        lasso.className = DOCUMENT_SELECTION_LASSO_CLASS;
        lasso.setAttribute(DOCUMENT_SELECTION_LASSO_ATTRIBUTE, "");
        lasso.setAttribute("aria-hidden", "true");
        lasso.style.position = "fixed";
        lasso.style.left = "0px";
        lasso.style.top = "0px";
        lasso.style.width = "0px";
        lasso.style.height = "0px";

        document.body.appendChild(lasso);

        return lasso;
    }

    function removeDocumentSelectionLasso() {
        const lasso = activeSelectionDrag?.lasso;

        if (lasso?.parentNode) {
            lasso.parentNode.removeChild(lasso);
        }

        document.documentElement.removeAttribute(DOCUMENT_SELECTION_LASSO_ACTIVE_ATTRIBUTE);
    }

    function getNormalizedPointerRect(startX, startY, currentX, currentY) {
        const left = Math.min(startX, currentX);
        const top = Math.min(startY, currentY);
        const right = Math.max(startX, currentX);
        const bottom = Math.max(startY, currentY);

        return {
            left,
            top,
            right,
            bottom,
            width: Math.max(0, right - left),
            height: Math.max(0, bottom - top)
        };
    }

    function positionDocumentSelectionLasso(lasso, rect) {
        if (!lasso || !rect) {
            return;
        }

        lasso.style.left = `${rect.left}px`;
        lasso.style.top = `${rect.top}px`;
        lasso.style.width = `${rect.width}px`;
        lasso.style.height = `${rect.height}px`;
    }

    function doRectsIntersect(firstRect, secondRect) {
        if (!firstRect || !secondRect) {
            return false;
        }

        return !(
            secondRect.left > firstRect.right ||
            secondRect.right < firstRect.left ||
            secondRect.top > firstRect.bottom ||
            secondRect.bottom < firstRect.top
        );
    }

    function getRowsIntersectingSelectionRect(selectionRoot, selectionRect) {
        return getDocumentRows(selectionRoot).filter(function (row) {
            return doRectsIntersect(selectionRect, row.getBoundingClientRect());
        });
    }

    function setDocumentSelectionClickSuppression(selectionRoot) {
        if (!selectionRoot) {
            return;
        }

        selectionRoot.__solomonSuppressNextDocumentSelectionClick = true;

        window.setTimeout(function () {
            if (selectionRoot.__solomonSuppressNextDocumentSelectionClick) {
                selectionRoot.__solomonSuppressNextDocumentSelectionClick = false;
            }
        }, 0);
    }

    function applyDocumentLassoSelection(event) {
        if (!activeSelectionDrag?.active) {
            return;
        }

        const selectionRoot = activeSelectionDrag.selectionRoot;
        const selectionRect = getNormalizedPointerRect(
            activeSelectionDrag.startX,
            activeSelectionDrag.startY,
            event.clientX,
            event.clientY
        );
        const intersectingRows = getRowsIntersectingSelectionRect(selectionRoot, selectionRect);
        const intersectingRowSet = new Set(intersectingRows);
        const baselineRowSet = activeSelectionDrag.preserveSelection
            ? activeSelectionDrag.baselineRows
            : new Set();

        positionDocumentSelectionLasso(activeSelectionDrag.lasso, selectionRect);

        getDocumentRows(selectionRoot).forEach(function (row) {
            setDocumentRowSelected(row, baselineRowSet.has(row) || intersectingRowSet.has(row));
        });

        dispatchDocumentSelectionChange(selectionRoot);
    }

    function activateDocumentSelectionLasso(event) {
        if (!activeSelectionDrag || activeSelectionDrag.active) {
            return;
        }

        activeSelectionDrag.active = true;
        activeSelectionDrag.lasso = createDocumentSelectionLasso();
        document.documentElement.setAttribute(DOCUMENT_SELECTION_LASSO_ACTIVE_ATTRIBUTE, "true");
        setDocumentSelectionClickSuppression(activeSelectionDrag.selectionRoot);
        closeActiveDocumentActionMenu();

        if (!activeSelectionDrag.preserveSelection) {
            clearDocumentSelection(activeSelectionDrag.selectionRoot);
        }

        applyDocumentLassoSelection(event);
    }

    function handleDocumentSelectionPointerDown(event) {
        const selectionRoot = getDocumentSelectionRootFromTarget(event.target);

        if (!canStartDocumentSelectionLasso(event, selectionRoot)) {
            return;
        }

        activeSelectionDrag = {
            active: false,
            pointerId: event.pointerId,
            selectionRoot,
            startX: event.clientX,
            startY: event.clientY,
            preserveSelection: Boolean(event.ctrlKey || event.metaKey),
            baselineRows: new Set(getSelectedDocumentRows(selectionRoot)),
            lasso: null
        };
    }

    function handleDocumentSelectionPointerMove(event) {
        if (!activeSelectionDrag || event.pointerId !== activeSelectionDrag.pointerId) {
            return;
        }

        const deltaX = Math.abs(event.clientX - activeSelectionDrag.startX);
        const deltaY = Math.abs(event.clientY - activeSelectionDrag.startY);

        if (!activeSelectionDrag.active && Math.max(deltaX, deltaY) >= DOCUMENT_SELECTION_LASSO_THRESHOLD) {
            activateDocumentSelectionLasso(event);
        }

        if (!activeSelectionDrag.active) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        applyDocumentLassoSelection(event);
    }

    function finishDocumentSelectionLasso(event) {
        if (!activeSelectionDrag || event.pointerId !== activeSelectionDrag.pointerId) {
            return;
        }

        const selectionRoot = activeSelectionDrag.selectionRoot;
        const wasActive = activeSelectionDrag.active;

        if (wasActive) {
            event.preventDefault();
            event.stopPropagation();
            applyDocumentLassoSelection(event);
            dispatchDocumentSelectionChange(selectionRoot);
            setDocumentSelectionClickSuppression(selectionRoot);
        }

        removeDocumentSelectionLasso();
        activeSelectionDrag = null;
    }

    function handleDocumentSelectionPointerCancel(event) {
        if (!activeSelectionDrag || event.pointerId !== activeSelectionDrag.pointerId) {
            return;
        }

        removeDocumentSelectionLasso();
        activeSelectionDrag = null;
    }

    function handleDocumentSelectionClick(event) {
        const selectionRoot = getDocumentSelectionRootFromTarget(event.target);

        if (selectionRoot?.__solomonSuppressNextDocumentSelectionClick) {
            selectionRoot.__solomonSuppressNextDocumentSelectionClick = false;
            event.preventDefault();
            event.stopPropagation();
            return;
        }

        const checkbox = event.target.closest(DOCUMENT_SELECTION_CHECKBOX_SELECTOR);

        if (checkbox) {
            const row = checkbox.closest(DOCUMENT_ROW_SELECTOR);

            event.preventDefault();
            event.stopPropagation();
            closeActiveDocumentActionMenu();
            toggleDocumentRowSelection(row);
            row?.focus({ preventScroll: true });
            return;
        }

        const row = event.target.closest(DOCUMENT_ROW_SELECTOR);

        if (!row || isDocumentInteractiveTarget(event.target)) {
            return;
        }

        if (event.shiftKey) {
            event.preventDefault();
            event.stopPropagation();
            closeActiveDocumentActionMenu();
            selectDocumentRange(row);
            row.focus({ preventScroll: true });
            return;
        }

        if (event.ctrlKey || event.metaKey) {
            event.preventDefault();
            event.stopPropagation();
            closeActiveDocumentActionMenu();
            toggleDocumentRowSelection(row);
            row.focus({ preventScroll: true });
        }
    }

    function handleDocumentSelectionKeydown(event) {
        const row = event.target.closest(DOCUMENT_ROW_SELECTOR);

        if (!row || isDocumentInteractiveTarget(event.target)) {
            return;
        }

        if (event.key === " " || event.key === "Spacebar") {
            event.preventDefault();
            closeActiveDocumentActionMenu();
            toggleDocumentRowSelection(row);
        }

        if (event.key === "Escape") {
            const selectionRoot = getDocumentSelectionRoot(row);

            if (getSelectedDocumentRows(selectionRoot).length > 0) {
                event.preventDefault();
                clearDocumentSelection(selectionRoot);
            }
        }
    }

    function handleDocumentSelectionContextMenu(event) {
        const row = event.target.closest(DOCUMENT_ROW_SELECTOR);

        if (!row || event.target.closest(DOCUMENT_ACTION_MENU_ITEM_SELECTOR)) {
            return;
        }

        if (isInsideSharedListing(row)) {
            return;
        }

        const actionMenu = row.querySelector("[data-document-action-menu]");
        const actionButton = row.querySelector(DOCUMENT_ACTION_MENU_BUTTON_SELECTOR);
        const selectionRoot = getDocumentSelectionRoot(row);
        const selectedRows = getSelectedDocumentRows(selectionRoot);

        if (!actionMenu || !actionButton) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        if (row.getAttribute("data-document-selected") !== "true" || selectedRows.length <= 1) {
            selectOnlyDocumentRow(row);
        }

        row.focus({ preventScroll: true });
        openDocumentActionMenu(actionMenu, actionButton, {
            mode: "context",
            clientX: event.clientX,
            clientY: event.clientY
        });
    }

    function ensureDocumentSelectionController() {
        if (selectionControllerReady) {
            return;
        }

        selectionControllerReady = true;
        document.addEventListener("pointerdown", handleDocumentSelectionPointerDown, true);
        document.addEventListener("pointermove", handleDocumentSelectionPointerMove, true);
        document.addEventListener("pointerup", finishDocumentSelectionLasso, true);
        document.addEventListener("pointercancel", handleDocumentSelectionPointerCancel, true);
        document.addEventListener("click", handleDocumentSelectionClick, true);
        document.addEventListener("keydown", handleDocumentSelectionKeydown, true);
        document.addEventListener("contextmenu", handleDocumentSelectionContextMenu, true);
    }

    function normalizeEmptyCollection(collection) {
        const cleanCollection = String(collection || "all").trim().toLowerCase();

        return DOCUMENT_EMPTY_STATES[cleanCollection] ? cleanCollection : "all";
    }

    function isLibraryDropCollection(collection) {
        const cleanCollection = normalizeEmptyCollection(collection);

        return cleanCollection === "all" || cleanCollection === "files";
    }

    function hasAuthorizedLibraryDropContract(list) {
        const dropZone = list?.closest?.("[data-document-drop-zone='library']");

        if (!dropZone) {
            return false;
        }

        return (
            dropZone.getAttribute("data-document-drop-target") === "my_files" &&
            dropZone.getAttribute("data-document-drop-contract") === "stored_document_only"
        );
    }

    function syncLibraryDropSurface(list, collection) {
        if (!list || !isLibraryDropCollection(collection) || !hasAuthorizedLibraryDropContract(list)) {
            return;
        }

        list.setAttribute("data-document-drop-surface", "library");
    }

    function getDocumentSectionsApi() {
        return window.SolomonWorkspaceDocumentSections || null;
    }

    function getEmptyStateContext(list, collection) {
        const explorer = list?.closest?.("[data-document-explorer]") || null;
        const cleanCollection = normalizeEmptyCollection(collection);
        const currentFolderId = String(
            explorer?.getAttribute("data-workspace-current-folder-id") || ""
        ).trim();

        return {
            collection: cleanCollection,
            explorer,
            currentFolderId,
            isCurrentFolder: cleanCollection === "files" && Boolean(currentFolderId)
        };
    }

    function getEmptyStateConfig(list, collection) {
        const context = getEmptyStateContext(list, collection);
        const sectionsApi = getDocumentSectionsApi();
        const fallback = DOCUMENT_EMPTY_STATES[context.collection] || DOCUMENT_EMPTY_STATES.all;
        const sectionConfig = typeof sectionsApi?.getDocumentSectionEmptyState === "function"
            ? sectionsApi.getDocumentSectionEmptyState(context.collection)
            : null;
        const config = Object.assign({}, fallback, sectionConfig || {});

        config.kicker = fallback.kicker || config.kicker || "Documents";

        if (context.isCurrentFolder) {
            config.kicker = "Folder";
            config.title = "This folder is empty";
            config.message = "Upload files or drag them into this folder. Files are stored here only; no document analysis starts automatically.";
            config.actionLabel = "Upload files";
        }

        return config;
    }

    function canRenderEmptyStateUploadAction(list, collection, config) {
        return Boolean(
            config?.actionLabel &&
            isLibraryDropCollection(collection) &&
            hasAuthorizedLibraryDropContract(list)
        );
    }

    function createEmptyStateIllustration(config) {
        const illustration = document.createElement("div");
        const primaryIcon = textElement(
            "span",
            "icon workspace-document-empty-illustration-icon workspace-document-empty-illustration-icon--primary",
            config.primaryIcon
        );
        const secondaryIcon = textElement(
            "span",
            "icon workspace-document-empty-illustration-icon workspace-document-empty-illustration-icon--secondary",
            config.secondaryIcon
        );
        const accentIcon = textElement(
            "span",
            "icon workspace-document-empty-illustration-icon workspace-document-empty-illustration-icon--accent",
            config.accentIcon
        );

        illustration.className = "workspace-document-empty-illustration";
        primaryIcon.setAttribute("aria-hidden", "true");
        secondaryIcon.setAttribute("aria-hidden", "true");
        accentIcon.setAttribute("aria-hidden", "true");
        illustration.append(primaryIcon, secondaryIcon, accentIcon);

        return illustration;
    }

    function createEmptyStateCopy(config) {
        const copy = document.createElement("div");

        copy.className = "workspace-document-empty-copy";
        copy.append(
            textElement("p", "workspace-document-empty-kicker", config.kicker || "Documents"),
            textElement("strong", "workspace-document-empty-title", config.title),
            textElement("p", "workspace-document-empty-message", config.message)
        );

        return copy;
    }

    function createEmptyStateUploadAction(list, collection, config) {
        if (!canRenderEmptyStateUploadAction(list, collection, config)) {
            return null;
        }

        return emptyActionButton(
            "workspace-document-command workspace-document-empty-action",
            {
                "data-document-upload-placeholder": "",
                "data-document-upload-trigger": "",
                "aria-label": config.actionLabel
            },
            "upload_file",
            config.actionLabel
        );
    }

    function createEmptyState(list, collection) {
        const cleanCollection = normalizeEmptyCollection(collection);
        const config = getEmptyStateConfig(list, cleanCollection);
        const emptyState = document.createElement("article");

        emptyState.className = [
            "workspace-document-section-empty",
            "workspace-document-empty-state",
            `workspace-document-empty-state--${config.modifier}`
        ].join(" ");
        emptyState.setAttribute("data-confirmed-empty", "true");
        emptyState.setAttribute("data-document-empty-section", cleanCollection);
        emptyState.setAttribute("aria-label", config.title);

        if (isLibraryDropCollection(cleanCollection)) {
            emptyState.setAttribute("data-document-drop-surface", "library");
        }

        const action = createEmptyStateUploadAction(
            list,
            cleanCollection,
            config
        );

        emptyState.append(
            createEmptyStateIllustration(config),
            createEmptyStateCopy(config)
        );

        if (action) {
            emptyState.appendChild(action);
        }

        return emptyState;
    }

    function renderEmptyFiles(list, collection) {
        if (!list) {
            return;
        }

        clearNode(list);
        syncLibraryDropSurface(list, collection);
        applySharedListingSurfaceContract(list, collection || "all");
        ensureSharedListingBridgeController();
        list.setAttribute("data-document-empty-collection", collection || "all");
        list.setAttribute("data-document-empty-state", "visible");
        list.setAttribute("data-document-list-state", "empty");
        list.setAttribute("aria-busy", "false");
        list.appendChild(createEmptyState(list, collection));
        initializeSharedListingControls(list);
    }

    function createDocumentSelectionControl(doc, options) {
        const cleanOptions = options || {};
        const label = document.createElement("label");
        const checkbox = document.createElement("input");
        const visual = document.createElement("span");
        const documentName = cleanOptions.objectName || doc.original_name || "selected file";
        const objectLabel = cleanOptions.objectLabel || "file";
        const disabled = cleanOptions.disabled === true;

        label.className = "workspace-document-file-selection";
        label.setAttribute("data-document-list-cell", "selection");
        label.setAttribute("aria-label", `Select ${objectLabel} ${documentName}`);

        checkbox.type = "checkbox";
        checkbox.className = "workspace-document-file-selection-input";
        checkbox.value = doc.document_id || "";
        checkbox.setAttribute("data-document-select-checkbox", "");
        checkbox.setAttribute("data-document-id", doc.document_id || "");
        checkbox.setAttribute("aria-checked", "false");

        if (disabled) {
            checkbox.disabled = true;
            checkbox.tabIndex = -1;
            checkbox.setAttribute("aria-disabled", "true");
            checkbox.setAttribute("data-document-select-disabled", "true");
            label.setAttribute("aria-disabled", "true");
        }

        visual.className = "workspace-document-file-selection-box";
        visual.setAttribute("aria-hidden", "true");

        label.append(checkbox, visual);

        return label;
    }


    function createDocumentActionMenuButton(doc, options) {
        const button = document.createElement("button");
        const cleanOptions = options || {};
        const context = String(cleanOptions.context || "active").trim().toLowerCase();
        const menuId = String(cleanOptions.menuId || "").trim();
        const objectKind = String(cleanOptions.objectKind || "file").trim().toLowerCase();
        const actionLabel = objectKind === "folder"
            ? "Folder options"
            : (context === "trash" ? "Trash options" : "File options");
        const icon = textElement("span", "icon", "more_vert");

        button.type = "button";
        button.className = "workspace-document-file-action-button";
        button.setAttribute("data-document-action-menu-button", doc.document_id || "");
        button.setAttribute("aria-haspopup", "menu");
        button.setAttribute("aria-expanded", "false");
        button.setAttribute("aria-label", `${actionLabel} for ${doc.original_name || "selected file"}`);

        if (menuId) {
            button.setAttribute("aria-controls", menuId);
        }

        icon.setAttribute("aria-hidden", "true");
        button.append(icon);

        return button;
    }

    function createDocumentActionMenu(rawDoc) {
        const cleanDoc = Records.normalizeDocument(rawDoc);
        const actionMenu = document.createElement("div");
        const trashed = isTrashedDocument(rawDoc);
        const isFolder = isWorkspaceFolderRecord(rawDoc, cleanDoc);
        const objectId = getWorkspaceObjectId(rawDoc, cleanDoc);
        const menuDoc = isFolder
            ? Object.assign({}, cleanDoc, {
                document_id: objectId,
                random_name: objectId,
                folder_id: objectId,
                workspace_item_id: objectId,
                workspace_item_type: "folder",
                original_name: getWorkspaceObjectName(rawDoc, cleanDoc),
                type_label: "Folder",
                selected_for_workflow: false
            })
            : cleanDoc;
        const menuId = `workspace-document-action-menu-${safeDomId(objectId || cleanDoc.document_id || cleanDoc.random_name)}`;
        const actionButton = createDocumentActionMenuButton(menuDoc, {
            context: trashed ? "trash" : "active",
            menuId,
            objectKind: isFolder ? "folder" : "file"
        });
        const popover = document.createElement("div");

        if (isFolder) {
            return createFolderActionMenu(rawDoc, menuDoc, actionButton, menuId);
        }

        ensureDocumentActionMenuController();

        actionMenu.className = "workspace-document-file-action-menu";
        actionMenu.setAttribute("data-document-list-cell", "actions");
        actionMenu.setAttribute("data-document-action-menu", "");
        actionMenu.setAttribute("data-document-menu-context", trashed ? "trash" : "active");
        actionMenu.setAttribute("data-document-selection-count", "1");
        actionMenu.setAttribute("data-document-selected-ids", cleanDoc.document_id || "");
        popover.id = menuId;
        popover.className = "workspace-document-file-action-popover";
        popover.setAttribute("role", "menu");
        popover.setAttribute("aria-label", `${trashed ? "Trash" : "File"} options for ${cleanDoc.original_name || "selected file"}`);
        popover.hidden = true;

        if (trashed) {
            appendTrashDocumentActions(popover, cleanDoc);
        } else {
            appendActiveDocumentActions(popover, rawDoc, cleanDoc);
        }

        actionMenu.append(actionButton, popover);

        return actionMenu;
    }

    function createDocumentActionMenuItem(doc, action, iconName, label, options) {
        const item = document.createElement("button");
        const cleanOptions = options || {};
        const icon = textElement("span", "icon", iconName);
        const labelNode = textElement("span", "", label);
        const selectionPolicy = cleanOptions.selectionPolicy || "single";

        item.type = "button";
        item.className = "workspace-document-file-action-item";
        item.setAttribute("role", "menuitem");
        item.setAttribute("data-document-action-menu-item", action);
        item.setAttribute("data-document-id", doc.document_id || "");
        item.setAttribute("data-document-selection-policy", selectionPolicy);
        item.setAttribute("data-document-single-label", label);
        item.setAttribute("data-document-multiple-label", cleanOptions.multipleLabel || label);
        item.setAttribute("data-document-selection-count", "1");
        item.setAttribute("data-document-selected-ids", doc.document_id || "");
        item.setAttribute("aria-label", `${label} ${doc.original_name || "selected file"}`);

        if (cleanOptions.variant) {
            item.setAttribute("data-document-action-variant", cleanOptions.variant);
        }

        if (cleanOptions.confirmLabel) {
            item.setAttribute("data-document-action-confirm-label", cleanOptions.confirmLabel);
        }

        if (cleanOptions.solomonActionId) {
            item.setAttribute("data-solomon-action-id", cleanOptions.solomonActionId);
        }

        if (cleanOptions.solomonActionFamily) {
            item.setAttribute("data-solomon-action-family", cleanOptions.solomonActionFamily);
        }

        labelNode.setAttribute("data-document-action-label", "");
        icon.setAttribute("aria-hidden", "true");
        item.append(icon, labelNode);

        return item;
    }

    function createDocumentActionMenuSeparator() {
        const separator = document.createElement("span");

        separator.className = "workspace-document-file-action-separator";
        separator.setAttribute("role", "separator");
        separator.setAttribute("aria-hidden", "true");

        return separator;
    }

    function createSolomonActionSubmenu(solomonActionItems) {
        const group = document.createElement("div");
        const trigger = document.createElement("button");
        const sourcePanel = document.createElement("div");
        const icon = textElement("span", "icon", "bolt");
        const label = textElement("span", "", "Actions");
        const chevron = textElement("span", "icon workspace-document-solomon-action-submenu-chevron", "chevron_right");

        group.className = "workspace-document-solomon-action-submenu";
        trigger.type = "button";
        trigger.className = "workspace-document-file-action-item workspace-document-solomon-action-submenu-trigger";
        trigger.setAttribute("role", "menuitem");
        trigger.setAttribute("aria-haspopup", "menu");
        trigger.setAttribute("aria-expanded", "false");
        trigger.setAttribute("data-solomon-action-submenu-trigger", "");
        trigger.setAttribute("data-workspace-listing-action-submenu-trigger", "");
        trigger.setAttribute(
            SOLOMON_ACTION_SUBMENU_IDS_ATTRIBUTE,
            JSON.stringify(
                solomonActionItems
                    .map(function (item) {
                        return item.getAttribute("data-solomon-action-id") || "";
                    })
                    .filter(Boolean)
            )
        );
        trigger.setAttribute("aria-label", "Actions");
        icon.setAttribute("aria-hidden", "true");
        chevron.setAttribute("aria-hidden", "true");

        sourcePanel.className = "workspace-document-file-action-popover workspace-document-solomon-action-submenu-popover";
        sourcePanel.setAttribute("data-solomon-action-submenu-source", "");
        sourcePanel.setAttribute("data-workspace-listing-action-submenu-source", "");
        sourcePanel.setAttribute("role", "menu");
        sourcePanel.setAttribute("aria-label", "Actions");
        sourcePanel.hidden = true;

        solomonActionItems.forEach(function (item) {
            sourcePanel.appendChild(item);
        });

        trigger.append(icon, label, chevron);
        group.append(trigger, sourcePanel);
        return group;
    }

    function createSolomonActionMenuItem(doc, action) {
        const cleanAction = action && typeof action === "object" ? action : {};

        return createDocumentActionMenuItem(
            doc,
            cleanAction.command,
            cleanAction.icon,
            cleanAction.label,
            {
                selectionPolicy: cleanAction.selection_policy || "single",
                solomonActionId: cleanAction.action_id,
                solomonActionFamily: cleanAction.family
            }
        );
    }

    function appendActiveDocumentActions(popover, rawDoc, normalizedDoc) {
        const doc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(rawDoc || {});
        const availableSurfaceActions = getWorkspaceObjectAvailableActions(rawDoc, doc);
        const solomonActions = getWorkspaceObjectSolomonActions(rawDoc, doc);
        const authoritative = Boolean(
            rawDoc?.surface_actions_authoritative === true ||
            doc?.surface_actions_authoritative === true
        );
        const allows = function (actionName) {
            return !authoritative || availableSurfaceActions.has(actionName);
        };
        const primaryActions = [];
        const solomonActionItems = solomonActions.map(function (action) {
            return createSolomonActionMenuItem(doc, action);
        });
        const informationActions = [];
        const lifecycleActions = [];

        if (allows("open")) {
            primaryActions.push(
                createDocumentActionMenuItem(doc, "open", "open_in_new", "Open Reader")
            );
        }

        if (allows("ask_solomon_ai")) {
            primaryActions.push(
                createDocumentActionMenuItem(
                    doc,
                    "ask_solomon_ai",
                    "auto_awesome",
                    "Ask SolomonAI",
                    {
                        selectionPolicy: "multiple",
                        multipleLabel: "Ask SolomonAI about Selected"
                    }
                )
            );
        }

        if (allows("share")) {
            informationActions.push(
                createDocumentActionMenuItem(
                    doc,
                    "share",
                    "person_add",
                    "Share",
                    {
                        selectionPolicy: "multiple",
                        multipleLabel: "Share Selected"
                    }
                )
            );
        }

        if (allows("view_details")) {
            informationActions.push(
                createDocumentActionMenuItem(doc, "details", "info", "Details")
            );
        }

        if (allows("move_to_trash")) {
            lifecycleActions.push(
                createDocumentActionMenuItem(
                    doc,
                    "delete",
                    "delete",
                    "Move to Trash",
                    {
                        selectionPolicy: "multiple",
                        multipleLabel: "Move Selected to Trash"
                    }
                )
            );
        }

        const appendGroup = function (group) {
            if (!group.length) {
                return;
            }

            if (popover.children.length > 0) {
                popover.appendChild(createDocumentActionMenuSeparator());
            }

            group.forEach(function (item) {
                popover.appendChild(item);
            });
        };

        appendGroup(primaryActions);

        if (solomonActionItems.length) {
            if (popover.children.length > 0) {
                popover.appendChild(createDocumentActionMenuSeparator());
            }

            popover.appendChild(createSolomonActionSubmenu(solomonActionItems));
        }

        appendGroup(informationActions);
        appendGroup(lifecycleActions);
    }

    function appendTrashDocumentActions(popover, doc) {
        popover.append(
            createDocumentActionMenuItem(doc, "open", "open_in_new", "Open Reader"),
            createDocumentActionMenuItem(doc, "details", "info", "Details"),
            createDocumentActionMenuSeparator(),
            createDocumentActionMenuItem(
                doc,
                "restore",
                "restore_from_trash",
                "Restore",
                {
                    selectionPolicy: "multiple",
                    multipleLabel: "Restore Selected"
                }
            ),
            createDocumentActionMenuSeparator(),
            createDocumentActionMenuItem(
                doc,
                "permanent_delete",
                "delete_forever",
                "Delete forever",
                {
                    variant: "danger",
                    confirmLabel: "Delete forever",
                    selectionPolicy: "multiple",
                    multipleLabel: "Delete Selected Forever"
                }
            )
        );
    }

    function appendFolderActions(popover, rawDoc, normalizedDoc) {
        const doc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(rawDoc || {});
        const route = resolveWorkspaceFolderRoute(rawDoc, doc);
        const capabilities = getWorkspaceObjectCapabilities(rawDoc, doc);
        const availableActions = getWorkspaceObjectAvailableActions(rawDoc, doc);
        const authoritative = Boolean(
            rawDoc?.surface_actions_authoritative === true ||
            doc?.surface_actions_authoritative === true
        );
        const trashed = isTrashedDocument(rawDoc) || isTrashedDocument(doc);
        const fallbackByAction = {
            open: isWorkspaceObjectOpenEnabled(rawDoc, doc, route),
            view_details: isWorkspaceObjectCapabilityAllowed(
                rawDoc,
                doc,
                "can_view_details",
                true
            ),
            move_to_trash: capabilities.can_move_to_trash === true,
            restore: capabilities.can_restore === true,
            permanent_delete: capabilities.can_permanently_delete === true
        };
        const allows = function (actionName) {
            if (authoritative) {
                return availableActions.has(actionName);
            }

            return availableActions.has(actionName) || fallbackByAction[actionName] === true;
        };
        const primaryActions = [];
        const informationActions = [];
        const lifecycleActions = [];

        if (!trashed && allows("open")) {
            primaryActions.push(
                createDocumentActionMenuItem(
                    doc,
                    "open",
                    "folder_open",
                    "Open"
                )
            );
        }

        if (allows("view_details")) {
            informationActions.push(
                createDocumentActionMenuItem(
                    doc,
                    "details",
                    "info",
                    "Details"
                )
            );
        }

        if (!trashed && allows("move_to_trash")) {
            lifecycleActions.push(
                createDocumentActionMenuItem(
                    doc,
                    "delete",
                    "delete",
                    "Move to Trash"
                )
            );
        }

        if (trashed && allows("restore")) {
            lifecycleActions.push(
                createDocumentActionMenuItem(
                    doc,
                    "restore",
                    "restore_from_trash",
                    "Restore"
                )
            );
        }

        if (trashed && allows("permanent_delete")) {
            lifecycleActions.push(
                createDocumentActionMenuItem(
                    doc,
                    "permanent_delete",
                    "delete_forever",
                    "Delete forever",
                    {
                        variant: "danger",
                        confirmLabel: "Delete forever"
                    }
                )
            );
        }

        [primaryActions, informationActions, lifecycleActions]
            .filter(function (group) {
                return group.length > 0;
            })
            .forEach(function (group, index) {
                if (index > 0) {
                    popover.appendChild(createDocumentActionMenuSeparator());
                }

                group.forEach(function (item) {
                    popover.appendChild(item);
                });
            });
    }

    function createFolderActionMenu(rawDoc, normalizedDoc, actionButton, menuId) {
        const doc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(rawDoc || {});
        const actionMenu = document.createElement("div");
        const popover = document.createElement("div");

        ensureDocumentActionMenuController();

        actionMenu.className = "workspace-document-file-action-menu workspace-document-folder-action-menu";
        actionMenu.setAttribute("data-document-list-cell", "actions");
        actionMenu.setAttribute("data-document-action-menu", "");
        actionMenu.setAttribute("data-document-folder-actions", "available");
        actionMenu.setAttribute(
            "data-document-menu-context",
            isTrashedDocument(rawDoc) || isTrashedDocument(doc) ? "trash" : "active"
        );
        actionMenu.setAttribute("data-document-selection-count", "1");
        actionMenu.setAttribute("data-document-selected-ids", doc.document_id || "");
        actionMenu.setAttribute("data-workspace-folder-id", doc.folder_id || doc.document_id || "");
        popover.id = menuId;
        popover.className = "workspace-document-file-action-popover";
        popover.setAttribute("role", "menu");
        popover.setAttribute(
            "aria-label",
            `Folder actions for ${doc.original_name || "selected folder"}`
        );
        popover.hidden = true;

        appendFolderActions(popover, rawDoc, doc);

        if (!popover.childElementCount) {
            return createFolderActionPlaceholder(rawDoc, doc);
        }

        actionMenu.append(actionButton, popover);

        return actionMenu;
    }


    function createFolderActionPlaceholder(rawDoc, normalizedDoc) {
        const doc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(rawDoc || {});
        const holder = document.createElement("div");
        const objectName = getWorkspaceObjectName(rawDoc, doc);

        holder.className = "workspace-document-file-action-menu workspace-document-folder-action-menu";
        holder.setAttribute("data-document-list-cell", "actions");
        holder.setAttribute("data-document-folder-actions", "unavailable");
        holder.setAttribute("aria-label", `Folder actions for ${objectName} are not available yet`);

        return holder;
    }


    function getDocumentFileExtension(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);
        const candidates = [
            cleanRawDoc.extension,
            cleanRawDoc.file_extension,
            cleanRawDoc.original_name,
            cleanRawDoc.filename,
            cleanRawDoc.name,
            cleanDoc.extension,
            cleanDoc.file_extension,
            cleanDoc.original_name,
            cleanDoc.filename,
            cleanDoc.name
        ];

        for (const candidate of candidates) {
            const value = String(candidate || "").trim().toLowerCase();

            if (!value) {
                continue;
            }

            if (/^\.[a-z0-9]{1,12}$/.test(value)) {
                return value;
            }

            const filename = value.replace(/[?#].*$/, "").split(/[\\/]/).pop() || "";
            const match = filename.match(/\.([a-z0-9]{1,12})$/);

            if (match) {
                return `.${match[1]}`;
            }
        }

        return "";
    }

    function canUseDocumentThumbnailUrl(rawDoc, normalizedDoc) {
        const extension = getDocumentFileExtension(rawDoc, normalizedDoc);

        return [
            ".pdf",
            ".png",
            ".jpg",
            ".jpeg",
            ".webp",
            ".gif",
            ".bmp",
            ".tif",
            ".tiff"
        ].includes(extension);
    }

    function getDocumentThumbnailUrl(rawDoc, normalizedDoc) {
        const cleanRawDoc = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(cleanRawDoc);
        const thumbnailUrl = (
            cleanRawDoc.thumbnail_url ||
            cleanRawDoc.thumbnailUrl ||
            cleanRawDoc.preview_thumbnail_url ||
            cleanRawDoc.previewThumbnailUrl ||
            cleanRawDoc.document_thumbnail_url ||
            cleanRawDoc.workspace_thumbnail_url ||
            cleanRawDoc.preview_image_url ||
            cleanRawDoc.image_preview_url ||
            cleanDoc.thumbnail_url ||
            cleanDoc.thumbnailUrl ||
            cleanDoc.preview_thumbnail_url ||
            cleanDoc.previewThumbnailUrl ||
            cleanDoc.document_thumbnail_url ||
            cleanDoc.workspace_thumbnail_url ||
            cleanDoc.preview_image_url ||
            cleanDoc.image_preview_url ||
            ""
        );

        if (!thumbnailUrl || !canUseDocumentThumbnailUrl(cleanRawDoc, cleanDoc)) {
            return "";
        }

        return String(thumbnailUrl || "").trim();
    }

    function getDocumentThumbnailFallbackKind(rawDoc, normalizedDoc) {
        if (isWorkspaceFolderRecord(rawDoc, normalizedDoc)) {
            return "folder";
        }

        const extension = getDocumentFileExtension(rawDoc, normalizedDoc);

        if (extension === ".doc") {
            return "legacy-word";
        }

        if (extension === ".docx") {
            return "word";
        }

        if (extension === ".pdf") {
            return "pdf";
        }

        if ([".xlsx", ".xls"].includes(extension)) {
            return "spreadsheet";
        }

        if (extension === ".csv") {
            return "table";
        }

        if (extension === ".txt") {
            return "text";
        }

        if ([".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tif", ".tiff"].includes(extension)) {
            return "image";
        }

        return "file";
    }

    function getDocumentThumbnailFallbackPayload(rawDoc, normalizedDoc) {
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(rawDoc || {});
        const kind = getDocumentThumbnailFallbackKind(rawDoc, cleanDoc);
        const extension = getDocumentFileExtension(rawDoc, cleanDoc).replace(".", "").toUpperCase();
        const typeLabel = getWorkspaceObjectTypeLabel(rawDoc, cleanDoc);
        const iconName = getWorkspaceObjectIconName(rawDoc, cleanDoc);

        const payloads = {
            folder: {
                badge: "FOLDER",
                title: "Folder",
                detail: "Workspace folder"
            },
            "legacy-word": {
                badge: "DOC",
                title: "Legacy Word",
                detail: "Preview unavailable"
            },
            word: {
                badge: "DOCX",
                title: "Word Document",
                detail: "Text preview available"
            },
            pdf: {
                badge: "PDF",
                title: "PDF Document",
                detail: "Preview pending"
            },
            spreadsheet: {
                badge: extension || "XLS",
                title: "Spreadsheet",
                detail: "Workbook stored"
            },
            table: {
                badge: "CSV",
                title: "CSV File",
                detail: "Table stored"
            },
            text: {
                badge: "TXT",
                title: "Text File",
                detail: "Text stored"
            },
            image: {
                badge: extension || "IMG",
                title: "Image File",
                detail: "Image stored"
            },
            file: {
                badge: extension || "FILE",
                title: typeLabel,
                detail: "File stored"
            }
        };

        return {
            kind,
            iconName,
            typeLabel,
            ...(payloads[kind] || payloads.file)
        };
    }

    function getDocumentThumbnailState(rawDoc, normalizedDoc) {
        if (isWorkspaceFolderRecord(rawDoc, normalizedDoc)) {
            return "folder";
        }

        return getDocumentThumbnailUrl(rawDoc, normalizedDoc) ? "ready" : "fallback";
    }

    function appendFallbackPreviewLines(fileShape) {
        const lineStack = document.createElement("span");

        lineStack.className = "workspace-document-file-thumbnail-lines";
        lineStack.setAttribute("aria-hidden", "true");

        for (let index = 0; index < 4; index += 1) {
            const line = document.createElement("span");

            line.className = "workspace-document-file-thumbnail-line";
            lineStack.appendChild(line);
        }

        fileShape.appendChild(lineStack);
    }

    function renderDocumentThumbnailFallback(thumbnail, rawDoc, normalizedDoc) {
        if (!thumbnail) {
            return;
        }

        clearNode(thumbnail);
        thumbnail.setAttribute("data-document-thumbnail-state", "fallback");
        thumbnail.closest(DOCUMENT_ROW_SELECTOR)?.setAttribute(
            "data-document-thumbnail-state",
            "fallback"
        );
        thumbnail.setAttribute(
            "aria-label",
            `${getWorkspaceObjectTypeLabel(rawDoc, normalizedDoc)} placeholder`
        );
        thumbnail.appendChild(
            createDocumentThumbnailFallback(rawDoc, normalizedDoc)
        );
    }

    function createDocumentThumbnail(rawDoc, normalizedDoc) {
        const doc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(rawDoc || {});
        const thumbnail = document.createElement("figure");
        const thumbnailUrl = getDocumentThumbnailUrl(rawDoc, doc);
        const typeLabel = getWorkspaceObjectTypeLabel(rawDoc, doc);
        const fallbackKind = getDocumentThumbnailFallbackKind(rawDoc, doc);
        const isFolder = isWorkspaceFolderRecord(rawDoc, doc);

        thumbnail.className = "workspace-document-file-thumbnail";
        thumbnail.classList.toggle("workspace-document-file-thumbnail--folder", isFolder);
        thumbnail.setAttribute("data-document-list-cell", "thumbnail");
        thumbnail.setAttribute("data-document-thumbnail", "");
        thumbnail.setAttribute("data-document-thumbnail-state", getDocumentThumbnailState(rawDoc, doc));
        thumbnail.setAttribute("data-document-thumbnail-type", typeLabel);
        thumbnail.setAttribute("data-document-thumbnail-fallback-kind", fallbackKind);
        thumbnail.setAttribute("aria-label", thumbnailUrl ? `${typeLabel} preview` : `${typeLabel} placeholder`);

        if (thumbnailUrl) {
            const image = document.createElement("img");

            image.className = "workspace-document-file-thumbnail-image";
            image.alt = "";
            image.loading = "lazy";
            image.decoding = "async";
            image.draggable = false;
            image.addEventListener("error", function () {
                renderDocumentThumbnailFallback(thumbnail, rawDoc, doc);
            }, { once: true });
            image.src = thumbnailUrl;
            thumbnail.appendChild(image);
        } else {
            renderDocumentThumbnailFallback(thumbnail, rawDoc, doc);
        }

        return thumbnail;
    }

    function createDocumentThumbnailFallback(rawDoc, normalizedDoc) {
        const payload = getDocumentThumbnailFallbackPayload(rawDoc, normalizedDoc);
        const wrapper = document.createElement("span");
        const fileShape = document.createElement("span");
        const icon = textElement("span", "icon workspace-document-file-thumbnail-icon", payload.iconName);
        const corner = document.createElement("span");
        const badge = textElement("span", "workspace-document-file-thumbnail-badge", payload.badge);
        const copy = document.createElement("span");
        const title = textElement("strong", "", payload.title);
        const detail = textElement("span", "", payload.detail);

        wrapper.className = "workspace-document-file-thumbnail-fallback";
        wrapper.setAttribute("data-document-thumbnail-fallback", payload.kind);

        fileShape.className = "workspace-document-file-thumbnail-file";
        icon.setAttribute("aria-hidden", "true");

        corner.className = "workspace-document-file-thumbnail-corner";
        corner.setAttribute("aria-hidden", "true");

        copy.className = "workspace-document-file-thumbnail-copy";
        copy.append(title, detail);

        fileShape.append(icon, corner, badge);
        appendFallbackPreviewLines(fileShape);
        wrapper.append(fileShape, copy);

        return wrapper;
    }

    function getDocumentSortProjection(list) {
        const explorer = (
            list?.closest("[data-document-explorer]") ||
            list?.closest("[data-document-browser]") ||
            null
        );
        const content = (
            list?.closest("[data-document-file-content]") ||
            explorer?.querySelector("[data-document-file-content]") ||
            null
        );
        const control = (
            explorer?.querySelector(DOCUMENT_SORT_CONTROL_SELECTOR) ||
            content?.querySelector(DOCUMENT_SORT_CONTROL_SELECTOR) ||
            null
        );
        const host = control?.querySelector(DOCUMENT_SORT_TRIGGER_HOST_SELECTOR) || null;
        const trigger = (
            control?.querySelector(DOCUMENT_SORT_TRIGGER_SELECTOR) ||
            explorer?.querySelector(DOCUMENT_SORT_TRIGGER_SELECTOR) ||
            content?.querySelector(DOCUMENT_SORT_TRIGGER_SELECTOR) ||
            null
        );
        const menu = control?.querySelector(DOCUMENT_SORT_MENU_SELECTOR) || null;

        return { explorer, content, control, host, trigger, menu };
    }

    function stageDocumentSortTrigger(list) {
        const projection = getDocumentSortProjection(list);

        if (
            projection.host instanceof HTMLElement &&
            projection.trigger instanceof HTMLButtonElement &&
            !projection.host.contains(projection.trigger)
        ) {
            projection.trigger.classList.remove(
                "workspace-document-file-list-sort-menu-trigger"
            );
            projection.trigger.classList.add(
                "workspace-document-content-sort-trigger"
            );
            projection.host.appendChild(projection.trigger);
        }

        return projection;
    }

    function createFileListSortControlCell(sortTrigger) {
        const cell = document.createElement("th");
        const content = document.createElement("span");
        const icon = textElement(
            "span",
            "icon workspace-document-sort-button-icon",
            "sort"
        );
        const label = textElement(
            "span",
            "workspace-document-sort-button-label",
            "Sort"
        );
        const triggerId = String(sortTrigger?.id || "workspaceDocumentSortTrigger").trim();
        const controlsId = String(
            sortTrigger?.getAttribute("aria-controls") ||
            "workspaceDocumentSortMenu"
        ).trim();

        cell.className = [
            "workspace-document-file-list-header-cell",
            "workspace-document-file-list-header-cell--actions",
            "workspace-document-file-list-header-cell--sort-control"
        ].join(" ");
        cell.id = `${triggerId}HeaderCell`;
        cell.setAttribute("data-document-list-header-cell", "actions");
        cell.setAttribute("data-document-sort-cell-trigger", "");
        cell.setAttribute("scope", "col");
        cell.setAttribute("tabindex", "0");
        cell.setAttribute("aria-label", "Sort files and folders");
        cell.setAttribute("aria-haspopup", "menu");
        cell.setAttribute("aria-expanded", "false");

        if (controlsId) {
            cell.setAttribute("aria-controls", controlsId);
        }

        if (sortTrigger instanceof HTMLButtonElement) {
            const ariaLabel = String(sortTrigger.getAttribute("aria-label") || "").trim();
            const title = String(sortTrigger.getAttribute("title") || "").trim();

            sortTrigger.classList.remove(
                "workspace-document-file-list-sort-menu-trigger"
            );
            sortTrigger.classList.add(
                "workspace-document-content-sort-trigger"
            );

            if (ariaLabel) {
                cell.setAttribute("aria-label", ariaLabel);
            }

            if (title) {
                cell.setAttribute("title", title);
            }
        }

        content.className = "workspace-document-file-list-sort-cell-content";
        icon.setAttribute("aria-hidden", "true");
        content.append(icon, label);
        cell.appendChild(content);

        return cell;
    }

    function createFileListHeaderCell(modifier, label, options) {
        const cell = document.createElement("th");
        const sortKey = String(options?.sortKey || "").trim().toLowerCase();

        cell.className = `workspace-document-file-list-header-cell workspace-document-file-list-header-cell--${modifier}`;
        cell.setAttribute("data-document-list-header-cell", modifier);
        cell.setAttribute("scope", "col");

        if (!label || !sortKey) {
            cell.classList.add("workspace-document-file-list-header-cell--static");
            cell.setAttribute("aria-label", label || "Actions");
            cell.textContent = label;
            return cell;
        }

        const button = document.createElement("button");
        const labelElement = document.createElement("span");
        const directionIcon = document.createElement("span");

        cell.setAttribute("aria-sort", "none");

        button.type = "button";
        button.className = "workspace-document-file-list-sort-button";
        button.setAttribute("data-document-column-sort-key", sortKey);
        button.setAttribute("data-document-column-sort-label", label);
        button.setAttribute("aria-pressed", "false");
        button.setAttribute("aria-label", `Sort by ${label}`);

        labelElement.className = "workspace-document-file-list-sort-label";
        labelElement.textContent = label;

        directionIcon.className = "icon workspace-document-file-list-sort-icon";
        directionIcon.setAttribute("data-document-column-sort-icon", "");
        directionIcon.setAttribute("aria-hidden", "true");
        directionIcon.textContent = "arrow_downward";
        directionIcon.hidden = true;

        button.append(labelElement, directionIcon);
        cell.append(button);

        return cell;
    }

    function renderFileListHeader(section, sortTrigger, sortAuthority) {
        const header = document.createElement("tr");
        const cleanSection = String(section || "files").trim().toLowerCase();
        const authorizedSortKeys = new Set(
            Array.isArray(sortAuthority?.allowedKeys)
                ? sortAuthority.allowedKeys
                : []
        );

        header.className = "workspace-document-file-list-header";
        header.setAttribute("data-document-list-header", "");
        header.setAttribute("data-document-list-header-section", cleanSection);

        if (cleanSection === "recent") {
            const recentHeaderCell = function (modifier, label, sortKey) {
                return createFileListHeaderCell(
                    modifier,
                    label,
                    authorizedSortKeys.has(sortKey)
                        ? { sortKey }
                        : undefined
                );
            };

            header.classList.add("workspace-document-file-list-header--recent");
            header.append(
                recentHeaderCell("name", "Name", "name"),
                recentHeaderCell("activity", "Activity", "activity"),
                recentHeaderCell("owner", "Owner", "owner"),
                recentHeaderCell("location", "Location", "location"),
                recentHeaderCell("size", "File size", "size"),
                createFileListHeaderCell("actions-available", "Actions Available"),
                authorizedSortKeys.size
                    ? createFileListSortControlCell(sortTrigger)
                    : createFileListHeaderCell("actions", "")
            );
            return header;
        }

        header.append(
            createFileListHeaderCell("name", "Name", { sortKey: "name" }),
            createFileListHeaderCell("type", "Type", { sortKey: "type" }),
            createFileListHeaderCell("size", "Size", { sortKey: "size" }),
            createFileListHeaderCell("uploaded", "Modified", { sortKey: "uploaded" }),
            createFileListHeaderCell("actions-available", "Actions Available"),
            createFileListSortControlCell(sortTrigger)
        );

        return header;
    }

    function createFileTableColumn(modifier) {
        const column = document.createElement("col");

        column.className = `workspace-document-file-table-column workspace-document-file-table-column--${modifier}`;
        column.setAttribute("data-document-table-column", modifier);
        return column;
    }

    function createFileTable(section, sortTrigger, sortAuthority) {
        const cleanSection = String(section || "files").trim().toLowerCase();
        const region = document.createElement("div");
        const table = document.createElement("table");
        const caption = document.createElement("caption");
        const columnGroup = document.createElement("colgroup");
        const head = document.createElement("thead");
        const body = document.createElement("tbody");
        const columns = cleanSection === "recent"
            ? ["name", "activity", "owner", "location", "size", "actions-available", "actions"]
            : ["name", "type", "size", "uploaded", "actions-available", "actions"];

        region.className = "workspace-document-table-region";
        region.setAttribute("data-document-table-region", "");
        region.setAttribute("tabindex", "-1");

        table.className = "workspace-document-file-table";
        table.setAttribute("data-document-file-table", "");
        table.setAttribute("data-document-table-section", cleanSection);

        caption.className = "workspace-document-table-caption";
        caption.textContent = cleanSection === "recent"
            ? "Recent files and folders"
            : "Files and folders";

        columns.forEach(function (modifier) {
            columnGroup.appendChild(createFileTableColumn(modifier));
        });

        head.className = "workspace-document-file-table-head";
        head.setAttribute("data-document-table-head", "");
        head.appendChild(renderFileListHeader(
            cleanSection,
            sortTrigger,
            sortAuthority
        ));

        body.className = "workspace-document-file-table-body";
        body.setAttribute("data-document-table-body", "");

        table.append(caption, columnGroup, head, body);
        region.appendChild(table);

        return { region, table, body };
    }

    function createDocumentTableCell(modifier, content) {
        const cell = document.createElement("td");

        cell.className = `workspace-document-table-cell workspace-document-table-cell--${modifier}`;
        cell.setAttribute("data-document-list-cell", modifier);

        if (Array.isArray(content)) {
            cell.append(...content);
        } else if (content) {
            cell.appendChild(content);
        }

        return cell;
    }

    function createSolomonActionsAvailableContent(rawDoc, normalizedDoc) {
        const cleanDoc = normalizedDoc && typeof normalizedDoc === "object"
            ? normalizedDoc
            : Records.normalizeDocument(rawDoc || {});
        const isFolder = isWorkspaceFolderRecord(rawDoc, cleanDoc);
        const count = isFolder
            ? null
            : getWorkspaceObjectSolomonActionCount(rawDoc, cleanDoc);
        const content = textElement(
            "span",
            "workspace-document-actions-available-count",
            isFolder ? "—" : String(count)
        );

        content.classList.toggle("is-zero", count === 0);
        content.classList.toggle("is-folder", isFolder);
        content.setAttribute(
            "aria-label",
            isFolder
                ? "Actions Available does not apply to this folder"
                : `${count} ${count === 1 ? "Action" : "Actions"} available`
        );

        return content;
    }

    function formatRecentActivityDate(value) {
        const cleanValue = String(value || "").trim();

        if (!cleanValue) {
            return "";
        }

        const parsed = new Date(cleanValue);

        if (Number.isNaN(parsed.getTime())) {
            return cleanValue;
        }

        const now = new Date();
        const options = {
            month: "short",
            day: "numeric"
        };

        if (parsed.getFullYear() !== now.getFullYear()) {
            options.year = "numeric";
        }

        return new Intl.DateTimeFormat(undefined, options).format(parsed);
    }


    function createRecentGroupHeading(label) {
        const heading = textElement(
            "h3",
            "workspace-document-recent-group-heading",
            label || "Earlier"
        );

        heading.setAttribute("data-document-recent-group-heading", "");
        return heading;
    }

    function syncRecentGroupPresentation(items) {
        if (!items) {
            return;
        }

        const itemCount = items.childElementCount;
        const columnCount = Math.max(1, Math.min(itemCount, 4));

        items.setAttribute("data-document-recent-item-count", String(itemCount));
        items.setAttribute("data-document-recent-columns", String(columnCount));
    }

    function createRecentGroupSection(label) {
        const cleanLabel = String(label || "Earlier").trim() || "Earlier";
        const section = document.createElement("section");
        const items = document.createElement("div");

        section.className = "workspace-document-recent-group";
        section.setAttribute("data-document-recent-group-section", cleanLabel);
        section.setAttribute("role", "group");
        section.setAttribute("aria-label", cleanLabel);

        items.className = "workspace-document-recent-group-items";
        items.setAttribute("data-document-recent-group-items", cleanLabel);
        items.setAttribute("data-document-recent-item-count", "0");
        items.setAttribute("data-document-recent-columns", "1");
        items.setAttribute("role", "presentation");

        section.append(
            createRecentGroupHeading(cleanLabel),
            items
        );

        return { section, items };
    }

    function renderFileRow(rawDoc, options) {
        const cleanOptions = options || {};
        const section = String(cleanOptions.section || "files").trim().toLowerCase();
        const layout = String(cleanOptions.layout || "list").trim().toLowerCase();
        const isListLayout = layout === "list";
        const isRecent = section === "recent";
        const normalizedDoc = Records.normalizeDocument(rawDoc);
        const isFolder = isWorkspaceFolderRecord(rawDoc, normalizedDoc);
        const workspaceObjectId = getWorkspaceObjectId(rawDoc, normalizedDoc);
        const rowDoc = Object.assign({}, normalizedDoc, {
            document_id: workspaceObjectId,
            random_name: isFolder ? workspaceObjectId : (normalizedDoc.random_name || workspaceObjectId),
            original_name: getWorkspaceObjectName(rawDoc, normalizedDoc),
            type_label: getWorkspaceObjectTypeLabel(rawDoc, normalizedDoc),
            selected_for_workflow: isFolder ? false : normalizedDoc.selected_for_workflow
        });
        const row = document.createElement(isListLayout ? "tr" : "article");
        const identity = document.createElement("div");
        const documentName = rowDoc.original_name || (isFolder ? "Untitled Folder" : "Untitled Document");
        const objectRoute = resolveWorkspaceObjectOpenRoute(rawDoc, rowDoc);
        const canOpenObject = isWorkspaceObjectOpenEnabled(rawDoc, rowDoc, objectRoute);
        const fileSize = isFolder ? "Folder" : Records.formatFileSize(rowDoc.size_bytes);
        const uploadedLabel = Records.getDocumentUploadedLabel(rowDoc);
        const trashed = isTrashedDocument(rawDoc);
        const typeMeta = textElement("span", "workspace-document-file-meta workspace-document-file-meta--type", rowDoc.type_label || "Workspace File");
        const sizeMeta = textElement("span", "workspace-document-file-meta workspace-document-file-meta--size", fileSize);
        const uploadedMeta = textElement("span", "workspace-document-file-meta workspace-document-file-meta--uploaded", uploadedLabel);
        const recentActivityValue = (
            rowDoc.recent_activity_at_utc ||
            rowDoc.recent_activity_at ||
            rowDoc.updated_at ||
            rowDoc.uploaded_at
        );
        const recentActivityDetailedLabel = Records.formatDateTime(
            recentActivityValue
        ) || uploadedLabel;
        const recentActivityLabel = formatRecentActivityDate(
            recentActivityValue
        ) || recentActivityDetailedLabel;
        const recentActivityReason = rowDoc.recent_activity_reason || "Uploaded";
        const activityMeta = document.createElement("span");
        const activityDate = textElement(
            "strong",
            "workspace-document-recent-activity-date",
            recentActivityLabel
        );
        const activityReason = textElement(
            "small",
            "workspace-document-recent-activity-reason",
            recentActivityReason
        );
        const ownerMeta = document.createElement("span");
        const ownerIcon = textElement(
            "span",
            "icon workspace-document-recent-owner-icon",
            "account_circle"
        );
        const ownerLabel = textElement(
            "span",
            "workspace-document-recent-owner-label",
            rowDoc.owner_label || "Me"
        );
        const locationMeta = document.createElement("span");
        const locationIcon = textElement(
            "span",
            "icon workspace-document-recent-location-icon",
            "folder"
        );
        const locationLabel = textElement(
            "span",
            "workspace-document-recent-location-label",
            rowDoc.location_label || "Location unavailable"
        );

        activityMeta.className = "workspace-document-file-meta workspace-document-file-meta--activity";
        activityMeta.setAttribute("aria-label", `${recentActivityDetailedLabel}; ${recentActivityReason}`);
        activityMeta.append(activityDate, activityReason);

        ownerMeta.className = "workspace-document-file-meta workspace-document-file-meta--owner";
        ownerIcon.setAttribute("aria-hidden", "true");
        ownerMeta.append(ownerIcon, ownerLabel);

        locationMeta.className = "workspace-document-file-meta workspace-document-file-meta--location";
        locationIcon.setAttribute("aria-hidden", "true");
        locationMeta.append(locationIcon, locationLabel);

        const thumbnailUrl = getDocumentThumbnailUrl(rawDoc, rowDoc);
        const thumbnailState = getDocumentThumbnailState(rawDoc, rowDoc);
        const thumbnailFallbackKind = getDocumentThumbnailFallbackKind(rawDoc, rowDoc);
        const objectKind = isFolder ? "folder" : "file";
        const objectCapabilities = getWorkspaceObjectCapabilities(rawDoc, rowDoc);
        const solomonActionCount = isFolder
            ? 0
            : getWorkspaceObjectSolomonActionCount(rawDoc, rowDoc);
        const canMoveObject = !isFolder && objectCapabilities.can_move === true && !trashed;
        const canShareObject = !isFolder && objectCapabilities.can_share === true && !trashed;
        const canAcceptMovedFiles = (
            isFolder &&
            section === "files" &&
            objectCapabilities.can_create_child_folder === true &&
            !trashed
        );

        ensureDocumentSelectionController();

        row.className = isFolder
            ? "workspace-document-file workspace-document-folder"
            : "workspace-document-file";
        row.classList.toggle("workspace-document-file--recent", isRecent);
        row.classList.toggle("workspace-document-file--table-row", isListLayout);
        row.classList.toggle("workspace-document-file--grid-card", !isListLayout);
        row.setAttribute("data-document-row-section", section);
        row.setAttribute("role", isListLayout ? "row" : "option");
        row.setAttribute("tabindex", "0");
        row.setAttribute("aria-selected", "false");
        row.setAttribute("data-document-list-row", "");
        row.setAttribute("data-document-keyboard-row", "true");
        row.setAttribute("data-document-id", rowDoc.document_id);
        row.setAttribute("data-random-name", rowDoc.random_name || rowDoc.document_id);
        row.setAttribute("data-document-active", rowDoc.selected_for_workflow ? "true" : "false");
        row.setAttribute("data-document-selected", "false");
        row.setAttribute("data-document-selected-for-workflow", rowDoc.selected_for_workflow ? "true" : "false");
        row.setAttribute("data-document-trashed", trashed ? "true" : "false");
        row.setAttribute("data-document-type-label", rowDoc.type_label);
        row.setAttribute("data-document-size", String(rowDoc.size_bytes || ""));
        row.setAttribute("data-document-uploaded-label", uploadedLabel);
        row.setAttribute("data-document-status-label", isFolder ? "Folder" : (trashed ? "Trash" : Records.getDocumentWorkflowLabel(rowDoc)));
        row.setAttribute("data-document-action-context", trashed ? "trash" : "active");
        row.setAttribute("data-solomon-action-count", String(solomonActionCount));
        row.setAttribute("data-document-thumbnail-state", thumbnailState);
        row.setAttribute("data-document-thumbnail-url", thumbnailUrl);
        row.setAttribute("data-document-thumbnail-fallback-kind", thumbnailFallbackKind);
        row.setAttribute("data-document-folder", isFolder ? "true" : "false");
        row.setAttribute("data-document-can-move", canMoveObject ? "true" : "false");
        row.setAttribute("data-document-can-share", canShareObject ? "true" : "false");
        row.setAttribute("data-document-drag-source", canMoveObject ? "move" : "none");
        row.setAttribute("draggable", canMoveObject ? "true" : "false");

        if (isRecent) {
            row.setAttribute("data-document-recent-group", rowDoc.recent_group_label || "Earlier");
            row.setAttribute("data-document-recent-activity-kind", rowDoc.recent_activity_kind || "uploaded");
            row.setAttribute("data-document-recent-owner", rowDoc.owner_label || "Me");
            row.setAttribute("data-document-recent-location", rowDoc.location_label || "Location unavailable");
        }

        row.setAttribute("data-workspace-object-kind", objectKind);
        row.setAttribute("aria-label", isFolder
            ? `${documentName}; Folder; updated ${uploadedLabel}`
            : isRecent
                ? `${documentName}; ${recentActivityDetailedLabel}; ${recentActivityReason}; ${rowDoc.owner_label || "Me"}; ${fileSize}; ${rowDoc.location_label || "Location unavailable"}`
                : `${documentName}; ${rowDoc.type_label}; ${fileSize}; uploaded ${uploadedLabel}; ${solomonActionCount} ${solomonActionCount === 1 ? "Action" : "Actions"} available`);

        if (isFolder) {
            row.setAttribute("data-workspace-folder-contract", "workspace_folder_v1");
            row.setAttribute("data-workspace-folder-id", workspaceObjectId);
            row.setAttribute("data-folder-id", workspaceObjectId);
            row.setAttribute("data-document-open-enabled", canOpenObject ? "true" : "false");
            row.setAttribute("data-workspace-folder-open-enabled", canOpenObject ? "true" : "false");
            row.setAttribute("data-workspace-object-folder-visibility-only", "true");
            row.setAttribute("data-workspace-object-file-authority-inherited", "false");
            row.setAttribute("data-workspace-object-allow-ai-query", "false");
            row.setAttribute(
                "data-document-drop-folder-target",
                canAcceptMovedFiles ? "true" : "false"
            );
            if (canAcceptMovedFiles) {
                row.setAttribute("data-document-drop-label", documentName);
            }
        }

        applySharedListingRowContract(row, rawDoc, rowDoc, trashed);

        identity.className = "workspace-document-file-identity";
        identity.setAttribute("title", documentName);
        identity.append(textElement("strong", "", documentName));

        if (isRecent) {
            identity.append(
                textElement(
                    "span",
                    "workspace-document-file-secondary workspace-document-file-secondary--size",
                    fileSize
                )
            );
        }

        const fileIcon = textElement("span", "icon workspace-document-file-icon", getWorkspaceObjectIconName(rawDoc, rowDoc));

        if (isFolder && isListLayout) {
            fileIcon.classList.add("workspace-document-folder-glyph");
        }

        const selectionControl = createDocumentSelectionControl(rowDoc, {
            objectName: documentName,
            objectLabel: objectKind
        });
        const actionMenu = createDocumentActionMenu(rawDoc);

        fileIcon.setAttribute("aria-hidden", "true");

        if (isListLayout) {
            const nameCellContent = document.createElement("div");

            nameCellContent.className = "workspace-document-table-name";
            nameCellContent.append(selectionControl, fileIcon, identity);

            row.appendChild(createDocumentTableCell("name", nameCellContent));

            if (isRecent) {
                row.append(
                    createDocumentTableCell("activity", activityMeta),
                    createDocumentTableCell("owner", ownerMeta),
                    createDocumentTableCell("location", locationMeta),
                    createDocumentTableCell("size", sizeMeta)
                );
            } else {
                row.append(
                    createDocumentTableCell("type", typeMeta),
                    createDocumentTableCell("size", sizeMeta),
                    createDocumentTableCell("uploaded", uploadedMeta)
                );
            }

            row.appendChild(
                createDocumentTableCell(
                    "actions-available",
                    createSolomonActionsAvailableContent(rawDoc, rowDoc)
                )
            );
            row.appendChild(createDocumentTableCell("actions", actionMenu));
            return row;
        }

        identity.setAttribute("data-document-list-cell", "name");
        typeMeta.setAttribute("data-document-list-cell", "type");
        sizeMeta.setAttribute("data-document-list-cell", "size");
        uploadedMeta.setAttribute("data-document-list-cell", "uploaded");
        activityMeta.setAttribute("data-document-list-cell", "activity");
        ownerMeta.setAttribute("data-document-list-cell", "owner");
        locationMeta.setAttribute("data-document-list-cell", "location");
        fileIcon.setAttribute("data-document-list-cell", "icon");

        row.append(
            selectionControl,
            createDocumentThumbnail(rawDoc, rowDoc),
            fileIcon,
            identity
        );

        if (isRecent) {
            row.append(activityMeta, ownerMeta, locationMeta, sizeMeta);
        } else {
            row.append(typeMeta, sizeMeta, uploadedMeta);
        }

        row.appendChild(actionMenu);
        return row;
    }

    function getRenderEmptyCollection(list, options) {
        const cleanOptions = options || {};

        if (cleanOptions.collection) {
            return cleanOptions.collection;
        }

        if (cleanOptions.trashMode) {
            return "trash";
        }

        return list?.getAttribute("data-document-empty-collection") || "all";
    }

    function getActiveDocumentLayout(list) {
        const layoutRoot = (
            list?.closest("[data-document-explorer]") ||
            list?.closest("[data-document-browser]") ||
            list
        );
        const cleanLayout = String(
            list?.getAttribute("data-document-layout") ||
            layoutRoot?.getAttribute("data-document-layout") ||
            layoutRoot?.querySelector("[data-document-layout-option].is-active")?.getAttribute("data-document-layout-option") ||
            ""
        ).trim().toLowerCase();

        if (cleanLayout === "grid" || cleanLayout === "cards" || cleanLayout === "card") {
            return "grid";
        }

        return "list";
    }

    function renderFiles(list, docs, options) {
        const cleanOptions = options || {};
        const safeDocs = Array.isArray(docs) ? docs : [];
        const emptyCollection = getRenderEmptyCollection(list, cleanOptions);
        const section = String(
            cleanOptions.section ||
            cleanOptions.collection ||
            list?.getAttribute("data-document-list-section") ||
            "files"
        ).trim().toLowerCase();
        const layout = getActiveDocumentLayout(list);
        const sortAuthority = cleanOptions.sortAuthority && typeof cleanOptions.sortAuthority === "object"
            ? cleanOptions.sortAuthority
            : null;
        const recentSortAvailable = (
            section === "recent" &&
            Array.isArray(sortAuthority?.allowedKeys) &&
            sortAuthority.allowedKeys.length > 0
        );
        const groupRecentByActivity = (
            section === "recent" &&
            (!sortAuthority || String(sortAuthority.key || "activity").trim().toLowerCase() === "activity")
        );

        if (!list) {
            return;
        }

        const sortProjection = stageDocumentSortTrigger(list);
        const sortAvailable = safeDocs.length > 0 && (section !== "recent" || recentSortAvailable);

        if (sortProjection.control instanceof HTMLElement) {
            sortProjection.control.hidden = !sortAvailable;
            sortProjection.control.setAttribute(
                "aria-hidden",
                sortAvailable ? "false" : "true"
            );
            if (!sortAvailable) {
                sortProjection.control.setAttribute("data-document-sort-open", "false");
            }
        }

        if (!sortAvailable) {
            if (sortProjection.menu instanceof HTMLElement) {
                sortProjection.menu.hidden = true;
            }
            if (sortProjection.trigger instanceof HTMLButtonElement) {
                sortProjection.trigger.setAttribute("aria-expanded", "false");
            }
        }

        clearNode(list);
        syncLibraryDropSurface(list, emptyCollection);
        applySharedListingSurfaceContract(list, emptyCollection);
        ensureSharedListingBridgeController();
        list.removeAttribute("data-document-empty-collection");
        list.setAttribute("data-document-empty-state", safeDocs.length ? "hidden" : "visible");
        list.setAttribute("data-document-list-presentation", layout === "list" ? "table" : "grid");

        if (section === "recent") {
            list.setAttribute(
                "data-document-recent-grouping",
                groupRecentByActivity ? "activity" : "none"
            );
        } else {
            list.removeAttribute("data-document-recent-grouping");
        }

        if (!safeDocs.length) {
            renderEmptyFiles(list, emptyCollection);
            initializeSharedListingControls(list);
            return;
        }

        if (layout === "list") {
            const table = createFileTable(
                section,
                sortProjection.trigger,
                sortAuthority
            );

            safeDocs.forEach(function (doc) {
                table.body.appendChild(renderFileRow(doc, {
                    section,
                    layout: "list"
                }));
            });

            list.appendChild(table.region);
            initializeSharedListingControls(list);
            return;
        }

        let currentRecentGroup = "";
        let currentRecentGroupItems = null;
        const recentGroupItems = [];

        safeDocs.forEach(function (doc) {
            const normalizedDoc = Records.normalizeDocument(doc);

            if (groupRecentByActivity) {
                const groupLabel = normalizedDoc.recent_group_label || "Earlier";

                if (groupLabel !== currentRecentGroup || !currentRecentGroupItems) {
                    const group = createRecentGroupSection(groupLabel);

                    list.appendChild(group.section);
                    recentGroupItems.push(group.items);
                    currentRecentGroup = groupLabel;
                    currentRecentGroupItems = group.items;
                }

                currentRecentGroupItems.appendChild(
                    renderFileRow(doc, { section, layout: "grid" })
                );
                return;
            }

            list.appendChild(renderFileRow(doc, { section, layout: "grid" }));
        });

        recentGroupItems.forEach(syncRecentGroupPresentation);
        initializeSharedListingControls(list);
    }

    function getDocumentFromRow(explorer, row) {
        if (!row) {
            return null;
        }

        const documentId = row.getAttribute("data-document-id") || "";
        const isFolder = row.getAttribute("data-document-folder") === "true";
        const storedDoc = explorer.__solomonDocumentById?.get(documentId);

        if (storedDoc) {
            const normalizedStoredDoc = Records.normalizeDocument(storedDoc);
            const folderId = (
                storedDoc.folder_id ||
                storedDoc.workspace_item_id ||
                documentId
            );

            normalizedStoredDoc.trashed = isTrashedDocument(storedDoc);
            normalizedStoredDoc.document_status = normalizedStoredDoc.trashed ? "trash" : "active";
            normalizedStoredDoc.library_selected = row.getAttribute("data-document-selected") === "true";

            if (isFolder || isWorkspaceFolderRecord(storedDoc, normalizedStoredDoc)) {
                normalizedStoredDoc.folder = true;
                normalizedStoredDoc.is_folder = true;
                normalizedStoredDoc.folder_id = folderId;
                normalizedStoredDoc.workspace_item_id = folderId;
                normalizedStoredDoc.workspace_item_type = "folder";
                normalizedStoredDoc.document_id = folderId;
                normalizedStoredDoc.random_name = folderId;
                normalizedStoredDoc.original_name = getWorkspaceObjectName(storedDoc, normalizedStoredDoc);
                normalizedStoredDoc.type_label = "Folder";
                normalizedStoredDoc.reader_url = "";
                normalizedStoredDoc.workspace_reader_url = "";
                normalizedStoredDoc.open_url = (
                    resolveWorkspaceFolderRoute(storedDoc, normalizedStoredDoc) ||
                    row.getAttribute("data-document-open-route") ||
                    row.getAttribute("data-workspace-object-open-route") ||
                    ""
                );
            }

            return normalizedStoredDoc;
        }

        return Records.normalizeDocument({
            document_id: documentId,
            random_name: row.getAttribute("data-random-name") || documentId,
            original_name: row.querySelector("strong")?.textContent || documentId,
            active: row.getAttribute("data-document-active") === "true",
            selected_for_workflow: row.getAttribute("data-document-selected-for-workflow") === "true",
            library_selected: row.getAttribute("data-document-selected") === "true",
            trashed: row.getAttribute("data-document-trashed") === "true",
            document_status: row.getAttribute("data-document-trashed") === "true" ? "trash" : "active",
            type_label: row.getAttribute("data-document-type-label") || (isFolder ? "Folder" : "Workspace File"),
            size_bytes: row.getAttribute("data-document-size") || "",
            thumbnail_url: row.getAttribute("data-document-thumbnail-url") || "",
            folder: isFolder,
            is_folder: isFolder,
            folder_id: isFolder ? (row.getAttribute("data-workspace-folder-id") || documentId) : "",
            workspace_item_id: isFolder ? (row.getAttribute("data-workspace-folder-id") || documentId) : "",
            workspace_item_type: isFolder ? "folder" : "file",
            open_url: isFolder
                ? (
                    row.getAttribute("data-document-open-route") ||
                    row.getAttribute("data-workspace-object-open-route") ||
                    ""
                )
                : row.getAttribute("data-document-route") || "",
            reader_url: isFolder ? "" : row.getAttribute("data-document-reader-url") || row.getAttribute("data-document-route") || "",
            workspace_reader_url: isFolder ? "" : row.getAttribute("data-document-reader-url") || row.getAttribute("data-document-route") || ""
        });
    }

    function getRecentFilterElements(control) {
        if (!(control instanceof HTMLElement)) {
            return {};
        }

        return {
            select: control.querySelector(RECENT_FILTER_SELECT_SELECTOR),
            trigger: control.querySelector(RECENT_FILTER_TRIGGER_SELECTOR),
            label: control.querySelector(RECENT_FILTER_LABEL_SELECTOR),
            menu: control.querySelector(RECENT_FILTER_MENU_SELECTOR)
        };
    }

    function getRecentFilterOptionButtons(menu) {
        if (!(menu instanceof HTMLElement)) {
            return [];
        }

        return Array.from(menu.querySelectorAll(RECENT_FILTER_OPTION_SELECTOR)).filter(function (option) {
            return option instanceof HTMLButtonElement && !option.disabled;
        });
    }

    function getSelectedRecentFilterOption(select) {
        if (!(select instanceof HTMLSelectElement)) {
            return null;
        }

        return select.options[select.selectedIndex] || select.options[0] || null;
    }

    function createRecentFilterOptionButton(option, selectedValue, optionIndex) {
        const button = document.createElement("button");
        const label = document.createElement("span");
        const check = document.createElement("span");
        const cleanValue = String(option?.value || "");
        const cleanLabel = String(option?.textContent || option?.label || "").trim() || "Option";

        button.type = "button";
        button.className = "workspace-document-recent-filter-option";
        button.setAttribute("data-document-recent-filter-option", cleanValue);
        button.setAttribute("data-document-recent-filter-option-index", String(optionIndex));
        button.setAttribute("role", "option");
        button.setAttribute("aria-selected", cleanValue === selectedValue ? "true" : "false");
        button.disabled = Boolean(option?.disabled);

        label.textContent = cleanLabel;

        check.className = "icon workspace-document-recent-filter-option-check";
        check.setAttribute("aria-hidden", "true");
        check.textContent = "check";

        button.append(label, check);
        return button;
    }

    function syncRecentFilterControl(control) {
        const { select, trigger, label, menu } = getRecentFilterElements(control);

        if (
            !(select instanceof HTMLSelectElement) ||
            !(trigger instanceof HTMLButtonElement) ||
            !(label instanceof HTMLElement) ||
            !(menu instanceof HTMLElement)
        ) {
            return;
        }

        const selectedOption = getSelectedRecentFilterOption(select);
        const selectedValue = String(select.value || "");
        const selectedLabel = String(selectedOption?.textContent || selectedOption?.label || "").trim();
        const fallbackLabel = String(
            control.getAttribute("data-document-recent-filter-control") || "Filter"
        );

        label.textContent = selectedLabel || fallbackLabel.charAt(0).toUpperCase() + fallbackLabel.slice(1);
        trigger.disabled = select.disabled;
        control.setAttribute(
            "data-document-recent-filter-active",
            selectedValue ? "true" : "false"
        );
        const activeState = selectedValue ? "true" : "false";

        if (select.getAttribute("data-document-recent-filter-active") !== activeState) {
            select.setAttribute("data-document-recent-filter-active", activeState);
        }

        menu.replaceChildren(
            ...Array.from(select.options).map(function (option, optionIndex) {
                return createRecentFilterOptionButton(option, selectedValue, optionIndex);
            })
        );
    }

    function closeRecentFilterMenu(control, options) {
        const cleanControl = control instanceof HTMLElement ? control : activeRecentFilterControl;
        const restoreFocus = Boolean(options?.restoreFocus);

        if (!(cleanControl instanceof HTMLElement)) {
            return;
        }

        const { trigger, menu } = getRecentFilterElements(cleanControl);

        if (menu instanceof HTMLElement) {
            menu.hidden = true;
        }

        if (trigger instanceof HTMLButtonElement) {
            trigger.setAttribute("aria-expanded", "false");

            if (restoreFocus) {
                trigger.focus({ preventScroll: true });
            }
        }

        cleanControl.setAttribute("data-document-recent-filter-open", "false");

        if (activeRecentFilterControl === cleanControl) {
            activeRecentFilterControl = null;
        }
    }

    function focusRecentFilterOption(control, edge) {
        const { select, menu } = getRecentFilterElements(control);
        const options = getRecentFilterOptionButtons(menu);

        if (!options.length) {
            return;
        }

        let target = null;

        if (edge === "first") {
            target = options[0];
        } else if (edge === "last") {
            target = options[options.length - 1];
        } else {
            const selectedValue = select instanceof HTMLSelectElement ? String(select.value || "") : "";
            target = options.find(function (option) {
                return option.getAttribute("data-document-recent-filter-option") === selectedValue;
            }) || options[0];
        }

        target.focus({ preventScroll: true });
        target.scrollIntoView({ block: "nearest" });
    }

    function openRecentFilterMenu(control, focusEdge) {
        const { trigger, menu } = getRecentFilterElements(control);

        if (
            !(trigger instanceof HTMLButtonElement) ||
            !(menu instanceof HTMLElement) ||
            trigger.disabled
        ) {
            return;
        }

        if (activeRecentFilterControl && activeRecentFilterControl !== control) {
            closeRecentFilterMenu(activeRecentFilterControl);
        }

        syncRecentFilterControl(control);
        menu.hidden = false;
        trigger.setAttribute("aria-expanded", "true");
        control.setAttribute("data-document-recent-filter-open", "true");
        activeRecentFilterControl = control;

        window.requestAnimationFrame(function () {
            focusRecentFilterOption(control, focusEdge || "selected");
        });
    }

    function selectRecentFilterOption(control, optionButton) {
        const { select } = getRecentFilterElements(control);

        if (
            !(select instanceof HTMLSelectElement) ||
            !(optionButton instanceof HTMLButtonElement) ||
            optionButton.disabled
        ) {
            return;
        }

        const nextValue = String(optionButton.getAttribute("data-document-recent-filter-option") || "");
        const valueChanged = select.value !== nextValue;

        select.value = nextValue;
        syncRecentFilterControl(control);
        closeRecentFilterMenu(control, { restoreFocus: true });

        if (valueChanged) {
            select.dispatchEvent(new Event("input", { bubbles: true }));
            select.dispatchEvent(new Event("change", { bubbles: true }));
        }
    }

    function moveRecentFilterOptionFocus(menu, direction) {
        const options = getRecentFilterOptionButtons(menu);
        const currentIndex = options.indexOf(document.activeElement);

        if (!options.length) {
            return;
        }

        let nextIndex = 0;

        if (direction === "first") {
            nextIndex = 0;
        } else if (direction === "last") {
            nextIndex = options.length - 1;
        } else if (direction === "previous") {
            nextIndex = currentIndex <= 0 ? options.length - 1 : currentIndex - 1;
        } else {
            nextIndex = currentIndex < 0 || currentIndex >= options.length - 1 ? 0 : currentIndex + 1;
        }

        options[nextIndex].focus({ preventScroll: true });
        options[nextIndex].scrollIntoView({ block: "nearest" });
    }

    function initializeRecentFilterControl(control) {
        if (
            !(control instanceof HTMLElement) ||
            control.getAttribute("data-document-recent-filter-ready") === "true"
        ) {
            return;
        }

        const { select, trigger, menu } = getRecentFilterElements(control);

        if (
            !(select instanceof HTMLSelectElement) ||
            !(trigger instanceof HTMLButtonElement) ||
            !(menu instanceof HTMLElement)
        ) {
            return;
        }

        control.setAttribute("data-document-recent-filter-ready", "true");
        control.setAttribute("data-document-recent-filter-open", "false");
        syncRecentFilterControl(control);

        trigger.addEventListener("click", function () {
            if (activeRecentFilterControl === control && !menu.hidden) {
                closeRecentFilterMenu(control);
                return;
            }

            openRecentFilterMenu(control, "selected");
        });

        trigger.addEventListener("keydown", function (event) {
            if (!["ArrowDown", "ArrowUp", "Home", "End", "Enter", " "].includes(event.key)) {
                return;
            }

            event.preventDefault();

            if (event.key === "ArrowUp" || event.key === "End") {
                openRecentFilterMenu(control, "last");
            } else {
                openRecentFilterMenu(control, "first");
            }
        });

        menu.addEventListener("click", function (event) {
            const target = event.target instanceof Element ? event.target : null;
            const option = target?.closest(RECENT_FILTER_OPTION_SELECTOR);

            if (option instanceof HTMLButtonElement) {
                selectRecentFilterOption(control, option);
            }
        });

        menu.addEventListener("keydown", function (event) {
            if (event.key === "ArrowDown") {
                event.preventDefault();
                moveRecentFilterOptionFocus(menu, "next");
            } else if (event.key === "ArrowUp") {
                event.preventDefault();
                moveRecentFilterOptionFocus(menu, "previous");
            } else if (event.key === "Home") {
                event.preventDefault();
                moveRecentFilterOptionFocus(menu, "first");
            } else if (event.key === "End") {
                event.preventDefault();
                moveRecentFilterOptionFocus(menu, "last");
            } else if (event.key === "Escape") {
                event.preventDefault();
                closeRecentFilterMenu(control, { restoreFocus: true });
            } else if (event.key === "Enter" || event.key === " ") {
                const target = event.target instanceof Element ? event.target : null;
                const option = target?.closest(RECENT_FILTER_OPTION_SELECTOR);

                if (option instanceof HTMLButtonElement) {
                    event.preventDefault();
                    selectRecentFilterOption(control, option);
                }
            } else if (event.key === "Tab") {
                closeRecentFilterMenu(control);
            }
        });

        select.addEventListener("change", function () {
            syncRecentFilterControl(control);
        });

        select.addEventListener("input", function () {
            syncRecentFilterControl(control);
        });

        const observer = new MutationObserver(function () {
            syncRecentFilterControl(control);
        });

        observer.observe(select, {
            attributeFilter: ["disabled", "label", "selected", "value"],
            attributes: true,
            childList: true,
            subtree: true
        });
    }

    function initializeRecentFilterMenus(root) {
        const cleanRoot = root instanceof Document || root instanceof HTMLElement ? root : document;

        if (activeRecentFilterControl && !activeRecentFilterControl.isConnected) {
            activeRecentFilterControl = null;
        }

        cleanRoot.querySelectorAll(RECENT_FILTER_CONTROL_SELECTOR).forEach(initializeRecentFilterControl);

        if (recentFilterMenuControllerReady) {
            return;
        }

        recentFilterMenuControllerReady = true;

        document.addEventListener(WORKSPACE_LOADED_EVENT, function (event) {
            const mount = event?.detail?.mount;
            initializeRecentFilterMenus(mount instanceof HTMLElement ? mount : document);
        });

        document.addEventListener("pointerdown", function (event) {
            if (
                activeRecentFilterControl &&
                !activeRecentFilterControl.contains(event.target)
            ) {
                closeRecentFilterMenu(activeRecentFilterControl);
            }
        });

        document.addEventListener("keydown", function (event) {
            if (event.key === "Escape" && activeRecentFilterControl) {
                closeRecentFilterMenu(activeRecentFilterControl, { restoreFocus: true });
            }
        });

        document.addEventListener("reset", function (event) {
            if (!(event.target instanceof HTMLFormElement)) {
                return;
            }

            window.setTimeout(function () {
                event.target.querySelectorAll(RECENT_FILTER_CONTROL_SELECTOR).forEach(syncRecentFilterControl);
            }, 0);
        }, true);
    }

    ensureDocumentActionMenuController();
    ensureDocumentSelectionController();

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            initializeRecentFilterMenus(document);
        }, { once: true });
    } else {
        initializeRecentFilterMenus(document);
    }

    window[API_NAME] = Object.freeze({
        clearNode,
        textElement,
        renderMetadataGrid,
        updateCollectionCounts,
        getActiveCollection,
        getFilteredDocuments,
        isWorkspaceFolderRecord,
        getWorkspaceObjectId,
        getWorkspaceObjectName,
        isTrashedDocument,
        getDocumentRows,
        getSelectedDocumentRows,
        getSelectedDocumentIds,
        clearDocumentSelection,
        renderEmptyFiles,
        createDocumentActionMenu,
        resolveDocumentReaderRoute,
        resolveWorkspaceFolderRoute,
        resolveWorkspaceObjectOpenRoute,
        getDocumentThumbnailUrl,
        getDocumentThumbnailFallbackKind,
        createDocumentThumbnail,
        renderFileListHeader,
        renderFileRow,
        renderFiles,
        getDocumentFromRow,
        initializeRecentFilterMenus
    });
})();