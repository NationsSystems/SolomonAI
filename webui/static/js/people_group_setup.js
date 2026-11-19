/* -------------------------------------------------------------------
   FILE: people_group_setup.js
   DIRECTORY: webui/static/js/
   -------------------------------------------------------------------
   Client transport for the people group setup screen.

   Authority remains server-side in canonical /people group routes. This
   script only handles form validation, group ID preview, request submission,
   and redirect display.
------------------------------------------------------------------- */

(function () {
    "use strict";

    const form = document.querySelector("[data-people-group-setup-form]");
    const groupNameInput = document.getElementById("groupName");
    const groupSlugInput = document.getElementById("groupSlug");
    const submitButton = document.querySelector("[data-people-group-setup-submit]");
    const output = document.querySelector("[data-people-group-setup-output]");
    const groupSlugPreview = document.querySelector("[data-people-group-slug-preview]");
    const groupNameError = document.getElementById("error-groupName");
    const groupSlugError = document.getElementById("error-groupSlug");

    if (
        !form ||
        !groupNameInput ||
        !groupSlugInput ||
        !submitButton ||
        !output ||
        !groupSlugPreview ||
        !groupNameError ||
        !groupSlugError
    ) {
        return;
    }

    function cleanValue(value) {
        return String(value || "")
            .replace(/\s+/g, " ")
            .trim();
    }

    function buildSlug(value) {
        return cleanValue(value)
            .toLowerCase()
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "")
            .slice(0, 48)
            .replace(/-+$/g, "");
    }

    function setupEndpoint() {
        return cleanValue(
            form.getAttribute("data-people-group-setup-endpoint")
        ) || "/people/groups";
    }

    function setError(element, message) {
        element.textContent = message || "";
        element.hidden = !message;
    }

    function setOutput(message) {
        output.textContent = message || "";
        output.hidden = !message;
    }

    function isValidGroupId(groupId) {
        return /^[a-z0-9][a-z0-9-]{1,46}[a-z0-9]$/.test(groupId);
    }

    function isFormValid() {
        const groupName = cleanValue(groupNameInput.value);
        const groupId = buildSlug(groupSlugInput.value);

        return groupName.length > 0 && isValidGroupId(groupId);
    }

    function setLoading(isLoading) {
        submitButton.disabled = isLoading || !isFormValid();
        submitButton.textContent = isLoading
            ? "Creating Group Workspace..."
            : "Create Group Workspace";
    }

    function syncGroupIdFromGroupName() {
        if (groupSlugInput.dataset.userEdited === "true") {
            return;
        }

        groupSlugInput.value = buildSlug(groupNameInput.value);
    }

    function renderValidation() {
        const groupName = cleanValue(groupNameInput.value);
        const groupId = buildSlug(groupSlugInput.value);

        setError(
            groupNameError,
            groupName ? "" : "Group name is required."
        );

        setError(
            groupSlugError,
            isValidGroupId(groupId)
                ? ""
                : "Use 3 to 48 lowercase letters, numbers, or hyphens."
        );

        if (groupId) {
            groupSlugPreview.textContent = `Group ID: ${groupId}`;
            groupSlugPreview.hidden = false;
        } else {
            groupSlugPreview.textContent = "";
            groupSlugPreview.hidden = true;
        }

        submitButton.disabled = !isFormValid();
    }

    async function submitPeopleGroupSetup(event) {
        event.preventDefault();

        syncGroupIdFromGroupName();
        renderValidation();
        setOutput("");

        if (!isFormValid()) {
            return;
        }

        const payload = {
            group_name: cleanValue(groupNameInput.value),
            group_slug: buildSlug(groupSlugInput.value)
        };

        setLoading(true);

        try {
            const response = await fetch(setupEndpoint(), {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const result = await response.json().catch(function () {
                return {};
            });

            if (!response.ok || !result.ok) {
                setOutput(result.error || "Group setup could not be completed.");
                setLoading(false);
                return;
            }

            setOutput(result.message || "Group setup completed successfully.");

            window.location.assign(result.redirect || "/people");
        } catch (error) {
            setOutput("Group setup could not be completed. Check your connection and try again.");
            setLoading(false);
        }
    }

    groupNameInput.addEventListener("input", function () {
        syncGroupIdFromGroupName();
        renderValidation();
    });

    groupSlugInput.addEventListener("input", function () {
        groupSlugInput.dataset.userEdited = "true";
        groupSlugInput.value = buildSlug(groupSlugInput.value);
        renderValidation();
    });

    form.addEventListener("submit", submitPeopleGroupSetup);

    output.hidden = true;
    groupSlugPreview.hidden = true;
    groupNameError.hidden = true;
    groupSlugError.hidden = true;

    syncGroupIdFromGroupName();
    renderValidation();
}());