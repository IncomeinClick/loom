import json
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pathlib import Path

from app.auth import verify_api_key
from app.config import settings
from app.models import WorkflowConfig, WorkflowUpdate, StepConfig
from app.engine.executor import run_workflow
from app.services.git_tracker import auto_commit

router = APIRouter(prefix="/api/workflows", tags=["workflows"], dependencies=[Depends(verify_api_key)])


def _wf_path(workflow_id: str) -> Path:
    return settings.workflows_path / f"{workflow_id}.json"


def _load_workflow(workflow_id: str) -> WorkflowConfig:
    path = _wf_path(workflow_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    return WorkflowConfig(**json.loads(path.read_text(encoding="utf-8")))


def _save_workflow(wf: WorkflowConfig):
    path = _wf_path(wf.id)
    path.write_text(json.dumps(wf.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")


@router.get("")
async def list_workflows(page: str = None):
    workflows = []
    for f in sorted(settings.workflows_path.glob("*.json")):
        try:
            wf = json.loads(f.read_text(encoding="utf-8"))
            if page and wf.get("page") != page:
                continue
            workflows.append(wf)
        except Exception:
            continue
    return workflows


@router.get("/{workflow_id}")
async def get_workflow(workflow_id: str):
    return _load_workflow(workflow_id).model_dump()


@router.post("")
async def create_workflow(data: WorkflowConfig):
    if _wf_path(data.id).exists():
        raise HTTPException(status_code=409, detail=f"Workflow '{data.id}' already exists")
    _save_workflow(data)
    auto_commit(f"Create workflow: {data.name}")
    return data.model_dump()


@router.put("/{workflow_id}")
async def update_workflow(workflow_id: str, data: WorkflowUpdate):
    wf = _load_workflow(workflow_id)
    wf_dict = wf.model_dump()
    update_dict = data.model_dump(exclude_none=True)
    wf_dict.update(update_dict)
    updated = WorkflowConfig(**wf_dict)
    _save_workflow(updated)
    auto_commit(f"Update workflow: {workflow_id}")
    return updated.model_dump()


@router.delete("/{workflow_id}")
async def delete_workflow(workflow_id: str):
    path = _wf_path(workflow_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Workflow '{workflow_id}' not found")
    path.unlink()
    auto_commit(f"Delete workflow: {workflow_id}")
    return {"deleted": workflow_id}


@router.post("/{workflow_id}/duplicate")
async def duplicate_workflow(workflow_id: str, new_id: str, new_name: str = None):
    wf = _load_workflow(workflow_id)
    if _wf_path(new_id).exists():
        raise HTTPException(status_code=409, detail=f"Workflow '{new_id}' already exists")
    new_wf = wf.model_copy()
    new_wf.id = new_id
    new_wf.name = new_name or f"{wf.name} (copy)"
    new_wf.active = False
    _save_workflow(new_wf)
    auto_commit(f"Duplicate workflow: {workflow_id} → {new_id}")
    return new_wf.model_dump()


# --- Prompt editing (convenience endpoint) ---

@router.put("/{workflow_id}/steps/{step_id}/prompt")
async def update_step_prompt(workflow_id: str, step_id: str, data: dict):
    wf = _load_workflow(workflow_id)
    for step in wf.steps:
        if step.id == step_id:
            if "system_prompt" in data:
                step.system_prompt = data["system_prompt"]
            if "user_prompt" in data:
                step.user_prompt = data["user_prompt"]
            _save_workflow(wf)
            auto_commit(f"Update prompt: {workflow_id}/{step_id}")
            return step.model_dump()
    raise HTTPException(status_code=404, detail=f"Step '{step_id}' not found in workflow '{workflow_id}'")


# --- Manual trigger ---

@router.post("/{workflow_id}/trigger")
async def trigger_workflow(workflow_id: str, background_tasks: BackgroundTasks):
    wf = _load_workflow(workflow_id)
    execution_id = await run_workflow(wf)
    return {"execution_id": execution_id, "workflow_id": workflow_id, "status": "started"}
