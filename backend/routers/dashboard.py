import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, verify_token
from backend.models.page import Page
from backend.models.page_meta import PageMeta
from backend.models.credential import Credential

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"], dependencies=[Depends(verify_token)])


# ---------- Schemas ----------

class PageMetaUpdate(BaseModel):
    monetized_at: Optional[datetime] = None
    ads_running_at: Optional[datetime] = None
    notes: Optional[str] = None


class PageDashboardEntry(BaseModel):
    page_id: str
    name: str
    language: str
    market: Optional[str]
    niche_id: str
    # Stage timestamps
    setup_at: Optional[datetime]
    fb_ready_at: Optional[datetime]
    video_live_at: Optional[datetime]
    image_live_at: Optional[datetime]
    ads_running_at: Optional[datetime]
    monetized_at: Optional[datetime]
    # Extra
    fb_page_id: Optional[str]
    notes: Optional[str]
    # Computed
    current_stage: int  # 0-6
    workflow_count: int


class DashboardSummary(BaseModel):
    total_pages: int
    by_stage: dict[str, int]
    pages: list[PageDashboardEntry]


# ---------- Helpers ----------

# Step types that identify workflow category
VIDEO_STEP_TYPES = {"nova_video"}
IMAGE_STEP_TYPES = {"gen_image"}


def _auto_detect_stages(
    page: Page,
    meta: PageMeta,
    fb_creds: list[Credential],
) -> bool:
    """Auto-detect stages 1-4 from real data. Returns True if meta was changed."""
    now = datetime.now(timezone.utc)
    changed = False

    # Stage 1 - Setup: page has at least 1 workflow
    has_workflows = len(page.workflows) > 0
    if has_workflows and not meta.setup_at:
        meta.setup_at = now
        changed = True
    elif not has_workflows and meta.setup_at:
        meta.setup_at = None
        changed = True

    # Stage 2 - FB Ready: page has a facebook credential
    has_fb_cred = any(c.type == "facebook" for c in fb_creds)
    if has_fb_cred and not meta.fb_ready_at:
        meta.fb_ready_at = now
        changed = True
    elif not has_fb_cred and meta.fb_ready_at:
        meta.fb_ready_at = None
        changed = True

    # Stage 3 - Video Live: active + scheduled workflow with nova_video step
    has_video_live = any(
        w.active and w.schedule
        and any(s.type in VIDEO_STEP_TYPES for s in w.steps)
        for w in page.workflows
    )
    if has_video_live and not meta.video_live_at:
        meta.video_live_at = now
        changed = True
    elif not has_video_live and meta.video_live_at:
        meta.video_live_at = None
        changed = True

    # Stage 4 - Image Live: active + scheduled workflow with gen_image step
    has_image_live = any(
        w.active and w.schedule
        and any(s.type in IMAGE_STEP_TYPES for s in w.steps)
        for w in page.workflows
    )
    if has_image_live and not meta.image_live_at:
        meta.image_live_at = now
        changed = True
    elif not has_image_live and meta.image_live_at:
        meta.image_live_at = None
        changed = True

    return changed


def _compute_stage(meta: PageMeta) -> int:
    """Return current stage 0-6 based on which timestamps are set."""
    if meta.monetized_at:
        return 6
    if meta.ads_running_at:
        return 5
    if meta.image_live_at:
        return 4
    if meta.video_live_at:
        return 3
    if meta.fb_ready_at:
        return 2
    if meta.setup_at:
        return 1
    return 0


def _build_entry(page: Page, meta: PageMeta) -> PageDashboardEntry:
    return PageDashboardEntry(
        page_id=page.id,
        name=page.name,
        language=page.language,
        market=page.market,
        niche_id=page.niche_id,
        setup_at=meta.setup_at,
        fb_ready_at=meta.fb_ready_at,
        video_live_at=meta.video_live_at,
        image_live_at=meta.image_live_at,
        ads_running_at=meta.ads_running_at,
        monetized_at=meta.monetized_at,
        fb_page_id=meta.fb_page_id,
        notes=meta.notes,
        current_stage=_compute_stage(meta),
        workflow_count=len(page.workflows),
    )


# ---------- Routes ----------

