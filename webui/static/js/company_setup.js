/* -------------------------------------------------------------------
   FILE: company_setup.js
   DIRECTORY: webui/static/js/
   -------------------------------------------------------------------
   Client transport for the commercial account company setup screen.

   Authority remains server-side in /company/setup. This script only handles
   form validation, workspace ID preview, request submission, and redirect
   display.
------------------------------------------------------------------- */

(function () {
    "use strict";

    const form = document.getElementById("companySetupForm");
    const companyNameInput = document.getElementById("companyName");
    const companySlugInput = document.getElementById("companySlug");
    const submitButton = document.getElementById("companySetupBtn");
    const output = document.getElementById("companySetupOutput");
    const workspaceIdPreview = document.getElementById("subdomainPreview");
    const companyNameError = document.getElementById("error-companyName");
    const companySlugError = document.getElementById("error-companySlug");

    if (
        !form ||
        !companyNameInput ||
        !companySlugInput ||
        !submitButton ||
        !output ||
        !workspaceIdPreview ||
        !companyNameError ||
        !companySlugError
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

    function setError(element, message) {
        element.textContent = message || "";
        element.hidden = !message;
    }

    function setOutput(message) {
        output.textContent = message || "";
        output.hidden = !message;
    }

    function setLoading(isLoading) {
        submitButton.disabled = isLoading || !isFormValid();
        submitButton.textContent = isLoading
            ? "Creating Company Workspace..."
            : "Create Company Workspace";
    }

    function isValidWorkspaceId(workspaceId) {
        return /^[a-z0-9][a-z0-9-]{1,46}[a-z0-9]$/.test(workspaceId);
    }

    function syncWorkspaceIdFromCompanyName() {
        if (companySlugInput.dataset.userEdited === "true") {
            return;
        }

        companySlugInput.value = buildSlug(companyNameInput.value);
    }

    function isFormValid() {
        const companyName = cleanValue(companyNameInput.value);
        const workspaceId = buildSlug(companySlugInput.value);

        return companyName.length > 0 && isValidWorkspaceId(workspaceId);
    }

    function renderValidation() {
        const companyName = cleanValue(companyNameInput.value);
        const workspaceId = buildSlug(companySlugInput.value);

        setError(
            companyNameError,
            companyName ? "" : "Company name is required."
        );

        setError(
            companySlugError,
            isValidWorkspaceId(workspaceId)
                ? ""
                : "Use 3 to 48 lowercase letters, numbers, or hyphens."
        );

        if (workspaceId) {
            workspaceIdPreview.textContent = `Workspace ID: ${workspaceId}`;
            workspaceIdPreview.hidden = false;
        } else {
            workspaceIdPreview.textContent = "";
            workspaceIdPreview.hidden = true;
        }

        submitButton.disabled = !isFormValid();
    }

    async function submitCompanySetup(event) {
        event.preventDefault();

        syncWorkspaceIdFromCompanyName();
        renderValidation();
        setOutput("");

        if (!isFormValid()) {
            return;
        }

        const payload = {
            company_name: cleanValue(companyNameInput.value),
            company_slug: buildSlug(companySlugInput.value)
        };

        setLoading(true);

        try {
            const response = await fetch("/company/setup", {
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
                setOutput(result.error || "Company setup could not be completed.");
                setLoading(false);
                return;
            }

            setOutput(result.message || "Company setup completed successfully.");

            window.location.assign(result.redirect || "/");
        } catch (error) {
            setOutput("Company setup could not be completed. Check your connection and try again.");
            setLoading(false);
        }
    }

    companyNameInput.addEventListener("input", function () {
        syncWorkspaceIdFromCompanyName();
        renderValidation();
    });

    companySlugInput.addEventListener("input", function () {
        companySlugInput.dataset.userEdited = "true";
        companySlugInput.value = buildSlug(companySlugInput.value);
        renderValidation();
    });

    form.addEventListener("submit", submitCompanySetup);

    output.hidden = true;
    workspaceIdPreview.hidden = true;
    companyNameError.hidden = true;
    companySlugError.hidden = true;

    syncWorkspaceIdFromCompanyName();
    renderValidation();
}());