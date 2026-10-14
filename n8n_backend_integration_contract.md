# 1. System Overview

In the Content Repurposing Platform architecture, n8n acts as the central orchestration engine that connects the backend API with external AI services (like OpenAI/Avalai) and automates the content generation workflows.

- **What triggers n8n:** The FastAPI backend triggers n8n via webhooks whenever a user submits text, submits a URL, completes a media upload, or explicitly requests content generation from a transcript.
- **What data n8n receives:** n8n receives event identifiers, source text/transcripts, project metadata, and specific output requirements (e.g., "generate 1 LinkedIn post and 2 Tweets").
- **What data n8n produces:** n8n produces canonical representations (summaries/core ideas) of transcripts, specific platform-tailored content (tweets, blogs, captions), and handles image/media generation via AI.
- **Which services communicate with n8n:** 
  - **FastAPI (`api`):** Sends triggers via webhooks and receives updates via internal callback endpoints.
  - **PostgreSQL (`postgres`):** n8n does not interact with the database directly. All interactions are securely routed through the FastAPI callbacks to maintain the database lifecycle.

## Architecture Diagram

```
User (Frontend)
   |
   | (Uploads Media / Submits URL / Requests Generation)
   v
FastAPI (Backend)
   |
   | (Webhook Event: text.submitted / url.submitted / job.created / generation.requested)
   v
n8n (Webhook Node)
   |
   | (HTTP Requests to LLM APIs / Image Gen / Scrapers)
   v
AI Providers (OpenAI, Avalai, etc.)
   |
   | (Parsed AI Responses)
   v
n8n (HTTP Request Nodes)
   |
   | (Callbacks: POST /canonical, POST /outputs, PATCH /outputs, etc.)
   v
FastAPI (Backend)
   |
   | (ORM Operations)
   v
PostgreSQL (Database)
```

---

# 2. Complete n8n Entry Points

The backend triggers n8n using POST requests to the URLs defined in the `.env` file. These events are queued in the `webhook_events` table and dispatched asynchronously.

## Name: `text.submitted`

**Trigger location:**
- **File:** `services/api/app/routers/content.py`
- **Function:** `submit_text`
- **Line:** ~75

**HTTP Method:** `POST`

**URL format:** `N8N_WEBHOOK_URL` (e.g., `http://n8n:5678/webhook/content-uploaded`)

**Exact Request Headers:**
```
Content-Type: application/json
```

**Exact JSON Payload:**
```json
{
  "event_id": "uuid",
  "event": "text.submitted",
  "timestamp": "2026-09-07T07:39:23.000Z",
  "data": {
    "source_id": "uuid",
    "project_id": "uuid",
    "source_type": "text",
    "content": "Raw user inputted text here"
  }
}
```

**Field Explanations:**
- `event_id`: Unique identifier for the webhook attempt. Used for tracking retries.
- `event`: The event type string identifier (`text.submitted`).
- `timestamp`: ISO 8601 UTC timestamp.
- `data.source_id`: UUID of the newly created record in the `sources` table.
- `data.project_id`: UUID of the project this text belongs to.
- `data.content`: The actual text submitted by the user.

---

## Name: `url.submitted`

**Trigger location:**
- **File:** `services/api/app/routers/content.py`
- **Function:** `submit_url`
- **Line:** ~191

**HTTP Method:** `POST`

**URL format:** `N8N_WEBHOOK_URL`

**Exact Request Headers:**
```
Content-Type: application/json
```

**Exact JSON Payload:**
```json
{
  "event_id": "uuid",
  "event": "url.submitted",
  "timestamp": "2026-09-07T07:39:23.000Z",
  "data": {
    "source_id": "uuid",
    "project_id": "uuid",
    "source_type": "url",
    "platform": "youtube",
    "url": "https://youtube.com/watch?v=..."
  }
}
```

**Field Explanations:**
- `data.platform`: Pre-resolved by the backend (e.g., `"youtube"`, `"instagram"`).
- `data.url`: The exact URL the user provided.

---

## Name: `job.created` (File Uploaded)

**Trigger location:**
- **File:** `services/api/app/routers/uploads.py`
- **Function:** `complete_upload`
- **Line:** ~390

**HTTP Method:** `POST`

**URL format:** `N8N_WEBHOOK_URL`

**Exact Request Headers:**
```
Content-Type: application/json
```

