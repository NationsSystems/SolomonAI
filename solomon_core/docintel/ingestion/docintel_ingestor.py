# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/ingestion/docintel_ingestor.py
# DIRECTORY: solomon_core/docintel/ingestion/
# ---------------------------------------------------------------------------
# DocIntel Ingestor — Evidence-Bound, Read-Only
#
# PURPOSE
#   Extract document text and explicit document signals without allowing one
#   extraction method to destroy valid evidence found by another method.
# ---------------------------------------------------------------------------

from dataclasses import dataclass
from pathlib import Path
from time import monotonic
from typing import Callable, Dict, List, Optional
import re
import subprocess
import sys
import tempfile
import zipfile
import xml.etree.ElementTree as ET

from config import settings
from solomon_core.docintel.extractors.explicit_section_extractor import (
    extract_sections,
)
from solomon_core.docintel.extractors.explicit_structural_signal_extractor import (
    extract_structural_signals,
)
from solomon_core.docintel.extractors.explicit_value_extractor import (
    extract_explicit_values,
)
from solomon_core.docintel.ingestion.afr_detector import build_afr_for_documents
from solomon_core.docintel.intent.explicit_intent import ExplicitIntent
from solomon_core.db import SessionLocal
from solomon_core.logger import get_logger
from solomon_core.models import FileRegistry
from solomon_core.workspace_reader.workspace_reader_csv_preview import (
    build_csv_preview,
    build_csv_preview_text_blocks,
    get_csv_preview_non_empty_cells,
)
from solomon_core.workspace_reader.workspace_reader_xls_preview import (
    build_xls_preview,
    build_xls_preview_text_blocks,
    get_xls_preview_non_empty_cells,
)
from solomon_core.workspace_reader.workspace_reader_tabular_evidence import (
    TABULAR_EVIDENCE_CONTRACT,
)
from solomon_core.workspace_reader.workspace_reader_xlsx_preview import (
    build_xlsx_preview,
    build_xlsx_preview_text_blocks,
    get_xlsx_preview_non_empty_cells,
)

logger = get_logger("docintel.ingestor")


class DocIntelIngestError(Exception):
    pass


@dataclass(frozen=True)
class DocIntelExtractionPolicy:
    """Optional bounded evidence policy for task-specific document ingest.

    Canonical DocIntel callers that do not supply a policy retain exhaustive
    extraction behavior. The policy is intended for derived artifacts such as
    Auto Summary whose semantic contract requires representative coverage, not
    line-by-line source exhaustion.
    """

    name: str
    max_pdf_pages: int
    leading_pdf_pages: int
    trailing_pdf_pages: int
    min_pdf_pages: int
    target_extracted_chars: int
    max_pdf_seconds: float
    ocr_dpi: int


@dataclass(frozen=True)
class _BoundedExtractionResult:
    text: str
    metadata: Dict


DocIntelProgressCallback = Callable[[Dict], None]


# ---------------------------------------------------------------------------
# Text Hygiene / Evidence Scoring
# ---------------------------------------------------------------------------

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_CURRENCY_RE = re.compile(r"\$\s*[\d,]+(?:\.\d{2})?")
_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")
_EVIDENCE_WORD_RE = re.compile(
    r"\b("
    r"bid|proposal|scope|price|pricing|total|amount|addenda|alternate|"
    r"allowance|exclusion|clarification|schedule|mobilization|drawing|"
    r"permit|engineering|temporary|utility|hazardous|condition"
    r")\b",
    re.I,
)
_LINE_PREFIX_RE = re.compile(
    r"^(?:ao|o&|aÂ«|oÂ«|Â©|Â«|[ao]|&|@|•|-|–|—)\s+",
    re.I,
)
_WORD_XML_NAMESPACE = (
    "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
)
SUPPORTED_TEXT_SUFFIXES = frozenset({
    ".pdf",
    ".docx",
    ".txt",
    ".csv",
    ".xlsx",
    ".xls",
})

_NATIVE_PDF_MIN_CHARS = 1200
_NATIVE_PDF_MIN_WORDS = 180
_NATIVE_PDF_MIN_NONEMPTY_LINES = 8
_NATIVE_PDF_MIN_PRINTABLE_RATIO = 0.90
_NATIVE_PDF_MIN_ALPHANUMERIC_RATIO = 0.45
_NATIVE_PDF_STRONG_ALPHANUMERIC_RATIO = 0.60
_NATIVE_PDF_STRONG_WORD_COUNT = 350
_NATIVE_PDF_STRONG_LINE_COUNT = 20
_NATIVE_PDF_MAX_ACCEPTABLE_FRACTURE_RATIO = 0.30
_NATIVE_PDF_MAX_ACCEPTABLE_GLUED_RATIO = 0.18
_NATIVE_PDF_MAX_ACCEPTABLE_SHORT_TOKEN_RATIO = 0.25


def _sanitize_extracted_text(text: str) -> str:
    """Remove non-printable control characters without destroying line breaks."""

    if not text:
        return ""

    cleaned = _CONTROL_CHAR_RE.sub(" ", text)
    cleaned = re.sub(r"[ ]{2,}", " ", cleaned)

    return cleaned.strip()


def _currency_to_float(value: str) -> float:
    try:
        return float(
            value.replace("$", "")
            .replace(",", "")
            .strip()
        )
    except Exception:
        return 0.0


def _extraction_evidence_score(text: str) -> float:
    """
    Score extraction usefulness as evidence, not routing authority.

    This score helps choose/preserve the best text extraction result when OCR
    fallback and vector extraction disagree.
    """

    if not isinstance(text, str) or not text.strip():
        return 0.0

    currencies = _CURRENCY_RE.findall(text)
    dates = _DATE_RE.findall(text)
    words = _EVIDENCE_WORD_RE.findall(text)
    largest_currency = max(
        (
            _currency_to_float(value)
            for value in currencies
        ),
        default=0.0,
    )

    score = min(
        len(text.strip()) / 500.0,
        20.0,
    )
    score += min(
        len(currencies) * 4.0,
        24.0,
    )
    score += min(
        len(dates) * 2.0,
        10.0,
    )
    score += min(
        len(words) * 0.35,
        20.0,
    )

    if largest_currency >= 10000:
        score += 12.0

    return score


def _line_key(line: str) -> str:
    cleaned = (
        str(line or "")
        .replace("\u00a0", " ")
        .strip()
    )
    cleaned = _LINE_PREFIX_RE.sub(
        "",
        cleaned,
    ).strip()
    cleaned = re.sub(
        r"\s+",
        " ",
        cleaned,
    )

    return cleaned.lower()


def _merge_extracted_texts(
    primary: str,
    fallback: str,
) -> str:
    """
    Preserve unique evidence from two extraction methods while reducing exact
    duplicate lines. The primary extractor remains first so document order is
    mostly preserved.
    """

    blocks: List[str] = []
    seen = set()

    for text in (
        primary,
        fallback,
    ):
        if not isinstance(text, str) or not text.strip():
            continue

        output_lines: List[str] = []

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            key = _line_key(line)

            if not key:
                if (
                    output_lines
                    and output_lines[-1]
                ):
                    output_lines.append("")

                continue

            if key in seen:
                continue

            seen.add(key)
            output_lines.append(line)

        block = "\n".join(
            output_lines
        ).strip()

        if block:
            blocks.append(block)

    return "\n\n".join(blocks).strip()


