# Loom Workflow Templates

Two starter templates for the most common Loom content pipelines:

- **`video-workflow-template.json`** — 11 steps. Generates a unique idea → researches it → writes a script → renders voiceover + video → posts to Facebook → updates the data table.
- **`image-workflow-template.json`** — 6 steps. Picks an unposted row from the data table → generates an image prompt → renders the image → posts to Facebook → updates the row.

The image template **pairs with** the video template — the video workflow populates the content data table, the image workflow consumes it.

## What's in (and what's NOT in) these templates

The templates are **skeletons** with example prompts. You will replace:

- All `<PLACEHOLDER>` values (page IDs, credential IDs, language, schedule)
- The example prompts with your own niche prompts
- The optional first-comment text (CTA / affiliate link) — or delete the `fb_comment` step if you don't need it

The templates ship with **example prompts** so you can see the expected variable wiring (`{{Generate Idea}}`, `{{row.script}}`, etc.). Adapt them — don't keep them verbatim.

## Prerequisites

Before importing, set up these in your Loom dashboard:

1. **Niche** — create a niche for your content category.
2. **Page** — create a page under that niche; this is your `<YOUR_PAGE_ID>`.
3. **Credentials** — add credentials for each provider you'll use:
   - Gemini API key (for LLM steps and image generation)
   - OpenAI API key (if you want gpt-4o-mini for the image prompt step)
   - Nova credential (for voiceover and video generation)
   - Facebook Page access token (for posting)
4. **Data table** — create a table named `<YOUR_PAGE_ID>-content` with these columns:
   `seed`, `idea`, `script`, `caption`, `video`, `image`.

You can do all of the above through the Loom dashboard UI.

## How to import

### Option A — using the import script

```bash
# Edit the JSON template first: replace every <PLACEHOLDER> with your real values
vim video-workflow-template.json

# Then import
export LOOM_URL="http://your-loom-host:8000"
export LOOM_TOKEN="your-bearer-token"
python import_template.py video-workflow-template.json
```

The script will:

- Strip the `_comment` fields out of the JSON
- Verify no `<PLACEHOLDER>` strings remain
- POST `/api/workflows` to create the workflow
- POST `/api/steps` for each step in order

### Option B — using the Loom dashboard UI

Use the template JSON as a reference and create the workflow + steps manually in the UI.

## After importing

1. Open the workflow in your Loom dashboard.
2. Verify each step's config is correct (variable references, credential bindings).
3. Run a single manual trigger to test the full pipeline end-to-end.
4. When you're happy with the output, set `active: true` to start the cron schedule.

## Tips

- **Schedule:** the templates ship with a sample 3-times-per-day schedule. Use the `page-scheduler` skill (or your own judgment) to pick non-colliding times across all your workflows.
- **De-dup:** the `Generate Idea` step uses `lookup_table_id` + `lookup_columns` to avoid repeating old ideas. Make sure the column name in `lookup_columns` matches a real column in your data table.
- **Variable references:** every `{{Some Name}}` in a step's config must match a previous step's `output_var` exactly (case-sensitive, spaces matter). After editing, double-check that nothing silently resolves to an empty string.
- **Image workflow timing:** schedule the image workflow's first trigger **after** the video workflow's first trigger — otherwise the image workflow will find no unposted rows.
