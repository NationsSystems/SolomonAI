/* -------------------------------------------------------------------
   FILE: workspace_document_sections.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentSections";

    if (window[API_NAME]) {
        return;
    }

    const DEFAULT_DOCUMENT_SECTION = "files";
    const VALID_DOCUMENT_SECTIONS = Object.freeze([
        "files",
        "reports",
        "recent",
        "shared",
        "trash"
    ]);
    const FETCHABLE_DOCUMENT_SECTIONS = Object.freeze([
        "files",
        "shared",
        "recent",
        "trash"
    ]);

    const DOCUMENT_SECTION_LABELS = Object.freeze({
        files: "My Files",
        reports: "Reports",
        recent: "Recent",
        shared: "Shared with me",
        trash: "Trash"
    });

    const DOCUMENT_SECTION_ICONS = Object.freeze({
        files: "folder_open",
        reports: "summarize",
        recent: "schedule",
        shared: "folder_shared",
        trash: "delete_outline"
    });

    const DOCUMENT_SECTION_PATHS = Object.freeze({
        files: "/",
        reports: "/reports",
        recent: "/recent",
        shared: "/shared",
        trash: "/trash"
    });

    const DOCUMENT_SECTION_EMPTY_COPY = Object.freeze({
        files: "Upload files to begin building your Solomon Documents library.",
        reports: "Completed document reviews and generated artifacts will appear here.",
        recent: "Recently opened, uploaded, and updated files will appear here.",
        shared: "Files and folders shared with you will appear here after server authorization.",
        trash: "Files moved to Trash stay available here until they are restored or deleted forever."
    });

    const DOCUMENT_SECTION_LOADING_COPY = Object.freeze({
        files: "Loading My Files.",
        shared: "Loading Shared with me.",
        recent: "Loading Recent.",
        trash: "Loading Trash."
    });

    const DOCUMENT_SECTION_EMPTY_STATE = Object.freeze({
        files: Object.freeze({
            modifier: "files",
            primaryIcon: "folder_open",
            secondaryIcon: "description",
            accentIcon: "upload_file",
            title: "Drop files here or use Upload.",
            message: "Upload stores the file in Solomon Documents only. It does not start DocIntel, classification, extraction, or analysis.",
            actionLabel: "Upload files"
        }),
        reports: Object.freeze({
            modifier: "reports",
            primaryIcon: "summarize",
            secondaryIcon: "description",
            accentIcon: "task_alt",
            title: "No completed reports yet",
            message: "Completed Bid & Scope Review reports and future document artifacts will appear here after an explicit workflow is run."
        }),
        shared: Object.freeze({
            modifier: "shared",
            primaryIcon: "folder_shared",
            secondaryIcon: "description",
            accentIcon: "groups",
            title: "Nothing has been shared with you",
            message: "Authorized shared folders and individually shared files will appear here without changing their original ownership."
        }),
        recent: Object.freeze({
            modifier: "recent",
            primaryIcon: "schedule",
            secondaryIcon: "description",
            accentIcon: "history",
            title: "No recent activity yet",
            message: "Recently opened, uploaded, and updated files will appear here once there is activity in the workspace."
        }),
        trash: Object.freeze({
            modifier: "trash",
            primaryIcon: "delete_outline",
            secondaryIcon: "description",
            accentIcon: "restore_from_trash",
            title: "Trash is empty",
            message: "Files moved to Trash can be restored from here until they are deleted forever."
        })
    });

    function normalizeDocumentSection(section) {
        const cleanSection = String(
            section ||
            DEFAULT_DOCUMENT_SECTION
        ).trim().toLowerCase();

        return VALID_DOCUMENT_SECTIONS.includes(cleanSection)
            ? cleanSection
            : DEFAULT_DOCUMENT_SECTION;
    }

    function isFetchableDocumentSection(section) {
        return FETCHABLE_DOCUMENT_SECTIONS.includes(
            normalizeDocumentSection(section)
        );
    }

    function getDocumentSectionLabel(section) {
        const cleanSection = normalizeDocumentSection(section);

        return (
            DOCUMENT_SECTION_LABELS[cleanSection] ||
            DOCUMENT_SECTION_LABELS[DEFAULT_DOCUMENT_SECTION]
        );
    }

    function getDocumentSectionIcon(section) {
        const cleanSection = normalizeDocumentSection(section);

        return (
            DOCUMENT_SECTION_ICONS[cleanSection] ||
            DOCUMENT_SECTION_ICONS[DEFAULT_DOCUMENT_SECTION]
        );
    }

    function getDocumentSectionPath(section) {
        const cleanSection = normalizeDocumentSection(section);

        return (
            DOCUMENT_SECTION_PATHS[cleanSection] ||
            DOCUMENT_SECTION_PATHS[DEFAULT_DOCUMENT_SECTION]
        );
    }

    function normalizeRoutePath(pathname) {
        const cleanPath = String(
            pathname ||
            ""
        ).replace(/\/+$/, "");

        return cleanPath || "/";
    }

    function getDocumentSectionFromPath(pathname) {
        const cleanPath = normalizeRoutePath(
            pathname ||
            window.location?.pathname ||
            ""
        );

        if (cleanPath === DOCUMENT_SECTION_PATHS.reports) {
            return "reports";
        }

        if (cleanPath === DOCUMENT_SECTION_PATHS.recent) {
            return "recent";
        }

        if (cleanPath === DOCUMENT_SECTION_PATHS.shared) {
            return "shared";
        }

        if (cleanPath === DOCUMENT_SECTION_PATHS.trash) {
            return "trash";
        }

        return DEFAULT_DOCUMENT_SECTION;
    }

    function getDocumentSectionEmptyCopy(section) {
        const cleanSection = normalizeDocumentSection(section);

        return (
            DOCUMENT_SECTION_EMPTY_COPY[cleanSection] ||
            DOCUMENT_SECTION_EMPTY_COPY[DEFAULT_DOCUMENT_SECTION]
        );
    }

    function getDocumentSectionLoadingCopy(section) {
        const cleanSection = normalizeDocumentSection(section);

        return (
            DOCUMENT_SECTION_LOADING_COPY[cleanSection] ||
            ""
        );
    }

    function getDocumentSectionEmptyState(section) {
        const cleanSection = normalizeDocumentSection(section);

        return (
            DOCUMENT_SECTION_EMPTY_STATE[cleanSection] ||
            DOCUMENT_SECTION_EMPTY_STATE[DEFAULT_DOCUMENT_SECTION]
        );
    }

    window[API_NAME] = Object.freeze({
        DEFAULT_DOCUMENT_SECTION,
        VALID_DOCUMENT_SECTIONS,
        FETCHABLE_DOCUMENT_SECTIONS,
        DOCUMENT_SECTION_LABELS,
        DOCUMENT_SECTION_ICONS,
        DOCUMENT_SECTION_PATHS,
        DOCUMENT_SECTION_EMPTY_COPY,
        DOCUMENT_SECTION_LOADING_COPY,
        DOCUMENT_SECTION_EMPTY_STATE,
        normalizeDocumentSection,
        isFetchableDocumentSection,
        getDocumentSectionLabel,
        getDocumentSectionIcon,
        getDocumentSectionPath,
        normalizeRoutePath,
        getDocumentSectionFromPath,
        getDocumentSectionEmptyCopy,
        getDocumentSectionLoadingCopy,
        getDocumentSectionEmptyState
    });
}());