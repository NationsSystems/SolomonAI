/* -------------------------------------------------------------------
   FILE: company_staff.js
   DIRECTORY: webui/static/js/
   -------------------------------------------------------------------
   Client transport for people and group invitation controls.

   Authority remains server-side in canonical /people routes. This script only
   loads authorized data, renders controls, submits user actions, and
   refreshes state.
------------------------------------------------------------------- */

(function () {
    "use strict";

    const registry = window.NationsCompanyStaff =
        window.NationsCompanyStaff || {};

    const ENDPOINTS = {
        data: "/people/data",
        invite: "/people/invite",
        revokeInvitation: function (invitationRowId) {
            return `/people/invitations/${encodeURIComponent(String(invitationRowId || ""))}/revoke`;
        },
        member: function (membershipId) {
            return `/people/memberships/${encodeURIComponent(String(membershipId || ""))}`;
        },
        memberRole: function (membershipId) {
            return `/people/memberships/${encodeURIComponent(String(membershipId || ""))}/role`;
        }
    };

    const ROLE_LABELS = {
        owner: "Owner",
        admin: "Admin",
        member: "Member",
        guest: "Guest"
    };

    const ROLE_ORDER = {
        owner: 0,
        admin: 1,
        member: 2,
        guest: 3
    };

    function cleanText(value) {
        return String(value || "").trim();
    }

    function normalizeRole(value) {
        const role = cleanText(value).toLowerCase();

        return Object.prototype.hasOwnProperty.call(ROLE_LABELS, role)
            ? role
            : "member";
    }

    function roleLabel(value) {
        const role = normalizeRole(value);

        return ROLE_LABELS[role] || "Member";
    }

    function createElement(tagName, className, text) {
        const element = document.createElement(tagName);

        if (className) {
            element.className = className;
        }

        if (typeof text === "string") {
            element.textContent = text;
        }

        return element;
    }

    function clearElement(element) {
        while (element.firstChild) {
            element.removeChild(element.firstChild);
        }
    }

    function resolveCompanyStaffPage(root) {
        const scope = root && typeof root.querySelector === "function"
            ? root
            : document;

        if (
            scope instanceof Element &&
            scope.matches("[data-company-staff-page]")
        ) {
            return scope;
        }

        return scope.querySelector("[data-company-staff-page]");
    }

    function resolveCompanyStaffElements(root) {
        const page = resolveCompanyStaffPage(root);

        if (!page) {
            return null;
        }

        return {
            page: page,
            inviteForm: page.querySelector("[data-company-staff-invite-form]"),
            roleSelect: page.querySelector("[data-company-staff-role-select]"),
            inviteSubmit: page.querySelector("[data-company-staff-invite-submit]"),
            inviteResult: page.querySelector("[data-company-staff-invite-result]"),
            refreshButton: page.querySelector("[data-company-staff-refresh]"),
            invitationsList: page.querySelector("[data-company-staff-invitations-list]"),
            membersList: page.querySelector("[data-company-staff-members-list]"),
            statusBox: page.querySelector("[data-company-staff-status]")
        };
    }

    function hasRequiredCompanyStaffElements(elements) {
        return Boolean(
            elements &&
            elements.page &&
            elements.inviteForm &&
            elements.roleSelect &&
            elements.inviteSubmit &&
            elements.inviteResult &&
            elements.refreshButton &&
            elements.invitationsList &&
            elements.membersList &&
            elements.statusBox
        );
    }

    function buildAbsoluteInviteUrl(value) {
        const cleanValue = cleanText(value);

        if (!cleanValue) {
            return "";
        }

        if (
            cleanValue.indexOf("http://") === 0 ||
            cleanValue.indexOf("https://") === 0
        ) {
            return cleanValue;
        }

        if (cleanValue.charAt(0) === "/") {
            return `${window.location.origin}${cleanValue}`;
        }

        return cleanValue;
    }

    function createEmpty(message) {
        return createElement("div", "company-staff-empty", message);
    }

    function createError(message) {
        return createElement("div", "company-staff-error", message);
    }

    function createPill(text, modifier) {
        const pill = createElement("span", "company-staff-pill", text);

        if (modifier) {
            pill.classList.add(modifier);
        }

        return pill;
    }

    function rolePill(role) {
        const normalized = normalizeRole(role);

        return createPill(
            roleLabel(normalized),
            `is-${normalized}`
        );
    }

    function statusPill(status, isExpired) {
        const cleanStatus = cleanText(status).toLowerCase() || "pending";

        if (isExpired) {
            return createPill("Expired", "is-expired");
        }

        return createPill(
            cleanStatus,
            cleanStatus === "pending" ? "is-pending" : ""
        );
    }

    function formatDate(value) {
        const cleanValue = cleanText(value);

        if (!cleanValue) {
            return "";
        }

        const date = new Date(cleanValue);

        if (Number.isNaN(date.getTime())) {
            return cleanValue;
        }

        return date.toLocaleString(undefined, {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "numeric",
            minute: "2-digit"
        });
    }

    function sortRoles(roles) {
        return (Array.isArray(roles) ? roles : [])
            .map(normalizeRole)
            .filter(function (role, index, values) {
                return values.indexOf(role) === index;
            })
            .sort(function (left, right) {
                return (ROLE_ORDER[left] || 99) - (ROLE_ORDER[right] || 99);
            });
    }

    function updateRoleSelectOptions(select, roles, selectedRole) {
        const allowedRoles = sortRoles(roles);
        const selected = normalizeRole(selectedRole);

        clearElement(select);

        allowedRoles.forEach(function (role) {
            const option = document.createElement("option");
            option.value = role;
            option.textContent = roleLabel(role);
            option.selected = role === selected;
            select.appendChild(option);
        });

        if (!select.options.length) {
            const option = document.createElement("option");
            option.value = "member";
            option.textContent = "Member";
            select.appendChild(option);
        }
    }

    function createRoleSelect(roles, selectedRole) {
        const select = createElement("select", "company-staff-select");
        updateRoleSelectOptions(select, roles, selectedRole);
        return select;
    }

    async function fetchJson(url, options) {
        const response = await fetch(url, {
            credentials: "same-origin",
            ...(options || {})
        });

        const payload = await response.json().catch(function () {
            return {};
        });

        if (!response.ok || !payload.ok) {
            const message = payload.error || "The request could not be completed.";
            throw new Error(message);
        }

        return payload;
    }

    function initializeCompanyStaffPage(root) {
        const elements = resolveCompanyStaffElements(root);

        if (!hasRequiredCompanyStaffElements(elements)) {
            return false;
        }

        if (
            elements.page.getAttribute(
                "data-company-staff-bound"
            ) === "true"
        ) {
            return true;
        }

        elements.page.setAttribute(
            "data-company-staff-bound",
            "true"
        );

        const inviteForm = elements.inviteForm;
        const roleSelect = elements.roleSelect;
        const inviteSubmit = elements.inviteSubmit;
        const inviteResult = elements.inviteResult;
        const refreshButton = elements.refreshButton;
        const invitationsList = elements.invitationsList;
        const membersList = elements.membersList;
        const statusBox = elements.statusBox;

        let isLoading = false;
        let canInviteRoles = ["member", "guest"];
        let canAssignRoles = ["member", "guest"];

        function setStatus(message, mode) {
            statusBox.textContent = cleanText(message);
            statusBox.classList.remove("is-success", "is-error");

            if (mode === "success") {
                statusBox.classList.add("is-success");
            }

            if (mode === "error") {
                statusBox.classList.add("is-error");
            }
        }

        async function copyToClipboard(value, button) {
            const originalText = button.textContent;

            try {
                if (
                    navigator.clipboard &&
                    typeof navigator.clipboard.writeText === "function"
                ) {
                    await navigator.clipboard.writeText(value);
                    button.textContent = "Copied";
                    setStatus("Group invite copied.", "success");
                } else {
                    window.prompt("Copy group invite:", value);
                    button.textContent = "Copy Group Invite";
                }
            } catch (error) {
                window.prompt("Copy group invite:", value);
                setStatus("Copy shortcut was not available. Use the displayed group invite.", "error");
            }

            window.setTimeout(function () {
                button.textContent = originalText;
            }, 1400);
        }

        function setInviteResult(message, mode, copyValue) {
            clearElement(inviteResult);
            inviteResult.hidden = !message;
            inviteResult.classList.remove("is-success", "is-error");

            if (!message) {
                return;
            }

            if (mode === "success") {
                inviteResult.classList.add("is-success");
            }

            if (mode === "error") {
                inviteResult.classList.add("is-error");
            }

            const messageText = createElement("div", "", message);
            inviteResult.appendChild(messageText);

            if (copyValue) {
                const copyBlock = createElement("code", "company-staff-copy-value", copyValue);
                const copyButton = createElement("button", "company-staff-action", "Copy Group Invite");

                copyButton.type = "button";
                copyButton.addEventListener("click", function () {
                    copyToClipboard(copyValue, copyButton);
                });

                inviteResult.appendChild(copyBlock);
                inviteResult.appendChild(copyButton);
            }
        }

        function setLoadingState(nextLoading) {
            isLoading = Boolean(nextLoading);
            refreshButton.disabled = isLoading;
            refreshButton.textContent = isLoading ? "Refreshing..." : "Refresh";
        }

        function updateInviteRoleOptions(payload) {
            const nextRoles = payload
                && payload.roles
                && Array.isArray(payload.roles.can_invite)
                ? payload.roles.can_invite
                : ["member", "guest"];

            canInviteRoles = sortRoles(nextRoles);
            updateRoleSelectOptions(roleSelect, canInviteRoles, roleSelect.value || "member");
        }

        function updateAssignableRoles(payload) {
            const nextRoles = payload
                && payload.roles
                && Array.isArray(payload.roles.can_assign)
                ? payload.roles.can_assign
                : ["member", "guest"];

            canAssignRoles = sortRoles(nextRoles);
        }

        function createPersonHeader(options) {
            const header = createElement("div", "company-staff-card-header");
            const content = createElement("div", "");
            const title = createElement(
                "h3",
                "company-staff-person-title",
                cleanText(options.title) || "Group member"
            );
            const subtitle = createElement(
                "p",
                "company-staff-person-subtitle",
                cleanText(options.subtitle)
            );
            const meta = createElement("div", "company-staff-card-meta");

            content.appendChild(title);

            if (cleanText(options.subtitle)) {
                content.appendChild(subtitle);
            }

            header.appendChild(content);
            header.appendChild(meta);

            return {
                header: header,
                meta: meta
            };
        }

        function createInvitationCard(invitation) {
            const card = createElement("article", "company-staff-card");
            const headerParts = createPersonHeader({
                title: invitation.email,
                subtitle: invitation.expires_at
                    ? `Expires ${formatDate(invitation.expires_at)}`
                    : "No expiration date available"
            });
            const actions = createElement("div", "company-staff-card-actions");
            const revokeButton = createElement("button", "company-staff-danger", "Revoke");

            revokeButton.type = "button";
            revokeButton.disabled = Boolean(invitation.is_expired);

            headerParts.meta.appendChild(rolePill(invitation.role));
            headerParts.meta.appendChild(statusPill(invitation.status, invitation.is_expired));

            revokeButton.addEventListener("click", function () {
                revokeInvitation({
                    invitationRowId: invitation.id,
                    email: invitation.email,
                    button: revokeButton
                });
            });

            actions.appendChild(revokeButton);

            card.appendChild(headerParts.header);
            card.appendChild(actions);

            return card;
        }

        function createMemberCard(member) {
            const card = createElement("article", "company-staff-card");
            const username = cleanText(member.username);
            const email = cleanText(member.email);
            const role = normalizeRole(member.role);
            const headerParts = createPersonHeader({
                title: email || username || `User ${member.user_id || ""}`,
                subtitle: username && email ? username : ""
            });
            const actions = createElement("div", "company-staff-card-actions");

            headerParts.meta.appendChild(rolePill(role));
            headerParts.meta.appendChild(
                createPill(
                    cleanText(member.status) || "active",
                    ""
                )
            );

            if (member.is_self) {
                headerParts.meta.appendChild(
                    createPill(
                        "You",
                        "is-admin"
                    )
                );
            }

            if (member.joined_at) {
                headerParts.meta.appendChild(
                    createPill(
                        `Joined ${formatDate(member.joined_at)}`,
                        ""
                    )
                );
            }

            if (member.can_change_role) {
                const roleControl = createElement("div", "company-staff-role-control");
                const roleLabelElement = createElement("label", "", "Role");
                const memberRoleSelect = createRoleSelect(canAssignRoles, role);
                const saveRoleButton = createElement("button", "company-staff-action", "Save Role");

                saveRoleButton.type = "button";

                saveRoleButton.addEventListener("click", function () {
                    updateMemberRole({
                        membershipId: member.membership_id,
                        role: memberRoleSelect.value,
                        button: saveRoleButton
                    });
                });

                roleControl.appendChild(roleLabelElement);
                roleControl.appendChild(memberRoleSelect);
                roleControl.appendChild(saveRoleButton);
                actions.appendChild(roleControl);
            }

            if (member.can_remove) {
                const removeButton = createElement("button", "company-staff-danger", "Remove");

                removeButton.type = "button";
                removeButton.addEventListener("click", function () {
                    removeMember({
                        membershipId: member.membership_id,
                        label: email || username || "this member",
                        button: removeButton
                    });
                });

                actions.appendChild(removeButton);
            }

            card.appendChild(headerParts.header);

            if (actions.childNodes.length) {
                card.appendChild(actions);
            }

            return card;
        }

        function renderInvitations(invitations) {
            clearElement(invitationsList);

            if (!Array.isArray(invitations) || invitations.length === 0) {
                invitationsList.appendChild(
                    createEmpty("No pending group invitations.")
                );
                return;
            }

            invitations.forEach(function (invitation) {
                invitationsList.appendChild(
                    createInvitationCard(invitation)
                );
            });
        }

        function renderMembers(members) {
            clearElement(membersList);

            if (!Array.isArray(members) || members.length === 0) {
                membersList.appendChild(
                    createEmpty("No group members were found.")
                );
                return;
            }

            members.forEach(function (member) {
                membersList.appendChild(
                    createMemberCard(member)
                );
            });
        }

        async function loadCompanyStaff() {
            if (isLoading) {
                return;
            }

            setLoadingState(true);
            setStatus("Loading people and group controls...");

            try {
                const payload = await fetchJson(ENDPOINTS.data);

                updateInviteRoleOptions(payload);
                updateAssignableRoles(payload);
                renderInvitations(payload.pending_invitations || []);
                renderMembers(payload.active_staff || []);
                setStatus("People and group controls loaded.", "success");
            } catch (error) {
                clearElement(invitationsList);
                clearElement(membersList);

                invitationsList.appendChild(
                    createError(error.message || "Pending group invitations could not be loaded.")
                );
                membersList.appendChild(
                    createError(error.message || "Group members could not be loaded.")
                );

                setStatus(
                    error.message || "People and group controls could not be loaded.",
                    "error"
                );
            } finally {
                setLoadingState(false);
            }
        }

        async function submitInvitation(event) {
            event.preventDefault();

            const formData = new FormData(inviteForm);
            const email = cleanText(formData.get("email"));
            const role = normalizeRole(formData.get("role"));
            const originalText = inviteSubmit.textContent;

            if (!email) {
                setInviteResult("Enter an email address.", "error");
                return;
            }

            inviteSubmit.disabled = true;
            inviteSubmit.textContent = "Creating...";
            setInviteResult("");
            setStatus("Creating group invite...");

            try {
                const payload = await fetchJson(ENDPOINTS.invite, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        email: email,
                        role: role
                    })
                });

                inviteForm.reset();
                updateRoleSelectOptions(roleSelect, canInviteRoles, "member");

                setInviteResult(
                    payload.message || "Group invite created.",
                    "success",
                    buildAbsoluteInviteUrl(payload.accept_url || "")
                );
                setStatus("Group invite created. Copy and share it with the member.", "success");
                await loadCompanyStaff();
            } catch (error) {
                setInviteResult(
                    error.message || "The group invite could not be created.",
                    "error"
                );
                setStatus(
                    error.message || "The group invite could not be created.",
                    "error"
                );
            } finally {
                inviteSubmit.disabled = false;
                inviteSubmit.textContent = originalText;
            }
        }

        async function revokeInvitation(options) {
            const email = cleanText(options.email) || "this group invite";
            const confirmed = window.confirm(
                `Revoke the pending group invite for ${email}?`
            );

            if (!confirmed) {
                return;
            }

            const button = options.button;
            const originalText = button.textContent;

            button.disabled = true;
            button.textContent = "Revoking...";
            setStatus("Revoking group invite...");

            try {
                await fetchJson(ENDPOINTS.revokeInvitation(options.invitationRowId), {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        reason: "Revoked from people and groups screen."
                    })
                });

                setStatus("Group invite revoked.", "success");
                await loadCompanyStaff();
            } catch (error) {
                setStatus(
                    error.message || "The group invite could not be revoked.",
                    "error"
                );
                button.disabled = false;
                button.textContent = originalText;
            }
        }

        async function updateMemberRole(options) {
            const button = options.button;
            const originalText = button.textContent;

            button.disabled = true;
            button.textContent = "Saving...";
            setStatus("Saving member role...");

            try {
                await fetchJson(ENDPOINTS.memberRole(options.membershipId), {
                    method: "PATCH",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        role: normalizeRole(options.role)
                    })
                });

                setStatus("Member role updated.", "success");
                await loadCompanyStaff();
            } catch (error) {
                setStatus(
                    error.message || "The member role could not be updated.",
                    "error"
                );
                button.disabled = false;
                button.textContent = originalText;
            }
        }

        async function removeMember(options) {
            const label = cleanText(options.label) || "this member";
            const confirmed = window.confirm(
                `Remove ${label} from the group?`
            );

            if (!confirmed) {
                return;
            }

            const button = options.button;
            const originalText = button.textContent;

            button.disabled = true;
            button.textContent = "Removing...";
            setStatus("Removing member...");

            try {
                await fetchJson(ENDPOINTS.member(options.membershipId), {
                    method: "DELETE"
                });

                setStatus("Member removed.", "success");
                await loadCompanyStaff();
            } catch (error) {
                setStatus(
                    error.message || "The member could not be removed.",
                    "error"
                );
                button.disabled = false;
                button.textContent = originalText;
            }
        }

        inviteForm.addEventListener("submit", submitInvitation);
        refreshButton.addEventListener("click", loadCompanyStaff);

        loadCompanyStaff();

        return true;
    }

    function initializeCurrentCompanyStaffPage() {
        return initializeCompanyStaffPage(document);
    }

    registry.initialize = initializeCompanyStaffPage;
    registry.initializeCurrent = initializeCurrentCompanyStaffPage;

    if (!registry.lifecycleBound) {
        registry.lifecycleBound = true;

        document.addEventListener(
            "solomon:workspace-loaded",
            function (event) {
                initializeCompanyStaffPage(
                    event?.detail?.mount || document
                );
            }
        );
    }

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initializeCurrentCompanyStaffPage,
            { once: true }
        );
    } else {
        initializeCurrentCompanyStaffPage();
    }
}());