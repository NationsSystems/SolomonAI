# memory_store.py — Phase 18 Knowledge Foundations Upgrade
# ---------------------------------------------------------
# Phase 18 Enhancements:
#   • Embedding normalization
#   • Knowledge Graph v1 scaffolding fields
#   • Planner confidence + reinforcement snapshot embedding
#   • Stable "memory envelope" structure
#   • Safe, typed memory logging
#   • Patched for full KG compatibility (Phase 18.4)
# ---------------------------------------------------------

import os
import json
from datetime import datetime, timedelta
from sqlalchemy import text
from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal, engine
from config import settings

from solomon_core.reinforcement_store import record_signal, adaptive_tune_weights

from solomon_core.solomon_tools.embedding_client import embed_text
import numpy as np

from solomon_core.reinforcement_store import get_reinforcement_snapshot

logger = get_logger("memory_store")


DATA_DIR = settings.DATA_DIR
MEMORY_JSON_PATH = os.path.join(DATA_DIR, "memory.json")


def init_db():
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS task_history (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    task_id VARCHAR(64),
                    user_id INT DEFAULT 0,
                    user VARCHAR(64) DEFAULT 'system',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    task_text TEXT,
                    intent VARCHAR(128),
                    entities_json JSON,
                    result_preview TEXT,
                    success BOOLEAN,
                    error_type VARCHAR(128),
                    duration_ms INT,
                    reasoning_source VARCHAR(128),
                    confidence FLOAT,
                    summary TEXT,
                    debug_trace TEXT
                )
            """))

            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS memory (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    task_text TEXT,
                    intent VARCHAR(128),
                    entities_json JSON,
                    result TEXT,
                    summary TEXT,
                    context_hint TEXT,
                    reasoning_source VARCHAR(128),
                    user_output TEXT,
                    success BOOLEAN,
                    embedding JSON,
                    kg_context_key VARCHAR(256) DEFAULT NULL,
                    kg_entities JSON DEFAULT NULL,
                    kg_tags JSON DEFAULT NULL,
                    planner_confidence FLOAT DEFAULT 0,
                    reinforcement_weight FLOAT DEFAULT 0
                )
            """))

        logger.info("[MySQL] memory_store: tables verified/updated for Phase 18")

    except Exception as e:
        logger.error(f"[init_db] Failed: {e}")


init_db()


def normalize_embedding(vec):
    try:
        arr = np.array(vec, dtype="float32")
        norm = np.linalg.norm(arr)
        if norm == 0:
            return arr.tolist()
        return (arr / norm).tolist()
    except Exception as e:
        logger.error(f"[normalize_embedding] Failed: {e}")
        return None


def log_task_start(task_id: str, user_id: str, task_text: str):
    try:
        if not user_id or str(user_id).lower() in ("anonymous", "none", "null"):
            user_id = 0
        else:
            try:
                user_id = int(user_id)
            except ValueError:
                user_id = 0

        db = SessionLocal()
        db.execute(text("""
            INSERT INTO task_history (
                task_id, user_id, user, created_at, task_text, success, reasoning_source
            ) VALUES (:task_id, :user_id, 'system', NOW(), :task_text, 0, 'pending')
        """), {"task_id": task_id, "user_id": user_id, "task_text": task_text})
        db.commit()

    except Exception as e:
        logger.error(f"[log_task_start] error: {e}")
    finally:
        db.close()


def log_task_result(task_id: str, intent: str, entities: dict,
                    result, success: bool, error_type: str,
                    duration_ms: int, reasoning_source: str = "deterministic",
                    confidence: float = None, summary: str = None,
                    debug_trace: str = None):
    try:
        db = SessionLocal()

        safe_entities = json.dumps(entities, ensure_ascii=False) if isinstance(entities, (dict, list)) else None
        safe_result = json.dumps(result, ensure_ascii=False) if isinstance(result, (dict, list)) else str(result)

        db.execute(text("""
            UPDATE task_history
            SET user='system',
                intent=:intent,
                entities_json=:entities_json,
                result_preview=:result_preview,
                success=:success,
                error_type=:error_type,
                duration_ms=:duration_ms,
                reasoning_source=:reasoning_source,
                confidence=:confidence,
                summary=:summary,
                debug_trace=:debug_trace,
                updated_at=NOW()
            WHERE task_id=:task_id
        """), {
            "intent": intent,
            "entities_json": safe_entities,
            "result_preview": safe_result[:250] if safe_result else None,
            "success": 1 if success else 0,
            "error_type": error_type,
            "duration_ms": duration_ms,
            "reasoning_source": reasoning_source,
            "confidence": confidence,
            "summary": summary,
            "debug_trace": debug_trace,
            "task_id": task_id
        })
        db.commit()

        try:
            record_signal(
                intent=intent or "unknown",
                reasoning_source=reasoning_source or "unspecified",
                success=success,
                confidence=confidence or 0.5,
                planner_confidence=None
            )
            if int(task_id[-1], 16) % 10 == 0:
                adaptive_tune_weights()

        except Exception as e:
            logger.error(f"[Reinforce] update failed after task {task_id}: {e}")

    except Exception as e:
        logger.error(f"[log_task_result] error: {e}")
    finally:
        db.close()


