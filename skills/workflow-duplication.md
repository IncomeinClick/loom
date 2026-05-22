---
name: workflow-duplication
description: >
  Use this skill when the user wants to duplicate a workflow to create a variant — such as a new content theme (e.g. "2026 forecast"), a different time period, or a new angle on the same page. Also use when duplicating a reference workflow across multiple pages that already exist, adapting prompts for each page's language and topic. Triggers include "duplicate workflow", "create video-2", "make a forecast variant", "clone workflow and change prompts", "create workflow variant", or any request to replicate a workflow with prompt modifications. This skill does NOT create new pages — use page-translation or page-creation for that.
---

# Workflow Duplication Skill

Duplicates a reference workflow to create variants with adapted LLM prompts, then schedules them for even distribution. Common use cases:

- Creating a new content theme variant (e.g. video-2 "2026 forecast" from video-1 "current period")
- Duplicating a proven workflow across existing pages with language/topic adaptation
- Cloning a workflow on the same page with different prompt angles

## Dependencies

- **`name-sop`** — for naming the new workflow ID and display name
- **`page-scheduler`** — for scheduling the new + existing workflows without collisions

---

## Phase 1: Understand the Request

Gather these details from the user (or infer from context):

1. **Reference workflow** — which existing workflow to duplicate
2. **Target pages** — which pages get the new workflow (could be the same page)
3. **Variant theme** — what changes in the new version (temporal shift, topic change, tone change, etc.)
4. **Prompt changes** — what specific text replacements or rewrites are needed in the LLM steps

Then confirm the plan:

> "จะ duplicate workflow [REF] ไปยัง [TARGETS] โดยปรับ prompt ให้เป็น [THEME] — ถูกต้องไหม?"

---

## Phase 2: Analyze Reference Workflow

Before duplicating, read the reference workflow to understand its structure:

1. `GET /api/workflows/{ref_id}` — check step count, step types, schedule
2. For each LLM step (type=`llm`), read the prompt via `GET /api/workflows/{ref_id}/steps/{step_id}/prompt`
3. Identify which steps need prompt changes based on the variant theme
4. Present a summary to the user:
   - Total steps and their types
   - Which LLM steps will be modified and what changes
   - Which steps remain unchanged

---

## Phase 3: Duplicate Workflows

For each target:

1. Determine new workflow ID and name using **`name-sop`**
2. `POST /api/workflows/{ref_id}/duplicate` with `{new_id, new_name}`
   - If duplicating to a different page, include `page_id` in the request body
3. Verify the duplicate: `GET /api/workflows/{new_id}` — confirm step count matches reference

### Naming Convention

New workflow IDs follow the pattern: `{page-id}-{workflow-type}-{variant-number}`

Examples:
- `<your-page-id>-video-2`
- `<your-other-page-id>-video-3`

---

## Phase 4: Update LLM Prompts

For each duplicated workflow, update the LLM step prompts:

1. `GET /api/workflows/{new_id}/steps/{step_id}/prompt` — get current system_prompt and user_prompt
2. Apply the planned text replacements or rewrites
3. `PUT /api/workflows/{new_id}/steps/{step_id}/prompt` with `{system_prompt, user_prompt}`
4. Verify: confirm "2026" (or whatever the variant marker is) appears in the updated prompts

### Prompt Adaptation Guidelines

| Change Type | Approach |
|-------------|----------|
| Temporal shift | Find-and-replace time references (e.g. "เร็วๆนี้" → "ในปี 2026") |
| Language adaptation | Translate the full prompt while preserving structure, variables, and tone |
| Topic change | Rewrite relevant sections while keeping the workflow structure intact |
| Tone change | Adjust language style without changing the content structure |

Important:
- **Preserve all template variables** like `{{Generate Date}}`, `{{Research Content}}` etc.
- **Preserve constraints** (character limits, formatting rules, output structure)
- **Preserve system prompts** unless the variant specifically requires changing them
- When doing temporal shifts, check ALL LLM steps — not just the obvious ones. Search for any time-related phrases in both system_prompt and user_prompt.

### Multi-language Families

When duplicating across a page family (e.g. TH + EN + PH versions), each language needs its own text replacements:

