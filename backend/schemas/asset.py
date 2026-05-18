from pydantic import BaseModel


class AssetGenerateRequest(BaseModel):
    theme: str  # style/theme description


class BioGenerateRequest(BaseModel):
    niche_description: str


class AssetGenerateResponse(BaseModel):
    image_base64: str
    path: str


class BioGenerateResponse(BaseModel):
    bio: str
