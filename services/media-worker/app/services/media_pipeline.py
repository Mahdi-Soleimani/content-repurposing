"""Media Processing Pipeline — Core Orchestration.

Wires together: Storage → FFmpeg → STT → PostgreSQL.

Flow:
  1. Download from MinIO
  2. ffprobe → detect media_type (video/audio)
  3. Insert into `media` table
  4. FFmpeg normalize → 16kHz Mono PCM WAV
  5. Chunk if > 25MB
  6. AvalAI STT
  7. Insert into `transcripts` table
  8. Update statuses
  9. Cleanup temp files
"""

import logging
import os
import shutil
import asyncio
import httpx
import uuid
from datetime import datetime
from pathlib import Path

from app.config import settings
from app.processors.ffmpeg_processor import FFmpegProcessor
from app.processors.metadata import MetadataExtractor
from app.services.storage_service import storage_service
from app.services.db_service import db_service
from app.services.transcription import ProviderFactory

logger = logging.getLogger(__name__)

async def _send_webhook_with_retry(webhook_url: str, payload: dict, max_retries: int = 3):
    if not webhook_url:
        logger.warning("No webhook URL configured for transcription.completed.")
        return

    async with httpx.AsyncClient() as client:
        for attempt in range(max_retries):
            try:
                response = await client.post(webhook_url, json=payload, timeout=10.0)
                if response.status_code in (200, 201, 202):
                    logger.info(f"✅ Webhook transcription.completed sent successfully (attempt {attempt + 1})")
                    return
                else:
                    logger.warning(f"⚠️ Webhook returned {response.status_code}: {response.text[:200]} (attempt {attempt + 1})")
            except Exception as e:
                logger.error(f"❌ Webhook send failed (attempt {attempt + 1}): {str(e)}")
            
            if attempt < max_retries - 1:
                sleep_time = 2 ** attempt
                logger.info(f"Retrying webhook in {sleep_time} seconds...")
                await asyncio.sleep(sleep_time)
        
        logger.error("❌ Webhook sending failed after all retries.")

ffmpeg = FFmpegProcessor()
metadata_extractor = MetadataExtractor()


