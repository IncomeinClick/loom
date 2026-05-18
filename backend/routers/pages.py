from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, verify_token
from backend.exceptions import NotFoundError
from backend.models.niche import Niche
from backend.models.page import Page
from backend.schemas.page import PageCreate, PageUpdate, PageResponse
from backend.services.json_sync import export_page, delete_config
from backend.services.notification_service import notify_activity

router = APIRouter(prefix="/pages", tags=["pages"], dependencies=[Depends(verify_token)])


def _to_response(page: Page, workflow_count: int | None = None) -> PageResponse:
    return PageResponse(
        id=page.id,
        niche_id=page.niche_id,
        name=page.name,
        language=page.language,
        market=page.market,
        hashtag=page.hashtag,
        bio=page.bio,
        profile_image=page.profile_image,
        cover_photo=page.cover_photo,
        cloned_from=page.cloned_from,
        group_name=page.group_name,
        sort_order=page.sort_order,
        workflow_count=workflow_count if workflow_count is not None else len(page.workflows),
        created_at=page.created_at,
        updated_at=page.updated_at,
    )


@router.get("", response_model=list[PageResponse])
async def list_pages(
    niche_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Page)
    if niche_id:
        stmt = stmt.where(Page.niche_id == niche_id)
    stmt = stmt.order_by(Page.sort_order)
    result = await db.execute(stmt)
    pages = result.scalars().all()
    return [_to_response(p) for p in pages]


@router.post("", response_model=PageResponse, status_code=201)
async def create_page(body: PageCreate, db: AsyncSession = Depends(get_db)):
    niche = await db.get(Niche, body.niche_id)
    if not niche:
        raise NotFoundError("Niche", body.niche_id)
    page = Page(
        id=body.id,
        niche_id=body.niche_id,
        name=body.name,
        language=body.language,
        market=body.market,
        hashtag=body.hashtag,
        bio=body.bio,
    )
    db.add(page)
    await db.flush()
    await export_page(db, page.id)
    await notify_activity("created", "page", page.id, f"Name: {page.name}")
    return _to_response(page, workflow_count=0)


@router.get("/{page_id}", response_model=PageResponse)
async def get_page(page_id: str, db: AsyncSession = Depends(get_db)):
    page = await db.get(Page, page_id)
    if not page:
        raise NotFoundError("Page", page_id)
    return _to_response(page)


@router.put("/{page_id}", response_model=PageResponse)
async def update_page(page_id: str, body: PageUpdate, db: AsyncSession = Depends(get_db)):
    page = await db.get(Page, page_id)
    if not page:
        raise NotFoundError("Page", page_id)
    needs_export = False
    if body.name is not None:
        page.name = body.name
        needs_export = True
    if body.language is not None:
        page.language = body.language
        needs_export = True
    if body.market is not None:
        page.market = body.market
        needs_export = True
    if body.hashtag is not None:
        page.hashtag = body.hashtag
        needs_export = True
    if body.bio is not None:
        page.bio = body.bio
        needs_export = True
    if 'group_name' in body.model_fields_set:
        page.group_name = body.group_name
    if 'sort_order' in body.model_fields_set:
        page.sort_order = body.sort_order
    db.add(page)
    await db.flush()
    if needs_export:
        await export_page(db, page.id)
        await notify_activity("updated", "page", page_id)
    return _to_response(page)


