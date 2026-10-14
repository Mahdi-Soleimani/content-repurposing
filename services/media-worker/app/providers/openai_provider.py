"""OpenAI Whisper transcription provider."""

import os

from openai import AsyncOpenAI

from app.providers.base import TranscriptionProvider, TranscriptionResult


class OpenAIProvider(TranscriptionProvider):
    """OpenAI Whisper API provider for transcription."""

    def __init__(self):
        self._client = None

    @property
    def provider_name(self) -> str:
        return "openai"

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=os.getenv("OPENAI_API_KEY", ""),
            )
        return self._client

    async def transcribe(
        self,
        audio_path: str,
        language: str = "fa",
        model: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe using OpenAI Whisper API."""
        model = model or "whisper-1"

        with open(audio_path, "rb") as audio_file:
            response = await self.client.audio.transcriptions.create(
                model=model,
                file=audio_file,
                language=language,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )

        segments = []
        if hasattr(response, "segments") and response.segments:
            segments = [
                {
                    "start": seg.start if hasattr(seg, 'start') else seg.get("start"),
                    "end": seg.end if hasattr(seg, 'end') else seg.get("end"),
                    "text": seg.text if hasattr(seg, 'text') else seg.get("text"),
                }
                for seg in response.segments
            ]

        return TranscriptionResult(
            text=response.text,
            language=response.language if hasattr(response, "language") else language,
            duration=response.duration if hasattr(response, "duration") else None,
            segments=segments,
            provider=self.provider_name,
            model=model,
        )

    async def is_available(self) -> bool:
        """Check if OpenAI API key is configured."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        return bool(api_key) and api_key != "sk-your-openai-key"
