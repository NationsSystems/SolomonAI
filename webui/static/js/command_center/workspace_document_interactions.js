/* -------------------------------------------------------------------
   FILE: workspace_document_interactions.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const DEFAULT_DOCUMENT_ROW_SELECTOR = ".workspace-document-file[data-document-id]";
    const DEFAULT_DOCUMENT_ACTION_MENU_SELECTOR = "[data-document-action-menu]";
    const DEFAULT_DOCUMENT_ACTION_MENU_BUTTON_SELECTOR = "[data-document-action-menu-button]";
    const DEFAULT_DOCUMENT_ACTION_MENU_ITEM_SELECTOR = "[data-document-action-menu-item]";
    const DEFAULT_DOCUMENT_ACTION_NAME_ATTRIBUTE = "data-document-action-menu-item";
    const DEFAULT_DOCUMENT_ACTION_MENU_POPOVER_SELECTOR = ".workspace-document-file-action-popover";
    const DEFAULT_SHARED_LISTING_SELECTOR = [
        "[data-workspace-listing-contract]",
        "[data-workspace-listing-controller='true']"
    ].join(", ");
    const DEFAULT_SHARED_LISTING_SELECT_EVENT = "nations:workspace-listing-select";
    const DEFAULT_SHARED_LISTING_ACTION_EVENT = "nations:workspace-listing-action";
    const SHARED_LISTING_ADAPTER_KEY = "__solomonDocumentSharedListingAdapterBound";
    const WORKSPACE_CONTEXT_MENU_OPEN_EVENT = "nations:workspace-context-menu-open";
    const WORKSPACE_CONTEXT_MENU_CLOSE_EVENT = "nations:workspace-context-menu-close";
    const WORKSPACE_CONTEXT_OBJECT = "object";
    const WORKSPACE_CONTEXT_LOCATION = "location";
    const CONTEXT_COORDINATOR_BOUND_KEY = "__solomonDocumentContextCoordinatorBound";
    const DEFAULT_INTERACTION_CONTROL_SELECTOR = [
        "button",
        "a",
        "input",
        "select",
        "textarea",
        "[role='button']",
        "[role='menuitem']",
        "[data-document-action-menu]",
        "[data-document-action-menu-button]",
        "[data-document-action-menu-item]",
        "[data-document-select-checkbox]"
    ].join(", ");
    const DEFAULT_OPEN_BLOCKED_CONTROL_SELECTOR = [
        "button",
        "a",
        "input",
        "select",
        "textarea",
        "[role='button']",
        "[role='menuitem']",
        "[data-document-action-menu]",
        "[data-document-action-menu-button]",
        "[data-document-action-menu-item]"
    ].join(", ");

    const COMMON_FILE_ACTIONS = Object.freeze(["open", "open_reader", "reader"]);
    const ACTIVE_FILE_ACTIONS = Object.freeze(["ask_solomon_ai", "summary", "share", "delete"]);
    const TRASH_FILE_ACTIONS = Object.freeze(["restore", "permanent_delete"]);

    function cleanValue(value) {
        return String(value || "").trim();
    }

    function normalizeActionName(value) {
        return cleanValue(value)
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "_")
            .replace(/^_+|_+$/g, "");
    }

    function getConfig(options) {
        const cleanOptions = options || {};

        return {
            rowSelector: cleanValue(cleanOptions.rowSelector) || DEFAULT_DOCUMENT_ROW_SELECTOR,
            actionMenuSelector: cleanValue(cleanOptions.actionMenuSelector) || DEFAULT_DOCUMENT_ACTION_MENU_SELECTOR,
            actionMenuButtonSelector: cleanValue(cleanOptions.actionMenuButtonSelector) || DEFAULT_DOCUMENT_ACTION_MENU_BUTTON_SELECTOR,
            actionMenuItemSelector: cleanValue(cleanOptions.actionMenuItemSelector) || DEFAULT_DOCUMENT_ACTION_MENU_ITEM_SELECTOR,
            actionNameAttribute: cleanValue(cleanOptions.actionNameAttribute) || DEFAULT_DOCUMENT_ACTION_NAME_ATTRIBUTE,
            actionMenuPopoverSelector: cleanValue(cleanOptions.actionMenuPopoverSelector) || DEFAULT_DOCUMENT_ACTION_MENU_POPOVER_SELECTOR,
            sharedListingSelector: cleanValue(cleanOptions.sharedListingSelector) || DEFAULT_SHARED_LISTING_SELECTOR,
            sharedListingSelectEvent: cleanValue(cleanOptions.sharedListingSelectEvent) || DEFAULT_SHARED_LISTING_SELECT_EVENT,
            sharedListingActionEvent: cleanValue(cleanOptions.sharedListingActionEvent) || DEFAULT_SHARED_LISTING_ACTION_EVENT,
            interactionControlSelector: cleanValue(cleanOptions.interactionControlSelector) || DEFAULT_INTERACTION_CONTROL_SELECTOR,
            openBlockedControlSelector: cleanValue(cleanOptions.openBlockedControlSelector) || DEFAULT_OPEN_BLOCKED_CONTROL_SELECTOR,
            getDocumentRows: typeof cleanOptions.getDocumentRows === "function"
                ? cleanOptions.getDocumentRows
                : getDocumentRows,
            selectFile: typeof cleanOptions.selectFile === "function"
                ? cleanOptions.selectFile
                : null,
            openDocument: typeof cleanOptions.openDocument === "function"
                ? cleanOptions.openDocument
                : null,
            isDocumentInTrashContext: typeof cleanOptions.isDocumentInTrashContext === "function"
                ? cleanOptions.isDocumentInTrashContext
                : null,
            hasAnyDocumentInTrashContext: typeof cleanOptions.hasAnyDocumentInTrashContext === "function"
                ? cleanOptions.hasAnyDocumentInTrashContext
                : null,
            hasAnyDocumentOutsideTrashContext: typeof cleanOptions.hasAnyDocumentOutsideTrashContext === "function"
                ? cleanOptions.hasAnyDocumentOutsideTrashContext
                : null,
            updateSelectionFromRows: typeof cleanOptions.updateSelectionFromRows === "function"
                ? cleanOptions.updateSelectionFromRows
                : null,
            setDocumentRowSelected: typeof cleanOptions.setDocumentRowSelected === "function"
                ? cleanOptions.setDocumentRowSelected
                : null,
            setDocumentRowsSelectedByIds: typeof cleanOptions.setDocumentRowsSelectedByIds === "function"
                ? cleanOptions.setDocumentRowsSelectedByIds
                : null,
            getActionSelectionFromMenuItem: typeof cleanOptions.getActionSelectionFromMenuItem === "function"
                ? cleanOptions.getActionSelectionFromMenuItem
                : null,
            showFileDetails: typeof cleanOptions.showFileDetails === "function"
                ? cleanOptions.showFileDetails
                : null,
            openShare: typeof cleanOptions.openShare === "function"
                ? cleanOptions.openShare
                : null,
            showFileSummary: typeof cleanOptions.showFileSummary === "function"
                ? cleanOptions.showFileSummary
                : null,
            runSolomonAction: typeof cleanOptions.runSolomonAction === "function"
                ? cleanOptions.runSolomonAction
                : null,
            requestSolomonAiSession: typeof cleanOptions.requestSolomonAiSession === "function"
                ? cleanOptions.requestSolomonAiSession
                : null,
            requestMoveDocumentToTrash: typeof cleanOptions.requestMoveDocumentToTrash === "function"
                ? cleanOptions.requestMoveDocumentToTrash
                : null,
            restoreDocumentFromTrash: typeof cleanOptions.restoreDocumentFromTrash === "function"
                ? cleanOptions.restoreDocumentFromTrash
                : null,
            requestPermanentDeleteDocument: typeof cleanOptions.requestPermanentDeleteDocument === "function"
                ? cleanOptions.requestPermanentDeleteDocument
                : null,
            showStatus: typeof cleanOptions.showStatus === "function"
                ? cleanOptions.showStatus
                : null,
            onUnsupportedAction: typeof cleanOptions.onUnsupportedAction === "function"
                ? cleanOptions.onUnsupportedAction
                : null
        };
    }

    function getDocumentRows(explorer, options) {
        const config = getConfig(options);

        return Array.from(explorer?.querySelectorAll(config.rowSelector) || []);
    }

    function getDocumentIdFromRow(row) {
        return cleanValue(row?.getAttribute("data-document-id"));
    }

    function getRowFromEvent(event, explorer, options) {
        const config = getConfig(options);
        const detailRow = event?.detail?.row;
        const detailRowElement = detailRow instanceof Element ? detailRow : null;
        const row = detailRowElement && explorer?.contains(detailRowElement)
            ? detailRowElement
            : event?.target?.closest(config.rowSelector) || null;

        if (!row || !explorer?.contains(row)) {
            return null;
        }

        return row;
    }

    function dispatchWorkspaceContextMenuOpen(explorer, context, detail) {
        const cleanContext = normalizeActionName(context);

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
        return normalizeActionName(event?.detail?.context);
    }

    function bindWorkspaceContextMenuCoordinator(explorer, options) {
        const config = getConfig(options);

        if (!explorer || explorer[CONTEXT_COORDINATOR_BOUND_KEY] === true) {
            return;
        }

        explorer[CONTEXT_COORDINATOR_BOUND_KEY] = true;

        explorer.addEventListener(WORKSPACE_CONTEXT_MENU_OPEN_EVENT, function (event) {
            const context = getWorkspaceContextMenuEventContext(event);

            if (context === WORKSPACE_CONTEXT_LOCATION) {
                closeDocumentActionMenus(explorer, null, config);
            }
        });

        explorer.addEventListener(WORKSPACE_CONTEXT_MENU_CLOSE_EVENT, function () {
            closeDocumentActionMenus(explorer, null, config);
        });
    }

    function hasSharedListingController() {
        return typeof window.NationsCommandSidebar?.initializeWorkspaceListingControls === "function";
    }

    function isSharedListingRow(row, options) {
        const config = getConfig(options);

        return Boolean(
            hasSharedListingController() &&
            row?.closest?.(config.sharedListingSelector)
        );
    }

    function isSelectionModifierEvent(event) {
        return Boolean(event?.metaKey || event?.ctrlKey || event?.shiftKey);
    }

    function isDocumentRowMenuControl(target, options) {
        const config = getConfig(options);

        return Boolean(target?.closest(config.actionMenuSelector));
    }

    function isDocumentRowInteractionControl(target, options) {
        const config = getConfig(options);

        return Boolean(target?.closest(config.interactionControlSelector));
    }

    function isDocumentRowOpenBlockedControl(target, options) {
        const config = getConfig(options);

        return Boolean(target?.closest(config.openBlockedControlSelector));
    }

    function canSelectDocumentRow(row, target, options) {
        return Boolean(row && !isDocumentRowInteractionControl(target, options));
    }

    function isExplicitOpenDisabled(row) {
        const state = cleanValue(
            row?.getAttribute("data-workspace-object-open-enabled") ||
            row?.getAttribute("data-document-open-enabled") ||
            row?.getAttribute("data-search-result-open-enabled")
        ).toLowerCase();

        return (
            state === "false" ||
            state === "0" ||
            state === "no"
        );
    }

    function canOpenDocumentRow(explorer, row, target, options) {
        const documentId = getDocumentIdFromRow(row);

        return Boolean(
            explorer &&
            row &&
            documentId &&
            !isExplicitOpenDisabled(row) &&
            !isDocumentRowOpenBlockedControl(target, options)
        );
    }

    function selectFile(explorer, row, config, options) {
        if (!config.selectFile) {
            return null;
        }

        const cleanOptions = options || {};

        return config.selectFile(
            explorer,
            row,
            Object.assign({}, cleanOptions, {
                selectionIntent:
                    normalizeActionName(cleanOptions.selectionIntent) ||
                    "programmatic_selection",
                openInspector: cleanOptions.openInspector === true
            })
        );
    }

    function openDocumentRow(explorer, row, options) {
        const config = getConfig(options);
        const documentId = getDocumentIdFromRow(row);
        const sidebarApi = window.NationsCommandSidebar || {};

        if (!documentId) {
            return;
        }

        if (
            isSharedListingRow(row, config) &&
            typeof sidebarApi.openWorkspaceListingObject === "function"
        ) {
            sidebarApi.openWorkspaceListingObject(row, {
                mode: "document_interaction_adapter"
            });
            return;
        }

        if (config.openDocument) {
            config.openDocument(explorer, documentId);
        }
    }

    function focusDocumentRow(row) {
        if (!row || typeof row.focus !== "function") {
            return;
        }

        row.focus({ preventScroll: false });
    }

    function closeDocumentActionPopover(popover) {
        if (!popover) {
            return;
        }

        popover.classList.remove("is-open");
        popover.hidden = true;
        popover.setAttribute("hidden", "");
        popover.setAttribute("aria-hidden", "true");
    }

    function closeDocumentActionMenuElement(menu, config) {
        if (!menu) {
            return;
        }

        const button = menu.querySelector(config.actionMenuButtonSelector);
        const popover = menu.querySelector(config.actionMenuPopoverSelector);

        menu.classList.remove("is-open");
        menu.setAttribute("data-document-action-menu-state", "closed");

        if (button) {
            button.setAttribute("aria-expanded", "false");
            button.setAttribute("data-document-action-menu-button-state", "closed");
        }

        closeDocumentActionPopover(popover);
    }

    function closeDocumentActionMenus(explorer, exceptMenu, options) {
        const config = getConfig(options);
        const root = explorer || document;

        root.querySelectorAll?.(config.actionMenuSelector).forEach(function (menu) {
            if (exceptMenu && menu === exceptMenu) {
                return;
            }

            closeDocumentActionMenuElement(menu, config);
        });

        root.querySelectorAll?.(config.actionMenuPopoverSelector).forEach(function (popover) {
            const ownerMenu = popover.closest(config.actionMenuSelector);

            if (exceptMenu && ownerMenu === exceptMenu) {
                return;
            }

            closeDocumentActionPopover(popover);
        });
    }

    function hasOpenDocumentActionMenu(explorer, options) {
        const config = getConfig(options);

        return Boolean(explorer?.querySelector(`${config.actionMenuSelector}.is-open`));
    }

    function toggleDocumentActionMenu(explorer, button, options) {
        const config = getConfig(options);
        const menu = button?.closest(config.actionMenuSelector);
        const popover = menu?.querySelector(config.actionMenuPopoverSelector);
        const isOpen = menu?.classList.contains("is-open");

        if (!menu || !popover) {
            return;
        }

        if (!isOpen) {
            dispatchWorkspaceContextMenuOpen(explorer, WORKSPACE_CONTEXT_OBJECT, {
                source: "document_action_menu",
                row: button.closest(config.rowSelector) || null
            });
        }

        closeDocumentActionMenus(explorer, menu, config);

        if (isOpen) {
            menu.classList.remove("is-open");
            button.setAttribute("aria-expanded", "false");
            popover.hidden = true;
            return;
        }

        menu.classList.add("is-open");
        button.setAttribute("aria-expanded", "true");
        popover.hidden = false;
    }

    function moveDocumentRowFocus(explorer, currentRow, movement, options) {
        const config = getConfig(options);
        const rows = config.getDocumentRows(explorer, options);

        if (!rows.length) {
            return false;
        }

        let currentIndex = rows.indexOf(currentRow);

        if (currentIndex < 0) {
            currentIndex = rows.findIndex(function (row) {
                return row.classList.contains("is-selected");
            });
        }

        if (currentIndex < 0) {
            currentIndex = 0;
        }

        let nextIndex = currentIndex;

        if (movement === "first") {
            nextIndex = 0;
        } else if (movement === "last") {
            nextIndex = rows.length - 1;
        } else if (movement === "previous") {
            nextIndex = Math.max(0, currentIndex - 1);
        } else if (movement === "next") {
            nextIndex = Math.min(rows.length - 1, currentIndex + 1);
        }

        const nextRow = rows[nextIndex];

        if (!nextRow) {
            return false;
        }

        closeDocumentActionMenus(explorer, null, config);
        selectFile(explorer, nextRow, config, {
            selectionIntent: "keyboard_navigation",
            openInspector: true
        });
        focusDocumentRow(nextRow);

        return true;
    }

    function openDocumentRowActionMenu(explorer, row, options) {
        const config = getConfig(options);
        const actionButton = row?.querySelector(config.actionMenuButtonSelector);

        if (!explorer || !row || !actionButton) {
            return;
        }

        actionButton.focus({ preventScroll: true });
        toggleDocumentActionMenu(explorer, actionButton, config);
    }

    function handleDocumentRowClick(event, explorer, options) {
        const config = getConfig(options);

        if (event.defaultPrevented || event.detail > 1) {
            return;
        }

        const row = getRowFromEvent(event, explorer, config);

        if (
            isSharedListingRow(row, config) ||
            !canSelectDocumentRow(row, event.target, config)
        ) {
            return;
        }

        if (isSelectionModifierEvent(event)) {
            return;
        }

        event.preventDefault();
        closeDocumentActionMenus(explorer, null, config);
        selectFile(explorer, row, config, {
            selectionIntent: "primary_selection",
            openInspector: true
        });
    }

    function handleDocumentRowDoubleClick(event, explorer, options) {
        const config = getConfig(options);

        if (event.defaultPrevented) {
            return;
        }

        const row = getRowFromEvent(event, explorer, config);

        if (
            isSharedListingRow(row, config) ||
            !canOpenDocumentRow(explorer, row, event.target, config)
        ) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        closeDocumentActionMenus(explorer, null, config);
        selectFile(explorer, row, config, {
            selectionIntent: "primary_open",
            openInspector: false
        });
        openDocumentRow(explorer, row, config);
    }

    function handleDocumentRowContextMenu(event, explorer, options) {
        const config = getConfig(options);

        if (event.defaultPrevented) {
            return;
        }

        const row = getRowFromEvent(event, explorer, config);

        if (isSharedListingRow(row, config) || !row) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        closeDocumentActionMenus(explorer, null, config);
        selectFile(explorer, row, config, {
            selectionIntent: "context_menu",
            openInspector: false
        });
        openDocumentRowActionMenu(explorer, row, config);
    }

    function handleDocumentRowKeydown(event, explorer, options) {
        const config = getConfig(options);

        if (event.defaultPrevented) {
            return;
        }

        const row = getRowFromEvent(event, explorer, config);

        if (!row || isSharedListingRow(row, config)) {
            return;
        }

        if (event.key === "Enter") {
            if (!canOpenDocumentRow(explorer, row, event.target, config)) {
                return;
            }

            event.preventDefault();
            closeDocumentActionMenus(explorer, null, config);
            selectFile(explorer, row, config, {
                selectionIntent: "keyboard_open",
                openInspector: false
            });
            openDocumentRow(explorer, row, config);
            return;
        }

        if (event.key === " ") {
            if (!canSelectDocumentRow(row, event.target, config)) {
                return;
            }

            event.preventDefault();
            closeDocumentActionMenus(explorer, null, config);

            if (row.getAttribute("data-document-selected") === "true") {
                if (config.setDocumentRowSelected) {
                    config.setDocumentRowSelected(row, false);
                }

                if (config.updateSelectionFromRows) {
                    config.updateSelectionFromRows(explorer, {
                        selectionIntent: "keyboard_selection",
                        openInspector: true
                    });
                }
            } else {
                selectFile(explorer, row, config, {
                    selectionIntent: "keyboard_selection",
                    openInspector: true
                });
            }
            return;
        }

        if (event.key === "ArrowUp") {
            event.preventDefault();
            moveDocumentRowFocus(explorer, row, "previous", config);
            return;
        }

        if (event.key === "ArrowDown") {
            event.preventDefault();
            moveDocumentRowFocus(explorer, row, "next", config);
            return;
        }

        if (event.key === "Home") {
            event.preventDefault();
            moveDocumentRowFocus(explorer, row, "first", config);
            return;
        }

        if (event.key === "End") {
            event.preventDefault();
            moveDocumentRowFocus(explorer, row, "last", config);
            return;
        }

        if ((event.key === "F10" && event.shiftKey) || event.key === "ContextMenu") {
            event.preventDefault();
            selectFile(explorer, row, config, {
                selectionIntent: "context_menu",
                openInspector: false
            });
            openDocumentRowActionMenu(explorer, row, config);
        }
    }

    function bindRenderedDocumentRow(explorer, row, options) {
        const config = getConfig(options);

        if (!explorer || !row || row.getAttribute("data-document-row-bound") === "true") {
            return;
        }

        row.setAttribute("data-document-row-bound", "true");

        if (isSharedListingRow(row, config)) {
            return;
        }

        row.addEventListener("click", function (event) {
            handleDocumentRowClick(event, explorer, config);
        });

        row.addEventListener("dblclick", function (event) {
            handleDocumentRowDoubleClick(event, explorer, config);
        });

        row.addEventListener("contextmenu", function (event) {
            handleDocumentRowContextMenu(event, explorer, config);
        });
    }

    function getSharedListingActionElement(event, row, config) {
        const actionElement = event?.detail?.actionElement;

        if (actionElement?.matches?.(config.actionMenuItemSelector)) {
            return actionElement;
        }

        if (actionElement?.closest) {
            const closestAction = actionElement.closest(config.actionMenuItemSelector);

            if (closestAction) {
                return closestAction;
            }
        }

        const actionName = normalizeActionName(event?.detail?.action);

        if (!actionName || !row) {
            return null;
        }

        return Array.from(row.querySelectorAll(config.actionMenuItemSelector)).find(function (item) {
            return normalizeActionName(getActionName(item, config)) === actionName;
        }) || null;
    }

    function handleSharedListingSelectEvent(event, explorer, options) {
        const config = getConfig(options);
        const row = getRowFromEvent(event, explorer, config);

        if (!row || event?.detail?.selected !== true) {
            return false;
        }

        selectFile(explorer, row, config, {
            selectionIntent:
                normalizeActionName(event?.detail?.selectionIntent) ||
                "programmatic_selection",
            openInspector: event?.detail?.openInspector === true
        });
        return true;
    }

    function handleSharedListingDetailsEvent(event, explorer, row, config) {
        if (!row || typeof config.showFileDetails !== "function") {
            return false;
        }

        event.preventDefault();
        event.stopPropagation();
        selectFile(explorer, row, config, {
            selectionIntent: "details_command",
            openInspector: false
        });
        config.showFileDetails(explorer, row);

        return true;
    }

    function handleSharedListingActionEvent(event, explorer, options) {
        const config = getConfig(options);
        const row = getRowFromEvent(event, explorer, config);
        const actionName = normalizeActionName(event?.detail?.action);

        if (!row || !actionName || isCommonFileAction(actionName)) {
            return false;
        }

        const actionItem = getSharedListingActionElement(event, row, config);

        if (!actionItem) {
            if (actionName === "details") {
                return handleSharedListingDetailsEvent(
                    event,
                    explorer,
                    row,
                    config
                );
            }

            return false;
        }

        event.preventDefault();
        event.stopPropagation();
        runDocumentActionMenuItem(explorer, actionItem, config);

        return true;
    }

    function bindSharedListingAdapter(explorer, options) {
        const config = getConfig(options);

        if (!explorer || explorer[SHARED_LISTING_ADAPTER_KEY] === true) {
            return;
        }

        explorer[SHARED_LISTING_ADAPTER_KEY] = true;

        explorer.addEventListener(
            config.sharedListingSelectEvent,
            function (event) {
                handleSharedListingSelectEvent(event, explorer, config);
            },
            true
        );

        explorer.addEventListener(
            config.sharedListingActionEvent,
            function (event) {
                handleSharedListingActionEvent(event, explorer, config);
            },
            true
        );
    }

    function bindRenderedDocumentRows(explorer, options) {
        const config = getConfig(options);

        bindSharedListingAdapter(explorer, config);
        bindWorkspaceContextMenuCoordinator(explorer, config);

        config.getDocumentRows(explorer, config).forEach(function (row) {
            bindRenderedDocumentRow(explorer, row, config);
        });
    }

    function getActionName(actionItem, options) {
        const config = getConfig(options);

        return normalizeActionName(
            cleanValue(actionItem?.getAttribute(config.actionNameAttribute)) ||
            cleanValue(actionItem?.dataset?.documentActionMenuItem)
        );
    }

    function isDisabledActionItem(actionItem) {
        return Boolean(
            actionItem?.disabled ||
            actionItem?.getAttribute("aria-disabled") === "true"
        );
    }

    function getActionSelection(actionItem, config) {
        if (config.getActionSelectionFromMenuItem) {
            return config.getActionSelectionFromMenuItem(actionItem);
        }

        const documentId = cleanValue(actionItem?.getAttribute("data-document-id"));

        if (!documentId) {
            return null;
        }

        return {
            action: actionItem,
            documentId,
            documentIds: [documentId],
            documentNames: []
        };
    }

    function getActionRow(explorer, documentId, config) {
        const cleanId = cleanValue(documentId);

        if (!cleanId || !window.CSS || typeof window.CSS.escape !== "function") {
            return null;
        }

        return explorer?.querySelector(`${config.rowSelector}[data-document-id="${CSS.escape(cleanId)}"]`) || null;
    }

    function showStatus(explorer, payload, config) {
        if (config.showStatus) {
            config.showStatus(explorer, payload);
        }
    }

    function selectActionRows(explorer, request, config) {
        if (request.selectedCount > 1) {
            if (config.setDocumentRowsSelectedByIds) {
                config.setDocumentRowsSelectedByIds(explorer, request.documentIds);
            }

            if (config.updateSelectionFromRows) {
                config.updateSelectionFromRows(explorer, {
                    selectionIntent: "action_menu",
                    openInspector: false
                });
            }
            return;
        }

        if (request.row) {
            selectFile(explorer, request.row, config, {
                selectionIntent: "action_menu",
                openInspector: false
            });
        }
    }

    function buildActionRequest(explorer, actionItem, config) {
        const actionName = getActionName(actionItem, config);
        const selection = getActionSelection(actionItem, config);
        const documentIds = Array.isArray(selection?.documentIds) ? selection.documentIds : [];
        const documentId = cleanValue(selection?.documentId || documentIds[0]);
        const row = getActionRow(explorer, documentId, config);

        if (!actionName || !documentIds.length) {
            return null;
        }

        return {
            actionItem,
            actionName,
            solomonActionId: cleanValue(actionItem?.getAttribute("data-solomon-action-id")),
            solomonActionFamily: cleanValue(actionItem?.getAttribute("data-solomon-action-family")),
            actionLabel: cleanValue(actionItem?.getAttribute("data-document-single-label")),
            selection,
            documentId,
            documentIds,
            documentNames: Array.isArray(selection?.documentNames) ? selection.documentNames : [],
            row,
            selectedCount: documentIds.length
        };
    }

    function isCommonFileAction(actionName) {
        return COMMON_FILE_ACTIONS.includes(normalizeActionName(actionName));
    }

    function isActiveFileAction(actionName) {
        return ACTIVE_FILE_ACTIONS.includes(normalizeActionName(actionName));
    }

    function isTrashFileAction(actionName) {
        return TRASH_FILE_ACTIONS.includes(normalizeActionName(actionName));
    }

    function runDocumentActionMenuItem(explorer, actionItem, options) {
        const config = getConfig(options);
        const request = buildActionRequest(explorer, actionItem, config);

        if (!request || isDisabledActionItem(actionItem)) {
            return;
        }

        closeDocumentActionMenus(explorer, null, config);
        selectActionRows(explorer, request, config);

        if (
            config.hasAnyDocumentInTrashContext &&
            config.hasAnyDocumentInTrashContext(explorer, request.documentIds) &&
            isActiveFileAction(request.actionName)
        ) {
            showStatus(explorer, {
                action: request.actionName,
                documentId: request.documentId,
                documentIds: request.documentIds,
                variant: "info",
                message: "Restore the selected file before using this action."
            }, config);
            return;
        }

        if (
            config.hasAnyDocumentOutsideTrashContext &&
            config.hasAnyDocumentOutsideTrashContext(explorer, request.documentIds) &&
            isTrashFileAction(request.actionName)
        ) {
            showStatus(explorer, {
                action: request.actionName,
                documentId: request.documentId,
                documentIds: request.documentIds,
                variant: "info",
                message: "This action is only available in Trash."
            }, config);
            return;
        }

        if (request.solomonActionId) {
            if (request.selectedCount > 1) {
                showStatus(explorer, {
                    action: request.actionName,
                    documentIds: request.documentIds,
                    variant: "info",
                    message: `${request.actionLabel || "This Action"} is available for one file at a time.`
                }, config);
                return;
            }

            if (config.runSolomonAction) {
                config.runSolomonAction(explorer, request);
            } else {
                showStatus(explorer, {
                    action: request.actionName,
                    documentId: request.documentId,
                    variant: "error",
                    message: "The Solomon Action runner is not available in this workspace."
                }, config);
            }
            return;
        }

        if (request.actionName === "details") {
            if (request.selectedCount > 1) {
                showStatus(explorer, {
                    action: "details",
                    documentIds: request.documentIds,
                    variant: "info",
                    message: "Details are available for one file at a time."
                }, config);
                return;
            }

            if (request.row && config.showFileDetails) {
                config.showFileDetails(explorer, request.row);
            }
            return;
        }

        if (request.actionName === "share") {
            if (config.openShare) {
                config.openShare(explorer, request.documentIds, {
                    documentNames: request.documentNames
                });
            }
            return;
        }

        if (request.actionName === "summary") {
            if (request.selectedCount > 1) {
                showStatus(explorer, {
                    action: "summary",
                    documentIds: request.documentIds,
                    variant: "info",
                    message: "View Summary is available for one file at a time."
                }, config);
                return;
            }

            if (request.row && config.showFileSummary) {
                config.showFileSummary(explorer, request.row);
            }
            return;
        }

        if (
            request.actionName === "open" ||
            request.actionName === "open_reader" ||
            request.actionName === "reader"
        ) {
            if (request.selectedCount > 1) {
                showStatus(explorer, {
                    action: "open_reader",
                    documentIds: request.documentIds,
                    variant: "info",
                    message: "Reader opens one file at a time."
                }, config);
                return;
            }

            if (request.row) {
                openDocumentRow(explorer, request.row, config);
            } else if (config.openDocument) {
                config.openDocument(explorer, request.documentId);
            }
            return;
        }

        if (request.actionName === "ask_solomon_ai") {
            if (config.requestSolomonAiSession) {
                config.requestSolomonAiSession(explorer, request.documentIds, {
                    documentNames: request.documentNames
                });
            }
            return;
        }

        if (request.actionName === "delete") {
            if (config.requestMoveDocumentToTrash) {
                config.requestMoveDocumentToTrash(explorer, request.documentIds);
            }
            return;
        }

        if (request.actionName === "restore") {
            if (config.restoreDocumentFromTrash) {
                config.restoreDocumentFromTrash(explorer, request.documentIds);
            }
            return;
        }

        if (request.actionName === "permanent_delete") {
            if (config.requestPermanentDeleteDocument) {
                config.requestPermanentDeleteDocument(explorer, request.documentIds);
            }
            return;
        }

        if (config.onUnsupportedAction) {
            config.onUnsupportedAction(explorer, request);
        }
    }

    function handleDocumentActionMenuButtonClick(event, explorer, options) {
        const config = getConfig(options);
        const button = event?.target?.closest(config.actionMenuButtonSelector);
        const row = button?.closest(config.rowSelector);

        if (!button || !explorer?.contains(button)) {
            return false;
        }

        if (isSharedListingRow(row, config)) {
            return false;
        }

        event.preventDefault();
        event.stopPropagation();
        toggleDocumentActionMenu(explorer, button, config);

        return true;
    }

    function handleDocumentActionMenuItemClick(event, explorer, options) {
        const config = getConfig(options);
        const actionItem = event?.target?.closest(config.actionMenuItemSelector);
        const row = actionItem?.closest(config.rowSelector);

        if (!actionItem || !explorer?.contains(actionItem)) {
            return false;
        }

        if (isSharedListingRow(row, config)) {
            return false;
        }

        event.preventDefault();
        event.stopPropagation();
        runDocumentActionMenuItem(explorer, actionItem, config);

        return true;
    }

    function handleDocumentActionMenuKeydown(event, explorer, options) {
        const config = getConfig(options);

        if (event.defaultPrevented || event.key !== "Escape") {
            return false;
        }

        if (!hasOpenDocumentActionMenu(explorer, config)) {
            return false;
        }

        event.preventDefault();
        closeDocumentActionMenus(explorer, null, config);

        return true;
    }

    function handleDocumentActionMenuOutsideClick(event, explorer, options) {
        const config = getConfig(options);

        if (!hasOpenDocumentActionMenu(explorer, config)) {
            return false;
        }

        if (event?.target?.closest(config.actionMenuSelector)) {
            return false;
        }

        closeDocumentActionMenus(explorer, null, config);

        return true;
    }

    window.SolomonWorkspaceDocumentInteractions = Object.freeze({
        bindRenderedDocumentRow,
        bindRenderedDocumentRows,
        bindSharedListingAdapter,
        bindWorkspaceContextMenuCoordinator,
        canOpenDocumentRow,
        canSelectDocumentRow,
        cleanValue,
        closeDocumentActionMenus,
        dispatchWorkspaceContextMenuClose,
        dispatchWorkspaceContextMenuOpen,
        focusDocumentRow,
        getDocumentIdFromRow,
        getDocumentRows,
        handleDocumentActionMenuButtonClick,
        handleDocumentActionMenuItemClick,
        handleDocumentActionMenuKeydown,
        handleDocumentActionMenuOutsideClick,
        handleDocumentRowClick,
        handleDocumentRowContextMenu,
        handleDocumentRowDoubleClick,
        handleDocumentRowKeydown,
        hasOpenDocumentActionMenu,
        isDocumentRowInteractionControl,
        isDocumentRowMenuControl,
        isDocumentRowOpenBlockedControl,
        isSelectionModifierEvent,
        isSharedListingRow,
        moveDocumentRowFocus,
        openDocumentRow,
        openDocumentRowActionMenu,
        runDocumentActionMenuItem,
        toggleDocumentActionMenu
    });
})();