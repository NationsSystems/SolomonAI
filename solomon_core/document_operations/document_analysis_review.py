# -------------------------------------------------------------------
# FILE: document_analysis_review.py
# DIRECTORY: solomon_core/document_operations/
# -------------------------------------------------------------------
# Adapter-owned Document Analysis runner for the Documents workspace.
# This bypasses the V1 drivetrain and uses one bounded SolomonAI local
# LLM call to author the review response.
# -------------------------------------------------------------------

from pathlib import Path
from typing import Any, Dict, List
import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET

from solomon_core.logger import get_logger
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionInput,
    LLMExecutionMode,
    LLMResponseFormat,
)
from solomon_core.llm.llm_executor import execute_llm

logger = get_logger("document_analysis_review")

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_WORD_XML_NAMESPACE = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

SUPPORTED_DOCUMENT_ANALYSIS_SUFFIXES = frozenset({
    ".pdf",
    ".docx",
    ".txt",
    ".csv",
})

LLM_CALL_SITE = "document_analysis_review"
MAX_TOTAL_CONTEXT_CHARS = 950
MAX_SINGLE_DOCUMENT_CHARS = 900
MAX_PROMPT_CHARS = 1550

DOCUMENT_ANALYSIS_OPERATION = "document_analysis"
DOCUMENT_ANALYSIS_LABEL = "Document Analysis"

_EVIDENCE_TERMS = (
    "include",
    "included",
    "exclude",
    "excluded",
    "exclusion",
    "price",
    "pricing",
    "amount",
    "fee",
    "cost",
    "proposal",
    "agreement",
    "contract",
    "policy",
    "valid",
    "validity",
    "alternate",
    "allowance",
    "addendum",
    "addenda",
    "clarification",
    "qualifier",
    "qualifications",
    "payment",
    "terms",
    "schedule",
    "date",
    "deadline",
    "duration",
    "party",
    "parties",
    "approval",
    "signature",
    "insurance",
    "tax",
    "risk",
    "issue",
    "missing",
    "required",
    "requirement",
    "responsible",
    "condition",
    "compliance",
    "attachment",
    "amendment",
    "version",
    "source",
    "note",
    "action",
    "dependency",
)


class DocumentAnalysisReviewError(Exception):
    """Raised when the adapter-owned document analysis cannot process a file."""


def _sanitize_text(value: str) -> str:
    """Return safe extracted text without non-printable control characters."""

    if not isinstance(value, str) or not value.strip():
        return ""

    cleaned = _CONTROL_CHAR_RE.sub(" ", value)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    return cleaned.strip()


def _decode_text_bytes(data: bytes, file_name: str) -> str:
    """Decode text bytes using common document encodings."""

    last_error = None

    for encoding in ("utf-8-sig", "utf-8", "utf-16", "cp1252"):
        try:
            return data.decode(encoding)
        except Exception as exc:
            last_error = exc

    raise DocumentAnalysisReviewError(
        f"Could not decode text from {file_name}: {last_error}"
    )


def _extract_pdf_text(path: Path) -> str:
    """Extract text from a PDF without entering the V1 drivetrain."""

    try:
        import PyPDF2

        reader = PyPDF2.PdfReader(str(path))
    except Exception as exc:
        raise DocumentAnalysisReviewError(
            f"PDF extraction failed opening {path.name}."
        ) from exc

    pages = []

    for page_index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            raise DocumentAnalysisReviewError(
                f"PDF extraction failed on page {page_index + 1} of {path.name}."
            ) from exc

        if text.strip():
            pages.append(text.strip())

    return _sanitize_text("\n\n".join(pages))


def _extract_docx_text_python_docx(path: Path) -> str:
    """Extract DOCX text with python-docx when available."""

    try:
        import docx
    except Exception as exc:
        raise DocumentAnalysisReviewError("python-docx is not available.") from exc

    try:
        document = docx.Document(str(path))
    except Exception as exc:
        raise DocumentAnalysisReviewError(
            f"DOCX extraction failed opening {path.name}."
        ) from exc

    lines = []

    for paragraph in document.paragraphs:
        text = str(paragraph.text or "").strip()

        if text:
            lines.append(text)

    for table in document.tables:
        for row in table.rows:
            cells = [
                str(cell.text or "").strip()
                for cell in row.cells
                if str(cell.text or "").strip()
            ]

            if cells:
                lines.append(" | ".join(cells))

    return _sanitize_text("\n".join(lines))