**Exact JSON Payload:**
```json
{
  "event_id": "uuid",
  "event": "job.created",
  "timestamp": "2026-09-07T07:39:23.000Z",
  "data": {
    "upload": {
      "id": "uuid",
      "media_type": "video/mp4"
    },
    "job": {
      "id": "uuid"
    },
    "project_id": "uuid"
  }
}
```

**Field Explanations:**
- `data.upload.id`: The UUID of the file in the `uploads` table.
- `data.job.id`: The UUID of the `media_process` job queued in the `jobs` table (picked up by `media-worker`).

*(Note: n8n usually ignores this trigger in the content repurposing flow, as it waits for the `generation.requested` trigger after transcription is complete).*

---

## Name: `generation.requested`

**Trigger location:**
- **File:** `services/api/app/routers/generation.py`
- **Function:** `generate_content`
- **Line:** ~211

**HTTP Method:** `POST`

**URL format:** `N8N_GENERATION_WEBHOOK_URL` (falls back to `N8N_WEBHOOK_URL` if empty).

**Exact Request Headers:**
```
Content-Type: application/json
```

**Exact JSON Payload:**
```json
{
  "event_id": "uuid",
  "event": "generation.requested",
  "timestamp": "2026-09-07T07:39:23.000Z",
  "data": {
    "generation_job_id": "uuid",
    "project_id": "uuid",
    "transcript_id": "uuid",
    "transcript_text": "The full transcribed text goes here...",
    "requested_outputs": {
      "linkedin_post": 1,
      "tweet": 1
    }
  }
}
```

**Field Explanations:**
- `data.generation_job_id`: **CRITICAL**. UUID of the job in `generation_jobs`. Must be passed back in all callbacks.
- `data.transcript_text`: The full string text that the AI needs to process.
- `data.requested_outputs`: A dictionary of requested output types and the quantity (always split to `1` by the backend router before sending to n8n).

---

# 3. Complete n8n Callback Endpoints

These are the REST API endpoints n8n must call via the HTTP Request Node to update the system.

## Endpoint: Initialize Canonical Content

**Method:** `POST`
**URL:** `http://api:8000/api/projects/{project_id}/canonical`
**Who calls it:** n8n

**Purpose:**
Saves the initial AI-generated summary/canonical representation of the transcript before generating specific outputs. Links the `generation_job` to this canonical content and sets the job to `PROCESSING`.

**Request body:**
```json
{
  "generation_job_id": "UUID_FROM_WEBHOOK",
  "content": {
    "canonical_representation": {
      "title": "Extracted Title",
      "summary": "Core ideas..."
    }
  },
  "metadata": {
    "llm_used": "gpt-4o"
  }
}
```

**Database changes:**
- `INSERT INTO canonical_contents` (saves title, content, and metadata).
- `UPDATE generation_jobs` (sets `canonical_content_id`, `status = 'PROCESSING'`, `started_at = NOW()`).

**Expected response:**
```json
{
  "message": "Canonical content saved successfully",
  "id": "new_canonical_content_uuid"
}
```

---

## Endpoint: Create Generated Output

**Method:** `POST`
**URL:** `http://api:8000/api/projects/{project_id}/jobs/{generation_job_id}/outputs`
**Who calls it:** n8n

**Purpose:**
Initializes a new specific platform output (e.g., a Tweet or LinkedIn post). Automatically checks if all requested outputs for the job are completed, and if so, marks the `generation_job` as `COMPLETED`.

**Request body:**
```json
{
  "canonical_content_id": "UUID_FROM_CANONICAL_RESPONSE",
  "output_type": "tweet",
  "status": "processing",
  "title": "A catchy tweet",
  "content": "The actual tweet content here...",
  "metadata": {},
  "media": []
}
```

**Database changes:**
- `INSERT INTO generated_outputs`.
- Conditionally `UPDATE generation_jobs SET status = 'COMPLETED'` if all requested outputs are fulfilled.

**Expected response:**
```json
{
  "message": "Output initialized successfully",
  "output_id": "uuid",
  "generation_job_id": "uuid",
  "status": "processing",
  "progress": {
    "completed": 1,
    "total": 2
  }
}
```

---

## Endpoint: Update Output Incrementally

**Method:** `PATCH`
**URL:** `http://api:8000/api/projects/{project_id}/jobs/{generation_job_id}/outputs/{output_id}`
**Who calls it:** n8n