@router.post("/{page_id}/rename")
async def rename_page(page_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """Rename a page's ID and/or name. Optional cascade renames related entities."""
    import json
    from fastapi import HTTPException
    from sqlalchemy import text
    from backend.models.workflow import Workflow
    from backend.models.credential import Credential
    from backend.models.page_meta import PageMeta
    from backend.models.datatable import DataTable
    from backend.models.step import Step
    from backend.services.json_sync import export_workflow
    from backend.services.scheduler_service import scheduler_service

    page = await db.get(Page, page_id)
    if not page:
        raise NotFoundError("Page", page_id)

    new_id = body.get("new_id", "").strip()
    new_name = body.get("new_name", "").strip()
    cascade = body.get("cascade", False)

    if new_name:
        page.name = new_name

    if new_id and new_id != page_id:
        existing = await db.get(Page, new_id)
        if existing:
            raise HTTPException(status_code=409, detail=f"Page ID '{new_id}' already exists")

        # Update direct FK references
        await db.execute(text("UPDATE pages SET cloned_from = :new WHERE cloned_from = :old"), {"new": new_id, "old": page_id})
        await db.execute(text("UPDATE workflows SET page_id = :new WHERE page_id = :old"), {"new": new_id, "old": page_id})
        await db.execute(text("UPDATE credentials SET page_id = :new WHERE page_id = :old"), {"new": new_id, "old": page_id})
        await db.execute(text("UPDATE page_meta SET page_id = :new WHERE page_id = :old"), {"new": new_id, "old": page_id})
        await db.execute(text("UPDATE pages SET id = :new WHERE id = :old"), {"new": new_id, "old": page_id})
        await db.flush()

        delete_config("pages", page_id)

        if cascade:
            # Cascade-rename credentials: fb-{old} -> fb-{new}
            creds_result = await db.execute(select(Credential).where(Credential.page_id == new_id))
            for cred in creds_result.scalars().all():
                if cred.id.startswith(f"fb-{page_id}"):
                    suffix = cred.id[len(f"fb-{page_id}"):]
                    new_cred_id = f"fb-{new_id}{suffix}"
                    if not await db.get(Credential, new_cred_id):
                        all_steps = await db.execute(select(Step))
                        for step in all_steps.scalars().all():
                            if cred.id in (step.config or ""):
                                cfg = json.loads(step.config)
                                if cfg.get("credential_id") == cred.id:
                                    cfg["credential_id"] = new_cred_id
                                    step.config = json.dumps(cfg, ensure_ascii=False)
                        await db.execute(text("UPDATE credentials SET id = :new WHERE id = :old"), {"new": new_cred_id, "old": cred.id})

            # Cascade-rename datatables: {old}-content -> {new}-content
            dts_result = await db.execute(select(DataTable))
            for dt in dts_result.scalars().all():
                if dt.id.startswith(f"{page_id}-"):
                    suffix = dt.id[len(page_id):]
                    new_dt_id = f"{new_id}{suffix}"
                    if not await db.get(DataTable, new_dt_id):
                        all_steps = await db.execute(select(Step))
                        for step in all_steps.scalars().all():
                            if dt.id in (step.config or ""):
                                cfg = json.loads(step.config)
                                changed = False
                                if cfg.get("table_id") == dt.id:
                                    cfg["table_id"] = new_dt_id
                                    changed = True
                                if cfg.get("lookup_table_id") == dt.id:
                                    cfg["lookup_table_id"] = new_dt_id
                                    changed = True
                                if changed:
                                    step.config = json.dumps(cfg, ensure_ascii=False)
                        await db.execute(text("UPDATE datarows SET datatable_id = :new WHERE datatable_id = :old"), {"new": new_dt_id, "old": dt.id})
                        await db.execute(text("UPDATE datatables SET id = :new WHERE id = :old"), {"new": new_dt_id, "old": dt.id})

            # Cascade-rename workflows: {old}-video -> {new}-video
            wfs_result = await db.execute(select(Workflow).where(Workflow.page_id == new_id))
            for wf in wfs_result.scalars().all():
                if wf.id.startswith(f"{page_id}-"):
                    suffix = wf.id[len(page_id):]
                    new_wf_id = f"{new_id}{suffix}"
                    if not await db.get(Workflow, new_wf_id):
                        # Rename step IDs
                        steps_result = await db.execute(select(Step).where(Step.workflow_id == wf.id))
                        for step in steps_result.scalars().all():
                            if step.id.startswith(f"{wf.id}-"):
                                step_suffix = step.id[len(wf.id) + 1:]
                                new_step_id = f"{new_wf_id}-{step_suffix}"
                                await db.execute(text("UPDATE step_outputs SET step_id = :new WHERE step_id = :old"), {"new": new_step_id, "old": step.id})
                                await db.execute(text("UPDATE steps SET id = :new WHERE id = :old"), {"new": new_step_id, "old": step.id})
                        # Update FKs
                        await db.execute(text("UPDATE steps SET workflow_id = :new WHERE workflow_id = :old"), {"new": new_wf_id, "old": wf.id})
                        await db.execute(text("UPDATE executions SET workflow_id = :new WHERE workflow_id = :old"), {"new": new_wf_id, "old": wf.id})
                        await db.execute(text("UPDATE datatables SET workflow_id = :new WHERE workflow_id = :old"), {"new": new_wf_id, "old": wf.id})
                        await db.execute(text("UPDATE workflows SET id = :new WHERE id = :old"), {"new": new_wf_id, "old": wf.id})
                        scheduler_service.remove_job(wf.id)
                        delete_config("workflows", wf.id)

            await db.flush()

            # Re-register scheduler and re-export for all workflows
            wfs_after = await db.execute(select(Workflow).where(Workflow.page_id == new_id))
            for wf in wfs_after.scalars().all():
                if wf.active and wf.schedule:
                    scheduler_service.add_job(wf.id, wf.schedule)
                await export_workflow(db, wf.id)

        page = await db.get(Page, new_id)

    await db.flush()
    await export_page(db, page.id)
    await notify_activity("renamed", "page", page.id, f"From: {page_id}")
    return _to_response(page)


@router.post("/{page_id}/clone", response_model=PageResponse, status_code=201)
async def clone_page(page_id: str, db: AsyncSession = Depends(get_db)):
    page = await db.get(Page, page_id)
    if not page:
        raise NotFoundError("Page", page_id)
    new_id = f"{page_id}-copy"
    existing = await db.get(Page, new_id)
    counter = 2
    while existing:
        new_id = f"{page_id}-copy-{counter}"
        existing = await db.get(Page, new_id)
        counter += 1
    new_page = Page(
        id=new_id,
        niche_id=page.niche_id,
        name=f"{page.name} (copy)",
        language=page.language,
        market=page.market,
        hashtag=page.hashtag,
        bio=page.bio,
        cloned_from=page.id,
    )
    db.add(new_page)
    await db.flush()
    await export_page(db, new_page.id)
    await notify_activity("cloned", "page", new_page.id, f"From: {page_id}")
    return _to_response(new_page, workflow_count=0)


@router.delete("/{page_id}", status_code=204)
async def delete_page(page_id: str, db: AsyncSession = Depends(get_db)):
    page = await db.get(Page, page_id)
    if not page:
        raise NotFoundError("Page", page_id)
    page_name = page.name
    await db.delete(page)
    await db.flush()
    delete_config("pages", page_id)
    await notify_activity("deleted", "page", page_id, f"Name: {page_name}")