def _should_preserve_vector_text(
    vector_text: str,
    ocr_text: str,
) -> bool:
    vector_score = _extraction_evidence_score(
        vector_text
    )
    ocr_score = _extraction_evidence_score(
        ocr_text
    )

    if vector_score >= 10:
        return True

    if (
        vector_score >= (ocr_score * 0.65)
        and len(vector_text.strip()) >= 500
    ):
        return True

    return False


# ---------------------------------------------------------------------------
# Raw Text Probe
# ---------------------------------------------------------------------------

def _raw_text_probe_enabled() -> bool:
    return bool(
        settings.DOCINTEL_RAW_TEXT_PROBE_ENABLED
    )


def _emit_raw_text_probe(
    *,
    file_name: str,
    method: str,
    text: str,
) -> None:
    if not _raw_text_probe_enabled():
        return

    try:
        if not isinstance(text, str) or not text.strip():
            return

        max_preview = 8000
        preview = text[:max_preview]

        sys.stdout.write("\n")
        sys.stdout.write(
            "========== SOLOMON RAW TEXT PROBE ==========\n"
        )
        sys.stdout.write(
            f"FILE: {file_name}\n"
        )
        sys.stdout.write(
            f"METHOD: {method}\n"
        )
        sys.stdout.write(
            f"CHARS_TOTAL: {len(text)}\n"
        )
        sys.stdout.write(
            f"CHARS_SHOWN: {len(preview)}\n"
        )
        sys.stdout.write(
            "---------------------------------------------\n"
        )
        sys.stdout.write(preview)
        sys.stdout.write(
            "\n========== END RAW TEXT PROBE ===============\n\n"
        )
        sys.stdout.flush()
    except Exception as exc:
        logger.warning(
            "[RAW_TEXT_PROBE_FAIL]",
            extra={
                "error": str(exc),
            },
        )


# ---------------------------------------------------------------------------
# PDF Text Extraction
# ---------------------------------------------------------------------------

def _emit_extraction_progress(
    callback: Optional[DocIntelProgressCallback],
    **payload,
) -> None:
    if callback is None:
        return

    callback(dict(payload))


def _selected_pdf_pages(
    total_pages: int,
    policy: DocIntelExtractionPolicy,
) -> List[int]:
    """Return a deterministic representative 1-based page plan."""

    if total_pages <= 0:
        return []

    max_pages = max(1, int(policy.max_pdf_pages))
    if total_pages <= max_pages:
        return list(range(1, total_pages + 1))

    leading_count = min(
        max(0, int(policy.leading_pdf_pages)),
        max_pages,
        total_pages,
    )
    trailing_count = min(
        max(0, int(policy.trailing_pdf_pages)),
        max_pages - leading_count,
        max(0, total_pages - leading_count),
    )

    selected = list(range(1, leading_count + 1))
    trailing_start = max(leading_count + 1, total_pages - trailing_count + 1)
    trailing = list(range(trailing_start, total_pages + 1))
    selected_set = set(selected) | set(trailing)
    distributed_slots = max_pages - len(selected_set)

    if distributed_slots > 0:
        for slot in range(1, distributed_slots + 1):
            candidate = int(
                round(
                    1
                    + (
                        slot
                        * (total_pages - 1)
                        / (distributed_slots + 1)
                    )
                )
            )
            candidate = max(1, min(total_pages, candidate))

            if candidate in selected_set:
                for radius in range(1, total_pages + 1):
                    lower = candidate - radius
                    upper = candidate + radius
                    if 1 <= lower <= total_pages and lower not in selected_set:
                        candidate = lower
                        break
                    if 1 <= upper <= total_pages and upper not in selected_set:
                        candidate = upper
                        break

            if candidate not in selected_set:
                selected_set.add(candidate)

    if len(selected_set) < max_pages:
        for page_number in range(1, total_pages + 1):
            if page_number in selected_set:
                continue
            selected_set.add(page_number)
            if len(selected_set) >= max_pages:
                break

    return sorted(selected_set)


def _pdf_acquisition_order(
    selected_pages: List[int],
    policy: DocIntelExtractionPolicy,
) -> List[int]:
    """Favor document structure early while preserving broad coverage."""

    if not selected_pages:
        return []

    selected_set = set(selected_pages)
    leading = [
        page
        for page in selected_pages
        if page <= max(0, int(policy.leading_pdf_pages))
    ]
    trailing = [
        page
        for page in selected_pages
        if page not in leading
        and page >= max(selected_pages) - max(0, int(policy.trailing_pdf_pages)) + 1
    ]
    interior = [
        page
        for page in selected_pages
        if page not in set(leading)
        and page not in set(trailing)
    ]

    order: List[int] = []
    for page in leading:
        if page in selected_set and page not in order:
            order.append(page)

    if trailing:
        final_page = trailing[-1]
        if final_page not in order:
            order.append(final_page)

    if interior:
        center = (min(selected_pages) + max(selected_pages)) / 2.0
        for page in sorted(interior, key=lambda value: (abs(value - center), value)):
            if page not in order:
                order.append(page)

    for page in trailing:
        if page not in order:
            order.append(page)

    for page in selected_pages:
        if page not in order:
            order.append(page)

    return order


def _bounded_pdf_vector_text(
    path: Path,
    *,
    selected_pages: List[int],
    progress_callback: Optional[DocIntelProgressCallback],
) -> tuple[str, int, List[int]]:
    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(str(path))
    except Exception as exc:
        raise DocIntelIngestError(
            f"PyPDF2 failed opening PDF: {path.name}"
        ) from exc

    total_pages = len(reader.pages)
    blocks = []
    pages_with_text: List[int] = []

    for completed, page_number in enumerate(selected_pages, start=1):
        try:
            text = reader.pages[page_number - 1].extract_text() or ""
        except Exception as exc:
            raise DocIntelIngestError(
                "PyPDF2 failed extracting page "
                f"{page_number} of {path.name}"
            ) from exc

        clean_page = _sanitize_extracted_text(text)
        if clean_page:
            pages_with_text.append(page_number)
            blocks.append(
                (
                    page_number,
                    f"[SOURCE PAGE {page_number} OF {total_pages}]\n{clean_page}",
                )
            )

        _emit_extraction_progress(
            progress_callback,
            phase="native_text_probe",
            completed_pages=completed,
            planned_pages=len(selected_pages),
            source_page=page_number,
            source_page_count=total_pages,
            evidence_chars=sum(len(block) for _, block in blocks),
        )

    return (
        "\n\n".join(block for _, block in sorted(blocks)),
        total_pages,
        pages_with_text,
    )


