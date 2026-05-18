import json
from datetime import datetime

from pydantic import BaseModel, field_validator


class StepOutputResponse(BaseModel):
    id: str
    step_id: str
    status: str
    output: str | None
    error_message: str | None
    duration_ms: int | None
    started_at: datetime | None
    finished_at: datetime | None

    model_config = {"from_attributes": True}


class ExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    page_name: str | None = None
    status: str
    trigger_type: str
    started_at: datetime
    finished_at: datetime | None
    error_message: str | None
    duration_ms: int | None = None  # computed

    model_config = {"from_attributes": True}


class ExecutionDetailResponse(ExecutionResponse):
    variables: dict  # parsed from JSON string
    step_outputs: list[StepOutputResponse] = []

    @field_validator("variables", mode="before")
    @classmethod
    def parse_variables(cls, v: object) -> dict:
        if isinstance(v, str):
            return json.loads(v)
        return v
