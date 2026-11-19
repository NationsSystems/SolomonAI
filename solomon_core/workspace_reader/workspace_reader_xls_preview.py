# -------------------------------------------------------------------
# FILE: workspace_reader_xls_preview.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# First-party read-only legacy XLS workbook preview helpers.
# -------------------------------------------------------------------

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

from solomon_core.logger import get_logger
from solomon_core.workspace_reader.workspace_reader_tabular_evidence import (
    build_tabular_evidence_text_blocks,
)

logger = get_logger("workspace_reader.xls_preview")

MAX_XLS_PREVIEW_SHEETS = 5
MAX_XLS_PREVIEW_ROWS = 60
MAX_XLS_PREVIEW_COLUMNS = 18
MIN_XLS_DISPLAY_ROWS = 28
MIN_XLS_DISPLAY_COLUMNS = 12
MAX_XLS_SCAN_ROWS = 1000
MAX_XLS_SCAN_COLUMNS = 80
MAX_XLS_CELL_CHARS = 120
MAX_XLS_TEXT_BLOCKS = 120


def format_xls_cell_text(text: str) -> str:
    """Return compact, safe display text for a legacy XLS cell."""

    clean_text = " ".join(
        str(text or "")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    )

    if len(clean_text) > MAX_XLS_CELL_CHARS:
        return f"{clean_text[: MAX_XLS_CELL_CHARS - 1].rstrip()}…"

    return clean_text


