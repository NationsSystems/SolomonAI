# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/docintel_context.py
# ---------------------------------------------------------------------------

from solomon_core.logger import get_logger

logger = get_logger("docintel_context")


def _build_document_context(documents):
    try:
        text_parts = []
        meta = []

        for d in documents or []:
            txt = d.get("text")
            if isinstance(txt, str) and txt.strip():
                text_parts.append(txt.strip())

            meta.append(
                {
                    "document_id": d.get("document_id"),
                    "display_name": d.get("display_name"),
                }
            )

        joined_text = "\n\n".join(text_parts).strip()

        if not joined_text:
            logger.warning("[NARRATOR] no document text available for grounding")

        return {
            "documents": meta,
            "document_text": joined_text,
            "document_count": len(meta),
        }

    except Exception as e:
        logger.error(f"[NARRATOR] document context build failure: {e}")
        return {"documents": [], "document_text": "", "document_count": 0}