"""Application configuration with Pydantic Settings."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProviderConfig(BaseSettings):
    """Single LLM provider configuration."""
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    priority: int = 10  # lower = higher priority
    max_tokens: int = 4096
    temperature: float = 0.7


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore",
    )

    # App
    app_name: str = "伴学系统 Bansheng"
    debug: bool = True
    secret_key: str = "dev-secret-change-in-production"

    # Database
    database_url: str = "postgresql+asyncpg://bansheng:bansheng@localhost:5432/bansheng"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM Gateway – LM Studio (local, zero-cost, highest priority)
    lm_studio: LLMProviderConfig = LLMProviderConfig(
        api_base="http://localhost:1234/v1",
        model="qwen3.6-35b",
        priority=1,
    )

    # Ollama (local fallback)
    ollama: LLMProviderConfig = LLMProviderConfig(
        api_base="http://localhost:11434/v1",
        model="qwen2.5:7b",
        priority=2,
    )

    # DeepSeek (cloud)
    deepseek: LLMProviderConfig = LLMProviderConfig(
        api_base="https://api.deepseek.com/v1",
        model="deepseek-chat",
        priority=3,
    )

    # GLM (ZhipuAI cloud)
    zhipu: LLMProviderConfig = LLMProviderConfig(
        api_base="https://open.bigmodel.cn/api/paas/v4",
        model="glm-4-flash",
        priority=4,
    )

    # Qwen (Alibaba cloud)
    qwen: LLMProviderConfig = LLMProviderConfig(
        api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        model="qwen-plus",
        priority=5,
    )

    def get_providers(self) -> list[tuple[str, LLMProviderConfig]]:
        """Return enabled providers sorted by priority."""
        providers = [
            ("lm_studio", self.lm_studio),
            ("ollama", self.ollama),
            ("deepseek", self.deepseek),
            ("zhipu", self.zhipu),
            ("qwen", self.qwen),
        ]
        enabled = [(n, p) for n, p in providers if p.api_base]
        enabled.sort(key=lambda x: x[1].priority)
        return enabled


settings = Settings()
