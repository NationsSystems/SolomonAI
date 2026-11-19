/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_request_payload.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI execution-request payload construction.

   Builds the request envelope from the active conversation and
   server-rendered source membership. JavaScript describes browser
   context only; operation resolution, routing, and execution authority
   remain exclusively server-owned.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before request payloads."
        );
    }

    const contract = modules.requireModule("contract");
    const navigation = modules.requireModule(
        "conversation_navigation"
    );
    const membership = modules.requireModule(
        "source_membership"
    );
    const {
        constants,
        cleanValue
    } = contract;

    function getSourceMode(documentCount) {
        return membership.getSourceMode(
            documentCount
        );
    }

    function buildRequestFiles(documentIds) {
        return documentIds.map(function (documentId) {
            return {
                id: documentId,
                document_id: documentId
            };
        });
    }

    function buildSourceContext(documentIds) {
        const safeDocumentIds = Array.isArray(documentIds)
            ? documentIds.slice()
            : [];

        return {
            mode: getSourceMode(safeDocumentIds.length),
            document_ids: safeDocumentIds,
            selected_document_ids: safeDocumentIds,
            files: buildRequestFiles(safeDocumentIds)
        };
    }

    function buildCommandContext() {
        return {
            module: constants.SOLOMON_AI_MODULE_ID
        };
    }

    function buildWorkspaceContext(sourceMode) {
        return {
            schema: constants.WORKSPACE_CONTEXT_SCHEMA,
            source: constants.SOLOMON_AI_WORKSPACE_SOURCE,
            route: window.location.pathname,
            module: constants.SOLOMON_AI_MODULE_ID,
            module_label: "SolomonAI",
            workspace_mode: sourceMode,
            command_surface: "solomon_ai_workspace",
            command_mode: "conversation",
            active_section: "conversation",
            trusted_context_required: true
        };
    }

    function getRequestContext(elements) {
        const documentIds = membership.getAttachedSourceIds(
            elements
        );
        const conversationId = navigation.getConversationId(
            elements
        );
        const sourceContext = buildSourceContext(
            documentIds
        );

        return {
            conversationId,
            documentIds,
            sourceContext
        };
    }

    function buildRequestPayload(elements, message) {
        const context = getRequestContext(elements);

        return {
            task: message,
            conversation_id: context.conversationId,
            document_ids: context.documentIds,
            selected_document_ids: context.documentIds,
            source_context: context.sourceContext,
            command_context: buildCommandContext(),
            workspace_context: buildWorkspaceContext(
                context.sourceContext.mode
            )
        };
    }

    function isRequestPayloadReady(payload) {
        return Boolean(
            cleanValue(payload?.task) &&
            cleanValue(payload?.conversation_id)
        );
    }

    modules.registerModule(
        "request_payload",
        {
            buildCommandContext,
            buildRequestFiles,
            buildRequestPayload,
            buildSourceContext,
            buildWorkspaceContext,
            getRequestContext,
            getSourceMode,
            isRequestPayloadReady
        }
    );
})(window);