/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_source_membership.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI conversation source membership contract.

   Resolves rendered source identifiers, canonical endpoints, source-list
   packet validation, and presentation handoff. File access, ownership,
   and membership authority remain server-owned.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before source membership."
        );
    }

    const contract = modules.requireModule("contract");
    const navigation = modules.requireModule("conversation_navigation");
    const { constants, cleanValue } = contract;

    function getSourceItems(elements) {
        return Array.from(
            elements?.sourceList?.querySelectorAll(
                "[data-solomon-ai-source]"
            ) || []
        );
    }

    function getSourceId(source) {
        return cleanValue(source?.document_id || source?.random_name);
    }

    function collectUniqueIds(values) {
        const seen = new Set();
        const sourceIds = [];

        values.forEach(function (value) {
            const sourceId = cleanValue(value);

            if (!sourceId || seen.has(sourceId)) {
                return;
            }

            seen.add(sourceId);
            sourceIds.push(sourceId);
        });

        return sourceIds;
    }

    function getAttachedSourceIds(elements) {
        return collectUniqueIds(
            getSourceItems(elements).map(function (item) {
                return (
                    item.getAttribute("data-solomon-ai-source-id") ||
                    item.getAttribute("data-document-id")
                );
            })
        );
    }

    function getPacketSourceIds(sources) {
        return collectUniqueIds(
            (Array.isArray(sources) ? sources : []).map(getSourceId)
        );
    }

    function sourceMembershipMatches(elements, sources) {
        const renderedIds = getAttachedSourceIds(elements);
        const packetIds = getPacketSourceIds(sources);

        return (
            renderedIds.length === packetIds.length &&
            renderedIds.every(function (sourceId, index) {
                return sourceId === packetIds[index];
            })
        );
    }

    function getSourceMode(sourceCount) {
        if (sourceCount > 1) {
            return "selection";
        }

        return sourceCount === 1 ? "file" : "workspace";
    }

    function getSourceCountLabel(sourceCount) {
        if (sourceCount === 1) {
            return "1 source";
        }

        return sourceCount > 1 ? `${sourceCount} sources` : "No sources";
    }

    function getSourceContract(elements) {
        return cleanValue(
            elements.workspace.getAttribute(
                "data-solomon-ai-source-contract"
            )
        ) || constants.SOURCE_MEMBERSHIP_CONTRACT;
    }

    function getSourcesEndpoint(elements) {
        const conversationId = navigation.getConversationId(elements);

        if (!conversationId) {
            return "";
        }

        return cleanValue(
            elements.workspace.getAttribute(
                "data-solomon-ai-sources-endpoint"
            )
        ) || (
            "/workspace/solomon/conversations/" +
            encodeURIComponent(conversationId) +
            "/sources"
        );
    }

    function getPublicWebEndpoint(elements) {
        return cleanValue(
            elements?.workspace?.getAttribute(
                "data-solomon-ai-public-web-endpoint"
            )
        );
    }

    function isPublicWebSelected(elements) {
        return (
            cleanValue(
                elements?.workspace?.getAttribute(
                    "data-solomon-ai-public-web-selected"
                )
            ).toLowerCase() === "true"
        );
    }

    function applyPublicWebSelection(
        elements,
        selected
    ) {
        const normalizedSelection = selected === true;

        elements?.workspace?.setAttribute(
            "data-solomon-ai-public-web-selected",
            normalizedSelection ? "true" : "false"
        );

        if (elements?.publicWebToggle) {
            elements.publicWebToggle.checked = normalizedSelection;
        }

        return normalizedSelection;
    }

    function setPublicWebStatus(elements, message, variant) {
        if (!elements?.publicWebStatus) {
            return;
        }

        const cleanMessage = cleanValue(message);

        elements.publicWebStatus.textContent = cleanMessage;
        elements.publicWebStatus.hidden = !cleanMessage;
        elements.publicWebStatus.setAttribute(
            "data-solomon-ai-public-web-status-variant",
            cleanValue(variant) || "info"
        );
    }

    function getSourceRemoveEndpoint(elements, documentId) {
        const conversationId = navigation.getConversationId(elements);
        const cleanDocumentId = cleanValue(documentId);

        if (!conversationId || !cleanDocumentId) {
            return "";
        }

        return (
            "/workspace/solomon/conversations/" +
            encodeURIComponent(conversationId) +
            "/sources/" +
            encodeURIComponent(cleanDocumentId)
        );
    }

    function setSourceStatus(elements, message, variant) {
        const panel = elements.sourceList?.parentElement;
        let status = panel?.querySelector(
            "[data-solomon-ai-source-status]"
        );

        if (!panel) {
            return;
        }

        if (!status) {
            status = document.createElement("p");
            status.className = "solomon-ai-sources__status";
            status.setAttribute("data-solomon-ai-source-status", "");
            status.setAttribute("role", "status");
            status.setAttribute("aria-live", "polite");
            panel.insertBefore(status, elements.sourceList);
        }

        const cleanMessage = cleanValue(message);

        status.textContent = cleanMessage;
        status.hidden = !cleanMessage;
        status.setAttribute(
            "data-solomon-ai-source-status-variant",
            cleanValue(variant) || "info"
        );
    }

    function refreshPresentation(elements) {
        modules.getModule("source_state")
            ?.updateSourceState?.(elements);
        modules.getModule("source_preview_interactions")
            ?.refresh?.(elements);
    }

    function validateSourcePacket(elements, packet) {
        return Boolean(
            packet?.ok !== false &&
            cleanValue(packet?.contract) === getSourceContract(elements) &&
            cleanValue(packet?.conversation_id) ===
                navigation.getConversationId(elements) &&
            Array.isArray(packet?.sources)
        );
    }

    function applySourcePacket(elements, packet, options) {
        if (!validateSourcePacket(elements, packet)) {
            throw new Error("The server returned an invalid file list.");
        }

        const preserveExisting = (
            options?.preserveExisting === true &&
            sourceMembershipMatches(elements, packet.sources)
        );

        applyPublicWebSelection(
            elements,
            packet?.public_web_selected === true
        );

        if (preserveExisting) {
            refreshPresentation(elements);
        } else {
            modules.requireModule("source_list")
                .renderConversationSources(elements, packet.sources);
        }

        elements.workspace.setAttribute(
            "data-solomon-ai-conversation-id",
            cleanValue(packet.conversation_id)
        );
        elements.workspace.setAttribute(
            "data-solomon-ai-source-contract",
            cleanValue(packet.contract)
        );
    }

    modules.registerModule("source_membership", {
        applyPublicWebSelection,
        applySourcePacket,
        getAttachedSourceIds,
        getPacketSourceIds,
        getSourceContract,
        getSourceCountLabel,
        getSourceId,
        getSourceItems,
        getSourceMode,
        getSourceRemoveEndpoint,
        getSourcesEndpoint,
        getPublicWebEndpoint,
        isPublicWebSelected,
        refreshPresentation,
        setPublicWebStatus,
        setSourceStatus,
        sourceMembershipMatches,
        validateSourcePacket
    });
})(window, document);