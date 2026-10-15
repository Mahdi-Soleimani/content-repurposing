# Security Policy

## Supported Versions

We take security seriously and actively maintain security updates for the following versions:

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | :white_check_mark: |
| < 1.0   | :x:                |

## Reporting a Vulnerability

If you discover a security vulnerability within the Content Repurposing Platform, please do **NOT** open a public issue on GitHub. Public disclosure before a fix is available puts users and installations at risk.

Instead, please report security vulnerabilities responsibly:

1. **Email**: Send detailed information about the vulnerability to `mahdisoleimani2003@gmail.com` (or create a private GitHub Security Advisory under the **Security** tab of the repository).
2. **Details to Include**:
   - Type of vulnerability (e.g., SSRF, SQL Injection, RCE, Broken Object Level Authorization, Information Disclosure).
   - Step-by-step reproduction steps or proof-of-concept (PoC).
   - Affected service (`api`, `media-worker`, `source-worker`, `web`, or infrastructure).
   - Potential impact and suggested mitigations if known.

## Vulnerability Handling Process

- **Acknowledgement**: We will acknowledge receipt of your vulnerability report within 48 hours.
- **Assessment**: We will confirm the vulnerability, determine its severity, and keep you informed throughout the resolution process.
- **Resolution**: Once a fix is validated, a patched release will be published alongside appropriate release notes acknowledging your contribution (if desired).

## Security Best Practices for Self-Hosting

When deploying the Content Repurposing Platform in production:

1. **Secrets**: Never commit `.env` or use default passwords (`POSTGRES_PASSWORD`, `N8N_ENCRYPTION_KEY`, `API_SECRET_KEY`).
2. **Network Isolation**: Keep internal services (`postgres`, `redis`, `minio`, workers) off the public Internet. Only expose the Caddy reverse proxy on ports 80/443.
3. **Storage Access**: Restrict object storage policies and use dedicated IAM credentials with minimal permissions.
4. **Cookie Security**: Store YouTube `cookies.txt` strictly in private storage with encrypted backups.
