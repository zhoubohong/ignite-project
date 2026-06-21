"""L1 Session Memory — Redis-backed conversation history."""
from __future__ import annotations

import uuid

import pytest


class TestSessionMemory:
    """Session memory using FakeRedis fixture from conftest."""

    @pytest.mark.asyncio
    async def test_add_and_retrieve_history(self, session_memory_with_fakeredis):
        sm = session_memory_with_fakeredis
        sid = uuid.uuid4()

        await sm.add_turn(sid, "user", "你好")
        await sm.add_turn(sid, "assistant", "你好！有什么可以帮你的？")

        history = await sm.get_history(sid)
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "你好"
        assert history[1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_empty_history(self, session_memory_with_fakeredis):
        sm = session_memory_with_fakeredis
        sid = uuid.uuid4()
        history = await sm.get_history(sid)
        assert history == []

    @pytest.mark.asyncio
    async def test_get_messages_with_system_prompt(self, session_memory_with_fakeredis):
        sm = session_memory_with_fakeredis
        sid = uuid.uuid4()

        await sm.add_turn(sid, "user", "什么是二次函数？")

        msgs = await sm.get_messages(sid, system_prompt="你是一位数学老师")
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert "数学老师" in msgs[0]["content"]
        assert msgs[1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_get_messages_without_system_prompt(self, session_memory_with_fakeredis):
        sm = session_memory_with_fakeredis
        sid = uuid.uuid4()

        await sm.add_turn(sid, "user", "hello")

        msgs = await sm.get_messages(sid)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"

    @pytest.mark.asyncio
    async def test_max_turns_trimming(self, session_memory_with_fakeredis):
        """When turns exceed max_turns (5), old ones are trimmed."""
        sm = session_memory_with_fakeredis  # max_turns=5 from conftest
        sid = uuid.uuid4()

        for i in range(8):
            await sm.add_turn(sid, "user", f"msg{i}")

        history = await sm.get_history(sid)
        assert len(history) == 5, f"Expected 5 turns retained, got {len(history)}"
        # The earliest 3 should be trimmed, so first retained turn is msg3
        assert history[0]["content"] == "msg3"

    @pytest.mark.asyncio
    async def test_clear(self, session_memory_with_fakeredis):
        sm = session_memory_with_fakeredis
        sid = uuid.uuid4()

        await sm.add_turn(sid, "user", "test")
        assert len(await sm.get_history(sid)) == 1

        await sm.clear(sid)
        assert len(await sm.get_history(sid)) == 0

    @pytest.mark.asyncio
    async def test_independent_sessions(self, session_memory_with_fakeredis):
        """Different session IDs should have independent histories."""
        sm = session_memory_with_fakeredis
        sid1 = uuid.uuid4()
        sid2 = uuid.uuid4()

        await sm.add_turn(sid1, "user", "session1")
        await sm.add_turn(sid2, "user", "session2")

        h1 = await sm.get_history(sid1)
        h2 = await sm.get_history(sid2)

        assert len(h1) == 1
        assert len(h2) == 1
        assert h1[0]["content"] == "session1"
        assert h2[0]["content"] == "session2"

    @pytest.mark.asyncio
    async def test_role_preservation(self, session_memory_with_fakeredis):
        sm = session_memory_with_fakeredis
        sid = uuid.uuid4()

        for role in ["user", "assistant", "system", "user"]:
            await sm.add_turn(sid, role, f"content-{role}")

        history = await sm.get_history(sid)
        assert [h["role"] for h in history] == ["user", "assistant", "system", "user"]
