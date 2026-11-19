/* -------------------------------------------------------------------
   FILE: resource_usage.js
   DIRECTORY: webui/static/js/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const page = document.querySelector("[data-resource-usage-page]");
    if (!page) {
        return;
    }

    const endpoint = String(page.dataset.resourceUsageEndpoint || "/resource-usage/data");
    const windowControl = page.querySelector("[data-resource-usage-window]");
    const status = page.querySelector("[data-resource-usage-status]");

    const selectors = {
        occupancy: "[data-resource-usage-occupancy]",
        occupancyLabel: "[data-resource-usage-occupancy-label]",
        occupancyNote: "[data-resource-usage-occupancy-note]",
        headroom: "[data-resource-usage-headroom]",
        requestCount: "[data-resource-usage-request-count]",
        realtimeP95: "[data-resource-usage-realtime-p95]",
        queueP95: "[data-resource-usage-queue-p95]",
        realtimeAverage: "[data-resource-usage-realtime-average]",
        successCount: "[data-resource-usage-success-count]",
        failureCount: "[data-resource-usage-failure-count]",
        workloads: "[data-resource-usage-workloads]",
        capacityRows: "[data-resource-usage-capacity-rows]",
        activityRows: "[data-resource-usage-activity-rows]",
        capacityScope: "[data-resource-usage-capacity-scope]",
        capacitySection: "[data-resource-usage-capacity-section]",
        groupsSection: "[data-resource-usage-groups-section]",
        groups: "[data-resource-usage-groups]"
    };

    function el(selector) {
        return page.querySelector(selector);
    }

    function setText(selector, value) {
        const target = el(selector);
        if (target) {
            target.textContent = value;
        }
    }

    function number(value) {
        const parsed = Number(value);
        return Number.isFinite(parsed) ? parsed : 0;
    }

    function formatCount(value) {
        return Math.max(0, Math.round(number(value))).toLocaleString();
    }

    function formatPercent(value) {
        const numeric = Math.max(0, Math.min(100, number(value)));
        const digits = numeric >= 10 ? 1 : 2;
        return `${numeric.toFixed(digits)}%`;
    }

    function formatDuration(value) {
        const milliseconds = Math.max(0, number(value));
        if (milliseconds < 1) {
            return "<1 ms";
        }
        if (milliseconds < 1000) {
            return `${Math.round(milliseconds)} ms`;
        }
        if (milliseconds < 60000) {
            return `${(milliseconds / 1000).toFixed(milliseconds >= 10000 ? 1 : 2)} s`;
        }
        return `${(milliseconds / 60000).toFixed(1)} min`;
    }

    function formatPeriod(value) {
        if (!value) {
            return "—";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return String(value);
        }
        return new Intl.DateTimeFormat(undefined, {
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit"
        }).format(date);
    }

    function workloadLabel(value) {
        const key = String(value || "").trim().toLowerCase();
        const labels = {
            llm: "AI responses",
            embedding: "Retrieval & indexing",
            embeddings: "Retrieval & indexing",
            summary: "Summaries"
        };
        return labels[key] || key.replace(/_/g, " ").replace(/\b\w/g, function (letter) {
            return letter.toUpperCase();
        }) || "Other";
    }

    function renderWorkloads(counts) {
        const container = el(selectors.workloads);
        if (!container) {
            return;
        }
        const entries = Object.entries(counts || {}).
            map(function (entry) {
                return [entry[0], Math.max(0, number(entry[1]))];
            }).
            filter(function (entry) {
                return entry[1] > 0;
            }).
            sort(function (a, b) {
                return b[1] - a[1];
            });
        const total = entries.reduce(function (sum, entry) {
            return sum + entry[1];
        }, 0);

        container.replaceChildren();
        if (!entries.length) {
            const empty = document.createElement("p");
            empty.className = "resource-usage-status";
            empty.textContent = "No compute activity was recorded in this period.";
            container.appendChild(empty);
            return;
        }

        entries.forEach(function (entry) {
            const row = document.createElement("div");
            row.className = "resource-usage-workload-row";

            const copy = document.createElement("div");
            copy.className = "resource-usage-workload-copy";
            const label = document.createElement("strong");
            label.textContent = workloadLabel(entry[0]);
            const count = document.createElement("span");
            count.textContent = formatCount(entry[1]);
            copy.append(label, count);

            const track = document.createElement("div");
            track.className = "resource-usage-workload-track";
            const fill = document.createElement("div");
            fill.className = "resource-usage-workload-fill";
            fill.style.width = `${Math.max(2, (entry[1] / total) * 100)}%`;
            track.appendChild(fill);

            row.append(copy, track);
            container.appendChild(row);
        });
    }

    function appendCell(row, value) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.appendChild(cell);
    }

    function renderCapacity(rows, scope) {
        const body = el(selectors.capacityRows);
        const section = el(selectors.capacitySection);
        if (!body || !section) {
            return;
        }
        const capacityRows = Array.isArray(rows) ? rows.slice() : [];
        body.replaceChildren();

        const scopeBadge = el(selectors.capacityScope);
        if (scopeBadge) {
            scopeBadge.textContent = scope === "installation" ? "Dedicated capacity" : "Workspace attributed";
        }

        if (!capacityRows.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 5;
            cell.className = "resource-usage-empty-row";
            cell.textContent = "Installation capacity history is not available for this workspace scope.";
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }

        capacityRows.sort(function (a, b) {
            return new Date(b.period_start || 0) - new Date(a.period_start || 0);
        }).forEach(function (item) {
            const row = document.createElement("tr");
            appendCell(row, formatPeriod(item.period_start));
            appendCell(row, formatPercent(item.qualified_compute_occupancy_pct));
            appendCell(row, formatPercent(item.headroom_pct));
            appendCell(row, formatDuration(item.p0_queue_wait_avg_ms));
            appendCell(row, `${formatCount(item.spool_backlog_peak)} jobs`);
            body.appendChild(row);
        });
    }

    function renderActivity(rows) {
        const body = el(selectors.activityRows);
        if (!body) {
            return;
        }
        const activityRows = Array.isArray(rows) ? rows.slice() : [];
        body.replaceChildren();

        if (!activityRows.length) {
            const row = document.createElement("tr");
            const cell = document.createElement("td");
            cell.colSpan = 5;
            cell.className = "resource-usage-empty-row";
            cell.textContent = "No workspace compute activity was recorded in this period.";
            row.appendChild(cell);
            body.appendChild(row);
            return;
        }

        activityRows.sort(function (a, b) {
            return new Date(b.period_start || 0) - new Date(a.period_start || 0);
        }).forEach(function (item) {
            const row = document.createElement("tr");
            const workloads = Object.entries(item.workload_counts || {}).
                filter(function (entry) {
                    return number(entry[1]) > 0;
                }).
                map(function (entry) {
                    return `${workloadLabel(entry[0])}: ${formatCount(entry[1])}`;
                }).
                join(" · ") || "—";
            appendCell(row, formatPeriod(item.period_start));
            appendCell(row, formatCount(item.compute_event_count));
            appendCell(row, workloads);
            appendCell(row, formatDuration(item.execution_avg_ms));
            appendCell(row, formatCount(item.failed_event_count));
            body.appendChild(row);
        });
    }

    function renderGroups(groups) {
        const section = el(selectors.groupsSection);
        const container = el(selectors.groups);
        if (!section || !container) {
            return;
        }
        const entries = Array.isArray(groups) ? groups : [];
        section.hidden = entries.length === 0;
        container.replaceChildren();
        entries.forEach(function (group) {
            const item = document.createElement("div");
            item.className = "resource-usage-detail-list";
            const row = document.createElement("div");
            const name = document.createElement("dt");
            name.textContent = String(group.name || group.group_name || "Group");
            const value = document.createElement("dd");
            value.textContent = formatCount(group.compute_event_count || group.request_count);
            row.append(name, value);
            item.appendChild(row);
            container.appendChild(item);
        });
    }

    function renderReport(report) {
        const summary = report.summary || {};
        const capacity = Array.isArray(report.installation_capacity) ? report.installation_capacity : [];
        const latestCapacity = capacity.reduce(function (latest, item) {
            if (!latest) {
                return item;
            }
            return new Date(item.period_start || 0) > new Date(latest.period_start || 0) ? item : latest;
        }, null);
        const installationScope = report.capacity_scope === "installation" && latestCapacity;

        if (installationScope) {
            setText(selectors.occupancyLabel, "Qualified occupancy");
            setText(selectors.occupancy, formatPercent(latestCapacity.qualified_compute_occupancy_pct));
            setText(selectors.occupancyNote, "Occupied qualified compute capacity in the latest recorded hour.");
            setText(selectors.headroom, formatPercent(latestCapacity.headroom_pct));
        } else {
            setText(selectors.occupancyLabel, "Workspace usage share");
            setText(selectors.occupancy, formatPercent(summary.qualified_compute_occupancy_contribution_pct));
            setText(selectors.occupancyNote, "Your workspace's attributed compute use across the selected history window.");
            setText(selectors.headroom, "Scoped");
        }

        setText(selectors.requestCount, formatCount(summary.request_count));
        setText(selectors.realtimeP95, formatDuration(summary.realtime_execution_p95_ms));
        setText(selectors.queueP95, formatDuration(summary.realtime_queue_wait_p95_ms));
        setText(selectors.realtimeAverage, formatDuration(summary.realtime_execution_avg_ms));
        setText(selectors.successCount, formatCount(summary.successful_event_count));
        setText(selectors.failureCount, formatCount(summary.failed_event_count));

        renderWorkloads(summary.workload_counts);
        renderCapacity(capacity, report.capacity_scope);
        renderActivity(report.hourly_usage);
        renderGroups(report.group_usage);
    }

    async function loadReport(hours) {
        status.classList.remove("is-error");
        status.textContent = "Loading usage history…";
        if (windowControl) {
            windowControl.disabled = true;
        }

        try {
            const url = new URL(endpoint, window.location.origin);
            url.searchParams.set("hours", String(hours));
            const response = await fetch(url.toString(), {
                method: "GET",
                credentials: "same-origin",
                headers: {
                    Accept: "application/json"
                }
            });
            const payload = await response.json().catch(function () {
                return {};
            });
            if (!response.ok || !payload.ok) {
                throw new Error(payload.error || "Resource usage history could not be loaded.");
            }

            renderReport(payload);
            const endAt = payload.window && payload.window.end_at ? formatPeriod(payload.window.end_at) : "now";
            status.textContent = `Usage history through ${endAt}.`;
        } catch (error) {
            status.classList.add("is-error");
            status.textContent = error && error.message ? error.message : "Resource usage history could not be loaded.";
        } finally {
            if (windowControl) {
                windowControl.disabled = false;
            }
        }
    }

    if (windowControl) {
        const defaultHours = String(page.dataset.resourceUsageDefaultHours || "24");
        if (["24", "72", "168"].includes(defaultHours)) {
            windowControl.value = defaultHours;
        }
        windowControl.addEventListener("change", function () {
            loadReport(windowControl.value);
        });
    }

    loadReport(windowControl ? windowControl.value : (page.dataset.resourceUsageDefaultHours || "24"));
}());
