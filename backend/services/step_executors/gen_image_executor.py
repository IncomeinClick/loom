"""Gen Image executor — generate image via Gemini."""
import base64
from uuid import uuid4

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.credential import Credential
from backend.services.credential_service import credential_service
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables

DEFAULT_MODEL = "gemini-2.5-flash-image"


class GenImageExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession | None = None):
        self.db = db

    async def _get_api_key(self, credential_id: str) -> str | None:
        """Look up API key from stored credential. Falls back to env var."""
        if not credential_id or not self.db:
            return None
        cred = await self.db.get(Credential, credential_id)
        if not cred:
            raise ValueError(f"gen_image: credential '{credential_id}' not found. It may have been deleted.")
        return credential_service.decrypt(cred.encrypted_value)

    async def execute(self, config: dict, variables: dict) -> str:
        prompt = resolve_variables(config.get("prompt", ""), variables)
        model = config.get("model", DEFAULT_MODEL)
        # Strip "models/" prefix if present (API URL already includes it)
        if model.startswith("models/"):
            model = model[len("models/"):]
        api_key = await self._get_api_key(config.get("credential_id", ""))
        key = api_key or settings.GEMINI_API_KEY

        if not key:
            raise ValueError("gen_image: no API key — set credential_id in step config or GEMINI_API_KEY in .env")

        image_bytes = await self._generate_image(prompt, model, key)

        # Save to data/assets/generated/
        save_dir = settings.ASSETS_DIR / "generated"
        save_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{uuid4().hex[:12]}.png"
        save_path = save_dir / filename
        save_path.write_bytes(image_bytes)

        return str(save_path)

    async def _generate_image(self, prompt: str, model: str, key: str) -> bytes:
        """Call Gemini image generation API and return image bytes."""
        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": key},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "responseModalities": ["TEXT", "IMAGE"],
                    },
                },
            )
            response.raise_for_status()
            data = response.json()

            candidates = data.get("candidates")
            if not candidates:
                block_reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
                raise ValueError(f"Gemini returned no candidates (blockReason: {block_reason})")

            content = candidates[0].get("content")
            if not content or not content.get("parts"):
                finish_reason = candidates[0].get("finishReason", "unknown")
                raise ValueError(f"Gemini returned no content parts (finishReason: {finish_reason})")

            for part in content["parts"]:
                if "inlineData" in part:
                    return base64.b64decode(part["inlineData"]["data"])

            raise ValueError("No image data in Gemini response")
