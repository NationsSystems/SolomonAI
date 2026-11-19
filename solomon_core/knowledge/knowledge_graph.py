# knowledge_graph.py — Phase 18 Knowledge Graph Stability Upgrade (Option B4-A)
# -------------------------------------------------------------
# Phase 18 adds:
#   • Memory ingestion → KG
#   • KG context anchors (kg_context_key)
#   • Memory→Task→Skill linkage
#   • Reinforcement + planner_confidence weighting
#   • Embedding stability hooks (no direct FAISS here)
#   • Dedup + canonical IDs
#   • Option B4-A: hardened public APIs, stabilized schemas, cluster normalization
#   • Phase 18 Fix: JSON-safe KG export (tuple keys converted to strings)
# -------------------------------------------------------------

import datetime
from collections import defaultdict
import json

from solomon_core.logger import get_logger

logger = get_logger("knowledge_graph")

# =============================================================
# Core In-Memory Knowledge Graph Structure
# =============================================================
KG = {
    "tasks": {},
    "skills": {},
    "files": {},
    "errors": {},
    "users": {},
    "memory": {},
    "links": [],
    "weights": defaultdict(float),
}

# =============================================================
# JSON-safe helper
# =============================================================
def _json_safe_dict(d):
    """Convert dict with non-JSON keys (tuples, ints) to safe string-keyed dict."""
    safe = {}
    for k, v in d.items():
        if isinstance(k, tuple):
            k = "|".join(str(x) for x in k)
        else:
            k = str(k)
        safe[k] = v
    return safe


# =============================================================
# Utility: Normalize timestamps
# =============================================================
def _norm_ts(ts):
    if ts is None:
        return None
    if isinstance(ts, datetime.datetime):
        return ts.isoformat()
    return ts

# =============================================================
# Utility: Canonical ID builder
# =============================================================
def _canon(value):
    if value is None:
        return None
    return str(value).strip().lower()

# =============================================================
# Edge Creation
# =============================================================
def _add_edge(src_type, src_id, relation, dst_type, dst_id, weight=1.0):
    if not src_id or not dst_id:
        return

    src_id = _canon(src_id)
    dst_id = _canon(dst_id)
    relation = _canon(relation)

    edge = (src_type, src_id, relation, dst_type, dst_id)

    KG["links"].append(edge)
    KG["weights"][edge] += float(weight)

    logger.debug(f"[KG] edge {edge} weight={KG['weights'][edge]:.3f}")

# =============================================================
# Entity Extractors
# =============================================================
def extract_task_entities(task: dict):
    if not task:
        return {}
    return {
        "task_id": task.get("id") or task.get("task_id"),
        "intent": task.get("intent"),
        "raw_text": task.get("text") or task.get("task_text"),
        "timestamp": _norm_ts(task.get("timestamp")),
        "files": task.get("files", []),
        "skills": task.get("skills", []),
        "user": task.get("user"),
        "error": task.get("error"),
        "summary": task.get("summary")
    }

def extract_file_entities(task: dict):
    return [{"filename": _canon(f)} for f in task.get("files", [])]

def extract_skill_entities(task: dict):
    return [{"skill": _canon(s)} for s in task.get("skills", [])]

def extract_error_entities(task: dict):
    err = task.get("error")
    if not err:
        return None
    return {
        "message": str(err),
        "hash": _canon(hash(str(err))),
        "task_id": _canon(task.get("id")),
        "timestamp": _norm_ts(task.get("timestamp"))
    }

def extract_user_entities(task: dict):
    user = task.get("user")
    if not user:
        return None
    return {
        "user": _canon(user),
        "last_seen": _norm_ts(task.get("timestamp"))
    }

# =============================================================
# Memory Extraction (Phase 18)
# =============================================================
def extract_memory_entities(memory_row: dict):
    if not memory_row:
        return None

    mid = memory_row.get("kg_context_key") or memory_row.get("intent")
    mid = _canon(mid)

    return {
        "context_id": mid,
        "task_text": memory_row.get("task_text"),
        "intent": memory_row.get("intent"),
        "entities": memory_row.get("entities_json"),
        "summary": memory_row.get("summary"),
        "timestamp": _norm_ts(memory_row.get("created_at")),
        "planner_confidence": float(memory_row.get("planner_confidence") or 0),
        "reinforcement_weight": float(memory_row.get("reinforcement_weight") or 0),
        "kg_tags": memory_row.get("kg_tags"),
        "kg_entities": memory_row.get("kg_entities"),
    }

