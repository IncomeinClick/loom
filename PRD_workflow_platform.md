# PRD: Loom — Workflow Automation Platform
**Version:** 1.1
**Author:** David (AI Assistant)
**For:** Pond + Development team
**Date:** 2026-02-21

---

## 1. Overview

**Loom** is a lightweight web-based workflow automation platform that replaces n8n for managing Facebook content generation pipelines across multiple pages and niches.

Loom is a visual tool for Pond to create new Facebook pages quickly, manage their assets (profile image, cover photo, bio), and orchestrate content automation workflows. David (AI assistant) is the primary operator — he creates pages, builds workflows, edits prompts, and triggers runs. Pond uses the UI to review David's work, tweak prompts, and monitor performance.

The platform supports **multiple niches** (e.g. Chinese astrology, motivational quotes, horoscopes), each with potentially different workflow sequences. It also supports **cloning a page into a new language/market** — duplicating all workflows and translating prompts while preserving the pipeline structure.

---

## 2. Problem Statement

Current setup uses n8n (Hostinger hosted) which has:
- Plan limitations (no folder API, no credential API)
- Visual workflows that require UI access to edit prompts
- No programmatic control over credentials
- Scaling friction — each new page requires manual UI work
- No built-in asset generation (profile image, cover photo, bio)
- No concept of "niche" — each page is isolated, can't share workflow templates
- Cloning a page to a new language requires rebuilding workflows from scratch

---

## 3. Goals

- Replace n8n with a self-hosted platform on the existing server
- Allow visual workflow viewing and prompt editing via web UI
- Enable full programmatic control by the AI agent
- Make page replication fast and scriptable (including language cloning)
- Support multiple niches with different workflow sequences
- Generate page assets (profile image, cover photo, bio) from within the platform
- Support easy addition of new workflow steps without code changes

---

## 4. Users

| User | Role |
|---|---|
| Pond | Owner — reviews workflows, monitors performance |
| กาน / ตาล | Staff — may edit prompts, check status |
| David (AI) | Primary operator — creates pages, generates assets, builds workflows, edits prompts, triggers runs, monitors |

---

## 5. Core Concepts

### 5.1 Niche
A content category (e.g. "Chinese Astrology", "Motivational Quotes", "Daily Horoscope"). Each niche defines a set of workflow templates that can be reused across pages. Different niches may have completely different step sequences.

### 5.2 Page
A Facebook page belonging to a specific niche, with its own language/market, credentials, assets (profile image, cover photo, bio), and content table. Multiple pages can share the same niche but target different languages.

### 5.3 Workflow
A named sequence of steps that runs on a schedule. Each page can have multiple workflows (e.g. "Video Content", "Image Post", "Horoscope 2569"). Workflow sequences vary by niche — a Chinese astrology page has different steps than a motivational quotes page.

### 5.4 Step
A single unit of work within a workflow. Can be:
- `llm` — Call an LLM (OpenAI, Gemini) with a prompt
- `http` — Call an external HTTP API (Nova-Astra, FB Graph API)
- `datatable` — Read/write from a data store
- `schedule` — Trigger node (cron expression)

### 5.5 Prompt
Each `llm` step has an editable prompt. Prompts support template variables like `{{zodiac}}`, `{{idea}}`, etc. passed from previous steps.

---

## 6. Features

### 6.1 Workflow Management
- List all workflows grouped by page
- View workflow as a visual step diagram (linear flow)
- Activate / deactivate a workflow
- Duplicate a workflow (for new page replication)
- Delete a workflow
- Different niches can have different workflow sequences (steps are not fixed)

### 6.2 Prompt Editor
- Click any `llm` step to open a prompt editor
- Edit system prompt and user prompt
- Save changes instantly
- Changes take effect on next run

### 6.3 Manual Trigger
- Trigger any workflow manually from the UI
- View live execution log as it runs

### 6.4 Execution History
- List recent executions per workflow
- View status (success / failed)
- View output of each step for a given execution

### 6.5 Page & Credential Management
- List all pages and their associated credentials
- Add/edit credentials (FB Graph API token, etc.)
- Assign credentials to workflows
- Each page belongs to a niche and has a language/market

