/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_source_picker.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   Existing-file picker for SolomonAI conversation sources.

   Presents the server-authorized file catalog, supports collection
   navigation, search, multi-selection, asynchronous Reader access, and
   attachment submission. JavaScript controls presentation only; file
   access and conversation membership remain server-authoritative.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before source picker."
        );
    }

    const contract = modules.requireModule("contract");
    const transport = modules.requireModule("source_transport");
    const {
        cleanValue,
        setElementVisibility
    } = contract;
    const {
        SOURCE_PICKER_DEFAULT_SCOPE,
        SOURCE_PICKER_SCOPES,
        SOURCE_PICKER_SEARCH_DEBOUNCE_MS
    } = contract.constants;

    const SCOPE_LABELS = Object.freeze({
        "": "Recent",
        my_files: "My Files",
        company_library: "Company Library",
        shared_with_me: "Shared with me"
    });

    const WORKSPACE_LISTING_CONTRACT_FALLBACK =
        "nations_workspace_listing_v1";
    const DOCUMENTS_MODULE_ID = "documents";
    const DEFAULT_SOLOMON_WORKSPACE_ROUTE = "/ai";
    const PICKER_READER_LAUNCH_SELECTOR = [
        "[data-solomon-ai-source-picker-reader-url][href]",
        ".solomon-ai-file-picker__item-open[href]"
    ].join(", ");

    function getState(elements) {
        const picker = elements?.sourcePicker;

        if (!picker) {
            return null;
        }

        if (!picker.__solomonSourcePickerState) {
            picker.__solomonSourcePickerState = {
                files: [],
                loading: false,
                open: false,
                query: "",
                requestSequence: 0,
                returnFocus: null,
                scope: SOURCE_PICKER_DEFAULT_SCOPE,
                searchTimer: null,
                selected: new Set()
            };
        }

        return picker.__solomonSourcePickerState;
    }

    function setPickerState(elements, state) {
        elements?.sourcePicker?.setAttribute(
            "data-solomon-ai-source-picker-state",
            cleanValue(state) || "ready"
        );
    }

    function setStatus(elements, message, state = "info") {
        if (!elements?.sourcePickerStatus) {
            return;
        }

        elements.sourcePickerStatus.textContent = cleanValue(message);
        elements.sourcePickerStatus.setAttribute(
            "data-solomon-ai-source-picker-status-state",
            cleanValue(state) || "info"
        );
    }

    function setEmptyState(elements, visible, message = "") {
        setElementVisibility(
            elements?.sourcePickerEmpty,
            visible
        );

        if (elements?.sourcePickerEmptyMessage && message) {
            elements.sourcePickerEmptyMessage.textContent = message;
        }
    }

    function formatFileSize(value) {
        const size = Number(value);

        if (!Number.isFinite(size) || size < 0) {
            return "";
        }

        if (size < 1024) {
            return `${size} B`;
        }

        if (size < 1024 * 1024) {
            return `${Math.round(size / 1024)} KB`;
        }

        return `${(
            size /
            (1024 * 1024)
        ).toFixed(1)} MB`;
    }

    function getFileIcon(file) {
        const extension = cleanValue(
            file?.extension
        ).toLowerCase();

        if (extension === ".pdf") {
            return "picture_as_pdf";
        }

        if (
            extension === ".xlsx" ||
            extension === ".xls" ||
            extension === ".csv"
        ) {
            return "table_view";
        }

        if (
            extension === ".png" ||
            extension === ".jpg" ||
            extension === ".jpeg" ||
            extension === ".webp" ||
            extension === ".tif" ||
            extension === ".tiff"
        ) {
            return "image";
        }

        return "description";
    }

    function getScopeLabel(scope) {
        return (
            SCOPE_LABELS[
                cleanValue(scope).toLowerCase()
            ] ||
            "Files"
        );
    }

    function createTextElement(tagName, className, text) {
        const element = document.createElement(tagName);

        if (className) {
            element.className = className;
        }

        element.textContent = cleanValue(text);

        return element;
    }

    function getSameOriginUrl(value) {
        const cleanUrl = cleanValue(value);

        if (!cleanUrl) {
            return null;
        }

        try {
            const url = new URL(cleanUrl, window.location.origin);
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

    function isWorkspaceReaderRoute(value) {
        const url = getSameOriginUrl(value);
        const pathParts = url?.pathname
            .split("/")
            .filter(Boolean) || [];

        return (
            pathParts.length >= 4 &&
            pathParts[0] === "workspace" &&
            (
                pathParts[1] === "file" ||
                pathParts[1] === "document"
            ) &&
            pathParts[3] === "reader"
        );
    }

    function getRightPaneCallerRoute() {
        const route = [
            window.location.pathname || "/",
            window.location.search || "",
            window.location.hash || ""
        ].join("");

        if (isWorkspaceReaderRoute(route)) {
            return DEFAULT_SOLOMON_WORKSPACE_ROUTE;
        }

        return route.startsWith("/")
            ? route
            : DEFAULT_SOLOMON_WORKSPACE_ROUTE;
    }

    function appendReaderBackRoute(readerUrl, backRoute) {
        const url = getSameOriginUrl(readerUrl);
        const cleanBackRoute = cleanValue(backRoute);

        if (!url || !isWorkspaceReaderRoute(getRelativeUrl(url))) {
            return "";
        }

        if (
            !cleanBackRoute ||
            !cleanBackRoute.startsWith("/") ||
            isWorkspaceReaderRoute(cleanBackRoute)
        ) {
            return getRelativeUrl(url);
        }

        url.searchParams.set("back", cleanBackRoute);

        return getRelativeUrl(url);
    }

    function buildPickerReaderUrl(readerUrl) {
        return appendReaderBackRoute(
            readerUrl,
            getRightPaneCallerRoute()
        );
    }

    function getPickerFileReaderUrl(file) {
        return cleanValue(
            file?.reader_url ||
            file?.readerUrl ||
            file?.workspace_reader_url ||
            file?.workspaceReaderUrl ||
            file?.document_reader_url ||
            file?.documentReaderUrl
        );
    }

    function getPickerFileMimeType(file) {
        return cleanValue(
            file?.mime_type ||
            file?.mimeType ||
            file?.mime ||
            file?.content_type ||
            file?.contentType
        );
    }

    function getSharedListingContract() {
        return cleanValue(
            window.NationsCommandSidebar
                ?.constants
                ?.WORKSPACE_LISTING_CONTRACT
        ) || WORKSPACE_LISTING_CONTRACT_FALLBACK;
    }

    function setOptionalAttribute(element, name, value) {
        const clean = cleanValue(value);

        if (clean) {
            element.setAttribute(name, clean);
        } else {
            element.removeAttribute(name);
        }
    }

    function applyPickerReaderLaunchContract(
        openLink,
        file,
        documentId,
        originalName,
        readerUrl,
        fullReaderUrl
    ) {
        const mimeType = getPickerFileMimeType(file);
        const callerRoute = getRightPaneCallerRoute();

        openLink.setAttribute("data-workspace-object", "");
        openLink.setAttribute("data-workspace-object-type", "file");
        openLink.setAttribute("data-workspace-object-kind", "file");
        openLink.setAttribute(
            "data-workspace-object-route",
            fullReaderUrl
        );
        openLink.setAttribute(
            "data-workspace-object-module",
            DOCUMENTS_MODULE_ID
        );
        openLink.setAttribute(
            "data-workspace-object-open-enabled",
            "true"
        );
        openLink.setAttribute(
            "data-workspace-listing-contract",
            getSharedListingContract()
        );

        setOptionalAttribute(
            openLink,
            "data-workspace-object-id",
            documentId
        );
        setOptionalAttribute(
            openLink,
            "data-workspace-object-name",
            originalName
        );
        setOptionalAttribute(
            openLink,
            "data-workspace-object-mime",
            mimeType
        );

        setOptionalAttribute(
            openLink,
            "data-document-id",
            documentId
        );
        setOptionalAttribute(
            openLink,
            "data-document-name",
            originalName
        );
        openLink.setAttribute(
            "data-document-route",
            fullReaderUrl
        );
        openLink.setAttribute(
            "data-document-open-enabled",
            "true"
        );
        openLink.setAttribute(
            "data-document-reader-url",
            fullReaderUrl
        );
        setOptionalAttribute(
            openLink,
            "data-document-mime",
            mimeType
        );

        openLink.setAttribute(
            "data-command-route",
            fullReaderUrl
        );
        openLink.setAttribute(
            "data-command-module",
            DOCUMENTS_MODULE_ID
        );
        openLink.setAttribute(
            "data-command-shell-navigation",
            "true"
        );

        openLink.setAttribute(
            "data-solomon-ai-source-picker-reader-url",
            fullReaderUrl
        );
        openLink.setAttribute(
            "data-solomon-ai-source-picker-reader-back-route",
            callerRoute
        );
        openLink.setAttribute(
            "data-right-pane-content-launch",
            "reader"
        );
        openLink.setAttribute(
            "data-right-pane-content-back-route",
            callerRoute
        );

        if (readerUrl !== fullReaderUrl) {
            openLink.setAttribute(
                "data-solomon-ai-source-picker-original-reader-url",
                readerUrl
            );
        }
    }

    function getReaderLaunchRoute(control) {
        return getSameOriginRelativeRoute(
            control?.getAttribute("data-workspace-object-route") ||
            control?.getAttribute("data-document-route") ||
            control?.getAttribute("data-command-route") ||
            control?.getAttribute(
                "data-solomon-ai-source-picker-reader-url"
            ) ||
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
                        source: "solomon_ai_source_picker",
                        async: true
                    }
                );

                if (result !== false) {
                    return true;
                }
            } catch (error) {
                console.warn(
                    "[SOLOMON_AI_SOURCE_PICKER] Async Reader launch failed; falling back to hard navigation.",
                    error
                );
            }
        }

        window.location.assign(cleanRoute);
        return false;
    }

    function createPickerItem(file) {
        const documentId = cleanValue(
            file?.document_id
        );
        const originalName = cleanValue(
            file?.original_name ||
            file?.filename ||
            documentId
        );
        const selectable = Boolean(
            documentId &&
            file?.selectable !== false &&
            file?.attached !== true
        );
        const attached = file?.attached === true;
        const item = document.createElement("article");
        const option = document.createElement("button");
        const icon = createTextElement(
            "span",
            "solomon-ai-file-picker__item-icon icon",
            getFileIcon(file)
        );
        const copy = document.createElement("span");
        const detailParts = [
            getScopeLabel(file?.access_scope),
            formatFileSize(file?.size_bytes)
        ].filter(Boolean);
        const state = createTextElement(
            "span",
            "solomon-ai-file-picker__item-state",
            attached ? "Already added" : "Select"
        );

        item.className = "solomon-ai-file-picker__item";
        item.setAttribute(
            "data-solomon-ai-source-picker-item",
            ""
        );
        item.setAttribute(
            "data-document-id",
            documentId
        );

        if (attached) {
            item.classList.add("is-attached");
        }

        option.type = "button";
        option.className = "solomon-ai-file-picker__option";
        option.setAttribute(
            "data-solomon-ai-source-picker-option",
            ""
        );
        option.setAttribute(
            "data-document-id",
            documentId
        );
        option.setAttribute("role", "option");
        option.setAttribute("aria-selected", "false");
        option.disabled = !selectable;

        copy.className = "solomon-ai-file-picker__item-copy";
        copy.append(
            createTextElement(
                "strong",
                "",
                originalName
            ),
            createTextElement(
                "span",
                "",
                detailParts.join(" · ")
            )
        );

        option.append(
            icon,
            copy,
            state
        );
        item.append(option);

        const readerUrl = getPickerFileReaderUrl(file);
        const fullReaderUrl = buildPickerReaderUrl(readerUrl);

        if (fullReaderUrl) {
            const openLink = document.createElement("a");
            const openIcon = createTextElement(
                "span",
                "icon",
                "open_in_new"
            );

            openLink.className =
                "solomon-ai-file-picker__item-open";
            openLink.href = fullReaderUrl;
            openLink.setAttribute(
                "aria-label",
                `Open ${originalName} in Reader`
            );
            openLink.title = "Open in Reader";
            applyPickerReaderLaunchContract(
                openLink,
                file,
                documentId,
                originalName,
                readerUrl,
                fullReaderUrl
            );
            openLink.append(openIcon);
            item.append(openLink);
        }

        return item;
    }

    function updateSelection(elements) {
        const state = getState(elements);

        if (!state) {
            return;
        }

        const selectedCount = state.selected.size;

        elements?.sourcePickerList
            ?.querySelectorAll(
                "[data-solomon-ai-source-picker-option]"
            )
            .forEach(function (option) {
                const documentId = cleanValue(
                    option.getAttribute(
                        "data-document-id"
                    )
                );
                const selected = state.selected.has(
                    documentId
                );

                option.classList.toggle(
                    "is-selected",
                    selected
                );
                option.setAttribute(
                    "aria-selected",
                    selected ? "true" : "false"
                );

                const itemState = option.querySelector(
                    ".solomon-ai-file-picker__item-state"
                );

                if (itemState && !option.disabled) {
                    itemState.textContent = selected
                        ? "Selected"
                        : "Select";
                }
            });

        if (elements?.sourcePickerSelection) {
            elements.sourcePickerSelection.textContent = (
                selectedCount === 1
                    ? "1 file selected"
                    : selectedCount > 1
                        ? `${selectedCount} files selected`
                        : "No files selected"
            );
        }

        if (elements?.sourcePickerAttach) {
            elements.sourcePickerAttach.disabled = Boolean(
                state.loading ||
                !selectedCount
            );
        }
    }

    function renderCatalog(elements, packet) {
        const state = getState(elements);
        const files = Array.isArray(packet?.files)
            ? packet.files
            : [];

        if (!state || !elements?.sourcePickerList) {
            return false;
        }

        state.files = files;

        const selectableIds = new Set(
            files
                .filter(function (file) {
                    return (
                        file?.selectable !== false &&
                        file?.attached !== true
                    );
                })
                .map(function (file) {
                    return cleanValue(file?.document_id);
                })
                .filter(Boolean)
        );

        state.selected = new Set(
            Array.from(state.selected).filter(
                function (documentId) {
                    return selectableIds.has(documentId);
                }
            )
        );

        elements.sourcePickerList.replaceChildren(
            ...files.map(createPickerItem)
        );

        const hasFiles = files.length > 0;

        setElementVisibility(
            elements.sourcePickerList,
            hasFiles
        );

        setEmptyState(
            elements,
            !hasFiles,
            state.query
                ? "No files match this search."
                : "No files are available in this collection."
        );

        const availableCount = Number(
            packet?.available_count
        );

        setStatus(
            elements,
            hasFiles
                ? (
                    Number.isFinite(availableCount)
                        ? `${availableCount} files available to add.`
                        : `${files.length} files found.`
                )
                : "",
            "info"
        );

        updateSelection(elements);
        return true;
    }

    async function loadCatalog(elements) {
        const state = getState(elements);

        if (!state) {
            return false;
        }

        const requestSequence = (
            state.requestSequence + 1
        );

        state.requestSequence = requestSequence;
        state.loading = true;

        setPickerState(elements, "loading");
        setStatus(
            elements,
            "Loading authorized files…",
            "info"
        );
        setEmptyState(elements, false);
        updateSelection(elements);

        try {
            const packet = await transport.requestAvailableFiles(
                elements,
                {
                    scope: state.scope,
                    query: state.query
                }
            );

            if (
                !state.open ||
                requestSequence !== state.requestSequence
            ) {
                return false;
            }

            renderCatalog(elements, packet);
            setPickerState(elements, "ready");
            return true;
        } catch (error) {
            if (
                !state.open ||
                requestSequence !== state.requestSequence
            ) {
                return false;
            }

            elements?.sourcePickerList?.replaceChildren();
            setElementVisibility(
                elements?.sourcePickerList,
                false
            );
            setEmptyState(
                elements,
                true,
                cleanValue(error?.message) ||
                    "Files could not be loaded."
            );
            setStatus(
                elements,
                cleanValue(error?.message) ||
                    "Files could not be loaded.",
                "error"
            );
            setPickerState(elements, "error");
            return false;
        } finally {
            if (requestSequence === state.requestSequence) {
                state.loading = false;
                updateSelection(elements);
            }
        }
    }

    function activateScope(elements, scope) {
        const state = getState(elements);
        const cleanScope = cleanValue(scope).toLowerCase();

        if (
            !state ||
            !SOURCE_PICKER_SCOPES.includes(cleanScope)
        ) {
            return false;
        }

        state.scope = cleanScope;
        state.selected.clear();

        elements.sourcePickerScopes.forEach(
            function (button) {
                const buttonScope = cleanValue(
                    button.getAttribute(
                        "data-solomon-ai-source-picker-scope"
                    )
                ).toLowerCase();
                const active = buttonScope === cleanScope;

                button.classList.toggle(
                    "is-active",
                    active
                );
                button.setAttribute(
                    "aria-selected",
                    active ? "true" : "false"
                );
                button.tabIndex = active ? 0 : -1;
            }
        );

        updateSelection(elements);
        loadCatalog(elements);
        return true;
    }

    function toggleSelection(elements, option) {
        const state = getState(elements);
        const documentId = cleanValue(
            option?.getAttribute(
                "data-document-id"
            )
        );

        if (
            !state ||
            !documentId ||
            option?.disabled
        ) {
            return false;
        }

        if (state.selected.has(documentId)) {
            state.selected.delete(documentId);
        } else {
            state.selected.add(documentId);
        }

        updateSelection(elements);
        return true;
    }

    function scheduleSearch(elements) {
        const state = getState(elements);

        if (!state) {
            return;
        }

        window.clearTimeout(state.searchTimer);

        state.searchTimer = window.setTimeout(
            function () {
                state.query = cleanValue(
                    elements?.sourcePickerSearch?.value
                );
                state.selected.clear();
                updateSelection(elements);
                loadCatalog(elements);
            },
            SOURCE_PICKER_SEARCH_DEBOUNCE_MS
        );
    }

    function getFocusableElements(elements) {
        if (!elements?.sourcePickerDialog) {
            return [];
        }

        return Array.from(
            elements.sourcePickerDialog.querySelectorAll(
                "a[href], button:not([disabled]), " +
                "input:not([disabled]), [tabindex]:not([tabindex='-1'])"
            )
        ).filter(function (element) {
            return !element.hidden;
        });
    }

    function handlePickerKeydown(event, elements) {
        const state = getState(elements);

        if (!state?.open) {
            return;
        }

        if (event.key === "Escape") {
            event.preventDefault();
            close(elements);
            return;
        }

        if (event.key !== "Tab") {
            return;
        }

        const focusable = getFocusableElements(elements);

        if (!focusable.length) {
            event.preventDefault();
            elements.sourcePickerDialog?.focus();
            return;
        }

        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (
            event.shiftKey &&
            document.activeElement === first
        ) {
            event.preventDefault();
            last.focus();
        } else if (
            !event.shiftKey &&
            document.activeElement === last
        ) {
            event.preventDefault();
            first.focus();
        }
    }

    async function attachSelected(elements) {
        const state = getState(elements);

        if (
            !state ||
            state.loading ||
            !state.selected.size
        ) {
            return false;
        }

        state.loading = true;
        setPickerState(elements, "attaching");
        setStatus(
            elements,
            "Adding selected files…",
            "info"
        );
        updateSelection(elements);

        try {
            const packet = await transport.attachConversationSources(
                elements,
                Array.from(state.selected)
            );

            if (!packet) {
                throw new Error(
                    "The selected files could not be added."
                );
            }

            close(elements);
            return true;
        } catch (error) {
            setPickerState(elements, "error");
            setStatus(
                elements,
                cleanValue(error?.message) ||
                    "The selected files could not be added.",
                "error"
            );
            return false;
        } finally {
            state.loading = false;
            updateSelection(elements);
        }
    }

    function close(elements, options = {}) {
        const state = getState(elements);

        if (!state?.open) {
            return false;
        }

        state.open = false;
        state.requestSequence += 1;
        state.selected.clear();

        window.clearTimeout(state.searchTimer);

        elements.sourcePicker.hidden = true;
        elements.sourcePicker.setAttribute(
            "aria-hidden",
            "true"
        );
        document.body.removeAttribute(
            "data-solomon-ai-source-picker-open"
        );
        setPickerState(elements, "closed");
        updateSelection(elements);

        const returnFocus = state.returnFocus;

        state.returnFocus = null;

        if (
            options?.focus !== false &&
            returnFocus &&
            returnFocus.isConnected &&
            typeof returnFocus.focus === "function"
        ) {
            returnFocus.focus({
                preventScroll: true
            });
        }

        return true;
    }

    function open(elements) {
        const state = getState(elements);

        initialize(elements);

        if (
            !state ||
            !elements?.sourcePicker ||
            transport.isPending(elements)
        ) {
            return false;
        }

        state.open = true;
        state.scope = SOURCE_PICKER_DEFAULT_SCOPE;
        state.query = "";
        state.selected.clear();
        state.returnFocus = document.activeElement;

        if (elements.sourcePickerSearch) {
            elements.sourcePickerSearch.value = "";
        }

        elements.sourcePicker.hidden = false;
        elements.sourcePicker.setAttribute(
            "aria-hidden",
            "false"
        );
        document.body.setAttribute(
            "data-solomon-ai-source-picker-open",
            "true"
        );

        activateScope(
            elements,
            SOURCE_PICKER_DEFAULT_SCOPE
        );

        window.requestAnimationFrame(function () {
            (
                elements.sourcePickerSearch ||
                elements.sourcePickerDialog
            )?.focus({
                preventScroll: true
            });
        });

        return true;
    }

    function handlePickerListClick(event, elements) {
        const readerLaunchControl = event.target?.closest?.(
            PICKER_READER_LAUNCH_SELECTOR
        );

        if (
            readerLaunchControl &&
            elements.sourcePickerList?.contains(
                readerLaunchControl
            )
        ) {
            const route = getReaderLaunchRoute(
                readerLaunchControl
            );

            if (!route) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();

            close(elements, {
                focus: false
            });
            launchReaderRoute(route);
            return;
        }

        const option = event.target?.closest?.(
            "[data-solomon-ai-source-picker-option]"
        );

        if (
            option &&
            elements.sourcePickerList.contains(option)
        ) {
            toggleSelection(elements, option);
        }
    }

    function bindPicker(elements) {
        const picker = elements?.sourcePicker;

        if (
            !picker ||
            picker.getAttribute(
                "data-solomon-ai-source-picker-bound"
            ) === "true"
        ) {
            return false;
        }

        picker.setAttribute(
            "data-solomon-ai-source-picker-bound",
            "true"
        );

        elements.sourcePickerCloseButtons.forEach(
            function (button) {
                button.addEventListener(
                    "click",
                    function (event) {
                        event.preventDefault();
                        close(elements);
                    }
                );
            }
        );

        elements.sourcePickerScopes.forEach(
            function (button) {
                button.addEventListener(
                    "click",
                    function () {
                        activateScope(
                            elements,
                            button.getAttribute(
                                "data-solomon-ai-source-picker-scope"
                            )
                        );
                    }
                );
            }
        );

        elements.sourcePickerSearch?.addEventListener(
            "input",
            function () {
                scheduleSearch(elements);
            }
        );

        elements.sourcePickerList?.addEventListener(
            "click",
            function (event) {
                handlePickerListClick(
                    event,
                    elements
                );
            }
        );

        elements.sourcePickerAttach?.addEventListener(
            "click",
            function () {
                attachSelected(elements);
            }
        );

        picker.addEventListener(
            "keydown",
            function (event) {
                handlePickerKeydown(
                    event,
                    elements
                );
            }
        );

        return true;
    }

    function initialize(elements) {
        if (
            !elements?.workspace ||
            !elements?.sourcePicker
        ) {
            return false;
        }

        bindPicker(elements);
        setPickerState(elements, "closed");
        return true;
    }

    modules.registerModule(
        "source_picker",
        {
            activateScope,
            appendReaderBackRoute,
            attachSelected,
            buildPickerReaderUrl,
            close,
            getRightPaneCallerRoute,
            handlePickerListClick,
            initialize,
            launchReaderRoute,
            loadCatalog,
            open,
            renderCatalog,
            scheduleSearch,
            toggleSelection,
            updateSelection
        }
    );
})(window);