def make_memory_envelope(task_text, intent, entities, result,
                         summary, reasoning_source, user_output,
                         context_hint=None, success=True, planner_conf=None,
                         kg_entities=None, kg_tags=None, embedding=None):

    norm_emb = normalize_embedding(embedding) if embedding else None

    def safe_json(val):
        if isinstance(val, (dict, list)):
            try:
                return json.dumps(val, ensure_ascii=False)
            except Exception:
                return None
        return val

    return {
        "task_text": task_text,
        "intent": intent,
        "entities_json": safe_json(entities),
        "result": safe_json(result),
        "summary": summary,
        "context_hint": context_hint,
        "reasoning_source": reasoning_source,
        "user_output": safe_json(user_output),
        "success": 1 if success else 0,
        "embedding": json.dumps(norm_emb, ensure_ascii=False) if norm_emb else None,
        "kg_context_key": intent or "unknown",
        "kg_entities": safe_json(kg_entities),
        "kg_tags": safe_json(kg_tags),
        "planner_confidence": float(planner_conf or 0),
        "reinforcement_weight": 0.0,
    }


def log_memory_entry(task_text: str, intent: str, entities: dict,
                     result, summary: str, context_hint: str = None,
                     reasoning_source: str = None, user_output=None,
                     success: bool = True, embedding=None,
                     planner_confidence=None, kg_entities=None, kg_tags=None):

    try:
        envelope = make_memory_envelope(
            task_text=task_text,
            intent=intent,
            entities=entities,
            result=result,
            summary=summary,
            context_hint=context_hint,
            reasoning_source=reasoning_source,
            user_output=user_output,
            success=success,
            embedding=embedding,
            planner_conf=planner_confidence,
            kg_entities=kg_entities,
            kg_tags=kg_tags
        )

        try:
            rstate = get_reinforcement_snapshot()
            rkey = f"{intent}/{reasoning_source}"
            envelope["reinforcement_weight"] = rstate.get(rkey, {}).get("weight", 0.0)
        except Exception as e:
            logger.error(f"[memory_store] reinforcement snapshot fail: {e}")
            envelope["reinforcement_weight"] = 0.0

        db = SessionLocal()
        db.execute(text("""
            INSERT INTO memory (
                created_at, task_text, intent, entities_json, result, summary,
                context_hint, reasoning_source, user_output, success, embedding,
                kg_context_key, kg_entities, kg_tags,
                planner_confidence, reinforcement_weight
            )
            VALUES (NOW(), :task_text, :intent, :entities_json, :result, :summary,
                    :context_hint, :reasoning_source, :user_output, :success, :embedding,
                    :kg_context_key, :kg_entities, :kg_tags,
                    :planner_confidence, :reinforcement_weight)
        """), envelope)
        db.commit()

    except Exception as e:
        logger.error(f"[log_memory_entry] error: {e}")
    finally:
        db.close()


def get_recent_tasks(limit: int = 20):
    try:
        db = SessionLocal()
        result = db.execute(text(f"""
            SELECT task_id, user_id, user, created_at, task_text, intent,
                   result_preview, success, error_type, duration_ms,
                   reasoning_source, confidence, summary, debug_trace,
                   entities_json
            FROM task_history
            ORDER BY id DESC
            LIMIT {limit}
        """))
        rows = result.fetchall()

        clean_rows = []
        for row in rows:
            m = dict(row._mapping)
            m["skills"] = []
            m["files"] = []
            clean_rows.append(m)

        return clean_rows

    except Exception as e:
        logger.error(f"[get_recent_tasks] error: {e}")
        return []
    finally:
        db.close()


def get_recent_memory(limit: int = 50):
    try:
        db = SessionLocal()

        rows = db.execute(text(f"""
            SELECT created_at, task_text, intent, entities_json, result, summary,
                   context_hint, reasoning_source, user_output, success,
                   embedding, kg_context_key, kg_entities, kg_tags,
                   planner_confidence, reinforcement_weight
            FROM memory
            ORDER BY id DESC
            LIMIT {limit}
        """)).fetchall()

        return [dict(row._mapping) for row in rows]

    except Exception as e:
        logger.error(f"[get_recent_memory] error: {e}")
        return []
    finally:
        db.close()


