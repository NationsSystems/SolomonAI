/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_source_preview.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI attached-file preview presentation.

   Builds and controls the preview surface for files already authorized
   and serialized by the server. JavaScript does not decide file access,
   conversation membership, or Reader authority.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before source preview."
        );
    }

    const contract = modules.requireModule("contract");
    const { constants, cleanValue } = contract;
    const WORKSPACE_LISTING_CONTRACT_FALLBACK =
        "nations_workspace_listing_v1";
    const DOCUMENTS_MODULE_ID = "documents";
    const DEFAULT_SOLOMON_WORKSPACE_ROUTE = "/ai";

    function getSourceItems(elements) {
        return Array.from(
            elements?.sourceList?.querySelectorAll(
                "[data-solomon-ai-source]"
            ) || []
        );
    }

    function getSourceItemName(item) {
        return cleanValue(
            item?.getAttribute("data-solomon-ai-source-name") ||
            item?.querySelector(
                ".solomon-ai-source-item__copy strong"
            )?.textContent ||
            item?.querySelector("strong")?.textContent
        ) || "Workspace document";
    }

    function getSourceItemReaderUrl(item) {
        return cleanValue(
            item?.getAttribute("data-solomon-ai-source-reader-url") ||
            item?.querySelector(
                "[data-solomon-ai-source-reader-url]"
            )?.getAttribute("href") ||
            item?.querySelector(
                ".solomon-ai-source-item__open"
            )?.getAttribute("href")
        );
    }

    function getSourceItemId(item, readerUrl) {
        const explicitId = cleanValue(
            item?.getAttribute("data-solomon-ai-source-id") ||
            item?.getAttribute("data-document-id") ||
            item?.getAttribute("data-workspace-object-id")
        );

        if (explicitId) {
            return explicitId;
        }

        const url = getSameOriginUrl(readerUrl);
        const pathParts = url?.pathname
            .split("/")
            .filter(Boolean) || [];

        if (
            pathParts.length >= 3 &&
            pathParts[0] === "workspace" &&
            (pathParts[1] === "file" || pathParts[1] === "document")
        ) {
            try {
                return decodeURIComponent(pathParts[2]);
            } catch (_error) {
                return pathParts[2] || "";
            }
        }

        return "";
    }

    function getSourceItemMimeType(item) {
        return cleanValue(
            item?.getAttribute("data-solomon-ai-source-mime") ||
            item?.getAttribute("data-document-mime") ||
            item?.getAttribute("data-workspace-object-mime")
        );
    }

    function getSameOriginUrl(value) {
        const cleanUrl = cleanValue(value);

        if (!cleanUrl) {
            return null;
        }

        try {
            const url = new URL(cleanUrl, window.location.origin);
            return url.origin === window.location.origin ? url : null;
        } catch (error) {
            return null;
        }
    }

    function getRelativeUrl(url) {
        if (!url) {
            return "";
        }

        return `${url.pathname}${url.search}${url.hash}`;
    }

    function isWorkspaceReaderRoute(value) {
        const url = getSameOriginUrl(value);
        const pathParts = url?.pathname
            .split("/")
            .filter(Boolean) || [];

        return (
            pathParts.length >= 4 &&
            pathParts[0] === "workspace" &&
            (pathParts[1] === "file" || pathParts[1] === "document") &&
            pathParts[3] === "reader"
        );
    }

    function getRightPaneCallerRoute() {
        const route = `${window.location.pathname || "/"}${window.location.search || ""}${window.location.hash || ""}`;

        if (isWorkspaceReaderRoute(route)) {
            return DEFAULT_SOLOMON_WORKSPACE_ROUTE;
        }

        return route.startsWith("/")
            ? route
            : DEFAULT_SOLOMON_WORKSPACE_ROUTE;
    }

    function appendReaderBackRoute(readerUrl, backRoute) {
        const url = getSameOriginUrl(readerUrl);
        const cleanBackRoute = cleanValue(backRoute);

        if (!url || !isWorkspaceReaderRoute(getRelativeUrl(url))) {
            return "";
        }

        if (
            !cleanBackRoute ||
            !cleanBackRoute.startsWith("/") ||
            isWorkspaceReaderRoute(cleanBackRoute)
        ) {
            return getRelativeUrl(url);
        }

        url.searchParams.set("back", cleanBackRoute);

        return getRelativeUrl(url);
    }

    function buildReaderUrlWithReturn(readerUrl) {
        return appendReaderBackRoute(
            readerUrl,
            getRightPaneCallerRoute()
        );
    }

    function buildReaderThumbnailUrl(readerUrl) {
        const url = getSameOriginUrl(readerUrl);

        if (!url) {
            return "";
        }

        url.search = "";
        url.hash = "";

        if (!url.pathname.endsWith("/reader")) {
            return "";
        }

        url.pathname = `${url.pathname}/thumbnail.png`;
        return url.pathname;
    }

    function getSharedListingContract() {
        return cleanValue(
            window.NationsCommandSidebar?.constants?.WORKSPACE_LISTING_CONTRACT
        ) || WORKSPACE_LISTING_CONTRACT_FALLBACK;
    }

    function setOptionalAttribute(element, name, value) {
        const clean = cleanValue(value);

        if (clean) {
            element.setAttribute(name, clean);
        } else {
            element.removeAttribute(name);
        }
    }

    function applySourceReaderLaunchContract(open, item, sourceName, readerUrl, fullReaderUrl) {
        const sourceId = getSourceItemId(item, readerUrl);
        const mimeType = getSourceItemMimeType(item);
        const callerRoute = getRightPaneCallerRoute();

        if (!open) {
            return;
        }

        open.setAttribute("data-workspace-object", "");
        open.setAttribute("data-workspace-object-type", "file");
        open.setAttribute("data-workspace-object-kind", "file");
        open.setAttribute("data-workspace-object-route", fullReaderUrl);
        open.setAttribute("data-workspace-object-module", DOCUMENTS_MODULE_ID);
        open.setAttribute("data-workspace-object-open-enabled", "true");
        open.setAttribute("data-workspace-listing-contract", getSharedListingContract());

        setOptionalAttribute(open, "data-workspace-object-id", sourceId);
        setOptionalAttribute(open, "data-workspace-object-name", sourceName);
        setOptionalAttribute(open, "data-workspace-object-mime", mimeType);

        setOptionalAttribute(open, "data-document-id", sourceId);
        setOptionalAttribute(open, "data-document-name", sourceName);
        open.setAttribute("data-document-route", fullReaderUrl);
        open.setAttribute("data-document-open-enabled", "true");
        setOptionalAttribute(open, "data-document-reader-url", fullReaderUrl);
        setOptionalAttribute(open, "data-document-mime", mimeType);

        open.setAttribute("data-command-route", fullReaderUrl);
        open.setAttribute("data-command-module", DOCUMENTS_MODULE_ID);
        open.setAttribute("data-command-shell-navigation", "true");

        open.setAttribute("data-solomon-ai-source-reader-url", fullReaderUrl);
        open.setAttribute("data-solomon-ai-source-reader-back-route", callerRoute);
        open.setAttribute("data-right-pane-content-launch", "reader");
        open.setAttribute("data-right-pane-content-back-route", callerRoute);
    }

    function createSourcePreview(elements) {
        const previewId = constants.SOURCE_PREVIEW_ID;
        const template = document.createElement("template");

        template.innerHTML = `
            <section id="${previewId}" class="solomon-ai-source-preview"
                data-solomon-ai-source-preview role="dialog"
                aria-modal="false" aria-labelledby="${previewId}-title" hidden>
                <header class="solomon-ai-source-preview__header">
                    <div class="solomon-ai-source-preview__header-copy">
                        <span class="solomon-ai-source-preview__eyebrow">File preview</span>
                        <strong id="${previewId}-title"
                            class="solomon-ai-source-preview__title"
                            data-solomon-ai-source-preview-title></strong>
                    </div>
                    <button type="button" class="solomon-ai-source-preview__close"
                        data-solomon-ai-source-preview-close
                        aria-label="Close file preview" title="Close preview">
                        <span class="icon" aria-hidden="true">close</span>
                    </button>
                </header>
                <div class="solomon-ai-source-preview__body">
                    <div class="solomon-ai-source-preview__media"
                        data-solomon-ai-source-preview-media>
                        <img class="solomon-ai-source-preview__image"
                            data-solomon-ai-source-preview-image alt="">
                        <div class="solomon-ai-source-preview__fallback"
                            data-solomon-ai-source-preview-fallback hidden>
                            <span class="solomon-ai-source-preview__fallback-icon icon"
                                aria-hidden="true">description</span>
                            <span class="solomon-ai-source-preview__fallback-text">
                                A quick preview is not available for this file type.
                            </span>
                        </div>
                    </div>
                </div>
                <footer class="solomon-ai-source-preview__footer">
                    <a class="solomon-ai-source-preview__open"
                        data-solomon-ai-source-reader-url>
                        <span class="icon" aria-hidden="true">open_in_new</span>
                        <span>Open in Reader</span>
                    </a>
                </footer>
            </section>
        `.trim();

        const preview = template.content.firstElementChild;
        (elements.sourceList?.parentElement || elements.workspace).append(
            preview
        );
        elements.sourcePreview = preview;
        return preview;
    }

    function ensureSourcePreview(elements) {
        if (elements.sourcePreview?.isConnected) {
            return elements.sourcePreview;
        }

        const preview = elements.workspace.querySelector(
            "[data-solomon-ai-source-preview]"
        );

        if (preview) {
            elements.sourcePreview = preview;
            return preview;
        }

        return createSourcePreview(elements);
    }

    function setPreviewFallback(preview, visible) {
        const image = preview?.querySelector(
            "[data-solomon-ai-source-preview-image]"
        );
        const fallback = preview?.querySelector(
            "[data-solomon-ai-source-preview-fallback]"
        );

        if (image) {
            image.hidden = visible;
        }

        if (fallback) {
            fallback.hidden = !visible;
        }
    }

    function closeSourcePreview(elements, options) {
        const preview = elements.sourcePreview ||
            elements.workspace.querySelector(
                "[data-solomon-ai-source-preview]"
            );

        if (!preview || preview.hidden) {
            return false;
        }

        const activeItem = elements.sourceList?.querySelector(
            "[data-solomon-ai-source-preview-state='open']"
        );
        const focusTarget = activeItem?.querySelector(
            "[data-solomon-ai-source-preview-trigger]"
        );

        preview.hidden = true;
        preview.removeAttribute("data-solomon-ai-source-id");
        preview.removeAttribute("data-solomon-ai-source-reader-url");
        preview.removeAttribute("data-solomon-ai-source-reader-back-route");

        getSourceItems(elements).forEach(function (item) {
            item.removeAttribute(
                "data-solomon-ai-source-preview-state"
            );

            item.querySelectorAll(
                "[data-solomon-ai-source-preview-trigger]"
            ).forEach(function (trigger) {
                trigger.setAttribute(
                    "aria-expanded",
                    "false"
                );
            });
        });

        if (
            options?.focus === true &&
            focusTarget?.isConnected
        ) {
            focusTarget.focus({
                preventScroll: true
            });
        }

        return true;
    }

    function openSourcePreview(elements, item, trigger) {
        const readerUrl = getSourceItemReaderUrl(item);
        const fullReaderUrl = buildReaderUrlWithReturn(
            readerUrl
        );

        if (!readerUrl || !fullReaderUrl) {
            return false;
        }

        const preview = ensureSourcePreview(elements);
        const sourceName = getSourceItemName(item);
        const sourceId = getSourceItemId(item, readerUrl);
        const title = preview.querySelector(
            "[data-solomon-ai-source-preview-title]"
        );
        const image = preview.querySelector(
            "[data-solomon-ai-source-preview-image]"
        );
        const open = preview.querySelector(
            "[data-solomon-ai-source-reader-url]"
        );
        const thumbnailUrl = cleanValue(
            item?.getAttribute(
                "data-solomon-ai-source-thumbnail-url"
            )
        ) || buildReaderThumbnailUrl(readerUrl);

        getSourceItems(elements).forEach(function (sourceItem) {
            const active = sourceItem === item;

            sourceItem.setAttribute(
                "data-solomon-ai-source-preview-state",
                active ? "open" : "closed"
            );

            sourceItem.querySelectorAll(
                "[data-solomon-ai-source-preview-trigger]"
            ).forEach(function (sourceTrigger) {
                sourceTrigger.setAttribute(
                    "aria-expanded",
                    active ? "true" : "false"
                );
            });
        });

        if (title) {
            title.textContent = sourceName;
            title.title = sourceName;
        }

        if (open) {
            open.href = fullReaderUrl;
            open.setAttribute(
                "aria-label",
                `Open ${sourceName} in Reader`
            );
            applySourceReaderLaunchContract(
                open,
                item,
                sourceName,
                readerUrl,
                fullReaderUrl
            );
        }

        if (image) {
            image.onload = function () {
                setPreviewFallback(
                    preview,
                    false
                );
            };

            image.onerror = function () {
                setPreviewFallback(
                    preview,
                    true
                );
            };

            image.alt = `Preview of ${sourceName}`;

            if (thumbnailUrl) {
                setPreviewFallback(
                    preview,
                    false
                );
                image.src = thumbnailUrl;
            } else {
                image.removeAttribute("src");
                setPreviewFallback(
                    preview,
                    true
                );
            }
        }

        preview.setAttribute(
            "data-solomon-ai-source-id",
            sourceId
        );
        preview.setAttribute(
            "data-solomon-ai-source-reader-url",
            fullReaderUrl
        );
        preview.setAttribute(
            "data-solomon-ai-source-reader-back-route",
            getRightPaneCallerRoute()
        );
        preview.hidden = false;

        trigger?.setAttribute(
            "aria-expanded",
            "true"
        );

        return true;
    }

    modules.registerModule(
        "source_preview",
        {
            appendReaderBackRoute,
            buildReaderThumbnailUrl,
            buildReaderUrlWithReturn,
            closeSourcePreview,
            ensureSourcePreview,
            getRightPaneCallerRoute,
            getSourceItemName,
            getSourceItemReaderUrl,
            getSourceItems,
            openSourcePreview
        }
    );
})(window, document);