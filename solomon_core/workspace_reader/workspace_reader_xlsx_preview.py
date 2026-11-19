# -------------------------------------------------------------------
# FILE: workspace_reader_xlsx_preview.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# First-party read-only XLSX workbook preview helpers.
# -------------------------------------------------------------------

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Tuple

from solomon_core.logger import get_logger
from solomon_core.workspace_reader.workspace_reader_tabular_evidence import (
    build_tabular_evidence_text_blocks,
)

logger = get_logger("workspace_reader.xlsx_preview")

MAX_XLSX_PREVIEW_SHEETS = 5
MAX_XLSX_PREVIEW_ROWS = 60
MAX_XLSX_PREVIEW_COLUMNS = 18
MIN_XLSX_DISPLAY_ROWS = 28
MIN_XLSX_DISPLAY_COLUMNS = 12
MAX_XLSX_SCAN_ROWS = 1000
MAX_XLSX_SCAN_COLUMNS = 80
MAX_XLSX_CELL_CHARS = 120
MAX_XLSX_TEXT_BLOCKS = 120


def format_xlsx_cell_value(value) -> str:
    """Return a compact, safe display value for an XLSX cell."""

    if value is None:
        return ""

    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"

    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %I:%M %p")

    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, time):
        return value.strftime("%I:%M %p")

    if isinstance(value, Decimal):
        text = format(value, "f")
    else:
        text = str(value)

    clean_text = " ".join(
        text.replace("\r", " ").replace("\n", " ").replace("\t", " ").split()
    )

    if len(clean_text) > MAX_XLSX_CELL_CHARS:
        return f"{clean_text[: MAX_XLSX_CELL_CHARS - 1].rstrip()}…"

    return clean_text


def get_xlsx_preview_total_cells(sheets: List[Dict]) -> int:
    """Return the total rendered preview cell count."""

    total_cells = 0

    for sheet in sheets:
        for row in sheet.get("rows") or []:
            total_cells += len(row.get("cells") or [])

    return total_cells


def get_xlsx_preview_non_empty_cells(sheets: List[Dict]) -> int:
    """Return the total non-empty preview cell count."""

    return sum(int(sheet.get("non_empty_cell_count") or 0) for sheet in sheets)


def _get_visible_worksheets(workbook) -> List:
    """Return visible worksheets only."""

    return [
        worksheet
        for worksheet in workbook.worksheets
        if getattr(worksheet, "sheet_state", "visible") == "visible"
    ]


def _normalize_sheet_name(name) -> str:
    """Return a compact safe sheet name."""

    clean_name = str(name or "Sheet").strip()

    if not clean_name:
        return "Sheet"

    if len(clean_name) > 80:
        return f"{clean_name[:79].rstrip()}…"

    return clean_name


def _build_column_labels(column_count: int) -> List[str]:
    """Return spreadsheet column labels."""

    from openpyxl.utils import get_column_letter

    return [get_column_letter(index) for index in range(1, column_count + 1)]


def _get_declared_dimension_count(value) -> int:
    """Return a safe worksheet dimension count."""

    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _prepare_read_only_worksheet(worksheet) -> None:
    """Reset unreliable read-only dimensions when supported by openpyxl."""

    reset_dimensions = getattr(worksheet, "reset_dimensions", None)

    if callable(reset_dimensions):
        reset_dimensions()


def _get_display_row_window(
    *,
    first_non_empty_row: int,
    last_non_empty_row: int,
) -> Tuple[int, int]:
    """Return the bounded row window shown in the spreadsheet preview."""

    if last_non_empty_row <= 0:
        return 0, 0

    if last_non_empty_row <= MAX_XLSX_PREVIEW_ROWS:
        start_row = 1
        data_row_count = last_non_empty_row
    else:
        start_row = max(1, first_non_empty_row)
        data_row_count = max(1, last_non_empty_row - start_row + 1)

    display_row_count = max(
        MIN_XLSX_DISPLAY_ROWS,
        min(data_row_count, MAX_XLSX_PREVIEW_ROWS),
    )
    end_row = start_row + display_row_count - 1

    return start_row, end_row


