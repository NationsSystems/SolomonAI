/* -------------------------------------------------------------------
   FILE: submenu_pointer_intent.js
   DIRECTORY: webui/static/js/command_center/
   -------------------------------------------------------------------
   Canonical Solomon pointer-intent contract for hierarchical menus.
   Keeps an open submenu stable while a mouse/pen pointer is plausibly
   travelling from its parent item toward the submenu.
------------------------------------------------------------------- */

(function () {
    "use strict";

    if (window.SolomonSubmenuPointerIntent) {
        return;
    }

    const CONTRACT = "solomon_submenu_pointer_intent_v1";
    const POINTER_HISTORY_LENGTH = 3;
    const SAFE_CORRIDOR_TOLERANCE_PX = 75;
    const AIM_DELAY_MS = 300;
    const pointerHistory = [];

    function isSupportedPointer(event) {
        const pointerType = String(event?.pointerType || "mouse").toLowerCase();

        return pointerType === "mouse" || pointerType === "pen";
    }

    function recordPointer(event) {
        if (!isSupportedPointer(event)) {
            return;
        }

        const x = Number(event.clientX);
        const y = Number(event.clientY);

        if (!Number.isFinite(x) || !Number.isFinite(y)) {
            return;
        }

        pointerHistory.push({ x, y });

        while (pointerHistory.length > POINTER_HISTORY_LENGTH) {
            pointerHistory.shift();
        }
    }

    function getTriangleSign(point, first, second) {
        return (
            (point.x - second.x) * (first.y - second.y) -
            (first.x - second.x) * (point.y - second.y)
        );
    }

    function pointInTriangle(point, first, second, third) {
        const d1 = getTriangleSign(point, first, second);
        const d2 = getTriangleSign(point, second, third);
        const d3 = getTriangleSign(point, third, first);
        const hasNegative = d1 < 0 || d2 < 0 || d3 < 0;
        const hasPositive = d1 > 0 || d2 > 0 || d3 > 0;

        return !(hasNegative && hasPositive);
    }

    function getSubmenuSide(triggerRect, submenuRect) {
        if (submenuRect.left >= triggerRect.right - 1) {
            return "right";
        }

        if (submenuRect.right <= triggerRect.left + 1) {
            return "left";
        }

        const triggerCenter = triggerRect.left + (triggerRect.width / 2);
        const submenuCenter = submenuRect.left + (submenuRect.width / 2);

        return submenuCenter >= triggerCenter ? "right" : "left";
    }

    function isPointerAimingAtSubmenu(trigger, submenu) {
        if (!(trigger instanceof Element) || !(submenu instanceof Element)) {
            return false;
        }

        if (pointerHistory.length < 2) {
            return false;
        }

        const origin = pointerHistory[0];
        const current = pointerHistory[pointerHistory.length - 1];
        const triggerRect = trigger.getBoundingClientRect();
        const submenuRect = submenu.getBoundingClientRect();
        const side = getSubmenuSide(triggerRect, submenuRect);
        const horizontalTravel = current.x - origin.x;

        if (side === "right" && horizontalTravel <= 0) {
            return false;
        }

        if (side === "left" && horizontalTravel >= 0) {
            return false;
        }

        const nearEdgeX = side === "right"
            ? submenuRect.left
            : submenuRect.right;
        const upperCorner = {
            x: nearEdgeX,
            y: submenuRect.top - SAFE_CORRIDOR_TOLERANCE_PX
        };
        const lowerCorner = {
            x: nearEdgeX,
            y: submenuRect.bottom + SAFE_CORRIDOR_TOLERANCE_PX
        };

        return pointInTriangle(current, origin, upperCorner, lowerCorner);
    }

    function createGuard() {
        let closeTimer = 0;

        function cancelClose() {
            if (closeTimer) {
                window.clearTimeout(closeTimer);
                closeTimer = 0;
            }
        }

        function requestClose(trigger, submenu, closeCallback) {
            cancelClose();

            if (typeof closeCallback !== "function") {
                return false;
            }

            if (!isPointerAimingAtSubmenu(trigger, submenu)) {
                closeCallback();
                return false;
            }

            closeTimer = window.setTimeout(function () {
                closeTimer = 0;
                closeCallback();
            }, AIM_DELAY_MS);

            return true;
        }

        function dispose() {
            cancelClose();
        }

        return Object.freeze({
            requestClose,
            cancelClose,
            dispose
        });
    }

    document.addEventListener("pointermove", recordPointer, {
        capture: true,
        passive: true
    });

    window.SolomonSubmenuPointerIntent = Object.freeze({
        contract: CONTRACT,
        pointerHistoryLength: POINTER_HISTORY_LENGTH,
        safeCorridorTolerancePx: SAFE_CORRIDOR_TOLERANCE_PX,
        aimDelayMs: AIM_DELAY_MS,
        createGuard,
        isPointerAimingAtSubmenu
    });
}());
