// ==========================================================
// Solomon Admin Dashboard Logic — Phase 17 UI Enhancements
// ==========================================================
// Handles health checks, diagnostics, recovery tools,
// and SAFE global admin UX helpers (confirm modal).
// ==========================================================

document.addEventListener("DOMContentLoaded", () => {
    const output = document.getElementById("adminOutput");
    const refreshBtn = document.getElementById("refreshHealth");
    const actionButtons = document.querySelectorAll(".actionBtn");

    if (output) {
        output.classList.add("diagnostic-pre");
    }

    function updateHealth(details) {
        const setStatus = (id, ok) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.textContent = ok ? "✅ OK" : "❌ Error";
            el.style.color = ok ? "limegreen" : "crimson";
        };
        if (!details) return;
        setStatus("uploadsStatus", details.uploads_accessible);
        setStatus("dbStatus", details.schema_ok);
        setStatus("coreStatus", details.core_ok);
        setStatus("ollamaStatus", details.ollama_ok);
    }

    async function fetchJSON(endpoint, method = "GET") {
        try {
            const res = await fetch(endpoint, { method });
            return await res.json();
        } catch (err) {
            return { ok: false, error: err.message || "Network error" };
        }
    }

    if (refreshBtn && output) {
        refreshBtn.addEventListener("click", async () => {
            output.textContent = "🔍 Checking system health...";
            const data = await fetchJSON("/admin/health/ready");
            if (data.details) updateHealth(data.details);
            output.textContent = JSON.stringify(data, null, 2);
        });
    }

    actionButtons.forEach(btn => {
        btn.addEventListener("click", async () => {
            const endpoint = btn.dataset.endpoint;
            if (!endpoint) {
                if (output) {
                    output.textContent =
                        "⚠️ This action is not configured (missing data-endpoint).";
                }
                return;
            }

            if (output) output.textContent = `⏳ Running ${endpoint} ...`;
            const data = await fetchJSON(endpoint);
            if (output) output.textContent = JSON.stringify(data, null, 2);
        });
    });

    if (refreshBtn && output) refreshBtn.click();

    async function loadErrorSummary() {
        const badge = document.getElementById("errorSummaryBadge");
        if (!badge) return;

        const data = await fetchJSON("/admin/errors/summary");

        if (!data || data.status !== "ok") {
            badge.textContent = "—";
            badge.classList.add("zero");
            return;
        }

        badge.textContent = String(data.total);
        badge.classList.toggle("zero", data.total === 0);
    }

    loadErrorSummary();
});

// =====================================================
// ⭐ ADMIN TOAST SYSTEM (LIGHTWEIGHT)
// =====================================================

(function injectAdminToasts() {
    if (document.getElementById("adminToastContainer")) return;

    const html = `<div id="adminToastContainer"
        style="position:fixed; top:90px; right:20px; z-index:9999;"></div>`;
    document.body.insertAdjacentHTML("beforeend", html);

    window.adminToast = function (message, type = "info") {
        const el = document.createElement("div");
        el.textContent = message;

        const colors = {
            success: "#10D49A",
            error: "#FF5B5B",
            info: "#19AFFA",
            warning: "#FFB020"
        };

        el.style.background = colors[type] || colors.info;
        el.style.color = "#000";
        el.style.padding = "10px 14px";
        el.style.marginTop = "8px";
        el.style.borderRadius = "8px";
        el.style.fontWeight = "600";
        el.style.boxShadow = "0 6px 18px rgba(0,0,0,.25)";
        el.style.opacity = "0";
        el.style.transition = "opacity .2s";

        const container = document.getElementById("adminToastContainer");
        container.appendChild(el);

        requestAnimationFrame(() => (el.style.opacity = "1"));

        setTimeout(() => {
            el.style.opacity = "0";
            setTimeout(() => el.remove(), 200);
        }, 2200);
    };
})();

// =====================================================
// ⭐ SAFE ADMIN CONFIRM MODAL (ASYNC, VARIANT SUPPORT)
// =====================================================

(function injectAdminConfirm() {
    if (document.getElementById("adminConfirmModal")) return;

    const modalHTML = `
<div class="modal fade admin-theme"
     id="adminConfirmModal"
     tabindex="-1">
  <div class="modal-dialog modal-dialog-centered">
    <div class="modal-content">
      <div class="modal-header">
        <h5 class="modal-title">Confirm Action</h5>
        <button type="button"
                class="btn-close"
                data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <p id="adminConfirmMessage"></p>
      </div>
      <div class="modal-footer">
        <button class="btn btn-secondary"
                data-bs-dismiss="modal">Cancel</button>
        <button class="btn"
                id="adminConfirmYes">Confirm</button>
      </div>
    </div>
  </div>
</div>`;

    document.body.insertAdjacentHTML("beforeend", modalHTML);

    let resolveFn = null;
    const yesBtn = document.getElementById("adminConfirmYes");

    window.adminConfirm = function (message, variant = "neutral") {
        return new Promise(resolve => {
            resolveFn = resolve;

            document.getElementById("adminConfirmMessage").textContent = message;

            yesBtn.classList.remove("btn-danger", "btn-dark");
            yesBtn.classList.add(
                variant === "danger" ? "btn-danger" : "btn-dark"
            );

            const modal = new bootstrap.Modal(
                document.getElementById("adminConfirmModal"),
                { backdrop: "static", keyboard: false }
            );
            modal.show();
        });
    };

    yesBtn.addEventListener("click", () => {
        const modalEl = document.getElementById("adminConfirmModal");
        const modal = bootstrap.Modal.getInstance(modalEl);
        modal.hide();
        if (resolveFn) resolveFn(true);
        resolveFn = null;
    });

    document
        .getElementById("adminConfirmModal")
        .addEventListener("hidden.bs.modal", () => {
            if (resolveFn) resolveFn(false);
            resolveFn = null;
        });
})();
