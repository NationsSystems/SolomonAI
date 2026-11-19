/* -------------------------------------------------------------------
   FILE: workspace_document_uploads.js
   DIRECTORY: webui/static/js/command_center/
   Solomon Documents upload input, validation, progress,
   and workspace folder creation transport
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentUploads";
    const STATUS_API_NAME = "SolomonWorkspaceDocumentStatus";

    const UPLOAD_INPUT_SELECTOR = "input[data-document-upload-input]";
    const UPLOAD_TRIGGER_SELECTOR = "[data-document-upload-placeholder], [data-document-upload-trigger]";
    const FOLDER_CREATE_TRIGGER_SELECTOR = "[data-workspace-folder-create-trigger]";
    const UPLOAD_SUCCESS_VISIBLE_MS = 3200;
    const FOLDER_CREATE_SUCCESS_VISIBLE_MS = 2600;
    const WORKSPACE_FOLDER_MAX_NAME_LENGTH = 120;

    const ACCEPTED_UPLOAD_EXTENSIONS = Object.freeze([
        ".pdf",
        ".doc",
        ".docx",
        ".txt",
        ".csv",
        ".xlsx",
        ".xls",
        ".png",
        ".jpg",
        ".jpeg"
    ]);

    const ACCEPTED_UPLOAD_TYPES = ACCEPTED_UPLOAD_EXTENSIONS.join(",");

    let activeFolderCreateDialog = null;


    if (window[API_NAME]) {
        return;
    }

    const Status = window[STATUS_API_NAME];

    if (!Status) {
        console.error("[DOCUMENT_UPLOADS] Missing workspace_document_status.js.");
        return;
    }

    function getUploadOptions(explorer, overrides) {
        return Object.assign(
            {},
            explorer?.__solomonDocumentUploadOptions || {},
            overrides || {}
        );
    }

    function setUploadOptions(explorer, options) {
        if (!explorer) {
            return {};
        }

        explorer.__solomonDocumentUploadOptions = getUploadOptions(explorer, options);
        return explorer.__solomonDocumentUploadOptions;
    }

    function resolveUploadEndpoint(explorer, options) {
        const cleanOptions = getUploadOptions(explorer, options);

        if (typeof cleanOptions.getEndpoint === "function") {
            return String(cleanOptions.getEndpoint(explorer) || "").trim();
        }

        return String(cleanOptions.endpoint || "").trim();
    }

    function resolveFormFieldName(options) {
        return String(options?.formFieldName || "files").trim() || "files";
    }

    function uploadFormData(url, formData, onProgress) {
        return new Promise(function (resolve, reject) {
            const request = new XMLHttpRequest();

            request.open("POST", url, true);
            request.withCredentials = true;
            request.setRequestHeader("X-Requested-With", "XMLHttpRequest");

            request.upload.addEventListener("progress", function (event) {
                if (!event.lengthComputable || typeof onProgress !== "function") {
                    return;
                }

                onProgress(Math.round((event.loaded / event.total) * 100));
            });

            request.addEventListener("load", function () {
                const contentType = String(request.getResponseHeader("content-type") || "").toLowerCase();

                if (!contentType.includes("application/json")) {
                    reject(new Error("The server returned an invalid document response."));
                    return;
                }

                let payload = null;

                try {
                    payload = JSON.parse(request.responseText || "{}");
                } catch (error) {
                    reject(new Error("The server returned unreadable upload status."));
                    return;
                }

                if (request.status < 200 || request.status >= 300 || payload.ok === false) {
                    reject(new Error(payload.user_output || payload.error || "Document upload failed."));
                    return;
                }

                resolve(payload);
            });

            request.addEventListener("error", function () {
                reject(new Error("The upload connection failed before Solomon could store the file."));
            });

            request.addEventListener("abort", function () {
                reject(new Error("The upload was cancelled before Solomon could store the file."));
            });

            request.send(formData);
        });
    }

    function getUploadFileCount(files) {
        return Array.from(files || []).length;
    }

    function getUploadItemLabel(files) {
        const fileCount = getUploadFileCount(files);

        if (fileCount === 1) {
            return "1 item";
        }

        return `${fileCount} items`;
    }

    function getUploadCompleteMessage(files) {
        const fileCount = getUploadFileCount(files);

        if (fileCount === 1) {
            return "Upload complete.";
        }

        return `${fileCount} uploads complete.`;
    }

    function getUploadFailedMessage(message) {
        const cleanMessage = String(message || "").trim();

        if (!cleanMessage) {
            return "Upload failed.";
        }

        if (cleanMessage.length > 92) {
            return "Upload failed.";
        }

        return `Upload failed. ${cleanMessage}`;
    }

    function getUploadExtensionFromFile(file) {
        const fileName = String(file?.name || "").trim();
        const dotIndex = fileName.lastIndexOf(".");

        if (dotIndex < 0) {
            return "";
        }

        return fileName.slice(dotIndex).toLowerCase();
    }

    function isAcceptedUploadFile(file) {
        const extension = getUploadExtensionFromFile(file);

        return ACCEPTED_UPLOAD_EXTENSIONS.includes(extension);
    }

    function getAcceptedUploadTypeLabel() {
        return "Use PDF, Word, text, CSV, spreadsheet, PNG, or JPG.";
    }

    function getRejectedUploadMessage(files) {
        const rejectedFiles = Array.from(files || []).filter(function (file) {
            return !isAcceptedUploadFile(file);
        });

        if (!rejectedFiles.length) {
            return "";
        }

        if (rejectedFiles.length === 1) {
            return `Unsupported file type. ${getAcceptedUploadTypeLabel()}`;
        }

        return `Some files are unsupported. ${getAcceptedUploadTypeLabel()}`;
    }

    function validateFiles(explorer, files) {
        const fileList = Array.from(files || []).filter(Boolean);

        if (!fileList.length) {
            return [];
        }

        const rejectedMessage = getRejectedUploadMessage(fileList);

        if (rejectedMessage) {
            Status.show(explorer, {
                action: "upload_rejected",
                variant: "error",
                message: rejectedMessage
            });

            return [];
        }

        return fileList;
    }

    function setUploadStatus(explorer, options) {
        const state = String(options?.state || "idle").trim() || "idle";

        if (state === "idle") {
            Status.dismiss();
            return;
        }

        if (state === "uploading") {
            return;
        }

        if (state === "success") {
            Status.show(explorer, {
                action: "upload",
                variant: "success",
                message: getUploadCompleteMessage(options?.files),
                durationMs: UPLOAD_SUCCESS_VISIBLE_MS,
                force: true
            });
            return;
        }

        if (state === "error") {
            Status.show(explorer, {
                action: "upload",
                variant: "error",
                message: getUploadFailedMessage(options?.message)
            });
        }
    }

    function createStatusController(explorer, files) {
        let completed = false;
        let latestProgress = 0;

        return {
            updateProgress: function (percent) {
                latestProgress = Math.max(0, Math.min(100, Number(percent || 0)));
            },

            complete: function () {
                completed = true;

                setUploadStatus(explorer, {
                    state: "success",
                    files,
                    progress: latestProgress || 100
                });
            },

            fail: function (message) {
                completed = true;

                setUploadStatus(explorer, {
                    state: "error",
                    title: "Upload failed",
                    message: message || "The upload could not be completed.",
                    progress: latestProgress || 100
                });
            },

            isComplete: function () {
                return completed;
            }
        };
    }

    function getCurrentWorkspaceFolderId(explorer) {
        return String(
            explorer?.getAttribute("data-workspace-current-folder-id") ||
            explorer?.getAttribute("data-current-folder-id") ||
            ""
        ).trim();
    }

    function appendWorkspaceLocationFields(explorer, formData, options) {
        const hasExplicitParent = Object.prototype.hasOwnProperty.call(
            options || {},
            "parentFolderId"
        );
        const parentFolderId = hasExplicitParent
            ? String(options?.parentFolderId || "").trim()
            : getCurrentWorkspaceFolderId(explorer);

        if (!parentFolderId) {
            return;
        }

        formData.append("parent_folder_id", parentFolderId);
    }

    function buildFormData(explorer, files, options) {
        const formData = new FormData();
        const formFieldName = resolveFormFieldName(options);

        Array.from(files || []).forEach(function (file) {
            formData.append(formFieldName, file);
        });

        appendWorkspaceLocationFields(explorer, formData, options);

        return formData;
    }

    async function uploadFiles(explorer, files, options) {
        const cleanOptions = getUploadOptions(explorer, options);
        const endpoint = resolveUploadEndpoint(explorer, cleanOptions);
        const uploadList = Array.from(files || []).filter(Boolean);

        if (!endpoint || !uploadList.length) {
            return null;
        }

        const uploadStatus = createStatusController(explorer, uploadList);
        const formData = buildFormData(explorer, uploadList, cleanOptions);

        if (typeof cleanOptions.beforeUpload === "function") {
            cleanOptions.beforeUpload(explorer, uploadList);
        }

        try {
            const payload = await uploadFormData(endpoint, formData, function (percent) {
                uploadStatus.updateProgress(percent);
            });

            uploadStatus.complete();

            if (typeof cleanOptions.afterUpload === "function") {
                await cleanOptions.afterUpload(explorer, payload, uploadList);
            }

            return payload;
        } catch (error) {
            uploadStatus.fail(error.message);

            if (typeof cleanOptions.onUploadError === "function") {
                cleanOptions.onUploadError(explorer, error, uploadList);
            }

            return null;
        }
    }

    function queueFiles(explorer, files, options) {
        const cleanOptions = getUploadOptions(explorer, options);
        const uploadList = validateFiles(explorer, files);

        if (!uploadList.length) {
            return null;
        }

        if (typeof cleanOptions.beforeQueue === "function") {
            cleanOptions.beforeQueue(explorer, uploadList);
        }

        return uploadFiles(explorer, uploadList, cleanOptions);
    }

    function prepareUploadInput(input) {
        input.hidden = false;
        input.removeAttribute("hidden");
        input.setAttribute("aria-hidden", "true");
        input.setAttribute("tabindex", "-1");
        input.style.border = "0";
        input.style.clip = "rect(0 0 0 0)";
        input.style.clipPath = "inset(50%)";
        input.style.height = "1px";
        input.style.left = "-10000px";
        input.style.margin = "0";
        input.style.opacity = "0";
        input.style.overflow = "hidden";
        input.style.padding = "0";
        input.style.pointerEvents = "none";
        input.style.position = "fixed";
        input.style.top = "0";
        input.style.width = "1px";
        input.style.zIndex = "-1";
    }

    function getUploadInput(explorer, options) {
        let input = explorer.querySelector(UPLOAD_INPUT_SELECTOR);

        setUploadOptions(explorer, options);

        if (input) {
            input.accept = ACCEPTED_UPLOAD_TYPES;
            input.multiple = true;
            prepareUploadInput(input);
            return input;
        }

        input = document.createElement("input");
        input.type = "file";
        input.multiple = true;
        input.accept = ACCEPTED_UPLOAD_TYPES;
        input.setAttribute("data-document-upload-input", "true");
        prepareUploadInput(input);

        input.addEventListener("click", function (event) {
            event.stopPropagation();
        });

        input.addEventListener("change", function () {
            queueFiles(explorer, input.files);
            input.value = "";
        });

        explorer.appendChild(input);
        return input;
    }

    function openPicker(explorer, options) {
        const input = getUploadInput(explorer, options);

        input.value = "";
        input.click();
    }

    function isDisabledUploadTrigger(trigger) {
        return Boolean(
            !trigger ||
            trigger.disabled ||
            trigger.getAttribute("aria-disabled") === "true"
        );
    }

    function handleUploadTriggerClick(explorer, event) {
        const trigger = event?.target?.closest?.(UPLOAD_TRIGGER_SELECTOR);

        if (!trigger || !explorer?.contains(trigger) || isDisabledUploadTrigger(trigger)) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        openPicker(explorer);
    }

    function getDocumentRefreshButton(explorer) {
        return explorer?.querySelector?.("[data-document-refresh]") || null;
    }

    function getFolderCreateEndpoint(explorer, trigger) {
        return String(
            trigger?.getAttribute("data-workspace-folder-create-endpoint") ||
            explorer?.getAttribute("data-workspace-folder-create-endpoint") ||
            explorer?.getAttribute("data-workspace-folders-endpoint") ||
            ""
        ).trim();
    }

    function normalizeFolderName(value) {
        return String(value || "").trim().split(/\s+/).join(" ");
    }

    function getFolderNameValidationMessage(folderName) {
        const cleanName = normalizeFolderName(folderName);

        if (!cleanName) {
            return "Folder name is required.";
        }

        if (cleanName.length > WORKSPACE_FOLDER_MAX_NAME_LENGTH) {
            return `Folder name must be ${WORKSPACE_FOLDER_MAX_NAME_LENGTH} characters or fewer.`;
        }

        if (cleanName === "." || cleanName === "..") {
            return "Folder name is reserved.";
        }

        if (cleanName.includes("/") || cleanName.includes("\\")) {
            return "Folder name cannot contain slashes.";
        }

        for (const character of cleanName) {
            if (character.charCodeAt(0) < 32) {
                return "Folder name contains unsupported control characters.";
            }
        }

        return "";
    }

    function setFolderCreateStatus(explorer, options) {
        const state = String(options?.state || "").trim().toLowerCase();

        if (state === "success") {
            Status.show(explorer, {
                action: "folder_create",
                variant: "success",
                message: options?.message || "Folder created.",
                durationMs: FOLDER_CREATE_SUCCESS_VISIBLE_MS,
                force: true
            });
            return;
        }

        if (state === "error") {
            Status.show(explorer, {
                action: "folder_create",
                variant: "error",
                message: options?.message || "Folder could not be created."
            });
        }
    }

    async function postFolderCreate(endpoint, payload) {
        const response = await fetch(endpoint, {
            method: "POST",
            credentials: "same-origin",
            headers: {
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify(payload)
        });

        const contentType = String(response.headers.get("content-type") || "").toLowerCase();

        if (!contentType.includes("application/json")) {
            throw new Error("The server returned an invalid folder response.");
        }

        const responsePayload = await response.json();

        if (!response.ok || responsePayload.ok === false) {
            throw new Error(responsePayload.user_output || responsePayload.error || "Folder could not be created.");
        }

        return responsePayload;
    }

    function closeDocumentNewMenu(trigger) {
        const menuShell = trigger?.closest?.("[data-document-new-menu]");
        const menuPanel = menuShell?.querySelector?.("[data-document-new-menu-panel]");
        const menuTrigger = menuShell?.querySelector?.("[data-document-new-menu-trigger]");

        if (menuPanel) {
            menuPanel.hidden = true;
            menuPanel.setAttribute("aria-hidden", "true");
        }

        if (menuTrigger) {
            menuTrigger.setAttribute("aria-expanded", "false");
        }
    }

    function requestDocumentListRefresh(explorer, payload) {
        const refreshButton = getDocumentRefreshButton(explorer);

        explorer?.dispatchEvent?.(
            new CustomEvent("solomon:workspace-folder-created", {
                bubbles: true,
                detail: {
                    payload
                }
            })
        );

        document.dispatchEvent(
            new CustomEvent("solomon:workspace-documents-refresh-requested", {
                bubbles: true,
                detail: {
                    source: "folder_create",
                    payload
                }
            })
        );

        if (
            refreshButton &&
            !refreshButton.disabled &&
            refreshButton.getAttribute("aria-disabled") !== "true"
        ) {
            refreshButton.click();
        }
    }

    async function createWorkspaceFolder(explorer, trigger, folderName) {
        const cleanName = normalizeFolderName(folderName);
        const validationMessage = getFolderNameValidationMessage(cleanName);
        const endpoint = getFolderCreateEndpoint(explorer, trigger);
        const parentFolderId = getCurrentWorkspaceFolderId(explorer);

        if (validationMessage) {
            setFolderCreateStatus(explorer, {
                state: "error",
                message: validationMessage
            });
            return null;
        }

        if (!endpoint) {
            setFolderCreateStatus(explorer, {
                state: "error",
                message: "Folder creation is not available in this workspace."
            });
            return null;
        }

        try {
            const createPayload = {
                name: cleanName
            };

            if (parentFolderId) {
                createPayload.parent_folder_id = parentFolderId;
            }

            const payload = await postFolderCreate(endpoint, createPayload);

            setFolderCreateStatus(explorer, {
                state: "success",
                message: "Folder created."
            });
            requestDocumentListRefresh(explorer, payload);

            return payload;
        } catch (error) {
            setFolderCreateStatus(explorer, {
                state: "error",
                message: error.message
            });

            return null;
        }
    }

    function createFolderDialogElement() {
        const dialog = document.createElement("dialog");
        const form = document.createElement("form");
        const header = document.createElement("header");
        const title = document.createElement("h2");
        const description = document.createElement("p");
        const label = document.createElement("label");
        const input = document.createElement("input");
        const actions = document.createElement("div");
        const cancelButton = document.createElement("button");
        const submitButton = document.createElement("button");
        const titleId = "workspaceFolderCreateDialogTitle";
        const inputId = "workspaceFolderCreateInput";

        dialog.className = "workspace-document-folder-dialog";
        dialog.setAttribute("data-workspace-folder-create-dialog", "");
        dialog.setAttribute("aria-labelledby", titleId);

        form.method = "dialog";
        form.className = "workspace-document-folder-form";
        form.setAttribute("data-workspace-folder-create-form", "");

        header.className = "workspace-document-folder-dialog-header";

        title.id = titleId;
        title.textContent = "New folder";

        description.textContent = "Folders organize your workspace. File access stays controlled by the server.";

        label.setAttribute("for", inputId);
        label.textContent = "Folder name";

        input.id = inputId;
        input.name = "name";
        input.type = "text";
        input.required = true;
        input.maxLength = WORKSPACE_FOLDER_MAX_NAME_LENGTH;
        input.autocomplete = "off";
        input.setAttribute("data-workspace-folder-create-input", "");

        actions.className = "workspace-document-folder-dialog-actions";

        cancelButton.type = "button";
        cancelButton.value = "cancel";
        cancelButton.textContent = "Cancel";
        cancelButton.setAttribute("data-workspace-folder-create-cancel", "");

        submitButton.type = "submit";
        submitButton.value = "create";
        submitButton.textContent = "Create";
        submitButton.setAttribute("data-workspace-folder-create-submit", "");

        header.append(title, description);
        actions.append(cancelButton, submitButton);
        form.append(header, label, input, actions);
        dialog.appendChild(form);

        cancelButton.addEventListener("click", function () {
            dialog.close("cancel");
        });

        form.addEventListener("submit", async function (event) {
            event.preventDefault();

            const context = dialog.__solomonWorkspaceFolderContext || {};
            const explorer = context.explorer || null;
            const trigger = context.trigger || null;
            const cleanName = normalizeFolderName(input.value);
            const submit = form.querySelector("[data-workspace-folder-create-submit]");

            if (!cleanName) {
                setFolderCreateStatus(explorer, {
                    state: "error",
                    message: "Folder name is required."
                });
                input.focus();
                return;
            }

            if (submit) {
                submit.disabled = true;
                submit.setAttribute("aria-disabled", "true");
            }

            try {
                const payload = await createWorkspaceFolder(
                    explorer,
                    trigger,
                    cleanName
                );

                if (payload) {
                    input.value = "";
                    dialog.close("created");
                }
            } finally {
                if (submit) {
                    submit.disabled = false;
                    submit.setAttribute("aria-disabled", "false");
                }
            }
        });

        return dialog;
    }

    function getFolderCreateDialog() {
        if (activeFolderCreateDialog?.isConnected) {
            return activeFolderCreateDialog;
        }

        activeFolderCreateDialog = document.querySelector("[data-workspace-folder-create-dialog]");

        if (activeFolderCreateDialog) {
            return activeFolderCreateDialog;
        }

        activeFolderCreateDialog = createFolderDialogElement();
        document.body.appendChild(activeFolderCreateDialog);

        return activeFolderCreateDialog;
    }

    async function openFolderCreateDialog(explorer, trigger) {
        closeDocumentNewMenu(trigger);

        if (!("HTMLDialogElement" in window) || typeof HTMLDialogElement.prototype.showModal !== "function") {
            const folderName = window.prompt("Folder name");

            if (folderName === null) {
                return null;
            }

            return createWorkspaceFolder(
                explorer,
                trigger,
                folderName
            );
        }

        const dialog = getFolderCreateDialog();
        const input = dialog.querySelector("[data-workspace-folder-create-input]");

        dialog.__solomonWorkspaceFolderContext = {
            explorer,
            trigger
        };

        if (input) {
            input.value = "";
        }

        if (!dialog.open) {
            dialog.showModal();
        }

        window.setTimeout(function () {
            input?.focus();
        }, 0);

        return dialog;
    }

    function isDisabledFolderCreateTrigger(trigger) {
        return Boolean(
            !trigger ||
            trigger.disabled ||
            trigger.getAttribute("aria-disabled") === "true"
        );
    }

    function handleFolderCreateTriggerClick(explorer, event) {
        const trigger = event?.target?.closest?.(FOLDER_CREATE_TRIGGER_SELECTOR);

        if (!trigger || !explorer?.contains(trigger) || isDisabledFolderCreateTrigger(trigger)) {
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        event.stopImmediatePropagation();

        if (
            !isMyFilesSection(explorer) ||
            !isFilesWorkspaceView(explorer) ||
            isReaderWorkspaceView(explorer)
        ) {
            setFolderCreateStatus(explorer, {
                state: "error",
                message: "Folders can be created from My Files."
            });
            return;
        }

        openFolderCreateDialog(explorer, trigger);
    }

    function bindFolderCreateTriggers(explorer) {
        if (!explorer) {
            return;
        }

        if (explorer.getAttribute("data-workspace-folder-create-click-bound") === "true") {
            return;
        }

        explorer.setAttribute("data-workspace-folder-create-click-bound", "true");

        explorer.addEventListener("click", function (event) {
            handleFolderCreateTriggerClick(explorer, event);
        }, true);
    }

    function bindUploadTriggers(explorer, options) {
        if (!explorer) {
            return;
        }

        setUploadOptions(explorer, options);

        if (explorer.getAttribute("data-document-upload-click-bound") === "true") {
            return;
        }

        explorer.setAttribute("data-document-upload-click-bound", "true");

        explorer.addEventListener("click", function (event) {
            handleUploadTriggerClick(explorer, event);
        }, true);
    }

    function bind(explorer, options) {
        bindUploadTriggers(explorer, options);
        bindFolderCreateTriggers(explorer);
        return explorer || null;
    }

    window[API_NAME] = Object.freeze({
        acceptedUploadExtensions: ACCEPTED_UPLOAD_EXTENSIONS,
        acceptedUploadTypes: ACCEPTED_UPLOAD_TYPES,
        setUploadOptions,
        getUploadInput,
        openPicker,
        queueFiles,
        uploadFiles,
        validateFiles,
        createWorkspaceFolder,
        openFolderCreateDialog,
        bind,
        bindUploadTriggers,
        bindFolderCreateTriggers
    });
})();