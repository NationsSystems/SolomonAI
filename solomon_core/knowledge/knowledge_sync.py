# knowledge_sync.py — Phase 18 Memory–KG Synchronization Layer
# -------------------------------------------------------------
# Responsibilities:
#   • Sync recent memory entries into the Knowledge Graph
#   • Sync recent task history into the KG
#   • Provide unified sync entrypoints for:
#         - Autonomy loop
#         - Planner
#         - Admin diagnostics
#   • Keep KG consistent with reinforcement updates
#   • Lightweight, safe, non-blocking operations
#
# This module intentionally performs ZERO heavy computation.
# It simply reads, sanitizes, and hands off data to knowledge_graph.py
# -------------------------------------------------------------

from solomon_core.logger import get_logger
from solomon_core.knowledge.knowledge_graph import (
    update_kg_from_task,
    update_kg_from_memory,
)
from solomon_core.memory_store import (
    get_recent_tasks,
    get_recent_memory,
)

logger = get_logger("knowledge_sync")


# -------------------------------------------------------------
# Internal: safe iteration helper
# -------------------------------------------------------------
def _safe_iter(name, rows, fn):
    """Applies fn(row) to each row safely."""
    if not rows:
        logger.debug(f"[knowledge_sync] No rows to sync for {name}")
        return

    for r in rows:
        try:
            fn(r)
        except Exception as e:
            logger.error(f"[knowledge_sync] {name} sync error: {e}")


# -------------------------------------------------------------
# Sync memory entries → KG
# -------------------------------------------------------------
def sync_memory_into_kg(limit: int = 50):
    """
    Pulls the last N memory entries and ingests them into the KG.
    Uses the Phase 18 KG context anchors.
    """
    logger.debug("[knowledge_sync] Syncing memory → KG...")
    rows = get_recent_memory(limit=limit)
    _safe_iter("memory", rows, update_kg_from_memory)
    return {"ok": True, "count": len(rows)}


# -------------------------------------------------------------
# Sync task history → KG
# -------------------------------------------------------------
def sync_tasks_into_kg(limit: int = 50):
    """
    Pulls the last N task_history entries and ingests them into the KG.
    Phase 18 fix: also includes skills/files if present.
    """
    logger.debug("[knowledge_sync] Syncing tasks → KG...")
    rows = get_recent_tasks(limit=limit)

    tasks = []
    for row in rows:
        try:
            tasks.append({
                "id": row.get("task_id"),
                "task_id": row.get("task_id"),
                "task_text": row.get("task_text"),
                "intent": row.get("intent"),
                "text": row.get("task_text"),
                "timestamp": row.get("created_at"),
                "summary": row.get("summary"),
                "user": row.get("user"),

                # Phase 18: restore full linkage
                "skills": row.get("skills", []) or [],
                "files": row.get("files", []) or [],

                "error": row.get("error_type"),
            })
        except Exception as e:
            logger.error(f"[knowledge_sync] Task row conversion error: {e}")

    _safe_iter("task", tasks, update_kg_from_task)
    return {"ok": True, "count": len(tasks)}


# -------------------------------------------------------------
# Complete Synchronization: Memory + Tasks
# -------------------------------------------------------------
def sync_all(limit_memory: int = 50, limit_tasks: int = 50):
    """
    Full KG refresh pipeline:
       1. Load memory entries
       2. Load tasks
       3. Update KG
    Lightweight & fast — safe to call frequently.
    """

    logger.info("[knowledge_sync] Running full KG sync...")

    mem_res = sync_memory_into_kg(limit_memory)
    task_res = sync_tasks_into_kg(limit_tasks)

    logger.info(
        f"[knowledge_sync] Sync complete "
        f"(memory={mem_res['count']}, tasks={task_res['count']})"
    )

    return {
        "ok": True,
        "memory_synced": mem_res["count"],
        "tasks_synced": task_res["count"],
    }


# -------------------------------------------------------------
# NEW — Unified Sync Entrypoint (Phase 18)
# -------------------------------------------------------------
def sync_knowledge_graph(limit_memory: int = 50, limit_tasks: int = 50):
    """
    Phase 18 unified sync entrypoint — matches import path in:
        operational_cognition_controller
        diagnostics_bp
        planner bootstrap
        autonomy loop (optional)
    """
    try:
        return sync_all(limit_memory=limit_memory, limit_tasks=limit_tasks)
    except Exception as e:
        logger.error(f"[knowledge_sync] sync_knowledge_graph error: {e}")
        return {"ok": False, "error": str(e)}


# -------------------------------------------------------------
# Scheduler Hook — For Autonomy Loop (optional)
# -------------------------------------------------------------
def run_autonomy_sync():
    """
    Called within the autonomy loop once per cycle.
    Keeps KG aligned with recent memory & task logs.
    """
    try:
        return sync_all(limit_memory=20, limit_tasks=20)
    except Exception as e:
        logger.error(f"[knowledge_sync] Autonomy sync error: {e}")
        return {"ok": False, "error": str(e)}


__all__ = [
    "sync_memory_into_kg",
    "sync_tasks_into_kg",
    "sync_all",
    "sync_knowledge_graph",   # ← REQUIRED EXPORT
    "run_autonomy_sync",
]
