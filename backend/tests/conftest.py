"""Shared test fixtures: mock LLM gateway, FakeRedis, in-memory SQLite, FastAPI TestClient."""
from __future__ import annotations

import asyncio
import json
import os
import uuid
from typing import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Override environment before any imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"


@pytest.fixture(scope="session")
def event_loop():
    """Session-scoped event loop for all async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── Mock LLM Gateway ───────────────────────────────────────────────

class MockChatCompletionMessage:
    def __init__(self, content: str):
        self.content = content


class MockChatCompletionChoice:
    def __init__(self, content: str, finish_reason: str = "stop"):
        self.message = MockChatCompletionMessage(content)
        self.finish_reason = finish_reason
        self.delta = MockChatCompletionMessage(content)


class MockUsage:
    total_tokens = 100


class MockChatCompletion:
    def __init__(self, content: str, model: str = "test-model"):
        self.choices = [MockChatCompletionChoice(content)]
        self.model = model
        self.usage = MockUsage()


async def _mock_chat(*args, **kwargs):
    """Return a mock LLMResponse based on the message content."""
    messages = args[0] if args else kwargs.get("messages", [])
    user_content = ""
    for m in messages:
        if m.get("role") == "user":
            user_content = m.get("content", "")
            break

    # Intent classification: return JSON based on triggers in user input
    if "分类器" in str(messages):
        if "数学" in user_content or "方程" in user_content or "函数" in user_content:
            return MagicMock(
                content=json.dumps({"intent": "learn", "subject": "math", "agent": "stem", "knowledge_points": ["二次方程"]}),
                model="test-model", provider="mock", tokens_used=10, finish_reason="stop",
            )
        if "物理" in user_content or "力" in user_content:
            return MagicMock(
                content=json.dumps({"intent": "learn", "subject": "physics", "agent": "stem", "knowledge_points": ["牛顿定律"]}),
                model="test-model", provider="mock", tokens_used=10, finish_reason="stop",
            )
        if "化学" in user_content or "反应" in user_content:
            return MagicMock(
                content=json.dumps({"intent": "learn", "subject": "chemistry", "agent": "stem", "knowledge_points": ["化学反应"]}),
                model="test-model", provider="mock", tokens_used=10, finish_reason="stop",
            )
        if "生物" in user_content:
            return MagicMock(
                content=json.dumps({"intent": "learn", "subject": "biology", "agent": "stem", "knowledge_points": ["细胞"]}),
                model="test-model", provider="mock", tokens_used=10, finish_reason="stop",
            )
        if "语文" in user_content or "诗词" in user_content or "作文" in user_content:
            return MagicMock(
                content=json.dumps({"intent": "learn", "subject": "chinese", "agent": "liberal_arts", "knowledge_points": ["古诗鉴赏"]}),
                model="test-model", provider="mock", tokens_used=10, finish_reason="stop",
            )
        if "英语" in user_content or "english" in user_content.lower():
            return MagicMock(
                content=json.dumps({"intent": "learn", "subject": "english", "agent": "liberal_arts", "knowledge_points": ["语法"]}),
                model="test-model", provider="mock", tokens_used=10, finish_reason="stop",
            )
        if "历史" in user_content:
            return MagicMock(
                content=json.dumps({"intent": "learn", "subject": "history", "agent": "liberal_arts", "knowledge_points": ["辛亥革命"]}),
                model="test-model", provider="mock", tokens_used=10, finish_reason="stop",
            )
        if "政治" in user_content:
            return MagicMock(
                content=json.dumps({"intent": "learn", "subject": "politics", "agent": "liberal_arts", "knowledge_points": ["宪法"]}),
                model="test-model", provider="mock", tokens_used=10, finish_reason="stop",
            )
        if "考试" in user_content or "组卷" in user_content or "模拟" in user_content:
            return MagicMock(
                content=json.dumps({"intent": "exam", "subject": "math", "agent": "exam", "knowledge_points": []}),
                model="test-model", provider="mock", tokens_used=10, finish_reason="stop",
            )
        # Default
        return MagicMock(
            content=json.dumps({"intent": "learn", "subject": "math", "agent": "stem", "knowledge_points": []}),
            model="test-model", provider="mock", tokens_used=10, finish_reason="stop",
        )

    # Error classification: return error type
    if "分析学生错因" in str(messages):
        return MagicMock(
            content="calculation", model="test-model", provider="mock", tokens_used=5, finish_reason="stop",
        )

    # Question generation: return JSON with questions
    if "题库" in str(messages) or "生成" in str(messages):
        return MagicMock(
            content=json.dumps({
                "questions": [
                    {
                        "qtype": "single_choice",
                        "stem": f"测试题目：{user_content[:20]}",
                        "options": {"A": "选项A", "B": "选项B", "C": "选项C", "D": "选项D"},
                        "answer": "B",
                        "explanation": "测试解析",
                        "difficulty": 0.5,
                        "knowledge_points": ["测试知识点"],
                    }
                ]
            }),
            model="test-model", provider="mock", tokens_used=50, finish_reason="stop",
        )

    # Generic chat reply
    return MagicMock(
        content=f"Mock reply: {user_content[:50]}",
        model="test-model", provider="mock", tokens_used=20, finish_reason="stop",
    )


async def _mock_chat_stream(*args, **kwargs):
    """Mock streaming chat."""
    messages = args[0] if args else kwargs.get("messages", [])
    user_content = ""
    for m in messages:
        if m.get("role") == "user":
            user_content = m.get("content", "")
            break

    tokens = ["Mock", " ", "streaming", " ", "reply", ": ", user_content[:20]]
    for token in tokens:
        yield token


@pytest.fixture(autouse=True)
def mock_llm_gateway():
    """Mock the global LLM gateway singleton for all tests."""
    import fakeredis.aioredis as faioredis
    fr = faioredis.FakeRedis(decode_responses=True)
    with patch("app.llm.gateway.gateway.chat", side_effect=_mock_chat), \
         patch("app.llm.gateway.gateway.chat_stream", side_effect=_mock_chat_stream), \
         patch("app.agents.orchestrator.gateway.chat", side_effect=_mock_chat), \
         patch("app.agents.orchestrator.gateway.chat_stream", side_effect=_mock_chat_stream), \
         patch("app.question_bank.generator.gateway.chat", side_effect=_mock_chat), \
         patch("app.db.database.init_db", return_value=None), \
         patch("app.memory.session.session_memory._redis", fr):
        yield


# ─── FakeRedis ──────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def fake_redis():
    """FakeRedis fixture for session memory tests."""
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield r
    await r.flushall()


@pytest.fixture
def session_memory_with_fakeredis(fake_redis):
    """SessionMemory bound to FakeRedis."""
    from app.memory.session import SessionMemory
    sm = SessionMemory(max_turns=5)
    sm._redis = fake_redis
    return sm


# ─── In-memory SQLite Database ──────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

_engine = None
_sessionmaker = None


async def _get_test_engine():
    global _engine, _sessionmaker
    if _engine is None:
        _engine = create_async_engine(
            TEST_DATABASE_URL, echo=False,
            connect_args={"check_same_thread": False},
        )
        _sessionmaker = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)

        # Import models to register them with SQLAlchemy metadata
        import app.models.user  # noqa: F401
        import app.models.question  # noqa: F401
        import app.models.session  # noqa: F401
        from app.models.base import Base

        # Override PostgreSQL-only types for SQLite compatibility
        from sqlalchemy import JSON, LargeBinary, ARRAY
        from sqlalchemy.dialects.postgresql import JSONB
        from pgvector.sqlalchemy import Vector

        for table_name, table in list(Base.metadata.tables.items()):
            new_cols = []
            for col in table.columns:
                new_type = None
                if hasattr(col.type, "item_type") or isinstance(col.type, ARRAY):
                    new_type = JSON()
                elif isinstance(col.type, JSONB):
                    new_type = JSON()
                elif isinstance(col.type, Vector):
                    new_type = LargeBinary()
                if new_type is not None:
                    new_cols.append((col, new_type))
            for col, new_type in new_cols:
                col.type = new_type

        async with _engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    return _engine


@pytest_asyncio.fixture
async def test_db():
    """In-memory SQLite test database session."""
    await _get_test_engine()
    async with _sessionmaker() as session:
        yield session


# ─── FastAPI TestClient ─────────────────────────────────────────────

@pytest_asyncio.fixture
async def async_client(test_db) -> AsyncIterator[AsyncClient]:
    """Async HTTP client for FastAPI test app with overridden DB dependency."""
    from app.main import app
    from app.db.database import get_db

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


# ─── Test data helpers ─────────────────────────────────────────────

@pytest.fixture
def test_user_id():
    return uuid.uuid4()


@pytest.fixture
def test_session_id():
    return uuid.uuid4()


@pytest_asyncio.fixture
async def seed_question(test_db):
    """Seed a question in the test DB using ORM."""
    from app.models.question import Question
    q = Question(
        qtype="single_choice",
        subject="math",
        grade_level="7",
        stem="1 + 1 = ?",
        options={"A": "1", "B": "2", "C": "3", "D": "4"},
        answer="B",
        explanation="1+1=2",
        knowledge_points=["加法"],
        source="manual",
    )
    test_db.add(q)
    await test_db.flush()
    await test_db.commit()
    return str(q.id)