def _extract_docx_part_text(zip_file: zipfile.ZipFile, member_name: str) -> str:
    """Extract readable text from one DOCX XML member."""

    try:
        root = ET.fromstring(zip_file.read(member_name))
    except Exception:
        return ""

    lines = []

    for paragraph in root.iter(f"{_WORD_XML_NAMESPACE}p"):
        fragments = [
            node.text
            for node in paragraph.iter(f"{_WORD_XML_NAMESPACE}t")
            if node.text
        ]
        line = "".join(fragments).strip()

        if line:
            lines.append(line)

    return "\n".join(lines).strip()


def _extract_docx_text_xml(path: Path) -> str:
    """Fallback DOCX text extraction using the zipped XML body."""

    try:
        with zipfile.ZipFile(str(path)) as archive:
            names = archive.namelist()
            members = ["word/document.xml"]
            members.extend(
                sorted(
                    name for name in names
                    if name.startswith("word/header") and name.endswith(".xml")
                )
            )
            members.extend(
                sorted(
                    name for name in names
                    if name.startswith("word/footer") and name.endswith(".xml")
                )
            )

            blocks = [
                _extract_docx_part_text(archive, member)
                for member in members
                if member in names
            ]
    except Exception as exc:
        raise DocumentAnalysisReviewError(
            f"DOCX XML extraction failed for {path.name}."
        ) from exc

    return _sanitize_text("\n\n".join(block for block in blocks if block))


def _extract_docx_text(path: Path) -> str:
    """Extract DOCX text with python-docx, falling back to XML."""

    try:
        text = _extract_docx_text_python_docx(path)
        method = "python_docx"
    except Exception as exc:
        logger.warning(
            "[document_analysis_review.docx_python_fail] file=%s error=%s",
            path.name,
            exc,
        )
        text = _extract_docx_text_xml(path)
        method = "docx_xml"

    if not text:
        raise DocumentAnalysisReviewError(f"DOCX extraction produced no text: {path.name}")

    logger.info(
        "[document_analysis_review.extract] file=%s method=%s chars=%s",
        path.name,
        method,
        len(text),
    )

    return text


def _extract_plain_text(path: Path) -> str:
    """Extract TXT text."""

    text = _decode_text_bytes(path.read_bytes(), path.name)
    cleaned = _sanitize_text(text)

    if not cleaned:
        raise DocumentAnalysisReviewError(f"Text extraction produced no text: {path.name}")

    return cleaned


def _extract_csv_text(path: Path) -> str:
    """Extract CSV rows into readable line text."""

    raw_text = _decode_text_bytes(path.read_bytes(), path.name)
    rows = []

    try:
        reader = csv.reader(io.StringIO(raw_text))
        for row in reader:
            cells = [str(cell or "").strip() for cell in row if str(cell or "").strip()]
            if cells:
                rows.append(" | ".join(cells))
    except Exception:
        return _sanitize_text(raw_text)

    cleaned = _sanitize_text("\n".join(rows))

    if not cleaned:
        raise DocumentAnalysisReviewError(f"CSV extraction produced no text: {path.name}")

    return cleaned


def extract_document_text(path_value: str) -> str:
    """Extract text for the adapter-owned document analysis path."""

    path = Path(str(path_value or "").strip())
    suffix = path.suffix.lower()

    if not path.exists() or not path.is_file():
        raise DocumentAnalysisReviewError(f"Document path does not exist: {path}")

    if suffix not in SUPPORTED_DOCUMENT_ANALYSIS_SUFFIXES:
        raise DocumentAnalysisReviewError(f"Unsupported document analysis file type: {suffix}")

    if suffix == ".pdf":
        return _extract_pdf_text(path)

    if suffix == ".docx":
        return _extract_docx_text(path)

    if suffix == ".csv":
        return _extract_csv_text(path)

    return _extract_plain_text(path)


def build_llm_documents(documents: List[Dict]) -> List[Dict]:
    """Build LLM document inputs from resolved file-manager documents."""

    llm_documents = []

    for document in documents:
        if not isinstance(document, dict):
            continue

        resolved_path = str(document.get("resolved_path") or "").strip()
        document_id = str(
            document.get("document_id")
            or document.get("random_name")
            or ""
        ).strip()
        original_name = str(
            document.get("original_name")
            or document.get("filename")
            or document_id
        ).strip()

        if not resolved_path or not document_id:
            continue

        text = extract_document_text(resolved_path)

        llm_documents.append({
            "document_id": document_id,
            "original_name": original_name,
            "filename": original_name,
            "display_name": original_name,
            "text": text,
            "source_path": resolved_path,
        })

    return llm_documents


def _line_has_evidence_term(line: str) -> bool:
    """Return whether a line looks useful for document analysis."""

    lower_line = line.lower()

    return any(term in lower_line for term in _EVIDENCE_TERMS)


