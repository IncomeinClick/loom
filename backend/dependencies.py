from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.database import get_session


async def get_db(session: AsyncSession = Depends(get_session)):
    try:
        yield session
        await session.commit()
    except Exception:
        await session.rollback()
        raise


async def verify_token(authorization: str = Header(default="")):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if token != settings.API_BEARER_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid token")
