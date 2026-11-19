/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_composer_layout.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI composer sizing and conversation-scroll reservation.

   Keeps the growing textarea, fixed composer shell, and conversation
   scroll region synchronized. JavaScript manages presentation geometry
   only and does not own conversation or execution authority.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before composer layout."
        );
    }

    const contract = modules.requireModule("contract");
    const { constants, getElements } = contract;

    function isConversationNearBottom(scroll) {
        if (!scroll) {
            return false;
        }

        return (
            scroll.scrollHeight -
            scroll.scrollTop -
            scroll.clientHeight
        ) <= constants.COMPOSER_BOTTOM_STICK_THRESHOLD_PX;
    }

    function getComposerReserveBreathingRoom() {
        return (
            window.innerWidth <=
            constants.COMPOSER_MOBILE_BREAKPOINT_PX
        )
            ? constants.COMPOSER_RESERVE_MOBILE_BREATHING_ROOM_PX
            : constants.COMPOSER_RESERVE_BREATHING_ROOM_PX;
    }

    function updateComposerReserve(elements, options) {
        if (
            !elements?.workspace ||
            !elements?.composerShell ||
            !elements?.scroll
        ) {
            return false;
        }

        const shellHeight = Math.ceil(
            elements.composerShell.getBoundingClientRect().height
        );

        if (!shellHeight) {
            return false;
        }

        const reserveHeight = (
            shellHeight + getComposerReserveBreathingRoom()
        );
        const currentReserve = parseFloat(
            window.getComputedStyle(elements.workspace).getPropertyValue(
                "--solomon-ai-composer-reserve-height"
            )
        ) || 0;

        if (Math.abs(currentReserve - reserveHeight) < 1) {
            return false;
        }

        elements.workspace.style.setProperty(
            "--solomon-ai-composer-reserve-height",
            `${reserveHeight}px`
        );
        elements.workspace.setAttribute(
            "data-solomon-ai-composer-reserve-height",
            String(reserveHeight)
        );

        if (options?.stickToBottom !== true) {
            return true;
        }

        window.requestAnimationFrame(function () {
            if (elements.scroll?.isConnected) {
                elements.scroll.scrollTop =
                    elements.scroll.scrollHeight;
            }
        });

        return true;
    }

    function resolveComposerElements(input, elements) {
        if (elements?.workspace) {
            return elements;
        }

        const workspace = input?.closest(
            constants.WORKSPACE_SELECTOR
        );

        return workspace ? getElements(workspace) : null;
    }

    function resizeInput(input, elements) {
        if (!input) {
            return false;
        }

        const resolvedElements = resolveComposerElements(
            input,
            elements
        );
        const shouldStickToBottom = isConversationNearBottom(
            resolvedElements?.scroll
        );
        const configuredMaxHeight = parseFloat(
            window.getComputedStyle(input).maxHeight
        );
        const maxHeight = (
            Number.isFinite(configuredMaxHeight) &&
            configuredMaxHeight > 0
        )
            ? configuredMaxHeight
            : 180;

        input.style.height = "auto";

        const nextHeight = Math.min(
            input.scrollHeight,
            maxHeight
        );

        input.style.height = `${nextHeight}px`;
        input.style.overflowY = (
            input.scrollHeight > maxHeight
                ? "auto"
                : "hidden"
        );

        updateComposerReserve(resolvedElements, {
            stickToBottom: shouldStickToBottom
        });

        return true;
    }

    function bindComposerInputResize(elements) {
        const input = elements?.input;

        if (
            !input ||
            input.getAttribute(
                "data-solomon-ai-composer-input-layout-bound"
            ) === "true"
        ) {
            return false;
        }

        input.setAttribute(
            "data-solomon-ai-composer-input-layout-bound",
            "true"
        );
        input.addEventListener("input", function () {
            resizeInput(input, elements);
        });

        return true;
    }

    function bindComposerLayout(elements) {
        if (
            !elements?.workspace ||
            !elements?.composerShell ||
            elements.workspace.getAttribute(
                "data-solomon-ai-composer-layout-bound"
            ) === "true"
        ) {
            return false;
        }

        elements.workspace.setAttribute(
            "data-solomon-ai-composer-layout-bound",
            "true"
        );

        if (typeof window.ResizeObserver === "function") {
            const observer = new ResizeObserver(function () {
                updateComposerReserve(elements, {
                    stickToBottom: isConversationNearBottom(
                        elements.scroll
                    )
                });
            });

            observer.observe(elements.composerShell);
            elements.workspace.solomonAIComposerResizeObserver =
                observer;
        }

        updateComposerReserve(elements, {
            stickToBottom: false
        });

        return true;
    }

    function disconnectComposerLayout(elements) {
        const workspace = elements?.workspace;
        const observer = workspace?.solomonAIComposerResizeObserver;

        if (
            observer &&
            typeof observer.disconnect === "function"
        ) {
            observer.disconnect();
        }

        if (workspace) {
            delete workspace.solomonAIComposerResizeObserver;
            workspace.removeAttribute(
                "data-solomon-ai-composer-layout-bound"
            );
        }
    }

    function refresh(elements, options) {
        if (!elements?.workspace) {
            return false;
        }

        resizeInput(elements.input, elements);
        updateComposerReserve(elements, {
            stickToBottom: options?.stickToBottom === true
        });

        return true;
    }

    function initialize(elements) {
        if (!elements?.workspace) {
            return false;
        }

        bindComposerInputResize(elements);
        bindComposerLayout(elements);
        refresh(elements);

        return true;
    }

    modules.registerModule("composer_layout", {
        bindComposerInputResize,
        bindComposerLayout,
        disconnectComposerLayout,
        getComposerReserveBreathingRoom,
        initialize,
        isConversationNearBottom,
        refresh,
        resizeInput,
        resolveComposerElements,
        updateComposerReserve
    });
})(window);