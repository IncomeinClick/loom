import json
from datetime import datetime

from pydantic import BaseModel, field_validator


class StepCreate(BaseModel):
    id: str
    name: str
    type: str  # llm, http, datatable, schedule
    sort_order: int = 0
    config: dict = {}  # type-specific config as a dict
    output_var: str | None = None


class StepUpdate(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    config: dict | None = None
    output_var: str | None = None


class StepResponse(BaseModel):
    id: str
    workflow_id: str
    name: str
    type: str
    sort_order: int
    config: dict  # parsed from JSON string
    output_var: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("config", mode="before")
    @classmethod
    def parse_config(cls, v: object) -> dict:
        if isinstance(v, str):
            return json.loads(v)
        return v


class PromptUpdate(BaseModel):
    system_prompt: str
    user_prompt: str


class PromptResponse(BaseModel):
    step_id: str
    system_prompt: str
    user_prompt: str


class StepReorder(BaseModel):
    step_ids: list[str]  # ordered list of step IDs
