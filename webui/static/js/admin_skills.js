document.addEventListener("DOMContentLoaded", () => {

    // ============================================================
    // ELEMENT REFERENCES
    // ============================================================
    const container = document.getElementById("skillsContainer");
    const modal = document.getElementById("skillModal");
    const modalBody = document.getElementById("modalBody");
    const modalTitle = document.getElementById("modalTitle");
    const syncBtn = document.getElementById("syncFaissBtn");

    // Phase 10.5.4 simulation controls
    const simulateBtn = document.getElementById("simulateBtn");
    const simulationPanel = document.getElementById("simulationPanel");
    const simCode = document.getElementById("simCode");
    const simInput = document.getElementById("simInput");
    const runSimBtn = document.getElementById("runSimBtn");
    const simResultPanel = document.getElementById("simResultPanel");
    const simResultOutput = document.getElementById("simResultOutput");

    // Summary counters
    const summaryTotal = document.getElementById("skillCount");
    const summaryDb = document.getElementById("skillDbCount");
    const summaryFaiss = document.getElementById("skillFaissCount");


    // ============================================================
    // UTIL: Toast wrapper
    // ============================================================
    function toast(msg, type = "info") {
        if (window.SolomonForm && window.SolomonForm.showToast) {
            window.SolomonForm.showToast(msg, type);
        } else {
            console.warn("[Toast Fallback]", msg);
        }
    }


    // ============================================================
    // LOAD SKILLS INTO GRID
    // ============================================================
    function loadSkills() {
        fetch("/admin/api/skills")
            .then(res => res.json())
            .then(data => {
                if (!data.ok) {
                    toast("Failed to load skills", "error");
                    return;
                }

                const skills = data.skills || [];

                // --- Summary counts ---
                summaryTotal.textContent = skills.length;
                summaryDb.textContent = skills.filter(s =>
                    s.persistent_id !== null && s.persistent_id !== undefined
                ).length;
                summaryFaiss.textContent = skills.filter(s =>
                    s.faiss_vector === true
                ).length;

                // --- Render Skills ---
                container.innerHTML = "";

                skills.forEach(skill => {
                    const div = document.createElement("div");
                    div.className = "skill-card";

                    div.innerHTML = `
                        <h3>${skill.name}</h3>

                        <div class="skill-meta">
                            <div><strong>Intent:</strong> ${skill.intent || "N/A"}</div>
                            <div><strong>Source:</strong> ${skill.source || "unknown"}</div>
                            <div><strong>Created:</strong> ${skill.created_at || "N/A"}</div>
                            <div><strong>DB:</strong> ${skill.persistent_id ? "Yes" : "No"}</div>
                            <div><strong>FAISS:</strong> ${skill.faiss_vector ? "Yes" : "No"}</div>
                        </div>
                    `;

                    div.addEventListener("click", () => openModal(skill.name));
                    container.appendChild(div);
                });
            })
            .catch(err => {
                toast("Error loading skills: " + err, "error");
            });
    }


    // ============================================================
    // MODAL VIEWER
    // ============================================================
    function openModal(name) {
        fetch(`/admin/api/skills/${name}`)
            .then(res => res.json())
            .then(data => {
                if (!data.ok) {
                    toast("Skill not found", "error");
                    return;
                }

                const skill = data.skill;

                modalTitle.textContent = skill.name;
                modalBody.textContent = JSON.stringify(skill, null, 2);

                // Preload Python code into simulation editor
                simCode.value = skill.python_code || "";

                // Hide simulation panel until requested
                simulationPanel.style.display = "none";
                simResultPanel.style.display = "none";

                modal.style.display = "flex";
            })
            .catch(err => {
                toast("Error loading skill details: " + err, "error");
            });
    }

    // Safe modal close (only close on backdrop)
    modal.addEventListener("click", (e) => {
        if (e.target === modal) {
            modal.style.display = "none";
        }
    });


    // ============================================================
    // PHASE 10.5.4 — SKILL UPGRADE SIMULATION
    // ============================================================
    simulateBtn.addEventListener("click", () => {
        simulationPanel.style.display = "block";
        simResultPanel.style.display = "none";
    });

    runSimBtn.addEventListener("click", async () => {
        let test_input = {};

        // Validate JSON input
        if (simInput.value.trim() !== "") {
            try {
                test_input = JSON.parse(simInput.value);
            } catch (e) {
                toast("Test input must be valid JSON.", "error");
                return;
            }
        }

        const payload = {
            skill_name: modalTitle.textContent,
            python_code: simCode.value,
            test_input
        };

        const response = await fetch("/admin/skill_simulator/run", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        const data = await response.json();

        simResultPanel.style.display = "block";
        simResultOutput.textContent = JSON.stringify(data, null, 4);
    });


    // ============================================================
    // FAISS SYNC
    // ============================================================
    syncBtn.addEventListener("click", () => {
        fetch("/admin/api/skills/sync", { method: "POST" })
            .then(res => res.json())
            .then(data => {
                if (!data.ok) {
                    toast("FAISS sync failed", "error");
                    return;
                }

                toast("FAISS index synchronized", "success");
                loadSkills();
            })
            .catch(err => {
                toast("FAISS sync error: " + err, "error");
            });
    });


    // ============================================================
    // INITIAL LOAD
    // ============================================================
    loadSkills();

});
