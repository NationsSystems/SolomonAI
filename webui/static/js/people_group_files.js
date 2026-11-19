/* -------------------------------------------------------------------
   FILE: people_group_files.js
   DIRECTORY: webui/static/js/
   -------------------------------------------------------------------
   Client transport for canonical explicit Group file sharing.

   Authority remains server-side in canonical /people group routes. This
   script only loads authorized data, renders controls, submits user actions,
   and refreshes state.
------------------------------------------------------------------- */

(function () {
    "use strict";

    const registry = window.NationsPeopleGroupFiles =
        window.NationsPeopleGroupFiles || {};

    const ENDPOINTS = {
        data: function (groupId) {
            return `/people/groups/${encodeURIComponent(String(groupId || ""))}/files/data`;
        },
        add: function (groupId) {
            return `/people/groups/${encodeURIComponent(String(groupId || ""))}/files`;
        },
        item: function (groupId, grantId) {
            return `/people/groups/${encodeURIComponent(String(groupId || ""))}/files/${encodeURIComponent(String(grantId || ""))}`;
        }
    };

    function cleanText(value) {
        return String(value || "").trim();
    }

    function createElement(tagName, className, text) {
        const element = document.createElement(tagName);

        if (className) {
            element.className = className;
        }

        if (typeof text === "string") {
            element.textContent = text;
        }

        return element;
    }

    function clearElement(element) {
        while (element.firstChild) {
            element.removeChild(element.firstChild);
        }
    }

    function resolveGroupFilesPage(root) {
        const scope = root && typeof root.querySelector === "function"
            ? root
            : document;

        if (
            scope instanceof Element &&
            scope.matches("[data-people-group-files-page]")
        ) {
            return scope;
        }

        return scope.querySelector("[data-people-group-files-page]");
    }

    function resolveGroupFilesElements(root) {
        const page = resolveGroupFilesPage(root);

        if (!page) {
            return null;
        }

        return {
            page: page,
            ownedFilesList: page.querySelector("[data-people-owned-files-list]"),
            groupFilesList: page.querySelector("[data-people-group-files-list]"),
            refreshButton: page.querySelector("[data-people-group-files-refresh]"),
            statusBox: page.querySelector("[data-people-group-files-status]")
        };
    }

    function hasRequiredGroupFilesElements(elements) {
        return Boolean(
            elements &&
            elements.page &&
            elements.ownedFilesList &&
            elements.groupFilesList &&
            elements.refreshButton &&
            elements.statusBox
        );
    }

    function resolveGroupIdFromPathname(pathname) {
        const cleanPath = String(pathname || "").trim();
        const match = cleanPath.match(/^\/people\/groups\/([^/]+)\/files(?:\/)?$/i);

        return match ? decodeURIComponent(match[1]) : "";
    }

    function resolveGroupId(page, payload) {
        const pageGroupId = cleanText(
            page?.getAttribute("data-people-group-id") ||
            page?.getAttribute("data-group-id")
        );

        if (pageGroupId) {
            return pageGroupId;
        }

        const payloadGroup = payload && typeof payload.group === "object"
            ? payload.group
            : {};

        const payloadGroupId = cleanText(
            payloadGroup?.group_id ||
            payloadGroup?.id ||
            payload?.group_id ||
            ""
        );

        if (payloadGroupId) {
            return payloadGroupId;
        }

        return resolveGroupIdFromPathname(window.location.pathname);
    }

    function setStatus(statusBox, message, mode) {
        statusBox.textContent = cleanText(message);
        statusBox.classList.remove("is-success", "is-error");

        if (mode === "success") {
            statusBox.classList.add("is-success");
        }

        if (mode === "error") {
            statusBox.classList.add("is-error");
        }
    }

    function setLoadingState(state, refreshButton, nextLoading) {
        state.isLoading = Boolean(nextLoading);
        refreshButton.disabled = state.isLoading;
        refreshButton.textContent = state.isLoading ? "Refreshing..." : "Refresh";
    }

    function formatBytes(value) {
        const bytes = Number(value || 0);

        if (!Number.isFinite(bytes) || bytes <= 0) {
            return "Unknown size";
        }

        if (bytes < 1024) {
            return `${bytes} B`;
        }

        if (bytes < 1024 * 1024) {
            return `${(bytes / 1024).toFixed(1)} KB`;
        }

        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    function createPill(text, modifier) {
        const pill = createElement("span", "people-group-files-pill", text);

        if (modifier) {
            pill.classList.add(modifier);
        }

        return pill;
    }

    function createEmpty(message) {
        return createElement("div", "people-group-files-empty", message);
    }

    function createError(message) {
        return createElement("div", "people-group-files-error", message);
    }

    function normalizePermission(value) {
        const cleanValue = cleanText(value).toLowerCase();

        return cleanValue === "edit" ? "edit" : "view";
    }

    function createPermissionSelect(selectedValue) {
        const select = createElement("select", "people-group-files-select");
        const normalized = normalizePermission(selectedValue);
        const options = [
            { value: "view", label: "Viewer" },
            { value: "edit", label: "Editor" }
        ];

        options.forEach(function (permission) {
            const option = document.createElement("option");
            option.value = permission.value;
            option.textContent = permission.label;
            option.selected = permission.value === normalized;
            select.appendChild(option);
        });

        return select;
    }

    function createToggle(options) {
        const row = createElement("div", "people-group-files-toggle-row");
        const labelBlock = createElement("div", "");
        const title = createElement("span", "people-group-files-toggle-label", options.title);
        const copy = createElement("span", "people-group-files-toggle-copy", options.copy);
        const toggleLabel = createElement("label", "people-group-files-toggle");
        const checkbox = document.createElement("input");
        const toggleText = document.createElement("span");

        checkbox.type = "checkbox";
        checkbox.checked = Boolean(options.checked);

        toggleText.textContent = options.checked ? "Enabled" : "Disabled";

        checkbox.addEventListener("change", function () {
            toggleText.textContent = checkbox.checked ? "Enabled" : "Disabled";
        });

        labelBlock.appendChild(title);
        labelBlock.appendChild(copy);

        toggleLabel.appendChild(checkbox);
        toggleLabel.appendChild(toggleText);

        row.appendChild(labelBlock);
        row.appendChild(toggleLabel);

        return {
            row: row,
            input: checkbox
        };
    }

    function createFileHeader(file) {
        const header = createElement("div", "people-group-files-file-card-header");
        const content = createElement("div", "");
        const title = createElement(
            "h3",
            "people-group-files-file-title",
            cleanText(file.original_name) || cleanText(file.document_id) || "Untitled file"
        );
        const meta = createElement("div", "people-group-files-file-meta");
        const actions = createElement("div", "people-group-files-card-actions");

        meta.appendChild(
            createPill(
                cleanText(file.extension) || "file",
                ""
            )
        );
        meta.appendChild(
            createPill(
                formatBytes(file.size_bytes),
                ""
            )
        );

        if (file.reader_url) {
            const readerLink = createElement("a", "people-group-files-action", "View");
            readerLink.href = file.reader_url;
            readerLink.target = "_blank";
            readerLink.rel = "noopener noreferrer";
            actions.appendChild(readerLink);
        }

        content.appendChild(title);
        content.appendChild(meta);

        header.appendChild(content);
        header.appendChild(actions);

        return {
            header: header,
            actions: actions,
            meta: meta
        };
    }

    function createOwnedFileCard(file, handlers) {
        const card = createElement("article", "people-group-files-file-card");
        const headerParts = createFileHeader(file);
        const controls = createElement("div", "people-group-files-controls");
        const permissionSelect = createPermissionSelect("view");
        const downloadToggle = createToggle({
            title: "Download",
            copy: "Allow Group members with this share to download the source file.",
            checked: true
        });
        const permissionRow = createElement("div", "people-group-files-toggle-row");
        const permissionLabel = createElement("div", "");
        const permissionTitle = createElement("span", "people-group-files-toggle-label", "Permission");
        const permissionCopy = createElement("span", "people-group-files-toggle-copy", "Viewer can read. Editor can also modify content where supported.");
        const actions = createElement("div", "people-group-files-card-actions");
        const addButton = createElement("button", "people-group-files-action", "Share with Group");
        const dragShareAvailable = !file.in_group_library;

        addButton.type = "button";
        card.setAttribute("data-document-drag-document-id", cleanText(file.document_id));
        card.setAttribute("data-document-drag-file-id", cleanText(file.file_id));
        card.setAttribute(
            "data-document-drag-name",
            cleanText(file.original_name) || cleanText(file.document_id) || "Untitled file"
        );
        card.setAttribute("data-document-drag-can-share", dragShareAvailable ? "true" : "false");
        card.setAttribute("data-document-share-drag-source", dragShareAvailable ? "true" : "false");
        card.setAttribute("draggable", dragShareAvailable ? "true" : "false");
        permissionSelect.setAttribute("data-document-share-permission", "true");
        downloadToggle.input.setAttribute("data-document-share-download", "true");

        if (file.in_group_library) {
            addButton.textContent = "Already shared";
            addButton.disabled = true;
            headerParts.meta.appendChild(
                createPill("Shared with Group", "is-enabled")
            );
        }

        permissionLabel.appendChild(permissionTitle);
        permissionLabel.appendChild(permissionCopy);
        permissionRow.appendChild(permissionLabel);
        permissionRow.appendChild(permissionSelect);

        addButton.addEventListener("click", function () {
            handlers.addGroupFile({
                fileId: file.file_id,
                documentId: file.document_id,
                fileName: file.original_name || file.document_id,
                permission: permissionSelect.value,
                allowDownload: downloadToggle.input.checked,
                button: addButton
            });
        });

        controls.appendChild(permissionRow);
        controls.appendChild(downloadToggle.row);
        actions.appendChild(addButton);
        card.appendChild(headerParts.header);
        card.appendChild(controls);
        card.appendChild(actions);

        return card;
    }

    function createGroupFileCard(file, handlers) {
        const card = createElement("article", "people-group-files-file-card");
        const headerParts = createFileHeader(file);
        const controls = createElement("div", "people-group-files-controls");
        const permissionSelect = createPermissionSelect(file.permission);
        const downloadToggle = createToggle({
            title: "Download",
            copy: "Allow Group members with this share to download the source file.",
            checked: file.allow_download !== false
        });
        const permissionRow = createElement("div", "people-group-files-toggle-row");
        const permissionLabel = createElement("div", "");
        const permissionTitle = createElement("span", "people-group-files-toggle-label", "Permission");
        const permissionCopy = createElement("span", "people-group-files-toggle-copy", "Change the Group grant between Viewer and Editor.");
        const actions = createElement("div", "people-group-files-card-actions");
        const saveButton = createElement("button", "people-group-files-action", "Update Share");
        const removeButton = createElement("button", "people-group-files-danger", "Unshare");

        saveButton.type = "button";
        removeButton.type = "button";

        headerParts.meta.appendChild(
            createPill(
                normalizePermission(file.permission) === "edit" ? "Editor" : "Viewer",
                "is-enabled"
            )
        );
        headerParts.meta.appendChild(
            createPill(
                file.allow_download === false ? "Download blocked" : "Download allowed",
                file.allow_download === false ? "is-disabled" : "is-enabled"
            )
        );

        permissionLabel.appendChild(permissionTitle);
        permissionLabel.appendChild(permissionCopy);
        permissionRow.appendChild(permissionLabel);
        permissionRow.appendChild(permissionSelect);

        saveButton.addEventListener("click", function () {
            handlers.updateGroupFile({
                grantId: file.grant_id,
                permission: permissionSelect.value,
                allowDownload: downloadToggle.input.checked,
                button: saveButton
            });
        });

        removeButton.addEventListener("click", function () {
            handlers.removeGroupFile({
                grantId: file.grant_id,
                fileName: file.original_name,
                button: removeButton
            });
        });

        controls.appendChild(permissionRow);
        controls.appendChild(downloadToggle.row);
        actions.appendChild(saveButton);
        actions.appendChild(removeButton);
        card.appendChild(headerParts.header);
        card.appendChild(controls);
        card.appendChild(actions);

        return card;
    }

    function renderOwnedFiles(ownedFilesList, files, handlers) {
        clearElement(ownedFilesList);

        if (!Array.isArray(files) || files.length === 0) {
            ownedFilesList.appendChild(
                createEmpty("No owned files are available. Upload files in My Files first, then return here.")
            );
            return;
        }

        files.forEach(function (file) {
            ownedFilesList.appendChild(
                createOwnedFileCard(file, handlers)
            );
        });
    }

    function renderGroupFiles(groupFilesList, files, handlers) {
        clearElement(groupFilesList);

        if (!Array.isArray(files) || files.length === 0) {
            groupFilesList.appendChild(
                createEmpty("No files have been shared with this Group yet.")
            );
            return;
        }

        files.forEach(function (file) {
            groupFilesList.appendChild(
                createGroupFileCard(file, handlers)
            );
        });
    }

    async function fetchJson(url, options) {
        const response = await fetch(url, {
            credentials: "same-origin",
            ...(options || {})
        });

        const payload = await response.json().catch(function () {
            return {};
        });

        if (!response.ok || !payload.ok) {
            const message = payload.error || "The request could not be completed.";
            throw new Error(message);
        }

        return payload;
    }

    function initializePeopleGroupFilesPage(root) {
        const elements = resolveGroupFilesElements(root);

        if (!hasRequiredGroupFilesElements(elements)) {
            return false;
        }

        if (
            elements.page.getAttribute(
                "data-people-group-files-bound"
            ) === "true"
        ) {
            return true;
        }

        elements.page.setAttribute(
            "data-people-group-files-bound",
            "true"
        );

        const page = elements.page;
        const ownedFilesList = elements.ownedFilesList;
        const groupFilesList = elements.groupFilesList;
        const refreshButton = elements.refreshButton;
        const statusBox = elements.statusBox;
        const state = {
            isLoading: false,
            groupId: resolveGroupId(page),
            groupName: cleanText(page.getAttribute("data-people-group-name")) || "Group"
        };

        function requireGroupId() {
            state.groupId = cleanText(
                state.groupId ||
                resolveGroupId(page)
            );

            if (state.groupId) {
                return state.groupId;
            }

            throw new Error(
                "Group context is not ready. Open this screen from a valid group."
            );
        }

        async function loadGroupFiles() {
            if (state.isLoading) {
                return;
            }

            let groupId = "";

            try {
                groupId = requireGroupId();
            } catch (error) {
                clearElement(ownedFilesList);
                clearElement(groupFilesList);

                ownedFilesList.appendChild(
                    createError(error.message)
                );
                groupFilesList.appendChild(
                    createError(error.message)
                );
                setStatus(statusBox, error.message, "error");
                return;
            }

            setLoadingState(state, refreshButton, true);
            setStatus(statusBox, "Loading Group shares...");

            try {
                const payload = await fetchJson(ENDPOINTS.data(groupId));
                state.groupId = resolveGroupId(page, payload) || groupId;
                state.groupName = cleanText(payload?.group?.name) || state.groupName || "Group";

                const handlers = {
                    addGroupFile,
                    updateGroupFile,
                    removeGroupFile
                };

                renderOwnedFiles(ownedFilesList, payload.owned_files || [], handlers);
                renderGroupFiles(
                    groupFilesList,
                    payload.group_files || [],
                    handlers
                );
                setStatus(statusBox, "Group shares loaded.", "success");
            } catch (error) {
                clearElement(ownedFilesList);
                clearElement(groupFilesList);

                ownedFilesList.appendChild(
                    createError(error.message || "Owned files could not be loaded.")
                );
                groupFilesList.appendChild(
                    createError(error.message || "Group files could not be loaded.")
                );

                setStatus(
                    statusBox,
                    error.message || "Group file controls could not be loaded.",
                    "error"
                );
            } finally {
                setLoadingState(state, refreshButton, false);
            }
        }

        async function addGroupFile(options) {
            let groupId = "";

            try {
                groupId = requireGroupId();
            } catch (error) {
                setStatus(statusBox, error.message, "error");
                return;
            }

            const Share = window.SolomonWorkspaceDocumentShare;
            if (!Share || typeof Share.open !== "function") {
                setStatus(statusBox, "The Share workspace is unavailable.", "error");
                return;
            }

            await Share.open({
                documents: [{
                    documentId: cleanText(options?.documentId),
                    name: cleanText(options?.fileName) || cleanText(options?.documentId) || "File"
                }],
                principalType: "group",
                principalId: groupId,
                permission: normalizePermission(options?.permission),
                allowDownload: options?.allowDownload !== false
            });
        }

        function handleGroupShareDrop(event) {
            const resources = Array.isArray(event?.detail?.resources)
                ? event.detail.resources
                : [];

            if (!resources.length) {
                return;
            }

            const resource = resources[0];
            const documentId = cleanText(resource?.documentId);
            const card = documentId
                ? Array.from(
                    ownedFilesList.querySelectorAll("[data-document-drag-document-id]")
                ).find(function (candidate) {
                    return cleanText(
                        candidate.getAttribute("data-document-drag-document-id")
                    ) === documentId;
                }) || null
                : null;

            if (!card || card.getAttribute("data-document-drag-can-share") !== "true") {
                setStatus(
                    statusBox,
                    "Only an active file you own can be shared with this Group.",
                    "error"
                );
                return;
            }

            const permissionSelect = card.querySelector("[data-document-share-permission]");
            const downloadInput = card.querySelector("[data-document-share-download]");

            addGroupFile({
                fileId: cleanText(card.getAttribute("data-document-drag-file-id")),
                documentId: documentId,
                fileName: cleanText(card.getAttribute("data-document-drag-name")) || resource?.name,
                permission: permissionSelect?.value || "view",
                allowDownload: downloadInput?.checked !== false
            });
        }

        async function updateGroupFile(options) {
            let groupId = "";

            try {
                groupId = requireGroupId();
            } catch (error) {
                setStatus(statusBox, error.message, "error");
                return;
            }

            const button = options.button;
            const originalText = button.textContent;

            button.disabled = true;
            button.textContent = "Saving...";
            setStatus(statusBox, "Updating Group share...");

            try {
                await fetchJson(ENDPOINTS.item(groupId, options.grantId), {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        permission: options.permission,
                        allow_download: options.allowDownload
                    })
                });

                setStatus(statusBox, "Group share updated.", "success");
                await loadGroupFiles();
            } catch (error) {
                setStatus(
                    statusBox,
                    error.message || "The Group share could not be updated.",
                    "error"
                );
                button.disabled = false;
                button.textContent = originalText;
            }
        }

        async function removeGroupFile(options) {
            let groupId = "";

            try {
                groupId = requireGroupId();
            } catch (error) {
                setStatus(statusBox, error.message, "error");
                return;
            }

            const fileName = cleanText(options.fileName) || "this file";
            const confirmed = window.confirm(
                `Unshare ${fileName} from this Group?`
            );

            if (!confirmed) {
                return;
            }

            const button = options.button;
            const originalText = button.textContent;

            button.disabled = true;
            button.textContent = "Removing...";
            setStatus(statusBox, "Removing Group share...");

            try {
                await fetchJson(ENDPOINTS.item(groupId, options.grantId), {
                    method: "DELETE"
                });

                setStatus(statusBox, "File unshared from Group.", "success");
                await loadGroupFiles();
            } catch (error) {
                setStatus(
                    statusBox,
                    error.message || "The file could not be unshared from the Group.",
                    "error"
                );
                button.disabled = false;
                button.textContent = originalText;
            }
        }

        refreshButton.addEventListener("click", loadGroupFiles);
        page.addEventListener(
            "solomon:workspace-group-share-drop-requested",
            handleGroupShareDrop
        );
        document.addEventListener(
            "solomon:workspace-share-updated",
            loadGroupFiles
        );

        loadGroupFiles();

        return true;
    }

    function initializeCurrentPeopleGroupFilesPage() {
        return initializePeopleGroupFilesPage(document);
    }

    registry.initialize = initializePeopleGroupFilesPage;
    registry.initializeCurrent = initializeCurrentPeopleGroupFilesPage;

    if (!registry.lifecycleBound) {
        registry.lifecycleBound = true;

        document.addEventListener(
            "solomon:workspace-loaded",
            function (event) {
                initializePeopleGroupFilesPage(
                    event?.detail?.mount || document
                );
            }
        );
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initializeCurrentPeopleGroupFilesPage,
            { once: true }
        );
    } else {
        initializeCurrentPeopleGroupFilesPage();
    }
}());