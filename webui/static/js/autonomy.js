// autonomy.js — Autonomy Dashboard Logic (Phase 9.11.6)

async function loadAutonomyStatus() {
    try {
        // UPDATED: /autonomy/status → /admin/autonomy/status
        const res = await fetch("/admin/autonomy/status");
        const data = await res.json();

        // --- Today's stats ---
        document.getElementById("new_skills").textContent = data.today.new_skills;
        document.getElementById("upgrades").textContent = data.today.upgrades;

        // --- Last run ---
        document.getElementById("last_run_ts").textContent =
            data.last_run.timestamp ?? "None";

        document.getElementById("last_run_success").textContent =
            data.last_run.success === true ? "Yes" :
            data.last_run.success === false ? "No" : "N/A";

        // --- Stability / Autopause ---
        document.getElementById("autopause").textContent =
            data.stability.autopause ? "YES" : "NO";

        document.getElementById("autopause_reason").textContent =
            data.stability.reason ?? "None";

    } catch (err) {
        console.error("[Autonomy] Failed to fetch status:", err);

        // Optional fallback UI
        document.getElementById("autopause").textContent = "Error";
        document.getElementById("autopause_reason").textContent = "API error";
    }
}

// Initial load
loadAutonomyStatus();

// Refresh every 15 seconds
setInterval(loadAutonomyStatus, 15000);