def _compact_line(line: str, limit: int = 180) -> str:
    """Return one compact evidence line."""

    cleaned = re.sub(r"\s+", " ", _sanitize_text(line)).strip()

    if len(cleaned) <= limit:
        return cleaned

    return cleaned[:limit].rstrip() + "..."


def _select_evidence_excerpt(text: str, limit: int) -> str:
    """
    Select a small evidence excerpt for the local LLM.

    This is deterministic context compression only. It does not author the
    review, decide outcomes, or replace the LLM response.
    """

    cleaned = _sanitize_text(text)

    if not cleaned:
        return ""

    raw_lines = re.split(r"[\r\n]+", cleaned)
    lines = [
        _compact_line(line)
        for line in raw_lines
        if _sanitize_text(line)
    ]

    if not lines:
        return cleaned[:limit].strip()

    selected = []

    for line in lines:
        if _line_has_evidence_term(line):
            selected.append(line)

        if len("\n".join(selected)) >= limit:
            break

    if not selected:
        selected = lines[:8]

    excerpt = "\n".join(selected).strip()

    if len(excerpt) <= limit:
        return excerpt

    return excerpt[:limit].rsplit("\n", 1)[0].strip() or excerpt[:limit].strip()


def _build_document_context(documents: List[Dict]) -> str:
    """Build bounded document context for the local LLM."""

    if not documents:
        return ""

    per_document_limit = min(
        MAX_SINGLE_DOCUMENT_CHARS,
        max(450, int(MAX_TOTAL_CONTEXT_CHARS / max(len(documents), 1))),
    )

    blocks = []

    for index, document in enumerate(documents, start=1):
        name = str(
            document.get("display_name")
            or document.get("original_name")
            or document.get("filename")
            or f"Document {index}"
        ).strip()
        text = _select_evidence_excerpt(
            str(document.get("text") or ""),
            per_document_limit,
        )

        if not text:
            continue

        blocks.append(
            f"DOCUMENT {index}: {name}\n"
            f"{text}"
        )

    return "\n\n".join(blocks).strip()[:MAX_TOTAL_CONTEXT_CHARS].strip()


def _build_llm_prompt(documents: List[Dict]) -> str:
    """Build the single local LLM prompt for Document Analysis."""

    document_context = _build_document_context(documents)

    if not document_context:
        raise DocumentAnalysisReviewError("No readable document text was available.")

    prompt = f"""
SolomonAI document analysis. Use only the document excerpt. Do not invent facts. Do not claim actions were completed.

Write 3 short bullets:
1. Key details.
2. Issues or missing information.
3. Questions before action.

Document excerpt:
{document_context}
""".strip()

    if len(prompt) > MAX_PROMPT_CHARS:
        raise DocumentAnalysisReviewError(
            "Document Analysis prompt was too large for the hardware-safe inline LLM path."
        )

    return prompt


def _has_repeated_compact_artifacts(text: str) -> bool:
    """Detect malformed compact token artifacts from local generation."""

    if re.search(r"\bLLMExecution(Result|Failure|Output)\b", text):
        return True

    if re.search(r"[A-Za-z]{2,}(?:N[A-Z][A-Za-z]{2,}){3,}", text):
        return True

    compact_hits = re.findall(r"\bN[A-Z][A-Za-z]{3,}", text)

    return len(compact_hits) >= 8


def _looks_like_review_text(text: str) -> bool:
    """Validate that model text is readable enough to show as a review."""

    cleaned = _sanitize_text(text)

    if len(cleaned) < 40:
        return False

    if _has_repeated_compact_artifacts(cleaned):
        return False

    words = re.findall(r"[A-Za-z][A-Za-z'-]{2,}", cleaned)
    unique_words = {word.lower() for word in words}
    space_count = cleaned.count(" ")

    if len(words) < 9:
        return False

    if len(unique_words) < 7:
        return False

    if space_count < 6:
        return False

    if space_count < int(len(cleaned) / 45):
        return False

    return True