class MediaPipeline:
    """Orchestrates the full media processing pipeline."""

    async def process(self, job_id: str) -> dict:
        """Run the full pipeline based on Job ID.

        Returns:
            {
                "status": "completed",
                "job_id": "...",
                "upload_id": "...",
                "source_id": "...",
                "media_id": "...",
                "transcript_id": "...",
                "media_type": "video",
                "duration_seconds": 1245.3,
                "language": "fa"
            }
        """
        temp_files = []  # Track files to cleanup
        job = await db_service.get_job(job_id)
        if not job:
            return {"status": "failed", "job_id": job_id, "error": "Job not found"}
            
        upload_id = str(job["upload_id"])
        
        upload = await db_service.get_upload_details(upload_id)
        if not upload:
            await db_service.update_job_status(job_id, "FAILED", error="Upload details not found")
            return {"status": "failed", "job_id": job_id, "error": "Upload details not found"}
            
        project_id = str(upload["project_id"])
        source_id = str(upload["source_id"])
        object_key = upload["object_key"]
        
        provider_name = job["provider"] or "shenava"

        try:
            # ──── 0. Idempotency Check ────
            existing = await db_service.get_existing_transcript(upload_id)
            if existing:
                logger.info(f"Transcript already exists for upload {upload_id}, returning existing result")
                await db_service.update_job_status(job_id, "COMPLETED")
                return {
                    "status": "completed",
                    "job_id": job_id,
                    "upload_id": upload_id,
                    "source_id": source_id,
                    "media_id": str(existing["media_id"]),
                    "transcript_id": str(existing["transcript_id"]),
                    "media_type": existing["media_type"],
                    "duration_seconds": existing.get("duration_seconds"),
                    "language": existing.get("language", "fa"),
                }

            # ──── 1. Update status → PROCESSING ────
            await db_service.update_upload_status(upload_id, "PROCESSING")
            await db_service.update_source_status(source_id, "PROCESSING")
            await db_service.update_job_status(job_id, "PROCESSING")

            # ──── 2. Download from MinIO ────
            local_filename = f"{upload_id}_{os.path.basename(object_key)}"
            local_path = storage_service.download_to_local(object_key, local_filename)
            temp_files.append(local_path)
            logger.info(f"Downloaded to {local_path}")

            # ──── 3. Detect media type via ffprobe ────
            probe_result = await metadata_extractor.extract(local_path)
            if probe_result.get("status") != "success":
                raise RuntimeError(f"ffprobe failed: {probe_result.get('error', 'unknown')}")

            has_video = "video" in probe_result
            has_audio = "audio" in probe_result
            media_type = "video" if has_video else "audio"
            duration = probe_result.get("duration", 0)
            file_size = probe_result.get("size", 0)

            video_info = probe_result.get("video", {})
            width = video_info.get("width")
            height = video_info.get("height")

            logger.info(f"Detected: {media_type}, duration={duration}s, size={file_size}")

            # ──── 4. Insert into `media` table ────
            media_id = await db_service.insert_media(
                project_id=project_id,
                source_id=source_id,
                upload_id=upload_id,
                media_type=media_type,
                storage_key=object_key,
                mime_type=probe_result.get("format_name"),
                duration_seconds=duration,
                width=width,
                height=height,
                size_bytes=file_size,
                metadata=probe_result,
            )

            # ──── 5. FFmpeg Normalize → 16kHz Mono PCM WAV ────
            normalize_result = await ffmpeg.extract_audio(
                input_path=local_path,
                output_format="wav",
                sample_rate=settings.CANONICAL_SAMPLE_RATE,
            )
            if normalize_result.get("status") != "success":
                raise RuntimeError(f"FFmpeg normalization failed: {normalize_result.get('error', 'unknown')}")

            wav_path = normalize_result["output_path"]
            temp_files.append(wav_path)
            wav_size = normalize_result.get("file_size", 0)
            logger.info(f"Normalized audio: {wav_path} ({wav_size} bytes)")

            # ──── 6. Chunk if needed ────
            max_size = settings.MAX_STT_FILE_SIZE_MB * 1024 * 1024
            audio_files_to_transcribe = []
            wav_size = os.path.getsize(wav_path)
            duration_sec = duration

            # Chunk if file is too large (API limit) OR too long (Local RAM limit for Shenava)
            if wav_size > max_size or duration_sec > settings.CHUNK_DURATION_SECONDS:
                logger.info(f"File needs chunking. Size: {wav_size/1024/1024:.2f}MB, Duration: {duration_sec:.1f}s")
                chunk_result = await ffmpeg.chunk_audio(
                    input_path=wav_path,
                    chunk_duration_seconds=settings.CHUNK_DURATION_SECONDS,
                )
                if chunk_result.get("status") != "success":
                    raise RuntimeError(f"Chunking failed: {chunk_result.get('error', 'unknown')}")

                audio_files_to_transcribe = chunk_result["chunk_paths"]
                temp_files.extend(audio_files_to_transcribe)
                # Also track the chunk directory
                chunk_dir = os.path.dirname(audio_files_to_transcribe[0]) if audio_files_to_transcribe else None
                if chunk_dir:
                    temp_files.append(chunk_dir)
                logger.info(f"Split into {len(audio_files_to_transcribe)} chunks")
            else:
                audio_files_to_transcribe = [wav_path]

            # ──── 7. STT Provider Setup ────
            all_text_parts = []
            all_segments = []
            segment_offset = 0.0
            result_language = "fa"
            
            stt_provider = ProviderFactory.create(provider_name)
            result_model = stt_provider.model

            for i, audio_file in enumerate(audio_files_to_transcribe):
                logger.info(f"Transcribing chunk {i + 1}/{len(audio_files_to_transcribe)}: {audio_file} using {stt_provider.name}")
                tr_result = await stt_provider.transcribe(
                    audio_path=audio_file,
                    language="fa",
                )
                all_text_parts.append(tr_result.text)
                result_language = tr_result.language

                # Offset segments for chunked files
                if tr_result.segments:
                    for seg in tr_result.segments:
                        all_segments.append({
                            "start": seg.get("start", 0) + segment_offset,
                            "end": seg.get("end", 0) + segment_offset,
                            "text": seg.get("text", ""),
                        })

                # Calculate offset for next chunk
                if tr_result.duration:
                    segment_offset += tr_result.duration
                elif len(audio_files_to_transcribe) > 1:
                    segment_offset += settings.CHUNK_DURATION_SECONDS

            final_text = " ".join(all_text_parts)
            logger.info(f"Transcription complete: {len(final_text)} chars, {len(all_segments)} segments")

            # ──── 8. Insert into `transcripts` table ────
            transcript_id = await db_service.insert_transcript(
                project_id=project_id,
                media_id=media_id,
                source_id=source_id,
                language=result_language,
                text=final_text,
                segments=all_segments if all_segments else None,
                duration_seconds=duration,
                provider=stt_provider.name,
                model=result_model,
                status="COMPLETED",
                metadata={
                    "chunk_count": len(audio_files_to_transcribe),
                    "original_file_size": file_size,
                    "wav_file_size": wav_size,
                },
            )

            # ──── 9. Update statuses ────
            await db_service.update_upload_status(upload_id, "COMPLETED")
            await db_service.update_source_status(source_id, "READY")
            await db_service.update_job_status(job_id, "COMPLETED", provider=stt_provider.name, model=result_model)
            
            # ──── 10. Record processing usage ────
            cost = 0.0
            tokens_used = 0
            if provider_name == "avalai":
                cost = (duration / 60) * 0.006  # Estimated cost: $0.006 per minute for whisper
            
            await db_service.insert_processing_usage(
                project_id=project_id,
                job_id=job_id,
                provider=stt_provider.name,
                model=result_model,
                duration_seconds=duration,
                audio_seconds=duration,
                input_size_bytes=file_size,
                tokens_used=tokens_used,
                cost=cost
            )

            # ──── 11. Trigger Async Webhook ────
            # Webhook removed as requested.

            logger.info(f"Pipeline complete: media={media_id}, transcript={transcript_id}")

            return {
                "status": "completed",
                "job_id": job_id,
                "upload_id": upload_id,
                "source_id": source_id,
                "media_id": media_id,
                "transcript_id": transcript_id,
                "media_type": media_type,
                "duration_seconds": duration,
                "language": result_language,
            }

        except Exception as e:
            logger.error(f"Pipeline failed for job {job_id}: {e}", exc_info=True)

            # Update statuses to FAILED
            try:
                if 'upload_id' in locals():
                    await db_service.update_upload_status(upload_id, "FAILED", error_message=str(e))
                if 'source_id' in locals():
                    await db_service.update_source_status(source_id, "FAILED")
                await db_service.update_job_status(job_id, "FAILED", error=str(e))
            except Exception as status_err:
                logger.error(f"Failed to update status after error: {status_err}")

            return {
                "status": "failed",
                "job_id": job_id,
                "upload_id": locals().get('upload_id'),
                "source_id": locals().get('source_id'),
                "error": str(e),
            }

        finally:
            # ──── 10. Cleanup temp files ────
            for f in temp_files:
                try:
                    if os.path.isdir(f):
                        shutil.rmtree(f)
                    elif os.path.isfile(f):
                        os.remove(f)
                except OSError:
                    pass


media_pipeline = MediaPipeline()
