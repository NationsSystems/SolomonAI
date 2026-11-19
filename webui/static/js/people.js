/* -------------------------------------------------------------------
   FILE: people.js
   DIRECTORY: webui/static/js/
   -------------------------------------------------------------------
   Transport and presentation for the canonical People workspace.

   Server routes remain authoritative for Solomon access, Group membership,
   contextual invitation state, and all permission-changing operations.
------------------------------------------------------------------- */

(function () {
    "use strict";

    const registry = window.NationsPeople = window.NationsPeople || {};

    const ENDPOINTS = {
        data: "/people/data",
        groups: "/people/group-directory",
        group: function (groupId) {
            return `/people/group-directory/${encodeURIComponent(String(groupId || ""))}`;
        },
        groupMembers: function (groupId) {
            return `${ENDPOINTS.group(groupId)}/members`;
        },
        groupMember: function (groupId, membershipId) {
            return `${ENDPOINTS.group(groupId)}/members/${encodeURIComponent(String(membershipId || ""))}`;
        },
        groupMemberRole: function (groupId, membershipId) {
            return `${ENDPOINTS.groupMember(groupId, membershipId)}/role`;
        }
    };

    const ROLE_LABELS = {
        owner: "Owner",
        admin: "Admin",
        member: "Member",
        guest: "Guest"
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
        return ROLE_LABELS[normalizeRole(value)] || "Member";
    }

    function displayName(person) {
        return cleanText(person?.username) || cleanText(person?.email) || "User";
    }

    function initials(value) {
        const source = cleanText(value);
        const parts = source.split(/[\s@._-]+/).filter(Boolean);
        return (parts.slice(0, 2).map(function (part) {
            return part.charAt(0).toUpperCase();
        }).join("") || "U").slice(0, 2);
    }

    function formatDate(value) {
        if (!value) {
            return "-";
        }
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) {
            return "-";
        }
        return new Intl.DateTimeFormat(undefined, {
            month: "short",
            day: "numeric",
            year: "numeric"
        }).format(date);
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

    function icon(name, className) {
        return createElement("span", `icon${className ? ` ${className}` : ""}`, name);
    }

    function clearElement(element) {
        if (element) {
            element.replaceChildren();
        }
    }

    async function fetchJson(url, options) {
        const response = await fetch(url, {
            credentials: "same-origin",
            cache: "no-store",
            ...(options || {})
        });
        let payload = {};
        try {
            payload = await response.json();
        } catch (_error) {
            payload = {};
        }
        if (!response.ok || payload.ok === false) {
            const error = new Error(
                cleanText(payload.error) || `Request failed (${response.status}).`
            );
            error.status = response.status;
            throw error;
        }
        return payload;
    }

    function resolvePage(root) {
        const scope = root && typeof root.querySelector === "function" ? root : document;
        if (scope instanceof Element && scope.matches("[data-people-page]")) {
            return scope;
        }
        return scope.querySelector("[data-people-page]");
    }

    function initializePeoplePage(root) {
        const page = resolvePage(root);
        if (!page || page.dataset.peopleInitialized === "true") {
            return false;
        }
        page.dataset.peopleInitialized = "true";

        const elements = {
            page: page,
            tabs: Array.from(page.querySelectorAll("[data-people-view]")),
            panels: Array.from(page.querySelectorAll("[data-people-view-panel]")),
            status: page.querySelector("[data-people-status]"),
            peopleList: page.querySelector("[data-people-directory-list]"),
            groupsList: page.querySelector("[data-people-groups-list]"),
            groupsCount: page.querySelector("[data-people-groups-count]"),
            groupsHeading: page.querySelector("[data-people-groups-heading]"),
            groupDetail: page.querySelector("[data-people-group-detail]"),
            createGroupButtons: Array.from(page.querySelectorAll("[data-people-create-group]")),
            peopleSearch: page.querySelector('[data-people-search="people"]'),
            groupsSearch: page.querySelector('[data-people-search="groups"]'),
            groupStatusFilter: page.querySelector("[data-people-group-status-filter]"),
            groupDialog: page.querySelector("[data-people-group-dialog]"),
            groupForm: page.querySelector("[data-people-group-form]"),
            groupDialogTitle: page.querySelector("[data-people-group-dialog-title]"),
            groupName: page.querySelector("[data-people-group-name]"),
            groupDescription: page.querySelector("[data-people-group-description]"),
            groupSave: page.querySelector("[data-people-group-save]"),
            membersDialog: page.querySelector("[data-people-members-dialog]"),
            membersForm: page.querySelector("[data-people-members-form]"),
            membersDialogTitle: page.querySelector("[data-people-members-dialog-title]"),
            memberSearch: page.querySelector("[data-people-member-search]"),
            memberPicker: page.querySelector("[data-people-member-picker]"),
            memberEmail: page.querySelector("[data-people-member-email]"),
            memberInviteResult: page.querySelector("[data-people-member-invite-result]"),
            addMembersSubmit: page.querySelector("[data-people-add-members-submit]")
        };

        const state = {
            payload: null,
            selectedGroupId: "",
            groupDialogMode: "create",
            editingGroupId: ""
        };

        const initialUrl = new URL(window.location.href);
        const initialView = cleanText(initialUrl.searchParams.get("view"));
        const initialGroupId = cleanText(initialUrl.searchParams.get("group"));
        let joinedFromInvite = initialUrl.searchParams.get("joined") === "1";

        function clearJoinUrlState() {
            if (!joinedFromInvite && !initialGroupId && !initialView) {
                return;
            }
            const cleanUrl = new URL(window.location.href);
            cleanUrl.searchParams.delete("joined");
            cleanUrl.searchParams.delete("group");
            cleanUrl.searchParams.delete("view");
            window.history.replaceState({}, "", `${cleanUrl.pathname}${cleanUrl.search}${cleanUrl.hash}`);
        }

        function setStatus(message, kind) {
            if (!elements.status) {
                return;
            }
            elements.status.textContent = cleanText(message);
            elements.status.classList.toggle("is-error", kind === "error");
            elements.status.classList.toggle("is-success", kind === "success");
        }

        function activeGroup() {
            const groups = Array.isArray(state.payload?.groups) ? state.payload.groups : [];
            return groups.find(function (group) {
                return cleanText(group.group_id) === state.selectedGroupId;
            }) || null;
        }

        function selectView(view) {
            const normalized = ["people", "groups"].includes(view)
                ? view
                : "people";
            page.dataset.peopleActiveView = normalized;
            elements.tabs.forEach(function (tab) {
                const active = tab.dataset.peopleView === normalized;
                tab.classList.toggle("is-active", active);
                if (active) {
                    tab.setAttribute("aria-current", "page");
                } else {
                    tab.removeAttribute("aria-current");
                }
            });
            elements.panels.forEach(function (panel) {
                const active = panel.dataset.peopleViewPanel === normalized;
                panel.hidden = !active;
                panel.classList.toggle("is-active", active);
            });
        }

        function renderEmpty(target, message) {
            clearElement(target);
            target.appendChild(createElement("div", "people-empty", message));
        }

        function makePersonIdentity(person) {
            const wrapper = createElement("div", "people-identity");
            wrapper.appendChild(createElement("span", "people-avatar", initials(displayName(person))));
            const copy = createElement("span", "people-identity-copy");
            copy.appendChild(createElement("strong", "", displayName(person)));
            if (cleanText(person.email) && displayName(person) !== cleanText(person.email)) {
                copy.appendChild(createElement("small", "", cleanText(person.email)));
            }
            wrapper.appendChild(copy);
            return wrapper;
        }

        function makeStatusPill(status) {
            const normalized = cleanText(status).toLowerCase() || "active";
            const pill = createElement("span", `people-status-pill is-${normalized}`);
            pill.appendChild(createElement("span", "people-status-dot"));
            pill.appendChild(document.createTextNode(
                normalized.charAt(0).toUpperCase() + normalized.slice(1)
            ));
            return pill;
        }

        function makeRolePill(role) {
            return createElement(
                "span",
                `people-role-pill is-${normalizeRole(role)}`,
                roleLabel(role)
            );
        }

        function renderPeople() {
            const people = Array.isArray(state.payload?.people) ? state.payload.people : [];
            const query = cleanText(elements.peopleSearch?.value).toLowerCase();
            const filtered = people.filter(function (person) {
                if (!query) {
                    return true;
                }
                return [person.username, person.email, ...(person.groups || [])]
                    .join(" ")
                    .toLowerCase()
                    .includes(query);
            });

            clearElement(elements.peopleList);
            if (!filtered.length) {
                renderEmpty(elements.peopleList, people.length ? "No people match this search." : "No active people were found.");
                return;
            }

            filtered.forEach(function (person) {
                const row = createElement("div", "people-table-row", "");
                row.setAttribute("role", "row");
                const nameCell = createElement("div", "people-table-cell");
                nameCell.appendChild(makePersonIdentity(person));
                row.appendChild(nameCell);
                row.appendChild(createElement("div", "people-table-cell people-muted-cell", cleanText(person.email) || "-"));
                row.appendChild(createElement(
                    "div",
                    "people-table-cell people-muted-cell",
                    person.group_count ? `${person.group_count} ${person.group_count === 1 ? "group" : "groups"}` : "-"
                ));
                const statusCell = createElement("div", "people-table-cell");
                statusCell.appendChild(makeStatusPill(person.status));
                row.appendChild(statusCell);
                elements.peopleList.appendChild(row);
            });
        }

        function filteredGroups() {
            const groups = Array.isArray(state.payload?.groups) ? state.payload.groups : [];
            const query = cleanText(elements.groupsSearch?.value).toLowerCase();
            const status = cleanText(elements.groupStatusFilter?.value).toLowerCase() || "all";
            return groups.filter(function (group) {
                if (status !== "all" && cleanText(group.status).toLowerCase() !== status) {
                    return false;
                }
                if (!query) {
                    return true;
                }
                return [group.name, group.description]
                    .join(" ")
                    .toLowerCase()
                    .includes(query);
            });
        }

        function renderGroups() {
            const allGroups = Array.isArray(state.payload?.groups) ? state.payload.groups : [];
            const groups = filteredGroups();
            if (!state.selectedGroupId || !allGroups.some(function (group) {
                return cleanText(group.group_id) === state.selectedGroupId;
            })) {
                state.selectedGroupId = cleanText(allGroups[0]?.group_id);
            }

            clearElement(elements.groupsList);
            if (!groups.length) {
                renderEmpty(
                    elements.groupsList,
                    allGroups.length ? "No groups match this search." : (
                        state.payload?.current_user?.can_create_group
                            ? "No groups have been created yet."
                            : "You are not currently a member of any groups."
                    )
                );
            } else {
                groups.forEach(function (group) {
                    const row = createElement("button", "people-table-row people-group-row");
                    row.type = "button";
                    row.dataset.groupId = cleanText(group.group_id);
                    row.classList.toggle("is-selected", cleanText(group.group_id) === state.selectedGroupId);
                    const groupCell = createElement("div", "people-table-cell");
                    const identity = createElement("div", "people-group-identity");
                    identity.appendChild(icon("groups", "people-group-icon"));
                    identity.appendChild(createElement("strong", "", cleanText(group.name) || "Group"));
                    groupCell.appendChild(identity);
                    row.appendChild(groupCell);
                    row.appendChild(createElement("div", "people-table-cell people-count-cell", String(group.member_count || 0)));
                    row.appendChild(createElement("div", "people-table-cell people-muted-cell people-description-cell", cleanText(group.description) || "-"));
                    const statusCell = createElement("div", "people-table-cell");
                    statusCell.appendChild(makeStatusPill(group.status));
                    row.appendChild(statusCell);
                    row.addEventListener("click", function () {
                        state.selectedGroupId = cleanText(group.group_id);
                        renderGroups();
                        renderGroupDetail();
                    });
                    elements.groupsList.appendChild(row);
                });
            }

            if (elements.groupsCount) {
                elements.groupsCount.textContent = `${allGroups.length} ${allGroups.length === 1 ? "group" : "groups"}`;
            }
            if (elements.groupsHeading) {
                elements.groupsHeading.textContent = state.payload?.current_user?.can_manage_people ? "Groups" : "My Groups";
            }
            renderGroupDetail();
        }

        function roleSelectForMember(group, member) {
            const select = createElement("select", "people-inline-role-select");
            const choices = Array.isArray(member.assignable_roles)
                ? member.assignable_roles.map(normalizeRole)
                : [];
            const currentRole = normalizeRole(member.role);
            if (!choices.includes(currentRole)) {
                choices.unshift(currentRole);
            }
            choices.forEach(function (role) {
                const option = createElement("option", "", roleLabel(role));
                option.value = role;
                option.selected = currentRole === role;
                select.appendChild(option);
            });
            select.addEventListener("change", async function () {
                const oldValue = normalizeRole(member.role);
                select.disabled = true;
                try {
                    await fetchJson(ENDPOINTS.groupMemberRole(group.group_id, member.membership_id), {
                        method: "PATCH",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({role: select.value})
                    });
                    setStatus("Group role updated.", "success");
                    await loadData(group.group_id);
                } catch (error) {
                    select.value = oldValue;
                    setStatus(error.message, "error");
                    select.disabled = false;
                }
            });
            return select;
        }

        function renderMemberList(group, container) {
            const members = Array.isArray(group.members) ? group.members : [];
            const invitations = Array.isArray(group.pending_member_invitations)
                ? group.pending_member_invitations
                : [];

            if (!members.length && !invitations.length) {
                renderEmpty(container, "No one is in this group yet.");
                return;
            }

            members.forEach(function (member) {
                const row = createElement("div", "people-member-row");
                row.appendChild(makePersonIdentity(member));
                const roleCell = createElement("div", "people-member-role");
                if (member.can_change_role) {
                    roleCell.appendChild(roleSelectForMember(group, member));
                } else {
                    roleCell.appendChild(makeRolePill(member.role));
                }
                row.appendChild(roleCell);
                row.appendChild(createElement(
                    "span",
                    "people-member-date",
                    formatDate(member.joined_at || member.created_at)
                ));
                const actions = createElement("div", "people-member-actions");
                if (member.can_remove) {
                    const remove = createElement("button", "people-icon-action people-icon-action--danger");
                    remove.type = "button";
                    remove.title = "Remove from group";
                    remove.setAttribute("aria-label", `Remove ${displayName(member)} from group`);
                    remove.appendChild(icon("person_remove"));
                    remove.addEventListener("click", async function () {
                        if (!window.confirm(`Remove ${displayName(member)} from ${group.name}?`)) {
                            return;
                        }
                        remove.disabled = true;
                        try {
                            await fetchJson(
                                ENDPOINTS.groupMember(group.group_id, member.membership_id),
                                {method: "DELETE"}
                            );
                            setStatus("Member removed.", "success");
                            await loadData(group.group_id);
                        } catch (error) {
                            setStatus(error.message, "error");
                            remove.disabled = false;
                        }
                    });
                    actions.appendChild(remove);
                }
                row.appendChild(actions);
                container.appendChild(row);
            });

            invitations.forEach(function (invitation) {
                const row = createElement("div", "people-member-row people-member-row--pending");
                const identity = createElement("div", "people-person-identity");
                const avatar = createElement("span", "people-avatar", initials(invitation.email));
                const copy = createElement("span", "people-person-copy");
                copy.appendChild(createElement("strong", "", cleanText(invitation.email)));
                copy.appendChild(createElement(
                    "small",
                    "",
                    invitation.status === "expired"
                        ? "Invite expired"
                        : "Invite sent"
                ));
                identity.appendChild(avatar);
                identity.appendChild(copy);
                row.appendChild(identity);

                const roleCell = createElement("div", "people-member-role");
                roleCell.appendChild(makeRolePill(invitation.role || "member"));
                row.appendChild(roleCell);

                row.appendChild(createElement(
                    "span",
                    "people-member-date",
                    invitation.status === "expired"
                        ? "Expired"
                        : "Pending"
                ));

                const statusCell = createElement("div", "people-member-actions");
                statusCell.appendChild(makeStatusPill(invitation.status || "pending"));
                row.appendChild(statusCell);
                container.appendChild(row);
            });
        }


        function renderGroupDetail() {
            const group = activeGroup();
            clearElement(elements.groupDetail);
            if (!group) {
                renderEmpty(elements.groupDetail, "Select a group to view its members and details.");
                return;
            }

            const header = createElement("div", "people-detail-header");
            const titleWrap = createElement("div", "people-detail-title-wrap");
            const groupIcon = icon("groups", "people-detail-group-icon");
            titleWrap.appendChild(groupIcon);
            const titleCopy = createElement("div", "people-detail-title-copy");
            const titleLine = createElement("div", "people-detail-title-line");
            titleLine.appendChild(createElement("h2", "", cleanText(group.name) || "Group"));
            titleLine.appendChild(makeStatusPill(group.status));
            titleCopy.appendChild(titleLine);
            titleCopy.appendChild(createElement("p", "", cleanText(group.description) || "No description"));
            const selfRole = group.current_membership?.role;
            if (selfRole) {
                const membershipCopy = createElement("small", "people-membership-copy", "Your role: ");
                membershipCopy.appendChild(makeRolePill(selfRole));
                titleCopy.appendChild(membershipCopy);
            }
            titleWrap.appendChild(titleCopy);
            header.appendChild(titleWrap);
            elements.groupDetail.appendChild(header);

            const stats = createElement("div", "people-detail-stats");
            const memberStat = createElement("div", "people-detail-stat");
            memberStat.appendChild(createElement("strong", "", String(group.member_count || 0)));
            memberStat.appendChild(createElement("span", "", "Members"));
            stats.appendChild(memberStat);
            const createdStat = createElement("div", "people-detail-stat");
            createdStat.appendChild(createElement("strong", "", formatDate(group.created_at)));
            createdStat.appendChild(createElement("span", "", "Created"));
            stats.appendChild(createdStat);
            elements.groupDetail.appendChild(stats);

            if (group.can_edit || group.can_add_members || group.can_delete) {
                const actions = createElement("div", "people-detail-actions");
                if (group.can_edit) {
                    const edit = createElement("button", "people-action");
                    edit.type = "button";
                    edit.appendChild(icon("edit"));
                    edit.appendChild(document.createTextNode(" Edit Group"));
                    edit.addEventListener("click", function () { openGroupDialog("edit", group); });
                    actions.appendChild(edit);
                }

                if (group.can_add_members) {
                    const add = createElement("button", "people-action");
                    add.type = "button";
                    add.appendChild(icon("person_add"));
                    add.appendChild(document.createTextNode(" Add People"));
                    add.addEventListener("click", function () { openMembersDialog(group); });
                    actions.appendChild(add);
                }

                if (group.can_delete) {
                    const del = createElement("button", "people-danger");
                    del.type = "button";
                    del.appendChild(icon("delete_outline"));
                    del.appendChild(document.createTextNode(" Delete Group"));
                    del.addEventListener("click", async function () {
                        if (!window.confirm(`Delete ${group.name}? Files shared with this group will not be deleted, but group-derived access will be revoked.`)) {
                            return;
                        }
                        del.disabled = true;
                        try {
                            await fetchJson(ENDPOINTS.group(group.group_id), {method: "DELETE"});
                            state.selectedGroupId = "";
                            setStatus("Group deleted. Shared files were not deleted.", "success");
                            await loadData();
                        } catch (error) {
                            setStatus(error.message, "error");
                            del.disabled = false;
                        }
                    });
                    actions.appendChild(del);
                }
                elements.groupDetail.appendChild(actions);
            }

            const membersPanel = createElement("section", "people-detail-members");
            const membersHead = createElement("div", "people-detail-section-heading");
            const listedPeopleCount = Number(group.member_count || 0)
                + Number(group.pending_member_count || 0);
            membersHead.appendChild(createElement("h3", "", `Members (${listedPeopleCount})`));
            membersPanel.appendChild(membersHead);
            const memberList = createElement("div", "people-member-list");
            renderMemberList(group, memberList);
            membersPanel.appendChild(memberList);
            elements.groupDetail.appendChild(membersPanel);

        }

        async function copyText(value) {
            const text = cleanText(value);
            if (!text) {
                throw new Error("Invitation link is unavailable.");
            }
            if (navigator.clipboard && window.isSecureContext) {
                await navigator.clipboard.writeText(text);
                return;
            }
            const input = document.createElement("textarea");
            input.value = text;
            input.setAttribute("readonly", "readonly");
            input.style.position = "fixed";
            input.style.opacity = "0";
            document.body.appendChild(input);
            input.select();
            const copied = document.execCommand("copy");
            input.remove();
            if (!copied) {
                throw new Error("The invitation link could not be copied.");
            }
        }

        function renderCapabilities() {
            elements.createGroupButtons.forEach(function (button) {
                button.hidden = !Boolean(state.payload?.current_user?.can_create_group);
            });
        }

        function renderAll() {
            renderCapabilities();
            renderPeople();
            renderGroups();
        }

        async function loadData(preferredGroupId) {
            setStatus("Loading people and groups...");
            try {
                const payload = await fetchJson(ENDPOINTS.data);
                state.payload = payload;
                const requested = cleanText(preferredGroupId);
                if (requested && (payload.groups || []).some(function (group) {
                    return cleanText(group.group_id) === requested;
                })) {
                    state.selectedGroupId = requested;
                }
                renderAll();

                if (joinedFromInvite && requested) {
                    const joinedGroup = (payload.groups || []).find(function (group) {
                        return cleanText(group.group_id) === requested;
                    });
                    setStatus(
                        joinedGroup ? `You joined ${joinedGroup.name}.` : "You're ready to use Solomon.",
                        "success"
                    );
                    clearJoinUrlState();
                    joinedFromInvite = false;
                } else {
                    setStatus("");
                }
            } catch (error) {
                state.payload = null;
                renderEmpty(elements.groupsList, error.message || "People and groups could not be loaded.");
                renderEmpty(elements.peopleList, error.message || "People could not be loaded.");
                renderEmpty(elements.groupDetail, "Group details are unavailable.");
                setStatus(error.message, "error");
            }
        }

        function openGroupDialog(mode, group) {
            if (!elements.groupDialog || typeof elements.groupDialog.showModal !== "function") {
                return;
            }
            state.groupDialogMode = mode;
            state.editingGroupId = mode === "edit" ? cleanText(group?.group_id) : "";
            elements.groupDialogTitle.textContent = mode === "edit" ? "Edit group" : "Create group";
            elements.groupSave.textContent = mode === "edit" ? "Save Changes" : "Create Group";
            elements.groupName.value = mode === "edit" ? cleanText(group?.name) : "";
            elements.groupDescription.value = mode === "edit" ? cleanText(group?.description) : "";
            elements.groupDialog.showModal();
            window.requestAnimationFrame(function () {
                elements.groupName.focus();
            });
        }

        function availablePeopleForGroup(group) {
            const people = Array.isArray(state.payload?.people) ? state.payload.people : [];
            const memberIds = new Set((group?.members || []).map(function (member) {
                return Number(member.user_id);
            }));
            return people.filter(function (person) {
                return !memberIds.has(Number(person.user_id));
            });
        }

        function renderMemberPicker(group) {
            const query = cleanText(elements.memberSearch?.value).toLowerCase();
            const people = availablePeopleForGroup(group).filter(function (person) {
                return !query || [person.username, person.email].join(" ").toLowerCase().includes(query);
            });
            clearElement(elements.memberPicker);
            if (!people.length) {
                renderEmpty(
                    elements.memberPicker,
                    query
                        ? "No people match this search."
                        : "Everyone in Solomon is already in this group."
                );
                return;
            }
            people.forEach(function (person) {
                const label = createElement("label", "people-member-option");
                const checkbox = document.createElement("input");
                checkbox.type = "checkbox";
                checkbox.value = String(person.user_id);
                checkbox.dataset.peopleMemberChoice = "true";
                label.appendChild(checkbox);
                label.appendChild(makePersonIdentity(person));
                elements.memberPicker.appendChild(label);
            });
        }

        function openMembersDialog(group) {
            if (!elements.membersDialog || typeof elements.membersDialog.showModal !== "function") {
                return;
            }
            state.selectedGroupId = cleanText(group.group_id);
            elements.membersDialogTitle.textContent = `Add people to ${group.name}`;
            elements.memberSearch.value = "";
            if (elements.memberEmail) {
                elements.memberEmail.value = "";
            }
            if (elements.memberInviteResult) {
                elements.memberInviteResult.hidden = true;
                elements.memberInviteResult.textContent = "";
                elements.memberInviteResult.className = "people-invite-result";
            }
            renderMemberPicker(group);
            elements.membersDialog.showModal();
        }

        function closeDialog(dialog) {
            if (dialog?.open) {
                dialog.close();
            }
        }

        elements.tabs.forEach(function (tab) {
            tab.addEventListener("click", function () {
                selectView(tab.dataset.peopleView);
            });
        });
        elements.createGroupButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                openGroupDialog("create", null);
            });
        });
        page.querySelectorAll("[data-people-dialog-close]").forEach(function (button) {
            button.addEventListener("click", function () {
                closeDialog(button.closest("dialog"));
            });
        });
        elements.peopleSearch?.addEventListener("input", renderPeople);
        [elements.groupsSearch, elements.groupStatusFilter].forEach(function (control) {
            control?.addEventListener("input", renderGroups);
            control?.addEventListener("change", renderGroups);
        });
        elements.memberSearch?.addEventListener("input", function () {
            const group = activeGroup();
            if (group) {
                renderMemberPicker(group);
            }
        });

        elements.groupForm?.addEventListener("submit", async function (event) {
            event.preventDefault();
            const name = cleanText(elements.groupName.value);
            const description = cleanText(elements.groupDescription.value);
            elements.groupSave.disabled = true;
            try {
                const isEdit = state.groupDialogMode === "edit" && state.editingGroupId;
                const payload = await fetchJson(
                    isEdit ? ENDPOINTS.group(state.editingGroupId) : ENDPOINTS.groups,
                    {
                        method: isEdit ? "PATCH" : "POST",
                        headers: {"Content-Type": "application/json"},
                        body: JSON.stringify({name: name, description: description})
                    }
                );
                closeDialog(elements.groupDialog);
                setStatus(isEdit ? "Group updated." : "Group created.", "success");
                await loadData(payload.group?.group_id || state.editingGroupId);
            } catch (error) {
                setStatus(error.message, "error");
            } finally {
                elements.groupSave.disabled = false;
            }
        });

        elements.membersForm?.addEventListener("submit", async function (event) {
            event.preventDefault();
            const group = activeGroup();
            if (!group) {
                return;
            }

            const userIds = Array.from(
                elements.memberPicker.querySelectorAll('[data-people-member-choice]:checked')
            )
                .map(function (input) { return Number(input.value); })
                .filter(Number.isFinite);
            const email = cleanText(elements.memberEmail?.value);

            if (!userIds.length && !email) {
                setStatus(
                    "Select someone already in Solomon or enter an email address.",
                    "error"
                );
                return;
            }

            elements.addMembersSubmit.disabled = true;
            if (elements.memberInviteResult) {
                elements.memberInviteResult.hidden = true;
                elements.memberInviteResult.textContent = "";
            }

            try {
                const payload = await fetchJson(ENDPOINTS.groupMembers(group.group_id), {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({
                        user_ids: userIds,
                        email: email,
                        role: "member"
                    })
                });

                const invitation = payload.invitation;
                await loadData(group.group_id);

                if (invitation && invitation.mode === "invited") {
                    if (elements.memberInviteResult) {
                        clearElement(elements.memberInviteResult);
                        elements.memberInviteResult.appendChild(createElement(
                            "span",
                            "",
                            `Invite sent to ${invitation.email || email}.`
                        ));
                        const inviteUrl = cleanText(
                            invitation.absolute_accept_url || invitation.accept_url
                        );
                        if (inviteUrl) {
                            const copy = createElement(
                                "button",
                                "people-inline-copy-action",
                                "Copy link"
                            );
                            copy.type = "button";
                            copy.addEventListener("click", async function () {
                                try {
                                    await copyText(inviteUrl);
                                    copy.textContent = "Copied";
                                } catch (error) {
                                    setStatus(error.message, "error");
                                }
                            });
                            elements.memberInviteResult.appendChild(copy);
                        }
                        elements.memberInviteResult.className = "people-invite-result is-success";
                        elements.memberInviteResult.hidden = false;
                    }
                    if (elements.memberEmail) {
                        elements.memberEmail.value = "";
                    }
                    renderMemberPicker(activeGroup());
                    setStatus("Invite sent.", "success");
                } else {
                    closeDialog(elements.membersDialog);
                    setStatus(payload.message || "People added.", "success");
                }
            } catch (error) {
                if (elements.memberInviteResult && email) {
                    elements.memberInviteResult.textContent = error.message;
                    elements.memberInviteResult.className = "people-invite-result is-error";
                    elements.memberInviteResult.hidden = false;
                }
                setStatus(error.message, "error");
            } finally {
                elements.addMembersSubmit.disabled = false;
            }
        });

        selectView(
            initialView === "groups"
                ? "groups"
                : (page.dataset.peopleActiveView || "people")
        );
        loadData(initialGroupId);
        return true;
    }

    function initializeCurrentPeoplePage() {
        return initializePeoplePage(document);
    }

    registry.initialize = initializePeoplePage;
    registry.initializeCurrent = initializeCurrentPeoplePage;

    if (!registry.lifecycleBound) {
        registry.lifecycleBound = true;
        document.addEventListener("solomon:workspace-loaded", function (event) {
            initializePeoplePage(event?.detail?.mount || document);
        });
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initializeCurrentPeoplePage, {once: true});
    } else {
        initializeCurrentPeoplePage();
    }
}());