# =============================================================
# KG Update: Task
# =============================================================
def update_kg_from_task(task: dict):
    if not task:
        return

    ent = extract_task_entities(task)
    task_id = _canon(ent.get("task_id"))
    if not task_id:
        return

    KG["tasks"][task_id] = ent

    files = extract_file_entities(task)
    for f in files:
        fname = f["filename"]
        KG["files"][fname] = f
        _add_edge("task", task_id, "uses_file", "file", fname)

    skills = extract_skill_entities(task)
    for s in skills:
        sname = s["skill"]
        KG["skills"][sname] = s
        _add_edge("task", task_id, "invokes_skill", "skill", sname)

    error_ent = extract_error_entities(task)
    if error_ent:
        err_hash = error_ent["hash"]
        KG["errors"][err_hash] = error_ent
        _add_edge("task", task_id, "produced_error", "error", err_hash)

    user_ent = extract_user_entities(task)
    if user_ent:
        uname = user_ent["user"]
        KG["users"][uname] = user_ent
        _add_edge("task", task_id, "submitted_by", "user", uname)

    for s in skills:
        for f in files:
            _add_edge("skill", s["skill"], "touches_file", "file", f["filename"])

# =============================================================
# KG Update: Result
# =============================================================
def update_kg_from_result(result: dict):
    if not result:
        return
    task_id = _canon(result.get("task_id"))
    node = KG["tasks"].get(task_id)
    if not node:
        return
    node["result"] = result.get("result")
    node["summary"] = result.get("summary")

# =============================================================
# KG Update: Error
# =============================================================
def update_kg_from_error(error_info: dict):
    if not error_info:
        return
    err_hash = _canon(hash(str(error_info)))
    KG["errors"][err_hash] = {
        "message": str(error_info),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }

# =============================================================
# KG Update: Memory
# =============================================================
def update_kg_from_memory(memory_row: dict):
    ent = extract_memory_entities(memory_row)
    if not ent:
        return

    context_id = ent["context_id"]
    KG["memory"][context_id] = ent

    w_pc = ent.get("planner_confidence") or 0
    w_rf = ent.get("reinforcement_weight") or 0
    weight_total = 0.5 + (w_pc * 0.3) + (w_rf * 0.2)

    intent = _canon(ent.get("intent"))
    if intent:
        _add_edge("memory", context_id, "expresses_intent", "intent", intent, weight_total)

    # Tags
    tags = []
    try:
        if ent.get("kg_tags"):
            tags = json.loads(ent["kg_tags"]) if isinstance(ent["kg_tags"], str) else ent["kg_tags"]
    except Exception:
        tags = []
    for tag in tags:
        _add_edge("memory", context_id, "tagged_as", "tag", _canon(tag), weight_total)

    # Entities
    ents = []
    try:
        if ent.get("kg_entities"):
            ents = json.loads(ent["kg_entities"]) if isinstance(ent["kg_entities"], str) else ent["kg_entities"]
    except Exception:
        ents = []
    for obj in ents:
        if isinstance(obj, dict):
            for k, v in obj.items():
                _add_edge("memory", context_id, "mentions", k, _canon(v), weight_total)

# =============================================================
# Snapshot
# =============================================================
def get_kg_snapshot():
    try:
        return {
            "tasks": list(KG["tasks"].values()),
            "skills": list(KG["skills"].values()),
            "files": list(KG["files"].values()),
            "errors": list(KG["errors"].values()),
            "users": list(KG["users"].values()),
            "memory": list(KG["memory"].values()),
            "links": KG["links"][:],
            "weights": _json_safe_dict(KG["weights"]),
        }
    except Exception as e:
        logger.error(f"[KG] Snapshot error: {e}")
        return {}

