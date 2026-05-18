import json
from datetime import datetime

from pydantic import BaseModel, field_validator


class DataTableResponse(BaseModel):
    id: str
    workflow_id: str | None
    name: str
    columns: list[str] = []
    row_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("columns", mode="before")
    @classmethod
    def parse_columns(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v or []


class DataTableCreate(BaseModel):
    id: str
    name: str
    columns: list[str] = []
    workflow_id: str | None = None


class DataTableUpdate(BaseModel):
    name: str | None = None
    columns: list[str] | None = None


class DataRowCreate(BaseModel):
    data: dict


class DataRowResponse(BaseModel):
    id: str
    datatable_id: str
    data: dict  # parsed from JSON string
    used: bool
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_validator("data", mode="before")
    @classmethod
    def parse_data(cls, v: object) -> dict:
        if isinstance(v, str):
            return json.loads(v)
        return v
