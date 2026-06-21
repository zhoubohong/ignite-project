"""Dashboard API — 学习统计、掌握度变化、错题分布."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Integer as SAInt, select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.memory.learning import learning_memory
from app.models.session import StudySession, AnswerRecord
from app.models.user import KnowledgeMastery, MistakeRecord

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats/{user_id}")
async def get_stats(
    user_id: str,
    days: int = Query(default=7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get learning stats for dashboard."""
    uid = uuid.UUID(user_id)
    stats = await learning_memory.get_session_stats(db, uid, days)
    return stats


@router.get("/mastery/{user_id}")
async def get_mastery_heatmap(
    user_id: str,
    subject: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Get mastery heatmap data for all knowledge points."""
    uid = uuid.UUID(user_id)
    stmt = select(KnowledgeMastery).where(KnowledgeMastery.user_id == uid)
    if subject:
        stmt = stmt.where(KnowledgeMastery.subject == subject)
    result = await db.execute(stmt)
    masteries = result.scalars().all()
    return [
        {
            "knowledge_point": m.knowledge_point,
            "subject": m.subject,
            "state": m.state,
            "p_learned": m.p_learned,
            "total_attempts": m.total_attempts,
            "correct_count": m.correct_count,
        }
        for m in masteries
    ]


@router.get("/mistakes/{user_id}")
async def get_mistake_distribution(
    user_id: str,
    days: int = Query(default=30, le=365),
    db: AsyncSession = Depends(get_db),
):
    """Get mistake distribution by error type."""
    uid = uuid.UUID(user_id)
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(MistakeRecord.error_type, func.count(MistakeRecord.id))
        .where(MistakeRecord.user_id == uid)
        .where(MistakeRecord.created_at >= cutoff)
        .group_by(MistakeRecord.error_type)
    )
    return {row[0] or "unknown": row[1] for row in result.all()}


@router.get("/daily/{user_id}")
async def get_daily_activity(
    user_id: str,
    days: int = Query(default=7, le=90),
    db: AsyncSession = Depends(get_db),
):
    """Get daily question count and correct rate."""
    uid = uuid.UUID(user_id)
    from datetime import datetime, timedelta
    cutoff = datetime.now() - timedelta(days=days)

    result = await db.execute(
        select(
            cast(AnswerRecord.created_at, Date).label("day"),
            func.count(AnswerRecord.id).label("total"),
            func.sum(AnswerRecord.is_correct.cast(SAInt)).label("correct"),
        )
        .where(AnswerRecord.user_id == uid)
        .where(AnswerRecord.created_at >= cutoff)
        .group_by("day")
        .order_by("day")
    )

    return [
        {
            "date": str(row[0]),
            "total": row[1],
            "correct": row[2] or 0,
            "accuracy": round((row[2] or 0) / row[1] * 100, 1) if row[1] else 0,
        }
        for row in result.all()
    ]
