/* -------------------------------------------------------------------
   FILE: workspace_document_trash_mutations.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const DEFAULT_ACTIVE_DOCUMENTS_ENDPOINT = "/uploads/me";
    const DEFAULT_TRASH_DOCUMENTS_ENDPOINT = "/uploads/me/trash";
    const DEFAULT_RECENT_DOCUMENTS_ENDPOINT = DEFAULT_ACTIVE_DOCUMENTS_ENDPOINT;
    const DEFAULT_FOLDER_LIFECYCLE_ENDPOINT = "/uploads/me/folders";
    const MUTATION_REQUEST_TIMEOUT_MS = 20000;

    function cleanValue(value) {
        return String(value || "").trim();
    }

    function getRecordsApi(options) {
        return options?.Records || window.SolomonWorkspaceDocumentRecords || null;
    }

    function getStatusApi(options) {
        return options?.Status || window.SolomonWorkspaceDocumentStatus || null;
    }

    function getConfirmApi(options) {
        if (typeof options?.getConfirmApi === "function") {
            return options.getConfirmApi();
        }

        return window.SolomonUIConfirm || null;
    }

    function getEndpoint(explorer, key, options) {
        if (typeof options?.getEndpoint === "function") {
            const configuredEndpoint = cleanValue(
                options.getEndpoint(explorer, key)
            );

            if (configuredEndpoint) {
                return configuredEndpoint;
            }
        }

        if (!explorer) {
            return "";
        }

        if (key === "active") {
            return cleanValue(
                explorer.dataset.activeDocumentsEndpoint ||
                DEFAULT_ACTIVE_DOCUMENTS_ENDPOINT
            );
        }

        if (key === "trash") {
            return cleanValue(
                explorer.dataset.trashDocumentsEndpoint ||
                ""
            );
        }

        if (key === "recent") {
            return cleanValue(
                explorer.dataset.recentDocumentsEndpoint ||
                explorer.getAttribute("data-recent-documents-endpoint") ||
                ""
            );
        }

        if (key === "folders") {
            return cleanValue(
                explorer.dataset.workspaceFolderLifecycleEndpoint ||
                explorer.getAttribute("data-workspace-folder-lifecycle-endpoint") ||
                explorer.dataset.workspaceFolderCreateEndpoint ||
                explorer.getAttribute("data-workspace-folder-create-endpoint") ||
                DEFAULT_FOLDER_LIFECYCLE_ENDPOINT
            );
        }

        return "";
    }

    function normalizeDocumentSection(section, options) {
        if (typeof options?.normalizeDocumentSection === "function") {
            return options.normalizeDocumentSection(section);
        }

        return cleanValue(section).toLowerCase() || "files";
    }

    function getCurrentDocumentSection(explorer, options) {
        return normalizeDocumentSection(explorer?.getAttribute("data-workspace-section"), options);
    }

    function isTrashManagementSurface(explorer, options) {
        return getCurrentDocumentSection(explorer, options) === "trash";
    }

    function isTrashStateValue(value) {
        return [
            "trash",
            "trashed",
            "deleted"
        ].includes(
            cleanValue(value)
                .toLowerCase()
                .replace(/[-\s]+/g, "_")
        );
    }

    function isDocumentRecordInTrash(doc) {
        if (!doc || typeof doc !== "object") {
            return false;
        }

        if (
            doc.trashed === true ||
            doc.is_trashed === true ||
            doc.isTrashed === true
        ) {
            return true;
        }

        if (
            cleanValue(doc.trashed_at) ||
            cleanValue(doc.trashedAt)
        ) {
            return true;
        }

        return [
            doc.document_status,
            doc.documentStatus,
            doc.storage_status,
            doc.storageStatus,
            doc.library_status,
            doc.libraryStatus,
            doc.status,
            doc.action_context,
            doc.actionContext
        ].some(isTrashStateValue);
    }

    function getDocumentRowById(explorer, documentId) {
        const cleanId = cleanValue(documentId);

        if (!explorer || !cleanId) {
            return null;
        }

        const escapedId =
            window.CSS &&
            typeof window.CSS.escape === "function"
                ? window.CSS.escape(cleanId)
                : cleanId.replace(/"/g, '\\"');
        const candidate = explorer.querySelector([
            `[data-document-id="${escapedId}"]`,
            `[data-document-record-id="${escapedId}"]`,
            `[data-file-id="${escapedId}"]`,
            `[data-workspace-object-id="${escapedId}"]`
        ].join(","));

        if (!candidate) {
            return null;
        }

        return candidate.closest([
            "[data-document-list-row]",
            "[data-workspace-object-row]",
            "[data-document-row]",
            ".workspace-document-file-row",
            ".workspace-document-card",
            "[role='option']"
        ].join(",")) || candidate;
    }

    function isDocumentRowInTrash(row) {
        if (!row) {
            return false;
        }

        if (
            cleanValue(
                row.getAttribute("data-document-trashed")
            ).toLowerCase() === "true"
        ) {
            return true;
        }

        return [
            row.getAttribute("data-document-storage-status"),
            row.getAttribute("data-document-status"),
            row.getAttribute("data-document-action-context"),
            row.getAttribute("data-workspace-object-action-context"),
            row.getAttribute("data-document-menu-context")
        ].some(isTrashStateValue);
    }

    function getDocumentRecordById(
        explorer,
        documentId
    ) {
        const cleanId = cleanValue(documentId);

        if (!explorer || !cleanId) {
            return null;
        }

        const mappedRecord =
            explorer.__solomonDocumentById?.get?.(
                cleanId
            );

        if (mappedRecord) {
            return mappedRecord;
        }

        const selectedRecords = [
            explorer.__selectedDocument,
            ...(Array.isArray(
                explorer.__selectedDocuments
            )
                ? explorer.__selectedDocuments
                : [])
        ];

        return selectedRecords.find(function (doc) {
            return getRecordDocumentId(
                doc,
                {}
            ) === cleanId;
        }) || null;
    }

    function isWorkspaceFolderRecord(doc, options) {
        const Records = getRecordsApi(options);

        if (Records && typeof Records.isWorkspaceFolderRecord === "function") {
            return Records.isWorkspaceFolderRecord(doc);
        }

        const itemType = cleanValue(
            doc?.workspace_item_type ||
            doc?.item_type ||
            doc?.resource_type ||
            doc?.document_kind ||
            doc?.object_type ||
            doc?.kind
        ).toLowerCase();

        return Boolean(
            itemType === "folder" ||
            doc?.folder === true ||
            doc?.is_folder === true
        );
    }

    function isWorkspaceFolderId(explorer, objectId, options) {
        return isWorkspaceFolderRecord(
            getDocumentRecordById(explorer, objectId),
            options
        );
    }

    function isDocumentInTrashContext(
        explorer,
        documentId,
        options
    ) {
        if (
            getCurrentDocumentSection(
                explorer,
                options
            ) === "trash"
        ) {
            return true;
        }

        if (
            typeof options?.isDocumentInTrashContext ===
            "function"
        ) {
            try {
                if (
                    options.isDocumentInTrashContext(
                        explorer,
                        documentId
                    )
                ) {
                    return true;
                }
            } catch (error) {
                console.warn(
                    "[DOCUMENT_TRASH][CONTEXT_CHECK]",
                    error
                );
            }
        }

        const row = getDocumentRowById(
            explorer,
            documentId
        );

        if (isDocumentRowInTrash(row)) {
            return true;
        }

        return isDocumentRecordInTrash(
            getDocumentRecordById(
                explorer,
                documentId
            )
        );
    }

    function areAllDocumentsInTrashContext(
        explorer,
        documentIds,
        options
    ) {
        const ids = uniqueDocumentValues(
            documentIds
        );

        return Boolean(
            ids.length &&
            ids.every(function (documentId) {
                return isDocumentInTrashContext(
                    explorer,
                    documentId,
                    options
                );
            })
        );
    }

    function hasAnyDocumentInTrashContext(
        explorer,
        documentIds,
        options
    ) {
        return uniqueDocumentValues(
            documentIds
        ).some(function (documentId) {
            return isDocumentInTrashContext(
                explorer,
                documentId,
                options
            );
        });
    }

    function uniqueDocumentValues(values) {
        if (typeof values === "string") {
            return uniqueDocumentValues(values.split(","));
        }

        const seen = new Set();
        const cleanValues = [];

        (Array.isArray(values) ? values : []).forEach(function (value) {
            const clean = cleanValue(value);

            if (!clean || seen.has(clean)) {
                return;
            }

            seen.add(clean);
            cleanValues.push(clean);
        });

        return cleanValues;
    }

    function getDocumentNamesByIds(explorer, documentIds, options) {
        if (typeof options?.getDocumentNamesByIds === "function") {
            return uniqueDocumentValues(options.getDocumentNamesByIds(explorer, documentIds));
        }

        const ids = uniqueDocumentValues(documentIds);
        const names = [];

        ids.forEach(function (documentId) {
            const doc = explorer?.__solomonDocumentById?.get(documentId);

            if (doc?.original_name) {
                names.push(doc.original_name);
            }
        });

        return uniqueDocumentValues(names);
    }

    function getDocumentSelectionLabel(count, options) {
        if (typeof options?.getDocumentSelectionLabel === "function") {
            return cleanValue(options.getDocumentSelectionLabel(count));
        }

        return Number(count) === 1 ? "1 file" : `${Number(count) || 0} files`;
    }

    function getDocumentMutationSummaryName(documentIds, documentNames, options) {
        const ids = uniqueDocumentValues(documentIds);
        const names = uniqueDocumentValues(documentNames);

        if (ids.length > 1) {
            return getDocumentSelectionLabel(ids.length, options);
        }

        return names[0] || ids[0] || "File";
    }

    function buildMutationHeaders(headers) {
        return Object.assign({
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        }, headers || {});
    }

    function isAbortError(error) {
        return cleanValue(error?.name) === "AbortError";
    }

    async function fetchJson(url, options) {
        const controller = typeof AbortController === "function"
            ? new AbortController()
            : null;
        const timeoutId = controller
            ? window.setTimeout(function () {
                controller.abort();
            }, MUTATION_REQUEST_TIMEOUT_MS)
            : null;

        try {
            const response = await fetch(url, {
                method: options?.method || "GET",
                credentials: "same-origin",
                headers: buildMutationHeaders(options?.headers),
                body: options?.body || undefined,
                signal: controller ? controller.signal : undefined
            });
            const contentType = cleanValue(response.headers.get("content-type")).toLowerCase();

            if (!contentType.includes("application/json")) {
                throw new Error("The server returned an invalid document response.");
            }

            const payload = await response.json();

            if (!response.ok || payload.ok === false) {
                throw new Error(payload.user_output || payload.error || "Document request failed.");
            }

            return payload;
        } catch (error) {
            if (isAbortError(error)) {
                throw new Error("The document action timed out. Refresh Documents before trying again.");
            }

            throw error;
        } finally {
            if (timeoutId) {
                window.clearTimeout(timeoutId);
            }
        }
    }

    function showStatus(explorer, payload, options) {
        const Status = getStatusApi(options);

        if (typeof options?.showStatus === "function") {
            options.showStatus(explorer, payload);
            return;
        }

        if (Status && typeof Status.show === "function") {
            Status.show(explorer, payload);
        }
    }

    function isTrashMutationBusy(explorer) {
        return explorer?.__solomonDocumentTrashMutationInFlight === true;
    }

    function beginTrashMutation(explorer, action, documentIds, options) {
        if (!explorer) {
            return false;
        }

        if (isTrashMutationBusy(explorer)) {
            showStatus(explorer, {
                action: action || "document_mutation",
                documentIds: uniqueDocumentValues(documentIds),
                variant: "info",
                message: "Document action already in progress."
            }, options);
            return false;
        }

        explorer.__solomonDocumentTrashMutationInFlight = true;
        explorer.setAttribute("data-document-explorer-loading", "true");

        return true;
    }

    function endTrashMutation(explorer) {
        if (!explorer) {
            return;
        }

        explorer.__solomonDocumentTrashMutationInFlight = false;
        explorer.removeAttribute("data-document-explorer-loading");
    }

    function yieldToBrowser() {
        return new Promise(function (resolve) {
            window.setTimeout(resolve, 0);
        });
    }

    function buildTrashDocumentsEndpoint(explorer, options) {
        const configuredEndpoint = getEndpoint(explorer, "trash", options);

        if (configuredEndpoint) {
            return configuredEndpoint;
        }

        const activeEndpoint = getEndpoint(explorer, "active", options) || DEFAULT_ACTIVE_DOCUMENTS_ENDPOINT;
        const cleanEndpoint = cleanValue(activeEndpoint).replace(/\/+$/, "");

        if (!cleanEndpoint) {
            return DEFAULT_TRASH_DOCUMENTS_ENDPOINT;
        }

        if (cleanEndpoint.endsWith("/trash")) {
            return cleanEndpoint;
        }

        return `${cleanEndpoint}/trash`;
    }

    function buildRecentDocumentsEndpoint(explorer, options) {
        const configuredEndpoint = getEndpoint(explorer, "recent", options);

        if (configuredEndpoint) {
            return configuredEndpoint;
        }

        return (
            getEndpoint(explorer, "active", options) ||
            DEFAULT_RECENT_DOCUMENTS_ENDPOINT
        );
    }

    function getDocumentSectionEndpoint(explorer, section, options) {
        const cleanSection = normalizeDocumentSection(section, options);

        if (cleanSection === "trash") {
            return buildTrashDocumentsEndpoint(explorer, options);
        }

        if (cleanSection === "recent") {
            return buildRecentDocumentsEndpoint(explorer, options);
        }

        if (cleanSection === "files" || cleanSection === "shared") {
            return getEndpoint(explorer, "active", options) || DEFAULT_ACTIVE_DOCUMENTS_ENDPOINT;
        }

        return "";
    }

    function buildMoveToTrashEndpoint(explorer, documentId, options) {
        const baseEndpoint = getEndpoint(explorer, "active", options) || DEFAULT_ACTIVE_DOCUMENTS_ENDPOINT;
        const cleanBase = cleanValue(baseEndpoint).replace(/\/+$/, "");
        const cleanId = cleanValue(documentId);

        if (!cleanId) {
            return "";
        }

        return `${cleanBase}/${encodeURIComponent(cleanId)}`;
    }

    function buildTrashDocumentEndpoint(explorer, documentId, options) {
        const trashEndpoint = buildTrashDocumentsEndpoint(explorer, options);
        const cleanBase = cleanValue(trashEndpoint).replace(/\/+$/, "");
        const cleanId = cleanValue(documentId);

        if (!cleanBase || !cleanId) {
            return "";
        }

        return `${cleanBase}/${encodeURIComponent(cleanId)}`;
    }

    function buildRestoreFromTrashEndpoint(explorer, documentId, options) {
        const trashDocumentEndpoint = buildTrashDocumentEndpoint(explorer, documentId, options);

        if (!trashDocumentEndpoint) {
            return "";
        }

        return `${trashDocumentEndpoint}/restore`;
    }

    function buildPermanentDeleteEndpoint(explorer, documentId, options) {
        return buildTrashDocumentEndpoint(explorer, documentId, options);
    }

    function buildMoveFolderToTrashEndpoint(explorer, folderId, options) {
        const baseEndpoint = getEndpoint(explorer, "folders", options) || DEFAULT_FOLDER_LIFECYCLE_ENDPOINT;
        const cleanBase = cleanValue(baseEndpoint).replace(/\/+$/, "");
        const cleanId = cleanValue(folderId);

        if (!cleanBase || !cleanId) {
            return "";
        }

        return `${cleanBase}/${encodeURIComponent(cleanId)}`;
    }

    function buildTrashFolderEndpoint(explorer, folderId, options) {
        const baseEndpoint = getEndpoint(explorer, "folders", options) || DEFAULT_FOLDER_LIFECYCLE_ENDPOINT;
        const cleanBase = cleanValue(baseEndpoint).replace(/\/+$/, "");
        const cleanId = cleanValue(folderId);

        if (!cleanBase || !cleanId) {
            return "";
        }

        return `${cleanBase}/trash/${encodeURIComponent(cleanId)}`;
    }

    function buildRestoreFolderEndpoint(explorer, folderId, options) {
        const endpoint = buildTrashFolderEndpoint(explorer, folderId, options);

        return endpoint ? `${endpoint}/restore` : "";
    }

    function buildPermanentDeleteFolderEndpoint(explorer, folderId, options) {
        return buildTrashFolderEndpoint(explorer, folderId, options);
    }

    function getSuppressedTrashDocumentIds(explorer) {
        if (!explorer.__solomonSuppressedTrashDocumentIds) {
            explorer.__solomonSuppressedTrashDocumentIds = new Set();
        }

        return explorer.__solomonSuppressedTrashDocumentIds;
    }

    function getOptimisticTrashDocuments(explorer) {
        if (!explorer.__solomonOptimisticTrashDocuments) {
            explorer.__solomonOptimisticTrashDocuments = new Map();
        }

        return explorer.__solomonOptimisticTrashDocuments;
    }

    function suppressDocumentInTrash(explorer, documentId) {
        const cleanId = cleanValue(documentId);

        if (!cleanId) {
            return;
        }

        getSuppressedTrashDocumentIds(explorer).add(cleanId);
        getOptimisticTrashDocuments(explorer).delete(cleanId);
    }

    function unsuppressDocumentInTrash(explorer, documentId) {
        const cleanId = cleanValue(documentId);

        if (!cleanId) {
            return;
        }

        getSuppressedTrashDocumentIds(explorer).delete(cleanId);
    }

    function getRecordDocumentId(doc, options) {
        const Records = getRecordsApi(options);

        if (Records && typeof Records.getDocumentId === "function") {
            return cleanValue(Records.getDocumentId(doc));
        }

        return cleanValue(doc?.document_id || doc?.random_name || doc?.file_id);
    }

    function normalizeDocument(doc, options) {
        const Records = getRecordsApi(options);

        if (Records && typeof Records.normalizeDocument === "function") {
            return Records.normalizeDocument(doc || {});
        }

        return doc || {};
    }

    function shouldSuppressTrashDocument(explorer, doc, options) {
        const documentId = getRecordDocumentId(doc, options);

        if (!documentId) {
            return false;
        }

        return getSuppressedTrashDocumentIds(explorer).has(documentId);
    }

    function buildOptimisticTrashDocument(explorer, documentId, payload, options) {
        const cleanId = cleanValue(documentId);
        const storedDoc = cleanId ? explorer?.__solomonDocumentById?.get(cleanId) : null;
        const selectedDoc = explorer?.__selectedDocument?.document_id === cleanId
            ? explorer.__selectedDocument
            : null;
        const sourceDoc = storedDoc || selectedDoc || {};
        const movedPayload = payload?.moved_to_trash || payload?.deleted || {};
        const normalizedDoc = normalizeDocument(sourceDoc, options);
        const originalName = (
            sourceDoc.original_name ||
            movedPayload.original_name ||
            normalizedDoc.original_name ||
            cleanId
        );

        return Object.assign({}, sourceDoc, {
            document_id: cleanId,
            random_name: sourceDoc.random_name || movedPayload.document_id || cleanId,
            file_id: sourceDoc.file_id || movedPayload.file_id || "",
            original_name: originalName,
            active: false,
            selected_for_workflow: false,
            trashed: true,
            document_status: "trash",
            trashed_at: movedPayload.trashed_at || sourceDoc.trashed_at || new Date().toISOString(),
            workflow_status: sourceDoc.workflow_status || normalizedDoc.workflow_status || "not_started",
            analysis_status: sourceDoc.analysis_status || normalizedDoc.analysis_status || "not_started",
            reader_url: sourceDoc.reader_url || normalizedDoc.reader_url || "",
            workspace_reader_url: sourceDoc.workspace_reader_url || normalizedDoc.workspace_reader_url || ""
        });
    }

    function getCachedDocumentSection(explorer, section, options) {
        if (typeof options?.getCachedDocumentSection === "function") {
            return options.getCachedDocumentSection(explorer, section);
        }

        return [];
    }

    function setCachedDocumentSection(explorer, section, docs, options) {
        if (typeof options?.setCachedDocumentSection === "function") {
            options.setCachedDocumentSection(explorer, section, docs);
        }
    }

    function upsertDocumentInCachedSection(explorer, section, doc, options) {
        const cleanSection = normalizeDocumentSection(section, options);
        const documentId = getRecordDocumentId(doc, options);
        const cachedDocs = getCachedDocumentSection(explorer, cleanSection, options) || [];
        const nextDocs = [];
        let inserted = false;

        if (!documentId) {
            return;
        }

        cachedDocs.forEach(function (cachedDoc) {
            if (getRecordDocumentId(cachedDoc, options) === documentId) {
                if (!inserted) {
                    nextDocs.push(doc);
                    inserted = true;
                }

                return;
            }

            nextDocs.push(cachedDoc);
        });

        if (!inserted) {
            nextDocs.unshift(doc);
        }

        setCachedDocumentSection(explorer, cleanSection, nextDocs, options);
    }

    function rememberDocumentInTrash(explorer, doc, options) {
        const documentId = getRecordDocumentId(doc, options);

        if (!documentId) {
            return;
        }

        unsuppressDocumentInTrash(explorer, documentId);
        getOptimisticTrashDocuments(explorer).set(documentId, doc);
        upsertDocumentInCachedSection(explorer, "trash", doc, options);
    }

    function mergeTrashDocumentsForRender(explorer, docs, options) {
        const mergedById = new Map();
        const optimisticDocs = getOptimisticTrashDocuments(explorer);

        optimisticDocs.forEach(function (doc, documentId) {
            if (!shouldSuppressTrashDocument(explorer, doc, options)) {
                mergedById.set(documentId, doc);
            }
        });

        (Array.isArray(docs) ? docs : []).forEach(function (doc) {
            const documentId = getRecordDocumentId(doc, options);

            if (!documentId || shouldSuppressTrashDocument(explorer, doc, options)) {
                return;
            }

            if (optimisticDocs.has(documentId)) {
                optimisticDocs.delete(documentId);
            }

            mergedById.set(documentId, doc);
        });

        return Array.from(mergedById.values());
    }

    function invalidateDocumentSectionCache(explorer, section, options) {
        if (typeof options?.invalidateDocumentSectionCache === "function") {
            options.invalidateDocumentSectionCache(explorer, section);
        }
    }

    function invalidateDocumentSectionCaches(explorer, sections, options) {
        uniqueDocumentValues(sections).forEach(function (section) {
            invalidateDocumentSectionCache(explorer, section, options);
        });
    }

    function removeDocumentRowsFromDom(explorer, documentIds) {
        const ids = uniqueDocumentValues(documentIds);

        if (!explorer || !ids.length) {
            return;
        }

        ids.forEach(function (documentId) {
            const escapedId = window.CSS && typeof window.CSS.escape === "function"
                ? window.CSS.escape(documentId)
                : documentId.replace(/"/g, '\\"');

            const candidates = explorer.querySelectorAll([
                `[data-document-id="${escapedId}"]`,
                `[data-document-row][data-document-id="${escapedId}"]`,
                `[data-document-record-id="${escapedId}"]`,
                `[data-file-id="${escapedId}"]`
            ].join(","));

            candidates.forEach(function (candidate) {
                const row = candidate.closest(
                    "[data-document-row], .workspace-document-file-row, .workspace-document-card, [role='option']"
                ) || candidate;

                if (row && row.parentNode) {
                    row.parentNode.removeChild(row);
                }
            });
        });
    }

    function removeDocumentRowsFromCurrentView(explorer, documentIds, section, options) {
        if (typeof options?.removeDocumentRowsFromCurrentView === "function") {
            options.removeDocumentRowsFromCurrentView(explorer, documentIds, section);
            return;
        }

        removeDocumentRowsFromDom(explorer, documentIds);
    }

    function renderPreviewEmpty(explorer, options) {
        if (typeof options?.renderPreviewEmpty === "function") {
            options.renderPreviewEmpty(explorer);
        }
    }

    function renderDeleteConfirmation(explorer, doc, options) {
        if (typeof options?.renderDeleteConfirmation === "function") {
            options.renderDeleteConfirmation(explorer, doc);
        }
    }

    function refreshAfterDocumentMutation(explorer, section, options) {
        const cleanSection = normalizeDocumentSection(
            section || getCurrentDocumentSection(explorer, options),
            options
        );

        if (typeof options?.refreshAfterDocumentMutation === "function") {
            return options.refreshAfterDocumentMutation(explorer, cleanSection, {
                quiet: true
            });
        }

        return Promise.resolve(null);
    }

    function extractPayloadDocuments(payload) {
        const candidateLists = [
            payload?.workspace_items,
            payload?.items,
            payload?.documents,
            payload?.uploads,
            payload?.files,
            payload?.rows,
            payload?.trash,
            payload?.data?.workspace_items,
            payload?.data?.items,
            payload?.data?.documents,
            payload?.data?.uploads,
            payload?.data?.files,
            payload?.data?.rows,
            payload?.data?.trash
        ];

        for (const candidateList of candidateLists) {
            if (Array.isArray(candidateList)) {
                return candidateList;
            }
        }

        if (Array.isArray(payload)) {
            return payload;
        }

        return [];
    }

    async function fetchTrashDocuments(explorer, options) {
        const endpoint = buildTrashDocumentsEndpoint(explorer, options);

        if (!endpoint) {
            throw new Error("Unable to locate the Trash endpoint.");
        }

        const payload = await fetchJson(endpoint, {
            method: "GET"
        });

        return extractPayloadDocuments(payload)
            .map(function (doc) {
                return normalizeDocument(doc, options);
            })
            .filter(function (doc) {
                return Boolean(getRecordDocumentId(doc, options));
            });
    }

    function getCachedTrashDocumentIds(explorer, options) {
        const cachedTrashDocs = getCachedDocumentSection(explorer, "trash", options) || [];
        const ids = [];

        cachedTrashDocs.forEach(function (doc) {
            const documentId = getRecordDocumentId(doc, options);

            if (documentId) {
                ids.push(documentId);
            }
        });

        return uniqueDocumentValues(ids);
    }

    function getVisibleTrashDocumentIds(explorer) {
        const ids = [];

        if (!explorer) {
            return ids;
        }

        explorer.querySelectorAll("[data-document-id], [data-document-record-id], [data-file-id]").forEach(function (node) {
            const documentId = cleanValue(
                node.getAttribute("data-document-id") ||
                node.getAttribute("data-document-record-id") ||
                node.getAttribute("data-file-id")
            );

            if (documentId) {
                ids.push(documentId);
            }
        });

        return uniqueDocumentValues(ids);
    }

    async function getTrashDocumentIdsForEmptyTrash(explorer, options) {
        try {
            const serverTrashDocs = await fetchTrashDocuments(explorer, options);
            const serverIds = serverTrashDocs.map(function (doc) {
                return getRecordDocumentId(doc, options);
            });

            return uniqueDocumentValues(serverIds);
        } catch (error) {
            console.warn("[DOCUMENT_TRASH][EMPTY_FETCH_FALLBACK]", error);
        }

        const cachedIds = getCachedTrashDocumentIds(explorer, options);

        if (cachedIds.length) {
            return cachedIds;
        }

        return getVisibleTrashDocumentIds(explorer);
    }

    async function moveDocumentToTrash(explorer, documentId, options) {
        const endpoint = buildMoveToTrashEndpoint(explorer, documentId, options);

        if (!endpoint) {
            throw new Error("Unable to locate the document trash endpoint.");
        }

        return fetchJson(endpoint, {
            method: "DELETE"
        });
    }

    async function restoreSingleDocumentFromTrash(explorer, documentId, options) {
        const endpoint = buildRestoreFromTrashEndpoint(explorer, documentId, options);

        if (!endpoint) {
            throw new Error("Unable to locate the document restore endpoint.");
        }

        return fetchJson(endpoint, {
            method: "POST"
        });
    }

    async function permanentlyDeleteDocument(explorer, documentId, options) {
        const endpoint = buildPermanentDeleteEndpoint(explorer, documentId, options);

        if (!endpoint) {
            throw new Error("Unable to locate the permanent delete endpoint.");
        }

        return fetchJson(endpoint, {
            method: "DELETE"
        });
    }

    async function moveFolderToTrash(explorer, folderId, options) {
        const endpoint = buildMoveFolderToTrashEndpoint(explorer, folderId, options);

        if (!endpoint) {
            throw new Error("Unable to locate the folder trash endpoint.");
        }

        return fetchJson(endpoint, {
            method: "DELETE"
        });
    }

    async function restoreSingleFolderFromTrash(explorer, folderId, options) {
        const endpoint = buildRestoreFolderEndpoint(explorer, folderId, options);

        if (!endpoint) {
            throw new Error("Unable to locate the folder restore endpoint.");
        }

        return fetchJson(endpoint, {
            method: "POST"
        });
    }

    async function permanentlyDeleteFolder(explorer, folderId, options) {
        const endpoint = buildPermanentDeleteFolderEndpoint(explorer, folderId, options);

        if (!endpoint) {
            throw new Error("Unable to locate the folder permanent-delete endpoint.");
        }

        return fetchJson(endpoint, {
            method: "DELETE"
        });
    }

    function dispatchWorkspaceFolderMutation(explorer, detail) {
        explorer?.dispatchEvent?.(new CustomEvent("solomon:workspace-folder-mutated", {
            bubbles: true,
            detail: detail || {}
        }));
    }

    async function moveFoldersToTrash(explorer, folderIds, options) {
        const ids = uniqueDocumentValues(folderIds);
        const names = getDocumentNamesByIds(explorer, ids, options);
        const summaryName = getDocumentMutationSummaryName(ids, names, options);
        const currentSection = getCurrentDocumentSection(explorer, options);

        for (const folderId of ids) {
            const payload = await moveFolderToTrash(explorer, folderId, options);

            removeDocumentRowsFromCurrentView(
                explorer,
                [folderId],
                currentSection,
                options
            );
            dispatchWorkspaceFolderMutation(explorer, {
                action: "move_to_trash",
                folderId,
                payload,
                section: currentSection
            });
            await yieldToBrowser();
        }

        invalidateDocumentSectionCaches(explorer, ["files", "shared", "trash"], options);
        showStatus(explorer, {
            action: "delete",
            documentIds: ids,
            variant: "success",
            message: ids.length > 1
                ? `${summaryName} moved to Trash.`
                : "Folder moved to Trash."
        }, options);
    }

    async function moveDocumentsToTrash(explorer, documentIds, options) {
        const ids = uniqueDocumentValues(documentIds);
        const movedNames = getDocumentNamesByIds(explorer, ids, options);
        const movedLabel = getDocumentMutationSummaryName(ids, movedNames, options);
        const currentSection = getCurrentDocumentSection(explorer, options);

        if (!ids.length) {
            return;
        }

        for (const documentId of ids) {
            const payload = await moveDocumentToTrash(explorer, documentId, options);
            const optimisticDoc = buildOptimisticTrashDocument(explorer, documentId, payload, options);

            rememberDocumentInTrash(explorer, optimisticDoc, options);
            removeDocumentRowsFromCurrentView(
                explorer,
                [documentId],
                currentSection === "recent" ? "recent" : "files",
                options
            );
            await yieldToBrowser();
        }

        invalidateDocumentSectionCaches(explorer, ["files", "recent", "trash"], options);

        showStatus(explorer, {
            action: "delete",
            documentIds: ids,
            variant: "success",
            message: ids.length > 1
                ? `${movedLabel} moved to Trash.`
                : "File moved to Trash."
        }, options);
    }

    async function restoreDocumentFromTrash(explorer, documentIds, options) {
        const ids = uniqueDocumentValues(documentIds);
        const restoredNames = getDocumentNamesByIds(explorer, ids, options);
        const restoredLabel = getDocumentMutationSummaryName(ids, restoredNames, options);
        const currentSection = getCurrentDocumentSection(explorer, options);

        if (!ids.length) {
            return;
        }

        if (!isTrashManagementSurface(
            explorer,
            options
        )) {
            showStatus(explorer, {
                action: "restore",
                documentIds: ids,
                variant: "info",
                message: "Restore is only available from Trash."
            }, options);
            return;
        }

        if (!areAllDocumentsInTrashContext(
            explorer,
            ids,
            options
        )) {
            showStatus(explorer, {
                action: "restore",
                documentIds: ids,
                variant: "info",
                message: "Only files in Trash can be restored."
            }, options);
            return;
        }

        if (!beginTrashMutation(explorer, "restore", ids, options)) {
            return;
        }

        try {
            for (const documentId of ids) {
                await restoreSingleDocumentFromTrash(explorer, documentId, options);
                suppressDocumentInTrash(explorer, documentId);
                removeDocumentRowsFromCurrentView(
                    explorer,
                    [documentId],
                    currentSection,
                    options
                );
                await yieldToBrowser();
            }

            invalidateDocumentSectionCaches(explorer, ["trash", "files", "recent"], options);

            showStatus(explorer, {
                action: "restore",
                documentIds: ids,
                variant: "success",
                message: ids.length > 1
                    ? `${restoredLabel} restored to My Files.`
                    : "File restored to My Files."
            }, options);
        } catch (error) {
            console.error("[DOCUMENT_TRASH][RESTORE]", error);
            showStatus(explorer, {
                action: "restore",
                documentIds: ids,
                variant: "error",
                message: error.message || "Unable to restore file."
            }, options);
        } finally {
            endTrashMutation(explorer);
        }
    }

    async function restoreFoldersFromTrash(explorer, folderIds, options) {
        const ids = uniqueDocumentValues(folderIds);
        const names = getDocumentNamesByIds(explorer, ids, options);
        const summaryName = getDocumentMutationSummaryName(ids, names, options);
        const currentSection = getCurrentDocumentSection(explorer, options);

        if (!ids.length) {
            return;
        }

        if (!isTrashManagementSurface(explorer, options)) {
            showStatus(explorer, {
                action: "restore",
                documentIds: ids,
                variant: "info",
                message: "Folder restore is only available from Trash."
            }, options);
            return;
        }

        if (!beginTrashMutation(explorer, "restore", ids, options)) {
            return;
        }

        try {
            for (const folderId of ids) {
                const payload = await restoreSingleFolderFromTrash(explorer, folderId, options);

                removeDocumentRowsFromCurrentView(
                    explorer,
                    [folderId],
                    currentSection,
                    options
                );
                dispatchWorkspaceFolderMutation(explorer, {
                    action: "restore",
                    folderId,
                    payload,
                    section: currentSection
                });
                await yieldToBrowser();
            }

            invalidateDocumentSectionCaches(explorer, ["trash", "files", "shared"], options);
            showStatus(explorer, {
                action: "restore",
                documentIds: ids,
                variant: "success",
                message: ids.length > 1
                    ? `${summaryName} restored.`
                    : "Folder restored."
            }, options);
        } catch (error) {
            console.error("[DOCUMENT_TRASH][FOLDER_RESTORE]", error);
            showStatus(explorer, {
                action: "restore",
                documentIds: ids,
                variant: "error",
                message: error.message || "Unable to restore folder."
            }, options);
        } finally {
            endTrashMutation(explorer);
        }
    }

    async function permanentlyDeleteFolders(explorer, folderIds, options) {
        const ids = uniqueDocumentValues(folderIds);
        const names = getDocumentNamesByIds(explorer, ids, options);
        const summaryName = getDocumentMutationSummaryName(ids, names, options);

        for (const folderId of ids) {
            const payload = await permanentlyDeleteFolder(explorer, folderId, options);

            removeDocumentRowsFromCurrentView(explorer, [folderId], "trash", options);
            dispatchWorkspaceFolderMutation(explorer, {
                action: "permanent_delete",
                folderId,
                payload,
                section: "trash"
            });
            await yieldToBrowser();
        }

        invalidateDocumentSectionCaches(explorer, ["trash", "files", "shared"], options);
        showStatus(explorer, {
            action: "permanent_delete",
            documentIds: ids,
            variant: "success",
            message: ids.length > 1
                ? `${summaryName} permanently deleted.`
                : "Folder permanently deleted."
        }, options);
    }

    async function permanentlyDeleteDocuments(explorer, documentIds, options) {
        const ids = uniqueDocumentValues(documentIds);
        const deletedNames = getDocumentNamesByIds(explorer, ids, options);
        const deletedLabel = getDocumentMutationSummaryName(ids, deletedNames, options);

        if (!ids.length) {
            return;
        }

        for (const documentId of ids) {
            await permanentlyDeleteDocument(explorer, documentId, options);
            suppressDocumentInTrash(explorer, documentId);
            removeDocumentRowsFromCurrentView(explorer, [documentId], "trash", options);
            await yieldToBrowser();
        }

        invalidateDocumentSectionCaches(explorer, ["trash", "recent"], options);

        showStatus(explorer, {
            action: "permanent_delete",
            documentIds: ids,
            variant: "success",
            message: ids.length > 1
                ? `${deletedLabel} permanently deleted.`
                : "File permanently deleted."
        }, options);
    }

    async function emptyTrashDocuments(explorer, documentIds, options) {
        const ids = uniqueDocumentValues(documentIds);

        if (!ids.length) {
            return;
        }

        for (const documentId of ids) {
            if (isWorkspaceFolderId(explorer, documentId, options)) {
                await permanentlyDeleteFolder(explorer, documentId, options);
                dispatchWorkspaceFolderMutation(explorer, {
                    action: "permanent_delete",
                    folderId: documentId,
                    section: "trash"
                });
            } else {
                await permanentlyDeleteDocument(explorer, documentId, options);
                suppressDocumentInTrash(explorer, documentId);
            }

            removeDocumentRowsFromCurrentView(explorer, [documentId], "trash", options);
            await yieldToBrowser();
        }

        getOptimisticTrashDocuments(explorer).clear();
        invalidateDocumentSectionCaches(explorer, ["trash", "recent"], options);
        await refreshAfterDocumentMutation(explorer, "trash", options);

        showStatus(explorer, {
            action: "empty_trash",
            documentIds: ids,
            variant: "success",
            message: ids.length === 1
                ? "Trash emptied. 1 item permanently deleted."
                : `Trash emptied. ${ids.length} items permanently deleted.`
        }, options);
    }

    function runConfirmApiMethod(confirmApi, methodName, options) {
        if (!confirmApi || typeof confirmApi[methodName] !== "function") {
            return null;
        }

        return new Promise(function (resolve) {
            let settled = false;

            function finish(value) {
                if (settled) {
                    return;
                }

                settled = true;
                resolve(Boolean(value));
            }

            try {
                const result = confirmApi[methodName](Object.assign({}, options || {}, {
                    onConfirm: function () {
                        finish(true);
                    },
                    onCancel: function () {
                        finish(false);
                    }
                }));

                if (result && typeof result.then === "function") {
                    result.then(function (value) {
                        finish(value !== false);
                    }).catch(function () {
                        finish(false);
                    });
                    return;
                }

                if (typeof result === "boolean") {
                    finish(result);
                }
            } catch (error) {
                console.error("[DOCUMENT_TRASH][CONFIRM]", error);
                finish(false);
            }
        });
    }

    async function confirmDocumentMutation(confirmOptions, options) {
        const confirmApi = getConfirmApi(options);
        const cleanOptions = confirmOptions || {};
        const methodOrder = ["confirm", "open", "show"];

        for (const methodName of methodOrder) {
            const result = runConfirmApiMethod(confirmApi, methodName, cleanOptions);

            if (result) {
                return result;
            }
        }

        showStatus(null, {
            action: "confirm",
            variant: "error",
            message: "Confirmation UI is unavailable."
        }, options);

        return false;
    }

    async function requestMoveDocumentToTrash(explorer, documentIds, options) {
        const ids = uniqueDocumentValues(documentIds);

        if (!ids.length) {
            return;
        }

        if (hasAnyDocumentInTrashContext(
            explorer,
            ids,
            options
        )) {
            showStatus(explorer, {
                action: "delete",
                documentIds: ids,
                variant: "info",
                message: ids.length > 1
                    ? "One or more selected files are already in Trash."
                    : "This file is already in Trash."
            }, options);
            return;
        }

        if (!beginTrashMutation(explorer, "delete", ids, options)) {
            return;
        }

        try {
            await moveDocumentsToTrash(explorer, ids, options);
        } catch (error) {
            console.error("[DOCUMENT_TRASH][REQUEST_MOVE]", error);
            showStatus(explorer, {
                action: "delete",
                documentIds: ids,
                variant: "error",
                message: error.message || "Unable to move file to Trash."
            }, options);
        } finally {
            endTrashMutation(explorer);
        }
    }

    async function requestMoveFolderToTrash(explorer, folderIds, options) {
        const ids = uniqueDocumentValues(folderIds);

        if (!ids.length || !beginTrashMutation(explorer, "delete", ids, options)) {
            return;
        }

        try {
            await moveFoldersToTrash(explorer, ids, options);
        } catch (error) {
            console.error("[DOCUMENT_TRASH][FOLDER_MOVE]", error);
            showStatus(explorer, {
                action: "delete",
                documentIds: ids,
                variant: "error",
                message: error.message || "Unable to move folder to Trash."
            }, options);
        } finally {
            endTrashMutation(explorer);
        }
    }

    async function requestPermanentDeleteFolder(explorer, folderIds, options) {
        const ids = uniqueDocumentValues(folderIds);
        const names = getDocumentNamesByIds(explorer, ids, options);
        const summaryName = getDocumentMutationSummaryName(ids, names, options);

        if (!ids.length) {
            return;
        }

        if (!isTrashManagementSurface(explorer, options)) {
            showStatus(explorer, {
                action: "permanent_delete",
                documentIds: ids,
                variant: "info",
                message: "Delete forever is only available from Trash."
            }, options);
            return;
        }

        const confirmed = await confirmDocumentMutation({
            title: ids.length > 1 ? "Permanently delete selected folders?" : "Permanently delete folder?",
            message: `${summaryName} will be permanently deleted. This cannot be undone.`,
            confirmLabel: "Delete forever",
            cancelLabel: "Cancel",
            danger: true
        }, options);

        if (!confirmed) {
            showStatus(explorer, {
                action: "permanent_delete",
                documentIds: ids,
                variant: "info",
                message: "Permanent delete cancelled."
            }, options);
            return;
        }

        if (!beginTrashMutation(explorer, "permanent_delete", ids, options)) {
            return;
        }

        try {
            await permanentlyDeleteFolders(explorer, ids, options);
        } catch (error) {
            console.error("[DOCUMENT_TRASH][FOLDER_PERMANENT_DELETE]", error);
            showStatus(explorer, {
                action: "permanent_delete",
                documentIds: ids,
                variant: "error",
                message: error.message || "Unable to permanently delete folder."
            }, options);
        } finally {
            endTrashMutation(explorer);
        }
    }

    async function requestPermanentDeleteDocument(explorer, documentIds, options) {
        const ids = uniqueDocumentValues(documentIds);
        const names = getDocumentNamesByIds(explorer, ids, options);
        const summaryName = getDocumentMutationSummaryName(ids, names, options);

        if (!ids.length) {
            return;
        }

        if (!isTrashManagementSurface(
            explorer,
            options
        )) {
            showStatus(explorer, {
                action: "permanent_delete",
                documentIds: ids,
                variant: "info",
                message: "Delete forever is only available from Trash."
            }, options);
            return;
        }

        if (!areAllDocumentsInTrashContext(
            explorer,
            ids,
            options
        )) {
            showStatus(explorer, {
                action: "permanent_delete",
                documentIds: ids,
                variant: "info",
                message: "Only files in Trash can be permanently deleted."
            }, options);
            return;
        }

        const confirmed = await confirmDocumentMutation({
            title: ids.length > 1 ? "Permanently delete selected files?" : "Permanently delete file?",
            message: `${summaryName} will be permanently deleted. This cannot be undone.`,
            confirmLabel: "Delete forever",
            cancelLabel: "Cancel",
            danger: true
        }, options);

        if (!confirmed) {
            showStatus(explorer, {
                action: "permanent_delete",
                documentIds: ids,
                variant: "info",
                message: "Permanent delete cancelled."
            }, options);
            return;
        }

        if (!beginTrashMutation(explorer, "permanent_delete", ids, options)) {
            return;
        }

        try {
            await permanentlyDeleteDocuments(explorer, ids, options);
        } catch (error) {
            console.error("[DOCUMENT_TRASH][REQUEST_PERMANENT_DELETE]", error);
            showStatus(explorer, {
                action: "permanent_delete",
                documentIds: ids,
                variant: "error",
                message: error.message || "Unable to permanently delete file."
            }, options);
        } finally {
            endTrashMutation(explorer);
        }
    }

    async function requestEmptyTrash(explorer, options) {
        if (!explorer) {
            return;
        }

        if (getCurrentDocumentSection(explorer, options) !== "trash") {
            showStatus(explorer, {
                action: "empty_trash",
                variant: "info",
                message: "Empty Trash is only available from Trash."
            }, options);
            return;
        }

        if (isTrashMutationBusy(explorer)) {
            showStatus(explorer, {
                action: "empty_trash",
                variant: "info",
                message: "Document action already in progress."
            }, options);
            return;
        }

        let ids = [];

        try {
            ids = await getTrashDocumentIdsForEmptyTrash(explorer, options);
        } catch (error) {
            console.error("[DOCUMENT_TRASH][EMPTY_LIST]", error);
            showStatus(explorer, {
                action: "empty_trash",
                variant: "error",
                message: error.message || "Unable to inspect Trash before emptying it."
            }, options);
            return;
        }

        ids = uniqueDocumentValues(ids);

        if (!ids.length) {
            showStatus(explorer, {
                action: "empty_trash",
                variant: "info",
                message: "Trash is already empty."
            }, options);
            return;
        }

        const confirmed = await confirmDocumentMutation({
            title: "Empty Trash?",
            message: ids.length === 1
                ? "1 item will be permanently deleted. This cannot be undone."
                : `${ids.length} items will be permanently deleted. This cannot be undone.`,
            confirmLabel: "Empty Trash",
            cancelLabel: "Cancel",
            danger: true
        }, options);

        if (!confirmed) {
            showStatus(explorer, {
                action: "empty_trash",
                documentIds: ids,
                variant: "info",
                message: "Empty Trash cancelled."
            }, options);
            return;
        }

        if (!beginTrashMutation(explorer, "empty_trash", ids, options)) {
            return;
        }

        try {
            await emptyTrashDocuments(explorer, ids, options);
        } catch (error) {
            console.error("[DOCUMENT_TRASH][REQUEST_EMPTY]", error);
            showStatus(explorer, {
                action: "empty_trash",
                documentIds: ids,
                variant: "error",
                message: error.message || "Unable to empty Trash."
            }, options);
        } finally {
            endTrashMutation(explorer);
        }
    }

    function findExplorerFromNode(node) {
        if (!node || typeof node.closest !== "function") {
            return null;
        }

        return node.closest("[data-document-explorer]");
    }

    function handleEmptyTrashTriggerClick(event) {
        const trigger = event.target?.closest?.("[data-document-empty-trash-trigger]");

        if (!trigger || event.__solomonEmptyTrashHandled) {
            return;
        }

        const explorer = findExplorerFromNode(trigger);

        if (!explorer) {
            return;
        }

        event.__solomonEmptyTrashHandled = true;
        event.preventDefault();
        requestEmptyTrash(explorer, {});
    }

    function bindEmptyTrashControls(root) {
        const cleanRoot = root && typeof root.addEventListener === "function"
            ? root
            : document;

        if (cleanRoot.__solomonEmptyTrashControlsBound === true) {
            return;
        }

        cleanRoot.__solomonEmptyTrashControlsBound = true;
        cleanRoot.addEventListener("click", handleEmptyTrashTriggerClick);
    }

    function resetPendingDocumentOperation(explorer, options) {
        explorer.__pendingDocumentOperation = null;
        explorer.removeAttribute("data-document-pending-operation");
        explorer.removeAttribute("data-document-pending-operation-ids");
        explorer.removeAttribute("data-document-pending-operation-name");
        explorer.removeAttribute("data-document-pending-operation-mode");
        renderPreviewEmpty(explorer, options);
    }

    function runPendingDocumentOperation(explorer, operation, options) {
        const pendingOperation = operation || explorer.__pendingDocumentOperation || {};
        const operationType = pendingOperation.type || "";
        const documentIds = uniqueDocumentValues(pendingOperation.documentIds);

        if (operationType === "move_to_trash") {
            requestMoveDocumentToTrash(explorer, documentIds, options);
            return;
        }

        if (operationType === "permanent_delete") {
            requestPermanentDeleteDocument(explorer, documentIds, options);
            return;
        }

        if (operationType === "empty_trash") {
            requestEmptyTrash(explorer, options);
        }
    }

    bindEmptyTrashControls(document);

    window.SolomonWorkspaceDocumentTrashMutations = Object.freeze({
        bindEmptyTrashControls,
        buildMoveFolderToTrashEndpoint,
        buildMoveToTrashEndpoint,
        buildPermanentDeleteFolderEndpoint,
        buildRecentDocumentsEndpoint,
        buildRestoreFolderEndpoint,
        buildTrashFolderEndpoint,
        buildOptimisticTrashDocument,
        buildPermanentDeleteEndpoint,
        buildRestoreFromTrashEndpoint,
        buildTrashDocumentEndpoint,
        buildTrashDocumentsEndpoint,
        emptyTrashDocuments,
        fetchTrashDocuments,
        getDocumentMutationSummaryName,
        getDocumentSectionEndpoint,
        getOptimisticTrashDocuments,
        getSuppressedTrashDocumentIds,
        getTrashDocumentIdsForEmptyTrash,
        getVisibleTrashDocumentIds,
        mergeTrashDocumentsForRender,
        moveDocumentToTrash,
        moveDocumentsToTrash,
        moveFolderToTrash,
        moveFoldersToTrash,
        permanentlyDeleteDocument,
        permanentlyDeleteDocuments,
        permanentlyDeleteFolder,
        permanentlyDeleteFolders,
        rememberDocumentInTrash,
        requestEmptyTrash,
        requestMoveDocumentToTrash,
        requestMoveFolderToTrash,
        requestPermanentDeleteDocument,
        requestPermanentDeleteFolder,
        resetPendingDocumentOperation,
        restoreDocumentFromTrash,
        restoreFoldersFromTrash,
        runPendingDocumentOperation,
        shouldSuppressTrashDocument,
        suppressDocumentInTrash,
        unsuppressDocumentInTrash,
        upsertDocumentInCachedSection
    });
})();