from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.dependencies import get_db, verify_token
from backend.exceptions import NotFoundError
from backend.models.credential import Credential
from backend.models.page import Page
from backend.models.page_meta import PageMeta
from backend.schemas.credential import CredentialCreate, CredentialUpdate, CredentialResponse
from backend.services.notification_service import notify_activity

try:
    from cryptography.fernet import Fernet
except ImportError:
    Fernet = None  # type: ignore[assignment,misc]

router = APIRouter(prefix="/credentials", tags=["credentials"], dependencies=[Depends(verify_token)])


def _encrypt(value: str) -> str:
    if not settings.FERNET_KEY or Fernet is None:
        return value  # dev mode: no encryption
    f = Fernet(settings.FERNET_KEY.encode())
    return f.encrypt(value.encode()).decode()


def _decrypt(encrypted: str) -> str:
    if not settings.FERNET_KEY or Fernet is None:
        return encrypted
    f = Fernet(settings.FERNET_KEY.encode())
    return f.decrypt(encrypted.encode()).decode()


def _mask(value: str) -> str:
    if len(value) <= 4:
        return "****"
    return "****" + value[-4:]


def _build_response(cred: Credential) -> CredentialResponse:
    return CredentialResponse(
        id=cred.id,
        page_id=cred.page_id,
        name=cred.name,
        type=cred.type,
        masked_value=_mask(cred.last_four or ""),
        created_at=cred.created_at,
        updated_at=cred.updated_at,
    )


@router.get("", response_model=list[CredentialResponse])
async def list_credentials(
    page_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Credential)
    if page_id:
        stmt = stmt.where(Credential.page_id == page_id)

    result = await db.execute(stmt)
    credentials = result.scalars().all()
    return [_build_response(c) for c in credentials]


@router.post("", response_model=CredentialResponse, status_code=201)
async def create_credential(body: CredentialCreate, db: AsyncSession = Depends(get_db)):
    encrypted = _encrypt(body.value)
    last_four = body.value[-4:] if len(body.value) >= 4 else body.value

    cred = Credential(
        id=body.id,
        page_id=body.page_id,
        name=body.name,
        type=body.type,
        encrypted_value=encrypted,
        last_four=last_four,
    )
    db.add(cred)
    await db.flush()
    await notify_activity("created", "credential", cred.id, f"Type: {cred.type}")
    return _build_response(cred)


@router.get("/{cred_id}", response_model=CredentialResponse)
async def get_credential(cred_id: str, db: AsyncSession = Depends(get_db)):
    cred = await db.get(Credential, cred_id)
    if not cred:
        raise NotFoundError("Credential", cred_id)
    return _build_response(cred)


@router.put("/{cred_id}", response_model=CredentialResponse)
async def update_credential(cred_id: str, body: CredentialUpdate, db: AsyncSession = Depends(get_db)):
    cred = await db.get(Credential, cred_id)
    if not cred:
        raise NotFoundError("Credential", cred_id)

    if body.name is not None:
        cred.name = body.name
    if 'page_id' in body.model_fields_set:
        cred.page_id = body.page_id
    if body.type is not None:
        cred.type = body.type
    if body.value is not None:
        cred.encrypted_value = _encrypt(body.value)
        cred.last_four = body.value[-4:] if len(body.value) >= 4 else body.value

    db.add(cred)
    await db.flush()
    await notify_activity("updated", "credential", cred_id)
    return _build_response(cred)


@router.delete("/{cred_id}", status_code=204)
async def delete_credential(cred_id: str, db: AsyncSession = Depends(get_db)):
    cred = await db.get(Credential, cred_id)
    if not cred:
        raise NotFoundError("Credential", cred_id)

    cred_name = cred.name
    await db.delete(cred)
    await db.flush()
    await notify_activity("deleted", "credential", cred_id, f"Name: {cred_name}")


