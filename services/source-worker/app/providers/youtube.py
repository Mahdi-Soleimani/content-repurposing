"""YouTube provider using yt-dlp."""

import os
import time
import json
import asyncio
import logging
import signal
from pathlib import Path
from app.providers.base import DownloadProvider, DownloadResult

logger = logging.getLogger(__name__)

def classify_error(stderr_output: str) -> tuple[str, bool]:
    """Classify the stderr output from yt-dlp.
    Returns: (ErrorCategory, ShouldRetry)
    """
    stderr_output = stderr_output.lower()
    
    # Fail fast errors
    if "sign in to confirm" in stderr_output or "bot" in stderr_output or "page needs to be reloaded" in stderr_output:
        return "BotDetectionError", False
    if "private video" in stderr_output:
        return "PrivateVideoError", False
    if "unavailable" in stderr_output or "no video formats" in stderr_output:
        return "UnavailableVideoError", False
    if "invalid" in stderr_output or "not a valid url" in stderr_output:
        return "InvalidURL", False
        
    # Retriable errors
    if "network" in stderr_output or "timeout" in stderr_output:
        return "NetworkError", True
    if "500" in stderr_output or "502" in stderr_output or "503" in stderr_output or "504" in stderr_output:
        return "Http5xxError", True
        
    return "ExtractorError", True

def cleanup_directory(output_dir: str):
    """Remove any yt-dlp partial files and incomplete wav files."""
    try:
        if not os.path.exists(output_dir):
            return
        for f in os.listdir(output_dir):
            if f.endswith(".part") or f.endswith(".ytdl") or f.endswith(".temp") or f.endswith(".wav"):
                file_path = os.path.join(output_dir, f)
                try:
                    os.remove(file_path)
                    logger.debug(f"Cleaned up temporary file: {file_path}")
                except Exception as e:
                    logger.warning(f"Failed to remove temp file {file_path}: {e}")
    except Exception as e:
        logger.error(f"Cleanup failed in {output_dir}: {e}")

