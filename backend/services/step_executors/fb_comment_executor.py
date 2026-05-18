"""Facebook Comment executor — comment on a post via Graph API."""
import json
import logging

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.credential import Credential
from backend.services.credential_service import credential_service
from backend.services.step_executors.base import BaseExecutor
from backend.services.step_executors.fb_post_executor import _raise_fb_error
from backend.services.template_engine import resolve_variables

logger = logging.getLogger(__name__)

FB_GRAPH_URL = "https://graph.facebook.com/v23.0"


class FBCommentExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_fb_token(self, credential_id: str) -> str:
        if not credential_id:
            raise ValueError("Facebook Comment: no credential selected. Please select a Facebook credential in the step config.")
        cred = await self.db.get(Credential, credential_id)
        if not cred:
            raise ValueError(f"Facebook Comment: credential '{credential_id}' not found. It may have been deleted.")
        return credential_service.decrypt(cred.encrypted_value)

    async def execute(self, config: dict, variables: dict) -> str:
        post_id = resolve_variables(config.get("post_id", ""), variables)
        message = resolve_variables(config.get("message", ""), variables)

        if not post_id:
            raise ValueError("Facebook Comment: post_id is required but is empty or unresolved.")

        access_token = await self._get_fb_token(config.get("credential_id", ""))

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                f"{FB_GRAPH_URL}/{post_id}/comments",
                data={
                    "access_token": access_token,
                    "message": message,
                },
            )
            _raise_fb_error(response)
            data = response.json()

        return json.dumps(data, ensure_ascii=False)
