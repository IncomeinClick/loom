import json

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, verify_token
from backend.exceptions import NotFoundError, ValidationError
from backend.models.workflow import Workflow
from backend.models.step import Step
from backend.schemas.step import StepCreate, StepUpdate, StepResponse, StepReorder, PromptUpdate, PromptResponse
from backend.services.json_sync import export_workflow
from backend.services.step_executors import EXECUTOR_MAP, DB_EXECUTOR_TYPES
from backend.services.notification_service import notify_activity

router = APIRouter(
    prefix="/workflows/{workflow_id}/steps",
    tags=["steps"],
    dependencies=[Depends(verify_token)],
)


async def _get_workflow_or_404(workflow_id: str, db: AsyncSession) -> Workflow:
    wf = await db.get(Workflow, workflow_id)
    if not wf:
        raise NotFoundError("Workflow", workflow_id)
    return wf


async def _get_step_or_404(step_id: str, workflow_id: str, db: AsyncSession) -> Step:
    result = await db.execute(
        select(Step).where(Step.id == step_id, Step.workflow_id == workflow_id)
    )
    step = result.scalar_one_or_none()
    if not step:
        raise NotFoundError("Step", step_id)
    return step


@router.get("", response_model=list[StepResponse])
async def list_steps(workflow_id: str, db: AsyncSession = Depends(get_db)):
    await _get_workflow_or_404(workflow_id, db)

    result = await db.execute(
        select(Step)
        .where(Step.workflow_id == workflow_id)
        .order_by(Step.sort_order)
    )
    steps = result.scalars().all()
    return [StepResponse.model_validate(s) for s in steps]


@router.post("", response_model=StepResponse, status_code=201)
async def create_step(workflow_id: str, body: StepCreate, db: AsyncSession = Depends(get_db)):
    await _get_workflow_or_404(workflow_id, db)

    step = Step(
        id=body.id,
        workflow_id=workflow_id,
        name=body.name,
        type=body.type,
        sort_order=body.sort_order,
        config=json.dumps(body.config, ensure_ascii=False),
        output_var=body.output_var,
    )
    db.add(step)
    await db.flush()
    await export_workflow(db, workflow_id)
    await notify_activity("created", "step", step.id, f"Workflow: {workflow_id}, Type: {step.type}")
    return StepResponse.model_validate(step)


# Reorder MUST be before /{step_id} routes to avoid matching "reorder" as a step_id
@router.put("/reorder", response_model=list[StepResponse])
async def reorder_steps(
    workflow_id: str,
    body: StepReorder,
    db: AsyncSession = Depends(get_db),
):
    await _get_workflow_or_404(workflow_id, db)

    for idx, step_id in enumerate(body.step_ids):
        step = await _get_step_or_404(step_id, workflow_id, db)
        step.sort_order = idx
        db.add(step)

    await db.flush()

    result = await db.execute(
        select(Step)
        .where(Step.workflow_id == workflow_id)
        .order_by(Step.sort_order)
    )
    steps = result.scalars().all()
    await export_workflow(db, workflow_id)
    return [StepResponse.model_validate(s) for s in steps]


@router.get("/{step_id}", response_model=StepResponse)
async def get_step(workflow_id: str, step_id: str, db: AsyncSession = Depends(get_db)):
    step = await _get_step_or_404(step_id, workflow_id, db)
    return StepResponse.model_validate(step)


@router.put("/{step_id}", response_model=StepResponse)
async def update_step(
    workflow_id: str,
    step_id: str,
    body: StepUpdate,
    db: AsyncSession = Depends(get_db),
):
    step = await _get_step_or_404(step_id, workflow_id, db)

    if body.name is not None:
        step.name = body.name
    if body.sort_order is not None:
        step.sort_order = body.sort_order
    if body.config is not None:
        step.config = json.dumps(body.config, ensure_ascii=False)
    if body.output_var is not None:
        step.output_var = body.output_var

    db.add(step)
    await db.flush()
    await export_workflow(db, workflow_id)
    return StepResponse.model_validate(step)


@router.delete("/{step_id}", status_code=204)
async def delete_step(workflow_id: str, step_id: str, db: AsyncSession = Depends(get_db)):
    step = await _get_step_or_404(step_id, workflow_id, db)
    step_name = step.name
    await db.delete(step)
    await db.flush()
    await export_workflow(db, workflow_id)
    await notify_activity("deleted", "step", step_id, f"Workflow: {workflow_id}, Name: {step_name}")


@router.get("/{step_id}/prompt", response_model=PromptResponse)
async def get_prompt(workflow_id: str, step_id: str, db: AsyncSession = Depends(get_db)):
    step = await _get_step_or_404(step_id, workflow_id, db)

    if step.type != "llm":
        raise ValidationError(f"Step '{step_id}' is type '{step.type}', not 'llm'")

    config = step.config_dict
    return PromptResponse(
        step_id=step.id,
        system_prompt=config.get("system_prompt", ""),
        user_prompt=config.get("user_prompt", ""),
    )


@router.put("/{step_id}/prompt", response_model=PromptResponse)
async def update_prompt(
    workflow_id: str,
    step_id: str,
    body: PromptUpdate,
    db: AsyncSession = Depends(get_db),
):
    step = await _get_step_or_404(step_id, workflow_id, db)

    if step.type != "llm":
        raise ValidationError(f"Step '{step_id}' is type '{step.type}', not 'llm'")

    config = step.config_dict
    config["system_prompt"] = body.system_prompt
    config["user_prompt"] = body.user_prompt
    step.config_dict = config

    db.add(step)
    await db.flush()
    await export_workflow(db, workflow_id)
    return PromptResponse(
        step_id=step.id,
        system_prompt=body.system_prompt,
        user_prompt=body.user_prompt,
    )


class TestStepRequest(BaseModel):
    variables: dict = {}


@router.post("/{step_id}/test")
async def test_step(
    workflow_id: str,
    step_id: str,
    body: TestStepRequest,
    db: AsyncSession = Depends(get_db),
):
    """Execute a single step with provided variables and return its output."""
    step = await _get_step_or_404(step_id, workflow_id, db)
    config = step.config_dict

    executor_cls = EXECUTOR_MAP.get(step.type)
    if not executor_cls:
        raise ValidationError(f"Unknown step type: {step.type}")

    if step.type in DB_EXECUTOR_TYPES:
        executor = executor_cls(db)
    else:
        executor = executor_cls()

    try:
        output = await executor.execute(config, dict(body.variables))
        return {"status": "success", "output": output}
    except Exception as e:
        return {"status": "error", "error": str(e)}
