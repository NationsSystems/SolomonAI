# -------------------------------------------------------------------
# FILE: workspace_reader_pdf_preview.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# Server-owned PDF preview helpers for the Solomon workspace reader.
# -------------------------------------------------------------------

from io import BytesIO
from threading import Lock
from typing import Dict, List

from solomon_core.logger import get_logger
from solomon_core.workspace_reader.workspace_reader_urls import (
    build_workspace_document_page_image_url,
)

logger = get_logger("workspace_reader.pdf_preview")

PDF_RENDER_ZOOM = 1.65

_PDFIUM_OPERATION_LOCK = Lock()


def _load_pdfium():
    """Load the permissively licensed PDFium Python binding."""

    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError(
            "pypdfium2 is required for Solomon PDF preview rendering."
        ) from exc

    return pdfium


def get_pdf_page_count(source_path: str, *, request_id: str = "untracked") -> int:
    """Return the page count for a PDF using server-side parsing."""

    try:
        pdfium = _load_pdfium()

        with _PDFIUM_OPERATION_LOCK:
            pdf_doc = pdfium.PdfDocument(source_path)

            try:
                return int(len(pdf_doc))
            finally:
                pdf_doc.close()
    except Exception as exc:
        logger.warning(
            "[workspace.reader.pdf_count_failed] request_id=%s path=%s error=%s",
            request_id,
            source_path,
            exc,
        )
        return 0


def build_pdf_reader_pages(document_id: str, page_count: int) -> List[Dict]:
    """Build server-owned PDF page surface descriptors."""

    pages = []

    for page_number in range(1, int(page_count or 0) + 1):
        pages.append({
            "page_number": page_number,
            "label": f"Page {page_number}",
            "image_url": build_workspace_document_page_image_url(
                document_id,
                page_number,
            ),
        })

    return pages


def render_pdf_page_image(source_path: str, page_number: int) -> BytesIO:
    """Render a single PDF page to a PNG image stream."""

    pdfium = _load_pdfium()
    image_stream = BytesIO()

    with _PDFIUM_OPERATION_LOCK:
        pdf_doc = pdfium.PdfDocument(source_path)

        try:
            pdf_doc.init_forms()

            page_index = int(page_number) - 1
            page_count = int(len(pdf_doc))

            if page_index < 0 or page_index >= page_count:
                raise ValueError(
                    "PDF page number is outside the document range."
                )

            page = pdf_doc[page_index]

            try:
                bitmap = page.render(
                    scale=PDF_RENDER_ZOOM,
                    may_draw_forms=True,
                    draw_annots=True,
                    fill_color=(255, 255, 255, 255),
                )

                try:
                    image = bitmap.to_pil()

                    try:
                        if image.mode not in {"RGB", "L"}:
                            converted_image = image.convert("RGB")
                            image.close()
                            image = converted_image

                        image.save(
                            image_stream,
                            format="PNG",
                            optimize=False,
                        )
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()
        finally:
            pdf_doc.close()

    image_stream.seek(0)
    return image_stream