/* ==========================================================================
   FILE: webui/static/js/app.ui.core.js
   DIRECTORY: webui/static/js/
   Solomon Workspace — UI Core
   ========================================================================== */

(function () {

/* ---------------------------------------------------------------------------
   NAMESPACE SAFETY
--------------------------------------------------------------------------- */
window.Solomon = window.Solomon || {};
window.Solomon.ui = window.Solomon.ui || {};

const ui = window.Solomon.ui;

/* ---------------------------------------------------------------------------
   ELEMENT REFERENCES
--------------------------------------------------------------------------- */
ui.portalRoot = document.getElementById("portal-root");
ui.form = document.getElementById("taskForm");
ui.conversation = document.getElementById("conversation-region");

ui.taskInput = document.getElementById("taskInput");
ui.runButton = document.getElementById("runButton");

ui.showUploadBtn = document.getElementById("showUpload");
ui.fileInput = document.getElementById("fileInput");
ui.uploadedFileList = document.getElementById("uploadedFileList");
ui.attachmentsRegion = document.getElementById("attachments-region");

ui.scrollToBottomBtn = document.getElementById("scrollToBottom");
ui.attachmentBadge = document.getElementById("attachmentBadge");

/* ---------------------------------------------------------------------------
   SERVER STATE
--------------------------------------------------------------------------- */
ui.serverUploadedFiles = ui.serverUploadedFiles || [];
window.serverUploadedFiles = ui.serverUploadedFiles;

/* ---------------------------------------------------------------------------
   WORKSPACE STATE
--------------------------------------------------------------------------- */
ui.userScrolledUp = false;
ui.portalActivated = false;
ui.thinkingMsg = null;
ui.thinkingInterval = null;
ui.thinkingStep = 0;

/* ---------------------------------------------------------------------------
   LEGACY GREETING CONTRACT — DISABLED
--------------------------------------------------------------------------- */
ui.scheduleInitialGreeting = function () {
    return;
};

ui.cancelInitialGreeting = function () {
    ui.activatePortal?.();
};

/* ---------------------------------------------------------------------------
   UPLOAD RECORD HELPERS
--------------------------------------------------------------------------- */
function cleanValue(value) {
    return String(value || "").trim();
}

function normalizeUploadRecord(file) {
    const originalName = cleanValue(
        file?.original_name ||
        file?.filename ||
        file?.name
    );

    const randomName = cleanValue(
        file?.random_name ||
        file?.stored_name ||
        file?.storage_name
    );

    const documentId = cleanValue(
        file?.document_id ||
        file?.upload_id ||
        file?.file_id ||
        randomName
    );

    return {
        ...file,
        document_id: documentId,
        upload_id: cleanValue(file?.upload_id || documentId),
        file_id: cleanValue(file?.file_id || documentId),
        original_name: originalName,
        filename: cleanValue(file?.filename || originalName),
        random_name: randomName
    };
}

function applyUploadDataset(li, file) {
    li.dataset.documentId = file.document_id || "";
    li.dataset.uploadId = file.upload_id || "";
    li.dataset.fileId = file.file_id || "";
    li.dataset.originalName = file.original_name || "";
    li.dataset.filename = file.filename || "";
    li.dataset.randomName = file.random_name || "";
}

/* ---------------------------------------------------------------------------
   BADGE HELPER
--------------------------------------------------------------------------- */
ui.updateAttachmentBadge = function () {
    if (!ui.attachmentBadge) return;

    const count = ui.serverUploadedFiles.length;

    if (!count) {
        ui.attachmentBadge.classList.add("d-none");
        ui.attachmentBadge.textContent = "";
        return;
    }

    ui.attachmentBadge.classList.remove("d-none");
    ui.attachmentBadge.textContent = String(count);
};

/* ---------------------------------------------------------------------------
   TIME FORMATTER
--------------------------------------------------------------------------- */
ui.formatTimestamp = function (date = new Date()) {
    try {
        return date.toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric",
            hour: "numeric",
            minute: "2-digit"
        });
    } catch {
        return "";
    }
};

/* ---------------------------------------------------------------------------
   SCROLL HELPERS
--------------------------------------------------------------------------- */
ui.isNearBottom = function () {
    if (!ui.conversation) return true;

    const tolerance = 120;
    return (
        ui.conversation.scrollHeight -
        ui.conversation.scrollTop -
        ui.conversation.clientHeight
    ) <= tolerance;
};

ui.maybeAutoScroll = function () {
    if (!ui.conversation) return;

    if (!ui.userScrolledUp || ui.isNearBottom()) {
        ui.conversation.scrollTo({
            top: ui.conversation.scrollHeight,
            behavior: "smooth"
        });
    }

    ui.updateScrollButtonVisibility?.();
};

