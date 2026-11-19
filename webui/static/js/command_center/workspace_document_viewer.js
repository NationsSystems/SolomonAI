/* -------------------------------------------------------------------
   FILE: workspace_document_viewer.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const EXPLORER_SELECTOR = "[data-document-explorer]";
    const FILE_LIST_SELECTOR = "[data-document-list]";
    const COLLECTION_SELECTOR = "[data-document-collection]";
    const DOCUMENT_SECTION_LINK_SELECTOR = "[data-document-section-link]";
    const DOCUMENT_SECTION_TITLE_SELECTOR = "[data-document-section-title]";
    const DOCUMENT_SELECTION_RAIL_SELECTOR = "[data-document-selection-rail]";
    const DOCUMENT_SELECTION_ROW_SELECTOR = "[data-document-selection-row]";
    const DOCUMENT_CLEAR_SELECTION_SELECTOR = "[data-document-clear-selection]";
    const DOCUMENT_REFRESH_BUTTON_SELECTOR = "[data-document-refresh]";
    const UPLOAD_TRIGGER_SELECTOR = "[data-document-upload-placeholder], [data-document-upload-trigger]";
    const WORKSPACE_VIEW_BUTTON_SELECTOR = ".workspace-document-view-button[data-workspace-view]";
    const WORKSPACE_VIEW_PANEL_SELECTOR = "[data-workspace-view-panel]";
    const WORKSPACE_READER_PANEL_SELECTOR = "[data-workspace-reader-panel]";
    const READER_CONTROLLER_SELECTOR = "[data-reader-controller]";
    const WORKSPACE_READER_CLOSE_SELECTOR = "[data-workspace-reader-close]";
    const DOCUMENT_LAYOUT_BUTTON_SELECTOR = "button[data-document-layout-option]";
    const RECENT_FILTER_FORM_SELECTOR = "[data-document-recent-filters]";
    const RECENT_FILTER_CONTROL_SELECTOR = "[data-document-recent-filter]";
    const RECENT_FILTER_CLEAR_SELECTOR = "[data-document-recent-filter-clear]";
    const RECENT_FILTER_STATUS_SELECTOR = "[data-document-recent-filter-status]";
    const DOCUMENT_SORT_CONTROL_SELECTOR = "[data-document-sort-control]";
    const DOCUMENT_SORT_TRIGGER_SELECTOR = "[data-document-sort-trigger]";
    const DOCUMENT_SORT_CELL_TRIGGER_SELECTOR = "[data-document-sort-cell-trigger]";
    const DOCUMENT_SORT_MENU_SELECTOR = "[data-document-sort-menu]";
    const DOCUMENT_SORT_OPTION_SELECTOR = "[data-document-sort-option]";
    const DOCUMENT_SORT_KEY_GROUP_SELECTOR = "[data-document-sort-key-group]";
    const DOCUMENT_SORT_FOLDERS_GROUP_SELECTOR = "[data-document-sort-folders-group]";
    const DOCUMENT_COLUMN_SORT_SELECTOR = "[data-document-column-sort-key]";
    const DOCUMENT_ACTION_MENU_SELECTOR = "[data-document-action-menu]";
    const DOCUMENT_ACTION_MENU_BUTTON_SELECTOR = "[data-document-action-menu-button]";
    const DOCUMENT_ACTION_MENU_ITEM_SELECTOR = "[data-document-action-menu-item]";
    const SOLOMON_FILE_ACTION_CONTROL_SELECTOR = "[data-solomon-file-action]";
    const SOLOMON_ACTIONS_DETAILS_SELECTOR = [
        "[data-document-selection-solomon-actions]",
        "[data-reader-solomon-actions]"
    ].join(", ");
    const SOLOMON_ACTIONS_TRIGGER_SELECTOR = [
        ".workspace-document-selection-solomon-actions-trigger",
        ".document-reader-solomon-actions-trigger"
    ].join(", ");
    const SOLOMON_ACTIONS_MENU_SELECTOR = [
        ".workspace-document-selection-solomon-actions-menu",
        ".document-reader-solomon-actions-menu"
    ].join(", ");
    const SOLOMON_ACTIONS_VIEWPORT_PADDING = 8;
    const SOLOMON_ACTIONS_MENU_GAP = 3;
    const DOCUMENT_SELECTION_COMMAND_FIT_EVENT = "solomon:documents-command-fit";
    const DOCUMENT_ROW_SELECTOR = ".workspace-document-file[data-document-id]";
    const DOCUMENT_WHITESPACE_BLOCKED_SELECTOR = [
        DOCUMENT_ROW_SELECTOR,
        DOCUMENT_SORT_CELL_TRIGGER_SELECTOR,
        SOLOMON_ACTIONS_TRIGGER_SELECTOR,
        "a",
        "button",
        "input",
        "label",
        "select",
        "textarea",
        "[contenteditable='true']",
        "[role='button']",
        "[role='menuitem']"
    ].join(",");
    const DOCUMENT_SELECTION_CHECKBOX_SELECTOR = "[data-document-select-checkbox]";
    const DOCUMENT_DEFAULT_UTILITY_SELECTOR = "[data-document-selection-default-utility], [data-document-default-utility-row]";
    const DOCUMENT_INSPECTOR_CLEAR_EVENT = "solomon:document-inspector-clear";
    const SHARED_LISTING_SELECT_EVENT = "nations:workspace-listing-select";
    const SHARED_LISTING_ACTION_EVENT = "nations:workspace-listing-action";
    const SHARED_LISTING_READER_LAUNCH_EVENT = "nations:workspace-listing-reader-launch";
    const WORKSPACE_LOADED_EVENT = "solomon:workspace-loaded";
    const DOCUMENT_OPERATION_CONFIRM_SELECTOR = "[data-document-operation-confirm]";
    const DOCUMENT_OPERATION_CANCEL_SELECTOR = "[data-document-operation-cancel]";
    const DOCUMENT_OPEN_DEDUPE_WINDOW_MS = 1200;

    const DOCUMENT_LAYOUT_STORAGE_KEY = "solomon.documentLayout.v1";
    const DOCUMENT_SORT_STORAGE_KEY = "solomon.documentSort.v2";
    const DEFAULT_DOCUMENT_LAYOUT = "list";
    const DEFAULT_DOCUMENT_SORT_KEY = "uploaded";
    const DEFAULT_DOCUMENT_SORT_DIRECTION = "desc";
    const DEFAULT_DOCUMENT_SORT_FOLDERS = "top";
    const VALID_DOCUMENT_SORT_KEYS = Object.freeze(["uploaded", "name", "type", "size"]);
    const VALID_DOCUMENT_SORT_DIRECTIONS = Object.freeze(["asc", "desc"]);
    const VALID_DOCUMENT_SORT_FOLDERS = Object.freeze(["top", "mixed"]);
    const RECENT_FILTER_FIELDS = Object.freeze([
        "type",
        "people",
        "modified",
        "source"
    ]);
    const RECENT_FILTER_LABELS = Object.freeze({
        type: "Type",
        people: "People",
        modified: "Modified",
        source: "Source"
    });
    const RECENT_SORT_CONTRACT = "server_owned_recent_sort_v1";
    const RECENT_SORT_QUERY_FIELDS = Object.freeze(["sort", "direction"]);
    const MODIFIED_FILTER_OPTIONS = Object.freeze([
        Object.freeze({ value: "today", label: "Today" }),
        Object.freeze({ value: "last_7_days", label: "Last 7 days" }),
        Object.freeze({ value: "last_30_days", label: "Last 30 days" }),
        Object.freeze({ value: "this_year", label: "This year" })
    ]);
    const DEFAULT_WORKSPACE_VIEW = "files";
    const READER_WORKSPACE_VIEW = "reader";
    const VALID_WORKSPACE_VIEWS = Object.freeze(["files", "chat", "preview", "reader"]);
    const READER_ROUTE_PATTERN = /^\/workspace\/(?:file|document)\/[^/]+\/reader\/?$/;
    const READER_FRAGMENT_ROUTE_PATTERN = /^\/workspace\/(?:file|document)\/[^/]+\/reader\/fragment\/?$/;

    const DEFAULT_ACTIVE_DOCUMENTS_ENDPOINT = "/uploads/me";
    const DEFAULT_TRASH_DOCUMENTS_ENDPOINT = "/uploads/me/trash";
    const DEFAULT_UPLOAD_ENDPOINT = "/uploads";
    const DOCUMENT_SUMMARY_ENDPOINT_PREFIX = "/uploads";
    const DOCUMENT_SUMMARY_FULL_OPEN_EVENT = "solomon:document-summary-open-full";
    const SOLOMON_AI_CONVERSATION_CREATE_ENDPOINT = "/workspace/document-operation/ai";
    const SOLOMON_AI_WORKSPACE_URL = "/ai";

    const BID_SCOPE_OPERATION_KEY = "bid_scope_review";
    const BID_SCOPE_OPERATION_LABEL = "Start Bid & Scope Review";

    const ENDPOINTS = Object.freeze({
        active: "activeDocumentsEndpoint",
        trash: "trashDocumentsEndpoint",
        open: "workspaceOpenEndpoint",
        upload: "documentUploadEndpoint"
    });

    const Records = window.SolomonWorkspaceDocumentRecords;
    const Library = window.SolomonWorkspaceDocumentLibrary;
    const Status = window.SolomonWorkspaceDocumentStatus;
    const Uploads = window.SolomonWorkspaceDocumentUploads;
    const Conversation = window.SolomonWorkspaceDocumentConversation;
    const Preview = window.SolomonWorkspaceDocumentPreview;
    const Operations = window.SolomonWorkspaceDocumentOperations;
    const Sections = window.SolomonWorkspaceDocumentSections;
    const Interactions = window.SolomonWorkspaceDocumentInteractions;
    const Selection = window.SolomonWorkspaceDocumentSelection;
    const SectionNavigation = window.SolomonWorkspaceDocumentSectionNavigation;
    const ReaderLifecycle = window.SolomonWorkspaceDocumentReaderLifecycle;
    const TrashMutations = window.SolomonWorkspaceDocumentTrashMutations;
    const ViewState = window.SolomonWorkspaceDocumentViewState;

    let initialized = false;
    let solomonActionsMenuPositionFrame = 0;

    // Intelligence readiness is durable server state. Keep this workspace free of
    // page-lifetime completion transports so browser-native navigation never owns
    // a long-lived intelligence connection.

    if (!Records || !Library || !Status || !Uploads || !Conversation || !Preview || !Operations || !Sections || !Interactions || !Selection || !SectionNavigation || !ReaderLifecycle || !TrashMutations || !ViewState) {
        console.error("[DOCUMENT_VIEWER] Missing required Solomon document modules.");
        return;
    }

    function isReaderRoute() {
        return ReaderLifecycle.isReaderRoute(getDocumentReaderLifecycleOptions());
    }

    function hasEmbeddedReaderSurface(explorer) {
        return ReaderLifecycle.hasEmbeddedReaderSurface(explorer, getDocumentReaderLifecycleOptions());
    }

    function shouldUseServerReaderView(explorer) {
        return ReaderLifecycle.shouldUseServerReaderView(explorer, getDocumentReaderLifecycleOptions());
    }

    function normalizeWorkspaceView(viewName) {
        return ReaderLifecycle.normalizeWorkspaceView(viewName, getDocumentReaderLifecycleOptions());
    }

    const normalizeDocumentSection = Sections.normalizeDocumentSection;
    const isFetchableDocumentSection = Sections.isFetchableDocumentSection;
    const getDocumentSectionLabel = Sections.getDocumentSectionLabel;
    const getDocumentSectionIcon = Sections.getDocumentSectionIcon;

    function normalizeWorkspaceRoutePath(pathname) {
        return SectionNavigation.normalizeWorkspaceRoutePath(pathname, getDocumentSectionNavigationOptions());
    }

    function getWorkspaceSectionPath(section) {
        return SectionNavigation.getWorkspaceSectionPath(section, getDocumentSectionNavigationOptions());
    }

    function getWorkspaceSectionFromPath(pathname) {
        return SectionNavigation.getWorkspaceSectionFromPath(pathname, getDocumentSectionNavigationOptions());
    }

    function isWorkspaceSectionPath(pathname) {
        return SectionNavigation.isWorkspaceSectionPath(pathname, getDocumentSectionNavigationOptions());
    }

    function isTrashSection(explorer) {
        return normalizeDocumentSection(explorer?.getAttribute("data-workspace-section")) === "trash";
    }

    function getCurrentWorkspaceView(explorer) {
        return ReaderLifecycle.getCurrentWorkspaceView(explorer, getDocumentReaderLifecycleOptions());
    }

    function getInitialWorkspaceView(explorer) {
        return ReaderLifecycle.getInitialWorkspaceView(explorer, getDocumentReaderLifecycleOptions());
    }

    function getReaderPanel(explorer) {
        return ReaderLifecycle.getReaderPanel(explorer, getDocumentReaderLifecycleOptions());
    }

    function clearReaderRouteHash() {
        ReaderLifecycle.clearReaderRouteHash();
    }

    function closeReaderView(explorer, options) {
        ReaderLifecycle.closeReaderView(
            explorer,
            Object.assign(
                {},
                getDocumentReaderLifecycleOptions(),
                options || {}
            )
        );
    }

    function applyReaderRouteView(explorer) {
        ReaderLifecycle.applyReaderRouteView(explorer, getDocumentReaderLifecycleOptions());
    }

    function restoreWorkspaceView(explorer, viewName) {
        ReaderLifecycle.restoreWorkspaceView(explorer, viewName, getDocumentReaderLifecycleOptions());
    }

    function isReaderWorkspaceView(explorer) {
        return ReaderLifecycle.isReaderWorkspaceView(explorer, getDocumentReaderLifecycleOptions());
    }

    function isReaderOpeningOrActive(explorer) {
        const state = cleanValue(
            explorer?.getAttribute("data-workspace-reader-state")
        ).toLowerCase();

        return Boolean(
            state === "opening" ||
            state === "loading" ||
            state === "rendering" ||
            state === "loaded" ||
            isReaderWorkspaceView(explorer) ||
            shouldUseServerReaderView(explorer)
        );
    }

    function getEndpoint(explorer, key) {
        const datasetKey = ENDPOINTS[key];

        if (!datasetKey) {
            return "";
        }

        if (key === "active") {
            return String(explorer.dataset[datasetKey] || DEFAULT_ACTIVE_DOCUMENTS_ENDPOINT).trim();
        }

        if (key === "trash") {
            return String(explorer.dataset[datasetKey] || DEFAULT_TRASH_DOCUMENTS_ENDPOINT).trim();
        }

        if (key === "upload") {
            return String(explorer.dataset[datasetKey] || DEFAULT_UPLOAD_ENDPOINT).trim();
        }

        return String(explorer.dataset[datasetKey] || "").trim();
    }

    function buildTrashDocumentsEndpoint(explorer) {
        return TrashMutations.buildTrashDocumentsEndpoint(explorer, getDocumentTrashMutationOptions());
    }

    function getDocumentSectionEndpoint(explorer, section) {
        return TrashMutations.getDocumentSectionEndpoint(explorer, section, getDocumentTrashMutationOptions());
    }

    function buildMoveToTrashEndpoint(explorer, documentId) {
        return TrashMutations.buildMoveToTrashEndpoint(explorer, documentId, getDocumentTrashMutationOptions());
    }

    function buildTrashDocumentEndpoint(explorer, documentId) {
        return TrashMutations.buildTrashDocumentEndpoint(explorer, documentId, getDocumentTrashMutationOptions());
    }

    function buildRestoreFromTrashEndpoint(explorer, documentId) {
        return TrashMutations.buildRestoreFromTrashEndpoint(explorer, documentId, getDocumentTrashMutationOptions());
    }

    function buildPermanentDeleteEndpoint(explorer, documentId) {
        return TrashMutations.buildPermanentDeleteEndpoint(explorer, documentId, getDocumentTrashMutationOptions());
    }

    function buildReaderFragmentUrl(readerUrl) {
        return ReaderLifecycle.buildReaderFragmentUrl(readerUrl, getDocumentReaderLifecycleOptions());
    }

    async function fetchJson(url, options) {
        const response = await fetch(url, {
            method: options?.method || "GET",
            credentials: "same-origin",
            headers: options?.headers || {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            },
            body: options?.body || undefined
        });

        const contentType = String(response.headers.get("content-type") || "").toLowerCase();

        if (!contentType.includes("application/json")) {
            throw new Error("The server returned an invalid document response.");
        }

        const payload = await response.json();

        if (!response.ok || payload.ok === false) {
            throw new Error(payload.user_output || payload.error || "Document request failed.");
        }

        return payload;
    }

    function cleanValue(value) {
        return Selection.cleanValue(value);
    }

    function getRecentFilterForm(explorer) {
        return explorer?.querySelector(RECENT_FILTER_FORM_SELECTOR) || null;
    }

    function getRecentFilterControl(explorer, fieldName) {
        const cleanField = cleanValue(fieldName).toLowerCase();

        if (!RECENT_FILTER_FIELDS.includes(cleanField)) {
            return null;
        }

        return explorer?.querySelector(
            `${RECENT_FILTER_CONTROL_SELECTOR}[data-document-recent-filter="${cleanField}"]`
        ) || null;
    }

    function readRecentFilterStateFromLocation() {
        const state = {};
        const search = new URLSearchParams(window.location.search || "");

        RECENT_FILTER_FIELDS.forEach(function (fieldName) {
            state[fieldName] = cleanValue(search.get(fieldName));
        });

        return state;
    }

    function getRecentFilterState(explorer) {
        const form = getRecentFilterForm(explorer);
        const section = normalizeDocumentSection(
            explorer?.getAttribute("data-workspace-section") || "files"
        );
        const useLocationState = (
            section === "recent" &&
            form?.getAttribute("data-document-recent-filters-ready") !== "true"
        );
        const locationState = useLocationState
            ? readRecentFilterStateFromLocation()
            : {};
        const state = {};

        RECENT_FILTER_FIELDS.forEach(function (fieldName) {
            const control = getRecentFilterControl(explorer, fieldName);

            state[fieldName] = cleanValue(
                useLocationState
                    ? locationState[fieldName]
                    : control?.value
            );
        });

        return state;
    }

    function hasActiveRecentFilters(state) {
        const cleanState = state && typeof state === "object" ? state : {};

        return RECENT_FILTER_FIELDS.some(function (fieldName) {
            return Boolean(cleanValue(cleanState[fieldName]));
        });
    }

    function readRecentSortRequestStateFromLocation() {
        const search = new URLSearchParams(window.location.search || "");

        return {
            sort: cleanValue(search.get("sort")),
            direction: cleanValue(search.get("direction"))
        };
    }

    function getRecentSortAuthority(explorer) {
        const authority = explorer?.__solomonRecentSortAuthority;

        return authority && typeof authority === "object"
            ? authority
            : null;
    }

    function getRecentSortRequestState(explorer) {
        const authority = getRecentSortAuthority(explorer);

        if (authority) {
            const requestedKey = cleanValue(
                explorer?.getAttribute("data-document-sort-key")
            ).toLowerCase();
            const requestedDirection = cleanValue(
                explorer?.getAttribute("data-document-sort-direction")
            ).toLowerCase();

            return {
                sort: authority.allowedKeys.includes(requestedKey)
                    ? requestedKey
                    : authority.key,
                direction: authority.allowedDirections.includes(requestedDirection)
                    ? requestedDirection
                    : authority.direction
            };
        }

        return readRecentSortRequestStateFromLocation();
    }

    function buildRecentRequestEndpoint(endpoint, state, sortState) {
        const cleanEndpoint = cleanValue(endpoint);

        if (!cleanEndpoint) {
            return "";
        }

        let parsedUrl;

        try {
            parsedUrl = new URL(cleanEndpoint, window.location.origin);
        } catch (_error) {
            return cleanEndpoint;
        }

        RECENT_FILTER_FIELDS.forEach(function (fieldName) {
            const fieldValue = cleanValue(state?.[fieldName]);

            if (fieldValue) {
                parsedUrl.searchParams.set(fieldName, fieldValue);
            } else {
                parsedUrl.searchParams.delete(fieldName);
            }
        });

        RECENT_SORT_QUERY_FIELDS.forEach(function (fieldName) {
            const fieldValue = cleanValue(sortState?.[fieldName]);

            if (fieldValue) {
                parsedUrl.searchParams.set(fieldName, fieldValue);
            } else {
                parsedUrl.searchParams.delete(fieldName);
            }
        });

        return `${parsedUrl.pathname}${parsedUrl.search}`;
    }

    function buildRecentPageRoute(state, sortState) {
        return buildRecentRequestEndpoint("/recent", state, sortState) || "/recent";
    }

    function syncRecentFilterLocation(state) {
        if (window.location.pathname !== "/recent" || !window.history?.replaceState) {
            return;
        }

        const currentUrl = new URL(window.location.href);

        RECENT_FILTER_FIELDS.forEach(function (fieldName) {
            const fieldValue = cleanValue(state?.[fieldName]);

            if (fieldValue) {
                currentUrl.searchParams.set(fieldName, fieldValue);
            } else {
                currentUrl.searchParams.delete(fieldName);
            }
        });

        window.history.replaceState(
            Object.assign({}, window.history.state || {}, {
                recentFilters: Object.assign({}, state || {})
            }),
            "",
            `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`
        );
    }

    function syncRecentSortLocation(sortState) {
        if (window.location.pathname !== "/recent" || !window.history?.replaceState) {
            return;
        }

        const currentUrl = new URL(window.location.href);

        RECENT_SORT_QUERY_FIELDS.forEach(function (fieldName) {
            const fieldValue = cleanValue(sortState?.[fieldName]);

            if (fieldValue) {
                currentUrl.searchParams.set(fieldName, fieldValue);
            } else {
                currentUrl.searchParams.delete(fieldName);
            }
        });

        window.history.replaceState(
            Object.assign({}, window.history.state || {}, {
                recentSort: Object.assign({}, sortState || {})
            }),
            "",
            `${currentUrl.pathname}${currentUrl.search}${currentUrl.hash}`
        );
    }

    function normalizeRecentSortAuthority(payload) {
        const safePayload = payload && typeof payload === "object" ? payload : {};
        const source = safePayload.sort && typeof safePayload.sort === "object"
            ? safePayload.sort
            : null;

        if (
            !source ||
            cleanValue(safePayload.sort_contract) !== RECENT_SORT_CONTRACT ||
            cleanValue(source.contract) !== RECENT_SORT_CONTRACT
        ) {
            return null;
        }

        const allowedDirections = Array.from(new Set(
            (Array.isArray(source.allowed_directions) ? source.allowed_directions : [])
                .map(function (value) {
                    return cleanValue(value).toLowerCase();
                })
                .filter(Boolean)
        ));
        const allowedKeys = Array.from(new Set(
            (Array.isArray(source.allowed_keys) ? source.allowed_keys : [])
                .map(function (value) {
                    return cleanValue(value).toLowerCase();
                })
                .filter(Boolean)
        ));

        if (!allowedKeys.length || !allowedDirections.length) {
            return null;
        }

        const options = (Array.isArray(source.options) ? source.options : [])
            .map(function (option) {
                const value = cleanValue(option?.value).toLowerCase();
                const label = cleanValue(option?.label);
                const defaultDirection = cleanValue(option?.default_direction).toLowerCase();
                const directionMode = cleanValue(option?.direction_mode).toLowerCase();

                if (!value || !label || !allowedKeys.includes(value)) {
                    return null;
                }

                return {
                    value,
                    label,
                    defaultDirection: allowedDirections.includes(defaultDirection)
                        ? defaultDirection
                        : allowedDirections[0],
                    directionMode
                };
            })
            .filter(Boolean);
        const optionKeys = options.map(function (option) {
            return option.value;
        });
        const authoritativeKeys = allowedKeys.filter(function (value) {
            return optionKeys.includes(value);
        });

        if (!authoritativeKeys.length) {
            return null;
        }

        const defaultKeyCandidate = cleanValue(source.default_key).toLowerCase();
        const defaultKey = authoritativeKeys.includes(defaultKeyCandidate)
            ? defaultKeyCandidate
            : authoritativeKeys[0];
        const defaultDirectionCandidate = cleanValue(source.default_direction).toLowerCase();
        const defaultDirection = allowedDirections.includes(defaultDirectionCandidate)
            ? defaultDirectionCandidate
            : allowedDirections[0];
        const keyCandidate = cleanValue(source.key).toLowerCase();
        const key = authoritativeKeys.includes(keyCandidate)
            ? keyCandidate
            : defaultKey;
        const directionCandidate = cleanValue(source.direction).toLowerCase();
        const direction = allowedDirections.includes(directionCandidate)
            ? directionCandidate
            : (
                options.find(function (option) {
                    return option.value === key;
                })?.defaultDirection || defaultDirection
            );

        return {
            contract: RECENT_SORT_CONTRACT,
            key,
            direction,
            defaultKey,
            defaultDirection,
            allowedKeys: authoritativeKeys,
            allowedDirections,
            folderPlacementSupported: source.folder_placement_supported === true,
            options: options.filter(function (option) {
                return authoritativeKeys.includes(option.value);
            })
        };
    }

    function ensureDefaultDocumentSortMenuProjection(explorer) {
        if (!explorer || explorer.__solomonDefaultDocumentSortMenuProjection) {
            return;
        }

        const keyGroup = explorer.querySelector(DOCUMENT_SORT_KEY_GROUP_SELECTOR);
        const foldersGroup = explorer.querySelector(DOCUMENT_SORT_FOLDERS_GROUP_SELECTOR);

        explorer.__solomonDefaultDocumentSortMenuProjection = {
            keyGroupNodes: keyGroup instanceof HTMLElement
                ? Array.from(keyGroup.childNodes).map(function (node) {
                    return node.cloneNode(true);
                })
                : [],
            foldersHidden: foldersGroup instanceof HTMLElement ? foldersGroup.hidden : false
        };
    }

    function restoreDefaultDocumentSortMenuProjection(explorer) {
        const baseline = explorer?.__solomonDefaultDocumentSortMenuProjection;
        const keyGroup = explorer?.querySelector(DOCUMENT_SORT_KEY_GROUP_SELECTOR);
        const foldersGroup = explorer?.querySelector(DOCUMENT_SORT_FOLDERS_GROUP_SELECTOR);

        if (!baseline) {
            return;
        }

        if (
            keyGroup instanceof HTMLElement &&
            keyGroup.getAttribute("data-document-sort-authority-projection") === "recent"
        ) {
            keyGroup.replaceChildren(
                ...baseline.keyGroupNodes.map(function (node) {
                    return node.cloneNode(true);
                })
            );
            keyGroup.removeAttribute("data-document-sort-authority-projection");
        }

        if (foldersGroup instanceof HTMLElement) {
            foldersGroup.hidden = Boolean(baseline.foldersHidden);
            foldersGroup.removeAttribute("aria-hidden");
            Array.from(foldersGroup.querySelectorAll(DOCUMENT_SORT_OPTION_SELECTOR)).forEach(function (option) {
                if (option instanceof HTMLButtonElement) {
                    option.disabled = false;
                }
            });
        }
    }

    function createServerSortOption(option) {
        const button = document.createElement("button");
        const label = document.createElement("span");
        const indicator = document.createElement("span");

        button.type = "button";
        button.className = "workspace-document-sort-option";
        button.setAttribute("data-document-sort-option", "");
        button.setAttribute("data-document-sort-field", "key");
        button.setAttribute("data-document-sort-value", option.value);
        button.setAttribute("role", "menuitemradio");
        button.setAttribute("tabindex", "-1");
        button.setAttribute("aria-checked", "false");

        label.textContent = option.label;
        indicator.className = "icon workspace-document-sort-option-check";
        indicator.setAttribute("aria-hidden", "true");
        indicator.textContent = "check";
        button.append(label, indicator);

        return button;
    }

    function projectRecentSortMenu(explorer, authority) {
        ensureDefaultDocumentSortMenuProjection(explorer);

        const keyGroup = explorer?.querySelector(DOCUMENT_SORT_KEY_GROUP_SELECTOR);
        const foldersGroup = explorer?.querySelector(DOCUMENT_SORT_FOLDERS_GROUP_SELECTOR);

        if (keyGroup instanceof HTMLElement) {
            const label = keyGroup.querySelector(".workspace-document-sort-menu-label");

            Array.from(keyGroup.querySelectorAll(DOCUMENT_SORT_OPTION_SELECTOR)).forEach(function (option) {
                option.remove();
            });
            authority.options.forEach(function (option) {
                keyGroup.appendChild(createServerSortOption(option));
            });
            keyGroup.setAttribute("data-document-sort-authority-projection", "recent");

            if (label instanceof HTMLElement) {
                label.textContent = "Sort by";
            }
        }

        if (foldersGroup instanceof HTMLElement) {
            foldersGroup.hidden = !authority.folderPlacementSupported;
            foldersGroup.setAttribute(
                "aria-hidden",
                authority.folderPlacementSupported ? "false" : "true"
            );
            Array.from(foldersGroup.querySelectorAll(DOCUMENT_SORT_OPTION_SELECTOR)).forEach(function (option) {
                if (option instanceof HTMLButtonElement) {
                    option.disabled = !authority.folderPlacementSupported;
                }
            });
        }
    }

    function syncRecentSortAuthority(explorer, payload, requestedSection) {
        const section = normalizeDocumentSection(
            requestedSection ||
            explorer?.getAttribute("data-workspace-section") ||
            "files"
        );

        if (section !== "recent") {
            const hadRecentSortAuthority = Boolean(getRecentSortAuthority(explorer));

            explorer.__solomonRecentSortAuthority = null;
            restoreDefaultDocumentSortMenuProjection(explorer);

            if (hadRecentSortAuthority) {
                setDocumentSort(
                    explorer,
                    getInitialDocumentSort(),
                    { explorer, persist: false }
                );
            }

            return null;
        }

        const authority = normalizeRecentSortAuthority(payload);

        if (!authority) {
            explorer.__solomonRecentSortAuthority = null;
            return null;
        }

        explorer.__solomonRecentSortAuthority = authority;
        projectRecentSortMenu(explorer, authority);
        setDocumentSort(
            explorer,
            {
                key: authority.key,
                direction: authority.direction,
                folders: DEFAULT_DOCUMENT_SORT_FOLDERS
            },
            {
                explorer,
                persist: false
            }
        );
        syncRecentSortLocation({
            sort: authority.key,
            direction: authority.direction
        });

        return authority;
    }

    function createRecentFilterOption(option) {
        const node = document.createElement("option");
        const value = cleanValue(option?.value);
        const label = cleanValue(option?.label) || value;
        const count = Number(option?.count);

        node.value = value;
        node.textContent = Number.isFinite(count)
            ? `${label} (${count})`
            : label;
        node.setAttribute("data-document-recent-filter-option", value);
        return node;
    }

    function normalizeListingFilterToken(value) {
        return cleanValue(value).toLowerCase();
    }

    function getDocumentFilterSourceCache(explorer) {
        if (!explorer.__solomonDocumentFilterSourceCache) {
            explorer.__solomonDocumentFilterSourceCache = new Map();
        }

        return explorer.__solomonDocumentFilterSourceCache;
    }

    function setDocumentFilterSource(explorer, section, docs) {
        if (!explorer) {
            return;
        }

        const cleanSection = normalizeDocumentSection(section);
        const safeDocs = Array.isArray(docs) ? docs.slice() : [];

        getDocumentFilterSourceCache(explorer).set(cleanSection, safeDocs);
    }

    function hasDocumentFilterSource(explorer, section) {
        if (!explorer?.__solomonDocumentFilterSourceCache) {
            return false;
        }

        return explorer.__solomonDocumentFilterSourceCache.has(
            normalizeDocumentSection(section)
        );
    }

    function getDocumentFilterSource(explorer, section) {
        if (!explorer) {
            return [];
        }

        const cleanSection = normalizeDocumentSection(section);
        const cache = getDocumentFilterSourceCache(explorer);

        if (cache.has(cleanSection)) {
            const docs = cache.get(cleanSection);
            return Array.isArray(docs) ? docs.slice() : [];
        }

        const cachedDocs = getCachedDocumentSection(explorer, cleanSection);
        return Array.isArray(cachedDocs) ? cachedDocs.slice() : [];
    }

    function removeDocumentFromFilterSource(explorer, section, documentId) {
        const cleanId = cleanValue(documentId);

        if (!cleanId || !explorer?.__solomonDocumentFilterSourceCache) {
            return;
        }

        const cleanSection = normalizeDocumentSection(section);
        const docs = getDocumentFilterSource(explorer, cleanSection).filter(function (doc) {
            return Records.getDocumentId(doc) !== cleanId;
        });

        setDocumentFilterSource(explorer, cleanSection, docs);
    }

    function getListingFilterSectionLabel(explorer, section) {
        const cleanSection = normalizeDocumentSection(section);

        if (cleanSection === "shared") {
            return "Shared with me";
        }

        if (cleanSection === "trash") {
            return "Trash";
        }

        if (cleanSection === "recent") {
            return "Recent";
        }

        return "My Files";
    }

    function getDocumentTypeFilterDescriptor(rawDoc) {
        const doc = Records.normalizeDocument(rawDoc || {});
        const isFolder = Library.isWorkspaceFolderRecord(rawDoc, doc);
        const extension = normalizeListingFilterToken(doc.extension);
        const typeLabel = normalizeListingFilterToken(
            doc.type_label || doc.mime_type
        );

        if (isFolder) {
            return { value: "folders", label: "Folders" };
        }

        if (extension === "pdf" || typeLabel.includes("pdf")) {
            return { value: "pdfs", label: "PDFs" };
        }

        if (
            ["doc", "docx"].includes(extension) ||
            typeLabel.includes("document")
        ) {
            return { value: "documents", label: "Documents" };
        }

        if (
            ["csv", "xls", "xlsx"].includes(extension) ||
            typeLabel.includes("spreadsheet")
        ) {
            return { value: "spreadsheets", label: "Spreadsheets" };
        }

        if (
            ["gif", "jpeg", "jpg", "png", "webp"].includes(extension) ||
            typeLabel.includes("image")
        ) {
            return { value: "images", label: "Images" };
        }

        if (
            ["md", "rtf", "txt"].includes(extension) ||
            typeLabel.includes("text")
        ) {
            return { value: "text", label: "Text files" };
        }

        return { value: "other", label: "Other files" };
    }

    function getDocumentPeopleFilterDescriptor(rawDoc) {
        const doc = Records.normalizeDocument(rawDoc || {});
        const label = cleanValue(
            rawDoc?.owner_label ||
            rawDoc?.owner_name ||
            rawDoc?.uploaded_by_name ||
            doc.owner_label ||
            doc.owner_name ||
            doc.uploaded_by_name
        ) || "Me";

        return {
            value: normalizeListingFilterToken(label),
            label
        };
    }

    function getDocumentSourceFilterDescriptor(explorer, rawDoc, section) {
        const doc = Records.normalizeDocument(rawDoc || {});
        const label = cleanValue(
            rawDoc?.location_label ||
            rawDoc?.source_label ||
            rawDoc?.source ||
            doc.location_label ||
            doc.source_label ||
            doc.source
        ) || getListingFilterSectionLabel(explorer, section);

        return {
            value: normalizeListingFilterToken(label),
            label
        };
    }

    function getDocumentModifiedTimestamp(rawDoc) {
        const doc = Records.normalizeDocument(rawDoc || {});
        return readDocumentTimestampValue(rawDoc, doc);
    }

    function matchesModifiedFilter(timestamp, filterValue) {
        const cleanFilter = normalizeListingFilterToken(filterValue);

        if (!cleanFilter) {
            return true;
        }

        if (!Number.isFinite(timestamp) || timestamp <= 0) {
            return false;
        }

        const now = new Date();
        const current = new Date(timestamp);
        const startOfToday = new Date(
            now.getFullYear(),
            now.getMonth(),
            now.getDate()
        ).getTime();

        if (cleanFilter === "today") {
            return timestamp >= startOfToday;
        }

        if (cleanFilter === "last_7_days") {
            return timestamp >= startOfToday - (6 * 24 * 60 * 60 * 1000);
        }

        if (cleanFilter === "last_30_days") {
            return timestamp >= startOfToday - (29 * 24 * 60 * 60 * 1000);
        }

        if (cleanFilter === "this_year") {
            return current.getFullYear() === now.getFullYear();
        }

        return true;
    }

    function addListingFilterOption(optionMap, descriptor) {
        const value = cleanValue(descriptor?.value);
        const label = cleanValue(descriptor?.label);

        if (!value || !label) {
            return;
        }

        const current = optionMap.get(value) || {
            value,
            label,
            count: 0
        };

        current.count += 1;
        optionMap.set(value, current);
    }

    function buildListingFilterOptions(explorer, docs, section) {
        const safeDocs = Array.isArray(docs) ? docs : [];
        const typeOptions = new Map();
        const peopleOptions = new Map();
        const sourceOptions = new Map();
        const modifiedCounts = new Map(
            MODIFIED_FILTER_OPTIONS.map(function (option) {
                return [option.value, 0];
            })
        );

        safeDocs.forEach(function (doc) {
            addListingFilterOption(
                typeOptions,
                getDocumentTypeFilterDescriptor(doc)
            );
            addListingFilterOption(
                peopleOptions,
                getDocumentPeopleFilterDescriptor(doc)
            );
            addListingFilterOption(
                sourceOptions,
                getDocumentSourceFilterDescriptor(explorer, doc, section)
            );

            const timestamp = getDocumentModifiedTimestamp(doc);
            MODIFIED_FILTER_OPTIONS.forEach(function (option) {
                if (matchesModifiedFilter(timestamp, option.value)) {
                    modifiedCounts.set(
                        option.value,
                        Number(modifiedCounts.get(option.value) || 0) + 1
                    );
                }
            });
        });

        const sortOptions = function (options) {
            return Array.from(options.values()).sort(function (a, b) {
                return a.label.localeCompare(b.label, undefined, {
                    numeric: true,
                    sensitivity: "base"
                });
            });
        };

        return {
            type: sortOptions(typeOptions),
            people: sortOptions(peopleOptions),
            modified: MODIFIED_FILTER_OPTIONS.map(function (option) {
                return {
                    value: option.value,
                    label: option.label,
                    count: Number(modifiedCounts.get(option.value) || 0)
                };
            }).filter(function (option) {
                return option.count > 0;
            }),
            source: sortOptions(sourceOptions)
        };
    }

    function filterDocumentsForCurrentView(explorer, docs, section) {
        const cleanSection = normalizeDocumentSection(section);
        const safeDocs = Array.isArray(docs) ? docs.slice() : [];

        if (cleanSection === "recent") {
            return safeDocs;
        }

        const state = getRecentFilterState(explorer);

        if (!hasActiveRecentFilters(state)) {
            return safeDocs;
        }

        return safeDocs.filter(function (doc) {
            const typeDescriptor = getDocumentTypeFilterDescriptor(doc);
            const peopleDescriptor = getDocumentPeopleFilterDescriptor(doc);
            const sourceDescriptor = getDocumentSourceFilterDescriptor(
                explorer,
                doc,
                cleanSection
            );
            const modifiedTimestamp = getDocumentModifiedTimestamp(doc);

            return (
                (!state.type || typeDescriptor.value === state.type) &&
                (!state.people || peopleDescriptor.value === state.people) &&
                (!state.source || sourceDescriptor.value === state.source) &&
                matchesModifiedFilter(modifiedTimestamp, state.modified)
            );
        });
    }

    function syncRecentFilterControls(explorer, payload, docs, requestedSection) {
        const form = getRecentFilterForm(explorer);

        if (!form) {
            return;
        }

        const section = normalizeDocumentSection(
            requestedSection ||
            explorer?.getAttribute("data-workspace-section") ||
            "files"
        );
        const safePayload = payload && typeof payload === "object"
            ? payload
            : {};
        const safeDocs = Array.isArray(docs)
            ? docs
            : getDocumentFilterSource(explorer, section);
        const previousSection = normalizeDocumentSection(
            form.getAttribute("data-document-filter-section") || section
        );
        const sectionChanged = previousSection !== section;
        const filterOptions = section === "recent"
            ? (
                safePayload.filter_options &&
                typeof safePayload.filter_options === "object"
                    ? safePayload.filter_options
                    : {}
            )
            : buildListingFilterOptions(explorer, safeDocs, section);
        const selectedFilters = (
            section === "recent" &&
            safePayload.filters &&
            typeof safePayload.filters === "object"
        )
            ? safePayload.filters
            : sectionChanged
                ? {}
                : getRecentFilterState(explorer);

        RECENT_FILTER_FIELDS.forEach(function (fieldName) {
            const control = getRecentFilterControl(explorer, fieldName);

            if (!control) {
                return;
            }

            while (control.firstChild) {
                control.removeChild(control.firstChild);
            }

            const defaultOption = document.createElement("option");
            const defaultLabel = RECENT_FILTER_LABELS[fieldName] || fieldName;

            defaultOption.value = "";
            defaultOption.textContent = defaultLabel;
            control.appendChild(defaultOption);

            (Array.isArray(filterOptions[fieldName])
                ? filterOptions[fieldName]
                : []
            ).forEach(function (option) {
                const optionNode = createRecentFilterOption(option);

                if (optionNode.value) {
                    control.appendChild(optionNode);
                }
            });

            const selectedValue = cleanValue(selectedFilters[fieldName]);
            const hasAvailableOptions = control.options.length > 1;
            const controlContainer = control.closest(
                "[data-document-recent-filter-control]"
            );

            control.value = Array.from(control.options).some(function (option) {
                return option.value === selectedValue;
            }) ? selectedValue : "";
            control.disabled = !hasAvailableOptions;
            control.setAttribute(
                "data-document-recent-filter-active",
                control.value ? "true" : "false"
            );

            if (controlContainer) {
                controlContainer.setAttribute(
                    "data-document-listing-filter-available",
                    hasAvailableOptions ? "true" : "false"
                );
            }
        });

        form.setAttribute("data-document-recent-filters-ready", "true");
        form.setAttribute("data-document-listing-filters-ready", "true");
        form.setAttribute("data-document-filter-section", section);
        form.setAttribute("aria-busy", "false");

        const resolvedState = getRecentFilterState(explorer);
        const isFiltered = hasActiveRecentFilters(resolvedState);
        const clearButton = form.querySelector(RECENT_FILTER_CLEAR_SELECTOR);
        const status = form.querySelector(RECENT_FILTER_STATUS_SELECTOR);
        const visibleCount = section === "recent"
            ? Number(safePayload.count || 0)
            : filterDocumentsForCurrentView(
                explorer,
                safeDocs,
                section
            ).length;
        const totalCount = section === "recent"
            ? Number(safePayload.unfiltered_count || visibleCount)
            : safeDocs.length;

        if (clearButton) {
            clearButton.hidden = !isFiltered;
            clearButton.setAttribute("aria-hidden", isFiltered ? "false" : "true");
        }

        if (status) {
            status.textContent = isFiltered
                ? `${visibleCount} of ${totalCount} items`
                : "";
        }

        explorer.setAttribute("data-document-listing-filtered", isFiltered ? "true" : "false");
        explorer.setAttribute("data-document-listing-visible-count", String(visibleCount));
        explorer.setAttribute("data-document-listing-unfiltered-count", String(totalCount));

        if (section === "recent") {
            explorer.setAttribute("data-document-recent-filtered", isFiltered ? "true" : "false");
            explorer.setAttribute("data-document-recent-visible-count", String(visibleCount));
            explorer.setAttribute("data-document-recent-unfiltered-count", String(totalCount));
            syncRecentFilterLocation(resolvedState);
        }
    }

    function syncRecentFilteredEmptyState(explorer) {
        if (!explorer) {
            return;
        }

        const state = getRecentFilterState(explorer);

        if (!hasActiveRecentFilters(state)) {
            return;
        }

        const list = explorer.querySelector(FILE_LIST_SELECTOR);
        const emptyState = list?.querySelector(".workspace-document-empty-state");
        const emptyTitle = emptyState?.querySelector(
            ".workspace-document-empty-title, strong"
        );
        const emptyMessage = emptyState?.querySelector(
            ".workspace-document-empty-message, p"
        );

        if (emptyTitle) {
            emptyTitle.textContent = "No matching items";
        }

        if (emptyMessage) {
            emptyMessage.textContent = "Try clearing one or more filters.";
        }
    }

    function setRecentFilterBusy(explorer, busy) {
        const form = getRecentFilterForm(explorer);
        const status = form?.querySelector(RECENT_FILTER_STATUS_SELECTOR);

        if (!form) {
            return;
        }

        form.setAttribute("aria-busy", busy ? "true" : "false");

        if (busy && status) {
            status.textContent = "Filtering…";
        } else if (status?.textContent === "Filtering…") {
            status.textContent = "";
        }
    }

    function handleRecentFilterChange(event, explorer) {
        const control = event?.target?.closest?.(RECENT_FILTER_CONTROL_SELECTOR);

        if (!control || !explorer?.contains(control)) {
            return false;
        }

        control.setAttribute(
            "data-document-recent-filter-active",
            control.value ? "true" : "false"
        );

        const section = normalizeDocumentSection(
            explorer.getAttribute("data-workspace-section") || "files"
        );
        const state = getRecentFilterState(explorer);

        setRecentFilterBusy(explorer, true);

        if (section === "recent") {
            syncRecentFilterLocation(state);
            refreshFiles(explorer, {
                quiet: true,
                section: "recent",
                source: "recent_filter_change"
            });
            return true;
        }

        const sourceDocs = getDocumentFilterSource(explorer, section);

        renderCurrentDocumentSection(explorer, sourceDocs, {
            forceRender: true,
            renderOrigin: "listing_filter_change",
            section
        });
        syncRecentFilterControls(explorer, {}, sourceDocs, section);
        syncRecentFilteredEmptyState(explorer);
        setRecentFilterBusy(explorer, false);
        return true;
    }

    function handleRecentFilterClear(event, explorer) {
        const button = event?.target?.closest?.(RECENT_FILTER_CLEAR_SELECTOR);

        if (!button || !explorer?.contains(button)) {
            return false;
        }

        event.preventDefault();

        RECENT_FILTER_FIELDS.forEach(function (fieldName) {
            const control = getRecentFilterControl(explorer, fieldName);

            if (control) {
                control.value = "";
                control.setAttribute("data-document-recent-filter-active", "false");
            }
        });

        const section = normalizeDocumentSection(
            explorer.getAttribute("data-workspace-section") || "files"
        );
        const state = getRecentFilterState(explorer);

        setRecentFilterBusy(explorer, true);

        if (section === "recent") {
            syncRecentFilterLocation(state);
            refreshFiles(explorer, {
                quiet: true,
                section: "recent",
                source: "recent_filter_clear"
            });
            return true;
        }

        const sourceDocs = getDocumentFilterSource(explorer, section);

        renderCurrentDocumentSection(explorer, sourceDocs, {
            forceRender: true,
            renderOrigin: "listing_filter_clear",
            section
        });
        syncRecentFilterControls(explorer, {}, sourceDocs, section);
        setRecentFilterBusy(explorer, false);
        return true;
    }

    function handleRecentFilterSubmit(event, explorer) {
        const form = event?.target?.closest?.(RECENT_FILTER_FORM_SELECTOR);

        if (!form || !explorer?.contains(form)) {
            return false;
        }

        event.preventDefault();
        return true;
    }


    function getDocumentSelectionOptions(options) {
        const cleanOptions = options || {};
        const selectors = Object.assign({}, cleanOptions.selectors || {}, {
            documentRow: DOCUMENT_ROW_SELECTOR,
            selectionRail: DOCUMENT_SELECTION_RAIL_SELECTOR,
            selectionRow: DOCUMENT_SELECTION_ROW_SELECTOR,
            selectionCheckbox: DOCUMENT_SELECTION_CHECKBOX_SELECTOR
        });

        return Object.assign({}, cleanOptions, {
            Records,
            Library,
            Conversation,
            selectors,
            normalizeDocumentSection,
            isTrashSection
        });
    }

    function getDocumentInteractionOptions() {
        const Share = window.SolomonWorkspaceDocumentShare;

        return {
            rowSelector: DOCUMENT_ROW_SELECTOR,
            actionMenuSelector: DOCUMENT_ACTION_MENU_SELECTOR,
            actionMenuButtonSelector: DOCUMENT_ACTION_MENU_BUTTON_SELECTOR,
            actionMenuItemSelector: DOCUMENT_ACTION_MENU_ITEM_SELECTOR,
            sharedListingSelectEvent: SHARED_LISTING_SELECT_EVENT,
            getDocumentRows,
            selectFile,
            openDocument,
            isDocumentInTrashContext,
            hasAnyDocumentInTrashContext,
            hasAnyDocumentOutsideTrashContext,
            updateSelectionFromRows: updateExplorerSelectionFromRows,
            setDocumentRowSelected,
            setDocumentRowsSelectedByIds,
            getActionSelectionFromMenuItem: getDocumentActionSelectionFromMenuItem,
            showFileDetails,
            showFileSummary,
            runSolomonAction: runSolomonFileAction,
            openShare: function (_explorer, documentIds, payload) {
                if (!Share || typeof Share.open !== "function") {
                    return;
                }
                Share.open({
                    documentIds: Array.isArray(documentIds) ? documentIds : [],
                    documentNames: Array.isArray(payload?.documentNames) ? payload.documentNames : []
                });
            },
            requestSolomonAiSession: requestSolomonAiConversation,
            requestSolomonAiConversation,
            requestBidScopeReviewHandoff,
            requestMoveDocumentToTrash,
            restoreDocumentFromTrash,
            requestPermanentDeleteDocument,
            showStatus: function (explorer, payload) {
                Status.show(explorer, payload);
            }
        };
    }

    function getDocumentSectionNavigationOptions(options) {
        const cleanOptions = options || {};
        const selectors = Object.assign({}, cleanOptions.selectors || {}, {
            fileList: FILE_LIST_SELECTOR,
            sectionLink: DOCUMENT_SECTION_LINK_SELECTOR,
            sectionTitle: DOCUMENT_SECTION_TITLE_SELECTOR,
            refreshButton: DOCUMENT_REFRESH_BUTTON_SELECTOR,
            uploadTrigger: UPLOAD_TRIGGER_SELECTOR,
            documentRow: DOCUMENT_ROW_SELECTOR
        });

        return Object.assign({}, cleanOptions, {
            Sections,
            Conversation,
            Status,
            selectors,
            defaultSection: "files",
            routes: {
                files: "/",
                reports: "/reports",
                recent: "/recent",
                trash: "/trash"
            },
            resetDocumentSelection,
            renderPreviewEmpty,
            renderEmptyFiles: Library.renderEmptyFiles,
            renderFiles,
            renderTrashFiles,
            refreshFiles,
            cacheDocuments,
            getCachedDocumentSection,
            getFallbackDocuments: function (explorer) {
                return Array.isArray(explorer?.__solomonDocuments) ? explorer.__solomonDocuments : [];
            },
            getInitialDocuments: function (explorer) {
                return getInitialDocuments(explorer);
            },
            openUploadPicker,
            normalizeDocumentSection,
            isFetchableDocumentSection,
            getDocumentSectionLabel,
            getDocumentSectionIcon,
            getDocumentSectionEmptyState: Sections.getDocumentSectionEmptyState,
            getDocumentSectionEmptyCopy: Sections.getDocumentSectionEmptyCopy
        });
    }

    function getDocumentReaderLifecycleOptions(options) {
        const cleanOptions = options || {};
        const selectors = Object.assign({}, cleanOptions.selectors || {}, {
            viewButton: WORKSPACE_VIEW_BUTTON_SELECTOR,
            viewPanel: WORKSPACE_VIEW_PANEL_SELECTOR,
            readerPanel: WORKSPACE_READER_PANEL_SELECTOR,
            readerController: READER_CONTROLLER_SELECTOR
        });

        return Object.assign({}, cleanOptions, {
            Conversation,
            selectors,
            defaultWorkspaceView: DEFAULT_WORKSPACE_VIEW,
            readerWorkspaceView: READER_WORKSPACE_VIEW,
            validWorkspaceViews: VALID_WORKSPACE_VIEWS,
            readerRoutePattern: READER_ROUTE_PATTERN,
            readerFragmentRoutePattern: READER_FRAGMENT_ROUTE_PATTERN
        });
    }

    function getDocumentTrashMutationOptions(options) {
        const cleanOptions = options || {};

        return Object.assign({}, cleanOptions, {
            Records,
            Status,
            getEndpoint,
            fetchJson,
            normalizeDocumentSection,
            getCachedDocumentSection,
            setCachedDocumentSection,
            invalidateDocumentSectionCache,
            removeDocumentRowsFromCurrentView,
            renderPreviewEmpty,
            renderDeleteConfirmation,
            refreshAfterDocumentMutation,
            getDocumentNamesByIds,
            getDocumentSelectionLabel,
            showStatus: function (explorer, payload) {
                Status.show(explorer, payload);
            },
            getConfirmApi
        });
    }

    function handleServerOwnedDocumentSortChange(explorer, sort, section) {
        const cleanSection = normalizeDocumentSection(section);
        const authority = getRecentSortAuthority(explorer);

        if (cleanSection !== "recent" || !authority) {
            return false;
        }

        const requestedKey = cleanValue(sort?.key).toLowerCase();
        const requestedDirection = cleanValue(sort?.direction).toLowerCase();

        if (
            !authority.allowedKeys.includes(requestedKey) ||
            !authority.allowedDirections.includes(requestedDirection)
        ) {
            return false;
        }

        syncRecentSortLocation({
            sort: requestedKey,
            direction: requestedDirection
        });
        refreshFiles(explorer, {
            section: "recent",
            source: "recent_sort_change",
            forceRender: true
        });
        return true;
    }

    function getDocumentViewStateOptions(options) {
        const cleanOptions = options || {};
        const explorer = cleanOptions.explorer || null;
        const section = normalizeDocumentSection(
            explorer?.getAttribute("data-workspace-section") || "files"
        );
        const recentSortAuthority = section === "recent"
            ? getRecentSortAuthority(explorer)
            : null;
        const selectors = Object.assign({}, cleanOptions.selectors || {}, {
            collection: COLLECTION_SELECTOR,
            layoutButton: DOCUMENT_LAYOUT_BUTTON_SELECTOR,
            sortControl: DOCUMENT_SORT_CONTROL_SELECTOR,
            sortTrigger: DOCUMENT_SORT_TRIGGER_SELECTOR,
            sortMenu: DOCUMENT_SORT_MENU_SELECTOR,
            sortOption: DOCUMENT_SORT_OPTION_SELECTOR,
            columnSort: DOCUMENT_COLUMN_SORT_SELECTOR
        });
        const sortOptions = recentSortAuthority
            ? recentSortAuthority.options
            : [];
        const sortKeyLabels = {};
        const sortDefaultDirections = {};
        const sortDirectionModes = {};

        sortOptions.forEach(function (option) {
            sortKeyLabels[option.value] = option.label;
            sortDefaultDirections[option.value] = option.defaultDirection;
            sortDirectionModes[option.value] = option.directionMode;
        });

        return Object.assign({}, cleanOptions, {
            Records,
            Conversation,
            selectors,
            layoutStorageKey: DOCUMENT_LAYOUT_STORAGE_KEY,
            sortStorageKey: DOCUMENT_SORT_STORAGE_KEY,
            defaultLayout: DEFAULT_DOCUMENT_LAYOUT,
            defaultSortKey: recentSortAuthority
                ? recentSortAuthority.defaultKey
                : DEFAULT_DOCUMENT_SORT_KEY,
            defaultSortDirection: recentSortAuthority
                ? recentSortAuthority.defaultDirection
                : DEFAULT_DOCUMENT_SORT_DIRECTION,
            defaultSortFolders: DEFAULT_DOCUMENT_SORT_FOLDERS,
            validSortKeys: recentSortAuthority
                ? recentSortAuthority.allowedKeys
                : VALID_DOCUMENT_SORT_KEYS,
            validSortDirections: recentSortAuthority
                ? recentSortAuthority.allowedDirections
                : VALID_DOCUMENT_SORT_DIRECTIONS,
            validSortFolders: VALID_DOCUMENT_SORT_FOLDERS,
            sortKeyLabels,
            sortDefaultDirections,
            sortDirectionModes,
            sortFolderPlacementEnabled: recentSortAuthority
                ? recentSortAuthority.folderPlacementSupported
                : true,
            persistSort: !recentSortAuthority,
            onSortChange: recentSortAuthority
                ? handleServerOwnedDocumentSortChange
                : null,
            isFolderDocumentRecord,
            normalizeWorkspaceView,
            normalizeDocumentSection,
            getCachedDocumentSection: getDocumentFilterSource,
            renderCurrentDocumentSection,
            renderCurrentSectionFromCache,
            enableDocumentSorting: true
        });
    }

    function getSelectionRail(explorer) {
        return Selection.getSelectionRail(explorer, getDocumentSelectionOptions());
    }

    function getSelectionRow(explorer) {
        return Selection.getSelectionRow(explorer, getDocumentSelectionOptions());
    }

    function setNodeVisibility(node, visible) {
        if (!node) {
            return;
        }

        node.hidden = !visible;
        node.setAttribute("aria-hidden", visible ? "false" : "true");

        if (visible) {
            node.removeAttribute("hidden");
            node.style.removeProperty("display");
        }
    }

    function setSelectionRailVisibility(explorer, state) {
        const selectionRow = getSelectionRow(explorer);
        const rail = getSelectionRail(explorer);
        const defaultUtility = selectionRow?.querySelector(DOCUMENT_DEFAULT_UTILITY_SELECTOR) || null;
        const cleanState = cleanValue(state) || "empty";
        const isSelectionActive = cleanState !== "empty";

        if (selectionRow) {
            selectionRow.hidden = false;
            selectionRow.removeAttribute("hidden");
            selectionRow.setAttribute("data-document-selection-state", cleanState);
            selectionRow.setAttribute(
                "data-document-selection-count",
                isSelectionActive ? cleanValue(rail?.getAttribute("data-document-selection-count")) || "1" : "0"
            );
            selectionRow.setAttribute("aria-hidden", "false");
            selectionRow.style.removeProperty("display");
        }

        setNodeVisibility(defaultUtility, true);

        if (rail) {
            rail.setAttribute("data-document-selection-state", cleanState);
            setNodeVisibility(rail, isSelectionActive);
        }
    }

    function splitDocumentValueList(value, separator) {
        return Selection.splitDocumentValueList(value, separator);
    }

    function uniqueDocumentValues(values) {
        return Selection.uniqueDocumentValues(values);
    }

    function getDocumentSelectionLabel(count) {
        return Selection.getDocumentSelectionLabel(count);
    }

    function getDocumentRows(explorer) {
        return Selection.getDocumentRows(explorer, getDocumentSelectionOptions());
    }

    function getSelectedDocumentRows(explorer) {
        return Selection.getSelectedDocumentRows(explorer, getDocumentSelectionOptions());
    }

    function getDocumentIdsFromRows(rows) {
        return Selection.getDocumentIdsFromRows(rows);
    }

    function getDocumentNamesFromRows(rows) {
        return Selection.getDocumentNamesFromRows(rows);
    }

    function getDocumentRecordsFromRows(explorer, rows) {
        return Selection.getDocumentRecordsFromRows(explorer, rows, getDocumentSelectionOptions());
    }

    function getDocumentRecordsByIds(explorer, documentIds) {
        return Selection.getDocumentRecordsByIds(explorer, documentIds, getDocumentSelectionOptions());
    }

    function getDocumentNamesByIds(explorer, documentIds) {
        return Selection.getDocumentNamesByIds(explorer, documentIds, getDocumentSelectionOptions());
    }

    function setDocumentRowSelected(row, selected) {
        Selection.setDocumentRowSelected(row, selected, getDocumentSelectionOptions());
    }

    function setOnlyDocumentRowSelected(explorer, row) {
        Selection.setOnlyDocumentRowSelected(explorer, row, getDocumentSelectionOptions());
    }

    function setDocumentRowsSelectedByIds(explorer, documentIds) {
        Selection.setDocumentRowsSelectedByIds(explorer, documentIds, getDocumentSelectionOptions());
    }

    function getActionDocumentPayload(action, primaryAttributeName) {
        return Selection.getActionDocumentPayload(action, primaryAttributeName);
    }

    function getDocumentActionSelectionFromMenuItem(actionItem) {
        return Selection.getDocumentActionSelectionFromMenuItem(actionItem);
    }

    function normalizeSharedListingActionName(value) {
        return cleanValue(value)
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "_")
            .replace(/^_+|_+$/g, "");
    }

    function isSharedListingManagedRow(row) {
        if (!row || typeof Interactions.isSharedListingRow !== "function") {
            return false;
        }

        return Interactions.isSharedListingRow(row, getDocumentInteractionOptions());
    }

    function getDocumentActionMenuItemFromSharedListingEvent(event, row) {
        const actionElement = event?.detail?.actionElement;
        const actionName = normalizeSharedListingActionName(event?.detail?.action);

        if (actionElement?.matches?.(DOCUMENT_ACTION_MENU_ITEM_SELECTOR)) {
            return actionElement;
        }

        if (actionElement?.closest) {
            const closestItem = actionElement.closest(DOCUMENT_ACTION_MENU_ITEM_SELECTOR);

            if (closestItem) {
                return closestItem;
            }
        }

        if (!row || !actionName) {
            return null;
        }

        return Array.from(row.querySelectorAll(DOCUMENT_ACTION_MENU_ITEM_SELECTOR)).find(function (item) {
            return normalizeSharedListingActionName(
                item.getAttribute("data-document-action-menu-item")
            ) === actionName;
        }) || null;
    }

    function getSelectionSummaryName(documentIds, documentNames) {
        return Selection.getSelectionSummaryName(documentIds, documentNames);
    }

    function isDocumentRecordTrashed(doc) {
        return Selection.isDocumentRecordTrashed(doc, getDocumentSelectionOptions());
    }

    function hasAnyDocumentInTrashContext(explorer, documentIds) {
        return Selection.hasAnyDocumentInTrashContext(explorer, documentIds, getDocumentSelectionOptions());
    }

    function hasAnyDocumentOutsideTrashContext(explorer, documentIds) {
        return Selection.hasAnyDocumentOutsideTrashContext(explorer, documentIds, getDocumentSelectionOptions());
    }

    function updateExplorerSelectionFromRows(explorer, options) {
        return Selection.updateExplorerSelectionFromRows(explorer, getDocumentSelectionOptions(options));
    }

    function hasRenderableSelection(selection) {
        const values = Array.isArray(selection) ? selection : [selection];

        return values.some(function (doc) {
            return Boolean(doc?.document_id || doc?.random_name);
        });
    }

    function renderSelectionRailEmpty(explorer) {
        Selection.renderSelectionRailEmpty(explorer, getDocumentSelectionOptions());
        setSelectionRailVisibility(explorer, "empty");
    }

    function renderSelectionRail(explorer, selection, options) {
        const state = hasRenderableSelection(selection) ? "selected" : "empty";

        Selection.renderSelectionRail(
            explorer,
            selection,
            getDocumentSelectionOptions(options)
        );
        if (window.SolomonWorkspaceDocumentShare?.syncSelectionRail) {
            window.SolomonWorkspaceDocumentShare.syncSelectionRail(explorer, selection);
        }
        setSelectionRailVisibility(
            explorer,
            cleanValue(getSelectionRail(explorer)?.getAttribute("data-document-selection-state")) || state
        );
    }

    function isFolderDocumentRecord(doc) {
        if (typeof Selection.isFolderDocumentRecord === "function") {
            return Selection.isFolderDocumentRecord(doc, getDocumentSelectionOptions());
        }

        const itemType = cleanValue(
            doc?.workspace_item_type ||
            doc?.item_type ||
            doc?.resource_type ||
            doc?.document_kind ||
            doc?.object_type ||
            doc?.kind ||
            doc?.document_type ||
            doc?.type
        ).toLowerCase();
        const containerType = cleanValue(
            doc?.container_type ||
            doc?.workspace_container_type
        ).toLowerCase();

        return Boolean(
            itemType === "folder" ||
            containerType === "workspace_folder" ||
            doc?.folder === true ||
            doc?.is_folder === true
        );
    }

    function getFolderDocumentId(doc) {
        if (!isFolderDocumentRecord(doc)) {
            return "";
        }

        return cleanValue(
            doc?.folder_id ||
            doc?.workspace_item_id ||
            doc?.object_id ||
            doc?.random_name ||
            doc?.document_id
        );
    }

    function getFolderRouteCandidate(value) {
        const route = cleanValue(value);

        if (!route || route === "#") {
            return "";
        }

        const sameOriginUrl = getSameOriginUrl(route);

        if (
            sameOriginUrl &&
            isWorkspaceReaderRoutePath(sameOriginUrl.pathname)
        ) {
            return "";
        }

        return sameOriginUrl ? getRelativeUrl(sameOriginUrl) : "";
    }

    function getFolderOpenRouteFromRecord(doc) {
        if (!isFolderDocumentRecord(doc)) {
            return "";
        }

        return [
            doc?.folder_url,
            doc?.folderUrl,
            doc?.canonical_url,
            doc?.canonicalUrl,
            doc?.workspace_object_route,
            doc?.workspaceObjectRoute,
            doc?.object_route,
            doc?.objectRoute,
            doc?.open_url,
            doc?.openUrl,
            doc?.route,
            doc?.url
        ].map(getFolderRouteCandidate).find(Boolean) || "";
    }

    function getFolderOpenRouteFromRow(row) {
        if (!row || row.getAttribute("data-document-folder") !== "true") {
            return "";
        }

        return [
            row.getAttribute("data-document-open-route"),
            row.getAttribute("data-workspace-object-open-route"),
            row.getAttribute("data-workspace-object-route"),
            row.getAttribute("data-document-route"),
            row.getAttribute("data-command-route")
        ].map(getFolderRouteCandidate).find(Boolean) || "";
    }

    function buildFolderFallbackRoute(doc, row) {
        const folderId = (
            getFolderDocumentId(doc) ||
            cleanValue(row?.getAttribute("data-workspace-folder-id")) ||
            cleanValue(row?.getAttribute("data-folder-id")) ||
            cleanValue(row?.getAttribute("data-document-id"))
        );

        return folderId
            ? `/?folder_id=${encodeURIComponent(folderId)}`
            : "";
    }

    function getFolderOpenRoute(doc, row) {
        if (!isFolderDocumentRecord(doc)) {
            return "";
        }

        return (
            getFolderOpenRouteFromRecord(doc) ||
            getFolderOpenRouteFromRow(row) ||
            buildFolderFallbackRoute(doc, row)
        );
    }

    function appendFolderReturnRoute(folderRoute, returnRoute) {
        const parsedFolderRoute = getSameOriginUrl(folderRoute);
        const cleanReturnRoute = getSameOriginRelativeRoute(returnRoute);

        if (!parsedFolderRoute || !cleanReturnRoute) {
            return folderRoute;
        }

        parsedFolderRoute.searchParams.set(
            "return_to",
            cleanReturnRoute
        );

        return getRelativeUrl(parsedFolderRoute);
    }

    function openFolderDocument(explorer, doc, options) {
        const cleanOptions = options || {};
        const row = cleanOptions.row || null;
        const folderId = getFolderDocumentId(doc) ||
            cleanValue(row?.getAttribute("data-workspace-folder-id")) ||
            cleanValue(row?.getAttribute("data-folder-id")) ||
            cleanValue(row?.getAttribute("data-document-id"));
        const folderRoute = getFolderOpenRoute(doc, row);
        const navigationRoute = appendFolderReturnRoute(
            folderRoute,
            getCurrentRelativeRoute()
        );

        if (!folderRoute) {
            Status.show(explorer, {
                action: "open_folder",
                documentIds: folderId ? [folderId] : [],
                variant: "info",
                message: "Folder navigation is not available for this folder."
            });
            return false;
        }

        Conversation.markFilesViewIntent(explorer);
        Conversation.returnToFiles(explorer);
        restoreWorkspaceView(explorer, DEFAULT_WORKSPACE_VIEW);

        loadRightPaneRoute(
            navigationRoute,
            getWorkspaceModuleForRoute(navigationRoute, "documents"),
            {
                push: true,
                async: true,
                launchMode: "folder",
                source: cleanValue(cleanOptions.source) ||
                    "workspace_document_viewer_open_folder",
                folderId
            }
        );

        return true;
    }

    function getDocuments(payload) {
        if (Array.isArray(payload?.workspace_items)) {
            return payload.workspace_items;
        }

        if (Array.isArray(payload?.items)) {
            return payload.items;
        }

        if (Array.isArray(payload?.uploads)) {
            return payload.uploads;
        }

        if (Array.isArray(payload?.docs)) {
            return payload.docs;
        }

        return [];
    }

    function getInitialDocuments(explorer) {
        if (Records && typeof Records.getInitialDocuments === "function") {
            return Records.getInitialDocuments(explorer);
        }

        if (!explorer) {
            return [];
        }

        const section = normalizeDocumentSection(
            explorer.getAttribute("data-workspace-section") || "files"
        );
        const cachedDocs = getCachedDocumentSection(explorer, section);

        if (Array.isArray(cachedDocs)) {
            return cachedDocs;
        }

        if (Array.isArray(explorer.__solomonDocuments)) {
            return explorer.__solomonDocuments;
        }

        return [];
    }

    function setDocumentListState(explorer, section, state) {
        SectionNavigation.setDocumentListState(explorer, section, state, getDocumentSectionNavigationOptions());
    }

    function getServerReaderUrl(payload) {
        return ReaderLifecycle.getServerReaderUrl(payload);
    }

    function getRelativeUrl(parsedUrl) {
        return `${parsedUrl.pathname}${parsedUrl.search}${parsedUrl.hash}`;
    }

    function getSameOriginUrl(route) {
        const cleanRoute = cleanValue(route);

        if (!cleanRoute) {
            return null;
        }

        try {
            const parsedUrl = new URL(
                cleanRoute,
                window.location.origin
            );

            return parsedUrl.origin === window.location.origin
                ? parsedUrl
                : null;
        } catch (_error) {
            return null;
        }
    }

    function getSameOriginRelativeRoute(route) {
        const parsedUrl = getSameOriginUrl(route);

        return parsedUrl ? getRelativeUrl(parsedUrl) : "";
    }

    function getCurrentRelativeRoute() {
        return `${window.location.pathname || "/"}${window.location.search || ""}${window.location.hash || ""}`;
    }

    function isWorkspaceReaderRoutePath(pathname) {
        const cleanPath = String(pathname || "")
            .trim()
            .replace(/\/+$/, "") || "/";

        return (
            READER_ROUTE_PATTERN.test(cleanPath) ||
            READER_FRAGMENT_ROUTE_PATTERN.test(cleanPath)
        );
    }

    function normalizeSafeReaderBackRoute(route) {
        const cleanRoute = cleanValue(route);
        let parsedUrl = null;

        if (!cleanRoute) {
            return "";
        }

        try {
            parsedUrl = new URL(
                cleanRoute,
                window.location.origin
            );
        } catch (_error) {
            return "";
        }

        if (parsedUrl.origin !== window.location.origin) {
            return "";
        }

        if (!parsedUrl.pathname.startsWith("/")) {
            return "";
        }

        if (isWorkspaceReaderRoutePath(parsedUrl.pathname)) {
            return "";
        }

        return getRelativeUrl(parsedUrl);
    }

    function getWorkspaceSectionReaderBackRoute(explorer) {
        const section = normalizeDocumentSection(
            explorer?.getAttribute("data-workspace-section") ||
            "files"
        );

        if (section === "recent") {
            return buildRecentPageRoute(
                getRecentFilterState(explorer),
                getRecentSortRequestState(explorer)
            );
        }

        if (section === "trash") {
            return "/trash";
        }

        if (section === "reports") {
            return "/reports";
        }

        return "/";
    }

    function getReaderPanelBackRoute(explorer) {
        const readerPanel = getReaderPanel(explorer);

        return normalizeSafeReaderBackRoute(
            readerPanel?.getAttribute("data-workspace-reader-back-route") ||
            readerPanel?.getAttribute("data-right-pane-content-back-route") ||
            ""
        );
    }

    function getExplorerStampedBackRoute(explorer) {
        return normalizeSafeReaderBackRoute(
            explorer?.dataset?.workspaceReaderBackRoute ||
            explorer?.getAttribute("data-workspace-reader-back-route") ||
            explorer?.getAttribute("data-right-pane-content-back-route") ||
            explorer?.getAttribute("data-right-pane-content-route") ||
            explorer?.getAttribute("data-workspace-route") ||
            ""
        );
    }

    function getHistoryReaderBackRoute() {
        return normalizeSafeReaderBackRoute(
            window.history?.state?.readerBackRoute ||
            window.history?.state?.backRoute ||
            ""
        );
    }

    function getReaderBackRouteFromReaderUrl(readerUrl) {
        const parsedUrl = getSameOriginUrl(readerUrl);

        if (!parsedUrl || !isWorkspaceReaderRoutePath(parsedUrl.pathname)) {
            return "";
        }

        return normalizeSafeReaderBackRoute(
            parsedUrl.searchParams.get("back") || ""
        );
    }

    function getReaderCallerBackRoute(explorer, options) {
        const cleanOptions = options || {};
        const optionBackRoute = normalizeSafeReaderBackRoute(cleanOptions.backRoute);
        const readerUrlBackRoute = getReaderBackRouteFromReaderUrl(cleanOptions.readerUrl);
        const currentRoute = normalizeSafeReaderBackRoute(
            getCurrentRelativeRoute()
        );

        return (
            optionBackRoute ||
            readerUrlBackRoute ||
            getReaderBackRouteFromLocation() ||
            getExplorerStampedBackRoute(explorer) ||
            getReaderPanelBackRoute(explorer) ||
            getHistoryReaderBackRoute() ||
            currentRoute ||
            getWorkspaceSectionReaderBackRoute(explorer)
        );
    }

    function appendReaderBackRoute(readerUrl, backRoute) {
        const cleanReaderUrl = cleanValue(readerUrl);
        const cleanBackRoute = normalizeSafeReaderBackRoute(backRoute);
        let parsedUrl = null;

        if (!cleanReaderUrl) {
            return "";
        }

        try {
            parsedUrl = new URL(
                cleanReaderUrl,
                window.location.origin
            );
        } catch (_error) {
            return cleanReaderUrl;
        }

        if (parsedUrl.origin !== window.location.origin) {
            return cleanReaderUrl;
        }

        if (!isWorkspaceReaderRoutePath(parsedUrl.pathname)) {
            return getRelativeUrl(parsedUrl);
        }

        if (parsedUrl.searchParams.has("back")) {
            return getRelativeUrl(parsedUrl);
        }

        if (cleanBackRoute) {
            parsedUrl.searchParams.set(
                "back",
                cleanBackRoute
            );
        }

        return getRelativeUrl(parsedUrl);
    }

    function getReaderBackRouteFromLocation() {
        let currentUrl = null;

        try {
            currentUrl = new URL(window.location.href);
        } catch (_error) {
            return "";
        }

        return normalizeSafeReaderBackRoute(
            currentUrl.searchParams.get("back") || ""
        );
    }

    function getReaderCloseBackRoute(explorer) {
        return (
            getReaderBackRouteFromLocation() ||
            getExplorerStampedBackRoute(explorer) ||
            getReaderPanelBackRoute(explorer) ||
            getHistoryReaderBackRoute() ||
            getReaderCallerBackRoute(explorer)
        );
    }

    function getWorkspaceModuleForRoute(route, fallbackModule) {
        const parsedUrl = getSameOriginUrl(route);

        if (!parsedUrl) {
            return fallbackModule || "documents";
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

        return fallbackModule || "documents";
    }

    function fallbackToRightPaneRoute(route) {
        const cleanRoute = cleanValue(route);

        if (!cleanRoute) {
            return false;
        }

        window.location.assign(cleanRoute);
        return false;
    }

    function loadRightPaneRoute(route, moduleId, options) {
        const relativeRoute = getSameOriginRelativeRoute(route);
        const cleanRoute = relativeRoute || cleanValue(route);
        const sidebarApi = window.NationsCommandSidebar || null;

        if (!cleanRoute) {
            return false;
        }

        if (
            relativeRoute &&
            sidebarApi &&
            typeof sidebarApi.loadWorkspace === "function"
        ) {
            try {
                const result = sidebarApi.loadWorkspace(
                    relativeRoute,
                    moduleId || getWorkspaceModuleForRoute(relativeRoute),
                    Object.assign(
                        {
                            push: true,
                            async: true,
                            source: "workspace_document_viewer"
                        },
                        options || {}
                    )
                );

                if (result && typeof result.then === "function") {
                    result.then(function (resolved) {
                        if (resolved === false) {
                            fallbackToRightPaneRoute(relativeRoute);
                        }
                    }).catch(function (error) {
                        console.warn(
                            "[DOCUMENT_VIEWER][RIGHT_PANE] Async launch failed; falling back to hard navigation.",
                            error
                        );
                        fallbackToRightPaneRoute(relativeRoute);
                    });
                } else if (result === false) {
                    fallbackToRightPaneRoute(relativeRoute);
                }

                return true;
            } catch (error) {
                console.warn(
                    "[DOCUMENT_VIEWER][RIGHT_PANE] Async launch failed; falling back to hard navigation.",
                    error
                );
                fallbackToRightPaneRoute(relativeRoute);
                return true;
            }
        }

        return fallbackToRightPaneRoute(cleanRoute);
    }

    function navigateToReaderBackRoute(backRoute) {
        const cleanBackRoute = normalizeSafeReaderBackRoute(backRoute);

        if (!cleanBackRoute) {
            return false;
        }

        return loadRightPaneRoute(
            cleanBackRoute,
            getWorkspaceModuleForRoute(cleanBackRoute),
            {
                push: true,
                launchMode: "reader_close",
                source: "workspace_document_viewer_reader_close",
                backRoute: cleanBackRoute
            }
        ) !== false;
    }

    function getDocumentActionName(explorer, documentId) {
        return Selection.getDocumentActionName(explorer, documentId, getDocumentSelectionOptions());
    }

    function getDocumentActionRecord(explorer, documentId) {
        return Selection.getDocumentActionRecord(explorer, documentId, getDocumentSelectionOptions());
    }

    function hasFolderDocumentActionTarget(explorer, documentIds) {
        return uniqueDocumentValues(documentIds).some(function (documentId) {
            return isFolderDocumentRecord(getDocumentActionRecord(explorer, documentId));
        });
    }

    function rejectFolderDocumentAction(explorer, action, documentIds, message) {
        const ids = uniqueDocumentValues(documentIds);

        if (!ids.length || !hasFolderDocumentActionTarget(explorer, ids)) {
            return false;
        }

        Status.show(explorer, {
            action: action || "folder_action",
            documentIds: ids,
            variant: "info",
            message: message || "This action runs on files only."
        });

        return true;
    }

    function partitionFolderLifecycleTargets(explorer, documentIds) {
        const folderIds = [];
        const fileIds = [];

        uniqueDocumentValues(documentIds).forEach(function (documentId) {
            if (isFolderDocumentRecord(getDocumentActionRecord(explorer, documentId))) {
                folderIds.push(documentId);
                return;
            }

            fileIds.push(documentId);
        });

        return {
            folderIds,
            fileIds
        };
    }

    function rejectMixedFolderLifecycleTargets(explorer, action, targets) {
        if (!targets?.folderIds?.length || !targets?.fileIds?.length) {
            return false;
        }

        const ids = uniqueDocumentValues([
            ...targets.folderIds,
            ...targets.fileIds
        ]);

        Status.show(explorer, {
            action: action || "folder_lifecycle",
            documentIds: ids,
            variant: "info",
            message: "Select only files or only folders for this action."
        });

        return true;
    }

    function getConfirmApi() {
        const confirmApi = window.SolomonUIConfirm || null;

        if (confirmApi && typeof confirmApi.open === "function") {
            return confirmApi;
        }

        return {
            open: function (options) {
                const title = cleanValue(options?.title);
                const message = cleanValue(options?.message);
                const prompt = [title, message].filter(Boolean).join("\n\n") || "Continue?";

                if (window.confirm(prompt)) {
                    if (typeof options?.onConfirm === "function") {
                        options.onConfirm();
                    }
                    return;
                }

                if (typeof options?.onCancel === "function") {
                    options.onCancel();
                }
            }
        };
    }

    function getSuppressedTrashDocumentIds(explorer) {
        return TrashMutations.getSuppressedTrashDocumentIds(explorer);
    }

    function getOptimisticTrashDocuments(explorer) {
        return TrashMutations.getOptimisticTrashDocuments(explorer);
    }

    function suppressDocumentInTrash(explorer, documentId) {
        TrashMutations.suppressDocumentInTrash(explorer, documentId);
    }

    function unsuppressDocumentInTrash(explorer, documentId) {
        TrashMutations.unsuppressDocumentInTrash(explorer, documentId);
    }

    function shouldSuppressTrashDocument(explorer, doc) {
        return TrashMutations.shouldSuppressTrashDocument(explorer, doc, getDocumentTrashMutationOptions());
    }

    function buildOptimisticTrashDocument(explorer, documentId, payload) {
        return TrashMutations.buildOptimisticTrashDocument(
            explorer,
            documentId,
            payload,
            getDocumentTrashMutationOptions()
        );
    }

    function upsertDocumentInCachedSection(explorer, section, doc) {
        TrashMutations.upsertDocumentInCachedSection(
            explorer,
            section,
            doc,
            getDocumentTrashMutationOptions()
        );
    }

    function rememberDocumentInTrash(explorer, doc) {
        TrashMutations.rememberDocumentInTrash(explorer, doc, getDocumentTrashMutationOptions());
    }

    function mergeTrashDocumentsForRender(explorer, docs) {
        return TrashMutations.mergeTrashDocumentsForRender(explorer, docs, getDocumentTrashMutationOptions());
    }

    function normalizeDocumentLayout(layout) {
        return ViewState.normalizeDocumentLayout(layout, getDocumentViewStateOptions());
    }

    function readStoredDocumentLayout() {
        return ViewState.readStoredDocumentLayout(getDocumentViewStateOptions());
    }

    function storeDocumentLayout(layout) {
        ViewState.storeDocumentLayout(layout, getDocumentViewStateOptions());
    }

    function setDocumentLayout(explorer, layout, options) {
        return ViewState.setDocumentLayout(
            explorer,
            layout,
            getDocumentViewStateOptions(options)
        );
    }

    function getInitialDocumentLayout(explorer) {
        return ViewState.getInitialDocumentLayout(explorer, getDocumentViewStateOptions());
    }

    function normalizeDocumentSortKey(value) {
        return ViewState.normalizeDocumentSortKey(value, getDocumentViewStateOptions());
    }

    function normalizeDocumentSortDirection(value) {
        return ViewState.normalizeDocumentSortDirection(value, getDocumentViewStateOptions());
    }

    function readStoredDocumentSort() {
        return ViewState.readStoredDocumentSort(getDocumentViewStateOptions());
    }

    function storeDocumentSort(sort) {
        ViewState.storeDocumentSort(sort, getDocumentViewStateOptions());
    }

    function getDocumentSort(explorer) {
        return ViewState.getDocumentSort(
            explorer,
            getDocumentViewStateOptions({ explorer })
        );
    }

    function applyDocumentSortControls(explorer, sort) {
        ViewState.applyDocumentSortControls(
            explorer,
            sort,
            getDocumentViewStateOptions({ explorer })
        );
    }

    function setDocumentSort(explorer, nextSort, options) {
        return ViewState.setDocumentSort(
            explorer,
            nextSort,
            getDocumentViewStateOptions(
                Object.assign({}, options || {}, { explorer })
            )
        );
    }

    function getInitialDocumentSort() {
        return ViewState.getInitialDocumentSort(getDocumentViewStateOptions());
    }

    function readDocumentTimestampValue(rawDoc, normalizedDoc) {
        return ViewState.readDocumentTimestampValue(rawDoc, normalizedDoc);
    }

    function getDocumentSortValue(rawDoc, sortKey) {
        return ViewState.getDocumentSortValue(
            rawDoc,
            sortKey,
            getDocumentViewStateOptions()
        );
    }

    function compareDocumentSortValues(a, b, sortKey) {
        return ViewState.compareDocumentSortValues(
            a,
            b,
            sortKey,
            getDocumentViewStateOptions()
        );
    }

    function sortDocumentsForCurrentView(explorer, docs) {
        return ViewState.sortDocumentsForCurrentView(
            explorer,
            docs,
            getDocumentViewStateOptions({ explorer })
        );
    }

    function renderCurrentSectionFromCache(explorer) {
        const section = normalizeDocumentSection(explorer.getAttribute("data-workspace-section"));
        const sourceDocs = getDocumentFilterSource(explorer, section);
        const fallbackDocs = Array.isArray(explorer.__solomonDocuments) ? explorer.__solomonDocuments : [];

        renderCurrentDocumentSection(
            explorer,
            hasDocumentFilterSource(explorer, section)
                ? sourceDocs
                : fallbackDocs,
            { section }
        );

        if (section === "recent") {
            syncRecentFilteredEmptyState(explorer);
        }
    }

    function isDisabledCollectionButton(collectionButton) {
        return ViewState.isDisabledCollectionButton(collectionButton);
    }

    function isCurrentCollectionButton(explorer, collectionButton) {
        return ViewState.isCurrentCollectionButton(
            explorer,
            collectionButton,
            getDocumentViewStateOptions()
        );
    }

    function renderPreviewEmpty(explorer) {
        if (shouldUseServerReaderView(explorer)) {
            applyReaderRouteView(explorer);
            return;
        }

        Preview.renderEmpty(explorer);
    }

    function renderPreviewError(explorer, message) {
        if (shouldUseServerReaderView(explorer)) {
            console.warn("[DOCUMENT_VIEWER][READER_ROUTE] Suppressed preview error while reader is active.", message);
            applyReaderRouteView(explorer);
            return;
        }

        Preview.renderError(explorer, message);
        Conversation.setView(explorer, "preview");
    }

    function renderPreviewDetails(explorer, doc) {
        Preview.renderDetails(explorer, doc);
    }

    function renderDeleteConfirmation(explorer, doc) {
        Preview.renderDeleteConfirmation(explorer, doc);
        Conversation.setView(explorer, "preview");
    }

    function getDocumentSectionCache(explorer) {
        if (!explorer.__solomonDocumentSectionCache) {
            explorer.__solomonDocumentSectionCache = new Map();
        }

        return explorer.__solomonDocumentSectionCache;
    }

    function getCachedDocumentSection(explorer, section) {
        const cleanSection = normalizeDocumentSection(section);
        const cache = getDocumentSectionCache(explorer);

        if (!cache.has(cleanSection)) {
            return null;
        }

        const docs = cache.get(cleanSection);

        return Array.isArray(docs) ? docs : [];
    }

    function setCachedDocumentSection(explorer, section, docs) {
        const cleanSection = normalizeDocumentSection(section);
        const cache = getDocumentSectionCache(explorer);
        const safeDocs = Array.isArray(docs) ? docs : [];

        cache.set(cleanSection, safeDocs);
    }

    function invalidateDocumentSectionCache(explorer, section) {
        const cleanSection = normalizeDocumentSection(section);

        explorer?.__solomonDocumentSectionCache?.delete(cleanSection);
        explorer?.__solomonDocumentFilterSourceCache?.delete(cleanSection);
    }

    function cacheDocuments(explorer, docs, options) {
        const cleanSection = normalizeDocumentSection(
            options?.section ||
            explorer.getAttribute("data-workspace-section") ||
            "files"
        );
        const safeDocs = Array.isArray(docs) ? docs : [];
        const documentsById = new Map();

        safeDocs.forEach(function (doc) {
            const documentId = Records.getDocumentId(doc);

            if (documentId) {
                documentsById.set(documentId, doc);
            }
        });

        explorer.__solomonDocuments = safeDocs;
        explorer.__solomonDocumentById = documentsById;
        setCachedDocumentSection(explorer, cleanSection, safeDocs);

        if (cleanSection === "files" && options?.updateCollectionCounts !== false) {
            Library.updateCollectionCounts(explorer, safeDocs);
        }
    }

    function removeDocumentFromCachedSection(explorer, section, documentId) {
        const cleanSection = normalizeDocumentSection(section);
        const cleanId = String(documentId || "").trim();
        const cachedDocs = getCachedDocumentSection(explorer, cleanSection);

        if (!cleanId || !Array.isArray(cachedDocs)) {
            return [];
        }

        const remainingDocs = cachedDocs.filter(function (doc) {
            return Records.getDocumentId(doc) !== cleanId;
        });

        setCachedDocumentSection(explorer, cleanSection, remainingDocs);
        removeDocumentFromFilterSource(
            explorer,
            cleanSection,
            cleanId
        );

        if (normalizeDocumentSection(explorer.getAttribute("data-workspace-section")) === cleanSection) {
            explorer.__solomonDocuments = remainingDocs;
            explorer.__solomonDocumentById = new Map();

            remainingDocs.forEach(function (doc) {
                const remainingId = Records.getDocumentId(doc);

                if (remainingId) {
                    explorer.__solomonDocumentById.set(remainingId, doc);
                }
            });
        }

        return remainingDocs;
    }

    function removeDocumentRowsFromCurrentView(explorer, documentIds, section) {
        const cleanIds = uniqueDocumentValues(documentIds);
        const cleanSection = normalizeDocumentSection(section || explorer.getAttribute("data-workspace-section"));
        const list = explorer.querySelector(FILE_LIST_SELECTOR);
        let remainingDocs = getCachedDocumentSection(explorer, cleanSection) || [];

        cleanIds.forEach(function (documentId) {
            const row = explorer.querySelector(`.workspace-document-file[data-document-id="${CSS.escape(documentId)}"]`);

            remainingDocs = removeDocumentFromCachedSection(explorer, cleanSection, documentId);

            if (row) {
                row.remove();
            }
        });

        resetDocumentSelection(explorer);
        renderPreviewEmpty(explorer);
        Conversation.returnToFiles(explorer);
        restoreWorkspaceView(explorer, DEFAULT_WORKSPACE_VIEW);

        if (cleanSection === "trash" && list && !list.querySelector(DOCUMENT_ROW_SELECTOR)) {
            renderDocumentSectionPlaceholder(explorer, "trash");
        }

        if (cleanSection === "files" && list && !list.querySelector(DOCUMENT_ROW_SELECTOR)) {
            renderFiles(explorer, remainingDocs, { section: "files" });
        }

        if (cleanSection === "recent" && list && !list.querySelector(DOCUMENT_ROW_SELECTOR)) {
            renderFiles(explorer, remainingDocs, { section: "recent" });
        }
    }

    function removeDocumentRowFromCurrentView(explorer, documentId, section) {
        removeDocumentRowsFromCurrentView(explorer, [documentId], section);
    }

    function syncDocumentRefreshControls(explorer, section) {
        SectionNavigation.syncDocumentRefreshControls(explorer, section, getDocumentSectionNavigationOptions());
    }

    function syncDocumentUploadControls(explorer, section) {
        SectionNavigation.syncDocumentUploadControls(explorer, section, getDocumentSectionNavigationOptions());
    }

    function updateDocumentSectionChrome(explorer, section) {
        SectionNavigation.updateDocumentSectionChrome(explorer, section, getDocumentSectionNavigationOptions());
    }

    function renderDocumentSectionStatus(explorer, section, message) {
        SectionNavigation.renderDocumentSectionStatus(explorer, section, message, getDocumentSectionNavigationOptions());
    }

    function renderDocumentSectionPlaceholder(explorer, section) {
        SectionNavigation.renderDocumentSectionPlaceholder(explorer, section, getDocumentSectionNavigationOptions());
    }

    function renderDocumentSectionLoading(explorer, section) {
        SectionNavigation.renderDocumentSectionLoading(explorer, section, getDocumentSectionNavigationOptions());
    }

    function renderDocumentSectionError(explorer, section, message) {
        SectionNavigation.renderDocumentSectionError(
            explorer,
            section,
            message,
            getDocumentSectionNavigationOptions()
        );
    }

    function renderCurrentDocumentSection(explorer, docs, options) {
        SectionNavigation.renderCurrentDocumentSection(
            explorer,
            docs,
            getDocumentSectionNavigationOptions(options)
        );
    }

    function applyDocumentSection(explorer, section, options) {
        SectionNavigation.applyDocumentSection(
            explorer,
            section,
            getDocumentSectionNavigationOptions(options)
        );
    }

    function shouldHandleDocumentSectionLink(event, link) {
        return SectionNavigation.shouldHandleDocumentSectionLink(
            event,
            link,
            getDocumentSectionNavigationOptions()
        );
    }

    function navigateDocumentSection(explorer, link, options) {
        SectionNavigation.navigateDocumentSection(
            explorer,
            link,
            getDocumentSectionNavigationOptions(options)
        );
    }

    function bindDocumentSectionHistory() {
        SectionNavigation.bindDocumentSectionHistory(
            EXPLORER_SELECTOR,
            getDocumentSectionNavigationOptions()
        );
    }

    async function loadReaderFragment(explorer, readerUrl, options) {
        return ReaderLifecycle.loadReaderFragment(
            explorer,
            readerUrl,
            Object.assign({}, getDocumentReaderLifecycleOptions(), options || {})
        );
    }

    function buildUploadOptions(explorer) {
        return {
            getEndpoint: function () {
                return getEndpoint(explorer, "upload");
            },
            beforeQueue: function () {
                Conversation.markFilesViewIntent(explorer);
                Conversation.setView(explorer, "files");
            },
            beforeUpload: function () {
                explorer.setAttribute("data-document-explorer-loading", "true");
            },
            afterUpload: async function () {
                try {
                    const allFilesCollection = explorer.querySelector("[data-document-collection='all']");

                    if (allFilesCollection) {
                        setCollection(explorer, allFilesCollection, { skipRender: true });
                    }

                    invalidateDocumentSectionCache(explorer, "files");
                    await refreshFiles(explorer, {
                        quiet: true,
                        section: "files"
                    });
                } finally {
                    explorer.removeAttribute("data-document-explorer-loading");
                }
            },
            onUploadError: function (targetExplorer, error) {
                explorer.removeAttribute("data-document-explorer-loading");
                renderPreviewError(targetExplorer || explorer, error.message);
            }
        };
    }

    function openUploadPicker(explorer) {
        Conversation.markFilesViewIntent(explorer);
        Conversation.setView(explorer, "files");
        Uploads.openPicker(explorer, buildUploadOptions(explorer));
    }

    function closeDocumentActionMenus(explorer, exceptMenu) {
        Interactions.closeDocumentActionMenus(explorer, exceptMenu, getDocumentInteractionOptions());
    }

    function hasOpenDocumentActionMenu(explorer) {
        return Interactions.hasOpenDocumentActionMenu(explorer, getDocumentInteractionOptions());
    }

    function toggleDocumentActionMenu(explorer, button) {
        Interactions.toggleDocumentActionMenu(explorer, button, getDocumentInteractionOptions());
    }

    function runDocumentActionMenuItem(explorer, actionItem) {
        Interactions.runDocumentActionMenuItem(explorer, actionItem, getDocumentInteractionOptions());
    }

    function showSingleSelectionBoundary(explorer) {
        const lastShown = Number(explorer?.__solomonSingleSelectionBoundaryShownAt || 0);
        const now = Date.now();

        if (!explorer || now - lastShown < 2800) {
            return;
        }

        explorer.__solomonSingleSelectionBoundaryShownAt = now;
        Status.show(explorer, {
            action: "single_file_selection",
            variant: "info",
            message: "Solomon Documents currently supports one selected document at a time."
        });
    }

    function getDocumentIdFromRow(row) {
        return Interactions.getDocumentIdFromRow(row);
    }

    function isDocumentInTrashContext(explorer, documentId) {
        return Selection.isDocumentInTrashContext(explorer, documentId, getDocumentSelectionOptions());
    }

    function clearSelection(explorer) {
        if (!explorer) {
            return;
        }

        Selection.clearSelection(explorer, getDocumentSelectionOptions());
        explorer.__selectedDocument = null;
        explorer.__selectedDocuments = [];
        explorer.setAttribute("data-document-selected", "false");
        explorer.setAttribute("data-document-selected-count", "0");
        setSelectionRailVisibility(explorer, "empty");
    }

    function applySelectedDocumentState(explorer, row, doc) {
        if (!explorer || !row || !doc?.document_id) {
            return;
        }

        setOnlyDocumentRowSelected(explorer, row);
        explorer.__selectedDocument = doc;
        explorer.__selectedDocuments = [doc];
        explorer.setAttribute("data-document-selected", "true");
        explorer.setAttribute("data-document-selected-count", "1");
    }

    function safeDocumentSelectionSideEffect(label, callback) {
        try {
            callback();
        } catch (error) {
            console.warn(`[DOCUMENT_VIEWER][SELECT][${label}]`, error);
        }
    }

    function selectFile(explorer, row, options) {
        if (!row) {
            return null;
        }

        const doc = Library.getDocumentFromRow(explorer, row);

        if (!doc?.document_id) {
            return null;
        }

        const selectedDocs = [doc];

        applySelectedDocumentState(explorer, row, doc);
        renderSelectionRail(explorer, selectedDocs, options);
        setSelectionRailVisibility(explorer, "selected");

        safeDocumentSelectionSideEffect("preview", function () {
            renderPreviewDetails(explorer, doc);
        });

        safeDocumentSelectionSideEffect("conversation_intent", function () {
            if (isReaderOpeningOrActive(explorer)) {
                return;
            }

            Conversation.markFilesViewIntent(explorer);
            Conversation.returnToFiles(explorer);
        });

        return doc;
    }

    function showFileDetails(explorer, row) {
        if (!row) {
            return;
        }

        const doc = selectFile(explorer, row, {
            selectionIntent: "details_command",
            openInspector: true
        });

        if (!doc?.document_id) {
            return;
        }

        Conversation.markFilesViewIntent(explorer);
        Conversation.returnToFiles(explorer);
        restoreWorkspaceView(explorer, DEFAULT_WORKSPACE_VIEW);
    }

    function getContextRailApi() {
        return window.NationsCommandSidebar || null;
    }

    function buildDocumentSummaryEndpoint(documentId) {
        const cleanDocumentId = cleanValue(documentId);

        if (!cleanDocumentId) {
            return "";
        }

        return `${DOCUMENT_SUMMARY_ENDPOINT_PREFIX}/${encodeURIComponent(cleanDocumentId)}/summary`;
    }

    function isCurrentDocumentSummaryRequest(explorer, documentId, requestId) {
        const ContextRail = getContextRailApi();

        if (
            ContextRail &&
            typeof ContextRail.isContextRailSummaryRequestCurrent === "function"
        ) {
            return ContextRail.isContextRailSummaryRequestCurrent(
                documentId,
                requestId
            );
        }

        return Boolean(
            requestId &&
            explorer?.__solomonDocumentSummaryRequestId === requestId
        );
    }

    async function showFileSummary(explorer, row) {
        if (!row) {
            return;
        }

        const ContextRail = getContextRailApi();
        const doc = selectFile(explorer, row, {
            selectionIntent: "summary_command",
            openInspector: true
        });
        const documentId = cleanValue(doc?.document_id || doc?.random_name);
        const endpoint = buildDocumentSummaryEndpoint(documentId);

        if (!doc || !documentId || !endpoint) {
            return;
        }

        if (
            !ContextRail ||
            typeof ContextRail.showContextRailSummaryLoading !== "function" ||
            typeof ContextRail.showContextRailSummary !== "function" ||
            typeof ContextRail.showContextRailSummaryError !== "function"
        ) {
            Status.show(explorer, {
                action: "summary",
                variant: "error",
                message: "The Summary panel is not available in this workspace."
            });
            return;
        }

        Conversation.markFilesViewIntent(explorer);
        Conversation.returnToFiles(explorer);
        restoreWorkspaceView(explorer, DEFAULT_WORKSPACE_VIEW);

        const requestId = `${documentId}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
        explorer.__solomonDocumentSummaryRequestId = requestId;
        ContextRail.showContextRailSummaryLoading(doc, { requestId });

        try {
            const payload = await fetchJson(endpoint);

            if (!isCurrentDocumentSummaryRequest(explorer, documentId, requestId)) {
                return;
            }

            const responseDocumentId = cleanValue(
                payload?.document_id || payload?.random_name
            );

            if (responseDocumentId && responseDocumentId !== documentId) {
                throw new Error("The server returned a summary for a different document.");
            }

            ContextRail.showContextRailSummary(doc, payload, { requestId });
        } catch (error) {
            if (!isCurrentDocumentSummaryRequest(explorer, documentId, requestId)) {
                return;
            }

            ContextRail.showContextRailSummaryError(
                doc,
                error?.message || "The persisted summary could not be retrieved.",
                { requestId }
            );
        }
    }

    function runSolomonFileAction(explorer, request) {
        const actionId = cleanValue(request?.solomonActionId);
        const row = request?.row || null;
        const doc = row
            ? Library.getDocumentFromRow(explorer, row)
            : null;
        const documentId = cleanValue(
            request?.documentId ||
            doc?.document_id ||
            doc?.random_name
        );
        const documentName = cleanValue(
            request?.documentNames?.[0] ||
            doc?.original_name ||
            row?.getAttribute("data-document-name")
        ) || "Selected file";

        if (!actionId || !documentId || !Operations || typeof Operations.runAction !== "function") {
            Status.show(explorer, {
                action: "solomon_action",
                variant: "error",
                message: "The Solomon Action runner is not available in this workspace."
            });
            return null;
        }

        // Solomon Actions are navigation-neutral. The initiating center surface
        // (Files, Reader, or another governed surface) remains in place while the
        // canonical right rail owns loading, result, and error presentation.
        return Operations.runAction(explorer, {
            actionId,
            actionLabel: cleanValue(request?.actionLabel) || "Action",
            documentId,
            documentName,
            document: doc || {
                document_id: documentId,
                original_name: documentName
            }
        });
    }

    function showSelectedFileDetails(explorer) {
        const selectedRows = getSelectedDocumentRows(explorer);

        if (selectedRows.length !== 1) {
            Status.show(explorer, {
                action: "details",
                variant: "info",
                message: "Select one document to view details."
            });
            return;
        }

        showFileDetails(explorer, selectedRows[0]);
    }

    function getDocumentCollection(doc) {
        return ViewState.getDocumentCollection(doc, getDocumentViewStateOptions());
    }

    function bindRenderedDocumentRows(explorer) {
        Interactions.bindRenderedDocumentRows(explorer, getDocumentInteractionOptions());
    }

    function getDocumentRenderSignature(explorer, section, docs) {
        const cleanDocs = Array.isArray(docs) ? docs : [];
        const layout = cleanValue(
            explorer?.getAttribute("data-document-layout") || DEFAULT_DOCUMENT_LAYOUT
        );
        const folderId = cleanValue(
            explorer?.getAttribute("data-workspace-current-folder-id") || ""
        );
        let serializedDocs = "";

        try {
            serializedDocs = JSON.stringify(cleanDocs);
        } catch (_error) {
            serializedDocs = cleanDocs.map(function (doc) {
                return cleanValue(
                    doc?.workspace_item_id ||
                    doc?.folder_id ||
                    doc?.document_id ||
                    doc?.random_name ||
                    doc?.id
                );
            }).join("|");
        }

        return [section, layout, folderId, serializedDocs].join("\u001f");
    }

    function hasStableDocumentPresentation(list, documentCount) {
        const state = cleanValue(list?.getAttribute("data-document-list-state"));

        if (!list || !["ready", "empty"].includes(state)) {
            return false;
        }

        if (documentCount > 0) {
            return Boolean(list.querySelector(DOCUMENT_ROW_SELECTOR));
        }

        return Boolean(list.querySelector(".workspace-document-empty-state"));
    }

    function shouldPreserveDocumentPresentation(list, signature, documentCount, options) {
        return Boolean(
            options?.forceRender !== true &&
            hasStableDocumentPresentation(list, documentCount) &&
            list.__solomonDocumentRenderSignature === signature
        );
    }

    function commitDocumentRenderSignature(list, signature) {
        if (list) {
            list.__solomonDocumentRenderSignature = signature;
        }
    }

    function renderFiles(explorer, docs, options) {
        const list = explorer.querySelector(FILE_LIST_SELECTOR);
        const section = normalizeDocumentSection(
            options?.section ||
            explorer.getAttribute("data-workspace-section") ||
            "files"
        );
        const activeDocs = (Array.isArray(docs) ? docs : []).filter(function (doc) {
            return !isDocumentRecordTrashed(doc);
        });
        setDocumentFilterSource(explorer, section, activeDocs);
        const filteredDocs = filterDocumentsForCurrentView(
            explorer,
            activeDocs,
            section
        );
        const sortedDocs = section === "recent"
            ? filteredDocs.slice()
            : sortDocumentsForCurrentView(explorer, filteredDocs);

        if (section !== "recent") {
            syncRecentFilterControls(
                explorer,
                {},
                activeDocs,
                section
            );
        }

        cacheDocuments(explorer, sortedDocs, {
            section,
            updateCollectionCounts: section === "files"
        });

        if (!list) {
            return false;
        }

        const renderSignature = getDocumentRenderSignature(
            explorer,
            section,
            sortedDocs
        );

        if (shouldPreserveDocumentPresentation(
            list,
            renderSignature,
            sortedDocs.length,
            options
        )) {
            setDocumentListState(explorer, section, sortedDocs.length ? "ready" : "empty");
            syncDocumentRefreshControls(explorer, section);
            ViewState.applyDocumentSortControls(
                explorer,
                ViewState.getDocumentSort(
                    explorer,
                    getDocumentViewStateOptions({ explorer })
                ),
                getDocumentViewStateOptions({ explorer })
            );
            return false;
        }

        resetDocumentSelection(explorer);
        Library.renderFiles(list, sortedDocs, {
            collection: section,
            section,
            sortAuthority: section === "recent"
                ? getRecentSortAuthority(explorer)
                : null
        });
        commitDocumentRenderSignature(list, renderSignature);
        bindRenderedDocumentRows(explorer);
        renderPreviewEmpty(explorer);
        setDocumentListState(explorer, section, sortedDocs.length ? "ready" : "empty");
        syncDocumentRefreshControls(explorer, section);
        ViewState.applyDocumentSortControls(
            explorer,
            ViewState.getDocumentSort(
                explorer,
                getDocumentViewStateOptions({ explorer })
            ),
            getDocumentViewStateOptions({ explorer })
        );
        syncRecentFilteredEmptyState(explorer);
        return true;
    }

    function renderTrashFiles(explorer, docs, options) {
        const list = explorer.querySelector(FILE_LIST_SELECTOR);
        const mergedDocs = mergeTrashDocumentsForRender(explorer, docs);
        const trashDocs = mergedDocs.filter(function (doc) {
            return isDocumentRecordTrashed(doc) && !shouldSuppressTrashDocument(explorer, doc);
        });
        setDocumentFilterSource(explorer, "trash", trashDocs);
        const filteredDocs = filterDocumentsForCurrentView(
            explorer,
            trashDocs,
            "trash"
        );
        const sortedDocs = sortDocumentsForCurrentView(explorer, filteredDocs);

        syncRecentFilterControls(
            explorer,
            {},
            trashDocs,
            "trash"
        );

        cacheDocuments(explorer, sortedDocs, {
            section: "trash",
            updateCollectionCounts: false
        });

        if (!list) {
            return false;
        }

        const renderSignature = getDocumentRenderSignature(
            explorer,
            "trash",
            sortedDocs
        );

        if (shouldPreserveDocumentPresentation(
            list,
            renderSignature,
            sortedDocs.length,
            options
        )) {
            setDocumentListState(explorer, "trash", sortedDocs.length ? "ready" : "empty");
            syncDocumentRefreshControls(explorer, "trash");
            ViewState.applyDocumentSortControls(
                explorer,
                ViewState.getDocumentSort(
                    explorer,
                    getDocumentViewStateOptions({ explorer })
                ),
                getDocumentViewStateOptions({ explorer })
            );
            return false;
        }

        resetDocumentSelection(explorer);
        renderPreviewEmpty(explorer);
        Library.renderFiles(list, sortedDocs, {
            collection: "trash",
            section: "trash",
            trashMode: true
        });
        commitDocumentRenderSignature(list, renderSignature);
        bindRenderedDocumentRows(explorer);
        setDocumentListState(
            explorer,
            "trash",
            sortedDocs.length ? "ready" : "empty"
        );
        syncDocumentRefreshControls(explorer, "trash");
        ViewState.applyDocumentSortControls(
            explorer,
            ViewState.getDocumentSort(
                explorer,
                getDocumentViewStateOptions({ explorer })
            ),
            getDocumentViewStateOptions({ explorer })
        );
        syncRecentFilteredEmptyState(explorer);
        return true;
    }

    async function refreshFiles(explorer, options) {
        const section = normalizeDocumentSection(
            options?.section ||
            explorer.getAttribute("data-workspace-section") ||
            "files"
        );
        const baseEndpoint = getDocumentSectionEndpoint(explorer, section);
        const endpoint = section === "recent"
            ? buildRecentRequestEndpoint(
                baseEndpoint,
                getRecentFilterState(explorer),
                getRecentSortRequestState(explorer)
            )
            : baseEndpoint;
        const requestId = Number(
            explorer.__solomonDocumentRefreshRequestId || 0
        ) + 1;
        const manualRefresh = cleanValue(options?.source) === "manual_refresh";

        const list = explorer.querySelector(FILE_LIST_SELECTOR);
        const hadRenderableRows = Boolean(
            list?.querySelector(DOCUMENT_ROW_SELECTOR)
        );

        explorer.__solomonDocumentRefreshRequestId = requestId;

        if (!endpoint) {
            renderDocumentSectionError(
                explorer,
                section,
                "The server did not provide an authorized endpoint for this view."
            );
            return false;
        }

        explorer.__solomonDocumentRefreshInFlight = true;

        if (hadRenderableRows && manualRefresh) {
            setDocumentListState(explorer, section, "refreshing");
        } else if (!hadRenderableRows) {
            renderDocumentSectionLoading(explorer, section);
        }

        syncDocumentRefreshControls(explorer, section);

        try {
            const payload = await fetchJson(endpoint);

            if (requestId !== explorer.__solomonDocumentRefreshRequestId) {
                return false;
            }

            let docs = getDocuments(payload);

            syncRecentSortAuthority(explorer, payload, section);

            if (
                (section === "files" || section === "shared")
                && typeof SectionNavigation.syncWorkspaceFolderNavigation === "function"
            ) {
                SectionNavigation.syncWorkspaceFolderNavigation(
                    explorer,
                    payload
                );
            }

            if (section === "trash") {
                docs = mergeTrashDocumentsForRender(explorer, docs);
            }

            setDocumentFilterSource(explorer, section, docs);
            syncRecentFilterControls(
                explorer,
                payload,
                docs,
                section
            );

            cacheDocuments(explorer, docs, {
                section,
                updateCollectionCounts: section === "files"
            });
            renderCurrentDocumentSection(explorer, docs, {
                forceRender: manualRefresh || options?.forceRender === true,
                renderOrigin: cleanValue(options?.source),
                section
            });

            syncRecentFilteredEmptyState(explorer);

            if (manualRefresh) {
                Status.show(explorer, {
                    action: "refresh",
                    variant: "success",
                    message: section === "trash"
                        ? "Trash refreshed."
                        : section === "recent"
                            ? "Recent refreshed."
                            : section === "shared"
                                ? "Shared with me refreshed."
                                : "Folder refreshed."
                });
            }

            return true;
        } catch (error) {
            if (requestId !== explorer.__solomonDocumentRefreshRequestId) {
                return false;
            }

            console.error("[DOCUMENT_VIEWER][REFRESH]", error);

            const fallbackMessage = section === "trash"
                ? "Unable to refresh Trash."
                : section === "recent"
                    ? "Unable to refresh Recent."
                    : section === "shared"
                        ? "Unable to refresh Shared with me."
                        : "Unable to refresh My Files.";
            const errorMessage = error.message || fallbackMessage;

            if (
                section === "recent" &&
                cleanValue(options?.source) === "recent_sort_change"
            ) {
                const authority = getRecentSortAuthority(explorer);

                if (authority) {
                    setDocumentSort(
                        explorer,
                        {
                            key: authority.key,
                            direction: authority.direction,
                            folders: DEFAULT_DOCUMENT_SORT_FOLDERS
                        },
                        { explorer, persist: false }
                    );
                    syncRecentSortLocation({
                        sort: authority.key,
                        direction: authority.direction
                    });
                }
            }

            if (hadRenderableRows) {
                setDocumentListState(explorer, section, "ready");
            } else {
                renderDocumentSectionError(explorer, section, errorMessage);
            }

            Status.show(explorer, {
                action: "refresh",
                variant: "error",
                message: errorMessage
            });

            return false;
        } finally {
            if (requestId === explorer.__solomonDocumentRefreshRequestId) {
                explorer.__solomonDocumentRefreshInFlight = false;
                setRecentFilterBusy(explorer, false);
                syncDocumentRefreshControls(explorer, section);
            }
        }
    }

    async function openDocument(explorer, documentId, options) {
        const cleanOptions = options || {};
        const endpoint = getEndpoint(explorer, "open");
        const cleanDocumentId = String(documentId || "").trim();
        const now = Date.now();
        const readerBackRoute = getReaderCallerBackRoute(explorer, cleanOptions);
        const section = normalizeDocumentSection(
            cleanOptions.surface ||
            explorer?.getAttribute("data-workspace-section") ||
            "files"
        );
        const actionRecord = getDocumentActionRecord(explorer, cleanDocumentId);

        if (!cleanDocumentId) {
            return;
        }

        if (isFolderDocumentRecord(actionRecord)) {
            openFolderDocument(explorer, actionRecord, {
                row: cleanOptions.row || null,
                source: cleanValue(cleanOptions.source) ||
                    "workspace_document_viewer_open_folder"
            });
            return;
        }

        if (!endpoint) {
            return;
        }

        if (
            explorer.__solomonOpenDocumentId === cleanDocumentId &&
            now - Number(explorer.__solomonOpenDocumentStartedAt || 0) <= DOCUMENT_OPEN_DEDUPE_WINDOW_MS
        ) {
            return;
        }

        explorer.__solomonOpenDocumentId = cleanDocumentId;
        explorer.__solomonOpenDocumentStartedAt = now;
        explorer.setAttribute("data-workspace-reader-state", "loading");

        try {
            const payload = await fetchJson(endpoint, {
                method: "POST",
                body: JSON.stringify({
                    action: "open_reader",
                    document_id: cleanDocumentId,
                    surface: section,
                    back: readerBackRoute
                })
            });
            const readerUrl = appendReaderBackRoute(
                getServerReaderUrl(payload),
                readerBackRoute
            );

            if (!readerUrl) {
                throw new Error("The server did not return a Reader URL for this document.");
            }

            explorer.dataset.workspaceReaderBackRoute = readerBackRoute;

            await loadReaderFragment(explorer, readerUrl, {
                documentId: cleanDocumentId,
                backRoute: readerBackRoute,
                launchMode: cleanValue(cleanOptions.launchMode) || "reader",
                source: cleanValue(cleanOptions.source) || "workspace_document_viewer",
                surface: section,
                async: true
            });

            if (cleanValue(cleanOptions.representation).toLowerCase() === "summary") {
                const ReaderControls = window.SolomonWorkspaceDocumentReaderControls;

                if (ReaderControls && typeof ReaderControls.setRepresentation === "function") {
                    await ReaderControls.setRepresentation(
                        getReaderPanel(explorer),
                        "summary"
                    );
                }
            }

        } catch (error) {
            console.error("[DOCUMENT_VIEWER][OPEN]", error);
            explorer.setAttribute("data-workspace-reader-state", "error");
            renderPreviewError(explorer, error.message || "Unable to open Reader.");
        }
    }

    function navigateToSolomonAiWorkspace(url) {
        loadRightPaneRoute(
            url,
            "solomon_ai",
            {
                push: true,
                launchMode: "solomon_ai",
                source: "workspace_document_viewer_ask_solomon_ai"
            }
        );
    }

    async function requestSolomonAiConversation(explorer, documentIds, options) {
        const cleanDocumentIds = uniqueDocumentValues(documentIds);
        const documentNames = uniqueDocumentValues(
            options?.documentNames || getDocumentNamesByIds(explorer, cleanDocumentIds)
        );
        const conversationId = cleanValue(explorer?.dataset?.solomonAiConversationId);
        const requestPayload = {
            document_ids: cleanDocumentIds
        };

        if (!cleanDocumentIds.length) {
            Status.show(explorer, {
                action: "ask_solomon_ai",
                variant: "info",
                message: "Select a document before asking file-specific questions."
            });
            return;
        }

        if (rejectFolderDocumentAction(
            explorer,
            "ask_solomon_ai",
            cleanDocumentIds,
            "Folders cannot be used as SolomonAI sources. Select a file instead."
        )) {
            return;
        }

        if (explorer.__solomonDocumentAiConversationInFlight) {
            return;
        }

        if (conversationId) {
            requestPayload.conversation_id = conversationId;
        }

        explorer.__solomonDocumentAiConversationInFlight = true;
        explorer.setAttribute("data-solomon-ai-conversation-state", "creating");
        Conversation.markFilesViewIntent(explorer);

        try {
            const payload = await fetchJson(SOLOMON_AI_CONVERSATION_CREATE_ENDPOINT, {
                method: "POST",
                body: JSON.stringify(requestPayload)
            });
            const conversationUrl = cleanValue(
                payload.conversation_url ||
                payload.redirect_url ||
                payload.workspace_url ||
                SOLOMON_AI_WORKSPACE_URL
            );

            if (!conversationUrl) {
                throw new Error("The server did not return a SolomonAI conversation URL.");
            }

            navigateToSolomonAiWorkspace(conversationUrl);
        } catch (error) {
            explorer.__solomonDocumentAiConversationInFlight = false;
            explorer.removeAttribute("data-solomon-ai-conversation-state");

            console.error("[DOCUMENT_VIEWER][SOLOMON_AI_CONVERSATION]", error);
            Status.show(explorer, {
                action: "ask_solomon_ai",
                documentIds: cleanDocumentIds,
                documentNames,
                variant: "error",
                message: error.message || "SolomonAI could not open the selected files."
            });
        }
    }

    function runBidScopeReviewOperation(explorer, documentIds, options) {
        const cleanDocumentIds = uniqueDocumentValues(documentIds);
        const documentNames = uniqueDocumentValues(options?.documentNames || getDocumentNamesByIds(explorer, cleanDocumentIds));
        const firstDocumentId = cleanDocumentIds[0] || "";
        const summaryName = getSelectionSummaryName(cleanDocumentIds, documentNames);
        const operationOptions = {
            operationKey: BID_SCOPE_OPERATION_KEY,
            operationLabel: BID_SCOPE_OPERATION_LABEL,
            endpoint: getEndpoint(explorer, "open"),
            documentIds: cleanDocumentIds,
            documentId: firstDocumentId,
            documentName: summaryName,
            metadata: {
                source: "documents_workspace",
                selected_count: cleanDocumentIds.length,
                selected_names: documentNames
            },
            onBeforeStart: function () {
                Conversation.markFilesViewIntent(explorer);
            },
            onStatus: function (statusPayload) {
                Status.show(explorer, statusPayload);
            }
        };

        if (!cleanDocumentIds.length) {
            Status.show(explorer, {
                action: BID_SCOPE_OPERATION_KEY,
                variant: "info",
                message: "Select a document before starting Bid & Scope Review."
            });
            return Promise.resolve(null);
        }

        if (rejectFolderDocumentAction(
            explorer,
            BID_SCOPE_OPERATION_KEY,
            cleanDocumentIds,
            "Bid & Scope Review runs on files only. Select a file instead."
        )) {
            return Promise.resolve(null);
        }

        return Operations.run(operationOptions);
    }

    function resetDocumentSelection(explorer) {
        clearSelection(explorer);
        explorer.__pendingDocumentOperation = null;
        explorer.removeAttribute("data-document-pending-operation");
        explorer.removeAttribute("data-document-pending-operation-ids");
        explorer.removeAttribute("data-document-pending-operation-name");
        explorer.removeAttribute("data-document-pending-operation-mode");

        if (explorer.__solomonConfirmContext) {
            explorer.__solomonConfirmContext = null;
        }
    }

    function hasDocumentSelectionState(explorer) {
        return Boolean(
            getSelectedDocumentRows(explorer).length ||
            explorer?.__selectedDocument ||
            (
                Array.isArray(explorer?.__selectedDocuments) &&
                explorer.__selectedDocuments.length
            ) ||
            explorer?.getAttribute("data-document-selected") === "true" ||
            Number(explorer?.getAttribute("data-document-selected-count") || 0) > 0
        );
    }

    function clearDocumentDetailsState(explorer, options) {
        if (!explorer) {
            return false;
        }

        const wasReaderActive = isReaderOpeningOrActive(explorer);
        const hadSelection = hasDocumentSelectionState(explorer);

        resetDocumentSelection(explorer);

        if (!wasReaderActive) {
            renderPreviewEmpty(explorer);
            Conversation.markFilesViewIntent(explorer);
            Conversation.returnToFiles(explorer);
            restoreWorkspaceView(
                explorer,
                cleanValue(options?.workspaceView) || DEFAULT_WORKSPACE_VIEW
            );
        }

        return hadSelection;
    }

    async function refreshAfterDocumentMutation(explorer, section, options) {
        const cleanSection = normalizeDocumentSection(section || explorer.getAttribute("data-workspace-section"));

        invalidateDocumentSectionCache(explorer, cleanSection);

        await refreshFiles(explorer, {
            quiet: options?.quiet !== false,
            section: cleanSection
        });
    }

    async function refreshCurrentDocumentSection(explorer, options) {
        const section = normalizeDocumentSection(
            options?.section ||
            explorer.getAttribute("data-workspace-section") ||
            "files"
        );

        if (!isFetchableDocumentSection(section)) {
            renderDocumentSectionPlaceholder(explorer, section);
            syncDocumentRefreshControls(explorer, section);
            return;
        }

        await refreshFiles(explorer, {
            quiet: options?.quiet !== false,
            section
        });
    }

    async function moveDocumentToTrash(explorer, documentId) {
        return TrashMutations.moveDocumentToTrash(explorer, documentId, getDocumentTrashMutationOptions());
    }

    async function restoreDocumentFromTrash(explorer, documentIds) {
        const targets = partitionFolderLifecycleTargets(explorer, documentIds);

        if (rejectMixedFolderLifecycleTargets(explorer, "restore", targets)) {
            return null;
        }

        if (targets.folderIds.length) {
            return TrashMutations.restoreFoldersFromTrash(
                explorer,
                targets.folderIds,
                getDocumentTrashMutationOptions()
            );
        }

        return TrashMutations.restoreDocumentFromTrash(
            explorer,
            targets.fileIds,
            getDocumentTrashMutationOptions()
        );
    }

    async function permanentlyDeleteDocument(explorer, documentId) {
        return TrashMutations.permanentlyDeleteDocument(
            explorer,
            documentId,
            getDocumentTrashMutationOptions()
        );
    }

    function getDocumentMutationSummaryName(documentIds, documentNames) {
        return TrashMutations.getDocumentMutationSummaryName(
            documentIds,
            documentNames,
            getDocumentTrashMutationOptions()
        );
    }

    function requestMoveDocumentToTrash(explorer, documentIds) {
        const targets = partitionFolderLifecycleTargets(explorer, documentIds);

        if (rejectMixedFolderLifecycleTargets(explorer, "delete", targets)) {
            return;
        }

        if (targets.folderIds.length) {
            TrashMutations.requestMoveFolderToTrash(
                explorer,
                targets.folderIds,
                getDocumentTrashMutationOptions()
            );
            return;
        }

        TrashMutations.requestMoveDocumentToTrash(
            explorer,
            targets.fileIds,
            getDocumentTrashMutationOptions()
        );
    }

    function requestPermanentDeleteDocument(explorer, documentIds) {
        const targets = partitionFolderLifecycleTargets(explorer, documentIds);

        if (rejectMixedFolderLifecycleTargets(explorer, "permanent_delete", targets)) {
            return;
        }

        if (targets.folderIds.length) {
            TrashMutations.requestPermanentDeleteFolder(
                explorer,
                targets.folderIds,
                getDocumentTrashMutationOptions()
            );
            return;
        }

        TrashMutations.requestPermanentDeleteDocument(
            explorer,
            targets.fileIds,
            getDocumentTrashMutationOptions()
        );
    }

    function requestBidScopeReviewHandoff(explorer, documentIds, options) {
        const cleanDocumentIds = uniqueDocumentValues(documentIds);
        const documentNames = uniqueDocumentValues(options?.documentNames || getDocumentNamesByIds(explorer, cleanDocumentIds));

        if (!cleanDocumentIds.length) {
            Status.show(explorer, {
                action: BID_SCOPE_OPERATION_KEY,
                variant: "info",
                message: "Select a document before starting Bid & Scope Review."
            });
            return;
        }

        runBidScopeReviewOperation(explorer, cleanDocumentIds, {
            documentNames
        })
            .then(function (payload) {
                const redirectUrl = payload?.redirect_url || payload?.result?.redirect_url || "";

                if (redirectUrl) {
                    loadRightPaneRoute(
                        redirectUrl,
                        getWorkspaceModuleForRoute(redirectUrl),
                        {
                            push: true,
                            launchMode: "document_operation_result",
                            source: "workspace_document_viewer_bid_scope_review",
                            operationKey: BID_SCOPE_OPERATION_KEY
                        }
                    );
                }
            })
            .catch(function (error) {
                console.error("[DOCUMENT_VIEWER][BID_SCOPE]", error);
                Status.show(explorer, {
                    action: BID_SCOPE_OPERATION_KEY,
                    documentIds: cleanDocumentIds,
                    variant: "error",
                    message: error.message || "Bid & Scope Review could not start."
                });
            });
    }

    function runPendingDocumentOperation(explorer, operation) {
        TrashMutations.runPendingDocumentOperation(
            explorer,
            operation,
            getDocumentTrashMutationOptions()
        );
    }

    function shouldUseTargetAction(target, attributeName) {
        const action = target.closest(`[${attributeName}]`);

        if (!action) {
            return null;
        }

        return getActionDocumentPayload(action, attributeName);
    }

    function shouldAskSolomonAiFromAction(target) {
        return shouldUseTargetAction(target, "data-document-ask-solomon-ai");
    }

    function shouldRunBidScopeFromAction(target) {
        return shouldUseTargetAction(target, "data-document-use-bid-scope");
    }

    function shouldDeleteFromAction(target) {
        return shouldUseTargetAction(target, "data-document-delete");
    }

    function shouldRestoreFromAction(target) {
        return shouldUseTargetAction(target, "data-document-restore");
    }

    function shouldPermanentDeleteFromAction(target) {
        return shouldUseTargetAction(target, "data-document-permanent-delete");
    }

    function shouldShowDetailsFromAction(target) {
        return shouldUseTargetAction(target, "data-document-selected-details");
    }

    function shouldOpenDocumentFromAction(target) {
        return shouldUseTargetAction(target, "data-document-open");
    }

    function resetSolomonActionsMenuPosition(details) {
        const menu = details?.querySelector?.(SOLOMON_ACTIONS_MENU_SELECTOR);

        if (!menu) {
            return;
        }

        [
            "left",
            "top",
            "right",
            "bottom",
            "maxHeight",
            "maxWidth",
            "overflowY",
            "position",
            "visibility"
        ].forEach(function (propertyName) {
            menu.style[propertyName] = "";
        });
        menu.style.removeProperty("--solomon-actions-anchor-x");
        menu.removeAttribute("data-solomon-actions-menu-positioned");
        details?.removeAttribute?.("data-solomon-actions-placement");
        details?.removeAttribute?.("data-solomon-actions-alignment");
    }

    function positionSolomonActionsMenu(details) {
        if (!details?.open) {
            resetSolomonActionsMenuPosition(details);
            return;
        }

        const trigger = details.querySelector(SOLOMON_ACTIONS_TRIGGER_SELECTOR);
        const menu = details.querySelector(SOLOMON_ACTIONS_MENU_SELECTOR);

        if (!trigger || !menu) {
            return;
        }

        const viewportWidth = Math.max(
            0,
            document.documentElement?.clientWidth || window.innerWidth || 0
        );
        const viewportHeight = Math.max(
            0,
            document.documentElement?.clientHeight || window.innerHeight || 0
        );

        if (!viewportWidth || !viewportHeight) {
            return;
        }

        const padding = SOLOMON_ACTIONS_VIEWPORT_PADDING;
        const gap = SOLOMON_ACTIONS_MENU_GAP;
        const isSelectionActions = details.matches("[data-document-selection-solomon-actions]");

        menu.style.right = "auto";
        menu.style.bottom = "auto";
        menu.style.left = "0px";
        menu.style.top = "0px";
        menu.style.maxHeight = "";
        menu.style.maxWidth = `${Math.max(1, viewportWidth - (padding * 2))}px`;
        menu.style.overflowY = "";
        menu.style.visibility = "hidden";

        const triggerRect = trigger.getBoundingClientRect();

        if (isSelectionActions) {
            /*
             * SOLOMON ANCHORED COMMAND FLYOUT V1
             * ----------------------------------
             * The selected-file Actions menu is owned by the command that opened
             * it. Keep the menu in the trigger's local positioning context and
             * choose only attached edge alignments (right, left, or a centered
             * constrained fallback). Do not viewport-clamp the menu to an
             * unrelated free-floating location.
             */
            menu.style.position = "absolute";

            const detailsRect = details.getBoundingClientRect();
            const menuRect = menu.getBoundingClientRect();
            const availableWidth = Math.max(1, viewportWidth - (padding * 2));
            const menuWidth = Math.min(menuRect.width || 220, availableWidth);
            const preferredRightLeft = triggerRect.right - menuWidth;
            const preferredLeftLeft = triggerRect.left;
            const canAlignRight = preferredRightLeft >= padding;
            const canAlignLeft = preferredLeftLeft + menuWidth <= viewportWidth - padding;
            let alignment = "right";
            let targetLeft = preferredRightLeft;

            if (!canAlignRight && canAlignLeft) {
                alignment = "left";
                targetLeft = preferredLeftLeft;
            } else if (!canAlignRight && !canAlignLeft) {
                alignment = "center";
                targetLeft = Math.min(
                    Math.max(
                        padding,
                        (triggerRect.left + (triggerRect.width / 2)) - (menuWidth / 2)
                    ),
                    Math.max(padding, viewportWidth - padding - menuWidth)
                );
            }

            const availableBelow = Math.max(
                0,
                viewportHeight - triggerRect.bottom - gap - padding
            );
            const availableAbove = Math.max(
                0,
                triggerRect.top - gap - padding
            );
            const placeAbove = Boolean(
                menuRect.height > availableBelow &&
                availableAbove > availableBelow
            );
            const availableHeight = placeAbove ? availableAbove : availableBelow;
            const maxHeight = Math.max(1, availableHeight);
            const renderedHeight = Math.min(menuRect.height || maxHeight, maxHeight);
            const targetTop = placeAbove
                ? triggerRect.top - gap - renderedHeight
                : triggerRect.bottom + gap;
            const anchorViewportX = triggerRect.left + (triggerRect.width / 2);
            const anchorLocalX = Math.min(
                Math.max(14, anchorViewportX - targetLeft),
                Math.max(14, menuWidth - 14)
            );

            menu.style.left = `${Math.round(targetLeft - detailsRect.left)}px`;
            menu.style.top = `${Math.round(targetTop - detailsRect.top)}px`;
            menu.style.maxHeight = `${Math.floor(maxHeight)}px`;
            menu.style.overflowY = menuRect.height > maxHeight ? "auto" : "visible";
            menu.style.setProperty(
                "--solomon-actions-anchor-x",
                `${Math.round(anchorLocalX)}px`
            );
            menu.style.visibility = "visible";
            menu.setAttribute("data-solomon-actions-menu-positioned", "true");
            details.setAttribute(
                "data-solomon-actions-placement",
                placeAbove ? "above" : "below"
            );
            details.setAttribute("data-solomon-actions-alignment", alignment);
            return;
        }

        /*
         * Reader Actions use the existing viewport-aware floating placement.
         * Reader toolbars can live inside a different containment hierarchy, so
         * preserve their proven fixed-position behavior without changing the
         * selected-file anchored flyout contract above.
         */
        menu.style.position = "fixed";

        const menuRect = menu.getBoundingClientRect();
        const availableWidth = Math.max(0, viewportWidth - (padding * 2));
        const menuWidth = Math.min(menuRect.width, availableWidth);
        const desiredLeft = triggerRect.right - menuWidth;
        const maxLeft = Math.max(padding, viewportWidth - menuWidth - padding);
        const left = Math.min(
            Math.max(padding, desiredLeft),
            maxLeft
        );
        const availableBelow = Math.max(
            0,
            viewportHeight - triggerRect.bottom - gap - padding
        );
        const availableAbove = Math.max(
            0,
            triggerRect.top - gap - padding
        );
        const placeAbove = Boolean(
            menuRect.height > availableBelow &&
            availableAbove > availableBelow
        );
        const availableHeight = placeAbove ? availableAbove : availableBelow;
        const maxHeight = Math.max(
            96,
            Math.min(menuRect.height || availableHeight, availableHeight || 96)
        );
        const renderedHeight = Math.min(menuRect.height || maxHeight, maxHeight);
        const top = placeAbove
            ? Math.max(padding, triggerRect.top - gap - renderedHeight)
            : Math.min(
                triggerRect.bottom + gap,
                Math.max(padding, viewportHeight - padding - renderedHeight)
            );

        menu.style.left = `${Math.round(left)}px`;
        menu.style.top = `${Math.round(top)}px`;
        menu.style.maxHeight = `${Math.floor(maxHeight)}px`;
        menu.style.overflowY = menuRect.height > maxHeight ? "auto" : "visible";

        for (let pass = 0; pass < 2; pass += 1) {
            const renderedRect = menu.getBoundingClientRect();
            let leftCorrection = 0;
            let topCorrection = 0;

            if (renderedRect.left < padding) {
                leftCorrection += padding - renderedRect.left;
            }
            if (renderedRect.right > viewportWidth - padding) {
                leftCorrection -= renderedRect.right - (viewportWidth - padding);
            }
            if (renderedRect.top < padding) {
                topCorrection += padding - renderedRect.top;
            }
            if (renderedRect.bottom > viewportHeight - padding) {
                topCorrection -= renderedRect.bottom - (viewportHeight - padding);
            }

            if (Math.abs(leftCorrection) < 0.5 && Math.abs(topCorrection) < 0.5) {
                break;
            }

            const currentLeft = Number.parseFloat(menu.style.left || "0") || 0;
            const currentTop = Number.parseFloat(menu.style.top || "0") || 0;
            menu.style.left = `${Math.round(currentLeft + leftCorrection)}px`;
            menu.style.top = `${Math.round(currentTop + topCorrection)}px`;
        }

        menu.style.visibility = "visible";
        menu.setAttribute("data-solomon-actions-menu-positioned", "true");
        details.setAttribute(
            "data-solomon-actions-placement",
            placeAbove ? "above" : "below"
        );
        details.setAttribute("data-solomon-actions-alignment", "viewport");
    }

    function positionOpenSolomonActionsMenus() {
        document.querySelectorAll(`${SOLOMON_ACTIONS_DETAILS_SELECTOR}[open]`).forEach(
            positionSolomonActionsMenu
        );
    }

    function scheduleSolomonActionsMenuPosition() {
        if (solomonActionsMenuPositionFrame) {
            return;
        }

        solomonActionsMenuPositionFrame = window.requestAnimationFrame(function () {
            solomonActionsMenuPositionFrame = 0;
            positionOpenSolomonActionsMenus();
        });
    }

    function closeSolomonActionsMenusExcept(target) {
        document.querySelectorAll(`${SOLOMON_ACTIONS_DETAILS_SELECTOR}[open]`).forEach(
            function (details) {
                if (target && details.contains(target)) {
                    return;
                }

                details.open = false;
                resetSolomonActionsMenuPosition(details);
            }
        );
    }

    function handleSolomonActionsToggle(event) {
        const details = event?.target;

        if (
            !(details instanceof Element) ||
            !details.matches(SOLOMON_ACTIONS_DETAILS_SELECTOR)
        ) {
            return;
        }

        if (details.open) {
            document.querySelectorAll(`${SOLOMON_ACTIONS_DETAILS_SELECTOR}[open]`).forEach(
                function (candidate) {
                    if (candidate !== details) {
                        candidate.open = false;
                        resetSolomonActionsMenuPosition(candidate);
                    }
                }
            );
            scheduleSolomonActionsMenuPosition();
            return;
        }

        resetSolomonActionsMenuPosition(details);
    }

    function handleSolomonActionsDocumentClick(event) {
        const target = event?.target instanceof Element ? event.target : null;

        if (!target) {
            return;
        }

        if (target.closest(SOLOMON_ACTIONS_DETAILS_SELECTOR)) {
            if (target.closest(SOLOMON_ACTIONS_TRIGGER_SELECTOR)) {
                scheduleSolomonActionsMenuPosition();
            }
            return;
        }

        closeSolomonActionsMenusExcept(target);
    }

    function getSolomonFileActionControlRequest(target, explorer) {
        const control = target?.closest?.(SOLOMON_FILE_ACTION_CONTROL_SELECTOR);

        if (!control || !explorer?.contains(control)) {
            return null;
        }

        const documentId = cleanValue(control.getAttribute("data-document-id"));
        const actionId = cleanValue(control.getAttribute("data-solomon-action-id"));

        if (!documentId || !actionId) {
            return null;
        }

        const row = window.CSS && typeof window.CSS.escape === "function"
            ? explorer.querySelector(`${DOCUMENT_ROW_SELECTOR}[data-document-id="${CSS.escape(documentId)}"]`)
            : null;

        return {
            control,
            row,
            documentId,
            documentNames: [
                cleanValue(control.getAttribute("data-document-name")) || "Selected file"
            ],
            solomonActionId: actionId,
            solomonActionFamily: cleanValue(control.getAttribute("data-solomon-action-family")),
            actionLabel: cleanValue(control.getAttribute("data-solomon-action-label")) || "Action"
        };
    }

    function handleSolomonFileActionControlClick(event, explorer) {
        const request = getSolomonFileActionControlRequest(event?.target, explorer);

        if (!request) {
            return false;
        }

        event.preventDefault();
        event.stopPropagation();

        const details = request.control.closest("details");

        if (details) {
            details.open = false;
        }

        runSolomonFileAction(explorer, request);
        return true;
    }

    function handleOperationConfirmClick(event, explorer) {
        const button = event.target.closest(DOCUMENT_OPERATION_CONFIRM_SELECTOR);

        if (!button || !explorer.contains(button)) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        runPendingDocumentOperation(explorer);
    }

    function handleOperationCancelClick(event, explorer) {
        const button = event.target.closest(DOCUMENT_OPERATION_CANCEL_SELECTOR);

        if (!button || !explorer.contains(button)) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        TrashMutations.resetPendingDocumentOperation(explorer, getDocumentTrashMutationOptions());
        Status.show(explorer, {
            action: "delete",
            variant: "info",
            message: "Document action cancelled."
        });
    }

    function handleSelectedRailClick(event, explorer) {
        const clearSelectionButton = event.target.closest(DOCUMENT_CLEAR_SELECTION_SELECTOR);
        const solomonAiSelection = shouldAskSolomonAiFromAction(event.target);
        const bidScopeSelection = shouldRunBidScopeFromAction(event.target);
        const deleteSelection = shouldDeleteFromAction(event.target);
        const restoreSelection = shouldRestoreFromAction(event.target);
        const permanentDeleteSelection = shouldPermanentDeleteFromAction(event.target);
        const detailsSelection = shouldShowDetailsFromAction(event.target);
        const openSelection = shouldOpenDocumentFromAction(event.target);
        const hasSelectedRailAction = Boolean(
            clearSelectionButton ||
            solomonAiSelection ||
            bidScopeSelection ||
            deleteSelection ||
            restoreSelection ||
            permanentDeleteSelection ||
            detailsSelection ||
            openSelection
        );

        if (hasSelectedRailAction) {
            event.stopPropagation();
        }

        if (clearSelectionButton && explorer.contains(clearSelectionButton)) {
            event.preventDefault();
            clearDocumentDetailsState(explorer, {
                source: "selection_rail_clear"
            });
            return;
        }

        if (solomonAiSelection) {
            event.preventDefault();
            requestSolomonAiConversation(explorer, solomonAiSelection.documentIds, {
                documentNames: solomonAiSelection.documentNames
            });
            return;
        }

        if (bidScopeSelection) {
            event.preventDefault();
            requestBidScopeReviewHandoff(explorer, bidScopeSelection.documentIds, {
                documentNames: bidScopeSelection.documentNames
            });
            return;
        }

        if (deleteSelection) {
            event.preventDefault();
            requestMoveDocumentToTrash(explorer, deleteSelection.documentIds);
            return;
        }

        if (restoreSelection) {
            event.preventDefault();
            restoreDocumentFromTrash(explorer, restoreSelection.documentIds);
            return;
        }

        if (permanentDeleteSelection) {
            event.preventDefault();
            requestPermanentDeleteDocument(explorer, permanentDeleteSelection.documentIds);
            return;
        }

        if (detailsSelection) {
            event.preventDefault();
            showSelectedFileDetails(explorer);
            return;
        }

        if (!openSelection) {
            return;
        }

        event.preventDefault();

        if (openSelection.documentIds.length > 1) {
            Status.show(explorer, {
                action: "open_reader",
                documentIds: openSelection.documentIds,
                variant: "info",
                message: "Reader opens one document at a time."
            });
            return;
        }

        openDocument(explorer, openSelection.documentId);
    }

    function handleActionMenuClick(event, explorer) {
        if (Interactions.handleDocumentActionMenuButtonClick(event, explorer, getDocumentInteractionOptions())) {
            return true;
        }

        return Interactions.handleDocumentActionMenuItemClick(event, explorer, getDocumentInteractionOptions());
    }

    function handleSharedListingSelect(event, explorer) {
        const row = getDocumentRowFromEvent(event, explorer);
        const detail = event?.detail || {};

        if (event.defaultPrevented || !row || detail.selected !== true) {
            return false;
        }

        selectFile(explorer, row, {
            selectionIntent:
                normalizeSharedListingActionName(detail.selectionIntent) ||
                "shared_listing_selection",
            openInspector: false
        });

        return true;
    }

    function handleSharedListingAction(event, explorer) {
        const row = getDocumentRowFromEvent(event, explorer);
        const actionName = normalizeSharedListingActionName(event?.detail?.action);
        const actionItem = getDocumentActionMenuItemFromSharedListingEvent(event, row);

        if (event.defaultPrevented || !row || !actionName) {
            return false;
        }

        if (actionName === "details") {
            event.preventDefault();
            event.stopPropagation();
            showFileDetails(explorer, row);
            return true;
        }

        if (actionItem) {
            event.preventDefault();
            event.stopPropagation();
            runDocumentActionMenuItem(explorer, actionItem);
            return true;
        }

        return false;
    }

    function getSharedListingReaderRoute(detail) {
        return cleanValue(
            detail?.openRoute ||
            detail?.route ||
            detail?.readerUrl ||
            detail?.reader_url ||
            ""
        );
    }

    function getSharedListingReaderBackRoute(detail, readerRoute, explorer) {
        return (
            normalizeSafeReaderBackRoute(detail?.backRoute) ||
            getReaderBackRouteFromReaderUrl(readerRoute) ||
            getReaderCallerBackRoute(explorer, {
                backRoute: detail?.backRoute,
                readerUrl: readerRoute
            })
        );
    }

    async function openSharedListingReaderRoute(explorer, documentId, readerRoute, backRoute, detail) {
        const actionRecord = getDocumentActionRecord(explorer, documentId);

        if (isFolderDocumentRecord(actionRecord)) {
            return openFolderDocument(explorer, actionRecord, {
                row: detail?.row || null,
                source: "workspace_document_viewer_shared_listing_folder"
            });
        }

        const readerUrl = appendReaderBackRoute(
            readerRoute,
            backRoute
        );
        const section = normalizeDocumentSection(
            detail?.surface ||
            explorer?.getAttribute("data-workspace-section") ||
            "files"
        );

        if (!readerUrl) {
            return false;
        }

        explorer.dataset.workspaceReaderBackRoute = backRoute;
        explorer.setAttribute("data-workspace-reader-back-route", backRoute);
        explorer.setAttribute("data-right-pane-content-back-route", backRoute);
        explorer.setAttribute("data-workspace-reader-state", "loading");

        await loadReaderFragment(explorer, readerUrl, {
            documentId,
            backRoute,
            launchMode: "reader",
            source: "workspace_document_viewer_shared_listing",
            surface: section,
            async: true
        });

        return true;
    }

    function handleSharedListingReaderLaunch(event, explorer) {
        const row = getDocumentRowFromEvent(event, explorer);
        const detail = event?.detail || {};
        const documentId = getDocumentIdFromRow(row) || cleanValue(detail.id);
        const readerRoute = getSharedListingReaderRoute(detail);
        const readerBackRoute = getSharedListingReaderBackRoute(
            detail,
            readerRoute,
            explorer
        );

        if (event.defaultPrevented || !row || !documentId) {
            return false;
        }

        if (isFolderDocumentRecord(getDocumentActionRecord(explorer, documentId))) {
            event.preventDefault();
            event.stopPropagation();
            openFolderDocument(
                explorer,
                getDocumentActionRecord(explorer, documentId),
                {
                    row,
                    source: "workspace_document_viewer_shared_listing_folder"
                }
            );
            return true;
        }

        event.preventDefault();
        event.stopPropagation();

        if (readerRoute && isWorkspaceReaderRoutePath(getSameOriginUrl(readerRoute)?.pathname || "")) {
            openSharedListingReaderRoute(
                explorer,
                documentId,
                readerRoute,
                readerBackRoute,
                Object.assign({}, detail, {
                    row
                })
            ).catch(function (error) {
                console.error("[DOCUMENT_VIEWER][SHARED_READER_OPEN]", error);
                explorer.setAttribute("data-workspace-reader-state", "error");
                renderPreviewError(explorer, error.message || "Unable to open Reader.");
            });
            return true;
        }

        openDocument(explorer, documentId, {
            row,
            backRoute: readerBackRoute,
            launchMode: "reader",
            source: "workspace_document_viewer_shared_listing",
            surface: detail.surface
        });

        return true;
    }

    function getDocumentRowFromEvent(event, explorer) {
        const detailRow = event?.detail?.row;
        const detailRowElement = detailRow instanceof Element ? detailRow : null;
        const row = detailRowElement && explorer?.contains(detailRowElement)
            ? detailRowElement
            : event?.target?.closest(DOCUMENT_ROW_SELECTOR) || null;

        if (!row || !explorer?.contains(row)) {
            return null;
        }

        return row;
    }

    function handleDocumentRowKeydown(event, explorer) {
        Interactions.handleDocumentRowKeydown(event, explorer, getDocumentInteractionOptions());
    }

    function setCollection(explorer, collectionButton, options) {
        ViewState.setCollection(
            explorer,
            collectionButton,
            getDocumentViewStateOptions(options)
        );
    }

    function handleCollectionClick(event, explorer) {
        ViewState.handleCollectionClick(
            event,
            explorer,
            getDocumentViewStateOptions()
        );
    }

    function handleSectionLinkClick(event, explorer) {
        SectionNavigation.handleSectionLinkClick(
            event,
            explorer,
            getDocumentSectionNavigationOptions()
        );
    }

    function handleWorkspaceViewClick(event, explorer) {
        const button = event.target.closest(WORKSPACE_VIEW_BUTTON_SELECTOR);

        if (!button || !explorer.contains(button)) {
            return;
        }

        const viewName = normalizeWorkspaceView(button.getAttribute("data-workspace-view"));

        if (viewName === READER_WORKSPACE_VIEW) {
            event.preventDefault();
            restoreWorkspaceView(explorer, READER_WORKSPACE_VIEW);
            return;
        }

        event.preventDefault();
        restoreWorkspaceView(explorer, viewName);
    }

    function handleDocumentRefreshClick(event, explorer) {
        SectionNavigation.handleDocumentRefreshClick(
            event,
            explorer,
            getDocumentSectionNavigationOptions()
        );
    }

    function handleUploadClick(event, explorer) {
        SectionNavigation.handleUploadClick(
            event,
            explorer,
            getDocumentSectionNavigationOptions()
        );
    }

    function handleDocumentColumnSortClick(event, explorer) {
        return ViewState.handleDocumentColumnSortClick(
            event,
            explorer,
            getDocumentViewStateOptions({ explorer })
        );
    }

    function handleDocumentSortClick(event, explorer) {
        return ViewState.handleDocumentSortClick(
            event,
            explorer,
            getDocumentViewStateOptions({ explorer })
        );
    }

    function handleDocumentSortKeydown(event, explorer) {
        return ViewState.handleDocumentSortKeydown(
            event,
            explorer,
            getDocumentViewStateOptions({ explorer })
        );
    }

    function closeDocumentSortMenu(explorer, options) {
        ViewState.closeDocumentSortMenu(
            explorer,
            getDocumentViewStateOptions(
                Object.assign({}, options || {}, { explorer })
            )
        );
    }

    function handleDocumentLayoutClick(event, explorer) {
        ViewState.handleDocumentLayoutClick(
            event,
            explorer,
            getDocumentViewStateOptions({ explorer })
        );
    }

    function handleReaderCloseClick(event, explorer) {
        const button = event.target.closest(WORKSPACE_READER_CLOSE_SELECTOR);

        if (!button || !explorer.contains(button)) {
            return false;
        }

        event.preventDefault();
        event.stopPropagation();

        if (navigateToReaderBackRoute(getReaderCloseBackRoute(explorer))) {
            return true;
        }

        closeReaderView(explorer, {
            explicitClose: true,
            launchMode: "reader_close",
            source: "workspace_document_viewer_reader_close"
        });
        return true;
    }

    function handleDocumentSelectionInputChange(event, explorer) {
        const checkbox = event?.target?.closest?.(
            DOCUMENT_SELECTION_CHECKBOX_SELECTOR
        );

        if (!checkbox || !explorer?.contains(checkbox)) {
            return;
        }

        updateExplorerSelectionFromRows(explorer, {
            selectionIntent: "checkbox_selection",
            openInspector: true
        });
    }

    function handleDocumentInspectorClear(event) {
        const detail = event?.detail || {};

        if (detail.clearSelection === false) {
            return;
        }

        document.querySelectorAll(EXPLORER_SELECTOR).forEach(function (explorer) {
            clearDocumentDetailsState(explorer, {
                source: cleanValue(detail.source) || "document_inspector_clear"
            });
        });
    }

    function isDocumentWhitespaceClick(event, explorer) {
        const list = event?.target?.closest?.(FILE_LIST_SELECTOR);

        if (
            !event ||
            event.defaultPrevented ||
            event.button !== 0 ||
            !list ||
            !explorer?.contains(list)
        ) {
            return false;
        }

        return !event.target?.closest?.(DOCUMENT_WHITESPACE_BLOCKED_SELECTOR);
    }

    function handleDocumentWhitespaceClick(event, explorer) {
        if (!isDocumentWhitespaceClick(event, explorer)) {
            return false;
        }

        closeDocumentActionMenus(explorer);
        SectionNavigation.closeWorkspaceContextMenus(
            explorer,
            getDocumentSectionNavigationOptions()
        );

        if (hasDocumentSelectionState(explorer)) {
            clearDocumentDetailsState(explorer, {
                source: "workspace_document_whitespace"
            });
        }

        event.stopImmediatePropagation();
        return true;
    }

    function handleDocumentSummaryFullOpen(event) {
        const detail = event?.detail || {};
        const documentId = cleanValue(detail.documentId || detail.document_id);
        const explorer = detail.explorer || document.querySelector(EXPLORER_SELECTOR);

        if (!explorer || !documentId) {
            return;
        }

        openDocument(explorer, documentId, {
            launchMode: "reader_summary",
            source: cleanValue(detail.source) || "context_rail_summary",
            representation: "summary"
        });
    }

    function handleExplorerClick(event, explorer) {
        if (handleSolomonFileActionControlClick(event, explorer)) {
            return;
        }

        if (handleActionMenuClick(event, explorer)) {
            return;
        }

        if (handleRecentFilterClear(event, explorer)) {
            return;
        }

        if (handleReaderCloseClick(event, explorer)) {
            return;
        }

        if (handleDocumentColumnSortClick(event, explorer)) {
            return;
        }

        if (handleDocumentSortClick(event, explorer)) {
            return;
        }

        handleCollectionClick(event, explorer);
        handleSectionLinkClick(event, explorer);
        handleWorkspaceViewClick(event, explorer);
        handleDocumentRefreshClick(event, explorer);
        handleUploadClick(event, explorer);
        handleSelectedRailClick(event, explorer);
        handleOperationConfirmClick(event, explorer);
        handleOperationCancelClick(event, explorer);
        handleDocumentLayoutClick(event, explorer);
    }

    function handleExplorerKeydown(event, explorer) {
        if (handleDocumentSortKeydown(event, explorer)) {
            return;
        }

        handleDocumentRowKeydown(event, explorer);
    }

    function handleDocumentKeydown(event) {
        if (event.key !== "Escape") {
            return;
        }

        document.querySelectorAll(EXPLORER_SELECTOR).forEach(function (explorer) {
            Interactions.handleDocumentActionMenuKeydown(event, explorer, getDocumentInteractionOptions());
            closeDocumentSortMenu(explorer, { restoreFocus: true });
        });
    }

    function bindExplorer(explorer) {
        if (!explorer || explorer.dataset.documentViewerBound === "true") {
            return;
        }

        explorer.dataset.documentViewerBound = "true";

        explorer.addEventListener("click", function (event) {
            handleDocumentWhitespaceClick(event, explorer);
        }, true);

        Uploads.bind(explorer, buildUploadOptions(explorer));

        explorer.addEventListener("click", function (event) {
            handleExplorerClick(event, explorer);
        });

        explorer.addEventListener("keydown", function (event) {
            handleExplorerKeydown(event, explorer);
        });

        explorer.addEventListener("change", function (event) {
            if (handleRecentFilterChange(event, explorer)) {
                return;
            }

            handleDocumentSelectionInputChange(event, explorer);
        });

        explorer.addEventListener("submit", function (event) {
            handleRecentFilterSubmit(event, explorer);
        });

        explorer.addEventListener(SHARED_LISTING_SELECT_EVENT, function (event) {
            handleSharedListingSelect(event, explorer);
        });

        explorer.addEventListener(SHARED_LISTING_ACTION_EVENT, function (event) {
            handleSharedListingAction(event, explorer);
        });

        explorer.addEventListener(SHARED_LISTING_READER_LAUNCH_EVENT, function (event) {
            handleSharedListingReaderLaunch(event, explorer);
        });

        if (explorer.getAttribute("data-search-results-surface") === "true") {
            return;
        }

        ensureDefaultDocumentSortMenuProjection(explorer);
        setDocumentLayout(explorer, getInitialDocumentLayout(explorer), { persist: false });

        const initialSection = normalizeDocumentSection(
            explorer.getAttribute("data-workspace-section") || "files"
        );

        if (initialSection !== "recent") {
            setDocumentSort(explorer, getInitialDocumentSort(), { persist: false });
        }

        if (shouldUseServerReaderView(explorer)) {
            applyReaderRouteView(explorer);
            return;
        }

        restoreWorkspaceView(explorer, getInitialWorkspaceView(explorer));

        SectionNavigation.initializeDocumentSection(
            explorer,
            getDocumentSectionNavigationOptions()
        );
    }

    function initializeDocumentExplorers() {
        document.querySelectorAll(EXPLORER_SELECTOR).forEach(bindExplorer);
    }

    function handleDocumentRefreshRequest(event) {
        const requestedExplorer = event?.detail?.explorer;
        const explorers = (
            requestedExplorer instanceof Element &&
            requestedExplorer.matches(EXPLORER_SELECTOR)
        )
            ? [requestedExplorer]
            : Array.from(document.querySelectorAll(EXPLORER_SELECTOR));

        explorers.forEach(function (explorer) {
            if (explorer.getAttribute("data-search-results-surface") === "true") {
                return;
            }

            const section = normalizeDocumentSection(
                explorer.getAttribute("data-workspace-section") || "files"
            );

            invalidateDocumentSectionCache(explorer, section);
            refreshFiles(explorer, {
                quiet: true,
                forceRender: true,
                source: cleanValue(event?.detail?.source) || "external_refresh",
                section: section
            });
        });
    }

    function bootstrap() {
        if (!initialized) {
            initialized = true;

            bindDocumentSectionHistory();
            document.addEventListener("keydown", handleDocumentKeydown);
            document.addEventListener("toggle", handleSolomonActionsToggle, true);
            document.addEventListener("click", handleSolomonActionsDocumentClick);
            document.addEventListener("scroll", scheduleSolomonActionsMenuPosition, true);
            window.addEventListener("resize", scheduleSolomonActionsMenuPosition);
            document.addEventListener(DOCUMENT_SELECTION_COMMAND_FIT_EVENT, scheduleSolomonActionsMenuPosition);
            document.addEventListener(DOCUMENT_INSPECTOR_CLEAR_EVENT, handleDocumentInspectorClear);
            document.addEventListener(DOCUMENT_SUMMARY_FULL_OPEN_EVENT, handleDocumentSummaryFullOpen);
            document.addEventListener(WORKSPACE_LOADED_EVENT, initializeDocumentExplorers);
            document.addEventListener(
                "solomon:workspace-documents-refresh-requested",
                handleDocumentRefreshRequest
            );
            document.addEventListener("click", function (event) {
                const target = event.target instanceof Element ? event.target : null;

                document.querySelectorAll(EXPLORER_SELECTOR).forEach(function (explorer) {
                    const sortControl = explorer.querySelector(DOCUMENT_SORT_CONTROL_SELECTOR);
                    const sortTrigger = explorer.querySelector(DOCUMENT_SORT_TRIGGER_SELECTOR);
                    const sortCellTrigger = explorer.querySelector(DOCUMENT_SORT_CELL_TRIGGER_SELECTOR);
                    const clickIsInsideSort = Boolean(
                        sortControl?.contains(target) ||
                        sortTrigger?.contains(target) ||
                        sortCellTrigger?.contains(target)
                    );

                    if (sortControl && !clickIsInsideSort) {
                        closeDocumentSortMenu(explorer);
                    }
                });
            }, true);

            document.addEventListener("click", function (event) {
                const target = event.target instanceof Element ? event.target : null;

                document.querySelectorAll(EXPLORER_SELECTOR).forEach(function (explorer) {
                    if (
                        !target?.closest(DOCUMENT_ACTION_MENU_SELECTOR) &&
                        hasOpenDocumentActionMenu(explorer)
                    ) {
                        closeDocumentActionMenus(explorer);
                    }
                });
            });
        }

        initializeDocumentExplorers();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bootstrap);
    } else {
        bootstrap();
    }
})();