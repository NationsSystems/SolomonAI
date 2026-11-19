# solomon_core/skills/semantic/docintel_report_export.py
# ---------------------------------------------------------------
# Phase 23 — Enterprise DocIntel Report Export Generator
#
# Supported formats:
#   ✓ DOCX
#   ✓ PDF
#   ✓ CSV
#
# Phase-23 Requirements:
#   • STRICT SCHEMA
#   • Safe output folder
#   • Deterministic filename generation
#   • Domain-neutral, no hidden dependencies
# ---------------------------------------------------------------

import os
import csv
from datetime import datetime
from solomon_core.logger import get_logger

from docx import Document
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

logger = get_logger("skill_docintel_report_export")

EXPORT_DIR = os.path.join(os.getcwd(), "data", "reports")
os.makedirs(EXPORT_DIR, exist_ok=True)


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _safe_filename(name: str):
    """Prevent unsafe filenames."""
    return "".join(c for c in name if c.isalnum() or c in ("_", "-", ".")).rstrip()


def _build_filename(base: str, ext: str):
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = base or f"docintel_report_{ts}"
    return f"{_safe_filename(base)}.{ext}"


def _export_docx(path, title, narrative, structured):
    doc = Document()
    doc.add_heading(title, level=1)

    doc.add_heading("Executive Summary", level=2)
    doc.add_paragraph(narrative or "")

    doc.add_heading("Structured Intelligence", level=2)
    doc.add_paragraph(str(structured) if structured is not None else "(none)")

    doc.save(path)


def _export_pdf(path, title, narrative, structured):
    """PDF generator with page-overflow protection."""
    c = canvas.Canvas(path, pagesize=LETTER)
    width, height = LETTER
    y = height - 50

    def write_line(text, font="Helvetica", size=11, step=14):
        nonlocal y
        c.setFont(font, size)
        c.drawString(50, y, text[:90])
        y -= step
        if y < 80:
            c.showPage()
            y = height - 50

    # Title
    write_line(title, font="Helvetica-Bold", size=14, step=26)

    write_line("Executive Summary:", font="Helvetica-Bold", size=12, step=20)
    for line in (narrative or "").splitlines():
        write_line(line)

    write_line("", step=20)
    write_line("Structured Intelligence:", font="Helvetica-Bold", size=12, step=20)

    for line in str(structured).splitlines():
        write_line(line, size=9, step=12)

    c.save()


def _export_csv(path, structured):
    """Flattened CSV export for interoperability."""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if isinstance(structured, dict):
            for key, value in structured.items():
                writer.writerow([key, str(value)])
        else:
            writer.writerow(["data", str(structured)])


# ---------------------------------------------------------------
# ENTRY POINT — Phase-23 Hardened Export Skill
# ---------------------------------------------------------------

def execute(arguments: dict):

    structured = arguments.get("structured")
    narrative = arguments.get("result") or arguments.get("narrative", "")

    fmt = (arguments.get("format") or "docx").lower()
    filename = arguments.get("filename")

    if not structured and not narrative:
        return {
            "ok": False,
            "result": "No report content provided",
            "user_output": "Nothing to export."
        }

    if fmt not in ("docx", "pdf", "csv"):
        return {
            "ok": False,
            "result": f"Unsupported export format: {fmt}",
            "user_output": "Supported formats: docx, pdf, csv"
        }

    outfile = _build_filename(filename, fmt)
    full_path = os.path.join(EXPORT_DIR, outfile)

    title = filename or "Solomon DocIntel Report"

    try:
        if fmt == "docx":
            _export_docx(full_path, title, narrative, structured)
        elif fmt == "pdf":
            _export_pdf(full_path, title, narrative, structured)
        elif fmt == "csv":
            _export_csv(full_path, structured)

    except Exception as e:
        logger.error(f"[docintel_report_export] Export failure: {e}")
        return {
            "ok": False,
            "result": str(e),
            "user_output": "Report export failed."
        }

    return {
        "ok": True,
        "path": full_path,
        "format": fmt,
        "result": full_path,
        "user_output": f"Report exported successfully to: {full_path}"
    }
