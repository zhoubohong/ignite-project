"""统一LLM Gateway — 本地优先(LM Studio/Ollama)，云端兜底，fallback+重试."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

import httpx
from openai import AsyncOpenAI

from app.core.config import LLMProviderConfig, settings

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    finish_reason: str = "stop"


@dataclass
class LLMProvider:
    name: str
    config: LLMProviderConfig
    client: AsyncOpenAI = field(init=False)
    healthy: bool = True
    fail_count: int = 0

    def __post_init__(self) -> None:
        self.client = AsyncOpenAI(
            base_url=self.config.api_base,
            api_key=self.config.api_key or "not-needed",
            http_client=httpx.AsyncClient(timeout=120.0),
        )

    async def check_health(self) -> bool:
        """Probe provider availability with a lightweight models list call."""
        try:
            await self.client.models.list()
            self.healthy = True
            self.fail_count = 0
            return True
        except Exception:
            self.fail_count += 1
            if self.fail_count > 3:
                self.healthy = False
            return False


class LLMGateway:
    """Multi-provider LLM Gateway with automatic fallback.

    Priority order:
      1. LM Studio (local, zero-cost) → 2. Ollama (local) → 3. DeepSeek → 4. GLM → 5. Qwen
    """

    def __init__(self) -> None:
        self.providers: list[LLMProvider] = []
        self._lock = asyncio.Lock()
        self._init_providers()

    def _init_providers(self) -> None:
        for name, cfg in settings.get_providers():
            self.providers.append(LLMProvider(name=name, config=cfg))
        logger.info(
            "LLM Gateway initialized with %d providers: %s",
            len(self.providers),
            [p.name for p in self.providers],
        )

    async def _try_provider(
        self,
        provider: LLMProvider,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse | None:
        """Attempt completion on a single provider."""
        try:
            model = provider.config.model
            resp = await provider.client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=kwargs.get("max_tokens", provider.config.max_tokens),
                temperature=kwargs.get("temperature", provider.config.temperature),
            )
            choice = resp.choices[0]
            return LLMResponse(
                content=choice.message.content or "",
                model=resp.model,
                provider=provider.name,
                tokens_used=resp.usage.total_tokens if resp.usage else 0,
                finish_reason=choice.finish_reason or "stop",
            )
        except Exception as e:
            logger.warning("Provider %s failed: %s", provider.name, e)
            await provider.check_health()
            return None

    async def chat(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> LLMResponse:
        """Send chat request with automatic fallback across providers."""
        for provider in self.providers:
            if not provider.healthy:
                continue
            result = await self._try_provider(provider, messages, **kwargs)
            if result is not None:
                return result
        raise RuntimeError("All LLM providers unavailable")

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> AsyncIterator[str]:
        """Streaming chat with fallback (non-streaming fallback if stream fails)."""
        for provider in self.providers:
            if not provider.healthy:
                continue
            try:
                model = provider.config.model
                stream = await provider.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=kwargs.get("max_tokens", provider.config.max_tokens),
                    temperature=kwargs.get("temperature", provider.config.temperature),
                    stream=True,
                )
                async for chunk in stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
                return
            except Exception as e:
                logger.warning("Stream provider %s failed: %s", provider.name, e)
                await provider.check_health()

        # Last resort: non-streaming fallback
        resp = await self.chat(messages, **kwargs)
        yield resp.content


# Global singleton
gateway = LLMGateway()
