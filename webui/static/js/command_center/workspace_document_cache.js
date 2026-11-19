/* -------------------------------------------------------------------
   FILE: workspace_document_cache.js
   DIRECTORY: webui/static/js/command_center/
------------------------------------------------------------------- */

(function () {
    "use strict";

    const API_NAME = "SolomonWorkspaceDocumentCache";

    if (window[API_NAME]) {
        return;
    }

    const Records = window.SolomonWorkspaceDocumentRecords;
    const Sections = window.SolomonWorkspaceDocumentSections;

    if (!Records || !Sections) {
        console.error("[DOCUMENT_CACHE] Missing required Solomon document modules.");
        return;
    }

    const normalizeDocumentSection = Sections.normalizeDocumentSection;

    function getDocumentSectionCache(explorer) {
        if (!explorer.__solomonDocumentSectionCache) {
            explorer.__solomonDocumentSectionCache = new Map();
        }

        return explorer.__solomonDocumentSectionCache;
    }

    function getCachedDocumentSection(explorer, section) {
        const cleanSection = normalizeDocumentSection(section);
        const cache = getDocumentSectionCache(explorer);

        if (!cache.has(cleanSection)) {
            return null;
        }

        const docs = cache.get(cleanSection);

        return Array.isArray(docs) ? docs : [];
    }

    function setCachedDocumentSection(explorer, section, docs) {
        const cleanSection = normalizeDocumentSection(section);
        const cache = getDocumentSectionCache(explorer);
        const safeDocs = Array.isArray(docs) ? docs : [];

        cache.set(cleanSection, safeDocs);
    }

    function invalidateDocumentSectionCache(explorer, section) {
        if (!explorer?.__solomonDocumentSectionCache) {
            return;
        }

        explorer.__solomonDocumentSectionCache.delete(normalizeDocumentSection(section));
    }

    function indexDocumentsById(docs) {
        const documentsById = new Map();

        (Array.isArray(docs) ? docs : []).forEach(function (doc) {
            const documentId = Records.getDocumentId(doc);

            if (documentId) {
                documentsById.set(documentId, doc);
            }
        });

        return documentsById;
    }

    function cacheDocuments(explorer, docs, options) {
        const cleanSection = normalizeDocumentSection(
            options?.section ||
            explorer?.getAttribute("data-workspace-section") ||
            "files"
        );
        const safeDocs = Array.isArray(docs) ? docs : [];

        explorer.__solomonDocuments = safeDocs;
        explorer.__solomonDocumentById = indexDocumentsById(safeDocs);
        setCachedDocumentSection(explorer, cleanSection, safeDocs);

        if (
            cleanSection === "files" &&
            options?.updateCollectionCounts !== false &&
            options?.library &&
            typeof options.library.updateCollectionCounts === "function"
        ) {
            options.library.updateCollectionCounts(explorer, safeDocs);
        }
    }

    function removeDocumentFromCachedSection(explorer, section, documentId) {
        const cleanSection = normalizeDocumentSection(section);
        const cleanId = String(documentId || "").trim();
        const cachedDocs = getCachedDocumentSection(explorer, cleanSection);

        if (!cleanId || !Array.isArray(cachedDocs)) {
            return [];
        }

        const remainingDocs = cachedDocs.filter(function (doc) {
            return Records.getDocumentId(doc) !== cleanId;
        });

        setCachedDocumentSection(explorer, cleanSection, remainingDocs);

        if (normalizeDocumentSection(explorer.getAttribute("data-workspace-section")) === cleanSection) {
            explorer.__solomonDocuments = remainingDocs;
            explorer.__solomonDocumentById = indexDocumentsById(remainingDocs);
        }

        return remainingDocs;
    }

    function upsertDocumentInCachedSection(explorer, section, doc) {
        const cleanSection = normalizeDocumentSection(section);
        const documentId = Records.getDocumentId(doc);
        const cachedDocs = getCachedDocumentSection(explorer, cleanSection) || [];
        const nextDocs = [];
        let inserted = false;

        if (!documentId) {
            return;
        }

        cachedDocs.forEach(function (cachedDoc) {
            if (Records.getDocumentId(cachedDoc) === documentId) {
                if (!inserted) {
                    nextDocs.push(doc);
                    inserted = true;
                }

                return;
            }

            nextDocs.push(cachedDoc);
        });

        if (!inserted) {
            nextDocs.unshift(doc);
        }

        setCachedDocumentSection(explorer, cleanSection, nextDocs);
    }

    window[API_NAME] = Object.freeze({
        getDocumentSectionCache,
        getCachedDocumentSection,
        setCachedDocumentSection,
        invalidateDocumentSectionCache,
        indexDocumentsById,
        cacheDocuments,
        removeDocumentFromCachedSection,
        upsertDocumentInCachedSection
    });
})();