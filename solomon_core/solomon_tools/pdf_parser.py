# pdf_parser.py — Phase-26 Robust PDF → Text Extractor
# ------------------------------------------------------
# Requirements:
#   • Never crash
#   • Return "" on ANY failure
#   • Used by semantic.extract_text and summarize_document
#   • Must tolerate:
#       – encrypted PDFs
#       – malformed PDFs
#       – zero-page PDFs
#       – PyPDF2 inconsistencies
#       – metadata-only extraction failures
# ------------------------------------------------------

import io
import re
from solomon_core.logger import get_logger

logger = get_logger("pdf_parser")

try:
    import PyPDF2
except Exception:
    PyPDF2 = None
    logger.warning("[pdf_parser] PyPDF2 not available — PDF support disabled")


# ------------------------------------------------------
# Metadata / object-stream detection
# ------------------------------------------------------
_PDF_METADATA_SIGNAL_RE = re.compile(
    r"(\/Type\s*\/|xref|trailer|obj\s+\d+|\<\?xpacket|<rdf:RDF)",
    re.IGNORECASE,
)


def _looks_like_pdf_metadata(text: str) -> bool:
    """
    Returns True if extracted text appears to be
    PDF structure / metadata rather than human-readable content.
    """
    if not text:
        return True

    sample = text[:2000]

    # Very short output is not meaningful text
    if len(sample.strip()) < 100:
        return True

    # High density of metadata / object markers
    hits = len(_PDF_METADATA_SIGNAL_RE.findall(sample))
    if hits >= 3:
        return True

    # Heuristic: very low alphabetic ratio
    alpha = sum(c.isalpha() for c in sample)
    ratio = alpha / max(len(sample), 1)
    if ratio < 0.15:
        return True

    return False


def pdf_to_text(path: str) -> str:
    """
    Phase-26: SAFE PDF → text converter

    Behavior:
    • Returns extracted text ONLY if it appears human-readable
    • Returns "" if extraction yields metadata/object structure
    • Returning "" intentionally triggers OCR fallback upstream
    • Never raises
    """
    # Module unavailable
    if not PyPDF2:
        logger.warning("[pdf_parser] Called without PyPDF2 module.")
        return ""

    try:
        with open(path, "rb") as f:
            try:
                reader = PyPDF2.PdfReader(f)
            except Exception as e:
                logger.error(f"[pdf_parser] Reader init failed: {e}")
                return ""

            # Encrypted PDF → fail gracefully
            if getattr(reader, "is_encrypted", False):
                try:
                    reader.decrypt("")
                except Exception:
                    logger.warning(f"[pdf_parser] Encrypted PDF not readable: {path}")
                    return ""

            pages = getattr(reader, "pages", [])
            if not pages:
                logger.warning(f"[pdf_parser] PDF has no pages: {path}")
                return ""

            text_chunks = []

            for idx, page in enumerate(pages):
                try:
                    txt = page.extract_text() or ""
                    text_chunks.append(txt)
                except Exception as e:
                    logger.error(f"[pdf_parser] Page {idx} failed: {e}")
                    text_chunks.append("")

            final = "\n".join(text_chunks).strip()

            # --------------------------------------------------
            # 🔒 Phase-26 SAFETY: Reject metadata-only output
            # --------------------------------------------------
            if _looks_like_pdf_metadata(final):
                logger.warning(
                    f"[pdf_parser] Metadata-only extraction detected — forcing OCR: {path}"
                )
                return ""

            return final

    except Exception as e:
        logger.error(f"[pdf_parser] Failed: {e}")
        return ""
