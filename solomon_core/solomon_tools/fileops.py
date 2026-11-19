# fileops.py — Deterministic file operations for Solomon (structured exceptions + numeric safety)
import os
import json
import pandas as pd
import string
from pathlib import Path
from typing import List, Union

from config import settings

try:
    import docx
except ImportError:
    docx = None

try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

# ---------------------------------------------------
# NEW: FAISS (CPU only)
# ---------------------------------------------------
try:
    import faiss
except Exception:
    faiss = None


# ---------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------
class FileTypeError(Exception):
    pass


class FileReadError(Exception):
    pass


class FileValidationError(Exception):
    pass


# ---------------------------------------------------
# Paths
# ---------------------------------------------------
BASE_DIR = settings.DATA_DIR
UPLOADS_DIR = settings.UPLOADS_DIR

# New FAISS directory
FAISS_DIR = os.path.join(BASE_DIR, "faiss")
FAISS_INDEX_PATH = os.path.join(FAISS_DIR, "index.faiss")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(FAISS_DIR, exist_ok=True)


# ---------------------------------------------------
# User upload directory helper
# ---------------------------------------------------
def get_user_upload_dir(user_id: str = None) -> str:
    user = user_id or getattr(settings, "CURRENT_USER", "anonymous")
    path = os.path.join(UPLOADS_DIR, str(user))
    os.makedirs(path, exist_ok=True)
    return path


def resolve_user_file_path(filename: str, user_id: str = None) -> str:
    user_dir = get_user_upload_dir(user_id)
    safe_path = os.path.abspath(os.path.join(user_dir, os.path.basename(filename)))
    if not safe_path.startswith(os.path.abspath(user_dir)):
        raise FileReadError(f"Illegal path access attempt outside user dir: {filename}")
    if not os.path.exists(safe_path):
        raise FileReadError(f"File not found: {filename}")
    return safe_path


