/* -------------------------------------------------------------------
   FILE: workspace_document_search.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentSearch";
    const EXPLORER_SELECTOR = "[data-document-explorer]";
    const LIST_SELECTOR = "[data-document-list]";
    const ROW_SELECTOR = ".workspace-document-file[data-document-id]";
    const LIST_HEADER_SELECTOR = "[data-document-list-header]";
    const SEARCH_SELECTOR = "[data-document-search]";
    const INPUT_SELECTOR = "[data-document-search-input]";
    const CLEAR_SELECTOR = "[data-document-search-clear]";
    const STATUS_SELECTOR = "[data-document-search-status]";
    const NO_RESULTS_SELECTOR = "[data-document-search-no-results]";
    const SECTION_LINK_SELECTOR = "[data-document-section-link]";
    const SELECTION_CHANGE_EVENT = "solomon:documents-selection-change";
    const WORKSPACE_LOADED_EVENT = "solomon:workspace-loaded";
    const SERVER_SEARCH_SURFACE_SELECTOR = '[data-search-results-surface="true"]';
    const SEARCH_FILTER_SELECTOR = "[data-search-filter]";
    const SEARCH_FILTER_CLEAR_SELECTOR = "[data-search-filter-clear]";
    const SEARCH_LAYOUT_SELECTOR = "[data-search-layout-option]";
    const SEARCH_COLUMN_SORT_SELECTOR = "[data-search-column-sort-key]";
    const SEARCH_SORT_CONTROL_SELECTOR = "[data-search-sort-control]";
    const SEARCH_SORT_TRIGGER_SELECTOR = "[data-search-sort-trigger]";
    const SEARCH_SORT_MENU_SELECTOR = "[data-search-sort-menu]";
    const SEARCH_SORT_OPTION_SELECTOR = "[data-search-sort-option]";
    const SEARCH_SORT_DIRECTION_LABEL_SELECTOR = "[data-search-sort-direction-label]";

    const SEARCH_DEFAULT_DIRECTIONS = Object.freeze({
        relevance: "desc",
        name: "asc",
        modified: "desc",
        type: "asc",
        size: "desc"
    });

    const SEARCH_SORT_LABELS = Object.freeze({
        relevance: "Relevance",
        name: "Name",
        modified: "Date modified",
        type: "File type",
        size: "File size"
    });

    const SECTION_LABELS = Object.freeze({
        files: "My Files",
        reports: "Reports",
        recent: "Recent",
        trash: "Trash"
    });

    if (window[API_NAME]) {
        return;
    }

    function normalizeValue(value) {
        return String(value || "")
            .trim()
            .toLowerCase()
            .replace(/\s+/g, " ");
    }

    function getSection(explorer) {
        const section = normalizeValue(
            explorer?.getAttribute("data-workspace-section") || "files"
        );

        return SECTION_LABELS[section] ? section : "files";
    }

    function getSectionLabel(explorer) {
        return SECTION_LABELS[getSection(explorer)];
    }

    function getSearchInput(explorer) {
        return explorer?.querySelector(INPUT_SELECTOR) || null;
    }

    function getSearchQuery(explorer) {
        return normalizeValue(getSearchInput(explorer)?.value);
    }

    function getSearchTerms(explorer) {
        return getSearchQuery(explorer).split(" ").filter(Boolean);
    }

    function getRowSearchText(row) {
        return normalizeValue([
            row?.querySelector(".workspace-document-file-identity strong")?.textContent,
            row?.getAttribute("data-document-type-label"),
            row?.getAttribute("data-document-status-label"),
            row?.getAttribute("data-document-uploaded-label"),
            row?.getAttribute("data-document-size")
        ].filter(Boolean).join(" "));
    }

    function rowMatchesTerms(row, terms) {
        if (!terms.length) {
            return true;
        }

        const searchText = getRowSearchText(row);

        return terms.every(function (term) {
            return searchText.includes(term);
        });
    }

    function setVisible(node, visible) {
        if (!node) {
            return;
        }

        node.hidden = !visible;
        node.setAttribute("aria-hidden", visible ? "false" : "true");
    }

    function setStatus(explorer, message) {
        const status = explorer?.querySelector(STATUS_SELECTOR);
        const cleanMessage = String(message || "").trim();

        if (!status) {
            return;
        }

        status.textContent = cleanMessage;
        setVisible(status, Boolean(cleanMessage));
    }

    function syncSearchChrome(explorer, hasQuery) {
        const search = explorer?.querySelector(SEARCH_SELECTOR);
        const input = getSearchInput(explorer);
        const clearButton = explorer?.querySelector(CLEAR_SELECTOR);
        const sectionLabel = getSectionLabel(explorer);

        search?.setAttribute("aria-label", `Search ${sectionLabel}`);

        if (input) {
            input.setAttribute("aria-label", `Search ${sectionLabel}`);
            input.setAttribute("placeholder", `Search in ${sectionLabel}`);
        }

        setVisible(clearButton, hasQuery);
    }

    function createNoResultsState(explorer, query) {
        const article = document.createElement("article");
        const icon = document.createElement("span");
        const copy = document.createElement("div");
        const title = document.createElement("strong");
        const message = document.createElement("p");

        article.className = "workspace-document-search-empty";
        article.setAttribute("data-document-search-no-results", "");
        article.setAttribute("role", "status");
        article.setAttribute(
            "aria-label",
            `No ${getSectionLabel(explorer).toLowerCase()} results`
        );

        icon.className = "icon workspace-document-search-empty-icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = "search_off";

        copy.className = "workspace-document-search-empty-copy";
        title.textContent = `No results for “${query}”`;
        message.textContent = "Try a different file name or file type.";
        copy.append(title, message);
        article.append(icon, copy);

        return article;
    }

    function syncNoResultsState(explorer, list, query, rowCount, visibleCount) {
        const existing = list?.querySelector(NO_RESULTS_SELECTOR) || null;
        const shouldShow = Boolean(query && rowCount && visibleCount === 0);

        if (!shouldShow) {
            existing?.remove();
            return;
        }

        if (existing?.getAttribute("data-document-search-query") === query) {
            return;
        }

        existing?.remove();

        const noResults = createNoResultsState(explorer, query);

        noResults.setAttribute("data-document-search-query", query);
        list.appendChild(noResults);
    }

    function clearHiddenSelection(explorer, rows) {
        const hasHiddenSelection = rows.some(function (row) {
            return (
                row.hidden &&
                row.getAttribute("data-document-selected") === "true"
            );
        });

        if (!hasHiddenSelection) {
            return;
        }

        const Library = window.SolomonWorkspaceDocumentLibrary;
        const list = explorer.querySelector(LIST_SELECTOR);

        if (
            Library &&
            typeof Library.clearDocumentSelection === "function"
        ) {
            Library.clearDocumentSelection(list);
            return;
        }

        rows.forEach(function (row) {
            const checkbox = row.querySelector(
                "[data-document-select-checkbox]"
            );

            row.classList.remove("is-selected");
            row.setAttribute("aria-selected", "false");
            row.setAttribute("data-document-selected", "false");

            if (checkbox) {
                checkbox.checked = false;
                checkbox.setAttribute("aria-checked", "false");
            }
        });

        list?.dispatchEvent(new CustomEvent(SELECTION_CHANGE_EVENT, {
            bubbles: true,
            detail: {
                selectedCount: 0,
                selectedIds: []
            }
        }));
    }

    function applySearch(explorer) {
        const list = explorer?.querySelector(LIST_SELECTOR);
        const search = explorer?.querySelector(SEARCH_SELECTOR);
        const query = getSearchQuery(explorer);
        const terms = getSearchTerms(explorer);
        const rows = list
            ? Array.from(list.querySelectorAll(ROW_SELECTOR))
            : [];
        const listHeader = list?.querySelector(LIST_HEADER_SELECTOR) || null;
        let visibleCount = 0;

        syncSearchChrome(explorer, Boolean(query));

        rows.forEach(function (row) {
            const matches = rowMatchesTerms(row, terms);

            row.hidden = !matches;
            row.classList.toggle("is-search-hidden", !matches);
            row.setAttribute("aria-hidden", matches ? "false" : "true");

            if (matches) {
                visibleCount += 1;
            }
        });

        if (listHeader) {
            listHeader.hidden = Boolean(
                query &&
                rows.length &&
                visibleCount === 0
            );
        }

        search?.setAttribute(
            "data-document-search-state",
            !query
                ? "idle"
                : visibleCount
                    ? "results"
                    : "empty"
        );

        explorer?.setAttribute("data-document-search-query", query);
        explorer?.setAttribute(
            "data-document-search-result-count",
            String(visibleCount)
        );

        syncNoResultsState(
            explorer,
            list,
            query,
            rows.length,
            visibleCount
        );

        if (!query) {
            setStatus(explorer, "");
            return;
        }

        clearHiddenSelection(explorer, rows);

        if (!rows.length) {
            setStatus(
                explorer,
                `No ${getSectionLabel(explorer).toLowerCase()} items are available to search.`
            );
            return;
        }

        if (!visibleCount) {
            setStatus(explorer, `No results for ${query}.`);
            return;
        }

        setStatus(
            explorer,
            `${visibleCount} ${visibleCount === 1 ? "item" : "items"} shown for ${query}.`
        );
    }

    function scheduleApply(explorer) {
        if (
            !explorer ||
            explorer.__solomonDocumentSearchApplyPending
        ) {
            return;
        }

        explorer.__solomonDocumentSearchApplyPending = true;

        window.requestAnimationFrame(function () {
            explorer.__solomonDocumentSearchApplyPending = false;

            if (explorer.isConnected) {
                applySearch(explorer);
            }
        });
    }

    function resetSearch(explorer, options) {
        const input = getSearchInput(explorer);

        if (!input) {
            return;
        }

        input.value = "";
        applySearch(explorer);

        if (options?.focus) {
            input.focus({ preventScroll: true });
        }
    }

    function isServerSearchExplorer(explorer) {
        return Boolean(
            explorer?.matches(SERVER_SEARCH_SURFACE_SELECTOR) ||
            normalizeValue(explorer?.getAttribute("data-workspace-module")) === "search"
        );
    }

    function getSearchNavigationUrl(explorer) {
        const route = String(
            explorer?.getAttribute("data-search-route") ||
            explorer?.getAttribute("data-workspace-route") ||
            window.location.href
        ).trim();

        try {
            return new URL(route, window.location.origin);
        } catch (error) {
            return new URL(window.location.href);
        }
    }

    function dispatchSearchNavigation(route) {
        const cleanRoute = String(route || "").trim();

        if (!cleanRoute) {
            return;
        }

        const link = document.createElement("a");

        link.href = cleanRoute;
        link.hidden = true;
        link.setAttribute("data-command-shell-navigation", "true");
        link.setAttribute("data-command-module", "search");
        link.setAttribute("data-command-section", "search");
        link.setAttribute("data-command-route", cleanRoute);
        link.setAttribute(
            "data-command-navigation-contract",
            "workspace_module_section_route"
        );
        document.body.appendChild(link);
        link.click();
        window.setTimeout(function () {
            link.remove();
        }, 0);
    }

    function navigateServerSearch(explorer, updates) {
        const url = getSearchNavigationUrl(explorer);

        Object.entries(updates || {}).forEach(function (entry) {
            const key = String(entry[0] || "").trim();
            const value = entry[1];

            if (!key) {
                return;
            }

            if (value === null || value === undefined || String(value).trim() === "") {
                url.searchParams.delete(key);
                return;
            }

            url.searchParams.set(key, String(value).trim());
        });

        url.searchParams.delete("partial");
        dispatchSearchNavigation(`${url.pathname}${url.search}${url.hash}`);
    }

    function getServerSearchSortState(explorer) {
        const url = getSearchNavigationUrl(explorer);
        const sortKey = normalizeValue(
            explorer?.getAttribute("data-search-sort-key") ||
            url.searchParams.get("sort") ||
            "relevance"
        );
        const direction = normalizeValue(
            explorer?.getAttribute("data-search-sort-direction") ||
            url.searchParams.get("direction") ||
            SEARCH_DEFAULT_DIRECTIONS[sortKey] ||
            "desc"
        );

        return {
            key: SEARCH_DEFAULT_DIRECTIONS[sortKey] ? sortKey : "relevance",
            direction: direction === "asc" ? "asc" : "desc",
            folders: normalizeValue(
                explorer?.getAttribute("data-search-folder-placement") ||
                url.searchParams.get("folders") ||
                "top"
            ) === "mixed" ? "mixed" : "top"
        };
    }

    function getServerSearchSortControl(explorer) {
        return explorer?.querySelector(SEARCH_SORT_CONTROL_SELECTOR) || null;
    }

    function getServerSearchSortMenu(explorer) {
        return explorer?.querySelector(SEARCH_SORT_MENU_SELECTOR) || null;
    }

    function getServerSearchSortTrigger(explorer) {
        return explorer?.querySelector(SEARCH_SORT_TRIGGER_SELECTOR) || null;
    }

    function getServerSearchSortOptions(explorer) {
        return Array.from(
            explorer?.querySelectorAll(SEARCH_SORT_OPTION_SELECTOR) || []
        );
    }

    function setServerSearchSortMenuOpen(explorer, open, options) {
        const control = getServerSearchSortControl(explorer);
        const trigger = getServerSearchSortTrigger(explorer);
        const menu = getServerSearchSortMenu(explorer);
        const shouldOpen = Boolean(open && control && trigger && menu);

        if (!control || !trigger || !menu) {
            return;
        }

        control.setAttribute("data-document-sort-open", shouldOpen ? "true" : "false");
        trigger.setAttribute("aria-expanded", shouldOpen ? "true" : "false");
        menu.hidden = !shouldOpen;

        if (shouldOpen && options?.focusFirst) {
            const selectedOption = getServerSearchSortOptions(explorer).find(function (option) {
                return option.getAttribute("aria-checked") === "true";
            });
            const firstOption = selectedOption || getServerSearchSortOptions(explorer)[0];

            firstOption?.focus({ preventScroll: true });
        }

        if (!shouldOpen && options?.restoreFocus) {
            trigger.focus({ preventScroll: true });
        }
    }

    function syncServerSearchDirectionLabels(explorer, sortKey) {
        const labels = {
            relevance: {
                asc: "Least relevant first",
                desc: "Most relevant first"
            },
            name: {
                asc: "A to Z",
                desc: "Z to A"
            },
            type: {
                asc: "A to Z",
                desc: "Z to A"
            },
            modified: {
                asc: "Oldest first",
                desc: "Newest first"
            },
            size: {
                asc: "Smallest first",
                desc: "Largest first"
            }
        };
        const selectedLabels = labels[sortKey] || labels.relevance;

        explorer?.querySelectorAll(SEARCH_SORT_DIRECTION_LABEL_SELECTOR).forEach(function (label) {
            const direction = normalizeValue(
                label.getAttribute("data-search-sort-direction-label")
            );

            if (selectedLabels[direction]) {
                label.textContent = selectedLabels[direction];
            }
        });
    }

    function syncServerSearchSortPresentation(explorer) {
        const state = getServerSearchSortState(explorer);

        explorer?.setAttribute("data-search-sort-key", state.key);
        explorer?.setAttribute("data-search-sort-direction", state.direction);
        explorer?.setAttribute("data-search-folder-placement", state.folders);
        syncServerSearchDirectionLabels(explorer, state.key);

        getServerSearchSortOptions(explorer).forEach(function (option) {
            const field = normalizeValue(option.getAttribute("data-search-sort-field"));
            const value = normalizeValue(option.getAttribute("data-search-sort-value"));
            const selected = (
                (field === "key" && value === state.key) ||
                (field === "direction" && value === state.direction) ||
                (field === "folders" && value === state.folders)
            );

            option.setAttribute("aria-checked", selected ? "true" : "false");
            option.tabIndex = selected ? 0 : -1;
        });

        const sortKeyLabel = SEARCH_SORT_LABELS[state.key] || SEARCH_SORT_LABELS.relevance;
        const sortTrigger = getServerSearchSortTrigger(explorer);
        const directionLabel = state.direction === "asc" ? "ascending" : "descending";

        if (sortTrigger instanceof HTMLElement) {
            sortTrigger.setAttribute(
                "aria-label",
                `Sort search results. Current order: ${sortKeyLabel}, ${directionLabel}.`
            );
            sortTrigger.setAttribute(
                "title",
                `Sort search results: ${sortKeyLabel}, ${directionLabel}`
            );
        }

        explorer?.querySelectorAll(SEARCH_COLUMN_SORT_SELECTOR).forEach(function (button) {
            const key = normalizeValue(button.getAttribute("data-search-column-sort-key"));
            const label = String(
                button.getAttribute("data-search-column-sort-label") || "column"
            ).trim();
            const active = key === state.key;
            const icon = button.querySelector("[data-search-column-sort-icon]");
            const cell = button.closest("th, [role='columnheader']");

            button.classList.toggle("is-active", active);
            button.setAttribute("aria-pressed", active ? "true" : "false");
            button.setAttribute(
                "aria-label",
                active
                    ? `Sort by ${label}, currently ${state.direction === "asc" ? "ascending" : "descending"}`
                    : `Sort by ${label}`
            );
            if (cell instanceof HTMLElement) {
                cell.setAttribute(
                    "aria-sort",
                    active
                        ? state.direction === "asc" ? "ascending" : "descending"
                        : "none"
                );
            }

            if (icon) {
                icon.hidden = !active;
                icon.textContent = state.direction === "asc"
                    ? "arrow_upward"
                    : "arrow_downward";
            }
        });
    }

    function handleServerSearchColumnSort(event, explorer, button) {
        const nextKey = normalizeValue(
            button.getAttribute("data-search-column-sort-key")
        );
        const state = getServerSearchSortState(explorer);

        if (!SEARCH_DEFAULT_DIRECTIONS[nextKey]) {
            return false;
        }

        event.preventDefault();
        event.stopImmediatePropagation();
        navigateServerSearch(explorer, {
            sort: nextKey,
            direction: nextKey === state.key
                ? (state.direction === "asc" ? "desc" : "asc")
                : SEARCH_DEFAULT_DIRECTIONS[nextKey]
        });
        return true;
    }

    function handleServerSearchSortOption(event, explorer, option) {
        const field = normalizeValue(option.getAttribute("data-search-sort-field"));
        const value = normalizeValue(option.getAttribute("data-search-sort-value"));
        const state = getServerSearchSortState(explorer);
        const updates = {};

        if (field === "key" && SEARCH_DEFAULT_DIRECTIONS[value]) {
            updates.sort = value;
            updates.direction = value === state.key
                ? state.direction
                : SEARCH_DEFAULT_DIRECTIONS[value];
        } else if (field === "direction" && (value === "asc" || value === "desc")) {
            updates.direction = value;
        } else if (field === "folders" && (value === "top" || value === "mixed")) {
            updates.folders = value;
        } else {
            return false;
        }

        event.preventDefault();
        event.stopImmediatePropagation();
        setServerSearchSortMenuOpen(explorer, false);
        navigateServerSearch(explorer, updates);
        return true;
    }

    function handleServerSearchClick(event, explorer) {
        const clearButton = event.target.closest(SEARCH_FILTER_CLEAR_SELECTOR);
        const layoutButton = event.target.closest(SEARCH_LAYOUT_SELECTOR);
        const columnButton = event.target.closest(SEARCH_COLUMN_SORT_SELECTOR);
        const sortTrigger = event.target.closest(SEARCH_SORT_TRIGGER_SELECTOR);
        const sortOption = event.target.closest(SEARCH_SORT_OPTION_SELECTOR);

        if (clearButton && explorer.contains(clearButton)) {
            event.preventDefault();
            event.stopImmediatePropagation();
            navigateServerSearch(explorer, {
                filter_type: null,
                people: null,
                modified: null,
                source: null
            });
            return;
        }

        if (layoutButton && explorer.contains(layoutButton)) {
            const route = String(layoutButton.getAttribute("data-command-route") || "").trim();

            event.preventDefault();
            event.stopImmediatePropagation();

            if (route) {
                dispatchSearchNavigation(route);
            } else {
                navigateServerSearch(explorer, {
                    layout: normalizeValue(layoutButton.getAttribute("data-search-layout-option")) || "list"
                });
            }
            return;
        }

        if (columnButton && explorer.contains(columnButton)) {
            handleServerSearchColumnSort(event, explorer, columnButton);
            return;
        }

        if (sortTrigger && explorer.contains(sortTrigger)) {
            const control = getServerSearchSortControl(explorer);
            const isOpen = control?.getAttribute("data-document-sort-open") === "true";

            event.preventDefault();
            event.stopImmediatePropagation();
            setServerSearchSortMenuOpen(explorer, !isOpen, {
                focusFirst: !isOpen
            });
            return;
        }

        if (sortOption && explorer.contains(sortOption)) {
            handleServerSearchSortOption(event, explorer, sortOption);
            return;
        }

        const sortControl = getServerSearchSortControl(explorer);

        if (
            sortControl?.getAttribute("data-document-sort-open") === "true" &&
            !sortControl.contains(event.target) &&
            !getServerSearchSortTrigger(explorer)?.contains(event.target)
        ) {
            setServerSearchSortMenuOpen(explorer, false);
        }
    }

    function handleServerSearchChange(event, explorer) {
        const select = event.target.closest(SEARCH_FILTER_SELECTOR);

        if (!select || !explorer.contains(select)) {
            return;
        }

        event.preventDefault();
        event.stopImmediatePropagation();
        navigateServerSearch(explorer, {
            [select.name]: String(select.value || "").trim() || null
        });
    }

    function focusServerSearchSortOption(explorer, nextIndex) {
        const options = getServerSearchSortOptions(explorer);

        if (!options.length) {
            return;
        }

        const boundedIndex = (nextIndex + options.length) % options.length;

        options.forEach(function (option, index) {
            option.tabIndex = index === boundedIndex ? 0 : -1;
        });
        options[boundedIndex].focus({ preventScroll: true });
    }

    function handleServerSearchKeydown(event, explorer) {
        const trigger = event.target.closest(SEARCH_SORT_TRIGGER_SELECTOR);
        const option = event.target.closest(SEARCH_SORT_OPTION_SELECTOR);

        if (trigger && explorer.contains(trigger)) {
            if (["Enter", " ", "ArrowDown"].includes(event.key)) {
                event.preventDefault();
                event.stopImmediatePropagation();
                setServerSearchSortMenuOpen(explorer, true, { focusFirst: true });
            }
            return;
        }

        if (!option || !explorer.contains(option)) {
            return;
        }

        const options = getServerSearchSortOptions(explorer);
        const currentIndex = options.indexOf(option);

        if (event.key === "Escape") {
            event.preventDefault();
            event.stopImmediatePropagation();
            setServerSearchSortMenuOpen(explorer, false, { restoreFocus: true });
            return;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();
            event.stopImmediatePropagation();
            focusServerSearchSortOption(explorer, currentIndex + 1);
            return;
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();
            event.stopImmediatePropagation();
            focusServerSearchSortOption(explorer, currentIndex - 1);
            return;
        }

        if (event.key === "Home") {
            event.preventDefault();
            event.stopImmediatePropagation();
            focusServerSearchSortOption(explorer, 0);
            return;
        }

        if (event.key === "End") {
            event.preventDefault();
            event.stopImmediatePropagation();
            focusServerSearchSortOption(explorer, options.length - 1);
            return;
        }

        if (event.key === "Enter" || event.key === " ") {
            handleServerSearchSortOption(event, explorer, option);
        }
    }

    function bindServerSearchExplorer(explorer) {
        if (
            !explorer ||
            explorer.dataset.serverSearchBound === "true"
        ) {
            return;
        }

        explorer.dataset.serverSearchBound = "true";
        explorer.addEventListener("click", function (event) {
            handleServerSearchClick(event, explorer);
        }, true);
        explorer.addEventListener("change", function (event) {
            handleServerSearchChange(event, explorer);
        }, true);
        explorer.addEventListener("keydown", function (event) {
            handleServerSearchKeydown(event, explorer);
        }, true);

        const Library = window.SolomonWorkspaceDocumentLibrary;

        if (Library && typeof Library.initializeRecentFilterMenus === "function") {
            Library.initializeRecentFilterMenus(explorer);
        }

        syncServerSearchSortPresentation(explorer);
    }

    function bindExplorer(explorer) {
        if (!explorer) {
            return;
        }

        if (isServerSearchExplorer(explorer)) {
            bindServerSearchExplorer(explorer);
            return;
        }

        if (explorer.dataset.documentSearchBound === "true") {
            return;
        }

        const list = explorer.querySelector(LIST_SELECTOR);

        explorer.dataset.documentSearchBound = "true";

        explorer.addEventListener("input", function (event) {
            if (event.target.closest(INPUT_SELECTOR)) {
                applySearch(explorer);
            }
        });

        explorer.addEventListener("click", function (event) {
            const clearButton = event.target.closest(CLEAR_SELECTOR);
            const sectionLink = event.target.closest(SECTION_LINK_SELECTOR);

            if (
                clearButton &&
                explorer.contains(clearButton)
            ) {
                event.preventDefault();
                event.stopPropagation();
                resetSearch(explorer, { focus: true });
                return;
            }

            if (
                sectionLink &&
                explorer.contains(sectionLink)
            ) {
                resetSearch(explorer);
            }
        });

        explorer.addEventListener("keydown", function (event) {
            if (
                event.key === "Escape" &&
                event.target.closest(INPUT_SELECTOR) &&
                getSearchQuery(explorer)
            ) {
                event.preventDefault();
                event.stopPropagation();
                resetSearch(explorer, { focus: true });
            }
        });

        if (list) {
            const listObserver = new MutationObserver(function (mutations) {
                const hasDocumentMutation = mutations.some(function (mutation) {
                    const changedNodes = [
                        ...Array.from(mutation.addedNodes || []),
                        ...Array.from(mutation.removedNodes || [])
                    ];

                    return changedNodes.some(function (node) {
                        return !node.matches?.(NO_RESULTS_SELECTOR);
                    });
                });

                if (hasDocumentMutation) {
                    scheduleApply(explorer);
                }
            });

            listObserver.observe(list, {
                childList: true
            });

            explorer.__solomonDocumentSearchListObserver = listObserver;
        }

        const sectionObserver = new MutationObserver(function () {
            resetSearch(explorer);
        });

        sectionObserver.observe(explorer, {
            attributes: true,
            attributeFilter: [
                "data-workspace-section"
            ]
        });

        explorer.__solomonDocumentSearchSectionObserver = sectionObserver;

        applySearch(explorer);
    }

    function initialize() {
        document
            .querySelectorAll(EXPLORER_SELECTOR)
            .forEach(bindExplorer);
    }

    window[API_NAME] = Object.freeze({
        apply: applySearch,
        reset: resetSearch,
        initialize
    });

    document.addEventListener(
        WORKSPACE_LOADED_EVENT,
        initialize
    );

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initialize
        );
    } else {
        initialize();
    }
})();