def _build_preview_rows_from_scan(
    worksheet,
) -> Tuple[List[Dict], int, int, int, int, int]:
    """Scan worksheet rows and build a bounded spreadsheet-like display grid."""

    scanned_rows: Dict[int, List[str]] = {}
    first_non_empty_row = 0
    last_non_empty_row = 0
    last_non_empty_column = 0
    non_empty_cell_count = 0
    scanned_row_count = 0

    for row_number, values in enumerate(worksheet.iter_rows(values_only=True), start=1):
        if row_number > MAX_XLSX_SCAN_ROWS:
            break

        scanned_row_count = row_number
        limited_values = list(values or ())[:MAX_XLSX_SCAN_COLUMNS]
        cells = [format_xlsx_cell_value(value) for value in limited_values]
        row_last_non_empty_column = 0

        for column_index, cell_value in enumerate(cells, start=1):
            if cell_value:
                row_last_non_empty_column = column_index
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
        MIN_XLSX_DISPLAY_COLUMNS,
        min(last_non_empty_column, MAX_XLSX_PREVIEW_COLUMNS),
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


def _build_xlsx_sheet_preview(
    worksheet,
    *,
    value_source: str,
    read_mode: str,
) -> Dict:
    """Build a bounded read-only preview for one worksheet."""

    from openpyxl.utils import get_column_letter

    if read_mode == "read_only":
        _prepare_read_only_worksheet(worksheet)

    sheet_name = _normalize_sheet_name(getattr(worksheet, "title", "Sheet"))
    declared_row_count = _get_declared_dimension_count(
        getattr(worksheet, "max_row", 0)
    )
    declared_column_count = _get_declared_dimension_count(
        getattr(worksheet, "max_column", 0)
    )

    (
        rendered_rows,
        rendered_column_count,
        non_empty_cell_count,
        scanned_row_count,
        last_non_empty_row,
        last_non_empty_column,
    ) = _build_preview_rows_from_scan(worksheet)

    last_rendered_row = (
        int(rendered_rows[-1].get("row_number") or 0) if rendered_rows else 0
    )
    row_limit_hit = non_empty_cell_count > 0 and (
        last_non_empty_row > last_rendered_row
        or scanned_row_count >= MAX_XLSX_SCAN_ROWS
    )
    column_limit_hit = last_non_empty_column > MAX_XLSX_PREVIEW_COLUMNS
    truncated = row_limit_hit or column_limit_hit

    if rendered_rows and rendered_column_count > 0:
        range_label = (
            f"A{rendered_rows[0].get('row_number', 1)}:"
            f"{get_column_letter(rendered_column_count)}"
            f"{last_rendered_row}"
        )
        data_range_label = f"A1:{get_column_letter(last_non_empty_column)}{last_non_empty_row}"
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
        "value_source": value_source,
        "read_mode": read_mode,
    }


def _build_xlsx_preview_from_workbook(
    source_path: str,
    *,
    data_only: bool,
    read_only: bool,
) -> Tuple[List[Dict], bool, int]:
    """Build XLSX preview sheets from one workbook read mode."""

    from openpyxl import load_workbook

    workbook = None
    clean_path = str(source_path or "").strip()
    value_source = "cached_values" if data_only else "formulas"
    read_mode = "read_only" if read_only else "standard"

    try:
        workbook = load_workbook(
            filename=clean_path,
            read_only=read_only,
            data_only=data_only,
        )

        visible_worksheets = _get_visible_worksheets(workbook)
        selected_worksheets = visible_worksheets[:MAX_XLSX_PREVIEW_SHEETS]
        preview_sheets = [
            _build_xlsx_sheet_preview(
                worksheet,
                value_source=value_source,
                read_mode=read_mode,
            )
            for worksheet in selected_worksheets
        ]

        workbook_truncated = len(visible_worksheets) > MAX_XLSX_PREVIEW_SHEETS
        preview_truncated = workbook_truncated or any(
            bool(sheet.get("truncated")) for sheet in preview_sheets
        )

        return preview_sheets, preview_truncated, len(visible_worksheets)

    finally:
        if workbook is not None:
            workbook.close()


def _select_best_preview(
    current_sheets: List[Dict],
    current_truncated: bool,
    current_visible_sheet_count: int,
    current_source: str,
    candidate_sheets: List[Dict],
    candidate_truncated: bool,
    candidate_visible_sheet_count: int,
    candidate_source: str,
) -> Tuple[List[Dict], bool, int, str]:
    """Return the preview with the most readable cell content."""

    current_non_empty_cells = get_xlsx_preview_non_empty_cells(current_sheets)
    candidate_non_empty_cells = get_xlsx_preview_non_empty_cells(candidate_sheets)

    if candidate_non_empty_cells > current_non_empty_cells:
        return (
            candidate_sheets,
            candidate_truncated,
            candidate_visible_sheet_count,
            candidate_source,
        )

    return (
        current_sheets,
        current_truncated,
        current_visible_sheet_count,
        current_source,
    )


