/* -------------------------------------------------------------------
   FILE: workspace_document_view_state.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const DEFAULT_COLLECTION_SELECTOR = "[data-document-collection]";
    const DEFAULT_DOCUMENT_LIST_SELECTOR = "[data-document-list]";
    const DEFAULT_DOCUMENT_LIST_HEADER_SELECTOR = "[data-document-list-header], [data-workspace-listing-header]";
    const DEFAULT_DOCUMENT_LAYOUT_BUTTON_SELECTOR = "button[data-document-layout-option]";
    const DEFAULT_DOCUMENT_SORT_CONTROL_SELECTOR = "[data-document-sort-control]";
    const DEFAULT_DOCUMENT_SORT_TRIGGER_SELECTOR = "[data-document-sort-trigger]";
    const DEFAULT_DOCUMENT_SORT_CELL_TRIGGER_SELECTOR = "[data-document-sort-cell-trigger]";
    const DEFAULT_DOCUMENT_SORT_MENU_SELECTOR = "[data-document-sort-menu]";
    const DEFAULT_DOCUMENT_SORT_OPTION_SELECTOR = "[data-document-sort-option]";
    const DEFAULT_DOCUMENT_COLUMN_SORT_SELECTOR = "[data-document-column-sort-key]";

    const DEFAULT_DOCUMENT_LAYOUT_STORAGE_KEY = "solomon.documentLayout.v1";
    const DEFAULT_DOCUMENT_SORT_STORAGE_KEY = "solomon.documentSort.v2";
    const DEFAULT_DOCUMENT_LAYOUT = "list";
    const DEFAULT_DOCUMENT_SORT_KEY = "uploaded";
    const DEFAULT_DOCUMENT_SORT_DIRECTION = "desc";
    const DEFAULT_DOCUMENT_SORT_FOLDERS = "top";
    const DEFAULT_VALID_DOCUMENT_SORT_KEYS = Object.freeze(["uploaded", "name", "type", "size"]);
    const DEFAULT_VALID_DOCUMENT_SORT_DIRECTIONS = Object.freeze(["asc", "desc"]);
    const DEFAULT_VALID_DOCUMENT_SORT_FOLDERS = Object.freeze(["top", "mixed"]);

    function cleanValue(value) {
        return String(value || "").trim();
    }

    function getRecordsApi(options) {
        return options?.Records || window.SolomonWorkspaceDocumentRecords || null;
    }

    function getConversationApi(options) {
        return options?.Conversation || window.SolomonWorkspaceDocumentConversation || null;
    }

    function getSelector(options, key, fallback) {
        return cleanValue(options?.selectors?.[key]) || fallback;
    }

    function getConfig(options) {
        const cleanOptions = options || {};

        return Object.assign({}, cleanOptions, {
            Records: getRecordsApi(cleanOptions),
            Conversation: getConversationApi(cleanOptions),
            selectors: Object.assign({}, cleanOptions.selectors || {}),
            layoutStorageKey: cleanValue(cleanOptions.layoutStorageKey) || DEFAULT_DOCUMENT_LAYOUT_STORAGE_KEY,
            sortStorageKey: cleanValue(cleanOptions.sortStorageKey) || DEFAULT_DOCUMENT_SORT_STORAGE_KEY,
            defaultLayout: cleanValue(cleanOptions.defaultLayout) || DEFAULT_DOCUMENT_LAYOUT,
            defaultSortKey: cleanValue(cleanOptions.defaultSortKey) || DEFAULT_DOCUMENT_SORT_KEY,
            defaultSortDirection: cleanValue(cleanOptions.defaultSortDirection) || DEFAULT_DOCUMENT_SORT_DIRECTION,
            defaultSortFolders: cleanValue(cleanOptions.defaultSortFolders) || DEFAULT_DOCUMENT_SORT_FOLDERS,
            validSortKeys: Array.isArray(cleanOptions.validSortKeys) && cleanOptions.validSortKeys.length
                ? cleanOptions.validSortKeys
                : DEFAULT_VALID_DOCUMENT_SORT_KEYS,
            validSortDirections: Array.isArray(cleanOptions.validSortDirections) && cleanOptions.validSortDirections.length
                ? cleanOptions.validSortDirections
                : DEFAULT_VALID_DOCUMENT_SORT_DIRECTIONS,
            validSortFolders: Array.isArray(cleanOptions.validSortFolders) && cleanOptions.validSortFolders.length
                ? cleanOptions.validSortFolders
                : DEFAULT_VALID_DOCUMENT_SORT_FOLDERS,
            sortKeyLabels: cleanOptions.sortKeyLabels && typeof cleanOptions.sortKeyLabels === "object"
                ? Object.assign({}, cleanOptions.sortKeyLabels)
                : {},
            sortDefaultDirections: cleanOptions.sortDefaultDirections && typeof cleanOptions.sortDefaultDirections === "object"
                ? Object.assign({}, cleanOptions.sortDefaultDirections)
                : {},
            sortDirectionModes: cleanOptions.sortDirectionModes && typeof cleanOptions.sortDirectionModes === "object"
                ? Object.assign({}, cleanOptions.sortDirectionModes)
                : {},
            sortFolderPlacementEnabled: cleanOptions.sortFolderPlacementEnabled !== false,
            persistSort: cleanOptions.persistSort !== false,
            onSortChange: typeof cleanOptions.onSortChange === "function"
                ? cleanOptions.onSortChange
                : null,
            isFolderDocumentRecord: typeof cleanOptions.isFolderDocumentRecord === "function"
                ? cleanOptions.isFolderDocumentRecord
                : null,
            normalizeWorkspaceView: typeof cleanOptions.normalizeWorkspaceView === "function"
                ? cleanOptions.normalizeWorkspaceView
                : normalizeWorkspaceView,
            normalizeDocumentSection: typeof cleanOptions.normalizeDocumentSection === "function"
                ? cleanOptions.normalizeDocumentSection
                : normalizeDocumentSection,
            getCachedDocumentSection: typeof cleanOptions.getCachedDocumentSection === "function"
                ? cleanOptions.getCachedDocumentSection
                : null,
            renderCurrentDocumentSection: typeof cleanOptions.renderCurrentDocumentSection === "function"
                ? cleanOptions.renderCurrentDocumentSection
                : null,
            renderCurrentSectionFromCache: typeof cleanOptions.renderCurrentSectionFromCache === "function"
                ? cleanOptions.renderCurrentSectionFromCache
                : null
        });
    }

    function normalizeWorkspaceView(viewName) {
        const cleanView = cleanValue(viewName || "files").toLowerCase();

        return cleanView || "files";
    }

    function normalizeDocumentSection(section) {
        const cleanSection = cleanValue(section || "files").toLowerCase();

        return cleanSection || "files";
    }

    function normalizeDocumentLayout(layout, options) {
        const config = getConfig(options);
        const cleanLayout = cleanValue(layout || config.defaultLayout).toLowerCase();

        return cleanLayout === "grid" ? "grid" : config.defaultLayout;
    }

    function readStoredDocumentLayout(options) {
        const config = getConfig(options);

        if (!window.localStorage) {
            return "";
        }

        try {
            return cleanValue(window.localStorage.getItem(config.layoutStorageKey));
        } catch (error) {
            console.warn("[DOCUMENT_VIEW_STATE][LAYOUT] Unable to read stored layout.", error);
            return "";
        }
    }

    function storeDocumentLayout(layout, options) {
        const config = getConfig(options);

        if (!window.localStorage) {
            return;
        }

        try {
            window.localStorage.setItem(
                config.layoutStorageKey,
                normalizeDocumentLayout(layout, config)
            );
        } catch (error) {
            console.warn("[DOCUMENT_VIEW_STATE][LAYOUT] Unable to store layout.", error);
        }
    }

    function getDocumentList(explorer, options) {
        const config = getConfig(options);
        const listSelector = getSelector(
            config,
            "fileList",
            DEFAULT_DOCUMENT_LIST_SELECTOR
        );

        return explorer?.querySelector(listSelector) || null;
    }

    function getSurfaceValue(explorer, attributeName) {
        return cleanValue(
            explorer?.getAttribute(attributeName) ||
            explorer?.closest(`[${attributeName}]`)?.getAttribute(attributeName)
        ).toLowerCase();
    }

    function isSearchResultsSurface(explorer) {
        const moduleName = getSurfaceValue(explorer, "data-workspace-module");
        const sectionName = getSurfaceValue(explorer, "data-workspace-section");
        const rightPaneSurface = getSurfaceValue(explorer, "data-right-pane-content-surface");

        return Boolean(
            moduleName === "search" ||
            sectionName === "search" ||
            rightPaneSurface === "search" ||
            explorer?.querySelector("[data-search-results-list]")
        );
    }

    function syncDocumentLayoutSurfaceAttributes(explorer, layout, options) {
        const config = getConfig(options);
        const nextLayout = normalizeDocumentLayout(layout, config);
        const list = getDocumentList(explorer, config);

        if (!explorer) {
            return;
        }

        explorer.setAttribute("data-document-layout", nextLayout);
        explorer.setAttribute("data-workspace-listing-layout", nextLayout);

        if (list) {
            list.setAttribute("data-document-layout", nextLayout);
            list.setAttribute("data-workspace-listing-layout", nextLayout);
        }
    }

    function getDocumentLibraryApi() {
        return window.SolomonWorkspaceDocumentLibrary || null;
    }

    function ensureStaticListHeader(explorer, options) {
        const config = getConfig(options);
        const list = getDocumentList(explorer, config);

        if (!list || list.querySelector("[data-document-table-region]")) {
            return;
        }

        // Search layout changes are server-routed. Never synthesize a detached
        // header outside the canonical semantic table.
    }

    function syncStaticLayoutHeaders(explorer, layout, options) {
        const config = getConfig(options);
        const nextLayout = normalizeDocumentLayout(layout, config);
        const headerSelector = getSelector(
            config,
            "listHeader",
            DEFAULT_DOCUMENT_LIST_HEADER_SELECTOR
        );
        const list = getDocumentList(explorer, config);
        const shouldShowTable = nextLayout === "list";

        if (!explorer || !list) {
            return;
        }

        if (shouldShowTable) {
            ensureStaticListHeader(explorer, config);
        }

        list.querySelectorAll("[data-document-table-region]").forEach(function (region) {
            region.hidden = !shouldShowTable;
            region.setAttribute("aria-hidden", shouldShowTable ? "false" : "true");
        });

        list.querySelectorAll(headerSelector).forEach(function (header) {
            header.setAttribute("aria-hidden", shouldShowTable ? "false" : "true");
        });
    }

    function setDocumentLayout(explorer, layout, options) {
        const config = getConfig(options);
        const layoutButtonSelector = getSelector(
            config,
            "layoutButton",
            DEFAULT_DOCUMENT_LAYOUT_BUTTON_SELECTOR
        );
        const nextLayout = normalizeDocumentLayout(layout, config);

        if (!explorer) {
            return nextLayout;
        }

        syncDocumentLayoutSurfaceAttributes(explorer, nextLayout, config);

        explorer.querySelectorAll(layoutButtonSelector).forEach(function (button) {
            const isActive = normalizeDocumentLayout(
                button.getAttribute("data-document-layout-option"),
                config
            ) === nextLayout;

            button.classList.toggle("is-active", isActive);
            button.setAttribute("aria-pressed", isActive ? "true" : "false");
        });

        if (isSearchResultsSurface(explorer)) {
            syncStaticLayoutHeaders(explorer, nextLayout, config);
        }

        if (options?.persist !== false) {
            storeDocumentLayout(nextLayout, config);
        }

        return nextLayout;
    }

    function getInitialDocumentLayout(explorer, options) {
        const config = getConfig(options);

        if (isSearchResultsSurface(explorer)) {
            return normalizeDocumentLayout(
                explorer?.getAttribute("data-document-layout") ||
                readStoredDocumentLayout(config) ||
                config.defaultLayout,
                config
            );
        }

        return normalizeDocumentLayout(
            readStoredDocumentLayout(config) ||
            explorer?.getAttribute("data-document-layout") ||
            config.defaultLayout,
            config
        );
    }

    function normalizeDocumentSortKey(value, options) {
        const config = getConfig(options);
        const cleanKey = cleanValue(value || config.defaultSortKey).toLowerCase();

        return config.validSortKeys.includes(cleanKey) ? cleanKey : config.defaultSortKey;
    }

    function normalizeDocumentSortDirection(value, options) {
        const config = getConfig(options);
        const cleanDirection = cleanValue(value || config.defaultSortDirection).toLowerCase();

        return config.validSortDirections.includes(cleanDirection)
            ? cleanDirection
            : config.defaultSortDirection;
    }

    function normalizeDocumentSortFolders(value, options) {
        const config = getConfig(options);
        const cleanFolders = cleanValue(value || config.defaultSortFolders).toLowerCase();

        return config.validSortFolders.includes(cleanFolders)
            ? cleanFolders
            : config.defaultSortFolders;
    }

    function readStoredDocumentSort(options) {
        const config = getConfig(options);

        if (!window.localStorage) {
            return {};
        }

        try {
            const rawValue = window.localStorage.getItem(config.sortStorageKey);
            const storedSort = rawValue ? JSON.parse(rawValue) : {};

            return {
                key: normalizeDocumentSortKey(storedSort?.key, config),
                direction: normalizeDocumentSortDirection(storedSort?.direction, config),
                folders: normalizeDocumentSortFolders(storedSort?.folders, config)
            };
        } catch (error) {
            console.warn("[DOCUMENT_VIEW_STATE][SORT] Unable to read stored sort.", error);
            return {};
        }
    }

    function storeDocumentSort(sort, options) {
        const config = getConfig(options);

        if (!window.localStorage) {
            return;
        }

        try {
            window.localStorage.setItem(config.sortStorageKey, JSON.stringify({
                key: normalizeDocumentSortKey(sort?.key, config),
                direction: normalizeDocumentSortDirection(sort?.direction, config),
                folders: normalizeDocumentSortFolders(sort?.folders, config)
            }));
        } catch (error) {
            console.warn("[DOCUMENT_VIEW_STATE][SORT] Unable to store sort.", error);
        }
    }

    function getDocumentSort(explorer, options) {
        const config = getConfig(options);
        const storedSort = readStoredDocumentSort(config);

        return {
            key: normalizeDocumentSortKey(
                explorer?.getAttribute("data-document-sort-key") ||
                storedSort.key ||
                config.defaultSortKey,
                config
            ),
            direction: normalizeDocumentSortDirection(
                explorer?.getAttribute("data-document-sort-direction") ||
                storedSort.direction ||
                config.defaultSortDirection,
                config
            ),
            folders: normalizeDocumentSortFolders(
                explorer?.getAttribute("data-document-sort-folders") ||
                storedSort.folders ||
                config.defaultSortFolders,
                config
            )
        };
    }

    function getDocumentSortElements(explorer, options) {
        const config = getConfig(options);
        const control = explorer?.querySelector(getSelector(
            config,
            "sortControl",
            DEFAULT_DOCUMENT_SORT_CONTROL_SELECTOR
        ));
        const sortTriggerSelector = getSelector(
            config,
            "sortTrigger",
            DEFAULT_DOCUMENT_SORT_TRIGGER_SELECTOR
        );
        const controlTrigger = control?.querySelector(sortTriggerSelector) ||
            explorer?.querySelector(sortTriggerSelector) ||
            null;
        const cellTrigger = explorer?.querySelector(
            DEFAULT_DOCUMENT_SORT_CELL_TRIGGER_SELECTOR
        ) || null;

        return {
            control,
            trigger: cellTrigger || controlTrigger,
            controlTrigger,
            menu: control?.querySelector(getSelector(
                config,
                "sortMenu",
                DEFAULT_DOCUMENT_SORT_MENU_SELECTOR
            )),
            options: Array.from(control?.querySelectorAll(getSelector(
                config,
                "sortOption",
                DEFAULT_DOCUMENT_SORT_OPTION_SELECTOR
            )) || []),
            columnSortButtons: Array.from(explorer?.querySelectorAll(getSelector(
                config,
                "columnSort",
                DEFAULT_DOCUMENT_COLUMN_SORT_SELECTOR
            )) || [])
        };
    }

    function getDocumentSortTriggers(elements) {
        const triggers = [elements?.trigger, elements?.controlTrigger];

        return triggers.filter(function (trigger, index) {
            return (
                trigger instanceof HTMLElement &&
                triggers.indexOf(trigger) === index
            );
        });
    }

    function isDocumentSortTriggerDisabled(trigger) {
        return trigger instanceof HTMLButtonElement && trigger.disabled;
    }

    function setDocumentSortTriggerExpanded(elements, expanded) {
        getDocumentSortTriggers(elements).forEach(function (trigger) {
            trigger.setAttribute("aria-expanded", expanded ? "true" : "false");
        });
    }

    function getDocumentSortKeyLabel(sortKey, options) {
        const config = getConfig(options);
        const labels = Object.assign({
            name: "Name",
            uploaded: "Date modified",
            type: "File type",
            size: "File size"
        }, config.sortKeyLabels || {});

        return labels[sortKey] || labels[config.defaultSortKey] || labels.uploaded || sortKey;
    }

    function getDocumentSortDirectionLabels(sortKey, options) {
        const config = getConfig(options);
        const directionMode = cleanValue(
            config.sortDirectionModes?.[sortKey]
        ).toLowerCase();

        if (
            directionMode === "text" ||
            (!directionMode && (sortKey === "name" || sortKey === "type"))
        ) {
            return {
                asc: "A to Z",
                desc: "Z to A"
            };
        }

        if (directionMode === "size" || (!directionMode && sortKey === "size")) {
            return {
                asc: "Smallest to largest",
                desc: "Largest to smallest"
            };
        }

        return {
            asc: "Oldest to newest",
            desc: "Newest to oldest"
        };
    }

    function getDefaultDocumentSortDirection(sortKey, options) {
        const config = getConfig(options);
        const configuredDirection = cleanValue(
            config.sortDefaultDirections?.[sortKey]
        ).toLowerCase();

        if (config.validSortDirections.includes(configuredDirection)) {
            return configuredDirection;
        }

        return sortKey === "name" || sortKey === "type"
            ? "asc"
            : "desc";
    }

    function getOppositeDocumentSortDirection(direction) {
        return direction === "asc" ? "desc" : "asc";
    }

    function applyDocumentColumnSortControls(
        elements,
        sortKey,
        sortDirection,
        options
    ) {
        const config = getConfig(options);

        elements.columnSortButtons.forEach(function (button) {
            if (!(button instanceof HTMLButtonElement)) {
                return;
            }

            const buttonSortKey = cleanValue(
                button.getAttribute("data-document-column-sort-key")
            ).toLowerCase();
            const label = cleanValue(
                button.getAttribute("data-document-column-sort-label")
            ) || getDocumentSortKeyLabel(buttonSortKey, config);
            const active = buttonSortKey === sortKey;
            const cell = button.closest("th, [role='columnheader']");
            const icon = button.querySelector("[data-document-column-sort-icon]");
            const nextDirection = active
                ? getOppositeDocumentSortDirection(sortDirection)
                : getDefaultDocumentSortDirection(buttonSortKey, config);
            const currentDirectionLabel = getDocumentSortDirectionLabels(buttonSortKey, config)[sortDirection];
            const nextDirectionLabel = getDocumentSortDirectionLabels(buttonSortKey, config)[nextDirection];

            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
            button.setAttribute(
                "aria-label",
                active
                    ? `Sorted by ${label}, ${currentDirectionLabel}. Activate to sort ${nextDirectionLabel}.`
                    : `Sort by ${label}, ${nextDirectionLabel}.`
            );
            if (cell instanceof HTMLElement) {
                cell.setAttribute(
                    "aria-sort",
                    active
                        ? sortDirection === "asc"
                            ? "ascending"
                            : "descending"
                        : "none"
                );
            }

            if (icon instanceof HTMLElement) {
                icon.hidden = !active;
                icon.textContent = sortDirection === "asc"
                    ? "arrow_upward"
                    : "arrow_downward";
            }
        });
    }

    function applyDocumentSortControls(explorer, sort, options) {
        const config = getConfig(options);
        const cleanSort = sort || getDocumentSort(explorer, config);
        const sortKey = normalizeDocumentSortKey(cleanSort.key, config);
        const sortDirection = normalizeDocumentSortDirection(cleanSort.direction, config);
        const sortFolders = normalizeDocumentSortFolders(cleanSort.folders, config);
        const directionLabels = getDocumentSortDirectionLabels(sortKey, config);
        const elements = getDocumentSortElements(explorer, config);
        const summaryParts = [
            getDocumentSortKeyLabel(sortKey, config),
            directionLabels[sortDirection]
        ];

        if (config.sortFolderPlacementEnabled) {
            summaryParts.push(
                sortFolders === "top" ? "folders on top" : "folders mixed with files"
            );
        }

        const summary = summaryParts.join(", ");

        if (elements.control instanceof HTMLElement) {
            elements.control.setAttribute("data-document-sort-key", sortKey);
            elements.control.setAttribute("data-document-sort-direction", sortDirection);
            elements.control.setAttribute("data-document-sort-folders", sortFolders);
        }

        getDocumentSortTriggers(elements).forEach(function (trigger) {
            trigger.setAttribute("aria-label", `Sort items: ${summary}`);
            trigger.setAttribute("title", `Sort: ${summary}`);
        });

        if (
            elements.menu instanceof HTMLElement &&
            elements.trigger instanceof HTMLElement &&
            elements.trigger.id
        ) {
            elements.menu.setAttribute("aria-labelledby", elements.trigger.id);
        }

        elements.options.forEach(function (optionButton) {
            if (!(optionButton instanceof HTMLButtonElement)) {
                return;
            }

            const field = cleanValue(optionButton.getAttribute("data-document-sort-field"));
            const value = cleanValue(optionButton.getAttribute("data-document-sort-value"));
            const selected = (
                (field === "key" && value === sortKey) ||
                (field === "direction" && value === sortDirection) ||
                (field === "folders" && value === sortFolders)
            );

            optionButton.setAttribute("aria-checked", selected ? "true" : "false");

            if (field === "direction") {
                const label = optionButton.querySelector("[data-document-sort-option-label]");

                if (label) {
                    label.textContent = directionLabels[value] || value;
                }
            }
        });

        applyDocumentColumnSortControls(
            elements,
            sortKey,
            sortDirection,
            config
        );
    }

    function setDocumentSort(explorer, nextSort, options) {
        const config = getConfig(options);
        const currentSort = getDocumentSort(explorer, config);
        const sort = {
            key: normalizeDocumentSortKey(nextSort?.key || currentSort.key, config),
            direction: normalizeDocumentSortDirection(nextSort?.direction || currentSort.direction, config),
            folders: normalizeDocumentSortFolders(nextSort?.folders || currentSort.folders, config)
        };

        if (!explorer) {
            return sort;
        }

        explorer.setAttribute("data-document-sort-key", sort.key);
        explorer.setAttribute("data-document-sort-direction", sort.direction);
        explorer.setAttribute("data-document-sort-folders", sort.folders);
        applyDocumentSortControls(explorer, sort, config);

        if (config.persistSort && options?.persist !== false) {
            storeDocumentSort(sort, config);
        }

        return sort;
    }

    function getInitialDocumentSort(options) {
        const config = getConfig(options);
        const storedSort = readStoredDocumentSort(config);

        return {
            key: normalizeDocumentSortKey(storedSort.key || config.defaultSortKey, config),
            direction: normalizeDocumentSortDirection(storedSort.direction || config.defaultSortDirection, config),
            folders: normalizeDocumentSortFolders(storedSort.folders || config.defaultSortFolders, config)
        };
    }

    function normalizeDocument(doc, options) {
        const config = getConfig(options);
        const Records = config.Records;

        if (Records && typeof Records.normalizeDocument === "function") {
            return Records.normalizeDocument(doc || {});
        }

        return doc || {};
    }

    function readDocumentTimestampValue(rawDoc, normalizedDoc) {
        const candidates = [
            rawDoc?.modified_at,
            rawDoc?.updated_at,
            normalizedDoc?.modified_at,
            normalizedDoc?.updated_at,
            rawDoc?.uploaded_at,
            rawDoc?.upload_date,
            rawDoc?.created_at,
            rawDoc?.created,
            normalizedDoc?.uploaded_at,
            normalizedDoc?.upload_date,
            normalizedDoc?.created_at,
            normalizedDoc?.created
        ];

        for (const value of candidates) {
            if (typeof value === "number" && Number.isFinite(value)) {
                return value;
            }

            const parsed = Date.parse(String(value || ""));

            if (Number.isFinite(parsed)) {
                return parsed;
            }
        }

        return 0;
    }

    function getDocumentSortValue(rawDoc, sortKey, options) {
        const config = getConfig(options);
        const doc = normalizeDocument(rawDoc || {}, config);
        const cleanSortKey = normalizeDocumentSortKey(sortKey, config);

        if (cleanSortKey === "name") {
            return cleanValue(doc.original_name || doc.filename || doc.random_name).toLowerCase();
        }

        if (cleanSortKey === "type") {
            return cleanValue(doc.type_label || doc.mime_type || doc.extension || "Workspace File").toLowerCase();
        }

        if (cleanSortKey === "size") {
            const size = Number(doc.size_bytes || rawDoc?.size_bytes || rawDoc?.size || 0);

            return Number.isFinite(size) ? size : 0;
        }

        return readDocumentTimestampValue(rawDoc, doc);
    }

    function compareDocumentSortValues(a, b, sortKey, options) {
        const config = getConfig(options);
        const first = getDocumentSortValue(a.doc, sortKey, config);
        const second = getDocumentSortValue(b.doc, sortKey, config);

        if (typeof first === "number" || typeof second === "number") {
            return (Number(first) || 0) - (Number(second) || 0);
        }

        return cleanValue(first).localeCompare(cleanValue(second), undefined, {
            numeric: true,
            sensitivity: "base"
        });
    }

    function isFolderDocumentRecord(doc, options) {
        const config = getConfig(options);

        if (config.isFolderDocumentRecord) {
            return Boolean(config.isFolderDocumentRecord(doc));
        }

        const normalizedDoc = normalizeDocument(doc || {}, config);
        const itemType = cleanValue(
            doc?.workspace_item_type ||
            doc?.item_type ||
            doc?.resource_type ||
            doc?.document_kind ||
            doc?.object_type ||
            doc?.kind ||
            normalizedDoc?.workspace_item_type ||
            normalizedDoc?.item_type ||
            normalizedDoc?.resource_type ||
            normalizedDoc?.document_kind ||
            normalizedDoc?.object_type ||
            normalizedDoc?.kind
        ).toLowerCase();

        return Boolean(
            itemType === "folder" ||
            doc?.folder === true ||
            doc?.is_folder === true ||
            normalizedDoc?.folder === true ||
            normalizedDoc?.is_folder === true
        );
    }

    function sortDocumentsForCurrentView(explorer, docs, options) {
        const config = getConfig(options);
        const safeDocs = Array.isArray(docs) ? docs.slice() : [];

        if (config.enableDocumentSorting !== true) {
            return safeDocs;
        }

        const sort = getDocumentSort(explorer, config);
        const sortKey = normalizeDocumentSortKey(sort.key, config);
        const sortDirection = normalizeDocumentSortDirection(sort.direction, config);
        const sortFolders = normalizeDocumentSortFolders(sort.folders, config);
        const indexedDocs = safeDocs.map(function (doc, index) {
            return {
                doc,
                index,
                isFolder: isFolderDocumentRecord(doc, config)
            };
        });

        indexedDocs.sort(function (a, b) {
            if (sortFolders === "top" && a.isFolder !== b.isFolder) {
                return a.isFolder ? -1 : 1;
            }

            const result = compareDocumentSortValues(a, b, sortKey, config);

            if (result === 0) {
                return a.index - b.index;
            }

            return sortDirection === "asc" ? result : result * -1;
        });

        return indexedDocs.map(function (entry) {
            return entry.doc;
        });
    }

    function getDocumentCollection(doc, options) {
        const normalizedDoc = normalizeDocument(doc || {}, options);
        const extension = cleanValue(normalizedDoc.extension).toLowerCase();
        const typeLabel = cleanValue(normalizedDoc.type_label).toLowerCase();

        if (typeLabel.includes("spreadsheet") || ["csv", "xls", "xlsx"].includes(extension)) {
            return "spreadsheets";
        }

        if (typeLabel.includes("image") || ["png", "jpg", "jpeg", "webp", "gif"].includes(extension)) {
            return "images";
        }

        if (typeLabel.includes("pdf") || extension === "pdf") {
            return "pdfs";
        }

        if (["doc", "docx"].includes(extension) || typeLabel.includes("document")) {
            return "documents";
        }

        return "all";
    }

    function isDisabledCollectionButton(collectionButton) {
        if (!collectionButton) {
            return true;
        }

        return (
            collectionButton.disabled ||
            collectionButton.getAttribute("aria-disabled") === "true"
        );
    }

    function isCurrentCollectionButton(explorer, collectionButton, options) {
        const config = getConfig(options);

        if (!explorer || !collectionButton) {
            return false;
        }

        return (
            collectionButton.classList.contains("is-active") &&
            config.normalizeWorkspaceView(explorer.getAttribute("data-workspace-view")) === "files"
        );
    }

    function setCollection(explorer, collectionButton, options) {
        const config = getConfig(options);
        const collectionSelector = getSelector(config, "collection", DEFAULT_COLLECTION_SELECTOR);

        if (!collectionButton || isDisabledCollectionButton(collectionButton)) {
            return;
        }

        if (isCurrentCollectionButton(explorer, collectionButton, config) && !options?.force) {
            return;
        }

        explorer.querySelectorAll(collectionSelector).forEach(function (button) {
            button.classList.toggle("is-active", button === collectionButton);
        });

        if (!options?.skipRender) {
            if (config.renderCurrentSectionFromCache) {
                config.renderCurrentSectionFromCache(explorer);
            }

            if (config.Conversation && typeof config.Conversation.returnToFiles === "function") {
                config.Conversation.returnToFiles(explorer);
            }
        }
    }

    function handleCollectionClick(event, explorer, options) {
        const config = getConfig(options);
        const collectionSelector = getSelector(config, "collection", DEFAULT_COLLECTION_SELECTOR);
        const collectionButton = event?.target?.closest(collectionSelector);

        if (!collectionButton || !explorer?.contains(collectionButton)) {
            return false;
        }

        event.preventDefault();
        setCollection(explorer, collectionButton, config);

        return true;
    }

    function getSectionDocumentsForRender(explorer, options) {
        const config = getConfig(options);
        const section = config.normalizeDocumentSection(explorer?.getAttribute("data-workspace-section"));
        const docs = config.getCachedDocumentSection
            ? config.getCachedDocumentSection(explorer, section)
            : null;

        return {
            section,
            docs: docs || explorer?.__solomonDocuments || []
        };
    }

    function rerenderCurrentSectionWithSort(explorer, sort, options) {
        const config = getConfig(options);
        const sectionDocuments = getSectionDocumentsForRender(explorer, config);

        if (isSearchResultsSurface(explorer)) {
            applyDocumentSortControls(explorer, sort, config);
            return;
        }

        if (
            config.onSortChange &&
            config.onSortChange(
                explorer,
                sort,
                sectionDocuments.section
            ) === true
        ) {
            applyDocumentSortControls(explorer, sort, config);
            return;
        }

        if (config.renderCurrentDocumentSection) {
            config.renderCurrentDocumentSection(explorer, sectionDocuments.docs, {
                section: sectionDocuments.section
            });
        }

        applyDocumentSortControls(explorer, sort, config);
    }

    function rerenderCurrentSectionForLayout(explorer, options) {
        const config = getConfig(options);
        const sectionDocuments = getSectionDocumentsForRender(explorer, config);
        const currentLayout = normalizeDocumentLayout(
            explorer?.getAttribute("data-document-layout"),
            config
        );

        if (!config.renderCurrentDocumentSection) {
            return;
        }

        if (isSearchResultsSurface(explorer)) {
            syncStaticLayoutHeaders(explorer, currentLayout, config);
            return;
        }

        config.renderCurrentDocumentSection(explorer, sectionDocuments.docs, {
            section: sectionDocuments.section
        });
    }

    function closeDocumentSortMenu(explorer, options) {
        const config = getConfig(options);
        const elements = getDocumentSortElements(explorer, config);
        const restoreFocus = Boolean(options?.restoreFocus);
        const wasOpen = Boolean(
            elements.control?.getAttribute("data-document-sort-open") === "true" ||
            (elements.menu instanceof HTMLElement && !elements.menu.hidden)
        );

        if (elements.menu instanceof HTMLElement) {
            elements.menu.hidden = true;
        }

        setDocumentSortTriggerExpanded(elements, false);

        if (
            restoreFocus &&
            wasOpen &&
            elements.trigger instanceof HTMLElement
        ) {
            elements.trigger.focus({ preventScroll: true });
        }

        if (elements.control instanceof HTMLElement) {
            elements.control.setAttribute("data-document-sort-open", "false");
        }
    }

    function focusDocumentSortOption(explorer, focusEdge, options) {
        const elements = getDocumentSortElements(explorer, options);
        const optionButtons = elements.options.filter(function (optionButton) {
            return optionButton instanceof HTMLButtonElement && !optionButton.disabled;
        });

        if (!optionButtons.length) {
            return;
        }

        let target = optionButtons.find(function (optionButton) {
            return optionButton.getAttribute("aria-checked") === "true";
        }) || optionButtons[0];

        if (focusEdge === "first") {
            target = optionButtons[0];
        } else if (focusEdge === "last") {
            target = optionButtons[optionButtons.length - 1];
        }

        target.focus({ preventScroll: true });
        target.scrollIntoView({ block: "nearest" });
    }

    function openDocumentSortMenu(explorer, focusEdge, options) {
        const config = getConfig(options);
        const elements = getDocumentSortElements(explorer, config);

        if (
            !(elements.control instanceof HTMLElement) ||
            !(elements.trigger instanceof HTMLElement) ||
            !(elements.menu instanceof HTMLElement) ||
            isDocumentSortTriggerDisabled(elements.trigger)
        ) {
            return false;
        }

        applyDocumentSortControls(explorer, getDocumentSort(explorer, config), config);
        elements.menu.hidden = false;
        setDocumentSortTriggerExpanded(elements, true);
        elements.control.setAttribute("data-document-sort-open", "true");

        window.requestAnimationFrame(function () {
            focusDocumentSortOption(explorer, focusEdge || "selected", config);
        });

        return true;
    }

    function moveDocumentSortOptionFocus(explorer, direction, options) {
        const elements = getDocumentSortElements(explorer, options);
        const optionButtons = elements.options.filter(function (optionButton) {
            return optionButton instanceof HTMLButtonElement && !optionButton.disabled;
        });
        const currentIndex = optionButtons.indexOf(document.activeElement);

        if (!optionButtons.length) {
            return;
        }

        let nextIndex = 0;

        if (direction === "first") {
            nextIndex = 0;
        } else if (direction === "last") {
            nextIndex = optionButtons.length - 1;
        } else if (direction === "previous") {
            nextIndex = currentIndex <= 0 ? optionButtons.length - 1 : currentIndex - 1;
        } else {
            nextIndex = currentIndex < 0 || currentIndex >= optionButtons.length - 1
                ? 0
                : currentIndex + 1;
        }

        optionButtons[nextIndex].focus({ preventScroll: true });
        optionButtons[nextIndex].scrollIntoView({ block: "nearest" });
    }

    function selectDocumentSortOption(explorer, optionButton, options) {
        const config = getConfig(options);

        if (!(optionButton instanceof HTMLButtonElement) || optionButton.disabled) {
            return false;
        }

        const field = cleanValue(optionButton.getAttribute("data-document-sort-field"));
        const value = cleanValue(optionButton.getAttribute("data-document-sort-value"));

        if (!field || !value || !["key", "direction", "folders"].includes(field)) {
            return false;
        }

        const nextSort = {};
        nextSort[field] = value;
        const sort = setDocumentSort(explorer, nextSort, config);

        rerenderCurrentSectionWithSort(explorer, sort, config);
        optionButton.focus({ preventScroll: true });
        return true;
    }

    function handleDocumentColumnSortClick(event, explorer, options) {
        const config = getConfig(options);
        const target = event?.target instanceof Element ? event.target : null;
        const button = target?.closest(getSelector(
            config,
            "columnSort",
            DEFAULT_DOCUMENT_COLUMN_SORT_SELECTOR
        ));

        if (!(button instanceof HTMLButtonElement) || !explorer?.contains(button) || button.disabled) {
            return false;
        }

        const nextKey = normalizeDocumentSortKey(
            button.getAttribute("data-document-column-sort-key"),
            config
        );
        const currentSort = getDocumentSort(explorer, config);
        const nextDirection = currentSort.key === nextKey
            ? getOppositeDocumentSortDirection(currentSort.direction)
            : getDefaultDocumentSortDirection(nextKey, config);
        const nextSort = setDocumentSort(
            explorer,
            {
                key: nextKey,
                direction: nextDirection
            },
            config
        );

        event.preventDefault();
        closeDocumentSortMenu(explorer, config);
        rerenderCurrentSectionWithSort(explorer, nextSort, config);

        window.requestAnimationFrame(function () {
            const nextButton = explorer.querySelector(
                `${getSelector(config, "columnSort", DEFAULT_DOCUMENT_COLUMN_SORT_SELECTOR)}[data-document-column-sort-key="${nextKey}"]`
            );

            if (nextButton instanceof HTMLButtonElement) {
                nextButton.focus({ preventScroll: true });
            }
        });

        return true;
    }

    function handleDocumentSortClick(event, explorer, options) {
        const config = getConfig(options);
        const elements = getDocumentSortElements(explorer, config);
        const target = event?.target instanceof Element ? event.target : null;
        const sortTriggerSelector = getSelector(
            config,
            "sortTrigger",
            DEFAULT_DOCUMENT_SORT_TRIGGER_SELECTOR
        );
        const trigger = target?.closest(
            `${sortTriggerSelector}, ${DEFAULT_DOCUMENT_SORT_CELL_TRIGGER_SELECTOR}`
        );
        const optionButton = target?.closest(getSelector(
            config,
            "sortOption",
            DEFAULT_DOCUMENT_SORT_OPTION_SELECTOR
        ));

        if (trigger && explorer?.contains(trigger)) {
            event.preventDefault();

            if (
                elements.control?.getAttribute("data-document-sort-open") === "true" &&
                elements.menu instanceof HTMLElement &&
                !elements.menu.hidden
            ) {
                closeDocumentSortMenu(explorer, config);
            } else {
                openDocumentSortMenu(explorer, "selected", config);
            }

            return true;
        }

        if (optionButton && elements.menu?.contains(optionButton)) {
            event.preventDefault();
            return selectDocumentSortOption(explorer, optionButton, config);
        }

        return Boolean(elements.menu?.contains(target));
    }

    function handleDocumentSortKeydown(event, explorer, options) {
        const config = getConfig(options);
        const elements = getDocumentSortElements(explorer, config);
        const target = event?.target instanceof Element ? event.target : null;

        if (target === elements.trigger) {
            if (!["ArrowDown", "ArrowUp", "Home", "End", "Enter", " "].includes(event.key)) {
                return false;
            }

            event.preventDefault();
            openDocumentSortMenu(
                explorer,
                event.key === "ArrowUp" || event.key === "End" ? "last" : "first",
                config
            );
            return true;
        }

        if (!(elements.menu instanceof HTMLElement) || !elements.menu.contains(target)) {
            return false;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();
            moveDocumentSortOptionFocus(explorer, "next", config);
        } else if (event.key === "ArrowUp") {
            event.preventDefault();
            moveDocumentSortOptionFocus(explorer, "previous", config);
        } else if (event.key === "Home") {
            event.preventDefault();
            moveDocumentSortOptionFocus(explorer, "first", config);
        } else if (event.key === "End") {
            event.preventDefault();
            moveDocumentSortOptionFocus(explorer, "last", config);
        } else if (event.key === "Escape") {
            event.preventDefault();
            closeDocumentSortMenu(explorer, Object.assign({}, config, { restoreFocus: true }));
        } else if (event.key === "Enter" || event.key === " ") {
            const optionButton = target.closest(getSelector(
                config,
                "sortOption",
                DEFAULT_DOCUMENT_SORT_OPTION_SELECTOR
            ));

            if (optionButton instanceof HTMLButtonElement) {
                event.preventDefault();
                selectDocumentSortOption(explorer, optionButton, config);
            }
        } else if (event.key === "Tab") {
            closeDocumentSortMenu(explorer, config);
        } else {
            return false;
        }

        return true;
    }

    function handleDocumentLayoutClick(event, explorer, options) {
        const config = getConfig(options);
        const layoutButtonSelector = getSelector(
            config,
            "layoutButton",
            DEFAULT_DOCUMENT_LAYOUT_BUTTON_SELECTOR
        );
        const layoutButton = event?.target?.closest(layoutButtonSelector);
        const nextLayoutValue = layoutButton?.getAttribute("data-document-layout-option");

        if (!layoutButton || !explorer?.contains(layoutButton)) {
            return false;
        }

        event.preventDefault();

        const nextLayout = setDocumentLayout(explorer, nextLayoutValue, config);

        if (isSearchResultsSurface(explorer)) {
            syncStaticLayoutHeaders(explorer, nextLayout, config);
            return true;
        }

        rerenderCurrentSectionForLayout(explorer, config);

        return true;
    }

    window.SolomonWorkspaceDocumentViewState = Object.freeze({
        applyDocumentSortControls,
        compareDocumentSortValues,
        getDocumentCollection,
        getDocumentSort,
        getDocumentSortValue,
        getInitialDocumentLayout,
        getInitialDocumentSort,
        handleCollectionClick,
        handleDocumentLayoutClick,
        handleDocumentColumnSortClick,
        handleDocumentSortClick,
        handleDocumentSortKeydown,
        closeDocumentSortMenu,
        isCurrentCollectionButton,
        isDisabledCollectionButton,
        normalizeDocumentLayout,
        normalizeDocumentSortDirection,
        normalizeDocumentSortFolders,
        normalizeDocumentSortKey,
        readDocumentTimestampValue,
        readStoredDocumentLayout,
        readStoredDocumentSort,
        rerenderCurrentSectionWithSort,
        setCollection,
        setDocumentLayout,
        setDocumentSort,
        sortDocumentsForCurrentView,
        storeDocumentLayout,
        storeDocumentSort
    });
})();