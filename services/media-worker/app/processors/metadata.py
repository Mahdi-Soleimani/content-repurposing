"""Media metadata extraction using FFprobe."""

import asyncio
import json


class MetadataExtractor:
    """Extract metadata from media files using FFprobe."""

    async def extract(self, file_path: str) -> dict:
        """Extract comprehensive metadata from a media file."""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
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
            probe_data = json.loads(stdout.decode())
        except json.JSONDecodeError:
            return {"status": "error", "error": "Failed to parse FFprobe output"}

        # Extract key info
        format_info = probe_data.get("format", {})
        streams = probe_data.get("streams", [])

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        result = {
            "status": "success",
            "duration": float(format_info.get("duration", 0)),
            "size": int(format_info.get("size", 0)),
            "format_name": format_info.get("format_name", ""),
            "bit_rate": int(format_info.get("bit_rate", 0)),
        }

        if video_stream:
            result["video"] = {
                "codec": video_stream.get("codec_name", ""),
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "fps": video_stream.get("r_frame_rate", ""),
                "resolution": f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
            }

        if audio_stream:
            result["audio"] = {
                "codec": audio_stream.get("codec_name", ""),
                "sample_rate": audio_stream.get("sample_rate", ""),
                "channels": audio_stream.get("channels"),
            }

        return result
