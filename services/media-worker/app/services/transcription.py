"""Transcription service — provider-agnostic interface.

Usage:
    service = TranscriptionService()
    result = await service.transcribe("audio.wav", language="fa")

The service automatically selects the configured provider.
Changing provider requires zero code changes in calling code.

    TranscriptionService
           │
           ▼
    Provider Interface
           │
     ┌─────┴─────┐
     ▼           ▼
   AvalAI      OpenAI
"""

import os

from app.providers.base import TranscriptionProvider, TranscriptionResult
from app.providers.openai_provider import OpenAIProvider
from app.providers.avalai_provider import AvalAIProvider
from app.providers.shenava_provider import ShenavaProvider


class ProviderFactory:
    """Factory for creating transcription providers."""

    providers: dict[str, type[TranscriptionProvider]] = {
        "openai": OpenAIProvider,
        "avalai": AvalAIProvider,
        "shenava": ShenavaProvider,
    }

    @classmethod
    def create(cls, name: str) -> TranscriptionProvider:
        """Create a provider instance by name."""
        provider_cls = cls.providers.get(name)
        if not provider_cls:
            raise Exception(f"Unknown provider: {name}. Available: {list(cls.providers.keys())}")
        return provider_cls()

    @classmethod
    async def get_available_providers(cls) -> list[str]:
        """List providers that are currently available."""
        available = []
        for name, provider_cls in cls.providers.items():
            instance = provider_cls()
            if await instance.is_available():
                available.append(name)
        return available
