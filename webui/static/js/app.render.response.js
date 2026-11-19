/* ==========================================================================
   FILE: webui/static/js/app.render.response.js
   DIRECTORY: webui/static/js/
   Solomon Response Rendering — Explicit Workflow Integrated
   ========================================================================== */

(function () {

/* ==========================================================================
   THINKING INDICATOR
   ========================================================================== */

function _clearThinkingIndicator() {
    const ui = window.Solomon?.ui;
    if (!ui) return;

    if (ui.thinkingInterval) {
        clearInterval(ui.thinkingInterval);
        ui.thinkingInterval = null;
    }

    if (ui.thinkingMsg && ui.thinkingMsg.remove) {
        ui.thinkingMsg.remove();
        ui.thinkingMsg = null;
    }
}

/* ==========================================================================
   STATE
   ========================================================================== */

function _setStateForPacket(packet) {
    if (!window.SolomonState?.setGuiState) return;

    const nextState = packet?.ok === false
        ? window.SolomonState.GUI_STATES.ERROR_RECOVERABLE
        : window.SolomonState.GUI_STATES.ANSWER_RENDERED;

    window.SolomonState.setGuiState(nextState);
}

/* ==========================================================================
   WORKSPACE RENDER MOTION
   ========================================================================== */

const WORKSPACE_EXIT_MS = 260;
const WORKSPACE_ENTER_MS = 560;
const WORKSPACE_RENDER_STAGGER_MS = 42;

function _prefersReducedMotion() {
    return Boolean(
        window.matchMedia &&
        window.matchMedia("(prefers-reduced-motion: reduce)").matches
    );
}

function _canAnimateElement(element) {
    return Boolean(
        element &&
        typeof element.animate === "function" &&
        !_prefersReducedMotion()
    );
}

function _animateElement(element, keyframes, options) {
    if (!_canAnimateElement(element)) {
        return Promise.resolve(false);
    }

    return new Promise((resolve) => {
        let animation;

        try {
            animation = element.animate(keyframes, options);
        } catch {
            resolve(false);
            return;
        }

        animation.onfinish = () => resolve(true);
        animation.oncancel = () => resolve(false);
    });
}

function _animateWorkspacePanelExit(panel) {
    return _animateElement(
        panel,
        [
            {
                opacity: 1,
                filter: "blur(0px) saturate(1) brightness(1)",
                transform: "translate3d(0, 0, 0) scale(1)"
            },
            {
                opacity: 0,
                filter: "blur(7px) saturate(0.86) brightness(0.74)",
                transform: "translate3d(0, 10px, 0) scale(0.982)"
            }
        ],
        {
            duration: WORKSPACE_EXIT_MS,
            easing: "cubic-bezier(0.4, 0, 1, 1)",
            fill: "forwards"
        }
    );
}

function _animateWorkspacePanelEnter(panel) {
    return _animateElement(
        panel,
        [
            {
                opacity: 0,
                filter: "blur(8px) saturate(0.88) brightness(0.82)",
                transform: "translate3d(0, 14px, 0) scale(0.972)"
            },
            {
                opacity: 0.72,
                offset: 0.52,
                filter: "blur(1.5px) saturate(1.04) brightness(1.03)",
                transform: "translate3d(0, -2px, 0) scale(1.006)"
            },
            {
                opacity: 1,
                filter: "blur(0px) saturate(1) brightness(1)",
                transform: "translate3d(0, 0, 0) scale(1)"
            }
        ],
        {
            duration: WORKSPACE_ENTER_MS,
            easing: "cubic-bezier(0.22, 1, 0.36, 1)",
            fill: "both"
        }
    );
}

function _getRenderableChildren(root) {
    if (!root) return [];

    return Array.from(root.children || [])
        .filter((element) => {
            if (!element || element.hidden) return false;

            const rect = element.getBoundingClientRect?.();
            return Boolean(rect && rect.width && rect.height);
        })
        .slice(0, 8);
}

function _animatePanelArrival(root) {
    if (!_canAnimateElement(root)) {
        return;
    }

    const children = _getRenderableChildren(root);

    if (!children.length) {
        _animateWorkspacePanelEnter(root);
        return;
    }

    children.forEach((child, index) => {
        _animateElement(
            child,
            [
                {
                    opacity: 0,
                    filter: "blur(6px) brightness(0.82)",
                    transform: "translate3d(0, 12px, 0) scale(0.982)"
                },
                {
                    opacity: 1,
                    filter: "blur(0px) brightness(1)",
                    transform: "translate3d(0, 0, 0) scale(1)"
                }
            ],
            {
                delay: index * WORKSPACE_RENDER_STAGGER_MS,
                duration: 420,
                easing: "cubic-bezier(0.22, 1, 0.36, 1)",
                fill: "both"
            }
        );
    });
}

function _animateRenderedSurface(element) {
    if (!_canAnimateElement(element)) {
        return;
    }

    _animateElement(
        element,
        [
            {
                opacity: 0,
                filter: "blur(8px) saturate(0.92) brightness(0.84)",
                transform: "translate3d(0, 16px, 0) scale(0.976)"
            },
            {
                opacity: 0.84,
                offset: 0.58,
                filter: "blur(1px) saturate(1.06) brightness(1.04)",
                transform: "translate3d(0, -2px, 0) scale(1.004)"
            },
            {
                opacity: 1,
                filter: "blur(0px) saturate(1) brightness(1)",
                transform: "translate3d(0, 0, 0) scale(1)"
            }
        ],
        {
            duration: 640,
            easing: "cubic-bezier(0.22, 1, 0.36, 1)",
            fill: "both"
        }
    );
}

function _applyImmediateWorkspaceView(panels, nextPanel, nextView) {
    panels.forEach((panel) => {
        const isActive = panel === nextPanel;

        panel.hidden = !isActive;
        panel.setAttribute("aria-hidden", isActive ? "false" : "true");
    });

    return Boolean(nextView);
}

function _swapWorkspaceViewPanels(panels, nextPanel) {
    panels.forEach((panel) => {
        const isActive = panel === nextPanel;

        panel.hidden = !isActive;
        panel.setAttribute("aria-hidden", isActive ? "false" : "true");
    });
}

function _transitionWorkspaceView(panels, activePanel, nextPanel) {
    if (!nextPanel) {
        return;
    }

    if (
        _prefersReducedMotion() ||
        !_canAnimateElement(nextPanel) ||
        activePanel === nextPanel
    ) {
        _swapWorkspaceViewPanels(panels, nextPanel);
        return;
    }

    if (!activePanel) {
        _swapWorkspaceViewPanels(panels, nextPanel);
        _animateWorkspacePanelEnter(nextPanel);
        _animatePanelArrival(nextPanel);
        return;
    }

    panels.forEach((panel) => {
        if (panel !== activePanel && panel !== nextPanel) {
            panel.hidden = true;
            panel.setAttribute("aria-hidden", "true");
        }
    });

    activePanel.setAttribute("aria-hidden", "true");

    _animateWorkspacePanelExit(activePanel).finally(() => {
        activePanel.hidden = true;
        nextPanel.hidden = false;
        nextPanel.setAttribute("aria-hidden", "false");

        window.requestAnimationFrame(() => {
            _animateWorkspacePanelEnter(nextPanel);
            _animatePanelArrival(nextPanel);
        });
    });
}

/* ==========================================================================
   PRECONSTRUCTION WORKSPACE VIEW STATE
   ========================================================================== */

function _getPreconWorkspace() {
    return document.getElementById("precon-live-workspace");
}

function _setPreconWorkspaceView(viewName) {
    const workspace = _getPreconWorkspace();

    if (!workspace) {
        return false;
    }

    const nextView = String(viewName || "").trim() || "intake";
    const panels = Array.from(workspace.querySelectorAll("[data-precon-view-panel]"));
    const nextPanel = panels.find((panel) => panel.dataset.preconViewPanel === nextView);
    const activePanel = panels.find((panel) => !panel.hidden);

    if (!nextPanel) {
        return false;
    }

    workspace.dataset.preconView = nextView;

    if (!activePanel || _prefersReducedMotion()) {
        _applyImmediateWorkspaceView(panels, nextPanel, nextView);

        if (!_prefersReducedMotion()) {
            _animateWorkspacePanelEnter(nextPanel);
            _animatePanelArrival(nextPanel);
        }

        return true;
    }

    _transitionWorkspaceView(panels, activePanel, nextPanel);

    return true;
}

function _scrollWorkspaceIntoView() {
    const workspace = _getPreconWorkspace();

    if (!workspace?.scrollIntoView) {
        return;
    }

    workspace.scrollIntoView({
        behavior: _prefersReducedMotion() ? "auto" : "smooth",
        block: "start"
    });
}

function _resetPreconstructionWorkspace() {
    const ui = window.Solomon?.ui;
    const conversation = ui?.conversation;

    if (conversation) {
        conversation.innerHTML = "";
        conversation.classList.remove("has-report-output");
    }

    _clearWorkspaceArtifactContext();

    _setPreconWorkspaceView("intake");

    if (window.SolomonState?.setGuiState) {
        window.SolomonState.setGuiState(
            window.SolomonState.GUI_STATES.IDLE
        );
    }

    _scrollWorkspaceIntoView();
}

function showProcessingState() {
    _clearThinkingIndicator();
    _clearWorkspaceArtifactContext();
    _setPreconWorkspaceView("processing");
    _scrollWorkspaceIntoView();
}

/* ==========================================================================
   WORKSPACE ARTIFACT CONTEXT
   ========================================================================== */

function _setDatasetValue(element, key, value) {
    if (!element || !key) return;

    const cleanValue = String(value || "").trim();

    if (cleanValue) {
        element.dataset[key] = cleanValue;
    }
}

function _clearWorkspaceArtifactContext() {
    const workspace = _getPreconWorkspace();

    if (!workspace?.dataset) {
        return;
    }

    delete workspace.dataset.workspaceContext;
    delete workspace.dataset.workspaceRecordId;
    delete workspace.dataset.activeRecordId;
    delete workspace.dataset.activeReviewId;
    delete workspace.dataset.reviewId;
    delete workspace.dataset.workspaceRecordKind;
    delete workspace.dataset.activeRecordKind;
    delete workspace.dataset.artifactKind;
    delete workspace.dataset.activeSection;
    delete workspace.dataset.workspaceSection;
}

function _applyWorkspaceArtifactContext(target, packet, reportTitle, documentName) {
    const payload = packet?.payload || {};
    const reviewId = packet?.review_id || payload.review_id || "";

    const artifact = {
        workspaceContext: "true",
        workspaceRecordKind: "bid_scope_review",
        activeRecordKind: "bid_scope_review",
        artifactKind: "bid_scope_review_report",
        workspaceSection: "review_results",
        activeSection: "review_results",
        proLibrary: "construction_operations",
        workspaceDomain: "construction_operations",
        workspaceModule: "preconstruction",
        workspaceMode: "command_center",
        reportTitle,
        documentName,
    };

    Object.entries(artifact).forEach(([key, value]) => {
        _setDatasetValue(target, key, value);
    });

    if (reviewId) {
        _setDatasetValue(target, "workspaceRecordId", reviewId);
        _setDatasetValue(target, "activeRecordId", reviewId);
        _setDatasetValue(target, "activeReviewId", reviewId);
        _setDatasetValue(target, "reviewId", reviewId);
        _setDatasetValue(target, "recordId", reviewId);
    }
}

/* ==========================================================================
   CONTENT EXTRACTION
   ========================================================================== */

function _getRenderableContent(packet) {
    if (!packet) return "";

    const payload = packet.payload || {};

    if (packet.user_output) {
        return packet.user_output;
    }

    if (payload.user_output) {
        return payload.user_output;
    }

    if (payload.answer) {
        return payload.answer;
    }

    if (packet.answer) {
        return packet.answer;
    }

    if (packet.error) {
        return packet.error;
    }

    return "";
}

function _getMessageType(packet) {
    if (packet?.ok === false) {
        return "error";
    }

    return "answer";
}

function _isDocIntelReport(packet) {
    const payload = packet?.payload || {};
    const answer = payload.answer;

    return (
        packet?.ok !== false &&
        packet?.packet_type === "docintel" &&
        typeof answer === "string" &&
        answer.trim().length > 0
    );
}

function _stripHtml(html) {
    const temp = document.createElement("div");
    temp.innerHTML = html || "";
    return (temp.textContent || temp.innerText || "").trim();
}

function _extractReportTitle(html) {
    const temp = document.createElement("div");
    temp.innerHTML = html || "";

    const boldTitle = temp.querySelector("b")?.textContent?.trim();
    if (boldTitle) {
        return boldTitle;
    }

    return "Bid & Scope Review Complete";
}

function _extractDocumentNameFromTitle(title) {
    if (!title || typeof title !== "string") {
        return "";
    }

    const separator = "—";
    if (!title.includes(separator)) {
        return "";
    }

    return title.split(separator).slice(1).join(separator).trim();
}

function _formatTimestamp() {
    if (window.Solomon?.ui?.formatTimestamp) {
        return window.Solomon.ui.formatTimestamp(new Date());
    }

    return new Date().toLocaleString();
}

function _escapeHtml(value) {
    return String(value || "")
        .replaceAll("&", "&amp;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
}

function _setLastCopyText(text) {
    window.SolomonRender._lastCopyText = text || "";
}

function _copyReportText(text) {
    const copyText = text || "";

    if (!copyText) {
        return;
    }

    if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(copyText).catch(() => {});
        return;
    }

    const textarea = document.createElement("textarea");
    textarea.value = copyText;
    textarea.setAttribute("readonly", "readonly");
    textarea.style.position = "fixed";
    textarea.style.left = "-9999px";

    document.body.appendChild(textarea);
    textarea.select();

    try {
        document.execCommand("copy");
    } catch {
        // Non-fatal fallback failure.
    }

    textarea.remove();
}

function _printReport(reportElement) {
    if (!reportElement) {
        window.print();
        return;
    }

    const printWindow = window.open("", "_blank", "noopener,noreferrer");
    if (!printWindow) {
        window.print();
        return;
    }

    printWindow.document.write(`
        <!doctype html>
        <html>
            <head>
                <title>Nations Systems Review Report</title>
                <style>
                    body {
                        color: #111827;
                        font-family: Arial, sans-serif;
                        line-height: 1.5;
                        margin: 32px;
                    }

                    .bei-list {
                        margin: 8px 0 18px 22px;
                    }

                    .bei-divider {
                        border: 0;
                        border-top: 1px solid #d1d5db;
                        margin-top: 24px;
                    }

                    b {
                        display: block;
                        margin-top: 18px;
                    }
                </style>
            </head>
            <body>
                ${reportElement.innerHTML}
            </body>
        </html>
    `);

    printWindow.document.close();
    printWindow.focus();
    printWindow.print();
}

/* ==========================================================================
   DOCINTEL / BEI REPORT RENDERING
   ========================================================================== */

function _renderDocIntelReport(packet) {
    const ui = window.Solomon?.ui;
    const conversation = ui?.conversation;

    if (!conversation) {
        return false;
    }

    const payload = packet.payload || {};
    const answerHtml = payload.answer || "";
    const reportTitle = _extractReportTitle(answerHtml);
    const documentName = _extractDocumentNameFromTitle(reportTitle);
    const reviewId = packet.review_id || payload.review_id || "";
    const generatedAt = _formatTimestamp();
    const copyText = _stripHtml(answerHtml);

    _setLastCopyText(copyText);

    conversation.innerHTML = "";
    conversation.classList.add("has-report-output");

    const reportShell = document.createElement("section");
    reportShell.className = "precon-report-shell";
    reportShell.setAttribute("aria-label", "Bid and Scope Review report");

    _applyWorkspaceArtifactContext(
        reportShell,
        packet,
        reportTitle,
        documentName
    );

    _applyWorkspaceArtifactContext(
        _getPreconWorkspace(),
        packet,
        reportTitle,
        documentName
    );

    const metadata = [];

    if (reviewId) {
        metadata.push(`Saved Review #${_escapeHtml(reviewId)}`);
    }

    if (documentName) {
        metadata.push(_escapeHtml(documentName));
    }

    metadata.push(_escapeHtml(generatedAt));

    reportShell.innerHTML = `
        <header class="precon-report-header">
            <div class="precon-report-heading">
                <p class="precon-report-eyebrow">Review Results</p>
                <h2 class="precon-report-title">Bid &amp; Scope Review Complete</h2>
                <p class="precon-report-meta">${metadata.join(" · ")}</p>
            </div>

            <div class="precon-report-actions" aria-label="Report actions">
                <button type="button"
                        class="precon-report-action"
                        data-precon-report-action="copy">
                    Copy
                </button>

                <button type="button"
                        class="precon-report-action"
                        data-precon-report-action="print">
                    Print
                </button>

                <button type="button"
                        class="precon-report-action"
                        data-precon-report-action="new-review">
                    Start New Review
                </button>
            </div>
        </header>

        <article class="precon-report-body">
            ${answerHtml}
        </article>
    `;

    conversation.appendChild(reportShell);
    _setPreconWorkspaceView("result");
    _animateRenderedSurface(reportShell);

    const reportBody = reportShell.querySelector(".precon-report-body");
    const copyButton = reportShell.querySelector('[data-precon-report-action="copy"]');
    const printButton = reportShell.querySelector('[data-precon-report-action="print"]');
    const newReviewButton = reportShell.querySelector('[data-precon-report-action="new-review"]');

    if (copyButton) {
        copyButton.addEventListener("click", () => {
            _copyReportText(copyText);
        });
    }

    if (printButton) {
        printButton.addEventListener("click", () => {
            _printReport(reportBody);
        });
    }

    if (newReviewButton) {
        newReviewButton.addEventListener("click", () => {
            _resetPreconstructionWorkspace();
        });
    }

    _scrollWorkspaceIntoView();

    return true;
}

/* ==========================================================================
   FALLBACK RESPONSE RENDERING
   ========================================================================== */

function _renderStandardResponse(packet) {
    const ui = window.Solomon?.ui;
    const content = _getRenderableContent(packet);
    const messageType = _getMessageType(packet);

    if (!ui?.appendSystemMessage) {
        return;
    }

    if (content) {
        ui.appendSystemMessage(content, messageType);
        return;
    }

    if (packet.payload) {
        ui.appendSystemMessage(packet.payload, messageType);
        return;
    }

    ui.appendSystemMessage(
        "The workflow returned no displayable output.",
        "error"
    );
}

/* ==========================================================================
   MAIN RESPONSE RENDERER
   ========================================================================== */

function renderExecutionResponse(packet) {
    if (!packet) return;

    _clearThinkingIndicator();

    if (_isDocIntelReport(packet)) {
        _renderDocIntelReport(packet);
    } else {
        _renderStandardResponse(packet);
    }

    _setStateForPacket(packet);
}

window.SolomonRender = {
    _lastCopyText: "",
    renderExecutionResponse,
    showProcessingState
};

})();