# ---------------------------------------------------
# MIME Detection
# ---------------------------------------------------
def detect_mime_type(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".txt":
        return "text/plain"
    elif ext == ".csv":
        return "text/csv"
    elif ext in [".xls", ".xlsx"]:
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif ext == ".json":
        return "application/json"
    elif ext == ".pdf":
        return "application/pdf"
    elif ext == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        raise FileTypeError(f"Unsupported file extension '{ext}' for file {path}")


# ---------------------------------------------------
# File Parser
# ---------------------------------------------------
def parse_file(filename: str) -> str:
    user_dir = get_user_upload_dir()
    path = os.path.join(user_dir, filename)
    if not os.path.exists(path):
        raise FileReadError(f"File not found: {filename}")

    try:
        mime_type = detect_mime_type(path)

        if mime_type == "text/plain":
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

        elif mime_type == "text/csv":
            return pd.read_csv(path).to_string(index=False)

        elif mime_type in [
            "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ]:
            return pd.read_excel(path).to_string(index=False)

        elif mime_type == "application/json":
            with open(path, "r", encoding="utf-8") as f:
                return json.dumps(json.load(f), indent=2)

        elif mime_type == "application.pdf" and PyPDF2:
            text = ""
            with open(path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                for page in reader.pages:
                    text += page.extract_text() or ""
            return text.strip() or "[Warning] PDF contains no readable text."

        elif mime_type == (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ) and docx:
            doc = docx.Document(path)
            return "\n".join(p.text for p in doc.paragraphs)

        else:
            raise FileTypeError(
                f"Unsupported MIME type or missing library for {filename}: {mime_type}"
            )

    except (FileTypeError, FileReadError):
        raise
    except Exception as e:
        raise FileReadError(f"Error parsing {filename}: {e}")


# ---------------------------------------------------
# Deterministic operations
# ---------------------------------------------------
def _meta(filename: str):
    """Return standardized metadata block."""
    user_dir = get_user_upload_dir()
    path = os.path.join(user_dir, filename)
    return {
        "filename": os.path.basename(filename),
        "filepath": path,
    }


def count_lines(filename: str) -> dict:
    try:
        meta = _meta(filename)
        content = parse_file(filename)
        return {
            "ok": True,
            **meta,
            "result": content.count("\n") + 1
        }
    except Exception as e:
        return {
            "ok": False,
            **_meta(filename),
            "error_type": type(e).__name__,
            "error_message": str(e),
            "result": None
        }


def first_n_lines(filename: str, n: int = 5) -> dict:
    try:
        meta = _meta(filename)
        content = parse_file(filename)
        lines = content.splitlines()
        return {
            "ok": True,
            **meta,
            "result": "\n".join(lines[:n])
        }
    except Exception as e:
        return {
            "ok": False,
            **_meta(filename),
            "error_type": type(e).__name__,
            "error_message": str(e),
            "result": None
        }


def get_words_starting_with(filename: str, letter: str) -> List[str]:
    try:
        content = parse_file(filename)
        return [w for w in content.split() if w.lower().startswith(letter.lower())]
    except Exception:
        return []


def merge_text_files(file1: Union[str, dict], file2: Union[str, dict]) -> dict:
    try:
        def normalize(f):
            if isinstance(f, str):
                return os.path.basename(f)
            if isinstance(f, dict):
                for v in f.values():
                    if isinstance(v, str):
                        return os.path.basename(v)
            return str(f)

        f1 = normalize(file1)
        f2 = normalize(file2)

        meta = {
            "filename": os.path.basename(f1),
            "filepath": os.path.join(get_user_upload_dir(), f1),
            "file2": os.path.basename(f2),
            "file2_path": os.path.join(get_user_upload_dir(), f2),
        }

        content1 = parse_file(f1)
        content2 = parse_file(f2)
        merged = (content1 + "\n" + content2).strip()

        return {
            "ok": True,
            **meta,
            "result": merged
        }

    except Exception as e:
        return {
            "ok": False,
            "filename": os.path.basename(str(file1)),
            "filepath": os.path.join(get_user_upload_dir(), os.path.basename(str(file1))),
            "error_type": type(e).__name__,
            "error_message": str(e),
            "result": None
        }


def sum_excel_column(filename: str, column_name: str) -> dict:
    try:
        meta = _meta(filename)
        path = meta["filepath"]

        if not os.path.exists(path):
            raise FileReadError(f"File does not exist: {filename}")

        df = pd.read_excel(path)

        # Determine column
        if column_name in df.columns:
            col = df[column_name]
        else:
            col_letter = column_name.strip().upper()
            if col_letter in list(string.ascii_uppercase):
                idx = list(string.ascii_uppercase).index(col_letter)
                col = df.iloc[:, idx]
            else:
                raise FileValidationError(
                    f"Column '{column_name}' not found in {filename}"
                )

        numeric = pd.to_numeric(col, errors="coerce").dropna()
        if numeric.empty:
            raise FileValidationError(
                f"Column '{column_name}' in {filename} contains no numeric data to sum."
            )

        return {
            "ok": True,
            **meta,
            "result": float(numeric.sum())
        }

    except Exception as e:
        return {
            "ok": False,
            **_meta(filename),
            "error_type": type(e).__name__,
            "error_message": str(e),
            "result": None
        }


# ---------------------------------------------------
# Phase 22/24 — **FAISS Auto-Create (Always 768-dim)**
# ---------------------------------------------------
def ensure_faiss_index():
    """
    Guarantee that Solomon has a functioning FAISS index.

    Behavior:
      ✓ If FAISS not installed → return None
      ✓ If index file missing → create 768-dim index
      ✓ If index corrupted → replace with new 768-dim index
      ✓ Always returns FAISS index object or None
    """
    if faiss is None:
        return None

    DIM = 768  # Phase 22+ universal embedding size

    # ---------------------------------------------------
    # CASE 1 — Index missing → auto-create new one
    # ---------------------------------------------------
    if not os.path.exists(FAISS_INDEX_PATH):
        try:
            index = faiss.IndexFlatL2(DIM)
            faiss.write_index(index, FAISS_INDEX_PATH)
            return index
        except Exception:
            return None

    # ---------------------------------------------------
    # CASE 2 — Index exists → try to load
    # ---------------------------------------------------
    try:
        index = faiss.read_index(FAISS_INDEX_PATH)

        # Ensure dimension matches 768
        if index.d != DIM:
            index = faiss.IndexFlatL2(DIM)
            faiss.write_index(index, FAISS_INDEX_PATH)

        return index

    except Exception:
        # Corrupted → replace it
        try:
            index = faiss.IndexFlatL2(DIM)
            faiss.write_index(index, FAISS_INDEX_PATH)
            return index
        except Exception:
            return None
