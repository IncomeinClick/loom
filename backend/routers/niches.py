from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, verify_token
from backend.exceptions import NotFoundError, ConflictError
from backend.models.niche import Niche
from backend.schemas.niche import NicheCreate, NicheUpdate, NicheResponse
from backend.services.json_sync import export_niche, delete_config
from backend.services.notification_service import notify_activity

router = APIRouter(prefix="/niches", tags=["niches"], dependencies=[Depends(verify_token)])


@router.get("", response_model=list[NicheResponse])
async def list_niches(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Niche))
    niches = result.scalars().all()
    return [
        NicheResponse(
            id=n.id,
            name=n.name,
            description=n.description,
            page_count=len(n.pages),
            created_at=n.created_at,
            updated_at=n.updated_at,
        )
        for n in niches
    ]


@router.post("", response_model=NicheResponse, status_code=201)
async def create_niche(body: NicheCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.get(Niche, body.id)
    if existing:
        raise ConflictError(f"Niche '{body.id}' already exists")

    niche = Niche(
        id=body.id,
        name=body.name,
        description=body.description,
    )
    db.add(niche)
    await db.flush()
    await export_niche(db, niche.id)
    await notify_activity("created", "niche", niche.id, f"Name: {niche.name}")
    return NicheResponse(
        id=niche.id,
        name=niche.name,
        description=niche.description,
        page_count=0,
        created_at=niche.created_at,
        updated_at=niche.updated_at,
    )


@router.get("/{niche_id}", response_model=NicheResponse)
async def get_niche(niche_id: str, db: AsyncSession = Depends(get_db)):
    niche = await db.get(Niche, niche_id)
    if not niche:
        raise NotFoundError("Niche", niche_id)
    return NicheResponse(
        id=niche.id,
        name=niche.name,
        description=niche.description,
        page_count=len(niche.pages),
        created_at=niche.created_at,
        updated_at=niche.updated_at,
    )


@router.put("/{niche_id}", response_model=NicheResponse)
async def update_niche(niche_id: str, body: NicheUpdate, db: AsyncSession = Depends(get_db)):
    niche = await db.get(Niche, niche_id)
    if not niche:
        raise NotFoundError("Niche", niche_id)

    if body.name is not None:
        niche.name = body.name
    if body.description is not None:
        niche.description = body.description

    db.add(niche)
    await db.flush()
    await export_niche(db, niche.id)
    await notify_activity("updated", "niche", niche_id)
    return NicheResponse(
        id=niche.id,
        name=niche.name,
        description=niche.description,
        page_count=len(niche.pages),
        created_at=niche.created_at,
        updated_at=niche.updated_at,
    )


@router.delete("/{niche_id}", status_code=204)
async def delete_niche(niche_id: str, db: AsyncSession = Depends(get_db)):
    niche = await db.get(Niche, niche_id)
    if not niche:
        raise NotFoundError("Niche", niche_id)

    if len(niche.pages) > 0:
        raise ConflictError(f"Cannot delete niche '{niche_id}': it has {len(niche.pages)} page(s)")

    niche_name = niche.name
    await db.delete(niche)
    await db.flush()
    delete_config("niches", niche_id)
    await notify_activity("deleted", "niche", niche_id, f"Name: {niche_name}")
