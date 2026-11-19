# planner_sandbox.py — Phase 21 Strict Mode Stub
# --------------------------------------------------------------------
# Phase 21 removes the LLM planner entirely.
#
# BUT:
#   • HFLO, admin tooling, and older modules still expect a
#     planner sandbox entrypoint.
#   • Removing the sandbox would break compatibility.
#
# So this module becomes a NO-OP “strict mode” stub.
#
# Responsibilities:
#   • Run harmless validation
#   • NEVER import planner files (they no longer exist)
#   • Always return success unless explicitly told otherwise
#   • Keep HFLO + admin UI stable
# --------------------------------------------------------------------

from solomon_core.logger import get_logger

logger = get_logger("planner_sandbox")


# =====================================================================
# PUBLIC ENTRYPOINT — Phase 21 NO-OP Planner Sandbox
# =====================================================================
def run_planner_sandbox() -> tuple:
    """
    Phase 21:
        The LLM planner has been fully removed.
        This function now acts as a compatibility stub.
    """
    logger.info("[Sandbox] Phase 21 strict mode — planner sandbox bypassed.")
    return True, None


# =====================================================================
# Phase 21: Skill patch sandbox — still needed for HFLO skill upgrades
# =====================================================================
def sandbox_test_skill(skill_name: str, patch_code: str):
    """
    Phase 21:
        Skill code is still verified in a restricted sandbox.
        AST and execution safety checks remain.
    """

    ok, err = _execute_patch_in_sandbox(patch_code)

    if not ok:
        return {"valid": False, "reason": err}

    return {"valid": True, "reason": None, "skill": skill_name}


# =====================================================================
# Minimal hardened execution sandbox for skill code
# =====================================================================
import ast

FORBIDDEN_NODES = (
    ast.Import, ast.ImportFrom, ast.With,
    ast.AsyncFunctionDef, ast.Await,
    ast.While, ast.Try, ast.Raise,
    ast.Global, ast.Nonlocal,
)

FORBIDDEN_CALLS = {
    "exec", "eval", "open", "compile",
    "globals", "locals", "__import__",
}

def _validate_ast_safety(code: str):
    try:
        tree = ast.parse(code)
    except Exception as e:
        return False, f"AST parse error: {e}"

    for node in ast.walk(tree):
        if isinstance(node, FORBIDDEN_NODES):
            return False, f"Forbidden syntax: {type(node).__name__}"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in FORBIDDEN_CALLS:
                return False, f"Forbidden call: {node.func.id}"

    return True, None


def _execute_patch_in_sandbox(code: str):
    safe, reason = _validate_ast_safety(code)
    if not safe:
        return False, f"Unsafe code: {reason}"

    safe_globals = {
        "__builtins__": {
            "len": len, "range": range,
            "min": min, "max": max, "sum": sum,
        }
    }
    safe_locals = {}

    try:
        exec(code, safe_globals, safe_locals)
    except Exception as e:
        return False, f"Execution failed: {e}"

    funcs = [v for v in safe_locals.values() if callable(v)]

    if len(funcs) == 0:
        return False, "No callable defined"
    if len(funcs) > 1:
        return False, "Multiple functions defined; ambiguous patch"

    return True, None


# =====================================================================
# Legacy wrapper
# =====================================================================
def run_code_in_sandbox(code: str):
    ok, err = _execute_patch_in_sandbox(code)
    if not ok:
        return False, err
    return True, None


__all__ = [
    "run_planner_sandbox",
    "sandbox_test_skill",
    "run_code_in_sandbox",
]
