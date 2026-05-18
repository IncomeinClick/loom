from datetime import datetime

from pydantic import BaseModel


class CredentialCreate(BaseModel):
    id: str
    page_id: str | None = None
    name: str
    type: str  # facebook, openai, gemini, nova_astra
    value: str  # raw value, will be encrypted


class CredentialUpdate(BaseModel):
    name: str | None = None
    page_id: str | None = None
    type: str | None = None
    value: str | None = None  # new raw value to encrypt


class CredentialResponse(BaseModel):
    id: str
    page_id: str | None
    name: str
    type: str
    masked_value: str  # e.g. "****7xQ3"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
