import base64

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, verify_token
from backend.exceptions import NotFoundError
from backend.models.page import Page
from backend.models.niche import Niche
from backend.schemas.asset import AssetGenerateRequest, BioGenerateRequest, AssetGenerateResponse, BioGenerateResponse
from backend.services.asset_service import generate_profile_image, generate_cover_photo, generate_bio
from backend.services.json_sync import export_page

router = APIRouter(
    prefix="/pages/{page_id}/assets",
    tags=["assets"],
    dependencies=[Depends(verify_token)],
)


@router.post("/profile", response_model=AssetGenerateResponse)
async def gen_profile(
    page_id: str,
    request: AssetGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    page = await db.get(Page, page_id)
    if not page:
        raise NotFoundError("Page", page_id)

    image_bytes, relative_path = await generate_profile_image(page.name, request.theme)

    # Update page record
    page.profile_image = relative_path
    db.add(page)
    await db.flush()
    await export_page(db, page_id)

    return AssetGenerateResponse(
        image_base64=base64.b64encode(image_bytes).decode(),
        path=relative_path,
    )


@router.post("/cover", response_model=AssetGenerateResponse)
async def gen_cover(
    page_id: str,
    request: AssetGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    page = await db.get(Page, page_id)
    if not page:
        raise NotFoundError("Page", page_id)

    image_bytes, relative_path = await generate_cover_photo(page.name, request.theme)

    page.cover_photo = relative_path
    db.add(page)
    await db.flush()
    await export_page(db, page_id)

    return AssetGenerateResponse(
        image_base64=base64.b64encode(image_bytes).decode(),
        path=relative_path,
    )


@router.post("/bio", response_model=BioGenerateResponse)
async def gen_bio(
    page_id: str,
    request: BioGenerateRequest,
    db: AsyncSession = Depends(get_db),
):
    page = await db.get(Page, page_id)
    if not page:
        raise NotFoundError("Page", page_id)

    # Get niche description for context
    niche_desc = request.niche_description
    if not niche_desc and page.niche_id:
        niche = await db.get(Niche, page.niche_id)
        if niche:
            niche_desc = niche.description or niche.name

    bio_text = await generate_bio(page.name, page.language or "en", niche_desc or "general")

    page.bio = bio_text
    db.add(page)
    await db.flush()
    await export_page(db, page_id)

    return BioGenerateResponse(bio=bio_text)