class YoutubeProvider(DownloadProvider):
    name = "yt_dlp"

    def _prepare_cookies(self) -> str | None:
        """Download cookies from storage to a temporary file. Returns file path or None."""
        from app.services.storage_service import storage_service
        import tempfile
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as temp_cookies:
                temp_cookies_path = temp_cookies.name
            
            storage_service.download_file("secrets/youtube/cookies.txt", temp_cookies_path)
            return temp_cookies_path
        except Exception as e:
            logger.debug(f"Cookies not available or failed to download: {e}")
            if 'temp_cookies_path' in locals() and os.path.exists(temp_cookies_path):
                os.remove(temp_cookies_path)
            return None

    def _cleanup_cookies(self, file_path: str | None):
        """Remove the temporary cookies file."""
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                logger.warning(f"Failed to remove temp cookies file {file_path}: {e}")

    def _get_cmd(self, url: str, output_template: str, cookies_file: str | None) -> list[str]:
        cmd = [
            "yt-dlp",
            "--js-runtimes", "node",
            "-f", "bestaudio",
            "-x",
            "--audio-format", "wav",
            "-o", output_template,
        ]
        
        if cookies_file and os.path.exists(cookies_file):
            cmd.extend(["--cookies", cookies_file])
            
        cmd.append(url)
        return cmd

    async def _run_process(self, cmd: list[str], timeout: int) -> tuple[int, str, str]:
        """Run process with timeout and graceful termination."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=os.setsid  # Important for process group termination
        )
        
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
            return process.returncode, stdout_bytes.decode(), stderr_bytes.decode()
        except asyncio.TimeoutError:
            logger.warning("yt-dlp process timed out. Sending SIGTERM...")
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                await asyncio.wait_for(process.communicate(), timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("yt-dlp ignored SIGTERM. Sending SIGKILL...")
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
            except ProcessLookupError:
                pass
            
            return -1, "", "TimeoutError: yt-dlp execution exceeded time limit."

    async def _check_limits(self, url: str, cookies_file: str | None) -> str | None:
        """Fetch metadata and check limits. Returns error message if rejected, None if allowed."""
        cmd = ["yt-dlp", "--js-runtimes", "node", "--dump-json"]
        
        if cookies_file and os.path.exists(cookies_file):
            cmd.extend(["--cookies", cookies_file])
            
        cmd.append(url)
        
        returncode, stdout, _ = await self._run_process(cmd, timeout=60)
        if returncode != 0:
            return None
            
        try:
            metadata = json.loads(stdout)
            filesize = metadata.get("filesize") or metadata.get("filesize_approx") or 0
            duration = metadata.get("duration") or 0
            
            max_size_mb = int(os.getenv("MAX_DOWNLOAD_SIZE_MB", "2048"))
            max_duration_sec = int(os.getenv("MAX_VIDEO_DURATION_SECONDS", "36000"))
            
            if filesize > max_size_mb * 1024 * 1024:
                return f"[LimitExceededError] File size {filesize / (1024*1024):.2f}MB exceeds limit of {max_size_mb}MB"
                
            if duration > max_duration_sec:
                return f"[LimitExceededError] Duration {duration}s exceeds limit of {max_duration_sec}s"
                
        except Exception as e:
            logger.warning(f"Failed to parse yt-dlp metadata: {e}")
            
        return None
            
    async def download(self, url: str, output_dir: str) -> DownloadResult:
        start_time = time.time()
        
        # Download cookies for this job
        cookies_file = self._prepare_cookies()
        
        try:
            # Check metadata limits first
            limit_error = await self._check_limits(url, cookies_file)
            if limit_error:
                logger.error(f"Download rejected: {limit_error}")
                return DownloadResult(
                    success=False,
                    error=limit_error,
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            output_template = os.path.join(output_dir, "%(id)s.%(ext)s")
            cmd = self._get_cmd(url, output_template, cookies_file)
            
            max_retries = int(os.getenv("YTDLP_MAX_RETRIES", "3"))
            timeout = int(os.getenv("YTDLP_TIMEOUT_SECONDS", "1800"))
            
            attempt = 1
            last_error_category = "Unknown"
            last_error_msg = ""
            
            while attempt <= max_retries:
                logger.info(f"Downloading from YouTube (Attempt {attempt}/{max_retries}): {url}")
                
                # Ensure clean state before each attempt
                cleanup_directory(output_dir)
                
                returncode, stdout, stderr = await self._run_process(cmd, timeout)
                
                if returncode == 0:
                    # Find the downloaded file
                    files = os.listdir(output_dir)
                    wav_files = [f for f in files if f.endswith(".wav")]
                    
                    if wav_files:
                        duration_ms = int((time.time() - start_time) * 1000)
                        file_path = os.path.join(output_dir, wav_files[0])
                        return DownloadResult(
                            success=True,
                            file_path=file_path,
                            file_size=os.path.getsize(file_path),
                            duration_ms=duration_ms,
                            content_type="audio/wav",
                            original_filename=wav_files[0]
                        )
                    else:
                        stderr = "No wav file found after successful yt-dlp execution."
                
                # If we reach here, it's a failure
                error_category, should_retry = classify_error(stderr)
                if "TimeoutError" in stderr:
                    error_category = "TimeoutError"
                    should_retry = True
                    
                last_error_category = error_category
                last_error_msg = stderr.strip()
                
                logger.error(f"Attempt {attempt} failed: [{error_category}] {last_error_msg}")
                
                if not should_retry:
                    logger.error(f"Fatal error ({error_category}). Aborting retries.")
                    break
                    
                attempt += 1
                if attempt <= max_retries:
                    backoff_time = 2 ** attempt
                    logger.info(f"Backing off for {backoff_time}s before next attempt...")
                    await asyncio.sleep(backoff_time)
                    
            # All attempts exhausted or fatal error
            cleanup_directory(output_dir)
            duration_ms = int((time.time() - start_time) * 1000)
            formatted_error = f"[{last_error_category}] {last_error_msg}"
            
            return DownloadResult(
                success=False, 
                error=formatted_error, 
                duration_ms=duration_ms
            )
        finally:
            self._cleanup_cookies(cookies_file)
