# ------------------------------------------------------------------
# FILE: solomon_core/orchestrator_lanes/clarification_lane_handler.py
# ------------------------------------------------------------------
# Solomon Clarification Lane Handler
# ------------------------------------------------------------------


def run_clarification_lane(*, document_count: int, build_suggestions):
    payload = {"answer": "More information is required."}

    suggestions = build_suggestions("clarification", document_count)
    if suggestions:
        payload["suggestions"] = suggestions

    return payload