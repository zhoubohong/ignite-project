"""L2 Learning Memory — mastery CRUD, session stats, weak-point tracking."""
from __future__ import annotations

import uuid

import pytest

from app.memory.learning import LearningMemory


class TestMasteryCRUD:
    """CRUD operations on KnowledgeMastery."""

    @pytest.mark.asyncio
    async def test_get_mastery_nonexistent(self, test_db):
        lm = LearningMemory()
        m = await lm.get_mastery(test_db, uuid.uuid4(), "nonexistent")
        assert m is None

    @pytest.mark.asyncio
    async def test_get_or_create_creates(self, test_db):
        lm = LearningMemory()
        uid = uuid.uuid4()
        m = await lm.get_or_create_mastery(test_db, uid, "一元一次方程", "math")
        assert m is not None
        assert m.knowledge_point == "一元一次方程"
        assert m.subject == "math"
        assert m.state == "untouched"
        assert m.p_learned == 0.3
        assert m.p_guess == 0.1
        assert m.p_slip == 0.05
        assert m.p_transit == 0.2
        assert m.total_attempts == 0
        assert m.correct_count == 0

    @pytest.mark.asyncio
    async def test_get_or_create_returns_existing(self, test_db):
        lm = LearningMemory()
        uid = uuid.uuid4()
        m1 = await lm.get_or_create_mastery(test_db, uid, "勾股定理", "math")
        m2 = await lm.get_or_create_mastery(test_db, uid, "勾股定理", "math")
        assert m1.id == m2.id  # same object

    @pytest.mark.asyncio
    async def test_multiple_users_isolated(self, test_db):
        lm = LearningMemory()
        u1 = uuid.uuid4()
        u2 = uuid.uuid4()

        m1 = await lm.get_or_create_mastery(test_db, u1, "函数", "math")
        m2 = await lm.get_or_create_mastery(test_db, u2, "函数", "math")

        assert m1.id != m2.id
        assert m1.user_id == u1
        assert m2.user_id == u2


class TestSessionStats:
    """Aggregate session statistics."""

    @pytest.mark.asyncio
    async def test_empty_stats(self, test_db):
        lm = LearningMemory()
        uid = uuid.uuid4()
        stats = await lm.get_session_stats(test_db, uid, days=30)
        assert stats["total_sessions"] == 0
        assert stats["total_questions_answered"] == 0
        assert stats["recent_mistakes"] == 0
        assert stats["weak_points_top5"] == []

    @pytest.mark.asyncio
    async def test_mastery_distribution(self, test_db):
        lm = LearningMemory()
        uid = uuid.uuid4()

        # Create several mastery records in different states
        for i, (kp, st) in enumerate([
            ("知识点1", "untouched"),
            ("知识点2", "exposed"),
            ("知识点3", "practicing"),
            ("知识点4", "mastered"),
        ]):
            m = await lm.get_or_create_mastery(test_db, uid, kp, "math")
            m.state = st
            m.total_attempts = i + 1
        await test_db.flush()

        stats = await lm.get_session_stats(test_db, uid, days=30)
        dist = stats["mastery_distribution"]
        assert dist.get("untouched", 0) >= 1
        assert dist.get("exposed", 0) >= 1
        assert dist.get("practicing", 0) >= 1

    @pytest.mark.asyncio
    async def test_weak_points_sorted(self, test_db):
        lm = LearningMemory()
        uid = uuid.uuid4()

        # Create points with different P(L) values
        for i, (kp, p_l) in enumerate([
            ("弱项A", 0.2),
            ("弱项B", 0.4),
            ("正常", 0.8),
            ("最弱", 0.1),
        ]):
            m = await lm.get_or_create_mastery(test_db, uid, kp, "math")
            m.p_learned = p_l
            m.state = "practicing"
        await test_db.flush()

        stats = await lm.get_session_stats(test_db, uid, days=30)
        weak = stats["weak_points_top5"]
        assert len(weak) >= 3  # only points with p_learned < 0.7
        # Should be sorted asc by p_learned
        assert weak[0]["knowledge_point"] == "最弱"
        assert weak[0]["p_learned"] == 0.1


class TestBKTUpdates:
    """BKT update integration with database (complementing test_bkt.py)."""

    @pytest.mark.asyncio
    async def test_consecutive_correct_builds_mastery(self, test_db):
        lm = LearningMemory()
        uid = uuid.uuid4()

        for i in range(6):
            m = await lm.update_bkt(test_db, uid, "math", "二次函数", True)

        assert m.total_attempts == 6
        assert m.correct_count == 6
        assert m.p_learned > 0.7
        assert m.state in ("practicing", "mastered")

    @pytest.mark.asyncio
    async def test_alternating_answers_oscillates(self, test_db):
        lm = LearningMemory()
        uid = uuid.uuid4()

        results = [True, False, True, False, True]
        for correct in results:
            await lm.update_bkt(test_db, uid, "math", "概率", correct)

        m = await lm.get_mastery(test_db, uid, "概率")
        assert m is not None
        assert m.total_attempts == 5
        assert m.correct_count == 3
        # With alternating pattern True-False-True-False-True (3 correct, 2 wrong),
        # BKT converges relatively high but still not mastered
        assert 0.3 < m.p_learned < 0.95
