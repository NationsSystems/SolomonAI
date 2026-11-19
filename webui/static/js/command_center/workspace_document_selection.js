/* -------------------------------------------------------------------
   FILE: workspace_document_selection.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const DOCUMENT_SELECTION_RAIL_SELECTOR = "[data-document-selection-rail]";
    const DOCUMENT_SELECTION_ROW_SELECTOR = "[data-document-selection-row]";
    const DOCUMENT_SELECTION_CHECKBOX_SELECTOR = "[data-document-select-checkbox]";
    const DOCUMENT_ROW_SELECTOR = ".workspace-document-file[data-document-id]";
    const DOCUMENT_DEFAULT_UTILITY_SELECTOR = "[data-document-selection-default-utility], [data-document-default-utility-row]";
    const DOCUMENT_SELECTION_CHANGE_EVENT = "solomon:documents-selection-change";
    const DOCUMENT_SELECTION_COMMAND_FIT_EVENT = "solomon:documents-command-fit";
    const DOCUMENT_SELECTION_OVERFLOW_SELECTOR = "[data-document-selection-command-overflow]";
    const DOCUMENT_SELECTION_OVERFLOW_MENU_SELECTOR = "[data-document-selection-command-overflow-menu]";
    const DOCUMENT_SELECTION_OVERFLOW_EPSILON = 2;

    function cleanValue(value) {
        return String(value || "").trim();
    }

    function normalizeLookupValue(value) {
        return cleanValue(value).toLowerCase();
    }

    function getRecordsApi(options) {
        return options?.Records || window.SolomonWorkspaceDocumentRecords || null;
    }

    function getLibraryApi(options) {
        return options?.Library || window.SolomonWorkspaceDocumentLibrary || null;
    }

    function getConversationApi(options) {
        return options?.Conversation || window.SolomonWorkspaceDocumentConversation || null;
    }

    function getSelector(options, key, fallback) {
        return cleanValue(options?.selectors?.[key]) || fallback;
    }

    function clearNode(node) {
        while (node?.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function textElement(tagName, className, text) {
        const element = document.createElement(tagName);

        if (className) {
            element.className = className;
        }

        element.textContent = String(text || "");

        return element;
    }

    function splitDocumentValueList(value, separator) {
        if (Array.isArray(value)) {
            return value.map(cleanValue).filter(Boolean);
        }

        return cleanValue(value)
            .split(separator || ",")
            .map(cleanValue)
            .filter(Boolean);
    }

    function uniqueDocumentValues(values) {
        const seen = new Set();
        const uniqueValues = [];

        (values || []).forEach(function (value) {
            const clean = cleanValue(value);

            if (!clean || seen.has(clean)) {
                return;
            }

            seen.add(clean);
            uniqueValues.push(clean);
        });

        return uniqueValues;
    }

    function normalizeSurfaceActionName(value) {
        const actionName = normalizeLookupValue(value);
        const aliases = {
            ask_about_this: "ask_solomon_ai",
            delete: "move_to_trash",
            delete_forever: "permanent_delete",
            details: "view_details",
            open_reader: "open",
            restore_from_trash: "restore"
        };

        return aliases[actionName] || actionName;
    }

    function normalizeSurfaceActions(value) {
        const sourceValues = Array.isArray(value)
            ? value
            : splitDocumentValueList(value, ",");

        return uniqueDocumentValues(sourceValues.map(normalizeSurfaceActionName));
    }

    function getDocumentSurfaceActionDecision(doc) {
        const sourceDoc = doc && typeof doc === "object" ? doc : {};
        const actionKeys = [
            "surface_actions",
            "surfaceActions",
            "available_actions",
            "availableActions",
            "actions"
        ];
        const actionKey = actionKeys.find(function (key) {
            return Object.prototype.hasOwnProperty.call(sourceDoc, key);
        });

        if (!actionKey && sourceDoc.surface_actions_authoritative !== true) {
            return {
                authoritative: false,
                actions: new Set()
            };
        }

        return {
            authoritative: true,
            actions: new Set(normalizeSurfaceActions(actionKey ? sourceDoc[actionKey] : []))
        };
    }

    function resolveSelectionSurfaceActionDecision(docs) {
        const decisions = (Array.isArray(docs) ? docs : []).map(getDocumentSurfaceActionDecision);

        if (!decisions.length || decisions.some(function (decision) {
            return decision.authoritative !== true;
        })) {
            return {
                authoritative: false,
                actions: new Set()
            };
        }

        const actions = new Set(decisions[0].actions);

        decisions.slice(1).forEach(function (decision) {
            Array.from(actions).forEach(function (actionName) {
                if (!decision.actions.has(actionName)) {
                    actions.delete(actionName);
                }
            });
        });

        return {
            authoritative: true,
            actions
        };
    }

    function normalizeSolomonActionDescriptor(action) {
        if (!action || typeof action !== "object" || Array.isArray(action)) {
            return null;
        }

        const actionId = cleanValue(action.action_id);
        const command = normalizeLookupValue(action.command);
        const label = cleanValue(action.label);
        const state = normalizeLookupValue(action.state || "available");

        if (!actionId || !command || !label || state !== "available") {
            return null;
        }

        return {
            action_id: actionId,
            command,
            label,
            family: normalizeLookupValue(action.family),
            icon: cleanValue(action.icon) || "bolt",
            state,
            selection_policy: normalizeLookupValue(action.selection_policy || "single") || "single"
        };
    }

    function getDocumentSolomonActionDecision(doc) {
        const sourceDoc = doc && typeof doc === "object" ? doc : {};
        const authoritative = sourceDoc.solomon_actions_authoritative === true;
        const rawActions = Array.isArray(sourceDoc.solomon_actions)
            ? sourceDoc.solomon_actions
            : [];

        if (!authoritative) {
            return {
                authoritative: false,
                actions: []
            };
        }

        return {
            authoritative: true,
            actions: rawActions
                .map(normalizeSolomonActionDescriptor)
                .filter(Boolean)
        };
    }

    function resolveSelectionSolomonActionDecision(docs) {
        const sourceDocs = Array.isArray(docs) ? docs : [];

        if (sourceDocs.length !== 1) {
            return {
                authoritative: sourceDocs.length > 0 && sourceDocs.every(function (doc) {
                    return getDocumentSolomonActionDecision(doc).authoritative === true;
                }),
                actions: []
            };
        }

        return getDocumentSolomonActionDecision(sourceDocs[0]);
    }

    function getDocumentSelectionLabel(count) {
        const total = Number(count || 0);

        if (total === 1) {
            return "1 file";
        }

        return `${total} files`;
    }

    function getFolderSelectionLabel(count) {
        const total = Number(count || 0);

        if (total === 1) {
            return "1 folder";
        }

        return `${total} folders`;
    }

    function getWorkspaceSelectionLabel(count, docs, options) {
        const total = Number(count || 0);
        const sourceDocs = Array.isArray(docs) ? docs : [];
        const folderCount = sourceDocs.filter(function (doc) {
            return isFolderDocumentRecord(doc, options);
        }).length;

        if (!total) {
            return "0 files";
        }

        if (folderCount === total) {
            return getFolderSelectionLabel(total);
        }

        if (folderCount > 0) {
            return total === 1 ? "1 item" : `${total} items`;
        }

        return getDocumentSelectionLabel(total);
    }

    function isFolderDocumentRecord(doc, options) {
        const Records = getRecordsApi(options);
        const rawDoc = doc && typeof doc === "object" ? doc : {};
        const normalizedDoc = Records && typeof Records.normalizeDocument === "function"
            ? Records.normalizeDocument(rawDoc)
            : rawDoc;
        const itemType = normalizeLookupValue(
            rawDoc.workspace_item_type ||
            rawDoc.item_type ||
            rawDoc.resource_type ||
            rawDoc.document_kind ||
            rawDoc.object_type ||
            rawDoc.kind ||
            rawDoc.document_type ||
            rawDoc.type ||
            normalizedDoc.workspace_item_type ||
            normalizedDoc.item_type ||
            normalizedDoc.resource_type ||
            normalizedDoc.document_kind ||
            normalizedDoc.object_type ||
            normalizedDoc.kind ||
            normalizedDoc.document_type ||
            normalizedDoc.type
        );

        return Boolean(
            itemType === "folder" ||
            rawDoc.folder === true ||
            rawDoc.is_folder === true ||
            normalizedDoc.folder === true ||
            normalizedDoc.is_folder === true
        );
    }

    function getDocumentRows(explorer, options) {
        const rowSelector = getSelector(options, "documentRow", DOCUMENT_ROW_SELECTOR);

        return Array.from(explorer?.querySelectorAll(rowSelector) || []);
    }

    function getSelectedDocumentRows(explorer, options) {
        const Library = getLibraryApi(options);

        if (Library && typeof Library.getSelectedDocumentRows === "function") {
            return Library.getSelectedDocumentRows(explorer);
        }

        return getDocumentRows(explorer, options).filter(function (row) {
            return row.getAttribute("data-document-selected") === "true";
        });
    }

    function getDocumentIdsFromRows(rows) {
        return uniqueDocumentValues(
            (rows || []).map(function (row) {
                return row?.getAttribute("data-document-id") || "";
            })
        );
    }

    function getDocumentNamesFromRows(rows) {
        return uniqueDocumentValues(
            (rows || []).map(function (row) {
                return row?.querySelector("strong")?.textContent || "";
            })
        );
    }

    function dispatchDocumentSelectionChange(explorer, docs, options) {
        const selectedRows = getSelectedDocumentRows(explorer, options);
        const selectedDocs = Array.isArray(docs) ? docs : [];
        const documentIds = getDocumentIdsFromRows(selectedRows);
        const rowNames = getDocumentNamesFromRows(selectedRows);
        const documentNames = uniqueDocumentValues(
            selectedDocs.map(function (doc) {
                return doc?.original_name || doc?.name || doc?.filename || doc?.document_id || "";
            }).concat(rowNames)
        );

        if (!explorer || typeof document.dispatchEvent !== "function") {
            return;
        }

        document.dispatchEvent(new CustomEvent(DOCUMENT_SELECTION_CHANGE_EVENT, {
            detail: {
                explorer,
                docs: selectedDocs.slice(),
                documentIds,
                documentNames,
                selectedCount: documentIds.length,
                selectionIntent: cleanValue(options?.selectionIntent) || "programmatic_selection",
                openInspector: options?.openInspector === true,
                source: "workspace_document_selection"
            }
        }));
    }

    function getDocumentRecordsFromRows(explorer, rows, options) {
        const Library = getLibraryApi(options);

        if (!Library || typeof Library.getDocumentFromRow !== "function") {
            return [];
        }

        return (rows || [])
            .map(function (row) {
                const doc = Library.getDocumentFromRow(explorer, row);
                const rawSurfaceActions = row?.getAttribute("data-document-surface-actions");

                if (rawSurfaceActions === null) {
                    return doc;
                }

                return Object.assign({}, doc, {
                    surface_actions: normalizeSurfaceActions(rawSurfaceActions),
                    surface_actions_authoritative: true
                });
            })
            .filter(function (doc) {
                return Boolean(doc?.document_id);
            });
    }

    function getDocumentActionName(explorer, documentId, options) {
        const Records = getRecordsApi(options);
        const cleanId = cleanValue(documentId);
        const storedDoc = cleanId ? explorer?.__solomonDocumentById?.get(cleanId) : null;
        const selectedDoc = explorer?.__selectedDocument;

        if (storedDoc && Records && typeof Records.normalizeDocument === "function") {
            return Records.normalizeDocument(storedDoc).original_name || cleanId;
        }

        if (selectedDoc && selectedDoc.document_id === cleanId) {
            return selectedDoc.original_name || cleanId;
        }

        return cleanId || "Selected file";
    }

    function getDocumentActionRecord(explorer, documentId, options) {
        const Records = getRecordsApi(options);
        const cleanId = cleanValue(documentId);
        const storedDoc = cleanId ? explorer?.__solomonDocumentById?.get(cleanId) : null;
        const selectedDoc = explorer?.__selectedDocument?.document_id === cleanId
            ? explorer.__selectedDocument
            : null;
        const sourceDoc = storedDoc || selectedDoc || {};
        const payload = {
            ...sourceDoc,
            document_id: cleanId || sourceDoc.document_id || sourceDoc.random_name || ""
        };

        if (Records && typeof Records.normalizeDocument === "function") {
            return Records.normalizeDocument(payload);
        }

        return payload;
    }

    function getDocumentRecordsByIds(explorer, documentIds, options) {
        return uniqueDocumentValues(documentIds)
            .map(function (documentId) {
                return getDocumentActionRecord(explorer, documentId, options);
            })
            .filter(function (doc) {
                return Boolean(doc?.document_id);
            });
    }

    function getDocumentNamesByIds(explorer, documentIds, options) {
        return uniqueDocumentValues(documentIds).map(function (documentId) {
            return getDocumentActionName(explorer, documentId, options);
        });
    }

    function setDocumentRowSelected(row, selected, options) {
        const cleanSelected = Boolean(selected);
        const checkboxSelector = getSelector(options, "selectionCheckbox", DOCUMENT_SELECTION_CHECKBOX_SELECTOR);
        const checkbox = row?.querySelector(checkboxSelector);

        if (!row) {
            return;
        }

        row.classList.toggle("is-selected", cleanSelected);
        row.setAttribute("aria-selected", cleanSelected ? "true" : "false");
        row.setAttribute("data-document-selected", cleanSelected ? "true" : "false");

        if (checkbox) {
            checkbox.checked = cleanSelected;
            checkbox.setAttribute("aria-checked", cleanSelected ? "true" : "false");
        }
    }

    function setOnlyDocumentRowSelected(explorer, row, options) {
        getDocumentRows(explorer, options).forEach(function (fileRow) {
            setDocumentRowSelected(fileRow, fileRow === row, options);
        });
    }

    function setDocumentRowsSelectedByIds(explorer, documentIds, options) {
        const selectedIds = new Set(uniqueDocumentValues(documentIds));

        getDocumentRows(explorer, options).forEach(function (row) {
            setDocumentRowSelected(
                row,
                selectedIds.has(row.getAttribute("data-document-id") || ""),
                options
            );
        });
    }

    function getSelectionRail(explorer, options) {
        const selector = getSelector(options, "selectionRail", DOCUMENT_SELECTION_RAIL_SELECTOR);

        return explorer?.querySelector(selector) || null;
    }

    function getSelectionRow(explorer, options) {
        const selector = getSelector(options, "selectionRow", DOCUMENT_SELECTION_ROW_SELECTOR);

        return explorer?.querySelector(selector) || null;
    }

    function setUtilityVisibility(utility, visible) {
        if (!utility) {
            return;
        }

        utility.hidden = !visible;
        utility.setAttribute("aria-hidden", visible ? "false" : "true");

        if (visible) {
            utility.removeAttribute("hidden");
            utility.style.removeProperty("display");
        }
    }

    function setSelectionRailVisibility(explorer, state, options) {
        const selectionRow = getSelectionRow(explorer, options);
        const rail = getSelectionRail(explorer, options);
        const defaultUtility = selectionRow?.querySelector(DOCUMENT_DEFAULT_UTILITY_SELECTOR) || null;
        const cleanState = cleanValue(state) || "empty";
        const isEmpty = cleanState === "empty";
        const isSelectionActive = !isEmpty;

        if (selectionRow) {
            selectionRow.hidden = false;
            selectionRow.removeAttribute("hidden");
            selectionRow.setAttribute("data-document-selection-state", cleanState);
            selectionRow.setAttribute("aria-hidden", "false");
            selectionRow.style.removeProperty("display");
        }

        setUtilityVisibility(defaultUtility, !isSelectionActive);

        if (rail) {
            rail.hidden = !isSelectionActive;
            rail.setAttribute("aria-hidden", isSelectionActive ? "false" : "true");
            rail.setAttribute("data-document-selection-state", cleanState);

            if (isSelectionActive) {
                rail.removeAttribute("hidden");
                rail.style.removeProperty("display");
            }
        }
    }

    function createSelectionActionButton(iconName, label, attributes, options) {
        const button = document.createElement("button");
        const cleanOptions = options || {};
        const cleanLabel = cleanValue(label) || "File action";

        button.type = "button";
        button.className = cleanOptions.className || "workspace-document-command";
        button.setAttribute("title", cleanOptions.title || cleanLabel);
        button.setAttribute("aria-label", cleanOptions.ariaLabel || cleanLabel);

        Object.entries(attributes || {}).forEach(function (entry) {
            button.setAttribute(entry[0], entry[1]);
        });

        const icon = textElement("span", "icon", iconName);
        const labelText = textElement(
            "span",
            "workspace-document-command-label",
            cleanLabel
        );

        icon.setAttribute("aria-hidden", "true");
        button.append(icon, labelText);

        return button;
    }

    function createDisabledSelectionActionButton(iconName, label, options) {
        const button = createSelectionActionButton(iconName, label, {}, Object.assign(
            {
                className: "workspace-document-command workspace-document-command-neutral workspace-document-command-icon-only",
                title: label,
                ariaLabel: label
            },
            options || {}
        ));

        button.disabled = true;
        button.setAttribute("aria-disabled", "true");

        return button;
    }

    function createSolomonSelectionActions(
        actions,
        documentId,
        documentName
    ) {
        const cleanActions = Array.isArray(actions) ? actions : [];
        const renderableActions = cleanActions.filter(function (action) {
            return action.selection_policy === "single";
        });
        const cleanDocumentId = cleanValue(documentId);
        const cleanDocumentName = cleanValue(documentName) || "Selected file";
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        const summaryIcon = textElement("span", "icon", "bolt");
        const summaryLabel = textElement("span", "", "Actions");
        const summaryCount = textElement(
            "span",
            "workspace-document-selection-solomon-action-count",
            String(renderableActions.length)
        );
        const menu = document.createElement("div");

        if (!renderableActions.length || !cleanDocumentId) {
            return null;
        }

        details.className = "workspace-document-selection-solomon-actions";
        details.setAttribute("data-document-selection-solomon-actions", "");

        summary.className = "workspace-document-command workspace-document-selection-solomon-actions-trigger";
        summary.setAttribute("aria-label", `${renderableActions.length} Solomon Actions available for ${cleanDocumentName}`);
        summary.setAttribute("title", "Actions");
        summaryIcon.setAttribute("aria-hidden", "true");
        summary.append(summaryIcon, summaryLabel, summaryCount);

        menu.className = "workspace-document-selection-solomon-actions-menu";
        menu.setAttribute("role", "menu");
        menu.setAttribute("aria-label", `Actions for ${cleanDocumentName}`);

        renderableActions.forEach(function (action) {
            const button = document.createElement("button");
            const icon = textElement("span", "icon", action.icon);
            const label = textElement("span", "", action.label);

            button.type = "button";
            button.className = "workspace-document-selection-solomon-action-item";
            button.setAttribute("role", "menuitem");
            button.setAttribute("data-solomon-file-action", "");
            button.setAttribute("data-solomon-action-id", action.action_id);
            button.setAttribute("data-solomon-action-label", action.label);
            button.setAttribute("data-solomon-action-family", action.family);
            button.setAttribute("data-solomon-action-command", action.command);
            button.setAttribute("data-document-id", cleanDocumentId);
            button.setAttribute("data-document-name", cleanDocumentName);
            button.setAttribute("aria-label", `${action.label} ${cleanDocumentName}`);
            icon.setAttribute("aria-hidden", "true");
            button.append(icon, label);
            menu.appendChild(button);
        });

        details.append(summary, menu);
        return details;
    }

    function getSelectionCommandPriority(command) {
        if (!(command instanceof HTMLElement)) {
            return 80;
        }

        if (command.matches("[data-document-open], [data-document-restore]")) {
            return 10;
        }

        if (command.matches("[data-document-ask-solomon-ai]")) {
            return 20;
        }

        if (command.matches("[data-document-selection-solomon-actions]")) {
            return 30;
        }

        if (command.matches("[data-document-selected-details]")) {
            return 70;
        }

        if (command.matches("[data-document-delete], [data-document-permanent-delete]")) {
            return 100;
        }

        return 80;
    }

    function annotateSelectionCommands(actions) {
        if (!(actions instanceof HTMLElement)) {
            return;
        }

        actions.querySelectorAll("[data-document-selection-action-group]").forEach(function (group) {
            const home = cleanValue(group.getAttribute("data-document-selection-action-group")) || "actions";

            Array.from(group.children).forEach(function (command, index) {
                if (!(command instanceof HTMLElement)) {
                    return;
                }

                command.setAttribute("data-document-command-home", home);
                command.setAttribute("data-document-command-home-order", String(index));
                command.setAttribute("data-document-command-priority", String(getSelectionCommandPriority(command)));

                if (!command.matches("[data-document-selection-solomon-actions]")) {
                    command.setAttribute("data-document-command-overflow-eligible", "true");
                }
            });
        });
    }

    function createSelectionOverflowControl() {
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        const icon = textElement("span", "icon", "more_horiz");
        const label = textElement("span", "workspace-document-command-label", "More");
        const menu = document.createElement("div");

        details.className = "workspace-document-selection-command-overflow";
        details.setAttribute("data-document-selection-command-overflow", "");
        details.hidden = true;

        summary.className = "workspace-document-command workspace-document-command-icon-only workspace-document-selection-command-overflow-trigger";
        summary.setAttribute("aria-label", "More selected file actions");
        summary.setAttribute("title", "More");
        icon.setAttribute("aria-hidden", "true");
        summary.append(icon, label);

        menu.className = "workspace-document-selection-command-overflow-menu";
        menu.setAttribute("data-document-selection-command-overflow-menu", "");
        menu.setAttribute("role", "menu");
        menu.setAttribute("aria-label", "More selected file actions");

        details.append(summary, menu);
        return details;
    }

    function restoreSelectionOverflowCommands(actions) {
        const overflow = actions?.querySelector(DOCUMENT_SELECTION_OVERFLOW_SELECTOR) || null;
        const menu = overflow?.querySelector(DOCUMENT_SELECTION_OVERFLOW_MENU_SELECTOR) || null;

        if (!(actions instanceof HTMLElement) || !(menu instanceof HTMLElement)) {
            return;
        }

        const overflowCommands = Array.from(menu.children).filter(function (command) {
            return command instanceof HTMLElement;
        });

        overflowCommands.sort(function (left, right) {
            const leftHome = cleanValue(left.getAttribute("data-document-command-home"));
            const rightHome = cleanValue(right.getAttribute("data-document-command-home"));

            if (leftHome !== rightHome) {
                return 0;
            }

            return Number(left.getAttribute("data-document-command-home-order") || 0) -
                Number(right.getAttribute("data-document-command-home-order") || 0);
        }).forEach(function (command) {
            const home = cleanValue(command.getAttribute("data-document-command-home"));
            const group = actions.querySelector(`[data-document-selection-action-group="${home}"]`);

            command.classList.remove("workspace-document-command--overflow");
            command.removeAttribute("role");

            if (group instanceof HTMLElement) {
                const homeOrder = Number(command.getAttribute("data-document-command-home-order") || 0);
                const before = Array.from(group.children).find(function (sibling) {
                    return sibling instanceof HTMLElement &&
                        Number(sibling.getAttribute("data-document-command-home-order") || 0) > homeOrder;
                });

                group.insertBefore(command, before || null);
            }
        });

        overflow.open = false;
        overflow.hidden = true;
    }

    function selectionCommandBarOverflows(rail) {
        const content = rail?.querySelector(".workspace-document-selection-rail-content") || null;
        const actions = rail?.querySelector(".workspace-document-selection-actions") || null;

        if (!(content instanceof HTMLElement) || !(actions instanceof HTMLElement)) {
            return false;
        }

        return (
            content.scrollWidth > content.clientWidth + DOCUMENT_SELECTION_OVERFLOW_EPSILON ||
            actions.scrollWidth > actions.clientWidth + DOCUMENT_SELECTION_OVERFLOW_EPSILON
        );
    }

    function fitSelectionCommands(rail) {
        const actions = rail?.querySelector(".workspace-document-selection-actions") || null;
        const overflow = actions?.querySelector(DOCUMENT_SELECTION_OVERFLOW_SELECTOR) || null;
        const menu = overflow?.querySelector(DOCUMENT_SELECTION_OVERFLOW_MENU_SELECTOR) || null;

        if (!(actions instanceof HTMLElement) || !(overflow instanceof HTMLElement) || !(menu instanceof HTMLElement)) {
            return;
        }

        restoreSelectionOverflowCommands(actions);

        const candidates = Array.from(
            actions.querySelectorAll('[data-document-command-overflow-eligible="true"]')
        ).filter(function (command) {
            return command instanceof HTMLElement;
        }).sort(function (left, right) {
            return Number(right.getAttribute("data-document-command-priority") || 80) -
                Number(left.getAttribute("data-document-command-priority") || 80);
        });

        for (const command of candidates) {
            if (!selectionCommandBarOverflows(rail)) {
                break;
            }

            overflow.hidden = false;
            command.classList.add("workspace-document-command--overflow");
            command.setAttribute("role", "menuitem");
            menu.appendChild(command);
        }

        if (!menu.children.length) {
            overflow.hidden = true;
            overflow.open = false;
        }

        document.dispatchEvent(new CustomEvent(DOCUMENT_SELECTION_COMMAND_FIT_EVENT, {
            detail: {
                rail: rail
            }
        }));
    }

    function scheduleSelectionCommandFit(rail) {
        if (!(rail instanceof HTMLElement) || rail.__solomonSelectionFitQueued) {
            return;
        }

        rail.__solomonSelectionFitQueued = true;
        window.requestAnimationFrame(function () {
            rail.__solomonSelectionFitQueued = false;
            fitSelectionCommands(rail);
        });
    }

    function ensureSelectionCommandBarObserver(explorer, rail, options) {
        const selectionRow = getSelectionRow(explorer, options);

        if (!(rail instanceof HTMLElement)) {
            return;
        }

        if (!rail.__solomonSelectionOverflowObserver && typeof window.ResizeObserver === "function") {
            const observer = new window.ResizeObserver(function () {
                scheduleSelectionCommandFit(rail);
            });

            observer.observe(rail);
            if (selectionRow instanceof HTMLElement) {
                observer.observe(selectionRow);
            }
            rail.__solomonSelectionOverflowObserver = observer;
        }

        if (!document.documentElement.hasAttribute("data-solomon-selection-overflow-bound")) {
            document.documentElement.setAttribute("data-solomon-selection-overflow-bound", "true");
            document.addEventListener("click", function (event) {
                document.querySelectorAll(`${DOCUMENT_SELECTION_OVERFLOW_SELECTOR}[open]`).forEach(function (details) {
                    if (details instanceof HTMLElement && !details.contains(event.target)) {
                        details.removeAttribute("open");
                    }
                });
            });
        }

        scheduleSelectionCommandFit(rail);
    }

    function createSelectionActionGroup(groupName, label) {
        const group = document.createElement("div");
        const cleanGroupName = cleanValue(groupName) || "actions";
        const cleanLabel = cleanValue(label) || "Selected file actions";

        group.className = `workspace-document-selection-action-group workspace-document-selection-action-group--${cleanGroupName}`;
        group.setAttribute("role", "group");
        group.setAttribute("aria-label", cleanLabel);
        group.setAttribute("data-document-selection-action-group", cleanGroupName);

        return group;
    }

    function createSelectionClearButton(documentName) {
        const button = document.createElement("button");
        const cleanName = cleanValue(documentName) || "selected file";

        button.type = "button";
        button.className = "workspace-document-selection-file-icon workspace-document-selection-clear-button";
        button.setAttribute("data-document-clear-selection", "");
        button.setAttribute("aria-label", `Clear selection for ${cleanName}`);
        button.setAttribute("title", "Clear selection");

        return button;
    }

    function getSelectionActionAttributes(attributeName, documentIds, documentNames) {
        const ids = uniqueDocumentValues(documentIds);
        const names = uniqueDocumentValues(documentNames);

        return {
            [attributeName]: ids[0] || "",
            "data-document-selected-ids": ids.join(","),
            "data-document-selected-names": names.join(" | "),
            "data-document-selection-count": String(ids.length)
        };
    }

    function getActionDocumentPayload(action, primaryAttributeName) {
        if (!action) {
            return null;
        }

        const selectedIds = splitDocumentValueList(
            action.getAttribute("data-document-selected-ids"),
            ","
        );
        const primaryId = cleanValue(action.getAttribute(primaryAttributeName));
        const documentIds = uniqueDocumentValues(
            selectedIds.length ? selectedIds : [primaryId]
        );
        const documentNames = splitDocumentValueList(
            action.getAttribute("data-document-selected-names"),
            "|"
        );

        if (!documentIds.length) {
            return null;
        }

        return {
            action,
            documentId: documentIds[0],
            documentIds,
            documentNames
        };
    }

    function getDocumentActionSelectionFromMenuItem(actionItem) {
        return getActionDocumentPayload(actionItem, "data-document-id");
    }

    function getSelectionSummaryName(documentIds, documentNames) {
        const ids = uniqueDocumentValues(documentIds);
        const names = uniqueDocumentValues(documentNames);

        if (ids.length > 1) {
            return getDocumentSelectionLabel(ids.length);
        }

        return names[0] || ids[0] || "Selected file";
    }

    function isDocumentRecordTrashed(doc, options) {
        const Records = getRecordsApi(options);
        const Library = getLibraryApi(options);

        if (!doc || typeof doc !== "object") {
            return false;
        }

        if (Library && typeof Library.isTrashedDocument === "function" && Library.isTrashedDocument(doc)) {
            return true;
        }

        const normalizedDoc = Records && typeof Records.normalizeDocument === "function"
            ? Records.normalizeDocument(doc)
            : doc;
        const documentStatus = String(
            doc.document_status ||
            doc.library_status ||
            doc.storage_status ||
            doc.status ||
            normalizedDoc.document_status ||
            normalizedDoc.library_status ||
            normalizedDoc.storage_status ||
            normalizedDoc.status ||
            ""
        ).trim().toLowerCase();

        return Boolean(
            doc.trashed === true ||
            normalizedDoc.trashed === true ||
            doc.trashed_at ||
            normalizedDoc.trashed_at ||
            ["trash", "trashed", "deleted"].includes(documentStatus)
        );
    }

    function isTrashSection(explorer, options) {
        if (typeof options?.isTrashSection === "function") {
            return options.isTrashSection(explorer);
        }

        if (typeof options?.normalizeDocumentSection === "function") {
            return options.normalizeDocumentSection(explorer?.getAttribute("data-workspace-section")) === "trash";
        }

        return cleanValue(explorer?.getAttribute("data-workspace-section")).toLowerCase() === "trash";
    }

    function isDocumentInTrashContext(explorer, documentId, options) {
        const cleanId = cleanValue(documentId);
        const rowSelector = getSelector(options, "documentRow", DOCUMENT_ROW_SELECTOR);
        const row = cleanId && window.CSS && typeof window.CSS.escape === "function"
            ? explorer?.querySelector(`${rowSelector}[data-document-id="${CSS.escape(cleanId)}"]`)
            : null;
        const storedDoc = cleanId ? explorer?.__solomonDocumentById?.get(cleanId) : null;

        if (isTrashSection(explorer, options)) {
            return true;
        }

        if (row?.getAttribute("data-document-trash-context") === "true") {
            return true;
        }

        if (storedDoc && isDocumentRecordTrashed(storedDoc, options)) {
            return true;
        }

        return false;
    }

    function hasAnyDocumentInTrashContext(explorer, documentIds, options) {
        return uniqueDocumentValues(documentIds).some(function (documentId) {
            return isDocumentInTrashContext(explorer, documentId, options);
        });
    }

    function hasAnyDocumentOutsideTrashContext(explorer, documentIds, options) {
        return uniqueDocumentValues(documentIds).some(function (documentId) {
            return !isDocumentInTrashContext(explorer, documentId, options);
        });
    }

    function renderSelectionRailEmpty(explorer, options) {
        const rail = getSelectionRail(explorer, options);

        if (!rail) {
            return;
        }

        clearNode(rail);
        rail.setAttribute("data-document-selection-state", "empty");
        rail.setAttribute("data-document-selection-count", "0");
        rail.removeAttribute("data-document-selected-ids");
        setSelectionRailVisibility(explorer, "empty", options);
        dispatchDocumentSelectionChange(explorer, [], options);
    }

    function normalizeSelectionDocuments(selection, options) {
        const Records = getRecordsApi(options);
        const rawDocs = Array.isArray(selection) ? selection : [selection];

        return rawDocs
            .map(function (doc) {
                const rawDoc = doc && typeof doc === "object" ? doc : {};
                const normalizedDoc = Records && typeof Records.normalizeDocument === "function"
                    ? Records.normalizeDocument(rawDoc)
                    : rawDoc;

                const mergedDoc = Object.assign({}, rawDoc, normalizedDoc);

                if (rawDoc.surface_actions_authoritative === true) {
                    mergedDoc.surface_actions = rawDoc.surface_actions;
                    mergedDoc.surface_actions_authoritative = true;
                }

                return mergedDoc;
            })
            .filter(function (doc) {
                return Boolean(doc.document_id);
            });
    }

    function getFileSizeLabel(doc, options) {
        const Records = getRecordsApi(options);

        if (Records && typeof Records.formatFileSize === "function") {
            return Records.formatFileSize(doc.size_bytes);
        }

        return "";
    }

    function appendSelectionActionGroup(actions, group) {
        if (group?.children?.length) {
            actions.appendChild(group);
        }
    }

    function renderSurfaceAuthorizedSelectionActions(
        primaryActions,
        secondaryActions,
        surfaceActions,
        documentIds,
        documentNames,
        firstDocumentName,
        selectedCount,
        options
    ) {
        const folderSelection = options?.folderSelection === true;
        const selectionLabel = folderSelection
            ? getFolderSelectionLabel(selectedCount)
            : getDocumentSelectionLabel(selectedCount);
        const multiple = selectedCount > 1;
        const specifications = [
            {
                action: "open",
                group: primaryActions,
                icon: folderSelection ? "folder_open" : "open_in_new",
                label: folderSelection ? "Open" : "Open Reader",
                attribute: "data-document-open",
                singleOnly: true,
                title: folderSelection ? "Open" : "Open Reader",
                ariaLabel: folderSelection
                    ? `Open ${firstDocumentName}`
                    : `Open ${firstDocumentName} in Reader`
            },
            {
                action: "ask_solomon_ai",
                group: primaryActions,
                icon: "auto_awesome",
                label: "Ask SolomonAI",
                attribute: "data-document-ask-solomon-ai",
                className: "workspace-document-command workspace-document-command-solomon",
                title: "Ask SolomonAI",
                ariaLabel: `Ask SolomonAI about ${multiple ? selectionLabel : firstDocumentName}`
            },
            {
                action: "restore",
                group: primaryActions,
                icon: "restore_from_trash",
                label: "Restore",
                attribute: "data-document-restore",
                title: multiple ? "Restore selected" : "Restore",
                ariaLabel: `Restore ${multiple ? selectionLabel : firstDocumentName}`
            },
            {
                action: "view_details",
                group: secondaryActions,
                icon: "info",
                label: "Details",
                attribute: "data-document-selected-details",
                singleOnly: true,
                title: "Details",
                ariaLabel: `Open details for ${firstDocumentName}`
            },
            {
                action: "move_to_trash",
                group: secondaryActions,
                icon: "delete",
                label: "Move to Trash",
                attribute: "data-document-delete",
                className: "workspace-document-command workspace-document-command-neutral workspace-document-command-icon-only",
                title: multiple ? "Move selected to Trash" : "Move to Trash",
                ariaLabel: `Move ${multiple ? selectionLabel : firstDocumentName} to Trash`
            },
            {
                action: "permanent_delete",
                group: secondaryActions,
                icon: "delete_forever",
                label: "Delete forever",
                attribute: "data-document-permanent-delete",
                className: "workspace-document-command workspace-document-command-danger workspace-document-command-icon-only",
                title: multiple ? "Delete selected forever" : "Delete forever",
                ariaLabel: `Delete ${multiple ? selectionLabel : firstDocumentName} forever`
            }
        ];

        specifications.forEach(function (specification) {
            if (
                !surfaceActions.has(specification.action) ||
                (multiple && specification.singleOnly)
            ) {
                return;
            }

            specification.group.append(
                createSelectionActionButton(
                    specification.icon,
                    specification.label,
                    getSelectionActionAttributes(
                        specification.attribute,
                        documentIds,
                        documentNames
                    ),
                    {
                        className: specification.className,
                        title: specification.title,
                        ariaLabel: specification.ariaLabel
                    }
                )
            );
        });
    }

    function renderSelectionRail(explorer, selection, options) {
        const rail = getSelectionRail(explorer, options);
        const docs = normalizeSelectionDocuments(selection, options);
        const documentIds = uniqueDocumentValues(docs.map(function (doc) {
            return doc.document_id;
        }));
        const documentNames = uniqueDocumentValues(docs.map(function (doc) {
            return doc.original_name || doc.name || doc.document_id;
        }));
        const selectedCount = documentIds.length;
        const folderDocs = docs.filter(function (doc) {
            return isFolderDocumentRecord(doc, options);
        });
        const hasFolderSelection = folderDocs.length > 0;
        const folderOnlySelection = selectedCount > 0 && folderDocs.length === selectedCount;
        const mixedObjectSelection = hasFolderSelection && !folderOnlySelection;
        const firstDoc = docs[0] || {};
        const firstIsFolder = isFolderDocumentRecord(firstDoc, options);
        const firstDocumentName = firstDoc.original_name || firstDoc.name || firstDoc.document_id || (firstIsFolder ? "Selected folder" : "Selected file");
        const selectionLabel = getWorkspaceSelectionLabel(selectedCount, docs, options);
        const trashSurface = !hasFolderSelection && isTrashSection(explorer, options);
        const trashSelection = !hasFolderSelection && (
            trashSurface ||
            hasAnyDocumentInTrashContext(explorer, documentIds, options) ||
            (
                docs.length &&
                docs.every(function (doc) {
                    return isDocumentRecordTrashed(doc, options);
                })
            )
        );
        const surfaceActionDecision = resolveSelectionSurfaceActionDecision(docs);
        const fileSize = selectedCount === 1
            ? (firstIsFolder ? "Workspace container" : getFileSizeLabel(firstDoc, options))
            : selectionLabel;
        const typeLabel = selectedCount === 1
            ? (firstIsFolder ? "Folder" : (firstDoc.type_label || "Workspace File"))
            : (hasFolderSelection ? "Selected items" : "Selected files");
        const content = document.createElement("div");
        const identity = document.createElement("div");
        const clearButton = createSelectionClearButton(
            selectedCount > 1 ? selectionLabel : firstDocumentName
        );
        const copy = document.createElement("div");
        const actions = document.createElement("div");
        const primaryActions = createSelectionActionGroup(
            "primary",
            hasFolderSelection
                ? "Workspace folder actions"
                : (trashSurface ? "Trash recovery actions" : "Primary selected file actions")
        );
        const secondaryActions = createSelectionActionGroup(
            "secondary",
            hasFolderSelection
                ? "Workspace folder details"
                : (trashSurface ? "Permanent deletion actions" : "More selected file actions")
        );
        const solomonActions = createSelectionActionGroup(
            "solomon",
            "Solomon Actions"
        );
        const solomonActionDecision = resolveSelectionSolomonActionDecision(docs);
        const overflowActions = createSelectionOverflowControl();
        const actionNames = documentNames.slice(0, 3).join(", ");
        const overflowCount = Math.max(0, selectedCount - 3);
        const selectedNamesLabel = overflowCount
            ? `${actionNames}, +${overflowCount} more`
            : actionNames;

        if (!rail || !selectedCount) {
            renderSelectionRailEmpty(explorer, options);
            return;
        }

        clearNode(rail);
        rail.setAttribute("data-document-selection-state", trashSurface ? "trash" : "selected");
        rail.setAttribute("data-document-selection-count", String(selectedCount));
        rail.setAttribute("data-document-selected-ids", documentIds.join(","));
        setSelectionRailVisibility(explorer, trashSurface ? "trash" : "selected", options);

        content.className = "workspace-document-selection-rail-content";
        identity.className = "workspace-document-selection-identity";
        copy.className = "workspace-document-selection-identity-copy";
        actions.className = "workspace-document-selection-actions";

        copy.append(
            textElement("span", "", trashSurface ? "Trash selection" : "Selected"),
            textElement(
                "strong",
                "",
                selectedCount > 1
                    ? `${selectionLabel} selected`
                    : firstDocumentName
            ),
            textElement(
                "em",
                "",
                selectedCount > 1
                    ? selectedNamesLabel
                    : `${typeLabel} · ${fileSize}`
            )
        );
        identity.append(clearButton, copy);

        if (hasFolderSelection) {
            if (mixedObjectSelection || !folderOnlySelection) {
                primaryActions.append(
                    createDisabledSelectionActionButton(
                        "block",
                        "File actions unavailable for mixed selections"
                    )
                );
            } else if (surfaceActionDecision.authoritative) {
                renderSurfaceAuthorizedSelectionActions(
                    primaryActions,
                    secondaryActions,
                    surfaceActionDecision.actions,
                    documentIds,
                    documentNames,
                    firstDocumentName,
                    selectedCount,
                    { folderSelection: true }
                );
            } else if (selectedCount === 1) {
                secondaryActions.append(
                    createSelectionActionButton("info", "Details", getSelectionActionAttributes(
                        "data-document-selected-details",
                        documentIds,
                        documentNames
                    ), {
                        title: "Folder details",
                        ariaLabel: `Open details for ${firstDocumentName}`
                    })
                );
            } else {
                primaryActions.append(
                    createDisabledSelectionActionButton(
                        "block",
                        "Folder actions unavailable for multiple folders"
                    )
                );
            }
        } else if (surfaceActionDecision.authoritative) {
            renderSurfaceAuthorizedSelectionActions(
                primaryActions,
                secondaryActions,
                surfaceActionDecision.actions,
                documentIds,
                documentNames,
                firstDocumentName,
                selectedCount
            );
        } else if (trashSurface) {
            if (selectedCount === 1) {
                primaryActions.append(
                    createSelectionActionButton("open_in_new", "Open Reader", getSelectionActionAttributes(
                        "data-document-open",
                        documentIds,
                        documentNames
                    ), {
                        title: "Open Reader",
                        ariaLabel: `Open ${firstDocumentName} in Reader`
                    }),
                    createSelectionActionButton("restore_from_trash", "Restore", getSelectionActionAttributes(
                        "data-document-restore",
                        documentIds,
                        documentNames
                    ), {
                        title: "Restore",
                        ariaLabel: `Restore ${firstDocumentName}`
                    })
                );
                secondaryActions.append(
                    createSelectionActionButton("info", "Details", getSelectionActionAttributes(
                        "data-document-selected-details",
                        documentIds,
                        documentNames
                    ), {
                        title: "Details",
                        ariaLabel: `Open details for ${firstDocumentName}`
                    }),
                    createSelectionActionButton("delete_forever", "Delete forever", getSelectionActionAttributes(
                        "data-document-permanent-delete",
                        documentIds,
                        documentNames
                    ), {
                        className: "workspace-document-command workspace-document-command-danger workspace-document-command-icon-only",
                        title: "Delete forever",
                        ariaLabel: `Delete ${firstDocumentName} forever`
                    })
                );
            } else {
                primaryActions.append(
                    createSelectionActionButton("restore_from_trash", "Restore", getSelectionActionAttributes(
                        "data-document-restore",
                        documentIds,
                        documentNames
                    ), {
                        title: "Restore selected",
                        ariaLabel: `Restore ${getDocumentSelectionLabel(selectedCount)}`
                    })
                );
                secondaryActions.append(
                    createSelectionActionButton("delete_forever", "Delete forever", getSelectionActionAttributes(
                        "data-document-permanent-delete",
                        documentIds,
                        documentNames
                    ), {
                        className: "workspace-document-command workspace-document-command-danger workspace-document-command-icon-only",
                        title: "Delete selected forever",
                        ariaLabel: `Delete ${getDocumentSelectionLabel(selectedCount)} forever`
                    })
                );
            }
        } else if (!trashSelection && selectedCount > 1) {
            primaryActions.append(
                createSelectionActionButton("auto_awesome", "Ask SolomonAI", getSelectionActionAttributes(
                    "data-document-ask-solomon-ai",
                    documentIds,
                    documentNames
                ), {
                    className: "workspace-document-command workspace-document-command-solomon",
                    title: "Ask SolomonAI",
                    ariaLabel: `Ask SolomonAI about ${getDocumentSelectionLabel(selectedCount)}`
                })
            );
            secondaryActions.append(
                createSelectionActionButton("delete", "Move to Trash", getSelectionActionAttributes(
                    "data-document-delete",
                    documentIds,
                    documentNames
                ), {
                    className: "workspace-document-command workspace-document-command-neutral workspace-document-command-icon-only",
                    title: "Move selected to Trash",
                    ariaLabel: `Move ${getDocumentSelectionLabel(selectedCount)} to Trash`
                })
            );
        } else if (!trashSelection) {
            primaryActions.append(
                createSelectionActionButton("open_in_new", "Open Reader", getSelectionActionAttributes(
                    "data-document-open",
                    documentIds,
                    documentNames
                ), {
                    title: "Open Reader",
                    ariaLabel: `Open ${firstDocumentName} in Reader`
                }),
                createSelectionActionButton("auto_awesome", "Ask SolomonAI", getSelectionActionAttributes(
                    "data-document-ask-solomon-ai",
                    documentIds,
                    documentNames
                ), {
                    className: "workspace-document-command workspace-document-command-solomon",
                    title: "Ask SolomonAI",
                    ariaLabel: `Ask SolomonAI about ${firstDocumentName}`
                })
            );
            secondaryActions.append(
                createSelectionActionButton("info", "Details", getSelectionActionAttributes(
                    "data-document-selected-details",
                    documentIds,
                    documentNames
                ), {
                    title: "Details",
                    ariaLabel: `Open details for ${firstDocumentName}`
                }),
                createSelectionActionButton("delete", "Move to Trash", getSelectionActionAttributes(
                    "data-document-delete",
                    documentIds,
                    documentNames
                ), {
                    className: "workspace-document-command workspace-document-command-neutral workspace-document-command-icon-only",
                    title: "Move to Trash",
                    ariaLabel: `Move ${firstDocumentName} to Trash`
                })
            );
        }

        if (
            !hasFolderSelection &&
            !trashSelection &&
            selectedCount === 1 &&
            solomonActionDecision.authoritative
        ) {
            const solomonActionControl = createSolomonSelectionActions(
                solomonActionDecision.actions,
                documentIds[0],
                firstDocumentName
            );

            if (solomonActionControl) {
                solomonActions.appendChild(solomonActionControl);
            }
        }

        appendSelectionActionGroup(actions, primaryActions);
        appendSelectionActionGroup(actions, solomonActions);
        appendSelectionActionGroup(actions, secondaryActions);
        annotateSelectionCommands(actions);
        actions.appendChild(overflowActions);
        content.append(identity, actions);
        rail.appendChild(content);
        ensureSelectionCommandBarObserver(explorer, rail, options);
        dispatchDocumentSelectionChange(explorer, docs, options);
    }

    function updateExplorerSelectionFromRows(explorer, options) {
        const Conversation = getConversationApi(options);
        const rows = getSelectedDocumentRows(explorer, options);
        const docs = getDocumentRecordsFromRows(explorer, rows, options);
        const selectedIds = getDocumentIdsFromRows(rows);
        const selectedCount = selectedIds.length;

        explorer.__selectedDocuments = docs;
        explorer.__selectedDocument = docs[0] || null;

        if (selectedCount) {
            explorer.setAttribute("data-document-selected", "true");
            explorer.setAttribute("data-document-selected-count", String(selectedCount));
        } else {
            explorer.removeAttribute("data-document-selected");
            explorer.setAttribute("data-document-selected-count", "0");
        }

        if (options?.markIntent !== false && selectedCount && Conversation && typeof Conversation.markFilesViewIntent === "function") {
            Conversation.markFilesViewIntent(explorer);
        }

        renderSelectionRail(explorer, docs, options);

        return docs;
    }

    function clearSelection(explorer, options) {
        getDocumentRows(explorer, options).forEach(function (row) {
            setDocumentRowSelected(row, false, options);
        });

        explorer.__selectedDocument = null;
        explorer.__selectedDocuments = [];
        explorer.removeAttribute("data-document-selected");
        explorer.setAttribute("data-document-selected-count", "0");

        renderSelectionRailEmpty(explorer, options);
    }

    window.SolomonWorkspaceDocumentSelection = Object.freeze({
        cleanValue,
        clearSelection,
        getActionDocumentPayload,
        getDocumentActionName,
        getDocumentActionRecord,
        getDocumentActionSelectionFromMenuItem,
        getDocumentIdsFromRows,
        getDocumentNamesByIds,
        getDocumentNamesFromRows,
        getDocumentRecordsByIds,
        getDocumentRecordsFromRows,
        getDocumentRows,
        getDocumentSelectionLabel,
        getFolderSelectionLabel,
        getSelectedDocumentRows,
        getSelectionRail,
        getSelectionRow,
        getSelectionSummaryName,
        getWorkspaceSelectionLabel,
        hasAnyDocumentInTrashContext,
        hasAnyDocumentOutsideTrashContext,
        isDocumentInTrashContext,
        isDocumentRecordTrashed,
        isFolderDocumentRecord,
        renderSelectionRail,
        renderSelectionRailEmpty,
        setDocumentRowSelected,
        setDocumentRowsSelectedByIds,
        setOnlyDocumentRowSelected,
        splitDocumentValueList,
        uniqueDocumentValues,
        updateExplorerSelectionFromRows
    });
})();