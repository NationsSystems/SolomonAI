# autonomy_persistence.py — Phase 8.4
# -------------------------------------------------------
# Handles durable storage of autonomous cognition cycles
# into MySQL using SQLAlchemy.
# -------------------------------------------------------

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from solomon_core.db import Base, SessionLocal, engine
from solomon_core.logger import get_logger

logger = get_logger("autonomy_persistence")


# -------------------------------------------------------
# ORM Model: AutonomyLog
# (defined here — NOT imported from models.py)
# -------------------------------------------------------
class AutonomyLog(Base):
    __tablename__ = "autonomy_log"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)

    run_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    task_text = Column(Text, nullable=True)
    intent = Column(String(128), nullable=False, default="autonomous_reflection")
    reasoning_source = Column(String(64), nullable=True)

    success = Column(Boolean, default=False, nullable=False)
    score = Column(Integer, default=3)
    summary = Column(Text, nullable=True)

    error_count = Column(Integer, default=0)

    # NEW: optional LLM planner metadata (for Phase 8.5)
    planner_meta = Column(Text, nullable=True)

    def __repr__(self):
        return (
            f"<AutonomyLog(id={self.id}, success={self.success}, "
            f"score={self.score}, reasoning='{self.reasoning_source}')>"
        )


# -------------------------------------------------------
# Ensure table exists (Phase 8.4 requirement)
# -------------------------------------------------------
try:
    Base.metadata.create_all(bind=engine)
    logger.info("[AutonomyLog] Table verified/created.")
except Exception as e:
    logger.error(f"[AutonomyLog] Failed to initialize table: {e}")


# -------------------------------------------------------
# Persistence Function
# -------------------------------------------------------
def log_autonomy_cycle(
    task_text: str,
    intent: str,
    reasoning_source: str,
    success: bool,
    summary: str,
    error_count: int,
    planner_meta: str = None,    # NEW optional metadata
):
    """Insert an autonomous cognition cycle into MySQL."""
    session = SessionLocal()
    try:
        row = AutonomyLog(
            task_text=task_text,
            intent=intent,
            reasoning_source=reasoning_source,
            success=success,
            summary=summary,
            error_count=error_count,
            planner_meta=planner_meta,
        )
        session.add(row)
        session.commit()
        logger.info("[AutonomyLog] Cycle persisted.")
    except Exception as e:
        session.rollback()
        logger.error(f"[AutonomyLog] Persist error: {e}")
    finally:
        session.close()
