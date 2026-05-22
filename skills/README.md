# Loom Skills (for Claude Code)

Three Claude Code skills that pair with this Loom instance. Drop them into your Claude Code `skills/` directory and Claude will pick them up automatically.

## What's here

| Skill | Triggers | What it does |
|---|---|---|
| **`workflow-duplication.md`** | "duplicate workflow", "create video-2", "clone workflow and change prompts" | Duplicates a reference workflow to create variants (new theme, new language, new page). Adapts LLM prompts and fixes data-table references. |
| **`page-scheduler.md`** | "schedule", "posting time", "when to post", "cron" | Calculates non-colliding posting times for all your workflows. Distributes posts evenly across peak hours per market. |
| **`run-ads.md`** | "run ads", "create campaign", "launch page-like ads" | Creates Facebook Page-Like campaigns via the Loom Ads API. 1 campaign → 1 adset → 4 ads (latest reels). |

## How to install

Drop the three `.md` files into your Claude Code skills directory:

```bash
# adjust path for your setup
cp workflow-duplication.md page-scheduler.md run-ads.md ~/.claude/skills/
```

Or, if you keep your Claude Code project in a different layout, place them wherever your `SKILL.md` files normally live.

Claude Code loads the front matter (`name`, `description`) automatically. You don't need to register them anywhere.

## How they fit together

These three skills are designed to be used in sequence when you grow your page network:

1. **`workflow-duplication`** — clone a proven workflow to a new page or new variant.
2. **`page-scheduler`** — recompute the schedule for the whole system so the new workflows don't collide with existing ones.
3. **`run-ads`** — when a page has enough content, launch a Page-Like campaign to grow it.

## Notes

- These skills assume you have a working Loom instance with the API reachable (default `http://127.0.0.1:8000`) and a bearer token configured.
- They expect Claude Code to be able to call the Loom API directly (either via shell/curl or via a small Python wrapper).
- The workflow-duplication skill depends on a `name-sop` convention — feel free to use the simple `<page-id>-<type>-<variant>` pattern or roll your own.
