/* -------------------------------------------------------------------
   FILE: workspace_document_operations.js
   DIRECTORY: webui/static/js/command_center/
   Generic Solomon document operation and Action runner.
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentOperations";
    const DEFAULT_OPERATION_ENDPOINT = "/workspace/document-operation/run";
    const DEFAULT_OPERATION_KEY = "bid_scope_review";
    const DEFAULT_OPERATION_ACTION_LABEL = "Run Bid & Scope Review";
    const DEFAULT_OPERATION_REPORT_LABEL = "Bid & Scope Review";
    const SOLOMON_AI_SESSION_OPERATION_KEY = "ask_solomon_ai";
    const DEFAULT_SOLOMON_AI_SESSION_ENDPOINT = "/workspace/document-operation/ai/session";
    const DEFAULT_SOLOMON_ACTION_ENDPOINT = "/workspace/actions/file/execute";
    const SOLOMON_AI_SESSION_SOURCE = "workspace_document_ai_source_selection";
    const DOCUMENTS_MODULE_ID = "documents";
    const SOLOMON_AI_MODULE_ID = "solomon_ai";
    const PEOPLE_MODULE_ID = "people";
    const SEARCH_MODULE_ID = "search";

    if (window[API_NAME]) {
        return;
    }

    function cleanValue(value) {
        return String(value || "").trim();
    }

    function uniqueCleanValues(values) {
        const seen = new Set();
        const cleaned = [];

        (values || []).forEach(function (value) {
            const clean = cleanValue(value);

            if (!clean || seen.has(clean)) {
                return;
            }

            seen.add(clean);
            cleaned.push(clean);
        });

        return cleaned;
    }

    function splitDocumentIdList(value) {
        if (Array.isArray(value)) {
            return uniqueCleanValues(value);
        }

        return uniqueCleanValues(
            cleanValue(value)
                .split(",")
                .map(function (item) {
                    return item.trim();
                })
        );
    }

    function getOperationEndpoint(explorer) {
        return cleanValue(
            explorer?.dataset?.documentOperationEndpoint ||
            explorer?.dataset?.bidScopeExecuteEndpoint ||
            DEFAULT_OPERATION_ENDPOINT
        );
    }

    function getSolomonActionEndpoint(explorer) {
        return cleanValue(
            explorer?.dataset?.solomonActionEndpoint ||
            explorer?.dataset?.workspaceSolomonActionEndpoint ||
            DEFAULT_SOLOMON_ACTION_ENDPOINT
        );
    }

    function getSolomonAiSessionEndpoint(explorer) {
        return cleanValue(
            explorer?.dataset?.documentAiSessionEndpoint ||
            explorer?.dataset?.workspaceDocumentAiSessionEndpoint ||
            explorer?.dataset?.solomonAiSessionEndpoint ||
            DEFAULT_SOLOMON_AI_SESSION_ENDPOINT
        );
    }

    function getActiveSolomonAiConversationId(explorer) {
        return cleanValue(
            explorer?.dataset?.solomonAiConversationId ||
            explorer?.dataset?.documentAiConversationId
        );
    }

    function getStatusApi() {
        return window.SolomonWorkspaceDocumentStatus || null;
    }

    function getPreviewApi() {
        return window.SolomonWorkspaceDocumentPreview || null;
    }

    function getContextRailApi() {
        return window.NationsCommandSidebar || null;
    }

    function getConversationApi() {
        return window.SolomonWorkspaceDocumentConversation || null;
    }

    function getSameOriginUrl(value) {
        const cleanUrl = cleanValue(value);

        if (!cleanUrl) {
            return null;
        }

        try {
            const parsedUrl = new URL(cleanUrl, window.location.origin);

            return parsedUrl.origin === window.location.origin
                ? parsedUrl
                : null;
        } catch (_error) {
            return null;
        }
    }

    function getRelativeUrl(parsedUrl) {
        if (!parsedUrl) {
            return "";
        }

        return `${parsedUrl.pathname}${parsedUrl.search}${parsedUrl.hash}`;
    }

    function getRightPaneModuleForRoute(route) {
        const parsedUrl = getSameOriginUrl(route);

        if (!parsedUrl) {
            return DOCUMENTS_MODULE_ID;
        }

        if (
            parsedUrl.pathname === "/ai" ||
            parsedUrl.pathname.startsWith("/ai/")
        ) {
            return SOLOMON_AI_MODULE_ID;
        }

        if (
            parsedUrl.pathname === "/people" ||
            parsedUrl.pathname.startsWith("/people/")
        ) {
            return PEOPLE_MODULE_ID;
        }

        if (parsedUrl.pathname === "/search") {
            return SEARCH_MODULE_ID;
        }

        return DOCUMENTS_MODULE_ID;
    }

    function fallbackToRoute(route) {
        const parsedUrl = getSameOriginUrl(route);
        const targetRoute = getRelativeUrl(parsedUrl) || cleanValue(route);

        if (!targetRoute) {
            return false;
        }

        window.location.assign(targetRoute);
        return false;
    }

    async function loadRightPaneRoute(route, options) {
        const parsedUrl = getSameOriginUrl(route);
        const cleanRoute = getRelativeUrl(parsedUrl);
        const sidebarApi = window.NationsCommandSidebar || null;
        const loadOptions = Object.assign(
            {
                push: true,
                async: true,
                launchMode: "document_operation_navigation",
                source: "workspace_document_operations"
            },
            options || {}
        );

        if (!cleanRoute) {
            return fallbackToRoute(route);
        }

        if (!sidebarApi || typeof sidebarApi.loadWorkspace !== "function") {
            return fallbackToRoute(cleanRoute);
        }

        try {
            const result = await sidebarApi.loadWorkspace(
                cleanRoute,
                getRightPaneModuleForRoute(cleanRoute),
                loadOptions
            );

            if (result === false) {
                return fallbackToRoute(cleanRoute);
            }

            return true;
        } catch (error) {
            console.warn(
                "[DOCUMENT_OPERATIONS] Async right-pane navigation failed; falling back to hard navigation.",
                error
            );
            return fallbackToRoute(cleanRoute);
        }
    }

    function navigateToSolomonAiWorkspace(url, options) {
        return loadRightPaneRoute(
            url || "/ai",
            Object.assign(
                {
                    launchMode: "document_ai_session",
                    source: "workspace_document_operations"
                },
                options || {}
            )
        );
    }

    function getDocumentIds(options) {
        const candidates = [
            options?.documentIds,
            options?.document_ids,
            options?.selectedIds,
            options?.selected_ids,
            options?.selectedDocumentIds,
            options?.selected_document_ids,
            options?.documentSelectedIds,
            options?.document_selected_ids,
            options?.dataset?.documentSelectedIds,
            options?.dataset?.selectedDocumentIds,
            options?.dataset?.selectedIds
        ];

        for (const candidate of candidates) {
            const ids = splitDocumentIdList(candidate);

            if (ids.length) {
                return ids;
            }
        }

        return uniqueCleanValues([getDocumentId(options)]);
    }

    function getDocumentNames(options) {
        const candidates = [
            options?.documentNames,
            options?.document_names,
            options?.selectedNames,
            options?.selected_names,
            options?.selectedDocumentNames,
            options?.selected_document_names,
            options?.documentSelectedNames,
            options?.document_selected_names,
            options?.dataset?.documentSelectedNames,
            options?.dataset?.selectedDocumentNames,
            options?.dataset?.selectedNames
        ];

        for (const candidate of candidates) {
            if (Array.isArray(candidate)) {
                const names = uniqueCleanValues(candidate);

                if (names.length) {
                    return names;
                }

                continue;
            }

            const names = uniqueCleanValues(
                cleanValue(candidate)
                    .split("|")
                    .map(function (item) {
                        return item.trim();
                    })
            );

            if (names.length) {
                return names;
            }
        }

        return uniqueCleanValues([getDocumentName(options)]);
    }

    function getDocumentCountLabel(count) {
        const total = Number(count || 0);

        if (total === 1) {
            return "1 file";
        }

        return `${total} files`;
    }

    function getDocumentName(options) {
        return cleanValue(options?.documentName) || "Selected file";
    }

    function getOperationDocumentName(options, documentIds) {
        const names = getDocumentNames(options);
        const selectedCount = documentIds.length || names.length;

        if (selectedCount > 1) {
            return getDocumentCountLabel(selectedCount);
        }

        return names[0] || getDocumentName(options);
    }

    function getDocumentId(options) {
        return cleanValue(
            options?.documentId ||
            options?.document_id ||
            options?.fileId ||
            options?.randomName
        );
    }

    function getOperationKey(options) {
        return cleanValue(options?.operation || options?.operationKey) || DEFAULT_OPERATION_KEY;
    }

    function isSolomonAiSessionOperation(operationKey) {
        return cleanValue(operationKey).toLowerCase() === SOLOMON_AI_SESSION_OPERATION_KEY;
    }

    function stripActionPrefix(label) {
        return cleanValue(label)
            .replace(/^run\s+/i, "")
            .replace(/^start\s+/i, "")
            .replace(/^quick\s+/i, "")
            .trim();
    }

    function getOperationActionLabel(options) {
        return cleanValue(options?.label || options?.operationLabel) || DEFAULT_OPERATION_ACTION_LABEL;
    }

    function getOperationReportLabel(options) {
        const operationKey = getOperationKey(options);
        const actionLabel = getOperationActionLabel(options);
        const reportLabel = stripActionPrefix(actionLabel);

        if (operationKey === DEFAULT_OPERATION_KEY) {
            return reportLabel || DEFAULT_OPERATION_REPORT_LABEL;
        }

        return reportLabel || actionLabel || "Document Operation";
    }

    function getPacketStatus(packet) {
        return cleanValue(packet?.status).toLowerCase();
    }

    function isFailedPacket(packet) {
        const status = getPacketStatus(packet);

        return packet?.ok === false || ["failed", "error", "cancelled"].includes(status);
    }

    function isCompletePacket(packet) {
        return getPacketStatus(packet) === "complete";
    }

    function showStatus(explorer, payload) {
        const Status = getStatusApi();

        if (!Status || typeof Status.show !== "function") {
            return;
        }

        Status.show(explorer, payload);
    }

    function showProcessing(explorer, options) {
        const Preview = getPreviewApi();
        const Conversation = getConversationApi();

        if (Conversation && typeof Conversation.markFilesViewIntent === "function") {
            Conversation.markFilesViewIntent(explorer);
        }

        if (Conversation && typeof Conversation.setView === "function") {
            Conversation.setView(explorer, "preview");
        }

        if (Preview && typeof Preview.renderOperationProcessing === "function") {
            Preview.renderOperationProcessing(explorer, options);
            return;
        }

        if (Preview && typeof Preview.renderReviewProcessing === "function") {
            Preview.renderReviewProcessing(explorer, options);
        }
    }

    function showResult(explorer, response, options) {
        const Preview = getPreviewApi();
        const Conversation = getConversationApi();

        if (Conversation && typeof Conversation.setView === "function") {
            Conversation.setView(explorer, "preview");
        }

        if (Preview && typeof Preview.renderOperationResult === "function") {
            Preview.renderOperationResult(explorer, response, options);
            return;
        }

        if (Preview && typeof Preview.renderReviewResult === "function") {
            Preview.renderReviewResult(explorer, response, options);
        }
    }

    function showError(explorer, error, options) {
        const Preview = getPreviewApi();
        const Conversation = getConversationApi();

        if (Conversation && typeof Conversation.setView === "function") {
            Conversation.setView(explorer, "preview");
        }

        if (Preview && typeof Preview.renderOperationError === "function") {
            Preview.renderOperationError(explorer, error.message, options);
            return;
        }

        if (Preview && typeof Preview.renderError === "function") {
            Preview.renderError(error.message || "The document operation could not be completed.");
        }
    }

    async function readJsonResponse(response) {
        const contentType = cleanValue(response.headers.get("content-type")).toLowerCase();

        if (!contentType.includes("application/json")) {
            throw new Error("The server returned an invalid document operation response.");
        }

        const payload = await response.json();

        if (!response.ok) {
            throw new Error(
                payload.user_output ||
                payload?.error?.message ||
                (typeof payload.error === "string" ? payload.error : "") ||
                payload?.result?.summary ||
                "The document operation request failed."
            );
        }

        if (payload.ok === false) {
            throw new Error(
                payload.user_output ||
                payload?.error?.message ||
                (typeof payload.error === "string" ? payload.error : "") ||
                payload?.result?.summary ||
                "The document operation failed."
            );
        }

        return payload;
    }

    function buildOperationPayload(options) {
        const documentIds = getDocumentIds(options);
        const documentId = documentIds[0] || "";
        const operation = getOperationKey(options);

        return {
            operation,
            document_id: documentId,
            document_ids: documentIds,
            source: "workspace_document_operation",
            target_region: "document_inspector"
        };
    }

    function buildSolomonAiSessionPayload(explorer, options) {
        const documentIds = getDocumentIds(options);
        const documentNames = getDocumentNames(options);
        const activeConversationId =
            getActiveSolomonAiConversationId(explorer);
        const payload = {
            operation: SOLOMON_AI_SESSION_OPERATION_KEY,
            document_id: documentIds[0] || "",
            document_ids: documentIds,
            document_names: documentNames,
            source: SOLOMON_AI_SESSION_SOURCE,
            target_region: "solomon_ai_workspace"
        };

        if (activeConversationId) {
            payload.conversation_id = activeConversationId;
        }

        return payload;
    }

    function getSolomonAiConversationUrl(response) {
        return cleanValue(
            response?.conversation_url ||
            response?.redirect_url ||
            response?.workspace_url ||
            response?.solomon_ai_url ||
            response?.url ||
            response?.location
        );
    }

    function normalizeResultTitle(title, operationLabel, status) {
        const cleanedTitle = stripActionPrefix(title);
        const cleanOperationLabel = stripActionPrefix(operationLabel) || DEFAULT_OPERATION_REPORT_LABEL;

        if (cleanedTitle) {
            return cleanedTitle;
        }

        if (["failed", "error", "cancelled"].includes(status)) {
            return `${cleanOperationLabel} Failed`;
        }

        return `${cleanOperationLabel} Complete`;
    }

    function normalizeOperationPacket(packet, options) {
        const sourcePacket = packet && typeof packet === "object" ? packet : {};
        const sourceResult = sourcePacket.result && typeof sourcePacket.result === "object"
            ? sourcePacket.result
            : {};
        const status = getPacketStatus(sourcePacket);
        const operationLabel = options.operationLabel || DEFAULT_OPERATION_REPORT_LABEL;
        const documentIds = Array.isArray(options.documentIds) ? options.documentIds : [];
        const documentNames = Array.isArray(options.documentNames) ? options.documentNames : [];

        return {
            ...sourcePacket,
            operation_label: operationLabel,
            document_ids: sourcePacket.document_ids || documentIds,
            document_count: sourcePacket.document_count || documentIds.length,
            document: sourcePacket.document || {
                document_id: options.documentId,
                original_name: options.documentName
            },
            documents: sourcePacket.documents || documentIds.map(function (documentId, index) {
                return {
                    document_id: documentId,
                    original_name: documentNames[index] || documentId
                };
            }),
            result: {
                ...sourceResult,
                title: normalizeResultTitle(sourceResult.title, operationLabel, status)
            }
        };
    }

    async function postOperation(endpoint, payload) {
        const response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify(payload)
        });

        return readJsonResponse(response);
    }

    function showCompletionStatus(explorer, response, options) {
        if (isFailedPacket(response)) {
            return;
        }

        if (isCompletePacket(response) || response?.ok === true) {
            showStatus(explorer, {
                action: "document_operation",
                documentId: options.documentId,
                documentIds: options.documentIds,
                fileName: options.documentName,
                variant: "success",
                message: `${options.operationLabel} complete for ${options.documentName}.`,
                durationMs: 2600
            });
        }
    }

    function normalizeActionResultPacket(packet, options) {
        const sourcePacket = packet && typeof packet === "object" ? packet : {};
        const sourceAction = sourcePacket.action && typeof sourcePacket.action === "object"
            ? sourcePacket.action
            : {};
        const sourceResource = sourcePacket.resource && typeof sourcePacket.resource === "object"
            ? sourcePacket.resource
            : {};
        const sourceExecution = sourcePacket.execution && typeof sourcePacket.execution === "object"
            ? sourcePacket.execution
            : {};
        const sourceResult = sourcePacket.result && typeof sourcePacket.result === "object"
            ? sourcePacket.result
            : {};

        return {
            ...sourcePacket,
            action: {
                ...sourceAction,
                action_id: cleanValue(sourceAction.action_id || options?.actionId),
                label: cleanValue(sourceAction.label || options?.actionLabel)
            },
            resource: {
                ...sourceResource,
                document_id: cleanValue(sourceResource.document_id || options?.documentId),
                name: cleanValue(sourceResource.name || options?.documentName)
            },
            execution: {
                ...sourceExecution,
                status: cleanValue(sourceExecution.status || (sourcePacket.ok === true ? "succeeded" : "failed")).toLowerCase(),
                stage: cleanValue(sourceExecution.stage),
                progress_percent: Number.isFinite(Number(sourceExecution.progress_percent))
                    ? Number(sourceExecution.progress_percent)
                    : null
            },
            result: {
                ...sourceResult,
                title: cleanValue(sourceResult.title || options?.actionLabel || "Action Result"),
                content: cleanValue(sourceResult.content || sourceResult.summary || sourceResult.text)
            }
        };
    }

    async function runAction(explorer, options) {
        const actionId = cleanValue(options?.actionId || options?.action_id);
        const documentId = cleanValue(options?.documentId || options?.document_id);
        const documentName = cleanValue(options?.documentName) || "Selected file";
        const actionLabel = cleanValue(options?.actionLabel || options?.label) || "Action";
        const actionParameters = options?.parameters && typeof options.parameters === "object"
            ? options.parameters
            : {};
        const endpoint = getSolomonActionEndpoint(explorer);
        const ContextRail = getContextRailApi();
        const documentRecord = options?.document && typeof options.document === "object"
            ? options.document
            : {
                document_id: documentId,
                original_name: documentName
            };
        const requestId = `${actionId}:${documentId}:${Date.now()}:${Math.random().toString(16).slice(2)}`;
        const presentationOptions = {
            actionId,
            actionLabel,
            documentId,
            documentName,
            requestId
        };

        if (!explorer || !endpoint || !actionId || !documentId) {
            return null;
        }

        if (
            !ContextRail ||
            typeof ContextRail.showContextRailActionLoading !== "function" ||
            typeof ContextRail.showContextRailActionResult !== "function" ||
            typeof ContextRail.showContextRailActionError !== "function"
        ) {
            showStatus(explorer, {
                action: "solomon_action",
                documentId,
                variant: "error",
                message: "The Action result panel is not available in this workspace."
            });
            return null;
        }

        // Action execution is intentionally presentation-local. The Explorer remains
        // fully interactive while Solomon works; only the right context rail owns
        // the Action busy state.
        ContextRail.showContextRailActionLoading(
            documentRecord,
            presentationOptions
        );

        try {
            const packet = normalizeActionResultPacket(
                await postOperation(
                    endpoint,
                    {
                        action_id: actionId,
                        document_id: documentId,
                        parameters: actionParameters
                    }
                ),
                presentationOptions
            );

            if (
                typeof ContextRail.isContextRailActionRequestCurrent === "function" &&
                !ContextRail.isContextRailActionRequestCurrent(documentId, requestId)
            ) {
                return packet;
            }

            ContextRail.showContextRailActionResult(
                documentRecord,
                packet,
                presentationOptions
            );

            return packet;
        } catch (error) {
            if (
                typeof ContextRail.isContextRailActionRequestCurrent !== "function" ||
                ContextRail.isContextRailActionRequestCurrent(documentId, requestId)
            ) {
                ContextRail.showContextRailActionError(
                    documentRecord,
                    error?.message || `${actionLabel} could not be completed.`,
                    presentationOptions
                );
            }
            return null;
        }
    }

    async function launchSolomonAiSession(explorer, options) {
        const endpoint = getSolomonAiSessionEndpoint(explorer);
        const documentIds = getDocumentIds(options);
        const documentNames = getDocumentNames(options);
        const documentName = getOperationDocumentName(options, documentIds);
        const renderOptions = {
            operation: SOLOMON_AI_SESSION_OPERATION_KEY,
            operationActionLabel: "Ask SolomonAI",
            operationLabel: "Ask SolomonAI",
            documentId: documentIds[0] || "",
            documentIds,
            documentName,
            documentNames,
            documentCount: documentIds.length
        };

        if (!explorer || !endpoint || !documentIds.length) {
            return null;
        }

        explorer.setAttribute("data-document-explorer-loading", "true");

        try {
            const response = await postOperation(
                endpoint,
                buildSolomonAiSessionPayload(
                    explorer,
                    {
                        ...options,
                        documentIds,
                        documentNames
                    }
                )
            );
            const conversationUrl =
                getSolomonAiConversationUrl(response);

            if (!conversationUrl) {
                throw new Error(
                    "The server did not return a SolomonAI conversation URL."
                );
            }

            await navigateToSolomonAiWorkspace(
                conversationUrl,
                {
                    documentIds,
                    documentNames,
                    documentName
                }
            );
            return response;
        } catch (error) {
            showError(explorer, error, renderOptions);
            return null;
        } finally {
            explorer.removeAttribute("data-document-explorer-loading");
        }
    }

    async function run(explorer, options) {
        const operationKey = getOperationKey(options);

        if (isSolomonAiSessionOperation(operationKey)) {
            return launchSolomonAiSession(explorer, {
                ...options,
                operation: SOLOMON_AI_SESSION_OPERATION_KEY
            });
        }

        const endpoint = getOperationEndpoint(explorer);
        const documentIds = getDocumentIds(options);
        const documentId = documentIds[0] || "";
        const documentNames = getDocumentNames(options);
        const documentName = getOperationDocumentName(options, documentIds);
        const operationActionLabel = getOperationActionLabel(options);
        const operationReportLabel = getOperationReportLabel({
            ...options,
            operation: operationKey,
            operationLabel: operationActionLabel
        });
        const renderOptions = {
            operation: operationKey,
            operationActionLabel,
            operationLabel: operationReportLabel,
            documentId,
            documentIds,
            documentName,
            documentNames,
            documentCount: documentIds.length
        };

        if (!explorer || !endpoint || !documentIds.length) {
            return null;
        }

        explorer.setAttribute("data-document-explorer-loading", "true");
        showProcessing(explorer, renderOptions);

        try {
            const payload = buildOperationPayload({
                ...options,
                operation: operationKey,
                documentIds
            });

            const resultPacket = normalizeOperationPacket(
                await postOperation(endpoint, payload),
                renderOptions
            );

            showResult(explorer, resultPacket, renderOptions);
            showCompletionStatus(explorer, resultPacket, renderOptions);

            return resultPacket;
        } catch (error) {
            showError(explorer, error, renderOptions);
            return null;
        } finally {
            explorer.removeAttribute("data-document-explorer-loading");
        }
    }

    window[API_NAME] = Object.freeze({
        run,
        runAction
    });
})();