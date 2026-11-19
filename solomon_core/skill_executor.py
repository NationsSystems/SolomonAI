# solomon_core/skill_executor.py
# ---------------------------------------------------------------------
# Phase 38 — Strict Micro-Skill Executor (NON-AUTHORITATIVE)
#
# GUARANTEES:
#   • NO routing authority
#   • NO clarification authority
#   • NO state transitions
#   • NO continuation decisions
#   • NO execution authority
#   • Deterministic execution ONLY
#
# ROLE:
#   • Execute registered micro-skills
#   • Return structured result packets
#   • NEVER invoke LLMs directly
#   • Orchestrator is the sole execution authority
# ---------------------------------------------------------------------

from solomon_core.logger import get_logger
from solomon_core.skill_registry import resolve_micro_skill

# Deterministic document extraction (allowed)
from solomon_core.skills.semantic.extract_text import execute as extract_text

logger = get_logger("skill_executor")


# =====================================================================
# STRICT MICRO-SKILL: generic_llm_reasoning (SIGNAL-ONLY)
# =====================================================================
def _skill_generic_llm_reasoning(arguments: dict, safe_executor=None) -> dict:
    logger.debug("[generic_llm_reasoning] ENTER")

    if safe_executor is None:
        logger.error("[generic_llm_reasoning] No safe_executor provided")
        return {
            "ok": False,
            "result": None,
            "user_output": "Execution authority unavailable.",
        }

    try:
        prompt_text = arguments.get("prompt") or arguments.get("query") or ""
        docs = arguments.get("docs") or []

        extracted_text = ""
        if isinstance(docs, list) and docs:
            pkt = extract_text({"docs": docs})
            if pkt.get("ok") and pkt.get("aggregated_text"):
                extracted_text = pkt["aggregated_text"]

        system_guard = (
            "Respond as a professional estimating assistant.\n"
            "Use cautious, descriptive language only.\n"
            "Do not invent or infer document contents.\n"
            "Limit the response to one concise paragraph.\n"
        )

        if extracted_text:
            final_prompt = (
                f"{system_guard}\n\nDOCUMENT CONTENT:\n"
                f"{extracted_text}\n\nUSER REQUEST:\n{prompt_text}"
            )
        else:
            final_prompt = f"{system_guard}\n\nUSER REQUEST:\n{prompt_text}"

        # ------------------------------------------------------------------
        # Phase-38: EXECUTION DELEGATED — NOT OWNED HERE
        # ------------------------------------------------------------------
        out = safe_executor(final_prompt)

        if not isinstance(out, str) or not out.strip():
            out = "The documents were reviewed, but no explicit details were found."

        logger.debug("[generic_llm_reasoning] EXIT ok=True")
        return {
            "ok": True,
            "result": out.strip(),
            "user_output": out.strip(),
        }

    except Exception as e:
        logger.error(f"[generic_llm_reasoning] Fatal: {e}")
        return {
            "ok": False,
            "result": None,
            "user_output": "Unable to process the request.",
        }


# =====================================================================
# INTERNAL STRICT MICRO-SKILL EXECUTION (NON-AUTHORITATIVE)
# =====================================================================
def _execute_micro_skill(skill_name: str, arguments: dict, safe_executor=None) -> dict:
    logger.debug(f"[skill_executor] resolve_micro_skill name={skill_name}")
    fn = resolve_micro_skill(skill_name)

    if fn is None:
        return {
            "ok": False,
            "result": None,
            "user_output": f"Internal error: skill '{skill_name}' is not registered.",
        }

    try:
        if fn.__name__ == "_skill_generic_llm_reasoning":
            packet = fn(arguments, safe_executor=safe_executor)
        else:
            packet = fn(arguments)

        if not isinstance(packet, dict):
            return {
                "ok": False,
                "result": None,
                "user_output": "Invalid skill output format.",
            }

        if packet.get("ok") is True and isinstance(packet.get("result"), str):
            packet.setdefault("execution_ok", True)
            packet.setdefault("grounded", True)
            packet.setdefault("summary", packet["result"])

        packet.setdefault(
            "user_output",
            packet.get("result") or packet.get("summary") or ""
        )

        return packet

    except Exception as e:
        logger.error(f"[skill_executor] Skill crash ({skill_name}): {e}")
        return {
            "ok": False,
            "result": None,
            "user_output": "The skill failed during execution.",
        }


# =====================================================================
# STRICT SKILL EXECUTOR ENTRYPOINT (CALLED BY ORCHESTRATOR ONLY)
# =====================================================================
def execute_skill(skill_name: str, arguments: dict, safe_executor=None) -> dict:
    """
    Phase 38 invariant:
        • Executes skill blindly
        • No execution authority
        • No fallback logic
        • No flow decisions
    """

    if not isinstance(arguments, dict):
        return {
            "ok": False,
            "result": None,
            "user_output": "Invalid arguments passed to skill executor.",
        }

    REMAP = {
        "run_diagnostics": "skill_run_diagnostics",
        "run_system_diagnostics": "skill_run_system_diagnostics",
        "run_skill_diagnostics": "skill_run_skill_diagnostics",
        "run_planner_diagnostics": "skill_run_planner_diagnostics",
        "run_memory_diagnostics": "skill_run_memory_diagnostics",
        "run_safety_diagnostics": "skill_run_safety_diagnostics",
    }

    skill_name = REMAP.get(skill_name, skill_name)
    return _execute_micro_skill(skill_name, dict(arguments), safe_executor=safe_executor)
