# file_grounding.py — Phase 5 / Step 1
# Structured "file grounding" layer for Solomon.
#
# Purpose:
#   Given a file path (PDF, DOCX, TXT, CSV, XLSX), extract lightweight,
#   deterministic, *verifiable* facts the LLM can be anchored to.
#   This version guarantees extract_file_facts() always returns a structured dict.

from __future__ import annotations

import os
import re
import io
import json
import csv
import hashlib
import datetime as _dt
from typing import Any, Dict, List, Optional, Tuple

# Optional parsers
try:
    import PyPDF2  # type: ignore
except Exception:
    PyPDF2 = None

try:
    import openpyxl  # type: ignore
except Exception:
    openpyxl = None

# Prefer Solomon's own MIME detector if available
try:
    from solomon_core.solomon_tools.fileops import detect_mime_type
except Exception:
    import mimetypes

    def detect_mime_type(path: str) -> str:
        mt, _ = mimetypes.guess_type(path)
        return mt or "application/octet-stream"


# -------------------------
# Paths & cache management
# -------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache", "grounding")
os.makedirs(CACHE_DIR, exist_ok=True)

UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)


# -------------------------
# Utility helpers
# -------------------------
def _sha256_head(path: str, bytes_n: int = 1_000_000) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(bytes_n))
    return h.hexdigest()


def file_fingerprint(path: str) -> str:
    st = os.stat(path)
    head = _sha256_head(path)
    raw = f"{os.path.basename(path)}|{st.st_size}|{int(st.st_mtime)}|{head}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _clean_text(s: str) -> str:
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\r?\n\s*\r?\n", "\n\n", s)
    s = s.replace("\x00", "")
    return s.strip()


def _truncate_list(items: List[Any], max_items: int = 6) -> List[Any]:
    return items if len(items) <= max_items else items[:max_items]


def _as_float_safe(x: Any) -> Optional[float]:
    try:
        return float(str(x).replace(",", ""))
    except Exception:
        return None


# -------------------------
# Extractors (format-specific)
# -------------------------
def _read_txt(path: str) -> str:
    for enc in ["utf-8", "utf-16", "cp1252", "latin-1"]:
        try:
            with open(path, "r", encoding=enc, errors="ignore") as f:
                return f.read()
        except Exception:
            continue
    with open(path, "rb") as f:
        return f.read().decode("utf-8", errors="ignore")


def _read_pdf_text(path: str) -> str:
    if PyPDF2 is None:
        return ""
    text_parts: List[str] = []
    try:
        with open(path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages[:25]:
                try:
                    text_parts.append(page.extract_text() or "")
                except Exception:
                    continue
    except Exception:
        return ""
    return "\n".join(text_parts)


def _read_csv_table_sample(path: str, max_rows: int = 50) -> List[List[Any]]:
    out: List[List[Any]] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            r = csv.reader(f)
            for i, row in enumerate(r):
                out.append(row)
                if i + 1 >= max_rows:
                    break
    except Exception:
        pass
    return out


def _read_xlsx_table_sample(path: str, max_rows: int = 50) -> List[List[Any]]:
    if openpyxl is None:
        return []
    try:
        wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
        ws = wb.active
        out: List[List[Any]] = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            out.append([cell for cell in row])
            if i + 1 >= max_rows:
                break
        return out
    except Exception:
        return []


# -------------------------
# Lightweight fact extraction
# -------------------------
_NUM_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[-+]?\d[\d,]*(?:\.\d+)?)", re.VERBOSE
)
_PERCENT_RE = re.compile(r"\b(-?\d+(?:\.\d+)?)\s?%")
_CURRENCY_RE = re.compile(r"(\$|USD|EUR|£|¥)\s?(-?\d{1,3}(?:,\d{3})*(?:\.\d+)?)")
_DATE_RE = re.compile(
    r"\b(?:(?:\d{4}[-/]\d{1,2}[-/]\d{1,2})|(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4})|(?:[A-Za-z]{3,9}\s+\d{1,2},\s+\d{4}))\b"
)
_URL_RE = re.compile(r"https?://[^\s)]+")
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _extract_numbers(text: str) -> Dict[str, Any]:
    numbers = [m.group(0) for m in _NUM_RE.finditer(text)]
    percents = [{"value": _as_float_safe(v), "raw": m.group(0)} for m in _PERCENT_RE.finditer(text) for v in [m.group(1)]]
    currency = [{"symbol": m.group(1), "amount": _as_float_safe(m.group(2)), "raw": m.group(0)} for m in _CURRENCY_RE.finditer(text)]
    floats = [_as_float_safe(n) for n in numbers if _as_float_safe(n) is not None]
    return {
        "count": len(numbers),
        "examples": _truncate_list(numbers, 8),
        "min": min(floats) if floats else None,
        "max": max(floats) if floats else None,
        "percents": _truncate_list(percents, 8),
        "currency": _truncate_list(currency, 8),
    }


def _extract_dates_entities(text: str) -> Dict[str, Any]:
    dates = list(set(_DATE_RE.findall(text)))
    urls = list(set(_URL_RE.findall(text)))
    emails = list(set(_EMAIL_RE.findall(text)))
    return {
        "dates_examples": _truncate_list(dates, 8),
        "urls_examples": _truncate_list(urls, 8),
        "emails_examples": _truncate_list(emails, 8),
    }


