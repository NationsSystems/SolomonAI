/* -------------------------------------------------------------------
   FILE: workspace_document_drag_drop.js
   DIRECTORY: webui/static/js/command_center/
   -------------------------------------------------------------------
   Canonical Solomon workspace drag/drop interaction layer.

   Drag/drop is transport-only UX. Server authority remains decisive.
   - External OS files -> Upload into My Files / an owned folder.
   - Owned Solomon files -> Move into an owned My Files folder.
   - Owner-controlled file -> Group target -> initiate the governed Share flow.

   Shared Files is never treated as a physical move destination.
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentDragDrop";
    const UPLOADS_API_NAME = "SolomonWorkspaceDocumentUploads";
    const STATUS_API_NAME = "SolomonWorkspaceDocumentStatus";

    const INTERNAL_TRANSFER_TYPE = "application/x-solomon-workspace-resources+json";
    const EXPLORER_SELECTOR = "[data-document-explorer]";
    const FILE_ROW_SELECTOR = ".workspace-document-file[data-document-id]";
    const MOVE_SOURCE_SELECTOR = `${FILE_ROW_SELECTOR}[data-document-can-move='true']:not([data-document-folder='true'])`;
    const GROUP_SHARE_SOURCE_SELECTOR = "[data-document-share-drag-source='true']";
    const FOLDER_ROW_TARGET_SELECTOR = `${FILE_ROW_SELECTOR}[data-document-folder='true'][data-document-drop-folder-target='true']`;
    const PERSONAL_TREE_TARGET_SELECTOR = "[data-workspace-folder-tree-node][data-workspace-folder-tree-scope='personal'][data-document-drop-folder-target='true']";
    const GROUP_SHARE_TARGET_SELECTOR = "[data-document-group-share-drop-target='true']";
    const LIBRARY_DROP_SELECTOR = "[data-document-drop-zone='library'][data-document-drop-target='my_files']";
    const DROP_OVERLAY_SELECTOR = "[data-document-drop-overlay]";
    const INTERACTIVE_SELECTOR = "button, a, input, select, textarea, [role='button'], [contenteditable='true']";
    const FILE_DRAG_TYPES = Object.freeze([
        "files",
        "application/x-moz-file",
        "application/x-moz-file-promise"
    ]);

    let activeTransfer = null;
    let activeTarget = null;
    let initialized = false;

    if (window[API_NAME]) {
        return;
    }

    function cleanText(value) {
        return String(value || "").trim();
    }

    function getUploadsApi() {
        return window[UPLOADS_API_NAME] || null;
    }

    function getStatusApi() {
        return window[STATUS_API_NAME] || null;
    }

    function getDataTransferTypes(event) {
        return Array.from(event?.dataTransfer?.types || [])
            .map(function (value) {
                return cleanText(value).toLowerCase();
            })
            .filter(Boolean);
    }

    function isExternalFileDrag(event) {
        const types = getDataTransferTypes(event);

        if (types.includes(INTERNAL_TRANSFER_TYPE)) {
            return false;
        }

        if (types.some(function (typeName) {
            return FILE_DRAG_TYPES.includes(typeName);
        })) {
            return true;
        }

        return Boolean(event?.dataTransfer?.files?.length);
    }

    function setDropEffect(event, value) {
        if (event?.dataTransfer) {
            event.dataTransfer.dropEffect = value;
        }
    }

    function getExplorer(node) {
        return node?.closest?.(EXPLORER_SELECTOR) || null;
    }

    function getRowName(row) {
        return cleanText(
            row?.getAttribute("data-document-name") ||
            row?.getAttribute("data-workspace-object-name") ||
            row?.querySelector?.(".workspace-document-file-identity strong")?.textContent ||
            row?.querySelector?.("strong")?.textContent ||
            "File"
        );
    }

    function getSelectedMoveRows(sourceRow) {
        const explorer = getExplorer(sourceRow);

        if (!explorer || !sourceRow?.matches?.(MOVE_SOURCE_SELECTOR)) {
            return [];
        }

        if (sourceRow.getAttribute("data-document-selected") !== "true") {
            return [sourceRow];
        }

        const selectedRows = Array.from(
            explorer.querySelectorAll(`${FILE_ROW_SELECTOR}[data-document-selected='true']`)
        );

        if (!selectedRows.length) {
            return [sourceRow];
        }

        const movableRows = selectedRows.filter(function (row) {
            return row.matches(MOVE_SOURCE_SELECTOR);
        });

        if (movableRows.length !== selectedRows.length) {
            return [];
        }

        return movableRows;
    }

    function buildMoveTransfer(sourceRow) {
        const rows = getSelectedMoveRows(sourceRow);

        if (!rows.length) {
            return null;
        }

        return {
            source: "documents",
            resources: rows.map(function (row) {
                return {
                    documentId: cleanText(row.getAttribute("data-document-id")),
                    name: getRowName(row),
                    canMove: row.getAttribute("data-document-can-move") === "true",
                    canShare: row.getAttribute("data-document-can-share") === "true"
                };
            }),
            sourceElements: rows,
            sourceExplorer: getExplorer(sourceRow)
        };
    }

    function buildGroupShareTransfer(source) {
        const documentId = cleanText(
            source?.getAttribute("data-document-drag-document-id") ||
            source?.getAttribute("data-document-id")
        );

        if (!documentId) {
            return null;
        }

        return {
            source: "group_files",
            resources: [{
                documentId: documentId,
                fileId: cleanText(source.getAttribute("data-document-drag-file-id")),
                name: cleanText(source.getAttribute("data-document-drag-name")) || getRowName(source),
                canMove: false,
                canShare: source.getAttribute("data-document-drag-can-share") === "true"
            }],
            sourceElements: [source],
            sourceExplorer: null
        };
    }

    function serializeTransfer(transfer) {
        return JSON.stringify({
            source: transfer?.source || "",
            resources: Array.isArray(transfer?.resources) ? transfer.resources : []
        });
    }

    function setSourceDragging(transfer, dragging) {
        (transfer?.sourceElements || []).forEach(function (element) {
            element.classList.toggle("is-document-drag-source", Boolean(dragging));
            element.setAttribute("aria-grabbed", dragging ? "true" : "false");
        });
    }

    function handleDragStart(event) {
        const target = event.target instanceof Element ? event.target : null;

        if (!target || target.closest(INTERACTIVE_SELECTOR)) {
            return;
        }

        const moveSource = target.closest(MOVE_SOURCE_SELECTOR);
        const shareSource = target.closest(GROUP_SHARE_SOURCE_SELECTOR);
        const transfer = moveSource
            ? buildMoveTransfer(moveSource)
            : shareSource
                ? buildGroupShareTransfer(shareSource)
                : null;

        if (!transfer || !transfer.resources.length || !event.dataTransfer) {
            event.preventDefault();
            return;
        }

        activeTransfer = transfer;
        setSourceDragging(transfer, true);

        event.dataTransfer.effectAllowed = "copyMove";
        event.dataTransfer.setData(INTERNAL_TRANSFER_TYPE, serializeTransfer(transfer));
        event.dataTransfer.setData(
            "text/plain",
            transfer.resources.map(function (resource) {
                return resource.name || resource.documentId;
            }).join("\n")
        );
    }

    function getTargetLabel(target, fallback) {
        return cleanText(
            target?.getAttribute("data-document-drop-label") ||
            target?.getAttribute("data-document-group-name") ||
            target?.querySelector?.(".workspace-folder-tree-link span:last-child")?.textContent ||
            target?.querySelector?.(".workspace-document-file-identity strong")?.textContent ||
            fallback
        );
    }

    function resolveFolderTarget(target) {
        const folderRow = target?.closest?.(FOLDER_ROW_TARGET_SELECTOR);

        if (folderRow) {
            return {
                kind: "folder",
                element: folderRow,
                folderId: cleanText(
                    folderRow.getAttribute("data-workspace-folder-id") ||
                    folderRow.getAttribute("data-folder-id") ||
                    folderRow.getAttribute("data-document-id")
                ),
                label: getTargetLabel(folderRow, "folder")
            };
        }

        const treeNode = target?.closest?.(PERSONAL_TREE_TARGET_SELECTOR);

        if (treeNode) {
            return {
                kind: "folder",
                element: treeNode,
                folderId: cleanText(treeNode.getAttribute("data-workspace-folder-id")),
                label: getTargetLabel(treeNode, "My Files")
            };
        }

        return null;
    }

    function resolveGroupTarget(target) {
        const groupTarget = target?.closest?.(GROUP_SHARE_TARGET_SELECTOR);

        if (!groupTarget) {
            return null;
        }

        const groupId = cleanText(
            groupTarget.getAttribute("data-document-group-id") ||
            groupTarget.getAttribute("data-people-group-id")
        );

        if (!groupId) {
            return null;
        }

        return {
            kind: "group",
            element: groupTarget,
            groupId: groupId,
            label: getTargetLabel(groupTarget, "Group")
        };
    }

    function resolveLibraryTarget(target) {
        const library = target?.closest?.(LIBRARY_DROP_SELECTOR);

        if (!library) {
            return null;
        }

        const explorer = getExplorer(library);

        if (
            !explorer ||
            cleanText(explorer.getAttribute("data-workspace-section")).toLowerCase() !== "files" ||
            cleanText(explorer.getAttribute("data-workspace-view")).toLowerCase() !== "files"
        ) {
            return null;
        }

        return {
            kind: "library",
            element: library,
            explorer: explorer,
            folderId: cleanText(explorer.getAttribute("data-workspace-current-folder-id")),
            label: cleanText(library.getAttribute("data-document-drop-label")) || "My Files"
        };
    }

    function isCurrentFolderMoveTarget(target) {
        if (!target || target.kind !== "folder" || activeTransfer?.source !== "documents") {
            return false;
        }

        const explorer = activeTransfer?.sourceExplorer;

        if (!explorer) {
            return false;
        }

        const currentFolderId = cleanText(
            explorer.getAttribute("data-workspace-current-folder-id")
        );

        return currentFolderId === cleanText(target.folderId);
    }

    function resolveDropTarget(event, externalFileDrag) {
        const target = event.target instanceof Element ? event.target : null;

        if (!target) {
            return null;
        }

        const groupTarget = resolveGroupTarget(target);
        if (!externalFileDrag && groupTarget) {
            const resources = activeTransfer?.resources || [];
            if (resources.length && resources.every(function (resource) {
                return resource.canShare === true;
            })) {
                return groupTarget;
            }
            return null;
        }

        const folderTarget = resolveFolderTarget(target);
        if (folderTarget) {
            if (!externalFileDrag && isCurrentFolderMoveTarget(folderTarget)) {
                return null;
            }
            return folderTarget;
        }

        if (externalFileDrag) {
            return resolveLibraryTarget(target);
        }

        return null;
    }

    function clearTargetState() {
        if (activeTarget?.element) {
            activeTarget.element.classList.remove(
                "is-document-drop-target",
                "is-document-drop-target--move",
                "is-document-drop-target--upload",
                "is-document-drop-target--share"
            );
            activeTarget.element.removeAttribute("data-document-drop-action-label");
            activeTarget.element
                .querySelector?.(".workspace-document-table-cell:first-child")
                ?.removeAttribute("data-document-drop-action-label");
            activeTarget.element
                .querySelector?.(":scope > .workspace-folder-tree-row")
                ?.removeAttribute("data-document-drop-action-label");
        }

        document.querySelectorAll(`${EXPLORER_SELECTOR}[data-document-drag-state]`).forEach(function (explorer) {
            explorer.removeAttribute("data-document-drag-state");
            const overlay = explorer.querySelector(DROP_OVERLAY_SELECTOR);
            if (overlay) {
                overlay.hidden = true;
                overlay.setAttribute("aria-hidden", "true");
            }
        });

        activeTarget = null;
    }

    function getOverlay(explorer) {
        return explorer?.querySelector?.(DROP_OVERLAY_SELECTOR) || null;
    }

    function setOverlayCopy(explorer, options) {
        const overlay = getOverlay(explorer);

        if (!overlay) {
            return;
        }

        const icon = overlay.querySelector(".workspace-document-drop-icon");
        const kicker = overlay.querySelector(".workspace-kicker");
        const title = overlay.querySelector(".workspace-document-drop-copy strong");
        const message = overlay.querySelector(".workspace-document-drop-copy span");

        if (icon) {
            icon.textContent = options.icon || "drive_folder_upload";
        }
        if (kicker) {
            kicker.textContent = options.kicker || "Upload";
        }
        if (title) {
            title.textContent = options.title || "Drop files here";
        }
        if (message) {
            message.textContent = options.message || "Solomon will verify the operation before changing state.";
        }
    }

    function showLibraryOverlay(target) {
        const explorer = target?.explorer;
        const overlay = getOverlay(explorer);

        if (!explorer || !overlay) {
            return;
        }

        setOverlayCopy(explorer, {
            icon: "drive_folder_upload",
            kicker: "Upload",
            title: `Drop files to upload to ${target.label}`,
            message: "Files are stored in the selected My Files location."
        });
        explorer.setAttribute("data-document-drag-state", "active");
        overlay.hidden = false;
        overlay.setAttribute("aria-hidden", "false");
    }

    function activateTarget(target, action) {
        if (!target?.element) {
            clearTargetState();
            return;
        }

        if (activeTarget?.element !== target.element) {
            clearTargetState();
        }

        activeTarget = target;

        if (target.kind === "library" && action === "upload") {
            showLibraryOverlay(target);
            return;
        }

        target.element.classList.add("is-document-drop-target");
        target.element.classList.add(`is-document-drop-target--${action}`);
        const actionLabel = action === "share"
            ? `Share with ${target.label}`
            : action === "upload"
                ? `Upload to ${target.label}`
                : `Move to ${target.label}`;

        target.element.setAttribute("data-document-drop-action-label", actionLabel);
        target.element
            .querySelector?.(".workspace-document-table-cell:first-child")
            ?.setAttribute("data-document-drop-action-label", actionLabel);
        target.element
            .querySelector?.(":scope > .workspace-folder-tree-row")
            ?.setAttribute("data-document-drop-action-label", actionLabel);
    }

    function preventBrowserFileNavigation(event) {
        if (!isExternalFileDrag(event)) {
            return;
        }

        event.preventDefault();

        if (!event.target?.closest?.(EXPLORER_SELECTOR)) {
            setDropEffect(event, "none");
        }
    }

    function handleDragOver(event) {
        const externalFileDrag = isExternalFileDrag(event);

        if (!externalFileDrag && !activeTransfer) {
            return;
        }

        const target = resolveDropTarget(event, externalFileDrag);

        event.preventDefault();

        if (!target) {
            setDropEffect(event, "none");
            clearTargetState();
            return;
        }

        const action = externalFileDrag
            ? "upload"
            : target.kind === "group"
                ? "share"
                : "move";

        setDropEffect(event, action === "move" ? "move" : "copy");
        activateTarget(target, action);
    }

    function status(explorer, variant, message) {
        const Status = getStatusApi();

        if (!Status?.show || !explorer) {
            return;
        }

        Status.show(explorer, {
            action: "drag_drop",
            variant: variant,
            message: message,
            durationMs: variant === "success" ? 2800 : undefined,
            force: true
        });
    }

    async function postJson(url, body) {
        const response = await fetch(url, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify(body)
        });
        const payload = await response.json().catch(function () {
            return {};
        });

        if (!response.ok || payload.ok === false) {
            throw new Error(payload.user_output || payload.error || "The operation could not be completed.");
        }

        return payload;
    }

    function getMoveEndpoint(explorer) {
        return cleanText(
            explorer?.getAttribute("data-workspace-document-move-endpoint") ||
            "/uploads/me/move"
        );
    }

    function requestExplorerRefresh(explorer, payload) {
        document.dispatchEvent(
            new CustomEvent("solomon:workspace-documents-refresh-requested", {
                detail: {
                    source: "drag_drop_move",
                    explorer: explorer,
                    payload: payload
                }
            })
        );
    }

    async function performMove(target, transfer) {
        const explorer = transfer?.sourceExplorer;
        const documentIds = (transfer?.resources || [])
            .map(function (resource) {
                return cleanText(resource.documentId);
            })
            .filter(Boolean);

        if (!explorer || !documentIds.length) {
            return;
        }

        try {
            const payload = await postJson(getMoveEndpoint(explorer), {
                document_ids: documentIds,
                destination_folder_id: target.folderId || ""
            });
            const movedCount = Number(payload.moved_count || documentIds.length);
            status(
                explorer,
                "success",
                movedCount === 1
                    ? `Moved file to ${target.label}.`
                    : `Moved ${movedCount} files to ${target.label}.`
            );

            if (explorer.getAttribute("data-search-results-surface") === "true") {
                window.setTimeout(function () {
                    window.location.reload();
                }, 120);
                return;
            }

            requestExplorerRefresh(explorer, payload);
        } catch (error) {
            status(explorer, "error", error.message || "The selected files could not be moved.");
        }
    }

    function performUpload(target, event) {
        const files = Array.from(event.dataTransfer?.files || []).filter(Boolean);
        const explorer = target.explorer || getExplorer(target.element);
        const Uploads = getUploadsApi();

        if (!files.length || !explorer || !Uploads?.queueFiles) {
            return;
        }

        Uploads.queueFiles(explorer, files, {
            parentFolderId: target.folderId || ""
        });
    }

    function performGroupShare(target, transfer) {
        const resources = Array.isArray(transfer?.resources) ? transfer.resources : [];

        if (!resources.length || !target?.element) {
            return;
        }

        target.element.dispatchEvent(
            new CustomEvent("solomon:workspace-group-share-drop-requested", {
                bubbles: true,
                detail: {
                    groupId: target.groupId,
                    groupName: target.label,
                    resources: resources
                }
            })
        );
    }

    function handleDrop(event) {
        const externalFileDrag = isExternalFileDrag(event);

        if (!externalFileDrag && !activeTransfer) {
            return;
        }

        const target = resolveDropTarget(event, externalFileDrag) || activeTarget;

        event.preventDefault();
        event.stopPropagation();

        if (!target) {
            setDropEffect(event, "none");
            clearTargetState();
            return;
        }

        const transfer = activeTransfer;
        clearTargetState();

        if (externalFileDrag) {
            performUpload(target, event);
            return;
        }

        if (target.kind === "group") {
            performGroupShare(target, transfer);
            return;
        }

        performMove(target, transfer);
    }

    function handleDragEnd() {
        setSourceDragging(activeTransfer, false);
        activeTransfer = null;
        clearTargetState();
    }

    function initialize() {
        if (initialized) {
            return;
        }

        initialized = true;
        document.addEventListener("dragstart", handleDragStart, true);
        document.addEventListener("dragover", handleDragOver, true);
        document.addEventListener("drop", handleDrop, true);
        document.addEventListener("dragend", handleDragEnd, true);
        document.addEventListener("dragleave", function (event) {
            if (!event.relatedTarget) {
                clearTargetState();
            }
        }, true);
        document.addEventListener("dragover", preventBrowserFileNavigation, true);
    }

    window[API_NAME] = Object.freeze({
        initialize: initialize,
        internalTransferType: INTERNAL_TRANSFER_TYPE
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initialize, { once: true });
    } else {
        initialize();
    }
}());