/* ---------------------------------------------------------------------------
   WORKSPACE ACTIVATION
--------------------------------------------------------------------------- */
ui.activatePortal = function () {
    if (ui.portalActivated) return;
    if (!ui.portalRoot) return;

    ui.portalActivated = true;
    ui.portalRoot.classList.remove("empty");
    ui.portalRoot.classList.add("active");
};

/* ---------------------------------------------------------------------------
   ATTACHMENTS
--------------------------------------------------------------------------- */
ui.refreshActiveUploads = async function () {
    if (!ui.uploadedFileList) return;

    try {
        const res = await fetch("/uploads/active", {
            credentials: "same-origin"
        });

        const data = await res.json();
        const docs = data?.docs || data?.files || [];

        ui.serverUploadedFiles.length = 0;
        docs.map(normalizeUploadRecord).forEach(d => ui.serverUploadedFiles.push(d));

        ui.renderUploadedFiles?.();
        ui.updateAttachmentBadge?.();

        if (window.SolomonState?.updateRunButtonAvailability) {
            window.SolomonState.updateRunButtonAvailability();
        }

    } catch (err) {
        console.error("[UI] Failed to refresh uploads", err);
    }
};

ui.deleteUpload = async function (randomName) {
    if (!randomName) return;

    try {
        await fetch(`/uploads/active/${encodeURIComponent(randomName)}`, {
            method: "DELETE",
            credentials: "same-origin"
        });

        await ui.refreshActiveUploads();
    } catch (err) {
        console.error("[UI] Delete failed", err);
    }
};

ui.renderUploadedFiles = function () {
    if (!ui.uploadedFileList || !ui.attachmentsRegion) return;

    ui.uploadedFileList.innerHTML = "";

    if (!ui.serverUploadedFiles.length) {
        ui.attachmentsRegion.classList.add("empty");
        ui.attachmentsRegion.classList.add("d-none");
        return;
    }

    ui.attachmentsRegion.classList.remove("empty");
    ui.attachmentsRegion.classList.remove("d-none");

    ui.serverUploadedFiles.forEach(file => {
        const normalizedFile = normalizeUploadRecord(file);
        const li = document.createElement("li");

        li.className = "file-row";
        applyUploadDataset(li, normalizedFile);

        const nameSpan = document.createElement("span");
        nameSpan.className = "file-name";
        nameSpan.textContent = normalizedFile.original_name || "uploaded file";

        const deleteButton = document.createElement("button");
        deleteButton.type = "button";
        deleteButton.className = "file-delete-btn";
        deleteButton.title = "Remove document";
        deleteButton.setAttribute("aria-label", "Remove document");
        deleteButton.innerHTML = `<span class="icon" aria-hidden="true">close</span>`;

        deleteButton.addEventListener("click", () => {
            ui.deleteUpload(normalizedFile.random_name);
        });

        li.appendChild(nameSpan);
        li.appendChild(deleteButton);
        ui.uploadedFileList.appendChild(li);
    });
};

/* ---------------------------------------------------------------------------
   FILE PICKER
--------------------------------------------------------------------------- */
function hideNativeFileInput() {
    if (!ui.fileInput) return;

    ui.fileInput.hidden = true;
    ui.fileInput.tabIndex = -1;
    ui.fileInput.setAttribute("aria-hidden", "true");
}

function wireUploadControls() {
    if (!ui.showUploadBtn || !ui.fileInput) return;

    ui.showUploadBtn.addEventListener("click", () => {
        ui.fileInput.click();
    });

    ui.fileInput.addEventListener("change", async () => {
        if (!ui.fileInput.files.length) return;

        const files = Array.from(ui.fileInput.files);

        try {
            for (const file of files) {
                const formData = new FormData();
                formData.append("file", file);

                await fetch("/uploads", {
                    method: "POST",
                    body: formData,
                    credentials: "same-origin"
                });
            }

            await ui.refreshActiveUploads();
        } catch (err) {
            console.error("[UI] Upload failed", err);
        } finally {
            ui.fileInput.value = "";
        }
    });
}

/* ---------------------------------------------------------------------------
   BOOTSTRAP
--------------------------------------------------------------------------- */
document.addEventListener("DOMContentLoaded", () => {
    try {
        hideNativeFileInput();
        wireUploadControls();

        ui.activatePortal?.();
        ui.refreshActiveUploads?.();

        if (window.SolomonState?.updateRunButtonAvailability) {
            window.SolomonState.updateRunButtonAvailability();
        }

        console.log("[UI] workspace ui core bootstrap complete");
    } catch (err) {
        console.warn("[UI] bootstrap error", err);
    }
});

})();