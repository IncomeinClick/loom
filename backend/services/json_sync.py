"""JSON config sync — exports DB state to human-readable JSON files."""
import json
import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.niche import Niche
from backend.models.page import Page
from backend.models.step import Step
from backend.models.workflow import Workflow

logger = logging.getLogger(__name__)


async def export_workflow(db: AsyncSession, workflow_id: str):
    """Export a workflow and its steps to a JSON config file."""
    result = await db.execute(select(Workflow).where(Workflow.id == workflow_id))
    workflow = result.scalar_one_or_none()
    if not workflow:
        return

    steps_result = await db.execute(
        select(Step).where(Step.workflow_id == workflow_id).order_by(Step.sort_order)
    )
    steps = steps_result.scalars().all()

    config = {
        "id": workflow.id,
        "name": workflow.name,
        "page": workflow.page_id,
        "active": workflow.active,
        "schedule": workflow.schedule,
        "description": workflow.description,
        "steps": [
            {
                "id": step.id,
                "name": step.name,
                "type": step.type,
                "output_var": step.output_var,
                **step.config_dict,
            }
            for step in steps
        ],
    }

    path = settings.CONFIGS_DIR / "workflows" / f"{workflow_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Exported workflow config: {path}")


async def export_page(db: AsyncSession, page_id: str):
    """Export a page to a JSON config file."""
    result = await db.execute(select(Page).where(Page.id == page_id))
    page = result.scalar_one_or_none()
    if not page:
        return

    config = {
        "id": page.id,
        "name": page.name,
        "niche": page.niche_id,
        "language": page.language,
        "market": page.market,
        "hashtag": page.hashtag,
        "cloned_from": page.cloned_from,
        "assets": {
            "profile_image": page.profile_image,
            "cover_photo": page.cover_photo,
            "bio": page.bio,
        },
    }

    path = settings.CONFIGS_DIR / "pages" / f"{page_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Exported page config: {path}")


async def export_niche(db: AsyncSession, niche_id: str):
    """Export a niche to a JSON config file."""
    result = await db.execute(select(Niche).where(Niche.id == niche_id))
    niche = result.scalar_one_or_none()
    if not niche:
        return

    config = {
        "id": niche.id,
        "name": niche.name,
        "description": niche.description,
    }

    path = settings.CONFIGS_DIR / "niches" / f"{niche_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Exported niche config: {path}")


def delete_config(entity_type: str, entity_id: str):
    """Delete a JSON config file."""
    path = settings.CONFIGS_DIR / entity_type / f"{entity_id}.json"
    if path.exists():
        path.unlink()
        logger.info(f"Deleted config: {path}")
