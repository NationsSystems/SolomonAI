/* -------------------------------------------------------------------
   FILE: command_sidebar_search.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const api = window.NationsCommandSidebar =
        window.NationsCommandSidebar || {};

    const SEARCH_MODULE_ID = "search";
    const DOCUMENTS_MODULE_ID = "documents";
    const RESULT_ATTRIBUTE = "data-command-global-search-result";
    const RESULT_SELECTOR = `[${RESULT_ATTRIBUTE}]`;
    const INTERNAL_ROUTE_PATTERN = /^\/(?!\/)/;
    const SEARCH_UNAVAILABLE_STATUS = 404;
    const WORKSPACE_LISTING_CONTRACT_FALLBACK = "nations_workspace_listing_v1";
    const SEARCH_SEE_ALL_CONTAINER_SELECTOR =
        "[data-command-global-search-see-all-container]";
    const SEARCH_SEE_ALL_SELECTOR =
        "[data-command-global-search-see-all]";
    const SEARCH_ALLOWED_TYPES = new Set([
        "all",
        "files",
        "conversations",
        "people",
        "groups"
    ]);
    const RECENT_SEARCH_RESULT_TYPE = "recent_search";
    const RECENT_SEARCH_STORAGE_KEY =
        "nations.globalSearch.recentQueries.session";
    const RECENT_SEARCH_MAX_ENTRIES = 6;

    function getSearchElements() {
        const c = api.constants || {};
        const form = document.querySelector(
            c.GLOBAL_SEARCH_FORM_SELECTOR
        );

        return {
            form,
            input: form?.querySelector(
                c.GLOBAL_SEARCH_INPUT_SELECTOR
            ) || null,
            control: form?.querySelector(
                c.GLOBAL_SEARCH_CONTROL_SELECTOR
            ) || null,
            clear: form?.querySelector(
                c.GLOBAL_SEARCH_CLEAR_SELECTOR
            ) || null,
            scopes: form
                ? Array.from(
                    form.querySelectorAll(
                        c.GLOBAL_SEARCH_SCOPE_SELECTOR
                    ) || []
                )
                : [],
            status: form?.querySelector(
                c.GLOBAL_SEARCH_STATUS_SELECTOR
            ) || null,
            results: form?.querySelector(
                c.GLOBAL_SEARCH_RESULTS_SELECTOR
            ) || null,
            seeAllContainer: form?.querySelector(
                SEARCH_SEE_ALL_CONTAINER_SELECTOR
            ) || null,
            seeAll: form?.querySelector(
                SEARCH_SEE_ALL_SELECTOR
            ) || null
        };
    }

    function normalizeText(value) {
        return String(value || "")
            .replace(/\s+/g, " ")
            .trim();
    }

    function normalizeSearchType(value) {
        const cleanType = normalizeText(value).toLowerCase();

        return SEARCH_ALLOWED_TYPES.has(cleanType)
            ? cleanType
            : "all";
    }

    function normalizeResultType(value) {
        const cleanType = normalizeText(value).toLowerCase();

        if (!cleanType) {
            return "result";
        }

        return cleanType;
    }

    function readRecentSearchQueries() {
        try {
            const storedValue = window.sessionStorage.getItem(
                RECENT_SEARCH_STORAGE_KEY
            );

            if (!storedValue) {
                return [];
            }

            const parsedValue = JSON.parse(storedValue);

            if (!Array.isArray(parsedValue)) {
                return [];
            }

            const seenQueries = new Set();

            return parsedValue.reduce(function (queries, entry) {
                const query = normalizeText(
                    typeof entry === "string"
                        ? entry
                        : entry?.query
                ).slice(0, 200);
                const queryKey = query.toLowerCase();

                if (!query || seenQueries.has(queryKey)) {
                    return queries;
                }

                seenQueries.add(queryKey);
                queries.push(query);

                return queries;
            }, []).slice(0, RECENT_SEARCH_MAX_ENTRIES);
        } catch (_error) {
            return [];
        }
    }

    function writeRecentSearchQueries(queries) {
        try {
            window.sessionStorage.setItem(
                RECENT_SEARCH_STORAGE_KEY,
                JSON.stringify(queries)
            );
        } catch (_error) {
            return false;
        }

        return true;
    }

    function rememberRecentSearchQuery(value) {
        const query = normalizeText(value).slice(0, 200);

        if (!query) {
            return [];
        }

        const queryKey = query.toLowerCase();
        const existingQueries = readRecentSearchQueries();
        const nextQueries = [
            query,
            ...existingQueries.filter(function (existingQuery) {
                return existingQuery.toLowerCase() !== queryKey;
            })
        ].slice(0, RECENT_SEARCH_MAX_ENTRIES);

        writeRecentSearchQueries(nextQueries);

        return nextQueries;
    }

    function isFileResultType(type) {
        const cleanType = normalizeResultType(type);

        return cleanType === "file" || cleanType === "files";
    }

    function getSharedListingContract() {
        return normalizeText(
            api.constants?.WORKSPACE_LISTING_CONTRACT
        ) || WORKSPACE_LISTING_CONTRACT_FALLBACK;
    }

    function getTypeLabel(type) {
        const cleanType = normalizeResultType(type);

        if (isFileResultType(cleanType)) {
            return "File";
        }

        if (
            cleanType === "conversation" ||
            cleanType === "conversations"
        ) {
            return "Conversation";
        }

        if (cleanType === "person" || cleanType === "people") {
            return "Person";
        }

        if (cleanType === "group" || cleanType === "groups") {
            return "Group";
        }

        if (cleanType === "workspace") {
            return "Workspace";
        }

        if (cleanType === "action") {
            return "Action";
        }

        if (cleanType === "capability_request") {
            return "Request";
        }

        return "Result";
    }

    function getFallbackIcon(type) {
        const cleanType = normalizeResultType(type);

        if (isFileResultType(cleanType)) {
            return "description";
        }

        if (
            cleanType === "conversation" ||
            cleanType === "conversations"
        ) {
            return "forum";
        }

        if (cleanType === "person" || cleanType === "people") {
            return "person";
        }

        if (cleanType === "group" || cleanType === "groups") {
            return "groups";
        }

        if (cleanType === "workspace") {
            return "space_dashboard";
        }

        if (cleanType === "action") {
            return "bolt";
        }

        if (cleanType === "capability_request") {
            return "add_task";
        }

        return "search";
    }

    function getSearchEndpoint(form) {
        return normalizeText(
            form?.getAttribute("data-command-search-endpoint")
        ) || api.constants.GLOBAL_SEARCH_ENDPOINT;
    }

    function getRecentSearchEndpoint(form) {
        return normalizeText(
            form?.getAttribute(
                "data-command-search-recent-endpoint"
            )
        );
    }

    function getSearchResultsRoute(form) {
        return normalizeText(
            form?.getAttribute("data-command-search-results-route")
        ) || api.constants.GLOBAL_SEARCH_RESULTS_ROUTE;
    }

    function getSearchContext(form) {
        return normalizeText(
            form?.getAttribute("data-command-search-context")
        );
    }

    function getSelectedSearchType(elements) {
        return normalizeSearchType(
            elements?.form?.getAttribute(
                "data-command-search-type"
            ) || api.state.globalSearchType
        );
    }

    function setSelectedSearchType(elements, value) {
        const searchType = normalizeSearchType(value);

        api.state.globalSearchType = searchType;
        elements?.form?.setAttribute(
            "data-command-search-type",
            searchType
        );

        Array.from(elements?.scopes || []).forEach(function (scope) {
            const isActive = normalizeSearchType(
                scope.getAttribute(
                    "data-command-global-search-scope"
                )
            ) === searchType;

            scope.classList.toggle("is-active", isActive);
            scope.setAttribute(
                "aria-pressed",
                isActive ? "true" : "false"
            );
        });

        return searchType;
    }

    function getResultId(result, index) {
        return normalizeText(
            result?.id ||
            result?.result_id ||
            result?.intelligence_id ||
            `global-search-result-${index}`
        );
    }

    function getFileResultObjectId(result, index) {
        return normalizeText(
            result?.document_id ||
            result?.documentId ||
            result?.file_id ||
            result?.fileId ||
            result?.upload_id ||
            result?.uploadId ||
            result?.random_name ||
            result?.randomName ||
            result?.object_id ||
            result?.objectId ||
            getResultId(result, index)
        );
    }

    function getResultTitle(result) {
        return normalizeText(
            result?.title ||
            result?.name ||
            result?.label ||
            "Untitled"
        );
    }

    function getResultFileExtension(result, title) {
        const explicitExtension = normalizeText(
            result?.extension ||
            result?.file_extension ||
            result?.file_ext
        ).replace(/^\./, "").toLowerCase();

        if (explicitExtension) {
            return explicitExtension;
        }

        const cleanTitle = normalizeText(title);
        const match = cleanTitle.match(/\.([a-z0-9]{1,12})$/i);

        return match ? match[1].toLowerCase() : "";
    }

    function getResultFileMimeType(result) {
        return normalizeText(
            result?.mime_type ||
            result?.mimetype ||
            result?.content_type ||
            result?.file_type
        ).toLowerCase();
    }

    function getFileDisplayType(result, title) {
        const extension = getResultFileExtension(result, title);
        const mimeType = getResultFileMimeType(result);
        const explicitLabel = normalizeText(result?.type_label);

        if (extension === "pdf" || mimeType.includes("pdf")) {
            return "PDF Document";
        }

        if (
            ["doc", "docx", "rtf", "odt"].includes(extension) ||
            mimeType.includes("word") ||
            mimeType.includes("document")
        ) {
            return "Document";
        }

        if (
            ["xls", "xlsx", "xlsm", "csv", "tsv", "ods"].includes(extension) ||
            mimeType.includes("spreadsheet") ||
            mimeType.includes("excel") ||
            mimeType.includes("csv")
        ) {
            return "Spreadsheet";
        }

        if (
            ["ppt", "pptx", "odp"].includes(extension) ||
            mimeType.includes("presentation") ||
            mimeType.includes("powerpoint")
        ) {
            return "Presentation";
        }

        if (
            ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "tif", "tiff"].includes(extension) ||
            mimeType.startsWith("image/")
        ) {
            return "Image";
        }

        if (
            ["mp3", "wav", "m4a", "aac", "flac", "ogg"].includes(extension) ||
            mimeType.startsWith("audio/")
        ) {
            return "Audio";
        }

        if (
            ["mp4", "mov", "avi", "mkv", "webm"].includes(extension) ||
            mimeType.startsWith("video/")
        ) {
            return "Video";
        }

        if (
            ["zip", "rar", "7z", "tar", "gz"].includes(extension) ||
            mimeType.includes("zip") ||
            mimeType.includes("archive")
        ) {
            return "Archive";
        }

        return explicitLabel || "File";
    }

    function getDisplayTypeLabel(result, type, title) {
        const cleanType = normalizeResultType(type);

        if (isFileResultType(cleanType)) {
            return getFileDisplayType(result, title);
        }

        return normalizeText(result?.type_label) || getTypeLabel(cleanType);
    }

    function getFileDisplayIcon(result, title) {
        const extension = getResultFileExtension(result, title);
        const mimeType = getResultFileMimeType(result);

        if (extension === "pdf" || mimeType.includes("pdf")) {
            return "picture_as_pdf";
        }

        if (
            ["doc", "docx", "rtf", "odt"].includes(extension) ||
            mimeType.includes("word") ||
            mimeType.includes("document")
        ) {
            return "article";
        }

        if (
            ["xls", "xlsx", "xlsm", "csv", "tsv", "ods"].includes(extension) ||
            mimeType.includes("spreadsheet") ||
            mimeType.includes("excel") ||
            mimeType.includes("csv")
        ) {
            return "table_chart";
        }

        if (
            ["ppt", "pptx", "odp"].includes(extension) ||
            mimeType.includes("presentation") ||
            mimeType.includes("powerpoint")
        ) {
            return "slideshow";
        }

        if (
            ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "tif", "tiff"].includes(extension) ||
            mimeType.startsWith("image/")
        ) {
            return "image";
        }

        if (
            ["mp3", "wav", "m4a", "aac", "flac", "ogg"].includes(extension) ||
            mimeType.startsWith("audio/")
        ) {
            return "audio_file";
        }

        if (
            ["mp4", "mov", "avi", "mkv", "webm"].includes(extension) ||
            mimeType.startsWith("video/")
        ) {
            return "movie";
        }

        if (
            ["zip", "rar", "7z", "tar", "gz"].includes(extension) ||
            mimeType.includes("zip") ||
            mimeType.includes("archive")
        ) {
            return "folder_zip";
        }

        return "description";
    }

    function getDisplayIcon(result, type, title) {
        const cleanType = normalizeResultType(type);

        if (isFileResultType(cleanType)) {
            return getFileDisplayIcon(result, title);
        }

        const explicitIcon = normalizeText(
            result?.icon ||
            result?.icon_key
        );

        return explicitIcon || getFallbackIcon(cleanType);
    }

    function getResultRoute(result) {
        return normalizeText(
            result?.reader_url ||
            result?.readerUrl ||
            result?.document_reader_url ||
            result?.documentReaderUrl ||
            result?.workspace_reader_url ||
            result?.workspaceReaderUrl ||
            result?.route ||
            result?.url ||
            result?.canonical_url ||
            result?.href ||
            ""
        );
    }

    function isInternalRoute(route) {
        return INTERNAL_ROUTE_PATTERN.test(
            normalizeText(route)
        );
    }

    function getRelativeUrl(url) {
        return `${url.pathname}${url.search}${url.hash}`;
    }

    function getSameOriginUrl(value) {
        const cleanRoute = normalizeText(value);

        if (!cleanRoute) {
            return null;
        }

        try {
            const url = new URL(cleanRoute, window.location.origin);

            return url.origin === window.location.origin
                ? url
                : null;
        } catch (_error) {
            return null;
        }
    }

    function getSameOriginRelativeRoute(value) {
        const url = getSameOriginUrl(value);

        return url ? getRelativeUrl(url) : "";
    }

    function getCurrentSearchRouteQuery() {
        try {
            const currentUrl = new URL(window.location.href);

            if (currentUrl.pathname !== "/search") {
                return "";
            }

            return normalizeText(
                currentUrl.searchParams.get("q") || ""
            );
        } catch (_error) {
            return "";
        }
    }

    function getCurrentSearchRouteType() {
        try {
            const currentUrl = new URL(window.location.href);

            if (currentUrl.pathname !== "/search") {
                return "";
            }

            return normalizeSearchType(
                currentUrl.searchParams.get("type") || "all"
            );
        } catch (_error) {
            return "";
        }
    }

    function syncCommittedSearchState(elements) {
        const committedQuery = getCurrentSearchRouteQuery();
        const committedType = getCurrentSearchRouteType();
        const inputQuery = normalizeText(elements?.input?.value);
        const inputIsDirty = api.state.globalSearchInputDirty === true;

        api.state.globalSearchCommittedQuery = committedQuery;

        if (committedType) {
            setSelectedSearchType(elements, committedType);
        }

        if (!committedQuery) {
            return false;
        }

        if (inputIsDirty && inputQuery !== committedQuery) {
            return false;
        }

        if (elements?.input && inputQuery !== committedQuery) {
            elements.input.value = committedQuery;
            setClearVisible(elements, true);
        }

        api.state.globalSearchInputDirty = false;
        rememberRecentSearchQuery(committedQuery);
        closeSearchResults(elements);

        return true;
    }

    function allowSuggestionsAfterInput() {
        api.state.globalSearchInputDirty = true;
    }

    function getCurrentRightPaneRoute() {
        return `${window.location.pathname || "/"}${window.location.search || ""}${window.location.hash || ""}`;
    }

    function getReaderBackRouteFromRoute(route) {
        const parsedUrl = getSameOriginUrl(route);

        if (!parsedUrl || !isWorkspaceReaderRoute(getRelativeUrl(parsedUrl))) {
            return "";
        }

        const backRoute = normalizeText(
            parsedUrl.searchParams.get("back") || ""
        );

        if (
            !backRoute ||
            !backRoute.startsWith("/") ||
            isWorkspaceReaderRoute(backRoute)
        ) {
            return "";
        }

        return backRoute;
    }

    function buildSearchBackRoute() {
        const currentRoute = getCurrentRightPaneRoute();
        const readerBackRoute = getReaderBackRouteFromRoute(currentRoute);

        return readerBackRoute || currentRoute || "/";
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

    function appendReaderBackRoute(route, backRoute) {
        const cleanRoute = normalizeText(route);
        const cleanBackRoute = normalizeText(backRoute);
        const parsedUrl = getSameOriginUrl(cleanRoute);

        if (!parsedUrl || !isWorkspaceReaderRoute(getRelativeUrl(parsedUrl))) {
            return cleanRoute;
        }

        if (
            !cleanBackRoute ||
            !cleanBackRoute.startsWith("/") ||
            isWorkspaceReaderRoute(cleanBackRoute)
        ) {
            return getRelativeUrl(parsedUrl);
        }

        if (parsedUrl.searchParams.has("back")) {
            return getRelativeUrl(parsedUrl);
        }

        parsedUrl.searchParams.set(
            "back",
            cleanBackRoute
        );

        return getRelativeUrl(parsedUrl);
    }

    function getNavigableResultRoute(result, elements) {
        return appendReaderBackRoute(
            getResultRoute(result),
            buildSearchBackRoute(elements)
        );
    }

    function getResultModule(result, route) {
        const explicitModule = normalizeText(
            result?.module ||
            result?.module_id ||
            result?.workspace_module ||
            ""
        ).toLowerCase();

        if (explicitModule) {
            return explicitModule;
        }

        if (
            route === "/" ||
            route === "/reports" ||
            route === "/recent" ||
            route === "/trash" ||
            route.startsWith("/workspace/file/") ||
            route.startsWith("/workspace/document/")
        ) {
            return DOCUMENTS_MODULE_ID;
        }

        if (
            route === "/ai" ||
            route.startsWith("/ai/")
        ) {
            return "solomon_ai";
        }

        if (
            route === "/people" ||
            route.startsWith("/people/")
        ) {
            return "people";
        }

        if (
            route === "/search" ||
            route.startsWith("/search?")
        ) {
            return SEARCH_MODULE_ID;
        }

        return SEARCH_MODULE_ID;
    }

    function applyFileResultContract(
        element,
        result,
        index,
        type,
        title,
        route,
        moduleId,
        backRoute
    ) {
        if (!element || !isFileResultType(type)) {
            return;
        }

        const objectId = getFileResultObjectId(result, index);
        const mimeType = getResultFileMimeType(result);
        const typeLabel = getFileDisplayType(result, title);
        const canOpen = Boolean(route);
        const readerLaunch = isWorkspaceReaderRoute(route);

        element.setAttribute("data-workspace-object", "");
        element.setAttribute("data-workspace-object-id", objectId);
        element.setAttribute("data-workspace-object-name", title);
        element.setAttribute("data-workspace-object-type", "file");
        element.setAttribute("data-workspace-object-kind", "file");
        element.setAttribute("data-workspace-object-route", route);
        element.setAttribute("data-workspace-object-module", moduleId || DOCUMENTS_MODULE_ID);
        element.setAttribute("data-workspace-object-open-enabled", canOpen ? "true" : "false");
        element.setAttribute("data-workspace-object-mime", mimeType);
        element.setAttribute("data-workspace-listing-contract", getSharedListingContract());

        element.setAttribute("data-document-id", objectId);
        element.setAttribute("data-document-name", title);
        element.setAttribute("data-document-route", route);
        element.setAttribute("data-document-open-enabled", canOpen ? "true" : "false");
        element.setAttribute("data-document-type-label", typeLabel);
        element.setAttribute("data-document-mime", mimeType);

        if (readerLaunch) {
            element.setAttribute("data-document-reader-url", route);
            element.setAttribute("data-right-pane-content-launch", "reader");
            element.setAttribute("data-right-pane-content-back-route", backRoute);
        } else {
            element.removeAttribute("data-document-reader-url");
            element.removeAttribute("data-right-pane-content-launch");
            element.removeAttribute("data-right-pane-content-back-route");
        }

        element.setAttribute("data-search-result-kind", "file");
        element.setAttribute("data-search-result-title", title);
        element.setAttribute("data-search-result-route", route);
        element.setAttribute("data-search-result-open-enabled", canOpen ? "true" : "false");
        element.setAttribute("data-search-result-open-trigger", "");
    }

    function buildSearchUrl(elements, query) {
        const searchUrl = new URL(
            getSearchEndpoint(elements?.form),
            window.location.origin
        );
        const context = getSearchContext(elements?.form);

        searchUrl.searchParams.set("q", query);
        searchUrl.searchParams.set(
            "type",
            getSelectedSearchType(elements)
        );
        searchUrl.searchParams.set(
            "limit",
            String(api.constants.GLOBAL_SEARCH_MAX_DROPDOWN_RESULTS)
        );

        if (context) {
            searchUrl.searchParams.set("context", context);
        }

        return searchUrl;
    }

    function buildSearchResultsUrl(elements, query) {
        const searchUrl = new URL(
            getSearchResultsRoute(elements?.form),
            window.location.origin
        );

        searchUrl.searchParams.set("q", query);
        searchUrl.searchParams.set(
            "type",
            getSelectedSearchType(elements)
        );

        return searchUrl;
    }

    function setStatus(elements, message) {
        if (!elements.status) {
            return;
        }

        const cleanMessage = normalizeText(message);

        elements.status.textContent = cleanMessage;
        elements.status.hidden = !cleanMessage;
    }

    function setInputExpanded(elements, expanded) {
        if (!elements.input) {
            return;
        }

        elements.input.setAttribute(
            "aria-expanded",
            expanded ? "true" : "false"
        );
    }

    function setClearVisible(elements, visible) {
        if (!elements.clear) {
            return;
        }

        elements.clear.hidden = !visible;
        elements.clear.setAttribute(
            "aria-hidden",
            visible ? "false" : "true"
        );
    }

    function setSeeAllVisible(elements, visible) {
        if (!elements.seeAllContainer) {
            return;
        }

        elements.seeAllContainer.hidden = !visible;
        elements.seeAllContainer.setAttribute(
            "aria-hidden",
            visible ? "false" : "true"
        );

        if (elements.seeAll) {
            elements.seeAll.tabIndex = visible ? 0 : -1;
        }
    }

    function setResultsOpen(elements, open, state) {
        const panelState = open
            ? normalizeText(state) || "results"
            : "idle";

        api.state.globalSearchPanelState = panelState;

        if (elements.form) {
            elements.form.setAttribute(
                "data-command-search-panel-state",
                panelState
            );
        }

        if (!elements.results) {
            setInputExpanded(elements, open);
            return;
        }

        elements.results.hidden = !open;
        elements.results.setAttribute(
            "aria-hidden",
            open ? "false" : "true"
        );
        elements.results.setAttribute(
            "data-command-search-state",
            panelState
        );

        setInputExpanded(elements, open);
    }

    function clearActiveResult(elements) {
        api.state.globalSearchActiveIndex = -1;

        if (elements.input) {
            elements.input.removeAttribute("aria-activedescendant");
        }

        elements.results?.querySelectorAll(RESULT_SELECTOR)
            .forEach(function (item) {
                item.setAttribute("aria-selected", "false");
            });
    }

    function cancelSearchDebounce() {
        window.clearTimeout(
            api.state.globalSearchDebounceTimer
        );

        api.state.globalSearchDebounceTimer = null;
    }

    function setSearchPending(elements, pending, query) {
        const isPending = pending === true;
        const cleanQuery = isPending
            ? normalizeText(query)
            : "";

        api.state.globalSearchPendingQuery = cleanQuery;

        if (elements.form) {
            elements.form.setAttribute(
                "data-command-search-pending",
                isPending ? "true" : "false"
            );
        }

        if (elements.results) {
            elements.results.setAttribute(
                "aria-busy",
                isPending ? "true" : "false"
            );
        }

        if (isPending) {
            setStatus(elements, "Searching.");
        }
    }

    function abortActiveSearchRequest() {
        if (
            api.state.globalSearchController &&
            typeof api.state.globalSearchController.abort ===
            "function"
        ) {
            api.state.globalSearchController.abort();
        }

        api.state.globalSearchController = null;
    }

    function invalidateSearchRequest(elements) {
        api.state.globalSearchRequestGeneration =
            Number(api.state.globalSearchRequestGeneration || 0) + 1;

        abortActiveSearchRequest();
        setSearchPending(elements, false);

        return api.state.globalSearchRequestGeneration;
    }

    function closeSearchResults(elements) {
        cancelSearchDebounce();
        invalidateSearchRequest(elements);

        api.state.globalSearchResults = [];

        clearActiveResult(elements);
        setSeeAllVisible(elements, false);
        setResultsOpen(elements, false);
        setStatus(elements, "");
    }

    function createIcon(name) {
        if (typeof api.createIcon === "function") {
            return api.createIcon(name);
        }

        const icon = document.createElement("span");

        icon.className = "icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = name;

        return icon;
    }

    function getResultMetadataObject(result) {
        for (const candidate of [
            result?.metadata,
            result?.document_metadata,
            result?.workspace_metadata
        ]) {
            if (
                candidate &&
                typeof candidate === "object" &&
                !Array.isArray(candidate)
            ) {
                return candidate;
            }
        }

        return {};
    }

    function getResultMetadataValue(
        result,
        fieldNames
    ) {
        const metadata =
            getResultMetadataObject(result);

        for (const fieldName of fieldNames) {
            const directValue =
                normalizeText(result?.[fieldName]);

            if (directValue) {
                return directValue;
            }

            const metadataValue =
                normalizeText(metadata?.[fieldName]);

            if (metadataValue) {
                return metadataValue;
            }
        }

        return "";
    }

    function getResultSecondaryMetadata(
        result,
        type,
        typeLabel
    ) {
        const values = [typeLabel];

        if (isFileResultType(type)) {
            values.push(
                getResultMetadataValue(
                    result,
                    [
                        "size_label",
                        "file_size_label",
                        "formatted_size",
                        "display_size"
                    ]
                ),
                getResultMetadataValue(
                    result,
                    [
                        "location_label",
                        "workspace_location_label",
                        "authorized_location_label"
                    ]
                )
            );
        } else {
            values.push(
                normalizeText(
                    result?.scope_label
                )
            );
        }

        return Array.from(
            new Set(
                values.filter(Boolean)
            )
        ).join(" · ");
    }

    function getResultTrailingMetadata(
        result,
        type
    ) {
        if (!isFileResultType(type)) {
            return "";
        }

        return getResultMetadataValue(
            result,
            [
                "uploaded_label",
                "uploadedLabel",
                "upload_label",
                "uploadLabel"
            ]
        );
    }

    function createResultElement(result, index, elements) {
        const type = normalizeResultType(result?.type);
        const title = getResultTitle(result);
        const typeLabel = getDisplayTypeLabel(result, type, title);
        const route = getNavigableResultRoute(result, elements);
        const backRoute = buildSearchBackRoute(elements);
        const moduleId = getResultModule(result, route);
        const iconName = getDisplayIcon(result, type, title);
        const secondaryMetadata =
            getResultSecondaryMetadata(
                result,
                type,
                typeLabel
            );
        const trailingMetadata =
            getResultTrailingMetadata(
                result,
                type
            );
        const canNavigate = Boolean(route);
        const element = document.createElement("button");

        element.type = "button";
        element.className = "command-global-search-result";
        element.id = `commandGlobalSearchResultOption${index}`;
        element.setAttribute(RESULT_ATTRIBUTE, "true");
        element.setAttribute("data-search-result-index", String(index));
        element.setAttribute("data-search-result-id", getResultId(result, index));
        element.setAttribute("data-search-result-type", type);
        element.setAttribute("data-search-result-title", title);
        element.setAttribute("data-search-result-route", route);
        element.setAttribute("data-search-result-can-open", canNavigate ? "true" : "false");
        element.setAttribute("role", "option");
        element.setAttribute("aria-selected", "false");

        if (canNavigate) {
            element.setAttribute("data-command-route-value", route);
            element.setAttribute("data-command-module-value", moduleId);
        }

        applyFileResultContract(
            element,
            result,
            index,
            type,
            title,
            route,
            moduleId,
            backRoute
        );

        const iconShell = document.createElement("span");
        iconShell.className = "command-global-search-result-icon";
        iconShell.setAttribute("aria-hidden", "true");
        iconShell.appendChild(createIcon(iconName));

        const copy = document.createElement("span");
        copy.className = "command-global-search-result-copy";

        const titleElement = document.createElement("strong");
        titleElement.textContent = title;

        const metadataElement =
            document.createElement("span");

        metadataElement.className =
            "command-global-search-result-snippet";
        metadataElement.textContent =
            secondaryMetadata;

        copy.appendChild(titleElement);

        if (secondaryMetadata) {
            copy.appendChild(
                metadataElement
            );
        }

        element.appendChild(iconShell);
        element.appendChild(copy);

        if (trailingMetadata) {
            const trailingElement =
                document.createElement("span");
            const trailingValue =
                document.createElement("span");

            trailingElement.className =
                "command-global-search-result-meta";
            trailingValue.className =
                "command-global-search-result-snippet";
            trailingValue.textContent =
                trailingMetadata;

            trailingElement.appendChild(
                trailingValue
            );
            element.appendChild(
                trailingElement
            );
        }

        return element;
    }

    function createSearchMessageElement(options) {
        const element = document.createElement("div");
        const iconShell = document.createElement("span");
        const copy = document.createElement("span");
        const title = document.createElement("strong");
        const summary = document.createElement("span");
        const state = normalizeText(options?.state) || "ready";

        element.className = "command-global-search-empty";
        element.setAttribute("role", "status");
        element.setAttribute("data-command-search-message", state);

        iconShell.className = "command-global-search-result-icon";
        iconShell.setAttribute("aria-hidden", "true");
        iconShell.appendChild(
            createIcon(
                normalizeText(options?.icon) || "manage_search"
            )
        );

        copy.className = "command-global-search-result-copy";
        title.textContent = normalizeText(options?.title);
        summary.textContent = normalizeText(options?.summary);

        copy.appendChild(title);

        if (summary.textContent) {
            copy.appendChild(summary);
        }

        element.appendChild(iconShell);
        element.appendChild(copy);

        return element;
    }

    function renderSearchMessage(elements, options) {
        if (!elements.results) {
            return;
        }

        const state = normalizeText(options?.state) || "ready";
        const status = normalizeText(options?.status);

        api.state.globalSearchResults = [];
        api.state.globalSearchActiveIndex = -1;

        elements.results.replaceChildren(
            createSearchMessageElement(options)
        );
        clearActiveResult(elements);
        setSeeAllVisible(
            elements,
            options?.showAllResults === true
        );
        setResultsOpen(elements, true, state);
        setStatus(elements, status);
    }

    function createRecentSearchElement(query, index) {
        const element = document.createElement("button");
        const iconShell = document.createElement("span");
        const copy = document.createElement("span");
        const title = document.createElement("strong");

        element.type = "button";
        element.className = "command-global-search-result";
        element.id = `commandGlobalRecentSearchOption${index}`;
        element.setAttribute(RESULT_ATTRIBUTE, "true");
        element.setAttribute("data-search-result-index", String(index));
        element.setAttribute(
            "data-search-result-id",
            `recent-search-${index}`
        );
        element.setAttribute(
            "data-search-result-type",
            RECENT_SEARCH_RESULT_TYPE
        );
        element.setAttribute("data-search-result-title", query);
        element.setAttribute("role", "option");
        element.setAttribute("aria-selected", "false");

        iconShell.className = "command-global-search-result-icon";
        iconShell.setAttribute("aria-hidden", "true");
        iconShell.appendChild(createIcon("search"));

        copy.className = "command-global-search-result-copy";
        title.textContent = query;
        copy.appendChild(title);

        element.appendChild(iconShell);
        element.appendChild(copy);

        return element;
    }

    function createResultGroup(label, headingId) {
        const group = document.createElement("div");
        const heading = document.createElement("div");

        group.className = "command-global-search-result-group";
        group.setAttribute("role", "group");
        group.setAttribute("aria-labelledby", headingId);

        heading.className = "command-global-search-result-heading";
        heading.id = headingId;
        heading.textContent = label;
        group.appendChild(heading);

        return group;
    }

    function formatFileSize(sizeBytes) {
        const bytes = Number(sizeBytes);

        if (!Number.isFinite(bytes) || bytes < 0) {
            return "";
        }

        if (bytes < 1024) {
            return `${Math.round(bytes)} B`;
        }

        const units = ["KB", "MB", "GB", "TB"];
        let value = bytes / 1024;
        let unitIndex = 0;

        while (value >= 1024 && unitIndex < units.length - 1) {
            value /= 1024;
            unitIndex += 1;
        }

        const digits = value >= 100 ? 0 : value >= 10 ? 1 : 2;

        return `${value.toFixed(digits)} ${units[unitIndex]}`;
    }

    function normalizeRecentFileResult(upload, index) {
        if (!upload || typeof upload !== "object") {
            return null;
        }

        const documentId = normalizeText(
            upload.document_id ||
            upload.random_name ||
            upload.file_id
        );
        const title = normalizeText(
            upload.original_name ||
            upload.display_name ||
            upload.name ||
            documentId
        );
        const route = normalizeText(
            upload.reader_url ||
            upload.workspace_reader_url
        );

        if (!documentId || !title || !route) {
            return null;
        }

        return Object.assign({}, upload, {
            id: `recent-file-${documentId || index}`,
            type: "file",
            title,
            name: title,
            document_id: documentId,
            route,
            reader_url: route,
            size_label: formatFileSize(upload.size_bytes),
            location_label: normalizeText(
                upload.location_label ||
                upload.workspace_location_label ||
                upload.authorized_location_label
            ),
            uploaded_label: normalizeText(
                upload.recent_activity_reason ||
                upload.recent_activity_at
            )
        });
    }

    function normalizeRecentFilesPayload(payload) {
        if (!payload || typeof payload !== "object" || payload.ok === false) {
            return [];
        }

        const candidates = Array.isArray(payload.items)
            ? payload.items
            : Array.isArray(payload.uploads)
                ? payload.uploads
                : Array.isArray(payload.workspace_items)
                    ? payload.workspace_items
                    : [];

        return candidates.reduce(function (results, upload, index) {
            const result = normalizeRecentFileResult(upload, index);

            if (result) {
                results.push(result);
            }

            return results;
        }, []);
    }

    function canShowRecentFiles(elements) {
        const searchType = getSelectedSearchType(elements);

        return searchType === "all" || searchType === "files";
    }

    function buildRecentDefaultsUrl(elements, limit) {
        const endpoint = getRecentSearchEndpoint(elements?.form);

        if (!endpoint) {
            return null;
        }

        const recentUrl = new URL(endpoint, window.location.origin);

        recentUrl.searchParams.set("sort", "activity");
        recentUrl.searchParams.set("direction", "desc");
        recentUrl.searchParams.set(
            "limit",
            String(Math.max(1, Number(limit) || 1))
        );

        return recentUrl;
    }

    function shouldRefreshDefaultState(elements) {
        const query = normalizeText(elements?.input?.value);
        const minQueryLength = Number(
            api.constants.GLOBAL_SEARCH_MIN_QUERY_LENGTH
        ) || 2;
        const panelOpen = Boolean(
            elements?.results &&
            elements.results.hidden !== true
        );

        return panelOpen && query.length < minQueryLength;
    }

    async function fetchRecentDefaultFiles(elements, limit) {
        if (
            api.state.globalSearchRecentFilesLoaded ||
            api.state.globalSearchRecentFilesLoading
        ) {
            return;
        }

        const recentUrl = buildRecentDefaultsUrl(elements, limit);

        if (!recentUrl) {
            api.state.globalSearchRecentFiles = [];
            api.state.globalSearchRecentFilesLoaded = true;
            api.state.globalSearchRecentFilesUnavailable = true;

            if (shouldRefreshDefaultState(elements)) {
                renderReadyState(elements);
            }

            return;
        }

        if (
            api.state.globalSearchRecentController &&
            typeof api.state.globalSearchRecentController.abort ===
            "function"
        ) {
            api.state.globalSearchRecentController.abort();
        }

        const controller = new AbortController();

        api.state.globalSearchRecentController = controller;
        api.state.globalSearchRecentFilesLoading = true;

        try {
            const response = await fetch(recentUrl.href, {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                signal: controller.signal
            });

            if (!response.ok) {
                throw new Error(
                    `Recent search defaults request failed: ${response.status}`
                );
            }

            const payload = await response.json();

            if (api.state.globalSearchRecentController !== controller) {
                return;
            }

            api.state.globalSearchRecentFiles =
                normalizeRecentFilesPayload(payload);
            api.state.globalSearchRecentFilesLoaded = true;
            api.state.globalSearchRecentFilesUnavailable = false;
        } catch (error) {
            if (error?.name === "AbortError") {
                return;
            }

            console.warn(
                "[GLOBAL_SEARCH] Recent search defaults unavailable.",
                error
            );
            api.state.globalSearchRecentFiles = [];
            api.state.globalSearchRecentFilesLoaded = true;
            api.state.globalSearchRecentFilesUnavailable = true;
        } finally {
            if (api.state.globalSearchRecentController === controller) {
                api.state.globalSearchRecentController = null;
                api.state.globalSearchRecentFilesLoading = false;
            }
        }

        if (shouldRefreshDefaultState(elements)) {
            renderReadyState(elements);
        }
    }

    function renderDefaultSearchState(elements) {
        if (!elements.results) {
            return;
        }

        const suggestionLimit = getDefaultSuggestionLimit();
        const recentQueries = readRecentSearchQueries().slice(
            0,
            suggestionLimit
        );
        const recentQueryResults = recentQueries.map(function (query, index) {
            return {
                id: `recent-search-${index}`,
                type: RECENT_SEARCH_RESULT_TYPE,
                title: query,
                query
            };
        });
        const remainingSlots = Math.max(
            0,
            suggestionLimit - recentQueryResults.length
        );
        const includeRecentFiles = canShowRecentFiles(elements);
        const recentFileResults = includeRecentFiles
            ? Array.from(api.state.globalSearchRecentFiles || []).slice(
                0,
                remainingSlots
            )
            : [];
        const combinedResults = [
            ...recentQueryResults,
            ...recentFileResults
        ];

        api.state.globalSearchResults = combinedResults;
        api.state.globalSearchActiveIndex = -1;

        elements.results.replaceChildren();
        clearActiveResult(elements);
        setSeeAllVisible(elements, false);

        let resultIndex = 0;

        if (recentQueryResults.length) {
            const searchGroup = createResultGroup(
                "Recent searches",
                "commandGlobalRecentSearchHeading"
            );

            recentQueries.forEach(function (query) {
                searchGroup.appendChild(
                    createRecentSearchElement(query, resultIndex)
                );
                resultIndex += 1;
            });

            elements.results.appendChild(searchGroup);
        }

        if (recentFileResults.length) {
            const fileGroup = createResultGroup(
                "Recent files",
                "commandGlobalRecentFilesHeading"
            );

            recentFileResults.forEach(function (result) {
                fileGroup.appendChild(
                    createResultElement(result, resultIndex, elements)
                );
                resultIndex += 1;
            });

            elements.results.appendChild(fileGroup);
        }

        if (!combinedResults.length) {
            const waitingForRecentFiles = Boolean(
                includeRecentFiles &&
                !api.state.globalSearchRecentFilesLoaded
            );

            const recentFilesUnavailable = Boolean(
                includeRecentFiles &&
                api.state.globalSearchRecentFilesUnavailable
            );

            elements.results.appendChild(
                createSearchMessageElement({
                    state: "default",
                    icon: waitingForRecentFiles ? "history" : "manage_search",
                    title: waitingForRecentFiles
                        ? "Recent activity"
                        : recentFilesUnavailable
                            ? "Recent activity is unavailable"
                            : "No recent activity yet",
                    summary: waitingForRecentFiles
                        ? "Loading your recent files."
                        : "Start typing to search your authorized workspace."
                })
            );
        }

        setResultsOpen(elements, true, "default");
        setStatus(
            elements,
            combinedResults.length
                ? `${combinedResults.length} recent suggestion${combinedResults.length === 1 ? "" : "s"} available.`
                : "Search suggestions ready."
        );

        if (
            includeRecentFiles &&
            remainingSlots > 0 &&
            !api.state.globalSearchRecentFilesLoaded &&
            !api.state.globalSearchRecentFilesLoading
        ) {
            fetchRecentDefaultFiles(elements, remainingSlots);
        }
    }

    function renderReadyState(elements) {
        renderDefaultSearchState(elements);
    }

    function renderErrorState(elements, query) {
        renderSearchMessage(elements, {
            state: "error",
            icon: "search_off",
            title: "Search is temporarily unavailable",
            summary: "Try again in a moment, or open the full search page.",
            status: "Search is temporarily unavailable.",
            showAllResults: Boolean(normalizeText(query))
        });
    }

    function createEmptyElement(query) {
        return createSearchMessageElement({
            state: "empty",
            icon: "manage_search",
            title: "No matching results",
            summary: query
                ? "Open all results to continue on the full search page."
                : "Start typing to search Nations Systems."
        });
    }

    function normalizePayload(payload) {
        if (Array.isArray(payload)) {
            return {
                ok: true,
                results: payload,
                capability_request: null
            };
        }

        if (!payload || typeof payload !== "object") {
            return {
                ok: false,
                results: [],
                capability_request: null
            };
        }

        return {
            ok: payload.ok !== false,
            results: Array.isArray(payload.results)
                ? payload.results
                : [],
            capability_request:
                payload.capability_request &&
                typeof payload.capability_request === "object"
                    ? payload.capability_request
                    : null
        };
    }

    function getDefaultSuggestionLimit() {
        const configuredLimit = Number(
            api.constants.GLOBAL_SEARCH_DEFAULT_SUGGESTION_LIMIT
        );

        return Number.isFinite(configuredLimit) && configuredLimit > 0
            ? configuredLimit
            : 5;
    }

    function getVisibleResultsLimit() {
        const configuredLimit = Number(
            api.constants.GLOBAL_SEARCH_MAX_DROPDOWN_RESULTS
        );

        return Number.isFinite(configuredLimit) && configuredLimit > 0
            ? configuredLimit
            : 8;
    }

    function renderSearchResults(elements, query, payload) {
        const normalizedPayload = normalizePayload(payload);
        const visibleResultsLimit = getVisibleResultsLimit();
        const results = normalizedPayload.results.slice(
            0,
            visibleResultsLimit
        );

        if (!normalizedPayload.ok) {
            renderErrorState(elements, query);
            return;
        }

        if (
            normalizedPayload.capability_request &&
            results.length < visibleResultsLimit
        ) {
            results.push(
                Object.assign(
                    {
                        type: "capability_request",
                        title: "Request this capability",
                        summary: "Send this request to your group admin.",
                        icon: "add_task"
                    },
                    normalizedPayload.capability_request
                )
            );
        }

        api.state.globalSearchResults = results;
        api.state.globalSearchActiveIndex = -1;

        if (!elements.results) {
            return;
        }

        elements.results.replaceChildren();

        if (!results.length) {
            elements.results.appendChild(
                createEmptyElement(query)
            );
            setSeeAllVisible(elements, Boolean(normalizeText(query)));
            setResultsOpen(elements, true, "empty");
            setStatus(elements, "No matching results.");
            return;
        }

        const fragment = document.createDocumentFragment();

        results.forEach(function (result, index) {
            fragment.appendChild(
                createResultElement(result, index, elements)
            );
        });

        elements.results.appendChild(fragment);
        setSeeAllVisible(elements, true);
        setResultsOpen(elements, true, "results");
        setStatus(
            elements,
            `${results.length} result${results.length === 1 ? "" : "s"} available.`
        );
    }

    function setActiveResult(elements, index) {
        const results = Array.from(
            elements.results?.querySelectorAll(RESULT_SELECTOR) || []
        );

        if (!results.length) {
            clearActiveResult(elements);
            return;
        }

        const nextIndex = Math.max(
            0,
            Math.min(index, results.length - 1)
        );

        api.state.globalSearchActiveIndex = nextIndex;

        results.forEach(function (item, itemIndex) {
            const isActive = itemIndex === nextIndex;

            item.setAttribute(
                "aria-selected",
                isActive ? "true" : "false"
            );
        });

        if (elements.input) {
            elements.input.setAttribute(
                "aria-activedescendant",
                results[nextIndex].id
            );
        }

        results[nextIndex].scrollIntoView({
            block: "nearest"
        });
    }

    function getLaunchMode(route) {
        return isWorkspaceReaderRoute(route)
            ? "reader"
            : "search_result";
    }

    function fallbackToRoute(route) {
        const cleanRoute = normalizeText(route);

        if (!cleanRoute) {
            return false;
        }

        window.location.assign(cleanRoute);
        return false;
    }

    function loadWorkspaceRoute(route, moduleId, options) {
        const relativeRoute = getSameOriginRelativeRoute(route);
        const cleanRoute = relativeRoute || normalizeText(route);

        if (!cleanRoute) {
            return false;
        }

        if (
            relativeRoute &&
            isInternalRoute(relativeRoute) &&
            typeof api.loadWorkspace === "function"
        ) {
            try {
                const result = api.loadWorkspace(
                    relativeRoute,
                    moduleId,
                    Object.assign(
                        {
                            push: true,
                            async: true
                        },
                        options || {}
                    )
                );

                if (
                    result &&
                    typeof result.then === "function"
                ) {
                    result.then(function (resolved) {
                        if (resolved === false) {
                            fallbackToRoute(relativeRoute);
                        }
                    }).catch(function (error) {
                        console.warn(
                            "[GLOBAL_SEARCH] Async right-pane launch failed; falling back to hard navigation.",
                            error
                        );
                        fallbackToRoute(relativeRoute);
                    });
                } else if (result === false) {
                    fallbackToRoute(relativeRoute);
                }

                return true;
            } catch (error) {
                console.warn(
                    "[GLOBAL_SEARCH] Async right-pane launch failed; falling back to hard navigation.",
                    error
                );
                fallbackToRoute(relativeRoute);
                return true;
            }
        }

        return fallbackToRoute(cleanRoute);
    }

    function buildResultLoadOptions(result, route, elements) {
        const type = normalizeResultType(result?.type);
        const title = getResultTitle(result);

        return {
            push: true,
            async: true,
            launchMode: getLaunchMode(route),
            source: "command_sidebar_search",
            backRoute: buildSearchBackRoute(elements),
            searchQuery: normalizeText(elements?.input?.value),
            searchType: getSelectedSearchType(elements),
            resultId: getResultId(result, api.state.globalSearchActiveIndex),
            resultType: type,
            resultTitle: title
        };
    }

    function activateRecentSearchResult(elements, result) {
        const query = normalizeText(
            result?.query || result?.title
        );

        if (!query || !elements.input) {
            return false;
        }

        rememberRecentSearchQuery(query);
        elements.input.value = query;
        setClearVisible(elements, true);
        api.state.globalSearchInputDirty = true;
        clearActiveResult(elements);
        refocusSearchInput(elements);
        activateSearchSurface(elements);

        return true;
    }

    function openResult(elements, index) {
        const result = api.state.globalSearchResults[index];

        if (!result) {
            return false;
        }

        if (normalizeResultType(result?.type) === RECENT_SEARCH_RESULT_TYPE) {
            return activateRecentSearchResult(elements, result);
        }

        const route = getNavigableResultRoute(result, elements);
        const activeQuery = normalizeText(elements?.input?.value);
        const minQueryLength = Number(
            api.constants.GLOBAL_SEARCH_MIN_QUERY_LENGTH
        ) || 2;

        if (activeQuery.length >= minQueryLength) {
            rememberRecentSearchQuery(activeQuery);
        }

        closeSearchResults(elements);

        if (!route) {
            return false;
        }

        return loadWorkspaceRoute(
            route,
            getResultModule(result, route),
            buildResultLoadOptions(
                result,
                route,
                elements
            )
        ) !== false;
    }

    function openFullSearchPage(elements) {
        const query = normalizeText(elements.input?.value);

        if (!query) {
            return false;
        }

        const searchUrl = buildSearchResultsUrl(
            elements,
            query
        );
        const route = getRelativeUrl(searchUrl);

        api.state.globalSearchCommittedQuery = query;
        api.state.globalSearchInputDirty = false;
        rememberRecentSearchQuery(query);

        closeSearchResults(elements);

        return loadWorkspaceRoute(
            route,
            SEARCH_MODULE_ID,
            {
                push: true,
                async: true,
                launchMode: "search_page",
                source: "command_sidebar_search",
                searchQuery: query,
                searchType: getSelectedSearchType(elements),
                backRoute: route
            }
        ) !== false;
    }

    function getResultElementFromEvent(event) {
        return event.target instanceof Element
            ? event.target.closest(RESULT_SELECTOR)
            : null;
    }

    function getResultIndexFromElement(element) {
        const index = Number(
            element?.getAttribute("data-search-result-index")
        );

        return Number.isInteger(index) ? index : -1;
    }

    function refocusSearchInput(elements) {
        if (!elements.input || document.activeElement === elements.input) {
            return;
        }

        elements.input.focus({
            preventScroll: true
        });
    }

    function openDropdownResult(elements, target) {
        const index = getResultIndexFromElement(target);

        if (index < 0) {
            return false;
        }

        setActiveResult(elements, index);
        return openResult(elements, index);
    }

    function activateSearchSurface(elements) {
        scheduleSearch(elements);
    }

    function selectSearchScope(elements, target) {
        setSelectedSearchType(
            elements,
            target?.getAttribute(
                "data-command-global-search-scope"
            )
        );

        api.state.globalSearchInputDirty = true;

        refocusSearchInput(elements);
        activateSearchSurface(elements);
    }

    function isCurrentSearchRequest(
        elements,
        query,
        generation,
        controller
    ) {
        return Boolean(
            Number(api.state.globalSearchRequestGeneration || 0) === generation &&
            api.state.globalSearchController === controller &&
            normalizeText(elements?.input?.value) === query
        );
    }

    async function fetchSearchResults(
        elements,
        query,
        generation
    ) {
        if (!query) {
            renderReadyState(elements);
            return;
        }

        if (
            Number(api.state.globalSearchRequestGeneration || 0) !==
            generation
        ) {
            return;
        }

        abortActiveSearchRequest();

        const controller = new AbortController();

        api.state.globalSearchController = controller;
        setSearchPending(elements, true, query);

        try {
            const response = await fetch(
                buildSearchUrl(elements, query).href,
                {
                    method: "GET",
                    credentials: "same-origin",
                    headers: {
                        "Accept": "application/json",
                        "X-Requested-With": "XMLHttpRequest"
                    },
                    signal: controller.signal
                }
            );

            if (!isCurrentSearchRequest(
                elements,
                query,
                generation,
                controller
            )) {
                return;
            }

            if (response.status === SEARCH_UNAVAILABLE_STATUS) {
                api.state.globalSearchApiUnavailable = true;
                renderErrorState(elements, query);
                return;
            }

            if (!response.ok) {
                throw new Error(
                    `Global search request failed: ${response.status}`
                );
            }

            const payload = await response.json();

            if (!isCurrentSearchRequest(
                elements,
                query,
                generation,
                controller
            )) {
                return;
            }

            renderSearchResults(elements, query, payload);
        } catch (error) {
            if (error?.name === "AbortError") {
                return;
            }

            if (!isCurrentSearchRequest(
                elements,
                query,
                generation,
                controller
            )) {
                return;
            }

            console.warn(
                "[GLOBAL_SEARCH] Live search failed.",
                error
            );
            renderErrorState(elements, query);
        } finally {
            if (isCurrentSearchRequest(
                elements,
                query,
                generation,
                controller
            )) {
                api.state.globalSearchController = null;
                setSearchPending(elements, false);
            }
        }
    }

    function scheduleSearch(elements) {
        const query = normalizeText(elements.input?.value);
        const minQueryLength = Number(
            api.constants.GLOBAL_SEARCH_MIN_QUERY_LENGTH
        ) || 2;
        const panelOpen = Boolean(
            elements.results &&
            elements.results.hidden !== true
        );

        setClearVisible(elements, Boolean(query));
        cancelSearchDebounce();

        const generation = invalidateSearchRequest(elements);

        if (!query || query.length < minQueryLength) {
            renderReadyState(elements);
            return;
        }

        if (api.state.globalSearchApiUnavailable) {
            renderErrorState(elements, query);
            return;
        }

        if (!panelOpen) {
            renderReadyState(elements);
        }

        setSearchPending(elements, true, query);

        api.state.globalSearchDebounceTimer =
            window.setTimeout(
                function () {
                    fetchSearchResults(
                        elements,
                        query,
                        generation
                    );
                },
                Number(api.constants.GLOBAL_SEARCH_DEBOUNCE_MS) || 180
            );
    }

    function handleSearchKeydown(event, elements) {
        const panelOpen = Boolean(
            elements.results &&
            elements.results.hidden !== true
        );
        const resultsOpen = Boolean(
            panelOpen &&
            api.state.globalSearchResults.length
        );

        if (event.key === "Escape") {
            if (panelOpen) {
                event.preventDefault();
                closeSearchResults(elements);
            }

            return;
        }

        if (!resultsOpen) {
            return;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();
            setActiveResult(
                elements,
                api.state.globalSearchActiveIndex + 1
            );
            return;
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();
            setActiveResult(
                elements,
                api.state.globalSearchActiveIndex <= 0
                    ? api.state.globalSearchResults.length - 1
                    : api.state.globalSearchActiveIndex - 1
            );
            return;
        }

        if (
            event.key === "Enter" &&
            api.state.globalSearchActiveIndex >= 0
        ) {
            event.preventDefault();
            openResult(
                elements,
                api.state.globalSearchActiveIndex
            );
        }
    }

    function bindCommittedSearchRouteSync(elements) {
        window.addEventListener(
            "popstate",
            function () {
                syncCommittedSearchState(elements);
            }
        );

        window.addEventListener(
            "solomon:workspace-loaded",
            function () {
                syncCommittedSearchState(elements);
            }
        );

        window.addEventListener(
            "solomon:workspace-route-changed",
            function () {
                syncCommittedSearchState(elements);
            }
        );
    }

    function bindGlobalSearch(elements) {
        if (
            !elements.form ||
            !elements.input ||
            elements.form.getAttribute(
                "data-command-global-search-bound"
            ) === "true"
        ) {
            return false;
        }

        elements.form.setAttribute(
            "data-command-global-search-bound",
            "true"
        );
        elements.form.setAttribute(
            "data-command-search-contract",
            api.constants.GLOBAL_SEARCH_CONTRACT
        );

        if (elements.results) {
            elements.results.setAttribute(
                "data-command-search-state",
                "idle"
            );
        }

        setSelectedSearchType(
            elements,
            elements.form.getAttribute(
                "data-command-search-type"
            )
        );
        setSeeAllVisible(elements, false);
        syncCommittedSearchState(elements);

        setClearVisible(
            elements,
            Boolean(normalizeText(elements.input.value))
        );

        elements.input.addEventListener(
            "input",
            function () {
                allowSuggestionsAfterInput();
                activateSearchSurface(elements);
            }
        );

        elements.input.addEventListener(
            "focus",
            function () {
                syncCommittedSearchState(elements);
                activateSearchSurface(elements);
            }
        );

        elements.input.addEventListener(
            "click",
            function () {
                activateSearchSurface(elements);
            }
        );

        elements.input.addEventListener(
            "keydown",
            function (event) {
                handleSearchKeydown(event, elements);
            }
        );

        elements.control?.addEventListener(
            "pointerdown",
            function (event) {
                if (
                    event.target instanceof Element &&
                    event.target.closest("button, input")
                ) {
                    return;
                }

                event.preventDefault();
                refocusSearchInput(elements);
                activateSearchSurface(elements);
            }
        );

        elements.form.addEventListener(
            "submit",
            function (event) {
                const query = normalizeText(elements.input.value);

                event.preventDefault();

                if (!query) {
                    refocusSearchInput(elements);
                    renderReadyState(elements);
                    return;
                }

                openFullSearchPage(elements);
            }
        );

        Array.from(elements.scopes || []).forEach(function (scope) {
            scope.addEventListener(
                "pointerdown",
                function (event) {
                    event.preventDefault();
                }
            );

            scope.addEventListener(
                "click",
                function (event) {
                    event.preventDefault();
                    event.stopPropagation();
                    selectSearchScope(elements, scope);
                }
            );
        });

        elements.results?.addEventListener(
            "pointerdown",
            function (event) {
                const target = getResultElementFromEvent(event);

                if (!target) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();
            },
            true
        );

        elements.results?.addEventListener(
            "click",
            function (event) {
                const target = getResultElementFromEvent(event);

                if (!target) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();
                event.stopImmediatePropagation();
                openDropdownResult(elements, target);
            },
            true
        );

        elements.clear?.addEventListener(
            "click",
            function (event) {
                event.preventDefault();
                event.stopPropagation();

                cancelSearchDebounce();
                invalidateSearchRequest(elements);
                elements.input.value = "";
                setClearVisible(elements, false);
                allowSuggestionsAfterInput();
                refocusSearchInput(elements);
                renderReadyState(elements);
            }
        );

        document.addEventListener(
            "pointerdown",
            function (event) {
                if (
                    elements.form &&
                    elements.form.contains(event.target)
                ) {
                    return;
                }

                closeSearchResults(elements);
            }
        );

        bindCommittedSearchRouteSync(elements);

        return true;
    }

    api.initializeGlobalSearch = function () {
        const elements = getSearchElements();

        if (elements.form && elements.input) {
            bindGlobalSearch(elements);
            api.state.globalSearchBound = true;
        }

        return Boolean(elements.form && elements.input);
    };
}());