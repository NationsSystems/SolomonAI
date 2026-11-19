# solomon_core/skills/semantic/docintel_export_xlsx.py
# ---------------------------------------------------------------
# Phase 23.1 — Enterprise DocIntel XLSX (Excel) Export Generator
#
# Produces a multi-sheet Excel workbook from DocIntel structured data.
# NO domain constants. NO demo-specific logic. Fully generic.
#
# Sheets:
#   1. Executive Summary
#   2. Obligations
#   3. Financials
#   4. Conflicts
#   5. Dates & Key Sections
#
# Inputs:
#   structured : dict  (machine-readable DocIntel block)
#   result     : str   (narrative summary)
#   filename   : str   (optional base name)
#
# Output (strict):
#   {
#       ok: True,
#       path: "<full path>",
#       format: "xlsx",
#       user_output: "Excel report exported successfully to: <path>"
#   }
# ---------------------------------------------------------------

import os
from datetime import datetime
from solomon_core.logger import get_logger

from openpyxl import Workbook
from openpyxl.styles import Font

logger = get_logger("skill_docintel_export_xlsx")

# Local export folder — NOT a domain constant
EXPORT_DIR = os.path.join(os.getcwd(), "data", "reports")
os.makedirs(EXPORT_DIR, exist_ok=True)


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _safe_filename(name: str):
    return "".join(c for c in name if c.isalnum() or c in ("_", "-", ".")).rstrip()


def _build_filename(base: str, ext: str):
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = base or f"docintel_report_{ts}"
    return f"{_safe_filename(base)}.{ext}"


def _bold(cell):
    cell.font = Font(bold=True)


# ---------------------------------------------------------------
# Sheet Builders
# ---------------------------------------------------------------

def _sheet_executive_summary(wb: Workbook, title: str, narrative: str):
    ws = wb.active
    ws.title = "Executive Summary"

    ws.append([title])
    _bold(ws["A1"])

    ws.append([])
    ws.append(["Summary"])
    _bold(ws["A3"])

    for line in (narrative or "").splitlines():
        ws.append([line])


def _sheet_obligations(wb: Workbook, structured: dict):
    ws = wb.create_sheet("Obligations")
    ws.append(["Document", "Obligation"])
    _bold(ws["A1"])
    _bold(ws["B1"])

    obligations = structured.get("obligation_index", {})
    for doc, items in obligations.items():
        for item in items:
            ws.append([doc, item])


def _sheet_financials(wb: Workbook, structured: dict):
    ws = wb.create_sheet("Financials")
    ws.append(["Document A", "Document B", "Shared Currency", "Unique to A", "Unique to B"])

    for cell in ("A1", "B1", "C1", "D1", "E1"):
        _bold(ws[cell])

    shared = structured.get("shared_currency", [])
    conflicts = structured.get("currency_conflicts", [])

    # Shared currency blocks
    for block in shared:
        ws.append([
            block.get("doc_a"),
            block.get("doc_b"),
            ", ".join(block.get("shared", [])),
            "",
            "",
        ])

    # Currency conflicts
    for block in conflicts:
        ws.append([
            block.get("doc_a"),
            block.get("doc_b"),
            "",
            ", ".join(block.get("unique_to_a", [])),
            ", ".join(block.get("unique_to_b", [])),
        ])


def _sheet_conflicts(wb: Workbook, structured: dict):
    ws = wb.create_sheet("Conflicts")
    ws.append(["Document A", "Document B", "Conflict Type", "Details"])

    for cell in ("A1", "B1", "C1", "D1"):
        _bold(ws[cell])

    for block in structured.get("currency_conflicts", []):
        ws.append([
            block.get("doc_a"),
            block.get("doc_b"),
            "Currency",
            f"A Only: {block.get('unique_to_a', [])} | B Only: {block.get('unique_to_b', [])}",
        ])


def _sheet_dates_and_sections(wb: Workbook, structured: dict):
    ws = wb.create_sheet("Dates & Key Sections")
    ws.append(["Document", "Dates", "Sections"])

    for cell in ("A1", "B1", "C1"):
        _bold(ws[cell])

    documents = structured.get("documents", {})
    date_index = structured.get("date_index", {})

    for doc, normalized in documents.items():
        dates = date_index.get(doc, [])
        sections = normalized.get("sections", [])

        ws.append([
            doc,
            ", ".join(dates),
            ", ".join(sections),
        ])


# ---------------------------------------------------------------
# ENTRY POINT — Phase-23.1 Strict XLSX Export
# ---------------------------------------------------------------

def execute(arguments: dict):

    structured = arguments.get("structured")
    narrative = arguments.get("result") or arguments.get("narrative", "")
    filename = arguments.get("filename")

    # Strict validation — must have SOMETHING to export
    if not structured and not narrative:
        return {
            "ok": False,
            "result": "No report content provided",
            "user_output": "Nothing to export."
        }

    outfile = _build_filename(filename, "xlsx")
    full_path = os.path.join(EXPORT_DIR, outfile)

    title = filename or "Solomon DocIntel Excel Report"

    try:
        wb = Workbook()

        _sheet_executive_summary(wb, title, narrative)
        _sheet_obligations(wb, structured or {})
        _sheet_financials(wb, structured or {})
        _sheet_conflicts(wb, structured or {})
        _sheet_dates_and_sections(wb, structured or {})

        wb.save(full_path)

    except Exception as e:
        logger.error(f"[docintel_export_xlsx] Export failure: {e}")
        return {
            "ok": False,
            "result": str(e),
            "user_output": "Excel export failed"
        }

    return {
        "ok": True,
        "path": full_path,
        "format": "xlsx",
        "user_output": f"Excel report exported successfully to: {full_path}"
    }
