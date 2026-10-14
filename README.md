<p align="center">
  <img src="docs/assets/banner.svg" alt="Content Repurposing Platform Banner" width="100%" />
</p>

<p align="center">
  <strong>Automated multimodal content transformation engine. Convert long-form video, podcasts, YouTube, and Instagram media into high-impact social media assets, articles, and carousels with visual workflow orchestration.</strong>
</p>

<p align="center">
  <a href="README.md"><strong>English</strong></a> •
  <a href="README.fa.md"><strong>فارسی</strong></a>
</p>

<p align="center">
  <a href="https://github.com/Mahdi-Soleimani/content-repurposing/actions/workflows/ci.yml">
    <img src="https://github.com/Mahdi-Soleimani/content-repurposing/actions/workflows/ci.yml/badge.svg" alt="CI Status" />
  </a>
  <img src="https://img.shields.io/badge/license-MIT-blue.svg?style=flat-square" alt="MIT License" />
  <img src="https://img.shields.io/badge/Python-3.12-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python 3.12" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688.svg?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/Next.js-15-black.svg?style=flat-square&logo=next.js&logoColor=white" alt="Next.js" />
  <img src="https://img.shields.io/badge/Docker-Compose-2496ED.svg?style=flat-square&logo=docker&logoColor=white" alt="Docker Compose" />
  <img src="https://img.shields.io/badge/n8n-Orchestration-EA4B71.svg?style=flat-square&logo=n8n&logoColor=white" alt="n8n" />
  <img src="https://img.shields.io/badge/sherpa--onnx-Offline%20ASR-4B5563.svg?style=flat-square" alt="Offline ASR" />
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=flat-square" alt="PRs Welcome" />
</p>

---

