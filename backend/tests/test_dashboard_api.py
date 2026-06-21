"""Dashboard API — stats, mastery heatmap, mistake distribution, daily activity."""
from __future__ import annotations

import uuid

import pytest

from app.models.user import User, KnowledgeMastery


class TestDashboardStats:
    """GET /api/dashboard/stats/{user_id}."""

    @pytest.mark.asyncio
    async def test_empty_stats_for_new_user(self, async_client):
        uid = str(uuid.uuid4())
        resp = await async_client.get(f"/api/dashboard/stats/{uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sessions"] == 0
        assert data["total_questions_answered"] == 0
        assert data["recent_mistakes"] == 0

    @pytest.mark.asyncio
    async def test_stats_custom_days(self, async_client):
        uid = str(uuid.uuid4())
        resp = await async_client.get(f"/api/dashboard/stats/{uid}", params={"days": 14})
        assert resp.status_code == 200
        data = resp.json()
        assert data["period_days"] == 14

    @pytest.mark.asyncio
    async def test_stats_with_data(self, async_client, test_db):
        """Seed mastery records and verify stats."""
        uid = uuid.uuid4()

        # Create user via ORM
        user = User(id=uid, username=f"testdb_{uid.hex[:8]}", display_name="Test", role="student", grade="8")
        test_db.add(user)

        # Create mastery records via ORM
        for i in range(3):
            km = KnowledgeMastery(
                user_id=uid,
                subject="math",
                knowledge_point=f"知识{i}",
                state="practicing",
                p_learned=0.3 + i * 0.1,
                total_attempts=i + 2,
            )
            test_db.add(km)
        await test_db.commit()

        resp = await async_client.get(f"/api/dashboard/stats/{uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert "mastery_distribution" in data


class TestMasteryHeatmap:
    """GET /api/dashboard/mastery/{user_id}."""

    @pytest.mark.asyncio
    async def test_empty_mastery(self, async_client):
        uid = str(uuid.uuid4())
        resp = await async_client.get(f"/api/dashboard/mastery/{uid}")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_mastery_with_subject_filter(self, async_client):
        uid = str(uuid.uuid4())
        resp = await async_client.get(f"/api/dashboard/mastery/{uid}", params={"subject": "math"})
        assert resp.status_code == 200
        # Empty or filtered — either is fine
        for item in resp.json():
            assert item["subject"] == "math"

    @pytest.mark.asyncio
    async def test_mastery_response_structure(self, async_client, test_db):
        uid = uuid.uuid4()
        user = User(id=uid, username=f"mu_{uid.hex[:8]}", display_name="Test", role="student", grade="7")
        test_db.add(user)

        km = KnowledgeMastery(
            user_id=uid,
            subject="physics",
            knowledge_point="牛顿第一定律",
            state="exposed",
            p_learned=0.5,
            total_attempts=3,
            correct_count=2,
        )
        test_db.add(km)
        await test_db.commit()

        resp = await async_client.get(f"/api/dashboard/mastery/{uid}")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        item = data[0]
        assert item["knowledge_point"] == "牛顿第一定律"
        assert item["state"] == "exposed"
        assert item["p_learned"] == 0.5


class TestMistakeDistribution:
    """GET /api/dashboard/mistakes/{user_id}."""

    @pytest.mark.asyncio
    async def test_empty_mistakes(self, async_client):
        uid = str(uuid.uuid4())
        resp = await async_client.get(f"/api/dashboard/mistakes/{uid}")
        assert resp.status_code == 200
        assert resp.json() == {}

    @pytest.mark.asyncio
    async def test_mistakes_custom_days(self, async_client):
        uid = str(uuid.uuid4())
        resp = await async_client.get(f"/api/dashboard/mistakes/{uid}", params={"days": 7})
        assert resp.status_code == 200


class TestDailyActivity:
    """GET /api/dashboard/daily/{user_id}."""

    @pytest.mark.asyncio
    async def test_empty_daily(self, async_client):
        uid = str(uuid.uuid4())
        resp = await async_client.get(f"/api/dashboard/daily/{uid}")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_daily_custom_days(self, async_client):
        uid = str(uuid.uuid4())
        resp = await async_client.get(f"/api/dashboard/daily/{uid}", params={"days": 14})
        assert resp.status_code == 200
        assert resp.json() == []
