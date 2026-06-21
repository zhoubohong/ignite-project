"""L2 Learning Memory — BKT mastery tracking + mistake book + session stats."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import StudySession, AnswerRecord
from app.models.user import KnowledgeMastery, MistakeRecord


class LearningMemory:
    """L2: Cross-session learning state (BKT mastery, mistake book, answer trails)."""

    # BKT master state machine
    STATE_ORDER = {"untouched": 0, "exposed": 1, "practicing": 2, "mastered": 3}

    async def get_mastery(
        self, db: AsyncSession, user_id: uuid.UUID, knowledge_point: str
    ) -> KnowledgeMastery | None:
        result = await db.execute(
            select(KnowledgeMastery).where(
                KnowledgeMastery.user_id == user_id,
                KnowledgeMastery.knowledge_point == knowledge_point,
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create_mastery(
        self, db: AsyncSession, user_id: uuid.UUID, knowledge_point: str, subject: str
    ) -> KnowledgeMastery:
        mastery = await self.get_mastery(db, user_id, knowledge_point)
        if mastery is None:
            mastery = KnowledgeMastery(
                user_id=user_id,
                subject=subject,
                knowledge_point=knowledge_point,
            )
            db.add(mastery)
            await db.flush()
        return mastery

    async def update_bkt(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        subject: str,
        knowledge_point: str,
        is_correct: bool,
    ) -> KnowledgeMastery:
        """BKT update: recalculate P(L) and state after an answer."""
        m = await self.get_or_create_mastery(db, user_id, knowledge_point, subject)

        p_l = m.p_learned
        p_g = m.p_guess
        p_s = m.p_slip
        p_t = m.p_transit

        if is_correct:
            # P(correct) = P(L)*(1-P(S)) + (1-P(L))*P(G)
            p_l_new = (p_l * (1 - p_s)) / (p_l * (1 - p_s) + (1 - p_l) * p_g)
        else:
            # P(incorrect) = P(L)*P(S) / (P(L)*P(S) + (1-P(L))*(1-P(G)))
            p_l_new = (p_l * p_s) / (p_l * p_s + (1 - p_l) * (1 - p_g))

        # Apply learning transition
        p_l_new = p_l_new + (1 - p_l_new) * p_t

        m.p_learned = round(p_l_new, 4)
        m.total_attempts += 1
        if is_correct:
            m.correct_count += 1

        # State machine transition
        m.state = self._compute_state(m)
        m.last_updated = datetime.now()

        await db.flush()
        return m

    def _compute_state(self, m: KnowledgeMastery) -> str:
        """Determine mastery state from BKT P(L) and attempt history."""
        if m.state == "untouched" and m.total_attempts > 0:
            return "exposed"
        if m.p_learned > 0.95:
            return "mastered"
        if m.total_attempts >= 3:
            # Check for degradation: 3 consecutive errors
            return "practicing"
        if m.state == "untouched":
            return "untouched"
        if m.total_attempts > 0:
            return "practicing" if m.state != "mastered" else m.state
        return m.state

    async def record_mistake(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        question_id: uuid.UUID,
        student_answer: str,
        correct_answer: str,
        error_type: str = "",
    ) -> MistakeRecord:
        rec = MistakeRecord(
            user_id=user_id,
            question_id=question_id,
            student_answer=student_answer,
            correct_answer=correct_answer,
            error_type=error_type,
        )
        db.add(rec)
        await db.flush()
        return rec

    async def get_session_stats(
        self, db: AsyncSession, user_id: uuid.UUID, days: int = 7
    ) -> dict:
        """Aggregate learning stats for dashboard."""
        now = datetime.now()
        from datetime import timedelta
        cutoff = now - timedelta(days=days)

        # Sessions in period
        result = await db.execute(
            select(func.count(StudySession.id), func.sum(StudySession.questions_answered))
            .where(StudySession.user_id == user_id)
            .where(StudySession.started_at >= cutoff)
        )
        row = result.one()
        total_sessions = row[0] or 0
        total_answered = row[1] or 0

        # Mastery distribution
        result = await db.execute(
            select(KnowledgeMastery.state, func.count(KnowledgeMastery.id))
            .where(KnowledgeMastery.user_id == user_id)
            .group_by(KnowledgeMastery.state)
        )
        mastery_dist = {row[0]: row[1] for row in result.all()}

        # Recent mistakes
        result = await db.execute(
            select(func.count(MistakeRecord.id))
            .where(MistakeRecord.user_id == user_id)
            .where(MistakeRecord.created_at >= cutoff)
        )
        recent_mistakes = result.scalar() or 0

        # Weak points (practicing or exposed with low P(L))
        result = await db.execute(
            select(KnowledgeMastery.knowledge_point, KnowledgeMastery.p_learned, KnowledgeMastery.subject)
            .where(KnowledgeMastery.user_id == user_id)
            .where(KnowledgeMastery.p_learned < 0.7)
            .order_by(KnowledgeMastery.p_learned.asc())
            .limit(5)
        )
        weak_points = [
            {"knowledge_point": r[0], "p_learned": r[1], "subject": r[2]}
            for r in result.all()
        ]

        return {
            "period_days": days,
            "total_sessions": total_sessions,
            "total_questions_answered": total_answered,
            "mastery_distribution": mastery_dist,
            "recent_mistakes": recent_mistakes,
            "weak_points_top5": weak_points,
        }


learning_memory = LearningMemory()
