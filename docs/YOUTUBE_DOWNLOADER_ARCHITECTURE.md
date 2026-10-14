# YouTube Downloader Architecture (Source Worker)

This document describes the design and behavior of the YouTube downloader pipeline located in `services/source-worker`. The system has been fortified to operate reliably against YouTube's anti-bot measures, network instability, and system crashes, optimized for a single-worker environment.

## 1. Environment Configuration
The behavior of the downloader is controlled via the following environment variables:

| Variable | Description | Default |
| -------- | ----------- | ------- |
| `YT_DLP_VERSION` | Fixed version of yt-dlp to ensure reproducible environments. | `2026.8.19` |
| `YOUTUBE_COOKIES_FILE` | Absolute path to a valid `cookies.txt` file (Netscape format) mounted into the container to bypass IP blocks. | `None` |
| `YTDLP_TIMEOUT_SECONDS` | Maximum allowed duration for a single download attempt before forcefully killing the process. | `1800` |
| `YTDLP_MAX_RETRIES` | Maximum number of exponential backoff retry attempts for transient errors (e.g., network timeout). | `3` |
| `JOB_STALE_TIMEOUT_SECONDS` | Maximum allowed age of a job in the `DOWNLOADING` state before it is considered stuck and recovered. | `7200` |
| `MAX_DOWNLOAD_SIZE_MB` | Maximum allowed filesize for a download (in MB). Rejected via metadata check before download starts. | `2048` |
| `MAX_VIDEO_DURATION_SECONDS` | Maximum allowed duration for a video (in seconds). Rejected via metadata check before download starts. | `36000` |

## 2. Job State Machine
A download job transitions through the following lifecycle states in the `sources` PostgreSQL table:

```text
PENDING -> DOWNLOADING -> UPLOADING -> COMPLETED
   \          |              |
    \         |              |
     ------------------------> FAILED (On fatal error or max retries)
```
*Note: Any job stuck in `DOWNLOADING` or `UPLOADING` beyond `JOB_STALE_TIMEOUT_SECONDS` will be forcefully recovered to `PENDING` up to 3 times, after which it transitions to `FAILED`.*

## 3. Storage Lifecycle
1. **Local Temp Creation:** `yt-dlp` creates a `.part` and `.ytdl` file in `/tmp/downloads/{source_id}/`.
2. **Local Temp Completion:** `yt-dlp` converts the finished file to a `.wav`.
3. **Idempotency & Processing:** `job_handler` reads the `.wav`.
4. **Upload to MinIO:** The file is streamed to the S3 bucket.
5. **Cleanup:** Regardless of success or failure, the `/tmp/downloads/{source_id}` directory is forcefully purged of all artifacts to prevent disk exhaustion.

## 4. Error Classification & Retry Policy
Errors are parsed from `stderr` and prepended to the final failure message as structured strings (e.g., `[NetworkError] Connection timed out`).

- **Retriable Errors (Exponential Backoff applied):**
  - `NetworkError` (Timeouts, connection resets)
  - `Http5xxError` (Internal Server Errors from YouTube)
  - `TimeoutError` (Process took longer than `YTDLP_TIMEOUT_SECONDS`)

- **Fatal Errors (Fail Fast, immediately marked as FAILED):**
  - `BotDetectionError` (YouTube asks to confirm you're not a bot)
  - `PrivateVideoError` (Video requires authentication)
  - `UnavailableVideoError` (Video deleted or geo-blocked)
  - `InvalidURL` (Malformed input)
  - `LimitExceededError` (Video exceeds `MAX_DOWNLOAD_SIZE_MB` or `MAX_VIDEO_DURATION_SECONDS`)

## 5. Startup Diagnostics
Upon booting, the `source-worker` automatically verifies the presence and version of:
- `yt-dlp`
- `node` (Required for evaluating YouTube's anti-bot JS challenges)
- `ffmpeg` (Required for audio extraction)
- Cookies File Availability

## 6. Process Termination Safety
If `yt-dlp` hangs infinitely, the system will:
1. Issue a `SIGTERM` (Request graceful exit).
2. Wait up to 5 seconds.
3. Issue a `SIGKILL` (Force destroy) to prevent zombie processes from hanging the worker thread permanently.
