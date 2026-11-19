/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_stream_parser.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI server-sent-event parsing.

   Converts streamed text into complete SSE records and normalizes the
   SolomonAI event types used by execution transport. JavaScript parses
   transport framing only; event content and response authority remain
   server-owned.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before stream parsing."
        );
    }

    const { cleanValue } = modules.requireModule("contract");

    const EVENT_NAMES = Object.freeze({
        OPEN: "solomon_ai_stream_open",
        ANSWER: "solomon_ai_answer",
        PACKET: "solomon_ai_packet",
        ERROR: "error",
        MESSAGE: "message"
    });

    function normalizeStreamText(value) {
        return String(value || "").replace(/\r\n?/g, "\n");
    }

    function parseEventData(dataText) {
        const sourceText = String(dataText || "");

        try {
            return JSON.parse(sourceText);
        } catch (error) {
            return {
                ok: false,
                error: sourceText
            };
        }
    }

    function parseServerSentEvent(block) {
        const lines = normalizeStreamText(block).split("\n");
        const dataLines = [];
        let eventName = EVENT_NAMES.MESSAGE;
        let eventId = "";
        let retry = null;

        lines.forEach(function (line) {
            if (!line || line.startsWith(":")) {
                return;
            }

            const separatorIndex = line.indexOf(":");
            const field = separatorIndex >= 0
                ? line.slice(0, separatorIndex)
                : line;
            let value = separatorIndex >= 0
                ? line.slice(separatorIndex + 1)
                : "";

            if (value.startsWith(" ")) {
                value = value.slice(1);
            }

            if (field === "event") {
                eventName = cleanValue(value) || EVENT_NAMES.MESSAGE;
                return;
            }

            if (field === "data") {
                dataLines.push(value);
                return;
            }

            if (field === "id") {
                eventId = value;
                return;
            }

            if (field === "retry") {
                const retryValue = Number.parseInt(value, 10);

                if (
                    Number.isInteger(retryValue) &&
                    retryValue >= 0
                ) {
                    retry = retryValue;
                }
            }
        });

        if (!dataLines.length) {
            return null;
        }

        const dataText = dataLines.join("\n");

        return {
            event: eventName,
            data: parseEventData(dataText),
            dataText,
            id: eventId,
            retry
        };
    }

    function splitServerSentEventBuffer(buffer, options) {
        let remaining = normalizeStreamText(buffer);
        const blocks = [];
        let boundaryIndex = remaining.indexOf("\n\n");

        while (boundaryIndex >= 0) {
            const block = remaining
                .slice(0, boundaryIndex)
                .trim();

            remaining = remaining.slice(
                boundaryIndex + 2
            );

            if (block) {
                blocks.push(block);
            }

            boundaryIndex = remaining.indexOf("\n\n");
        }

        if (
            options?.flush === true &&
            cleanValue(remaining)
        ) {
            blocks.push(remaining.trim());
            remaining = "";
        }

        return {
            blocks,
            remaining
        };
    }

    function parseServerSentEventBuffer(buffer, options) {
        const splitResult = splitServerSentEventBuffer(
            buffer,
            options
        );
        const events = splitResult.blocks
            .map(parseServerSentEvent)
            .filter(Boolean);

        return {
            events,
            remaining: splitResult.remaining
        };
    }

    function getStreamEventError(parsedEvent) {
        const eventData = parsedEvent?.data;

        return cleanValue(
            eventData?.error ||
            eventData?.user_output ||
            eventData?.message
        ) || "SolomonAI stream failed.";
    }

    function getStreamPacket(parsedEvent) {
        const eventData = parsedEvent?.data;

        return (
            eventData?.packet &&
            typeof eventData.packet === "object" &&
            !Array.isArray(eventData.packet)
        )
            ? eventData.packet
            : {};
    }

    function getStreamHttpStatus(
        parsedEvent,
        fallbackStatus
    ) {
        const eventStatus = Number.parseInt(
            parsedEvent?.data?.http_status,
            10
        );

        if (
            Number.isInteger(eventStatus) &&
            eventStatus >= 100 &&
            eventStatus <= 599
        ) {
            return eventStatus;
        }

        const fallback = Number.parseInt(
            fallbackStatus,
            10
        );

        return Number.isInteger(fallback)
            ? fallback
            : 0;
    }

    function isStreamEvent(parsedEvent, eventName) {
        return (
            cleanValue(parsedEvent?.event) ===
            eventName
        );
    }

    modules.registerModule(
        "stream_parser",
        {
            EVENT_NAMES,
            getStreamEventError,
            getStreamHttpStatus,
            getStreamPacket,
            isStreamEvent,
            normalizeStreamText,
            parseEventData,
            parseServerSentEvent,
            parseServerSentEventBuffer,
            splitServerSentEventBuffer
        }
    );
})(window);