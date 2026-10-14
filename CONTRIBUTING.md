# Contributing to Content Repurposing Platform

Thank you for your interest in contributing to the **Content Repurposing Platform**! We welcome contributions from the community to make automated multimedia repurposing faster, more accessible, and more versatile.

---

## Code of Conduct

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please treat all contributors with respect and kindness.

---

## How Can I Contribute?

### 1. Reporting Bugs
- Search existing GitHub issues to make sure the bug hasn't already been reported.
- If not, open a new issue using the **Bug Report** template.
- Include OS version, Docker / Python version, steps to reproduce, expected vs actual behavior, and relevant logs (without leaking any secrets).

### 2. Suggesting Enhancements
- Open a GitHub issue using the **Feature Request** template.
- Explain the problem, your proposed solution, and why it benefits users.

### 3. Submitting Pull Requests
1. Fork the repository and create your branch from `main`:
   ```bash
   git checkout -b feature/my-amazing-feature
   ```
2. Set up your local environment:
   ```bash
   cp .env.example .env
   docker compose up --build -d
   ```
3. Ensure your code adheres to project standards:
   - Python code formatted according to PEP 8.
   - Clean, readable JavaScript/React with TailwindCSS for the frontend.
   - All tests pass: `pytest` in `services/source-worker`.
4. Commit your changes using [Conventional Commits](https://www.conventionalcommits.org/):
   - `feat: add Telegram channel publisher integration`
   - `fix: resolve ffmpeg audio chunk offset drift`
   - `docs: update VPS deployment guide with Caddy SSL tips`
5. Open a Pull Request targeting `main`. Fill in the PR description template.

---

## Development Guidelines

- **No Secrets in Code**: Never hardcode API keys, secrets, or personal tokens. Always use `.env` and `os.getenv()`.
- **Stateless Workers**: Workers (`media-worker`, `source-worker`) should treat the local filesystem as ephemeral; all persistent assets must be stored in Object Storage (S3/MinIO) and referenced in PostgreSQL.
- **Database Migrations**: Update `docker/postgres/init.sql` for any schema changes. Ensure backwards-compatible migrations.
- **Microservices Boundaries**: Respect the service roles documented in `ARCHITECTURE.md`.

---

## Questions?

Feel free to open a GitHub Discussion or join our community chat!
