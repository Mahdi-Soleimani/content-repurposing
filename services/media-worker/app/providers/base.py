"""Base provider interface for AI services.

TranscriptionService → Provider Interface → AvalAI / OpenAI

This abstraction makes it easy to switch providers without
changing the calling code.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TranscriptionResult:
    """Standard transcription result across all providers."""
    text: str
    language: str
    duration: float | None = None
    segments: list[dict] | None = None
    confidence: float | None = None
    provider: str = ""
    model: str = ""


class TranscriptionProvider(ABC):
    """Abstract interface for transcription providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name of this provider."""
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        """Default model used by this provider."""
        ...

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """List of supported language codes."""
        ...

    @abstractmethod
    async def transcribe(
        self,
        audio_path: str,
        language: str = "fa",
    ) -> TranscriptionResult:
        """
        Transcribe an audio file.

        Args:
            audio_path: Path to the audio file
            language: Language code (default: Persian)
            model: Optional model override

        Returns:
            TranscriptionResult with text and metadata
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if this provider is currently available."""
        ...
