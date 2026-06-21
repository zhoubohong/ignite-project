"""BKT (Bayesian Knowledge Tracing) — P(L) math + state machine transitions."""
from __future__ import annotations

import math
import uuid

import pytest
from sqlalchemy import text

from app.memory.learning import LearningMemory


class TestBKTVanilla:
    """Pure-math BKT tests — no database needed."""

    def test_correct_answer_increases_p_learned(self):
        """A correct answer should increase P(L) from the default 0.3."""
        # Default: P(L)=0.3, P(G)=0.1, P(S)=0.05, P(T)=0.2
        p_l = 0.3
        p_g = 0.1
        p_s = 0.05
        p_t = 0.2

        # P(correct) = P(L)*(1-P(S)) + (1-P(L))*P(G)
        # = 0.3*0.95 + 0.7*0.1 = 0.285 + 0.07 = 0.355
        # P(L|correct) = P(L)*(1-P(S)) / P(correct)
        # = 0.285 / 0.355 ≈ 0.8028
        # After learning: P(L) = 0.8028 + (1-0.8028)*0.2 = 0.8028 + 0.0394 = 0.8422
        p_l_new = (p_l * (1 - p_s)) / (p_l * (1 - p_s) + (1 - p_l) * p_g)
        p_l_new = p_l_new + (1 - p_l_new) * p_t

        assert p_l_new > p_l, "Correct answer should increase P(L)"
        assert 0.8 < p_l_new < 0.9, f"Expected ~0.84, got {p_l_new}"

    def test_incorrect_answer_decreases_p_learned(self):
        """An incorrect answer should decrease P(L) from default 0.3."""
        p_l = 0.3
        p_g = 0.1
        p_s = 0.05
        p_t = 0.2

        # P(incorrect) = P(L)*P(S) + (1-P(L))*(1-P(G))
        # = 0.3*0.05 + 0.7*0.9 = 0.015 + 0.63 = 0.645
        # P(L|incorrect) = P(L)*P(S) / P(incorrect)
        # = 0.015 / 0.645 ≈ 0.0233
        # After learning: P(L) = 0.0233 + (1-0.0233)*0.2 = 0.0233 + 0.1953 = 0.2186
        p_l_new = (p_l * p_s) / (p_l * p_s + (1 - p_l) * (1 - p_g))
        p_l_new = p_l_new + (1 - p_l_new) * p_t

        assert p_l_new < p_l, "Incorrect answer should decrease P(L)"
        assert 0.1 < p_l_new < 0.3, f"Expected ~0.22, got {p_l_new}"

    def test_consecutive_correct_approaches_one(self):
        """After many correct answers, P(L) should approach 1.0."""
        p_l = 0.3
        p_g = 0.1
        p_s = 0.05
        p_t = 0.2

        for i in range(20):
            p_l_new = (p_l * (1 - p_s)) / (p_l * (1 - p_s) + (1 - p_l) * p_g)
            p_l = p_l_new + (1 - p_l_new) * p_t

        assert p_l > 0.95, f"After 20 correct, P(L)={p_l} should be > 0.95"

    def test_consecutive_incorrect_approaches_zero(self):
        """After many wrong answers, P(L) should approach 0."""
        p_l = 0.5  # start higher
        p_g = 0.1
        p_s = 0.05
        p_t = 0.2

        for i in range(20):
            p_l_new = (p_l * p_s) / (p_l * p_s + (1 - p_l) * (1 - p_g))
            p_l = p_l_new + (1 - p_l_new) * p_t

        assert p_l < 0.3, f"After 20 incorrect, P(L)={p_l} should be < 0.3"


class TestBKTStateMachine:
    """State machine transitions: untouched → exposed → practicing → mastered."""

    @pytest.mark.asyncio
    async def test_untouched_to_exposed(self, test_db):
        """First interaction moves from untouched to exposed."""
        lm = LearningMemory()
        uid = uuid.uuid4()

        m = await lm.update_bkt(test_db, uid, "math", "一次函数", True)
        assert m.state == "exposed"
        assert m.total_attempts == 1
        assert m.correct_count == 1

    @pytest.mark.asyncio
    async def test_mastery_threshold(self, test_db):
        """P(L) > 0.95 should mark as mastered."""
        lm = LearningMemory()
        uid = uuid.uuid4()

        # Artificially set P(L) high
        m = await lm.get_or_create_mastery(test_db, uid, "二次函数", "math")
        m.p_learned = 0.96
        m.state = "practicing"
        m.total_attempts = 10
        m.correct_count = 9
        await test_db.flush()

        # One more correct answer should push to mastered
        m = await lm.update_bkt(test_db, uid, "math", "二次函数", True)
        assert m.state == "mastered"

    @pytest.mark.asyncio
    async def test_state_persistence(self, test_db):
        """State persists across multiple BKT updates."""
        lm = LearningMemory()
        uid = uuid.uuid4()

        # Update multiple times
        for _ in range(3):
            await lm.update_bkt(test_db, uid, "math", "勾股定理", True)

        # Fetch again
        m = await lm.get_mastery(test_db, uid, "勾股定理")
        assert m is not None
        assert m.state != "untouched"
        assert m.total_attempts == 3
        assert m.correct_count == 3

    @pytest.mark.asyncio
    async def test_multiple_knowledge_points_isolated(self, test_db):
        """Different knowledge points don't interfere."""
        lm = LearningMemory()
        uid = uuid.uuid4()

        # Math correct
        m1 = await lm.update_bkt(test_db, uid, "math", "一元一次方程", True)
        # Physics incorrect
        m2 = await lm.update_bkt(test_db, uid, "physics", "牛顿第一定律", False)

        assert m1.subject == "math"
        assert m2.subject == "physics"
        assert m1.knowledge_point != m2.knowledge_point
        # Math should have higher P(L) after correct
        assert m1.p_learned > m2.p_learned


class TestMistakeRecording:
    """Mistake book recording tests."""

    @pytest.mark.asyncio
    async def test_record_mistake(self, test_db):
        lm = LearningMemory()
        uid = uuid.uuid4()
        qid = uuid.uuid4()

        rec = await lm.record_mistake(
            test_db, uid, qid,
            student_answer="A",
            correct_answer="B",
            error_type="reading",
        )
        assert rec is not None
        assert rec.error_type == "reading"
        assert rec.student_answer == "A"
        assert rec.correct_answer == "B"
        assert rec.resolved is False

    @pytest.mark.asyncio
    async def test_mistake_counts_in_stats(self, test_db):
        lm = LearningMemory()
        uid = uuid.uuid4()

        for i in range(3):
            await lm.record_mistake(
                test_db, uid, uuid.uuid4(),
                student_answer="X",
                correct_answer="Y",
                error_type="concept",
            )
        await test_db.commit()

        stats = await lm.get_session_stats(test_db, uid, days=30)
        assert stats["recent_mistakes"] == 3
