# -------------------------------------------------------------------
# FILE: document_summary_contract.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Shared durable contract identifiers for automatic document summaries.
#
# This module contains identity only. It does not enqueue work, execute models,
# read files, authorize users, or own SIS/web lifecycle.
# -------------------------------------------------------------------

AUTO_SUMMARY_JOB_TYPE = "generate_document_summary"
AUTO_SUMMARY_ARTIFACT_TYPE = "document_summary"
AUTO_SUMMARY_TARGET_TYPE = "file"
AUTO_SUMMARY_TRIGGER_TYPE = "file_upload"
AUTO_SUMMARY_PROCESSOR_KEY = "document_summary"
AUTO_SUMMARY_PROCESSOR_VERSION = "2.4"
AUTO_SUMMARY_SOURCE = "sis_auto_summary_v2"
AUTO_SUMMARY_PRIORITY = 100
AUTO_SUMMARY_CALL_SITE = "docintel_summary_narration"
AUTO_SUMMARY_CONTEXT_CONTRACT = "balanced_source_context_v2_tabular_rows_v2"

# Stage-based progress is intentionally deterministic. The opaque model decode
# interval is never represented as fabricated token-by-token progress; the
# percentage advances only when a durable processor stage is actually reached.
AUTO_SUMMARY_PROGRESS_SOURCE_VALIDATED = 15
AUTO_SUMMARY_PROGRESS_EXTRACTION_STARTED = 25
AUTO_SUMMARY_PROGRESS_EXTRACTION_COMPLETE = 45
AUTO_SUMMARY_PROGRESS_GENERATION_STARTED = 55
AUTO_SUMMARY_PROGRESS_GENERATION_COMPLETE = 85
AUTO_SUMMARY_PROGRESS_PERSISTENCE_STARTED = 90
AUTO_SUMMARY_PROGRESS_ARTIFACT_READY = 95


__all__ = [
    "AUTO_SUMMARY_ARTIFACT_TYPE",
    "AUTO_SUMMARY_CALL_SITE",
    "AUTO_SUMMARY_CONTEXT_CONTRACT",
    "AUTO_SUMMARY_JOB_TYPE",
    "AUTO_SUMMARY_PRIORITY",
    "AUTO_SUMMARY_PROCESSOR_KEY",
    "AUTO_SUMMARY_PROCESSOR_VERSION",
    "AUTO_SUMMARY_PROGRESS_ARTIFACT_READY",
    "AUTO_SUMMARY_PROGRESS_EXTRACTION_COMPLETE",
    "AUTO_SUMMARY_PROGRESS_EXTRACTION_STARTED",
    "AUTO_SUMMARY_PROGRESS_GENERATION_COMPLETE",
    "AUTO_SUMMARY_PROGRESS_GENERATION_STARTED",
    "AUTO_SUMMARY_PROGRESS_PERSISTENCE_STARTED",
    "AUTO_SUMMARY_PROGRESS_SOURCE_VALIDATED",
    "AUTO_SUMMARY_SOURCE",
    "AUTO_SUMMARY_TARGET_TYPE",
    "AUTO_SUMMARY_TRIGGER_TYPE",
]
