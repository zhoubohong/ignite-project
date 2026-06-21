"""Chat API — /send, /stream SSE, /answer/check with BKT + mistake recording."""
from __future__ import annotations

import json
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.db.database import get_db


# ── Fixture override for tests that need a pre-created user ──────────

@pytest_asyncio.fixture
async def client_with_user(test_db) -> AsyncClient:
    """Test client with a seeded user and overridden DB."""
    uid = str(uuid.uuid4())
    from sqlalchemy import text
    await test_db.execute(
        text("INSERT INTO users (id, username, grade) VALUES (:id, :uname, :grade)"),
        {"id": uid, "uname": f"testuser_{uid[:8]}", "grade": "7"},
    )
    await test_db.commit()

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client._test_uid = uid
        yield client
    app.dependency_overrides.clear()


class TestChatSend:
    """POST /api/chat/send — non-streaming chat."""

    @pytest.mark.asyncio
    async def test_send_math_question(self, async_client):
        resp = await async_client.post("/api/chat/send", json={
            "message": "请问什么是二次函数？",
            "user_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert "reply" in data
        assert len(data["reply"]) > 0

    @pytest.mark.asyncio
    async def test_send_with_session_id(self, async_client):
        sid = str(uuid.uuid4())
        resp = await async_client.post("/api/chat/send", json={
            "message": "继续上一题",
            "session_id": sid,
            "user_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == sid

    @pytest.mark.asyncio
    async def test_send_intent_is_returned(self, async_client):
        resp = await async_client.post("/api/chat/send", json={
            "message": "讲解一下物理中的牛顿定律",
            "user_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["intent"] in ("learn", "practice", "exam", "review", "other")

    @pytest.mark.asyncio
    async def test_send_empty_body_returns_422(self, async_client):
        resp = await async_client.post("/api/chat/send", json={})
        assert resp.status_code == 422


class TestChatStream:
    """POST /api/chat/stream — SSE streaming endpoint."""

    @pytest.mark.asyncio
    async def test_stream_returns_events(self, async_client):
        resp = await async_client.post("/api/chat/stream", json={
            "message": "什么是细胞？",
            "user_id": str(uuid.uuid4()),
        })
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")
        body = resp.text
        assert "data: " in body
        assert '"done": true' in body.lower() or '[DONE]' in body

    @pytest.mark.asyncio
    async def test_stream_metadata_event(self, async_client):
        resp = await async_client.post("/api/chat/stream", json={
            "message": "数学中的一元一次方程",
            "user_id": str(uuid.uuid4()),
        })
        body = resp.text
        # First event should contain metadata
        lines = [l for l in body.split("\n") if l.startswith("data:")]
        first = json.loads(lines[0].replace("data: ", ""))
        assert "session_id" in first
        assert "intent" in first
        assert "subject" in first


class TestAnswerCheck:
    """POST /api/chat/answer/check — answer validation + BKT update."""

    @pytest.mark.asyncio
    async def test_correct_answer(self, async_client, seed_question):
        sid = str(uuid.uuid4())
        uid = str(uuid.uuid4())

        resp = await async_client.post(
            "/api/chat/answer/check",
            json={
                "question_id": seed_question,
                "student_answer": "B",
                "session_id": sid,
                "user_id": uid,
                "subject": "math",
                "knowledge_point": "加法",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is True
        assert data["correct_answer"] == "B"
        # Mastery should be updated (p_learned > default 0.3 after correct)
        assert data["mastery_p_learned"] > 0.3

    @pytest.mark.asyncio
    async def test_incorrect_answer(self, async_client, seed_question):
        sid = str(uuid.uuid4())
        uid = str(uuid.uuid4())

        resp = await async_client.post(
            "/api/chat/answer/check",
            json={
                "question_id": seed_question,
                "student_answer": "A",
                "session_id": sid,
                "user_id": uid,
                "subject": "math",
                "knowledge_point": "加法",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_correct"] is False
        assert data["correct_answer"] == "B"
        # Should have an error type from mistake recording
        assert "error_type" in data

    @pytest.mark.asyncio
    async def test_answer_check_nonexistent_question(self, async_client):
        resp = await async_client.post(
            "/api/chat/answer/check",
            json={
                "question_id": str(uuid.uuid4()),
                "student_answer": "A",
                "session_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_answer_check_missing_params(self, async_client):
        resp = await async_client.post(
            "/api/chat/answer/check",
            json={"question_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 422
