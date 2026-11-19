/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_source_transport.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI conversation-source transport.

   Loads the conversation-scoped authorized file catalog, attaches
   selected existing files, synchronizes the authoritative source list,
   and removes individual source associations. JavaScript transports
   identifiers and renders validated server packets; file access and
   source membership authority remain server-owned.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before source transport."
        );
    }

    const contract = modules.requireModule("contract");
    const navigation = modules.requireModule("conversation_navigation");
    const membership = modules.requireModule("source_membership");
    const { cleanValue, readJsonResponse } = contract;

    function isPending(elements) {
        const composerState = modules.getModule("composer_state");

        if (typeof composerState?.isPending === "function") {
            return composerState.isPending(elements);
        }

        return elements?.composer?.getAttribute(
            "data-solomon-ai-pending"
        ) === "true";
    }

    function setSyncState(elements, state) {
        elements?.workspace?.setAttribute(
            "data-solomon-ai-source-sync-state",
            cleanValue(state) || "ready"
        );
    }

    function getPacketError(packet, response, fallbackPrefix) {
        return cleanValue(
            packet?.user_output ||
            packet?.error
        ) || `${fallbackPrefix}: ${response?.status || "unknown"}`;
    }

    function getCatalogEndpoint(elements) {
        return cleanValue(
            elements?.workspace?.getAttribute(
                "data-solomon-ai-source-catalog-endpoint"
            )
        );
    }

    function getAttachEndpoint(elements) {
        return cleanValue(
            elements?.workspace?.getAttribute(
                "data-solomon-ai-source-attach-endpoint"
            )
        );
    }

    function normalizeDocumentIds(documentIds) {
        const normalizedIds = [];
        const seenIds = new Set();

        for (const documentId of documentIds || []) {
            const cleanDocumentId = cleanValue(documentId);

            if (
                !cleanDocumentId ||
                seenIds.has(cleanDocumentId)
            ) {
                continue;
            }

            seenIds.add(cleanDocumentId);
            normalizedIds.push(cleanDocumentId);
        }

        return normalizedIds;
    }

    function packetMatchesConversation(elements, packet) {
        const activeConversationId = navigation.getConversationId(
            elements
        );
        const packetConversationId = cleanValue(
            packet?.conversation_id ||
            packet?.session_id
        );

        return Boolean(
            activeConversationId &&
            (
                !packetConversationId ||
                packetConversationId === activeConversationId
            )
        );
    }

    function requireCurrentConversationPacket(elements, packet) {
        if (packetMatchesConversation(elements, packet)) {
            return true;
        }

        throw new Error(
            "The active chat changed before the file request completed."
        );
    }

    function buildCatalogEndpoint(
        elements,
        {
            scope = "",
            query = ""
        } = {}
    ) {
        const endpoint = getCatalogEndpoint(elements);

        if (!endpoint) {
            return "";
        }

        const requestUrl = new URL(
            endpoint,
            window.location.origin
        );
        const cleanScope = cleanValue(scope).toLowerCase();
        const cleanQuery = cleanValue(query);

        if (cleanScope) {
            requestUrl.searchParams.set(
                "scope",
                cleanScope
            );
        }

        if (cleanQuery) {
            requestUrl.searchParams.set(
                "q",
                cleanQuery
            );
        }

        return requestUrl.toString();
    }

    async function requestSourcePacket(
        endpoint,
        method,
        payload = null
    ) {
        const requestMethod = cleanValue(
            method
        ).toUpperCase() || "GET";
        const headers = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        };
        const requestOptions = {
            method: requestMethod,
            credentials: "same-origin",
            headers
        };

        if (
            payload &&
            requestMethod !== "GET" &&
            requestMethod !== "HEAD"
        ) {
            headers["Content-Type"] = "application/json";
            requestOptions.body = JSON.stringify(payload);
        }

        const response = await fetch(
            endpoint,
            requestOptions
        );

        return {
            response,
            packet: await readJsonResponse(response)
        };
    }

    async function requestAvailableFiles(
        elements,
        {
            scope = "",
            query = ""
        } = {}
    ) {
        const conversationId = navigation.getConversationId(
            elements
        );
        const endpoint = buildCatalogEndpoint(
            elements,
            {
                scope,
                query
            }
        );

        if (!conversationId || !endpoint) {
            throw new Error(
                "The file catalog is not available for this chat."
            );
        }

        const { response, packet } = await requestSourcePacket(
            endpoint,
            "GET"
        );

        if (!response.ok || packet?.ok === false) {
            throw new Error(
                getPacketError(
                    packet,
                    response,
                    "File catalog request failed"
                )
            );
        }

        requireCurrentConversationPacket(
            elements,
            packet
        );

        return packet;
    }

    async function attachConversationSources(
        elements,
        documentIds
    ) {
        const conversationId = navigation.getConversationId(
            elements
        );
        const endpoint = getAttachEndpoint(elements);
        const cleanDocumentIds = normalizeDocumentIds(
            documentIds
        );

        if (
            !conversationId ||
            !endpoint ||
            !cleanDocumentIds.length
        ) {
            return null;
        }

        if (isPending(elements)) {
            membership.setSourceStatus(
                elements,
                "Wait for the current response to finish before adding files.",
                "info"
            );
            return null;
        }

        setSyncState(elements, "attaching");
        membership.setSourceStatus(
            elements,
            "Adding files to this chat…",
            "info"
        );

        try {
            const { response, packet } = await requestSourcePacket(
                endpoint,
                "POST",
                {
                    conversation_id: conversationId,
                    document_ids: cleanDocumentIds
                }
            );

            if (!response.ok || packet?.ok === false) {
                throw new Error(
                    getPacketError(
                        packet,
                        response,
                        "File attachment failed"
                    )
                );
            }

            requireCurrentConversationPacket(
                elements,
                packet
            );
            membership.applySourcePacket(
                elements,
                packet
            );
            membership.setSourceStatus(
                elements,
                "",
                "info"
            );
            setSyncState(elements, "ready");

            return packet;
        } catch (error) {
            setSyncState(elements, "error");
            membership.setSourceStatus(
                elements,
                cleanValue(error?.message) ||
                    "The selected files could not be added.",
                "error"
            );

            throw error;
        }
    }

    async function syncConversationSources(elements) {
        const conversationId = navigation.getConversationId(
            elements
        );
        const endpoint = membership.getSourcesEndpoint(
            elements
        );

        if (!conversationId || !endpoint) {
            membership.setSourceStatus(
                elements,
                "",
                "info"
            );
            setSyncState(elements, "ready");
            return false;
        }

        setSyncState(elements, "loading");
        membership.setSourceStatus(
            elements,
            "",
            "info"
        );

        try {
            const { response, packet } = await requestSourcePacket(
                endpoint,
                "GET"
            );

            if (!response.ok || packet?.ok === false) {
                throw new Error(
                    getPacketError(
                        packet,
                        response,
                        "File request failed"
                    )
                );
            }

            requireCurrentConversationPacket(
                elements,
                packet
            );
            membership.applySourcePacket(
                elements,
                packet,
                {
                    preserveExisting: true
                }
            );
            membership.setSourceStatus(
                elements,
                "",
                "info"
            );
            setSyncState(elements, "ready");
            return true;
        } catch (error) {
            setSyncState(elements, "error");
            membership.setSourceStatus(
                elements,
                cleanValue(error?.message) ||
                    "Files could not be loaded.",
                "error"
            );
            return false;
        }
    }

    async function updatePublicWebSelection(
        elements,
        selected
    ) {
        const endpoint = membership.getPublicWebEndpoint(
            elements
        );
        const previousSelection = (
            membership.isPublicWebSelected(elements)
        );
        const requestedSelection = selected === true;

        if (!endpoint || !elements?.publicWebToggle) {
            membership.applyPublicWebSelection(
                elements,
                previousSelection
            );
            membership.setPublicWebStatus(
                elements,
                "Public Web source access is unavailable for this chat.",
                "error"
            );
            return false;
        }

        if (isPending(elements)) {
            membership.applyPublicWebSelection(
                elements,
                previousSelection
            );
            membership.setPublicWebStatus(
                elements,
                "Wait for the current response to finish before changing Public Web.",
                "info"
            );
            return false;
        }

        elements.publicWebToggle.disabled = true;
        membership.setPublicWebStatus(
            elements,
            "Updating Public Web source access…",
            "info"
        );

        try {
            const { response, packet } = await requestSourcePacket(
                endpoint,
                "PUT",
                {
                    public_web_selected: requestedSelection
                }
            );

            if (!response.ok || packet?.ok === false) {
                throw new Error(
                    getPacketError(
                        packet,
                        response,
                        "Public Web source update failed"
                    )
                );
            }

            requireCurrentConversationPacket(
                elements,
                packet
            );
            membership.applySourcePacket(
                elements,
                packet,
                {
                    preserveExisting: true
                }
            );
            membership.setPublicWebStatus(
                elements,
                "",
                "info"
            );
            return true;
        } catch (error) {
            membership.applyPublicWebSelection(
                elements,
                previousSelection
            );
            membership.setPublicWebStatus(
                elements,
                cleanValue(error?.message) ||
                    "Public Web source access could not be updated.",
                "error"
            );
            return false;
        } finally {
            elements.publicWebToggle.disabled = false;
        }
    }

    function bindPublicWebSelection(elements) {
        const toggle = elements?.publicWebToggle;

        if (
            !toggle ||
            toggle.getAttribute(
                "data-solomon-ai-public-web-bound"
            ) === "true"
        ) {
            return false;
        }

        toggle.setAttribute(
            "data-solomon-ai-public-web-bound",
            "true"
        );
        toggle.addEventListener(
            "change",
            function () {
                updatePublicWebSelection(
                    elements,
                    toggle.checked
                );
            }
        );

        return true;
    }

    async function removeConversationSource(
        elements,
        button
    ) {
        const documentId = cleanValue(
            button?.getAttribute(
                "data-document-id"
            )
        );
        const endpoint = cleanValue(
            button?.getAttribute(
                "data-solomon-ai-source-remove-url"
            )
        ) || membership.getSourceRemoveEndpoint(
            elements,
            documentId
        );
        const item = button?.closest(
            "[data-solomon-ai-source]"
        );

        if (
            !button ||
            !documentId ||
            !endpoint ||
            button.disabled
        ) {
            return false;
        }

        if (isPending(elements)) {
            membership.setSourceStatus(
                elements,
                "Wait for the current response to finish before removing a file.",
                "info"
            );
            return false;
        }

        button.disabled = true;
        button.setAttribute(
            "aria-busy",
            "true"
        );
        item?.setAttribute(
            "data-solomon-ai-source-state",
            "removing"
        );
        membership.setSourceStatus(
            elements,
            "Removing file from this chat…",
            "info"
        );

        try {
            const { response, packet } = await requestSourcePacket(
                endpoint,
                "DELETE"
            );

            if (!response.ok || packet?.ok === false) {
                throw new Error(
                    getPacketError(
                        packet,
                        response,
                        "File removal failed"
                    )
                );
            }

            requireCurrentConversationPacket(
                elements,
                packet
            );
            membership.applySourcePacket(
                elements,
                packet
            );
            membership.setSourceStatus(
                elements,
                "",
                "info"
            );
            return true;
        } catch (error) {
            button.disabled = false;
            button.removeAttribute(
                "aria-busy"
            );
            item?.setAttribute(
                "data-solomon-ai-source-state",
                "attached"
            );
            membership.setSourceStatus(
                elements,
                cleanValue(error?.message) ||
                    "The file could not be removed.",
                "error"
            );
            return false;
        }
    }

    function bindSourceRemoval(elements) {
        const sourceList = elements?.sourceList;

        if (
            !sourceList ||
            sourceList.getAttribute(
                "data-solomon-ai-source-removal-bound"
            ) === "true"
        ) {
            return false;
        }

        sourceList.setAttribute(
            "data-solomon-ai-source-removal-bound",
            "true"
        );

        sourceList.addEventListener(
            "click",
            function (event) {
                const removeButton = event.target?.closest?.(
                    "[data-solomon-ai-source-remove]"
                );

                if (
                    !removeButton ||
                    !sourceList.contains(removeButton)
                ) {
                    return;
                }

                event.preventDefault();
                event.stopPropagation();

                removeConversationSource(
                    elements,
                    removeButton
                );
            }
        );

        return true;
    }

    function scheduleSourceSync(elements) {
        if (
            !elements?.workspace ||
            elements.workspace.getAttribute(
                "data-solomon-ai-source-sync-scheduled"
            ) === "true"
        ) {
            return false;
        }

        elements.workspace.setAttribute(
            "data-solomon-ai-source-sync-scheduled",
            "true"
        );

        window.setTimeout(function () {
            if (elements.workspace?.isConnected) {
                syncConversationSources(elements);
            }
        }, 0);

        return true;
    }

    function initialize(elements) {
        if (!elements?.workspace) {
            return false;
        }

        bindSourceRemoval(elements);
        bindPublicWebSelection(elements);
        scheduleSourceSync(elements);
        return true;
    }

    modules.registerModule(
        "source_transport",
        {
            attachConversationSources,
            bindPublicWebSelection,
            bindSourceRemoval,
            buildCatalogEndpoint,
            getAttachEndpoint,
            getCatalogEndpoint,
            initialize,
            isPending,
            normalizeDocumentIds,
            packetMatchesConversation,
            removeConversationSource,
            requestAvailableFiles,
            requestSourcePacket,
            scheduleSourceSync,
            setSyncState,
            syncConversationSources,
            updatePublicWebSelection
        }
    );
})(window);