# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/docintel_partition.py
# ---------------------------------------------------------------------------

from solomon_core.logger import get_logger

logger = get_logger("docintel_partition")


def _deterministic_partition(signals, documents):
    partitioned = {}

    for doc in documents:
        doc_id = doc.get("document_id")

        doc_view = {}
        total_assigned = 0

        for family, items in (signals or {}).items():
            if not isinstance(items, list):
                doc_view[family] = []
                continue

            filtered = [
                item
                for item in items
                if isinstance(item, dict)
                and item.get("document_id") == doc_id
            ]

            total_assigned += len(filtered)
            doc_view[family] = filtered

        partitioned[doc_id] = doc_view

        logger.info(
            "[PARTITION][DOC_SCOPE]",
            extra={
                "document_id": doc_id,
                "signals_assigned": total_assigned,
            },
        )

    return partitioned