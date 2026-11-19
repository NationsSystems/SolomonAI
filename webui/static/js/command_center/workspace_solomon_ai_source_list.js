/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_source_list.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI attached-file list rendering.

   Converts server-authorized source packets into source-list controls.
   JavaScript renders only server-returned metadata and does not decide
   file access, source membership, or Reader authority.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before source list."
        );
    }

    const contract = modules.requireModule("contract");
    const preview = modules.requireModule("source_preview");
    const membership = modules.requireModule("source_membership");
    const { constants, cleanValue } = contract;

    function setAttributes(element, attributes) {
        Object.entries(attributes).forEach(function (entry) {
            element.setAttribute(entry[0], entry[1]);
        });

        return element;
    }

    function getSourceName(source) {
        return cleanValue(
            source?.original_name ||
            source?.filename ||
            source?.document_id ||
            source?.random_name
        ) || "Workspace document";
    }

    function getSourceReaderUrl(source) {
        return cleanValue(
            source?.reader_url ||
            source?.workspace_reader_url
        );
    }

    function getSourceIconName(source) {
        const name = getSourceName(source).toLowerCase();

        if (name.endsWith(".pdf")) {
            return "picture_as_pdf";
        }

        if (/\.(png|jpe?g|webp|gif|tiff?)$/.test(name)) {
            return "image";
        }

        if (/\.(xlsx?|csv)$/.test(name)) {
            return "table_view";
        }

        return "description";
    }

    function createIcon(className, iconName) {
        const icon = document.createElement("span");

        icon.className = className;
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = iconName;

        return icon;
    }

    function createPreviewCopy(sourceName) {
        const copy = document.createElement("button");
        const name = document.createElement("strong");
        const membershipLabel = document.createElement("span");

        copy.type = "button";
        copy.className = "solomon-ai-source-item__copy";
        setAttributes(copy, {
            "data-solomon-ai-source-preview-trigger": "",
            "aria-haspopup": "dialog",
            "aria-controls": constants.SOURCE_PREVIEW_ID,
            "aria-expanded": "false",
            "aria-label": `Preview ${sourceName}`
        });

        name.title = sourceName;
        name.textContent = sourceName;
        membershipLabel.textContent = "Added to this chat";
        copy.append(name, membershipLabel);

        return copy;
    }

    function createPreviewButton(sourceName) {
        const button = document.createElement("button");

        button.type = "button";
        button.className = "solomon-ai-source-item__open";
        button.title = "Preview file";
        setAttributes(button, {
            "data-solomon-ai-source-preview-trigger": "",
            "aria-haspopup": "dialog",
            "aria-controls": constants.SOURCE_PREVIEW_ID,
            "aria-expanded": "false",
            "aria-label": `Preview ${sourceName}`
        });
        button.append(createIcon("icon", "visibility"));

        return button;
    }

    function createRemoveButton(elements, sourceId, sourceName) {
        const button = document.createElement("button");

        button.type = "button";
        button.className = "solomon-ai-source-item__remove";
        button.title = "Remove file";
        setAttributes(button, {
            "data-solomon-ai-source-remove": "",
            "data-document-id": sourceId,
            "data-solomon-ai-source-remove-url":
                membership.getSourceRemoveEndpoint(elements, sourceId),
            "aria-label": `Remove ${sourceName} from this chat`
        });
        button.append(createIcon("icon", "close"));

        return button;
    }

    function createSourceItem(elements, source) {
        const sourceId = membership.getSourceId(source);
        const sourceName = getSourceName(source);
        const readerUrl = getSourceReaderUrl(source);

        if (!sourceId) {
            return null;
        }

        const item = document.createElement("article");

        item.className = "solomon-ai-source-item";
        setAttributes(item, {
            "data-solomon-ai-source": "",
            "data-solomon-ai-source-id": sourceId,
            "data-solomon-ai-source-state": "attached",
            "data-document-id": sourceId,
            "data-solomon-ai-source-name": sourceName
        });

        if (readerUrl) {
            setAttributes(item, {
                "data-solomon-ai-source-reader-url": readerUrl,
                "data-solomon-ai-source-thumbnail-url":
                    preview.buildReaderThumbnailUrl(readerUrl)
            });
        }

        item.append(
            createIcon(
                "solomon-ai-source-item__icon icon",
                getSourceIconName(source)
            ),
            createPreviewCopy(sourceName)
        );

        if (readerUrl) {
            item.append(createPreviewButton(sourceName));
        }

        item.append(
            createRemoveButton(elements, sourceId, sourceName)
        );

        return item;
    }

    function renderConversationSources(elements, sources) {
        if (!elements?.sourceList) {
            return 0;
        }

        const safeSources = Array.isArray(sources) ? sources : [];
        const fragment = document.createDocumentFragment();
        let renderedCount = 0;

        preview.closeSourcePreview(elements);

        safeSources.forEach(function (source) {
            const item = createSourceItem(elements, source);

            if (item) {
                fragment.append(item);
                renderedCount += 1;
            }
        });

        elements.sourceList.replaceChildren(fragment);
        membership.refreshPresentation(elements);

        return renderedCount;
    }

    modules.registerModule("source_list", {
        createSourceItem,
        getSourceIconName,
        getSourceName,
        getSourceReaderUrl,
        renderConversationSources
    });
})(window, document);