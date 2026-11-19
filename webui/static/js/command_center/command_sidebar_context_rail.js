/* -------------------------------------------------------------------
   FILE: command_sidebar_context_rail.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "NationsCommandSidebar";
    const api = window[API_NAME] = window[API_NAME] || {};

    if (api.__contextRailLoaded) {
        return;
    }

    api.__contextRailLoaded = true;

    const COLLAPSED = "collapsed";
    const STANDARD = "standard";
    const DOCUMENT_SELECTION_CHANGE_EVENT = "solomon:documents-selection-change";
    const DOCUMENT_INSPECTOR_OPEN_EVENT = "solomon:document-inspector-open";
    const DOCUMENT_INSPECTOR_CLOSE_EVENT = "solomon:document-inspector-close";
    const DOCUMENT_INSPECTOR_SOURCE_CHANGE_EVENT = "solomon:document-inspector-source-change";
    const DOCUMENT_INSPECTOR_CLEAR_EVENT = "solomon:document-inspector-clear";
    const WORKSPACE_LOADED_EVENT = "solomon:workspace-loaded";
    const DOCUMENT_AI_CONVERSATIONS_ENDPOINT = "/workspace/document-operation/ai";
    const SOLOMON_WORKSPACE_URL = "/ai";
    const DOCUMENTS_MODULE_ID = "documents";
    const SOLOMON_AI_MODULE_ID = "solomon_ai";
    const PEOPLE_MODULE_ID = "people";
    const SEARCH_MODULE_ID = "search";
    const DETAILS_METADATA_CONTRACT = "workspace_document_metadata_v1";
    const DETAILS_OPEN_SELECTION_INTENTS = Object.freeze(["details_command"]);
    const SUMMARY_OPEN_SELECTION_INTENTS = Object.freeze(["summary_command"]);
    const INSPECTOR_VIEW_DETAILS = "details";
    const INSPECTOR_VIEW_SUMMARY = "summary";
    const INSPECTOR_VIEW_ACTION = "action";
    const RESULT_FORMAT_PLAIN_TEXT_V1 = "plain_text_v1";
    const RESULT_FORMAT_SOLOMON_MARKDOWN_V1 = "solomon_markdown_v1";
    const STRUCTURED_LIST_RESULT_TYPES = Object.freeze([
        "bullet_list",
        "dated_items",
        "action_items"
    ]);
    const PERSISTENT_INSPECTOR_VIEWS = Object.freeze([
        INSPECTOR_VIEW_SUMMARY,
        INSPECTOR_VIEW_ACTION
    ]);
    const DOCUMENT_SUMMARY_FULL_OPEN_EVENT = "solomon:document-summary-open-full";

    const DETAILS_UNAVAILABLE = Object.freeze({
        size: "Size unavailable",
        date: "Date unavailable",
        location: "Location unavailable"
    });

    const selectors = {
        root: "#portal-root",
        layout: ".command-center-layout",
        layer: "[data-command-content-layer]",
        rail: "[data-document-inspector-rail]",
        toggle: "[data-solomon-rail-toggle]",
        close: "[data-document-inspector-close]",
        empty: "[data-document-inspector-empty]",
        selection: "[data-document-inspector-selection]",
        fileIcon: "[data-document-inspector-file-icon]",
        fileName: "[data-document-inspector-file-name]",
        fileMeta: "[data-document-inspector-file-meta]",
        title: "[data-document-inspector-title]",
        detailsPanel: "[data-document-inspector-panel=\"details\"]",
        summaryPanel: "[data-document-inspector-panel=\"summary\"]",
        summaryCopy: "[data-document-inspector-summary-copy]",
        summaryStatus: "[data-document-inspector-summary-status]",
        summaryGenerated: "[data-document-inspector-summary-generated]",
        actionPanel: "[data-document-inspector-panel=\"action\"]",
        actionStatus: "[data-document-inspector-action-status]",
        actionCopy: "[data-document-inspector-action-copy]",
        actionGenerated: "[data-document-inspector-action-generated]",
        actionProgress: "[data-document-inspector-action-progress]",
        property: "[data-document-inspector-property]",
        footer: "[data-document-inspector-footer]",
        askSolomon: "[data-document-inspector-ask-solomon]",
        viewFullSummary: "[data-document-inspector-view-full-summary]",
        askSolomonMark: ".workspace-document-inspector-rail__solomon-mark",
        askSolomonMarkImage: ".workspace-document-inspector-rail__solomon-mark-image",
        explorer: "[data-document-explorer]",
        selectedRows: [
            ".workspace-document-file[data-document-id].is-selected",
            ".workspace-document-file[data-document-id][data-document-selected='true']",
            ".workspace-document-file[data-document-id][aria-selected='true']"
        ].join(", ")
    };

    const documentCache = new Map();
    let activeDocuments = [];
    let activeInspectorView = INSPECTOR_VIEW_DETAILS;
    let activeSummaryState = null;
    let activeActionState = null;
    let sessionRequestInFlight = false;
    let contextRailEventControllerReady = false;

    function cleanValue(value) {
        return String(value || "").trim();
    }

    function normalizeActionName(value) {
        return cleanValue(value)
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "_")
            .replace(/^_+|_+$/g, "");
    }

    // Right Context Rail Persistence Contract v1:
    // - ordinary selection churn never displaces Summary/Action presentations;
    // - clearing selection never collapses an already-open rail;
    // - explicit Details/Summary commands may replace the current presentation;
    // - only explicit rail close or authoritative invalidation should collapse it.
    function isPersistentInspectorPresentation() {
        return Boolean(
            activeDocuments.length &&
            PERSISTENT_INSPECTOR_VIEWS.includes(activeInspectorView)
        );
    }

    function isExplicitInspectorReplacementIntent(selectionIntent) {
        return Boolean(
            DETAILS_OPEN_SELECTION_INTENTS.includes(selectionIntent) ||
            SUMMARY_OPEN_SELECTION_INTENTS.includes(selectionIntent)
        );
    }

    function shouldPreserveInspectorPresentation(selectionIntent) {
        return Boolean(
            isPersistentInspectorPresentation() &&
            !isExplicitInspectorReplacementIntent(selectionIntent)
        );
    }

    function isUnavailableValue(value) {
        const cleanText = cleanValue(value).toLowerCase();

        return Boolean(
            !cleanText ||
            cleanText === "not available" ||
            cleanText === "unavailable" ||
            cleanText === "size unavailable" ||
            cleanText === "date unavailable" ||
            cleanText === "location unavailable" ||
            cleanText === "unknown" ||
            cleanText === "null" ||
            cleanText === "undefined" ||
            cleanText === "—" ||
            cleanText === "-"
        );
    }

    function firstAvailableText() {
        for (const value of arguments) {
            const cleanText = cleanValue(value);

            if (!isUnavailableValue(cleanText)) {
                return cleanText;
            }
        }

        return "";
    }

    function firstNumericValue() {
        for (const value of arguments) {
            if (value === null || value === undefined || value === "") {
                continue;
            }

            const numberValue = Number(value);

            if (Number.isFinite(numberValue) && numberValue >= 0) {
                return numberValue;
            }
        }

        return null;
    }

    function isNumericText(value) {
        const cleanText = cleanValue(value);

        return Boolean(cleanText && /^-?\d+(\.\d+)?$/.test(cleanText));
    }

    function getEventElement(event) {
        const target = event?.target;

        if (target instanceof Element) {
            return target;
        }

        return target?.parentElement || null;
    }

    function getClosestFromEvent(event, selector) {
        const target = getEventElement(event);

        return target?.closest?.(selector) || null;
    }

    function isRailOwnedElement(rail, element) {
        return Boolean(
            rail &&
            element &&
            (
                element === rail ||
                rail.contains(element)
            )
        );
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

    function getRightPaneModuleForRoute(route, fallbackModuleId) {
        const parsedUrl = getSameOriginUrl(route);
        const fallback = cleanValue(fallbackModuleId).toLowerCase();

        if (!parsedUrl) {
            return fallback || DOCUMENTS_MODULE_ID;
        }

        if (parsedUrl.pathname === SOLOMON_WORKSPACE_URL || parsedUrl.pathname.startsWith(`${SOLOMON_WORKSPACE_URL}/`)) {
            return SOLOMON_AI_MODULE_ID;
        }

        if (parsedUrl.pathname === "/people" || parsedUrl.pathname.startsWith("/people/")) {
            return PEOPLE_MODULE_ID;
        }

        if (parsedUrl.pathname === "/search") {
            return SEARCH_MODULE_ID;
        }

        return fallback || DOCUMENTS_MODULE_ID;
    }

    function fallbackToRoute(route) {
        const parsedUrl = getSameOriginUrl(route);
        const targetRoute = getRelativeUrl(parsedUrl) || cleanValue(route);

        if (!targetRoute) {
            return false;
        }

        window.location.assign(targetRoute);
        return false;
    }

    async function loadRightPaneRoute(route, moduleId, options) {
        const parsedUrl = getSameOriginUrl(route);
        const cleanRoute = getRelativeUrl(parsedUrl);
        const loadOptions = Object.assign(
            {
                push: true,
                async: true,
                launchMode: "context_rail_navigation",
                source: "command_sidebar_context_rail"
            },
            options || {}
        );

        if (!cleanRoute) {
            return fallbackToRoute(route);
        }

        if (typeof api.loadWorkspace !== "function") {
            return fallbackToRoute(cleanRoute);
        }

        try {
            const result = await api.loadWorkspace(
                cleanRoute,
                getRightPaneModuleForRoute(cleanRoute, moduleId),
                loadOptions
            );

            if (result === false) {
                return fallbackToRoute(cleanRoute);
            }

            return true;
        } catch (error) {
            console.warn(
                "[CONTEXT_RAIL] Async right-pane navigation failed; falling back to hard navigation.",
                error
            );
            return fallbackToRoute(cleanRoute);
        }
    }

    function navigateToSolomonWorkspace(options) {
        return loadRightPaneRoute(
            options?.url || SOLOMON_WORKSPACE_URL,
            SOLOMON_AI_MODULE_ID,
            Object.assign(
                {
                    launchMode: "solomon_ai_context_rail",
                    source: "command_sidebar_context_rail"
                },
                options || {}
            )
        );
    }

    function uniqueValues(values) {
        return Array.from(new Set((values || []).map(cleanValue).filter(Boolean)));
    }

    function getRecordsApi() {
        return window.SolomonWorkspaceDocumentRecords || null;
    }

    function getMetadataSource(doc) {
        if (!doc || typeof doc !== "object") {
            return {};
        }

        if (doc.metadata && typeof doc.metadata === "object") {
            return doc.metadata;
        }

        if (doc.document_metadata && typeof doc.document_metadata === "object") {
            return doc.document_metadata;
        }

        if (doc.workspace_metadata && typeof doc.workspace_metadata === "object") {
            return doc.workspace_metadata;
        }

        return {};
    }

    function normalizeDateLabel(value) {
        const cleanText = cleanValue(value);

        if (!cleanText) {
            return "";
        }

        const parsedDate = new Date(cleanText);

        if (Number.isNaN(parsedDate.getTime())) {
            return cleanText;
        }

        return parsedDate.toLocaleString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit"
        });
    }

    function readElementAttribute(element, attributeNames) {
        if (!element) {
            return "";
        }

        for (const attributeName of attributeNames || []) {
            const value = cleanValue(element.getAttribute(attributeName));

            if (value) {
                return value;
            }
        }

        return "";
    }

    function readRowCellText(row, names) {
        if (!row) {
            return "";
        }

        for (const name of names || []) {
            const cell = row.querySelector(
                [
                    `[data-document-cell="${name}"]`,
                    `[data-document-column="${name}"]`,
                    `[data-workspace-cell="${name}"]`,
                    `[data-workspace-column="${name}"]`,
                    `[data-document-list-cell="${name}"]`,
                    `.workspace-document-file__${name}`,
                    `.workspace-document-file-${name}`
                ].join(", ")
            );
            const text = cleanValue(cell?.textContent);

            if (text) {
                return text;
            }
        }

        return "";
    }

    function readRowMetadata(row) {
        const payload = {};
        const metadata = {};
        const documentId = readElementAttribute(
            row,
            [
                "data-document-id",
                "data-workspace-object-id",
                "data-file-id"
            ]
        );
        const documentName = (
            readElementAttribute(
                row,
                [
                    "data-document-name",
                    "data-workspace-object-name",
                    "data-original-name"
                ]
            ) ||
            cleanValue(row?.querySelector("strong")?.textContent)
        );
        const typeLabel = firstAvailableText(
            readElementAttribute(
                row,
                [
                    "data-document-type-label",
                    "data-workspace-object-type-label",
                    "data-type-label"
                ]
            ),
            readRowCellText(row, ["type"])
        );
        const rawSizeValue = readElementAttribute(
            row,
            [
                "data-document-size-bytes",
                "data-size-bytes",
                "data-workspace-object-size-bytes",
                "data-document-size"
            ]
        );
        const sizeLabel = firstAvailableText(
            readElementAttribute(
                row,
                [
                    "data-document-size-label",
                    "data-size-label",
                    "data-workspace-object-size-label"
                ]
            ),
            !isNumericText(rawSizeValue) ? rawSizeValue : "",
            readRowCellText(row, ["size"])
        );
        const sizeBytes = firstNumericValue(
            readElementAttribute(
                row,
                [
                    "data-document-size-bytes",
                    "data-size-bytes",
                    "data-workspace-object-size-bytes"
                ]
            ),
            isNumericText(rawSizeValue) ? rawSizeValue : ""
        );
        const uploadedAt = firstAvailableText(
            readElementAttribute(
                row,
                [
                    "data-document-uploaded-at",
                    "data-uploaded-at",
                    "data-workspace-object-uploaded-at"
                ]
            )
        );
        const uploadedLabel = firstAvailableText(
            readElementAttribute(
                row,
                [
                    "data-document-uploaded-label",
                    "data-uploaded-label",
                    "data-workspace-object-uploaded-label"
                ]
            ),
            readRowCellText(row, ["uploaded", "date"])
        );
        const locationLabel = firstAvailableText(
            readElementAttribute(
                row,
                [
                    "data-document-location-label",
                    "data-location-label",
                    "data-workspace-object-location-label"
                ]
            ),
            readRowCellText(row, ["location"])
        );
        const storageStatus = firstAvailableText(
            readElementAttribute(
                row,
                [
                    "data-document-storage-status",
                    "data-document-status",
                    "data-workspace-object-status",
                    "data-status"
                ]
            )
        );
        const storageStatusLabel = firstAvailableText(
            readElementAttribute(
                row,
                [
                    "data-document-storage-status-label",
                    "data-document-status-label",
                    "data-workspace-object-status-label",
                    "data-status-label"
                ]
            )
        );
        const trashed = (
            row?.getAttribute("data-document-trashed") === "true" ||
            ["trash", "trashed", "deleted"].includes(storageStatus.toLowerCase())
        );

        metadata.contract = readElementAttribute(
            row,
            [
                "data-document-metadata-contract",
                "data-workspace-metadata-contract"
            ]
        ) || DETAILS_METADATA_CONTRACT;

        if (documentId) {
            payload.document_id = documentId;
            payload.random_name = documentId;
        }

        if (documentName) {
            payload.original_name = documentName;
            payload.filename = documentName;
        }

        if (typeLabel) {
            payload.type_label = typeLabel;
            metadata.type_label = typeLabel;
        }

        if (sizeBytes !== null) {
            payload.size_bytes = sizeBytes;
            metadata.size_bytes = sizeBytes;
        }

        if (sizeLabel) {
            payload.size_label = sizeLabel;
            metadata.size_label = sizeLabel;
        }

        if (uploadedAt) {
            payload.uploaded_at = uploadedAt;
            metadata.uploaded_at = uploadedAt;
        }

        if (uploadedLabel) {
            payload.uploaded_label = uploadedLabel;
            metadata.uploaded_label = uploadedLabel;
        }

        if (locationLabel) {
            payload.location_label = locationLabel;
            metadata.location_label = locationLabel;
        }

        if (storageStatus) {
            payload.storage_status = storageStatus;
            payload.document_status = storageStatus;
            metadata.status_token = storageStatus;
        }

        if (storageStatusLabel) {
            payload.storage_status_label = storageStatusLabel;
            payload.status_label = storageStatusLabel;
            metadata.status_label = storageStatusLabel;
        }

        if (trashed) {
            payload.trashed = true;
            payload.document_status = "trash";
            payload.storage_status = "trash";
            metadata.status_token = "trash";
        }

        payload.metadata = metadata;
        payload.metadata_contract = metadata.contract;

        return payload;
    }

    function getSelectedRowForDocumentId(explorer, documentId) {
        const cleanDocumentId = cleanValue(documentId);

        if (!explorer || !cleanDocumentId) {
            return null;
        }

        return Array.from(explorer.querySelectorAll(selectors.selectedRows)).find(
            function (row) {
                return cleanValue(row.getAttribute("data-document-id")) === cleanDocumentId;
            }
        ) || null;
    }

    function mergeDocumentWithRow(doc, row) {
        const source = doc && typeof doc === "object" ? doc : {};
        const rowPayload = readRowMetadata(row);
        const sourceMetadata = getMetadataSource(source);
        const rowMetadata = rowPayload.metadata || {};
        const merged = Object.assign({}, source, rowPayload);

        merged.metadata = Object.assign({}, sourceMetadata, rowMetadata);
        merged.metadata_contract = merged.metadata.contract || DETAILS_METADATA_CONTRACT;

        return merged;
    }

    function mergeDocumentWithSelectedRow(explorer, doc) {
        const documentId = getDocumentId(doc);
        const row = getSelectedRowForDocumentId(explorer, documentId);

        return row ? mergeDocumentWithRow(doc, row) : doc;
    }

    function getElements() {
        const rail = document.querySelector(selectors.rail);
        const askSolomon = rail?.querySelector(selectors.askSolomon) || null;

        return {
            root: document.querySelector(selectors.root),
            layout: document.querySelector(selectors.layout),
            layer: document.querySelector(selectors.layer),
            rail,
            toggles: Array.from(document.querySelectorAll(selectors.toggle)),
            closes: rail ? Array.from(rail.querySelectorAll(selectors.close)) : [],
            empty: rail?.querySelector(selectors.empty) || null,
            selection: rail?.querySelector(selectors.selection) || null,
            fileIcon: rail?.querySelector(selectors.fileIcon) || null,
            fileName: rail?.querySelector(selectors.fileName) || null,
            fileMeta: rail?.querySelector(selectors.fileMeta) || null,
            title: rail?.querySelector(selectors.title) || null,
            detailsPanel: rail?.querySelector(selectors.detailsPanel) || null,
            summaryPanel: rail?.querySelector(selectors.summaryPanel) || null,
            summaryCopy: rail?.querySelector(selectors.summaryCopy) || null,
            summaryStatus: rail?.querySelector(selectors.summaryStatus) || null,
            summaryGenerated: rail?.querySelector(selectors.summaryGenerated) || null,
            actionPanel: rail?.querySelector(selectors.actionPanel) || null,
            actionStatus: rail?.querySelector(selectors.actionStatus) || null,
            actionCopy: rail?.querySelector(selectors.actionCopy) || null,
            actionGenerated: rail?.querySelector(selectors.actionGenerated) || null,
            actionProgress: rail?.querySelector(selectors.actionProgress) || null,
            footer: rail?.querySelector(selectors.footer) || null,
            askSolomon,
            viewFullSummary: rail?.querySelector(selectors.viewFullSummary) || null,
            askSolomonMark: askSolomon?.querySelector(selectors.askSolomonMark) || null,
            askSolomonMarkImage: askSolomon?.querySelector(selectors.askSolomonMarkImage) || null
        };
    }

    function getDocumentId(doc) {
        return cleanValue(
            doc?.document_id ||
            doc?.documentId ||
            doc?.random_name ||
            doc?.file_id ||
            doc?.id
        );
    }

    function getDocumentName(doc) {
        const metadata = getMetadataSource(doc);

        return cleanValue(
            doc?.original_name ||
            doc?.filename ||
            doc?.name ||
            doc?.display_name ||
            doc?.displayName ||
            metadata.display_name ||
            metadata.name ||
            getDocumentId(doc)
        ) || "Selected file";
    }

    function getDocumentType(doc) {
        const metadata = getMetadataSource(doc);

        return firstAvailableText(
            metadata.type_label,
            metadata.file_type_label,
            doc?.type_label,
            doc?.file_type_label,
            doc?.kind,
            doc?.mime_type,
            doc?.extension
        ) || "Workspace File";
    }

    function isTrashedDocument(doc) {
        const metadata = getMetadataSource(doc);
        const status = cleanValue(
            metadata.status_token ||
            metadata.status ||
            doc?.document_status ||
            doc?.library_status ||
            doc?.storage_status ||
            doc?.status
        ).toLowerCase();

        return Boolean(
            doc?.trashed === true ||
            doc?.isTrash === true ||
            doc?.trashed_at ||
            ["trash", "trashed", "deleted"].includes(status)
        );
    }

    function normalizeDocument(rawDoc) {
        const source = rawDoc && typeof rawDoc === "object" ? rawDoc : {};
        const initialDocumentId = getDocumentId(source);

        if (!initialDocumentId) {
            return null;
        }

        const Records = getRecordsApi();
        const cached = documentCache.get(initialDocumentId) || {};
        const mergedSource = Object.assign({}, cached, source);
        const recordsDoc = Records && typeof Records.normalizeDocument === "function"
            ? Records.normalizeDocument(mergedSource)
            : {};
        const normalizedSource = Object.assign({}, mergedSource, recordsDoc || {});
        const documentId = getDocumentId(normalizedSource);

        if (!documentId) {
            return null;
        }

        const normalized = Object.assign({}, normalizedSource, {
            document_id: documentId,
            original_name: getDocumentName(normalizedSource),
            type_label: getDocumentType(normalizedSource)
        });

        if (!normalized.metadata || typeof normalized.metadata !== "object") {
            normalized.metadata = Object.assign({}, getMetadataSource(normalizedSource));
        }

        normalized.metadata.contract = normalized.metadata.contract || DETAILS_METADATA_CONTRACT;
        normalized.metadata_contract = normalized.metadata.contract;

        documentCache.set(documentId, normalized);

        return normalized;
    }

    function normalizeDocuments(documents) {
        const seen = new Set();

        return (Array.isArray(documents) ? documents : [])
            .map(normalizeDocument)
            .filter(function (doc) {
                if (!doc || seen.has(doc.document_id)) {
                    return false;
                }

                seen.add(doc.document_id);
                return true;
            });
    }

    function resolveDocumentsByIds(explorer, documentIds) {
        return uniqueValues(documentIds)
            .map(function (documentId) {
                const sourceDoc = (
                    explorer?.__solomonDocumentById?.get(documentId) ||
                    documentCache.get(documentId) ||
                    { document_id: documentId }
                );

                return mergeDocumentWithSelectedRow(explorer, sourceDoc);
            });
    }

    function getDocumentsFromSelectedRows(explorer) {
        return Array.from(explorer?.querySelectorAll(selectors.selectedRows) || [])
            .map(function (row) {
                const documentId = cleanValue(row.getAttribute("data-document-id"));
                const storedDoc = (
                    explorer?.__solomonDocumentById?.get(documentId) ||
                    documentCache.get(documentId) ||
                    { document_id: documentId }
                );

                return mergeDocumentWithRow(storedDoc, row);
            });
    }

    function getInspectorContext() {
        const files = activeDocuments.slice();
        const documentIds = uniqueValues(files.map(getDocumentId));

        return {
            mode: files.length > 1 ? "selection" : files.length ? "file" : "workspace",
            files,
            document_ids: documentIds,
            documentIds,
            selectedCount: files.length,
            hasSelection: files.length > 0
        };
    }

    function dispatchInspectorEvent(eventName, detail) {
        document.dispatchEvent(
            new CustomEvent(eventName, {
                detail: Object.assign(
                    {
                        source: "command_sidebar_context_rail"
                    },
                    getInspectorContext(),
                    detail || {}
                )
            })
        );
    }

    function getDocumentLocation(doc) {
        const metadata = getMetadataSource(doc);
        const explicitLocation = firstAvailableText(
            metadata.location_label,
            metadata.location,
            doc?.location_label,
            doc?.location,
            doc?.parent_folder_name,
            doc?.workspace_location_label
        );

        if (explicitLocation) {
            return explicitLocation;
        }

        if (isTrashedDocument(doc)) {
            return "Trash";
        }

        const section = cleanValue(
            document.querySelector(selectors.explorer)?.getAttribute("data-workspace-section")
        ).toLowerCase();

        if (section === "reports") {
            return "Reports";
        }

        return "My Files";
    }

    function formatFileSize(value) {
        const Records = getRecordsApi();

        if (Records && typeof Records.formatFileSize === "function") {
            return Records.formatFileSize(value);
        }

        const size = Number(value);

        if (!Number.isFinite(size) || size < 0) {
            return DETAILS_UNAVAILABLE.size;
        }

        if (size < 1024) {
            return `${size} B`;
        }

        if (size < 1024 * 1024) {
            return `${(size / 1024).toFixed(1)} KB`;
        }

        return `${(size / (1024 * 1024)).toFixed(1)} MB`;
    }

    function getUploadedLabel(doc) {
        const Records = getRecordsApi();
        const metadata = getMetadataSource(doc);
        const explicitLabel = firstAvailableText(
            metadata.uploaded_label,
            metadata.created_label,
            doc?.uploaded_label,
            doc?.upload_time_label,
            doc?.created_label
        );

        if (explicitLabel) {
            return explicitLabel;
        }

        if (Records && typeof Records.getDocumentUploadedLabel === "function") {
            const recordsLabel = Records.getDocumentUploadedLabel(doc);

            if (!isUnavailableValue(recordsLabel)) {
                return recordsLabel;
            }
        }

        return firstAvailableText(
            normalizeDateLabel(metadata.uploaded_at),
            normalizeDateLabel(metadata.created_at),
            normalizeDateLabel(doc?.uploaded_at),
            normalizeDateLabel(doc?.upload_time),
            normalizeDateLabel(doc?.created_at)
        ) || DETAILS_UNAVAILABLE.date;
    }

    function getDetailsMetadata(doc) {
        const Records = getRecordsApi();
        const sourceDoc = doc && typeof doc === "object" ? doc : {};
        const normalizedDoc = Records && typeof Records.normalizeDocument === "function"
            ? Records.normalizeDocument(sourceDoc)
            : sourceDoc;
        const recordsMetadata = Records && typeof Records.getDocumentMetadata === "function"
            ? Records.getDocumentMetadata(normalizedDoc)
            : {};
        const sourceMetadata = getMetadataSource(sourceDoc);
        const normalizedMetadata = getMetadataSource(normalizedDoc);
        const sizeBytes = firstNumericValue(
            recordsMetadata?.size_bytes,
            normalizedMetadata?.size_bytes,
            sourceMetadata?.size_bytes,
            normalizedDoc?.size_bytes,
            sourceDoc?.size_bytes
        );
        const fallbackSizeLabel = sizeBytes !== null ? formatFileSize(sizeBytes) : "";
        const sizeLabel = firstAvailableText(
            recordsMetadata?.size_label,
            normalizedMetadata?.size_label,
            sourceMetadata?.size_label,
            normalizedDoc?.size_label,
            sourceDoc?.size_label,
            fallbackSizeLabel
        ) || DETAILS_UNAVAILABLE.size;
        const uploadedAt = firstAvailableText(
            recordsMetadata?.uploaded_at,
            normalizedMetadata?.uploaded_at,
            sourceMetadata?.uploaded_at,
            normalizedDoc?.uploaded_at,
            sourceDoc?.uploaded_at,
            sourceDoc?.upload_time,
            normalizedDoc?.created_at,
            sourceDoc?.created_at
        );
        const uploadedLabel = firstAvailableText(
            recordsMetadata?.uploaded_label,
            normalizedMetadata?.uploaded_label,
            sourceMetadata?.uploaded_label,
            normalizedDoc?.uploaded_label,
            sourceDoc?.uploaded_label,
            getUploadedLabel(normalizedDoc),
            normalizeDateLabel(uploadedAt)
        ) || DETAILS_UNAVAILABLE.date;
        const locationLabel = firstAvailableText(
            recordsMetadata?.location_label,
            normalizedMetadata?.location_label,
            sourceMetadata?.location_label,
            normalizedDoc?.location_label,
            sourceDoc?.location_label,
            getDocumentLocation(normalizedDoc)
        ) || DETAILS_UNAVAILABLE.location;
        const typeLabel = firstAvailableText(
            recordsMetadata?.type_label,
            normalizedMetadata?.type_label,
            sourceMetadata?.type_label,
            getDocumentType(normalizedDoc)
        ) || "Workspace File";

        return {
            contract: (
                recordsMetadata?.contract ||
                normalizedMetadata?.contract ||
                sourceMetadata?.contract ||
                DETAILS_METADATA_CONTRACT
            ),
            name: getDocumentName(normalizedDoc),
            typeLabel,
            sizeBytes,
            sizeLabel,
            uploadedAt,
            uploadedLabel,
            locationLabel,
            icon: getDocumentIcon(normalizedDoc),
            trash: isTrashedDocument(normalizedDoc)
        };
    }

    function getDocumentIcon(doc) {
        const Records = getRecordsApi();

        if (Records && typeof Records.getDocumentIconName === "function") {
            return Records.getDocumentIconName(doc);
        }

        return "draft";
    }

    function setVisible(node, visible) {
        if (!node) {
            return;
        }

        node.hidden = !visible;
        node.setAttribute("aria-hidden", visible ? "false" : "true");

        if (visible) {
            node.removeAttribute("hidden");
        }
    }

    function replaceAskSolomonImageWithIcon(elements) {
        const mark = elements?.askSolomonMark;
        const image = elements?.askSolomonMarkImage;

        if (!mark || !image || image.dataset.solomonIconFallbackApplied === "true") {
            return;
        }

        image.dataset.solomonIconFallbackApplied = "true";
        image.remove();
        mark.classList.add("icon");
        mark.textContent = "auto_awesome";
        mark.setAttribute("aria-hidden", "true");
    }

    function normalizeAskSolomonAction(elements) {
        const image = elements?.askSolomonMarkImage;

        if (!image) {
            return;
        }

        image.addEventListener(
            "error",
            function () {
                replaceAskSolomonImageWithIcon(elements);
            },
            { once: true }
        );

        if (image.complete && image.naturalWidth === 0) {
            replaceAskSolomonImageWithIcon(elements);
        }
    }

    function getPropertyElement(rail, propertyName) {
        return rail?.querySelector(
            `${selectors.property}[data-document-inspector-property="${propertyName}"]`
        ) || null;
    }

    function getPropertyContainer(property) {
        if (!property) {
            return null;
        }

        const container = (
            property.closest("[data-document-inspector-property-row]") ||
            property.closest(".workspace-document-inspector-property") ||
            property.closest(".workspace-document-inspector-rail__property") ||
            property.closest(".workspace-document-file-property") ||
            property.parentElement
        );

        if (
            !container ||
            container.hasAttribute("data-document-inspector-panel") ||
            container.hasAttribute("data-document-inspector-selection") ||
            container.hasAttribute("data-document-inspector-rail")
        ) {
            return property;
        }

        return container;
    }

    function setProperty(rail, propertyName, value) {
        const property = getPropertyElement(rail, propertyName);
        const container = getPropertyContainer(property);

        if (property) {
            property.textContent = cleanValue(value) || "Not available";
        }

        setVisible(container, Boolean(property));
    }

    function hideProperty(rail, propertyName) {
        const property = getPropertyElement(rail, propertyName);
        const container = getPropertyContainer(property);

        if (property) {
            property.textContent = "";
        }

        setVisible(container, false);
    }

    function getSelectionSummary(documents) {
        const docs = normalizeDocuments(documents);
        const firstDoc = docs[0] || null;

        if (!docs.length) {
            return null;
        }

        if (docs.length === 1) {
            const metadata = getDetailsMetadata(firstDoc);

            return {
                name: metadata.name,
                meta: `${metadata.typeLabel} · ${metadata.sizeLabel}`,
                type: metadata.typeLabel,
                size: metadata.sizeLabel,
                uploaded: metadata.uploadedLabel,
                location: metadata.locationLabel,
                icon: metadata.icon,
                trash: metadata.trash
            };
        }

        const metadataRecords = docs.map(getDetailsMetadata);
        const totalSize = metadataRecords.reduce(function (total, metadata) {
            return total + (
                Number.isFinite(metadata.sizeBytes)
                    ? metadata.sizeBytes
                    : 0
            );
        }, 0);
        const locationValues = uniqueValues(metadataRecords.map(function (metadata) {
            return metadata.locationLabel;
        })).filter(function (value) {
            return !isUnavailableValue(value);
        });
        const names = docs.map(getDocumentName);
        const preview = names.slice(0, 2).join(", ");
        const overflow = Math.max(0, names.length - 2);

        return {
            name: `${docs.length} files selected`,
            meta: overflow ? `${preview}, +${overflow} more` : preview,
            type: "Selected files",
            size: totalSize ? formatFileSize(totalSize) : "Multiple files",
            uploaded: "Multiple dates",
            location: locationValues.length === 1 ? locationValues[0] : "Multiple locations",
            icon: "file_copy",
            trash: docs.some(isTrashedDocument)
        };
    }

    function getActiveDocumentId() {
        return getDocumentId(activeDocuments[0] || null);
    }

    function clearNode(node) {
        while (node?.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function appendIntelligenceInlineContent(container, value) {
        const source = String(value || "");
        const tokenPattern = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\*[^*\n]+\*)/g;
        let cursor = 0;
        let match = null;

        while ((match = tokenPattern.exec(source)) !== null) {
            if (match.index > cursor) {
                container.appendChild(
                    document.createTextNode(source.slice(cursor, match.index))
                );
            }

            const token = match[0];
            let element = null;

            if (token.startsWith("**") && token.endsWith("**")) {
                element = document.createElement("strong");
                element.textContent = token.slice(2, -2);
            } else if (token.startsWith("`") && token.endsWith("`")) {
                element = document.createElement("code");
                element.textContent = token.slice(1, -1);
            } else {
                element = document.createElement("em");
                element.textContent = token.slice(1, -1);
            }

            container.appendChild(element);
            cursor = match.index + token.length;
        }

        if (cursor < source.length) {
            container.appendChild(
                document.createTextNode(source.slice(cursor))
            );
        }
    }

    function appendIntelligenceParagraph(container, lines) {
        const text = (lines || [])
            .map(cleanValue)
            .filter(Boolean)
            .join(" ");

        if (!text) {
            return;
        }

        const paragraph = document.createElement("p");
        appendIntelligenceInlineContent(paragraph, text);
        container.appendChild(paragraph);
    }

    function appendIntelligenceHeading(container, level, text) {
        const heading = document.createElement(level === 3 ? "h3" : "h2");
        appendIntelligenceInlineContent(heading, cleanValue(text));
        container.appendChild(heading);
    }

    function appendIntelligenceListItem(list, text) {
        const item = document.createElement("li");
        appendIntelligenceInlineContent(item, cleanValue(text));
        list.appendChild(item);
        return item;
    }

    function renderPlainIntelligenceContent(container, text) {
        const paragraphs = cleanValue(text)
            .split(/\n\s*\n+/)
            .map(cleanValue)
            .filter(Boolean);

        paragraphs.forEach(function (paragraphText) {
            appendIntelligenceParagraph(container, [paragraphText]);
        });
    }

    function renderSolomonMarkdownContent(container, text) {
        const lines = String(text || "").replace(/\r\n?/g, "\n").split("\n");
        let paragraphLines = [];
        let activeList = null;
        let activeListType = "";
        let lastTopLevelItem = null;
        let nestedList = null;
        let nestedListType = "";

        function flushParagraph() {
            appendIntelligenceParagraph(container, paragraphLines);
            paragraphLines = [];
        }

        function resetListState() {
            activeList = null;
            activeListType = "";
            lastTopLevelItem = null;
            nestedList = null;
            nestedListType = "";
        }

        function ensureTopLevelList(type) {
            if (activeList && activeListType === type) {
                return activeList;
            }

            const list = document.createElement(type);
            container.appendChild(list);
            activeList = list;
            activeListType = type;
            lastTopLevelItem = null;
            nestedList = null;
            nestedListType = "";
            return list;
        }

        function ensureNestedList(type) {
            if (!lastTopLevelItem) {
                return ensureTopLevelList(type);
            }

            if (nestedList && nestedListType === type) {
                return nestedList;
            }

            const list = document.createElement(type);
            lastTopLevelItem.appendChild(list);
            nestedList = list;
            nestedListType = type;
            return list;
        }

        lines.forEach(function (rawLine) {
            const line = String(rawLine || "");
            const trimmed = line.trim();

            if (!trimmed) {
                flushParagraph();
                resetListState();
                return;
            }

            const headingMatch = trimmed.match(/^(#{2,3})\s+(.+)$/);

            if (headingMatch) {
                flushParagraph();
                resetListState();
                appendIntelligenceHeading(
                    container,
                    headingMatch[1].length,
                    headingMatch[2]
                );
                return;
            }

            const unorderedMatch = line.match(/^(\s*)[-*]\s+(.+)$/);
            const orderedMatch = line.match(/^(\s*)\d+[.)]\s+(.+)$/);
            const listMatch = unorderedMatch || orderedMatch;

            if (listMatch) {
                flushParagraph();

                const type = unorderedMatch ? "ul" : "ol";
                const indentation = String(listMatch[1] || "").replace(/\t/g, "  ").length;
                const nested = indentation >= 2;
                const list = nested
                    ? ensureNestedList(type)
                    : ensureTopLevelList(type);
                const item = appendIntelligenceListItem(list, listMatch[2]);

                if (!nested) {
                    lastTopLevelItem = item;
                    nestedList = null;
                    nestedListType = "";
                }
                return;
            }

            resetListState();
            paragraphLines.push(trimmed);
        });

        flushParagraph();
    }

    function renderIntelligenceContent(container, text, format, resultType) {
        if (!container) {
            return;
        }

        clearNode(container);

        const cleanText = cleanValue(text);
        const cleanFormat = cleanValue(format).toLowerCase();
        const cleanResultType = cleanValue(resultType).toLowerCase();
        const shouldRenderMarkdown = Boolean(
            cleanFormat === RESULT_FORMAT_SOLOMON_MARKDOWN_V1 ||
            (
                STRUCTURED_LIST_RESULT_TYPES.includes(cleanResultType) &&
                /^\s*[-*]\s+\S+/m.test(cleanText)
            )
        );

        container.setAttribute(
            "data-solomon-intelligence-format",
            shouldRenderMarkdown
                ? RESULT_FORMAT_SOLOMON_MARKDOWN_V1
                : RESULT_FORMAT_PLAIN_TEXT_V1
        );

        if (!cleanText) {
            return;
        }

        if (shouldRenderMarkdown) {
            renderSolomonMarkdownContent(container, cleanText);
            return;
        }

        renderPlainIntelligenceContent(container, cleanText);
    }

    function getInspectorViewTitle(summaryView, actionView) {
        if (actionView) {
            return cleanValue(activeActionState?.resultTitle || activeActionState?.actionLabel) || "Action";
        }

        return summaryView ? "Summary" : "File details";
    }

    function setInspectorHeader(elements, summaryView, actionView) {
        const title = getInspectorViewTitle(summaryView, actionView);
        const closeLabel = actionView
            ? `Close ${title}`
            : (summaryView ? "Close summary" : "Close file details");

        if (elements.title) {
            elements.title.textContent = title;
        }

        if (elements.rail) {
            elements.rail.setAttribute("aria-label", title);
            elements.rail.setAttribute(
                "data-document-inspector-view",
                actionView
                    ? INSPECTOR_VIEW_ACTION
                    : (summaryView ? INSPECTOR_VIEW_SUMMARY : INSPECTOR_VIEW_DETAILS)
            );
        }

        elements.closes.forEach(function (close) {
            close.setAttribute("aria-label", closeLabel);
            close.setAttribute("title", closeLabel);

            const hiddenLabel = close.querySelector(".visually-hidden");

            if (hiddenLabel) {
                hiddenLabel.textContent = closeLabel;
            }
        });
    }

    function renderSummaryState(elements) {
        const state = activeSummaryState || {};
        const summaryState = cleanValue(state.state).toLowerCase() || "loading";
        const summaryText = cleanValue(state.shortSummary);
        const generatedLabel = normalizeDateLabel(state.generatedAt);
        const isLoading = summaryState === "loading";
        const isReady = summaryState === "ready";
        const isError = summaryState === "error";

        if (elements.summaryStatus) {
            let statusText = "";

            if (isLoading) {
                statusText = "Loading the saved summary…";
            } else if (isError) {
                statusText = cleanValue(state.message) || "The saved summary could not be loaded.";
            } else if (!isReady) {
                statusText = cleanValue(state.message) || "A current saved summary is not available.";
            } else if (!summaryText) {
                statusText = "The quick summary is unavailable. The full saved summary can still be opened in Reader.";
            }

            elements.summaryStatus.textContent = statusText;
            setVisible(elements.summaryStatus, Boolean(statusText));
        }

        if (elements.summaryCopy) {
            renderIntelligenceContent(
                elements.summaryCopy,
                isReady ? summaryText : "",
                RESULT_FORMAT_PLAIN_TEXT_V1,
                "summary"
            );
        }

        if (elements.summaryGenerated) {
            elements.summaryGenerated.textContent = generatedLabel
                ? `Generated ${generatedLabel}`
                : "";
            setVisible(elements.summaryGenerated, Boolean(isReady && generatedLabel));
        }

        setVisible(elements.viewFullSummary, Boolean(isReady));
    }

    function setSummaryPresentation(doc, state, options) {
        const documentId = getDocumentId(doc);
        const requestId = cleanValue(options?.requestId);

        if (!documentId) {
            return false;
        }

        activeInspectorView = INSPECTOR_VIEW_SUMMARY;
        activeSummaryState = Object.assign(
            {
                documentId,
                state: "loading",
                shortSummary: "",
                generatedAt: "",
                message: "",
                requestId
            },
            state || {}
        );

        setSourceContext(
            {
                file: doc,
                source: "workspace_document_summary"
            },
            {
                reason: cleanValue(options?.reason) || "summary"
            }
        );

        const elements = getElements();

        if (elements.rail) {
            if (requestId) {
                elements.rail.setAttribute("data-document-summary-request-id", requestId);
            } else {
                elements.rail.removeAttribute("data-document-summary-request-id");
            }
        }

        openInspector({
            reason: cleanValue(options?.reason) || "summary_command"
        });
        renderInspector();
        return true;
    }

    function showSummaryLoading(doc, options) {
        return setSummaryPresentation(
            doc,
            { state: "loading" },
            Object.assign({}, options || {}, { reason: "summary_loading" })
        );
    }

    function showSummary(doc, payload, options) {
        const summaryState = cleanValue(payload?.summary_state).toLowerCase();
        const ready = Boolean(
            payload?.ok !== false &&
            summaryState === "ready" &&
            cleanValue(payload?.detailed_summary)
        );

        return setSummaryPresentation(
            doc,
            ready
                ? {
                    state: "ready",
                    shortSummary: cleanValue(payload?.short_summary),
                    generatedAt: cleanValue(payload?.generated_at)
                }
                : {
                    state: summaryState || "unavailable",
                    message: "A current saved summary is no longer available for this file version."
                },
            Object.assign({}, options || {}, { reason: "summary_ready" })
        );
    }

    function showSummaryError(doc, message, options) {
        return setSummaryPresentation(
            doc,
            {
                state: "error",
                message: cleanValue(message) || "The saved summary could not be loaded."
            },
            Object.assign({}, options || {}, { reason: "summary_error" })
        );
    }

    function renderActionState(elements) {
        const state = activeActionState || {};
        const executionState = cleanValue(state.state).toLowerCase() || "loading";
        const content = cleanValue(state.content);
        const generatedLabel = normalizeDateLabel(state.generatedAt);
        const isLoading = ["loading", "processing", "pending", "running"].includes(executionState);
        const isReady = ["ready", "succeeded", "complete", "completed"].includes(executionState);
        const isError = ["error", "failed"].includes(executionState);
        const progressPercent = Number(state.progressPercent);
        let statusText = "";

        if (isLoading) {
            statusText = cleanValue(state.message) || `Solomon is working on ${cleanValue(state.actionLabel) || "this Action"}…`;
        } else if (isError) {
            statusText = cleanValue(state.message) || "Solomon could not complete this Action.";
        } else if (!isReady) {
            statusText = cleanValue(state.message) || "This Action is not ready yet.";
        }

        if (elements.actionPanel) {
            elements.actionPanel.setAttribute("aria-busy", isLoading ? "true" : "false");
        }

        if (elements.actionStatus) {
            elements.actionStatus.textContent = statusText;
            elements.actionStatus.setAttribute("data-document-inspector-action-state", executionState);
            setVisible(elements.actionStatus, Boolean(statusText));
        }

        if (elements.actionProgress) {
            const hasProgress = isLoading && Number.isFinite(progressPercent) && progressPercent >= 0;
            elements.actionProgress.value = hasProgress ? Math.min(100, Math.max(0, progressPercent)) : 0;
            setVisible(elements.actionProgress, hasProgress);
        }

        if (elements.actionCopy) {
            renderIntelligenceContent(
                elements.actionCopy,
                isReady ? content : "",
                state.resultFormat,
                state.resultType
            );
        }

        if (elements.actionGenerated) {
            elements.actionGenerated.textContent = generatedLabel
                ? `Generated ${generatedLabel}`
                : "";
            setVisible(elements.actionGenerated, Boolean(isReady && generatedLabel));
        }
    }

    function setActionPresentation(doc, state, options) {
        const documentId = getDocumentId(doc);
        const requestId = cleanValue(options?.requestId);

        if (!documentId) {
            return false;
        }

        activeInspectorView = INSPECTOR_VIEW_ACTION;
        activeSummaryState = null;
        activeActionState = Object.assign(
            {
                documentId,
                actionId: cleanValue(options?.actionId),
                actionLabel: cleanValue(options?.actionLabel) || "Action",
                resultTitle: cleanValue(options?.resultTitle),
                resultType: "",
                resultFormat: RESULT_FORMAT_PLAIN_TEXT_V1,
                state: "loading",
                content: "",
                generatedAt: "",
                message: "",
                progressPercent: null,
                requestId
            },
            state || {}
        );

        setSourceContext(
            {
                file: doc,
                source: "solomon_action"
            },
            {
                reason: cleanValue(options?.reason) || "solomon_action"
            }
        );

        const elements = getElements();

        if (elements.rail) {
            if (requestId) {
                elements.rail.setAttribute("data-solomon-action-request-id", requestId);
            } else {
                elements.rail.removeAttribute("data-solomon-action-request-id");
            }
        }

        openInspector({
            reason: cleanValue(options?.reason) || "solomon_action"
        });
        renderInspector();
        return true;
    }

    function showActionLoading(doc, options) {
        return setActionPresentation(
            doc,
            {
                state: "loading",
                message: `Solomon is working on ${cleanValue(options?.actionLabel) || "this Action"}…`
            },
            Object.assign({}, options || {}, { reason: "solomon_action_loading" })
        );
    }

    function showActionResult(doc, payload, options) {
        const execution = payload?.execution && typeof payload.execution === "object"
            ? payload.execution
            : {};
        const result = payload?.result && typeof payload.result === "object"
            ? payload.result
            : {};
        const action = payload?.action && typeof payload.action === "object"
            ? payload.action
            : {};
        const status = cleanValue(execution.status).toLowerCase() || (payload?.ok === true ? "succeeded" : "failed");
        const resultTitle = cleanValue(result.title || action.label || options?.actionLabel) || "Action Result";
        const content = cleanValue(result.content || result.summary || result.text);
        const pending = ["processing", "pending", "running", "queued"].includes(status);

        return setActionPresentation(
            doc,
            {
                actionId: cleanValue(action.action_id || options?.actionId),
                actionLabel: cleanValue(action.label || options?.actionLabel) || "Action",
                resultTitle,
                resultType: cleanValue(result.type),
                resultFormat: cleanValue(result.format || action.result_format) || RESULT_FORMAT_PLAIN_TEXT_V1,
                state: pending ? "processing" : (payload?.ok === false ? "error" : status),
                content,
                generatedAt: cleanValue(result.generated_at),
                message: pending
                    ? cleanValue(execution.stage) || "Solomon is still working on this Action."
                    : (content ? "" : "The Action completed, but no display content was returned."),
                progressPercent: execution.progress_percent
            },
            Object.assign({}, options || {}, {
                resultTitle,
                reason: pending ? "solomon_action_processing" : "solomon_action_ready"
            })
        );
    }

    function showActionError(doc, message, options) {
        return setActionPresentation(
            doc,
            {
                state: "error",
                message: cleanValue(message) || "Solomon could not complete this Action."
            },
            Object.assign({}, options || {}, { reason: "solomon_action_error" })
        );
    }

    function isActionRequestCurrent(documentId, requestId) {
        const elements = getElements();

        return Boolean(
            activeInspectorView === INSPECTOR_VIEW_ACTION &&
            cleanValue(documentId) &&
            cleanValue(documentId) === getActiveDocumentId() &&
            cleanValue(requestId) &&
            cleanValue(activeActionState?.requestId) === cleanValue(requestId) &&
            elements.rail?.getAttribute("data-solomon-action-request-id") === cleanValue(requestId)
        );
    }

    function isSummaryRequestCurrent(documentId, requestId) {
        const elements = getElements();

        return Boolean(
            activeInspectorView === INSPECTOR_VIEW_SUMMARY &&
            cleanValue(documentId) &&
            cleanValue(documentId) === getActiveDocumentId() &&
            cleanValue(requestId) &&
            cleanValue(activeSummaryState?.requestId) === cleanValue(requestId) &&
            elements.rail?.getAttribute("data-document-summary-request-id") === cleanValue(requestId)
        );
    }

    function renderInspector() {
        const elements = getElements();
        const summary = getSelectionSummary(activeDocuments);
        const hasSelection = Boolean(summary);
        const summaryView = Boolean(
            hasSelection &&
            activeDocuments.length === 1 &&
            activeInspectorView === INSPECTOR_VIEW_SUMMARY
        );
        const actionView = Boolean(
            hasSelection &&
            activeDocuments.length === 1 &&
            activeInspectorView === INSPECTOR_VIEW_ACTION
        );
        const summaryReady = Boolean(
            summaryView &&
            cleanValue(activeSummaryState?.state).toLowerCase() === "ready"
        );

        if (!elements.rail) {
            return;
        }

        elements.rail.setAttribute(
            "data-document-inspector-state",
            hasSelection ? "selected" : "empty"
        );
        elements.rail.setAttribute(
            "data-solomon-source-state",
            hasSelection ? "attached" : "empty"
        );

        setInspectorHeader(elements, summaryView, actionView);
        setVisible(elements.empty, !hasSelection);
        setVisible(elements.selection, hasSelection);
        setVisible(elements.detailsPanel, Boolean(hasSelection && !summaryView && !actionView));
        setVisible(elements.summaryPanel, Boolean(hasSelection && summaryView));
        setVisible(elements.actionPanel, Boolean(hasSelection && actionView));
        setVisible(
            elements.footer,
            Boolean(hasSelection && !summary?.trash && summaryView && summaryReady)
        );
        setVisible(elements.askSolomon, false);

        if (!summary) {
            hideProperty(elements.rail, "status");
            setVisible(elements.viewFullSummary, false);
            return;
        }

        if (elements.fileIcon) {
            elements.fileIcon.textContent = summary.icon;
        }

        if (elements.fileName) {
            elements.fileName.textContent = summary.name;
        }

        if (elements.fileMeta) {
            elements.fileMeta.textContent = summary.meta;
        }

        if (summaryView) {
            renderSummaryState(elements);
        } else if (actionView) {
            setVisible(elements.viewFullSummary, false);
            renderActionState(elements);
        } else {
            setVisible(elements.viewFullSummary, false);
            setProperty(elements.rail, "type", summary.type);
            setProperty(elements.rail, "size", summary.size);
            setProperty(elements.rail, "uploaded", summary.uploaded);
            setProperty(elements.rail, "location", summary.location);
            hideProperty(elements.rail, "status");
        }

        if (elements.askSolomon && !summaryView && !actionView) {
            const multiple = activeDocuments.length > 1;
            const label = multiple
                ? "Ask SolomonAI about these files"
                : "Ask SolomonAI about this file";
            const text = elements.askSolomon.querySelector("span:nth-child(2)");

            elements.askSolomon.setAttribute("aria-label", label);

            if (text) {
                text.textContent = label;
            }
        }
    }

    function synchronizeRailState(state) {
        const elements = getElements();
        const collapsed = state === COLLAPSED;

        [elements.root, elements.layout, elements.layer, elements.rail].forEach(function (node) {
            node?.setAttribute("data-solomon-rail-state", state);
        });

        if (elements.rail) {
            elements.rail.hidden = collapsed;
            elements.rail.setAttribute("aria-hidden", collapsed ? "true" : "false");

            if (!collapsed) {
                elements.rail.removeAttribute("hidden");
            }
        }

        elements.toggles.forEach(function (toggle) {
            toggle.setAttribute("aria-expanded", "false");
            toggle.setAttribute("data-solomon-toggle-state", COLLAPSED);
            toggle.classList.remove("is-active");
        });
    }

    function clearDocumentSurfaceSelection(reason) {
        dispatchInspectorEvent(
            DOCUMENT_INSPECTOR_CLEAR_EVENT,
            {
                action: "clear_selection",
                reason: cleanValue(reason) || "inspector_close",
                clearSelection: true
            }
        );
    }

    function shouldOpenInspectorFromSelection(detail) {
        const selectionIntent = normalizeActionName(
            detail?.selectionIntent ||
            detail?.interactionIntent ||
            detail?.intent ||
            detail?.reason
        );

        if (
            !DETAILS_OPEN_SELECTION_INTENTS.includes(selectionIntent) &&
            !SUMMARY_OPEN_SELECTION_INTENTS.includes(selectionIntent)
        ) {
            return false;
        }

        return detail?.openInspector !== false;
    }

    function openInspector(options) {
        bindContextRail();

        if (options?.sourceContext) {
            setSourceContext(
                options.sourceContext,
                {
                    reason: cleanValue(options.reason) || "open"
                }
            );
        }

        synchronizeRailState(STANDARD);
        dispatchInspectorEvent(
            DOCUMENT_INSPECTOR_OPEN_EVENT,
            {
                action: "open",
                reason: cleanValue(options?.reason) || "open"
            }
        );
    }

    function closeInspector(options) {
        const shouldClearSource = options?.clearSource !== false;
        const shouldClearSelection = options?.clearSelection === true;
        const reason = cleanValue(options?.reason) || "close";

        if (shouldClearSelection) {
            clearDocumentSurfaceSelection(reason);
        }

        if (shouldClearSource) {
            clearSourceContext({ reason });
        }

        activeInspectorView = INSPECTOR_VIEW_DETAILS;
        activeSummaryState = null;
        activeActionState = null;

        const elements = getElements();
        elements.rail?.removeAttribute("data-document-summary-request-id");
        elements.rail?.removeAttribute("data-solomon-action-request-id");

        synchronizeRailState(COLLAPSED);
        dispatchInspectorEvent(
            DOCUMENT_INSPECTOR_CLOSE_EVENT,
            {
                action: "close",
                reason
            }
        );
    }

    function setSourceContext(context, options) {
        const source = context || {};
        const files = Array.isArray(source.files)
            ? source.files
            : source.file
                ? [source.file]
                : [];
        const explorer = document.querySelector(selectors.explorer);
        const mergedFiles = files.map(function (file) {
            return mergeDocumentWithSelectedRow(explorer, file);
        });

        bindContextRail();

        activeDocuments = normalizeDocuments(mergedFiles);
        renderInspector();
        dispatchInspectorEvent(
            DOCUMENT_INSPECTOR_SOURCE_CHANGE_EVENT,
            {
                action: "set_source",
                reason: cleanValue(options?.reason || source.reason) || "source_context"
            }
        );

        return true;
    }

    function clearSourceContext(options) {
        activeDocuments = [];
        renderInspector();
        dispatchInspectorEvent(
            DOCUMENT_INSPECTOR_SOURCE_CHANGE_EVENT,
            {
                action: "clear_source",
                reason: cleanValue(options?.reason) || "clear"
            }
        );
    }

    function handleSelectionChange(event) {
        const detail = event?.detail || {};
        const explorer = detail.explorer ||
            event?.target?.closest?.(selectors.explorer) ||
            document.querySelector(selectors.explorer);
        let docs = Array.isArray(detail.docs) ? detail.docs : [];

        if (!docs.length && Array.isArray(detail.selectedIds)) {
            docs = resolveDocumentsByIds(explorer, detail.selectedIds);
        }

        if (!docs.length && Array.isArray(detail.documentIds)) {
            docs = resolveDocumentsByIds(explorer, detail.documentIds);
        }

        if (!docs.length && Number(detail.selectedCount || 0) > 0) {
            docs = getDocumentsFromSelectedRows(explorer);
        }

        if (docs.length) {
            const selectionIntent = normalizeActionName(
                detail?.selectionIntent ||
                detail?.interactionIntent ||
                detail?.intent ||
                detail?.reason
            );

            if (shouldPreserveInspectorPresentation(selectionIntent)) {
                return;
            }

            if (SUMMARY_OPEN_SELECTION_INTENTS.includes(selectionIntent)) {
                activeInspectorView = INSPECTOR_VIEW_SUMMARY;
                activeSummaryState = {
                    documentId: getDocumentId(docs[0] || null),
                    state: "loading",
                    shortSummary: "",
                    generatedAt: "",
                    message: "",
                    requestId: ""
                };
                activeActionState = null;
            } else {
                activeInspectorView = INSPECTOR_VIEW_DETAILS;
                activeSummaryState = null;
                activeActionState = null;
            }

            setSourceContext(
                {
                    files: docs,
                    source: cleanValue(detail.source) || "workspace_document_selection"
                },
                {
                    reason: "document_selection_change"
                }
            );

            if (shouldOpenInspectorFromSelection(detail)) {
                openInspector({
                    reason: normalizeActionName(detail.selectionIntent) || "document_selection_change"
                });
            }

            return;
        }

        // Selection is a center-surface concern. It must not implicitly close or
        // clear a right-rail presentation that the user has chosen to keep visible.
        if (activeDocuments.length) {
            return;
        }

        clearSourceContext({
            reason: "document_selection_empty"
        });
    }
    function showStatus(payload) {
        const Status = window.SolomonWorkspaceDocumentStatus;
        const explorer = document.querySelector(selectors.explorer);

        if (Status && typeof Status.show === "function" && explorer) {
            Status.show(explorer, payload);
        }
    }

    async function createDocumentAiSession() {
        const documentIds = uniqueValues(activeDocuments.map(getDocumentId));
        const elements = getElements();

        if (!documentIds.length || sessionRequestInFlight) {
            return;
        }

        sessionRequestInFlight = true;

        if (elements.askSolomon) {
            elements.askSolomon.disabled = true;
            elements.askSolomon.setAttribute("aria-busy", "true");
        }

        try {
            const response = await fetch(DOCUMENT_AI_CONVERSATIONS_ENDPOINT, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: JSON.stringify({ document_ids: documentIds })
            });
            const payload = await response.json();

            if (!response.ok || payload.ok === false) {
                throw new Error(
                    payload.user_output ||
                    payload.error ||
                    "SolomonAI could not open the selected files."
                );
            }

            await navigateToSolomonWorkspace({
                url:
                    payload.conversation_url ||
                    payload.redirect_url ||
                    payload.workspace_url ||
                    payload.session_url ||
                    SOLOMON_WORKSPACE_URL,
                launchMode: "document_ai_session",
                documentIds
            });
        } catch (error) {
            sessionRequestInFlight = false;

            if (elements.askSolomon) {
                elements.askSolomon.disabled = false;
                elements.askSolomon.removeAttribute("aria-busy");
            }

            showStatus({
                action: "ask_solomon_ai",
                variant: "error",
                message: error.message || "SolomonAI could not open the selected files."
            });
        }
    }

    function handleClick(event) {
        const elements = getElements();

        if (!elements.rail) {
            return;
        }

        const toggle = getClosestFromEvent(event, selectors.toggle);
        const close = getClosestFromEvent(event, selectors.close);
        const askSolomon = getClosestFromEvent(event, selectors.askSolomon);
        const viewFullSummary = getClosestFromEvent(event, selectors.viewFullSummary);

        if (close && isRailOwnedElement(elements.rail, close)) {
            event.preventDefault();
            event.stopPropagation();
            closeInspector({
                clearSource: true,
                clearSelection: false,
                reason: "close_button"
            });
            return;
        }

        if (askSolomon && isRailOwnedElement(elements.rail, askSolomon)) {
            event.preventDefault();
            event.stopPropagation();
            createDocumentAiSession();
            return;
        }

        if (viewFullSummary && isRailOwnedElement(elements.rail, viewFullSummary)) {
            const documentId = getActiveDocumentId();

            event.preventDefault();
            event.stopPropagation();

            if (documentId && cleanValue(activeSummaryState?.state).toLowerCase() === "ready") {
                document.dispatchEvent(
                    new CustomEvent(DOCUMENT_SUMMARY_FULL_OPEN_EVENT, {
                        detail: {
                            documentId,
                            document: activeDocuments[0] || null,
                            source: "context_rail_summary"
                        }
                    })
                );
            }
            return;
        }

        if (toggle) {
            event.preventDefault();
            event.stopPropagation();
            navigateToSolomonWorkspace({
                launchMode: "context_rail_toggle"
            });
        }
    }

    function ensureContextRailEventController() {
        if (contextRailEventControllerReady) {
            return;
        }

        contextRailEventControllerReady = true;
        document.addEventListener("click", handleClick, true);
        document.addEventListener(DOCUMENT_SELECTION_CHANGE_EVENT, handleSelectionChange);
        document.addEventListener(
            WORKSPACE_LOADED_EVENT,
            function () {
                bindContextRail();
            }
        );
    }

    function bindContextRail() {
        ensureContextRailEventController();

        const elements = getElements();

        if (!elements.rail) {
            return;
        }

        normalizeAskSolomonAction(elements);

        if (elements.rail.dataset.documentInspectorBound !== "true") {
            elements.rail.dataset.documentInspectorBound = "true";

            const state = cleanValue(elements.rail.getAttribute("data-solomon-rail-state")) || COLLAPSED;

            if (state === COLLAPSED && !activeDocuments.length) {
                synchronizeRailState(COLLAPSED);
            }
        }

        renderInspector();
    }

    api.initializeContextRail = bindContextRail;
    api.openContextRail = openInspector;
    api.closeContextRail = closeInspector;
    api.toggleContextRail = function () {
        navigateToSolomonWorkspace({
            launchMode: "context_rail_toggle"
        });
    };
    api.openContextRailForSource = function (context, options) {
        setSourceContext(
            context,
            {
                reason: cleanValue(options?.reason) || "open_for_source"
            }
        );
        openInspector(options);
    };
    api.setContextRailSource = setSourceContext;
    api.updateContextRailSource = setSourceContext;
    api.clearContextRailSource = clearSourceContext;
    api.getContextRailSource = getInspectorContext;
    api.showContextRailSummaryLoading = showSummaryLoading;
    api.showContextRailSummary = showSummary;
    api.showContextRailSummaryError = showSummaryError;
    api.isContextRailSummaryRequestCurrent = isSummaryRequestCurrent;
    api.showContextRailActionLoading = showActionLoading;
    api.showContextRailActionResult = showActionResult;
    api.showContextRailActionError = showActionError;
    api.isContextRailActionRequestCurrent = isActionRequestCurrent;

    api.open = openInspector;
    api.close = closeInspector;
    api.setSourceContext = setSourceContext;
    api.setDocumentSource = setSourceContext;
    api.getSourceContext = api.getContextRailSource;

    ensureContextRailEventController();

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bindContextRail);
    } else {
        bindContextRail();
    }
})();