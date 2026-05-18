from fastapi import APIRouter, Depends, HTTPException
from app.auth import verify_api_key
from app.database import get_db
from app.crypto import encrypt_value, decrypt_value, mask_value
from app.models import CredentialCreate, CredentialUpdate, CredentialOut

router = APIRouter(prefix="/api/credentials", tags=["credentials"], dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_credentials():
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM credentials ORDER BY name")
        rows = await cursor.fetchall()
        result = []
        for row in rows:
            decrypted = decrypt_value(row["encrypted_value"])
            result.append(CredentialOut(
                id=row["id"],
                name=row["name"],
                service=row["service"],
                masked_value=mask_value(decrypted),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            ).model_dump())
        return result
    finally:
        await db.close()


@router.get("/{credential_id}")
async def get_credential(credential_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Credential '{credential_id}' not found")
        decrypted = decrypt_value(row["encrypted_value"])
        return CredentialOut(
            id=row["id"],
            name=row["name"],
            service=row["service"],
            masked_value=mask_value(decrypted),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        ).model_dump()
    finally:
        await db.close()


@router.get("/{credential_id}/reveal")
async def reveal_credential(credential_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Credential '{credential_id}' not found")
        return {"id": row["id"], "value": decrypt_value(row["encrypted_value"])}
    finally:
        await db.close()


@router.post("")
async def create_credential(data: CredentialCreate):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT id FROM credentials WHERE id = ?", (data.id,))
        if await cursor.fetchone():
            raise HTTPException(status_code=409, detail=f"Credential '{data.id}' already exists")
        encrypted = encrypt_value(data.value)
        await db.execute(
            "INSERT INTO credentials (id, name, service, encrypted_value) VALUES (?, ?, ?, ?)",
            (data.id, data.name, data.service, encrypted),
        )
        await db.commit()
        return {"id": data.id, "name": data.name, "service": data.service, "masked_value": mask_value(data.value)}
    finally:
        await db.close()


@router.put("/{credential_id}")
async def update_credential(credential_id: str, data: CredentialUpdate):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM credentials WHERE id = ?", (credential_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Credential '{credential_id}' not found")

        updates = []
        params = []
        if data.name is not None:
            updates.append("name = ?")
            params.append(data.name)
        if data.service is not None:
            updates.append("service = ?")
            params.append(data.service)
        if data.value is not None:
            updates.append("encrypted_value = ?")
            params.append(encrypt_value(data.value))
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(credential_id)
            await db.execute(f"UPDATE credentials SET {', '.join(updates)} WHERE id = ?", params)
            await db.commit()
        return {"updated": credential_id}
    finally:
        await db.close()


@router.delete("/{credential_id}")
async def delete_credential(credential_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM credentials WHERE id = ?", (credential_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Credential '{credential_id}' not found")
        await db.commit()
        return {"deleted": credential_id}
    finally:
        await db.close()
