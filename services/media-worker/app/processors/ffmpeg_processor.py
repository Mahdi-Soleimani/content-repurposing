"""FFmpeg processor for audio extraction, conversion, and chunking."""

import asyncio
import os
import subprocess
from pathlib import Path


class FFmpegProcessor:
    """Handles FFmpeg-based media processing."""

    TEMP_DIR = Path("/tmp/media")

    def __init__(self):
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    async def extract_audio(
        self,
        input_path: str,
        output_format: str = "wav",
        sample_rate: int = 16000,
    ) -> dict:
        """
        Extract audio from a video file.

        video.mp4 → FFmpeg → audio.wav
        """
        input_file = Path(input_path)
        output_file = self.TEMP_DIR / f"{input_file.stem}_normalized.{output_format}"

        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-vn",                       # No video
            "-acodec", "pcm_s16le" if output_format == "wav" else "libmp3lame",
            "-ar", str(sample_rate),     # Sample rate
            "-ac", "1",                  # Mono
            "-y",                        # Overwrite
            str(output_file),
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return {
                "status": "error",
                "error": stderr.decode()[-500:],  # Last 500 chars of error
            }

        file_size = output_file.stat().st_size if output_file.exists() else 0

        return {
            "status": "success",
            "output_path": str(output_file),
            "format": output_format,
            "sample_rate": sample_rate,
            "file_size": file_size,
        }

    async def convert_audio(
        self,
        input_path: str,
        output_format: str = "mp3",
        bitrate: str = "128k",
    ) -> dict:
        """Convert audio between formats."""
        input_file = Path(input_path)
        output_file = self.TEMP_DIR / f"{input_file.stem}.{output_format}"

        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-b:a", bitrate,
            "-y",
            str(output_file),
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            return {"status": "error", "error": stderr.decode()[-500:]}

        return {
            "status": "success",
            "output_path": str(output_file),
            "format": output_format,
        }

    async def chunk_audio(
        self,
        input_path: str,
        chunk_duration_seconds: int = 600,  # 10 minutes
    ) -> dict:
        """Split audio into chunks for processing (e.g., STT has size limits)."""
        input_file = Path(input_path)
        chunk_dir = self.TEMP_DIR / f"chunks_{input_file.stem}"
        chunk_dir.mkdir(parents=True, exist_ok=True)

        # Get duration first
        probe_cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "csv=p=0",
            str(input_path),
        ]
        probe = await asyncio.create_subprocess_exec(
            *probe_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await probe.communicate()
        total_duration = float(stdout.decode().strip()) if stdout else 0

        # Split
        cmd = [
            "ffmpeg",
            "-i", str(input_path),
            "-f", "segment",
            "-segment_time", str(chunk_duration_seconds),
            "-c", "copy",
            "-y",
            str(chunk_dir / f"chunk_%03d{input_file.suffix}"),
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            return {"status": "error", "error": stderr.decode()[-500:]}

        chunks = sorted(chunk_dir.glob("chunk_*"))
        return {
            "status": "success",
            "total_duration": total_duration,
            "chunk_count": len(chunks),
            "chunk_paths": [str(c) for c in chunks],
        }
