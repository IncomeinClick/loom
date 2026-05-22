# Loom

Workflow automation for Facebook page management — schedule posts, generate captions/scripts/images with LLMs, run page workflows end-to-end, and manage credentials, datatables, and ad campaigns from a single dashboard.

## Features

- **Page workflows** — chain LLM, HTTP, image-gen, and FB-post steps with templated variables
- **Scheduler** — run workflows on cron (per-page or per-workflow) with execution history
- **Credentials vault** — encrypted storage (Fernet) for FB tokens, API keys, etc.
- **Datatables** — small SQLite tables for niche/topic rotation, lookup, and tracking
- **FB Ads** — create + monitor Page Like campaigns from the dashboard
- **Asset generation** — profile images, cover photos, bios via Gemini/OpenAI
- **Single static frontend** — Tailwind + Alpine, no build step

## Quick Start

```bash
# Clone
git clone https://github.com/IncomeinClick/loom.git
cd loom

# Set up Python environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e .

# Run
.venv/bin/python -m backend.run
```

Open http://localhost:8000 — on first load, the setup wizard will prompt for an email + password and generate the encryption keys for you.

## Companion repos

Loom ships as a clean engine — starter content and AI agent skills live in their own repos so you only pull in what you need:

- **[loom-templates](https://github.com/IncomeinClick/loom-templates)** — starter workflow templates (video + image content pipelines). Drop into `loom/templates/` to have them auto-seeded on first startup.
- **[loom-skills](https://github.com/IncomeinClick/loom-skills)** — Claude Code skills that work with this Loom instance (duplicate workflow, page scheduler, run ads).

If you want the example templates pre-seeded into your Loom dashboard:

```bash
git clone https://github.com/IncomeinClick/loom-templates.git templates
# then restart Loom — the startup hook will seed templates/*.json under a virtual "Template (Example)" page
```

## Configuration

All configuration lives in `.env` (auto-created by the setup wizard, or copy from `.env.example`):

| Variable | Description |
|---|---|
| `FERNET_KEY` | Symmetric key for credential encryption (auto-generated) |
| `API_BEARER_TOKEN` | Bearer token used for all API calls (auto-generated) |
| `USER_EMAIL` / `USER_PASS_HASH` | Login credentials (set by setup wizard) |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | LLM keys (optional, per executor) |
| `FB_APP_ID` / `FB_APP_SECRET` | FB app credentials for long-lived token exchange (optional) |
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_NOTIFY_CHAT_ID` | Activity + error alerts (optional, leave blank to disable) |
| `NOVA_VOICE_URL` / `NOVA_VIDEO_URL` | Custom Nova endpoints if you self-host (optional) |
| `GIT_AUTO_COMMIT` | Auto-commit `data/configs/` changes (default: false) |

## Production Deployment

A reference systemd unit lives in `deploy/loom.service` and an nginx site in `deploy/nginx-loom.conf`. See `deploy/SETUP.md` for the full server playbook.

## Tech stack

- **Backend:** FastAPI, SQLAlchemy + aiosqlite, APScheduler, Pydantic
- **Frontend:** Single HTML, Tailwind CDN, Alpine.js, vanilla JS
- **Storage:** SQLite (WAL) + JSON configs in `data/configs/`

## License

MIT
