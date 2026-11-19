/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_message_text.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI message-text normalization.

   Preserves server-authored text while normalizing known legacy headings
   and improving long summary readability before safe DOM rendering.
   JavaScript does not create factual content or alter response authority.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before message text."
        );
    }

    const { cleanValue } = modules.requireModule(
        "contract"
    );

    function normalizeMessageSourceText(value) {
        return String(value || "")
            .replace(/\r\n?/g, "\n")
            .trim();
    }

    function escapeRegularExpression(value) {
        return String(value || "").replace(
            /[.*+?^${}()|[\]\\]/g,
            "\\$&"
        );
    }

    function getKnownAssistantHeadingParts(
        line,
        options
    ) {
        const sourceLine = cleanValue(line);
        const hasFollowingContent = (
            options?.hasFollowingContent === true
        );
        const fileHeadingMatch = sourceLine.match(
            /^(?:#{2,4}\s+)?(?:\*\*|__)?((Summary|Key Details|Comparison)\s*[—–-]\s*(Selected Files|.+?\.(?:pdf|docx?|xlsx?|csv|txt|rtf|png|jpe?g|webp|gif|tiff?)))(?:\*\*|__)?(?:\s+([\s\S]+))?$/i
        );

        if (fileHeadingMatch) {
            return {
                heading: cleanValue(
                    fileHeadingMatch[1]
                ),
                headingType: cleanValue(
                    fileHeadingMatch[2]
                ).toLowerCase(),
                sourceTitle: cleanValue(
                    fileHeadingMatch[3]
                ),
                trailingText: cleanValue(
                    fileHeadingMatch[4]
                )
            };
        }

        if (!hasFollowingContent) {
            return null;
        }

        const standaloneHeadingMatch =
            sourceLine.match(
                /^(?:#{2,4}\s+)?(?:\*\*|__)?((Summary|Key Details|Comparison)\s*[—–-]\s*(.+?))(?:\*\*|__)?$/i
            );

        if (!standaloneHeadingMatch) {
            return null;
        }

        return {
            heading: cleanValue(
                standaloneHeadingMatch[1]
            ),
            headingType: cleanValue(
                standaloneHeadingMatch[2]
            ).toLowerCase(),
            sourceTitle: cleanValue(
                standaloneHeadingMatch[3]
            ),
            trailingText: ""
        };
    }

    function removeRepeatedHeadingTitle(
        body,
        sourceTitle
    ) {
        const normalizedBody = cleanValue(
            body
        );
        const normalizedTitle = cleanValue(
            sourceTitle
        );

        if (
            !normalizedBody ||
            !normalizedTitle ||
            normalizedTitle.toLowerCase() ===
                "selected files"
        ) {
            return normalizedBody;
        }

        return normalizedBody.replace(
            new RegExp(
                (
                    "^(?:(?:\\*\\*|__)\\s*)?" +
                    escapeRegularExpression(
                        normalizedTitle
                    ) +
                    "(?:\\s*(?:\\*\\*|__))?" +
                    "(?:\\s+|$)"
                ),
                "i"
            ),
            ""
        ).trim();
    }

    function splitCompleteSentences(value) {
        const source = String(value || "")
            .replace(/\s+/g, " ")
            .trim();
        const sentences = [];
        const boundaryPattern =
            /[.!?]+(?:["')\]]+)?(?=\s+|$)/g;
        let cursor = 0;
        let match = boundaryPattern.exec(
            source
        );

        while (match) {
            const endIndex = (
                match.index +
                match[0].length
            );
            const sentence = source
                .slice(
                    cursor,
                    endIndex
                )
                .trim();

            if (sentence) {
                sentences.push(
                    sentence
                );
            }

            cursor = endIndex;

            while (
                cursor < source.length &&
                /\s/.test(
                    source[cursor]
                )
            ) {
                cursor += 1;
            }

            match = boundaryPattern.exec(
                source
            );
        }

        const remainder = source
            .slice(cursor)
            .trim();

        if (remainder) {
            sentences.push(
                remainder
            );
        }

        return sentences;
    }

    function buildBalancedParagraphs(
        sentences,
        paragraphCount
    ) {
        const safeSentences = Array.isArray(
            sentences
        )
            ? sentences.filter(function (sentence) {
                return cleanValue(
                    sentence
                );
            })
            : [];
        const requestedParagraphs = Math.max(
            1,
            Number.parseInt(
                paragraphCount,
                10
            ) || 1
        );

        if (!safeSentences.length) {
            return [];
        }

        const paragraphs = [];
        const totalSentences =
            safeSentences.length;
        const totalParagraphs = Math.min(
            requestedParagraphs,
            totalSentences
        );
        const baseSize = Math.floor(
            totalSentences /
            totalParagraphs
        );
        const extraSentences = (
            totalSentences %
            totalParagraphs
        );
        let cursor = 0;

        for (
            let index = 0;
            index < totalParagraphs;
            index += 1
        ) {
            const groupSize = (
                baseSize +
                (
                    index < extraSentences
                        ? 1
                        : 0
                )
            );
            const paragraph = safeSentences
                .slice(
                    cursor,
                    cursor + groupSize
                )
                .join(" ")
                .trim();

            if (paragraph) {
                paragraphs.push(
                    paragraph
                );
            }

            cursor += groupSize;
        }

        return paragraphs;
    }

    function normalizeSummaryParagraphs(value) {
        const normalizedBody =
            normalizeMessageSourceText(
                value
            );

        if (
            !normalizedBody ||
            /\n\s*\n/.test(
                normalizedBody
            ) ||
            /^(?:#{2,4}\s+|[-*•]\s+|\d+[.)]\s+|>\s?)/m.test(
                normalizedBody
            )
        ) {
            return normalizedBody;
        }

        const sentences =
            splitCompleteSentences(
                normalizedBody
            );

        if (sentences.length < 3) {
            return normalizedBody;
        }

        return buildBalancedParagraphs(
            sentences,
            3
        ).join("\n\n");
    }

    function normalizeLegacyAssistantMarkdown(
        value
    ) {
        const normalizedText =
            normalizeMessageSourceText(
                value
            );

        if (!normalizedText) {
            return "";
        }

        const lines = normalizedText.split(
            "\n"
        );
        const firstLine = lines[0];
        const remainingLines = lines.slice(
            1
        );
        const headingParts =
            getKnownAssistantHeadingParts(
                firstLine,
                {
                    hasFollowingContent:
                        remainingLines.some(
                            function (line) {
                                return cleanValue(
                                    line
                                );
                            }
                        )
                }
            );

        if (!headingParts) {
            return normalizedText;
        }

        const bodyParts = [];

        if (headingParts.trailingText) {
            bodyParts.push(
                headingParts.trailingText
            );
        }

        if (remainingLines.length) {
            bodyParts.push(
                remainingLines.join(
                    "\n"
                )
            );
        }

        let body =
            removeRepeatedHeadingTitle(
                bodyParts
                    .join("\n")
                    .trim(),
                headingParts.sourceTitle
            );

        if (
            headingParts.headingType ===
            "summary"
        ) {
            body =
                normalizeSummaryParagraphs(
                    body
                );
        }

        return [
            `### ${headingParts.heading}`,
            body
        ].filter(Boolean).join(
            "\n\n"
        );
    }

    modules.registerModule(
        "message_text",
        {
            buildBalancedParagraphs,
            escapeRegularExpression,
            getKnownAssistantHeadingParts,
            normalizeLegacyAssistantMarkdown,
            normalizeMessageSourceText,
            normalizeSummaryParagraphs,
            removeRepeatedHeadingTitle,
            splitCompleteSentences
        }
    );
})(window);