def read_memory_entries(tag: str = None, limit: int = 20):
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "memory"))
    os.makedirs(base_dir, exist_ok=True)
    memory_file = os.path.join(base_dir, "memory.json")

    entries = []
    try:
        if os.path.exists(memory_file):
            with open(memory_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    for entry in reversed(data):
                        if tag and entry.get("tag") != tag:
                            continue
                        entries.append(entry)
                        if len(entries) >= limit:
                            break
        else:
            logger.debug("[memory_store] No legacy memory.json found.")
    except Exception as e:
        logger.error(f"[read_memory_entries] error: {e}")

    return entries


def extract_task_text_history(limit=200, days=30):
    try:
        db = SessionLocal()
        rows = db.execute(text("""
            SELECT task_text
            FROM task_history
            WHERE created_at >= NOW() - INTERVAL :days DAY
            ORDER BY id DESC
            LIMIT :limit
        """), {"days": days, "limit": limit}).fetchall()
        return [row[0] for row in rows if row[0]]
    except Exception as e:
        logger.error(f"[extract_task_text_history] error: {e}")
        return []
    finally:
        db.close()


def embed_task_history(limit=200, days=30):
    texts = extract_task_text_history(limit=limit, days=days)
    results = []
    for txt in texts:
        try:
            vec = embed_text(txt)
            if vec and len(vec) == 768:
                results.append((txt, np.array(vec, dtype="float32")))
        except Exception as e:
            logger.error(f"[embed_task_history] error: {e}")
    return results


def semantic_task_neighbors(text: str, top_k=5):
    try:
        vec_query = np.array(embed_text(text), dtype="float32")
        if len(vec_query) != 768:
            return []

        history = embed_task_history(limit=200, days=30)
        if not history:
            return []

        results = []
        for hist_text, hist_vec in history:
            denom = (np.linalg.norm(vec_query) * np.linalg.norm(hist_vec))
            sim = float(np.dot(vec_query, hist_vec) / denom) if denom != 0 else 0.0
            results.append((sim, hist_text))

        results.sort(reverse=True)
        return results[:top_k]

    except Exception as e:
        logger.error(f"[semantic_task_neighbors] error: {e}")
        return []


# ============================================================
# Phase 20 Step 5 — Unified Skill Difficulty Index (USDI)
# ============================================================

def extract_skill_history(limit=500, days=14):
    try:
        db = SessionLocal()
        rows = db.execute(text("""
            SELECT intent, success, error_type, reasoning_source, confidence,
                   created_at
            FROM task_history
            WHERE created_at >= NOW() - INTERVAL :days DAY
            ORDER BY id DESC
            LIMIT :limit
        """), {"days": days, "limit": limit}).fetchall()

        return [dict(row._mapping) for row in rows]

    except Exception as e:
        logger.error(f"[extract_skill_history] error: {e}")
        return []
    finally:
        db.close()


def get_skill_usage_windows(skill_name, days=14):
    skill_name = str(skill_name).lower().strip()
    rows = extract_skill_history(days=days)

    w10m = w1h = w24h = w7d = 0
    fail10m = fail1h = fail24h = 0
    now = datetime.utcnow()

    for r in rows:
        if not r["intent"] or r["intent"].lower() != skill_name:
            continue

        ts = r.get("created_at") or now
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except Exception:
                continue

        delta = now - ts

        if delta <= timedelta(minutes=10):
            w10m += 1
            if not r.get("success"):
                fail10m += 1

        if delta <= timedelta(hours=1):
            w1h += 1
            if not r.get("success"):
                fail1h += 1

        if delta <= timedelta(hours=24):
            w24h += 1
            if not r.get("success"):
                fail24h += 1

        if delta <= timedelta(days=7):
            w7d += 1

    return {
        "use": {"10m": w10m, "1h": w1h, "24h": w24h, "7d": w7d},
        "fail": {"10m": fail10m, "1h": fail1h, "24h": fail24h},
    }


def get_skill_difficulty_windows(skill_name):
    w = get_skill_usage_windows(skill_name)

    use = w["use"]
    fail = w["fail"]

    score = 0
    score += use["1h"] * 2
    score += use["24h"]
    score += fail["1h"] * 3
    score += fail["24h"] * 2

    return {
        "skill": skill_name,
        "usage_windows": use,
        "fail_windows": fail,
        "difficulty_score": score,
        "timestamp": datetime.utcnow().isoformat(),
    }