### 6.6 Page Assets Generator
A section within each page's settings to generate and manage Facebook page assets.

**6.6.1 Profile Image Generator**
- Input: page name, style/theme description
- Calls Google Gemini API (`gemini-3-pro-image-preview`) via `generateContent` endpoint
- API key stored in config/env
- Prompt enforcement:
  - Single layer background only — no combining two images, no double layers, no inner panel, no card effect
  - Background is creative — any style, no restrictions
  - All key elements (illustration + page name text) centered within the middle 70% of the image — safe for Facebook's circle crop
  - NO white space, NO rounded corners, NO borders
  - Page name text centered below main illustration
- Output: display generated image, option to regenerate, option to save/download as PNG

**6.6.2 Cover Photo Generator**
- Input: page name, style/theme description
- Calls same Gemini API (`gemini-3-pro-image-preview`) via `generateContent`
- Prompt enforcement:
  - Wide landscape composition — background fills edge to edge, no blank bars top or bottom
  - NO text of any kind — pure illustration only
  - Background extends fully to all edges
- Output: display generated image, option to regenerate, option to save/download as PNG

**6.6.3 Bio Generator**
- Input: page name, language/market, niche description
- Calls OpenAI or Gemini to generate a short Facebook page bio
- Output: editable text field, copy button

**General Image Generation Rules:**
- Pack ALL requirements into the first prompt — minimize regeneration (each call costs API credits)
- Both profile and cover use `gemini-3-pro-image-preview` model
- Images returned as base64 inline data from API response (`candidates[0].content.parts[0].inlineData.data`)
- Decode base64 and display in UI, allow download as PNG

### 6.7 Page Cloning (Language Swap)
- Clone an existing page into a new page with a different language/market
- Duplicates all workflows and their step configurations
- Translates prompts to the target language (via LLM call or manual edit)
- Generates new page assets (profile image, cover photo, bio) for the cloned page
- New page inherits the same niche but gets its own credentials and DataTable

### 6.8 DataTable
- Each workflow has an associated DataTable (content store)
- View rows in the DataTable from the UI
- Clear/reset table

### 6.9 Scheduling
- Each workflow has a cron schedule (e.g. 3x per day)
- Enable/disable schedule from UI
- Show next scheduled run time

---

## 7. Technical Architecture

### 7.1 Backend
- **Language:** Python 3.11+
- **Framework:** FastAPI
- **Scheduler:** APScheduler (cron-based)
- **Storage:** SQLite (workflows, steps, executions, credentials, datatables)
- **Config:** JSON files per workflow (human-readable, AI-editable)

### 7.2 Frontend
- **Framework:** Simple HTML + TailwindCSS + Alpine.js (no heavy framework)
- **Served by:** Nginx on existing server
- **No build step required** — static files only

### 7.3 Hosting
- Same server as OpenClaw (`openclaw.incomeinclick.in.th`)
- Nginx reverse proxy → FastAPI on internal port
- Separate subdomain or path (e.g. `workflows.incomeinclick.in.th` or `/workflows`)

### 7.4 AI Agent Control
- David can read/write workflow JSON configs directly via filesystem
- David can call the FastAPI backend to trigger runs, edit prompts, check status
- All workflow definitions stored as plain JSON files — human-readable, AI-editable
- David can also edit Loom's source code and restart the service to add/remove features

### 7.5 Security

**7.5.1 Credential Protection**
- All credentials (API keys, tokens) encrypted at rest in SQLite using Fernet symmetric encryption
- Master encryption key stored in `.env` file — never in code or config JSONs
- UI never shows full credential values — display only last 4 characters (e.g. `sk-...7xQ3`)
- Full value reveal requires explicit confirmation click

**7.5.2 Change Protection (Git Auto-Commit)**
- Loom's entire project directory is a git repository on the server
- Every config change (workflow edits, prompt updates, credential additions) triggers an automatic git commit with a descriptive message
- Every source code edit by David is also tracked in git history
- If something breaks → revert to any previous state via `git revert`
- This makes nothing David does irreversible

**7.5.3 Validation Layer**
- All workflow JSON changes validated against a schema before saving
- Malformed configs are rejected with clear error messages
- Health check endpoint (`GET /api/health`) to verify Loom is operational after changes