def _bounded_pdf_ocr_text(
    path: Path,
    *,
    total_pages: int,
    selected_pages: List[int],
    policy: DocIntelExtractionPolicy,
    progress_callback: Optional[DocIntelProgressCallback],
) -> tuple[str, List[int], str, float]:
    started_at = monotonic()
    blocks = []
    processed_pages: List[int] = []
    stop_reason = "page_budget_complete"
    acquisition_order = _pdf_acquisition_order(selected_pages, policy)
    bounded_source = total_pages > len(selected_pages)

    try:
        with tempfile.TemporaryDirectory() as temp_directory:
            temp_path = Path(temp_directory)

            for page_number in acquisition_order:
                elapsed = monotonic() - started_at
                remaining_seconds = float(policy.max_pdf_seconds) - elapsed
                if remaining_seconds <= 0 and processed_pages:
                    stop_reason = "time_budget_reached"
                    break

                image_prefix = temp_path / f"page-{page_number}"
                render_timeout = max(1.0, remaining_seconds)

                try:
                    subprocess.run(
                        [
                            "pdftoppm",
                            "-f",
                            str(page_number),
                            "-l",
                            str(page_number),
                            "-singlefile",
                            "-r",
                            str(int(policy.ocr_dpi)),
                            "-png",
                            "-gray",
                            str(path),
                            str(image_prefix),
                        ],
                        check=True,
                        capture_output=True,
                        timeout=render_timeout,
                    )
                except subprocess.TimeoutExpired:
                    if processed_pages:
                        stop_reason = "time_budget_reached"
                        break
                    raise

                image_path = image_prefix.with_suffix(".png")
                elapsed = monotonic() - started_at
                remaining_seconds = float(policy.max_pdf_seconds) - elapsed
                if remaining_seconds <= 0 and processed_pages:
                    stop_reason = "time_budget_reached"
                    break

                ocr_timeout = max(1.0, remaining_seconds)

                try:
                    result = subprocess.run(
                        [
                            "tesseract",
                            str(image_path),
                            "stdout",
                            "--psm",
                            "6",
                            "-l",
                            "eng",
                        ],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=ocr_timeout,
                    )
                except subprocess.TimeoutExpired:
                    if processed_pages:
                        stop_reason = "time_budget_reached"
                        break
                    raise

                clean_page = _sanitize_extracted_text(result.stdout or "")
                processed_pages.append(page_number)
                if clean_page:
                    blocks.append(
                        (
                            page_number,
                            f"[SOURCE PAGE {page_number} OF {total_pages}]\n{clean_page}",
                        )
                    )

                evidence_chars = sum(len(block) for _, block in blocks)
                elapsed = monotonic() - started_at
                _emit_extraction_progress(
                    progress_callback,
                    phase="ocr_evidence",
                    completed_pages=len(processed_pages),
                    planned_pages=len(selected_pages),
                    source_page=page_number,
                    source_page_count=total_pages,
                    evidence_chars=evidence_chars,
                    elapsed_seconds=round(elapsed, 2),
                )

                if (
                    bounded_source
                    and len(processed_pages) >= int(policy.min_pdf_pages)
                    and evidence_chars >= int(policy.target_extracted_chars)
                ):
                    stop_reason = "evidence_target_reached"
                    break

                if elapsed >= float(policy.max_pdf_seconds):
                    stop_reason = "time_budget_reached"
                    break

        return (
            "\n\n".join(block for _, block in sorted(blocks)),
            processed_pages,
            stop_reason,
            round(monotonic() - started_at, 2),
        )
    except Exception as exc:
        raise DocIntelIngestError(
            "Bounded OCR extraction failed"
        ) from exc


def _extract_pdf_text_bounded(
    path: Path,
    *,
    policy: DocIntelExtractionPolicy,
    progress_callback: Optional[DocIntelProgressCallback],
) -> _BoundedExtractionResult:
    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(str(path))
        total_pages = len(reader.pages)
    except Exception as exc:
        raise DocIntelIngestError(
            f"PyPDF2 failed opening PDF: {path.name}"
        ) from exc

    selected_pages = _selected_pdf_pages(total_pages, policy)
    if not selected_pages:
        raise DocIntelIngestError(
            f"PDF contains no processable pages: {path.name}"
        )

    logger.info(
        "[DOCINTEL][EVIDENCE_PLAN]",
        extra={
            "file": path.name,
            "policy": policy.name,
            "source_page_count": total_pages,
            "selected_pages": selected_pages,
            "page_budget": int(policy.max_pdf_pages),
            "ocr_dpi": int(policy.ocr_dpi),
            "max_pdf_seconds": float(policy.max_pdf_seconds),
        },
    )

    logger.info(
        "[DOCINTEL][TEXT][TRY_PYPDF2]",
        extra={
            "file": path.name,
            "bounded": True,
            "selected_pages": selected_pages,
        },
    )
    vector_text, _, native_pages = _bounded_pdf_vector_text(
        path,
        selected_pages=selected_pages,
        progress_callback=progress_callback,
    )
    vector_text = _sanitize_extracted_text(vector_text)

    logger.info(
        "[DOCINTEL][TEXT][PYPDF2_OK]",
        extra={
            "chars": len(vector_text),
            "evidence_score": round(_extraction_evidence_score(vector_text), 2),
            "bounded": True,
        },
    )

    from solomon_core.docintel.ingestion.text_quality_gate import (
        evaluate_text_quality,
    )

    fast_suspect = _fast_text_suspect(vector_text)
    eqg_result = evaluate_text_quality(vector_text)
    fallback_recommended = bool(eqg_result.get("fallback_recommended"))

    logger.info(
        "[EQG]",
        extra={
            "file": path.name,
            "text_health": eqg_result.get("text_health"),
            "fallback_recommended": fallback_recommended,
            "fast_suspect": fast_suspect,
            "signals": eqg_result.get("signals"),
            "bounded": True,
        },
    )

    native_quality_metrics = _native_pdf_text_quality_metrics(vector_text)
    native_text_sufficient = _native_pdf_text_is_sufficient(
        vector_text=vector_text,
        eqg_result=eqg_result,
        fast_suspect=fast_suspect,
    )
    complete_coverage = len(selected_pages) == total_pages

    if not fallback_recommended or native_text_sufficient:
        method = (
            "vector_bounded_quality_override"
            if fallback_recommended
            else "vector_bounded"
        )
        logger.info(
            "[DOCINTEL][TEXT][METHOD]",
            extra={
                "method": method,
                "chars": len(vector_text),
                "selected_pages": selected_pages,
            },
        )
        return _BoundedExtractionResult(
            text=vector_text,
            metadata={
                "policy": policy.name,
                "coverage_mode": (
                    "complete" if complete_coverage else "bounded_representative"
                ),
                "source_page_count": total_pages,
                "selected_pages": selected_pages,
                "evidence_pages": native_pages,
                "native_pages_with_text": native_pages,
                "ocr_pages_processed": [],
                "ocr_used": False,
                "ocr_dpi": int(policy.ocr_dpi),
                "stop_reason": "native_text_sufficient",
                "complete_source_coverage": complete_coverage,
                "evidence_chars": len(vector_text),
            },
        )

    logger.info(
        "[DOCINTEL][TEXT][FALLBACK]",
        extra={
            "file": path.name,
            "triggered": True,
            "reason": "eqg_suspect",
            "bounded": True,
        },
    )
    logger.info(
        "[DOCINTEL][TEXT][TRY_OCR]",
        extra={
            "file": path.name,
            "bounded": True,
            "selected_pages": selected_pages,
            "ocr_dpi": int(policy.ocr_dpi),
        },
    )

    ocr_text, ocr_pages, stop_reason, elapsed_seconds = _bounded_pdf_ocr_text(
        path,
        total_pages=total_pages,
        selected_pages=selected_pages,
        policy=policy,
        progress_callback=progress_callback,
    )
    ocr_text = _sanitize_extracted_text(ocr_text)

    if not ocr_text.strip():
        if vector_text.strip():
            combined_text = vector_text
            method = "vector_preserved_after_bounded_ocr_empty"
        else:
            raise DocIntelIngestError(
                "Bounded OCR fallback produced no extractable "
                f"text: {path.name}"
            )
    elif _should_preserve_vector_text(vector_text, ocr_text):
        combined_text = _merge_extracted_texts(vector_text, ocr_text)
        method = "hybrid_bounded_preserve"
    else:
        combined_text = ocr_text
        method = "ocr_bounded"

    evidence_pages = sorted(set(native_pages) | set(ocr_pages))
    complete_source_coverage = bool(
        len(evidence_pages) == total_pages
        and stop_reason == "page_budget_complete"
    )
    coverage_mode = (
        "complete"
        if complete_source_coverage
        else "bounded_representative"
    )

    logger.info(
        "[DOCINTEL][TEXT][METHOD]",
        extra={
            "method": method,
            "chars": len(combined_text),
            "source_page_count": total_pages,
            "selected_pages": selected_pages,
            "ocr_pages_processed": ocr_pages,
            "stop_reason": stop_reason,
            "elapsed_seconds": elapsed_seconds,
            "coverage_mode": coverage_mode,
        },
    )
    _emit_raw_text_probe(
        file_name=path.name,
        method=method,
        text=combined_text,
    )

    return _BoundedExtractionResult(
        text=combined_text,
        metadata={
            "policy": policy.name,
            "coverage_mode": coverage_mode,
            "source_page_count": total_pages,
            "selected_pages": selected_pages,
            "evidence_pages": evidence_pages,
            "native_pages_with_text": native_pages,
            "ocr_pages_processed": ocr_pages,
            "ocr_used": True,
            "ocr_dpi": int(policy.ocr_dpi),
            "stop_reason": stop_reason,
            "complete_source_coverage": complete_source_coverage,
            "evidence_chars": len(combined_text),
            "elapsed_seconds": elapsed_seconds,
        },
    )


