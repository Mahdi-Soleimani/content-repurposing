# Architecture & Persistence Rules

This document outlines the core persistence strategy and data flow for the Content Repurposing Platform. Any agent or developer working on this project MUST strictly adhere to these rules.

## Core Principles

1. **POSTGRESQL IS THE SINGLE SOURCE OF TRUTH.**
2. **S3/OBJECT STORAGE STORES ONLY BINARY/LARGE FILES.**
3. **N8N IS AN ORCHESTRATOR, NOT THE SYSTEM OF RECORD.**
4. **EVERY FINAL AI OUTPUT MUST BE PERSISTED IN `generated_outputs`.**
5. **EVERY GENERATED BINARY FILE MUST BE STORED IN OBJECT STORAGE AND REFERENCED BY `storage_key` IN THE DATABASE.**
6. **FRONTEND MUST REHYDRATE PROJECT STATE FROM THE BACKEND/DATABASE.**
7. **DO NOT RELY ON N8N EXECUTION DATA AS PERSISTENT APPLICATION STATE.**

---

## Database Schema Roles

The PostgreSQL database is organized into the following conceptual domains:

### 1. INPUT LAYER
- **`sources`**: Represents any raw input from the user (Text, URL, or metadata about an uploaded media file).
- **`uploads`**: Tracks the lifecycle of a direct file upload (e.g., UPLOADING, QUEUED, COMPLETED).
- **`media`**: Stores rich metadata about actual media files (videos, audios) located in Object Storage (duration, resolution, etc.).

### 2. AI CORE / ANALYSIS
- **`transcripts`**: Stores the raw text extracted from media or fetched from URLs, including timestamped segments.
- **`canonical_contents`**: The "Brain" of the content. After initial processing, LLMs extract a standardized format (Title, Summary, Key Points, Tone, Audience) and store it here. This table acts as the universal source for all generation tasks.

### 3. OUTPUT LAYER
- **`generation_jobs`**: A record of a user's request to generate content (e.g., "Generate 3 Telegram posts and 1 Article").
- **`generated_outputs`**: The final destination for every piece of content created by the AI. Text content is stored directly in a `content` JSONB field (or text field). If the output includes an image (like an Infographic), the image is saved to MinIO, and its path is saved as `storage_key` here.

### 4. SYSTEM & PIPELINE
- **`webhook_events`**: Tracks events sent to n8n for processing.
- **`jobs`**: Internal tracking for background tasks.

---

## Storage Convention

MinIO / Arvan S3 is used strictly for binaries. All files are organized by Project UUID:

```text
projects/
└── {project_uuid}/
    ├── uploads/
    │   ├── videos/
    │   └── audios/
    ├── processed/
    │   ├── audio/
    │   └── transcript/
    └── generated/
        ├── telegram/
        ├── articles/
        ├── carousel/
        ├── stories/
        └── infographic/
```

## Deletion Protocol

When a Project is deleted, two things must happen in coordination:
1. **Database Cleanup**: Delete the project record from PostgreSQL (cascading deletes will wipe `sources`, `transcripts`, `canonical_contents`, and `generated_outputs`).
2. **Storage Cleanup**: Delete all objects in MinIO prefixed with `projects/{project_uuid}/`.