**Purpose:**
Updates an existing output. Useful for multi-step generations like carousels (adding slides incrementally) or changing status from `processing` to `draft`.

**Request body:**
```json
{
  "status": "draft",
  "content": "Updated content...",
  "metadata": {
    "slide": {
      "index": 1,
      "text": "Slide 1 text",
      "image_url": "s3_path"
    }
  }
}
```

**Database changes:**
- `UPDATE generated_outputs SET ... WHERE id = {output_id}` (merges metadata intelligently if `slide` key is present).

**Expected response:**
```json
{
  "message": "Output updated successfully"
}
```

---

## Endpoint: Upload Generated Media

**Method:** `POST`
**URL:** `http://api:8000/api/projects/{project_id}/jobs/{generation_job_id}/outputs/media`
**Who calls it:** n8n

**Purpose:**
Allows n8n to upload an image generated by an AI (e.g., DALL-E) directly into the platform's S3/MinIO storage. The returned `storage_path` is then used in the `PATCH` output metadata.

**Request body:**
`multipart/form-data` containing a `file` field.

**Database changes:**
None directly (uploads to S3).

**Expected response:**
```json
{
  "storage_path": "projects/uuid/jobs/uuid/outputs/media/filename.jpg"
}
```

---

## Endpoint: Fail a Generation Job

**Method:** `POST`
**URL:** `http://api:8000/api/projects/{project_id}/jobs/{generation_job_id}/fail`
**Who calls it:** n8n (Error trigger node)

**Purpose:**
If the n8n workflow encounters an unrecoverable error (e.g., LLM API down), it must call this to inform the backend.

**Request body:**
```json
{
  "error_message": "OpenAI API timeout"
}
```

**Database changes:**
- `UPDATE generation_jobs SET status = 'FAILED', error_message = '...', completed_at = NOW()`.

**Expected response:**
```json
{
  "message": "Job marked as failed"
}
```

---

# 4. Complete n8n Workflow Requirements

Based on the callbacks and triggers, you need to build the following primary workflows.

## Workflow 1: Content Generation Pipeline

**Trigger:**
- **Webhook Node** listening to `POST` on `N8N_GENERATION_WEBHOOK_URL`.

**Input:**
- Payload containing `transcript_text`, `generation_job_id`, `project_id`, and `requested_outputs`.

**Steps Required:**

1. **Webhook Node:** Receives the `generation.requested` payload.
2. **AI / LLM Node (Canonical Extraction):**
   - Inputs the `transcript_text`.
   - Prompt: "Analyze this text, extract a title and a comprehensive summary."
   - Output format: JSON.
3. **HTTP Request Node (Callback Canonical):**
   - `POST http://api:8000/api/projects/{{ $json.body.data.project_id }}/canonical`
   - Payload: Passes the canonical JSON and `generation_job_id`.
   - Extracts `canonical_id` from the response.
4. **Switch / Router Node:**
   - Evaluates `{{ Object.keys($json.body.data.requested_outputs)[0] }}`.
   - Routes to specific generation branches (e.g., Twitter, LinkedIn, Carousel).
5. **AI / LLM Node (Output Generation):**
   - Prompt: "Based on the canonical summary, generate a [platform] post."
6. **HTTP Request Node (Callback Output Creation):**
   - `POST http://api:8000/api/projects/{{ project_id }}/jobs/{{ generation_job_id }}/outputs`
   - Payload: Status `draft`, canonical ID, and the generated content.
7. **Error Trigger Node (Global):**
   - Catches any failures.
   - `POST http://api:8000/api/projects/{{ project_id }}/jobs/{{ generation_job_id }}/fail`
   - Payload: Error message.

---

## Workflow 2: Source Ingestion (Optional/Future)

**Trigger:**
- **Webhook Node** listening to `POST` on `N8N_WEBHOOK_URL`.

**Input:**
- Payload containing `url.submitted` or `text.submitted`.

**Steps Required:**
- (Currently, the backend has internal Python workers handling media download and transcription. However, if you plan to use n8n for scraping, this is where you would hook in a scraper node based on the `url.submitted` event).

---

# 5. Database Lifecycle Mapping

