/* -------------------------------------------------------------------
   FILE: workspace_document_solomon_context.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    function cleanValue(value) {
        return String(value || "").trim();
    }

    function normalizeLookupValue(value) {
        return cleanValue(value).toLowerCase();
    }

    function getRecordsApi(options) {
        return options?.Records || window.SolomonWorkspaceDocumentRecords || null;
    }

    function getStatusApi(options) {
        return options?.Status || window.SolomonWorkspaceDocumentStatus || null;
    }

    function getRailApi() {
        const railApi = window.NationsCommandSidebar || null;

        if (!railApi || typeof railApi !== "object") {
            return null;
        }

        return railApi;
    }

    function normalizeDocument(doc, options) {
        const Records = getRecordsApi(options);

        if (Records && typeof Records.normalizeDocument === "function") {
            return Records.normalizeDocument(doc || {});
        }

        return doc || {};
    }

    function isFolderDocumentRecord(doc, options) {
        const rawDoc = doc && typeof doc === "object" ? doc : {};
        const normalizedDoc = normalizeDocument(rawDoc, options);
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

    function getDocumentName(doc, options) {
        const normalizedDoc = normalizeDocument(doc || {}, options);
        const name = cleanValue(
            normalizedDoc.original_name ||
            normalizedDoc.filename ||
            normalizedDoc.random_name ||
            normalizedDoc.document_id
        );

        return name || "Selected document";
    }

    function getDocumentKind(doc, options) {
        const normalizedDoc = normalizeDocument(doc || {}, options);
        const kind = cleanValue(
            normalizedDoc.type_label ||
            normalizedDoc.mime_type ||
            normalizedDoc.extension ||
            "Workspace Document"
        );

        return kind || "Workspace Document";
    }

    function normalizeRailFile(doc, options) {
        const normalizedDoc = normalizeDocument(doc || {}, options);
        const documentId = cleanValue(normalizedDoc.document_id || normalizedDoc.random_name);

        if (!documentId || isFolderDocumentRecord(doc, options)) {
            return null;
        }

        return {
            id: documentId,
            documentId,
            name: getDocumentName(normalizedDoc, options),
            kind: getDocumentKind(normalizedDoc, options),
            mimeType: normalizedDoc.mime_type || "",
            extension: normalizedDoc.extension || "",
            readerUrl: normalizedDoc.reader_url || normalizedDoc.workspace_reader_url || "",
            workflowStatus: normalizedDoc.workflow_status || "",
            analysisStatus: normalizedDoc.analysis_status || ""
        };
    }

    function getSelectionLabel(count, options) {
        if (typeof options?.getDocumentSelectionLabel === "function") {
            return options.getDocumentSelectionLabel(count);
        }

        return `${count} selected documents`;
    }

    function getSourceDocuments(docs, options) {
        return (Array.isArray(docs) ? docs : []).filter(function (doc) {
            return Boolean(normalizeRailFile(doc, options));
        });
    }

    function buildSourceContext(docs, options) {
        const files = (Array.isArray(docs) ? docs : [])
            .map(function (doc) {
                return normalizeRailFile(doc, options);
            })
            .filter(Boolean);
        const firstFile = files[0] || null;
        const fileCount = files.length;
        const selectionLabel = fileCount > 1
            ? getSelectionLabel(fileCount, options)
            : (firstFile?.name || "");
        const contextType = fileCount
            ? (fileCount > 1 ? "document_selection" : "document")
            : "";
        const contextLabel = fileCount > 1
            ? `${fileCount} selected documents`
            : (firstFile?.name || "");
        const contextKind = fileCount > 1
            ? "Selected documents"
            : (firstFile?.kind || "");

        return {
            contextType,
            contextLabel,
            contextKind,
            selectionLabel,
            fileCount,
            files,
            file: firstFile,
            documentId: firstFile?.documentId || "",
            documentName: firstFile?.name || "",
            documentKind: firstFile?.kind || ""
        };
    }

    function setSourceContext(explorer, docs, options) {
        const railApi = getRailApi();

        if (!railApi || !explorer) {
            return false;
        }

        const sourceContext = buildSourceContext(docs, options);

        if (typeof railApi.setSourceContext === "function") {
            railApi.setSourceContext(sourceContext);
        } else if (typeof railApi.setDocumentSource === "function") {
            railApi.setDocumentSource(sourceContext);
        } else {
            return false;
        }

        explorer.__solomonRailSourceContext = sourceContext;

        if (sourceContext.fileCount && options?.open !== false && typeof railApi.open === "function") {
            railApi.open({
                reason: "document_selection",
                sourceContext
            });
        }

        return true;
    }

    function showStatus(explorer, payload, options) {
        const Status = getStatusApi(options);

        if (Status && typeof Status.show === "function") {
            Status.show(explorer, payload);
        }
    }

    function getDocumentsByIds(explorer, documentIds, options) {
        if (typeof options?.getDocumentRecordsByIds === "function") {
            return options.getDocumentRecordsByIds(explorer, documentIds);
        }

        return [];
    }

    function openForDocuments(explorer, docs, options) {
        const requestedDocs = Array.isArray(docs) && docs.length
            ? docs
            : getDocumentsByIds(explorer, options?.documentIds || [], options);
        const sourceDocs = getSourceDocuments(requestedDocs, options);

        if (!sourceDocs.length) {
            showStatus(explorer, {
                action: "ask_solomon_ai",
                variant: "info",
                message: "Select a document before opening SolomonAI."
            }, options);
            return false;
        }

        if (!setSourceContext(explorer, sourceDocs, Object.assign({}, options || {}, { open: true }))) {
            showStatus(explorer, {
                action: "ask_solomon_ai",
                variant: "info",
                message: "SolomonAI rail is not available in this workspace."
            }, options);
            return false;
        }

        if (options?.showStatus !== false) {
            showStatus(explorer, {
                action: "ask_solomon_ai",
                documentIds: sourceDocs.map(function (doc) {
                    const normalizedDoc = normalizeDocument(doc, options);

                    return normalizedDoc.document_id || normalizedDoc.random_name || "";
                }).filter(Boolean),
                variant: "success",
                message: sourceDocs.length > 1
                    ? `SolomonAI is ready for ${sourceDocs.length} selected documents.`
                    : `SolomonAI is ready for ${getDocumentName(sourceDocs[0], options)}.`
            }, options);
        }

        return true;
    }

    function syncFromSelection(explorer, docs, options) {
        if (!explorer) {
            return;
        }

        setSourceContext(explorer, getSourceDocuments(docs, options), Object.assign({}, options || {}, {
            open: false
        }));
    }

    window.SolomonWorkspaceDocumentSolomonContext = Object.freeze({
        buildSourceContext,
        getDocumentKind,
        getDocumentName,
        getRailApi,
        getSourceDocuments,
        isFolderDocumentRecord,
        normalizeRailFile,
        openForDocuments,
        setSourceContext,
        syncFromSelection
    });
})();