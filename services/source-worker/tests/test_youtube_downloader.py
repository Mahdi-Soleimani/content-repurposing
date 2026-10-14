import os
import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from app.providers.youtube import YoutubeProvider, classify_error, cleanup_directory

@pytest.fixture
def provider():
    return YoutubeProvider()

def test_classify_error_bot_detection():
    category, retry = classify_error("Sign in to confirm you’re not a bot.")
    assert category == "BotDetectionError"
    assert not retry

def test_classify_error_private():
    category, retry = classify_error("This is a private video")
    assert category == "PrivateVideoError"
    assert not retry

def test_classify_error_network():
    category, retry = classify_error("network is unreachable")
    assert category == "NetworkError"
    assert retry

def test_cleanup_directory(tmp_path):
    # Create some dummy files
    p1 = tmp_path / "video.part"
    p1.write_text("data")
    p2 = tmp_path / "video.ytdl"
    p2.write_text("data")
    p3 = tmp_path / "video.temp"
    p3.write_text("data")
    p4 = tmp_path / "video.wav"
    p4.write_text("data")
    p5 = tmp_path / "video.txt"
    p5.write_text("data")
    
    cleanup_directory(str(tmp_path))
    
    # Verify cleanup
    assert not p1.exists()
    assert not p2.exists()
    assert not p3.exists()
    assert not p4.exists()
    assert p5.exists()  # .txt should not be cleaned up

def test_download_success(provider, tmp_path):
    with patch("app.providers.youtube.YoutubeProvider._check_limits", return_value=None), \
         patch("app.providers.youtube.YoutubeProvider._prepare_cookies", return_value=None), \
         patch("app.providers.youtube.YoutubeProvider._run_process") as mock_run_process:
        async def fake_run_process(*args, **kwargs):
            # Simulate yt-dlp creating the wav file after cleanup
            wav_file = tmp_path / "test.wav"
            wav_file.write_text("data")
            return 0, "", ""
            
        mock_run_process.side_effect = fake_run_process
        
        result = asyncio.run(provider.download("http://fake.url", str(tmp_path)))
        assert result.success
        assert result.file_path == str(tmp_path / "test.wav")

def test_download_bot_detection_no_retry(provider, tmp_path):
    with patch("app.providers.youtube.YoutubeProvider._check_limits", return_value=None), \
         patch("app.providers.youtube.YoutubeProvider._prepare_cookies", return_value=None), \
         patch("app.providers.youtube.YoutubeProvider._run_process") as mock_run_process:
        mock_run_process.return_value = (1, "", "Sign in to confirm you’re not a bot.")
        
        result = asyncio.run(provider.download("http://fake.url", str(tmp_path)))
        assert not result.success
        assert "[BotDetectionError]" in result.error
        # Should only attempt once because it's a fatal error
        assert mock_run_process.call_count == 1

def test_download_network_retry_exhausted(provider, tmp_path):
    with patch("app.providers.youtube.YoutubeProvider._check_limits", return_value=None), \
         patch("app.providers.youtube.YoutubeProvider._prepare_cookies", return_value=None), \
         patch("app.providers.youtube.YoutubeProvider._run_process") as mock_run_process, \
         patch.object(asyncio, "sleep", new_callable=AsyncMock):
        mock_run_process.return_value = (1, "", "network timeout")
        os.environ["YTDLP_MAX_RETRIES"] = "2"
        result = asyncio.run(provider.download("http://fake.url", str(tmp_path)))
        
        assert not result.success
        assert "[NetworkError]" in result.error
        # Should attempt exactly 2 times
        assert mock_run_process.call_count == 2
