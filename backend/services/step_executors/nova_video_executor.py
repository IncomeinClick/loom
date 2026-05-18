"""Nova Video executor — generate video via Nova API."""
import json
import os

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.credential import Credential
from backend.services.credential_service import credential_service
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables

NOVA_VIDEO_URL = os.environ.get("NOVA_VIDEO_URL", "")


class NovaVideoExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_nova_token(self, credential_id: str) -> str:
        if not credential_id:
            raise ValueError("Nova Video: no credential selected. Please select a Nova credential in the step config.")
        cred = await self.db.get(Credential, credential_id)
        if not cred:
            raise ValueError(f"Nova Video: credential '{credential_id}' not found. It may have been deleted.")
        token = credential_service.decrypt(cred.encrypted_value)
        if token.startswith("Bearer "):
            token = token[7:]
        return token

    async def execute(self, config: dict, variables: dict) -> str:
        if not NOVA_VIDEO_URL:
            raise ValueError("Nova Video: NOVA_VIDEO_URL not configured. Set it in .env to use this executor.")

        audio_url = resolve_variables(config.get("audio_url", ""), variables)
        video_script = resolve_variables(config.get("video_script", ""), variables)
        image_style = config.get("image_style", "photorealistic")
        image_model = config.get("image_model", "flux")

        if not audio_url:
            raise ValueError("Nova Video: audio_url is required but is empty or unresolved.")

        token = await self._get_nova_token(config.get("credential_id", ""))

        async with httpx.AsyncClient(timeout=1800) as client:
            response = await client.post(
                NOVA_VIDEO_URL,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={
                    "audio_url": audio_url,
                    "video_script": video_script,
                    "image_style": image_style,
                    "image_model": image_model,
                },
            )
            response.raise_for_status()
            data = response.json()

        # Return the video_url for use by subsequent steps
        video_url = data.get("video_url", "")
        return json.dumps(data, ensure_ascii=False) if not video_url else video_url
