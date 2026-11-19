/* -------------------------------------------------------------------
   FILE: command_sidebar_navigation.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const api = window.NationsCommandSidebar =
        window.NationsCommandSidebar || {};

    const SOLOMON_LAUNCHER_ID =
        "commandSolomonLauncher";

    const WORKSPACE_NAVIGATION_CONTRACT =
        "workspace_module_section_route";
    const WORKSPACE_IDENTITIES = Object.freeze({
        documents: Object.freeze({
            moduleId: "documents",
            href: "/"
        }),
        search: Object.freeze({
            moduleId: "search",
            href: "/search"
        }),
        solomonAi: Object.freeze({
            moduleId: "solomon_ai",
            href: "/ai"
        }),
        people: Object.freeze({
            moduleId: "people",
            href: "/people"
        })
    });
    const DOCUMENT_SECTION_IDENTITIES = Object.freeze({
        files: Object.freeze({
            sectionId: "files",
            href: "/"
        }),
        reports: Object.freeze({
            sectionId: "reports",
            href: "/reports"
        }),
        recent: Object.freeze({
            sectionId: "recent",
            href: "/recent"
        }),
        shared: Object.freeze({
            sectionId: "shared",
            href: "/shared"
        }),
        trash: Object.freeze({
            sectionId: "trash",
            href: "/trash"
        })
    });
    const DOCUMENT_WORKSPACE_PATHS = new Set([
        DOCUMENT_SECTION_IDENTITIES.files.href,
        DOCUMENT_SECTION_IDENTITIES.reports.href,
        DOCUMENT_SECTION_IDENTITIES.recent.href,
        DOCUMENT_SECTION_IDENTITIES.trash.href
    ]);
    const WORKSPACE_WINDOW_CLOSE_SELECTOR =
        "[data-command-window-close='true']";
    const LEGACY_WORKSPACE_CLOSE_SELECTOR =
        "[data-workspace-page-close='true']";
    const WORKSPACE_MOUNT_CLOSEABLE_ATTRIBUTE =
        "data-workspace-closeable";
    const WORKSPACE_CURRENT_FOLDER_ATTRIBUTE =
        "data-workspace-current-folder-id";
    const WORKSPACE_RETURN_ROUTE_ATTRIBUTE =
        "data-workspace-return-route";

    function normalizeCommandPathname(value) {
        const rawValue =
            String(value || "").trim();

        if (!rawValue) {
            return "/";
        }

        try {
            const parsedUrl =
                new URL(
                    rawValue,
                    window.location.origin
                );
            const pathname =
                parsedUrl.pathname
                    .trim()
                    .toLowerCase()
                    .replace(/\/+$/, "");

            return pathname || "/";
        } catch (_error) {
            const pathname =
                rawValue
                    .split("#", 1)[0]
                    .split("?", 1)[0]
                    .trim()
                    .toLowerCase()
                    .replace(/\/+$/, "");

            return pathname || "/";
        }
    }

    function normalizeCommandSection(value) {
        const sectionId =
            String(value || "")
                .trim()
                .toLowerCase();

        return Object.prototype.hasOwnProperty.call(
            DOCUMENT_SECTION_IDENTITIES,
            sectionId
        )
            ? sectionId
            : "";
    }

    function getDocumentSectionIdentity(pathname) {
        const cleanPath =
            normalizeCommandPathname(pathname);

        for (
            const identity of Object.values(
                DOCUMENT_SECTION_IDENTITIES
            )
        ) {
            if (identity.href === cleanPath) {
                return identity;
            }
        }

        if (isDocumentReaderPath(cleanPath)) {
            return DOCUMENT_SECTION_IDENTITIES.files;
        }

        return null;
    }

    function isDocumentsHomePath(pathname) {
        return (
            normalizeCommandPathname(pathname) ===
            DOCUMENT_SECTION_IDENTITIES
                .files.href
        );
    }

    function isDocumentReaderPath(pathname) {
        const cleanPath =
            normalizeCommandPathname(pathname);

        return (
            cleanPath.startsWith("/workspace/file/") ||
            cleanPath.startsWith("/workspace/document/")
        );
    }

    function isDocumentsPath(pathname) {
        const cleanPath =
            normalizeCommandPathname(pathname);

        return (
            DOCUMENT_WORKSPACE_PATHS.has(cleanPath) ||
            isDocumentReaderPath(cleanPath)
        );
    }

    function isSearchPath(pathname) {
        return (
            normalizeCommandPathname(pathname) ===
            WORKSPACE_IDENTITIES
                .search.href
        );
    }

    function isSolomonAiPath(pathname) {
        const cleanPath =
            normalizeCommandPathname(pathname);
        const solomonPath =
            WORKSPACE_IDENTITIES
                .solomonAi.href;

        return (
            cleanPath === solomonPath ||
            cleanPath.startsWith(
                `${solomonPath}/c/`
            )
        );
    }

    function isPeoplePath(pathname) {
        const cleanPath =
            normalizeCommandPathname(pathname);
        const peoplePath =
            WORKSPACE_IDENTITIES
                .people.href;

        return (
            cleanPath === peoplePath ||
            cleanPath.startsWith(
                `${peoplePath}/`
            )
        );
    }

    function isWorkspaceShellPath(pathname) {
        return (
            isDocumentsPath(pathname) ||
            isSearchPath(pathname) ||
            isSolomonAiPath(pathname) ||
            isPeoplePath(pathname)
        );
    }

    function isWorkspaceShellLink(link, pathname) {
        const moduleId =
            String(
                link?.getAttribute(
                    "data-command-module"
                ) || ""
            )
                .trim()
                .toLowerCase();
        const shellNavigation =
            link?.getAttribute(
                "data-command-shell-navigation"
            ) === "true";

        if (!isWorkspaceShellPath(pathname)) {
            return false;
        }

        if (
            isDocumentsPath(pathname) &&
            moduleId ===
                WORKSPACE_IDENTITIES
                    .documents.moduleId
        ) {
            return true;
        }

        if (
            isSearchPath(pathname) &&
            moduleId ===
                WORKSPACE_IDENTITIES
                    .search.moduleId
        ) {
            return true;
        }

        if (
            isSolomonAiPath(pathname) &&
            moduleId ===
                WORKSPACE_IDENTITIES
                    .solomonAi.moduleId
        ) {
            return true;
        }

        if (
            isPeoplePath(pathname) &&
            moduleId ===
                WORKSPACE_IDENTITIES
                    .people.moduleId
        ) {
            return true;
        }

        return shellNavigation;
    }

    function createSolomonPromptList(actions) {
        const list = document.createElement("ul");

        list.className =
            "solomon-workspace-conversation-message-prompts";
        list.setAttribute(
            "aria-label",
            "Suggested follow-up prompts"
        );
        list.setAttribute(
            "data-solomon-workspace-conversation-prompts",
            ""
        );

        actions.forEach(function (action) {
            const label = String(
                action?.label || ""
            ).trim();

            if (!label) {
                return;
            }

            const item =
                document.createElement("li");

            item.className =
                "solomon-workspace-conversation-prompt";
            item.setAttribute(
                "data-solomon-workspace-conversation-prompt",
                ""
            );
            item.textContent = label;

            list.append(item);
        });

        return list;
    }

    function escapeSolomonPattern(value) {
        return String(value || "").replace(
            /[.*+?^${}()|[\]\\]/g,
            "\\$&"
        );
    }

    function normalizeSolomonMessageContent(value) {
        return String(value || "")
            .replace(/\r\n?/g, "\n")
            .trim();
    }

    function normalizeSolomonBodyText(value) {
        return String(value || "")
            .replace(/[ \t]+/g, " ")
            .replace(/\s*\n\s*/g, " ")
            .trim();
    }

    function splitSolomonAssistantHeading(content) {
        const cleanContent =
            normalizeSolomonMessageContent(content);
        const lines = cleanContent
            .split("\n")
            .map(function (line) {
                return line.trim();
            })
            .filter(Boolean);
        const headingPattern =
            /^(Summary|Key Details|Comparison)\s*[—–-]\s*(.+)$/i;

        if (
            lines.length > 1 &&
            headingPattern.test(lines[0])
        ) {
            return {
                heading: lines[0],
                body: lines.slice(1).join("\n")
            };
        }

        const titledHeadingMatch =
            cleanContent.match(
                /^((?:Summary|Key Details|Comparison)\s*[—–-]\s*(.+?\.(?:pdf|docx?|xlsx?|csv|txt|rtf|png|jpe?g|webp|gif|tiff?)))\s+([\s\S]+)$/i
            );

        if (titledHeadingMatch) {
            const heading =
                titledHeadingMatch[1].trim();
            const title =
                titledHeadingMatch[2].trim();
            let body =
                titledHeadingMatch[3].trim();
            const repeatedTitlePattern =
                new RegExp(
                    `^${escapeSolomonPattern(
                        title
                    )}(?:\\s+|$)`,
                    "i"
                );

            body = body.replace(
                repeatedTitlePattern,
                ""
            ).trim();

            return {
                heading,
                body
            };
        }

        const selectedFilesHeadingMatch =
            cleanContent.match(
                /^((?:Summary|Comparison)\s*[—–-]\s*Selected Files)\s+([\s\S]+)$/i
            );

        if (selectedFilesHeadingMatch) {
            return {
                heading:
                    selectedFilesHeadingMatch[
                        1
                    ].trim(),
                body:
                    selectedFilesHeadingMatch[
                        2
                    ].trim()
            };
        }

        return {
            heading: "",
            body: cleanContent
        };
    }

    function createSolomonMessageParagraph(value) {
        const paragraph =
            document.createElement("p");

        paragraph.className = [
            "solomon-workspace-conversation-message-text",
            "solomon-workspace-conversation-message-paragraph"
        ].join(" ");
        paragraph.textContent =
            normalizeSolomonBodyText(value);

        return paragraph;
    }

    function createSolomonMessageList(
        lines,
        ordered
    ) {
        const list = document.createElement(
            ordered ? "ol" : "ul"
        );

        list.className = [
            "solomon-workspace-conversation-message-list",
            ordered
                ? "solomon-workspace-conversation-message-list--ordered"
                : "solomon-workspace-conversation-message-list--unordered"
        ].join(" ");

        lines.forEach(function (line) {
            const item =
                document.createElement("li");
            const cleanLine = ordered
                ? line.replace(
                    /^\d+[.)]\s+/,
                    ""
                )
                : line.replace(
                    /^[-*•]\s+/,
                    ""
                );

            item.className =
                "solomon-workspace-conversation-message-list-item";
            item.textContent =
                normalizeSolomonBodyText(
                    cleanLine
                );
            list.append(item);
        });

        return list;
    }

    function appendSolomonMessageBlocks(
        container,
        content
    ) {
        const cleanContent =
            normalizeSolomonMessageContent(content);

        if (!cleanContent) {
            return;
        }

        const blocks = cleanContent
            .split(/\n\s*\n/)
            .map(function (block) {
                return block.trim();
            })
            .filter(Boolean);

        blocks.forEach(function (block) {
            const lines = block
                .split("\n")
                .map(function (line) {
                    return line.trim();
                })
                .filter(Boolean);
            const unordered =
                lines.length > 1 &&
                lines.every(function (line) {
                    return /^[-*•]\s+/.test(
                        line
                    );
                });
            const ordered =
                lines.length > 1 &&
                lines.every(function (line) {
                    return /^\d+[.)]\s+/.test(
                        line
                    );
                });

            if (unordered || ordered) {
                container.append(
                    createSolomonMessageList(
                        lines,
                        ordered
                    )
                );
                return;
            }

            container.append(
                createSolomonMessageParagraph(
                    block
                )
            );
        });
    }

    function createSolomonMessageContent(
        role,
        content
    ) {
        const normalizedRole =
            role === "user"
                ? "user"
                : "assistant";
        const container =
            document.createElement("div");

        container.className = [
            "solomon-workspace-conversation-message-content",
            `solomon-workspace-conversation-message-content--${normalizedRole}`
        ].join(" ");
        container.setAttribute(
            "data-solomon-workspace-conversation-message-content",
            ""
        );

        if (normalizedRole === "user") {
            container.append(
                createSolomonMessageParagraph(
                    content
                )
            );
            return container;
        }

        const assistantContent =
            splitSolomonAssistantHeading(
                content
            );

        if (assistantContent.heading) {
            const heading =
                document.createElement("h3");

            heading.className =
                "solomon-workspace-conversation-message-heading";
            heading.textContent =
                assistantContent.heading;
            container.append(heading);
        }

        appendSolomonMessageBlocks(
            container,
            assistantContent.body
        );

        return container;
    }

    api.getWorkspaceUserLabel = function () {
        const explorer =
            document.querySelector(
                api.constants
                    .DOCUMENT_EXPLORER_SELECTOR
            );
        const label = String(
            explorer?.getAttribute(
                "data-user-display-name"
            ) || ""
        ).trim();

        return label || "You";
    };

    api.storeSolomonMessage = function (
        role,
        content,
        options
    ) {
        if (
            options?.store === false ||
            options?.state === "pending"
        ) {
            return;
        }

        api.state.solomonConversationMessages.push({
            role,
            content,
            options: {
                state: options?.state || "",
                variant:
                    options?.variant || "",
                label: options?.label || "",
                bridge:
                    options?.bridge || "",
                actions:
                    Array.isArray(
                        options?.actions
                    )
                        ? options.actions
                        : []
            }
        });
    };

    api.appendSolomonMessage = function (
        role,
        content,
        options
    ) {
        const elements =
            api.getWorkspaceConversationElements();

        if (!content) {
            return null;
        }

        api.storeSolomonMessage(
            role,
            content,
            options || {}
        );

        if (!elements.thread) {
            api.syncSolomonHistoryState();
            return null;
        }

        if (elements.empty) {
            elements.empty.hidden = true;
        }

        const normalizedRole =
            role === "user"
                ? "user"
                : "assistant";
        const message =
            document.createElement("article");

        message.className = [
            "solomon-workspace-conversation-message",
            `solomon-workspace-conversation-message--${normalizedRole}`
        ].join(" ");

        message.setAttribute(
            "data-solomon-workspace-conversation-message",
            ""
        );
        message.setAttribute(
            "data-solomon-message-role",
            normalizedRole
        );

        if (options?.state) {
            message.setAttribute(
                "data-solomon-message-state",
                options.state
            );
        }

        if (options?.variant) {
            message.setAttribute(
                "data-solomon-message-variant",
                options.variant
            );
        }

        const label =
            document.createElement("span");
        label.className =
            "solomon-workspace-conversation-message-label";
        label.textContent =
            options?.label ||
            (
                normalizedRole === "user"
                    ? api.getWorkspaceUserLabel()
                    : "SolomonAI"
            );

        const messageContent =
            createSolomonMessageContent(
                normalizedRole,
                content
            );

        message.append(
            label,
            messageContent
        );

        if (options?.bridge) {
            const bridge =
                document.createElement("p");

            bridge.className =
                "solomon-workspace-conversation-message-bridge";
            bridge.textContent =
                options.bridge;
            message.append(bridge);
        }

        if (
            Array.isArray(
                options?.actions
            ) &&
            options.actions.length
        ) {
            const prompts =
                createSolomonPromptList(
                    options.actions
                );

            if (prompts.children.length) {
                message.append(prompts);
            }
        }

        elements.thread.append(message);
        api.syncSolomonHistoryState();
        api.scrollWorkspaceConversationThread();

        return message;
    };

    api.renderPendingConversation = function (
        userText
    ) {
        api.state.solomonConversationState =
            "pending";

        api.appendSolomonMessage(
            "user",
            userText,
            {
                state: "sent",
                variant:
                    "home_conversation",
                label:
                    api.getWorkspaceUserLabel()
            }
        );

        api.removePendingMessage();

        api.state.solomonPendingMessage =
            api.appendSolomonMessage(
                "assistant",
                "SolomonAI is thinking",
                {
                    state: "pending",
                    variant:
                        "home_conversation_pending",
                    label: "SolomonAI",
                    store: false
                }
            );

        api.syncSolomonHistoryState();
        api.setWorkspaceConversationStatus(
            "SolomonAI is thinking"
        );
    };

    api.renderConversationResponse = function (
        packet
    ) {
        const normalizedPacket =
            api.normalizeSolomonPacket(packet);

        api.removePendingMessage();
        api.state.solomonConversationState =
            normalizedPacket.ok
                ? "ready"
                : "error";

        api.appendSolomonMessage(
            "assistant",
            normalizedPacket.answer,
            {
                state:
                    normalizedPacket.ok
                        ? "ready"
                        : "error",
                variant:
                    "home_conversation",
                label: "SolomonAI",
                bridge:
                    normalizedPacket.bridge,
                actions:
                    normalizedPacket.actions
            }
        );

        api.syncSolomonHistoryState();
        api.setWorkspaceConversationStatus(
            normalizedPacket.ok
                ? "Latest SolomonAI response"
                : "Response failed"
        );

        return normalizedPacket;
    };

    api.renderConversationError = function (
        message
    ) {
        api.removePendingMessage();
        api.state.solomonConversationState =
            "error";

        api.appendSolomonMessage(
            "assistant",
            message ||
                "SolomonAI could not complete that message.",
            {
                state: "error",
                variant:
                    "home_conversation",
                label: "SolomonAI",
                bridge:
                    "Try another prompt or ask for a supported workspace direction."
            }
        );

        api.syncSolomonHistoryState();
        api.setWorkspaceConversationStatus(
            "Response failed"
        );
    };

    function getWorkspaceIdentityForModule(moduleId) {
        const normalizedModuleId =
            String(moduleId || "")
                .trim()
                .toLowerCase();

        if (
            normalizedModuleId ===
            WORKSPACE_IDENTITIES
                .search.moduleId
        ) {
            return WORKSPACE_IDENTITIES
                .search;
        }

        if (
            normalizedModuleId ===
            WORKSPACE_IDENTITIES
                .solomonAi.moduleId
        ) {
            return WORKSPACE_IDENTITIES
                .solomonAi;
        }

        if (
            normalizedModuleId ===
            WORKSPACE_IDENTITIES
                .people.moduleId
        ) {
            return WORKSPACE_IDENTITIES
                .people;
        }

        if (
            normalizedModuleId ===
            WORKSPACE_IDENTITIES
                .documents.moduleId
        ) {
            return WORKSPACE_IDENTITIES
                .documents;
        }

        return null;
    }

    function resolveWorkspaceIdentity(moduleId) {
        const explicitIdentity =
            getWorkspaceIdentityForModule(moduleId);

        if (explicitIdentity) {
            return explicitIdentity;
        }

        const mount =
            document.querySelector(
                api.constants
                    .WORKSPACE_MOUNT_SELECTOR
            );
        const hasSearchSurface =
            Boolean(
                mount?.querySelector(
                    "[data-search-results-page], .search-workspace-shell, .search-command-app"
                )
            );
        const hasSolomonAiSurface =
            Boolean(
                mount?.querySelector(
                    "[data-solomon-ai-workspace]"
                )
            );
        const hasPeopleSurface =
            Boolean(
                mount?.querySelector(
                    "[data-people-page], .people-browser, .people-command-app"
                )
            );

        if (hasSearchSurface) {
            return WORKSPACE_IDENTITIES
                .search;
        }

        if (hasSolomonAiSurface) {
            return WORKSPACE_IDENTITIES
                .solomonAi;
        }

        if (hasPeopleSurface) {
            return WORKSPACE_IDENTITIES
                .people;
        }

        return WORKSPACE_IDENTITIES
            .documents;
    }

    function getWorkspaceSurfaceSelector(moduleId) {
        const identity =
            getWorkspaceIdentityForModule(moduleId);

        if (!identity) {
            return "";
        }

        if (
            identity.moduleId ===
            WORKSPACE_IDENTITIES
                .solomonAi.moduleId
        ) {
            return [
                "[data-solomon-ai-workspace]",
                ".solomon-ai-workspace",
                ".solomon-ai-conversation",
                ".solomon-ai-sources"
            ].join(", ");
        }

        if (
            identity.moduleId ===
            WORKSPACE_IDENTITIES
                .people.moduleId
        ) {
            return [
                "[data-people-page]",
                ".people-browser",
                ".people-command-app"
            ].join(", ");
        }

        if (
            identity.moduleId ===
            WORKSPACE_IDENTITIES
                .search.moduleId
        ) {
            return [
                "[data-search-results-page]",
                ".search-workspace-shell",
                ".search-command-app",
                ".search-explorer"
            ].join(", ");
        }

        if (
            identity.moduleId ===
            WORKSPACE_IDENTITIES
                .documents.moduleId
        ) {
            return [
                ".workspace-document-explorer",
                ".workspace-command-explorer",
                "[data-workspace-module='documents']"
            ].join(", ");
        }

        return "";
    }

    function hasExpectedWorkspaceContent(
        root,
        moduleId
    ) {
        const selector =
            getWorkspaceSurfaceSelector(moduleId);

        if (!selector) {
            return true;
        }

        return Boolean(
            root?.querySelector(selector)
        );
    }

    function normalizeWorkspaceAssetUrl(value) {
        try {
            return new URL(
                String(value || ""),
                window.location.origin
            ).href;
        } catch (_error) {
            return "";
        }
    }

    function collectWorkspaceStylesheets(roots) {
        const stylesheets = [];
        const seenHrefs = new Set();

        Array.from(roots || []).forEach(function (root) {
            if (
                !root ||
                typeof root.querySelectorAll !==
                    "function"
            ) {
                return;
            }

            root.querySelectorAll(
                'link[rel~="stylesheet"][href]'
            ).forEach(function (link) {
                const href =
                    normalizeWorkspaceAssetUrl(
                        link.getAttribute("href")
                    );

                if (
                    !href ||
                    seenHrefs.has(href)
                ) {
                    return;
                }

                const stylesheet =
                    link.cloneNode(true);

                stylesheet.href = href;
                stylesheets.push(stylesheet);
                seenHrefs.add(href);
            });
        });

        return stylesheets;
    }

    function removeWorkspaceStylesheets(root) {
        if (
            !root ||
            typeof root.querySelectorAll !==
                "function"
        ) {
            return;
        }

        root.querySelectorAll(
            'link[rel~="stylesheet"][href]'
        ).forEach(function (link) {
            link.remove();
        });
    }

    function activateWorkspaceStylesheets(
        stylesheets
    ) {
        const loadedHrefs = new Set();

        document.querySelectorAll(
            'link[rel~="stylesheet"][href]'
        ).forEach(function (link) {
            const href =
                normalizeWorkspaceAssetUrl(
                    link.getAttribute("href")
                );

            if (href) {
                loadedHrefs.add(href);
            }
        });

        Array.from(stylesheets || []).forEach(
            function (stylesheet) {
                const href =
                    normalizeWorkspaceAssetUrl(
                        stylesheet.getAttribute(
                            "href"
                        )
                    );

                if (
                    !href ||
                    loadedHrefs.has(href)
                ) {
                    return;
                }

                const activatedStylesheet =
                    stylesheet.cloneNode(true);

                activatedStylesheet.href = href;
                activatedStylesheet.setAttribute(
                    "data-workspace-managed-stylesheet",
                    "true"
                );

                document.head.append(
                    activatedStylesheet
                );
                loadedHrefs.add(href);
            }
        );
    }

    function createWorkspaceFragmentFromNodes(nodes) {
        const fragment =
            document.createDocumentFragment();

        Array.from(nodes || []).forEach(function (node) {
            fragment.append(
                node.cloneNode(true)
            );
        });

        return fragment;
    }

    function readWorkspaceMountCloseability(mount) {
        const value =
            String(
                mount?.getAttribute(
                    WORKSPACE_MOUNT_CLOSEABLE_ATTRIBUTE
                ) || ""
            )
                .trim()
                .toLowerCase();

        if (value === "true") {
            return true;
        }

        if (value === "false") {
            return false;
        }

        return null;
    }

    function applyWorkspaceMountCloseability(
        mount,
        closeable
    ) {
        if (!mount) {
            return;
        }

        if (typeof closeable !== "boolean") {
            mount.removeAttribute(
                WORKSPACE_MOUNT_CLOSEABLE_ATTRIBUTE
            );
            return;
        }

        mount.setAttribute(
            WORKSPACE_MOUNT_CLOSEABLE_ATTRIBUTE,
            closeable ? "true" : "false"
        );
    }

    function createWorkspaceResponse(
        fragment,
        stylesheetRoots,
        mountCloseability
    ) {
        const stylesheets =
            collectWorkspaceStylesheets(
                stylesheetRoots
            );

        removeWorkspaceStylesheets(
            fragment
        );

        return {
            fragment,
            stylesheets,
            mountCloseability:
                typeof mountCloseability === "boolean"
                    ? mountCloseability
                    : null
        };
    }

    function createWorkspaceFragmentFromHtml(
        html,
        moduleId
    ) {
        const cleanHtml =
            String(html || "").trim();

        if (!cleanHtml) {
            return null;
        }

        if (typeof DOMParser === "function") {
            const parsedDocument =
                new DOMParser().parseFromString(
                    cleanHtml,
                    "text/html"
                );
            const parsedMount =
                parsedDocument.querySelector(
                    api.constants
                        .WORKSPACE_MOUNT_SELECTOR
                );
            const stylesheetRoots = [
                parsedDocument.head,
                parsedDocument.body
            ];

            if (
                parsedMount &&
                hasExpectedWorkspaceContent(
                    parsedMount,
                    moduleId
                )
            ) {
                return createWorkspaceResponse(
                    createWorkspaceFragmentFromNodes(
                        parsedMount.childNodes
                    ),
                    stylesheetRoots,
                    readWorkspaceMountCloseability(
                        parsedMount
                    )
                );
            }

            if (
                parsedDocument.body &&
                hasExpectedWorkspaceContent(
                    parsedDocument.body,
                    moduleId
                )
            ) {
                return createWorkspaceResponse(
                    createWorkspaceFragmentFromNodes(
                        parsedDocument.body.childNodes
                    ),
                    stylesheetRoots
                );
            }
        }

        const template =
            document.createElement("template");

        template.innerHTML = cleanHtml;

        if (
            !hasExpectedWorkspaceContent(
                template.content,
                moduleId
            )
        ) {
            return null;
        }

        return createWorkspaceResponse(
            template.content.cloneNode(true),
            [template.content]
        );
    }


    function getWorkspacePathFromOptions(options) {
        try {
            return normalizeCommandPathname(
                new URL(
                    options?.url || window.location.href,
                    window.location.origin
                ).pathname
            );
        } catch (_error) {
            return normalizeCommandPathname(
                window.location.pathname
            );
        }
    }

    function getMountedNavigationContractSurface(mount) {
        if (!mount) {
            return null;
        }

        return (
            mount.querySelector(
                `[data-document-explorer][data-workspace-navigation-contract="${WORKSPACE_NAVIGATION_CONTRACT}"]`
            ) ||
            mount.querySelector(
                `[data-workspace-current-folder-id][data-workspace-navigation-contract="${WORKSPACE_NAVIGATION_CONTRACT}"]`
            ) ||
            mount.querySelector(
                `[data-workspace-navigation-contract="${WORKSPACE_NAVIGATION_CONTRACT}"]`
            )
        );
    }

    function getMountedFolderNavigationState(mount) {
        const contractSurface =
            getMountedNavigationContractSurface(
                mount
            );
        const folderId =
            String(
                contractSurface?.getAttribute(
                    WORKSPACE_CURRENT_FOLDER_ATTRIBUTE
                ) || ""
            ).trim();
        const rawReturnRoute =
            String(
                contractSurface?.getAttribute(
                    WORKSPACE_RETURN_ROUTE_ATTRIBUTE
                ) || ""
            ).trim();
        let returnRoute =
            WORKSPACE_IDENTITIES
                .documents.href;

        if (rawReturnRoute) {
            try {
                const parsedUrl =
                    new URL(
                        rawReturnRoute,
                        window.location.origin
                    );
                const returnPath =
                    normalizeCommandPathname(
                        parsedUrl.pathname
                    );

                if (
                    parsedUrl.origin ===
                        window.location.origin &&
                    (
                        isDocumentsPath(returnPath) ||
                        isSearchPath(returnPath)
                    )
                ) {
                    returnRoute = [
                        parsedUrl.pathname,
                        parsedUrl.search,
                        parsedUrl.hash
                    ].join("");
                }
            } catch (_error) {
                returnRoute =
                    WORKSPACE_IDENTITIES
                        .documents.href;
            }
        }

        return {
            folderId,
            isFolderSurface: Boolean(folderId),
            returnRoute
        };
    }

    function resolveWorkspaceNavigationState(
        moduleId,
        options
    ) {
        const identity =
            resolveWorkspaceIdentity(moduleId);
        const mount =
            document.querySelector(
                api.constants
                    .WORKSPACE_MOUNT_SELECTOR
            );
        const contractSurface =
            getMountedNavigationContractSurface(
                mount
            );
        const renderedModuleId =
            String(
                contractSurface?.getAttribute(
                    "data-workspace-module"
                ) || ""
            )
                .trim()
                .toLowerCase();
        const requestedRoute =
            getWorkspacePathFromOptions(options);
        const renderedRoute =
            normalizeCommandPathname(
                contractSurface?.getAttribute(
                    "data-workspace-route"
                ) || requestedRoute
            );
        const routePath =
            renderedModuleId === identity.moduleId
                ? renderedRoute
                : requestedRoute;
        const renderedSection =
            normalizeCommandSection(
                contractSurface?.getAttribute(
                    "data-workspace-section"
                )
            );
        const routeSection =
            getDocumentSectionIdentity(
                routePath
            );
        const sectionId =
            identity.moduleId ===
                WORKSPACE_IDENTITIES
                    .documents.moduleId
                ? (
                    renderedModuleId ===
                        identity.moduleId &&
                    renderedSection
                        ? renderedSection
                        : routeSection?.sectionId || ""
                )
                : "";

        return {
            moduleId: identity.moduleId,
            sectionId,
            routePath,
            navigationContract:
                WORKSPACE_NAVIGATION_CONTRACT
        };
    }

    function getCommandLinkRoute(link) {
        const route =
            link?.getAttribute(
                "data-command-route"
            ) || link?.getAttribute("href") || "";

        if (!route) {
            return "";
        }

        try {
            return normalizeCommandPathname(
                new URL(
                    route,
                    window.location.origin
                ).pathname
            );
        } catch (_error) {
            return "";
        }
    }

    function isWorkspaceRouteCloseable(
        pathname,
        moduleId
    ) {
        const identity =
            getWorkspaceIdentityForModule(moduleId);
        const cleanPath =
            normalizeCommandPathname(pathname);

        if (
            identity?.moduleId ===
            WORKSPACE_IDENTITIES
                .documents.moduleId &&
            isDocumentsHomePath(cleanPath)
        ) {
            return false;
        }

        return isWorkspaceShellPath(cleanPath);
    }

    function createWorkspaceWindowCloseControl() {
        const link =
            document.createElement("a");
        const icon =
            document.createElement("span");

        link.className = [
            "workspace-shell-window-close",
            "workspace-command-page-close"
        ].join(" ");
        link.href =
            WORKSPACE_IDENTITIES.documents.href;
        link.setAttribute(
            "data-command-shell-navigation",
            "true"
        );
        link.setAttribute(
            "data-command-navigation-contract",
            WORKSPACE_NAVIGATION_CONTRACT
        );
        link.setAttribute(
            "data-command-route",
            WORKSPACE_IDENTITIES.documents.href
        );
        link.setAttribute(
            "data-command-module",
            WORKSPACE_IDENTITIES.documents.moduleId
        );
        link.setAttribute(
            "data-command-section",
            DOCUMENT_SECTION_IDENTITIES.files.sectionId
        );
        link.setAttribute(
            "data-command-window-close",
            "true"
        );
        link.setAttribute(
            "aria-label",
            "Close workspace and return to Home"
        );
        link.title =
            "Return to Home";

        icon.className = "icon";
        icon.setAttribute("aria-hidden", "true");
        icon.textContent = "close";

        link.append(icon);

        return link;
    }

    function getWorkspaceWindowChromeHost(
        mount,
        moduleId
    ) {
        const identity =
            resolveWorkspaceIdentity(
                moduleId
            );
        const selectors = [];

        if (!mount) {
            return null;
        }

        if (
            identity.moduleId ===
            WORKSPACE_IDENTITIES
                .solomonAi.moduleId
        ) {
            selectors.push(
                "[data-solomon-ai-workspace]",
                ".solomon-ai-workspace"
            );
        }

        if (
            identity.moduleId ===
            WORKSPACE_IDENTITIES
                .people.moduleId
        ) {
            selectors.push(
                ".workspace-document-browser.people-browser",
                ".people-browser",
                "[data-people-page]"
            );
        }

        if (
            identity.moduleId ===
            WORKSPACE_IDENTITIES
                .search.moduleId
        ) {
            selectors.push(
                ".search-workspace-panel.workspace-command-view-panel",
                ".search-workspace-panel",
                ".workspace-command-files-panel.search-workspace-panel"
            );
        }

        selectors.push(
            ".workspace-command-view-panel:not([hidden])",
            ".workspace-command-files-panel",
            ".workspace-document-browser",
            ".workspace-command-main"
        );

        for (const selector of selectors) {
            const host = mount.querySelector(selector);

            if (host) {
                return host;
            }
        }

        return mount;
    }

    function removeLegacyWorkspaceCloseControls(
        mount,
        shellClose
    ) {
        if (!mount) {
            return;
        }

        mount.querySelectorAll(
            LEGACY_WORKSPACE_CLOSE_SELECTOR
        ).forEach(function (control) {
            if (
                control === shellClose ||
                control.getAttribute(
                    "data-command-window-close"
                ) === "true"
            ) {
                return;
            }

            control.remove();
        });
    }

    api.syncWorkspaceWindowChrome = function (
        moduleId,
        options
    ) {
        const mount =
            document.querySelector(
                api.constants
                    .WORKSPACE_MOUNT_SELECTOR
            );

        if (!mount) {
            return null;
        }

        const navigationState =
            resolveWorkspaceNavigationState(
                moduleId,
                options
            );
        const routePath =
            navigationState.routePath;
        const folderNavigationState =
            getMountedFolderNavigationState(
                mount
            );
        const routeIsHome =
            isDocumentsHomePath(routePath);
        const declaredCloseability =
            readWorkspaceMountCloseability(
                mount
            );
        const closeable =
            folderNavigationState.isFolderSurface
                ? true
                : routeIsHome
                    ? false
                    : (
                        declaredCloseability === null
                            ? isWorkspaceRouteCloseable(
                                routePath,
                                moduleId
                            )
                            : declaredCloseability
                    );
        const closeRoute =
            folderNavigationState.isFolderSurface
                ? folderNavigationState.returnRoute
                : WORKSPACE_IDENTITIES
                    .documents.href;
        const closePath =
            normalizeCommandPathname(
                closeRoute
            );
        const closeModuleId =
            isSearchPath(closePath)
                ? WORKSPACE_IDENTITIES
                    .search.moduleId
                : WORKSPACE_IDENTITIES
                    .documents.moduleId;
        const closeSection =
            getDocumentSectionIdentity(
                closePath
            )?.sectionId || "";
        let closeControl =
            mount.querySelector(
                WORKSPACE_WINDOW_CLOSE_SELECTOR
            );

        const closeHost =
            getWorkspaceWindowChromeHost(
                mount,
                moduleId
            );

        if (!closeControl) {
            closeControl =
                createWorkspaceWindowCloseControl();
        }

        if (
            closeHost &&
            closeControl.parentElement !== closeHost
        ) {
            closeHost.prepend(closeControl);
        }

        removeLegacyWorkspaceCloseControls(
            mount,
            closeControl
        );

        closeControl.href = closeRoute;
        closeControl.setAttribute(
            "data-command-route",
            closeRoute
        );
        closeControl.setAttribute(
            "data-command-module",
            closeModuleId
        );

        if (closeSection) {
            closeControl.setAttribute(
                "data-command-section",
                closeSection
            );
        } else {
            closeControl.removeAttribute(
                "data-command-section"
            );
        }

        closeControl.setAttribute(
            "aria-label",
            folderNavigationState.isFolderSurface
                ? "Close folder and return to the previous location"
                : "Close workspace and return to Home"
        );
        closeControl.title =
            folderNavigationState.isFolderSurface
                ? "Return to previous location"
                : "Return to Home";

        closeControl.hidden = !closeable;
        closeControl.setAttribute(
            "aria-hidden",
            closeable ? "false" : "true"
        );
        closeControl.setAttribute(
            "tabindex",
            closeable ? "0" : "-1"
        );

        closeControl.removeAttribute("style");

        mount.classList.toggle(
            "workspace-command-main--closeable",
            closeable
        );
        mount.setAttribute(
            WORKSPACE_MOUNT_CLOSEABLE_ATTRIBUTE,
            closeable ? "true" : "false"
        );
        mount.setAttribute(
            "data-workspace-route",
            routePath
        );
        mount.setAttribute(
            "data-workspace-section",
            navigationState.sectionId
        );
        mount.setAttribute(
            "data-workspace-navigation-contract",
            navigationState.navigationContract
        );
        mount.setAttribute(
            "data-workspace-window-chrome",
            "shell"
        );

        return closeControl;
    };


    api.updateSolomonLauncherState =
        function (moduleId) {
            const launcher =
                document.getElementById(
                    SOLOMON_LAUNCHER_ID
                );

            if (!launcher) {
                return null;
            }

            const identity =
                resolveWorkspaceIdentity(
                    moduleId
                );
            const isSolomonOpen = (
                identity.moduleId ===
                WORKSPACE_IDENTITIES
                    .solomonAi.moduleId
            );
            const targetIdentity =
                isSolomonOpen
                    ? WORKSPACE_IDENTITIES
                        .documents
                    : WORKSPACE_IDENTITIES
                        .solomonAi;
            const accessibleLabel =
                isSolomonOpen
                    ? "Close AI workspace"
                    : "Ask AI";

            launcher.href =
                targetIdentity.href;
            launcher.setAttribute(
                "data-command-module",
                targetIdentity.moduleId
            );
            launcher.setAttribute(
                "data-solomon-toggle-state",
                isSolomonOpen
                    ? "open"
                    : "closed"
            );
            launcher.setAttribute(
                "aria-label",
                accessibleLabel
            );
            launcher.title =
                accessibleLabel;
            launcher.classList.toggle(
                "is-active",
                isSolomonOpen
            );
            launcher.removeAttribute(
                "aria-current"
            );

            return {
                isSolomonOpen,
                targetModuleId:
                    targetIdentity.moduleId,
                targetHref:
                    targetIdentity.href
            };
        };

    api.updateWorkspaceIdentity = function (
        moduleId,
        options
    ) {
        const navigationState =
            resolveWorkspaceNavigationState(
                moduleId,
                options
            );
        const sidebar =
            document.getElementById(
                "commandSidebar"
            );

        document.documentElement.setAttribute(
            "data-command-workspace-product",
            navigationState.moduleId
        );
        document.documentElement.setAttribute(
            "data-command-workspace-section",
            navigationState.sectionId
        );
        document.documentElement.setAttribute(
            "data-command-workspace-route",
            navigationState.routePath
        );
        document.documentElement.setAttribute(
            "data-command-navigation-contract",
            navigationState.navigationContract
        );

        if (sidebar) {
            sidebar.setAttribute(
                "data-command-workspace-identity",
                navigationState.moduleId
            );
            sidebar.setAttribute(
                "data-command-workspace-section",
                navigationState.sectionId
            );
            sidebar.setAttribute(
                "data-command-workspace-route",
                navigationState.routePath
            );
            sidebar.setAttribute(
                "data-command-navigation-contract",
                navigationState.navigationContract
            );
        }

        api.updateSolomonLauncherState(
            navigationState.moduleId
        );

        return navigationState;
    };

    api.updateActiveCommandLink = function (
        moduleId,
        options
    ) {
        const navigationState =
            resolveWorkspaceNavigationState(
                moduleId,
                options
            );

        document.querySelectorAll(
            api.constants
                .COMMAND_LINK_SELECTOR
        ).forEach(function (link) {
            const isSolomonLauncher = (
                link.id ===
                SOLOMON_LAUNCHER_ID
            );
            const linkModuleId =
                String(
                    link.getAttribute(
                        "data-command-module"
                    ) || ""
                )
                    .trim()
                    .toLowerCase();
            const linkSectionId =
                normalizeCommandSection(
                    link.getAttribute(
                        "data-command-section"
                    )
                );
            const linkRoute =
                getCommandLinkRoute(link);
            const declaresNavigationContract = (
                link.getAttribute(
                    "data-command-navigation-contract"
                ) === WORKSPACE_NAVIGATION_CONTRACT
            );
            const isDocumentRouteLink = (
                linkModuleId ===
                    WORKSPACE_IDENTITIES
                        .documents.moduleId &&
                Boolean(linkRoute) &&
                isDocumentsPath(linkRoute)
            );
            const requiresRouteMatch = (
                declaresNavigationContract ||
                Boolean(linkSectionId) ||
                isDocumentRouteLink
            );
            const moduleMatches = (
                linkModuleId ===
                navigationState.moduleId
            );
            const sectionMatches = (
                !linkSectionId ||
                linkSectionId ===
                    navigationState.sectionId
            );
            const routeMatches = (
                !requiresRouteMatch ||
                !linkRoute ||
                linkRoute ===
                    navigationState.routePath
            );
            const isActive =
                isSolomonLauncher
                    ? (
                        navigationState.moduleId ===
                        WORKSPACE_IDENTITIES
                            .solomonAi.moduleId
                    )
                    : (
                        moduleMatches &&
                        sectionMatches &&
                        routeMatches
                    );

            link.classList.toggle(
                "is-active",
                isActive
            );

            if (isSolomonLauncher) {
                link.removeAttribute(
                    "aria-current"
                );
                return;
            }

            if (isActive) {
                link.setAttribute(
                    "aria-current",
                    "page"
                );
            } else {
                link.removeAttribute(
                    "aria-current"
                );
            }
        });
    };

    api.updateWorkspaceShellState = function (
        moduleId,
        options
    ) {
        const c = api.constants;
        const portalRoot =
            document.getElementById(
                "portal-root"
            );
        const mount =
            document.querySelector(
                c.WORKSPACE_MOUNT_SELECTOR
            );
        const navigationState =
            resolveWorkspaceNavigationState(
                moduleId,
                options
            );
        const activeWorkflow =
            api.getWorkflowForModule(
                navigationState.moduleId
            );

        [portalRoot, mount].forEach(
            function (element) {
                if (!element) {
                    return;
                }

                element.setAttribute(
                    "data-active-module",
                    navigationState.moduleId
                );
                element.setAttribute(
                    "data-active-section",
                    navigationState.sectionId
                );
                element.setAttribute(
                    "data-active-route",
                    navigationState.routePath
                );
                element.setAttribute(
                    "data-navigation-contract",
                    navigationState.navigationContract
                );
                element.setAttribute(
                    "data-active-workflow",
                    activeWorkflow
                );
            }
        );

        api.updateWorkspaceIdentity(
            navigationState.moduleId,
            options
        );
        api.updateActiveCommandLink(
            navigationState.moduleId,
            options
        );

        api.syncWorkspaceWindowChrome(
            navigationState.moduleId,
            options
        );

        api.clearTaskbarOutput();

        const sidebar =
            document.getElementById(
                "commandSidebar"
            );
        const form =
            document.querySelector(
                c.TASKBAR_FORM_SELECTOR
            );
        const input =
            form?.querySelector(
                c.TASKBAR_INPUT_SELECTOR
            );

        if (sidebar) {
            api.applyLockedTaskbarPosition(
                sidebar
            );
            sidebar.setAttribute(
                "data-solomon-input-mode",
                c.HOME_CONVERSATION_MODE
            );
            sidebar.setAttribute(
                "data-solomon-input-authority",
                c.HOME_CONVERSATION_DISPATCH_SOURCE
            );
            sidebar.setAttribute(
                "data-solomon-input-contract",
                c.HOME_CONVERSATION_CONTRACT
            );
        }

        if (form) {
            form.setAttribute(
                "aria-label",
                "Ask SolomonAI"
            );
            form.setAttribute(
                "data-solomon-command-mode",
                c.HOME_CONVERSATION_MODE
            );
            form.setAttribute(
                "data-solomon-command-authority",
                c.HOME_CONVERSATION_DISPATCH_SOURCE
            );
            api.applyTaskbarContractAttributes(
                form
            );
        }

        if (input) {
            input.setAttribute(
                "aria-label",
                "Ask SolomonAI"
            );
            input.placeholder =
                c.TASKBAR_PLACEHOLDER;
        }

        api.initializeWorkspaceViewControls();
        api.bindWorkspaceConversationSurface();
        api.syncSolomonHistoryState();

        return activeWorkflow;
    };

    api.dispatchWorkspaceLoaded = function (
        moduleId,
        activeWorkflow,
        mount,
        options
    ) {
        const navigationState =
            resolveWorkspaceNavigationState(
                moduleId,
                options
            );

        document.dispatchEvent(
            new CustomEvent(
                "solomon:workspace-loaded",
                {
                    detail: {
                        moduleId:
                            navigationState.moduleId,
                        sectionId:
                            navigationState.sectionId,
                        routePath:
                            navigationState.routePath,
                        navigationContract:
                            navigationState.navigationContract,
                        activeWorkflow,
                        mount
                    }
                }
            )
        );
    };

    api.replaceWorkspaceContent = function (
        html,
        moduleId,
        options
    ) {
        const mount =
            document.querySelector(
                api.constants
                    .WORKSPACE_MOUNT_SELECTOR
            );

        if (
            !mount ||
            !html ||
            !html.trim()
        ) {
            return false;
        }

        const workspaceResponse =
            createWorkspaceFragmentFromHtml(
                html,
                moduleId
            );

        if (
            !workspaceResponse ||
            !workspaceResponse.fragment
        ) {
            console.warn(
                "[WORKSPACE_NAVIGATION] Workspace response did not match requested module.",
                { moduleId }
            );
            return false;
        }

        activateWorkspaceStylesheets(
            workspaceResponse.stylesheets
        );

        mount.replaceChildren(
            workspaceResponse.fragment
        );
        applyWorkspaceMountCloseability(
            mount,
            workspaceResponse.mountCloseability
        );
        api.state.solomonWorkspaceSnapshot =
            null;
        document.documentElement.setAttribute(
            "data-solomon-workspace-conversation-open",
            "false"
        );

        const activeWorkflow =
            api.updateWorkspaceShellState(
                moduleId,
                options
            );

        /*
           Workspace loaded is dispatched by the navigation owner after
           mounted controls are initialized. Dispatching here binds document
           modules too early during async page swaps.
        */
        return true;
    };

    api.getPartialUrl = function (url) {
        const nextUrl = new URL(
            url,
            window.location.origin
        );

        nextUrl.searchParams.delete(
            "partial"
        );
        return nextUrl;
    };

    api.isModifiedNavigationEvent =
        function (event) {
            return (
                event.defaultPrevented ||
                event.button !== 0 ||
                event.altKey ||
                event.ctrlKey ||
                event.metaKey ||
                event.shiftKey
            );
        };

    api.isLogoutLink = function (link) {
        const moduleId =
            String(
                link.getAttribute(
                    "data-command-module"
                ) || ""
            )
                .trim()
                .toLowerCase();
        const href =
            String(
                link.getAttribute(
                    "href"
                ) || ""
            )
                .trim()
                .toLowerCase();

        return (
            moduleId === "logout" ||
            href === "/logout" ||
            href === "/auth/logout" ||
            href.startsWith("/logout?") ||
            href.startsWith(
                "/auth/logout?"
            )
        );
    };

    api.isAdminLink = function (link) {
        const navigationMode =
            String(
                link.getAttribute(
                    "data-command-navigation"
                ) || ""
            )
                .trim()
                .toLowerCase();

        if (
            navigationMode === "admin"
        ) {
            return true;
        }

        const url = new URL(
            link.href,
            window.location.origin
        );
        const pathname =
            url.pathname
                .replace(/\/+$/, "")
                .toLowerCase();

        return (
            pathname === "/admin" ||
            pathname.startsWith(
                "/admin/"
            )
        );
    };

    api.isHardNavigationLink = function (link) {
        if (
            !(link instanceof HTMLAnchorElement)
        ) {
            return false;
        }

        if (
            link.getAttribute(
                "data-command-hard-navigation"
            ) === "true" ||
            link.getAttribute(
                "data-workspace-router-ignore"
            ) === "true"
        ) {
            return true;
        }

        const url = new URL(
            link.href,
            window.location.origin
        );
        const pathname =
            normalizeCommandPathname(
                url.pathname
            );

        if (
            isWorkspaceShellLink(
                link,
                pathname
            )
        ) {
            return false;
        }

        return (
            pathname === "/auth" ||
            pathname.startsWith(
                "/auth/"
            )
        );
    };

    api.isEligibleWorkspaceLink =
        function (link) {
            return (
                link instanceof
                    HTMLAnchorElement &&
                !api.isLogoutLink(link) &&
                !api.isAdminLink(link) &&
                !api.isHardNavigationLink(link) &&
                (
                    !link.target ||
                    link.target === "_self"
                ) &&
                !link.hasAttribute(
                    "download"
                ) &&
                new URL(
                    link.href,
                    window.location.origin
                ).origin ===
                    window.location.origin
            );
        };

    api.shouldUseDocumentNavigation =
        function (link) {
            const moduleId =
                String(
                    link.getAttribute(
                        "data-command-module"
                    ) || ""
                )
                    .trim()
                    .toLowerCase();
            const shellNavigation =
                link.getAttribute(
                    "data-command-shell-navigation"
                ) === "true";
            const pathname =
                normalizeCommandPathname(
                    new URL(
                        link.href,
                        window.location.origin
                    ).pathname
                );

            if (
                isDocumentsPath(
                    pathname
                )
            ) {
                return (
                    shellNavigation ||
                    moduleId === "home" ||
                    moduleId ===
                        WORKSPACE_IDENTITIES
                            .documents.moduleId
                );
            }

            if (
                isWorkspaceShellPath(
                    pathname
                )
            ) {
                return false;
            }

            return (
                moduleId === "home" ||
                moduleId ===
                    WORKSPACE_IDENTITIES
                        .documents.moduleId
            );
        };
})();