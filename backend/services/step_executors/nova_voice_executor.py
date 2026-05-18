"""Nova Voice executor — generate voice audio via Nova API."""
import json
import os

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.credential import Credential
from backend.services.credential_service import credential_service
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables

NOVA_VOICE_URL = os.environ.get("NOVA_VOICE_URL", "")


class NovaVoiceExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_nova_token(self, credential_id: str) -> str:
        if not credential_id:
            raise ValueError("Nova Voice: no credential selected. Please select a Nova credential in the step config.")
        cred = await self.db.get(Credential, credential_id)
        if not cred:
            raise ValueError(f"Nova Voice: credential '{credential_id}' not found. It may have been deleted.")
        token = credential_service.decrypt(cred.encrypted_value)
        if token.startswith("Bearer "):
            token = token[7:]
        return token

    async def execute(self, config: dict, variables: dict) -> str:
        if not NOVA_VOICE_URL:
            raise ValueError("Nova Voice: NOVA_VOICE_URL not configured. Set it in .env to use this executor.")

        input_text = resolve_variables(config.get("input_text", ""), variables)
        voice = config.get("voice", "Algieba")
        style = config.get("style", "auto")

        if not input_text:
            raise ValueError("Nova Voice: input_text is required but is empty or unresolved.")

        token = await self._get_nova_token(config.get("credential_id", ""))

        try:
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(
                    NOVA_VOICE_URL,
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json={
                        "input": input_text,
                        "voice": voice,
                        "style": style,
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.TimeoutException:
            raise RuntimeError("Nova Voice API timed out after 300s. The request may still be processing server-side.")
        except httpx.HTTPStatusError as e:
            raise RuntimeError(f"Nova Voice API returned {e.response.status_code}: {e.response.text[:500]}")

        # Return the audio_url for use by subsequent steps
        audio_url = data.get("audio_url", "")
        return json.dumps(data, ensure_ascii=False) if not audio_url else audio_url
