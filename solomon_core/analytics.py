# solomon_core/analytics.py — Phase 7.4 (Adaptive Reinforcement Analytics)
# -------------------------------------------------------------------------
# Provides command-line and programmatic analytics of Solomon's task history
# and reinforcement trends.
# Can be run directly via:  python -m solomon_core.analytics

from sqlalchemy import func
from solomon_core.db import SessionLocal, TaskHistory
from tabulate import tabulate
from datetime import datetime


def get_metrics(limit: int = 100):
    """
    Returns dictionary summaries for recent tasks, overall statistics,
    and live reinforcement metrics for adaptive learning visualization.
    """
    # 🔁 Deferred import to avoid circular dependency
    from solomon_core.reinforcement_store import get_all_reinforcement

    session = SessionLocal()
    try:
        total = session.query(func.count(TaskHistory.id)).scalar() or 0
        successes = session.query(func.count(TaskHistory.id)).filter(TaskHistory.success == True).scalar() or 0
        failures = total - successes
        avg_duration = session.query(func.avg(TaskHistory.duration_ms)).scalar() or 0

        # Breakdown by reasoning source
        reasoning_counts = (
            session.query(TaskHistory.reasoning_source, func.count(TaskHistory.id))
            .group_by(TaskHistory.reasoning_source)
            .all()
        )

        # Breakdown by intent
        intent_counts = (
            session.query(TaskHistory.intent, func.count(TaskHistory.id))
            .group_by(TaskHistory.intent)
            .order_by(func.count(TaskHistory.id).desc())
            .limit(10)
            .all()
        )

        # Recent records
        recent = (
            session.query(
                TaskHistory.id,
                TaskHistory.user,
                TaskHistory.intent,
                TaskHistory.success,
                TaskHistory.reasoning_source,
                TaskHistory.duration_ms,
                TaskHistory.created_at,
            )
            .order_by(TaskHistory.id.desc())
            .limit(limit)
            .all()
        )

        # ✅ Phase 7.4: integrate reinforcement data
        reinforcement_data = get_all_reinforcement()
        avg_weight = 0.0
        top_positive, top_negative = None, None
        if reinforcement_data:
            weights = [r["success_weight"] for r in reinforcement_data if r.get("success_weight") is not None]
            avg_weight = round(sum(weights) / len(weights), 3) if weights else 0.0
            sorted_weights = sorted(reinforcement_data, key=lambda r: r["success_weight"], reverse=True)
            top_positive = sorted_weights[0] if sorted_weights else None
            top_negative = sorted_weights[-1] if sorted_weights else None

        return {
            "summary": {
                "total_tasks": total,
                "successes": successes,
                "failures": failures,
                "success_rate": round((successes / total * 100) if total else 0, 2),
                "avg_duration_ms": round(avg_duration, 2) if avg_duration else 0,
                "last_updated": datetime.utcnow().isoformat(),
            },
            "by_reasoning_source": {r[0] or "unknown": r[1] for r in reasoning_counts},
            "by_intent": {r[0] or "unknown": r[1] for r in intent_counts},
            "reinforcement": {
                "avg_weight": avg_weight,
                "top_positive": top_positive,
                "top_negative": top_negative,
                "count": len(reinforcement_data),
            },
            "recent": [
                {
                    "id": r.id,
                    "user": r.user,
                    "intent": r.intent,
                    "success": bool(r.success),
                    "reasoning_source": r.reasoning_source,
                    "duration_ms": r.duration_ms,
                    "created_at": r.created_at.isoformat(),
                }
                for r in recent
            ],
        }
    finally:
        session.close()


def print_metrics_table(data: dict):
    """Nicely formats analytics data in a terminal-friendly table."""
    summary = data.get("summary", {})
    print("\n=== Solomon Task Summary ===")
    print(tabulate(summary.items(), tablefmt="github"))

    print("\n=== Reasoning Source Breakdown ===")
    reasoning = data.get("by_reasoning_source", {})
    print(tabulate(reasoning.items(), headers=["Source", "Count"], tablefmt="github"))

    print("\n=== Top Intents ===")
    intents = data.get("by_intent", {})
    print(tabulate(intents.items(), headers=["Intent", "Count"], tablefmt="github"))

    # ✅ New: Reinforcement statistics summary
    reinforcement = data.get("reinforcement", {})
    if reinforcement:
        print("\n=== Reinforcement Summary ===")
        rows = [
            ("Average Weight", reinforcement.get("avg_weight")),
            ("Top Positive", f"{reinforcement.get('top_positive', {}).get('intent', '—')} "
                             f"({reinforcement.get('top_positive', {}).get('success_weight', '—')})"),
            ("Top Negative", f"{reinforcement.get('top_negative', {}).get('intent', '—')} "
                             f"({reinforcement.get('top_negative', {}).get('success_weight', '—')})"),
            ("Total Records", reinforcement.get("count", 0)),
        ]
        print(tabulate(rows, headers=["Metric", "Value"], tablefmt="github"))

    print("\n=== Recent Tasks ===")
    recent = data.get("recent", [])
    if not recent:
        print("(No recent tasks found.)")
        return
    table = [
        [
            r["id"],
            r["user"],
            r["intent"],
            "✅" if r["success"] else "❌",
            r["reasoning_source"],
            r["duration_ms"],
            r["created_at"].split("T")[0],
        ]
        for r in recent
    ]
    print(tabulate(table, headers=["ID", "User", "Intent", "OK", "Source", "ms", "Date"], tablefmt="github"))


def main():
    """Entry point for CLI usage."""
    data = get_metrics()
    print_metrics_table(data)


if __name__ == "__main__":
    main()
