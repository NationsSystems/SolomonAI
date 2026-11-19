/* ==========================================================================
   FILE: admin_users.js
   DIRECTORY: SolomonV3/webui/static/js/admin/
   ========================================================================== */

(function () {
    "use strict";

    const USERS_DATA_ENDPOINT = "/admin/users/data";

    let usersCache = [];
    let selectedUserIds = new Set();

    const tableBody = () => document.getElementById("usersTableBody");
    const notice = () => document.getElementById("adminUsersNotice");
    const refreshButton = () => document.getElementById("refreshUsersButton");
    const selectAllButton = () => document.getElementById("selectAllUsers");
    const clearSelectionButton = () => document.getElementById("clearUserSelection");
    const selectedCount = () => document.getElementById("selectedUserCount");
    const bulkActionButton = () => document.getElementById("bulkActionMenuButton");
    const passwordPanel = () => document.getElementById("temporaryPasswordPanel");
    const passwordOutput = () => document.getElementById("tempPasswordOutput");
    const copyPasswordButton = () => document.getElementById("copyTemporaryPassword");
    const dismissPasswordButton = () => document.getElementById("dismissTemporaryPassword");

    function textOrDash(value) {
        return value === null || value === undefined || value === "" ? "—" : String(value);
    }

    function getUserId(user) {
        return Number(user.id);
    }

    function getAccountIdentity(user) {
        return textOrDash(user.email);
    }

    function formatDate(value, mode) {
        if (!value) return "—";

        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return "—";

        return mode === "date" ? date.toLocaleDateString() : date.toLocaleString();
    }

    function setNotice(message, isError) {
        const element = notice();
        if (!element) return;

        element.hidden = !message;
        element.textContent = message || "";
        element.dataset.noticeType = isError ? "error" : "info";
    }

    function showToast(message, type) {
        if (typeof window.adminToast === "function") {
            window.adminToast(message, type || "info");
            return;
        }

        setNotice(message, type === "error");
    }

    async function confirmAction(message, mode) {
        if (typeof window.adminConfirm === "function") {
            return window.adminConfirm(message, mode);
        }

        showToast("Confirmation control is unavailable.", "error");
        return false;
    }

    async function requestJson(url, options) {
        const response = await fetch(url, options || {});
        const data = await response.json().catch(() => null);

        if (!response.ok || !data) {
            throw new Error("Request failed");
        }

        return data;
    }

    function closeMenus(exceptMenu) {
        document.querySelectorAll("[data-admin-menu]").forEach((menu) => {
            if (menu !== exceptMenu) {
                menu.dataset.menuOpen = "false";
            }
        });
    }

    function toggleMenu(menu) {
        const willOpen = menu.dataset.menuOpen !== "true";
        closeMenus(menu);
        menu.dataset.menuOpen = willOpen ? "true" : "false";
    }

    function clearTable(message) {
        const tbody = tableBody();
        if (!tbody) return;

        tbody.innerHTML = "";

        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 7;
        cell.textContent = message;

        row.appendChild(cell);
        tbody.appendChild(row);
    }

    function createCell(text) {
        const cell = document.createElement("td");
        cell.textContent = textOrDash(text);
        return cell;
    }

    function createPill(text, className) {
        const pill = document.createElement("span");
        pill.className = `admin-pill ${className || ""}`.trim();
        pill.textContent = text;
        return pill;
    }

    function createMenuButton(label, className, handler) {
        const button = document.createElement("button");

        button.type = "button";
        button.className = className;
        button.textContent = label;
        button.addEventListener("click", handler);

        return button;
    }

    function getSelectedUsers() {
        return usersCache.filter((user) => selectedUserIds.has(getUserId(user)));
    }

    function updateSelectionState() {
        const count = selectedUserIds.size;
        const allSelected = usersCache.length > 0 && count === usersCache.length;
        const countElement = selectedCount();
        const selectButton = selectAllButton();
        const clearButton = clearSelectionButton();
        const bulkButton = bulkActionButton();

        if (countElement) {
            countElement.textContent = `${count} Selected`;
        }

        if (selectButton) {
            selectButton.textContent = allSelected ? "Deselect All" : "Select All";
        }

        if (clearButton) {
            clearButton.disabled = count === 0;
        }

        if (bulkButton) {
            bulkButton.disabled = count === 0;
        }
    }

    function createSelectCell(user) {
        const cell = document.createElement("td");
        const label = document.createElement("label");
        const checkbox = document.createElement("input");
        const userId = getUserId(user);

        cell.className = "admin-select-col";
        label.className = "admin-check-control";

        checkbox.type = "checkbox";
        checkbox.className = "admin-user-checkbox";
        checkbox.value = String(userId);
        checkbox.checked = selectedUserIds.has(userId);
        checkbox.setAttribute("aria-label", `Select ${getAccountIdentity(user)}`);

        checkbox.addEventListener("change", () => {
            if (checkbox.checked) {
                selectedUserIds.add(userId);
            } else {
                selectedUserIds.delete(userId);
            }

            updateSelectionState();
        });

        label.appendChild(checkbox);
        label.appendChild(document.createElement("span"));
        cell.appendChild(label);

        return cell;
    }

    function createRoleCell(user) {
        const cell = document.createElement("td");
        const role = textOrDash(user.role);
        const className = role.toLowerCase() === "admin"
            ? "admin-pill-ready"
            : "admin-pill-muted";

        cell.appendChild(createPill(role, className));
        return cell;
    }

    function createStatusCell(user) {
        const cell = document.createElement("td");
        const isActive = Boolean(user.is_active);

        cell.appendChild(createPill(
            isActive ? "Active" : "Disabled",
            isActive ? "admin-pill-ready" : "admin-pill-warning"
        ));

        return cell;
    }

    function createActionsCell(user) {
        const cell = document.createElement("td");
        const menu = document.createElement("div");
        const trigger = document.createElement("button");
        const menuList = document.createElement("div");

        cell.className = "action-col";

        menu.className = "admin-menu admin-row-action-menu";
        menu.dataset.adminMenu = "";
        menu.dataset.menuOpen = "false";

        trigger.type = "button";
        trigger.className = "admin-action admin-row-action-trigger";
        trigger.textContent = "Actions";
        trigger.setAttribute("aria-haspopup", "true");

        trigger.addEventListener("click", (event) => {
            event.stopPropagation();
            toggleMenu(menu);
        });

        menuList.className = "admin-menu-list";
        menuList.setAttribute("role", "menu");

        menuList.appendChild(createMenuButton(
            "Toggle Admin Role",
            "admin-menu-item",
            () => toggleAdmin(user)
        ));

        menuList.appendChild(createMenuButton(
            user.is_active ? "Disable Account" : "Enable Account",
            "admin-menu-item",
            () => toggleActive(user)
        ));

        menuList.appendChild(createMenuButton(
            "Reset Password",
            "admin-menu-item",
            () => resetPassword(user)
        ));

        menuList.appendChild(createMenuButton(
            "Delete User",
            "admin-menu-item admin-menu-item-danger",
            () => deleteUser(user)
        ));

        menu.appendChild(trigger);
        menu.appendChild(menuList);
        cell.appendChild(menu);

        return cell;
    }

    function renderUsers(users) {
        const tbody = tableBody();
        if (!tbody) return;

        tbody.innerHTML = "";
        usersCache = Array.isArray(users) ? users : [];

        selectedUserIds = new Set(
            [...selectedUserIds].filter((id) => (
                usersCache.some((user) => getUserId(user) === id)
            ))
        );

        if (usersCache.length === 0) {
            clearTable("No users found.");
            updateSelectionState();
            return;
        }

        usersCache.forEach((user) => {
            const row = document.createElement("tr");

            row.appendChild(createSelectCell(user));
            row.appendChild(createCell(user.email));
            row.appendChild(createRoleCell(user));
            row.appendChild(createStatusCell(user));
            row.appendChild(createCell(formatDate(user.created_at, "date")));
            row.appendChild(createCell(formatDate(user.last_login_at, "datetime")));
            row.appendChild(createActionsCell(user));

            tbody.appendChild(row);
        });

        updateSelectionState();
    }

    async function loadUsers() {
        setNotice("");
        selectedUserIds.clear();
        closeMenus();
        clearTable("Loading users…");

        try {
            const data = await requestJson(USERS_DATA_ENDPOINT);

            if (!data.ok) {
                clearTable("Failed to load users.");
                showToast(data.error || "Failed to load users.", "error");
                return;
            }

            renderUsers(data.users);
        } catch {
            clearTable("Failed to load users.");
            showToast("Failed to load users.", "error");
        }
    }

    async function postUserAction(userId, action) {
        const endpoints = {
            "toggle-admin": `/admin/users/${userId}/toggle-admin`,
            "toggle-active": `/admin/users/${userId}/toggle-active`,
            "reset-password": `/admin/users/${userId}/reset-password`,
            "delete": `/admin/users/${userId}/delete`,
        };

        return requestJson(endpoints[action], { method: "POST" });
    }

    async function runSingleAction(user, action, confirmMessage, confirmMode) {
        closeMenus();

        const confirmed = await confirmAction(confirmMessage, confirmMode);
        if (!confirmed) return;

        try {
            const data = await postUserAction(getUserId(user), action);

            if (!data.ok) {
                showToast(data.error || "User action failed.", "error");
                return;
            }

            if (action === "reset-password") {
                showTemporaryPassword(`${getAccountIdentity(user)}: ${data.temporary_password}`);
            }

            showToast("User action completed.", "success");

            if (action !== "reset-password") {
                await loadUsers();
            }
        } catch {
            showToast("User action failed.", "error");
        }
    }

    async function toggleAdmin(user) {
        await runSingleAction(
            user,
            "toggle-admin",
            `Toggle admin role for ${getAccountIdentity(user)}?`
        );
    }

    async function toggleActive(user) {
        await runSingleAction(
            user,
            "toggle-active",
            `Enable or disable ${getAccountIdentity(user)}?`
        );
    }

    async function resetPassword(user) {
        await runSingleAction(
            user,
            "reset-password",
            `Reset password for ${getAccountIdentity(user)}? The new password will be shown once.`
        );
    }

    async function deleteUser(user) {
        await runSingleAction(
            user,
            "delete",
            `Delete account for ${getAccountIdentity(user)}? This action cannot be undone.`,
            "danger"
        );
    }

    function getBulkConfirmMessage(action, count) {
        const messages = {
            "toggle-admin": `Toggle admin role for ${count} selected user(s)?`,
            "toggle-active": `Enable or disable ${count} selected user account(s)?`,
            "reset-password": `Reset passwords for ${count} selected user(s)? Passwords will be shown once.`,
            "delete": `Delete ${count} selected user account(s)? This action cannot be undone.`,
        };

        return messages[action] || "Apply this action to selected users?";
    }

    async function applyBulkUserAction(action) {
        const selectedUsers = getSelectedUsers();

        closeMenus();

        if (!action || selectedUsers.length === 0) {
            showToast("Select users before choosing an action.", "error");
            return;
        }

        const confirmed = await confirmAction(
            getBulkConfirmMessage(action, selectedUsers.length),
            action === "delete" ? "danger" : undefined
        );

        if (!confirmed) return;

        const temporaryPasswords = [];
        let successCount = 0;
        let failureCount = 0;

        for (const user of selectedUsers) {
            try {
                const data = await postUserAction(getUserId(user), action);

                if (!data.ok) {
                    failureCount += 1;
                    continue;
                }

                successCount += 1;

                if (action === "reset-password") {
                    temporaryPasswords.push(`${getAccountIdentity(user)}: ${data.temporary_password}`);
                }
            } catch {
                failureCount += 1;
            }
        }

        if (temporaryPasswords.length > 0) {
            showTemporaryPassword(temporaryPasswords.join("\n"));
        }

        showToast(
            failureCount > 0
                ? `${successCount} completed, ${failureCount} failed.`
                : `${successCount} user action(s) completed.`,
            failureCount > 0 ? "error" : "success"
        );

        selectedUserIds.clear();
        await loadUsers();
    }

    function selectOrClearAll() {
        if (usersCache.length === 0) return;

        if (selectedUserIds.size === usersCache.length) {
            selectedUserIds.clear();
        } else {
            selectedUserIds = new Set(usersCache.map((user) => getUserId(user)));
        }

        renderUsers(usersCache);
    }

    function clearSelection() {
        selectedUserIds.clear();
        renderUsers(usersCache);
    }

    function showTemporaryPassword(passwordText) {
        const panel = passwordPanel();
        const output = passwordOutput();

        if (!panel || !output) return;

        output.textContent = passwordText || "";
        panel.hidden = false;
        panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    async function copyTemporaryPassword() {
        const output = passwordOutput();

        if (!output || !output.textContent) return;

        try {
            await navigator.clipboard.writeText(output.textContent);
            showToast("Temporary password copied.", "success");
        } catch {
            showToast("Unable to copy password.", "error");
        }
    }

    function dismissTemporaryPassword() {
        const panel = passwordPanel();
        const output = passwordOutput();

        if (output) output.textContent = "";
        if (panel) panel.hidden = true;
    }

    function bindEvents() {
        const refresh = refreshButton();
        const selectAll = selectAllButton();
        const clearSelected = clearSelectionButton();
        const bulkButton = bulkActionButton();
        const copy = copyPasswordButton();
        const dismiss = dismissPasswordButton();

        if (refresh) refresh.addEventListener("click", loadUsers);
        if (selectAll) selectAll.addEventListener("click", selectOrClearAll);
        if (clearSelected) clearSelected.addEventListener("click", clearSelection);

        if (bulkButton) {
            bulkButton.addEventListener("click", (event) => {
                event.stopPropagation();
                const menu = bulkButton.closest("[data-admin-menu]");
                if (menu) toggleMenu(menu);
            });
        }

        document.querySelectorAll("[data-bulk-action]").forEach((button) => {
            button.addEventListener("click", () => {
                applyBulkUserAction(button.dataset.bulkAction);
            });
        });

        if (copy) copy.addEventListener("click", copyTemporaryPassword);
        if (dismiss) dismiss.addEventListener("click", dismissTemporaryPassword);

        document.addEventListener("click", () => closeMenus());
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") closeMenus();
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        bindEvents();
        loadUsers();
    });

    window.loadAdminUsers = loadUsers;
}());