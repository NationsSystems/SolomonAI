/* -------------------------------------------------------------------
   FILE: workspace_document_reader_print.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentReaderPrint";

    const SHELL_SELECTOR = "[data-reader-controller]";
    const TEXT_CARD_SELECTOR = "[data-reader-text-card]";
    const TEXT_BODY_SELECTOR = "[data-reader-text-body]";
    const SUMMARY_BODY_SELECTOR = "[data-reader-summary-body]";
    const SUMMARY_PROVENANCE_SELECTOR = "[data-reader-summary-provenance]";
    const IMAGE_TARGET_SELECTOR = "[data-reader-image-target]";

    const PRINT_URL_ATTRIBUTE = "data-reader-print-url";
    const PRINT_PREVIEW_ATTRIBUTE = "data-reader-print-preview";
    const PRINT_IMAGE_ATTRIBUTE = "data-reader-print-image";
    const PRINT_IMAGE_URL_ATTRIBUTE = "data-reader-print-image-url";
    const PRINT_SPREADSHEET_ATTRIBUTE = "data-reader-print-spreadsheet";
    const PRINT_SUMMARY_ATTRIBUTE = "data-reader-print-summary";
    const PRINT_FRAME_ID = "solomonReaderPrintFrame";
    const PRINT_PREVIEW_FRAME_ID = "solomonReaderPreviewPrintFrame";
    const PRINT_IMAGE_FRAME_ID = "solomonReaderImagePrintFrame";
    const PRINT_SPREADSHEET_FRAME_ID = "solomonReaderSpreadsheetPrintFrame";
    const PRINT_SUMMARY_FRAME_ID = "solomonReaderSummaryPrintFrame";
    const PRINT_CLEANUP_DELAY_MS = 60000;
    const PRINT_LOAD_DELAY_MS = 350;
    const PRINT_PREVIEW_DELAY_MS = 120;
    const PRINT_IMAGE_DELAY_MS = 160;
    const PRINT_SPREADSHEET_DELAY_MS = 120;

    function getTextCard(shell) {
        return shell?.querySelector(TEXT_CARD_SELECTOR) || null;
    }

    function getTextBody(shell) {
        return shell?.querySelector(TEXT_BODY_SELECTOR) || null;
    }

    function getImagePreview(shell) {
        return shell?.querySelector(IMAGE_TARGET_SELECTOR) || null;
    }

    function getActiveSheet(shell) {
        const currentSheet = Number(shell?.getAttribute("data-reader-current-sheet") || 1);

        return (
            shell?.querySelector(`[data-reader-sheet="${CSS.escape(String(currentSheet))}"]`) ||
            shell?.querySelector("[data-reader-sheet]") ||
            null
        );
    }

    function getActiveSheetFrame(shell) {
        return getActiveSheet(shell)?.querySelector("[data-reader-spreadsheet-frame]") || null;
    }

    function getActiveSpreadsheetTable(shell) {
        return getActiveSheet(shell)?.querySelector("[data-reader-spreadsheet-table]") || null;
    }

    function getActiveSpreadsheetFooter(shell) {
        return getActiveSheet(shell)?.querySelector(".document-reader-text-footer") || null;
    }

    function getSheetName(sheet, fallback) {
        const name = String(sheet?.getAttribute("data-reader-sheet-name") || "").trim();

        return name || `Sheet ${fallback || 1}`;
    }

    function getActiveSheetName(shell) {
        const currentSheet = Number(shell?.getAttribute("data-reader-current-sheet") || 1);
        const activeSheet = getActiveSheet(shell);

        return getSheetName(activeSheet, currentSheet);
    }

    function getPrintUrl(control) {
        return String(control?.getAttribute(PRINT_URL_ATTRIBUTE) || "").trim();
    }

    function getPrintImageUrl(control, shell) {
        const attributeUrl = String(control?.getAttribute(PRINT_IMAGE_URL_ATTRIBUTE) || "").trim();
        const previewUrl = String(getImagePreview(shell)?.getAttribute("src") || "").trim();

        return attributeUrl || previewUrl;
    }

    function isPreviewPrintControl(control) {
        return String(control?.getAttribute(PRINT_PREVIEW_ATTRIBUTE) || "").trim().toLowerCase() === "true";
    }

    function isImagePrintControl(control) {
        return String(control?.getAttribute(PRINT_IMAGE_ATTRIBUTE) || "").trim().toLowerCase() === "true";
    }

    function isSpreadsheetPrintControl(control) {
        return String(control?.getAttribute(PRINT_SPREADSHEET_ATTRIBUTE) || "").trim().toLowerCase() === "true";
    }

    function isSummaryPrintControl(control) {
        return String(control?.getAttribute(PRINT_SUMMARY_ATTRIBUTE) || "").trim().toLowerCase() === "true";
    }

    function removeFrameById(frameId) {
        const existingFrame = document.getElementById(frameId);

        if (existingFrame) {
            existingFrame.remove();
        }
    }

    function createHiddenPrintFrame(frameId, title) {
        const frame = document.createElement("iframe");

        frame.id = frameId;
        frame.title = title;
        frame.setAttribute("aria-hidden", "true");
        frame.style.border = "0";
        frame.style.height = "1px";
        frame.style.left = "-10000px";
        frame.style.opacity = "0";
        frame.style.position = "fixed";
        frame.style.top = "0";
        frame.style.width = "1px";

        return frame;
    }

    function createOriginalPrintFrame(printUrl) {
        const frame = createHiddenPrintFrame(PRINT_FRAME_ID, "Print original document");

        frame.src = printUrl;

        return frame;
    }

    function escapeHtml(value) {
        const div = document.createElement("div");

        div.textContent = String(value || "");

        return div.innerHTML;
    }

    function escapeAttribute(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/"/g, "&quot;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;");
    }

    function getReaderTitle(shell) {
        return String(shell?.querySelector(".document-reader-file h1")?.textContent || document.title || "Document preview").trim();
    }

    function getPreviewFooterHtml(shell) {
        const footer = getTextCard(shell)?.querySelector(".document-reader-text-footer");
        const footerText = String(footer?.textContent || "").trim();

        if (!footerText) {
            return "";
        }

        return `<footer class="solomon-print-footer">${escapeHtml(footerText)}</footer>`;
    }

    function getPreviewBodyHtml(shell) {
        const textBody = getTextBody(shell);

        if (!textBody) {
            return "";
        }

        return textBody.innerHTML;
    }

    function getPreviewPrintHtml(shell) {
        const title = getReaderTitle(shell);
        const bodyHtml = getPreviewBodyHtml(shell);

        if (!bodyHtml) {
            return "";
        }

        return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${escapeHtml(title)}</title>
<style>
@page {
    margin: 0.62in;
}

html,
body {
    background: #ffffff;
    color: #0f172a;
    font-family: "Segoe UI", Arial, sans-serif;
    margin: 0;
    min-height: 100%;
    padding: 0;
}

body {
    box-sizing: border-box;
    font-size: 11pt;
    line-height: 1.5;
}

.solomon-print-page {
    box-sizing: border-box;
    margin: 0 auto;
    max-width: 7.35in;
    width: 100%;
}

.solomon-print-title {
    border-bottom: 1px solid #d9dee7;
    color: #0f172a;
    font-size: 13pt;
    font-weight: 700;
    line-height: 1.25;
    margin: 0 0 18pt;
    padding: 0 0 10pt;
}

.document-reader-text-body {
    box-sizing: border-box;
    color: #0f172a;
    width: 100%;
}

.document-reader-text-body p {
    color: #0f172a;
    font-size: 11pt !important;
    line-height: 1.55;
    margin: 0 0 9pt;
    overflow-wrap: break-word;
    white-space: pre-wrap;
    word-break: normal;
}

.solomon-print-footer {
    border-top: 1px solid #d9dee7;
    color: #64748b;
    font-size: 8.5pt;
    line-height: 1.35;
    margin-top: 18pt;
    padding-top: 9pt;
}

@media print {
    html,
    body {
        background: #ffffff !important;
    }

    .solomon-print-page {
        max-width: none;
    }
}
</style>
</head>
<body>
<main class="solomon-print-page">
    <h1 class="solomon-print-title">${escapeHtml(title)}</h1>
    <section class="document-reader-text-body">
        ${bodyHtml}
    </section>
    ${getPreviewFooterHtml(shell)}
</main>
</body>
</html>`;
    }

    function getSummaryPrintHtml(shell) {
        const title = getReaderTitle(shell);
        const summaryBody = shell?.querySelector(SUMMARY_BODY_SELECTOR);
        const provenance = shell?.querySelector(SUMMARY_PROVENANCE_SELECTOR);
        const bodyHtml = summaryBody?.innerHTML || "";
        const provenanceText = String(provenance?.textContent || "").trim();

        if (!bodyHtml) {
            return "";
        }

        return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${escapeHtml(title)} - Summary</title>
<style>
@page {
    margin: 0.62in;
}

html,
body {
    background: #ffffff;
    color: #0f172a;
    font-family: "Segoe UI", Arial, sans-serif;
    margin: 0;
    min-height: 100%;
    padding: 0;
}

body {
    box-sizing: border-box;
    font-size: 11pt;
    line-height: 1.5;
}

.solomon-summary-print-page {
    box-sizing: border-box;
    margin: 0 auto;
    max-width: 7.35in;
    width: 100%;
}

.solomon-summary-print-heading {
    border-bottom: 1px solid #d9dee7;
    margin: 0 0 18pt;
    padding: 0 0 10pt;
}

.solomon-summary-print-heading h1 {
    color: #0f172a;
    font-size: 14pt;
    line-height: 1.25;
    margin: 0 0 4pt;
}

.solomon-summary-print-heading span {
    color: #64748b;
    font-size: 8.5pt;
}

.document-reader-text-body {
    box-sizing: border-box;
    color: #0f172a;
    width: 100%;
}

.document-reader-text-body p {
    color: #0f172a;
    font-size: 11pt !important;
    line-height: 1.55;
    margin: 0 0 9pt;
    overflow-wrap: break-word;
    white-space: pre-wrap;
}

.document-reader-text-body p:first-child {
    font-weight: 700;
}

.solomon-print-footer {
    border-top: 1px solid #d9dee7;
    color: #64748b;
    font-size: 8.5pt;
    line-height: 1.35;
    margin-top: 18pt;
    padding-top: 9pt;
}

@media print {
    html,
    body {
        background: #ffffff !important;
    }

    .solomon-summary-print-page {
        max-width: none;
    }
}
</style>
</head>
<body>
<main class="solomon-summary-print-page">
    <header class="solomon-summary-print-heading">
        <h1>Summary</h1>
        <span>${escapeHtml(title)}</span>
    </header>
    <section class="document-reader-text-body">
        ${bodyHtml}
    </section>
    ${provenanceText ? `<footer class="solomon-print-footer">${escapeHtml(provenanceText)}</footer>` : ""}
</main>
</body>
</html>`;
    }

    function getSpreadsheetPrintHtml(shell) {
        const readerTitle = getReaderTitle(shell);
        const sheetName = getActiveSheetName(shell);
        const table = getActiveSpreadsheetTable(shell);
        const footer = getActiveSpreadsheetFooter(shell);
        const tableHtml = table?.outerHTML || "";
        const footerText = String(footer?.textContent || "").trim();

        if (!tableHtml) {
            return "";
        }

        return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${escapeHtml(readerTitle)} - ${escapeHtml(sheetName)}</title>
<style>
@page {
    margin: 0.35in;
    size: landscape;
}

html,
body {
    background: #ffffff;
    color: #0f172a;
    font-family: "Segoe UI", Arial, sans-serif;
    margin: 0;
    min-height: 100%;
    padding: 0;
}

body {
    box-sizing: border-box;
    font-size: 9pt;
    line-height: 1.35;
}

.solomon-print-spreadsheet-page {
    box-sizing: border-box;
    width: 100%;
}

.solomon-print-spreadsheet-title {
    align-items: baseline;
    border-bottom: 1px solid #d9dee7;
    color: #0f172a;
    display: flex;
    gap: 10pt;
    justify-content: space-between;
    margin: 0 0 10pt;
    padding: 0 0 7pt;
}

.solomon-print-spreadsheet-title h1 {
    font-size: 12pt;
    line-height: 1.2;
    margin: 0;
}

.solomon-print-spreadsheet-title span {
    color: #64748b;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
}

.document-reader-spreadsheet-table {
    border-collapse: collapse;
    color: #0f172a;
    font-size: 8pt;
    line-height: 1.25;
    table-layout: auto;
    width: 100%;
}

.document-reader-spreadsheet-table th,
.document-reader-spreadsheet-table td {
    border: 1px solid #cbd5e1;
    box-sizing: border-box;
    max-width: 180pt;
    padding: 4pt 5pt;
    text-align: left;
    vertical-align: top;
    white-space: normal;
    word-break: break-word;
}

.document-reader-spreadsheet-table thead th {
    background: #f1f5f9;
    color: #334155;
    font-size: 7pt;
    font-weight: 800;
    letter-spacing: 0.04em;
    text-transform: uppercase;
}

.document-reader-spreadsheet-table tbody th {
    background: #f8fafc;
    color: #475569;
    font-size: 7pt;
    font-weight: 800;
    text-align: right;
    width: 30pt;
}

.document-reader-spreadsheet-corner {
    width: 30pt;
}

.solomon-print-footer {
    border-top: 1px solid #d9dee7;
    color: #64748b;
    font-size: 7.5pt;
    line-height: 1.35;
    margin-top: 10pt;
    padding-top: 7pt;
}

@media print {
    html,
    body {
        background: #ffffff !important;
    }

    .document-reader-spreadsheet-table thead {
        display: table-header-group;
    }

    .document-reader-spreadsheet-table tr {
        break-inside: avoid;
        page-break-inside: avoid;
    }
}
</style>
</head>
<body>
<main class="solomon-print-spreadsheet-page">
    <header class="solomon-print-spreadsheet-title">
        <h1>${escapeHtml(readerTitle)}</h1>
        <span>${escapeHtml(sheetName)}</span>
    </header>
    ${tableHtml}
    ${footerText ? `<footer class="solomon-print-footer">${escapeHtml(footerText)}</footer>` : ""}
</main>
</body>
</html>`;
    }

    function getImagePrintHtml(shell, imageUrl) {
        const title = getReaderTitle(shell);

        if (!imageUrl || imageUrl === "#") {
            return "";
        }

        return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>${escapeHtml(title)}</title>
<style>
@page {
    margin: 0.35in;
}

html,
body {
    background: #ffffff;
    margin: 0;
    min-height: 100%;
    padding: 0;
}

body {
    align-items: center;
    box-sizing: border-box;
    display: flex;
    justify-content: center;
    min-height: 100vh;
}

.solomon-print-image-page {
    align-items: center;
    box-sizing: border-box;
    display: flex;
    justify-content: center;
    min-height: calc(100vh - 0.7in);
    width: 100%;
}

.solomon-print-image-page img {
    display: block;
    height: auto;
    max-height: calc(100vh - 0.7in);
    max-width: 100%;
    object-fit: contain;
    width: auto;
}

@media print {
    html,
    body {
        background: #ffffff !important;
        min-height: auto;
    }

    body {
        display: block;
    }

    .solomon-print-image-page {
        min-height: auto;
        page-break-inside: avoid;
    }

    .solomon-print-image-page img {
        max-height: 100%;
        max-width: 100%;
    }
}
</style>
</head>
<body>
<main class="solomon-print-image-page" aria-label="${escapeAttribute(title)}">
    <img src="${escapeAttribute(imageUrl)}" alt="${escapeAttribute(title)}">
</main>
</body>
</html>`;
    }

    function openPrintTargetFallback(printUrl) {
        const cleanPrintUrl = String(printUrl || "").trim();

        if (!cleanPrintUrl || cleanPrintUrl === "#") {
            return;
        }

        const printWindow = window.open(cleanPrintUrl, "_blank", "noopener");

        if (printWindow) {
            try {
                printWindow.opener = null;
                printWindow.focus();
            } catch (_error) {
                // Browser security settings may prevent focus/opener changes.
            }

            return;
        }

        const fallbackAnchor = document.createElement("a");

        fallbackAnchor.href = cleanPrintUrl;
        fallbackAnchor.target = "_blank";
        fallbackAnchor.rel = "noopener";
        fallbackAnchor.style.display = "none";

        document.body.appendChild(fallbackAnchor);
        fallbackAnchor.click();
        fallbackAnchor.remove();
    }

    function printFrame(frame, printUrl) {
        try {
            const frameWindow = frame.contentWindow;

            if (!frameWindow || typeof frameWindow.print !== "function") {
                openPrintTargetFallback(printUrl);
                return;
            }

            frameWindow.focus();
            frameWindow.print();

            window.setTimeout(function () {
                if (frame && frame.parentNode) {
                    frame.remove();
                }
            }, PRINT_CLEANUP_DELAY_MS);
        } catch (_error) {
            openPrintTargetFallback(printUrl);
        }
    }

    function printPreviewFrame(frame) {
        try {
            const frameWindow = frame.contentWindow;

            if (!frameWindow || typeof frameWindow.print !== "function") {
                return;
            }

            frameWindow.focus();
            frameWindow.print();

            window.setTimeout(function () {
                if (frame && frame.parentNode) {
                    frame.remove();
                }
            }, PRINT_CLEANUP_DELAY_MS);
        } catch (_error) {
            if (frame && frame.parentNode) {
                frame.remove();
            }
        }
    }

    function printOriginal(printUrl) {
        if (!printUrl || printUrl === "#") {
            return;
        }

        removeFrameById(PRINT_FRAME_ID);

        const frame = createOriginalPrintFrame(printUrl);

        frame.addEventListener("load", function () {
            window.setTimeout(function () {
                printFrame(frame, printUrl);
            }, PRINT_LOAD_DELAY_MS);
        }, { once: true });

        document.body.appendChild(frame);
    }

    function printPreview(shell) {
        const printHtml = getPreviewPrintHtml(shell);

        if (!printHtml) {
            return;
        }

        removeFrameById(PRINT_PREVIEW_FRAME_ID);

        const frame = createHiddenPrintFrame(PRINT_PREVIEW_FRAME_ID, "Print document preview");

        document.body.appendChild(frame);

        try {
            const frameDocument = frame.contentWindow?.document;

            if (!frameDocument) {
                frame.remove();
                return;
            }

            frameDocument.open();
            frameDocument.write(printHtml);
            frameDocument.close();

            window.setTimeout(function () {
                printPreviewFrame(frame);
            }, PRINT_PREVIEW_DELAY_MS);
        } catch (_error) {
            if (frame && frame.parentNode) {
                frame.remove();
            }
        }
    }

    function printImage(shell, imageUrl) {
        const printHtml = getImagePrintHtml(shell, imageUrl);

        if (!printHtml) {
            return;
        }

        removeFrameById(PRINT_IMAGE_FRAME_ID);

        const frame = createHiddenPrintFrame(PRINT_IMAGE_FRAME_ID, "Print image preview");

        document.body.appendChild(frame);

        try {
            const frameDocument = frame.contentWindow?.document;

            if (!frameDocument) {
                frame.remove();
                return;
            }

            frameDocument.open();
            frameDocument.write(printHtml);
            frameDocument.close();

            const printImage = frameDocument.querySelector("img");

            if (!printImage) {
                window.setTimeout(function () {
                    printPreviewFrame(frame);
                }, PRINT_IMAGE_DELAY_MS);
                return;
            }

            if (printImage.complete && printImage.naturalWidth > 0) {
                window.setTimeout(function () {
                    printPreviewFrame(frame);
                }, PRINT_IMAGE_DELAY_MS);
                return;
            }

            printImage.addEventListener("load", function () {
                window.setTimeout(function () {
                    printPreviewFrame(frame);
                }, PRINT_IMAGE_DELAY_MS);
            }, { once: true });

            printImage.addEventListener("error", function () {
                if (frame && frame.parentNode) {
                    frame.remove();
                }

                openPrintTargetFallback(imageUrl);
            }, { once: true });
        } catch (_error) {
            if (frame && frame.parentNode) {
                frame.remove();
            }

            openPrintTargetFallback(imageUrl);
        }
    }

    function printSummary(shell) {
        const printHtml = getSummaryPrintHtml(shell);

        if (!printHtml) {
            return;
        }

        removeFrameById(PRINT_SUMMARY_FRAME_ID);

        const frame = createHiddenPrintFrame(PRINT_SUMMARY_FRAME_ID, "Print summary");

        document.body.appendChild(frame);

        try {
            const frameDocument = frame.contentWindow?.document;

            if (!frameDocument) {
                frame.remove();
                return;
            }

            frameDocument.open();
            frameDocument.write(printHtml);
            frameDocument.close();

            window.setTimeout(function () {
                printPreviewFrame(frame);
            }, PRINT_PREVIEW_DELAY_MS);
        } catch (_error) {
            if (frame && frame.parentNode) {
                frame.remove();
            }
        }
    }

    function printSpreadsheet(shell) {
        const printHtml = getSpreadsheetPrintHtml(shell);

        if (!printHtml) {
            return;
        }

        removeFrameById(PRINT_SPREADSHEET_FRAME_ID);

        const frame = createHiddenPrintFrame(PRINT_SPREADSHEET_FRAME_ID, "Print spreadsheet preview");

        document.body.appendChild(frame);

        try {
            const frameDocument = frame.contentWindow?.document;

            if (!frameDocument) {
                frame.remove();
                return;
            }

            frameDocument.open();
            frameDocument.write(printHtml);
            frameDocument.close();

            window.setTimeout(function () {
                printPreviewFrame(frame);
            }, PRINT_SPREADSHEET_DELAY_MS);
        } catch (_error) {
            if (frame && frame.parentNode) {
                frame.remove();
            }
        }
    }

    function handlePrintClick(event) {
        const control = event.currentTarget;
        const shell = control?.closest(SHELL_SELECTOR);
        const printUrl = getPrintUrl(control);

        event.preventDefault();
        event.stopPropagation();

        if (isSummaryPrintControl(control)) {
            printSummary(shell);
            return;
        }

        if (isSpreadsheetPrintControl(control)) {
            printSpreadsheet(shell);
            return;
        }

        if (isImagePrintControl(control)) {
            printImage(shell, getPrintImageUrl(control, shell));
            return;
        }

        if (isPreviewPrintControl(control)) {
            printPreview(shell);
            return;
        }

        printOriginal(printUrl);
    }

    window[API_NAME] = Object.freeze({
        handlePrintClick,
        printImage,
        printOriginal,
        printPreview,
        printSpreadsheet,
        printSummary
    });
})();