| Language | Example temporal replacements |
|----------|-------------------------------|
| Thai | "เร็วๆนี้" → "ในปี 2026", "ในช่วงนี้" → "ในปี 2026" |
| English | "very soon" → "in 2026", "These days" → "In 2026" |
| Filipino | "sa malapit" → "sa taong 2026", "Sa mga araw na ito" → "Sa taong 2026" |

---

## Phase 4.5: Update Data Table References (Cross-Page Only)

When duplicating to a **different page**, the new workflow's data table references will still point to the source page's table. Fix all of them:

1. **`datatable_insert` steps** → update `table_id` to `{target-page-id}-content`
2. **`datatable_update` steps** → update `table_id` to `{target-page-id}-content`
3. **`llm` steps with `lookup_table_id` in config** → update to `{target-page-id}-content`

**CRITICAL:** The `lookup_table_id` is inside the `config` object of LLM steps (typically "Generate Idea" or "Gen Prompt"). It controls duplicate keyword checking. If left pointing to the source page's table, the workflow will check the wrong table for duplicates, causing repeated content.

Skip this phase if duplicating within the same page (the table references are already correct).

---

## Phase 4.6: Verify Variable References & Step Configs

After duplication, verify that **every step's config** uses correct variable references. Duplication can create mismatches between `output_var` names and template variables (`{{xxx}}`) used by downstream steps.

For each duplicated workflow:

1. **Build a variable map**: Read every step's `output_var`. This is the variable name downstream steps must use.
2. **Check every `{{variable}}` reference** in all step configs against the variable map:
   - Fields: `media_url`, `message`, `row_id`, `prompt`, `columns_json`, etc.
   - If a reference doesn't match any step's `output_var`, it will silently resolve to empty
3. **Check `fb_post` steps**:
   - `media_type` MUST be `"photo"` for image workflows (NOT `"image"` — the FB API treats anything != "photo" as video)
   - `message` should reference the script/caption from the row (e.g. `{{row.script}}`), NOT the image prompt
   - `media_url` should reference the image generation output
4. **Check `datatable_update` steps**:
   - `row_id` must use `.row_id` accessor (e.g. `{{row.row_id}}`)

**Quick method**: Compare each step's config side-by-side with the reference workflow. Any `{{...}}` that differs must be verified against actual `output_var` names.

---

## Phase 5: Schedule All Workflows

Use **`page-scheduler`** to determine optimal schedules for both the new and existing workflows:

1. The new variant workflows need new time slots
2. Existing workflows may need rescheduling to distribute evenly
3. Check for collisions across ALL active workflows in the system

Apply schedules:
- `PUT /api/workflows/{id}` with `{schedule: "cron1,cron2,cron3"}`

Present the full schedule to the user before applying:

> | Page | Workflow | Schedule (Bangkok) |
> |------|----------|--------------------|
> | ... | video-1 | 06:00, 11:00, 16:00 |
> | ... | video-2 | 08:30, 13:30, 18:30 |

---

## Phase 6: Verify & Activate

Run verification checks:

1. **Step count** — each new workflow has the same number of steps as the reference
2. **Prompt changes** — variant marker (e.g. "2026") appears in all modified steps
3. **Schedule collisions** — no two workflows share the exact same time slot
4. **Active status** — all new workflows are active

Present a final summary:

> "สร้าง workflow ใหม่ทั้งหมด [N] workflows:
> - [list each with name, schedule, active status]
> - ไม่มี schedule ชนกัน
> - Prompt ถูกแก้ไขทั้งหมด [M] steps"

---

## Error Handling

- **Duplicate ID already exists** — ask user if they want to delete and recreate, or use a different ID
- **Prompt replacement didn't match** — show the actual prompt text and ask user for the correct find/replace strings
- **Schedule collision** — suggest alternative times using page-scheduler

---

## Quick Reference: API Endpoints

| Action | Method | Endpoint |
|--------|--------|----------|
| Get workflow | GET | `/api/workflows/{id}` |
| Duplicate workflow | POST | `/api/workflows/{id}/duplicate` |
| Get step prompt | GET | `/api/workflows/{wf_id}/steps/{step_id}/prompt` |
| Update step prompt | PUT | `/api/workflows/{wf_id}/steps/{step_id}/prompt` |
| Update workflow schedule | PUT | `/api/workflows/{id}` |

Note: Thai characters in workflow IDs must be URL-encoded when making API calls.
