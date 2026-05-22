"""Auto-seed example workflow templates on Loom startup.

Idempotent — skips any workflow whose ID already exists in the database.
Templates live in /opt/loom/templates/*.json and are seeded under a
virtual "template" niche/page that gets created if missing.

The seeded workflows are always inactive (active=False) so they never
run unless the user explicitly activates them after duplicating to a
real page.
"""
import json
import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.niche import Niche
from backend.models.page import Page
from backend.models.step import Step
from backend.models.workflow import Workflow

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
TEMPLATE_NICHE_ID = "template"
TEMPLATE_PAGE_ID = "template"
LANGUAGE_PLACEHOLDER = "<en|th|tl|id|vi>"


def _strip_comments(obj):
    if isinstance(obj, dict):
        return {k: _strip_comments(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [_strip_comments(x) for x in obj]
    return obj


def _substitute(obj, page_id: str):
    """Replace <YOUR_PAGE_ID> placeholder with the seed page id."""
    if isinstance(obj, str):
        return obj.replace("<YOUR_PAGE_ID>", page_id)
    if isinstance(obj, dict):
        return {k: _substitute(v, page_id) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_substitute(x, page_id) for x in obj]
    return obj


async def seed_templates(db: AsyncSession) -> int:
    """Insert any template workflows not yet present in the database.

    Returns the number of newly seeded workflows.
    """
    if not TEMPLATE_DIR.exists():
        return 0
    files = sorted(TEMPLATE_DIR.glob("*.json"))
    if not files:
        return 0

    niche = await db.get(Niche, TEMPLATE_NICHE_ID)
    if not niche:
        db.add(Niche(
            id=TEMPLATE_NICHE_ID,
            name="Template",
            description="Example workflow templates. Duplicate to a real page to start using them.",
        ))
        await db.flush()
        logger.info(f"[seed] Created niche '{TEMPLATE_NICHE_ID}'")

    page = await db.get(Page, TEMPLATE_PAGE_ID)
    if not page:
        db.add(Page(
            id=TEMPLATE_PAGE_ID,
            niche_id=TEMPLATE_NICHE_ID,
            name="Template (Example)",
            language="English",
            bio="Example workflows that ship with Loom. Use the workflow-duplication skill to copy them onto a real page.",
        ))
        await db.flush()
        logger.info(f"[seed] Created page '{TEMPLATE_PAGE_ID}'")

    n_added = 0
    for fp in files:
        try:
            raw = _substitute(_strip_comments(json.loads(fp.read_text())), TEMPLATE_PAGE_ID)
            wf = raw["workflow"]
            steps = raw["steps"]

            if await db.get(Workflow, wf["id"]):
                continue

            language = wf.get("language", "English")
            if language == LANGUAGE_PLACEHOLDER or not language:
                language = "English"

            db.add(Workflow(
                id=wf["id"],
                page_id=TEMPLATE_PAGE_ID,
                name=wf["name"],
                description=wf.get("description"),
                language=language,
                schedule=wf.get("schedule"),
                active=False,
                sort_order=wf.get("sort_order", 0),
            ))
            await db.flush()

            for step in steps:
                step_id = f"{wf['id']}-step-{step['sort_order']:02d}"
                cfg = step.get("config", {})
                db.add(Step(
                    id=step_id,
                    workflow_id=wf["id"],
                    name=step["name"],
                    type=step["type"],
                    sort_order=step["sort_order"],
                    config=json.dumps(cfg, ensure_ascii=False),
                    output_var=step.get("output_var"),
                ))

            n_added += 1
            logger.info(f"[seed] Imported template workflow '{wf['id']}' ({len(steps)} steps)")
        except Exception as e:
            logger.exception(f"[seed] Failed to import {fp}: {e}")

    if n_added:
        await db.commit()
        logger.info(f"[seed] Seeded {n_added} new template workflow(s)")
    return n_added
