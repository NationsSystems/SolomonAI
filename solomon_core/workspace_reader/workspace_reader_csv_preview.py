# -------------------------------------------------------------------
# FILE: workspace_reader_csv_preview.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# First-party read-only CSV preview helpers.
# -------------------------------------------------------------------

import csv
from datetime import date, datetime, time
from decimal import Decimal
from io import StringIO
from pathlib import Path
from typing import Dict, List, Tuple

from solomon_core.logger import get_logger
from solomon_core.workspace_reader.workspace_reader_tabular_evidence import (
    build_tabular_evidence_text_blocks,
)

logger = get_logger("workspace_reader.csv_preview")

MAX_CSV_PREVIEW_BYTES = 900_000
MAX_CSV_PREVIEW_ROWS = 80
MAX_CSV_PREVIEW_COLUMNS = 18
MIN_CSV_DISPLAY_ROWS = 28
MIN_CSV_DISPLAY_COLUMNS = 10
MAX_CSV_SCAN_ROWS = 1000
MAX_CSV_CELL_CHARS = 120
MAX_CSV_TEXT_BLOCKS = 120

CSV_ENCODING_ATTEMPTS = (
    "utf-8-sig",
    "utf-8",
    "cp1252",
    "latin-1",
)


def format_csv_cell_value(value) -> str:
    """Return a compact, safe display value for a CSV cell."""

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

    if len(clean_text) > MAX_CSV_CELL_CHARS:
        return f"{clean_text[: MAX_CSV_CELL_CHARS - 1].rstrip()}…"

    return clean_text


def get_csv_preview_total_cells(sheets: List[Dict]) -> int:
    """Return the total rendered preview cell count."""

    total_cells = 0

    for sheet in sheets:
        for row in sheet.get("rows") or []:
            total_cells += len(row.get("cells") or [])

    return total_cells


def get_csv_preview_non_empty_cells(sheets: List[Dict]) -> int:
    """Return the total non-empty preview cell count."""

    return sum(int(sheet.get("non_empty_cell_count") or 0) for sheet in sheets)


def _column_index_to_label(index: int) -> str:
    """Return spreadsheet-style column label for a one-based index."""

    value = int(index or 0)

    if value <= 0:
        return ""

    label = ""

    while value:
        value, remainder = divmod(value - 1, 26)
        label = chr(65 + remainder) + label

    return label


def _build_column_labels(column_count: int) -> List[str]:
    """Return spreadsheet column labels."""

    return [
        _column_index_to_label(index)
        for index in range(1, int(column_count or 0) + 1)
    ]


def _read_csv_preview_bytes(source_path: str) -> Tuple[bytes, bool]:
    """Read a bounded byte sample for safe CSV preview."""

    path = Path(str(source_path or "").strip())
    file_size = path.stat().st_size
    truncated = file_size > MAX_CSV_PREVIEW_BYTES

    with path.open("rb") as handle:
        return handle.read(MAX_CSV_PREVIEW_BYTES), truncated


def _decode_csv_preview_bytes(raw_bytes: bytes) -> Tuple[str, str]:
    """Decode CSV preview bytes using conservative local encodings."""

    if not raw_bytes:
        return "", "empty"

    for encoding in CSV_ENCODING_ATTEMPTS:
        try:
            return raw_bytes.decode(encoding), encoding
        except UnicodeDecodeError:
            continue

    return raw_bytes.decode("utf-8", errors="replace"), "utf-8-replace"


def _sniff_csv_dialect(text: str):
    """Return a CSV dialect from a bounded sample, falling back safely."""

    sample = str(text or "")[:8192]

    try:
        return csv.Sniffer().sniff(sample)
    except csv.Error:
        return csv.excel


def _parse_csv_rows(text: str) -> Tuple[List[List[str]], str]:
    """Parse CSV text into bounded row values."""

    dialect = _sniff_csv_dialect(text)
    reader = csv.reader(StringIO(str(text or "")), dialect)
    parsed_rows: List[List[str]] = []
    dialect_name = getattr(dialect, "__name__", "") or "sniffed"

    for row_index, row in enumerate(reader, start=1):
        if row_index > MAX_CSV_SCAN_ROWS:
            break

        parsed_rows.append([
            format_csv_cell_value(cell)
            for cell in list(row or [])[:MAX_CSV_PREVIEW_COLUMNS]
        ])

    return parsed_rows, dialect_name


