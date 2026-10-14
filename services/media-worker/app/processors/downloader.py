"""URL downloader using yt-dlp for YouTube and other sources."""

import asyncio
import json
from pathlib import Path


class URLDownloader:
    """Download media from URLs using yt-dlp.

    Supports YouTube and many other platforms.
    Instagram handling is left as a future extension point.
    """

    TEMP_DIR = Path("/tmp/media/downloads")

    def __init__(self):
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)

    async def download(
        self,
        url: str,
        output_template: str | None = None,
        max_filesize: str = "500M",
    ) -> dict:
        """
        Download media from a URL.

        YouTube URL → yt-dlp → media file
        """
        if output_template is None:
            output_template = str(self.TEMP_DIR / "%(title)s.%(ext)s")

        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--max-filesize", max_filesize,
            "--output", output_template,
            "--print-json",
            "--no-simulate",
            url,
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
                "error": stderr.decode()[-500:],
                "url": url,
            }

        # Parse yt-dlp JSON output
        try:
            info = json.loads(stdout.decode())
            return {
                "status": "success",
                "title": info.get("title", ""),
                "duration": info.get("duration"),
                "filepath": info.get("_filename") or info.get("filename", ""),
                "ext": info.get("ext", ""),
                "filesize": info.get("filesize") or info.get("filesize_approx"),
                "url": url,
            }
        except json.JSONDecodeError:
            return {
                "status": "success",
                "url": url,
                "raw_output": stdout.decode()[:500],
            }

    async def get_info(self, url: str) -> dict:
        """Get metadata about a URL without downloading."""
        cmd = [
            "yt-dlp",
            "--no-playlist",
            "--dump-json",
            "--no-download",
            url,
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            return {"status": "error", "error": stderr.decode()[-500:]}

        try:
            info = json.loads(stdout.decode())
            return {
                "status": "success",
                "title": info.get("title", ""),
                "duration": info.get("duration"),
                "description": info.get("description", "")[:500],
                "uploader": info.get("uploader", ""),
                "thumbnail": info.get("thumbnail", ""),
            }
        except json.JSONDecodeError:
            return {"status": "error", "error": "Failed to parse metadata"}
