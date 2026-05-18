from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, verify_token
from backend.exceptions import NotFoundError
from backend.models.step import Step
from backend.models.workflow import Workflow
from backend.services.workflow_engine import run_workflow
from backend.services.notification_service import notify_activity

router = APIRouter(tags=["triggers"], dependencies=[Depends(verify_token)])


@router.post("/workflows/{workflow_id}/trigger")
async def trigger_workflow(
    workflow_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise NotFoundError("Workflow", workflow_id)

    execution_id = str(uuid4())
    background_tasks.add_task(run_workflow, workflow_id, execution_id, "manual")
    await notify_activity("triggered", "workflow", workflow_id, "Manual trigger")
    return {"execution_id": execution_id}


@router.post("/workflows/{workflow_id}/trigger-until/{step_id}")
async def trigger_workflow_until_step(
    workflow_id: str,
    step_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Run a workflow from step 1 up to and including the specified step."""
    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise NotFoundError("Workflow", workflow_id)

    result = await db.execute(
        select(Step).where(Step.id == step_id, Step.workflow_id == workflow_id)
    )
    if not result.scalar_one_or_none():
        raise NotFoundError("Step", step_id)

    execution_id = str(uuid4())
    background_tasks.add_task(run_workflow, workflow_id, execution_id, "manual", step_id)
    await notify_activity("triggered", "workflow", workflow_id, f"Until step: {step_id}")
    return {"execution_id": execution_id}
