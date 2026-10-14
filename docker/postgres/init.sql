-- ============================================================
-- Content Repurposing Platform — Database Schema
-- ============================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ──────────────────────────────────────────────
-- 2. projects
-- ──────────────────────────────────────────────
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    settings JSONB DEFAULT '{}',
    stt_provider VARCHAR(50) DEFAULT 'shenava' CHECK (stt_provider IN ('shenava', 'avalai')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_projects_status ON projects(status);

-- ──────────────────────────────────────────────
-- 3. sources
-- ──────────────────────────────────────────────
CREATE TABLE sources (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,          -- 'text', 'url', 'media'
    source_url TEXT,                            -- URL if applicable
    source_content TEXT,                        -- Raw text content
    original_filename VARCHAR(500),
    metadata JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'PENDING',
    downloader_used VARCHAR(50),
    retry_count INTEGER DEFAULT 0,
    error_code VARCHAR(100),
    error_message TEXT,
    platform VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sources_project_id ON sources(project_id);
CREATE INDEX idx_sources_source_type ON sources(source_type);

-- ──────────────────────────────────────────────
-- 3.5. uploads
-- ──────────────────────────────────────────────
CREATE TABLE uploads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    original_filename TEXT,
    object_key TEXT,
    content_type VARCHAR(100),
    file_size BIGINT,
    metadata JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'CREATED',
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_uploads_project_id ON uploads(project_id);
CREATE INDEX idx_uploads_source_id ON uploads(source_id);

-- ──────────────────────────────────────────────
-- 4. media
-- ──────────────────────────────────────────────
CREATE TABLE media (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    media_type VARCHAR(50) NOT NULL,           -- 'video', 'audio', 'image', 'document'
    object_key TEXT NOT NULL,                   -- S3/MinIO object key
    file_size BIGINT,
    mime_type VARCHAR(100),
    duration_seconds FLOAT,
    resolution VARCHAR(20),                    -- e.g. '1920x1080'
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_media_source_id ON media(source_id);
CREATE INDEX idx_media_project_id ON media(project_id);
CREATE INDEX idx_media_media_type ON media(media_type);

-- ──────────────────────────────────────────────
-- 4.5. downloads
-- ──────────────────────────────────────────────
CREATE TABLE downloads (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,        -- 'parth_dl', 'instaloader', 'yt_dlp'
    status VARCHAR(50) NOT NULL,          -- 'SUCCESS', 'FAILED'
    attempt_count INTEGER NOT NULL DEFAULT 1,
    error_message TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE INDEX idx_downloads_source_id ON downloads(source_id);

-- ──────────────────────────────────────────────
-- 5. transcripts
-- ──────────────────────────────────────────────
CREATE TABLE transcripts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    media_id UUID REFERENCES media(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    language VARCHAR(10) DEFAULT 'fa',
    full_text TEXT,
    segments JSONB DEFAULT '[]',               -- timestamped segments
    provider VARCHAR(50),                       -- 'openai', 'avalai'
    model VARCHAR(100),
    confidence FLOAT,
    content_status VARCHAR(50) DEFAULT 'READY',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_transcripts_media_id ON transcripts(media_id);
CREATE INDEX idx_transcripts_project_id ON transcripts(project_id);

-- ──────────────────────────────────────────────
-- 6. canonical_contents
-- ──────────────────────────────────────────────
CREATE TABLE canonical_contents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    transcript_id UUID REFERENCES transcripts(id) ON DELETE SET NULL,
    title VARCHAR(500),
    content TEXT NOT NULL,
    content_type VARCHAR(50) DEFAULT 'article', -- 'article', 'summary', 'notes'
    language VARCHAR(10) DEFAULT 'fa',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_canonical_contents_project_id ON canonical_contents(project_id);

-- ──────────────────────────────────────────────
-- 7. generated_outputs
-- ──────────────────────────────────────────────
CREATE TABLE generated_outputs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    canonical_content_id UUID NOT NULL REFERENCES canonical_contents(id) ON DELETE CASCADE,
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    generation_job_id UUID REFERENCES generation_jobs(id) ON DELETE CASCADE,
    output_type VARCHAR(50) NOT NULL,          -- 'tweet', 'linkedin_post', 'blog', 'caption', 'thread'
    platform VARCHAR(50),                       -- 'twitter', 'linkedin', 'instagram', 'telegram'
    title VARCHAR(500),
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    media JSONB DEFAULT '[]'::jsonb,
    status VARCHAR(50) DEFAULT 'draft',        -- 'draft', 'reviewed', 'approved', 'published'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_generated_outputs_canonical_id ON generated_outputs(canonical_content_id);
CREATE INDEX idx_generated_outputs_project_id ON generated_outputs(project_id);
CREATE INDEX idx_generated_outputs_status ON generated_outputs(status);



-- ──────────────────────────────────────────────
-- 10. generation_drafts
-- ──────────────────────────────────────────────
CREATE TABLE generation_drafts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    requested_outputs JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id)
);

-- ──────────────────────────────────────────────
-- 11. generation_jobs
-- ──────────────────────────────────────────────
CREATE TABLE generation_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    canonical_content_id UUID REFERENCES canonical_contents(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'PENDING',
    requested_outputs JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_message TEXT
);
CREATE INDEX idx_generation_jobs_project_id ON generation_jobs(project_id);

-- ──────────────────────────────────────────────
-- 12. jobs (Internal / Async Workers)
-- ──────────────────────────────────────────────
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE SET NULL,
    upload_id UUID REFERENCES uploads(id) ON DELETE CASCADE,
    job_type VARCHAR(100) NOT NULL,            -- 'media_process', 'transcription', 'content_generation', 'download'
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- 'pending', 'queued', 'processing', 'completed', 'failed', 'cancelled'
    provider VARCHAR(50),
    model VARCHAR(100),
    priority INTEGER DEFAULT 0,
    input_data JSONB DEFAULT '{}',
    output_data JSONB DEFAULT '{}',
    error_message TEXT,
    progress FLOAT DEFAULT 0,                  -- 0.0 to 1.0
    worker_id VARCHAR(100),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_jobs_project_id ON jobs(project_id);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_job_type ON jobs(job_type);
CREATE INDEX idx_jobs_priority_status ON jobs(priority DESC, created_at ASC) WHERE status = 'pending';

-- ──────────────────────────────────────────────
-- 12.5. webhook_events
-- ──────────────────────────────────────────────
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    upload_id UUID REFERENCES uploads(id) ON DELETE CASCADE,
    source_id UUID REFERENCES sources(id) ON DELETE CASCADE,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'PENDING',
    attempts INTEGER DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_webhook_events_status ON webhook_events(status);

-- ──────────────────────────────────────────────
-- 13. processing_usage
-- ──────────────────────────────────────────────
CREATE TABLE processing_usage (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE SET NULL,
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    duration_seconds FLOAT DEFAULT 0,
    audio_seconds FLOAT DEFAULT 0,
    input_size_bytes BIGINT DEFAULT 0,
    tokens_used INTEGER DEFAULT 0,
    cost FLOAT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_processing_usage_project_id ON processing_usage(project_id);
CREATE INDEX idx_processing_usage_job_id ON processing_usage(job_id);

-- ──────────────────────────────────────────────
-- Updated_at trigger function
-- ──────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply trigger to all tables with updated_at
CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_uploads_updated_at BEFORE UPDATE ON uploads FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_webhook_events_updated_at BEFORE UPDATE ON webhook_events FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_transcripts_updated_at BEFORE UPDATE ON transcripts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_canonical_contents_updated_at BEFORE UPDATE ON canonical_contents FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_generated_outputs_updated_at BEFORE UPDATE ON generated_outputs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jobs_updated_at BEFORE UPDATE ON jobs FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
CREATE TRIGGER update_generation_drafts_updated_at BEFORE UPDATE ON generation_drafts FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
