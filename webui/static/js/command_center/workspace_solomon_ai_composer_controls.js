/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_composer_controls.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI composer controls.

   Binds form submission, Enter-to-send behavior, and the composer +
   upload action. New device files enter through the shared canonical
   upload API, then the returned governed document identities are added
   to the current conversation through server-owned source authority.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before composer controls."
        );
    }

    const contract = modules.requireModule("contract");
    const composerState = modules.requireModule(
        "composer_state"
    );
    const requestSubmit = modules.requireModule(
        "request_submit"
    );
    const sourceTransport = modules.requireModule(
        "source_transport"
    );
    const membership = modules.requireModule(
        "source_membership"
    );
    const {
        cleanValue,
        constants,
        readJsonResponse
    } = contract;

    const readinessMonitors = new WeakMap();

    function getDocumentUploadsApi() {
        const uploads = window.SolomonWorkspaceDocumentUploads;

        if (
            !uploads ||
            typeof uploads.openPicker !== "function"
        ) {
            return null;
        }

        return uploads;
    }

    function getChatUploadEndpoint(elements) {
        return cleanValue(
            elements?.workspace?.getAttribute(
                "data-solomon-ai-upload-endpoint"
            )
        );
    }

    function getUploadedDocumentIds(payload) {
        const uploadedFiles = Array.isArray(payload?.files)
            ? payload.files
            : [];

        return sourceTransport.normalizeDocumentIds(
            uploadedFiles.map(function (file) {
                return (
                    file?.document_id ||
                    file?.random_name ||
                    ""
                );
            })
        );
    }

    async function addUploadedFilesToConversation(
        elements,
        payload
    ) {
        const documentIds = getUploadedDocumentIds(
            payload
        );

        if (!documentIds.length) {
            membership.setSourceStatus(
                elements,
                "The upload completed, but Solomon could not identify the new source.",
                "error"
            );
            return false;
        }

        try {
            const packet = await sourceTransport.attachConversationSources(
                elements,
                documentIds
            );

            if (!packet) {
                throw new Error(
                    "The uploaded file could not be added to this chat."
                );
            }

            membership.setSourceStatus(
                elements,
                "",
                "info"
            );
            return true;
        } catch (error) {
            membership.setSourceStatus(
                elements,
                "The file was uploaded to My Files, but it could not be added to this chat. Add it from Sources to try again.",
                "error"
            );
            return false;
        }
    }

    function openComposerUpload(elements) {
        if (
            !elements?.workspace ||
            composerState.isPending(elements)
        ) {
            return false;
        }

        const uploads = getDocumentUploadsApi();
        const uploadEndpoint = getChatUploadEndpoint(elements);

        if (!uploads || !uploadEndpoint) {
            membership.setSourceStatus(
                elements,
                "File upload is temporarily unavailable.",
                "error"
            );
            return false;
        }

        if (!sourceTransport.getAttachEndpoint(elements)) {
            membership.setSourceStatus(
                elements,
                "This chat is not ready to receive a new source yet.",
                "error"
            );
            return false;
        }

        uploads.openPicker(
            elements.workspace,
            {
                endpoint: uploadEndpoint,
                parentFolderId: "",
                afterUpload: async function (
                    explorer,
                    payload
                ) {
                    void explorer;
                    await addUploadedFilesToConversation(
                        elements,
                        payload
                    );
                }
            }
        );

        return true;
    }

    function bindComposerUploadButton(elements) {
        const uploadButton = elements?.composerSource;

        if (
            !uploadButton ||
            uploadButton.getAttribute(
                "data-solomon-ai-upload-control-bound"
            ) === "true"
        ) {
            return false;
        }

        uploadButton.setAttribute(
            "data-solomon-ai-upload-control-bound",
            "true"
        );

        uploadButton.addEventListener(
            "click",
            function (event) {
                event.preventDefault();

                if (uploadButton.disabled) {
                    return;
                }

                openComposerUpload(elements);
            }
        );

        return true;
    }

    function canSubmitFromKeyboard(event) {
        return Boolean(
            event?.key === "Enter" &&
            event.shiftKey !== true &&
            event.isComposing !== true
        );
    }

    function requestComposerSubmit(
        elements,
        event
    ) {
        const composer = elements?.composer;

        event?.preventDefault?.();

        if (
            !composer ||
            composerState.isPending(elements) ||
            !composerState.isInteractiveReady(elements)
        ) {
            return false;
        }

        void requestSubmit.submitMessage(
            event,
            elements
        );

        return true;
    }

    function handleComposerKeydown(
        event,
        elements
    ) {
        if (!canSubmitFromKeyboard(event)) {
            return false;
        }

        return requestComposerSubmit(
            elements,
            event
        );
    }

    function bindComposerSubmit(elements) {
        const composer = elements?.composer;

        if (
            !composer ||
            composer.getAttribute(
                "data-solomon-ai-composer-submit-bound"
            ) === "true"
        ) {
            return false;
        }

        composer.setAttribute(
            "data-solomon-ai-composer-submit-bound",
            "true"
        );

        composer.addEventListener(
            "submit",
            function (event) {
                requestComposerSubmit(
                    elements,
                    event
                );
            }
        );

        return true;
    }

    function bindSubmitButton(elements) {
        const submit = elements?.submit;

        if (
            !submit ||
            submit.getAttribute(
                "data-solomon-ai-submit-control-bound"
            ) === "true"
        ) {
            return false;
        }

        submit.setAttribute(
            "data-solomon-ai-submit-control-bound",
            "true"
        );

        submit.addEventListener(
            "click",
            function (event) {
                requestComposerSubmit(
                    elements,
                    event
                );
            }
        );

        return true;
    }

    function bindComposerKeydown(elements) {
        const input = elements?.input;

        if (
            !input ||
            input.getAttribute(
                "data-solomon-ai-composer-keydown-bound"
            ) === "true"
        ) {
            return false;
        }

        input.setAttribute(
            "data-solomon-ai-composer-keydown-bound",
            "true"
        );

        input.addEventListener(
            "keydown",
            function (event) {
                handleComposerKeydown(
                    event,
                    elements
                );
            }
        );

        return true;
    }

    function getReadinessPollDelay(elements) {
        if (document.hidden) {
            return constants.INTELLIGENCE_READINESS_HIDDEN_POLL_MS;
        }

        const state = composerState.getInteractiveReadinessState(
            elements
        );

        if (state === "ready") {
            return constants.INTELLIGENCE_READINESS_READY_POLL_MS;
        }

        if (state === "warming" || state === "checking") {
            return constants.INTELLIGENCE_READINESS_WARMING_POLL_MS;
        }

        return constants.INTELLIGENCE_READINESS_UNAVAILABLE_POLL_MS;
    }

    function scheduleReadinessCheck(elements) {
        const workspace = elements?.workspace;
        const monitor = workspace
            ? readinessMonitors.get(workspace)
            : null;

        if (!workspace || !monitor || !workspace.isConnected) {
            return false;
        }

        window.clearTimeout(monitor.timerId);
        monitor.timerId = window.setTimeout(
            function () {
                void refreshIntelligenceReadiness(elements);
            },
            getReadinessPollDelay(elements)
        );
        return true;
    }

    async function fetchIntelligenceReadiness() {
        const controller = new AbortController();
        const timeoutId = window.setTimeout(
            function () {
                controller.abort();
            },
            constants.INTELLIGENCE_READINESS_FETCH_TIMEOUT_MS
        );

        try {
            const response = await fetch(
                constants.INTELLIGENCE_READINESS_ENDPOINT,
                {
                    method: "GET",
                    credentials: "same-origin",
                    cache: "no-store",
                    headers: {
                        Accept: "application/json"
                    },
                    signal: controller.signal
                }
            );
            const payload = await readJsonResponse(response);

            if (
                !response.ok ||
                payload?.packet_type !==
                    "solomon_ai_intelligence_readiness"
            ) {
                throw new Error(
                    "Solomon intelligence readiness is unavailable."
                );
            }

            return payload;
        } finally {
            window.clearTimeout(timeoutId);
        }
    }

    async function refreshIntelligenceReadiness(elements) {
        const workspace = elements?.workspace;
        const monitor = workspace
            ? readinessMonitors.get(workspace)
            : null;

        if (
            !workspace ||
            !monitor ||
            monitor.inFlight ||
            !workspace.isConnected
        ) {
            return false;
        }

        monitor.inFlight = true;

        try {
            const readiness =
                await fetchIntelligenceReadiness();

            composerState.setInteractiveReadiness(
                elements,
                readiness
            );
            return true;
        } catch (error) {
            composerState.setInteractiveReadiness(
                elements,
                {
                    status: "unavailable",
                    can_submit: false,
                    user_message:
                        "Solomon is temporarily unavailable. " +
                        "Your other workspace features are unaffected."
                }
            );
            return false;
        } finally {
            monitor.inFlight = false;
            scheduleReadinessCheck(elements);
        }
    }

    function initializeIntelligenceReadiness(elements) {
        const workspace = elements?.workspace;

        if (!workspace) {
            return false;
        }

        if (!readinessMonitors.has(workspace)) {
            readinessMonitors.set(
                workspace,
                {
                    inFlight: false,
                    timerId: 0
                }
            );
        }

        composerState.setInteractiveReadiness(
            elements,
            {
                status: "checking",
                can_submit: false,
                user_message: "Checking Solomon availability…"
            }
        );
        void refreshIntelligenceReadiness(elements);
        return true;
    }

    function refresh(elements) {
        if (!elements?.composer) {
            return false;
        }

        const pending = composerState.isPending(
            elements
        );

        elements.composer.setAttribute(
            "data-solomon-ai-composer-control-state",
            pending ? "pending" : "ready"
        );

        return true;
    }

    function initialize(elements) {
        if (
            !elements?.composer ||
            !elements?.input
        ) {
            return false;
        }

        bindComposerSubmit(
            elements
        );
        bindSubmitButton(
            elements
        );
        bindComposerKeydown(
            elements
        );
        bindComposerUploadButton(
            elements
        );
        initializeIntelligenceReadiness(
            elements
        );
        refresh(elements);

        return true;
    }

    modules.registerModule(
        "composer_controls",
        {
            addUploadedFilesToConversation,
            bindComposerKeydown,
            bindComposerSubmit,
            bindComposerUploadButton,
            bindSubmitButton,
            canSubmitFromKeyboard,
            fetchIntelligenceReadiness,
            getReadinessPollDelay,
            handleComposerKeydown,
            initialize,
            getChatUploadEndpoint,
            getDocumentUploadsApi,
            getUploadedDocumentIds,
            initializeIntelligenceReadiness,
            openComposerUpload,
            refresh,
            refreshIntelligenceReadiness,
            requestComposerSubmit,
            scheduleReadinessCheck
        }
    );
})(window);