**7.5.4 Access Control**
- All API endpoints require a bearer token (API key)
- Nginx IP whitelist for the web UI — only authorized IPs can access the dashboard
- API key for David's programmatic access (stored in his environment)
- No public access without authentication

---

## 8. Workflow JSON Format

```json
{
  "id": "bulong-ng-langit-video",
  "name": "Bulong ng Langit - Video Content",
  "page": "bulong-ng-langit",
  "active": true,
  "schedule": "0 7,14,22 * * *",
  "steps": [
    {
      "id": "generate-zodiac",
      "name": "Generate Zodiac",
      "type": "llm",
      "model": "gpt-4o-mini",
      "system_prompt": "You are a Chinese astrology expert.",
      "user_prompt": "Pick one of the 12 Chinese zodiac animals: Rat, Ox, Tiger, Rabbit, Dragon, Snake, Horse, Goat, Monkey, Rooster, Dog, Pig. Reply with the animal name only.",
      "output_var": "zodiac"
    },
    {
      "id": "generate-idea",
      "name": "Generate Idea",
      "type": "llm",
      "model": "gemini-3-flash",
      "system_prompt": "You are a Chinese astrology content expert.",
      "user_prompt": "Create 1 short content idea about {{zodiac}} for social media. Max 50 characters.",
      "output_var": "idea"
    },
    {
      "id": "generate-voice",
      "name": "Generate Voice",
      "type": "http",
      "method": "POST",
      "url": "https://api.nova.incomeinclick.in.th/api/gen_voice",
      "body": {
        "input": "{{script}}",
        "voice": "Alnilam",
        "style": "auto"
      },
      "output_var": "audio_url"
    },
    {
      "id": "post-facebook",
      "name": "Post to Facebook",
      "type": "http",
      "method": "POST",
      "url": "https://graph.facebook.com/v23.0/me/videos",
      "credential": "bulong-ng-langit-fb",
      "body": {
        "description": "{{description}}"
      },
      "file_var": "video_file",
      "output_var": "post_id"
    }
  ]
}
```

---

## 9. Page Config Format

```json
{
  "id": "bulong-ng-langit",
  "name": "Bulong ng Langit",
  "niche": "chinese-astrology",
  "language": "Tagalog",
  "market": "Philippines",
  "hashtag": "#BulongngLangit",
  "cloned_from": null,
  "assets": {
    "profile_image": "assets/bulong-ng-langit/profile.png",
    "cover_photo": "assets/bulong-ng-langit/cover.png",
    "bio": "Bulong ng Langit — ang iyong gabay sa Chinese astrology at kapalaran."
  },
  "credentials": {
    "facebook": "bulong-ng-langit-fb",
    "nova_astra": "nova-astra-default"
  },
  "datatable": "bulong-ng-langit-content"
}
```

---

## 10. Data Migration

When moving from n8n:
1. Export all workflow JSONs from n8n (Hostinger)
2. Upload to server
3. David reads them and converts to platform JSON format
4. Credentials entered manually via UI (one-time per page)
5. Verify with test run before deactivating n8n

---

## 11. MVP Scope (Phase 1)

| Feature | Priority |
|---|---|
| Workflow list + status | P0 |
| Step diagram view | P0 |
| Prompt editor | P0 |
| Manual trigger + live log | P0 |
| Execution history | P0 |
| Page Assets Generator (profile, cover, bio) | P0 |
| Multi-niche support | P0 |
| Credential management | P1 |
| DataTable viewer | P1 |
| Schedule management | P1 |
| Workflow duplication | P1 |
| Page cloning (language swap) | P1 |
| Multi-user access | P2 |
| Dashboard / analytics | P2 |

---

## 12. Out of Scope (v1)

- Visual drag-and-drop workflow builder
- Branching/conditional logic
- Webhook triggers
- Mobile app

---

## 13. Success Criteria

- All current n8n workflows running on the new platform
- Pond and team can edit prompts without touching code
- David can fully operate the platform via API + filesystem
- New page creation (including asset generation) takes < 5 minutes of human effort
- Cloning a page to a new language takes < 5 minutes
- Profile image, cover photo, and bio can be generated from the UI in one click
- Multiple niches supported with different workflow sequences
