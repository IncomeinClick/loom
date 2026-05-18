from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from backend.schemas.step import StepResponse


class WorkflowCreate(BaseModel):
    id: str  # slug
    page_id: str
    name: str
    description: str | None = None
    language: str = "English"
    schedule: str | None = None
    active: bool = True


class WorkflowUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    language: str | None = None
    schedule: str | None = None
    active: bool | None = None
    sort_order: int | None = None


class WorkflowResponse(BaseModel):
    id: str
    page_id: str
    name: str
    description: str | None
    language: str
    schedule: str | None
    active: bool
    sort_order: int
    step_count: int = 0
    last_execution_status: str | None = None  # computed
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowDetailResponse(WorkflowResponse):
    steps: list[StepResponse] = []
