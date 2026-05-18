from datetime import datetime

from pydantic import BaseModel


class NicheCreate(BaseModel):
    id: str  # slug
    name: str
    description: str | None = None


class NicheUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class NicheResponse(BaseModel):
    id: str
    name: str
    description: str | None
    page_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