@router.post("/{cred_id}/rename")
async def rename_credential(cred_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """Rename a credential's ID and/or name, updating all step config references."""
    cred = await db.get(Credential, cred_id)
    if not cred:
        raise NotFoundError("Credential", cred_id)

    new_id = body.get("new_id", "").strip()
    new_name = body.get("new_name", "").strip()

    if new_name:
        cred.name = new_name

    if new_id and new_id != cred_id:
        # Check for conflicts
        existing = await db.get(Credential, new_id)
        if existing:
            raise HTTPException(status_code=409, detail=f"Credential ID '{new_id}' already exists")

        # Update step configs that reference the old credential ID
        from backend.models.step import Step
        steps_result = await db.execute(select(Step))
        for step in steps_result.scalars().all():
            if cred_id in (step.config or ""):
                import json
                cfg = json.loads(step.config)
                if cfg.get("credential_id") == cred_id:
                    cfg["credential_id"] = new_id
                    step.config = json.dumps(cfg, ensure_ascii=False)

        # Update PK via raw SQL (ORM can't change PKs)
        from sqlalchemy import text
        await db.execute(text("UPDATE credentials SET id = :new WHERE id = :old"), {"new": new_id, "old": cred_id})
        await db.flush()

        # Re-fetch with new ID
        cred = await db.get(Credential, new_id)

    await db.flush()
    await notify_activity("renamed", "credential", cred.id, f"From: {cred_id}")
    return _build_response(cred)


@router.post("/{cred_id}/reveal")
async def reveal_credential(cred_id: str, db: AsyncSession = Depends(get_db)):
    cred = await db.get(Credential, cred_id)
    if not cred:
        raise NotFoundError("Credential", cred_id)

    decrypted = _decrypt(cred.encrypted_value)
    return {"id": cred.id, "name": cred.name, "value": decrypted}


@router.post("/{cred_id}/sync-fb-pages")
async def sync_fb_pages(cred_id: str, db: AsyncSession = Depends(get_db)):
    """Use a facebook_user credential to fetch page tokens and link them to Loom pages."""
    cred = await db.get(Credential, cred_id)
    if not cred:
        raise NotFoundError("Credential", cred_id)
    if cred.type != "facebook_user":
        raise HTTPException(status_code=400, detail="Credential must be of type 'facebook_user'")

    user_token = _decrypt(cred.encrypted_value)

    # Optionally exchange for a long-lived user token (page tokens from long-lived tokens never expire)
    if settings.FB_APP_ID and settings.FB_APP_SECRET:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(
                    "https://graph.facebook.com/oauth/access_token",
                    params={
                        "grant_type": "fb_exchange_token",
                        "client_id": settings.FB_APP_ID,
                        "client_secret": settings.FB_APP_SECRET,
                        "fb_exchange_token": user_token,
                    },
                )
                resp.raise_for_status()
                user_token = resp.json()["access_token"]
                # Save long-lived token back so future resyncs don't need a fresh token
                cred.encrypted_value = _encrypt(user_token)
                cred.last_four = user_token[-4:]
                db.add(cred)
                await db.flush()
        except Exception:
            pass  # Token is likely already long-lived — continue with it as-is

    # Fetch all managed pages from Facebook
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                "https://graph.facebook.com/v23.0/me/accounts",
                params={"access_token": user_token, "limit": 200},
            )
            resp.raise_for_status()
            fb_pages = resp.json().get("data", [])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Facebook API error: {e}")

    # Load all Loom pages and PageMeta records
    pages_result = await db.execute(select(Page))
    loom_pages = pages_result.scalars().all()

    meta_result = await db.execute(select(PageMeta))
    metas = {m.page_id: m for m in meta_result.scalars().all()}

    # Build lookup: by fb_page_id (from PageMeta) and by normalized name
    by_fb_id: dict[str, str] = {}
    for page_id, m in metas.items():
        if m.fb_page_id:
            by_fb_id[m.fb_page_id] = page_id

    by_name: dict[str, str] = {p.name.lower().strip(): p.id for p in loom_pages}

    # Load all existing facebook credentials for quick lookup by page_id and by id
    fb_creds_result = await db.execute(
        select(Credential).where(Credential.type == "facebook")
    )
    fb_creds_by_page: dict[str, Credential] = {}
    fb_creds_by_id: dict[str, Credential] = {}
    for fc in fb_creds_result.scalars().all():
        fb_creds_by_id[fc.id] = fc
        if fc.page_id:
            fb_creds_by_page[fc.page_id] = fc

    # Build lookup: loom_page_id → page name for sync result display
    loom_page_names: dict[str, str] = {p.id: p.name for p in loom_pages}

    synced = []
    skipped = []
    seen_loom_ids: set[str] = set()  # Prevent duplicate syncs for same Loom page
    now = datetime.now(timezone.utc)

    for fb_page in fb_pages:
        fb_id = fb_page.get("id", "")
        fb_name = fb_page.get("name", "")
        fb_token = fb_page.get("access_token", "")

        if not fb_token:
            skipped.append({"fb_page_name": fb_name, "fb_page_id": fb_id, "reason": "no access_token in response"})
            continue

        # Find matching Loom page: first by fb_page_id stored in PageMeta, then by name
        loom_by_fb = by_fb_id.get(fb_id)
        loom_by_name = by_name.get(fb_name.lower().strip())
        loom_page_id = loom_by_fb or loom_by_name

        if not loom_page_id:
            skipped.append({"fb_page_name": fb_name, "fb_page_id": fb_id, "reason": "no matching Loom page"})
            continue

        # If fb_id match hits a duplicate, try name match instead (stale fb_page_id in PageMeta)
        if loom_page_id in seen_loom_ids and loom_by_name and loom_by_name not in seen_loom_ids:
            loom_page_id = loom_by_name
        elif loom_page_id in seen_loom_ids:
            resolved_name = loom_page_names.get(loom_page_id, loom_page_id)
            skipped.append({"fb_page_name": fb_name, "fb_page_id": fb_id, "reason": f"duplicate — resolves to '{resolved_name}' which is already linked"})
            continue
        seen_loom_ids.add(loom_page_id)

        encrypted = _encrypt(fb_token)
        last_four = fb_token[-4:] if len(fb_token) >= 4 else fb_token

        # Find existing credential: by page_id first, then by expected ID (fixes wrong page_id)
        expected_id = f"fb-{loom_page_id}"
        existing = fb_creds_by_page.get(loom_page_id) or fb_creds_by_id.get(expected_id)
        if existing:
            existing.encrypted_value = encrypted
            existing.last_four = last_four
            existing.page_id = loom_page_id  # Fix page_id if it was wrong
            existing.name = fb_name
            db.add(existing)
            action = "updated"
        else:
            new_cred = Credential(
                id=expected_id,
                page_id=loom_page_id,
                name=fb_name,
                type="facebook",
                encrypted_value=encrypted,
                last_four=last_four,
            )
            db.add(new_cred)
            action = "created"

        # Update PageMeta: always correct fb_page_id to current FB page
        meta = metas.get(loom_page_id)
        if meta:
            meta.fb_page_id = fb_id
            if not meta.fb_ready_at:
                meta.fb_ready_at = now
            db.add(meta)
        else:
            new_meta = PageMeta(
                page_id=loom_page_id,
                fb_page_id=fb_id,
                fb_ready_at=now,
            )
            db.add(new_meta)

        synced.append({
            "loom_page_id": loom_page_id,
            "loom_page_name": loom_page_names.get(loom_page_id, loom_page_id),
            "fb_page_name": fb_name,
            "fb_page_id": fb_id,
            "action": action,
        })

    await db.flush()

    if synced:
        await notify_activity("synced", "FB pages", cred_id, f"{len(synced)} synced, {len(skipped)} skipped")

    return {
        "synced": synced,
        "skipped": skipped,
        "total_fb_pages": len(fb_pages),
        "total_synced": len(synced),
        "total_skipped": len(skipped),
    }