def _call_local_llm(prompt: str) -> str:
    """Call the canonical local SolomonAI LLM executor once."""

    input_packet = LLMExecutionInput(
        user_query=prompt,
        mode=LLMExecutionMode.INFORMATIONAL_ONLY,
        context=None,
        response_format=LLMResponseFormat.TEXT,
        call_site=LLM_CALL_SITE,
    )

    result = execute_llm(input_packet)

    if not result or result.is_failure():
        failure = getattr(result, "failure", None)
        reason = getattr(failure, "reason", "unknown")
        message = getattr(failure, "message", "")

        logger.warning(
            "[document_analysis_review.llm_failure] reason=%s message=%s",
            reason,
            message,
        )

        raise DocumentAnalysisReviewError(
            "The local SolomonAI LLM could not complete Document Analysis."
        )

    output = getattr(result, "output", None)

    if getattr(output, "refusal", False):
        logger.warning("[document_analysis_review.llm_refusal]")
        raise DocumentAnalysisReviewError(
            "The local SolomonAI LLM refused the Document Analysis request."
        )

    text = _sanitize_text(getattr(output, "text", ""))

    if not text:
        raise DocumentAnalysisReviewError(
            "The local SolomonAI LLM returned an empty Document Analysis response."
        )

    if not _looks_like_review_text(text):
        logger.warning(
            "[document_analysis_review.llm_malformed_output] chars=%s sample=%s",
            len(text),
            text[:160],
        )
        raise DocumentAnalysisReviewError(
            "The local SolomonAI LLM returned malformed Document Analysis text."
        )

    return text


def _build_document_packet(documents: List[Dict]) -> Dict:
    """Build the primary document identity used by the UI packet."""

    first_document = documents[0] if documents else {}

    return {
        "document_id": str(first_document.get("document_id") or "").strip(),
        "original_name": str(
            first_document.get("original_name")
            or first_document.get("filename")
            or "Selected file"
        ).strip(),
        "filename": str(
            first_document.get("filename")
            or first_document.get("original_name")
            or "Selected file"
        ).strip(),
    }


def _build_failure_packet(message: str) -> Dict:
    """Build a stable failure packet for the file-manager operation route."""

    return {
        "ok": False,
        "status": "failed",
        "packet_type": "docintel",
        "operation": DOCUMENT_ANALYSIS_OPERATION,
        "operation_label": DOCUMENT_ANALYSIS_LABEL,
        "payload": {
            "answer": message,
            "bridge": "",
            "report_kind": DOCUMENT_ANALYSIS_OPERATION,
            "suggestions": [],
        },
        "result": {
            "title": f"{DOCUMENT_ANALYSIS_LABEL} Failed",
            "summary": message,
            "raw_packet_type": "document_analysis_llm_error",
        },
        "user_output": message,
        "verdict": "REQUIRES_ACTION",
    }


def run_document_analysis_review(documents: List[Dict]) -> Dict:
    """
    Run a pure local-LLM Document Analysis for the file-manager operation.

    This intentionally bypasses Investigator, CaseFile, Orchestrator, DocIntel
    flow, Judge, the V1 drivetrain, and the deterministic report packet.
    """

    try:
        llm_documents = build_llm_documents(documents)

        if not llm_documents:
            return _build_failure_packet(
                "Document Analysis requires at least one readable document."
            )

        total_chars = sum(
            len(str(document.get("text") or ""))
            for document in llm_documents
        )

        logger.info(
            "[document_analysis_review.run_llm] docs=%s chars=%s call_site=%s",
            len(llm_documents),
            total_chars,
            LLM_CALL_SITE,
        )

        prompt = _build_llm_prompt(llm_documents)
        answer = _call_local_llm(prompt)

        logger.info(
            "[document_analysis_review.complete_llm] docs=%s answer_chars=%s",
            len(llm_documents),
            len(answer),
        )

        return {
            "ok": True,
            "status": "complete",
            "packet_type": "docintel",
            "operation": DOCUMENT_ANALYSIS_OPERATION,
            "operation_label": DOCUMENT_ANALYSIS_LABEL,
            "document": _build_document_packet(llm_documents),
            "payload": {
                "answer": answer,
                "bridge": "Document Analysis complete.",
                "report_kind": DOCUMENT_ANALYSIS_OPERATION,
                "suggestions": [],
            },
            "result": {
                "title": f"{DOCUMENT_ANALYSIS_LABEL} Complete",
                "summary": answer,
                "raw_packet_type": "document_analysis_llm",
                "engine": "local_llm",
                "call_site": LLM_CALL_SITE,
                "document_count": len(llm_documents),
                "source_characters": total_chars,
            },
            "user_output": answer,
            "verdict": "COMPLETE",
            "actions": [
                {
                    "action": "open_reader",
                    "label": "Open Reader",
                },
            ],
        }
    except DocumentAnalysisReviewError as exc:
        logger.warning("[document_analysis_review.failed] error=%s", exc)
        return _build_failure_packet(str(exc))
    except Exception:
        logger.exception("[document_analysis_review.unexpected_failed]")
        return _build_failure_packet(
            "Document Analysis could not complete because the adapter hit an unexpected error."
        )


__all__ = [
    "DocumentAnalysisReviewError",
    "run_document_analysis_review",
]