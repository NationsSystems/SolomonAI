/* -------------------------------------------------------------------
   FILE: workspace_document_preview.js
   DIRECTORY: webui/static/js/command_center/
   Solomon Documents preview and inspector rendering contract
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentPreview";
    const RECORDS_API_NAME = "SolomonWorkspaceDocumentRecords";
    const LIBRARY_API_NAME = "SolomonWorkspaceDocumentLibrary";

    const INSPECTOR_SELECTOR = "[data-document-inspector]";
    const BID_SCOPE_OPERATION_KEY = "bid_scope_review";
    const BID_SCOPE_OPERATION_LABEL = "Bid & Scope Review";
    const DEFAULT_OPERATION_LABEL = "Document Operation";
    const BID_SCOPE_REPORT_CREATE_PATH = "/workspace/document-operation/report/create";
    const REPORT_STATUS_POLL_MS = 2200;
    const REPORT_STATUS_MAX_POLLS = 180;
    const REPORT_FETCH_TIMEOUT_MS = 12000;
    const DOCUMENTS_MODULE_ID = "documents";
    const WORKSPACE_LISTING_CONTRACT_FALLBACK =
        "nations_workspace_listing_v1";
    const DOCUMENT_METADATA_CONTRACT =
        "workspace_document_metadata_v1";
    const DETAIL_UNAVAILABLE = Object.freeze({
        size: "Size unavailable",
        date: "Date unavailable",
        location: "Location unavailable"
    });


    if (window[API_NAME]) {
        return;
    }

    const Records = window[RECORDS_API_NAME];
    const Library = window[LIBRARY_API_NAME];

    if (!Records || !Library) {
        console.error("[DOCUMENT_PREVIEW] Missing required Solomon document modules.");
        return;
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

        element.textContent = text || "";
        return element;
    }

    function hiddenInput(name, value) {
        const input = document.createElement("input");

        input.type = "hidden";
        input.name = name || "";
        input.value = value || "";

        return input;
    }

    function actionButton(className, dataName, dataValue, iconName, label) {
        const button = document.createElement("button");
        const icon = textElement("span", "icon", iconName);
        const labelNode = textElement("span", "", label);

        button.type = "button";
        button.className = className || "workspace-document-command";
        button.setAttribute(dataName, dataValue || "");
        button.append(icon, labelNode);

        return button;
    }

    function submitActionButton(className, iconName, label) {
        const button = document.createElement("button");

        button.type = "submit";
        button.className = className || "workspace-document-command";
        button.append(
            textElement("span", "icon", iconName),
            textElement("span", "", label)
        );

        return button;
    }

    function setSubmitButtonBusy(button, label) {
        if (!button) {
            return;
        }

        button.disabled = true;
        button.setAttribute("aria-busy", "true");
        button.replaceChildren(
            textElement("span", "icon", "sync"),
            textElement("span", "", label || "Preparing Report")
        );
    }

    function reportCreateForm(doc, explorer) {
        const form = document.createElement("form");
        const cleanDocumentId = cleanText(doc?.document_id || doc?.random_name || "");
        const submitButton = submitActionButton(
            "workspace-document-command workspace-document-command-primary",
            "rule_settings",
            "Run Bid & Scope Review"
        );

        form.method = "post";
        form.action = BID_SCOPE_REPORT_CREATE_PATH;
        form.className = "workspace-document-command-form workspace-document-command-form--report";
        form.setAttribute("data-document-report-create-form", "true");
        form.setAttribute("aria-label", "Create Bid & Scope Review report");

        form.append(
            hiddenInput("operation", BID_SCOPE_OPERATION_KEY),
            hiddenInput("document_ids", cleanDocumentId),
            submitButton
        );

        form.addEventListener("submit", function (event) {
            if (!window.fetch) {
                setSubmitButtonBusy(submitButton, "Opening Report");
                return;
            }

            event.preventDefault();

            if (form.getAttribute("data-document-report-running") === "true") {
                return;
            }

            form.setAttribute("data-document-report-running", "true");
            setSubmitButtonBusy(submitButton, "Preparing Report");
            startContentPanelReport(explorer, doc, form).catch(function (error) {
                if (error?.canceled) {
                    return;
                }

                renderReportTransportError(
                    explorer,
                    error?.message || "The report could not be prepared.",
                    doc,
                    error?.fallbackUrl || ""
                );
            });
        });

        return form;
    }

    function reportOpenButton(doc, explorer) {
        const button = actionButton(
            "workspace-document-command workspace-document-command-primary",
            "data-document-report-open",
            "true",
            "article",
            getDocumentReportActionLabel(doc)
        );

        button.setAttribute("aria-label", "Open existing Bid & Scope Review report");

        button.addEventListener("click", function () {
            if (button.disabled) {
                return;
            }

            button.disabled = true;
            button.setAttribute("aria-busy", "true");
            button.replaceChildren(
                textElement("span", "icon", "sync"),
                textElement("span", "", "Opening Report")
            );

            openExistingContentPanelReport(explorer, doc).catch(function (error) {
                if (error?.canceled) {
                    return;
                }

                renderReportTransportError(
                    explorer,
                    error?.message || "The report could not be opened.",
                    doc,
                    error?.fallbackUrl || getDocumentReportFallbackUrl(doc)
                );
            });
        });

        return button;
    }

    function reportCreateHandoffButton(doc) {
        const cleanDocumentId = cleanText(doc?.document_id || doc?.random_name || "");

        return actionButton(
            "workspace-document-command workspace-document-command-primary",
            "data-document-use-bid-scope",
            cleanDocumentId,
            "rule_settings",
            "Bid & Scope Review"
        );
    }

    function reportPrimaryAction(doc, explorer) {
        if (hasDocumentReport(doc)) {
            return reportOpenButton(doc, explorer);
        }

        return reportCreateHandoffButton(doc);
    }

    function disabledActionButton(iconName, label) {
        const button = document.createElement("button");

        button.type = "button";
        button.className = "workspace-document-command workspace-document-command-neutral";
        button.disabled = true;
        button.append(
            textElement("span", "icon", iconName),
            textElement("span", "", label)
        );

        return button;
    }

    function getWorkspaceSection(explorer) {
        const section = cleanText(
            explorer?.getAttribute("data-workspace-section") ||
            explorer?.getAttribute("data-active-section")
        ).toLowerCase();

        return section || "files";
    }

    function getWorkspaceSectionLabel(explorer) {
        const section = getWorkspaceSection(explorer);
        const labels = {
            files: "My Files",
            recent: "Recent",
            reports: "Reports",
            trash: "Trash"
        };

        return labels[section] || "My Files";
    }

    function getWorkspaceSectionRoute(explorer) {
        const section = getWorkspaceSection(explorer);
        const routes = {
            files: "/",
            recent: "/recent",
            reports: "/reports",
            trash: "/trash"
        };

        return routes[section] || "/";
    }

    function sectionViewButton(explorer, className, iconName, label) {
        return actionButton(
            className,
            "data-workspace-view",
            getWorkspaceSection(explorer),
            iconName,
            label || `Back to ${getWorkspaceSectionLabel(explorer)}`
        );
    }

    function breadcrumbLink(explorer, label) {
        const button = document.createElement("button");
        const sectionLabel = label || getWorkspaceSectionLabel(explorer);

        button.type = "button";
        button.className = "workspace-document-breadcrumb-link workspace-document-view-button";
        button.setAttribute("data-workspace-view", getWorkspaceSection(explorer));
        button.setAttribute("aria-label", `Open ${sectionLabel}`);
        button.setAttribute("title", `Open ${sectionLabel}`);
        button.append(textElement("span", "", sectionLabel));

        return button;
    }

    function renderInspectorNavigation(explorer, currentLabel) {
        const navigation = document.createElement("nav");
        const label = cleanText(currentLabel);

        navigation.className = "workspace-document-inspector-navigation workspace-document-breadcrumb";
        navigation.setAttribute("aria-label", "Content panel location");
        navigation.append(breadcrumbLink(explorer));

        if (label) {
            navigation.append(
                textElement("span", "workspace-document-breadcrumb-separator", "/"),
                textElement("span", "workspace-document-breadcrumb-current", label)
            );
        }

        return navigation;
    }

    function getInspector(explorer) {
        return explorer?.querySelector(INSPECTOR_SELECTOR) || null;
    }

    function getPreviewDocument(doc) {
        if (!doc) {
            return null;
        }

        return Records.normalizeDocument(doc);
    }

    function clearInspectorRenderState(inspector) {
        if (!inspector) {
            return;
        }

        inspector.removeAttribute("data-document-operation-render-state");
        inspector.removeAttribute("data-document-operation-render-signature");
        inspector.removeAttribute("data-document-operation-render-status");
        inspector.removeAttribute("data-document-report-transport-id");
        inspector.removeAttribute("data-document-report-transport-status");
        inspector.removeAttribute("data-document-summary-request-id");
    }

    function prepareInspector(inspector, options) {
        clearNode(inspector);
        clearInspectorRenderState(inspector);
        inspector.classList.toggle("workspace-document-inspector--danger", Boolean(options?.danger));
        inspector.removeAttribute("data-document-selection-state");
    }

    function cleanText(value) {
        return String(value || "").trim();
    }

    function getSameOriginUrl(value) {
        const cleanUrl = cleanText(value);

        if (!cleanUrl) {
            return null;
        }

        try {
            const url = new URL(cleanUrl, window.location.origin);
            return url.origin === window.location.origin ? url : null;
        } catch (_error) {
            return null;
        }
    }

    function getRelativeUrl(url) {
        if (!url) {
            return "";
        }

        return `${url.pathname}${url.search}${url.hash}`;
    }

    function getSameOriginRelativeRoute(value) {
        const url = getSameOriginUrl(value);

        return url ? getRelativeUrl(url) : "";
    }

    function fallbackToRoute(route) {
        const cleanRoute = cleanText(route);

        if (!cleanRoute) {
            return false;
        }

        window.location.assign(cleanRoute);
        return false;
    }

    function navigateRightPaneRoute(route, options) {
        const relativeRoute = getSameOriginRelativeRoute(route);
        const cleanRoute = relativeRoute || cleanText(route);
        const sidebarApi = window.NationsCommandSidebar || null;

        if (!cleanRoute) {
            return false;
        }

        if (
            relativeRoute &&
            sidebarApi &&
            typeof sidebarApi.loadWorkspace === "function"
        ) {
            try {
                const result = sidebarApi.loadWorkspace(
                    relativeRoute,
                    cleanText(options?.moduleId) || DOCUMENTS_MODULE_ID,
                    Object.assign(
                        {
                            push: true,
                            async: true,
                            source: "workspace_document_preview"
                        },
                        options || {}
                    )
                );

                if (result && typeof result.then === "function") {
                    result.then(function (resolved) {
                        if (resolved === false) {
                            fallbackToRoute(relativeRoute);
                        }
                    }).catch(function (error) {
                        console.warn(
                            "[DOCUMENT_PREVIEW] Async right-pane navigation failed; falling back to hard navigation.",
                            error
                        );
                        fallbackToRoute(relativeRoute);
                    });
                } else if (result === false) {
                    fallbackToRoute(relativeRoute);
                }

                return true;
            } catch (error) {
                console.warn(
                    "[DOCUMENT_PREVIEW] Async right-pane navigation failed; falling back to hard navigation.",
                    error
                );
                fallbackToRoute(relativeRoute);
                return true;
            }
        }

        return fallbackToRoute(cleanRoute);
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

    function getRightPaneCallerRoute(explorer) {
        const route = [
            window.location.pathname || "/",
            window.location.search || "",
            window.location.hash || ""
        ].join("");

        if (isWorkspaceReaderRoute(route)) {
            return getWorkspaceSectionRoute(explorer);
        }

        return route.startsWith("/") ? route : getWorkspaceSectionRoute(explorer);
    }

    function appendReaderBackRoute(readerUrl, backRoute) {
        const url = getSameOriginUrl(readerUrl);
        const cleanBackRoute = cleanText(backRoute);

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

        if (!url.searchParams.has("back")) {
            url.searchParams.set("back", cleanBackRoute);
        }

        return getRelativeUrl(url);
    }

    function getDocumentReaderRoute(doc, explorer) {
        const documentId = getPreviewDocumentId(doc);
        const explicitReaderUrl = cleanText(
            doc?.reader_url ||
            doc?.readerUrl ||
            doc?.workspace_reader_url ||
            doc?.workspaceReaderUrl ||
            doc?.document_reader_url ||
            doc?.documentReaderUrl
        );
        const fallbackReaderUrl = documentId
            ? `/workspace/file/${encodeURIComponent(documentId)}/reader`
            : "";

        return appendReaderBackRoute(
            explicitReaderUrl || fallbackReaderUrl,
            getRightPaneCallerRoute(explorer)
        );
    }

    function getDocumentMimeType(doc) {
        return cleanText(
            doc?.mime_type ||
            doc?.mimeType ||
            doc?.mime ||
            doc?.content_type ||
            doc?.contentType
        );
    }

    function getSharedListingContract() {
        return cleanText(
            window.NationsCommandSidebar?.constants?.WORKSPACE_LISTING_CONTRACT
        ) || WORKSPACE_LISTING_CONTRACT_FALLBACK;
    }

    function setOptionalAttribute(element, name, value) {
        const cleanValue = cleanText(value);

        if (cleanValue) {
            element.setAttribute(name, cleanValue);
        } else {
            element.removeAttribute(name);
        }
    }

    function applyReaderLaunchContract(button, explorer, rawDoc, options) {
        const doc = getPreviewDocument(rawDoc) || {};
        const isFolder = isPreviewFolderDocument(rawDoc) || isPreviewFolderDocument(doc);
        const documentId = isFolder
            ? ""
            : cleanText(options?.documentId) || getPreviewDocumentId(doc);
        const documentName = cleanText(options?.documentName) || getDocumentDisplayName(doc);
        const readerUrl = isFolder
            ? ""
            : cleanText(options?.readerUrl) || getDocumentReaderRoute(doc, explorer);
        const callerRoute = getRightPaneCallerRoute(explorer);
        const mimeType = isFolder ? "" : cleanText(options?.mimeType) || getDocumentMimeType(doc);
        const objectKind = isFolder ? "folder" : "file";
        const canOpen = Boolean(documentId && readerUrl && !isFolder);

        if (!button) {
            return null;
        }

        setOptionalAttribute(button, "data-document-id", documentId);
        setOptionalAttribute(button, "data-document-name", documentName);
        setOptionalAttribute(button, "data-document-route", readerUrl);
        setOptionalAttribute(button, "data-document-reader-url", readerUrl);
        setOptionalAttribute(button, "data-document-mime", mimeType);
        button.setAttribute("data-document-open-enabled", canOpen ? "true" : "false");

        setOptionalAttribute(button, "data-workspace-object-id", documentId);
        setOptionalAttribute(button, "data-workspace-object-name", documentName);
        button.setAttribute("data-workspace-object-type", objectKind);
        button.setAttribute("data-workspace-object-kind", objectKind);
        setOptionalAttribute(button, "data-workspace-object-route", readerUrl);
        button.setAttribute("data-workspace-object-module", DOCUMENTS_MODULE_ID);
        button.setAttribute("data-workspace-object-open-enabled", canOpen ? "true" : "false");
        setOptionalAttribute(button, "data-workspace-object-mime", mimeType);
        button.setAttribute("data-workspace-listing-contract", getSharedListingContract());

        setOptionalAttribute(button, "data-command-route", readerUrl);
        button.setAttribute("data-command-module", DOCUMENTS_MODULE_ID);
        button.setAttribute("data-command-shell-navigation", "true");

        if (readerUrl) {
            button.setAttribute("data-right-pane-content-launch", "reader");
            button.setAttribute("data-right-pane-content-back-route", callerRoute);
        } else {
            button.removeAttribute("data-right-pane-content-launch");
            button.removeAttribute("data-right-pane-content-back-route");
        }

        button.disabled = !canOpen;

        return button;
    }

    function createReaderOpenButton(explorer, rawDoc, label, options) {
        const doc = getPreviewDocument(rawDoc) || {};
        const documentId = cleanText(options?.documentId) || getPreviewDocumentId(doc);
        const button = actionButton(
            cleanText(options?.className) || "workspace-document-command",
            "data-document-open",
            documentId,
            "open_in_new",
            label || "Open Reader"
        );

        return applyReaderLaunchContract(
            button,
            explorer,
            doc,
            options || {}
        );
    }

    function normalizeText(value) {
        if (typeof value === "string") {
            return value.trim();
        }

        if (Array.isArray(value)) {
            return value
                .map(normalizeText)
                .filter(Boolean)
                .join("\n\n")
                .trim();
        }

        if (value && typeof value === "object") {
            return JSON.stringify(value, null, 2);
        }

        return cleanText(value);
    }

    function readNestedValue(source, path) {
        let current = source;

        String(path || "").split(".").forEach(function (key) {
            if (!current || typeof current !== "object") {
                current = null;
                return;
            }

            current = current[key];
        });

        return current;
    }

    function titleCase(value) {
        return cleanText(value)
            .replace(/[_-]+/g, " ")
            .replace(/\s+/g, " ")
            .replace(/\b\w/g, function (match) {
                return match.toUpperCase();
            });
    }

    function escapeRegExp(value) {
        return cleanText(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    }

    function getDisplayOperationLabel(value) {
        const label = cleanText(value);

        if (!label) {
            return "";
        }

        if (label.toLowerCase() === BID_SCOPE_OPERATION_KEY) {
            return BID_SCOPE_OPERATION_LABEL;
        }

        if (/[_-]/.test(label)) {
            return titleCase(label);
        }

        return label;
    }

    function getOperationLabel(response, options) {
        return (
            getDisplayOperationLabel(options?.operationLabel) ||
            getDisplayOperationLabel(response?.operation_label) ||
            DEFAULT_OPERATION_LABEL
        );
    }

    function getOperationStatus(response) {
        return cleanText(response?.status).toLowerCase();
    }

    function isPendingOperationResponse(response) {
        const status = getOperationStatus(response);

        return Boolean(response?.job_id) && ["queued", "submitted", "running"].includes(status);
    }

    function isReportArtifactResponse(response) {
        const artifactType = cleanText(response?.artifact_type).toLowerCase();
        const operation = cleanText(response?.operation || response?.operation_key).toLowerCase();
        const operationLabel = getDisplayOperationLabel(response?.operation_label);

        return (
            artifactType === "report" ||
            operation === BID_SCOPE_OPERATION_KEY ||
            operationLabel === BID_SCOPE_OPERATION_LABEL
        );
    }

    function getReportSurfaceUrl(response) {
        return (
            cleanText(response?.fragment_url) ||
            cleanText(response?.preparing_url) ||
            cleanText(response?.report_url) ||
            cleanText(response?.result_url)
        );
    }

    function openReportSurfaceIfAvailable(response) {
        const reportSurfaceUrl = isReportArtifactResponse(response)
            ? getReportSurfaceUrl(response)
            : "";

        if (!reportSurfaceUrl) {
            return false;
        }

        return navigateRightPaneRoute(
            reportSurfaceUrl,
            {
                launchMode: "report_surface",
                source: "workspace_document_preview_report"
            }
        );
    }

    function getOperationDocumentName(response, options) {
        return (
            cleanText(options?.documentName) ||
            cleanText(response?.document?.original_name) ||
            cleanText(response?.document?.filename) ||
            cleanText(response?.document?.random_name) ||
            "Selected file"
        );
    }

    function getOperationDocumentId(response, options) {
        return (
            cleanText(options?.documentId) ||
            cleanText(response?.document?.document_id) ||
            cleanText(response?.document?.random_name) ||
            cleanText(response?.document?.file_id)
        );
    }

    function getDocumentDisplayName(doc) {
        if (isPreviewFolderDocument(doc)) {
            return cleanText(
                doc?.original_name ||
                doc?.display_name ||
                doc?.name ||
                doc?.title ||
                doc?.random_name
            ) || "Selected folder";
        }

        return cleanText(
            doc?.original_name ||
            doc?.display_name ||
            doc?.name ||
            doc?.filename ||
            doc?.random_name
        ) || "Selected file";
    }

    function getDocumentReportRecord(doc) {
        if (typeof Records.getDocumentReportRecord === "function") {
            return Records.getDocumentReportRecord(doc);
        }

        return doc?.report && typeof doc.report === "object" ? doc.report : {};
    }

    function hasDocumentReport(doc) {
        if (typeof Records.hasDocumentReport === "function") {
            return Records.hasDocumentReport(doc);
        }

        const report = getDocumentReportRecord(doc);

        return Boolean(
            report?.has_report ||
            report?.review_id ||
            report?.job_id ||
            report?.fragment_url ||
            report?.report_url
        );
    }

    function getDocumentReportActionLabel(doc) {
        if (typeof Records.getDocumentReportActionLabel === "function") {
            return Records.getDocumentReportActionLabel(doc);
        }

        return `Open ${BID_SCOPE_OPERATION_LABEL}`;
    }

    function buildReportJobUrl(pathSegment, jobId) {
        const cleanJobId = cleanText(jobId);

        if (!cleanJobId) {
            return "";
        }

        return `/workspace/document-operation/report/${pathSegment}/${encodeURIComponent(jobId)}`;
    }

    function getDocumentReportFragmentUrl(doc) {
        const report = getDocumentReportRecord(doc);

        return (
            cleanText(report?.fragment_url || doc?.report_fragment_url) ||
            buildReportJobUrl("fragment", report?.job_id || doc?.report_job_id)
        );
    }

    function getDocumentReportStatusUrl(doc) {
        const report = getDocumentReportRecord(doc);

        return (
            cleanText(report?.status_url || doc?.report_status_url) ||
            buildReportJobUrl("status", report?.job_id || doc?.report_job_id)
        );
    }

    function getDocumentReportFallbackUrl(doc) {
        const report = getDocumentReportRecord(doc);

        return (
            cleanText(report?.report_url || doc?.report_url) ||
            cleanText(report?.preparing_url || doc?.report_preparing_url) ||
            buildReportJobUrl("result", report?.job_id || doc?.report_job_id)
        );
    }

    function isPendingReportStatus(status) {
        return ["queued", "submitted", "running", "processing", "in_progress"].includes(
            cleanText(status).toLowerCase()
        );
    }

    function commitReportRecordToDocument(doc, createPayload, statusPayload) {
        if (!doc || typeof doc !== "object") {
            return;
        }

        const currentReport = doc.report && typeof doc.report === "object" ? doc.report : {};
        const jobId = cleanText(createPayload?.job_id || statusPayload?.job_id || currentReport.job_id);
        const fragmentUrl = cleanText(statusPayload?.fragment_url || createPayload?.fragment_url || currentReport.fragment_url);
        const reportUrl = cleanText(statusPayload?.report_url || createPayload?.report_url || currentReport.report_url);
        const preparingUrl = cleanText(statusPayload?.preparing_url || createPayload?.preparing_url || currentReport.preparing_url);
        const statusUrl = cleanText(createPayload?.status_url || statusPayload?.status_url || currentReport.status_url);
        const status = cleanText(statusPayload?.status || createPayload?.status || currentReport.status || "complete");

        doc.report = {
            ...currentReport,
            operation_label: cleanText(createPayload?.operation_label || currentReport.operation_label) || BID_SCOPE_OPERATION_LABEL,
            status,
            job_id: jobId,
            fragment_url: fragmentUrl,
            report_url: reportUrl,
            preparing_url: preparingUrl,
            status_url: statusUrl,
            has_report: true
        };

        doc.report_status = status;
        doc.report_job_id = jobId;
        doc.report_fragment_url = fragmentUrl;
        doc.report_url = reportUrl;
        doc.report_preparing_url = preparingUrl;
        doc.report_status_url = statusUrl;
        doc.has_report = true;
    }

    function createReportTransportId() {
        if (window.crypto && typeof window.crypto.randomUUID === "function") {
            return window.crypto.randomUUID();
        }

        return `report-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }

    function markReportTransport(explorer, transportId, status) {
        const inspector = getInspector(explorer);

        if (!inspector || !transportId) {
            return;
        }

        inspector.setAttribute("data-document-report-transport-id", transportId);
        inspector.setAttribute("data-document-report-transport-status", status || "opening");
    }

    function isActiveReportTransport(explorer, transportId) {
        const inspector = getInspector(explorer);

        return (
            Boolean(inspector) &&
            inspector.getAttribute("data-document-report-transport-id") === transportId
        );
    }

    function setReportStatus(explorer, transportId, message) {
        const inspector = getInspector(explorer);

        if (!isActiveReportTransport(explorer, transportId)) {
            return;
        }

        const statusNode = inspector.querySelector("[data-document-report-status-copy]");

        if (statusNode && message) {
            statusNode.textContent = message;
        }
    }

    async function fetchWithTimeout(url, options, timeoutMs) {
        if (!window.AbortController) {
            return window.fetch(url, options);
        }

        const controller = new AbortController();
        const timeout = window.setTimeout(function () {
            controller.abort();
        }, timeoutMs || REPORT_FETCH_TIMEOUT_MS);

        try {
            return await window.fetch(url, {
                ...(options || {}),
                signal: controller.signal
            });
        } finally {
            window.clearTimeout(timeout);
        }
    }

    async function readJsonResponse(response) {
        const payload = await response.json().catch(function () {
            return {};
        });

        if (!response.ok || payload?.ok === false) {
            const error = new Error(
                cleanText(payload?.user_output) ||
                cleanText(payload?.status_label) ||
                cleanText(payload?.error) ||
                "The report request failed."
            );
            error.payload = payload;
            error.fallbackUrl = cleanText(payload?.report_url || payload?.preparing_url);
            throw error;
        }

        return payload;
    }

    function renderContentPanelReportPreparing(explorer, doc, transportId, options) {
        const inspector = getInspector(explorer);

        if (!inspector) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const documentName = getDocumentDisplayName(doc);
        const documentId = cleanText(doc?.document_id || doc?.random_name);
        const title = cleanText(options?.title) || "Preparing Bid & Scope Review";
        const statusCopy = cleanText(options?.statusCopy) || "Running background report job";
        const supportCopy = cleanText(options?.supportCopy) || "Building the commercial review artifact without blocking the browser.";
        const noticeCopy = cleanText(options?.noticeCopy) || "Reviewing scope language, exclusions, pricing terms, bid readiness signals, and commercial risk posture.";

        const body = document.createElement("div");
        const loader = document.createElement("div");
        const orbit = document.createElement("div");
        const copy = document.createElement("div");
        const actions = document.createElement("div");
        const backButton = actionButton(
            "workspace-document-command workspace-document-command-neutral",
            "data-document-report-cancel",
            "true",
            "arrow_back",
            "Back to File Details"
        );

        body.className = "workspace-document-inspector-body workspace-document-inspector-body--operation workspace-document-inspector-body--report-loading";
        loader.className = "workspace-report-preparation-loader";
        loader.setAttribute("role", "status");
        loader.setAttribute("aria-live", "polite");

        orbit.className = "workspace-report-preparation-orbit";
        orbit.setAttribute("aria-hidden", "true");
        orbit.append(
            textElement("span", "workspace-report-preparation-ring workspace-report-preparation-ring--outer", ""),
            textElement("span", "workspace-report-preparation-ring workspace-report-preparation-ring--middle", ""),
            textElement("span", "workspace-report-preparation-ring workspace-report-preparation-ring--inner", ""),
            textElement("span", "workspace-report-preparation-core", "SolomonAI")
        );

        copy.className = "workspace-report-preparation-copy";
        copy.append(
            textElement("strong", "", statusCopy),
            textElement("span", "", supportCopy)
        );
        copy.querySelector("strong").setAttribute("data-document-report-status-copy", "true");

        loader.append(orbit, copy);

        body.append(
            renderPanelHeading(
                "SolomonAI Commercial Report",
                title,
                documentName,
                "workspace-document-panel-heading--operation"
            ),
            loader,
            renderPanelNotice(
                "sync",
                noticeCopy,
                "workspace-document-panel-notice--info"
            )
        );

        actions.className = "workspace-document-inspector-actions";

        if (documentId) {
            actions.appendChild(
                createReaderOpenButton(
                    explorer,
                    doc,
                    "Open Source Document"
                )
            );
        }

        backButton.addEventListener("click", function () {
            renderDetails(explorer, doc);
        });
        actions.appendChild(backButton);

        markReportTransport(explorer, transportId, "running");
        inspector.append(renderInspectorNavigation(explorer, "Preparing Report"), body, actions);
    }

    async function createReportJob(form) {
        const response = await fetchWithTimeout(
            form.action,
            {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                },
                body: new FormData(form)
            },
            REPORT_FETCH_TIMEOUT_MS
        );

        return readJsonResponse(response);
    }

    async function fetchReportStatus(statusUrl) {
        const response = await fetchWithTimeout(
            statusUrl,
            {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                }
            },
            REPORT_FETCH_TIMEOUT_MS
        );

        return readJsonResponse(response);
    }

    async function waitForReportCompletion(explorer, transportId, statusUrl) {
        for (let attempt = 0; attempt < REPORT_STATUS_MAX_POLLS; attempt += 1) {
            if (!isActiveReportTransport(explorer, transportId)) {
                const error = new Error("Report viewing was canceled.");
                error.canceled = true;
                throw error;
            }

            const statusPayload = await fetchReportStatus(statusUrl);
            setReportStatus(explorer, transportId, statusPayload?.status_label);

            if (statusPayload?.ready) {
                return statusPayload;
            }

            await new Promise(function (resolve) {
                window.setTimeout(resolve, REPORT_STATUS_POLL_MS);
            });
        }

        throw new Error("The report is taking longer than expected. Try opening the report again from the file details panel.");
    }

    async function fetchReportFragment(fragmentUrl) {
        const response = await fetchWithTimeout(
            fragmentUrl,
            {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "Accept": "text/html",
                    "X-Requested-With": "XMLHttpRequest"
                }
            },
            REPORT_FETCH_TIMEOUT_MS
        );

        if (!response.ok) {
            throw new Error("The completed report fragment could not be loaded.");
        }

        return response.text();
    }

    function bindReportFragmentActions(explorer, doc) {
        const inspector = getInspector(explorer);
        const backButton = inspector?.querySelector("[data-document-report-back]");

        if (backButton) {
            backButton.addEventListener("click", function () {
                renderDetails(explorer, doc);
            });
        }
    }

    function renderReportFragmentHtml(explorer, doc, html) {
        const inspector = getInspector(explorer);

        if (!inspector) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const template = document.createElement("template");
        template.innerHTML = String(html || "").trim();

        inspector.setAttribute("data-document-report-transport-status", "complete");
        inspector.appendChild(template.content.cloneNode(true));
        bindReportFragmentActions(explorer, doc);
    }

    function renderReportTransportError(explorer, message, doc, fallbackUrl) {
        const inspector = getInspector(explorer);

        if (!inspector) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const documentName = getDocumentDisplayName(doc);
        const body = document.createElement("div");
        const actions = document.createElement("div");
        const backButton = actionButton(
            "workspace-document-command workspace-document-command-neutral",
            "data-document-report-back",
            "true",
            "arrow_back",
            "Back to File Details"
        );

        body.className = "workspace-document-inspector-body workspace-document-inspector-body--operation workspace-document-inspector-body--operation-error";
        body.append(
            renderPanelHeading(
                BID_SCOPE_OPERATION_LABEL,
                "Report preparation failed",
                documentName,
                "workspace-document-panel-heading--error"
            ),
            renderPanelNotice(
                "error",
                message || "The report could not be prepared.",
                "workspace-document-panel-notice--error"
            )
        );

        actions.className = "workspace-document-inspector-actions";
        backButton.addEventListener("click", function () {
            renderDetails(explorer, doc);
        });
        actions.appendChild(backButton);

        if (fallbackUrl) {
            const fallbackLink = document.createElement("a");

            fallbackLink.className = "workspace-document-command";
            fallbackLink.href = fallbackUrl;
            fallbackLink.append(
                textElement("span", "icon", "open_in_new"),
                textElement("span", "", "Open Report Surface")
            );
            actions.appendChild(fallbackLink);
        }

        inspector.append(renderInspectorNavigation(explorer, "Report Error"), body, actions);
    }

    async function openExistingContentPanelReport(explorer, doc) {
        const transportId = createReportTransportId();
        const report = getDocumentReportRecord(doc);
        const status = cleanText(report?.status || doc?.report_status);
        const fragmentUrl = getDocumentReportFragmentUrl(doc);
        const statusUrl = getDocumentReportStatusUrl(doc);
        const fallbackUrl = getDocumentReportFallbackUrl(doc);

        if (!isPendingReportStatus(status) && fragmentUrl) {
            markReportTransport(explorer, transportId, "opening");

            const fragmentHtml = await fetchReportFragment(fragmentUrl);

            if (!isActiveReportTransport(explorer, transportId)) {
                const error = new Error("Report viewing was canceled.");
                error.canceled = true;
                throw error;
            }

            commitReportRecordToDocument(doc, report, {
                fragment_url: fragmentUrl,
                report_url: fallbackUrl,
                status: status || "complete"
            });
            renderReportFragmentHtml(explorer, doc, fragmentHtml);
            return;
        }

        renderContentPanelReportPreparing(explorer, doc, transportId, {
            title: isPendingReportStatus(status)
                ? "Preparing Bid & Scope Review"
                : "Opening Bid & Scope Review",
            statusCopy: isPendingReportStatus(status)
                ? "Checking report status"
                : "Loading saved report artifact",
            supportCopy: isPendingReportStatus(status)
                ? "The existing report job is still active. SolomonAI will open it when ready."
                : "Loading the saved commercial review artifact into the file details panel.",
            noticeCopy: "Using the saved report record for this file. A new report will not be started."
        });

        if (isPendingReportStatus(status) && statusUrl) {
            const statusPayload = await waitForReportCompletion(explorer, transportId, statusUrl);
            const completedFragmentUrl = cleanText(statusPayload?.fragment_url) || fragmentUrl;

            if (!completedFragmentUrl) {
                const error = new Error("The completed report fragment endpoint was not returned.");
                error.fallbackUrl = cleanText(statusPayload?.report_url) || fallbackUrl;
                throw error;
            }

            commitReportRecordToDocument(doc, report, statusPayload);
            setReportStatus(explorer, transportId, "Report complete. Loading artifact.");

            const fragmentHtml = await fetchReportFragment(completedFragmentUrl);

            if (!isActiveReportTransport(explorer, transportId)) {
                const error = new Error("Report viewing was canceled.");
                error.canceled = true;
                throw error;
            }

            renderReportFragmentHtml(explorer, doc, fragmentHtml);
            return;
        }

        if (fragmentUrl) {
            const fragmentHtml = await fetchReportFragment(fragmentUrl);

            if (!isActiveReportTransport(explorer, transportId)) {
                const error = new Error("Report viewing was canceled.");
                error.canceled = true;
                throw error;
            }

            commitReportRecordToDocument(doc, report, {
                fragment_url: fragmentUrl,
                report_url: fallbackUrl,
                status: status || "complete"
            });
            renderReportFragmentHtml(explorer, doc, fragmentHtml);
            return;
        }

        if (statusUrl) {
            const statusPayload = await waitForReportCompletion(explorer, transportId, statusUrl);
            const completedFragmentUrl = cleanText(statusPayload?.fragment_url);

            if (!completedFragmentUrl) {
                const error = new Error("The completed report fragment endpoint was not returned.");
                error.fallbackUrl = cleanText(statusPayload?.report_url) || fallbackUrl;
                throw error;
            }

            commitReportRecordToDocument(doc, report, statusPayload);
            setReportStatus(explorer, transportId, "Report complete. Loading artifact.");

            const fragmentHtml = await fetchReportFragment(completedFragmentUrl);

            if (!isActiveReportTransport(explorer, transportId)) {
                const error = new Error("Report viewing was canceled.");
                error.canceled = true;
                throw error;
            }

            renderReportFragmentHtml(explorer, doc, fragmentHtml);
            return;
        }

        if (fallbackUrl) {
            navigateRightPaneRoute(
                fallbackUrl,
                {
                    launchMode: "report_surface",
                    source: "workspace_document_preview_report_fallback"
                }
            );
            return;
        }

        throw new Error("No saved report link is available for this file.");
    }

    async function startContentPanelReport(explorer, doc, form) {
        const transportId = createReportTransportId();

        renderContentPanelReportPreparing(explorer, doc, transportId);

        const createPayload = await createReportJob(form);

        if (!isActiveReportTransport(explorer, transportId)) {
            const error = new Error("Report viewing was canceled.");
            error.canceled = true;
            throw error;
        }

        const statusUrl = cleanText(createPayload?.status_url);
        const fragmentUrl = cleanText(createPayload?.fragment_url);
        const fallbackUrl = cleanText(createPayload?.report_url || createPayload?.preparing_url);

        if (!statusUrl) {
            const error = new Error("The report status endpoint was not returned.");
            error.fallbackUrl = fallbackUrl;
            throw error;
        }

        setReportStatus(explorer, transportId, "Report job submitted. Waiting for worker.");

        const statusPayload = await waitForReportCompletion(explorer, transportId, statusUrl);

        if (!isActiveReportTransport(explorer, transportId)) {
            const error = new Error("Report viewing was canceled.");
            error.canceled = true;
            throw error;
        }

        const completedFragmentUrl = (
            cleanText(statusPayload?.fragment_url) ||
            fragmentUrl
        );

        if (!completedFragmentUrl) {
            const error = new Error("The completed report fragment endpoint was not returned.");
            error.fallbackUrl = fallbackUrl;
            throw error;
        }

        commitReportRecordToDocument(doc, createPayload, statusPayload);
        setReportStatus(explorer, transportId, "Report complete. Loading artifact.");

        const fragmentHtml = await fetchReportFragment(completedFragmentUrl);

        if (!isActiveReportTransport(explorer, transportId)) {
            const error = new Error("Report viewing was canceled.");
            error.canceled = true;
            throw error;
        }

        renderReportFragmentHtml(explorer, doc, fragmentHtml);
    }

    function cleanReportPreamble(value, documentName) {
        let reportText = normalizeText(value);
        const escapedDocumentName = escapeRegExp(documentName);

        if (!reportText) {
            return "";
        }

        if (escapedDocumentName) {
            reportText = reportText.replace(
                new RegExp(`^SolomonAI\\s+Readout\\s*${documentName}\\s*`, "i"),
                ""
            );
            reportText = reportText.replace(
                new RegExp(`^${escapedDocumentName}\\s*`, "i"),
                ""
            );
        }

        reportText = reportText
            .replace(/^SolomonAI\s+Readout\s*/i, "")
            .replace(/^Report\s+generated\s+for\s*/i, "")
            .replace(/\n{3,}/g, "\n\n")
            .trim();

        return reportText;
    }

    function getOperationSummary(response, options) {
        const documentName = getOperationDocumentName(response, options);
        const paths = [
            "result.summary",
            "result.body",
            "result.output",
            "report.body",
            "report.text",
            "report.summary",
            "user_output",
            "payload.user_output",
            "payload.answer",
            "payload.output",
            "payload.summary",
            "payload.report",
            "workflow_response.user_output",
            "workflow_response.payload.answer",
            "workflow_response.payload.output",
            "workflow_response.payload.summary",
            "workflow_response.payload.report"
        ];

        for (const path of paths) {
            const value = cleanReportPreamble(readNestedValue(response, path), documentName);

            if (value) {
                return value;
            }
        }

        return "The document operation completed, but no display text was returned.";
    }

    function normalizePreviewLookupValue(value) {
        return cleanText(value).toLowerCase();
    }

    function isPreviewFolderDocument(doc) {
        const itemType = normalizePreviewLookupValue(
            doc?.workspace_item_type ||
            doc?.item_type ||
            doc?.resource_type ||
            doc?.document_kind ||
            doc?.object_type ||
            doc?.kind ||
            doc?.document_type ||
            doc?.type
        );

        return Boolean(
            itemType === "folder" ||
            doc?.folder === true ||
            doc?.is_folder === true
        );
    }

    function getPreviewDocumentId(doc) {
        if (isPreviewFolderDocument(doc)) {
            return "";
        }

        return cleanText(doc?.document_id || doc?.random_name || doc?.file_id);
    }

    function getPreviewFolderId(doc) {
        if (!isPreviewFolderDocument(doc)) {
            return "";
        }

        return cleanText(
            doc?.folder_id ||
            doc?.workspace_item_id ||
            doc?.object_id ||
            doc?.random_name ||
            doc?.document_id
        );
    }

    function normalizeDetailDate(value) {
        const cleanValue = cleanText(value);

        if (!cleanValue) {
            return "";
        }

        const parsedDate = new Date(cleanValue);

        if (Number.isNaN(parsedDate.getTime())) {
            return cleanValue;
        }

        return parsedDate.toLocaleString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit"
        });
    }

    function getDocumentModifiedLabel(doc) {
        return getDetailsMetadata(null, doc).updatedLabel;
    }

    function getDocumentLocationLabel(explorer, doc) {
        return getDetailsMetadata(explorer, doc).locationLabel;
    }

    function isPreviewTrashDocument(doc) {
        const status = cleanText(doc?.document_status || doc?.status).toLowerCase();

        return Boolean(
            doc?.trashed === true ||
            cleanText(doc?.trashed_at) ||
            ["trash", "trashed", "deleted"].includes(status)
        );
    }

    function isPlainObject(value) {
        return Boolean(
            value &&
            typeof value === "object" &&
            !Array.isArray(value)
        );
    }

    function isUnavailableDetailValue(value) {
        const cleanValue = cleanText(value).toLowerCase();

        return Boolean(
            !cleanValue ||
            cleanValue === "-" ||
            cleanValue === "—" ||
            cleanValue === "n/a" ||
            cleanValue === "na" ||
            cleanValue === "null" ||
            cleanValue === "undefined" ||
            cleanValue === "not available" ||
            cleanValue === "unavailable" ||
            cleanValue === "size unavailable" ||
            cleanValue === "date unavailable" ||
            cleanValue === "location unavailable"
        );
    }

    function firstAvailableDetailText() {
        for (const value of arguments) {
            const cleanValue = cleanText(value);

            if (!isUnavailableDetailValue(cleanValue)) {
                return cleanValue;
            }
        }

        return "";
    }

    function getDocumentMetadataRecord(doc) {
        if (!isPlainObject(doc)) {
            return {};
        }

        if (isPlainObject(doc.metadata)) {
            return doc.metadata;
        }

        if (isPlainObject(doc.document_metadata)) {
            return doc.document_metadata;
        }

        if (isPlainObject(doc.workspace_metadata)) {
            return doc.workspace_metadata;
        }

        return {};
    }

    function getRecordsMetadata(doc) {
        if (
            typeof Records.getDocumentMetadata !== "function" ||
            !isPlainObject(doc)
        ) {
            return {};
        }

        const metadata = Records.getDocumentMetadata(doc);

        return isPlainObject(metadata) ? metadata : {};
    }

    function readElementAttribute(element, names) {
        if (!element) {
            return "";
        }

        for (const name of names) {
            const value = cleanText(
                element.getAttribute(name)
            );

            if (value) {
                return value;
            }
        }

        return "";
    }

    function readElementText(element, selectors) {
        if (!element) {
            return "";
        }

        for (const selector of selectors) {
            const value = cleanText(
                element.querySelector(selector)?.textContent
            );

            if (value) {
                return value;
            }
        }

        return "";
    }

    function getNumericByteValue(value) {
        const cleanValue = cleanText(value).replace(/,/g, "");

        if (!/^\d+(?:\.\d+)?$/.test(cleanValue)) {
            return "";
        }

        const numericValue = Number(cleanValue);

        return Number.isFinite(numericValue) && numericValue >= 0
            ? String(Math.round(numericValue))
            : "";
    }

    function getPreviewDocumentIdentityValues(doc) {
        const values = [
            getPreviewDocumentId(doc),
            getPreviewFolderId(doc),
            doc?.document_id,
            doc?.random_name,
            doc?.file_id,
            doc?.folder_id,
            doc?.workspace_item_id,
            doc?.object_id
        ]
            .map(cleanText)
            .filter(Boolean);

        return Array.from(new Set(values));
    }

    function getPreviewMetadataElement(explorer, doc) {
        const identityValues =
            getPreviewDocumentIdentityValues(doc);

        if (!identityValues.length || !explorer) {
            return null;
        }

        const roots = [
            explorer.querySelector("[data-document-list]"),
            explorer.querySelector("[data-search-results-list]"),
            explorer.querySelector("[data-workspace-document-list]"),
            explorer.querySelector("[data-workspace-object-list]")
        ].filter(Boolean);

        roots.push(explorer);

        for (const root of Array.from(new Set(roots))) {
            const candidates = Array.from(
                root.querySelectorAll(
                    [
                        "[data-document-id]",
                        "[data-workspace-object-id]",
                        "[data-folder-id]",
                        "[data-workspace-folder-id]",
                        "[data-workspace-item-id]"
                    ].join(",")
                )
            );

            for (const candidate of candidates) {
                if (candidate.closest(INSPECTOR_SELECTOR)) {
                    continue;
                }

                const candidateId = cleanText(
                    candidate.getAttribute("data-document-id") ||
                    candidate.getAttribute("data-workspace-object-id") ||
                    candidate.getAttribute("data-folder-id") ||
                    candidate.getAttribute("data-workspace-folder-id") ||
                    candidate.getAttribute("data-workspace-item-id")
                );

                if (!identityValues.includes(candidateId)) {
                    continue;
                }

                return (
                    candidate.closest(
                        [
                            "[data-document-row]",
                            "[data-workspace-document-row]",
                            "[data-workspace-object-row]",
                            "[data-search-result]",
                            "[data-workspace-object]",
                            "[role='option']",
                            "[role='listitem']",
                            "article"
                        ].join(",")
                    ) ||
                    candidate
                );
            }
        }

        return null;
    }

    function readPreviewElementMetadata(element) {
        if (!element) {
            return {};
        }

        const sizeBytes = (
            getNumericByteValue(
                readElementAttribute(
                    element,
                    [
                        "data-document-size-bytes",
                        "data-size-bytes",
                        "data-file-size-bytes",
                        "data-content-length"
                    ]
                )
            ) ||
            getNumericByteValue(
                readElementAttribute(
                    element,
                    [
                        "data-document-size",
                        "data-file-size"
                    ]
                )
            )
        );
        const sizeDisplayValue = readElementAttribute(
            element,
            [
                "data-document-size-label",
                "data-size-label",
                "data-file-size-label",
                "data-document-size-display",
                "data-file-size-display"
            ]
        );
        const sizeFallbackValue = readElementAttribute(
            element,
            [
                "data-document-size",
                "data-file-size"
            ]
        );
        const uploadedAt = readElementAttribute(
            element,
            [
                "data-document-uploaded-at",
                "data-uploaded-at",
                "data-file-uploaded-at",
                "data-created-at"
            ]
        );
        const uploadedLabel = readElementAttribute(
            element,
            [
                "data-document-uploaded-label",
                "data-uploaded-label",
                "data-file-uploaded-label",
                "data-created-label"
            ]
        );
        const typeLabel = readElementAttribute(
            element,
            [
                "data-document-type-label",
                "data-file-type-label",
                "data-workspace-object-type-label"
            ]
        );
        const locationLabel = readElementAttribute(
            element,
            [
                "data-document-location-label",
                "data-workspace-location-label",
                "data-location-label",
                "data-parent-location-label"
            ]
        );
        const storageStatus = readElementAttribute(
            element,
            [
                "data-document-storage-status",
                "data-workspace-object-status",
                "data-document-status",
                "data-status"
            ]
        );
        const storageStatusLabel = readElementAttribute(
            element,
            [
                "data-document-status-label",
                "data-document-storage-status-label",
                "data-workspace-object-status-label",
                "data-status-label"
            ]
        );

        return {
            contract: readElementAttribute(
                element,
                [
                    "data-document-metadata-contract",
                    "data-workspace-metadata-contract"
                ]
            ) || DOCUMENT_METADATA_CONTRACT,
            type_label:
                firstAvailableDetailText(typeLabel),
            size_bytes: sizeBytes,
            size_label:
                firstAvailableDetailText(
                    sizeDisplayValue,
                    getNumericByteValue(sizeFallbackValue)
                        ? ""
                        : sizeFallbackValue,
                    readElementText(
                        element,
                        [
                            "[data-document-size-text]",
                            "[data-document-list-cell='size']",
                            "[data-workspace-column='size']",
                            ".workspace-document-size",
                            ".workspace-document-file-size"
                        ]
                    )
                ),
            uploaded_at:
                firstAvailableDetailText(uploadedAt),
            uploaded_label:
                firstAvailableDetailText(
                    uploadedLabel,
                    readElementText(
                        element,
                        [
                            "[data-document-uploaded-text]",
                            "[data-document-list-cell='uploaded']",
                            "[data-workspace-column='uploaded']",
                            ".workspace-document-uploaded",
                            ".workspace-document-file-uploaded"
                        ]
                    )
                ),
            location_label:
                firstAvailableDetailText(locationLabel),
            storage_status:
                firstAvailableDetailText(storageStatus),
            storage_status_label:
                firstAvailableDetailText(storageStatusLabel)
        };
    }

    function applyPreviewMetadata(doc, metadata) {
        if (!isPlainObject(doc) || !isPlainObject(metadata)) {
            return doc;
        }

        if (metadata.type_label) {
            doc.type_label = metadata.type_label;
        }

        if (metadata.size_bytes) {
            doc.size_bytes = metadata.size_bytes;
        }

        if (metadata.size_label) {
            doc.size_label = metadata.size_label;
            doc.file_size_label = metadata.size_label;
        }

        if (metadata.uploaded_at) {
            doc.uploaded_at = metadata.uploaded_at;
        }

        if (metadata.uploaded_label) {
            doc.uploaded_label = metadata.uploaded_label;
        }

        if (metadata.location_label) {
            doc.location_label = metadata.location_label;
        }

        if (metadata.storage_status) {
            doc.storage_status = metadata.storage_status;
        }

        if (metadata.storage_status_label) {
            doc.storage_status_label = metadata.storage_status_label;
            doc.status_label = metadata.storage_status_label;
        }

        doc.metadata = Object.assign(
            {},
            getDocumentMetadataRecord(doc),
            metadata,
            {
                contract:
                    metadata.contract ||
                    getDocumentMetadataRecord(doc).contract ||
                    DOCUMENT_METADATA_CONTRACT
            }
        );

        return doc;
    }

    function getDetailsDocument(explorer, rawDoc) {
        const normalizedDoc = getPreviewDocument(rawDoc);
        const rawPayload = isPlainObject(rawDoc) ? rawDoc : {};
        const doc = normalizedDoc
            ? Object.assign({}, rawPayload, normalizedDoc)
            : null;

        if (!doc) {
            return null;
        }

        const metadataElement = getPreviewMetadataElement(
            explorer,
            doc
        );
        const elementMetadata = readPreviewElementMetadata(
            metadataElement
        );

        applyPreviewMetadata(doc, elementMetadata);

        if (typeof Records.normalizeDocument === "function") {
            const normalizedWithMetadata =
                Records.normalizeDocument(doc);

            if (normalizedWithMetadata) {
                Object.assign(doc, normalizedWithMetadata);
                doc.metadata = Object.assign(
                    {},
                    getDocumentMetadataRecord(rawPayload),
                    getDocumentMetadataRecord(normalizedWithMetadata),
                    getDocumentMetadataRecord(doc),
                    elementMetadata
                );
                applyPreviewMetadata(doc, elementMetadata);
            }
        }

        return doc;
    }

    function getFallbackLocationLabel(explorer, doc) {
        const section = cleanText(explorer?.getAttribute("data-workspace-section")).toLowerCase();

        if (isPreviewTrashDocument(doc) || section === "trash") {
            return "Trash";
        }

        if (section === "reports") {
            return "Reports";
        }

        if (section === "recent") {
            return "Recent";
        }

        return "My Files";
    }

    function getFallbackStorageStatusLabel(doc) {
        const status = cleanText(
            doc?.storage_status ||
            doc?.document_status ||
            doc?.status
        ).toLowerCase();

        if (
            isPreviewTrashDocument(doc) ||
            ["trash", "trashed", "deleted"].includes(status)
        ) {
            return "In Trash";
        }

        if (status === "stored" || status === "active" || status === "ready") {
            return "Stored";
        }

        if (typeof Records.getDocumentStorageLabel === "function") {
            return Records.getDocumentStorageLabel(doc);
        }

        return "Stored";
    }

    function getDetailsMetadata(explorer, doc) {
        const sourceMetadata = getDocumentMetadataRecord(doc);
        const recordsMetadata = getRecordsMetadata(doc);
        const isFolder = isPreviewFolderDocument(doc);
        const formattedSize = isFolder
            ? ""
            : Records.formatFileSize(doc?.size_bytes);
        const uploadedDateLabel = normalizeDetailDate(
            doc?.uploaded_at ||
            doc?.upload_time ||
            doc?.created_at
        );
        const createdDateLabel = normalizeDetailDate(
            doc?.created_at ||
            doc?.uploaded_at
        );
        const updatedDateLabel = normalizeDetailDate(
            doc?.modified_at ||
            doc?.updated_at ||
            doc?.last_modified_at ||
            doc?.stored_at
        );

        return {
            contract:
                firstAvailableDetailText(
                    recordsMetadata.contract,
                    sourceMetadata.contract,
                    doc?.metadata_contract
                ) || DOCUMENT_METADATA_CONTRACT,
            typeLabel:
                firstAvailableDetailText(
                    recordsMetadata.type_label,
                    sourceMetadata.type_label,
                    doc?.type_label,
                    doc?.file_type_label,
                    isFolder ? "Folder" : "Workspace File"
                ) || (isFolder ? "Folder" : "Workspace File"),
            sizeLabel: isFolder
                ? "Not applicable"
                : (
                    firstAvailableDetailText(
                        recordsMetadata.size_label,
                        sourceMetadata.size_label,
                        doc?.size_label,
                        doc?.file_size_label,
                        doc?.size_display,
                        formattedSize
                    ) || DETAIL_UNAVAILABLE.size
                ),
            uploadedLabel: isFolder
                ? (
                    firstAvailableDetailText(
                        recordsMetadata.created_label,
                        sourceMetadata.created_label,
                        doc?.created_label,
                        createdDateLabel
                    ) || DETAIL_UNAVAILABLE.date
                )
                : (
                    firstAvailableDetailText(
                        recordsMetadata.uploaded_label,
                        sourceMetadata.uploaded_label,
                        doc?.uploaded_label,
                        doc?.upload_label,
                        uploadedDateLabel
                    ) || DETAIL_UNAVAILABLE.date
                ),
            createdLabel:
                firstAvailableDetailText(
                    recordsMetadata.created_label,
                    sourceMetadata.created_label,
                    doc?.created_label,
                    createdDateLabel
                ) || DETAIL_UNAVAILABLE.date,
            updatedLabel:
                firstAvailableDetailText(
                    recordsMetadata.updated_label,
                    sourceMetadata.updated_label,
                    doc?.updated_label,
                    updatedDateLabel
                ) || DETAIL_UNAVAILABLE.date,
            locationLabel:
                firstAvailableDetailText(
                    recordsMetadata.location_label,
                    sourceMetadata.location_label,
                    doc?.location_label,
                    doc?.workspace_location_label,
                    getFallbackLocationLabel(explorer, doc)
                ) || DETAIL_UNAVAILABLE.location,
            statusLabel:
                firstAvailableDetailText(
                    recordsMetadata.storage_status_label,
                    recordsMetadata.status_label,
                    sourceMetadata.storage_status_label,
                    sourceMetadata.status_label,
                    doc?.storage_status_label,
                    doc?.status_label,
                    getFallbackStorageStatusLabel(doc)
                ) || "Stored"
        };
    }

    function getDocumentStatusLabel(doc) {
        return getDetailsMetadata(null, doc).statusLabel;
    }

    function renderFilePropertyList(explorer, doc) {
        const properties = document.createElement("div");
        const metadata = getDetailsMetadata(explorer, doc);
        const rows = [
            ["Type", metadata.typeLabel],
            ["Size", metadata.sizeLabel],
            ["Uploaded", metadata.uploadedLabel],
            ["Location", metadata.locationLabel],
            ["Status", metadata.statusLabel]
        ];

        properties.className = "workspace-document-file-property-list";
        properties.setAttribute(
            "data-document-metadata-contract",
            metadata.contract
        );

        rows.forEach(function (row) {
            const item = document.createElement("div");

            item.className = "workspace-document-file-property";
            item.append(
                textElement("span", "", row[0]),
                textElement("strong", "", row[1])
            );

            properties.appendChild(item);
        });

        return properties;
    }

    function renderFileDetailsNotice(doc) {
        const notice = document.createElement("aside");
        const isTrash = isPreviewTrashDocument(doc);
        const copy = isTrash
            ? "This file is in Trash. You can still open it in Reader, restore it, or delete it forever from Trash."
            : "File actions are explicit. Opening the Reader or running Bid & Scope Review will only start when you choose that action.";

        notice.className = "workspace-document-file-note";
        notice.append(
            textElement("span", "icon", isTrash ? "delete_outline" : "info"),
            textElement("p", "", copy)
        );

        return notice;
    }

    function getFolderStatusLabel(doc) {
        if (isPreviewTrashDocument(doc)) {
            return "In Trash";
        }

        return "Workspace container";
    }

    function getFolderVisibilityLabel(doc) {
        const visibilityScope = cleanText(
            doc?.visibility_scope ||
            doc?.access_scope ||
            doc?.folder_scope
        );

        if (!visibilityScope) {
            return "My Files";
        }

        if (visibilityScope === "owner") {
            return "My Files";
        }

        return titleCase(visibilityScope);
    }

    function getFolderParentLabel(doc) {
        const parentFolderId = cleanText(
            doc?.parent_folder_id ||
            doc?.parent_folder_key
        );

        if (!parentFolderId || parentFolderId === "root") {
            return "My Files";
        }

        return "Nested folder";
    }

    function renderFolderPropertyList(explorer, doc) {
        const properties = document.createElement("div");
        const metadata = getDetailsMetadata(explorer, doc);
        const rows = [
            ["Type", metadata.typeLabel],
            ["Created", metadata.createdLabel],
            ["Location", metadata.locationLabel],
            ["Parent", getFolderParentLabel(doc)],
            ["Visibility", getFolderVisibilityLabel(doc)],
            ["Status", metadata.statusLabel]
        ];

        properties.className = "workspace-document-file-property-list";
        properties.setAttribute(
            "data-document-metadata-contract",
            metadata.contract
        );

        rows.forEach(function (row) {
            const item = document.createElement("div");

            item.className = "workspace-document-file-property";
            item.append(
                textElement("span", "", row[0]),
                textElement("strong", "", row[1])
            );

            properties.appendChild(item);
        });

        return properties;
    }

    function renderFolderDetailsNotice() {
        const notice = document.createElement("aside");

        notice.className = "workspace-document-file-note";
        notice.append(
            textElement("span", "icon", "folder"),
            textElement("p", "", "Folders organize workspace navigation only. File access, Reader launch, Bid & Scope Review, and SolomonAI sources remain controlled at the file level.")
        );

        return notice;
    }

    function renderFolderDetails(explorer, rawDoc) {
        const inspector = getInspector(explorer);
        const doc = getDetailsDocument(explorer, rawDoc);

        if (!inspector || !doc) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const metadata = getDetailsMetadata(explorer, doc);
        const folderName = getDocumentDisplayName(doc);
        const folderId = getPreviewFolderId(doc);
        const updatedLabel = metadata.updatedLabel;
        const body = document.createElement("div");
        const propertiesPage = document.createElement("section");
        const identity = document.createElement("div");
        const summaryIcon = textElement("span", "icon workspace-document-summary-file-icon", "folder");
        const identityCopy = document.createElement("div");
        const actions = document.createElement("div");
        const closeButton = sectionViewButton(
            explorer,
            "workspace-document-command workspace-document-command-neutral workspace-document-view-button",
            "close",
            "Close"
        );

        body.className = "workspace-document-inspector-body workspace-document-inspector-body--properties";
        propertiesPage.className = "workspace-document-file-properties workspace-document-file-properties--drive workspace-document-folder-properties";
        identity.className = "workspace-document-file-identity";
        identityCopy.className = "workspace-document-summary-copy";
        summaryIcon.setAttribute("aria-hidden", "true");

        identityCopy.append(
            textElement("p", "workspace-kicker", "Folder"),
            textElement("strong", "", folderName),
            textElement("span", "", folderId ? `Folder ID ${folderId} · Updated ${updatedLabel}` : `Updated ${updatedLabel}`)
        );

        identity.append(summaryIcon, identityCopy);
        propertiesPage.append(
            identity,
            renderFolderPropertyList(explorer, doc),
            renderFolderDetailsNotice()
        );
        body.append(propertiesPage);

        actions.className = "workspace-document-inspector-actions workspace-document-inspector-actions--details";
        actions.append(closeButton);

        inspector.append(renderInspectorNavigation(explorer, "Folder Details"), body, actions);
    }

    function renderOperationActions(response, options, explorer) {
        const actions = document.createElement("div");
        const documentId = getOperationDocumentId(response, options);
        const responseActions = Array.isArray(response?.actions) ? response.actions : [];

        actions.className = "workspace-document-inspector-actions";

        responseActions.forEach(function (item) {
            const actionName = cleanText(item?.action);
            const label = cleanText(item?.label);

            if (actionName === "open_reader" && documentId) {
                actions.appendChild(
                    createReaderOpenButton(
                        explorer,
                        response?.document || options?.document || null,
                        label || "Open Reader",
                        {
                            documentId,
                            documentName: getOperationDocumentName(response, options),
                            readerUrl: cleanText(
                                item?.reader_url ||
                                item?.readerUrl ||
                                item?.workspace_reader_url ||
                                item?.workspaceReaderUrl ||
                                response?.reader_url ||
                                response?.workspace_reader_url ||
                                options?.readerUrl
                            )
                        }
                    )
                );
            }
        });

        if (!actions.children.length && documentId) {
            actions.appendChild(
                createReaderOpenButton(
                    explorer,
                    response?.document || options?.document || null,
                    "Open Reader",
                    {
                        documentId,
                        documentName: getOperationDocumentName(response, options),
                        readerUrl: cleanText(
                            response?.reader_url ||
                            response?.workspace_reader_url ||
                            options?.readerUrl
                        )
                    }
                )
            );
        }

        actions.appendChild(
            sectionViewButton(
                explorer,
                "workspace-document-command workspace-document-command-neutral workspace-document-view-button",
                "folder_open",
                `Back to ${getWorkspaceSectionLabel(explorer)}`
            )
        );

        return actions;
    }

    function renderPanelHeading(kicker, title, subtitle, modifier) {
        const heading = document.createElement("header");

        heading.className = [
            "workspace-document-panel-heading",
            modifier || ""
        ].filter(Boolean).join(" ");

        heading.append(
            textElement("p", "workspace-document-panel-eyebrow", kicker),
            textElement("h2", "workspace-document-panel-title", title),
            textElement("p", "workspace-document-panel-subtitle", subtitle)
        );

        return heading;
    }

    function renderPanelNotice(iconName, copy, modifier) {
        const notice = document.createElement("aside");

        notice.className = [
            "workspace-document-panel-notice",
            modifier || ""
        ].filter(Boolean).join(" ");

        notice.append(
            textElement("span", "icon", iconName),
            textElement("p", "", copy)
        );

        return notice;
    }

    function renderEmpty(explorer) {
        const inspector = getInspector(explorer);

        if (!inspector) {
            return;
        }

        prepareInspector(inspector);
        explorer.removeAttribute("data-document-selected");

        const header = document.createElement("div");
        header.className = "workspace-document-inspector-header";
        header.append(
            textElement("p", "workspace-kicker", "My Files"),
            textElement("strong", "", "No document selected")
        );

        const body = document.createElement("div");
        body.className = "workspace-document-inspector-body workspace-document-inspector-body--summary-empty";
        body.append(
            textElement("span", "icon", "ads_click"),
            textElement("p", "", "Select a document to view its file properties, open it in the Solomon Reader, or run a document operation.")
        );

        inspector.append(header, body);
    }

    function renderError(explorer, message) {
        const inspector = getInspector(explorer);

        if (!inspector) {
            return;
        }

        prepareInspector(inspector);
        explorer.removeAttribute("data-document-selected");

        const header = document.createElement("div");
        header.className = "workspace-document-inspector-header";
        header.append(
            textElement("p", "workspace-kicker", "My Files"),
            textElement("strong", "", "Document action failed")
        );

        const body = document.createElement("div");
        body.className = "workspace-document-inspector-body workspace-document-inspector-body--summary-empty";
        body.append(
            textElement("span", "icon", "warning"),
            textElement("p", "", message || "The document action could not be completed.")
        );

        inspector.append(renderInspectorNavigation(explorer, "Error"), header, body);
    }

    function createShareInspectorAction(doc, mode) {
        const documentId = getPreviewDocumentId(doc);
        const documentName = getDocumentDisplayName(doc);
        const isManage = mode === "manage";
        const button = actionButton(
            "workspace-document-command workspace-document-command-neutral",
            isManage ? "data-document-manage-access-trigger" : "data-document-share-trigger",
            documentId,
            isManage ? "manage_accounts" : "person_add",
            isManage ? "Manage Access" : "Share"
        );

        button.setAttribute("data-document-id", documentId);
        button.setAttribute("data-document-name", documentName);
        return button;
    }

    function renderDetails(explorer, rawDoc) {
        const inspector = getInspector(explorer);
        const doc = getDetailsDocument(explorer, rawDoc);

        if (!inspector || !doc) {
            return;
        }

        if (isPreviewFolderDocument(rawDoc) || isPreviewFolderDocument(doc)) {
            renderFolderDetails(explorer, rawDoc);
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const metadata = getDetailsMetadata(explorer, doc);
        const documentName = getDocumentDisplayName(doc);
        const typeLabel = metadata.typeLabel;
        const fileSize = metadata.sizeLabel;
        const uploadedLabel = metadata.uploadedLabel;
        const documentId = getPreviewDocumentId(doc);
        const isTrash = isPreviewTrashDocument(doc);

        const body = document.createElement("div");
        const propertiesPage = document.createElement("section");
        const identity = document.createElement("div");
        const summaryIcon = textElement("span", "icon workspace-document-summary-file-icon", Records.getDocumentIconName(doc));
        const identityCopy = document.createElement("div");

        body.className = "workspace-document-inspector-body workspace-document-inspector-body--properties";
        propertiesPage.className = "workspace-document-file-properties workspace-document-file-properties--drive";
        identity.className = "workspace-document-file-identity";
        identityCopy.className = "workspace-document-summary-copy";
        summaryIcon.setAttribute("aria-hidden", "true");

        identityCopy.append(
            textElement("p", "workspace-kicker", typeLabel),
            textElement("strong", "", documentName),
            textElement("span", "", `${fileSize} · Uploaded ${uploadedLabel}`)
        );

        identity.append(summaryIcon, identityCopy);
        propertiesPage.append(
            identity,
            renderFilePropertyList(explorer, doc),
            renderFileDetailsNotice(doc)
        );
        body.append(propertiesPage);

        const actions = document.createElement("div");
        const closeButton = sectionViewButton(
            explorer,
            "workspace-document-command workspace-document-command-neutral workspace-document-view-button",
            "close",
            "Close"
        );

        actions.className = "workspace-document-inspector-actions workspace-document-inspector-actions--details";

        if (isTrash) {
            actions.append(
                createReaderOpenButton(
                    explorer,
                    doc,
                    "Open Reader"
                ),
                actionButton(
                    "workspace-document-command",
                    "data-document-restore",
                    documentId,
                    "restore_from_trash",
                    "Restore"
                ),
                actionButton(
                    "workspace-document-command workspace-document-command-neutral",
                    "data-document-permanent-delete",
                    documentId,
                    "delete_forever",
                    "Delete forever"
                ),
                closeButton
            );
        } else {
            const openButton = createReaderOpenButton(
                explorer,
                doc,
                "Open Reader"
            );

            const deleteButton = actionButton(
                "workspace-document-command workspace-document-command-neutral",
                "data-document-delete",
                documentId,
                "delete_outline",
                "Move to Trash"
            );

            const canShare = (
                doc?.capabilities?.can_share === true ||
                doc?.can_share === true ||
                rawDoc?.capabilities?.can_share === true ||
                rawDoc?.can_share === true
            );
            const shareActions = canShare
                ? [
                    createShareInspectorAction(doc, "share"),
                    createShareInspectorAction(doc, "manage")
                ]
                : [];

            actions.append(
                openButton,
                reportPrimaryAction(doc, explorer),
                ...shareActions,
                deleteButton,
                closeButton
            );
        }

        inspector.append(renderInspectorNavigation(explorer, "File Details"), body, actions);
    }

    function createSummaryBackButton(explorer, doc) {
        const button = actionButton(
            "workspace-document-command workspace-document-command-neutral",
            "data-document-summary-back",
            getPreviewDocumentId(doc),
            "arrow_back",
            "Back to Details"
        );

        button.addEventListener("click", function () {
            renderDetails(explorer, doc);
        });

        return button;
    }

    function createSummaryCloseButton(explorer, inspector) {
        const button = sectionViewButton(
            explorer,
            "workspace-document-command workspace-document-command-neutral workspace-document-view-button",
            "close",
            "Close"
        );

        button.addEventListener("click", function () {
            inspector?.removeAttribute("data-document-summary-request-id");
        });

        return button;
    }

    function appendSummaryCopy(container, summaryText) {
        cleanText(summaryText)
            .split(/\n+/)
            .map(cleanText)
            .filter(Boolean)
            .forEach(function (line) {
                container.appendChild(textElement("p", "", line));
            });
    }

    function renderSummaryLoading(explorer, rawDoc, options) {
        const inspector = getInspector(explorer);
        const doc = getDetailsDocument(explorer, rawDoc);

        if (!inspector || !doc) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const requestId = cleanText(options?.requestId);

        if (requestId) {
            inspector.setAttribute("data-document-summary-request-id", requestId);
        }

        const body = document.createElement("div");
        const actions = document.createElement("div");

        body.className = "workspace-document-inspector-body workspace-document-inspector-body--operation workspace-document-inspector-body--operation-loading";
        body.append(
            renderPanelHeading(
                "Auto Summary",
                getDocumentDisplayName(doc),
                "Retrieving the persisted summary for the current file version."
            ),
            renderPanelNotice(
                "sync",
                "Checking Solomon's stored intelligence artifact. This action does not start a new intelligence job or LLM request."
            )
        );

        actions.className = "workspace-document-inspector-actions workspace-document-inspector-actions--details";
        actions.append(
            createSummaryBackButton(explorer, doc),
            createSummaryCloseButton(explorer, inspector)
        );

        inspector.append(renderInspectorNavigation(explorer, "Summary"), body, actions);
    }

    function renderSummary(explorer, rawDoc, payload) {
        const inspector = getInspector(explorer);
        const doc = getDetailsDocument(explorer, rawDoc);

        if (!inspector || !doc) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const state = cleanText(payload?.summary_state).toLowerCase() || "missing";
        const documentName = getDocumentDisplayName(doc);
        const body = document.createElement("div");
        const actions = document.createElement("div");

        body.className = "workspace-document-inspector-body workspace-document-inspector-body--operation";
        body.append(
            renderPanelHeading(
                "Auto Summary",
                documentName,
                state === "ready"
                    ? "Stored for the current file version."
                    : "Persisted intelligence status for the current file version."
            )
        );

        if (state === "ready") {
            const summaryBlock = document.createElement("div");

            body.appendChild(
                renderPanelNotice(
                    "check_circle",
                    "This is the stored summary for the file's current content version. Viewing it did not invoke the LLM."
                )
            );
            summaryBlock.className = "workspace-document-operation-result-copy";
            appendSummaryCopy(summaryBlock, payload?.detailed_summary);
            body.appendChild(summaryBlock);
        } else if (state === "pending") {
            body.appendChild(
                renderPanelNotice(
                    "hourglass_top",
                    "Solomon is still processing this file's summary. The durable job will continue independently; opening this panel does not create another job."
                )
            );
        } else if (state === "stale") {
            body.appendChild(
                renderPanelNotice(
                    "history",
                    "A summary exists for older source content, so it is intentionally not displayed. Solomon will only show a summary bound to the file's current checksum and version."
                )
            );
        } else if (state === "failed") {
            body.appendChild(
                renderPanelNotice(
                    "warning",
                    "Summary processing did not complete successfully. The source file remains available, and no new intelligence job was started by this view."
                )
            );
        } else {
            body.appendChild(
                renderPanelNotice(
                    "info",
                    "No current persisted Auto Summary is available for this file. Viewing this panel does not start summary generation."
                )
            );
        }

        actions.className = "workspace-document-inspector-actions workspace-document-inspector-actions--details";
        actions.append(
            createSummaryBackButton(explorer, doc),
            createSummaryCloseButton(explorer, inspector)
        );

        inspector.append(renderInspectorNavigation(explorer, "Summary"), body, actions);
    }

    function renderSummaryError(explorer, rawDoc, message) {
        const inspector = getInspector(explorer);
        const doc = getDetailsDocument(explorer, rawDoc);

        if (!inspector || !doc) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const body = document.createElement("div");
        const actions = document.createElement("div");

        body.className = "workspace-document-inspector-body workspace-document-inspector-body--operation workspace-document-inspector-body--operation-error";
        body.append(
            renderPanelHeading(
                "Auto Summary",
                getDocumentDisplayName(doc),
                "The persisted summary could not be retrieved."
            ),
            renderPanelNotice(
                "warning",
                cleanText(message) || "The summary request could not be completed."
            )
        );

        actions.className = "workspace-document-inspector-actions workspace-document-inspector-actions--details";
        actions.append(
            createSummaryBackButton(explorer, doc),
            createSummaryCloseButton(explorer, inspector)
        );

        inspector.append(renderInspectorNavigation(explorer, "Summary Error"), body, actions);
    }

    function renderHandoffStep(title, copy) {
        const item = document.createElement("div");

        item.className = "workspace-document-file-property";
        item.append(
            textElement("span", "", title),
            textElement("strong", "", copy)
        );

        return item;
    }

    function renderOperationHandoff(explorer, options) {
        const inspector = getInspector(explorer);
        const documentId = cleanText(options?.documentId);
        const documentName = cleanText(options?.documentName) || "Selected file";
        const operationLabel = cleanText(options?.operationLabel) || BID_SCOPE_OPERATION_LABEL;
        const operationActionLabel = cleanText(options?.operationActionLabel) || `Run ${operationLabel}`;

        if (!inspector || !documentId) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const body = document.createElement("div");
        const steps = document.createElement("section");
        const actions = document.createElement("div");
        const startButton = actionButton(
            "workspace-document-command workspace-document-command-primary",
            "data-document-operation-confirm",
            documentId,
            "play_arrow",
            operationActionLabel
        );
        const cancelButton = actionButton(
            "workspace-document-command workspace-document-command-neutral",
            "data-document-operation-cancel",
            documentId,
            "arrow_back",
            "Back to File Details"
        );

        body.className = "workspace-document-inspector-body workspace-document-inspector-body--operation";
        steps.className = "workspace-document-file-property-list";
        actions.className = "workspace-document-inspector-actions";

        startButton.setAttribute("aria-label", `${operationActionLabel} for ${documentName}`);
        cancelButton.setAttribute("aria-label", `Return to file details for ${documentName}`);

        steps.append(
            renderHandoffStep(
                "Explicit action",
                "The workflow starts only after you press the start button below."
            ),
            renderHandoffStep(
                "Governed SolomonAI review",
                "SolomonAI will read the stored file and generate a Bid & Scope Review."
            ),
            renderHandoffStep(
                "Passive states stay passive",
                "Upload, selection, Details, Reader, and route changes do not start analysis."
            )
        );

        body.append(
            renderPanelHeading(
                "SolomonAI Governed Workflow",
                `Ready to run ${operationLabel}`,
                documentName,
                "workspace-document-panel-heading--operation"
            ),
            renderPanelNotice(
                "verified",
                "Nothing has been analyzed yet. No progress will be simulated; the content panel will update only when the server returns a real state or result.",
                "workspace-document-panel-notice--info"
            ),
            steps
        );

        actions.append(startButton, cancelButton);
        inspector.append(renderInspectorNavigation(explorer, "Workflow Confirmation"), body, actions);
    }

    function renderOperationProcessing(explorer, options) {
        const inspector = getInspector(explorer);
        const documentName = cleanText(options?.documentName) || "Selected file";
        const operationLabel = cleanText(options?.operationLabel) || BID_SCOPE_OPERATION_LABEL;
        const statusLabel = cleanText(options?.statusLabel) || "Preparing request";
        const detail = cleanText(options?.detail) || "Waiting for the server to accept the governed document operation.";

        if (!inspector) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const body = document.createElement("div");
        body.className = "workspace-document-inspector-body workspace-document-inspector-body--operation workspace-document-inspector-body--operation-loading";

        body.append(
            renderPanelHeading(
                "SolomonAI Governed Workflow",
                operationLabel,
                documentName,
                "workspace-document-panel-heading--operation"
            ),
            renderPanelNotice(
                "sync",
                detail,
                "workspace-document-panel-notice--info"
            )
        );

        const status = document.createElement("div");
        status.className = "workspace-document-operation-status";
        status.setAttribute("role", "status");
        status.append(
            textElement("span", "icon", "sync"),
            textElement("strong", "", statusLabel)
        );

        body.append(status);
        inspector.append(renderInspectorNavigation(explorer, "Workflow Running"), body);
    }

    function renderOperationResult(explorer, response, options) {
        const inspector = getInspector(explorer);
        const operationLabel = getOperationLabel(response, options);
        const documentName = getOperationDocumentName(response, options);
        const status = getOperationStatus(response);
        const pending = isPendingOperationResponse(response);
        const summary = getOperationSummary(response, options);
        const body = document.createElement("div");

        if (!inspector) {
            return;
        }

        if (openReportSurfaceIfAvailable(response)) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        body.className = "workspace-document-inspector-body workspace-document-inspector-body--operation workspace-document-inspector-body--operation-result";

        body.append(
            renderPanelHeading(
                "SolomonAI Governed Workflow",
                operationLabel,
                documentName,
                "workspace-document-panel-heading--operation"
            ),
            renderPanelNotice(
                pending ? "sync" : "task_alt",
                pending
                    ? "The operation is running on the server. Refresh this file later to view the finished report."
                    : "The operation completed on the server. This result is a real response returned by the governed workflow.",
                pending
                    ? "workspace-document-panel-notice--info"
                    : "workspace-document-panel-notice--success"
            )
        );

        const summaryBlock = document.createElement("div");
        summaryBlock.className = "workspace-document-operation-result-copy";

        summary.split("\n").forEach(function (line) {
            const paragraph = document.createElement("p");
            paragraph.textContent = line;
            summaryBlock.appendChild(paragraph);
        });

        body.append(summaryBlock);

        inspector.append(
            renderInspectorNavigation(explorer, pending ? "Workflow Running" : "Workflow Result"),
            body,
            renderOperationActions(response, options, explorer)
        );
    }

    function renderOperationError(explorer, message, options) {
        const inspector = getInspector(explorer);
        const documentName = cleanText(options?.documentName) || "Selected file";
        const operationLabel = cleanText(options?.operationLabel) || BID_SCOPE_OPERATION_LABEL;

        if (!inspector) {
            return;
        }

        prepareInspector(inspector);
        explorer.setAttribute("data-document-selected", "true");

        const body = document.createElement("div");
        body.className = "workspace-document-inspector-body workspace-document-inspector-body--operation workspace-document-inspector-body--operation-error";

        body.append(
            renderPanelHeading(
                "SolomonAI Governed Workflow",
                `${operationLabel} could not start`,
                documentName,
                "workspace-document-panel-heading--error"
            ),
            renderPanelNotice(
                "error",
                message || "The document operation could not be completed.",
                "workspace-document-panel-notice--error"
            )
        );

        const actions = document.createElement("div");
        actions.className = "workspace-document-inspector-actions";
        actions.append(
            sectionViewButton(
                explorer,
                "workspace-document-command workspace-document-command-neutral workspace-document-view-button",
                "folder_open",
                `Back to ${getWorkspaceSectionLabel(explorer)}`
            )
        );

        inspector.append(renderInspectorNavigation(explorer, "Operation Error"), body, actions);
    }

    function renderDeleteConfirmation(explorer, rawDoc) {
        const inspector = getInspector(explorer);
        const doc = getPreviewDocument(rawDoc);

        if (!inspector || !doc) {
            return;
        }

        if (isPreviewFolderDocument(rawDoc) || isPreviewFolderDocument(doc)) {
            renderFolderDetails(explorer, rawDoc);
            return;
        }

        prepareInspector(inspector, { danger: true });
        explorer.setAttribute("data-document-selected", "true");

        const header = document.createElement("div");
        header.className = "workspace-document-inspector-header workspace-document-inspector-header--danger";
        header.append(
            textElement("p", "workspace-kicker workspace-kicker-danger", "Move to Trash"),
            textElement("strong", "", doc.original_name || doc.random_name || "Selected Document")
        );

        const body = document.createElement("div");
        body.className = "workspace-document-inspector-body workspace-document-inspector-body--danger";

        const warningCopy = document.createElement("div");
        warningCopy.className = "workspace-document-danger-copy";
        warningCopy.append(
            textElement("strong", "", "Move this file to Trash?"),
            textElement("p", "", "This will remove the file from My Files and keep the stored copy in Trash for recovery."),
            textElement("small", "", "This will not start DocIntel, run analysis, or change a workflow.")
        );

        body.append(
            textElement("span", "icon", "delete_outline"),
            warningCopy
        );

        const actions = document.createElement("div");
        actions.className = "workspace-document-inspector-actions workspace-document-inspector-actions--danger";

        const confirmButton = actionButton(
            "workspace-document-command workspace-document-command-danger workspace-document-command-danger-primary",
            "data-document-delete-confirm",
            doc.document_id || "",
            "delete_outline",
            "Move to Trash"
        );

        const cancelButton = actionButton(
            "workspace-document-command workspace-document-command-neutral",
            "data-document-delete-cancel",
            doc.document_id || "",
            "close",
            "Cancel"
        );

        confirmButton.setAttribute("data-document-operation-confirm", doc.document_id || "");
        cancelButton.setAttribute("data-document-operation-cancel", doc.document_id || "");

        actions.append(confirmButton, cancelButton);
        inspector.append(renderInspectorNavigation(explorer, "Move to Trash"), header, body, actions);
    }

    window[API_NAME] = Object.freeze({
        renderEmpty,
        renderError,
        renderDetails,
        renderSummaryLoading,
        renderSummary,
        renderSummaryError,
        renderFolderDetails,
        isPreviewFolderDocument,
        renderOperationHandoff,
        renderOperationProcessing,
        renderOperationResult,
        renderOperationError,
        renderDeleteConfirmation
    });
})();