def _extract_headings(text: str) -> List[str]:
    headings: List[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) > 160:
            continue
        if re.match(r"^(?:[A-Z][A-Za-z0-9\-]+\s+){1,8}[A-Z][A-Za-z0-9\-]+$", line):
            headings.append(line)
        elif re.match(r"^(?:section|chapter|appendix)\s+\d+[:.\-]?\s", line, flags=re.I):
            headings.append(line)
        elif re.match(r"^[A-Z0-9][A-Z0-9 \-]{3,}$", line) and not re.search(r"[a-z]{3,}", line):
            headings.append(line)
        if len(headings) >= 10:
            break
    return headings


# -------------------------
# Public API
# -------------------------
def cache_key_for_path(path: str) -> str:
    return file_fingerprint(path)


def cache_path_for_key(key: str) -> str:
    return os.path.join(CACHE_DIR, f"{key}.json")


def load_grounding_from_cache(path: str) -> Optional[Dict[str, Any]]:
    key = cache_key_for_path(path)
    cp = cache_path_for_key(key)
    if os.path.exists(cp):
        try:
            with open(cp, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["_cache_hit"] = True
            return data
        except Exception:
            pass
    return None


def save_grounding_to_cache(path: str, grounding: Dict[str, Any]) -> None:
    try:
        key = cache_key_for_path(path)
        cp = cache_path_for_key(key)
        with open(cp, "w", encoding="utf-8") as f:
            json.dump(grounding, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def extract_file_facts(path: str) -> Dict[str, Any]:
    """
    Always returns a structured dictionary, even if the file cannot be read.
    Prevents NoneType errors for downstream .get() access.
    """
    try:
        candidate_path = path
        if not os.path.isabs(candidate_path) and not os.path.exists(candidate_path):
            possible_path = os.path.join(UPLOADS_DIR, os.path.basename(candidate_path))
            if os.path.exists(possible_path):
                candidate_path = possible_path
            else:
                lower_files = {f.lower(): f for f in os.listdir(UPLOADS_DIR)}
                if os.path.basename(candidate_path).lower() in lower_files:
                    candidate_path = os.path.join(UPLOADS_DIR, lower_files[os.path.basename(candidate_path).lower()])

        if not os.path.exists(candidate_path):
            return {"ok": False, "error": f"File does not exist: {os.path.basename(path)}"}

        cached = load_grounding_from_cache(candidate_path)
        if cached:
            return cached

        mime = detect_mime_type(candidate_path)
        name = os.path.basename(candidate_path)
        st = os.stat(candidate_path)
        fkey = file_fingerprint(candidate_path)

        text, table_sample = "", []

        if mime in ("text/plain", "application/json"):
            text = _read_txt(candidate_path)
        elif mime == "application/pdf":
            text = _read_pdf_text(candidate_path)
        elif mime in ("text/csv", "application/csv"):
            table_sample = _read_csv_table_sample(candidate_path)
        elif mime in ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",):
            table_sample = _read_xlsx_table_sample(candidate_path)
        elif mime.startswith("text/"):
            text = _read_txt(candidate_path)

        text_clean = _clean_text(text) if text else ""
        text_excerpt = text_clean[:2000] if text_clean else ""

        numeric = _extract_numbers(text_clean) if text_clean else {"count": 0}
        entities = _extract_dates_entities(text_clean) if text_clean else {}
        headings = _extract_headings(text_clean) if text_clean else []

        facts: Dict[str, Any] = {
            "ok": True,
            "filename": name,
            "path": candidate_path,
            "mime": mime,
            "fingerprint": fkey,
            "size_bytes": st.st_size,
            "modified_ts": int(st.st_mtime),
            "modified_iso": _dt.datetime.fromtimestamp(st.st_mtime).isoformat(),
            "text_excerpt": text_excerpt,
            "numeric": numeric,
            "entities": entities,
            "headings": headings,
            "table_sample": _truncate_list(table_sample, 50) if table_sample else [],
            "_cache_hit": False,
        }

        save_grounding_to_cache(candidate_path, facts)
        return facts

    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "filename": os.path.basename(path),
            "path": path,
            "mime": None,
            "text_excerpt": "",
            "numeric": {"count": 0},
            "entities": {},
            "headings": [],
            "table_sample": [],
            "_cache_hit": False,
        }


def compare_files_facts(path_a: str, path_b: str) -> Dict[str, Any]:
    fa = extract_file_facts(path_a)
    fb = extract_file_facts(path_b)

    if not fa.get("ok") or not fb.get("ok"):
        return {"ok": False, "error": "Failed to ground one or both files."}

    def minmax(d: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
        return d.get("numeric", {}).get("min"), d.get("numeric", {}).get("max")

    a_min, a_max = minmax(fa)
    b_min, b_max = minmax(fb)

    return {
        "ok": True,
        "a": {"filename": fa["filename"], "mime": fa["mime"], "numbers_count": fa["numeric"]["count"]},
        "b": {"filename": fb["filename"], "mime": fb["mime"], "numbers_count": fb["numeric"]["count"]},
        "delta": {"numbers_count_diff": fa["numeric"]["count"] - fb["numeric"]["count"]},
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="File grounding probe")
    parser.add_argument("path", help="Path to a file")
    args = parser.parse_args()
    print(json.dumps(extract_file_facts(args.path), indent=2, ensure_ascii=False))


# --- Backward compatibility alias ---
extract_file_context = extract_file_facts
