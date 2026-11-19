/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_conversation_navigation.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI conversation opening, contextual management, new-chat
   creation, and workspace exit navigation.

   Single click opens a History conversation asynchronously. The
   currently open conversation is the only persistently highlighted
   row. Each row exposes Rename and Delete through its options button,
   right-click menu, or keyboard context-menu command. Rename is edited
   inline within its owning row. The server remains authoritative for
   ownership, persistence, lifecycle, and recovery navigation.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before conversation navigation."
        );
    }

    const contract = modules.requireModule("contract");
    const {
        constants,
        cleanValue,
        readJsonResponse,
        setElementVisibility
    } = contract;

    const SELECTORS = Object.freeze({
        row: "[data-solomon-ai-history-row]",
        item: "[data-solomon-ai-history-item]",
        options: "[data-solomon-ai-history-options]",
        menu: "[data-solomon-ai-history-menu]",
        rename: "[data-solomon-ai-history-rename]",
        remove: "[data-solomon-ai-history-delete]",
        editor: "[data-solomon-ai-history-rename-editor]",
        input: "[data-solomon-ai-history-rename-input]",
        save: "[data-solomon-ai-history-rename-save]",
        cancel: "[data-solomon-ai-history-rename-cancel]",
        menuItem: "[role='menuitem']"
    });
    const MANAGEMENT_URL_ATTRIBUTE =
        "data-solomon-ai-conversation-management-url";
    const RENAME_URL_ATTRIBUTE =
        "data-solomon-ai-conversation-rename-url";
    const DELETE_URL_ATTRIBUTE =
        "data-solomon-ai-conversation-delete-url";
    const MANAGEMENT_PENDING_ATTRIBUTE =
        "data-solomon-ai-history-management-pending";
    const MANAGED_CONVERSATION_ATTRIBUTE =
        "data-solomon-ai-managed-conversation-id";

    let currentElements = null;
    let documentEventsBound = false;

    function getConversationId(elements) {
        const parts = window.location.pathname
            .split("/")
            .filter(Boolean);

        if (
            parts.length !== 3 ||
            parts[0] !== "ai" ||
            parts[1] !== "c"
        ) {
            return "";
        }

        let routeId = "";

        try {
            routeId = cleanValue(
                decodeURIComponent(parts[2])
            );
        } catch (error) {
            routeId = cleanValue(parts[2]);
        }

        const attributeId = cleanValue(
            elements?.workspace?.getAttribute(
                "data-solomon-ai-conversation-id"
            )
        );

        return (
            attributeId &&
            attributeId !== routeId
        )
            ? ""
            : routeId;
    }

    function buildConversationUrl(conversationId) {
        const cleanId = cleanValue(conversationId);

        return cleanId
            ? `/ai/c/${encodeURIComponent(cleanId)}`
            : "/ai";
    }

    function getSameOriginUrl(value) {
        const cleanUrl = cleanValue(value);

        if (!cleanUrl) {
            return null;
        }

        try {
            const parsedUrl = new URL(
                cleanUrl,
                window.location.origin
            );

            return parsedUrl.origin === window.location.origin
                ? parsedUrl
                : null;
        } catch (error) {
            return null;
        }
    }

    function getRelativeUrl(url) {
        if (!url) {
            return "";
        }

        return `${url.pathname}${url.search}${url.hash}`;
    }

    function getValidatedWorkspacePath(
        workspaceUrl
    ) {
        const url = getSameOriginUrl(workspaceUrl);

        if (!url) {
            return "";
        }

        const parts = url.pathname
            .split("/")
            .filter(Boolean);
        const isWorkspaceRoot = (
            parts.length === 1 &&
            parts[0] === "ai"
        );
        const isConversationRoute = (
            parts.length === 3 &&
            parts[0] === "ai" &&
            parts[1] === "c" &&
            Boolean(cleanValue(parts[2]))
        );

        if (
            url.search ||
            url.hash ||
            (
                !isWorkspaceRoot &&
                !isConversationRoute
            )
        ) {
            return "";
        }

        return url.pathname;
    }

    function navigateWithAnchorFallback(route) {
        const targetUrl = getSameOriginUrl(route);
        const cleanRoute = getRelativeUrl(targetUrl) || cleanValue(route);

        if (!cleanRoute) {
            return false;
        }

        const fallbackLink = document.createElement("a");

        fallbackLink.href = cleanRoute;
        fallbackLink.style.display = "none";
        fallbackLink.setAttribute(
            "data-solomon-ai-navigation-fallback",
            "true"
        );

        document.body.appendChild(fallbackLink);
        fallbackLink.click();
        fallbackLink.remove();

        return true;
    }

    async function loadRightPaneRoute(
        route,
        moduleId,
        options
    ) {
        const targetUrl = getSameOriginUrl(route);
        const cleanRoute = getRelativeUrl(targetUrl);
        const navigationApi =
            window.NationsCommandSidebar;
        const allowFallback =
            options?.allowFullNavigation !== false;
        const loadOptions = Object.assign(
            {
                push: options?.push !== false,
                async: true,
                launchMode: "solomon_ai_navigation",
                source: "workspace_solomon_ai_conversation_navigation"
            },
            options || {}
        );

        if (!cleanRoute) {
            return false;
        }

        if (
            navigationApi &&
            typeof navigationApi.loadWorkspace ===
                "function"
        ) {
            try {
                const result = await navigationApi.loadWorkspace(
                    cleanRoute,
                    moduleId,
                    loadOptions
                );

                if (result !== false) {
                    return true;
                }
            } catch (error) {
                console.warn(
                    "[SOLOMON_AI_NAVIGATION] Asynchronous workspace transition failed.",
                    error
                );
            }
        }

        return allowFallback
            ? navigateWithAnchorFallback(cleanRoute)
            : false;
    }

    async function loadSolomonAIWorkspace(
        workspaceUrl,
        options
    ) {
        const cleanWorkspaceUrl =
            getValidatedWorkspacePath(
                workspaceUrl
            );

        if (!cleanWorkspaceUrl) {
            return false;
        }

        return loadRightPaneRoute(
            cleanWorkspaceUrl,
            constants.SOLOMON_AI_MODULE_ID,
            Object.assign(
                {
                    launchMode: "solomon_ai_workspace"
                },
                options || {}
            )
        );
    }

    function getHistoryRows(elements) {
        return Array.from(
            elements?.workspace?.querySelectorAll(
                SELECTORS.row
            ) || []
        );
    }

    function getHistoryItems(elements) {
        return Array.from(
            elements?.workspace?.querySelectorAll(
                SELECTORS.item
            ) || []
        );
    }

    function getHistoryRow(node) {
        return (
            node?.closest?.(
                SELECTORS.row
            ) ||
            null
        );
    }

    function getHistoryItem(row) {
        return (
            row?.querySelector(
                SELECTORS.item
            ) ||
            null
        );
    }

    function getHistoryOptions(row) {
        return (
            row?.querySelector(
                SELECTORS.options
            ) ||
            null
        );
    }

    function getHistoryMenu(row) {
        return (
            row?.querySelector(
                SELECTORS.menu
            ) ||
            null
        );
    }

    function getHistoryMenuItems(row) {
        return Array.from(
            getHistoryMenu(row)?.querySelectorAll(
                `${SELECTORS.menuItem}:not([disabled])`
            ) || []
        );
    }

    function getRenameEditor(row) {
        return (
            row?.querySelector(
                SELECTORS.editor
            ) ||
            null
        );
    }

    function getRenameInput(row) {
        return (
            getRenameEditor(row)?.querySelector(
                SELECTORS.input
            ) ||
            null
        );
    }

    function getRenameCancel(row) {
        return (
            getRenameEditor(row)?.querySelector(
                SELECTORS.cancel
            ) ||
            null
        );
    }

    function getHistoryConversationId(node) {
        const row = getHistoryRow(node);

        return cleanValue(
            row?.getAttribute(
                "data-conversation-id"
            ) ||
            node?.getAttribute?.(
                "data-conversation-id"
            ) ||
            node?.getAttribute?.(
                "data-solomon-ai-conversation-id"
            )
        );
    }

    function getHistoryConversationTitle(node) {
        const row = getHistoryRow(node);

        return cleanValue(
            row?.getAttribute(
                "data-conversation-title"
            ) ||
            node?.getAttribute?.(
                "data-conversation-title"
            ) ||
            row?.querySelector(
                "[data-solomon-ai-history-item-title]"
            )?.textContent
        ) || "SolomonAI conversation";
    }

    function getHistoryUrlAttribute(actionName) {
        const cleanAction =
            cleanValue(actionName);

        if (cleanAction === "delete") {
            return DELETE_URL_ATTRIBUTE;
        }

        if (cleanAction === "rename") {
            return RENAME_URL_ATTRIBUTE;
        }

        return MANAGEMENT_URL_ATTRIBUTE;
    }

    function readHistoryUrlAttribute(
        node,
        attributeName
    ) {
        const row = getHistoryRow(node);

        return cleanValue(
            row?.getAttribute(
                attributeName
            ) ||
            node?.getAttribute?.(
                attributeName
            )
        );
    }

    function getHistoryManagementUrl(
        node,
        actionName
    ) {
        const row = getHistoryRow(node);
        const conversationId =
            getHistoryConversationId(
                row || node
            );
        const cleanAction =
            cleanValue(actionName);
        const actionUrlAttribute =
            getHistoryUrlAttribute(cleanAction);
        let endpoint =
            readHistoryUrlAttribute(
                row || node,
                actionUrlAttribute
            );

        if (
            !endpoint &&
            cleanAction === "rename"
        ) {
            endpoint =
                readHistoryUrlAttribute(
                    row || node,
                    MANAGEMENT_URL_ATTRIBUTE
                );
        }

        if (!conversationId || !endpoint) {
            return "";
        }

        try {
            const url = new URL(
                endpoint,
                window.location.origin
            );

            if (
                url.origin !==
                    window.location.origin ||
                url.search ||
                url.hash
            ) {
                return "";
            }

            return url.pathname;
        } catch (error) {
            return "";
        }
    }

    function getHistoryRowByConversationId(
        elements,
        conversationId
    ) {
        const cleanConversationId =
            cleanValue(conversationId);

        if (!cleanConversationId) {
            return null;
        }

        return (
            getHistoryRows(elements).find(
                function (row) {
                    return (
                        getHistoryConversationId(row) ===
                        cleanConversationId
                    );
                }
            ) ||
            null
        );
    }

    function getOpenMenuRow(elements) {
        return (
            getHistoryRows(elements).find(
                function (row) {
                    return row.classList.contains(
                        "is-menu-open"
                    );
                }
            ) ||
            null
        );
    }

    function getActiveRenameRow(elements) {
        return (
            getHistoryRows(elements).find(
                function (row) {
                    return row.classList.contains(
                        "is-renaming"
                    );
                }
            ) ||
            null
        );
    }

    function setManagedConversation(
        elements,
        conversationId
    ) {
        const cleanConversationId =
            cleanValue(conversationId);

        if (!elements?.workspace) {
            return;
        }

        if (cleanConversationId) {
            elements.workspace.setAttribute(
                MANAGED_CONVERSATION_ATTRIBUTE,
                cleanConversationId
            );
            return;
        }

        elements.workspace.removeAttribute(
            MANAGED_CONVERSATION_ATTRIBUTE
        );
    }

    function getManagedHistoryRow(elements) {
        const conversationId = cleanValue(
            elements?.workspace?.getAttribute(
                MANAGED_CONVERSATION_ATTRIBUTE
            )
        );

        return getHistoryRowByConversationId(
            elements,
            conversationId
        );
    }

    function getHistoryStateElement(elements) {
        return (
            elements?.history ||
            elements?.workspace ||
            null
        );
    }

    function isHistoryManagementPending(elements) {
        return (
            getHistoryStateElement(
                elements
            )?.getAttribute(
                MANAGEMENT_PENDING_ATTRIBUTE
            ) === "true"
        );
    }

    function setHistoryManagementStatus(
        elements,
        message
    ) {
        if (elements?.historyManagementStatus) {
            elements.historyManagementStatus.textContent =
                cleanValue(message);
        }
    }

    function setControlDisabled(
        control,
        disabled
    ) {
        if (!control) {
            return;
        }

        control.disabled = Boolean(disabled);
        control.setAttribute(
            "aria-disabled",
            disabled ? "true" : "false"
        );
    }

    function setHistoryManagementPending(
        elements,
        pending
    ) {
        const stateElement =
            getHistoryStateElement(elements);

        if (!stateElement) {
            return;
        }

        stateElement.setAttribute(
            MANAGEMENT_PENDING_ATTRIBUTE,
            pending ? "true" : "false"
        );
        stateElement.setAttribute(
            "aria-busy",
            pending ? "true" : "false"
        );

        [
            ...getHistoryItems(elements),
            ...(elements?.historyOptions || []),
            ...(elements?.historyRenameButtons || []),
            ...(elements?.historyDeleteButtons || []),
            ...(elements?.historyRenameInputs || []),
            ...(elements?.historyRenameSaveButtons || []),
            ...(elements?.historyRenameCancelButtons || [])
        ].forEach(function (control) {
            setControlDisabled(
                control,
                pending
            );
        });
    }

    function closeHistoryMenus(
        elements,
        options
    ) {
        const exceptRow =
            options?.exceptRow || null;
        const restoreFocusRow =
            options?.restoreFocusRow || null;

        getHistoryRows(elements).forEach(
            function (row) {
                if (row === exceptRow) {
                    return;
                }

                const menu =
                    getHistoryMenu(row);
                const trigger =
                    getHistoryOptions(row);

                row.classList.remove(
                    "is-menu-open"
                );

                if (menu) {
                    menu.hidden = true;
                    menu.setAttribute(
                        "aria-hidden",
                        "true"
                    );
                }

                trigger?.setAttribute(
                    "aria-expanded",
                    "false"
                );
            }
        );

        if (!restoreFocusRow) {
            return;
        }

        const trigger =
            getHistoryOptions(
                restoreFocusRow
            );

        if (
            trigger &&
            !trigger.disabled &&
            document.contains(trigger)
        ) {
            trigger.focus({
                preventScroll: true
            });
        }
    }

    function closeRenameEditor(
        elements,
        options
    ) {
        const managedRow =
            getManagedHistoryRow(elements) ||
            getActiveRenameRow(elements);
        const restoreFocus =
            options?.restoreFocus === true;

        getHistoryRows(elements).forEach(
            function (row) {
                const editor =
                    getRenameEditor(row);
                const input =
                    getRenameInput(row);

                row.classList.remove(
                    "is-renaming"
                );

                if (editor) {
                    setElementVisibility(
                        editor,
                        false
                    );
                }

                if (input) {
                    input.value =
                        getHistoryConversationTitle(
                            row
                        );
                }
            }
        );

        setManagedConversation(
            elements,
            ""
        );

        if (
            !restoreFocus ||
            !managedRow
        ) {
            return;
        }

        const trigger =
            getHistoryOptions(managedRow);

        if (
            trigger &&
            !trigger.disabled &&
            document.contains(trigger)
        ) {
            trigger.focus({
                preventScroll: true
            });
        }
    }

    function openHistoryMenu(
        elements,
        row,
        options
    ) {
        const menu =
            getHistoryMenu(row);
        const trigger =
            getHistoryOptions(row);

        if (
            !row ||
            !menu ||
            !trigger ||
            isHistoryManagementPending(elements)
        ) {
            return false;
        }

        closeRenameEditor(
            elements,
            {
                restoreFocus: false
            }
        );
        closeHistoryMenus(
            elements,
            {
                exceptRow: row
            }
        );

        row.classList.add(
            "is-menu-open"
        );
        menu.hidden = false;
        menu.setAttribute(
            "aria-hidden",
            "false"
        );
        trigger.setAttribute(
            "aria-expanded",
            "true"
        );

        setHistoryManagementStatus(
            elements,
            ""
        );

        if (options?.focusFirst === true) {
            const firstItem =
                getHistoryMenuItems(row)[0];

            window.requestAnimationFrame(
                function () {
                    if (
                        firstItem &&
                        !menu.hidden &&
                        document.contains(firstItem)
                    ) {
                        firstItem.focus({
                            preventScroll: true
                        });
                    }
                }
            );
        }

        return true;
    }

    function toggleHistoryMenu(
        elements,
        row
    ) {
        if (
            row?.classList.contains(
                "is-menu-open"
            )
        ) {
            closeHistoryMenus(
                elements,
                {
                    restoreFocusRow: row
                }
            );

            return false;
        }

        return openHistoryMenu(
            elements,
            row,
            {
                focusFirst: true
            }
        );
    }

    function focusAdjacentHistoryItem(
        elements,
        currentItem,
        offset
    ) {
        const items =
            getHistoryItems(elements);
        const currentIndex =
            items.indexOf(currentItem);

        if (
            !items.length ||
            currentIndex < 0
        ) {
            return;
        }

        const nextIndex = (
            currentIndex +
            offset +
            items.length
        ) % items.length;

        items[nextIndex].focus({
            preventScroll: true
        });
    }

    function focusBoundaryHistoryItem(
        elements,
        boundary
    ) {
        const items =
            getHistoryItems(elements);

        if (!items.length) {
            return;
        }

        const item = boundary === "end"
            ? items[items.length - 1]
            : items[0];

        item.focus({
            preventScroll: true
        });
    }

    function focusAdjacentMenuItem(
        row,
        currentItem,
        offset
    ) {
        const items =
            getHistoryMenuItems(row);
        const currentIndex =
            items.indexOf(currentItem);

        if (
            !items.length ||
            currentIndex < 0
        ) {
            return;
        }

        const nextIndex = (
            currentIndex +
            offset +
            items.length
        ) % items.length;

        items[nextIndex].focus({
            preventScroll: true
        });
    }

    function isPending(elements) {
        return (
            elements?.composer?.getAttribute(
                "data-solomon-ai-pending"
            ) === "true"
        );
    }

    function canManageHistory(elements) {
        if (isPending(elements)) {
            setHistoryManagementStatus(
                elements,
                "Wait for the current response to finish before managing conversations."
            );

            return false;
        }

        return !isHistoryManagementPending(elements);
    }

    async function navigateToConversation(
        elements,
        conversationId
    ) {
        const cleanId =
            cleanValue(conversationId);

        if (!cleanId) {
            return false;
        }

        if (
            isHistoryManagementPending(elements)
        ) {
            setHistoryManagementStatus(
                elements,
                "Wait for the current operation to finish before opening another conversation."
            );

            return false;
        }

        closeHistoryMenus(elements);
        closeRenameEditor(
            elements,
            {
                restoreFocus: false
            }
        );

        if (
            cleanId ===
            getConversationId(elements)
        ) {
            return true;
        }

        if (isPending(elements)) {
            setHistoryManagementStatus(
                elements,
                "Wait for the current response to finish before opening another conversation."
            );

            return false;
        }

        setHistoryManagementPending(
            elements,
            true
        );
        setHistoryManagementStatus(
            elements,
            "Opening conversation."
        );

        const transitioned =
            await loadSolomonAIWorkspace(
                buildConversationUrl(cleanId),
                {
                    push: true,
                    launchMode: "solomon_ai_history_conversation",
                    conversationId: cleanId
                }
            );

        if (
            !transitioned &&
            document.contains(
                elements?.workspace
            )
        ) {
            setHistoryManagementPending(
                elements,
                false
            );
            setHistoryManagementStatus(
                elements,
                "The conversation could not be opened."
            );
        }

        return transitioned;
    }

    async function openHistoryItem(
        elements,
        item
    ) {
        const row =
            getHistoryRow(item);
        const conversationId =
            getHistoryConversationId(row);

        if (!row || !conversationId) {
            return false;
        }

        return navigateToConversation(
            elements,
            conversationId
        );
    }

    function openRenameEditor(
        elements,
        row
    ) {
        const conversationId =
            getHistoryConversationId(row);
        const editor =
            getRenameEditor(row);
        const input =
            getRenameInput(row);

        if (
            !canManageHistory(elements) ||
            !row ||
            !conversationId ||
            !getHistoryManagementUrl(row, "rename") ||
            !editor ||
            !input
        ) {
            return false;
        }

        closeHistoryMenus(elements);
        closeRenameEditor(
            elements,
            {
                restoreFocus: false
            }
        );

        setManagedConversation(
            elements,
            conversationId
        );
        row.classList.add(
            "is-renaming"
        );

        input.value =
            getHistoryConversationTitle(row);

        setElementVisibility(
            editor,
            true
        );
        setHistoryManagementStatus(
            elements,
            ""
        );

        input.focus({
            preventScroll: true
        });
        input.select();

        return true;
    }

    function validateManagementPacket(
        packet,
        expectedAction,
        expectedConversationId
    ) {
        const conversationId = cleanValue(
            packet?.conversation_id
        );

        if (
            packet?.ok !== true ||
            packet?.packet_type !==
                "solomon_ai_conversation_management" ||
            packet?.artifact_type !==
                "conversation" ||
            packet?.conversation_action !==
                expectedAction ||
            conversationId !==
                expectedConversationId
        ) {
            return null;
        }

        if (expectedAction === "renamed") {
            const title =
                cleanValue(packet?.title);
            const conversationUrl = cleanValue(
                packet?.conversation_url
            );
            const expectedPath =
                buildConversationUrl(
                    conversationId
                );

            if (
                packet?.status !== "ready" ||
                !title ||
                title.length >
                    constants.CONVERSATION_TITLE_MAX_LENGTH ||
                !conversationUrl
            ) {
                return null;
            }

            try {
                const url = new URL(
                    conversationUrl,
                    window.location.origin
                );

                if (
                    url.origin !==
                        window.location.origin ||
                    url.pathname !== expectedPath ||
                    url.search ||
                    url.hash
                ) {
                    return null;
                }
            } catch (error) {
                return null;
            }

            return {
                conversationId,
                title,
                conversationUrl: expectedPath
            };
        }

        if (
            expectedAction === "deleted" &&
            packet?.status === "deleted"
        ) {
            const workspaceUrl = cleanValue(
                packet?.workspace_url
            );

            try {
                const url = new URL(
                    workspaceUrl,
                    window.location.origin
                );

                if (
                    url.origin !==
                        window.location.origin ||
                    url.pathname !== "/ai" ||
                    url.search ||
                    url.hash
                ) {
                    return null;
                }
            } catch (error) {
                return null;
            }

            return {
                conversationId,
                workspaceUrl: "/ai",
                activeConversationCleared:
                    packet
                        ?.active_conversation_cleared ===
                    true
            };
        }

        return null;
    }

    function updateHistoryRowTitle(
        row,
        title
    ) {
        const cleanTitle =
            cleanValue(title);
        const item =
            getHistoryItem(row);
        const options =
            getHistoryOptions(row);
        const menu =
            getHistoryMenu(row);
        const editor =
            getRenameEditor(row);
        const input =
            getRenameInput(row);
        const titleElement =
            row?.querySelector(
                "[data-solomon-ai-history-item-title]"
            );

        if (!row || !cleanTitle) {
            return false;
        }

        row.setAttribute(
            "data-conversation-title",
            cleanTitle
        );

        if (item) {
            item.setAttribute(
                "data-conversation-title",
                cleanTitle
            );
            item.setAttribute(
                "title",
                cleanTitle
            );
            item.setAttribute(
                "aria-label",
                `Open ${cleanTitle}`
            );
        }

        options?.setAttribute(
            "aria-label",
            `More options for ${cleanTitle}`
        );
        menu?.setAttribute(
            "aria-label",
            `Options for ${cleanTitle}`
        );

        if (editor) {
            editor.setAttribute(
                "data-conversation-title",
                cleanTitle
            );
            editor.setAttribute(
                "aria-label",
                `Rename ${cleanTitle}`
            );
        }

        if (input) {
            input.value =
                cleanTitle;
        }

        if (titleElement) {
            titleElement.textContent =
                cleanTitle;
        }

        return true;
    }

    async function renameManagedConversation(
        elements,
        requestedRow
    ) {
        const managedRow =
            getManagedHistoryRow(elements);
        const row = (
            requestedRow &&
            requestedRow === managedRow
        )
            ? requestedRow
            : managedRow;
        const conversationId =
            getHistoryConversationId(row);
        const endpoint =
            getHistoryManagementUrl(row, "rename");
        const input =
            getRenameInput(row);
        const title =
            cleanValue(input?.value);

        if (
            !canManageHistory(elements) ||
            !row ||
            !conversationId ||
            !endpoint ||
            !input
        ) {
            return false;
        }

        if (!title) {
            setHistoryManagementStatus(
                elements,
                "Enter a name for this conversation."
            );
            input.focus({
                preventScroll: true
            });

            return false;
        }

        if (
            title.length >
            constants.CONVERSATION_TITLE_MAX_LENGTH
        ) {
            setHistoryManagementStatus(
                elements,
                (
                    "Conversation names may not exceed " +
                    constants
                        .CONVERSATION_TITLE_MAX_LENGTH +
                    " characters."
                )
            );
            input.focus({
                preventScroll: true
            });

            return false;
        }

        setHistoryManagementPending(
            elements,
            true
        );
        setHistoryManagementStatus(
            elements,
            "Renaming conversation."
        );

        let renamed = false;

        try {
            const response = await fetch(
                endpoint,
                {
                    method: "PATCH",
                    credentials: "same-origin",
                    headers: {
                        "Accept":
                            "application/json",
                        "Content-Type":
                            "application/json",
                        "X-Requested-With":
                            "XMLHttpRequest"
                    },
                    body: JSON.stringify({
                        title
                    })
                }
            );
            const packet =
                await readJsonResponse(
                    response
                );

            if (
                !response.ok ||
                packet?.ok === false
            ) {
                throw new Error(
                    cleanValue(
                        packet?.user_output ||
                        packet?.error
                    ) ||
                    "The SolomonAI conversation could not be renamed."
                );
            }

            const validatedPacket =
                validateManagementPacket(
                    packet,
                    "renamed",
                    conversationId
                );

            if (!validatedPacket) {
                throw new Error(
                    "The server returned an invalid conversation rename contract."
                );
            }

            updateHistoryRowTitle(
                row,
                validatedPacket.title
            );

            renamed = true;

            setHistoryManagementStatus(
                elements,
                "Conversation renamed."
            );

            return true;
        } catch (error) {
            setHistoryManagementStatus(
                elements,
                cleanValue(
                    error?.message
                ) ||
                "The SolomonAI conversation could not be renamed."
            );

            return false;
        } finally {
            setHistoryManagementPending(
                elements,
                false
            );

            if (renamed) {
                closeRenameEditor(
                    elements,
                    {
                        restoreFocus: true
                    }
                );
            } else if (
                input &&
                document.contains(input)
            ) {
                input.focus({
                    preventScroll: true
                });
            }
        }
    }

    async function confirmConversationDeletion() {
        const confirmationApi =
            window.SolomonUIConfirm;

        if (
            !confirmationApi ||
            typeof confirmationApi.confirm !==
                "function"
        ) {
            throw new Error(
                "The conversation confirmation surface is unavailable."
            );
        }

        return confirmationApi.confirm({
            eyebrow: "SolomonAI",
            title: "Delete conversation?",
            message:
                "You won't be able to recover this conversation.",
            confirmLabel: "Delete",
            cancelLabel: "Cancel",
            danger: true
        });
    }

    function removeDeletedHistoryRow(
        elements,
        deletedRow
    ) {
        const rowsBeforeDeletion =
            getHistoryRows(elements);
        const deletedIndex =
            rowsBeforeDeletion.indexOf(
                deletedRow
            );

        if (
            deletedRow &&
            elements?.workspace?.contains(
                deletedRow
            )
        ) {
            deletedRow.remove();
        }

        const remainingRows =
            getHistoryRows(elements);

        return (
            deletedIndex >= 0
                ? (
                    remainingRows[
                        Math.min(
                            deletedIndex,
                            remainingRows.length - 1
                        )
                    ] ||
                    remainingRows[
                        Math.max(
                            0,
                            deletedIndex - 1
                        )
                    ]
                )
                : remainingRows[0]
        ) || null;
    }

    async function recoverFromActiveConversationDeletion(
        workspaceUrl
    ) {
        return loadSolomonAIWorkspace(
            cleanValue(workspaceUrl) ||
                "/ai",
            {
                push: true,
                launchMode: "solomon_ai_deleted_conversation_recovery"
            }
        );
    }

    async function deleteConversation(
        elements,
        row
    ) {
        const conversationId =
            getHistoryConversationId(row);
        const endpoint =
            getHistoryManagementUrl(row, "delete");

        if (
            !canManageHistory(elements) ||
            !row ||
            !conversationId ||
            !endpoint
        ) {
            return false;
        }

        closeHistoryMenus(elements);
        closeRenameEditor(
            elements,
            {
                restoreFocus: false
            }
        );

        let confirmed = false;

        try {
            confirmed =
                await confirmConversationDeletion();
        } catch (error) {
            setHistoryManagementStatus(
                elements,
                cleanValue(
                    error?.message
                ) ||
                "The deletion confirmation could not be opened."
            );

            return false;
        }

        if (!confirmed) {
            setHistoryManagementStatus(
                elements,
                "Conversation deletion canceled."
            );

            return false;
        }

        if (
            !elements
                ?.workspace
                ?.contains(row)
        ) {
            setHistoryManagementStatus(
                elements,
                "The conversation is no longer available."
            );

            return false;
        }

        setHistoryManagementPending(
            elements,
            true
        );
        setHistoryManagementStatus(
            elements,
            "Deleting conversation."
        );

        let recoveringWorkspace = false;

        try {
            const response = await fetch(
                endpoint,
                {
                    method: "DELETE",
                    credentials: "same-origin",
                    headers: {
                        "Accept":
                            "application/json",
                        "X-Requested-With":
                            "XMLHttpRequest"
                    }
                }
            );
            const packet =
                await readJsonResponse(
                    response
                );

            if (
                !response.ok ||
                packet?.ok === false
            ) {
                throw new Error(
                    cleanValue(
                        packet?.user_output ||
                        packet?.error
                    ) ||
                    "The SolomonAI conversation could not be deleted."
                );
            }

            const validatedPacket =
                validateManagementPacket(
                    packet,
                    "deleted",
                    conversationId
                );

            if (!validatedPacket) {
                throw new Error(
                    "The server returned an invalid conversation deletion contract."
                );
            }

            const deletingActiveConversation = (
                conversationId ===
                    getConversationId(elements) ||
                validatedPacket
                    .activeConversationCleared
            );
            const nextRow =
                removeDeletedHistoryRow(
                    elements,
                    row
                );

            if (deletingActiveConversation) {
                recoveringWorkspace = true;

                setHistoryManagementStatus(
                    elements,
                    "Conversation deleted. Opening the next available chat."
                );

                const recovered =
                    await recoverFromActiveConversationDeletion(
                        validatedPacket.workspaceUrl
                    );

                if (!recovered) {
                    recoveringWorkspace = false;

                    throw new Error(
                        "The conversation was deleted, but SolomonAI could not open the next chat."
                    );
                }

                return true;
            }

            setHistoryManagementStatus(
                elements,
                "Conversation deleted."
            );

            const nextItem =
                getHistoryItem(nextRow);

            if (
                nextItem &&
                document.contains(nextItem)
            ) {
                nextItem.focus({
                    preventScroll: true
                });
            }

            return true;
        } catch (error) {
            setHistoryManagementStatus(
                elements,
                cleanValue(
                    error?.message
                ) ||
                "The SolomonAI conversation could not be deleted."
            );

            return false;
        } finally {
            if (!recoveringWorkspace) {
                setHistoryManagementPending(
                    elements,
                    false
                );
            }
        }
    }

    function handleHistoryClick(
        event,
        elements
    ) {
        const optionsButton =
            event.target.closest(
                SELECTORS.options
            );

        if (optionsButton) {
            event.preventDefault();
            event.stopPropagation();

            toggleHistoryMenu(
                elements,
                getHistoryRow(optionsButton)
            );
            return;
        }

        const renameButton =
            event.target.closest(
                SELECTORS.rename
            );

        if (renameButton) {
            event.preventDefault();
            event.stopPropagation();

            openRenameEditor(
                elements,
                getHistoryRow(renameButton)
            );
            return;
        }

        const deleteButton =
            event.target.closest(
                SELECTORS.remove
            );

        if (deleteButton) {
            event.preventDefault();
            event.stopPropagation();

            void deleteConversation(
                elements,
                getHistoryRow(deleteButton)
            );
            return;
        }

        const item =
            event.target.closest(
                SELECTORS.item
            );

        if (!item) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        void openHistoryItem(
            elements,
            item
        );
    }

    function handleHistoryContextMenu(
        event,
        elements
    ) {
        const row =
            event.target.closest(
                SELECTORS.row
            );

        if (
            !row ||
            event.target.closest(
                SELECTORS.menu
            )
        ) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();

        openHistoryMenu(
            elements,
            row,
            {
                focusFirst: true
            }
        );
    }

    function handleHistoryKeydown(
        event,
        elements
    ) {
        const item =
            event.target.closest(
                SELECTORS.item
            );

        if (item) {
            if (
                event.key === "Enter" ||
                event.key === " "
            ) {
                event.preventDefault();
                event.stopPropagation();

                void openHistoryItem(
                    elements,
                    item
                );
                return;
            }

            if (
                event.key === "ArrowDown" ||
                event.key === "ArrowUp"
            ) {
                event.preventDefault();
                event.stopPropagation();

                focusAdjacentHistoryItem(
                    elements,
                    item,
                    event.key === "ArrowDown"
                        ? 1
                        : -1
                );
                return;
            }

            if (
                event.key === "Home" ||
                event.key === "End"
            ) {
                event.preventDefault();
                event.stopPropagation();

                focusBoundaryHistoryItem(
                    elements,
                    event.key === "End"
                        ? "end"
                        : "start"
                );
                return;
            }

            if (
                event.key === "ContextMenu" ||
                (
                    event.shiftKey &&
                    event.key === "F10"
                )
            ) {
                event.preventDefault();
                event.stopPropagation();

                openHistoryMenu(
                    elements,
                    getHistoryRow(item),
                    {
                        focusFirst: true
                    }
                );
            }

            return;
        }

        const optionsButton =
            event.target.closest(
                SELECTORS.options
            );

        if (
            optionsButton &&
            event.key === "ArrowDown"
        ) {
            event.preventDefault();
            event.stopPropagation();

            openHistoryMenu(
                elements,
                getHistoryRow(optionsButton),
                {
                    focusFirst: true
                }
            );
            return;
        }

        const menuItem =
            event.target.closest(
                SELECTORS.menuItem
            );

        if (!menuItem) {
            return;
        }

        const row =
            getHistoryRow(menuItem);

        if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();

            closeHistoryMenus(
                elements,
                {
                    restoreFocusRow: row
                }
            );
            return;
        }

        if (
            event.key === "ArrowDown" ||
            event.key === "ArrowUp"
        ) {
            event.preventDefault();
            event.stopPropagation();

            focusAdjacentMenuItem(
                row,
                menuItem,
                event.key === "ArrowDown"
                    ? 1
                    : -1
            );
            return;
        }

        if (
            event.key === "Home" ||
            event.key === "End"
        ) {
            const menuItems =
                getHistoryMenuItems(row);
            const targetItem =
                event.key === "End"
                    ? menuItems[
                        menuItems.length - 1
                    ]
                    : menuItems[0];

            if (targetItem) {
                event.preventDefault();
                event.stopPropagation();

                targetItem.focus({
                    preventScroll: true
                });
            }
        }
    }

    function bindHistory(elements) {
        const history =
            elements?.history;

        if (
            !history ||
            history.getAttribute(
                "data-solomon-ai-history-navigation-bound"
            ) === "true"
        ) {
            return;
        }

        history.setAttribute(
            "data-solomon-ai-history-navigation-bound",
            "true"
        );

        history.addEventListener(
            "click",
            function (event) {
                handleHistoryClick(
                    event,
                    elements
                );
            }
        );

        history.addEventListener(
            "contextmenu",
            function (event) {
                handleHistoryContextMenu(
                    event,
                    elements
                );
            }
        );

        history.addEventListener(
            "keydown",
            function (event) {
                handleHistoryKeydown(
                    event,
                    elements
                );
            }
        );

        history.addEventListener(
            "focusout",
            function () {
                window.setTimeout(
                    function () {
                        const openRow =
                            getOpenMenuRow(
                                elements
                            );

                        if (
                            openRow &&
                            !openRow.contains(
                                document.activeElement
                            )
                        ) {
                            closeHistoryMenus(
                                elements
                            );
                        }
                    },
                    0
                );
            }
        );
    }

    function bindRenameEditors(elements) {
        const editors =
            elements?.historyRenameEditors || [];

        editors.forEach(
            function (editor) {
                if (
                    !editor ||
                    editor.getAttribute(
                        "data-solomon-ai-history-rename-bound"
                    ) === "true"
                ) {
                    return;
                }

                const row =
                    getHistoryRow(editor);
                const input =
                    getRenameInput(row);
                const cancelButton =
                    getRenameCancel(row);

                editor.setAttribute(
                    "data-solomon-ai-history-rename-bound",
                    "true"
                );

                editor.addEventListener(
                    "submit",
                    function (event) {
                        event.preventDefault();
                        event.stopPropagation();

                        void renameManagedConversation(
                            elements,
                            row
                        );
                    }
                );

                cancelButton?.addEventListener(
                    "click",
                    function (event) {
                        event.preventDefault();
                        event.stopPropagation();

                        if (
                            isHistoryManagementPending(
                                elements
                            )
                        ) {
                            return;
                        }

                        setHistoryManagementStatus(
                            elements,
                            ""
                        );
                        closeRenameEditor(
                            elements,
                            {
                                restoreFocus: true
                            }
                        );
                    }
                );

                input?.addEventListener(
                    "keydown",
                    function (event) {
                        if (
                            event.key !== "Escape" ||
                            isHistoryManagementPending(
                                elements
                            )
                        ) {
                            return;
                        }

                        event.preventDefault();
                        event.stopPropagation();

                        setHistoryManagementStatus(
                            elements,
                            ""
                        );
                        closeRenameEditor(
                            elements,
                            {
                                restoreFocus: true
                            }
                        );
                    }
                );
            }
        );
    }

    function bindDocumentEvents() {
        if (documentEventsBound) {
            return;
        }

        documentEventsBound = true;

        document.addEventListener(
            "pointerdown",
            function (event) {
                const elements =
                    currentElements;

                if (
                    !elements?.workspace ||
                    !document.contains(
                        elements.workspace
                    ) ||
                    event.target.closest(
                        SELECTORS.options
                    ) ||
                    event.target.closest(
                        SELECTORS.menu
                    )
                ) {
                    return;
                }

                closeHistoryMenus(
                    elements
                );
            },
            true
        );

        document.addEventListener(
            "keydown",
            function (event) {
                if (
                    event.key !== "Escape"
                ) {
                    return;
                }

                const elements =
                    currentElements;

                if (
                    !elements?.workspace ||
                    !document.contains(
                        elements.workspace
                    )
                ) {
                    return;
                }

                const openRow =
                    getOpenMenuRow(
                        elements
                    );

                if (!openRow) {
                    return;
                }

                event.preventDefault();

                closeHistoryMenus(
                    elements,
                    {
                        restoreFocusRow: openRow
                    }
                );
            },
            true
        );
    }

    function setNewChatStatus(
        elements,
        message
    ) {
        if (elements?.newChatStatus) {
            elements.newChatStatus.textContent =
                cleanValue(message);
        }
    }

    function getNewConversationUrl(packet) {
        const conversationId = cleanValue(
            packet?.conversation_id
        );
        const conversationUrl = cleanValue(
            packet?.conversation_url
        );
        const expectedPath =
            buildConversationUrl(
                conversationId
            );
        const emptySources = (
            Array.isArray(
                packet?.document_ids
            ) &&
            Array.isArray(
                packet?.document_names
            ) &&
            Array.isArray(
                packet?.sources
            ) &&
            Number(
                packet?.document_count || 0
            ) === 0 &&
            packet.document_ids.length === 0 &&
            packet.document_names.length === 0 &&
            packet.sources.length === 0
        );

        if (
            !conversationId ||
            !conversationUrl ||
            packet?.ok !== true ||
            packet?.packet_type !==
                "solomon_ai_conversation" ||
            packet?.artifact_type !==
                "source_conversation" ||
            packet?.conversation_action !==
                "created" ||
            packet?.status !== "ready" ||
            !emptySources
        ) {
            return "";
        }

        try {
            const url = new URL(
                conversationUrl,
                window.location.origin
            );

            return (
                url.origin ===
                    window.location.origin &&
                url.pathname ===
                    expectedPath &&
                !url.search &&
                !url.hash
            )
                ? url.pathname
                : "";
        } catch (error) {
            return "";
        }
    }

    async function createNewConversation(
        elements
    ) {
        const button =
            elements?.newChat;
        const endpoint = cleanValue(
            elements?.workspace?.getAttribute(
                "data-solomon-ai-new-conversation-endpoint"
            )
        );

        if (
            !button ||
            button.disabled ||
            !endpoint
        ) {
            return false;
        }

        if (isPending(elements)) {
            setNewChatStatus(
                elements,
                "Wait for the current response to finish before starting a new chat."
            );

            return false;
        }

        if (
            isHistoryManagementPending(
                elements
            )
        ) {
            setNewChatStatus(
                elements,
                "Wait for the conversation update to finish before starting a new chat."
            );

            return false;
        }

        closeHistoryMenus(elements);
        closeRenameEditor(
            elements,
            {
                restoreFocus: false
            }
        );

        button.disabled = true;
        button.setAttribute(
            "aria-busy",
            "true"
        );
        setNewChatStatus(
            elements,
            "Starting a new chat."
        );

        let transitioning = false;

        try {
            const response = await fetch(
                endpoint,
                {
                    method: "POST",
                    credentials: "same-origin",
                    headers: {
                        "Accept":
                            "application/json",
                        "X-Requested-With":
                            "XMLHttpRequest"
                    }
                }
            );
            const packet =
                await readJsonResponse(
                    response
                );

            if (
                !response.ok ||
                packet?.ok === false
            ) {
                throw new Error(
                    cleanValue(
                        packet?.user_output ||
                        packet?.error
                    ) ||
                    "A new SolomonAI chat could not be created."
                );
            }

            const conversationUrl =
                getNewConversationUrl(
                    packet
                );

            if (!conversationUrl) {
                throw new Error(
                    "The server returned an invalid new-chat contract."
                );
            }

            setNewChatStatus(
                elements,
                "New chat created."
            );

            transitioning = true;

            const transitioned =
                await loadSolomonAIWorkspace(
                    conversationUrl,
                    {
                        push: true,
                        launchMode: "solomon_ai_new_conversation"
                    }
                );

            if (!transitioned) {
                transitioning = false;

                throw new Error(
                    "The new SolomonAI chat was created, but it could not be opened."
                );
            }

            return true;
        } catch (error) {
            setNewChatStatus(
                elements,
                cleanValue(
                    error?.message
                ) ||
                "A new SolomonAI chat could not be created."
            );

            return false;
        } finally {
            if (
                !transitioning &&
                document.contains(button)
            ) {
                button.disabled = false;
                button.removeAttribute(
                    "aria-busy"
                );
            }
        }
    }

    function bindNewChat(elements) {
        const button =
            elements?.newChat;

        if (
            !button ||
            button.getAttribute(
                "data-solomon-ai-new-chat-navigation-bound"
            ) === "true"
        ) {
            return;
        }

        button.setAttribute(
            "data-solomon-ai-new-chat-navigation-bound",
            "true"
        );

        button.addEventListener(
            "click",
            function (event) {
                event.preventDefault();

                void createNewConversation(
                    elements
                );
            }
        );
    }

    function redirectToDocuments() {
        void loadRightPaneRoute(
            constants.DOCUMENTS_URL,
            constants.DOCUMENTS_MODULE_ID,
            {
                push: true,
                launchMode: "solomon_ai_workspace_close"
            }
        );
    }

    function bindWorkspaceClose(
        elements
    ) {
        const closeControl =
            elements?.pageClose;

        if (
            !closeControl ||
            closeControl.getAttribute(
                "data-solomon-ai-page-close-navigation-bound"
            ) === "true"
        ) {
            return;
        }

        closeControl.setAttribute(
            "data-solomon-ai-page-close-navigation-bound",
            "true"
        );

        closeControl.addEventListener(
            "click",
            function (event) {
                if (
                    event.altKey ||
                    event.ctrlKey ||
                    event.metaKey ||
                    event.shiftKey
                ) {
                    return;
                }

                event.preventDefault();

                closeHistoryMenus(elements);
                closeRenameEditor(
                    elements,
                    {
                        restoreFocus: false
                    }
                );
                redirectToDocuments();
            }
        );
    }

    function initialize(elements) {
        if (!elements?.workspace) {
            return false;
        }

        currentElements = elements;

        bindDocumentEvents();
        bindWorkspaceClose(elements);
        bindHistory(elements);
        bindRenameEditors(elements);
        bindNewChat(elements);

        return true;
    }

    modules.registerModule(
        "conversation_navigation",
        {
            bindHistory,
            bindNewChat,
            bindRenameEditors,
            bindWorkspaceClose,
            buildConversationUrl,
            closeHistoryMenus,
            createNewConversation,
            deleteConversation,
            getConversationId,
            getHistoryConversationId,
            getHistoryConversationTitle,
            getHistoryRowByConversationId,
            initialize,
            loadSolomonAIWorkspace,
            navigateToConversation,
            openHistoryItem,
            openHistoryMenu,
            openRenameEditor,
            redirectToDocuments,
            renameManagedConversation
        }
    );
})(window, document);