def _build_display_rows(parsed_rows: List[List[str]]) -> Tuple[List[Dict], int, int, int, int]:
    """Build a bounded spreadsheet-like display grid from parsed CSV rows."""

    last_non_empty_row = 0
    last_non_empty_column = 0
    non_empty_cell_count = 0
    scanned_row_count = len(parsed_rows)

    for row_index, row in enumerate(parsed_rows, start=1):
        row_last_non_empty_column = 0

        for column_index, cell_value in enumerate(row, start=1):
            if cell_value:
                row_last_non_empty_column = column_index
                non_empty_cell_count += 1

        if row_last_non_empty_column > 0:
            last_non_empty_row = row_index
            last_non_empty_column = max(
                last_non_empty_column,
                row_last_non_empty_column,
            )

    if last_non_empty_column <= 0:
        rendered_column_count = MIN_CSV_DISPLAY_COLUMNS
    else:
        rendered_column_count = max(
            MIN_CSV_DISPLAY_COLUMNS,
            min(last_non_empty_column, MAX_CSV_PREVIEW_COLUMNS),
        )

    if last_non_empty_row <= 0:
        display_row_count = MIN_CSV_DISPLAY_ROWS
    else:
        display_row_count = max(
            MIN_CSV_DISPLAY_ROWS,
            min(last_non_empty_row, MAX_CSV_PREVIEW_ROWS),
        )

    rendered_rows: List[Dict] = []

    for row_number in range(1, display_row_count + 1):
        source_cells = list(parsed_rows[row_number - 1]) if row_number <= len(parsed_rows) else []
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
        last_non_empty_row,
        last_non_empty_column,
    )


def _normalize_sheet_name(source_path: str) -> str:
    """Return a compact CSV sheet label."""

    source_name = Path(str(source_path or "")).stem.strip() or "CSV"
    clean_name = source_name.replace("_", " ").strip()

    if not clean_name:
        return "CSV"

    if len(clean_name) > 80:
        return f"{clean_name[:79].rstrip()}…"

    return clean_name


def build_csv_preview(
    source_path: str,
    *,
    request_id: str = "untracked",
) -> Tuple[List[Dict], bool]:
    """Build safe first-party CSV preview sheets."""

    clean_path = str(source_path or "").strip()
    raw_bytes, byte_truncated = _read_csv_preview_bytes(clean_path)
    decoded_text, encoding = _decode_csv_preview_bytes(raw_bytes)
    parsed_rows, dialect_name = _parse_csv_rows(decoded_text)

    (
        rendered_rows,
        rendered_column_count,
        non_empty_cell_count,
        last_non_empty_row,
        last_non_empty_column,
    ) = _build_display_rows(parsed_rows)

    row_limit_hit = (
        len(parsed_rows) > MAX_CSV_PREVIEW_ROWS
        or len(parsed_rows) >= MAX_CSV_SCAN_ROWS
    )
    column_limit_hit = last_non_empty_column > MAX_CSV_PREVIEW_COLUMNS
    truncated = byte_truncated or row_limit_hit or column_limit_hit

    if non_empty_cell_count > 0 and rendered_column_count > 0:
        range_label = (
            f"A1:{_column_index_to_label(rendered_column_count)}"
            f"{len(rendered_rows)}"
        )
        data_range_label = (
            f"A1:{_column_index_to_label(max(1, last_non_empty_column))}"
            f"{max(1, last_non_empty_row)}"
        )
    else:
        range_label = "No readable cells"
        data_range_label = "No readable cells"

    sheet = {
        "name": _normalize_sheet_name(clean_path),
        "columns": _build_column_labels(rendered_column_count),
        "rows": rendered_rows,
        "declared_row_count": len(parsed_rows),
        "declared_column_count": last_non_empty_column,
        "rendered_row_count": len(rendered_rows),
        "rendered_column_count": rendered_column_count,
        "non_empty_cell_count": non_empty_cell_count,
        "scanned_row_count": len(parsed_rows),
        "last_non_empty_row": last_non_empty_row,
        "last_non_empty_column": last_non_empty_column,
        "range_label": range_label,
        "data_range_label": data_range_label,
        "truncated": truncated,
        "row_limit_hit": row_limit_hit,
        "column_limit_hit": column_limit_hit,
        "value_source": "csv",
        "read_mode": "text",
    }

    logger.info(
        "[workspace.reader.csv_preview_ready] request_id=%s path=%s "
        "encoding=%s dialect=%s rendered_rows=%s rendered_columns=%s "
        "rendered_cells=%s non_empty_cells=%s truncated=%s",
        request_id,
        Path(clean_path).name,
        encoding,
        dialect_name,
        len(rendered_rows),
        rendered_column_count,
        get_csv_preview_total_cells([sheet]),
        non_empty_cell_count,
        truncated,
    )

    return [sheet], truncated


def build_csv_preview_text_blocks(sheets: List[Dict]) -> List[str]:
    """Build bounded row-preserving text evidence for intelligence use."""

    return build_tabular_evidence_text_blocks(
        sheets,
        source_label="CSV",
        max_blocks=MAX_CSV_TEXT_BLOCKS,
        truncated_message="Preview truncated for this CSV file.",
    )
