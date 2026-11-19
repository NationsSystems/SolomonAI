/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_message_markdown.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI message-body rendering.

   Renders a deliberately limited markdown subset with DOM APIs only.
   Message text remains inert data; embedded HTML is never executed and
   response authority remains server-owned.
------------------------------------------------------------------- */

(function (window, document) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before message markdown."
        );
    }

    const messageText = modules.requireModule("message_text");
    const {
        normalizeLegacyAssistantMarkdown,
        normalizeMessageSourceText
    } = messageText;

    function appendTextWithLineBreaks(element, text) {
        String(text || "").split(/\r?\n/).forEach(function (line, index) {
            if (index > 0) {
                element.append(document.createElement("br"));
            }

            element.append(document.createTextNode(line));
        });
    }

    function createSafeMarkdownLink(token) {
        const match = String(token || "").match(
            /^\[([^\]\n]+)\]\((?:<)?(https?:\/\/[^\s)>]+)(?:>)?\)$/i
        );

        if (!match) {
            return null;
        }

        let url;

        try {
            url = new URL(match[2]);
        } catch (error) {
            return null;
        }

        if (url.protocol !== "http:" && url.protocol !== "https:") {
            return null;
        }

        const link = document.createElement("a");

        link.textContent = match[1];
        link.href = url.href;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        return link;
    }

    function appendInlineMarkdown(element, value) {
        const source = String(value || "");
        const tokenPattern =
            /(\[[^\]\n]+\]\((?:<)?https?:\/\/[^\s)>]+(?:>)?\)|`[^`\n]+`|\*\*[^*\n]+\*\*|__[^_\n]+__|\*[^*\n]+\*|_[^_\n]+_)/gi;
        let cursor = 0;
        let match = tokenPattern.exec(source);

        while (match) {
            if (match.index > cursor) {
                element.append(
                    document.createTextNode(
                        source.slice(cursor, match.index)
                    )
                );
            }

            const token = match[0];
            const markdownLink = createSafeMarkdownLink(token);

            if (markdownLink) {
                if (
                    match.index === cursor &&
                    element.lastElementChild?.tagName === "A"
                ) {
                    element.append(document.createTextNode(" "));
                }

                element.append(markdownLink);
            } else {
                let tagName = "em";
                let trimSize = 1;

                if (token.startsWith("`")) {
                    tagName = "code";
                } else if (
                    token.startsWith("**") ||
                    token.startsWith("__")
                ) {
                    tagName = "strong";
                    trimSize = 2;
                }

                const inlineElement = document.createElement(tagName);

                inlineElement.textContent = token.slice(
                    trimSize,
                    -trimSize
                );
                element.append(inlineElement);
            }

            cursor = match.index + token.length;
            match = tokenPattern.exec(source);
        }

        if (cursor < source.length) {
            element.append(
                document.createTextNode(source.slice(cursor))
            );
        }
    }

    function createMarkdownTextElement(tagName, text) {
        const element = document.createElement(tagName);

        appendInlineMarkdown(element, text);
        return element;
    }

    function prepareBody(body, format) {
        body.replaceChildren();
        body.setAttribute("data-solomon-ai-content-format", format);
        body.setAttribute(
            "data-solomon-ai-content-rendered",
            "true"
        );
    }

    function renderPlainMessageBody(body, text) {
        const normalizedText = normalizeMessageSourceText(text);
        const paragraphs = normalizedText
            .split(/\n\s*\n/)
            .filter(function (paragraph) {
                return String(paragraph || "").trim();
            });

        prepareBody(body, "plain");

        (paragraphs.length ? paragraphs : [normalizedText]).forEach(
            function (paragraphText) {
                const paragraph = document.createElement("p");

                appendTextWithLineBreaks(paragraph, paragraphText);
                body.append(paragraph);
            }
        );
    }

    function splitTableRow(line) {
        let value = String(line || "").trim();

        if (value.startsWith("|")) {
            value = value.slice(1);
        }

        if (value.endsWith("|")) {
            value = value.slice(0, -1);
        }

        const cells = [];
        let cell = "";
        let escaped = false;

        for (const character of value) {
            if (escaped) {
                cell += character;
                escaped = false;
                continue;
            }

            if (character === "\\") {
                escaped = true;
                continue;
            }

            if (character === "|") {
                cells.push(cell.trim());
                cell = "";
                continue;
            }

            cell += character;
        }

        if (escaped) {
            cell += "\\";
        }

        cells.push(cell.trim());
        return cells;
    }

    function isTableDivider(line) {
        const cells = splitTableRow(line);

        return cells.length > 1 && cells.every(function (cell) {
            return /^:?-{3,}:?$/.test(cell.replace(/\s+/g, ""));
        });
    }

    function appendMarkdownTable(body, headerLine, rowLines) {
        const wrapper = document.createElement("div");
        const table = document.createElement("table");
        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");
        const tbody = document.createElement("tbody");
        const headerCells = splitTableRow(headerLine);

        wrapper.className = "solomon-ai-message__table-scroll";

        headerCells.forEach(function (value) {
            headerRow.append(createMarkdownTextElement("th", value));
        });

        thead.append(headerRow);
        table.append(thead);

        rowLines.forEach(function (rowLine) {
            const row = document.createElement("tr");
            const cells = splitTableRow(rowLine);

            headerCells.forEach(function (_header, index) {
                row.append(
                    createMarkdownTextElement("td", cells[index] || "")
                );
            });

            tbody.append(row);
        });

        table.append(tbody);
        wrapper.append(table);
        body.append(wrapper);
    }

    function appendCodeBlock(body, language, lines) {
        const pre = document.createElement("pre");
        const code = document.createElement("code");
        const normalizedLanguage = String(language || "")
            .trim()
            .replace(/[^a-z0-9_+-]/gi, "")
            .slice(0, 32);

        if (normalizedLanguage) {
            code.setAttribute(
                "data-solomon-ai-code-language",
                normalizedLanguage.toLowerCase()
            );
        }

        code.textContent = lines.join("\n");
        pre.append(code);
        body.append(pre);
    }

    function renderMarkdownMessageBody(body, text) {
        const lines = normalizeLegacyAssistantMarkdown(text).split("\n");
        let paragraphLines = [];
        let quoteLines = [];
        let activeList = null;
        let activeListType = "";

        function flushParagraph() {
            const paragraphText = paragraphLines
                .join(" ")
                .replace(/\s+/g, " ")
                .trim();

            if (paragraphText) {
                body.append(
                    createMarkdownTextElement("p", paragraphText)
                );
            }

            paragraphLines = [];
        }

        function flushQuote() {
            const quoteText = quoteLines
                .join(" ")
                .replace(/\s+/g, " ")
                .trim();

            if (quoteText) {
                const quote = document.createElement("blockquote");

                quote.append(
                    createMarkdownTextElement("p", quoteText)
                );
                body.append(quote);
            }

            quoteLines = [];
        }

        function flushList() {
            activeList = null;
            activeListType = "";
        }

        function flushBlocks() {
            flushParagraph();
            flushQuote();
            flushList();
        }

        function startList(listType) {
            if (activeList && activeListType === listType) {
                return activeList;
            }

            flushList();
            activeList = document.createElement(
                listType === "ordered" ? "ol" : "ul"
            );
            activeListType = listType;
            body.append(activeList);
            return activeList;
        }

        prepareBody(body, "markdown");

        for (let index = 0; index < lines.length; index += 1) {
            const rawLine = lines[index];
            const line = rawLine.trim();

            if (!line) {
                flushBlocks();
                continue;
            }

            const fence = line.match(/^```\s*([a-z0-9_+-]*)\s*$/i);

            if (fence) {
                const codeLines = [];

                flushBlocks();
                index += 1;

                while (
                    index < lines.length &&
                    !/^```\s*$/.test(lines[index].trim())
                ) {
                    codeLines.push(lines[index]);
                    index += 1;
                }

                appendCodeBlock(body, fence[1], codeLines);
                continue;
            }

            if (
                line.includes("|") &&
                index + 1 < lines.length &&
                isTableDivider(lines[index + 1])
            ) {
                const rowLines = [];

                flushBlocks();
                index += 2;

                while (
                    index < lines.length &&
                    lines[index].trim() &&
                    lines[index].includes("|")
                ) {
                    rowLines.push(lines[index]);
                    index += 1;
                }

                appendMarkdownTable(body, rawLine, rowLines);
                index -= 1;
                continue;
            }

            const heading = line.match(/^(#{1,4})\s+(.+)$/);
            const unordered = line.match(/^[-*•]\s+(.+)$/);
            const ordered = line.match(/^\d+[.)]\s+(.+)$/);
            const quote = line.match(/^>\s?(.*)$/);

            if (heading) {
                flushBlocks();

                const level = Math.min(
                    4,
                    Math.max(2, heading[1].length)
                );

                body.append(
                    createMarkdownTextElement(
                        `h${level}`,
                        heading[2]
                    )
                );
                continue;
            }

            if (/^(?:-{3,}|\*{3,}|_{3,})$/.test(line)) {
                flushBlocks();
                body.append(document.createElement("hr"));
                continue;
            }

            if (unordered || ordered) {
                flushParagraph();
                flushQuote();

                startList(
                    ordered ? "ordered" : "unordered"
                ).append(
                    createMarkdownTextElement(
                        "li",
                        ordered ? ordered[1] : unordered[1]
                    )
                );
                continue;
            }

            if (quote) {
                flushParagraph();
                flushList();
                quoteLines.push(quote[1]);
                continue;
            }

            flushQuote();
            flushList();
            paragraphLines.push(line);
        }

        flushBlocks();

        if (!body.children.length) {
            body.append(document.createElement("p"));
        }
    }

    function renderMessageBody(body, text, options) {
        if (!body) {
            return false;
        }

        if (options?.markdown === true) {
            renderMarkdownMessageBody(body, text);
        } else {
            renderPlainMessageBody(body, text);
        }

        return true;
    }

    modules.registerModule("message_markdown", {
        appendInlineMarkdown,
        appendTextWithLineBreaks,
        createMarkdownTextElement,
        renderMarkdownMessageBody,
        renderMessageBody,
        renderPlainMessageBody
    });
})(window, document);
