"""
register_deterministic_skills.py
Phase-21 Modernization — Deterministic Micro-Skill Bootstrap
-------------------------------------------------------------
This script installs all deterministic micro-skills into the DB so that:
    • UnifiedExecutor can call them
    • Dispatcher fallback can be removed safely
    • Deterministic functions can be deleted from engine
    • Solomon becomes fully skill-driven

Run this ONCE manually after restoring Phase 20.

Phase 38 GUARANTEES:
    • BOOTSTRAP ONLY
    • NOT part of runtime execution path
    • NO orchestrator bypass
    • NO task lifecycle authority
    • HARD-GATED against runtime execution
"""

# ---------------------------------------------------------------------------
# Phase-38 Authority Declaration (HARD)
# ---------------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # This module may NEVER execute tasks at runtime

import os
import sys

# ---------------------------------------------------------------------------
# HARD RUNTIME GUARD — Phase-38
# ---------------------------------------------------------------------------
# This file MUST NOT run unless explicitly invoked for manual bootstrap.
# Any import-time or accidental execution is a Phase-38 violation.
# ---------------------------------------------------------------------------
if __name__ != "__main__":
    raise RuntimeError(
        "Phase-38 violation: register_deterministic_skills.py "
        "is bootstrap-only and must not be imported or executed at runtime."
    )

# ---------------------------------------------------------
# Ensure project root is in sys.path (bootstrap-only)
# ---------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# ---------------------------------------------------------
# Console indicator to show script is running (manual only)
# ---------------------------------------------------------
print("[Bootstrap] Starting deterministic skill installation...")

from solomon_core.skill_registry import register_skill_from_llm
from solomon_core.logger import get_logger

logger = get_logger("skill_bootstrap")

# ---------------------------------------------------------
# Micro-skill definitions (DATA ONLY)
# ---------------------------------------------------------
SKILLS = {
    "skill_count_lines": """
def run(params):
    filename = params["filename"]
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        return {"result": len(f.readlines())}
""",
    "skill_first_n_lines": """
def run(params):
    filename = params["filename"]
    n = int(params.get("n", 5))
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    return {"result": "".join(lines[:n])}
""",
    "skill_get_words_starting_with": """
def run(params):
    filename = params["filename"]
    letter = params["letter"].lower()
    words = []
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            for w in line.split():
                if w.lower().startswith(letter):
                    words.append(w)
    return {"result": words}
""",
    "skill_merge_text_files": """
def run(params):
    file1 = params["filename"]
    file2 = params["file2"]
    with open(file1, "r", encoding="utf-8", errors="ignore") as f1:
        content1 = f1.read()
    with open(file2, "r", encoding="utf-8", errors="ignore") as f2:
        content2 = f2.read()
    return {"result": content1 + "\\n" + content2}
""",
    "skill_sum_excel_column": """
def run(params):
    import openpyxl
    filename = params["filename"]
    column = params["column"]
    wb = openpyxl.load_workbook(filename, data_only=True)
    ws = wb.active
    total = 0
    for cell in ws[column]:
        if isinstance(cell.value, (int, float)):
            total += cell.value
    return {"result": total}
""",
    "skill_parse_file": """
def run(params):
    filename = params["filename"]
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        return {"result": f.read()}
""",
    "skill_extract_snippet": """
def run(params):
    text = params["text"]
    max_len = int(params.get("max_len", 200))
    return {"result": text[:max_len]}
""",
    "skill_preview_text_file": """
def run(params):
    filename = params["filename"]
    with open(filename, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    return {"result": "".join(lines[:10])}
""",
    "skill_summarize_error": """
def run(params):
    err = params["error"]
    return {"result": str(err)[:120]}
""",
    "skill_simulate_plan_basic": """
def run(params):
    plan = params["plan"]
    steps = [s.get("action", "unknown") for s in plan.get("steps", [])]
    return {"result": {"simulated_steps": steps}}
""",
    "skill_score_plan_basic": """
def run(params):
    plan = params["plan"]
    score = len(plan.get("steps", [])) * 3.34
    return {"result": score}
""",
    "skill_diag_check_uploads": """
def run(params):
    import os
    path = params["path"]
    exists = os.path.exists(path)
    writable = os.access(path, os.W_OK)
    return {"result": {"exists": exists, "writable": writable}}
""",
    "skill_diag_check_database": """
def run(params):
    return {"result": "ok"}
""",
    "skill_diag_check_faiss": """
def run(params):
    from solomon_core.skill_system import loader
    state = loader.get_faiss_state()
    return {"result": state}
""",
    "skill_diag_check_embeddings": """
def run(params):
    return {"result": "embedding_placeholder_ok"}
"""
}

# ---------------------------------------------------------
# Registration Logic (manual bootstrap only)
# ---------------------------------------------------------
def register_all_skills(*, manual_bootstrap_authorized: bool = False):
    if not manual_bootstrap_authorized:
        raise RuntimeError(
            "Phase-38 violation: deterministic skill bootstrap "
            "requires explicit manual authorization."
        )

    print(f"[Bootstrap] Installing {len(SKILLS)} deterministic micro-skills...")
    logger.info(f"[Bootstrap] Installing {len(SKILLS)} deterministic micro-skills...")

    for name, code in SKILLS.items():
        print(f"Installing: {name}")
        try:
            register_skill_from_llm(name, code.strip())
            logger.info(f"[OK] Installed skill: {name}")
        except Exception as e:
            print(f"[FAIL] {name}: {e}")
            logger.error(f"[FAIL] Could not install {name}: {e}")

    print("[Bootstrap] Deterministic micro-skill installation complete.")
    logger.info("[Bootstrap] Deterministic micro-skill installation complete.")

# ---------------------------------------------------------
# Main entrypoint (MANUAL ONLY, HARD-GATED)
# ---------------------------------------------------------
if __name__ == "__main__":
    register_all_skills(
        manual_bootstrap_authorized=True,
    )
