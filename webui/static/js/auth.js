// static/js/auth.js — Phase 6 · Step 6.7.7
// ------------------------------------------------------
// Handles login, logout, and automatic session expiry UX
// ------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
    const logoutBtn = document.getElementById("logoutBtn");
    const sessionModal = document.getElementById("sessionModal");

    // ----------------------------
    // Toast Helper (Phase 57 compatible)
    // ----------------------------
    function emitToast(message, type = "info") {
        // Prefer portal-level toast if present
        if (typeof window.showToast === "function") {
            window.showToast(message, type);
            return;
        }
        // Prefer shared SolomonForm toast if present
        if (window.SolomonForm && typeof window.SolomonForm.showToast === "function") {
            window.SolomonForm.showToast(message, type);
            return;
        }
        // Fallback: local toast (legacy behavior)
        let toast = document.createElement("div");
        toast.className = `toast ${type}`;
        toast.innerText = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.classList.add("visible"), 100);
        setTimeout(() => {
            toast.classList.remove("visible");
            toast.remove();
        }, 2500);
    }

    // ----------------------------
    // Manual Logout Handler
    // ----------------------------
    if (logoutBtn) {
        logoutBtn.addEventListener("click", async (e) => {
            e.preventDefault();
            try {
                const res = await fetch("/auth/logout", { method: "GET" });
                const data = await res.json();
                console.log("[Logout]", data);

                if (data.ok) {
                    emitToast("You have been logged out.", "info");
                    // UPDATED: /login → /auth/login
                    setTimeout(() => (window.location.href = "/auth/login"), 1200);
                } else {
                    emitToast(data.error || "Logout failed.", "error");
                }
            } catch (err) {
                console.error("Logout error:", err);
                emitToast("Error logging out.", "error");
            }
        });
    }

    // ----------------------------
    // Session Expiry Heartbeat
    // ----------------------------
    async function checkSession() {
        try {
            const res = await fetch("/session-check");
            if (res.status === 401) {
                console.warn("Session expired — redirecting.");
                showSessionExpiredModal();
            } else {
                const data = await res.json();
                if (!data.ok || data.expired) {
                    showSessionExpiredModal();
                }
            }
        } catch (err) {
            console.error("Session check failed:", err);
        }
    }

    // Run once on load + repeat every 5 minutes
    setTimeout(checkSession, 30000); // first check after 30 sec
    setInterval(checkSession, 5 * 60 * 1000);

    // ----------------------------
    // UX Helpers
    // ----------------------------
    function showSessionExpiredModal() {
        if (sessionModal) {
            sessionModal.classList.add("visible");
        } else {
            alert("Your session has expired. Please log in again.");
        }
        emitToast("Session expired. Redirecting to login…", "warning");
        // UPDATED: /login → /auth/login
        setTimeout(() => (window.location.href = "/auth/login"), 3000);
    }
});
