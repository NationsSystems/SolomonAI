/* -------------------------------------------------------------------
   FILE: command_sidebar.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const namespace = "NationsCommandSidebar";
    const api = window[namespace] =
        window[namespace] || {};

    if (api.__loaderStarted) {
        return;
    }

    api.__loaderStarted = true;

    const currentScript = document.currentScript;
    const baseUrl = currentScript?.src ||
        "/static/js/command_center/command_sidebar.js";
    const loaderUrl = new URL(
        baseUrl,
        window.location.origin
    );

    const modules = [
        {
            fileName: "command_sidebar_state.js",
            required: true
        },
        {
            fileName: "command_sidebar_views.js",
            required: true
        },
        {
            fileName: "command_sidebar_taskbar.js",
            required: true
        },
        {
            fileName: "command_sidebar_conversation.js",
            required: true
        },
        {
            fileName: "command_sidebar_navigation.js",
            required: true
        },
        {
            fileName: "command_sidebar_context_rail.js",
            required: true
        },
        {
            fileName: "command_sidebar_people_invite.js",
            required: true
        },
        {
            fileName: "workspace_document_section_navigation.js",
            required: true
        },
        {
            fileName: "submenu_pointer_intent.js",
            required: true
        },
        {
            fileName: "workspace_listing_controller.js",
            required: false
        },
        {
            fileName: "command_sidebar_search.js",
            required: true
        },
        {
            fileName: "command_sidebar_bootstrap.js",
            required: true
        }
    ];

    function getModuleUrl(fileName) {
        const moduleUrl = new URL(
            fileName,
            loaderUrl
        );

        moduleUrl.search = loaderUrl.search;

        return moduleUrl.href;
    }

    function normalizeModuleDefinition(moduleDefinition) {
        if (typeof moduleDefinition === "string") {
            return {
                fileName: moduleDefinition,
                required: true
            };
        }

        return {
            fileName: String(
                moduleDefinition?.fileName || ""
            ).trim(),
            required: moduleDefinition?.required !== false
        };
    }

    function loadScript(moduleDefinition) {
        const moduleConfig = normalizeModuleDefinition(
            moduleDefinition
        );

        return new Promise(function (
            resolve,
            reject
        ) {
            if (!moduleConfig.fileName) {
                if (moduleConfig.required) {
                    reject(
                        new Error(
                            "Unable to load command sidebar module: missing file name"
                        )
                    );
                    return;
                }

                resolve();
                return;
            }

            const script =
                document.createElement("script");

            script.src = getModuleUrl(
                moduleConfig.fileName
            );
            script.defer = true;
            script.onload = resolve;
            script.onerror = function () {
                const error = new Error(
                    "Unable to load command sidebar module: " +
                    moduleConfig.fileName
                );

                if (moduleConfig.required) {
                    reject(error);
                    return;
                }

                console.warn(
                    "[COMMAND_SIDEBAR] Optional module skipped.",
                    {
                        module: moduleConfig.fileName,
                        error
                    }
                );

                resolve();
            };

            document.head.appendChild(script);
        });
    }

    async function loadModules() {
        try {
            for (const moduleDefinition of modules) {
                await loadScript(moduleDefinition);
            }

            if (
                typeof api.initializeCommandSidebar ===
                "function"
            ) {
                api.initializeCommandSidebar();
            }
        } catch (error) {
            console.error(error);
            document.documentElement.setAttribute(
                "data-command-center-ready",
                "false"
            );
        }
    }

    loadModules();
}());