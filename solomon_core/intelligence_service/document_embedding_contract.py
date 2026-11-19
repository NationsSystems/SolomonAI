# -------------------------------------------------------------------
# FILE: document_embedding_contract.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Shared durable contract identifiers for document evidence embeddings.
#
# This module contains identity and deterministic chunking constants only. It
# does not enqueue work, execute models, read files, authorize users, or own
# SIS/web lifecycle.
# -------------------------------------------------------------------

DOCUMENT_EMBEDDING_JOB_TYPE = "generate_document_embeddings"
DOCUMENT_EMBEDDING_ARTIFACT_TYPE = "document_embeddings"
DOCUMENT_EMBEDDING_TARGET_TYPE = "file"
DOCUMENT_EMBEDDING_TRIGGER_TYPE = "file_upload"
DOCUMENT_EMBEDDING_LAZY_TRIGGER_TYPE = "large_resource_lazy_prepare"
DOCUMENT_EMBEDDING_PROCESSOR_KEY = "document_embeddings"
# v1.1 persists the document intelligence map alongside the canonical chunk manifest.
# Bumping this version makes old/current-source artifacts lazily requalify instead of
# being mistaken for the newer large-resource preparation contract.
DOCUMENT_EMBEDDING_PROCESSOR_VERSION = "1.1"
DOCUMENT_EMBEDDING_REUSABLE_PROCESSOR_VERSIONS = ("1.0", "1.1")
DOCUMENT_EMBEDDING_SOURCE = "sis_document_embeddings_v1"

# Large-resource document intelligence map. This is persisted alongside the
# existing chunk manifest in WorkspaceIntelligenceObject.metadata_json, so no
# schema migration or parallel index is required.
DOCUMENT_INTELLIGENCE_MAP_CONTRACT = "solomon_document_intelligence_map_v1"
DOCUMENT_INTELLIGENCE_MAP_MAX_BANDS = 24

# Retrieval-critical embeddings outrank optional background summaries in the
# durable Intelligence Spool. The repository dispatches lower numeric priority
# values first, so this value must remain below AUTO_SUMMARY_PRIORITY.
DOCUMENT_EMBEDDING_PRIORITY = 80

# Keep the first durable evidence representation aligned with the proven RAG
# lane behavior so moving from ephemeral to persisted retrieval does not also
# change retrieval granularity.
DOCUMENT_EMBEDDING_CHUNK_CHARS = 1200
DOCUMENT_EMBEDDING_CHUNK_OVERLAP = 180

# Stage-based progress remains deterministic. The embedding model call itself
# is opaque, so progress advances only at durable processor boundaries.
DOCUMENT_EMBEDDING_PROGRESS_SOURCE_VALIDATED = 15
DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_STARTED = 25
DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_COMPLETE = 45
DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_STARTED = 55
DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_COMPLETE = 85
DOCUMENT_EMBEDDING_PROGRESS_PERSISTENCE_STARTED = 90
DOCUMENT_EMBEDDING_PROGRESS_ARTIFACT_READY = 95


__all__ = [
    "DOCUMENT_EMBEDDING_ARTIFACT_TYPE",
    "DOCUMENT_EMBEDDING_CHUNK_CHARS",
    "DOCUMENT_EMBEDDING_CHUNK_OVERLAP",
    "DOCUMENT_EMBEDDING_JOB_TYPE",
    "DOCUMENT_EMBEDDING_LAZY_TRIGGER_TYPE",
    "DOCUMENT_INTELLIGENCE_MAP_CONTRACT",
    "DOCUMENT_INTELLIGENCE_MAP_MAX_BANDS",
    "DOCUMENT_EMBEDDING_PRIORITY",
    "DOCUMENT_EMBEDDING_PROCESSOR_KEY",
    "DOCUMENT_EMBEDDING_PROCESSOR_VERSION",
    "DOCUMENT_EMBEDDING_REUSABLE_PROCESSOR_VERSIONS",
    "DOCUMENT_EMBEDDING_PROGRESS_ARTIFACT_READY",
    "DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_COMPLETE",
    "DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_STARTED",
    "DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_COMPLETE",
    "DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_STARTED",
    "DOCUMENT_EMBEDDING_PROGRESS_PERSISTENCE_STARTED",
    "DOCUMENT_EMBEDDING_PROGRESS_SOURCE_VALIDATED",
    "DOCUMENT_EMBEDDING_SOURCE",
    "DOCUMENT_EMBEDDING_TARGET_TYPE",
    "DOCUMENT_EMBEDDING_TRIGGER_TYPE",
]