def _extract_pdf_text_pypdf(path: Path) -> str:
    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(
            str(path)
        )
    except Exception as exc:
        raise DocIntelIngestError(
            f"PyPDF2 failed opening PDF: {path.name}"
        ) from exc

    pages = []

    for page_index, page in enumerate(
        reader.pages
    ):
        try:
            text = page.extract_text() or ""

            if text.strip():
                pages.append(
                    text.strip()
                )
        except Exception as exc:
            raise DocIntelIngestError(
                "PyPDF2 failed extracting page "
                f"{page_index} of {path.name}"
            ) from exc

    return "\n\n".join(pages)


def _readable_character_ratio(text: str) -> float:
    """
    Measure readable extracted text without penalizing document structure.

    Python treats line breaks and tabs as non-printable, but they are valid
    structural characters in extracted documents. Control characters that
    could indicate corruption are already removed by _sanitize_extracted_text.
    """

    clean_text = str(text or "")

    if not clean_text:
        return 0.0

    readable_count = sum(
        1
        for char in clean_text
        if (
            char.isprintable()
            or char in {
                "\n",
                "\r",
                "\t",
            }
        )
    )

    return readable_count / max(
        len(clean_text),
        1,
    )


def _fast_text_suspect(text: str) -> bool:
    if not text:
        return True

    stripped = text.strip()

    if len(stripped) < 120:
        return True

    return (
        _readable_character_ratio(stripped)
        < 0.75
    )


def _native_pdf_text_quality_metrics(
    vector_text: str,
) -> Dict[str, float | int]:
    stripped = str(
        vector_text or ""
    ).strip()
    text_length = len(stripped)

    if not stripped:
        return {
            "chars": 0,
            "readable_ratio": 0.0,
            "alphanumeric_ratio": 0.0,
            "word_count": 0,
            "nonempty_line_count": 0,
        }

    alphanumeric_count = sum(
        1
        for char in stripped
        if char.isalnum()
    )
    word_count = len(
        re.findall(
            r"\b\w+\b",
            stripped,
        )
    )
    nonempty_line_count = sum(
        1
        for line in stripped.splitlines()
        if line.strip()
    )

    return {
        "chars": text_length,
        "readable_ratio": (
            _readable_character_ratio(
                stripped
            )
        ),
        "alphanumeric_ratio": (
            alphanumeric_count
            / max(
                text_length,
                1,
            )
        ),
        "word_count": word_count,
        "nonempty_line_count": (
            nonempty_line_count
        ),
    }


def _coerce_signal_float(
    signals: Dict,
    key: str,
) -> float:
    """Return one numeric EQG signal without trusting external shape."""

    if not isinstance(
        signals,
        dict,
    ):
        return 0.0

    value = signals.get(
        key,
        0.0,
    )

    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _eqg_signal_requires_ocr(
    *,
    metrics: Dict[str, float | int],
    signals: Dict,
) -> bool:
    """
    Return whether EQG signals are severe enough to require OCR.

    EQG remains a corruption detector, but it should not force OCR when native
    extraction already contains readable, dense, structured text. This keeps
    OCR as a recovery path instead of the default path for clean text PDFs.
    """

    if metrics["readable_ratio"] < _NATIVE_PDF_MIN_PRINTABLE_RATIO:
        return True

    if metrics["alphanumeric_ratio"] < _NATIVE_PDF_MIN_ALPHANUMERIC_RATIO:
        return True

    if metrics["word_count"] < _NATIVE_PDF_MIN_WORDS:
        return True

    fracture_ratio = _coerce_signal_float(
        signals,
        "fracture_ratio",
    )
    glued_ratio = _coerce_signal_float(
        signals,
        "glued_ratio",
    )
    short_token_ratio = _coerce_signal_float(
        signals,
        "short_token_ratio",
    )

    if fracture_ratio > _NATIVE_PDF_MAX_ACCEPTABLE_FRACTURE_RATIO:
        return True

    if glued_ratio > _NATIVE_PDF_MAX_ACCEPTABLE_GLUED_RATIO:
        return True

    if short_token_ratio > _NATIVE_PDF_MAX_ACCEPTABLE_SHORT_TOKEN_RATIO:
        return True

    return False


