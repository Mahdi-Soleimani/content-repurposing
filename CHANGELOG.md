# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-14

### Added
- **Multi-Source Ingestion Engine**:
  - Direct media upload pipeline with client-side S3 presigned PUT and progress bar.
  - Fortified YouTube downloader with `yt-dlp`, anti-bot cookie authentication, and exponential backoff retry.
  - Multi-downloader Instagram fallback chain (`parth-dl` → `instaloader` → `yt-dlp`).
  - Direct text submission with automatic transcription record creation.
- **Dual-Engine Speech Recognition (STT)**:
  - Offline, on-device Persian speech recognition powered by Shenava Koochik v1.5 (RNNT FastConformer onnx via `sherpa-onnx`) with isolated `spawn` ProcessPool to prevent GIL blocking.
  - Cloud speech recognition via AvalAI API (`gpt-4o-transcribe` / `scribe_v2`) and OpenAI Whisper with timestamped segments.
  - Per-project speech provider toggle in workspace settings.
- **Media Processing Core**:
  - FFprobe metadata extraction (duration, format, resolution, audio channels).
  - FFmpeg 16 kHz Mono PCM audio normalization and automatic duration/size chunking.
- **Content Brain & Repurposing Pipeline**:
  - Canonical content extraction extracting unified titles, core summaries, and themes.
  - Platform-specific content generation (Website Articles, LinkedIn Posts, Twitter Threads, Telegram Posts, Instagram Captions & Multi-slide Carousels).
  - Visual n8n workflow integration contract with asynchronous PostgreSQL webhook event tracking and retry queue.
- **Modern Web Dashboard**:
  - Next.js workspace dashboard with dark mode UI, real-time polling, and project CRUD.
  - YouTube cookie management UI with automated connection health diagnostics.
  - Rich Markdown output preview with GitHub Flavored Markdown (GFM) and HTML rendering.
- **Infrastructure**:
  - Multi-container Docker Compose deployment (PostgreSQL, Redis, MinIO, n8n, FastAPI, Media Worker, Source Worker, Next.js Web, Caddy reverse proxy).
  - Automatic database schema initialization with cascading deletes and updated_at triggers.
