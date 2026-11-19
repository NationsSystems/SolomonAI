# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/docintel_formatting.py
# ---------------------------------------------------------------------------

import os
import re
from solomon_core.logger import get_logger

logger = get_logger("docintel_formatting")


def _format_docintel_summary(answer_text: str, documents: list) -> str:
    try:
        if not isinstance(answer_text, str) or not answer_text.strip():
            return answer_text

        if not isinstance(documents, list) or len(documents) != 1:
            return answer_text

        display_name = (
            documents[0].get("display_name")
            or documents[0].get("original_name")
            or "Document"
        )
        base_name = os.path.splitext(str(display_name))[0] or "Document"

        text = answer_text.strip()

        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]

        if len(paras) < 3:
            sentences = re.split(
                r"(?<=[.!?])\s+",
                re.sub(r"\s+", " ", text).strip(),
            )
            sentences = [s.strip() for s in sentences if s.strip()]

            if len(sentences) >= 3:
                third = max(1, len(sentences) // 3)
                paras = [
                    " ".join(sentences[:third]).strip(),
                    " ".join(sentences[third:third * 2]).strip(),
                    " ".join(sentences[third * 2:]).strip(),
                ]
            else:
                while len(paras) < 3:
                    paras.append(text)

        while len(paras) < 3:
            paras.append(paras[-1] if paras else text)

        paras = paras[:3]

        title = f"Summary — {base_name}"

        formatted = (
            f"{title}\n"
            f"{paras[0]}\n"
            f"{base_name}\n"
            f"{paras[1]}\n"
            f"{base_name}\n"
            f"{paras[2]}"
        )

        return formatted.strip()

    except Exception as e:
        logger.warning(f"[DOCINTEL_FORMAT] non-fatal formatting failure: {e}")
        return answer_text