1. **Source Submission:** User submits a URL or Text (`sources` table).
2. **Upload/Download:** Python workers download video/audio (`uploads` & `media` tables).
3. **Transcription:** Background job transcribes media to text (`transcripts` table -> `status = 'READY'`).
4. **User Initiates Generation:** User clicks "Generate".
5. **Job Created:** Backend creates `generation_jobs` record (`status = 'PENDING'`).
6. **n8n Triggered:** Backend fires webhook to n8n.
7. **Canonical Stage:** n8n generates core ideas and POSTs to `/canonical`. 
   - `canonical_contents` record created.
   - `generation_jobs` `status` -> `PROCESSING`.
8. **Outputs Stage:** n8n generates platform specific content and POSTs to `/outputs`.
   - `generated_outputs` record created (`status = 'draft'`).
   - If output quota is met, backend auto-updates `generation_jobs` `status` -> `COMPLETED`.

---

# 6. Error Handling Contract

- **Failure Recognition:** n8n must proactively report unrecoverable errors. If n8n fails silently, the `generation_jobs` record remains stuck in `PENDING` or `PROCESSING` indefinitely.
- **Reporting Endpoint:** `POST /api/projects/{id}/jobs/{job_id}/fail`
- **Payload Format:** `{"error_message": "Description of error"}`
- **Retry Expectations:** The backend `webhook_events` table tracks failed webhook attempts to n8n, but n8n is responsible for handling retries to LLMs (using n8n's built-in retry settings on HTTP/LLM nodes).
- **Status Values Lifecycle:**
  - Job: `PENDING` -> `PROCESSING` -> `COMPLETED` | `FAILED`
  - Output: `processing` -> `draft` -> `reviewed` -> `approved` -> `published`

---

# 7. Authentication and Security

- **Network Security:** Because n8n and the FastAPI backend share a Docker network, n8n addresses the backend via internal DNS: `http://api:8000`. The backend addresses n8n via `http://n8n:5678`.
- **API Keys:** Currently, the internal callback endpoints do not enforce strict JWT/API key validation (they rely on UUID unpredictability and internal Docker network isolation).
- **Secrets Management:** LLM API keys (OpenAI, Avalai) should be configured inside n8n's Credentials manager, NOT hardcoded in nodes.

---

# 8. Environment Variables Required for n8n

These must be present in the backend `.env` to route correctly to n8n:

| Variable | Purpose | Used by |
|----------|---------|---------|
| `N8N_WEBHOOK_URL` | Default target for `text` and `url` events. | Backend FastAPI |
| `N8N_GENERATION_WEBHOOK_URL` | Explicit target for `generation.requested`. | Backend FastAPI |

*Note: In n8n, you must configure your Production URL environment variable (`WEBHOOK_URL`) so that n8n generates the correct URLs for its webhook nodes.*

---

# 9. Final n8n Rebuild Checklist

To manually recreate the lost workflows, follow this sequence exactly:

- [ ] **1. Create Generation Webhook:** In n8n, create a Webhook Node listening to `POST`. Set the path to match the UUID in your `.env`'s `N8N_GENERATION_WEBHOOK_URL` (e.g., `6114b91d-702b-4f47-9ae2-657a08ecd6bf`).
- [ ] **2. Configure AI Credentials:** Add your OpenAI / Avalai credentials to n8n's global credentials store.
- [ ] **3. Implement Canonical Extraction:** Add an LLM node connected to the webhook. Extract `{{ $json.body.data.transcript_text }}` into a structured JSON summary.
- [ ] **4. Build Canonical Callback:** Add an HTTP Request Node. Method: `POST`. URL: `http://api:8000/api/projects/{{ $json.body.data.project_id }}/canonical`. Map the generated summary to the payload.
- [ ] **5. Implement Routing Logic:** Use a Switch node to read `{{ Object.keys($json.body.data.requested_outputs) }}` and branch to different platform generators (Twitter, LinkedIn).
- [ ] **6. Build Output Generation:** Add LLM nodes for each branch to generate the final text.
- [ ] **7. Build Output Callback:** Add HTTP Request Nodes to post back to `http://api:8000/api/projects/{{ project_id }}/jobs/{{ generation_job_id }}/outputs`.
- [ ] **8. Build Error Handler:** Create an Error Trigger workflow that catches failures and POSTs the error message to `http://api:8000/api/projects/{{ project_id }}/jobs/{{ generation_job_id }}/fail`.
- [ ] **9. Test E2E:** Go to your frontend UI, submit text, and click Generate to fire the webhook and verify database state transitions.
