"""LLM Gateway — provider priority, fallback, health checks, error paths."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.config import LLMProviderConfig
from app.llm.gateway import LLMGateway, LLMProvider, LLMResponse


@pytest.fixture
def mock_chat_completion():
    """Create a mock openai ChatCompletion response."""
    choice = MagicMock()
    choice.message.content = "Hello from mock"
    choice.finish_reason = "stop"
    resp = MagicMock()
    resp.choices = [choice]
    resp.model = "mock-model"
    resp.usage = MagicMock(total_tokens=42)
    return resp


class TestLLMProvider:
    """Unit tests for LLMProvider health checks."""

    def test_healthy_by_default(self):
        with patch.object(LLMProvider, "__post_init__", return_value=None):
            provider = LLMProvider(
                name="test",
                config=LLMProviderConfig(api_base="http://test/v1", model="test"),
            )
            provider.client = MagicMock()
            assert provider.healthy is True
            assert provider.fail_count == 0

    @pytest.mark.asyncio
    async def test_health_check_fails_increments_counter(self):
        with patch.object(LLMProvider, "__post_init__", return_value=None):
            provider = LLMProvider(
                name="test",
                config=LLMProviderConfig(api_base="http://test/v1", model="test"),
            )
            mock_client = MagicMock()
            mock_client.models.list = AsyncMock(side_effect=Exception("down"))
            provider.client = mock_client
            # 4 failures → unhealthy
            for _ in range(4):
                result = await provider.check_health()
                assert result is False
            assert provider.healthy is False
            assert provider.fail_count == 4

    @pytest.mark.asyncio
    async def test_health_check_resets_on_success(self):
        with patch.object(LLMProvider, "__post_init__", return_value=None):
            provider = LLMProvider(
                name="test",
                config=LLMProviderConfig(api_base="http://test/v1", model="test"),
            )
            mock_client = MagicMock()
            mock_client.models.list = AsyncMock(return_value=MagicMock())
            provider.client = mock_client
            provider.fail_count = 2
            result = await provider.check_health()
            assert result is True
            assert provider.fail_count == 0
            assert provider.healthy is True


class TestLLMGateway:
    """LLM Gateway fallback and priority tests."""

    @pytest.mark.asyncio
    async def test_uses_first_healthy_provider(self, mock_chat_completion):
        with patch.object(LLMGateway, "_init_providers", return_value=None), \
             patch.object(LLMProvider, "__post_init__", return_value=None):

            gw = LLMGateway()

            # Create two mock providers
            p1 = LLMProvider(name="first", config=LLMProviderConfig(api_base="http://p1/v1", model="m1", priority=1))
            p2 = LLMProvider(name="second", config=LLMProviderConfig(api_base="http://p2/v1", model="m2", priority=2))

            p1.client = MagicMock()
            p1.client.chat.completions.create = AsyncMock(return_value=mock_chat_completion)
            p2.client = MagicMock()
            p2.client.chat.completions.create = AsyncMock(return_value=mock_chat_completion)

            gw.providers = [p1, p2]
            resp = await gw.chat([{"role": "user", "content": "hi"}])
            assert resp.provider == "first"
            assert resp.content == "Hello from mock"

    @pytest.mark.asyncio
    async def test_falls_back_when_first_fails(self, mock_chat_completion):
        with patch.object(LLMGateway, "_init_providers", return_value=None), \
             patch.object(LLMProvider, "__post_init__", return_value=None):

            gw = LLMGateway()

            p1 = LLMProvider(name="first", config=LLMProviderConfig(api_base="http://p1/v1", model="m1", priority=1))
            p2 = LLMProvider(name="second", config=LLMProviderConfig(api_base="http://p2/v1", model="m2", priority=2))

            p1.client = MagicMock()
            p1.client.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))
            p1.client.models.list = AsyncMock(side_effect=Exception("down"))
            p2.client = MagicMock()
            p2.client.chat.completions.create = AsyncMock(return_value=mock_chat_completion)

            gw.providers = [p1, p2]
            resp = await gw.chat([{"role": "user", "content": "hi"}])
            assert resp.provider == "second"

    @pytest.mark.asyncio
    async def test_skips_unhealthy_providers(self, mock_chat_completion):
        with patch.object(LLMGateway, "_init_providers", return_value=None), \
             patch.object(LLMProvider, "__post_init__", return_value=None):

            gw = LLMGateway()

            p1 = LLMProvider(name="first", config=LLMProviderConfig(api_base="http://p1/v1", model="m1", priority=1))
            p2 = LLMProvider(name="second", config=LLMProviderConfig(api_base="http://p2/v1", model="m2", priority=2))

            p1.client = MagicMock()
            p1.healthy = False
            p2.client = MagicMock()
            p2.client.chat.completions.create = AsyncMock(return_value=mock_chat_completion)

            gw.providers = [p1, p2]
            resp = await gw.chat([{"role": "user", "content": "hi"}])
            assert resp.provider == "second"

    @pytest.mark.asyncio
    async def test_raises_when_all_down(self, mock_chat_completion):
        with patch.object(LLMGateway, "_init_providers", return_value=None), \
             patch.object(LLMProvider, "__post_init__", return_value=None):

            gw = LLMGateway()

            p1 = LLMProvider(name="first", config=LLMProviderConfig(api_base="http://p1/v1", model="m1", priority=1))
            p1.client = MagicMock()
            p1.healthy = False
            gw.providers = [p1]

            with pytest.raises(RuntimeError, match="All LLM providers unavailable"):
                await gw.chat([{"role": "user", "content": "hi"}])


class TestLLMProviderConfigPriority:
    """Provider sorting by priority."""

    @pytest.mark.asyncio
    async def test_providers_sorted_by_priority(self):
        with patch.object(LLMGateway, "_init_providers", return_value=None), \
             patch.object(LLMProvider, "__post_init__", return_value=None):

            gw = LLMGateway()
            p1 = LLMProvider(name="zhipu", config=LLMProviderConfig(api_base="http://z/v1", model="z", priority=4))
            p1.client = MagicMock()
            p2 = LLMProvider(name="lm_studio", config=LLMProviderConfig(api_base="http://lm/v1", model="lm", priority=1))
            p2.client = MagicMock()
            p3 = LLMProvider(name="deepseek", config=LLMProviderConfig(api_base="http://ds/v1", model="ds", priority=3))
            p3.client = MagicMock()
            gw.providers = [p1, p2, p3]
            gw.providers.sort(key=lambda p: p.config.priority)
            assert gw.providers[0].name == "lm_studio"
            assert gw.providers[1].name == "deepseek"
            assert gw.providers[2].name == "zhipu"