## 📑 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [System Architecture](#-system-architecture)
- [Tech Stack](#-tech-stack)
- [Screenshots & Walkthrough](#-screenshots--walkthrough)
- [Value Proposition & Use Cases](#-value-proposition--use-cases)
- [Quick Start](#-quick-start)
  - [Prerequisites](#prerequisites)
  - [Step-by-Step Installation](#step-by-step-installation)
- [Environment Configuration](#-environment-configuration)
- [Production Deployment Guide](#-production-deployment-guide)
- [Testing](#-testing)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [Security](#-security)
- [License](#-license)
- [Authors & Acknowledgments](#-authors--acknowledgments)

---

## 🌟 Overview

Creating content is only half the battle. To maximize reach, every podcast, webinar, interview, or tutorial must be repurposed into multiple formats tailored for specific platforms: in-depth articles for websites, punchy threads for Twitter/X, authoritative thought-leadership posts for LinkedIn, quick updates for Telegram channels, and visual multi-slide carousels for Instagram.

Doing this manually requires hours of listening, transcription, summarization, copywriting, and formatting.

**Content Repurposing Platform (CRP)** is a full-stack, enterprise-grade open-source system that automates this entire pipeline:
1. **Ingests** media via direct uploads, resilient YouTube downloading (with anti-bot cookie support), Instagram fallback chains, or raw text.
2. **Normalizes & Transcribes** speech using either **100% offline, on-device Persian ASR** (via Shenava FastConformer ONNX) or **cloud AI** (AvalAI / OpenAI Whisper) with precise timestamps.
3. **Extracts Canonical Knowledge**: Distills core insights, structure, key quotes, and audience tone into a single "Brain" record.
4. **Repurposes & Publishes**: Generates multi-platform assets asynchronously via visual **n8n** workflows and returns formatted outputs to a sleek dashboard.

---

## 📸 Screenshots Gallery

| **Project Dashboard** | **Project Workspace & Sources** |
|:---:|:---:|
| ![Project Dashboard](docs/screenshots/01-dashboard.png) | ![Workspace & Sources](docs/screenshots/02-workspace.png) |
| *Multi-project dashboard with status badges and quick creation* | *Unified workspace managing inputs, media pipelines, and outputs* |

| **YouTube Anti-Bot & Cookies Settings** | **Multi-Format Content Generation** |
|:---:|:---:|
| ![YouTube Settings](docs/screenshots/03-youtube-settings.png) | ![Content Generation](docs/screenshots/04-outputs-preview.png) |
| *Session cookie manager to bypass YouTube bot detection* | *On-demand output selector (Articles, Telegram, Carousel, LinkedIn)* |

---

## ✨ Key Features

### 📥 1. Multi-Modal Ingestion
- **Direct Large-File Uploads**: Uses presigned S3/MinIO PUT URLs to upload multi-gigabyte videos and audios directly from browser memory with progress indicators.
- **Defensive YouTube Pipeline**: Powered by `yt-dlp` with configurable timeout groups (`SIGTERM`/`SIGKILL`), exponential backoff retry, and a built-in session health checker.
- **YouTube Cookie Session Manager**: Upload your browser `cookies.txt` via UI to safely bypass YouTube's *"Sign in to confirm you're not a bot"* challenges.
- **Instagram Fallback Chain**: Sequential downloader engine (`parth-dl` → `instaloader` → `yt-dlp`) ensures reliable reel and post downloads.
- **Direct Text Submissions**: Paste transcripts, notes, or articles directly for immediate generation.

### 🎙️ 2. Dual-Engine Speech Recognition (STT)
- **Zero-Cost Offline Persian ASR**: Integrates the **Shenava Koochik v1.5** FastConformer RNNT model using `sherpa-onnx`. Operates completely offline on CPU inside a spawned process pool, bypassing Python's GIL.
- **Cloud STT Flexibility**: Built-in support for **AvalAI** (`scribe_v2` / `gpt-4o-transcribe`) and **OpenAI Whisper** with word/segment timestamps.
- **Workspace Provider Toggle**: Select between offline local ASR and cloud models on a per-project basis.
- **Audio Pre-processing**: Automatic 16 kHz Mono PCM normalization and dynamic duration chunking (>180s) to keep memory footprint predictable.

### 🧠 3. Canonical Knowledge & Content Brain
- **Canonical Synthesis**: Rather than prompting raw transcripts into multiple prompts, the system extracts a standardized structured model (Title, Key Ideas, Tone, Audience).
- **Asynchronous Output Dispatch**: Generates multiple platform drafts sequentially or in parallel without blocking worker queues.
- **Supported Formats**:
  - 📝 **Website Articles**: Comprehensive long-form Markdown formatted with headings, bullet points, and code blocks.
  - 💼 **LinkedIn Posts**: Professional hooks, structured spacing, and engagement prompts.
  - 🧵 **Twitter Threads**: Byte-sized, punchy sequences designed for virality.
  - ✈️ **Telegram Updates**: Clean formatting tailored for channels with bold callouts and hashtags.
  - 🎨 **Instagram Carousels**: Multi-slide content with text per slide and automated DALL-E image generation prompts.

### 🖥️ 4. Modern Dashboard & UI
- **Project Workspaces**: Multi-project management with workspace isolation, project renaming, and hard deletion with synchronous S3 bucket prefix purging.
- **Live State Polling**: Real-time progress updates for ingestion, extraction, and generation.
- **Markdown & Code Rendering**: Full support for GitHub Flavored Markdown (GFM), HTML tables, and copy-to-clipboard utilities.

---

## 🏗️ System Architecture

The platform is designed as an event-driven microservices architecture containerized via Docker Compose.

```mermaid
flowchart TD
    subgraph Client ["Client Layer"]
        Browser["🖥️ Web Browser (Next.js Dashboard)"]
    end

    subgraph Gateway ["Reverse Proxy Gateway"]
        Caddy["🛡️ Caddy Reverse Proxy (:80 / :443)"]
    end

    subgraph CoreServices ["Core Services"]
        API["⚡ FastAPI Backend (:8000)"]
        SW["📥 Source Worker (:8002)"]
        MW["🎙️ Media Worker (:8001)"]
        Web["⚛️ Next.js Web (:3000)"]
    end

    subgraph StateAndStorage ["Persistence & Storage"]
        Postgres[("🐘 PostgreSQL (Main App)")]
        N8nPG[("🐘 PostgreSQL (n8n Dedicated)")]
        Redis[("⚡ Redis Queue & Cache")]
        S3[("🪣 MinIO / Arvan S3 Storage")]
    end

    subgraph Automation ["Orchestration & AI"]
        N8N["⚡ n8n Workflow Engine (:5678)"]
        Shenava["🧠 Shenava Koochik ASR (Local ONNX)"]
        CloudAI["☁️ AvalAI / OpenAI (GPT-4o & Whisper)"]
    end

    Browser -->|HTTP Requests| Caddy
    Caddy -->|/| Web
    Caddy -->|/api/*| API
    Caddy -->|/n8n/*, /webhook/*| N8N

    API --> Postgres
    API --> Redis
    API --> S3
    
    API -->|Enqueue Download| Redis
    Redis -->|Consume Job| SW
    SW -->|yt-dlp / instaloader| S3
    SW -->|Notify Complete| API

    API -->|Trigger Pipeline| MW
    MW -->|Fetch Media| S3
    MW -->|FFmpeg Normalize| MW
    MW -->|Local Inference| Shenava
    MW -->|Cloud Inference| CloudAI
    MW -->|Store Transcript| Postgres

    API -->|Webhook Event| N8N
    N8N --> N8nPG
    N8N -->|Prompt Synthesis| CloudAI
    N8N -->|POST /canonical & /outputs| API
```

---

## 🧰 Tech Stack

| Layer | Component | Version | Description |
|---|---|---|---|
| **Backend API** | [FastAPI](https://fastapi.tiangolo.com/) | `0.115.0` | Asynchronous Python REST API framework |
| **ASGI Engine** | [Uvicorn](https://www.uvicorn.org/) | `0.30.6` | Lightning-fast ASGI server |
| **Database** | [PostgreSQL](https://www.postgresql.org/) | `16-alpine` | Relational single source of truth |
| **Async ORM** | [SQLAlchemy](https://www.sqlalchemy.org/) + [asyncpg](https://github.com/MagicStack/asyncpg) | `2.0.32` / `0.29.0` | High-throughput asynchronous connection pool |
| **In-Memory Broker**| [Redis](https://redis.io/) | `7-alpine` | Task queue for heavy download pipelines |
| **Workflow Engine**| [n8n](https://n8n.io/) | `latest` | Visual workflow orchestration for AI steps |
| **Object Storage** | [MinIO](https://min.io/) / [Arvan S3](https://arvancloud.ir) | S3 v4 | S3-compatible binary storage for audio, video, & images |
| **Offline ASR** | [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) | `1.13.6` | CPU-optimized runtime for FastConformer models |
| **Audio Processing**| [FFmpeg](https://ffmpeg.org/) / FFprobe | System | 16 kHz Mono PCM audio extraction & chunking |
| **Scraping Engine** | [yt-dlp](https://github.com/yt-dlp/yt-dlp) | `2024.8.6` | Resilient YouTube stream extraction |
| **Instagram Scraper**| [instaloader](https://instaloader.github.io/) / parth-dl| `4.13.1` | Reel and video extractor |
| **Frontend** | [Next.js](https://nextjs.org/) + React | `15.x` | Modern server-rendered web dashboard |
| **Styling** | [TailwindCSS](https://tailwindcss.com/) | `4.x` | Responsive dark-mode interface |
| **Reverse Proxy** | [Caddy](https://caddyserver.com/) | `2-alpine` | Automatic TLS reverse proxy gateway |

---

## 📸 Screenshots & Walkthrough

| 1. Project Dashboard | 2. Workspace & Ingestion |
| :---: | :---: |
| ![Dashboard](docs/screenshots/01-dashboard.png) | ![Workspace](docs/screenshots/02-workspace.png) |
| *Manage multiple workspaces and monitor ongoing processing* | *Direct media upload, URL submission, and text input* |

| 3. YouTube Cookie Settings | 4. Generated Repurposed Outputs |
| :---: | :---: |
| ![YouTube Settings](docs/screenshots/03-youtube-settings.png) | ![Outputs Preview](docs/screenshots/04-outputs-preview.png) |
| *Upload session cookies and test YouTube connectivity* | *Review and copy platform-tailored articles and posts* |

---

## 💎 Value Proposition & Use Cases

- **Content Agencies**: Repurpose one client podcast episode or interview into 10+ social assets across LinkedIn, Twitter, Telegram, and blogs in under 3 minutes.
- **Solo Creators & YouTubers**: Turn every YouTube video into high-ranking SEO website articles and viral Twitter threads without manual transcription.
- **Privacy-Sensitive Teams**: Use local offline speech-to-text (`Shenava Koochik`) to transcribe proprietary audio on private hardware without sending voice data to external cloud APIs.
- **Educators & Researchers**: Transform recorded lectures and webinars into structured markdown summaries and study notes.

---

## 🚀 Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) (v24.0+) & [Docker Compose](https://docs.docker.com/compose/) (v2.20+)
- 4GB+ RAM recommended if running local offline ASR (2GB+ if using Cloud STT)
- Git

### Step-by-Step Installation

#### 1. Clone Repository
```bash
git clone https://github.com/Mahdi-Soleimani/content-repurposing.git
cd content-repurposing
```

#### 2. Configure Environment
```bash
cp .env.example .env
```
Open `.env` in your editor and configure your secrets (OpenAI/AvalAI API keys if using cloud providers):
```bash
nano .env
```

#### 3. (Optional) Download Offline Persian Model
If you plan to use local offline speech recognition instead of cloud APIs, download the quantized ONNX weights (only required once):
```bash
./scripts/download_models.sh
```

#### 4. Launch the Platform
```bash
docker compose up --build -d
```

#### 5. Verify Running Services
```bash
docker compose ps
```

Once started, access the platform components:
- **Web Dashboard**: [http://localhost](http://localhost) (or [http://localhost:3000](http://localhost:3000))
- **FastAPI Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **n8n Workflow Editor**: [http://localhost:5678](http://localhost:5678)
- **MinIO Console**: [http://localhost:9001](http://localhost:9001)

#### 6. Import n8n Workflow
1. Open n8n at `http://localhost:5678`.
2. Set up your admin account on first launch.
3. Click **Workflows** → **Import from File**.
4. Select `Content repurposing.json` from the repository root.
5. Activate the workflow!

---

## ⚙️ Environment Configuration

| Variable | Description | Required? | Default / Example |
|---|---|:---:|---|
| `POSTGRES_USER` | PostgreSQL superuser for app data | Yes | `app` |
| `POSTGRES_PASSWORD` | PostgreSQL password for app data | Yes | `changeme_in_production` |
| `POSTGRES_DB` | Application database name | Yes | `content_repurposing` |
| `DATABASE_URL` | Async connection string for FastAPI | Yes | `postgresql+asyncpg://app:pwd@postgres:5432/content_repurposing` |
| `N8N_POSTGRES_USER` | Dedicated PostgreSQL username for n8n | Yes | `n8n` |
| `N8N_POSTGRES_PASSWORD` | Dedicated PostgreSQL password for n8n | Yes | `changeme_in_production` |
| `N8N_POSTGRES_DB` | Dedicated database name for n8n | Yes | `n8n` |
| `REDIS_URL` | Redis connection URL | Yes | `redis://redis:6379/0` |
| `API_SECRET_KEY` | Secret key for backend session signing | Yes | `change-this-secret-key-in-production` |
| `S3_ENDPOINT_URL` | S3 API endpoint (`minio:9000` or cloud) | Yes | `http://minio:9000` |
| `S3_ACCESS_KEY` | Object storage access key | Yes | `minioadmin` |
| `S3_SECRET_KEY` | Object storage secret key | Yes | `minioadmin` |
| `S3_BUCKET_NAME` | Bucket name for media & outputs | Yes | `content-repurposing` |
| `S3_PUBLIC_URL` | Public base URL for browser presigned PUT | Yes | `http://localhost:9000` |
| `STT_PROVIDER` | Speech engine (`shenava`, `avalai`, `openai`) | Yes | `shenava` |
| `SHENAVA_MODEL_PATH` | Directory containing ONNX model files | Optional | `/app/models/shenava-koochik` |
| `AVALAI_API_KEY` | API Key for AvalAI Cloud Speech & LLM | Optional | `aa-...` |
| `OPENAI_API_KEY` | API Key for OpenAI Whisper & GPT | Optional | `sk-...` |
| `DOMAIN` | Domain for Caddy reverse proxy | Yes | `localhost` |

---

## 🌐 Production Deployment Guide

Deploying on an online VPS (Ubuntu 22.04 / 24.04 LTS):

### 1. Server Preparation
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y curl git ufw

# Configure UFW Firewall
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### 2. Install Docker & Compose
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 3. Deploy Repository
```bash
git clone https://github.com/Mahdi-Soleimani/content-repurposing.git /opt/content-repurposing
cd /opt/content-repurposing
cp .env.example .env
```

### 4. Configure Production Domain & HTTPS
1. In `.env`, set `DOMAIN=crp.yourdomain.com`.
2. Update `docker/caddy/Caddyfile`:
```caddy
crp.yourdomain.com {
    handle /api/* {
        reverse_proxy api:8000
    }
    handle /webhook/* {
        reverse_proxy n8n:5678
    }
    handle {
        reverse_proxy web:3000
    }
}
```
Caddy will automatically obtain and renew free Let's Encrypt SSL/TLS certificates!

### 5. Start Container Stack
```bash
docker compose -f docker-compose.yml up --build -d
```

---

## 🧪 Testing

Run backend tests using `pytest`:

```bash
# Test YouTube Downloader resilience & error classification
cd services/source-worker
python -m pytest tests/test_youtube_downloader.py -v
```

---

## 🗺️ Roadmap

- [x] Multi-format media ingestion (YouTube, Instagram, MP4, MP3).
- [x] Offline Persian Speech Recognition (`Shenava Koochik v1.5`).
- [x] Visual n8n workflow integration.
- [x] YouTube anti-bot cookie manager.
- [ ] Direct publishing integrations (Auto-post to Telegram Channels via Bot API).
- [ ] LinkedIn & Twitter OAuth 2.0 direct publishing.
- [ ] Speaker diarization (who spoke when in multi-speaker podcasts).
- [ ] AI subtitle generator (.SRT/.VTT output with burn-in video support).

---

## 🤝 Contributing

Contributions are what make the open-source community an incredible place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

Please review our [Contributing Guide](CONTRIBUTING.md) and [Code of Conduct](CODE_OF_CONDUCT.md) before opening a pull request.

---

## 🔐 Security

We take platform security seriously. If you discover a vulnerability, please read our [Security Policy](SECURITY.md) and contact us responsibly. **Never submit security bugs to public issues.**

---

## 📄 License

Distributed under the **MIT License**. See [`LICENSE`](LICENSE) for more details.

---

## 🙏 Authors & Acknowledgments

- **Mahdi Soleimani** — [GitHub (@Mahdi-Soleimani)](https://github.com/Mahdi-Soleimani)
- **Shenava Team** — For open-sourcing the [Shenava Koochik](https://huggingface.co/Reza2kn/Shenava-Koochik-v1.5-RNNT-sherpa-onnx) speech recognition model for the Persian language.
- **n8n Community** — For the outstanding workflow automation ecosystem.