def _native_pdf_text_is_sufficient(
    *,
    vector_text: str,
    eqg_result: Dict,
    fast_suspect: bool,
) -> bool:
    """
    Accept strong native PDF text without paying the full OCR cost.

    EQG remains authoritative for severe corruption. For commercially useful
    native text, EQG strong signals are treated as advisory unless the measured
    corruption crosses OCR-required thresholds.
    """

    if fast_suspect:
        return False

    metrics = _native_pdf_text_quality_metrics(
        vector_text
    )

    if (
        metrics["chars"]
        < _NATIVE_PDF_MIN_CHARS
    ):
        return False

    signals = (
        eqg_result.get("signals")
        if isinstance(
            eqg_result,
            dict,
        )
        else {}
    )
    signals = (
        signals
        if isinstance(
            signals,
            dict,
        )
        else {}
    )

    if _eqg_signal_requires_ocr(
        metrics=metrics,
        signals=signals,
    ):
        return False

    if (
        metrics["word_count"]
        < _NATIVE_PDF_MIN_WORDS
    ):
        return False

    has_document_structure = (
        metrics["nonempty_line_count"]
        >= _NATIVE_PDF_MIN_NONEMPTY_LINES
        or metrics["word_count"] >= 350
    )

    if not has_document_structure:
        return False

    broadly_readable = (
        metrics["readable_ratio"]
        >= _NATIVE_PDF_MIN_PRINTABLE_RATIO
        and metrics["alphanumeric_ratio"]
        >= _NATIVE_PDF_MIN_ALPHANUMERIC_RATIO
    )
    strongly_lexical = (
        metrics["alphanumeric_ratio"]
        >= _NATIVE_PDF_STRONG_ALPHANUMERIC_RATIO
        and metrics["word_count"]
        >= _NATIVE_PDF_STRONG_WORD_COUNT
        and metrics["nonempty_line_count"]
        >= _NATIVE_PDF_STRONG_LINE_COUNT
    )

    return (
        broadly_readable
        or strongly_lexical
    )