# =============================================================
# Relationship Queries
# =============================================================
def get_related_files_for_skill(skill_name):
    skill_name = _canon(skill_name)
    return [
        e for e in KG["links"]
        if e[0] == "skill" and e[1] == skill_name and e[2] == "touches_file"
    ]

def get_related_skills_for_file(file_name):
    file_name = _canon(file_name)
    return [
        e for e in KG["links"]
        if e[3] == file_name and e[2] == "touches_file"
    ]

def get_errors_for_task(task_id):
    task_id = _canon(task_id)
    return [
        e for e in KG["links"]
        if e[0] == "task" and e[1] == task_id and e[2] == "produced_error"
    ]

def get_tasks_for_user(user):
    user = _canon(user)
    return [
        e for e in KG["links"]
        if e[3] == user and e[2] == "submitted_by"
    ]

def get_skill_usage(skill_name):
    skill_name = _canon(skill_name)
    return [
        e for e in KG["links"]
        if e[0] == "task" and e[2] == "invokes_skill" and e[3] == skill_name
    ]

# =============================================================
# Metrics + Clustering
# =============================================================
def compute_edge_statistics():
    stats = defaultdict(float)
    for edge, weight in KG["weights"].items():
        src, sid, rel, dst, did = edge
        stats[(src, rel, dst)] += weight
    return stats

def score_skill_importance():
    scores = defaultdict(float)
    for (src, sid, rel, dst, did), w in KG["weights"].items():
        if rel == "invokes_skill":
            scores[did] += w
        elif rel == "touches_file" and src == "skill":
            scores[sid] += w
    return scores

def compute_error_affinity():
    affinity = defaultdict(float)
    for (src, sid, rel, dst, did), w in KG["weights"].items():
        if rel == "produced_error":
            affinity[(sid, did)] += w
    return affinity

def detect_clusters():
    clusters = defaultdict(list)
    for (src, sid, rel, dst, did), w in KG["weights"].items():
        if w >= 2:
            key = f"{src}:{rel}:{dst}"
            clusters[key].append({
                "src_id": sid,
                "dst_id": did,
                "weight": w
            })
    return clusters

def generate_kg_insights():
    insights = []
    skill_scores = score_skill_importance()

    if skill_scores:
        try:
            top_skill = max(skill_scores, key=skill_scores.get)
            insights.append(
                f"Skill '{top_skill}' is highly used (score {skill_scores[top_skill]})."
            )
        except Exception:
            pass

    for k, v in compute_edge_statistics().items():
        src, rel, dst = k
        if v >= 5:
            insights.append(
                f"Heavy relationship: {src} --{rel}--> {dst} occurred {v} times."
            )

    clusters = detect_clusters()
    for cname, members in clusters.items():
        if len(members) >= 3:
            insights.append(
                f"Cluster '{cname}' has {len(members)} strong co-occurrences."
            )

    return insights

# =============================================================
# Public APIs (Phase 18 JSON-safe)
# =============================================================
def get_kg_insights():
    try:
        return generate_kg_insights()
    except Exception as e:
        logger.error(f"[KG] insights error: {e}")
        return []

def get_kg_scores():
    """Stable schema, JSON-safe."""
    try:
        return {
            "skill_importance": _json_safe_dict(score_skill_importance()),
            "error_affinity": _json_safe_dict(compute_error_affinity()),
            "edge_stats": _json_safe_dict(compute_edge_statistics()),
        }
    except Exception as e:
        logger.error(f"[KG] scores error: {e}")
        return {}

def get_kg_clusters():
    """Stable cluster schema (JSON-safe)."""
    try:
        raw = detect_clusters()
        return {str(k): v for k, v in raw.items()}
    except Exception as e:
        logger.error(f"[KG] cluster error: {e}")
        return {}

# =============================================================
# Strategic KG Export (JSON-safe)
# =============================================================
def get_strategic_kg_summary():
    try:
        return {
            "top_skills": sorted(
                _json_safe_dict(score_skill_importance()).items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "top_errors": sorted(
                _json_safe_dict(compute_error_affinity()).items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "clusters": get_kg_clusters(),
            "insights": generate_kg_insights(),
            "timestamp": datetime.datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"[KG] strategic summary error: {e}")
        return {}
