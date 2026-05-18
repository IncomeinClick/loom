from datetime import datetime

from pydantic import BaseModel


class PageCreate(BaseModel):
    id: str  # slug
    niche_id: str
    name: str
    language: str = "English"
    market: str | None = None
    hashtag: str | None = None
    bio: str | None = None


class PageUpdate(BaseModel):
    name: str | None = None
    language: str | None = None
    market: str | None = None
    hashtag: str | None = None
    bio: str | None = None
    group_name: str | None = None
    sort_order: int | None = None


class PageResponse(BaseModel):
    id: str
    niche_id: str
    name: str
    language: str
    market: str | None
    hashtag: str | None
    bio: str | None
    profile_image: str | None
    cover_photo: str | None
    cloned_from: str | None
    group_name: str | None
    sort_order: int = 0
    workflow_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