def _extract_pdf_text_ocr(
    path: Path,
    *,
    progress_callback: Optional[DocIntelProgressCallback] = None,
) -> str:
    """Extract a scanned PDF incrementally instead of rendering it all at once.

    Large image-only PDFs used to enter one opaque ``pdftoppm`` call that
    rendered every page at 300 DPI before Tesseract started. That could hold a
    durable intelligence job at 25% for minutes with no page-level progress and
    no safe yield point. Process one page at a time so the caller can heartbeat,
    report progress, and abort cleanly between bounded local operations.
    """

    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(str(path))
        total_pages = len(reader.pages)
    except Exception as exc:
        raise DocIntelIngestError(
            f"PyPDF2 failed opening PDF for OCR: {path.name}"
        ) from exc

    if total_pages <= 0:
        raise DocIntelIngestError(
            f"PDF contains no OCR-processable pages: {path.name}"
        )

    started_at = monotonic()
    texts: List[str] = []
    evidence_chars = 0

    try:
        with tempfile.TemporaryDirectory() as temp_directory:
            temp_root = Path(temp_directory)

            for page_number in range(1, total_pages + 1):
                image_prefix = temp_root / f"page-{page_number:06d}"
                image_path = image_prefix.with_suffix(".png")

                subprocess.run(
                    [
                        "pdftoppm",
                        "-f",
                        str(page_number),
                        "-l",
                        str(page_number),
                        "-singlefile",
                        "-r",
                        "300",
                        "-png",
                        "-gray",
                        str(path),
                        str(image_prefix),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=120,
                )

                result = subprocess.run(
                    [
                        "tesseract",
                        str(image_path),
                        "stdout",
                        "--psm",
                        "6",
                        "-l",
                        "eng",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=120,
                )

                if result.returncode != 0:
                    raise DocIntelIngestError(
                        "Tesseract failed on "
                        f"page {page_number} of {total_pages}: "
                        f"{(result.stderr or '').strip()[:300]}"
                    )

                clean_page = _sanitize_extracted_text(result.stdout or "")
                if clean_page:
                    page_block = (
                        f"[SOURCE PAGE {page_number} OF {total_pages}]\n"
                        f"{clean_page}"
                    )
                    texts.append(page_block)
                    evidence_chars += len(page_block)

                try:
                    image_path.unlink(missing_ok=True)
                except OSError:
                    pass

                elapsed = round(monotonic() - started_at, 2)
                _emit_extraction_progress(
                    progress_callback,
                    phase="ocr_full",
                    completed_pages=page_number,
                    planned_pages=total_pages,
                    source_page=page_number,
                    source_page_count=total_pages,
                    evidence_chars=evidence_chars,
                    elapsed_seconds=elapsed,
                )
                logger.info(
                    "[DOCINTEL][TEXT][OCR_PROGRESS]",
                    extra={
                        "file": path.name,
                        "page": page_number,
                        "pages": total_pages,
                        "evidence_chars": evidence_chars,
                        "elapsed_seconds": elapsed,
                    },
                )

        return "\n\n".join(texts)
    except subprocess.TimeoutExpired as exc:
        raise DocIntelIngestError(
            "OCR page operation exceeded its bounded timeout"
        ) from exc
    except Exception as exc:
        if isinstance(exc, DocIntelIngestError):
            raise
        raise DocIntelIngestError(
            "OCR extraction failed"
        ) from exc


def _extract_pdf_text(
    path: Path,
    *,
    progress_callback: Optional[DocIntelProgressCallback] = None,
) -> str:
    from solomon_core.docintel.ingestion.text_quality_gate import (
        evaluate_text_quality,
    )

    logger.info(
        "[DOCINTEL][TEXT][TRY_PYPDF2]",
        extra={
            "file": path.name,
        },
    )
    vector_text = _sanitize_extracted_text(
        _extract_pdf_text_pypdf(path)
    )

    logger.info(
        "[DOCINTEL][TEXT][PYPDF2_OK]",
        extra={
            "chars": len(vector_text),
            "evidence_score": round(
                _extraction_evidence_score(
                    vector_text
                ),
                2,
            ),
        },
    )

    fast_suspect = _fast_text_suspect(
        vector_text
    )
    eqg_result = evaluate_text_quality(
        vector_text
    )

    fallback_recommended = bool(
        eqg_result.get(
            "fallback_recommended"
        )
    )

    logger.info(
        "[EQG]",
        extra={
            "file": path.name,
            "text_health": eqg_result.get(
                "text_health"
            ),
            "fallback_recommended": (
                fallback_recommended
            ),
            "fast_suspect": fast_suspect,
            "signals": eqg_result.get(
                "signals"
            ),
        },
    )

    if not fallback_recommended:
        method = (
            "vector_fast"
            if not fast_suspect
            else "vector"
        )
        logger.info(
            "[DOCINTEL][TEXT][METHOD]",
            extra={
                "method": method,
                "chars": len(vector_text),
            },
        )
        _emit_raw_text_probe(
            file_name=path.name,
            method=method,
            text=vector_text,
        )

        return vector_text

    native_quality_metrics = (
        _native_pdf_text_quality_metrics(
            vector_text
        )
    )
    native_text_sufficient = (
        _native_pdf_text_is_sufficient(
            vector_text=vector_text,
            eqg_result=eqg_result,
            fast_suspect=fast_suspect,
        )
    )

    logger.info(
        "[DOCINTEL][TEXT][NATIVE_QUALITY]",
        extra={
            "file": path.name,
            **native_quality_metrics,
            "sufficient": (
                native_text_sufficient
            ),
        },
    )

    if native_text_sufficient:
        logger.info(
            "[DOCINTEL][TEXT][OCR_BYPASSED]",
            extra={
                "file": path.name,
                "reason": (
                    "native_text_sufficient"
                ),
                "chars": len(vector_text),
                "evidence_score": round(
                    _extraction_evidence_score(
                        vector_text
                    ),
                    2,
                ),
                "signals": eqg_result.get(
                    "signals"
                ),
                **native_quality_metrics,
            },
        )
        logger.info(
            "[DOCINTEL][TEXT][METHOD]",
            extra={
                "method": (
                    "vector_quality_override"
                ),
                "chars": len(vector_text),
            },
        )
        _emit_raw_text_probe(
            file_name=path.name,
            method="vector_quality_override",
            text=vector_text,
        )

        return vector_text

    logger.info(
        "[DOCINTEL][TEXT][FALLBACK]",
        extra={
            "file": path.name,
            "triggered": True,
            "reason": "eqg_suspect",
        },
    )

    logger.info(
        "[DOCINTEL][TEXT][TRY_OCR]",
        extra={
            "file": path.name,
        },
    )

    try:
        ocr_text = _sanitize_extracted_text(
            _extract_pdf_text_ocr(
                path,
                progress_callback=progress_callback,
            )
        )
    except Exception:
        logger.exception(
            "[DOCINTEL][TEXT][OCR_FAIL]"
        )

        if vector_text.strip():
            logger.info(
                "[DOCINTEL][TEXT][METHOD]",
                extra={
                    "method": (
                        "vector_preserved_after_ocr_fail"
                    ),
                    "chars": len(vector_text),
                },
            )

            return vector_text

        raise

    if not ocr_text.strip():
        if vector_text.strip():
            logger.warning(
                "[DOCINTEL][TEXT][OCR_EMPTY_VECTOR_PRESERVED]"
            )

            return vector_text

        raise DocIntelIngestError(
            "OCR fallback produced no extractable "
            f"text: {path.name}"
        )

    logger.info(
        "[DOCINTEL][TEXT][OCR_OK]",
        extra={
            "chars": len(ocr_text),
            "evidence_score": round(
                _extraction_evidence_score(
                    ocr_text
                ),
                2,
            ),
        },
    )

    if _should_preserve_vector_text(
        vector_text,
        ocr_text,
    ):
        merged_text = _merge_extracted_texts(
            vector_text,
            ocr_text,
        )
        logger.info(
            "[DOCINTEL][TEXT][METHOD]",
            extra={
                "method": "hybrid_preserve",
                "chars": len(merged_text),
                "vector_chars": len(
                    vector_text
                ),
                "ocr_chars": len(
                    ocr_text
                ),
                "evidence_score": round(
                    _extraction_evidence_score(
                        merged_text
                    ),
                    2,
                ),
            },
        )
        _emit_raw_text_probe(
            file_name=path.name,
            method="hybrid_preserve",
            text=merged_text,
        )

        return merged_text

    logger.info(
        "[DOCINTEL][TEXT][METHOD]",
        extra={
            "method": "ocr_fallback",
            "chars": len(ocr_text),
        },
    )
    _emit_raw_text_probe(
        file_name=path.name,
        method="ocr_fallback",
        text=ocr_text,
    )

    return ocr_text


# ---------------------------------------------------------------------------
# DOCX / Plain Text Extraction
# ---------------------------------------------------------------------------

def _extract_docx_text_python_docx(
    path: Path,
) -> str:
    try:
        import docx
    except Exception as exc:
        raise DocIntelIngestError(
            "python-docx is not available"
        ) from exc

    try:
        document = docx.Document(
            str(path)
        )
    except Exception as exc:
        raise DocIntelIngestError(
            "python-docx failed opening DOCX: "
            f"{path.name}"
        ) from exc

    lines = []

    for paragraph in document.paragraphs:
        text = str(
            paragraph.text or ""
        ).strip()

        if text:
            lines.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [
                str(cell.text or "").strip()
                for cell in row.cells
                if str(
                    cell.text or ""
                ).strip()
            ]

            if cells:
                lines.append(
                    " | ".join(cells)
                )

    return "\n".join(lines).strip()


def _extract_docx_part_text(
    zip_file: zipfile.ZipFile,
    member_name: str,
) -> str:
    try:
        root = ET.fromstring(
            zip_file.read(member_name)
        )
    except Exception:
        return ""

    lines = []

    for paragraph in root.iter(
        f"{_WORD_XML_NAMESPACE}p"
    ):
        fragments = [
            node.text
            for node in paragraph.iter(
                f"{_WORD_XML_NAMESPACE}t"
            )
            if node.text
        ]
        line = "".join(
            fragments
        ).strip()

        if line:
            lines.append(line)

    return "\n".join(lines).strip()


def _extract_docx_text_xml(path: Path) -> str:
    try:
        with zipfile.ZipFile(
            str(path)
        ) as archive:
            names = archive.namelist()
            members = [
                "word/document.xml",
            ]
            members.extend(
                sorted(
                    name
                    for name in names
                    if (
                        name.startswith(
                            "word/header"
                        )
                        and name.endswith(
                            ".xml"
                        )
                    )
                )
            )
            members.extend(
                sorted(
                    name
                    for name in names
                    if (
                        name.startswith(
                            "word/footer"
                        )
                        and name.endswith(
                            ".xml"
                        )
                    )
                )
            )

            blocks = [
                _extract_docx_part_text(
                    archive,
                    member,
                )
                for member in members
                if member in names
            ]
    except Exception as exc:
        raise DocIntelIngestError(
            "DOCX XML extraction failed: "
            f"{path.name}"
        ) from exc

    return "\n\n".join(
        block
        for block in blocks
        if block
    ).strip()


def _extract_docx_text(path: Path) -> str:
    try:
        text = _sanitize_extracted_text(
            _extract_docx_text_python_docx(
                path
            )
        )
        method = "python_docx"
    except Exception as exc:
        logger.warning(
            "[DOCINTEL][DOCX][PYTHON_DOCX_FAIL]",
            extra={
                "file": path.name,
                "error": str(exc),
            },
        )
        text = _sanitize_extracted_text(
            _extract_docx_text_xml(path)
        )
        method = "docx_xml"

    if not text.strip():
        raise DocIntelIngestError(
            "DOCX extraction produced no text: "
            f"{path.name}"
        )

    logger.info(
        "[DOCINTEL][TEXT][METHOD]",
        extra={
            "file": path.name,
            "method": method,
            "chars": len(text),
            "evidence_score": round(
                _extraction_evidence_score(
                    text
                ),
                2,
            ),
        },
    )
    _emit_raw_text_probe(
        file_name=path.name,
        method=method,
        text=text,
    )

    return text


def _build_spreadsheet_extraction_result(path: Path) -> _BoundedExtractionResult:
    """Extract bounded structured spreadsheet evidence through Reader authority."""

    suffix = path.suffix.lower()

    try:
        if suffix == ".csv":
            sheets, truncated = build_csv_preview(
                str(path),
                request_id="docintel_ingest",
            )
            text_blocks = build_csv_preview_text_blocks(sheets)
            non_empty_cells = get_csv_preview_non_empty_cells(sheets)
            method = "workspace_reader_csv_preview"
        elif suffix == ".xlsx":
            sheets, truncated = build_xlsx_preview(
                str(path),
                request_id="docintel_ingest",
            )
            text_blocks = build_xlsx_preview_text_blocks(sheets)
            non_empty_cells = get_xlsx_preview_non_empty_cells(sheets)
            method = "workspace_reader_xlsx_preview"
        elif suffix == ".xls":
            sheets, truncated = build_xls_preview(
                str(path),
                request_id="docintel_ingest",
            )
            text_blocks = build_xls_preview_text_blocks(sheets)
            non_empty_cells = get_xls_preview_non_empty_cells(sheets)
            method = "workspace_reader_xls_preview"
        else:
            raise DocIntelIngestError(
                "Unsupported spreadsheet type: "
                f"{path.suffix}"
            )
    except DocIntelIngestError:
        raise
    except Exception as exc:
        raise DocIntelIngestError(
            "Spreadsheet extraction failed for "
            f"{path.name}: {exc}"
        ) from exc

    text = _sanitize_extracted_text(
        "\n".join(
            str(block or "").strip()
            for block in text_blocks
            if str(block or "").strip()
        )
    ).strip()

    if not text or non_empty_cells <= 0:
        raise DocIntelIngestError(
            "Spreadsheet extraction produced no readable cells: "
            f"{path.name}"
        )

    sheet_provenance = []

    for sheet in sheets:
        sheet_provenance.append({
            "name": str(sheet.get("name") or "Sheet"),
            "range_label": str(
                sheet.get("range_label") or "No readable cells"
            ),
            "data_range_label": str(
                sheet.get("data_range_label") or "No readable cells"
            ),
            "rendered_row_count": int(
                sheet.get("rendered_row_count") or 0
            ),
            "rendered_column_count": int(
                sheet.get("rendered_column_count") or 0
            ),
            "scanned_non_empty_cells": int(
                sheet.get("non_empty_cell_count") or 0
            ),
            "truncated": bool(sheet.get("truncated")),
            "value_source": str(sheet.get("value_source") or ""),
            "read_mode": str(sheet.get("read_mode") or ""),
        })

    coverage_mode = "representative" if truncated else "complete"
    stop_reason = (
        "spreadsheet_preview_bounded"
        if truncated
        else "spreadsheet_complete"
    )

    logger.info(
        "[DOCINTEL][TEXT][METHOD]",
        extra={
            "file": path.name,
            "method": method,
            "chars": len(text),
            "evidence_score": round(
                _extraction_evidence_score(text),
                2,
            ),
            "sheets": len(sheets),
            "non_empty_cells": non_empty_cells,
            "coverage_mode": coverage_mode,
            "truncated": bool(truncated),
        },
    )
    _emit_raw_text_probe(
        file_name=path.name,
        method=method,
        text=text,
    )

    return _BoundedExtractionResult(
        text=text,
        metadata={
            "coverage_mode": coverage_mode,
            "complete_source_coverage": not bool(truncated),
            "evidence_chars": len(text),
            "stop_reason": stop_reason,
            "spreadsheet_format": suffix.lstrip("."),
            "tabular_evidence_contract": TABULAR_EVIDENCE_CONTRACT,
            "spreadsheet_sheet_count": len(sheets),
            "spreadsheet_non_empty_cells": int(non_empty_cells),
            "spreadsheet_truncated": bool(truncated),
            "spreadsheet_sheets": sheet_provenance,
        },
    )


def _extract_spreadsheet_text(path: Path) -> str:
    """Return spreadsheet text using the canonical Reader extraction path."""

    return _build_spreadsheet_extraction_result(path).text


def _extract_plain_text(path: Path) -> str:
    encodings = (
        "utf-8-sig",
        "utf-8",
        "utf-16",
        "cp1252",
    )
    data = path.read_bytes()
    last_error = None

    for encoding in encodings:
        try:
            text = data.decode(encoding)
            cleaned = _sanitize_extracted_text(
                text
            )

            if cleaned.strip():
                logger.info(
                    "[DOCINTEL][TEXT][METHOD]",
                    extra={
                        "file": path.name,
                        "method": (
                            f"plain_text_{encoding}"
                        ),
                        "chars": len(cleaned),
                        "evidence_score": round(
                            _extraction_evidence_score(
                                cleaned
                            ),
                            2,
                        ),
                    },
                )
                _emit_raw_text_probe(
                    file_name=path.name,
                    method=(
                        f"plain_text_{encoding}"
                    ),
                    text=cleaned,
                )

                return cleaned
        except Exception as exc:
            last_error = exc

    raise DocIntelIngestError(
        "Plain text extraction failed for "
        f"{path.name}: {last_error}"
    )


def _extract_document_text(
    path: Path,
    *,
    progress_callback: Optional[DocIntelProgressCallback] = None,
) -> str:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf_text(
            path,
            progress_callback=progress_callback,
        )

    if suffix == ".docx":
        return _extract_docx_text(path)

    if suffix == ".txt":
        return _extract_plain_text(path)

    if suffix in {
        ".csv",
        ".xlsx",
        ".xls",
    }:
        return _extract_spreadsheet_text(path)

    raise DocIntelIngestError(
        "Unsupported document type: "
        f"{path.suffix}"
    )


def _extract_document_text_with_policy(
    path: Path,
    *,
    extraction_policy: DocIntelExtractionPolicy,
    progress_callback: Optional[DocIntelProgressCallback],
) -> _BoundedExtractionResult:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return _extract_pdf_text_bounded(
            path,
            policy=extraction_policy,
            progress_callback=progress_callback,
        )

    if suffix in {
        ".csv",
        ".xlsx",
        ".xls",
    }:
        spreadsheet_result = _build_spreadsheet_extraction_result(path)
        return _BoundedExtractionResult(
            text=spreadsheet_result.text,
            metadata={
                "policy": extraction_policy.name,
                **spreadsheet_result.metadata,
            },
        )

    text = _extract_document_text(
        path,
        progress_callback=progress_callback,
    )
    return _BoundedExtractionResult(
        text=text,
        metadata={
            "policy": extraction_policy.name,
            "coverage_mode": "complete",
            "complete_source_coverage": True,
            "evidence_chars": len(text),
            "stop_reason": "non_pdf_complete",
        },
    )


# ---------------------------------------------------------------------------
# Shared AFR Observation Accessor
# ---------------------------------------------------------------------------

def _resolve_original_name(
    doc_id: str,
    path: Path,
) -> str:
    """Resolve the display filename through the canonical FileRegistry table."""

    clean_doc_id = str(
        doc_id or ""
    ).strip()
    candidates = []
    seen = set()

    for value in (
        clean_doc_id,
        path.name,
        path.stem,
    ):
        candidate = str(
            value or ""
        ).strip()

        if (
            not candidate
            or candidate in seen
        ):
            continue

        candidates.append(candidate)
        seen.add(candidate)

    try:
        absolute_path = str(
            path.resolve()
        )
    except OSError:
        absolute_path = str(
            path.absolute()
        )

    db_session = SessionLocal()

    try:
        for candidate in candidates:
            record = (
                db_session.query(FileRegistry)
                .filter(
                    FileRegistry.random_name
                    == candidate
                )
                .first()
            )

            if (
                record
                and str(
                    record.original_name or ""
                ).strip()
            ):
                return str(
                    record.original_name
                ).strip()

        if absolute_path:
            record = (
                db_session.query(FileRegistry)
                .filter(
                    FileRegistry.path
                    == absolute_path
                )
                .first()
            )

            if (
                record
                and str(
                    record.original_name or ""
                ).strip()
            ):
                return str(
                    record.original_name
                ).strip()
    except Exception as exc:
        logger.warning(
            "[DOCINTEL][FILE_REGISTRY_NAME_RESOLVE_FAIL]",
            extra={
                "document_id": clean_doc_id,
                "path": str(path),
                "error": str(exc),
            },
        )
    finally:
        db_session.close()

    return clean_doc_id or path.name


def observe_documents(
    resolved_paths: List[str],
) -> Dict:
    if not resolved_paths:
        return {}

    documents: List[Dict] = []

    for path in [
        Path(path_value)
        for path_value in resolved_paths
    ]:
        if not path.exists():
            logger.warning(
                "[AFR][MISSING_PATH]",
                extra={
                    "path": str(path),
                },
            )
            continue

        doc_id = path.name
        original_name = _resolve_original_name(
            doc_id,
            path,
        )

        if (
            path.suffix.lower()
            not in SUPPORTED_TEXT_SUFFIXES
        ):
            logger.warning(
                "[AFR][SKIP_UNSUPPORTED]",
                extra={
                    "file": original_name,
                },
            )
            continue

        try:
            text = _extract_document_text(
                path
            )
        except Exception as exc:
            logger.warning(
                "[AFR][TEXT_FAIL]",
                extra={
                    "file": original_name,
                    "error": str(exc),
                },
            )
            continue

        documents.append({
            "document_id": doc_id,
            "original_name": original_name,
            "text": text,
        })

    if not documents:
        return {}

    try:
        return build_afr_for_documents(
            documents
        )
    except Exception as exc:
        logger.warning(
            "[AFR][DETECTOR_FAIL]",
            extra={
                "error": str(exc),
            },
        )

        return {}


# ---------------------------------------------------------------------------
# Public Ingest API
# ---------------------------------------------------------------------------

def ingest_documents_for_intent(
    *,
    intent: Optional[ExplicitIntent],
    resolved_paths: List[str],
    extraction_policy: Optional[DocIntelExtractionPolicy] = None,
    progress_callback: Optional[DocIntelProgressCallback] = None,
) -> Dict:
    if not resolved_paths:
        raise DocIntelIngestError(
            "No resolved document paths available"
        )

    resolved_path_objects = [
        Path(path_value)
        for path_value in resolved_paths
    ]
    documents: List[Dict] = []

    if isinstance(
        intent,
        ExplicitIntent,
    ):
        if not intent.document_ids:
            raise DocIntelIngestError(
                "ExplicitIntent contains no document_ids"
            )

        if (
            len(intent.document_ids)
            != len(resolved_path_objects)
        ):
            raise DocIntelIngestError(
                "Document ID count does not match "
                "resolved path count"
            )

        id_path_pairs = zip(
            intent.document_ids,
            resolved_path_objects,
        )
    else:
        id_path_pairs = [
            (
                path.name,
                path,
            )
            for path in resolved_path_objects
        ]

    for doc_id, path in id_path_pairs:
        if not path.exists():
            raise DocIntelIngestError(
                "Resolved document path does not exist: "
                f"{path}"
            )

        original_name = _resolve_original_name(
            doc_id,
            path,
        )

        logger.info(
            "[DOCINTEL][INGEST]",
            extra={
                "document_id": doc_id,
                "original_name": original_name,
            },
        )

        extraction_metadata = None
        if extraction_policy is None:
            text = _extract_document_text(
                path,
                progress_callback=progress_callback,
            )
        else:
            extraction_result = _extract_document_text_with_policy(
                path,
                extraction_policy=extraction_policy,
                progress_callback=progress_callback,
            )
            text = extraction_result.text
            extraction_metadata = extraction_result.metadata

        document_payload = {
            "document_id": doc_id,
            "original_name": original_name,
            "text": text,
        }
        if extraction_metadata is not None:
            document_payload["extraction"] = extraction_metadata

        documents.append(document_payload)

    if not documents:
        raise DocIntelIngestError(
            "No documents ingested after binding"
        )

    try:
        afr = build_afr_for_documents(
            documents
        )
    except Exception as exc:
        logger.warning(
            "[AFR] detector failure",
            extra={
                "error": str(exc),
            },
        )
        afr = {}

    section_signals = []
    value_signals = []
    structural_signals = []

    for document in documents:
        doc_id = document["document_id"]
        text = document["text"]

        before_sections = len(
            section_signals
        )
        before_values = len(
            value_signals
        )
        before_structural = len(
            structural_signals
        )

        try:
            section_signals.extend(
                extract_sections(
                    document_id=doc_id,
                    document_text=text,
                )
            )
        except Exception as exc:
            logger.warning(
                "Section extraction failed",
                extra={
                    "document_id": doc_id,
                    "error": str(exc),
                },
            )

        try:
            value_signals.extend(
                extract_explicit_values(
                    document_id=doc_id,
                    document_text=text,
                )
            )
        except Exception as exc:
            logger.warning(
                "Value extraction failed",
                extra={
                    "document_id": doc_id,
                    "error": str(exc),
                },
            )

        try:
            structural_signals.extend(
                extract_structural_signals(
                    document_id=doc_id,
                    document_text=text,
                )
            )
        except Exception as exc:
            logger.warning(
                "Structural extraction failed",
                extra={
                    "document_id": doc_id,
                    "error": str(exc),
                },
            )

        logger.info(
            "[DOCINTEL][SURVIVABILITY] "
            f"doc={doc_id} "
            f"chars={len(text)} "
            "sections_found="
            f"{len(section_signals) - before_sections} "
            "values_found="
            f"{len(value_signals) - before_values} "
            "structural_found="
            f"{len(structural_signals) - before_structural}"
        )

    monetary_signals = []
    exclusion_signals = []

    try:
        for item in value_signals:
            if not isinstance(
                item,
                dict,
            ):
                continue

            label = str(
                item.get("signal_type") or ""
            ).lower()

            if any(
                keyword in label
                for keyword in (
                    "price",
                    "currency",
                    "money",
                    "bid",
                    "total",
                )
            ):
                monetary_signals.append(
                    item
                )

        for item in structural_signals:
            if not isinstance(
                item,
                dict,
            ):
                continue

            label = str(
                item.get("signal_type") or ""
            ).lower()

            if "exclusion" in label:
                exclusion_signals.append(
                    item
                )
    except Exception as exc:
        logger.warning(
            "[SIGNAL_CLASSIFY] non-fatal classification failure",
            extra={
                "error": str(exc),
            },
        )

    return {
        "reasoning_type": "docintel",
        "inputs": {
            "documents": documents,
            "signals": {
                "sections": section_signals,
                "values": value_signals,
                "structural": structural_signals,
                "monetary": monetary_signals,
                "exclusions": exclusion_signals,
            },
            "afr": afr,
        },
    }