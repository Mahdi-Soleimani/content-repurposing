"""AvalAI transcription provider (OpenAI-compatible API)."""

from openai import AsyncOpenAI

from app.providers.base import TranscriptionProvider, TranscriptionResult
from app.config import settings


class AvalAIProvider(TranscriptionProvider):
    """AvalAI provider for transcription (OpenAI-compatible endpoint)."""

    def __init__(self):
        self._client = None

    @property
    def name(self) -> str:
        return "avalai"

    @property
    def model(self) -> str:
        return settings.AVALAI_STT_MODEL

    @property
    def supported_languages(self) -> list[str]:
        return ["fa", "en"]

    @property
    def client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=settings.AVALAI_API_KEY,
                base_url=settings.AVALAI_BASE_URL,
            )
        return self._client

    async def transcribe(
        self,
        audio_path: str,
        language: str = "fa",
    ) -> TranscriptionResult:
        """Transcribe using AvalAI API."""
        with open(audio_path, "rb") as audio_file:
            response = await self.client.audio.transcriptions.create(
                model=self.model,
                file=audio_file,
                language=language,
                response_format="verbose_json",
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
            provider=self.name,
            model=self.model,
        )

    async def is_available(self) -> bool:
        """Check if AvalAI API key is configured."""
        return bool(settings.AVALAI_API_KEY) and settings.AVALAI_API_KEY != "your-avalai-key"

