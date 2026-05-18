import json
import base64
import httpx
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from app.auth import verify_api_key
from app.config import settings
from app.database import get_db
from app.crypto import decrypt_value
from app.models import GenerateImageRequest, GenerateBioRequest

router = APIRouter(prefix="/api/assets", tags=["assets"], dependencies=[Depends(verify_api_key)])

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent"


async def _get_gemini_key() -> str:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT encrypted_value FROM credentials WHERE service = 'gemini' LIMIT 1")
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="No Gemini API credential found. Add a credential with service='gemini'.")
        return decrypt_value(row["encrypted_value"])
    finally:
        await db.close()


async def _get_openai_key() -> str:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT encrypted_value FROM credentials WHERE service = 'openai' LIMIT 1")
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="No OpenAI API credential found. Add a credential with service='openai'.")
        return decrypt_value(row["encrypted_value"])
    finally:
        await db.close()


async def _call_gemini_image(prompt: str, api_key: str) -> bytes:
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{GEMINI_API_URL}?key={api_key}",
            json=payload,
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Gemini API error: {resp.text}")
        data = resp.json()

    # Extract base64 image from response
    try:
        parts = data["candidates"][0]["content"]["parts"]
        for part in parts:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])
        raise HTTPException(status_code=502, detail="Gemini returned no image data")
    except (KeyError, IndexError) as e:
        raise HTTPException(status_code=502, detail=f"Unexpected Gemini response format: {e}")


def _ensure_page_assets_dir(page_id: str) -> Path:
    dir_path = settings.assets_path / page_id
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


@router.post("/generate/profile/{page_id}")
async def generate_profile_image(page_id: str, data: GenerateImageRequest):
    api_key = await _get_gemini_key()

    prompt = f"""Create a profile image for a Facebook page called "{data.page_name}".
Style/theme: {data.style_description}

STRICT REQUIREMENTS — follow ALL of these exactly:
- Single layer background ONLY — do NOT combine two images, no double layers, no inner panel, no card effect, no frame
- The background should be creative and visually striking — any artistic style is allowed
- All key elements (main illustration + page name text) must be centered within the MIDDLE 70% of the image — this is critical because Facebook crops profile images into a circle
- The page name "{data.page_name}" must appear as text centered below the main illustration
- NO white space around edges
- NO rounded corners
- NO borders of any kind
- The image should fill the entire canvas edge to edge
- Square aspect ratio (1:1)
- High quality, vibrant, professional look"""

    image_bytes = await _call_gemini_image(prompt, api_key)

    assets_dir = _ensure_page_assets_dir(page_id)
    image_path = assets_dir / "profile.png"
    image_path.write_bytes(image_bytes)

    # Update page config
    _update_page_asset(page_id, "profile_image", f"assets/{page_id}/profile.png")

    return {
        "status": "ok",
        "path": f"assets/{page_id}/profile.png",
        "image_base64": base64.b64encode(image_bytes).decode(),
    }


@router.post("/generate/cover/{page_id}")
async def generate_cover_photo(page_id: str, data: GenerateImageRequest):
    api_key = await _get_gemini_key()

    prompt = f"""Create a cover photo for a Facebook page called "{data.page_name}".
Style/theme: {data.style_description}

STRICT REQUIREMENTS — follow ALL of these exactly:
- Wide LANDSCAPE composition (820x312 ratio preferred)
- The background illustration must fill edge to edge — NO blank bars on top or bottom
- NO text of any kind — this must be pure illustration only, zero text, zero letters, zero words
- The background extends fully to ALL edges of the image
- No borders, no frames, no panels
- High quality, vibrant, professional look
- The artwork should match the theme and feel of the page"""

    image_bytes = await _call_gemini_image(prompt, api_key)

    assets_dir = _ensure_page_assets_dir(page_id)
    image_path = assets_dir / "cover.png"
    image_path.write_bytes(image_bytes)

    _update_page_asset(page_id, "cover_photo", f"assets/{page_id}/cover.png")

    return {
        "status": "ok",
        "path": f"assets/{page_id}/cover.png",
        "image_base64": base64.b64encode(image_bytes).decode(),
    }


@router.post("/generate/bio/{page_id}")
async def generate_bio(page_id: str, data: GenerateBioRequest):
    # Try OpenAI first, fall back to Gemini
    try:
        api_key = await _get_openai_key()
        bio = await _generate_bio_openai(data, api_key)
    except HTTPException:
        api_key = await _get_gemini_key()
        bio = await _generate_bio_gemini(data, api_key)

    _update_page_asset(page_id, "bio", bio)
    return {"status": "ok", "bio": bio}


async def _generate_bio_openai(data: GenerateBioRequest, api_key: str) -> str:
    prompt = f"""Write a short Facebook page bio for "{data.page_name}".
Language: {data.language}
Market: {data.market}
Niche: {data.niche_description}

Requirements:
- 1-2 sentences max
- Engaging and inviting
- Written in {data.language}
- Include what the page is about
- Do NOT include hashtags
- Return ONLY the bio text, nothing else"""

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 200,
            },
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"OpenAI error: {resp.text}")
        return resp.json()["choices"][0]["message"]["content"].strip()


async def _generate_bio_gemini(data: GenerateBioRequest, api_key: str) -> str:
    prompt = f"""Write a short Facebook page bio for "{data.page_name}".
Language: {data.language}. Market: {data.market}. Niche: {data.niche_description}.
1-2 sentences max, engaging, written in {data.language}. No hashtags. Return ONLY the bio text."""

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{url}?key={api_key}",
            json={"contents": [{"parts": [{"text": prompt}]}]},
        )
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Gemini error: {resp.text}")
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


def _update_page_asset(page_id: str, field: str, value: str):
    page_path = settings.pages_path / f"{page_id}.json"
    if not page_path.exists():
        return
    page = json.loads(page_path.read_text(encoding="utf-8"))
    if "assets" not in page:
        page["assets"] = {}
    page["assets"][field] = value
    page_path.write_text(json.dumps(page, indent=2, ensure_ascii=False), encoding="utf-8")


@router.get("/file/{page_id}/{filename}")
async def get_asset_file(page_id: str, filename: str):
    file_path = settings.assets_path / page_id / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Asset file not found")
    return FileResponse(str(file_path), media_type="image/png")
