/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_response_packet.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI response-packet normalization.

   Reads JSON responses and extracts answer, continuation, identifiers,
   and failure text from supported server packet shapes. JavaScript
   normalizes transport data only; packet authority remains server-owned.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before response packets."
        );
    }

    const { cleanValue } = modules.requireModule("contract");

    function isObjectRecord(value) {
        return Boolean(
            value &&
            typeof value === "object" &&
            !Array.isArray(value)
        );
    }

    async function readResponsePacket(response) {
        const responseText = await response.text();

        if (!responseText) {
            return {};
        }

        try {
            return JSON.parse(responseText);
        } catch (error) {
            return {
                ok: response.ok,
                user_output: responseText
            };
        }
    }

    function extractResponseText(packet) {
        const result = packet?.result;
        const resultPayload = result?.payload;
        const packetPayload = packet?.payload;
        const candidates = [
            typeof result === "string" ? result : "",
            result?.answer,
            result?.user_output,
            result?.message,
            result?.response,
            result?.text,
            resultPayload?.answer,
            resultPayload?.user_output,
            resultPayload?.message,
            packet?.user_output,
            packet?.answer,
            packet?.message,
            packet?.response,
            packet?.text,
            packetPayload?.answer,
            packetPayload?.user_output,
            packetPayload?.message,
            packet?.error
        ];

        for (const candidate of candidates) {
            const cleanCandidate = cleanValue(candidate);

            if (cleanCandidate) {
                return cleanCandidate;
            }
        }

        return "";
    }

    function normalizeResponseSuggestions(value) {
        if (!Array.isArray(value)) {
            return [];
        }

        const seen = new Set();
        const suggestions = [];

        value.forEach(function (item) {
            const suggestion = cleanValue(item);
            const normalizedSuggestion = suggestion.toLowerCase();

            if (
                !suggestion ||
                seen.has(normalizedSuggestion)
            ) {
                return;
            }

            seen.add(normalizedSuggestion);
            suggestions.push(suggestion);
        });

        return suggestions;
    }

    function extractResponsePresentation(packet) {
        const result = packet?.result;
        const candidates = [
            result?.payload,
            result,
            packet?.payload,
            packet
        ].filter(isObjectRecord);
        let bridge = "";
        let suggestions = [];

        candidates.forEach(function (candidate) {
            if (!bridge) {
                bridge = cleanValue(candidate?.bridge);
            }

            if (!suggestions.length) {
                suggestions = normalizeResponseSuggestions(
                    candidate?.suggestions
                );
            }
        });

        return {
            bridge,
            suggestions
        };
    }

    function extractResponseIdentity(packet) {
        const result = packet?.result;
        const candidates = [
            packet,
            packet?.payload,
            result,
            result?.payload
        ].filter(isObjectRecord);
        let requestId = "";
        let messageId = "";

        candidates.forEach(function (candidate) {
            if (!requestId) {
                requestId = cleanValue(
                    candidate?.request_id ||
                    candidate?.requestId
                );
            }

            if (!messageId) {
                messageId = cleanValue(
                    candidate?.message_id ||
                    candidate?.messageId ||
                    candidate?.assistant_message_id
                );
            }
        });

        return {
            requestId,
            messageId
        };
    }

    function normalizeHttpStatus(value, fallback) {
        const status = Number.parseInt(value, 10);

        if (
            Number.isInteger(status) &&
            status >= 100 &&
            status <= 599
        ) {
            return status;
        }

        const fallbackStatus = Number.parseInt(fallback, 10);

        return Number.isInteger(fallbackStatus)
            ? fallbackStatus
            : 0;
    }

    function isResponseFailure(packet, statusCode) {
        const status = normalizeHttpStatus(
            statusCode,
            packet?.http_status
        );
        const packetStatus = cleanValue(
            packet?.status
        ).toLowerCase();

        return Boolean(
            status >= 400 ||
            packet?.ok === false ||
            packetStatus === "failed" ||
            packetStatus === "error"
        );
    }

    function extractResponseError(packet, statusCode) {
        const responseText = extractResponseText(packet);

        if (responseText) {
            return responseText;
        }

        const status = normalizeHttpStatus(
            statusCode,
            packet?.http_status
        );

        return status
            ? `Request failed: ${status}`
            : "The SolomonAI request failed.";
    }

    function getResponseDisplayText(packet, fallbackText) {
        return (
            extractResponseText(packet) ||
            cleanValue(fallbackText) ||
            "The server returned no SolomonAI message."
        );
    }

    function normalizeResponsePacket(packet, statusCode) {
        const safePacket = isObjectRecord(packet)
            ? packet
            : {};
        const status = normalizeHttpStatus(
            statusCode,
            safePacket?.http_status
        );

        return {
            packet: safePacket,
            status,
            failed: isResponseFailure(safePacket, status),
            text: extractResponseText(safePacket),
            presentation: extractResponsePresentation(
                safePacket
            ),
            identity: extractResponseIdentity(safePacket)
        };
    }

    modules.registerModule("response_packet", {
        extractResponseError,
        extractResponseIdentity,
        extractResponsePresentation,
        extractResponseText,
        getResponseDisplayText,
        isObjectRecord,
        isResponseFailure,
        normalizeHttpStatus,
        normalizeResponsePacket,
        normalizeResponseSuggestions,
        readResponsePacket
    });
})(window);