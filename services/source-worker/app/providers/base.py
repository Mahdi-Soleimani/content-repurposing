"""Base provider for source downloading."""

import os
from abc import ABC, abstractmethod
from pydantic import BaseModel

class DownloadResult(BaseModel):
    success: bool
    file_path: str | None = None
    file_size: int = 0
    duration_ms: int = 0
    error: str | None = None
    content_type: str = "application/octet-stream"
    original_filename: str | None = None

class DownloadProvider(ABC):
    name: str

    @abstractmethod
    async def download(self, url: str, output_dir: str) -> DownloadResult:
        """Download media from URL to output_dir."""
        pass
