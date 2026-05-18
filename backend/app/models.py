from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# --- Credential Models ---

class CredentialCreate(BaseModel):
    id: str
    name: str
    service: str = ""
    value: str


class CredentialUpdate(BaseModel):
    name: Optional[str] = None
    service: Optional[str] = None
    value: Optional[str] = None


class CredentialOut(BaseModel):
    id: str
    name: str
    service: str
    masked_value: str
    created_at: str
    updated_at: str


# --- Page Models ---

class PageAssets(BaseModel):
    profile_image: str = ""
    cover_photo: str = ""
    bio: str = ""


class PageConfig(BaseModel):
    id: str
    name: str
    niche: str = ""
    language: str = ""
    market: str = ""
    hashtag: str = ""
    cloned_from: Optional[str] = None
    assets: PageAssets = Field(default_factory=PageAssets)
    credentials: dict = Field(default_factory=dict)
    datatable: str = ""


class PageCreate(BaseModel):
    id: str
    name: str
    niche: str = ""
    language: str = ""
    market: str = ""
    hashtag: str = ""
    credentials: dict = Field(default_factory=dict)


# --- Workflow Models ---

class StepConfig(BaseModel):
    id: str
    name: str
    type: str  # llm, http, datatable, schedule
    model: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt: Optional[str] = None
    method: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[dict] = None
    body: Optional[dict] = None
    credential: Optional[str] = None
    file_var: Optional[str] = None
    output_var: str = ""
    table_name: Optional[str] = None
    table_action: Optional[str] = None  # read, write, clear


class WorkflowConfig(BaseModel):
    id: str
    name: str
    page: str
    active: bool = True
    schedule: str = ""
    steps: list[StepConfig] = Field(default_factory=list)


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    active: Optional[bool] = None
    schedule: Optional[str] = None
    steps: Optional[list[StepConfig]] = None


# --- Execution Models ---

class ExecutionOut(BaseModel):
    id: str
    workflow_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None


class ExecutionStepOut(BaseModel):
    id: str
    execution_id: str
    step_id: str
    step_name: str
    status: str
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


# --- Asset Generation Models ---

class GenerateImageRequest(BaseModel):
    page_name: str
    style_description: str


class GenerateBioRequest(BaseModel):
    page_name: str
    language: str = "English"
    market: str = ""
    niche_description: str = ""


# --- Page Clone Model ---

class PageCloneRequest(BaseModel):
    new_id: str
    new_name: str
    target_language: str
    target_market: str
    new_hashtag: str = ""
