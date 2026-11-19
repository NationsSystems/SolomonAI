/* -------------------------------------------------------------------
   FILE: command_sidebar_people_invite.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const namespace = "NationsCommandSidebar";
    const api = window[namespace] =
        window[namespace] || {};

    if (api.__peopleInviteLoaded) {
        return;
    }

    api.__peopleInviteLoaded = true;

    const SELECTORS = {
        trigger: "[data-command-people-invite-trigger]",
        dialog: "[data-command-people-invite-dialog]",
        close: "[data-command-people-invite-close]",
        form: "[data-command-people-invite-form]",
        submit: "[data-command-people-invite-submit]",
        result: "[data-command-people-invite-result]",
        accountMenu: "[data-command-account-menu]",
        accountTrigger: "[data-command-account-trigger]",
        helpMenu: "[data-command-help-menu]",
        helpTrigger: "[data-command-help-trigger]"
    };

    const GROUP_ID_ATTRIBUTES = [
        "data-command-group-id",
        "data-command-people-group-id",
        "data-command-group-guid",
        "data-group-id",
        "data-group-guid"
    ];

    const ENDPOINTS = {
        groups: "/people/groups"
    };

    let lastFocusedElement = null;

    function cleanText(value) {
        return String(value || "").trim();
    }

    function getElements() {
        return {
            triggers: Array.from(
                document.querySelectorAll(SELECTORS.trigger)
            ),
            dialog: document.querySelector(SELECTORS.dialog),
            closeButtons: Array.from(
                document.querySelectorAll(SELECTORS.close)
            ),
            form: document.querySelector(SELECTORS.form),
            submit: document.querySelector(SELECTORS.submit),
            result: document.querySelector(SELECTORS.result),
            accountMenu: document.querySelector(SELECTORS.accountMenu),
            accountTrigger: document.querySelector(SELECTORS.accountTrigger),
            helpMenu: document.querySelector(SELECTORS.helpMenu),
            helpTrigger: document.querySelector(SELECTORS.helpTrigger)
        };
    }

    function readAttributeValue(element, attributeNames) {
        if (!element) {
            return "";
        }

        for (const attributeName of attributeNames) {
            const value = cleanText(
                element.getAttribute(attributeName)
            );

            if (value) {
                return value;
            }
        }

        return "";
    }

    function resolveGroupId(elements) {
        const candidates = [
            elements?.form,
            elements?.dialog,
            ...(elements?.triggers || []),
            document.body,
            document.documentElement
        ];

        for (const candidate of candidates) {
            const groupId = readAttributeValue(
                candidate,
                GROUP_ID_ATTRIBUTES
            );

            if (groupId) {
                return groupId;
            }
        }

        return "";
    }

    function buildInviteEndpoint(elements) {
        const groupId = resolveGroupId(elements);

        if (!groupId) {
            return "";
        }

        return (
            `${ENDPOINTS.groups}/` +
            `${encodeURIComponent(groupId)}/invitations`
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

    function clearElement(element) {
        if (!element) {
            return;
        }

        while (element.firstChild) {
            element.removeChild(element.firstChild);
        }
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

    function closeOpenPopover(menu, trigger) {
        if (menu) {
            menu.hidden = true;
        }

        if (trigger) {
            trigger.setAttribute("aria-expanded", "false");
        }
    }

    function closeWorkspacePopovers(elements) {
        closeOpenPopover(
            elements.accountMenu,
            elements.accountTrigger
        );
        closeOpenPopover(
            elements.helpMenu,
            elements.helpTrigger
        );
    }

    function setInviteFormVisible(elements, isVisible) {
        if (!elements.form) {
            return;
        }

        elements.form.hidden = !isVisible;

        if (isVisible && elements.form.style.display === "none") {
            elements.form.style.display = "";
        }
    }

    function setDialogOpen(elements, isOpen) {
        if (!elements.dialog) {
            return;
        }

        elements.dialog.hidden = !isOpen;

        elements.triggers.forEach(function (trigger) {
            trigger.setAttribute(
                "aria-expanded",
                isOpen ? "true" : "false"
            );
        });

        if (isOpen) {
            lastFocusedElement = document.activeElement;
            closeWorkspacePopovers(elements);
            setInviteFormVisible(
                elements,
                true
            );

            const emailInput = elements.form
                ? elements.form.querySelector("input[name='email']")
                : null;

            window.setTimeout(function () {
                if (emailInput) {
                    emailInput.focus();
                }
            }, 0);
        } else if (
            lastFocusedElement &&
            typeof lastFocusedElement.focus === "function"
        ) {
            lastFocusedElement.focus();
            lastFocusedElement = null;
        }
    }

    function resetResult(result) {
        if (!result) {
            return;
        }

        clearElement(result);
        result.hidden = true;
        result.classList.remove(
            "is-success",
            "is-error"
        );
    }

    function resolveEmailDeliveryText(emailDelivery) {
        if (
            emailDelivery &&
            emailDelivery.sent === true
        ) {
            return "The invitation email was sent. The recipient can open the email and continue through the secure acceptance page.";
        }

        if (
            emailDelivery &&
            emailDelivery.enabled === true &&
            emailDelivery.attempted === true
        ) {
            return "The invite link was created, but email delivery did not complete. Copy the link and send it manually.";
        }

        if (
            emailDelivery &&
            emailDelivery.enabled === false
        ) {
            return "The invite link was created. Email delivery is currently disabled, so copy and send the link manually.";
        }

        return "The invite link was created. Keep the link available in case you need to send it manually.";
    }

    function renderStatusLine(result, text) {
        if (!text) {
            return;
        }

        const status = createElement(
            "p",
            "command-people-invite-result-status",
            text
        );

        result.appendChild(status);
    }

    function renderResultActions(options) {
        const actions = createElement(
            "div",
            "command-people-invite-result-actions"
        );

        if (options.inviteUrl) {
            const copyButton = createElement(
                "button",
                "command-people-invite-secondary",
                "Copy Invite Link"
            );

            copyButton.type = "button";
            copyButton.addEventListener("click", function () {
                copyInviteUrl(
                    options.inviteUrl,
                    copyButton
                );
            });

            actions.appendChild(copyButton);
        }

        if (options.allowInviteAnother) {
            const inviteAnotherButton = createElement(
                "button",
                "command-people-invite-secondary",
                "Invite Another Person"
            );

            inviteAnotherButton.type = "button";
            inviteAnotherButton.addEventListener("click", function () {
                resetResult(
                    options.result
                );
                setInviteFormVisible(
                    options.elements,
                    true
                );

                if (options.elements.form) {
                    options.elements.form.reset();

                    const emailInput = options.elements.form.querySelector(
                        "input[name='email']"
                    );

                    if (emailInput) {
                        emailInput.focus();
                    }
                }
            });

            actions.appendChild(inviteAnotherButton);
        }

        const manageLink = createElement(
            "a",
            "command-people-invite-secondary",
            "Manage People"
        );

        manageLink.href = "/people";
        actions.appendChild(manageLink);

        if (options.elements) {
            const doneButton = createElement(
                "button",
                "command-people-invite-primary",
                "Done"
            );

            doneButton.type = "button";
            doneButton.addEventListener("click", function () {
                setDialogOpen(
                    options.elements,
                    false
                );
            });

            actions.appendChild(doneButton);
        }

        options.result.appendChild(actions);
    }

    function renderResult(options) {
        const result = options.result;

        if (!result) {
            return;
        }

        clearElement(result);
        result.hidden = false;
        result.classList.remove(
            "is-success",
            "is-error"
        );

        if (options.mode === "success") {
            result.classList.add("is-success");
        }

        if (options.mode === "error") {
            result.classList.add("is-error");
        }

        if (options.title) {
            const title = createElement(
                "h3",
                "command-people-invite-result-title",
                options.title
            );

            result.appendChild(title);
        }

        const message = createElement(
            "p",
            "command-people-invite-result-message",
            options.message || ""
        );

        result.appendChild(message);

        if (options.statusText) {
            renderStatusLine(
                result,
                options.statusText
            );
        }

        if (options.inviteUrl) {
            const linkValue = createElement(
                "code",
                "command-people-invite-copy-value",
                options.inviteUrl
            );

            result.appendChild(linkValue);
        }

        if (options.mode === "success") {
            renderResultActions({
                result: result,
                elements: options.elements,
                inviteUrl: options.inviteUrl,
                allowInviteAnother: true
            });
        } else if (options.inviteUrl) {
            renderResultActions({
                result: result,
                elements: options.elements,
                inviteUrl: options.inviteUrl,
                allowInviteAnother: false
            });
        }
    }

    async function copyInviteUrl(inviteUrl, button) {
        const originalText = button.textContent;

        try {
            if (
                navigator.clipboard &&
                typeof navigator.clipboard.writeText === "function"
            ) {
                await navigator.clipboard.writeText(inviteUrl);
                button.textContent = "Copied";
            } else {
                window.prompt(
                    "Copy invite link:",
                    inviteUrl
                );
            }
        } catch (error) {
            window.prompt(
                "Copy invite link:",
                inviteUrl
            );
        }

        window.setTimeout(function () {
            button.textContent = originalText;
        }, 1400);
    }

    function roleIsAllowed(role) {
        return [
            "admin",
            "member",
            "guest"
        ].indexOf(role) !== -1;
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
            throw new Error(
                payload.error ||
                "The request could not be completed."
            );
        }

        return payload;
    }

    function resolveInviteUrl(payload) {
        return buildAbsoluteInviteUrl(
            payload.absolute_accept_url ||
            payload.accept_url ||
            ""
        );
    }

    function resolveSuccessMessage(payload) {
        const emailDelivery = payload.email_delivery || {};

        if (emailDelivery.sent === true) {
            return payload.message || "Invite email sent.";
        }

        return payload.message || "Invite link created.";
    }

    async function submitInvite(event, elements) {
        event.preventDefault();

        if (
            !elements.form ||
            !elements.submit ||
            !elements.result
        ) {
            return;
        }

        const formData = new FormData(elements.form);
        const email = cleanText(formData.get("email"));
        const role = cleanText(formData.get("role")).toLowerCase();
        const groupId = resolveGroupId(elements);
        const inviteEndpoint = buildInviteEndpoint(elements);
        const originalText = elements.submit.textContent;

        resetResult(elements.result);

        if (!groupId || !inviteEndpoint) {
            renderResult({
                result: elements.result,
                elements: elements,
                mode: "error",
                title: "Group context unavailable",
                message: "Open a group before sending an invitation."
            });
            return;
        }

        if (!email) {
            renderResult({
                result: elements.result,
                elements: elements,
                mode: "error",
                title: "Email required",
                message: "Enter an email address."
            });
            return;
        }

        if (!roleIsAllowed(role)) {
            renderResult({
                result: elements.result,
                elements: elements,
                mode: "error",
                title: "Role required",
                message: "Choose a valid role."
            });
            return;
        }

        elements.submit.disabled = true;
        elements.submit.textContent = "Sending...";

        try {
            const payload = await fetchJson(
                inviteEndpoint,
                {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json"
                    },
                    body: JSON.stringify({
                        email: email,
                        role: role,
                        group_id: groupId
                    })
                }
            );

            const inviteUrl = resolveInviteUrl(
                payload
            );
            const emailDelivery = payload.email_delivery || {};

            elements.form.reset();
            setInviteFormVisible(
                elements,
                false
            );

            renderResult({
                result: elements.result,
                elements: elements,
                mode: "success",
                title: emailDelivery.sent === true
                    ? "Invitation email sent"
                    : "Invite link ready",
                message: resolveSuccessMessage(
                    payload
                ),
                statusText: resolveEmailDeliveryText(
                    emailDelivery
                ),
                inviteUrl: inviteUrl
            });
        } catch (error) {
            renderResult({
                result: elements.result,
                elements: elements,
                mode: "error",
                title: "Invitation not sent",
                message: error.message ||
                    "The invite link could not be created."
            });
        } finally {
            elements.submit.disabled = false;
            elements.submit.textContent = originalText;
        }
    }

    function handleEscape(event, elements) {
        if (
            event.key === "Escape" &&
            elements.dialog &&
            !elements.dialog.hidden
        ) {
            setDialogOpen(
                elements,
                false
            );
        }
    }

    function initializePeopleInvite() {
        const elements = getElements();

        if (
            !elements.dialog ||
            !elements.form ||
            !elements.triggers.length
        ) {
            return;
        }

        if (elements.dialog.dataset.peopleInviteInitialized === "true") {
            return;
        }

        elements.dialog.dataset.peopleInviteInitialized = "true";

        elements.triggers.forEach(function (trigger) {
            trigger.addEventListener("click", function () {
                resetResult(elements.result);
                setInviteFormVisible(
                    elements,
                    true
                );
                setDialogOpen(
                    elements,
                    true
                );
            });
        });

        elements.closeButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                setDialogOpen(
                    elements,
                    false
                );
            });
        });

        elements.form.addEventListener("submit", function (event) {
            submitInvite(
                event,
                elements
            );
        });

        document.addEventListener("keydown", function (event) {
            handleEscape(
                event,
                elements
            );
        });
    }

    api.initializePeopleInvite = initializePeopleInvite;

    if (document.readyState === "loading") {
        document.addEventListener(
            "DOMContentLoaded",
            initializePeopleInvite,
            { once: true }
        );
    } else {
        initializePeopleInvite();
    }
}());