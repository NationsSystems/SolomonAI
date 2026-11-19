/* -------------------------------------------------------------------
   FILE: workspace_document_reader_controls.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentReaderControls";
    const ReaderPrint = window.SolomonWorkspaceDocumentReaderPrint;

    const SHELL_SELECTOR = "[data-reader-controller]";
    const PAGE_STACK_SELECTOR = "[data-reader-page-stack]";
    const PAGE_CARD_SELECTOR = "[data-reader-page]";
    const PAGE_LINK_SELECTOR = "[data-reader-page-link]";
    const PAGE_IMAGE_SELECTOR = ".document-reader-page-image";
    const PAGE_RAIL_SELECTOR = "[data-reader-page-rail]";
    const IMAGE_TARGET_SELECTOR = "[data-reader-image-target]";
    const IMAGE_FIT_SCREEN_SELECTOR = "[data-reader-image-fit-screen]";
    const IMAGE_ACTUAL_SIZE_SELECTOR = "[data-reader-image-actual-size]";
    const IMAGE_ROTATE_SELECTOR = "[data-reader-image-rotate]";
    const SPREADSHEET_STACK_SELECTOR = "[data-reader-spreadsheet-stack]";
    const SPREADSHEET_SHEET_SELECTOR = "[data-reader-sheet]";
    const SPREADSHEET_SHEET_LINK_SELECTOR = "[data-reader-sheet-link]";
    const SPREADSHEET_SHEET_PREVIOUS_SELECTOR = "[data-reader-sheet-previous]";
    const SPREADSHEET_SHEET_NEXT_SELECTOR = "[data-reader-sheet-next]";
    const SPREADSHEET_SHEET_CONTROL_SELECTOR = "[data-reader-current-sheet-control]";
    const SPREADSHEET_SHEET_LABEL_SELECTOR = "[data-reader-current-sheet-label]";
    const SPREADSHEET_DENSITY_TOGGLE_SELECTOR = "[data-reader-spreadsheet-density-toggle]";
    const SPREADSHEET_DENSITY_LABEL_SELECTOR = "[data-reader-spreadsheet-density-label]";

    const CURRENT_PAGE_SELECTOR = "[data-reader-current-page]";
    const ZOOM_LABEL_SELECTOR = "[data-reader-zoom-label]";
    const FIT_LABEL_SELECTOR = "[data-reader-fit-label]";

    const PAGE_PREVIOUS_SELECTOR = "[data-reader-page-previous]";
    const PAGE_NEXT_SELECTOR = "[data-reader-page-next]";
    const PAGE_CONTROL_SELECTOR = "[data-reader-current-page-control]";
    const ZOOM_CONTROL_SELECTOR = "[data-reader-zoom-control]";
    const ZOOM_OUT_SELECTOR = "[data-reader-zoom-out]";
    const ZOOM_IN_SELECTOR = "[data-reader-zoom-in]";
    const FIT_TOGGLE_SELECTOR = "[data-reader-fit-toggle]";
    const FIT_TOGGLE_ICON_SELECTOR = "[data-reader-fit-toggle-icon]";
    const FIT_TOGGLE_LABEL_SELECTOR = "[data-reader-fit-toggle-label]";
    const FIT_WIDTH_SELECTOR = "[data-reader-fit-width], [data-reader-fit-control]";
    const FIT_PAGE_SELECTOR = "[data-reader-fit-page]";
    const RAIL_TOGGLE_SELECTOR = "[data-reader-rail-toggle]";
    const PRINT_SELECTOR = "[data-reader-print]";
    const DOWNLOAD_SELECTOR = "[data-reader-download]";
    const TEXT_CARD_SELECTOR = "[data-reader-text-card]";
    const TEXT_BODY_SELECTOR = "[data-reader-text-body]";
    const TEXT_SIZE_DECREASE_SELECTOR = "[data-reader-text-size-decrease]";
    const TEXT_SIZE_INCREASE_SELECTOR = "[data-reader-text-size-increase]";
    const TEXT_SIZE_CONTROL_SELECTOR = "[data-reader-text-size-control]";
    const TEXT_SIZE_LABEL_SELECTOR = "[data-reader-text-size-label]";
    const WRAP_TOGGLE_SELECTOR = "[data-reader-wrap-toggle]";
    const WRAP_LABEL_SELECTOR = "[data-reader-wrap-label]";
    const COPY_TEXT_SELECTOR = "[data-reader-copy-text]";
    const COPY_SUMMARY_SELECTOR = "[data-reader-copy-summary]";
    const REPRESENTATION_TARGET_SELECTOR = "[data-reader-representation-target]";
    const REPRESENTATION_TOGGLE_SELECTOR = "[data-reader-representation-toggle]";
    const REPRESENTATION_LABEL_SELECTOR = "[data-reader-representation-label]";
    const DOCUMENT_ONLY_SELECTOR = "[data-reader-document-only]";
    const SUMMARY_ONLY_SELECTOR = "[data-reader-summary-only]";
    const DOCUMENT_CONTENT_SELECTOR = "[data-reader-document-content]";
    const SUMMARY_CONTENT_SELECTOR = "[data-reader-summary-content]";
    const SUMMARY_BODY_SELECTOR = "[data-reader-summary-body]";
    const SUMMARY_STATUS_SELECTOR = "[data-reader-summary-status]";
    const SUMMARY_PROVENANCE_SELECTOR = "[data-reader-summary-provenance]";

    const READER_MODE_CSV = "csv";
    const READER_MODE_DOCX = "docx";
    const READER_MODE_TEXT = "text";
    const READER_MODE_IMAGE = "image";
    const READER_MODE_XLS = "xls";
    const READER_MODE_XLSX = "xlsx";

    const READER_REPRESENTATION_DOCUMENT = "document";
    const READER_REPRESENTATION_SUMMARY = "summary";
    const READER_SUMMARY_STATE_IDLE = "idle";
    const READER_SUMMARY_STATE_LOADING = "loading";
    const READER_SUMMARY_STATE_READY = "ready";
    const READER_SUMMARY_STATE_ERROR = "error";

    const DEFAULT_TEXT_SIZE = 100;
    const MIN_TEXT_SIZE = 80;
    const MAX_TEXT_SIZE = 140;
    const TEXT_SIZE_STEP = 10;

    const TEXT_WRAP_WRAP = "wrap";
    const TEXT_WRAP_NOWRAP = "nowrap";
    const COPY_RESET_DELAY_MS = 1600;

    const SPREADSHEET_DENSITY_COMFORTABLE = "comfortable";
    const SPREADSHEET_DENSITY_COMPACT = "compact";
    const DEFAULT_SHEET = 1;

    const FIT_MODE_WIDTH = "width";
    const FIT_MODE_ZOOM = "zoom";
    const FIT_MODE_SCREEN = "screen";
    const FIT_MODE_ACTUAL = "actual";
    const FIT_TARGET_WIDTH = "width";
    const FIT_TARGET_PAGE = "page";
    const FIT_TARGET_ZOOM = "zoom";
    const FIT_TARGET_SCREEN = "screen";
    const FIT_TARGET_ACTUAL = "actual";

    const RAIL_STATE_OPEN = "open";
    const RAIL_STATE_CLOSED = "closed";

    const DEFAULT_PAGE = 1;
    const DEFAULT_ZOOM = 100;
    const MIN_ZOOM = 35;
    const MAX_ZOOM = 200;
    const ZOOM_LEVELS = Object.freeze([50, 67, 75, 90, 100, 110, 125, 150, 175, 200]);

    const DEFAULT_IMAGE_ROTATION = 0;
    const IMAGE_ROTATION_STEP = 90;
    const IMAGE_ROTATION_FULL_TURN = 360;

    function clampNumber(value, min, max, fallback) {
        const number = Number(value);

        if (!Number.isFinite(number)) {
            return fallback;
        }

        return Math.min(Math.max(number, min), max);
    }

    function getPageCount(shell) {
        const storedPageCount = Number(shell?.getAttribute("data-reader-page-count") || 0);
        const countedPages = shell?.querySelectorAll(PAGE_CARD_SELECTOR).length || 0;
        const pageCount = storedPageCount > 0 ? storedPageCount : countedPages;

        return pageCount > 0 ? pageCount : DEFAULT_PAGE;
    }

    function getPageNumber(card) {
        return clampNumber(
            card?.getAttribute("data-reader-page"),
            DEFAULT_PAGE,
            Number.MAX_SAFE_INTEGER,
            DEFAULT_PAGE
        );
    }

    function getCurrentPage(shell) {
        return clampNumber(
            shell?.getAttribute("data-reader-current-page"),
            DEFAULT_PAGE,
            getPageCount(shell),
            DEFAULT_PAGE
        );
    }

    function getZoom(shell) {
        return clampNumber(
            shell?.getAttribute("data-reader-zoom"),
            MIN_ZOOM,
            MAX_ZOOM,
            DEFAULT_ZOOM
        );
    }

    function getReaderMode(shell) {
        return String(shell?.getAttribute("data-reader-mode") || "").trim().toLowerCase();
    }

    function isDocxReader(shell) {
        return getReaderMode(shell) === READER_MODE_DOCX;
    }

    function isPlainTextReader(shell) {
        return getReaderMode(shell) === READER_MODE_TEXT;
    }

    function isImageReader(shell) {
        return getReaderMode(shell) === READER_MODE_IMAGE;
    }

    function isSpreadsheetReader(shell) {
        const readerMode = getReaderMode(shell);

        return (
            readerMode === READER_MODE_CSV ||
            readerMode === READER_MODE_XLS ||
            readerMode === READER_MODE_XLSX
        );
    }

    function resolveReaderShell(root) {
        if (!root) {
            return document.querySelector(SHELL_SELECTOR);
        }

        if (root.matches && root.matches(SHELL_SELECTOR)) {
            return root;
        }

        return root.querySelector?.(SHELL_SELECTOR) || null;
    }

    function getReaderRepresentation(shell) {
        const representation = String(
            shell?.getAttribute("data-reader-representation") ||
            READER_REPRESENTATION_DOCUMENT
        ).trim().toLowerCase();

        return representation === READER_REPRESENTATION_SUMMARY
            ? READER_REPRESENTATION_SUMMARY
            : READER_REPRESENTATION_DOCUMENT;
    }

    function isSummaryAvailable(shell) {
        return String(
            shell?.getAttribute("data-reader-summary-available") || "false"
        ).trim().toLowerCase() === "true";
    }

    function setNodeVisible(node, visible) {
        if (!node) {
            return;
        }

        node.hidden = !visible;
        node.setAttribute("aria-hidden", visible ? "false" : "true");

        if (visible) {
            node.removeAttribute("hidden");
        }
    }

    function clearNode(node) {
        while (node?.firstChild) {
            node.removeChild(node.firstChild);
        }
    }

    function appendSummaryParagraphs(container, summaryText) {
        const paragraphs = String(summaryText || "")
            .trim()
            .split(/\n\s*\n+/)
            .map(function (text) {
                return String(text || "").trim();
            })
            .filter(Boolean);

        clearNode(container);

        paragraphs.forEach(function (paragraphText) {
            const paragraph = document.createElement("p");
            paragraph.textContent = paragraphText;
            container?.appendChild(paragraph);
        });
    }

    function formatSummaryGeneratedAt(value) {
        const cleanValue = String(value || "").trim();

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

    function setSummaryStatus(shell, message, state) {
        const body = shell?.querySelector(SUMMARY_BODY_SELECTOR);
        const status = shell?.querySelector(SUMMARY_STATUS_SELECTOR);
        const provenance = shell?.querySelector(SUMMARY_PROVENANCE_SELECTOR);
        const cleanMessage = String(message || "").trim();

        shell?.setAttribute(
            "data-reader-summary-state",
            String(state || READER_SUMMARY_STATE_IDLE).trim().toLowerCase()
        );

        if (body && status && !body.contains(status)) {
            clearNode(body);
            body.appendChild(status);
        }

        if (status) {
            status.textContent = cleanMessage;
            setNodeVisible(status, Boolean(cleanMessage));
        }

        setNodeVisible(provenance, false);
    }

    function renderSummaryPayload(shell, payload) {
        const body = shell?.querySelector(SUMMARY_BODY_SELECTOR);
        const provenance = shell?.querySelector(SUMMARY_PROVENANCE_SELECTOR);
        const detailedSummary = String(payload?.detailed_summary || "").trim();
        const responseDocumentId = String(payload?.document_id || "").trim();
        const expectedDocumentId = String(
            shell?.getAttribute("data-reader-document-id") || ""
        ).trim();
        const generatedAt = formatSummaryGeneratedAt(payload?.generated_at);

        if (responseDocumentId && expectedDocumentId && responseDocumentId !== expectedDocumentId) {
            throw new Error("The server returned a summary for a different document.");
        }

        if (
            payload?.ok === false ||
            String(payload?.summary_state || "").trim().toLowerCase() !== "ready" ||
            !detailedSummary
        ) {
            throw new Error("A current saved summary is not available for this file version.");
        }

        appendSummaryParagraphs(body, detailedSummary);
        shell.setAttribute("data-reader-summary-state", READER_SUMMARY_STATE_READY);

        if (provenance) {
            const generatedCopy = generatedAt ? `Generated ${generatedAt}` : "Saved summary";
            provenance.textContent = `${generatedCopy} · Current file version`;
            setNodeVisible(provenance, true);
        }

        shell.__solomonReaderSummaryPayload = payload;
        return payload;
    }

    async function loadReaderSummary(shell) {
        if (!shell || !isSummaryAvailable(shell)) {
            throw new Error("A current saved summary is not available for this file.");
        }

        if (shell.__solomonReaderSummaryPayload) {
            return shell.__solomonReaderSummaryPayload;
        }

        if (shell.__solomonReaderSummaryPromise) {
            return shell.__solomonReaderSummaryPromise;
        }

        const endpoint = String(
            shell.getAttribute("data-reader-summary-endpoint") || ""
        ).trim();

        if (!endpoint) {
            throw new Error("The saved summary endpoint is unavailable.");
        }

        setSummaryStatus(
            shell,
            "Loading the saved summary…",
            READER_SUMMARY_STATE_LOADING
        );

        shell.__solomonReaderSummaryPromise = (async function () {
            const response = await fetch(endpoint, {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    "Accept": "application/json",
                    "X-Requested-With": "XMLHttpRequest"
                }
            });
            const payload = await response.json().catch(function () {
                return {};
            });

            if (!response.ok) {
                throw new Error(
                    payload?.error ||
                    payload?.message ||
                    "The saved summary could not be loaded."
                );
            }

            return renderSummaryPayload(shell, payload);
        })();

        try {
            return await shell.__solomonReaderSummaryPromise;
        } catch (error) {
            setSummaryStatus(
                shell,
                error?.message || "The saved summary could not be loaded.",
                READER_SUMMARY_STATE_ERROR
            );
            throw error;
        } finally {
            shell.__solomonReaderSummaryPromise = null;
        }
    }

    function syncRepresentationControls(shell, representation) {
        const summaryView = representation === READER_REPRESENTATION_SUMMARY;

        shell?.querySelectorAll(REPRESENTATION_TARGET_SELECTOR).forEach(function (control) {
            if (control.matches(REPRESENTATION_TOGGLE_SELECTOR)) {
                const nextRepresentation = summaryView
                    ? READER_REPRESENTATION_DOCUMENT
                    : READER_REPRESENTATION_SUMMARY;
                const nextLabel = summaryView ? "Document" : "Summary";
                const actionLabel = summaryView
                    ? "Show original document"
                    : "Show full summary";
                const title = summaryView ? "View document" : "View summary";
                const label = control.querySelector(REPRESENTATION_LABEL_SELECTOR);

                control.setAttribute(
                    "data-reader-representation-target",
                    nextRepresentation
                );
                control.classList.remove("is-active");
                control.removeAttribute("aria-pressed");
                control.setAttribute("aria-label", actionLabel);
                control.setAttribute("title", title);

                if (label) {
                    label.textContent = nextLabel;
                }

                return;
            }

            const target = String(
                control.getAttribute("data-reader-representation-target") || ""
            ).trim().toLowerCase();
            const active = target === representation;

            control.classList.toggle("is-active", active);
            control.setAttribute("aria-pressed", active ? "true" : "false");
        });

        shell?.querySelectorAll(DOCUMENT_ONLY_SELECTOR).forEach(function (node) {
            setNodeVisible(node, !summaryView);
        });

        shell?.querySelectorAll(SUMMARY_ONLY_SELECTOR).forEach(function (node) {
            setNodeVisible(node, summaryView);
        });

        setNodeVisible(shell?.querySelector(DOCUMENT_CONTENT_SELECTOR), !summaryView);
        setNodeVisible(shell?.querySelector(SUMMARY_CONTENT_SELECTOR), summaryView);
    }

    async function setReaderRepresentation(shell, requestedRepresentation) {
        if (!shell) {
            return false;
        }

        const requested = String(
            requestedRepresentation || READER_REPRESENTATION_DOCUMENT
        ).trim().toLowerCase();
        const representation = (
            requested === READER_REPRESENTATION_SUMMARY &&
            isSummaryAvailable(shell)
        )
            ? READER_REPRESENTATION_SUMMARY
            : READER_REPRESENTATION_DOCUMENT;

        shell.setAttribute("data-reader-representation", representation);
        syncRepresentationControls(shell, representation);

        if (representation === READER_REPRESENTATION_SUMMARY) {
            try {
                await loadReaderSummary(shell);
            } catch (_error) {
                return false;
            }
        }

        return representation === requested;
    }

    async function setRepresentation(root, representation) {
        const shell = resolveReaderShell(root);

        if (!shell) {
            return false;
        }

        return setReaderRepresentation(shell, representation);
    }

    function isTextPreviewReader(shell) {
        return isDocxReader(shell) || isPlainTextReader(shell);
    }

    function getTextSize(shell) {
        return clampNumber(
            shell?.getAttribute("data-reader-text-size"),
            MIN_TEXT_SIZE,
            MAX_TEXT_SIZE,
            DEFAULT_TEXT_SIZE
        );
    }

    function getTextWrap(shell) {
        const wrap = String(shell?.getAttribute("data-reader-text-wrap") || TEXT_WRAP_WRAP).trim().toLowerCase();

        return wrap === TEXT_WRAP_NOWRAP ? TEXT_WRAP_NOWRAP : TEXT_WRAP_WRAP;
    }

    function getTextCard(shell) {
        return shell?.querySelector(TEXT_CARD_SELECTOR) || null;
    }

    function getTextBody(shell) {
        return shell?.querySelector(TEXT_BODY_SELECTOR) || null;
    }

    function getFitTarget(shell) {
        const target = String(shell?.getAttribute("data-reader-fit-target") || "").trim().toLowerCase();
        const mode = String(shell?.getAttribute("data-reader-fit-mode") || "").trim().toLowerCase();

        if (
            target === FIT_TARGET_ACTUAL ||
            target === FIT_TARGET_PAGE ||
            target === FIT_TARGET_SCREEN ||
            target === FIT_TARGET_WIDTH ||
            target === FIT_TARGET_ZOOM
        ) {
            return target;
        }

        if (mode === FIT_MODE_ACTUAL) {
            return FIT_TARGET_ACTUAL;
        }

        if (mode === FIT_MODE_SCREEN) {
            return FIT_TARGET_SCREEN;
        }

        if (mode === FIT_MODE_WIDTH) {
            return FIT_TARGET_WIDTH;
        }

        return FIT_TARGET_ZOOM;
    }

    function getRailState(shell) {
        const state = String(shell?.getAttribute("data-reader-rail-state") || RAIL_STATE_OPEN).trim().toLowerCase();

        return state === RAIL_STATE_CLOSED ? RAIL_STATE_CLOSED : RAIL_STATE_OPEN;
    }

    function getSheetCount(shell) {
        const storedSheetCount = Number(shell?.getAttribute("data-reader-sheet-count") || 0);
        const countedSheets = shell?.querySelectorAll(SPREADSHEET_SHEET_SELECTOR).length || 0;
        const sheetCount = storedSheetCount > 0 ? storedSheetCount : countedSheets;

        return sheetCount > 0 ? sheetCount : DEFAULT_SHEET;
    }

    function getCurrentSheet(shell) {
        return clampNumber(
            shell?.getAttribute("data-reader-current-sheet"),
            DEFAULT_SHEET,
            getSheetCount(shell),
            DEFAULT_SHEET
        );
    }

    function getSheetNumber(sheet) {
        return clampNumber(
            sheet?.getAttribute("data-reader-sheet"),
            DEFAULT_SHEET,
            Number.MAX_SAFE_INTEGER,
            DEFAULT_SHEET
        );
    }

    function getSpreadsheetDensity(shell) {
        const density = String(shell?.getAttribute("data-reader-spreadsheet-density") || SPREADSHEET_DENSITY_COMFORTABLE).trim().toLowerCase();

        return density === SPREADSHEET_DENSITY_COMPACT ? SPREADSHEET_DENSITY_COMPACT : SPREADSHEET_DENSITY_COMFORTABLE;
    }

    function getSheetName(sheet, fallback) {
        const name = String(sheet?.getAttribute("data-reader-sheet-name") || "").trim();

        return name || `Sheet ${fallback || DEFAULT_SHEET}`;
    }

    function getActiveSheet(shell) {
        const currentSheet = getCurrentSheet(shell);

        return (
            shell.querySelector(`[data-reader-sheet="${CSS.escape(String(currentSheet))}"]`) ||
            shell.querySelector(SPREADSHEET_SHEET_SELECTOR)
        );
    }

    function getActiveSheetName(shell) {
        const currentSheet = getCurrentSheet(shell);
        const activeSheet = getActiveSheet(shell);

        return getSheetName(activeSheet, currentSheet);
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

    function getActivePage(shell) {
        const currentPage = getCurrentPage(shell);

        return (
            shell.querySelector(`[data-reader-page="${CSS.escape(String(currentPage))}"]`) ||
            shell.querySelector(PAGE_CARD_SELECTOR)
        );
    }

    function getActiveImage(shell) {
        if (isImageReader(shell)) {
            return shell.querySelector(IMAGE_TARGET_SELECTOR);
        }

        return getActivePage(shell)?.querySelector(PAGE_IMAGE_SELECTOR) || shell.querySelector(PAGE_IMAGE_SELECTOR);
    }

    function getImageRotation(shell) {
        const storedRotation = Number(shell?.getAttribute("data-reader-image-rotation") || DEFAULT_IMAGE_ROTATION);

        if (!Number.isFinite(storedRotation)) {
            return DEFAULT_IMAGE_ROTATION;
        }

        return ((Math.round(storedRotation / IMAGE_ROTATION_STEP) * IMAGE_ROTATION_STEP) % IMAGE_ROTATION_FULL_TURN + IMAGE_ROTATION_FULL_TURN) % IMAGE_ROTATION_FULL_TURN;
    }

    function getImagePreview(shell) {
        return shell?.querySelector(IMAGE_TARGET_SELECTOR) || null;
    }

    function getImageCanvas(shell) {
        return shell?.querySelector(".document-reader-canvas--image") || null;
    }

    function isQuarterTurn(rotation) {
        return Math.abs(rotation % 180) === IMAGE_ROTATION_STEP;
    }

    function setButtonDisabled(button, disabled) {
        if (!button) {
            return;
        }

        button.disabled = Boolean(disabled);
        button.setAttribute("aria-disabled", disabled ? "true" : "false");
    }

    function updatePageControlState(shell, pageNumber) {
        const pageCount = getPageCount(shell);

        setButtonDisabled(shell.querySelector(PAGE_PREVIOUS_SELECTOR), pageNumber <= DEFAULT_PAGE);
        setButtonDisabled(shell.querySelector(PAGE_NEXT_SELECTOR), pageNumber >= pageCount);
    }

    function updateZoomControlState(shell) {
        const zoom = getZoom(shell);

        setButtonDisabled(shell.querySelector(ZOOM_OUT_SELECTOR), zoom <= MIN_ZOOM);
        setButtonDisabled(shell.querySelector(ZOOM_IN_SELECTOR), zoom >= MAX_ZOOM);
    }

    function updateFitControlState(shell) {
        const fitTarget = getFitTarget(shell);
        const fitToggleControl = shell.querySelector(FIT_TOGGLE_SELECTOR);
        const fitWidthControls = shell.querySelectorAll(FIT_WIDTH_SELECTOR);
        const fitPageControl = shell.querySelector(FIT_PAGE_SELECTOR);
        const fitScreenControl = shell.querySelector(IMAGE_FIT_SCREEN_SELECTOR);
        const actualSizeControl = shell.querySelector(IMAGE_ACTUAL_SIZE_SELECTOR);
        const fitLabel = shell.querySelector(FIT_LABEL_SELECTOR);

        if (fitToggleControl) {
            const nextTarget = fitTarget === FIT_TARGET_WIDTH ? FIT_TARGET_PAGE : FIT_TARGET_WIDTH;
            const nextLabel = nextTarget === FIT_TARGET_PAGE ? "Fit page" : "Fit width";
            const nextIcon = nextTarget === FIT_TARGET_PAGE ? "aspect_ratio" : "width";
            const toggleIcon = fitToggleControl.querySelector(FIT_TOGGLE_ICON_SELECTOR);
            const toggleLabel = fitToggleControl.querySelector(FIT_TOGGLE_LABEL_SELECTOR);

            fitToggleControl.setAttribute("aria-label", nextLabel);
            fitToggleControl.setAttribute("title", nextLabel);
            fitToggleControl.setAttribute("data-reader-fit-toggle-target", nextTarget);

            if (toggleIcon) {
                toggleIcon.textContent = nextIcon;
            }

            if (toggleLabel) {
                toggleLabel.textContent = nextLabel;
            }
        }

        fitWidthControls.forEach(function (control) {
            const isWidthControl = control.hasAttribute("data-reader-fit-width") || control.hasAttribute("data-reader-fit-control");
            const isActive = isWidthControl && fitTarget === FIT_TARGET_WIDTH;

            control.classList.toggle("is-active", isActive);
            control.setAttribute("aria-pressed", isActive ? "true" : "false");
        });

        if (fitPageControl) {
            const isActive = fitTarget === FIT_TARGET_PAGE;

            fitPageControl.classList.toggle("is-active", isActive);
            fitPageControl.setAttribute("aria-pressed", isActive ? "true" : "false");
        }

        if (fitScreenControl) {
            const isActive = fitTarget === FIT_TARGET_SCREEN;

            fitScreenControl.classList.toggle("is-active", isActive);
            fitScreenControl.setAttribute("aria-pressed", isActive ? "true" : "false");
        }

        if (actualSizeControl) {
            const isActive = fitTarget === FIT_TARGET_ACTUAL;

            actualSizeControl.classList.toggle("is-active", isActive);
            actualSizeControl.setAttribute("aria-pressed", isActive ? "true" : "false");
        }

        if (fitLabel) {
            if (isImageReader(shell)) {
                fitLabel.textContent = "Fit screen";
            } else if (fitTarget === FIT_TARGET_ACTUAL) {
                fitLabel.textContent = "Actual size";
            } else if (fitTarget === FIT_TARGET_PAGE) {
                fitLabel.textContent = "Fit page";
            } else if (fitTarget === FIT_TARGET_ZOOM) {
                fitLabel.textContent = "Custom zoom";
            } else {
                fitLabel.textContent = "Fit width";
            }
        }
    }

    function updateRailControlState(shell) {
        const rail = shell.querySelector(PAGE_RAIL_SELECTOR);
        const toggle = shell.querySelector(RAIL_TOGGLE_SELECTOR);
        const isOpen = getRailState(shell) === RAIL_STATE_OPEN;

        if (!toggle) {
            return;
        }

        setButtonDisabled(toggle, !rail);
        toggle.classList.toggle("is-active", Boolean(rail && isOpen));
        toggle.setAttribute("aria-pressed", rail && isOpen ? "true" : "false");
        toggle.setAttribute("aria-label", isOpen ? "Hide page thumbnails" : "Show page thumbnails");
        toggle.setAttribute("title", isOpen ? "Hide page thumbnails" : "Show page thumbnails");
    }

    function updateTextSizeControlState(shell) {
        const size = getTextSize(shell);
        const sizeLabel = shell.querySelector(TEXT_SIZE_LABEL_SELECTOR);

        if (sizeLabel) {
            sizeLabel.textContent = `${Math.round(size)}%`;
        }

        setButtonDisabled(shell.querySelector(TEXT_SIZE_DECREASE_SELECTOR), size <= MIN_TEXT_SIZE);
        setButtonDisabled(shell.querySelector(TEXT_SIZE_INCREASE_SELECTOR), size >= MAX_TEXT_SIZE);
    }

    function updateWrapControlState(shell) {
        const wrapToggle = shell.querySelector(WRAP_TOGGLE_SELECTOR);
        const wrapLabel = shell.querySelector(WRAP_LABEL_SELECTOR);
        const isWrapped = getTextWrap(shell) === TEXT_WRAP_WRAP;

        if (!wrapToggle) {
            return;
        }

        wrapToggle.classList.toggle("is-active", isWrapped);
        wrapToggle.setAttribute("aria-pressed", isWrapped ? "true" : "false");
        wrapToggle.setAttribute("aria-label", isWrapped ? "Disable text wrapping" : "Enable text wrapping");
        wrapToggle.setAttribute("title", isWrapped ? "No wrap" : "Wrap text");

        if (wrapLabel) {
            wrapLabel.textContent = isWrapped ? "Wrap" : "No wrap";
        }
    }

    function updateTextControlState(shell) {
        if (!isTextPreviewReader(shell)) {
            return;
        }

        updateTextSizeControlState(shell);
        updateWrapControlState(shell);
    }

    function updateImageControlState(shell) {
        const rotateControl = shell.querySelector(IMAGE_ROTATE_SELECTOR);

        if (!isImageReader(shell)) {
            return;
        }

        if (rotateControl) {
            const rotation = getImageRotation(shell);

            rotateControl.setAttribute("aria-label", `Rotate image view. Current rotation ${rotation} degrees.`);
            rotateControl.setAttribute("title", `Rotate ${rotation}°`);
        }
    }

    function updateSpreadsheetControlState(shell) {
        const currentSheet = getCurrentSheet(shell);
        const sheetCount = getSheetCount(shell);
        const sheetLabel = shell.querySelector(SPREADSHEET_SHEET_LABEL_SELECTOR);
        const densityToggle = shell.querySelector(SPREADSHEET_DENSITY_TOGGLE_SELECTOR);
        const densityLabel = shell.querySelector(SPREADSHEET_DENSITY_LABEL_SELECTOR);
        const density = getSpreadsheetDensity(shell);
        const isComfortable = density === SPREADSHEET_DENSITY_COMFORTABLE;

        if (!isSpreadsheetReader(shell)) {
            return;
        }

        if (sheetLabel) {
            sheetLabel.textContent = getActiveSheetName(shell);
        }

        setButtonDisabled(shell.querySelector(SPREADSHEET_SHEET_PREVIOUS_SELECTOR), currentSheet <= DEFAULT_SHEET);
        setButtonDisabled(shell.querySelector(SPREADSHEET_SHEET_NEXT_SELECTOR), currentSheet >= sheetCount);

        if (densityToggle) {
            densityToggle.classList.toggle("is-active", isComfortable);
            densityToggle.setAttribute("aria-pressed", isComfortable ? "true" : "false");
            densityToggle.setAttribute("aria-label", isComfortable ? "Switch to compact spreadsheet density" : "Switch to comfortable spreadsheet density");
            densityToggle.setAttribute("title", isComfortable ? "Compact density" : "Comfortable density");
        }

        if (densityLabel) {
            densityLabel.textContent = isComfortable ? "Comfortable" : "Compact";
        }
    }

    function setControlText(shell, pageNumber) {
        const pageNode = shell.querySelector(CURRENT_PAGE_SELECTOR);
        const zoomNode = shell.querySelector(ZOOM_LABEL_SELECTOR);
        const zoom = getZoom(shell);

        if (pageNode) {
            pageNode.textContent = String(pageNumber);
        }

        if (zoomNode) {
            zoomNode.textContent = `${Math.round(zoom)}%`;
        }

        updatePageControlState(shell, pageNumber);
        updateZoomControlState(shell);
        updateFitControlState(shell);
        updateRailControlState(shell);
        updateTextControlState(shell);
        updateSpreadsheetControlState(shell);
        updateImageControlState(shell);
    }

    function setActivePage(shell, pageNumber) {
        const safePageNumber = clampNumber(pageNumber, DEFAULT_PAGE, getPageCount(shell), DEFAULT_PAGE);

        shell.setAttribute("data-reader-current-page", String(safePageNumber));

        shell.querySelectorAll(PAGE_LINK_SELECTOR).forEach(function (link) {
            link.classList.toggle(
                "is-active",
                Number(link.getAttribute("data-reader-page-link")) === safePageNumber
            );
        });

        setControlText(shell, safePageNumber);
    }

    function setActiveSheet(shell, sheetNumber) {
        const safeSheetNumber = clampNumber(sheetNumber, DEFAULT_SHEET, getSheetCount(shell), DEFAULT_SHEET);

        shell.setAttribute("data-reader-current-sheet", String(safeSheetNumber));

        shell.querySelectorAll(SPREADSHEET_SHEET_SELECTOR).forEach(function (sheet) {
            sheet.classList.toggle(
                "is-active",
                getSheetNumber(sheet) === safeSheetNumber
            );
        });

        shell.querySelectorAll(SPREADSHEET_SHEET_LINK_SELECTOR).forEach(function (link) {
            link.classList.toggle(
                "is-active",
                Number(link.getAttribute("data-reader-sheet-link")) === safeSheetNumber
            );
        });

        updateSpreadsheetControlState(shell);
    }

    function replaceSheetHash(sheetNumber) {
        if (!window.history || typeof window.history.replaceState !== "function") {
            return;
        }

        window.history.replaceState(null, "", `#reader-sheet-${sheetNumber}`);
    }

    function scrollToSheet(shell, sheetNumber, options) {
        const safeSheetNumber = clampNumber(sheetNumber, DEFAULT_SHEET, getSheetCount(shell), DEFAULT_SHEET);
        const sheet = shell.querySelector(`[data-reader-sheet="${CSS.escape(String(safeSheetNumber))}"]`);

        if (!sheet) {
            return;
        }

        sheet.scrollIntoView({
            behavior: options?.instant ? "auto" : "smooth",
            block: "start",
            inline: "nearest"
        });

        setActiveSheet(shell, safeSheetNumber);

        if (options?.updateHash) {
            replaceSheetHash(safeSheetNumber);
        }
    }

    function scrollToCurrentSheet(shell) {
        scrollToSheet(shell, getCurrentSheet(shell));
    }

    function scrollBySheet(shell, direction) {
        const currentSheet = getCurrentSheet(shell);
        const nextSheet = clampNumber(
            currentSheet + (direction < 0 ? -1 : 1),
            DEFAULT_SHEET,
            getSheetCount(shell),
            currentSheet
        );

        scrollToSheet(shell, nextSheet, { updateHash: true });
    }

    function toggleSpreadsheetDensity(shell) {
        const nextDensity = getSpreadsheetDensity(shell) === SPREADSHEET_DENSITY_COMFORTABLE
            ? SPREADSHEET_DENSITY_COMPACT
            : SPREADSHEET_DENSITY_COMFORTABLE;

        shell.setAttribute("data-reader-spreadsheet-density", nextDensity);
        updateSpreadsheetControlState(shell);

        const activeFrame = getActiveSheetFrame(shell);

        if (activeFrame && typeof activeFrame.focus === "function") {
            activeFrame.focus({ preventScroll: true });
        }
    }

    function clearTextPreviewStyles(shell) {
        const textCard = getTextCard(shell);
        const textBody = getTextBody(shell);

        if (textCard) {
            textCard.style.maxWidth = "";
            textCard.style.transform = "";
            textCard.style.transformOrigin = "";
            textCard.style.width = "";
        }

        if (textBody) {
            textBody.style.removeProperty("--reader-document-zoom");
            textBody.style.removeProperty("--reader-plain-text-scale");
        }
    }

    function applyPlainTextSize(shell) {
        const textBody = getTextBody(shell);
        const scale = getTextSize(shell) / 100;

        if (!textBody) {
            return;
        }

        textBody.style.setProperty("--reader-plain-text-scale", String(scale));

        textBody.querySelectorAll("p").forEach(function (paragraph) {
            paragraph.style.fontSize = `${(0.94 * scale).toFixed(3)}rem`;
        });

        updateTextSizeControlState(shell);
    }

    function applyTextWrap(shell) {
        const textBody = getTextBody(shell);
        const textCard = getTextCard(shell);
        const canvas = shell.querySelector(".document-reader-canvas--text");
        const shouldWrap = getTextWrap(shell) === TEXT_WRAP_WRAP;

        if (!textBody) {
            return;
        }

        shell.setAttribute("data-reader-text-wrap", shouldWrap ? TEXT_WRAP_WRAP : TEXT_WRAP_NOWRAP);

        textBody.querySelectorAll("p").forEach(function (paragraph) {
            paragraph.style.overflowWrap = shouldWrap ? "" : "normal";
            paragraph.style.whiteSpace = shouldWrap ? "" : "pre";
            paragraph.style.wordBreak = shouldWrap ? "" : "normal";
        });

        if (canvas) {
            canvas.style.overflowX = shouldWrap ? "" : "auto";
        }

        if (textCard && isPlainTextReader(shell)) {
            textCard.style.maxWidth = shouldWrap ? "" : "none";
            textCard.style.width = shouldWrap ? "" : "max-content";
        }

        updateWrapControlState(shell);
    }

    function applyTextPreviewState(shell) {
        if (!isTextPreviewReader(shell)) {
            return;
        }

        if (isPlainTextReader(shell)) {
            applyPlainTextSize(shell);
            applyTextWrap(shell);
            return;
        }

        applyDocumentZoom(shell);
    }

    function applyDocumentZoom(shell) {
        const textCard = getTextCard(shell);
        const textBody = getTextBody(shell);
        const zoom = getZoom(shell);
        const scale = zoom / 100;

        if (!textCard) {
            return;
        }

        textCard.style.transformOrigin = "top center";
        textCard.style.transform = scale === 1 ? "" : `scale(${scale})`;
        textCard.style.setProperty("--reader-document-zoom", String(scale));

        if (textBody) {
            textBody.style.setProperty("--reader-document-zoom", String(scale));
        }
    }

    function calculateTextFitPageZoom(shell) {
        const canvas = shell.querySelector(".document-reader-canvas--text");
        const textCard = getTextCard(shell);

        if (!canvas || !textCard) {
            return DEFAULT_ZOOM;
        }

        const canvasRect = canvas.getBoundingClientRect();
        const cardRect = textCard.getBoundingClientRect();
        const availableWidth = Math.max(240, canvasRect.width - 48);
        const availableHeight = Math.max(240, canvasRect.height - 64);
        const cardWidth = Math.max(1, cardRect.width);
        const cardHeight = Math.max(1, cardRect.height);
        const scale = Math.min(availableWidth / cardWidth, availableHeight / cardHeight);

        return clampNumber(Math.round(scale * 100), MIN_ZOOM, MAX_ZOOM, DEFAULT_ZOOM);
    }

    function clearImageWidths(shell) {
        shell.querySelectorAll(PAGE_IMAGE_SELECTOR).forEach(function (image) {
            image.style.width = "";
        });
    }

    function setZoomAttributes(shell, zoom, target) {
        const safeZoom = clampNumber(zoom, MIN_ZOOM, MAX_ZOOM, DEFAULT_ZOOM);
        const cleanTarget = target || FIT_TARGET_ZOOM;

        shell.setAttribute("data-reader-zoom", String(Math.round(safeZoom)));
        shell.setAttribute("data-reader-fit-target", cleanTarget);

        if (cleanTarget === FIT_TARGET_WIDTH) {
            shell.setAttribute("data-reader-fit-mode", FIT_MODE_WIDTH);
        } else if (cleanTarget === FIT_TARGET_SCREEN) {
            shell.setAttribute("data-reader-fit-mode", FIT_MODE_SCREEN);
        } else if (cleanTarget === FIT_TARGET_ACTUAL) {
            shell.setAttribute("data-reader-fit-mode", FIT_MODE_ACTUAL);
        } else {
            shell.setAttribute("data-reader-fit-mode", FIT_MODE_ZOOM);
        }
    }

    function getImageNaturalWidth(image) {
        const naturalWidth = Number(image?.naturalWidth || image?.getAttribute("width") || 0);

        return Number.isFinite(naturalWidth) && naturalWidth > 0 ? naturalWidth : 0;
    }

    function getImageNaturalHeight(image) {
        const naturalHeight = Number(image?.naturalHeight || image?.getAttribute("height") || 0);

        return Number.isFinite(naturalHeight) && naturalHeight > 0 ? naturalHeight : 0;
    }

    function applyFixedZoom(shell) {
        const zoom = getZoom(shell);
        const scale = zoom / 100;

        shell.querySelectorAll(PAGE_IMAGE_SELECTOR).forEach(function (image) {
            const naturalWidth = getImageNaturalWidth(image);

            if (naturalWidth > 0) {
                image.style.width = `${Math.round(naturalWidth * scale)}px`;
            }
        });
    }

    function calculateFitPageZoom(shell) {
        const stack = shell.querySelector(PAGE_STACK_SELECTOR);
        const image = getActiveImage(shell);
        const naturalWidth = getImageNaturalWidth(image);
        const naturalHeight = getImageNaturalHeight(image);

        if (!stack || !image || !naturalWidth || !naturalHeight) {
            return DEFAULT_ZOOM;
        }

        const stackRect = stack.getBoundingClientRect();
        const availableWidth = Math.max(240, stackRect.width - 48);
        const availableHeight = Math.max(240, stackRect.height - 64);
        const scale = Math.min(availableWidth / naturalWidth, availableHeight / naturalHeight);
        const zoom = Math.round(scale * 100);

        return clampNumber(zoom, MIN_ZOOM, MAX_ZOOM, DEFAULT_ZOOM);
    }

    function calculateImageFitScreenZoom(shell) {
        const canvas = getImageCanvas(shell);
        const image = getImagePreview(shell);
        const naturalWidth = getImageNaturalWidth(image);
        const naturalHeight = getImageNaturalHeight(image);
        const rotation = getImageRotation(shell);

        if (!canvas || !image || !naturalWidth || !naturalHeight) {
            return DEFAULT_ZOOM;
        }

        const canvasRect = canvas.getBoundingClientRect();
        const rotated = isQuarterTurn(rotation);
        const renderedWidth = rotated ? naturalHeight : naturalWidth;
        const renderedHeight = rotated ? naturalWidth : naturalHeight;
        const availableWidth = Math.max(240, canvasRect.width - 56);
        const availableHeight = Math.max(240, canvasRect.height - 56);
        const scale = Math.min(availableWidth / renderedWidth, availableHeight / renderedHeight);
        const zoom = Math.round(scale * 100);

        return clampNumber(zoom, MIN_ZOOM, MAX_ZOOM, DEFAULT_ZOOM);
    }

    function applyImagePreviewState(shell) {
        const image = getImagePreview(shell);

        if (!image) {
            return;
        }

        const fitTarget = getFitTarget(shell);
        const rotation = getImageRotation(shell);
        const naturalWidth = getImageNaturalWidth(image);
        const naturalHeight = getImageNaturalHeight(image);
        const zoom = getZoom(shell);
        const scale = zoom / 100;

        image.style.maxWidth = "none";
        image.style.transform = rotation ? `rotate(${rotation}deg)` : "";
        image.style.transformOrigin = "center center";

        if (naturalWidth > 0) {
            image.style.width = `${Math.round(naturalWidth * scale)}px`;
        } else {
            image.style.width = fitTarget === FIT_TARGET_SCREEN ? "100%" : "";
        }

        if (naturalHeight > 0) {
            image.style.height = "auto";
        }

        shell.setAttribute("data-reader-image-rotation", String(rotation));
        updateImageControlState(shell);
    }

    function fitImageScreen(shell) {
        setZoomAttributes(shell, calculateImageFitScreenZoom(shell), FIT_TARGET_SCREEN);
        applyImagePreviewState(shell);
        setControlText(shell, getCurrentPage(shell));
    }

    function showImageActualSize(shell) {
        setZoomAttributes(shell, DEFAULT_ZOOM, FIT_TARGET_ACTUAL);
        applyImagePreviewState(shell);
        setControlText(shell, getCurrentPage(shell));
    }

    function rotateImage(shell) {
        const nextRotation = (getImageRotation(shell) + IMAGE_ROTATION_STEP) % IMAGE_ROTATION_FULL_TURN;

        shell.setAttribute("data-reader-image-rotation", String(nextRotation));

        if (getFitTarget(shell) === FIT_TARGET_SCREEN) {
            fitImageScreen(shell);
            return;
        }

        applyImagePreviewState(shell);
        setControlText(shell, getCurrentPage(shell));
    }

    function applyZoom(shell) {
        const fitTarget = getFitTarget(shell);

        if (isTextPreviewReader(shell)) {
            if (fitTarget === FIT_TARGET_WIDTH) {
                clearTextPreviewStyles(shell);
                setControlText(shell, getCurrentPage(shell));
                applyTextPreviewState(shell);
                return;
            }

            if (fitTarget === FIT_TARGET_PAGE && isDocxReader(shell)) {
                setZoomAttributes(shell, calculateTextFitPageZoom(shell), FIT_TARGET_PAGE);
            }

            applyTextPreviewState(shell);
            setControlText(shell, getCurrentPage(shell));
            return;
        }

        if (isImageReader(shell)) {
            if (fitTarget === FIT_TARGET_SCREEN) {
                setZoomAttributes(shell, calculateImageFitScreenZoom(shell), FIT_TARGET_SCREEN);
            } else if (fitTarget === FIT_TARGET_ACTUAL) {
                setZoomAttributes(shell, DEFAULT_ZOOM, FIT_TARGET_ACTUAL);
            }

            applyImagePreviewState(shell);
            setControlText(shell, getCurrentPage(shell));
            return;
        }

        if (fitTarget === FIT_TARGET_WIDTH) {
            clearImageWidths(shell);
            setControlText(shell, getCurrentPage(shell));
            return;
        }

        if (fitTarget === FIT_TARGET_PAGE) {
            setZoomAttributes(shell, calculateFitPageZoom(shell), FIT_TARGET_PAGE);
        }

        applyFixedZoom(shell);
        setControlText(shell, getCurrentPage(shell));
    }

    function getNextZoomValue(currentZoom, direction) {
        const cleanDirection = direction < 0 ? -1 : 1;
        const sortedLevels = Array.from(ZOOM_LEVELS).sort(function (a, b) {
            return a - b;
        });

        if (cleanDirection > 0) {
            return sortedLevels.find(function (zoom) {
                return zoom > currentZoom;
            }) || sortedLevels[sortedLevels.length - 1];
        }

        return Array.from(sortedLevels).reverse().find(function (zoom) {
            return zoom < currentZoom;
        }) || sortedLevels[0];
    }

    function setZoom(shell, zoom) {
        setZoomAttributes(shell, zoom, FIT_TARGET_ZOOM);
        applyZoom(shell);
    }

    function zoomIn(shell) {
        setZoom(shell, getNextZoomValue(getZoom(shell), 1));
    }

    function zoomOut(shell) {
        setZoom(shell, getNextZoomValue(getZoom(shell), -1));
    }

    function cycleZoom(shell) {
        const currentZoom = getZoom(shell);
        const currentIndex = ZOOM_LEVELS.indexOf(Math.round(currentZoom));
        const nextIndex = currentIndex >= 0
            ? (currentIndex + 1) % ZOOM_LEVELS.length
            : ZOOM_LEVELS.indexOf(DEFAULT_ZOOM);
        const nextZoom = ZOOM_LEVELS[nextIndex >= 0 ? nextIndex : 2];

        setZoom(shell, nextZoom);
    }

    function toggleFitMode(shell) {
        if (getFitTarget(shell) === FIT_TARGET_WIDTH) {
            fitPage(shell);
            return;
        }

        fitWidth(shell);
    }

    function fitWidth(shell) {
        if (isImageReader(shell)) {
            fitImageScreen(shell);
            return;
        }

        setZoomAttributes(shell, DEFAULT_ZOOM, FIT_TARGET_WIDTH);

        if (isTextPreviewReader(shell)) {
            clearTextPreviewStyles(shell);
            applyTextPreviewState(shell);
            setControlText(shell, getCurrentPage(shell));
            return;
        }

        clearImageWidths(shell);
        setControlText(shell, getCurrentPage(shell));
    }

    function fitPage(shell) {
        if (isImageReader(shell)) {
            fitImageScreen(shell);
            return;
        }

        if (isDocxReader(shell)) {
            setZoomAttributes(shell, calculateTextFitPageZoom(shell), FIT_TARGET_PAGE);
            applyZoom(shell);
            return;
        }

        setZoomAttributes(shell, calculateFitPageZoom(shell), FIT_TARGET_PAGE);
        applyZoom(shell);
    }

    function replacePageHash(pageNumber) {
        if (!window.history || typeof window.history.replaceState !== "function") {
            return;
        }

        window.history.replaceState(null, "", `#reader-page-${pageNumber}`);
    }

    function scrollToPage(shell, pageNumber, options) {
        const safePageNumber = clampNumber(pageNumber, DEFAULT_PAGE, getPageCount(shell), DEFAULT_PAGE);
        const page = shell.querySelector(`[data-reader-page="${CSS.escape(String(safePageNumber))}"]`);

        if (!page) {
            return;
        }

        page.scrollIntoView({
            behavior: options?.instant ? "auto" : "smooth",
            block: "start",
            inline: "center"
        });

        setActivePage(shell, safePageNumber);

        if (options?.updateHash) {
            replacePageHash(safePageNumber);
        }
    }

    function scrollToCurrentPage(shell) {
        scrollToPage(shell, getCurrentPage(shell));
    }

    function scrollByPage(shell, direction) {
        const currentPage = getCurrentPage(shell);
        const nextPage = clampNumber(
            currentPage + (direction < 0 ? -1 : 1),
            DEFAULT_PAGE,
            getPageCount(shell),
            currentPage
        );

        scrollToPage(shell, nextPage, { updateHash: true });
    }

    function getPageFromHash() {
        const match = String(window.location.hash || "").match(/^#reader-page-(\d+)$/);

        if (!match) {
            return 0;
        }

        const pageNumber = Number(match[1]);

        return Number.isFinite(pageNumber) && pageNumber > 0 ? pageNumber : 0;
    }

    function getSheetFromHash() {
        const match = String(window.location.hash || "").match(/^#reader-sheet-(\d+)$/);

        if (!match) {
            return 0;
        }

        const sheetNumber = Number(match[1]);

        return Number.isFinite(sheetNumber) && sheetNumber > 0 ? sheetNumber : 0;
    }

    function bindPageObserver(shell) {
        const stack = shell.querySelector(PAGE_STACK_SELECTOR);
        const pages = Array.from(shell.querySelectorAll(PAGE_CARD_SELECTOR));

        if (!stack || !pages.length || shell.__solomonReaderPageObserver) {
            return;
        }

        shell.__solomonReaderPageObserver = new IntersectionObserver(function (entries) {
            const visible = entries
                .filter(function (entry) {
                    return entry.isIntersecting;
                })
                .sort(function (a, b) {
                    return b.intersectionRatio - a.intersectionRatio;
                });

            if (!visible.length) {
                return;
            }

            setActivePage(shell, getPageNumber(visible[0].target));
        }, {
            root: stack,
            threshold: [0.18, 0.32, 0.48, 0.62, 0.78]
        });

        pages.forEach(function (page) {
            shell.__solomonReaderPageObserver.observe(page);
        });
    }

    function bindSheetObserver(shell) {
        const stack = shell.querySelector(SPREADSHEET_STACK_SELECTOR);
        const sheets = Array.from(shell.querySelectorAll(SPREADSHEET_SHEET_SELECTOR));

        if (!stack || !sheets.length || shell.__solomonReaderSheetObserver) {
            return;
        }

        shell.__solomonReaderSheetObserver = new IntersectionObserver(function (entries) {
            const visible = entries
                .filter(function (entry) {
                    return entry.isIntersecting;
                })
                .sort(function (a, b) {
                    return b.intersectionRatio - a.intersectionRatio;
                });

            if (!visible.length) {
                return;
            }

            setActiveSheet(shell, getSheetNumber(visible[0].target));
        }, {
            root: stack,
            threshold: [0.18, 0.34, 0.52, 0.70]
        });

        sheets.forEach(function (sheet) {
            shell.__solomonReaderSheetObserver.observe(sheet);
        });
    }

    function bindImageLoads(shell) {
        shell.querySelectorAll(`${PAGE_IMAGE_SELECTOR}, ${IMAGE_TARGET_SELECTOR}`).forEach(function (image) {
            if (image.complete) {
                applyZoom(shell);
                return;
            }

            image.addEventListener("load", function () {
                applyZoom(shell);
            }, { once: true });
        });
    }

    function isShellVisible(shell) {
        const hiddenParent = shell.closest("[hidden], [aria-hidden='true']");
        const rect = shell.getBoundingClientRect();

        return !hiddenParent && rect.width > 0 && rect.height > 0;
    }

    function toggleRail(shell) {
        const rail = shell.querySelector(PAGE_RAIL_SELECTOR);

        if (!rail) {
            return;
        }

        const nextState = getRailState(shell) === RAIL_STATE_OPEN
            ? RAIL_STATE_CLOSED
            : RAIL_STATE_OPEN;

        shell.setAttribute("data-reader-rail-state", nextState);
        updateRailControlState(shell);

        if (getFitTarget(shell) === FIT_TARGET_PAGE) {
            window.requestAnimationFrame(function () {
                fitPage(shell);
            });
        }
    }

    function handlePrintClick(event) {
        const control = event.currentTarget;
        const shell = control?.closest(SHELL_SELECTOR);
        const isSummaryPrint = String(
            control?.getAttribute("data-reader-print-summary") || ""
        ).trim().toLowerCase() === "true";

        if (isSummaryPrint) {
            event.preventDefault();
            event.stopPropagation();

            if (!ReaderPrint || typeof ReaderPrint.printSummary !== "function") {
                console.warn("[READER_CONTROLS] Reader summary print module is unavailable.");
                return;
            }

            loadReaderSummary(shell).then(function () {
                ReaderPrint.printSummary(shell);
            }).catch(function () {
                // The summary surface already presents the load error to the user.
            });
            return;
        }

        if (ReaderPrint && typeof ReaderPrint.handlePrintClick === "function") {
            ReaderPrint.handlePrintClick(event);
            return;
        }

        event.preventDefault();
        event.stopPropagation();
        console.warn("[READER_CONTROLS] Reader print module is unavailable.");
    }

    function setTextSize(shell, size) {
        const safeSize = clampNumber(size, MIN_TEXT_SIZE, MAX_TEXT_SIZE, DEFAULT_TEXT_SIZE);

        shell.setAttribute("data-reader-text-size", String(Math.round(safeSize)));
        applyPlainTextSize(shell);
    }

    function increaseTextSize(shell) {
        setTextSize(shell, getTextSize(shell) + TEXT_SIZE_STEP);
    }

    function decreaseTextSize(shell) {
        setTextSize(shell, getTextSize(shell) - TEXT_SIZE_STEP);
    }

    function resetTextSize(shell) {
        setTextSize(shell, DEFAULT_TEXT_SIZE);
    }

    function toggleTextWrap(shell) {
        const nextWrap = getTextWrap(shell) === TEXT_WRAP_WRAP
            ? TEXT_WRAP_NOWRAP
            : TEXT_WRAP_WRAP;

        shell.setAttribute("data-reader-text-wrap", nextWrap);
        applyTextWrap(shell);
    }

    function getPreviewText(shell) {
        const textBody = getTextBody(shell);

        return String(textBody?.innerText || "").trim();
    }

    function writeClipboardFallback(textValue) {
        const textArea = document.createElement("textarea");

        textArea.value = textValue;
        textArea.setAttribute("readonly", "true");
        textArea.style.height = "1px";
        textArea.style.left = "-10000px";
        textArea.style.position = "fixed";
        textArea.style.top = "0";
        textArea.style.width = "1px";

        document.body.appendChild(textArea);
        textArea.select();

        try {
            document.execCommand("copy");
        } finally {
            textArea.remove();
        }
    }

    function setCopyControlFeedback(control, copied) {
        if (!control) {
            return;
        }

        const originalTitle = control.getAttribute("data-reader-copy-original-title") || control.getAttribute("title") || "Copy text";
        const nextTitle = copied ? "Copied" : originalTitle;

        control.setAttribute("data-reader-copy-original-title", originalTitle);
        control.setAttribute("title", nextTitle);
        control.setAttribute("aria-label", copied ? "Text copied" : "Copy text preview");

        if (copied) {
            window.setTimeout(function () {
                control.setAttribute("title", originalTitle);
                control.setAttribute("aria-label", "Copy text preview");
            }, COPY_RESET_DELAY_MS);
        }
    }

    function copyPreviewText(shell, control) {
        const previewText = getPreviewText(shell);

        if (!previewText) {
            setCopyControlFeedback(control, false);
            return;
        }

        if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
            navigator.clipboard.writeText(previewText).then(function () {
                setCopyControlFeedback(control, true);
            }).catch(function () {
                writeClipboardFallback(previewText);
                setCopyControlFeedback(control, true);
            });
            return;
        }

        writeClipboardFallback(previewText);
        setCopyControlFeedback(control, true);
    }

    function setSummaryCopyControlFeedback(control, copied) {
        if (!control) {
            return;
        }

        const originalTitle = control.getAttribute("data-reader-copy-original-title") || control.getAttribute("title") || "Copy summary";
        const nextTitle = copied ? "Summary copied" : originalTitle;

        control.setAttribute("data-reader-copy-original-title", originalTitle);
        control.setAttribute("title", nextTitle);
        control.setAttribute("aria-label", copied ? "Summary copied" : "Copy summary");

        if (copied) {
            window.setTimeout(function () {
                control.setAttribute("title", originalTitle);
                control.setAttribute("aria-label", "Copy summary");
            }, COPY_RESET_DELAY_MS);
        }
    }

    async function copySummaryText(shell, control) {
        try {
            const payload = await loadReaderSummary(shell);
            const summaryText = String(payload?.detailed_summary || "").trim();

            if (!summaryText) {
                setSummaryCopyControlFeedback(control, false);
                return;
            }

            if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
                try {
                    await navigator.clipboard.writeText(summaryText);
                } catch (_error) {
                    writeClipboardFallback(summaryText);
                }
            } else {
                writeClipboardFallback(summaryText);
            }

            setSummaryCopyControlFeedback(control, true);
        } catch (_error) {
            setSummaryCopyControlFeedback(control, false);
        }
    }

    function isDisabledDownloadControl(control) {
        return Boolean(
            !control ||
            control.disabled ||
            control.getAttribute("aria-disabled") === "true"
        );
    }

    function isAnchorDownloadControl(control) {
        return Boolean(
            control &&
            control.tagName &&
            control.tagName.toLowerCase() === "a"
        );
    }

    function getDownloadHref(control) {
        const attributeHref = String(control?.getAttribute("href") || "").trim();
        const resolvedHref = String(control?.href || "").trim();

        return attributeHref || resolvedHref;
    }

    function hasUsableDownloadHref(control) {
        const href = getDownloadHref(control);

        return Boolean(href && href !== "#");
    }

    function triggerControlledDownload(control) {
        const href = getDownloadHref(control);

        if (!href || href === "#") {
            return false;
        }

        const downloadAnchor = document.createElement("a");
        const downloadName = String(control.getAttribute("download") || "").trim();

        downloadAnchor.href = href;
        downloadAnchor.rel = "noopener";
        downloadAnchor.style.display = "none";

        if (downloadName) {
            downloadAnchor.download = downloadName;
        } else if (control.hasAttribute("download")) {
            downloadAnchor.setAttribute("download", "");
        }

        document.body.appendChild(downloadAnchor);
        downloadAnchor.click();
        downloadAnchor.remove();

        return true;
    }

    function handleDownloadClick(event) {
        const control = event.currentTarget;

        event.preventDefault();
        event.stopPropagation();

        if (isDisabledDownloadControl(control) || !hasUsableDownloadHref(control)) {
            return;
        }

        triggerControlledDownload(control);
    }

    function bindDownloadControls(shell) {
        shell.querySelectorAll(DOWNLOAD_SELECTOR).forEach(function (control) {
            if (control.getAttribute("data-reader-download-bound") === "true") {
                return;
            }

            control.setAttribute("data-reader-download-bound", "true");
            control.addEventListener("click", handleDownloadClick);
        });
    }

    function bindReaderControls(shell) {
        if (!shell || shell.getAttribute("data-reader-controls-ready") === "true") {
            return;
        }

        const zoomControl = shell.querySelector(ZOOM_CONTROL_SELECTOR);
        const zoomOutControl = shell.querySelector(ZOOM_OUT_SELECTOR);
        const zoomInControl = shell.querySelector(ZOOM_IN_SELECTOR);
        const fitToggleControl = shell.querySelector(FIT_TOGGLE_SELECTOR);
        const fitWidthControl = shell.querySelector(FIT_WIDTH_SELECTOR);
        const fitPageControl = shell.querySelector(FIT_PAGE_SELECTOR);
        const imageFitScreenControl = shell.querySelector(IMAGE_FIT_SCREEN_SELECTOR);
        const imageActualSizeControl = shell.querySelector(IMAGE_ACTUAL_SIZE_SELECTOR);
        const imageRotateControl = shell.querySelector(IMAGE_ROTATE_SELECTOR);
        const sheetControl = shell.querySelector(SPREADSHEET_SHEET_CONTROL_SELECTOR);
        const previousSheetControl = shell.querySelector(SPREADSHEET_SHEET_PREVIOUS_SELECTOR);
        const nextSheetControl = shell.querySelector(SPREADSHEET_SHEET_NEXT_SELECTOR);
        const densityToggleControl = shell.querySelector(SPREADSHEET_DENSITY_TOGGLE_SELECTOR);
        const pageControl = shell.querySelector(PAGE_CONTROL_SELECTOR);
        const previousPageControl = shell.querySelector(PAGE_PREVIOUS_SELECTOR);
        const nextPageControl = shell.querySelector(PAGE_NEXT_SELECTOR);
        const railToggleControl = shell.querySelector(RAIL_TOGGLE_SELECTOR);
        const printControls = Array.from(shell.querySelectorAll(PRINT_SELECTOR));
        const textSizeDecreaseControl = shell.querySelector(TEXT_SIZE_DECREASE_SELECTOR);
        const textSizeIncreaseControl = shell.querySelector(TEXT_SIZE_INCREASE_SELECTOR);
        const textSizeControl = shell.querySelector(TEXT_SIZE_CONTROL_SELECTOR);
        const wrapToggleControl = shell.querySelector(WRAP_TOGGLE_SELECTOR);
        const copyTextControl = shell.querySelector(COPY_TEXT_SELECTOR);
        const copySummaryControl = shell.querySelector(COPY_SUMMARY_SELECTOR);
        const representationControls = Array.from(
            shell.querySelectorAll(REPRESENTATION_TARGET_SELECTOR)
        );
        const initialHashPage = getPageFromHash();
        const initialHashSheet = getSheetFromHash();

        shell.setAttribute("data-reader-controls-ready", "true");

        if (!shell.getAttribute("data-reader-fit-target")) {
            shell.setAttribute("data-reader-fit-target", isImageReader(shell) ? FIT_TARGET_SCREEN : FIT_TARGET_WIDTH);
        }

        if (!shell.getAttribute("data-reader-rail-state")) {
            shell.setAttribute("data-reader-rail-state", RAIL_STATE_OPEN);
        }

        if (!shell.getAttribute("data-reader-current-sheet")) {
            shell.setAttribute("data-reader-current-sheet", String(DEFAULT_SHEET));
        }

        if (!shell.getAttribute("data-reader-spreadsheet-density")) {
            shell.setAttribute("data-reader-spreadsheet-density", SPREADSHEET_DENSITY_COMFORTABLE);
        }

        bindDownloadControls(shell);
        syncRepresentationControls(shell, getReaderRepresentation(shell));
        setActivePage(shell, initialHashPage || DEFAULT_PAGE);

        if (isSpreadsheetReader(shell)) {
            setActiveSheet(shell, initialHashSheet || DEFAULT_SHEET);
        }

        if (isImageReader(shell)) {
            fitImageScreen(shell);
        } else {
            fitWidth(shell);
        }

        bindImageLoads(shell);
        bindPageObserver(shell);
        bindSheetObserver(shell);
        updateRailControlState(shell);
        applyTextPreviewState(shell);
        updateSpreadsheetControlState(shell);

        shell.querySelectorAll(PAGE_LINK_SELECTOR).forEach(function (link) {
            link.addEventListener("click", function (event) {
                const pageNumber = Number(link.getAttribute("data-reader-page-link") || DEFAULT_PAGE);

                event.preventDefault();
                scrollToPage(shell, pageNumber, { updateHash: true });
            });
        });

        shell.querySelectorAll(SPREADSHEET_SHEET_LINK_SELECTOR).forEach(function (link) {
            link.addEventListener("click", function (event) {
                const sheetNumber = Number(link.getAttribute("data-reader-sheet-link") || DEFAULT_SHEET);

                event.preventDefault();
                scrollToSheet(shell, sheetNumber, { updateHash: true });
            });
        });

        if (previousPageControl) {
            previousPageControl.addEventListener("click", function () {
                scrollByPage(shell, -1);
            });
        }

        if (nextPageControl) {
            nextPageControl.addEventListener("click", function () {
                scrollByPage(shell, 1);
            });
        }

        if (previousSheetControl) {
            previousSheetControl.addEventListener("click", function () {
                scrollBySheet(shell, -1);
            });
        }

        if (nextSheetControl) {
            nextSheetControl.addEventListener("click", function () {
                scrollBySheet(shell, 1);
            });
        }

        if (sheetControl) {
            sheetControl.addEventListener("click", function () {
                scrollToCurrentSheet(shell);
            });
        }

        if (densityToggleControl) {
            densityToggleControl.addEventListener("click", function () {
                toggleSpreadsheetDensity(shell);
            });
        }

        if (zoomControl) {
            zoomControl.addEventListener("click", function () {
                cycleZoom(shell);
            });
        }

        if (zoomOutControl) {
            zoomOutControl.addEventListener("click", function () {
                zoomOut(shell);
            });
        }

        if (zoomInControl) {
            zoomInControl.addEventListener("click", function () {
                zoomIn(shell);
            });
        }

        if (fitToggleControl) {
            fitToggleControl.addEventListener("click", function () {
                toggleFitMode(shell);
            });
        }

        if (fitWidthControl) {
            fitWidthControl.addEventListener("click", function () {
                fitWidth(shell);
            });
        }

        if (fitPageControl) {
            fitPageControl.addEventListener("click", function () {
                fitPage(shell);
            });
        }

        if (imageFitScreenControl) {
            imageFitScreenControl.addEventListener("click", function () {
                fitImageScreen(shell);
            });
        }

        if (imageActualSizeControl) {
            imageActualSizeControl.addEventListener("click", function () {
                showImageActualSize(shell);
            });
        }

        if (imageRotateControl) {
            imageRotateControl.addEventListener("click", function () {
                rotateImage(shell);
            });
        }

        if (pageControl) {
            pageControl.addEventListener("click", function () {
                scrollToCurrentPage(shell);
            });
        }

        if (railToggleControl) {
            railToggleControl.addEventListener("click", function () {
                toggleRail(shell);
            });
        }

        printControls.forEach(function (control) {
            control.addEventListener("click", handlePrintClick);
        });

        if (textSizeDecreaseControl) {
            textSizeDecreaseControl.addEventListener("click", function () {
                decreaseTextSize(shell);
            });
        }

        if (textSizeIncreaseControl) {
            textSizeIncreaseControl.addEventListener("click", function () {
                increaseTextSize(shell);
            });
        }

        if (textSizeControl) {
            textSizeControl.addEventListener("click", function () {
                resetTextSize(shell);
            });
        }

        if (wrapToggleControl) {
            wrapToggleControl.addEventListener("click", function () {
                toggleTextWrap(shell);
            });
        }

        if (copyTextControl) {
            copyTextControl.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                copyPreviewText(shell, copyTextControl);
            });
        }

        if (copySummaryControl) {
            copySummaryControl.addEventListener("click", function (event) {
                event.preventDefault();
                event.stopPropagation();
                copySummaryText(shell, copySummaryControl);
            });
        }

        representationControls.forEach(function (control) {
            control.addEventListener("click", function (event) {
                const representation = String(
                    control.getAttribute("data-reader-representation-target") || ""
                ).trim().toLowerCase();

                event.preventDefault();
                event.stopPropagation();
                setReaderRepresentation(shell, representation);
            });
        });

        window.addEventListener("resize", function () {
            if (!isShellVisible(shell)) {
                return;
            }

            if (
                getFitTarget(shell) === FIT_TARGET_PAGE ||
                getFitTarget(shell) === FIT_TARGET_SCREEN ||
                getFitTarget(shell) === FIT_TARGET_WIDTH
            ) {
                applyZoom(shell);
            }
        });

        window.addEventListener("hashchange", function () {
            const hashPage = getPageFromHash();
            const hashSheet = getSheetFromHash();

            if (!isShellVisible(shell)) {
                return;
            }

            if (hashPage) {
                scrollToPage(shell, hashPage, { instant: true });
                return;
            }

            if (hashSheet) {
                scrollToSheet(shell, hashSheet, { instant: true });
            }
        });

        if (initialHashPage) {
            window.requestAnimationFrame(function () {
                scrollToPage(shell, initialHashPage, { instant: true });
            });
        }

        if (initialHashSheet) {
            window.requestAnimationFrame(function () {
                scrollToSheet(shell, initialHashSheet, { instant: true });
            });
        }
    }

    function initialize(root) {
        const context = root || document;

        if (context.matches && context.matches(SHELL_SELECTOR)) {
            bindReaderControls(context);
            return;
        }

        context.querySelectorAll(SHELL_SELECTOR).forEach(bindReaderControls);
    }

    function bootstrap() {
        initialize(document);
    }

    window[API_NAME] = {
        initialize,
        bind: initialize,
        bootstrap,
        getRepresentation: function (root) {
            return getReaderRepresentation(resolveReaderShell(root));
        },
        setRepresentation
    };

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", bootstrap, { once: true });
    } else {
        bootstrap();
    }
})();