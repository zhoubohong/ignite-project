"""Question Bank API — CRUD + LLM generation."""
from __future__ import annotations

import json
import uuid

import pytest


class TestQuestionCRUD:
    """CRUD endpoints: GET list, POST create, GET by id, DELETE."""

    @pytest.mark.asyncio
    async def test_list_questions_empty(self, async_client):
        resp = await async_client.get("/api/questions/")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # May have questions from other tests; just verify it's valid JSON

    @pytest.mark.asyncio
    async def test_create_question(self, async_client):
        resp = await async_client.post("/api/questions/", json={
            "qtype": "single_choice",
            "subject": "math",
            "grade_level": "8",
            "difficulty": 0.6,
            "stem": "若 x² = 4，则 x = ?",
            "options": {"A": "2", "B": "-2", "C": "±2", "D": "4"},
            "answer": "C",
            "explanation": "平方根有两个值",
            "knowledge_points": ["平方根"],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["qtype"] == "single_choice"
        assert data["subject"] == "math"
        assert data["answer"] == "C"
        assert data["source"] == "manual"
        assert "id" in data
        return data["id"]

    @pytest.mark.asyncio
    async def test_get_question_by_id(self, async_client):
        # Create first
        create_resp = await async_client.post("/api/questions/", json={
            "qtype": "fill_blank",
            "subject": "english",
            "grade_level": "9",
            "stem": "The past tense of 'go' is ____.",
            "answer": "went",
            "knowledge_points": ["irregular verbs"],
        })
        qid = create_resp.json()["id"]

        # Get
        resp = await async_client.get(f"/api/questions/{qid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == qid
        assert data["answer"] == "went"

    @pytest.mark.asyncio
    async def test_get_question_not_found(self, async_client):
        resp = await async_client.get(f"/api/questions/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_question(self, async_client):
        create_resp = await async_client.post("/api/questions/", json={
            "qtype": "true_false",
            "subject": "physics",
            "stem": "光速在真空中是 3×10⁸ m/s。",
            "answer": "true",
        })
        qid = create_resp.json()["id"]

        resp = await async_client.delete(f"/api/questions/{qid}")
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

        # Verify deleted
        resp = await async_client.get(f"/api/questions/{qid}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_question_not_found(self, async_client):
        resp = await async_client.delete(f"/api/questions/{uuid.uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_create_question_minimal_fields(self, async_client):
        resp = await async_client.post("/api/questions/", json={
            "qtype": "short_answer",
            "subject": "chemistry",
            "stem": "水的化学式是什么？",
            "answer": "H₂O",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["difficulty"] == 0.5  # default
        assert data["grade_level"] == "7"  # default
        assert data["options"] == {}  # default


class TestQuestionListFiltering:
    """Filtering by subject, grade, qtype, difficulty."""

    @pytest.mark.asyncio
    async def test_filter_by_subject(self, async_client):
        resp = await async_client.get("/api/questions/", params={"subject": "math"})
        assert resp.status_code == 200
        # All returned questions should have subject=math
        for q in resp.json():
            assert q["subject"] == "math"

    @pytest.mark.asyncio
    async def test_filter_by_grade(self, async_client):
        resp = await async_client.get("/api/questions/", params={"grade_level": "8"})
        assert resp.status_code == 200
        for q in resp.json():
            assert q["grade_level"] == "8"

    @pytest.mark.asyncio
    async def test_filter_by_qtype(self, async_client):
        resp = await async_client.get("/api/questions/", params={"qtype": "single_choice"})
        assert resp.status_code == 200
        for q in resp.json():
            assert q["qtype"] == "single_choice"

    @pytest.mark.asyncio
    async def test_filter_by_difficulty_range(self, async_client):
        resp = await async_client.get("/api/questions/", params={
            "difficulty_min": 0.5,
            "difficulty_max": 0.7,
        })
        assert resp.status_code == 200
        for q in resp.json():
            assert 0.5 <= q["difficulty"] <= 0.7

    @pytest.mark.asyncio
    async def test_pagination(self, async_client):
        resp = await async_client.get("/api/questions/", params={"limit": 5, "offset": 0})
        assert resp.status_code == 200
        assert len(resp.json()) <= 5


class TestQuestionGeneration:
    """POST /api/questions/generate — LLM-powered question generation."""

    @pytest.mark.asyncio
    async def test_generate_questions(self, async_client):
        resp = await async_client.post("/api/questions/generate", json={
            "subject": "math",
            "grade_level": "7",
            "knowledge_points": ["分数运算"],
            "qtypes": ["single_choice", "fill_blank"],
            "count": 2,
            "difficulty": 0.4,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for q in data:
            assert "id" in q
            assert q["subject"] == "math"
            assert q["source"] == "llm"

    @pytest.mark.asyncio
    async def test_generate_with_defaults(self, async_client):
        resp = await async_client.post("/api/questions/generate", json={
            "subject": "english",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Default count=3, grade=7
        assert len(data) <= 3
