/* ==========================================================================
   FILE: webui/static/js/billing/billing.status.js
   DIRECTORY: webui/static/js/billing/
   ========================================================================== */

(function () {
    const STATUS_REGION_ID = "billing-status-region";
    const ANALYZE_BUTTON_ID = "bei-analyze-btn";
    const AUTO_DISMISS_MS = 12000;

    function getStatusRegion() {
        return document.getElementById(STATUS_REGION_ID);
    }

    function removeBillingQueryParameter() {
        if (!window.history || !window.history.replaceState) {
            return;
        }

        const currentUrl = new URL(window.location.href);

        if (!currentUrl.searchParams.has("billing")) {
            return;
        }

        currentUrl.searchParams.delete("billing");

        const cleanedUrl = [
            currentUrl.pathname,
            currentUrl.search,
            currentUrl.hash
        ].join("");

        window.history.replaceState({}, document.title, cleanedUrl || "/");
    }

    function dismissStatusNotice() {
        const statusRegion = getStatusRegion();

        if (!statusRegion) {
            return;
        }

        statusRegion.remove();
    }

    function bindReviewStartDismissal() {
        const analyzeButton = document.getElementById(ANALYZE_BUTTON_ID);

        if (!analyzeButton) {
            return;
        }

        analyzeButton.addEventListener("click", () => {
            dismissStatusNotice();
        }, { once: true });
    }

    function init() {
        const statusRegion = getStatusRegion();

        if (!statusRegion) {
            removeBillingQueryParameter();
            return;
        }

        removeBillingQueryParameter();
        bindReviewStartDismissal();

        window.setTimeout(() => {
            dismissStatusNotice();
        }, AUTO_DISMISS_MS);
    }

    document.addEventListener("DOMContentLoaded", init);
})();