"""Instagram provider chain (parth-dl -> instaloader -> yt-dlp)."""

import os
import time
import asyncio
import logging
import glob
from app.providers.base import DownloadProvider, DownloadResult

logger = logging.getLogger(__name__)

class InstagramProvider(DownloadProvider):
    name = "instagram_chain"

    async def download(self, url: str, output_dir: str) -> DownloadResult:
        start_time = time.time()
        
        # 1. Try parth-dl
        logger.info(f"[instagram] Trying parth-dl for {url}")
        res = await self._run_parth_dl(url, output_dir, start_time)
        if res.success:
            return res
            
        logger.warning(f"[instagram] parth-dl failed: {res.error}. Trying instaloader...")
        
        # 2. Try instaloader
        res = await self._run_instaloader(url, output_dir, start_time)
        if res.success:
            return res
            
        logger.warning(f"[instagram] instaloader failed: {res.error}. Trying yt-dlp...")
        
        # 3. Try yt-dlp
        res = await self._run_ytdlp(url, output_dir, start_time)
        if res.success:
            return res
            
        logger.error(f"[instagram] All downloaders failed for {url}")
        return DownloadResult(
            success=False,
            error=f"All downloaders failed. Last error (yt-dlp): {res.error}",
            duration_ms=int((time.time() - start_time) * 1000)
        )

    async def _run_parth_dl(self, url: str, output_dir: str, start_time: float) -> DownloadResult:
        cmd = ["parth-dl", url, "-P", output_dir]
        return await self._execute_and_find_media(cmd, output_dir, start_time)

    async def _run_instaloader(self, url: str, output_dir: str, start_time: float) -> DownloadResult:
        # url format: https://www.instagram.com/p/SHORTCODE/ or https://www.instagram.com/reel/SHORTCODE/?...
        # Extract shortcode safely
        clean_url = url.split('?')[0].rstrip('/')
        shortcode = clean_url.split('/')[-1]
            
        cmd = [
            "instaloader",
            "--dirname-pattern", output_dir,
            "--no-profile-pic",
            "--no-captions",
            "--no-metadata-json",
            "--no-compress-json",
            "--", f"-{shortcode}"
        ]
        return await self._execute_and_find_media(cmd, output_dir, start_time)

    async def _run_ytdlp(self, url: str, output_dir: str, start_time: float) -> DownloadResult:
        output_template = os.path.join(output_dir, "%(id)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "-f", "best",
            "-o", output_template,
            url
        ]
        return await self._execute_and_find_media(cmd, output_dir, start_time)

    async def _execute_and_find_media(self, cmd: list, output_dir: str, start_time: float) -> DownloadResult:
        logger.info(f"Running: {' '.join(cmd)}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
        except asyncio.TimeoutError:
            process.kill()
            await process.communicate()
            duration_ms = int((time.time() - start_time) * 1000)
            return DownloadResult(success=False, error="Command timed out after 5 minutes", duration_ms=duration_ms)
        duration_ms = int((time.time() - start_time) * 1000)
        
        if process.returncode != 0:
            return DownloadResult(success=False, error=stderr.decode(), duration_ms=duration_ms)
            
        # Cleanup extraneous files (instaloader creates .txt, .json.xz, .jpg)
        for ext in ["*.txt", "*.json.xz", "*.jpg"]:
            for f in glob.glob(os.path.join(output_dir, ext)):
                try:
                    os.remove(f)
                except OSError:
                    pass
        
        # Find the media file
        files = os.listdir(output_dir)
        media_files = [f for f in files if f.endswith((".mp4", ".mkv", ".webm"))]
        
        if not media_files:
            return DownloadResult(
                success=False, 
                error=f"No media file found. Output: {stdout.decode()}", 
                duration_ms=duration_ms
            )
            
        # We just pick the first one
        media_file = media_files[0]
        file_path = os.path.join(output_dir, media_file)
        file_size = os.path.getsize(file_path)
        
        return DownloadResult(
            success=True,
            file_path=file_path,
            file_size=file_size,
            duration_ms=duration_ms,
            content_type="video/mp4" if media_file.endswith(".mp4") else "video/webm",
            original_filename=media_file
        )
