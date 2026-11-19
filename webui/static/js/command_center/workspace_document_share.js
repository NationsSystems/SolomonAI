/* -------------------------------------------------------------------
   FILE: workspace_document_share.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentShare";
    const OPTIONS_ENDPOINT = "/people/shares/files/options";
    const SHARE_ENDPOINT = "/people/shares/files";
    const ROW_SELECTOR = ".workspace-document-file[data-document-id]";
    const RAIL_SELECTOR = "[data-document-selection-rail]";

    if (window[API_NAME]) {
        return;
    }

    let dialog = null;
    let state = null;

    function clean(value) {
        return String(value || "").trim();
    }

    function bool(value) {
        return value === true || value === "true" || value === 1 || value === "1";
    }

    function create(tag, className, text) {
        const node = document.createElement(tag);
        if (className) {
            node.className = className;
        }
        if (typeof text === "string") {
            node.textContent = text;
        }
        return node;
    }

    async function fetchJson(url, options) {
        const response = await fetch(url, Object.assign({
            credentials: "same-origin",
            headers: {
                "Accept": "application/json"
            }
        }, options || {}));
        let payload = null;

        try {
            payload = await response.json();
        } catch (_error) {
            payload = null;
        }

        if (!response.ok || !payload || payload.ok === false) {
            throw new Error(
                clean(payload?.error || payload?.message) ||
                `Share request failed (${response.status}).`
            );
        }

        return payload;
    }

    function normalizeDocuments(documents, documentIds, documentNames) {
        const source = Array.isArray(documents) ? documents : [];
        const ids = Array.isArray(documentIds) ? documentIds : [];
        const names = Array.isArray(documentNames) ? documentNames : [];
        const values = [];
        const seen = new Set();

        source.forEach(function (item) {
            const id = clean(
                typeof item === "string"
                    ? item
                    : (item?.documentId || item?.document_id || item?.random_name || item?.fileId || item?.file_id)
            );
            if (!id || seen.has(id)) {
                return;
            }
            seen.add(id);
            values.push({
                documentId: id,
                name: clean(
                    typeof item === "string"
                        ? ""
                        : (item?.name || item?.original_name || item?.title)
                ) || id
            });
        });

        ids.forEach(function (value, index) {
            const id = clean(value);
            if (!id || seen.has(id)) {
                return;
            }
            seen.add(id);
            values.push({
                documentId: id,
                name: clean(names[index]) || id
            });
        });

        return values;
    }

    function getDocumentFromTrigger(trigger) {
        const documentId = clean(
            trigger?.getAttribute("data-document-id") ||
            trigger?.getAttribute("data-document-share-document-id") ||
            trigger?.closest?.(ROW_SELECTOR)?.getAttribute("data-document-id")
        );
        const row = documentId && window.CSS?.escape
            ? document.querySelector(`${ROW_SELECTOR}[data-document-id="${CSS.escape(documentId)}"]`)
            : null;
        const name = clean(
            trigger?.getAttribute("data-document-name") ||
            trigger?.getAttribute("data-document-share-document-name") ||
            row?.querySelector(".workspace-document-file-identity strong")?.textContent ||
            row?.getAttribute("data-document-name") ||
            row?.getAttribute("data-original-name")
        );

        return documentId ? { documentId, name: name || documentId } : null;
    }

    function ensureDialog() {
        if (dialog && dialog.isConnected) {
            return dialog;
        }

        const shell = create("div", "workspace-share-shell");
        shell.setAttribute("data-workspace-share-shell", "");
        shell.hidden = true;
        shell.innerHTML = `
            <div class="workspace-share-backdrop" data-workspace-share-close></div>
            <section class="workspace-share-dialog" role="dialog" aria-modal="true" aria-labelledby="workspaceShareTitle">
                <header class="workspace-share-header">
                    <div>
                        <p class="workspace-share-kicker">Access</p>
                        <h2 id="workspaceShareTitle" data-workspace-share-title>Share</h2>
                        <p data-workspace-share-subtitle></p>
                    </div>
                    <button type="button" class="workspace-share-icon-button" data-workspace-share-close aria-label="Close Share">
                        <span class="icon" aria-hidden="true">close</span>
                    </button>
                </header>
                <div class="workspace-share-status" data-workspace-share-status role="status" aria-live="polite" hidden></div>
                <div class="workspace-share-body" data-workspace-share-body></div>
                <footer class="workspace-share-footer">
                    <button type="button" class="workspace-share-button workspace-share-button--secondary" data-workspace-share-close>Cancel</button>
                    <button type="button" class="workspace-share-button workspace-share-button--primary" data-workspace-share-submit>Share</button>
                </footer>
            </section>`;

        document.body.appendChild(shell);
        shell.addEventListener("click", handleDialogClick);
        shell.addEventListener("input", handleDialogInput);
        shell.addEventListener("change", handleDialogChange);
        dialog = shell;
        return dialog;
    }

    function close() {
        if (!dialog) {
            return;
        }
        dialog.hidden = true;
        document.documentElement.classList.remove("workspace-share-open");
        state = null;
    }

    function setStatus(message, mode) {
        const box = dialog?.querySelector("[data-workspace-share-status]");
        if (!box) {
            return;
        }
        box.classList.remove("is-error", "is-success", "is-info");
        const text = clean(message);
        box.textContent = text;
        box.hidden = !text;
        if (text && mode) {
            box.classList.add(`is-${mode}`);
        }
    }

    function setBusy(busy) {
        if (!dialog || !state) {
            return;
        }
        state.busy = Boolean(busy);
        dialog.querySelectorAll("button, input, select").forEach(function (node) {
            if (!node.hasAttribute("data-workspace-share-close")) {
                node.disabled = state.busy;
            }
        });
        const submit = dialog.querySelector("[data-workspace-share-submit]");
        if (submit) {
            submit.textContent = state.busy ? "Sharing..." : getSubmitLabel();
        }
    }

    function getSubmitLabel() {
        if (!state) {
            return "Share";
        }
        const count = state.documents.length;
        if (!count) {
            return "Share";
        }
        return count === 1 ? "Share" : `Share ${count} files`;
    }

    function renderDocumentPicker(container) {
        if (!state.allowFilePicker) {
            return;
        }

        const section = create("section", "workspace-share-section");
        const heading = create("div", "workspace-share-section-heading");
        const title = create("strong", "", "Files");
        const copy = create("span", "", "Choose one or more files you own.");
        const search = create("input", "workspace-share-search");
        const list = create("div", "workspace-share-file-picker");
        const query = clean(state.fileQuery).toLowerCase();

        search.type = "search";
        search.placeholder = "Search My Files";
        search.value = state.fileQuery || "";
        search.setAttribute("data-workspace-share-file-search", "");

        (state.options?.owned_files || []).forEach(function (file) {
            const id = clean(file.document_id || file.random_name || file.file_id);
            const name = clean(file.original_name) || id;
            if (!id || (query && !name.toLowerCase().includes(query))) {
                return;
            }

            const label = create("label", "workspace-share-file-option");
            const input = document.createElement("input");
            const copyBlock = create("span", "workspace-share-option-copy");
            input.type = "checkbox";
            input.setAttribute("data-workspace-share-file-option", id);
            input.checked = state.documents.some(function (doc) {
                return doc.documentId === id;
            });
            copyBlock.append(
                create("strong", "", name),
                create("span", "", clean(file.extension) || "File")
            );
            label.append(input, copyBlock);
            list.appendChild(label);
        });

        if (!list.children.length) {
            list.appendChild(create("p", "workspace-share-empty", "No matching owned files."));
        }

        heading.append(title, copy);
        section.append(heading, search, list);
        container.appendChild(section);
    }

    function getPrincipalKey(type, id) {
        return `${clean(type)}:${clean(id)}`;
    }

    function renderRecipientPicker(container) {
        const section = create("section", "workspace-share-section");
        const heading = create("div", "workspace-share-section-heading");
        const title = create("strong", "", "People or Groups");
        const copy = create("span", "", "Choose who should receive this explicit resource grant.");
        const search = create("input", "workspace-share-search");
        const list = create("div", "workspace-share-principal-list");
        const query = clean(state.recipientQuery).toLowerCase();
        const people = state.options?.people || [];
        const groups = state.options?.groups || [];
        const principals = [
            ...people.map(function (person) {
                return {
                    type: "user",
                    id: person.user_id || person.principal_id,
                    name: clean(person.name) || clean(person.email),
                    detail: clean(person.email),
                    icon: "person"
                };
            }),
            ...groups.map(function (group) {
                return {
                    type: "group",
                    id: group.group_id || group.principal_id,
                    name: clean(group.name) || "Group",
                    detail: "Group",
                    icon: "groups"
                };
            })
        ];

        search.type = "search";
        search.placeholder = "Search people or groups";
        search.value = state.recipientQuery || "";
        search.setAttribute("data-workspace-share-recipient-search", "");

        principals.forEach(function (principal) {
            const searchable = `${principal.name} ${principal.detail}`.toLowerCase();
            if (query && !searchable.includes(query)) {
                return;
            }
            const key = getPrincipalKey(principal.type, principal.id);
            const button = create("button", "workspace-share-principal");
            button.type = "button";
            button.setAttribute("data-workspace-share-principal", key);
            button.classList.toggle("is-selected", state.principalKey === key);
            button.append(
                create("span", "icon workspace-share-principal-icon", principal.icon),
                (function () {
                    const copyBlock = create("span", "workspace-share-option-copy");
                    copyBlock.append(
                        create("strong", "", principal.name),
                        create("span", "", principal.detail)
                    );
                    return copyBlock;
                })(),
                create("span", "icon workspace-share-principal-check", state.principalKey === key ? "check_circle" : "radio_button_unchecked")
            );
            list.appendChild(button);
        });

        if (!list.children.length) {
            list.appendChild(create(
                "p",
                "workspace-share-empty",
                state.options?.external_guest_enabled
                    ? "No matching person or Group."
                    : "No matching internal person or Group. External Guest sharing is not enabled in this deployment."
            ));
        }

        heading.append(title, copy);
        section.append(heading, search, list);
        container.appendChild(section);
    }

    function renderPermissionControls(container) {
        const section = create("section", "workspace-share-section workspace-share-permission-section");
        const permissionField = create("label", "workspace-share-field");
        const permissionLabel = create("span", "", "Permission");
        const permission = document.createElement("select");
        const downloadField = create("label", "workspace-share-download");
        const download = document.createElement("input");
        const downloadCopy = create("span", "workspace-share-option-copy");

        permission.setAttribute("data-workspace-share-permission", "");
        [
            ["view", "Viewer"],
            ["edit", "Editor"]
        ].forEach(function (item) {
            const option = document.createElement("option");
            option.value = item[0];
            option.textContent = item[1];
            option.selected = state.permission === item[0];
            permission.appendChild(option);
        });

        download.type = "checkbox";
        download.checked = state.allowDownload;
        download.setAttribute("data-workspace-share-download", "");
        downloadCopy.append(
            create("strong", "", "Allow download"),
            create("span", "", "Viewer access may be kept inside Solomon by turning this off.")
        );

        permissionField.append(permissionLabel, permission);
        downloadField.append(download, downloadCopy);
        section.append(permissionField, downloadField);
        container.appendChild(section);
    }

    function renderAccessList(container) {
        if (state.mode !== "manage" || state.documents.length !== 1) {
            return;
        }

        const section = create("section", "workspace-share-section workspace-share-access-section");
        const heading = create("div", "workspace-share-section-heading");
        const title = create("strong", "", "Current access");
        const copy = create("span", "", "Direct User and Group grants remain independent.");
        const list = create("div", "workspace-share-access-list");

        (state.access || []).forEach(function (grant) {
            const row = create("article", "workspace-share-access-row");
            const identity = create("div", "workspace-share-access-identity");
            const controls = create("div", "workspace-share-access-controls");
            const select = document.createElement("select");
            const downloadLabel = create("label", "workspace-share-access-download");
            const download = document.createElement("input");
            const save = create("button", "workspace-share-mini-button", "Save");
            const revoke = create("button", "workspace-share-mini-button workspace-share-mini-button--danger", "Remove");
            const principalType = clean(grant.principal_type);
            const principalId = clean(grant.principal_id);

            identity.append(
                create("span", "icon", principalType === "group" ? "groups" : "person"),
                (function () {
                    const copyBlock = create("span", "workspace-share-option-copy");
                    copyBlock.append(
                        create("strong", "", clean(grant.principal_name) || clean(grant.principal_email) || "Recipient"),
                        create("span", "", principalType === "group" ? "Group" : clean(grant.principal_email) || "Person")
                    );
                    return copyBlock;
                })()
            );

            [["view", "Viewer"], ["edit", "Editor"]].forEach(function (item) {
                const option = document.createElement("option");
                option.value = item[0];
                option.textContent = item[1];
                option.selected = clean(grant.permission).toLowerCase() === item[0];
                select.appendChild(option);
            });
            select.setAttribute("aria-label", "Permission");

            download.type = "checkbox";
            download.checked = grant.allow_download !== false;
            downloadLabel.append(download, create("span", "", "Download"));

            save.type = "button";
            save.setAttribute("data-workspace-share-access-save", "");
            save.setAttribute("data-principal-type", principalType);
            save.setAttribute("data-principal-id", principalId);
            revoke.type = "button";
            revoke.setAttribute("data-workspace-share-access-revoke", "");
            revoke.setAttribute("data-principal-type", principalType);
            revoke.setAttribute("data-principal-id", principalId);

            controls.append(select, downloadLabel, save, revoke);
            row.append(identity, controls);
            list.appendChild(row);
        });

        if (!list.children.length) {
            list.appendChild(create("p", "workspace-share-empty", "Only you currently have access."));
        }

        heading.append(title, copy);
        section.append(heading, list);
        container.appendChild(section);
    }

    function render() {
        const root = ensureDialog();
        const body = root.querySelector("[data-workspace-share-body]");
        const title = root.querySelector("[data-workspace-share-title]");
        const subtitle = root.querySelector("[data-workspace-share-subtitle]");
        const submit = root.querySelector("[data-workspace-share-submit]");

        body.replaceChildren();
        setStatus("");
        title.textContent = state.mode === "manage" ? "Manage Access" : "Share";
        subtitle.textContent = state.documents.length === 1
            ? state.documents[0].name
            : state.documents.length > 1
                ? `${state.documents.length} selected files`
                : "Choose files and the people or Groups who should receive access.";

        renderDocumentPicker(body);
        renderAccessList(body);
        renderRecipientPicker(body);
        renderPermissionControls(body);

        submit.textContent = getSubmitLabel();
        submit.disabled = !state.documents.length || !state.principalKey || state.busy;
    }

    async function loadOptions() {
        const url = state.allowFilePicker
            ? `${OPTIONS_ENDPOINT}?include_files=1`
            : OPTIONS_ENDPOINT;
        const payload = await fetchJson(url);
        state.options = payload;
    }

    async function loadAccess() {
        if (state.mode !== "manage" || state.documents.length !== 1) {
            state.access = [];
            return;
        }
        const id = state.documents[0].documentId;
        const payload = await fetchJson(`/people/shares/files/${encodeURIComponent(id)}/access`);
        state.access = Array.isArray(payload.access) ? payload.access : [];
    }

    function preselectPrincipal(options) {
        const type = clean(options?.principalType || options?.preselectedPrincipalType);
        const id = clean(options?.principalId || options?.preselectedPrincipalId);
        state.principalKey = type && id ? getPrincipalKey(type, id) : "";
    }

    async function open(options) {
        const cleanOptions = options || {};
        ensureDialog();
        state = {
            mode: clean(cleanOptions.mode).toLowerCase() === "manage" ? "manage" : "share",
            documents: normalizeDocuments(
                cleanOptions.documents,
                cleanOptions.documentIds,
                cleanOptions.documentNames
            ),
            allowFilePicker: cleanOptions.allowFilePicker === true || (
                !cleanOptions.documents && !cleanOptions.documentIds
            ),
            permission: clean(cleanOptions.permission).toLowerCase() === "edit" ? "edit" : "view",
            allowDownload: cleanOptions.allowDownload !== false,
            recipientQuery: "",
            fileQuery: "",
            principalKey: "",
            options: null,
            access: [],
            busy: false
        };
        preselectPrincipal(cleanOptions);

        dialog.hidden = false;
        document.documentElement.classList.add("workspace-share-open");
        setStatus("Loading share options...", "info");

        try {
            await Promise.all([loadOptions(), loadAccess()]);
            render();
            dialog.querySelector("[data-workspace-share-recipient-search]")?.focus();
        } catch (error) {
            setStatus(error.message || "Share options could not be loaded.", "error");
            const submit = dialog.querySelector("[data-workspace-share-submit]");
            if (submit) {
                submit.disabled = true;
            }
        }
    }

    async function submitShare() {
        if (!state || state.busy || !state.documents.length || !state.principalKey) {
            return;
        }
        const separator = state.principalKey.indexOf(":");
        const principalType = state.principalKey.slice(0, separator);
        const principalId = state.principalKey.slice(separator + 1);

        setBusy(true);
        setStatus("Creating explicit share grant...", "info");
        try {
            const payload = await fetchJson(SHARE_ENDPOINT, {
                method: "POST",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    document_ids: state.documents.map(function (doc) { return doc.documentId; }),
                    principal_type: principalType,
                    principal_id: principalId,
                    permission: state.permission,
                    allow_download: state.allowDownload
                })
            });
            setStatus(payload.message || "Access granted.", "success");
            document.dispatchEvent(new CustomEvent("solomon:workspace-share-updated", {
                detail: {
                    documentIds: state.documents.map(function (doc) { return doc.documentId; }),
                    principalType,
                    principalId
                }
            }));

            if (state.mode === "manage") {
                await loadAccess();
                state.principalKey = "";
                render();
                setStatus(payload.message || "Access granted.", "success");
            } else {
                window.setTimeout(close, 450);
            }
        } catch (error) {
            setStatus(error.message || "The file could not be shared.", "error");
        } finally {
            if (state) {
                setBusy(false);
                if (state.mode === "manage") {
                    render();
                }
            }
        }
    }

    async function updateAccess(button) {
        if (!state || state.documents.length !== 1) {
            return;
        }
        const row = button.closest(".workspace-share-access-row");
        const permission = row?.querySelector("select")?.value || "view";
        const allowDownload = row?.querySelector("input[type='checkbox']")?.checked !== false;
        const principalType = clean(button.getAttribute("data-principal-type"));
        const principalId = clean(button.getAttribute("data-principal-id"));

        setBusy(true);
        setStatus("Updating access...", "info");
        try {
            await fetchJson(SHARE_ENDPOINT, {
                method: "POST",
                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json"
                },
                body: JSON.stringify({
                    document_ids: [state.documents[0].documentId],
                    principal_type: principalType,
                    principal_id: principalId,
                    permission,
                    allow_download: allowDownload
                })
            });
            await loadAccess();
            render();
            setStatus("Access updated.", "success");
            document.dispatchEvent(new CustomEvent("solomon:workspace-share-updated", {
                detail: { documentIds: [state.documents[0].documentId], principalType, principalId }
            }));
        } catch (error) {
            setStatus(error.message || "Access could not be updated.", "error");
        } finally {
            if (state) {
                setBusy(false);
            }
        }
    }

    async function revokeAccess(button) {
        if (!state || state.documents.length !== 1) {
            return;
        }
        const principalType = clean(button.getAttribute("data-principal-type"));
        const principalId = clean(button.getAttribute("data-principal-id"));
        const documentId = state.documents[0].documentId;

        setBusy(true);
        setStatus("Revoking access...", "info");
        try {
            await fetchJson(
                `/people/shares/files/${encodeURIComponent(documentId)}/${encodeURIComponent(principalType)}/${encodeURIComponent(principalId)}`,
                { method: "DELETE" }
            );
            await loadAccess();
            render();
            setStatus("Access revoked.", "success");
            document.dispatchEvent(new CustomEvent("solomon:workspace-share-updated", {
                detail: { documentIds: [documentId], principalType, principalId }
            }));
        } catch (error) {
            setStatus(error.message || "Access could not be revoked.", "error");
        } finally {
            if (state) {
                setBusy(false);
            }
        }
    }

    function handleDialogClick(event) {
        const closeTrigger = event.target.closest("[data-workspace-share-close]");
        if (closeTrigger) {
            event.preventDefault();
            close();
            return;
        }

        const principal = event.target.closest("[data-workspace-share-principal]");
        if (principal && state) {
            state.principalKey = clean(principal.getAttribute("data-workspace-share-principal"));
            render();
            return;
        }

        const save = event.target.closest("[data-workspace-share-access-save]");
        if (save) {
            updateAccess(save);
            return;
        }

        const revoke = event.target.closest("[data-workspace-share-access-revoke]");
        if (revoke) {
            revokeAccess(revoke);
            return;
        }

        if (event.target.closest("[data-workspace-share-submit]")) {
            submitShare();
        }
    }

    function handleDialogInput(event) {
        if (!state) {
            return;
        }
        if (event.target.matches("[data-workspace-share-recipient-search]")) {
            state.recipientQuery = event.target.value;
            render();
            dialog.querySelector("[data-workspace-share-recipient-search]")?.focus();
        }
        if (event.target.matches("[data-workspace-share-file-search]")) {
            state.fileQuery = event.target.value;
            render();
            dialog.querySelector("[data-workspace-share-file-search]")?.focus();
        }
    }

    function handleDialogChange(event) {
        if (!state) {
            return;
        }
        if (event.target.matches("[data-workspace-share-file-option]")) {
            const id = clean(event.target.getAttribute("data-workspace-share-file-option"));
            const file = (state.options?.owned_files || []).find(function (item) {
                return clean(item.document_id || item.random_name || item.file_id) === id;
            });
            if (event.target.checked && file) {
                if (!state.documents.some(function (doc) { return doc.documentId === id; })) {
                    state.documents.push({
                        documentId: id,
                        name: clean(file.original_name) || id
                    });
                }
            } else {
                state.documents = state.documents.filter(function (doc) {
                    return doc.documentId !== id;
                });
            }
            render();
            return;
        }
        if (event.target.matches("[data-workspace-share-permission]")) {
            state.permission = event.target.value === "edit" ? "edit" : "view";
            return;
        }
        if (event.target.matches("[data-workspace-share-download]")) {
            state.allowDownload = event.target.checked;
        }
    }

    function rowsForSelection(explorer, selection) {
        const documents = normalizeDocuments(selection);
        if (!explorer || !window.CSS?.escape) {
            return [];
        }
        return documents.map(function (doc) {
            return explorer.querySelector(`${ROW_SELECTOR}[data-document-id="${CSS.escape(doc.documentId)}"]`);
        }).filter(Boolean);
    }

    function syncSelectionRail(explorer, selection) {
        const rail = explorer?.querySelector(RAIL_SELECTOR);
        if (!rail) {
            return;
        }

        rail.querySelector("[data-document-share-selection-action]")?.remove();
        const documents = normalizeDocuments(selection);
        const rows = rowsForSelection(explorer, selection);
        const canShare = Boolean(
            documents.length &&
            rows.length === documents.length &&
            rows.every(function (row) {
                return row.getAttribute("data-document-can-share") === "true" &&
                    row.getAttribute("data-document-folder") !== "true" &&
                    row.getAttribute("data-document-trashed") !== "true";
            })
        );
        if (!canShare) {
            return;
        }

        const button = create("button", "workspace-document-command workspace-document-command--icon");
        button.type = "button";
        button.setAttribute("data-document-share-selection-action", "");
        button.setAttribute("aria-label", documents.length > 1 ? "Share selected files" : "Share selected file");
        button.title = documents.length > 1 ? "Share selected files" : "Share";
        button.append(
            create("span", "icon", "person_add"),
            create("span", "", "Share")
        );
        button.addEventListener("click", function () {
            open({ documents });
        });

        const primary = rail.querySelector(".workspace-document-selection-action-group--primary") ||
            rail.querySelector(".workspace-document-selection-actions") || rail;
        primary.appendChild(button);
    }

    function handleGlobalClick(event) {
        const filePicker = event.target.closest("[data-document-share-files-trigger]");
        if (filePicker) {
            event.preventDefault();
            open({
                allowFilePicker: true,
                principalType: filePicker.getAttribute("data-share-principal-type"),
                principalId: filePicker.getAttribute("data-share-principal-id")
            });
            return;
        }

        const manage = event.target.closest("[data-document-manage-access-trigger]");
        if (manage) {
            const doc = getDocumentFromTrigger(manage);
            if (doc) {
                event.preventDefault();
                open({ mode: "manage", documents: [doc] });
            }
            return;
        }

        const share = event.target.closest("[data-document-share-trigger]");
        if (share) {
            const doc = getDocumentFromTrigger(share);
            if (doc) {
                event.preventDefault();
                open({ documents: [doc] });
            }
        }
    }

    document.addEventListener("click", handleGlobalClick, true);
    document.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && dialog && !dialog.hidden) {
            close();
        }
    });

    window[API_NAME] = Object.freeze({
        open,
        openManageAccess: function (options) {
            return open(Object.assign({}, options || {}, { mode: "manage" }));
        },
        close,
        syncSelectionRail
    });
}());