@router.get("", response_model=DashboardSummary)
async def get_dashboard(db: AsyncSession = Depends(get_db)):
    pages_result = await db.execute(select(Page))
    pages = pages_result.scalars().all()

    metas_result = await db.execute(select(PageMeta))
    metas = {m.page_id: m for m in metas_result.scalars().all()}

    # Load credentials grouped by page_id for auto-detection
    creds_result = await db.execute(select(Credential))
    creds_by_page: dict[str, list[Credential]] = {}
    for c in creds_result.scalars().all():
        creds_by_page.setdefault(c.page_id or "", []).append(c)

    stage_labels = {
        0: "not_started",
        1: "setup",
        2: "fb_ready",
        3: "video_live",
        4: "image_live",
        5: "ads_running",
        6: "monetized",
    }
    by_stage = {v: 0 for v in stage_labels.values()}

    dirty = False
    for page in pages:
        meta = metas.get(page.id)
        if not meta:
            meta = PageMeta(page_id=page.id)
            metas[page.id] = meta
            db.add(meta)

        # Auto-detect stages 1-4 from real data
        if _auto_detect_stages(page, meta, creds_by_page.get(page.id, [])):
            dirty = True

    if dirty:
        await db.flush()

    entries = []
    for page in pages:
        meta = metas[page.id]
        entry = _build_entry(page, meta)
        entries.append(entry)
        by_stage[stage_labels[entry.current_stage]] += 1

    return DashboardSummary(
        total_pages=len(pages),
        by_stage=by_stage,
        pages=entries,
    )


@router.get("/{page_id}", response_model=PageDashboardEntry)
async def get_page_meta(page_id: str, db: AsyncSession = Depends(get_db)):
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    meta = await db.get(PageMeta, page_id)
    if not meta:
        meta = PageMeta(page_id=page_id)
        db.add(meta)

    fb_creds = (await db.execute(
        select(Credential).where(Credential.page_id == page_id)
    )).scalars().all()

    if _auto_detect_stages(page, meta, list(fb_creds)):
        await db.flush()

    return _build_entry(page, meta)


@router.put("/{page_id}", response_model=PageDashboardEntry)
async def update_page_meta(page_id: str, body: PageMetaUpdate, db: AsyncSession = Depends(get_db)):
    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    meta = await db.get(PageMeta, page_id)
    if not meta:
        meta = PageMeta(page_id=page_id)
        db.add(meta)

    now = datetime.now(timezone.utc)

    # Only allow manual update for ads_running and monetized (stages 1-4 are auto-detected)
    if "ads_running_at" in body.model_fields_set:
        meta.ads_running_at = body.ads_running_at
    if "monetized_at" in body.model_fields_set:
        meta.monetized_at = body.monetized_at
    if body.notes is not None:
        meta.notes = body.notes

    meta.updated_at = now
    await db.flush()

    return _build_entry(page, meta)


@router.post("/{page_id}/stage/{stage}", response_model=PageDashboardEntry)
async def mark_stage(page_id: str, stage: str, db: AsyncSession = Depends(get_db)):
    """Mark a stage as completed now. Only 'ads_running' and 'monetized' are manually markable (1-4 are auto-detected)."""
    if stage not in ("ads_running", "monetized"):
        raise HTTPException(status_code=400, detail=f"Stage '{stage}' is auto-detected and cannot be manually set")

    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    meta = await db.get(PageMeta, page_id)
    if not meta:
        meta = PageMeta(page_id=page_id)
        db.add(meta)

    now = datetime.now(timezone.utc)
    if stage == "ads_running":
        meta.ads_running_at = now
    else:
        meta.monetized_at = now
    meta.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _build_entry(page, meta)


@router.post("/{page_id}/stage/{stage}/clear", response_model=PageDashboardEntry)
async def clear_stage(page_id: str, stage: str, db: AsyncSession = Depends(get_db)):
    """Clear a stage (undo). Only 'ads_running' and 'monetized' can be manually cleared."""
    if stage not in ("ads_running", "monetized"):
        raise HTTPException(status_code=400, detail=f"Stage '{stage}' is auto-detected and cannot be manually cleared")

    page = await db.get(Page, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    meta = await db.get(PageMeta, page_id)
    if not meta:
        return _build_entry(page, PageMeta(page_id=page_id))

    if stage == "ads_running":
        meta.ads_running_at = None
    else:
        meta.monetized_at = None
    meta.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _build_entry(page, meta)


