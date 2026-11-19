# solomon_core/skills/semantic/docintel_import_xlsx.py
# ---------------------------------------------------------------
# Phase 23.2 — Enterprise DocIntel XLS/XLSX Import + Normalization
#
# Hardened Phase-23 version:
#   • STRICT SCHEMA: only "file_path" accepted
#   • No inference from legacy argument names
#   • Path safety: allow only files inside Solomon data/uploads
#   • Deterministic normalization for downstream reconciliation
# ---------------------------------------------------------------

import os
import pandas as pd
from solomon_core.logger import get_logger

logger = get_logger("skill_docintel_import_xlsx")

# Root directory safety (Phase-23 policy)
ALLOWED_ROOT = os.path.join(os.getcwd(), "data", "uploads")


# ---------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------

def _normalize_column(col: str) -> str:
    """Deterministic Phase-23 column normalization."""
    return (
        str(col).strip().lower()
        .replace(" ", "_")
        .replace("-", "_")
        .replace("$", "usd")
        .replace("%", "pct")
    )


def _normalize_dataframe(df: pd.DataFrame):
    df = df.copy()
    df.columns = [_normalize_column(c) for c in df.columns]
    df = df.dropna(how="all")        # remove all-empty rows
    df = df.fillna("")               # fill NaN with empty strings
    return df


def _extract_numeric_total(df: pd.DataFrame):
    numeric_cols = df.select_dtypes(include="number")
    if numeric_cols.empty:
        return 0.0
    try:
        return float(numeric_cols.sum().sum())
    except Exception:
        return 0.0


def _is_safe_path(path: str) -> bool:
    """Prevent reading arbitrary system files."""
    try:
        abs_path = os.path.abspath(path)
        return abs_path.startswith(os.path.abspath(ALLOWED_ROOT))
    except Exception:
        return False


# ---------------------------------------------------------------
# ENTRY POINT — Phase-23.2 Strict XLSX Import
# ---------------------------------------------------------------

def execute(arguments: dict):

    # -----------------------------------------------------------
    # STRICT SCHEMA
    # -----------------------------------------------------------
    path = arguments.get("file_path")
    if not isinstance(path, str):
        return {
            "ok": False,
            "result": "file_path missing (strict schema)",
            "user_output": "No valid spreadsheet file was provided."
        }

    # -----------------------------------------------------------
    # SAFETY CHECK
    # -----------------------------------------------------------
    if not _is_safe_path(path):
        return {
            "ok": False,
            "result": "Attempt to access disallowed file path",
            "user_output": "Spreadsheet location is not permitted."
        }

    if not os.path.exists(path):
        return {
            "ok": False,
            "result": "Spreadsheet not found",
            "user_output": "The spreadsheet file does not exist."
        }

    ext = os.path.splitext(path)[1].lower()
    if ext not in (".xlsx", ".xls"):
        return {
            "ok": False,
            "result": f"Unsupported format: {ext}",
            "user_output": "Only .xlsx and .xls are supported."
        }

    # -----------------------------------------------------------
    # IMPORT SHEETS
    # -----------------------------------------------------------
    try:
        sheets = pd.read_excel(path, sheet_name=None)
    except Exception as e:
        logger.error(f"[docintel_import_xlsx] Excel read failure: {e}")
        return {
            "ok": False,
            "result": str(e),
            "user_output": "Failed to read spreadsheet."
        }

    structured = {
        "source_file": os.path.basename(path),
        "sheets": {},
        "totals": {},
    }

    # -----------------------------------------------------------
    # NORMALIZE SHEETS
    # -----------------------------------------------------------
    for sheet_name, df in sheets.items():
        try:
            df_norm = _normalize_dataframe(df)
            rows = df_norm.to_dict(orient="records")
            total = _extract_numeric_total(df_norm)

            structured["sheets"][sheet_name] = rows
            structured["totals"][sheet_name] = total

        except Exception as e:
            logger.error(f"[docintel_import_xlsx] Normalize failure in sheet '{sheet_name}': {e}")
            structured["sheets"][sheet_name] = []
            structured["totals"][sheet_name] = 0.0

    # -----------------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------------
    return {
        "ok": True,
        "structured": structured,
        "result": structured,
        "user_output": "Spreadsheet imported and normalized successfully."
    }
