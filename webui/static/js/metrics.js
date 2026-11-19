// static/js/metrics.js
// ------------------------------------------------------------
// Solomon Metrics Dashboard JS — Phase 17 UI Enhancements
// ------------------------------------------------------------
// Adds:
//   • Updated /admin/metrics/* endpoints
//   • Safety guards for missing elements
//   • Diagnostic-style formatting via .diagnostic-pre
//   • Clean error states consistent with admin diagnostics
// ------------------------------------------------------------

async function fetchMetrics() {
  try {
    const res = await fetch("/admin/metrics/data", {
      headers: { Accept: "application/json" },
    });

    const data = await res.json();
    if (!data || data.status !== "ok") {
      return setErrorState("Metrics fetch failed.");
    }

    const summary = data.summary || {};
    const reasoning = data.by_reasoning_source || {};
    const intents = data.by_intent || {};
    const recent = data.recent || [];

    // Summary values
    safeSet("total-tasks", summary.total_tasks ?? "—");
    safeSet("success-rate", `${(summary.success_rate ?? 0).toFixed(1)}%`);
    safeSet("avg-duration", `${summary.avg_duration_ms ?? "—"} ms`);
    safeSet(
      "last-updated",
      summary.last_updated?.split("T")[1]?.split(".")[0] ?? "—"
    );

    // Charts
    updateReasoningChart(reasoning);
    updateIntentChart(intents);

    // Sub-metrics
    fetchReinforcementMetrics();
    fetchAdaptiveBias();
    fetchAdaptiveWeights();

    // Recent tasks
    const tbody = document.getElementById("recent-tasks-body");
    if (tbody) {
      tbody.innerHTML = "";
      for (const row of recent) {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td>${row.id}</td>
          <td>${row.user}</td>
          <td>${row.intent}</td>
          <td>${row.success ? "✅" : "❌"}</td>
          <td>${row.reasoning_source}</td>
          <td>${row.duration_ms}</td>
          <td>${row.created_at.split("T")[0]}</td>
        `;
        tbody.appendChild(tr);
      }
    }
  } catch (err) {
    console.error("Metrics fetch failed:", err);
    setErrorState("Network failure loading metrics.");
  }
}

// --------------------------------------------------------------------
// Reinforcement metrics
// --------------------------------------------------------------------
async function fetchReinforcementMetrics() {
  try {
    const res = await fetch("/admin/metrics/reinforcement", {
      headers: { Accept: "application/json" },
    });

    const data = await res.json();
    if (!data || data.status !== "ok" || !data.data) return;

    const records = data.data;
    if (!records.length) return;

    const totalRecords = records.length;
    const avgWeight =
      records.reduce((sum, r) => sum + (r.success_weight ?? 0), 0) /
      totalRecords;

    const sorted = [...records].sort((a, b) => b.success_weight - a.success_weight);
    const topPositive = sorted[0];
    const topNegative = sorted[sorted.length - 1];

    safeSet("reinforce-avg-weight", avgWeight.toFixed(2));
    safeSet("reinforce-top-positive", topPositive?.intent || "—");
    safeSet(
      "reinforce-top-positive-weight",
      `Weight: ${topPositive?.success_weight?.toFixed(2) ?? "—"}`
    );
    safeSet("reinforce-top-negative", topNegative?.intent || "—");
    safeSet(
      "reinforce-top-negative-weight",
      `Weight: ${topNegative?.success_weight?.toFixed(2) ?? "—"}`
    );
    safeSet("reinforce-total", totalRecords);

    updateReinforcementChart(records);
  } catch (err) {
    console.error("Reinforcement fetch failed:", err);
  }
}

// --------------------------------------------------------------------
// Adaptive Bias (Phase 7.7)
// --------------------------------------------------------------------
async function fetchAdaptiveBias() {
  try {
    const res = await fetch("/admin/metrics/adaptive", {
      headers: { Accept: "application/json" },
    });

    const data = await res.json();
    if (!data || data.status !== "ok" || !data.data) return;

    const biases = data.data.biases || {};
    const avgBias = data.data.avg_bias ?? 0;

    safeSet("bias-deterministic", biases.deterministic?.toFixed(3));
    safeSet("bias-semantic", biases.semantic?.toFixed(3));
    safeSet("bias-llm", biases.llm?.toFixed(3));
    safeSet("bias-average", avgBias.toFixed(3));

    updateAdaptiveChart(biases);
  } catch (err) {
    console.error("Adaptive bias fetch failed:", err);
  }
}

// --------------------------------------------------------------------
// Adaptive Reasoning Weights
// --------------------------------------------------------------------
let weightsChart;
async function fetchAdaptiveWeights() {
  try {
    const res = await fetch("/admin/metrics/weights", {
      headers: { Accept: "application/json" },
    });

    const data = await res.json();
    if (!data || !data.weights) return;

    const weights = data.weights || {};
    const tbody = document.querySelector("#weightsTable tbody");
    if (tbody) {
      tbody.innerHTML = "";
      Object.entries(weights).forEach(([mode, value]) => {
        const pct = (Number(value) * 100).toFixed(1) + "%";
        const row = `<tr><td>${mode}</td><td>${pct}</td></tr>`;
        tbody.insertAdjacentHTML("beforeend", row);
      });
    }

    updateWeightsChart(data.history || []);
  } catch (err) {
    console.error("Adaptive weights fetch failed:", err);
  }
}

// ====================================================================
// Chart Renderers
// ====================================================================

let reinforcementChart;
function updateReinforcementChart(records) {
  const ctx = document.getElementById("chart-reinforcement")?.getContext("2d");
  if (!ctx) return;

  const labels = records.map(r => r.intent);
  const weights = records.map(r => r.success_weight);

  if (reinforcementChart) reinforcementChart.destroy();

  reinforcementChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Reinforcement Weight",
        data: weights,
        backgroundColor: weights.map(w => (w >= 0 ? "#00ff88" : "#ff4b4b")),
      }],
    },
    options: { responsive: true, scales: { y: { beginAtZero: true } } },
  });
}

let adaptiveChart;
function updateAdaptiveChart(biases) {
  const ctx = document.getElementById("chart-adaptive")?.getContext("2d");
  if (!ctx) return;

  if (adaptiveChart) adaptiveChart.destroy();

  adaptiveChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: Object.keys(biases),
      datasets: [{
        label: "Adaptive Bias",
        data: Object.values(biases),
        backgroundColor: "#00ff88",
      }],
    },
    options: {
      responsive: true,
      scales: { y: { beginAtZero: true, min: -0.5, max: 0.5 } },
    },
  });
}

function updateWeightsChart(history) {
  const ctx = document.getElementById("weightsChart")?.getContext("2d");
  if (!ctx) return;

  if (weightsChart) weightsChart.destroy();

  const labels = history.map(e => (e.timestamp || "").split("T").pop() || "");
  const deterministic = history.map(e => e.new_weights?.deterministic ?? 0);
  const semantic = history.map(e => e.new_weights?.semantic ?? 0);
  const llm = history.map(e => e.new_weights?.llm ?? 0);

  weightsChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Deterministic", data: deterministic, borderWidth: 2 },
        { label: "Semantic", data: semantic, borderWidth: 2 },
        { label: "LLM", data: llm, borderWidth: 2 },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: { position: "top" },
        title: { display: true, text: "Reasoning Weight Evolution" },
      },
      scales: { y: { min: 0, max: 1 } },
    },
  });
}

// Pie chart
let reasoningChart;
function updateReasoningChart(data) {
  const ctx = document.getElementById("chart-reasoning")?.getContext("2d");
  if (!ctx) return;

  if (reasoningChart) reasoningChart.destroy();

  reasoningChart = new Chart(ctx, {
    type: "pie",
    data: {
      labels: Object.keys(data),
      datasets: [
        {
          data: Object.values(data),
          backgroundColor: ["#36a2eb", "#4bc0c0", "#9966ff", "#ff9f40"],
        },
      ],
    },
  });
}

// Intent frequency chart
let intentChart;
function updateIntentChart(data) {
  const ctx = document.getElementById("chart-intents")?.getContext("2d");
  if (!ctx) return;

  if (intentChart) intentChart.destroy();

  intentChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: Object.keys(data),
      datasets: [
        { label: "Count", data: Object.values(data), backgroundColor: "#36a2eb" },
      ],
    },
    options: { scales: { y: { beginAtZero: true } } },
  });
}

// ====================================================================
// Utility Helpers
// ====================================================================

function safeSet(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function setErrorState(msg) {
  console.warn(msg);
  safeSet("total-tasks", "ERR");
  safeSet("success-rate", "ERR");
  safeSet("avg-duration", "ERR");
  safeSet("last-updated", "ERR");
}

// Initial load
fetchMetrics();
setInterval(fetchMetrics, 30000);
