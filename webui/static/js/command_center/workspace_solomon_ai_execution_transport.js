/* -------------------------------------------------------------------
   FILE: workspace_solomon_ai_execution_transport.js
   DIRECTORY: webui/static/js/command_center/
----------------------------------------------------------------------
   SolomonAI execution transport.

   Posts execution envelopes through the existing JSON or server-sent-event
   endpoints and forwards normalized stream stages to request orchestration.
   JavaScript transports server packets only; execution authority remains
   server-owned.
------------------------------------------------------------------- */

(function (window) {
    "use strict";

    const modules = window.SolomonAIWorkspaceModules;

    if (!modules) {
        throw new Error(
            "SolomonAI workspace contract must load before execution transport."
        );
    }

    const contract = modules.requireModule("contract");
    const responsePacket = modules.requireModule("response_packet");
    const streamParser = modules.requireModule("stream_parser");
    const { constants, cleanValue } = contract;
    const { EVENT_NAMES } = streamParser;

    function getExecutionEndpoint() {
        return cleanValue(
            constants.EXECUTION_ENDPOINT
        ) || "/api/task/execute";
    }

    function getExecutionStreamEndpoint() {
        return cleanValue(
            constants.EXECUTION_STREAM_ENDPOINT
        ) || "/api/task/execute/stream";
    }

    function buildExecutionHeaders(accept) {
        return {
            "Accept": accept,
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest"
        };
    }

    async function postExecution(payload) {
        const response = await fetch(
            getExecutionEndpoint(),
            {
                method: "POST",
                credentials: "same-origin",
                headers: buildExecutionHeaders(
                    "application/json"
                ),
                body: JSON.stringify(payload)
            }
        );
        const packet = await responsePacket.readResponsePacket(
            response
        );

        return {
            response,
            packet,
            status: response.status,
            streamed: false
        };
    }

    function supportsStreamReader(response) {
        return Boolean(
            response?.ok &&
            response.body &&
            typeof response.body.getReader === "function"
        );
    }

    function createStreamState(response) {
        return {
            finalPacket: null,
            finalStatus: response.status,
            streamError: ""
        };
    }

    function dispatchStreamEvent(
        parsedEvent,
        state,
        handlers,
        responseStatus
    ) {
        if (!parsedEvent) {
            return false;
        }

        const eventData = parsedEvent.data;

        if (
            streamParser.isStreamEvent(
                parsedEvent,
                EVENT_NAMES.OPEN
            )
        ) {
            handlers?.onOpen?.(eventData);
            return true;
        }

        if (
            streamParser.isStreamEvent(
                parsedEvent,
                EVENT_NAMES.ANSWER
            )
        ) {
            handlers?.onAnswer?.(eventData);
            return true;
        }

        if (
            streamParser.isStreamEvent(
                parsedEvent,
                EVENT_NAMES.PACKET
            )
        ) {
            state.finalStatus = streamParser.getStreamHttpStatus(
                parsedEvent,
                responseStatus
            );
            state.finalPacket = streamParser.getStreamPacket(
                parsedEvent
            );
            handlers?.onPacket?.(
                state.finalPacket,
                state.finalStatus
            );
            return true;
        }

        if (
            streamParser.isStreamEvent(
                parsedEvent,
                EVENT_NAMES.ERROR
            )
        ) {
            state.streamError = streamParser.getStreamEventError(
                parsedEvent
            );
            handlers?.onError?.(eventData);
            return true;
        }

        handlers?.onEvent?.(parsedEvent);
        return false;
    }

    function dispatchBufferedEvents(
        buffer,
        state,
        handlers,
        responseStatus,
        options
    ) {
        const parsed = streamParser.parseServerSentEventBuffer(
            buffer,
            options
        );

        parsed.events.forEach(function (parsedEvent) {
            dispatchStreamEvent(
                parsedEvent,
                state,
                handlers,
                responseStatus
            );
        });

        return parsed.remaining;
    }

    async function fallbackToJsonExecution(
        payload,
        handlers
    ) {
        const fallback = await postExecution(payload);

        handlers?.onPacket?.(
            fallback.packet,
            fallback.status
        );

        return fallback;
    }

    async function postExecutionStream(
        payload,
        handlers
    ) {
        const response = await fetch(
            getExecutionStreamEndpoint(),
            {
                method: "POST",
                credentials: "same-origin",
                headers: buildExecutionHeaders(
                    "text/event-stream"
                ),
                body: JSON.stringify(payload)
            }
        );

        if (!supportsStreamReader(response)) {
            return fallbackToJsonExecution(
                payload,
                handlers
            );
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder("utf-8");
        const state = createStreamState(response);
        let buffer = "";

        while (true) {
            const { value, done } = await reader.read();

            if (value) {
                buffer += decoder.decode(
                    value,
                    { stream: !done }
                );
                buffer = dispatchBufferedEvents(
                    buffer,
                    state,
                    handlers,
                    response.status
                );
            }

            if (done) {
                break;
            }
        }

        buffer += decoder.decode();
        buffer = dispatchBufferedEvents(
            buffer,
            state,
            handlers,
            response.status,
            { flush: true }
        );

        if (state.streamError) {
            throw new Error(
                state.streamError
            );
        }

        if (state.finalPacket === null) {
            throw new Error(
                "The SolomonAI stream ended without a final response packet."
            );
        }

        return {
            response,
            packet: state.finalPacket,
            status: state.finalStatus,
            streamed: true
        };
    }

    modules.registerModule(
        "execution_transport",
        {
            buildExecutionHeaders,
            createStreamState,
            dispatchBufferedEvents,
            dispatchStreamEvent,
            fallbackToJsonExecution,
            getExecutionEndpoint,
            getExecutionStreamEndpoint,
            postExecution,
            postExecutionStream,
            supportsStreamReader
        }
    );
})(window);