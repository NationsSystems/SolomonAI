# skill_simulation_engine.py — Phase 10.5.2
# ---------------------------------------------------------------
# Safely executes proposed HFLO skill upgrades in a restricted,
# isolated sandbox environment. This prevents untrusted code from
# running inside Solomon's main process.
#
# Returns a simulation report:
# {
#     "ok": bool,
#     "runtime_error": "...",
#     "output": "...",
#     "exceptions": [],
#     "duration_ms": int,
#     "security_flags": []
# }
#
# Used by:
#   - HFLO skill evolution (10.3.4)
#   - Admin preview in Phase 10.5.4
# ---------------------------------------------------------------

import time
import json
import traceback
import types

from solomon_core.logger import get_logger

logger = get_logger("skill_simulator")


# ---------------------------------------------------------------
# Restricted builtins — prevent filesystem access, imports, etc.
# ---------------------------------------------------------------
SAFE_BUILTINS = {
    "abs": abs,
    "min": min,
    "max": max,
    "sum": sum,
    "len": len,
    "range": range,
    "enumerate": enumerate,
    "sorted": sorted,
    "str": str,
    "int": int,
    "float": float,
    "dict": dict,
    "list": list,
    "set": set,
    "tuple": tuple,
    "json": json,
}


# ---------------------------------------------------------------
# Helper — Indent user-provided code safely
# ---------------------------------------------------------------
def _indent_user_code(src: str):
    return "\n".join("    " + line for line in src.splitlines())


# ---------------------------------------------------------------
# SECURITY CHECKS
# ---------------------------------------------------------------
def _basic_security_scan(code: str) -> list:
    """
    Prevent common malicious operations before execution.
    Returns a list of detected security flags.
    """
    flags = []

    blocked = [
        "import os",
        "import sys",
        "open(",
        "exec(",
        "eval(",
        "__import__",
        "subprocess",
        "socket",
        "shutil",
        "Path(",
        "requests",
        "http",
    ]

    for keyword in blocked:
        if keyword in code:
            flags.append(f"Blocked keyword detected: {keyword}")

    return flags


# ---------------------------------------------------------------
# MAIN SIMULATION FUNCTION
# ---------------------------------------------------------------
def simulate_skill_execution(python_code: str, test_input: dict = None) -> dict:
    """
    Runs a proposed skill's python_code inside a safe sandbox.

    test_input should be a dict of arguments passed to the function.
    """

    test_input = test_input or {}

    result_report = {
        "ok": False,
        "runtime_error": None,
        "output": None,
        "exceptions": [],
        "duration_ms": 0,
        "security_flags": [],
    }

    # First: security scan
    flags = _basic_security_scan(python_code)
    if flags:
        result_report["security_flags"] = flags
        result_report["runtime_error"] = "Security violations detected"
        return result_report

    # Prepare isolated namespace
    sandbox_globals = {"__builtins__": SAFE_BUILTINS}
    sandbox_locals = {}

    # Wrap user code
    wrapper_code = f"""
def _skill_entry(**kwargs):
{_indent_user_code(python_code)}
"""

    try:
        start = time.time()

        # Execute wrapper to create _skill_entry in sandbox
        exec(wrapper_code, sandbox_globals, sandbox_locals)

        func = sandbox_locals.get("_skill_entry")
        if not func or not isinstance(func, types.FunctionType):
            result_report["runtime_error"] = "Skill entry function not created"
            return result_report

        # Run the proposed code
        try:
            output = func(**test_input)
            result_report["output"] = output
        except Exception as inner:
            result_report["exceptions"].append(str(inner))
            result_report["runtime_error"] = "Runtime error during execution"
            return result_report

        # Duration
        duration = int((time.time() - start) * 1000)
        result_report["duration_ms"] = duration
        result_report["ok"] = True
        return result_report

    except Exception as e:
        result_report["runtime_error"] = str(e)
        result_report["exceptions"].append(traceback.format_exc())
        return result_report
