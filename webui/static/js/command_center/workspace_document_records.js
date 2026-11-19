/* -------------------------------------------------------------------
   FILE: workspace_document_records.js
   DIRECTORY: webui/static/js/command_center/
   Solomon Documents record normalization and metadata contract
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentRecords";
    const BID_SCOPE_OPERATION_LABEL = "Bid & Scope Review";
    const DOCUMENT_ROW_SELECTOR = ".workspace-document-file[data-document-id]";
    const DOCUMENT_METADATA_CONTRACT = "workspace_document_metadata_v1";
    const DOCUMENT_METADATA_UNAVAILABLE = Object.freeze({
        size: "Size unavailable",
        date: "Date unavailable",
        location: "Location unavailable"
    });

    if (window[API_NAME]) {
        return;
    }

    function compactString(value) {
        return String(value || "").trim();
    }

    function firstObject() {
        for (let index = 0; index < arguments.length; index += 1) {
            const value = arguments[index];

            if (value && typeof value === "object" && !Array.isArray(value)) {
                return value;
            }
        }

        return {};
    }

    function firstString() {
        for (let index = 0; index < arguments.length; index += 1) {
            const value = compactString(arguments[index]);

            if (value) {
                return value;
            }
        }

        return "";
    }

    function isUnavailableDisplayValue(value) {
        return [
            "",
            "-",
            "—",
            "n/a",
            "na",
            "null",
            "undefined"
        ].includes(compactString(value).toLowerCase());
    }

    function firstDisplayString() {
        for (let index = 0; index < arguments.length; index += 1) {
            const value = compactString(arguments[index]);

            if (!isUnavailableDisplayValue(value)) {
                return value;
            }
        }

        return "";
    }

    function getCanonicalSizeBytes(doc, isFolder) {
        if (isFolder) {
            return "";
        }

        const metadata = firstObject(
            doc?.metadata,
            doc?.document_metadata,
            doc?.workspace_metadata
        );
        const candidates = [
            metadata.size_bytes,
            doc?.size_bytes,
            doc?.file_size_bytes,
            doc?.content_length,
            doc?.bytes,
            doc?.file_size,
            doc?.size
        ];

        for (const candidate of candidates) {
            if (candidate === null || candidate === undefined || compactString(candidate) === "") {
                continue;
            }

            const numericValue = Number(candidate);

            if (Number.isFinite(numericValue) && numericValue >= 0) {
                return Math.floor(numericValue);
            }
        }

        return "";
    }

    function firstBoolean() {
        for (let index = 0; index < arguments.length; index += 1) {
            if (typeof arguments[index] === "boolean") {
                return arguments[index];
            }
        }

        return false;
    }

    function normalizeBooleanValue(value, fallback) {
        if (typeof value === "boolean") {
            return value;
        }

        const cleanValue = compactString(value).toLowerCase();

        if (!cleanValue) {
            return Boolean(fallback);
        }

        if (["true", "1", "yes", "y"].includes(cleanValue)) {
            return true;
        }

        if (["false", "0", "no", "n"].includes(cleanValue)) {
            return false;
        }

        return Boolean(fallback);
    }

    function normalizeStatusToken(value) {
        return String(value || "")
            .trim()
            .toLowerCase()
            .replace(/[\s-]+/g, "_");
    }

    function humanizeStatus(value) {
        return String(value || "")
            .trim()
            .replace(/[_-]+/g, " ")
            .replace(/\s+/g, " ")
            .replace(/\b\w/g, function (match) {
                return match.toUpperCase();
            });
    }

    function getWorkspaceObjectKind(doc) {
        return normalizeStatusToken(firstString(
            doc?.workspace_item_type,
            doc?.item_type,
            doc?.resource_type,
            doc?.document_kind,
            doc?.object_type,
            doc?.kind,
            doc?.document_type,
            doc?.type
        ));
    }

    function isWorkspaceFolderKind(value) {
        return [
            "folder",
            "workspace_folder",
            "workspace-folder",
            "directory",
            "workspace_directory",
            "workspace-directory"
        ].includes(normalizeStatusToken(value));
    }

    function isWorkspaceFileKind(value) {
        return [
            "file",
            "workspace_file",
            "workspace-file",
            "document",
            "stored_document",
            "stored-document",
            "upload",
            "uploaded_file",
            "uploaded-file"
        ].includes(normalizeStatusToken(value));
    }

    function hasWorkspaceFolderContract(doc) {
        return normalizeStatusToken(firstString(
            doc?.folder_contract,
            doc?.workspace_folder_contract,
            doc?.contract,
            doc?.workspace_contract
        )) === "workspace_folder_v1";
    }

    function isWorkspaceFolderRecord(doc) {
        const objectKind = getWorkspaceObjectKind(doc);
        const explicitFolder = Boolean(
            isWorkspaceFolderKind(objectKind) ||
            doc?.folder === true ||
            doc?.is_folder === true ||
            hasWorkspaceFolderContract(doc)
        );

        if (!explicitFolder) {
            return false;
        }

        return !isWorkspaceFileKind(objectKind);
    }

    function getFolderId(doc) {
        if (!isWorkspaceFolderRecord(doc)) {
            return "";
        }

        return firstString(
            doc?.folder_id,
            doc?.workspace_item_id,
            doc?.random_name,
            doc?.document_id
        );
    }

    function getFileName(doc) {
        const folderFallback = getFolderId(doc);
        const metadata = firstObject(
            doc?.metadata,
            doc?.document_metadata,
            doc?.workspace_metadata
        );

        return String(
            doc?.original_name ||
            doc?.display_name ||
            doc?.name ||
            metadata.name ||
            metadata.display_name ||
            doc?.title ||
            doc?.filename ||
            doc?.random_name ||
            doc?.document_id ||
            folderFallback ||
            ""
        ).trim();
    }

    function getDocumentId(doc) {
        if (isWorkspaceFolderRecord(doc)) {
            return firstString(
                doc?.document_id,
                doc?.random_name,
                doc?.folder_id,
                doc?.workspace_item_id
            );
        }

        return String(doc?.document_id || doc?.random_name || "").trim();
    }

    function getFileExtension(doc) {
        if (isWorkspaceFolderRecord(doc)) {
            return "";
        }

        const explicitExtension = String(doc?.extension || doc?.file_extension || "").trim().toLowerCase();

        if (explicitExtension) {
            return explicitExtension.startsWith(".") ? explicitExtension : `.${explicitExtension}`;
        }

        const filename = getFileName(doc);
        const dotIndex = filename.lastIndexOf(".");

        if (dotIndex < 0) {
            return "";
        }

        return filename.slice(dotIndex).toLowerCase();
    }

    function getServerTypeLabel(doc) {
        if (isWorkspaceFolderRecord(doc)) {
            return "Folder";
        }

        const metadata = firstObject(
            doc?.metadata,
            doc?.document_metadata,
            doc?.workspace_metadata
        );
        const explicitLabel = firstDisplayString(
            metadata.type_label,
            doc?.type_label,
            doc?.file_type_label
        );

        if (explicitLabel && explicitLabel !== "Workspace File") {
            return explicitLabel;
        }

        const extension = getFileExtension(doc);

        if (extension === ".pdf") {
            return "PDF Document";
        }

        if (extension === ".doc" || extension === ".docx") {
            return "Word Document";
        }

        if (extension === ".xls" || extension === ".xlsx") {
            return "Spreadsheet";
        }

        if (extension === ".csv") {
            return "CSV File";
        }

        if (extension === ".txt") {
            return "Text Document";
        }

        if ([".png", ".jpg", ".jpeg"].includes(extension)) {
            return "Image File";
        }

        return explicitLabel || "Workspace File";
    }

    function normalizeReportRecord(doc) {
        const report = firstObject(
            doc?.report,
            doc?.bid_scope_review,
            doc?.latest_report,
            doc?.latest_review,
            doc?.saved_review
        );
        const savedReview = firstObject(doc?.saved_review, report?.saved_review);
        const reviewId = firstString(
            report.review_id,
            report.saved_review_id,
            savedReview.review_id,
            doc?.review_id,
            doc?.saved_review_id
        );
        const jobId = firstString(
            report.job_id,
            report.report_job_id,
            doc?.job_id,
            doc?.report_job_id
        );
        const status = normalizeStatusToken(firstString(
            report.status,
            report.report_status,
            doc?.report_status,
            doc?.analysis_status,
            doc?.workflow_status
        ));
        const fragmentUrl = firstString(
            report.fragment_url,
            report.report_fragment_url,
            doc?.fragment_url,
            doc?.report_fragment_url
        );
        const reportUrl = firstString(
            report.report_url,
            report.result_url,
            report.url,
            doc?.report_url,
            doc?.report_result_url
        );
        const preparingUrl = firstString(
            report.preparing_url,
            doc?.preparing_url,
            doc?.report_preparing_url
        );
        const statusUrl = firstString(
            report.status_url,
            doc?.status_url,
            doc?.report_status_url
        );
        const saved = firstBoolean(
            report.saved,
            savedReview.saved,
            doc?.report_saved,
            doc?.has_saved_review
        );
        const hasExplicitReport = Boolean(
            saved ||
            reviewId ||
            jobId ||
            fragmentUrl ||
            reportUrl ||
            preparingUrl ||
            statusUrl ||
            ["complete", "completed", "finished", "ready"].includes(status)
        );

        return {
            operation_label: firstString(
                report.operation_label,
                report.label,
                doc?.operation_label,
                BID_SCOPE_OPERATION_LABEL
            ),
            status,
            saved,
            review_id: reviewId,
            job_id: jobId,
            fragment_url: fragmentUrl,
            report_url: reportUrl,
            preparing_url: preparingUrl,
            status_url: statusUrl,
            title: firstString(
                report.title,
                report.result_title,
                doc?.report_title
            ),
            generated_at: firstString(
                report.generated_at,
                report.completed_at,
                report.updated_at,
                report.created_at,
                doc?.report_generated_at,
                doc?.report_completed_at
            ),
            has_report: hasExplicitReport
        };
    }

    function getDocumentStatus(doc, isFolder) {
        const metadata = firstObject(
            doc?.metadata,
            doc?.document_metadata,
            doc?.workspace_metadata
        );
        const explicitStatus = firstString(
            metadata.status_token,
            metadata.status,
            doc?.document_status,
            doc?.storage_status,
            doc?.library_status,
            doc?.status
        );
        const isTrashed = normalizeBooleanValue(doc?.trashed, false);

        if (isTrashed) {
            return "trash";
        }

        if (explicitStatus) {
            return explicitStatus;
        }

        return isFolder ? "active" : "stored";
    }

    function normalizeDocument(doc) {
        const isFolder = isWorkspaceFolderRecord(doc);
        const documentId = getDocumentId(doc);
        const folderId = getFolderId(doc);
        const sourceMetadata = firstObject(
            doc?.metadata,
            doc?.document_metadata,
            doc?.workspace_metadata
        );
        const handoff = !isFolder && typeof doc?.handoff === "object" && doc.handoff ? doc.handoff : {};
        const selectedForWorkflow = isFolder ? false : Boolean(doc?.selected_for_workflow || doc?.active);
        const report = isFolder ? normalizeReportRecord({}) : normalizeReportRecord(doc);
        const documentStatus = getDocumentStatus(doc, isFolder);
        const trashed = normalizeBooleanValue(doc?.trashed, false) || normalizeStatusToken(documentStatus) === "trash";
        const workspaceItemType = isFolder ? "folder" : firstString(
            doc?.workspace_item_type,
            doc?.item_type,
            doc?.resource_type,
            doc?.document_kind,
            "file"
        );
        const normalizedDoc = {
            metadata_contract: DOCUMENT_METADATA_CONTRACT,
            document_id: documentId,
            file_id: isFolder ? "" : String(doc?.file_id || "").trim(),
            random_name: String(doc?.random_name || documentId).trim(),
            original_name: getFileName(doc) || documentId,
            display_name: firstString(doc?.display_name, doc?.name, sourceMetadata.display_name, sourceMetadata.name, getFileName(doc), documentId),
            name: firstString(doc?.name, doc?.display_name, sourceMetadata.name, sourceMetadata.display_name, getFileName(doc), documentId),
            active: selectedForWorkflow,
            selected_for_workflow: selectedForWorkflow,
            type_label: getServerTypeLabel(doc),
            size_bytes: getCanonicalSizeBytes(doc, isFolder),
            size_label: isFolder ? "" : firstDisplayString(
                sourceMetadata.size_label,
                doc?.size_label,
                doc?.file_size_label,
                doc?.formatted_size,
                doc?.display_size
            ),
            uploaded_at: firstString(
                sourceMetadata.uploaded_at,
                doc?.uploaded_at,
                doc?.upload_time,
                doc?.uploaded_on,
                doc?.created_at
            ),
            uploaded_label: firstDisplayString(
                sourceMetadata.uploaded_label,
                doc?.uploaded_label,
                doc?.uploaded_at_label,
                doc?.upload_time_label
            ),
            created_at: firstString(
                sourceMetadata.created_at,
                doc?.created_at,
                doc?.uploaded_at,
                doc?.upload_time
            ),
            created_label: firstDisplayString(
                sourceMetadata.created_label,
                doc?.created_label,
                doc?.created_at_label
            ),
            updated_at: firstString(
                sourceMetadata.updated_at,
                doc?.updated_at,
                doc?.modified_at
            ),
            updated_label: firstDisplayString(
                sourceMetadata.updated_label,
                doc?.updated_label,
                doc?.updated_at_label,
                doc?.modified_label
            ),
            recent_activity_at: firstString(
                doc?.recent_activity_at,
                doc?.recent_activity_at_utc
            ),
            recent_activity_at_utc: firstString(
                doc?.recent_activity_at_utc,
                doc?.recent_activity_at
            ),
            recent_activity_kind: firstString(
                doc?.recent_activity_kind,
                "uploaded"
            ),
            recent_activity_reason: firstDisplayString(
                doc?.recent_activity_reason,
                "Uploaded"
            ),
            recent_group_label: firstDisplayString(
                doc?.recent_group_label,
                "Earlier"
            ),
            owner_label: firstDisplayString(
                doc?.owner_label,
                doc?.owner_name,
                doc?.owner,
                "Me"
            ),
            location_label: firstDisplayString(
                sourceMetadata.location_label,
                doc?.location_label,
                doc?.workspace_location_label,
                doc?.authorized_location_label,
                doc?.folder_location_label,
                doc?.parent_folder_name
            ),
            storage_status: firstString(
                sourceMetadata.status_token,
                sourceMetadata.status,
                doc?.storage_status,
                doc?.library_status,
                documentStatus
            ),
            storage_status_label: firstDisplayString(
                sourceMetadata.status_label,
                doc?.storage_status_label,
                doc?.document_status_label,
                doc?.status_label
            ),
            workflow_status: isFolder ? "not_applicable" : doc?.workflow_status || "not_started",
            workflow_status_label: isFolder ? "" : firstDisplayString(
                doc?.workflow_status_label,
                doc?.workflow_label
            ),
            analysis_status: isFolder ? "not_applicable" : doc?.analysis_status || handoff.analysis_status || "not_started",
            handoff_required: isFolder ? false : doc?.handoff_required !== false,
            handoff_label: isFolder ? "" : handoff.label || "Run Bid & Scope Review",
            handoff_endpoint: isFolder ? "" : handoff.target || "",
            workflow_route: isFolder ? "" : handoff.workflow_route || doc?.workflow_route || "",
            workflow_key: isFolder ? "" : handoff.workflow_key || doc?.workflow_key || "bid_scope_review",
            extension: getFileExtension(doc),
            reader_url: isFolder ? "" : doc?.reader_url || doc?.workspace_reader_url || "",
            workspace_reader_url: isFolder ? "" : doc?.workspace_reader_url || doc?.reader_url || "",
            page_count: isFolder ? "" : doc?.page_count || "",
            page_count_label: isFolder ? "" : doc?.page_count_label || "",
            workspace_item_type: workspaceItemType,
            item_type: isFolder ? "folder" : firstString(doc?.item_type, workspaceItemType),
            resource_type: isFolder ? "folder" : firstString(doc?.resource_type, "file"),
            document_kind: isFolder ? "folder" : firstString(doc?.document_kind, "file"),
            object_type: isFolder ? "folder" : firstString(doc?.object_type, "file"),
            kind: isFolder ? "folder" : firstString(doc?.kind, "file"),
            folder: isFolder,
            is_folder: isFolder,
            folder_id: isFolder ? folderId : "",
            workspace_item_id: isFolder ? firstString(doc?.workspace_item_id, folderId, documentId) : "",
            workspace_object_id: isFolder ? firstString(doc?.workspace_object_id, folderId, documentId) : documentId,
            workspace_folder_id: isFolder ? "" : firstString(doc?.workspace_folder_id, doc?.folder_id),
            parent_folder_id: firstString(doc?.parent_folder_id),
            parent_folder_name: firstString(doc?.parent_folder_name),
            folder_path: firstString(doc?.folder_path, doc?.path),
            path: firstString(doc?.path, doc?.folder_path),
            depth: doc?.depth || "",
            scope: firstString(doc?.scope),
            visibility_scope: isFolder ? firstString(doc?.visibility_scope, doc?.access_scope, doc?.folder_scope, doc?.scope) : "",
            access_scope: isFolder ? firstString(doc?.access_scope, doc?.visibility_scope, doc?.folder_scope) : "",
            folder_scope: isFolder ? firstString(doc?.folder_scope, doc?.visibility_scope, doc?.access_scope) : "",
            visibility_label: firstString(doc?.visibility_label),
            folder_contract: isFolder ? firstString(doc?.folder_contract, doc?.workspace_folder_contract, "workspace_folder_v1") : "",
            folder_visibility_policy: isFolder ? firstString(doc?.folder_visibility_policy) : "",
            folder_permission_scope: isFolder ? firstString(doc?.folder_permission_scope) : "",
            file_authority_inherited: isFolder ? normalizeBooleanValue(doc?.file_authority_inherited, false) : false,
            allow_ai_query: isFolder ? normalizeBooleanValue(doc?.allow_ai_query, false) : true,
            capabilities: firstObject(doc?.capabilities),
            surface_actions_authoritative: doc?.surface_actions_authoritative === true,
            surface_actions: Array.isArray(doc?.surface_actions) ? doc.surface_actions.slice() : [],
            available_actions: Array.isArray(doc?.available_actions) ? doc.available_actions.slice() : [],
            actions: Array.isArray(doc?.actions) ? doc.actions.slice() : [],
            solomon_actions_authoritative: !isFolder && doc?.solomon_actions_authoritative === true,
            solomon_actions: !isFolder && Array.isArray(doc?.solomon_actions)
                ? doc.solomon_actions.map(function (action) {
                    return action && typeof action === "object" && !Array.isArray(action)
                        ? Object.assign({}, action)
                        : action;
                })
                : [],
            solomon_action_count: !isFolder && Number.isInteger(Number(doc?.solomon_action_count))
                ? Math.max(0, Number(doc.solomon_action_count))
                : 0,
            folder_url: isFolder ? firstString(doc?.folder_url, doc?.canonical_url, doc?.open_url, doc?.url) : "",
            canonical_url: isFolder ? firstString(doc?.canonical_url, doc?.folder_url, doc?.open_url, doc?.url) : "",
            open_url: isFolder ? firstString(doc?.open_url, doc?.folder_url, doc?.canonical_url, doc?.url) : firstString(doc?.open_url),
            organization_id: firstString(doc?.organization_id),
            group_id: firstString(doc?.group_id),
            document_status: documentStatus,
            status: documentStatus,
            trashed,
            trashed_at: doc?.trashed_at || "",
            report,
            report_status: report.status,
            report_saved: report.saved,
            report_review_id: report.review_id,
            report_job_id: report.job_id,
            report_url: report.report_url,
            report_fragment_url: report.fragment_url,
            report_preparing_url: report.preparing_url,
            report_status_url: report.status_url,
            has_report: isFolder ? false : report.has_report
        };

        normalizedDoc.metadata = buildCanonicalDocumentMetadata(normalizedDoc);
        normalizedDoc.size_label = normalizedDoc.metadata.size_label;
        normalizedDoc.uploaded_label = normalizedDoc.metadata.uploaded_label;
        normalizedDoc.created_label = normalizedDoc.metadata.created_label;
        normalizedDoc.updated_label = normalizedDoc.metadata.updated_label;
        normalizedDoc.location_label = normalizedDoc.metadata.location_label;
        normalizedDoc.storage_status_label = normalizedDoc.metadata.status_label;

        return normalizedDoc;
    }

    function getDocumentIconName(doc) {
        const normalizedDoc = normalizeDocument(doc);

        if (isWorkspaceFolderRecord(normalizedDoc)) {
            return "folder";
        }

        const extension = normalizedDoc.extension;

        if (extension === ".pdf") {
            return "picture_as_pdf";
        }

        if (extension === ".doc" || extension === ".docx" || extension === ".txt") {
            return "description";
        }

        if (extension === ".csv" || extension === ".xls" || extension === ".xlsx") {
            return "table_chart";
        }

        if ([".png", ".jpg", ".jpeg"].includes(extension)) {
            return "image";
        }

        return "insert_drive_file";
    }

    function formatFileSize(sizeBytes) {
        if (sizeBytes === null || sizeBytes === undefined || compactString(sizeBytes) === "") {
            return DOCUMENT_METADATA_UNAVAILABLE.size;
        }

        const size = Number(sizeBytes);

        if (!Number.isFinite(size) || size < 0) {
            return DOCUMENT_METADATA_UNAVAILABLE.size;
        }

        if (size < 1024) {
            return `${Math.floor(size)} B`;
        }

        if (size < 1024 * 1024) {
            return `${(size / 1024).toFixed(1)} KB`;
        }

        if (size < 1024 * 1024 * 1024) {
            return `${(size / (1024 * 1024)).toFixed(1)} MB`;
        }

        return `${(size / (1024 * 1024 * 1024)).toFixed(1)} GB`;
    }

    function formatDateTime(value) {
        const rawValue = compactString(value);

        if (isUnavailableDisplayValue(rawValue)) {
            return "";
        }

        const parsedDate = new Date(rawValue);

        if (Number.isNaN(parsedDate.getTime())) {
            return rawValue;
        }

        return parsedDate.toLocaleString(undefined, {
            year: "numeric",
            month: "short",
            day: "2-digit",
            hour: "numeric",
            minute: "2-digit"
        });
    }

    function getDocumentStorageLabelFromNormalized(normalizedDoc) {
        const statusToken = normalizeStatusToken(firstString(
            normalizedDoc?.storage_status,
            normalizedDoc?.document_status,
            normalizedDoc?.status
        ));

        if (normalizedDoc?.trashed || ["trash", "trashed", "deleted"].includes(statusToken)) {
            return "In Trash";
        }

        const explicitLabel = firstDisplayString(normalizedDoc?.storage_status_label);

        if (explicitLabel) {
            return explicitLabel;
        }

        if (isWorkspaceFolderRecord(normalizedDoc)) {
            if (!statusToken || ["active", "available", "stored", "ready"].includes(statusToken)) {
                return "Folder";
            }

            return humanizeStatus(statusToken);
        }

        if (!statusToken || ["active", "available", "stored", "ready"].includes(statusToken)) {
            return "Stored";
        }

        return humanizeStatus(statusToken);
    }

    function buildCanonicalDocumentMetadata(normalizedDoc) {
        const isFolder = isWorkspaceFolderRecord(normalizedDoc);
        const uploadedLabel = firstDisplayString(
            formatDateTime(normalizedDoc?.uploaded_at),
            normalizedDoc?.uploaded_label
        );
        const createdLabel = firstDisplayString(
            formatDateTime(normalizedDoc?.created_at || normalizedDoc?.uploaded_at),
            normalizedDoc?.created_label
        );
        const updatedLabel = firstDisplayString(
            formatDateTime(normalizedDoc?.updated_at),
            normalizedDoc?.updated_label
        );
        const sizeLabel = isFolder
            ? "Not applicable"
            : firstDisplayString(
                normalizedDoc?.size_bytes === "" ? "" : formatFileSize(normalizedDoc?.size_bytes),
                normalizedDoc?.size_label
            );

        return {
            contract: DOCUMENT_METADATA_CONTRACT,
            object_id: normalizedDoc?.workspace_object_id || normalizedDoc?.document_id || "",
            object_kind: isFolder ? "folder" : "file",
            name: normalizedDoc?.display_name || normalizedDoc?.original_name || normalizedDoc?.document_id || "",
            type_label: normalizedDoc?.type_label || (isFolder ? "Folder" : "Workspace File"),
            size_bytes: isFolder ? "" : normalizedDoc?.size_bytes,
            size_label: sizeLabel || DOCUMENT_METADATA_UNAVAILABLE.size,
            uploaded_at: normalizedDoc?.uploaded_at || "",
            uploaded_label: uploadedLabel || DOCUMENT_METADATA_UNAVAILABLE.date,
            created_at: normalizedDoc?.created_at || "",
            created_label: createdLabel || DOCUMENT_METADATA_UNAVAILABLE.date,
            updated_at: normalizedDoc?.updated_at || "",
            updated_label: updatedLabel || DOCUMENT_METADATA_UNAVAILABLE.date,
            location_label: firstDisplayString(normalizedDoc?.location_label) || DOCUMENT_METADATA_UNAVAILABLE.location,
            status_token: normalizeStatusToken(firstString(
                normalizedDoc?.storage_status,
                normalizedDoc?.document_status,
                normalizedDoc?.status
            )),
            status_label: getDocumentStorageLabelFromNormalized(normalizedDoc)
        };
    }

    function getDocumentMetadata(doc) {
        const normalizedDoc = normalizeDocument(doc);

        return Object.assign({}, normalizedDoc.metadata);
    }

    function getDocumentMetadataColumns(doc) {
        const metadata = getDocumentMetadata(doc);

        return {
            contract: metadata.contract,
            name: metadata.name,
            type: metadata.type_label,
            size: metadata.size_label,
            uploaded: metadata.uploaded_label,
            location: metadata.location_label,
            status: metadata.status_label
        };
    }

    function getDocumentUploadedLabel(doc) {
        return getDocumentMetadata(doc).uploaded_label;
    }

    function getDocumentStorageLabel(doc) {
        return getDocumentMetadata(doc).status_label;
    }

    function getDocumentReportRecord(doc) {
        return normalizeDocument(doc).report;
    }

    function hasDocumentReport(doc) {
        if (isWorkspaceFolderRecord(doc)) {
            return false;
        }

        return Boolean(getDocumentReportRecord(doc).has_report);
    }

    function getDocumentReportOpenUrl(doc) {
        if (isWorkspaceFolderRecord(doc)) {
            return "";
        }

        const report = getDocumentReportRecord(doc);

        return report.fragment_url || report.report_url || report.preparing_url || "";
    }

    function getDocumentReportActionLabel(doc) {
        if (isWorkspaceFolderRecord(doc)) {
            return "";
        }

        if (hasDocumentReport(doc)) {
            return `Open ${getDocumentReportRecord(doc).operation_label || BID_SCOPE_OPERATION_LABEL}`;
        }

        return `Run ${BID_SCOPE_OPERATION_LABEL}`;
    }

    function getDocumentReportLabel(doc) {
        const normalizedDoc = normalizeDocument(doc);

        if (isWorkspaceFolderRecord(normalizedDoc)) {
            return "Not applicable";
        }

        const report = normalizedDoc.report;
        const analysisStatus = normalizeStatusToken(normalizedDoc.analysis_status);
        const workflowStatus = normalizeStatusToken(normalizedDoc.workflow_status);
        const status = report.status || (analysisStatus && analysisStatus !== "not_started" ? analysisStatus : workflowStatus);

        if (report.has_report) {
            if (["queued", "submitted", "running", "processing", "in_progress"].includes(status)) {
                return "Preparing";
            }

            if (["failed", "error", "cancelled", "canceled"].includes(status)) {
                return "Needs attention";
            }

            if (report.review_id) {
                return `Complete · #${report.review_id}`;
            }

            return "Complete";
        }

        if (!status || status === "not_started" || status === "stored") {
            return "Not created";
        }

        if (["queued", "submitted", "running", "processing", "in_progress"].includes(status)) {
            return "Preparing";
        }

        if (["complete", "completed", "finished", "ready"].includes(status)) {
            return "Complete";
        }

        if (["failed", "error", "cancelled", "canceled"].includes(status)) {
            return "Needs attention";
        }

        return humanizeStatus(status);
    }

    function getDocumentWorkflowLabel(doc) {
        const normalizedDoc = normalizeDocument(doc);

        if (isWorkspaceFolderRecord(normalizedDoc)) {
            if (normalizedDoc.trashed) {
                return "In Trash";
            }

            return "Folder";
        }

        const reportLabel = getDocumentReportLabel(normalizedDoc);

        if (reportLabel !== "Not created") {
            return reportLabel;
        }

        if (normalizedDoc.selected_for_workflow) {
            return "Selected";
        }

        return "Stored";
    }

    function buildDocumentMetadataRows(doc) {
        const normalizedDoc = normalizeDocument(doc);
        const metadata = normalizedDoc.metadata;

        if (isWorkspaceFolderRecord(normalizedDoc)) {
            const rows = [
                ["Type", metadata.type_label],
                ["Location", metadata.location_label],
                ["Status", metadata.status_label],
                ["Created", metadata.created_label]
            ];

            if (normalizedDoc.visibility_label) {
                rows.push(["Visibility", normalizedDoc.visibility_label]);
            }

            if (normalizedDoc.parent_folder_name) {
                rows.push(["Parent", normalizedDoc.parent_folder_name]);
            }

            if (
                metadata.updated_label !== DOCUMENT_METADATA_UNAVAILABLE.date &&
                metadata.updated_label !== metadata.created_label
            ) {
                rows.push(["Updated", metadata.updated_label]);
            }

            return rows;
        }

        const rows = [
            ["Type", metadata.type_label],
            ["Size", metadata.size_label],
            ["Uploaded", metadata.uploaded_label],
            ["Location", metadata.location_label],
            ["Status", metadata.status_label],
            ["Report", getDocumentReportLabel(normalizedDoc)]
        ];

        if (normalizedDoc.page_count_label) {
            rows.push(["Pages", normalizedDoc.page_count_label]);
        } else if (normalizedDoc.page_count) {
            rows.push(["Pages", `${normalizedDoc.page_count} ${Number(normalizedDoc.page_count) === 1 ? "page" : "pages"}`]);
        }

        if (
            metadata.updated_label !== DOCUMENT_METADATA_UNAVAILABLE.date &&
            metadata.updated_label !== metadata.uploaded_label
        ) {
            rows.push(["Updated", metadata.updated_label]);
        }

        const reportGeneratedLabel = formatDateTime(normalizedDoc.report.generated_at);

        if (reportGeneratedLabel) {
            rows.push(["Report Updated", reportGeneratedLabel]);
        }

        return rows;
    }

    function getRowDocumentName(row) {
        return String(
            row?.getAttribute("data-document-name") ||
            row?.getAttribute("data-original-name") ||
            row?.getAttribute("data-workspace-object-name") ||
            row?.querySelector("[data-document-name]")?.textContent ||
            row?.querySelector("strong")?.textContent ||
            ""
        ).trim();
    }

    function getRowDocumentTypeLabel(row) {
        return String(
            row?.getAttribute("data-document-type-label") ||
            row?.getAttribute("data-workspace-object-kind") ||
            row?.querySelector("[data-document-list-cell='type']")?.textContent ||
            ""
        ).trim();
    }

    function getRowDocumentSize(row) {
        return String(
            row?.getAttribute("data-document-size-bytes") ||
            row?.getAttribute("data-document-size") ||
            row?.getAttribute("data-size-bytes") ||
            ""
        ).trim();
    }

    function getRowDocumentSizeLabel(row) {
        return firstDisplayString(
            row?.getAttribute("data-document-size-label"),
            row?.querySelector("[data-document-list-cell='size']")?.textContent
        );
    }

    function getRowDocumentUploadedAt(row) {
        return String(
            row?.getAttribute("data-document-uploaded-at") ||
            row?.getAttribute("data-uploaded-at") ||
            ""
        ).trim();
    }

    function getRowDocumentUploadedLabel(row) {
        return firstDisplayString(
            row?.getAttribute("data-document-uploaded-label"),
            row?.getAttribute("data-uploaded-label"),
            row?.querySelector("[data-document-list-cell='uploaded']")?.textContent
        );
    }

    function getRowDocumentLocationLabel(row) {
        return firstDisplayString(
            row?.getAttribute("data-document-location-label"),
            row?.getAttribute("data-workspace-location-label"),
            row?.getAttribute("data-authorized-location-label")
        );
    }

    function getRowDocumentStatusToken(row) {
        return String(
            row?.getAttribute("data-document-storage-status") ||
            row?.getAttribute("data-document-status") ||
            ""
        ).trim();
    }

    function getRowDocumentWorkflowStatusLabel(row) {
        return firstDisplayString(
            row?.getAttribute("data-document-status-label"),
            row?.getAttribute("data-workflow-status-label"),
            row?.getAttribute("data-workflow-status")
        );
    }

    function getRowDocumentThumbnailUrl(row) {
        return String(
            row?.getAttribute("data-document-thumbnail-url") ||
            row?.querySelector("[data-document-thumbnail] img")?.getAttribute("src") ||
            row?.querySelector("img")?.getAttribute("src") ||
            ""
        ).trim();
    }

    function getInitialDocumentFromRow(row) {
        const documentId = String(row?.getAttribute("data-document-id") || "").trim();
        const randomName = String(row?.getAttribute("data-random-name") || documentId).trim();
        const documentName = getRowDocumentName(row) || documentId;
        const typeLabel = getRowDocumentTypeLabel(row);
        const sizeBytes = getRowDocumentSize(row);
        const sizeLabel = getRowDocumentSizeLabel(row);
        const uploadedAt = getRowDocumentUploadedAt(row);
        const uploadedLabel = getRowDocumentUploadedLabel(row);
        const locationLabel = getRowDocumentLocationLabel(row);
        const storageStatus = getRowDocumentStatusToken(row);
        const workflowStatusLabel = getRowDocumentWorkflowStatusLabel(row);
        const folderId = firstString(
            row?.getAttribute("data-workspace-folder-id"),
            row?.getAttribute("data-folder-id")
        );
        const objectKind = firstString(
            row?.getAttribute("data-workspace-object-kind"),
            row?.getAttribute("data-workspace-item-type"),
            row?.getAttribute("data-document-kind"),
            row?.getAttribute("data-document-type"),
            typeLabel
        );
        const isFolder = Boolean(
            folderId ||
            normalizeStatusToken(objectKind) === "folder" ||
            row?.getAttribute("data-document-folder") === "true" ||
            row?.getAttribute("data-is-folder") === "true"
        );
        const trashed = row?.getAttribute("data-document-trashed") === "true";

        return normalizeDocument({
            metadata_contract: DOCUMENT_METADATA_CONTRACT,
            document_id: documentId,
            random_name: randomName,
            original_name: documentName,
            display_name: documentName,
            name: documentName,
            type_label: isFolder ? "Folder" : typeLabel,
            size_bytes: isFolder ? "" : sizeBytes,
            size_label: isFolder ? "" : sizeLabel,
            uploaded_at: uploadedAt,
            uploaded_label: uploadedLabel,
            location_label: locationLabel,
            selected_for_workflow: !isFolder && row?.getAttribute("data-document-selected-for-workflow") === "true",
            active: !isFolder && row?.getAttribute("data-document-active") === "true",
            document_status: trashed ? "trash" : (storageStatus || (isFolder ? "active" : "stored")),
            storage_status: trashed ? "trash" : (storageStatus || (isFolder ? "active" : "stored")),
            workflow_status: isFolder ? "not_applicable" : row?.getAttribute("data-workflow-status") || "not_started",
            workflow_status_label: isFolder ? "" : workflowStatusLabel,
            analysis_status: isFolder ? "not_applicable" : "",
            reader_url: isFolder ? "" : row?.getAttribute("data-document-reader-url") || "",
            thumbnail_url: getRowDocumentThumbnailUrl(row),
            workspace_item_type: isFolder ? "folder" : "file",
            item_type: isFolder ? "folder" : "file",
            resource_type: isFolder ? "folder" : "file",
            document_kind: isFolder ? "folder" : "file",
            object_type: isFolder ? "folder" : "file",
            kind: isFolder ? "folder" : "file",
            folder: isFolder,
            is_folder: isFolder,
            folder_id: isFolder ? folderId || randomName || documentId : "",
            workspace_item_id: isFolder ? folderId || randomName || documentId : "",
            parent_folder_id: row?.getAttribute("data-parent-folder-id") || "",
            workspace_folder_id: isFolder ? "" : row?.getAttribute("data-workspace-file-folder-id") || "",
            trashed
        });
    }

    function getInitialDocuments(explorer) {
        if (!explorer) {
            return [];
        }

        if (Array.isArray(explorer.__solomonDocuments) && explorer.__solomonDocuments.length) {
            return explorer.__solomonDocuments;
        }

        return Array.from(explorer.querySelectorAll(DOCUMENT_ROW_SELECTOR))
            .map(getInitialDocumentFromRow)
            .filter(function (doc) {
                return Boolean(doc.document_id);
            });
    }

    window[API_NAME] = Object.freeze({
        metadataContract: DOCUMENT_METADATA_CONTRACT,
        getFileName,
        getDocumentId,
        getFileExtension,
        getServerTypeLabel,
        getWorkspaceObjectKind,
        isWorkspaceFolderRecord,
        normalizeDocument,
        getDocumentIconName,
        formatFileSize,
        formatDateTime,
        getDocumentMetadata,
        getDocumentMetadataColumns,
        getDocumentUploadedLabel,
        getDocumentStorageLabel,
        getDocumentWorkflowLabel,
        getDocumentReportRecord,
        getDocumentReportLabel,
        getDocumentReportOpenUrl,
        getDocumentReportActionLabel,
        hasDocumentReport,
        buildDocumentMetadataRows,
        getInitialDocuments
    });
})();