def build_xlsx_preview(
    source_path: str,
    *,
    request_id: str = "untracked",
) -> Tuple[List[Dict], bool]:
    """Build safe first-party XLSX workbook preview sheets."""

    clean_path = str(source_path or "").strip()

    selected_sheets, selected_truncated, visible_sheet_count = (
        _build_xlsx_preview_from_workbook(
            clean_path,
            data_only=True,
            read_only=True,
        )
    )
    selected_source = "cached_values/read_only"

    if get_xlsx_preview_non_empty_cells(selected_sheets) <= 0:
        logger.info(
            "[workspace.reader.xlsx_cached_values_empty] request_id=%s path=%s "
            "visible_sheets=%s retry=formulas_read_only",
            request_id,
            Path(clean_path).name,
            visible_sheet_count,
        )

        formula_sheets, formula_truncated, formula_visible_sheet_count = (
            _build_xlsx_preview_from_workbook(
                clean_path,
                data_only=False,
                read_only=True,
            )
        )

        (
            selected_sheets,
            selected_truncated,
            visible_sheet_count,
            selected_source,
        ) = _select_best_preview(
            selected_sheets,
            selected_truncated,
            visible_sheet_count,
            selected_source,
            formula_sheets,
            formula_truncated,
            formula_visible_sheet_count,
            "formulas/read_only",
        )

    if get_xlsx_preview_non_empty_cells(selected_sheets) <= 0:
        logger.info(
            "[workspace.reader.xlsx_read_only_empty] request_id=%s path=%s "
            "visible_sheets=%s retry=standard_cached_values",
            request_id,
            Path(clean_path).name,
            visible_sheet_count,
        )

        standard_sheets, standard_truncated, standard_visible_sheet_count = (
            _build_xlsx_preview_from_workbook(
                clean_path,
                data_only=True,
                read_only=False,
            )
        )

        (
            selected_sheets,
            selected_truncated,
            visible_sheet_count,
            selected_source,
        ) = _select_best_preview(
            selected_sheets,
            selected_truncated,
            visible_sheet_count,
            selected_source,
            standard_sheets,
            standard_truncated,
            standard_visible_sheet_count,
            "cached_values/standard",
        )

    if get_xlsx_preview_non_empty_cells(selected_sheets) <= 0:
        logger.info(
            "[workspace.reader.xlsx_standard_cached_values_empty] "
            "request_id=%s path=%s visible_sheets=%s retry=standard_formulas",
            request_id,
            Path(clean_path).name,
            visible_sheet_count,
        )

        standard_formula_sheets = []
        standard_formula_truncated = False
        standard_formula_visible_sheet_count = visible_sheet_count

        try:
            (
                standard_formula_sheets,
                standard_formula_truncated,
                standard_formula_visible_sheet_count,
            ) = _build_xlsx_preview_from_workbook(
                clean_path,
                data_only=False,
                read_only=False,
            )
        except Exception as exc:
            logger.warning(
                "[workspace.reader.xlsx_standard_formula_retry_failed] "
                "request_id=%s path=%s error=%s",
                request_id,
                Path(clean_path).name,
                exc,
            )

        (
            selected_sheets,
            selected_truncated,
            visible_sheet_count,
            selected_source,
        ) = _select_best_preview(
            selected_sheets,
            selected_truncated,
            visible_sheet_count,
            selected_source,
            standard_formula_sheets,
            standard_formula_truncated,
            standard_formula_visible_sheet_count,
            "formulas/standard",
        )

    logger.info(
        "[workspace.reader.xlsx_preview_ready] request_id=%s path=%s "
        "visible_sheets=%s rendered_sheets=%s rendered_cells=%s "
        "non_empty_cells=%s value_source=%s truncated=%s",
        request_id,
        Path(clean_path).name,
        visible_sheet_count,
        len(selected_sheets),
        get_xlsx_preview_total_cells(selected_sheets),
        get_xlsx_preview_non_empty_cells(selected_sheets),
        selected_source,
        selected_truncated,
    )

    return selected_sheets, selected_truncated


def build_xlsx_preview_text_blocks(sheets: List[Dict]) -> List[str]:
    """Build bounded row-preserving text evidence for intelligence use."""

    return build_tabular_evidence_text_blocks(
        sheets,
        source_label="XLSX Sheet",
        max_blocks=MAX_XLSX_TEXT_BLOCKS,
        truncated_message="Preview truncated for this sheet.",
    )
