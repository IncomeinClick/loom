import json
from uuid import uuid4

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, verify_token
from backend.exceptions import NotFoundError
from backend.models.page import Page
from backend.models.workflow import Workflow
from backend.models.step import Step
from backend.models.execution import Execution
from backend.schemas.workflow import WorkflowCreate, WorkflowUpdate, WorkflowResponse, WorkflowDetailResponse
from backend.schemas.step import StepResponse
from backend.services.json_sync import export_workflow, delete_config
from backend.services.scheduler_service import scheduler_service
from backend.services.notification_service import notify_activity

router = APIRouter(prefix="/workflows", tags=["workflows"], dependencies=[Depends(verify_token)])


class DuplicateRequest(BaseModel):
    new_id: str
    new_name: str | None = None
    page_id: str | None = None


async def _get_last_execution_status(db: AsyncSession, workflow_id: str) -> str | None:
    result = await db.execute(
        select(Execution.status)
        .where(Execution.workflow_id == workflow_id)
        .order_by(Execution.started_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


@router.get("", response_model=list[WorkflowResponse])
async def list_workflows(
    page_id: str | None = Query(None),
    active: bool | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Workflow)
    if page_id:
        stmt = stmt.where(Workflow.page_id == page_id)
    if active is not None:
        stmt = stmt.where(Workflow.active == active)
    stmt = stmt.order_by(Workflow.sort_order)

    result = await db.execute(stmt)
    workflows = result.scalars().all()

    responses = []
    for wf in workflows:
        last_status = await _get_last_execution_status(db, wf.id)
        responses.append(
            WorkflowResponse(
                id=wf.id,
                page_id=wf.page_id,
                name=wf.name,
                description=wf.description,
                language=wf.language,
                schedule=wf.schedule,
                active=wf.active,
                sort_order=wf.sort_order,
                step_count=len(wf.steps),
                last_execution_status=last_status,
                created_at=wf.created_at,
                updated_at=wf.updated_at,
            )
        )
    return responses


@router.post("", response_model=WorkflowResponse, status_code=201)
async def create_workflow(body: WorkflowCreate, db: AsyncSession = Depends(get_db)):
    # Validate page exists
    page = await db.get(Page, body.page_id)
    if not page:
        raise NotFoundError("Page", body.page_id)

    wf = Workflow(
        id=body.id,
        page_id=body.page_id,
        name=body.name,
        description=body.description,
        language=body.language,
        schedule=body.schedule,
        active=body.active,
    )
    db.add(wf)
    await db.flush()
    await export_workflow(db, wf.id)

    # Register schedule if active with cron
    if wf.active and wf.schedule:
        scheduler_service.add_job(wf.id, wf.schedule)

    await notify_activity("created", "workflow", wf.id, f"Page: {wf.page_id}")

    return WorkflowResponse(
        id=wf.id,
        page_id=wf.page_id,
        name=wf.name,
        description=wf.description,
        language=wf.language,
        schedule=wf.schedule,
        active=wf.active,
        sort_order=wf.sort_order,
        step_count=0,
        last_execution_status=None,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


@router.get("/{workflow_id}", response_model=WorkflowDetailResponse)
async def get_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise NotFoundError("Workflow", workflow_id)

    last_status = await _get_last_execution_status(db, wf.id)
    steps = [StepResponse.model_validate(s) for s in wf.steps]
    return WorkflowDetailResponse(
        id=wf.id,
        page_id=wf.page_id,
        name=wf.name,
        description=wf.description,
        language=wf.language,
        schedule=wf.schedule,
        active=wf.active,
        sort_order=wf.sort_order,
        step_count=len(wf.steps),
        last_execution_status=last_status,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
        steps=steps,
    )


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(workflow_id: str, body: WorkflowUpdate, db: AsyncSession = Depends(get_db)):
    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise NotFoundError("Workflow", workflow_id)

    if body.name is not None:
        wf.name = body.name
    if body.description is not None:
        wf.description = body.description
    if body.language is not None:
        wf.language = body.language
    if 'schedule' in body.model_fields_set:
        wf.schedule = body.schedule
    if body.active is not None:
        wf.active = body.active
    if body.sort_order is not None:
        wf.sort_order = body.sort_order

    db.add(wf)
    await db.flush()
    await export_workflow(db, wf.id)

    # Update scheduler
    if wf.active and wf.schedule:
        scheduler_service.add_job(wf.id, wf.schedule)
    else:
        scheduler_service.remove_job(wf.id)

    # Notify — detect activate/deactivate vs regular update
    if body.active is True:
        await notify_activity("activated", "workflow", wf.id)
    elif body.active is False:
        await notify_activity("deactivated", "workflow", wf.id)
    else:
        await notify_activity("updated", "workflow", wf.id)

    last_status = await _get_last_execution_status(db, wf.id)
    return WorkflowResponse(
        id=wf.id,
        page_id=wf.page_id,
        name=wf.name,
        description=wf.description,
        language=wf.language,
        schedule=wf.schedule,
        active=wf.active,
        sort_order=wf.sort_order,
        step_count=len(wf.steps),
        last_execution_status=last_status,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(workflow_id: str, db: AsyncSession = Depends(get_db)):
    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise NotFoundError("Workflow", workflow_id)

    wf_name = wf.name
    await db.delete(wf)
    await db.flush()
    delete_config("workflows", workflow_id)
    scheduler_service.remove_job(workflow_id)
    await notify_activity("deleted", "workflow", workflow_id, f"Name: {wf_name}")


@router.post("/{workflow_id}/rename")
async def rename_workflow(workflow_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """Rename a workflow's ID and/or name, updating all FK references."""
    from fastapi import HTTPException
    from sqlalchemy import text

    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise NotFoundError("Workflow", workflow_id)

    new_id = body.get("new_id", "").strip()
    new_name = body.get("new_name", "").strip()

    if new_name:
        wf.name = new_name

    if new_id and new_id != workflow_id:
        existing = await db.get(Workflow, new_id)
        if existing:
            raise HTTPException(status_code=409, detail=f"Workflow ID '{new_id}' already exists")

        # Rename step IDs that follow {workflow_id}-{suffix} pattern
        steps_result = await db.execute(select(Step).where(Step.workflow_id == workflow_id))
        for step in steps_result.scalars().all():
            if step.id.startswith(f"{workflow_id}-"):
                suffix = step.id[len(workflow_id) + 1:]
                new_step_id = f"{new_id}-{suffix}"
                await db.execute(
                    text("UPDATE step_outputs SET step_id = :new WHERE step_id = :old"),
                    {"new": new_step_id, "old": step.id},
                )
                await db.execute(
                    text("UPDATE steps SET id = :new WHERE id = :old"),
                    {"new": new_step_id, "old": step.id},
                )

        # Update FK references
        await db.execute(text("UPDATE steps SET workflow_id = :new WHERE workflow_id = :old"), {"new": new_id, "old": workflow_id})
        await db.execute(text("UPDATE executions SET workflow_id = :new WHERE workflow_id = :old"), {"new": new_id, "old": workflow_id})
        await db.execute(text("UPDATE datatables SET workflow_id = :new WHERE workflow_id = :old"), {"new": new_id, "old": workflow_id})
        await db.execute(text("UPDATE workflows SET id = :new WHERE id = :old"), {"new": new_id, "old": workflow_id})
        await db.flush()

        # Scheduler: remove old, re-register with new ID
        scheduler_service.remove_job(workflow_id)
        delete_config("workflows", workflow_id)

        wf = await db.get(Workflow, new_id)
        if wf.active and wf.schedule:
            scheduler_service.add_job(wf.id, wf.schedule)

    await db.flush()
    await export_workflow(db, wf.id)
    await notify_activity("renamed", "workflow", wf.id, f"From: {workflow_id}")

    last_status = await _get_last_execution_status(db, wf.id)
    return WorkflowResponse(
        id=wf.id,
        page_id=wf.page_id,
        name=wf.name,
        description=wf.description,
        language=wf.language,
        schedule=wf.schedule,
        active=wf.active,
        sort_order=wf.sort_order,
        step_count=len(wf.steps),
        last_execution_status=last_status,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
    )


@router.post("/{workflow_id}/duplicate", response_model=WorkflowResponse, status_code=201)
async def duplicate_workflow(
    workflow_id: str,
    body: DuplicateRequest,
    db: AsyncSession = Depends(get_db),
):
    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise NotFoundError("Workflow", workflow_id)

    new_wf = Workflow(
        id=body.new_id,
        page_id=body.page_id or wf.page_id,
        name=body.new_name or f"{wf.name} (copy)",
        description=wf.description,
        language=wf.language,
        schedule=wf.schedule,
        active=wf.active,
        sort_order=wf.sort_order,
    )
    db.add(new_wf)
    await db.flush()

    # Duplicate steps
    for step in wf.steps:
        new_step = Step(
            id=f"{body.new_id}-{step.id.split('-', 1)[-1]}" if '-' in step.id else f"{body.new_id}-{step.id}",
            workflow_id=new_wf.id,
            name=step.name,
            type=step.type,
            sort_order=step.sort_order,
            config=step.config,
            output_var=step.output_var,
        )
        db.add(new_step)
    await db.flush()
    await export_workflow(db, new_wf.id)

    if new_wf.active and new_wf.schedule:
        scheduler_service.add_job(new_wf.id, new_wf.schedule)

    await notify_activity("duplicated", "workflow", new_wf.id, f"From: {workflow_id}")

    return WorkflowResponse(
        id=new_wf.id,
        page_id=new_wf.page_id,
        name=new_wf.name,
        description=new_wf.description,
        language=new_wf.language,
        schedule=new_wf.schedule,
        active=new_wf.active,
        sort_order=new_wf.sort_order,
        step_count=len(wf.steps),
        last_execution_status=None,
        created_at=new_wf.created_at,
        updated_at=new_wf.updated_at,
    )
