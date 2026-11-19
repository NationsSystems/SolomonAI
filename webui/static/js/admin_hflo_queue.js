document.addEventListener("DOMContentLoaded", () => {

    const container = document.getElementById("queueContainer");

    // ---------------------------------------------------------
    // Load HFLO queue
    // ---------------------------------------------------------
    function loadQueue() {
        fetch("/admin/hflo_queue/")
            .then(res => res.json())
            .then(data => {
                if (!data.ok) {
                    window.SolomonForm.showToast("Failed to load HFLO queue", "error");
                    return;
                }

                const items = data.items || [];
                container.innerHTML = "";

                if (items.length === 0) {
                    container.innerHTML = `<p>No pending upgrade items.</p>`;
                    return;
                }

                items.forEach(item => {
                    const div = document.createElement("div");
                    div.className = "queue-item";

                    const statusBadge =
                        item.reviewed === false
                            ? `<span class="badge badge-pending">Pending Review</span>`
                            : item.approved
                                ? `<span class="badge badge-approved">Approved</span>`
                                : `<span class="badge badge-rejected">Rejected</span>`;

                    div.innerHTML = `
                        <div class="queue-header">
                            <h3>Task ${item.task_id}</h3>
                            ${statusBadge}
                        </div>

                        <div class="item-meta">
                            <strong>Action:</strong> ${item.action}<br>
                            <strong>Skill:</strong> ${item.skill_name || "N/A"}<br>
                            <strong>Reason:</strong> ${item.reason || "N/A"}<br>
                            <strong>Created:</strong> ${item.created_at}
                        </div>

                        <details style="margin-top:10px;">
                            <summary style="cursor:pointer;">View Proposed Code</summary>
                            <pre class="code-block">${item.python_code || "(No code attached)"}</pre>
                        </details>

                        <div class="queue-actions">
                            <button class="btn-approve" onclick="approveItem(${item.id})">Approve</button>
                            <button class="btn-reject" onclick="rejectItem(${item.id})">Reject</button>
                            <button class="btn-delete" onclick="deleteItem(${item.id})">Delete</button>
                        </div>
                    `;

                    container.appendChild(div);
                });
            });
    }


    // ---------------------------------------------------------
    // Approve item
    // ---------------------------------------------------------
    window.approveItem = function(id) {
        fetch(`/admin/hflo_queue/approve/${id}`, { method: "POST" })
            .then(res => res.json())
            .then(data => {
                if (!data.ok) {
                    window.SolomonForm.showToast("Approval failed", "error");
                    return;
                }
                window.SolomonForm.showToast("Approved", "success");
                loadQueue();
            });
    };

    // ---------------------------------------------------------
    // Reject item
    // ---------------------------------------------------------
    window.rejectItem = function(id) {
        fetch(`/admin/hflo_queue/reject/${id}`, { method: "POST" })
            .then(res => res.json())
            .then(data => {
                if (!data.ok) {
                    window.SolomonForm.showToast("Rejection failed", "error");
                    return;
                }
                window.SolomonForm.showToast("Rejected", "success");
                loadQueue();
            });
    };

    // ---------------------------------------------------------
    // Delete item
    // ---------------------------------------------------------
    window.deleteItem = function(id) {
        fetch(`/admin/hflo_queue/${id}`, { method: "DELETE" })
            .then(res => res.json())
            .then(data => {
                if (!data.ok) {
                    window.SolomonForm.showToast("Delete failed", "error");
                    return;
                }
                window.SolomonForm.showToast("Deleted", "success");
                loadQueue();
            });
    };


    // Load on start
    loadQueue();
});