def format_xls_number(value) -> str:
    """Return a compact spreadsheet-style number label."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return format_xls_cell_text(value)

    if number.is_integer():
        return str(int(number))

    return format(number, ".12g")


def format_xls_cell_value(workbook, cell) -> str:
    """Return a compact, safe display value for a legacy XLS cell."""

    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError(
            "Legacy XLS preview requires the xlrd package."
        ) from exc

    cell_type = getattr(cell, "ctype", None)
    value = getattr(cell, "value", "")

    if cell_type in {xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK}:
        return ""

    if cell_type == xlrd.XL_CELL_BOOLEAN:
        return "TRUE" if bool(value) else "FALSE"

    if cell_type == xlrd.XL_CELL_NUMBER:
        return format_xls_number(value)

    if cell_type == xlrd.XL_CELL_DATE:
        try:
            parsed_datetime = xlrd.xldate_as_datetime(
                value,
                getattr(workbook, "datemode", 0),
            )
        except Exception:
            return format_xls_cell_text(value)

        if parsed_datetime.time() == time(0, 0):
            return parsed_datetime.strftime("%Y-%m-%d")

        return parsed_datetime.strftime("%Y-%m-%d %I:%M %p")

    if cell_type == xlrd.XL_CELL_ERROR:
        error_text = getattr(xlrd, "error_text_from_code", {}).get(value)
        return format_xls_cell_text(error_text or f"#ERROR {value}")

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %I:%M %p")

    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, time):
        return value.strftime("%I:%M %p")

    if isinstance(value, Decimal):
        return format_xls_cell_text(format(value, "f"))

    return format_xls_cell_text(value)


def get_xls_preview_total_cells(sheets: List[Dict]) -> int:
    """Return the total rendered preview cell count."""

    total_cells = 0

    for sheet in sheets:
        for row in sheet.get("rows") or []:
            total_cells += len(row.get("cells") or [])

    return total_cells


def get_xls_preview_non_empty_cells(sheets: List[Dict]) -> int:
    """Return the total non-empty preview cell count."""

    return sum(int(sheet.get("non_empty_cell_count") or 0) for sheet in sheets)


def _normalize_sheet_name(name) -> str:
    """Return a compact safe sheet name."""

    clean_name = str(name or "Sheet").strip()

    if not clean_name:
        return "Sheet"

    if len(clean_name) > 80:
        return f"{clean_name[:79].rstrip()}…"

    return clean_name


def _build_column_label(column_number: int) -> str:
    """Return an Excel-style column label for a one-based column number."""

    label = ""
    current_number = int(column_number or 0)

    while current_number > 0:
        current_number, remainder = divmod(current_number - 1, 26)
        label = f"{chr(65 + remainder)}{label}"

    return label or "A"


def _build_column_labels(column_count: int) -> List[str]:
    """Return spreadsheet column labels."""

    return [_build_column_label(index) for index in range(1, column_count + 1)]


def _get_visible_sheets(workbook) -> List:
    """Return visible sheets when visibility metadata is available."""

    visible_sheets = []

    for sheet in workbook.sheets():
        visibility = getattr(sheet, "visibility", 0)

        if visibility in (0, "visible", None):
            visible_sheets.append(sheet)

    return visible_sheets or list(workbook.sheets())


def _get_display_row_window(
    *,
    first_non_empty_row: int,
    last_non_empty_row: int,
) -> Tuple[int, int]:
    """Return the bounded row window shown in the spreadsheet preview."""

    if last_non_empty_row <= 0:
        return 0, 0

    if last_non_empty_row <= MAX_XLS_PREVIEW_ROWS:
        start_row = 1
        data_row_count = last_non_empty_row
    else:
        start_row = max(1, first_non_empty_row)
        data_row_count = max(1, last_non_empty_row - start_row + 1)

    display_row_count = max(
        MIN_XLS_DISPLAY_ROWS,
        min(data_row_count, MAX_XLS_PREVIEW_ROWS),
    )
    end_row = start_row + display_row_count - 1

    return start_row, end_row


def _build_preview_rows_from_scan(
    workbook,
    sheet,
) -> Tuple[List[Dict], int, int, int, int, int]:
    """Scan a legacy XLS sheet and build a bounded spreadsheet-like grid."""

    scanned_rows: Dict[int, List[str]] = {}
    first_non_empty_row = 0
    last_non_empty_row = 0
    last_non_empty_column = 0
    non_empty_cell_count = 0
    scanned_row_count = 0
    max_rows = min(int(getattr(sheet, "nrows", 0) or 0), MAX_XLS_SCAN_ROWS)
    max_columns = min(int(getattr(sheet, "ncols", 0) or 0), MAX_XLS_SCAN_COLUMNS)

    for zero_based_row in range(max_rows):
        row_number = zero_based_row + 1
        scanned_row_count = row_number
        cells: List[str] = []
        row_last_non_empty_column = 0

        for zero_based_column in range(max_columns):
            column_number = zero_based_column + 1
            cell = sheet.cell(zero_based_row, zero_based_column)
            cell_value = format_xls_cell_value(workbook, cell)
            cells.append(cell_value)

            if cell_value:
                row_last_non_empty_column = column_number
                non_empty_cell_count += 1

        if row_last_non_empty_column <= 0:
            continue

        if first_non_empty_row <= 0:
            first_non_empty_row = row_number

        last_non_empty_row = row_number
        last_non_empty_column = max(
            last_non_empty_column,
            row_last_non_empty_column,
        )
        scanned_rows[row_number] = cells[:row_last_non_empty_column]

    if non_empty_cell_count <= 0:
        return [], 0, 0, scanned_row_count, 0, 0

    rendered_column_count = max(
        MIN_XLS_DISPLAY_COLUMNS,
        min(last_non_empty_column, MAX_XLS_PREVIEW_COLUMNS),
    )
    start_row, end_row = _get_display_row_window(
        first_non_empty_row=first_non_empty_row,
        last_non_empty_row=last_non_empty_row,
    )

    rendered_rows: List[Dict] = []

    for row_number in range(start_row, end_row + 1):
        source_cells = list(scanned_rows.get(row_number) or [])
        display_cells = source_cells[:rendered_column_count]

        if len(display_cells) < rendered_column_count:
            display_cells.extend([""] * (rendered_column_count - len(display_cells)))

        rendered_rows.append(
            {
                "row_number": row_number,
                "cells": display_cells,
            }
        )

    return (
        rendered_rows,
        rendered_column_count,
        non_empty_cell_count,
        scanned_row_count,
        last_non_empty_row,
        last_non_empty_column,
    )


def _build_xls_sheet_preview(workbook, sheet) -> Dict:
    """Build a bounded read-only preview for one legacy XLS sheet."""

    sheet_name = _normalize_sheet_name(getattr(sheet, "name", "Sheet"))
    declared_row_count = int(getattr(sheet, "nrows", 0) or 0)
    declared_column_count = int(getattr(sheet, "ncols", 0) or 0)

    (
        rendered_rows,
        rendered_column_count,
        non_empty_cell_count,
        scanned_row_count,
        last_non_empty_row,
        last_non_empty_column,
    ) = _build_preview_rows_from_scan(workbook, sheet)

    last_rendered_row = (
        int(rendered_rows[-1].get("row_number") or 0) if rendered_rows else 0
    )
    row_limit_hit = non_empty_cell_count > 0 and (
        last_non_empty_row > last_rendered_row
        or scanned_row_count >= MAX_XLS_SCAN_ROWS
    )
    column_limit_hit = last_non_empty_column > MAX_XLS_PREVIEW_COLUMNS
    truncated = row_limit_hit or column_limit_hit

    if rendered_rows and rendered_column_count > 0:
        range_label = (
            f"A{rendered_rows[0].get('row_number', 1)}:"
            f"{_build_column_label(rendered_column_count)}"
            f"{last_rendered_row}"
        )
        data_range_label = (
            f"A1:{_build_column_label(last_non_empty_column)}{last_non_empty_row}"
        )
    else:
        range_label = "No readable cells"
        data_range_label = "No readable cells"

    return {
        "name": sheet_name,
        "columns": _build_column_labels(rendered_column_count),
        "rows": rendered_rows,
        "declared_row_count": declared_row_count,
        "declared_column_count": declared_column_count,
        "rendered_row_count": len(rendered_rows),
        "rendered_column_count": rendered_column_count,
        "non_empty_cell_count": non_empty_cell_count,
        "scanned_row_count": scanned_row_count,
        "last_non_empty_row": last_non_empty_row,
        "last_non_empty_column": last_non_empty_column,
        "range_label": range_label,
        "data_range_label": data_range_label,
        "truncated": truncated,
        "row_limit_hit": row_limit_hit,
        "column_limit_hit": column_limit_hit,
        "value_source": "legacy_xls_values",
        "read_mode": "xlrd",
    }


def build_xls_preview(
    source_path: str,
    *,
    request_id: str = "untracked",
) -> Tuple[List[Dict], bool]:
    """Build safe first-party legacy XLS workbook preview sheets."""

    try:
        import xlrd
    except ImportError as exc:
        raise RuntimeError(
            "Legacy XLS preview requires the xlrd package."
        ) from exc

    clean_path = str(source_path or "").strip()
    workbook = xlrd.open_workbook(
        clean_path,
        formatting_info=False,
        on_demand=True,
    )

    try:
        visible_sheets = _get_visible_sheets(workbook)
        selected_sheets = visible_sheets[:MAX_XLS_PREVIEW_SHEETS]
        preview_sheets = [
            _build_xls_sheet_preview(workbook, sheet)
            for sheet in selected_sheets
        ]
        workbook_truncated = len(visible_sheets) > MAX_XLS_PREVIEW_SHEETS
        preview_truncated = workbook_truncated or any(
            bool(sheet.get("truncated")) for sheet in preview_sheets
        )

        logger.info(
            "[workspace.reader.xls_preview_ready] request_id=%s path=%s "
            "visible_sheets=%s rendered_sheets=%s rendered_cells=%s "
            "non_empty_cells=%s truncated=%s",
            request_id,
            Path(clean_path).name,
            len(visible_sheets),
            len(preview_sheets),
            get_xls_preview_total_cells(preview_sheets),
            get_xls_preview_non_empty_cells(preview_sheets),
            preview_truncated,
        )

        return preview_sheets, preview_truncated

    finally:
        workbook.release_resources()


def build_xls_preview_text_blocks(sheets: List[Dict]) -> List[str]:
    """Build bounded row-preserving text evidence for intelligence use."""

    return build_tabular_evidence_text_blocks(
        sheets,
        source_label="XLS Sheet",
        max_blocks=MAX_XLS_TEXT_BLOCKS,
        truncated_message="Preview truncated for this sheet.",
    )
