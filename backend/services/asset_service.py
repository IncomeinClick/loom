"""Asset generation service — profile images, cover photos, bios via Gemini API."""
import base64
import logging
from pathlib import Path

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


async def generate_profile_image(page_name: str, theme: str) -> tuple[bytes, str]:
    """Generate a profile image using Gemini.

    Returns (image_bytes, saved_path).
    """
    prompt = (
        f"Create a profile image for a Facebook page called '{page_name}'. "
        f"Theme/style: {theme}. "
        "REQUIREMENTS: "
        "- Single layer background only — no combining two images, no double layers, no inner panel, no card effect. "
        "- Background is creative — any style, no restrictions. "
        "- All key elements (illustration + page name text) centered within the middle 70% of the image — safe for Facebook's circle crop. "
        "- NO white space, NO rounded corners, NO borders. "
        "- Page name text centered below main illustration. "
        "- Square aspect ratio (1:1). "
        "- High quality, vibrant colors."
    )

    image_bytes = await _generate_image(prompt)

    # Save to disk
    save_dir = settings.ASSETS_DIR / _slugify(page_name)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / "profile.png"
    save_path.write_bytes(image_bytes)

    relative_path = f"assets/{_slugify(page_name)}/profile.png"
    return image_bytes, relative_path


async def generate_cover_photo(page_name: str, theme: str) -> tuple[bytes, str]:
    """Generate a cover photo using Gemini.

    Returns (image_bytes, saved_path).
    """
    prompt = (
        f"Create a Facebook cover photo for a page called '{page_name}'. "
        f"Theme/style: {theme}. "
        "REQUIREMENTS: "
        "- Wide landscape composition — background fills edge to edge, no blank bars top or bottom. "
        "- NO text of any kind — pure illustration only. "
        "- Background extends fully to all edges. "
        "- Aspect ratio approximately 820x312 (Facebook cover photo dimensions). "
        "- High quality, vibrant colors, visually stunning."
    )

    image_bytes = await _generate_image(prompt)

    # Save to disk
    save_dir = settings.ASSETS_DIR / _slugify(page_name)
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / "cover.png"
    save_path.write_bytes(image_bytes)

    relative_path = f"assets/{_slugify(page_name)}/cover.png"
    return image_bytes, relative_path


async def generate_bio(page_name: str, language: str, niche_description: str) -> str:
    """Generate a Facebook page bio using Gemini."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
            params={"key": settings.GEMINI_API_KEY},
            json={
                "contents": [{
                    "parts": [{
                        "text": (
                            f"Write a short Facebook page bio (2-3 sentences, max 255 characters) "
                            f"for a page called '{page_name}'. "
                            f"Niche/topic: {niche_description}. "
                            f"Language: {language}. "
                            f"Write ONLY the bio text, nothing else."
                        )
                    }]
                }],
            },
        )
        response.raise_for_status()
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


async def _generate_image(prompt: str) -> bytes:
    """Call Gemini image generation API and return image bytes."""
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-image-preview:generateContent",
            params={"key": settings.GEMINI_API_KEY},
            json={
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                },
            },
        )
        response.raise_for_status()
        data = response.json()

        # Extract base64 image from response
        for part in data["candidates"][0]["content"]["parts"]:
            if "inlineData" in part:
                image_b64 = part["inlineData"]["data"]
                return base64.b64decode(image_b64)

        raise ValueError("No image data in Gemini response")


def _slugify(text: str) -> str:
    """Simple slugify for directory names."""
    import re
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text).strip("-")
