"""Facebook Post executor — post photo/video via Graph API.

Supports both binary file upload (local paths) and URL-based posting.
"""
import json
import logging
from pathlib import Path

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from backend.models.credential import Credential
from backend.services.credential_service import credential_service
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables

FB_GRAPH_URL = "https://graph.facebook.com/v23.0"

MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".webm": "video/webm",
}


def _raise_fb_error(response: httpx.Response) -> None:
    """Raise a clear error with Facebook's actual error message instead of generic httpx 400."""
    if response.is_success:
        return
    try:
        err = response.json().get("error", {})
        msg = err.get("message", response.text)
        code = err.get("code", "")
        subcode = err.get("error_subcode", "")
        user_msg = err.get("error_user_msg", "")
        detail = f"Facebook API error {code}"
        if subcode:
            detail += f"/{subcode}"
        detail += f": {msg}"
        if user_msg:
            detail += f" — {user_msg}"
        logger.error(f"FB Post failed: {detail}")
        raise ValueError(detail)
    except (json.JSONDecodeError, AttributeError):
        response.raise_for_status()


class FBPostExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_fb_token(self, credential_id: str) -> str:
        if not credential_id:
            raise ValueError("Facebook Post: no credential selected. Please select a Facebook credential in the step config.")
        cred = await self.db.get(Credential, credential_id)
        if not cred:
            raise ValueError(f"Facebook Post: credential '{credential_id}' not found. It may have been deleted.")
        return credential_service.decrypt(cred.encrypted_value)

    def _is_local_file(self, path: str) -> bool:
        """Check if the media_url is a local file path (not a URL)."""
        if path.startswith(("http://", "https://")):
            return False
        return Path(path).exists()

    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".webm"}

    def _detect_media_type(self, media_url: str, config_type: str) -> str:
        """Auto-detect media type from file extension, falling back to config value."""
        ext = Path(media_url).suffix.lower()
        if ext in self.IMAGE_EXTENSIONS:
            detected = "photo"
        elif ext in self.VIDEO_EXTENSIONS:
            detected = "video"
        else:
            return config_type
        if detected != config_type:
            logger.warning(f"FB Post: config says '{config_type}' but file is '{media_url}' — using '{detected}'")
        return detected

    async def execute(self, config: dict, variables: dict) -> str:
        media_type = config.get("media_type", "photo")
        media_url = resolve_variables(config.get("media_url", ""), variables)
        message = resolve_variables(config.get("message", ""), variables)

        if not media_url:
            raise ValueError("Facebook Post: media_url is required but is empty or unresolved.")

        # Auto-detect from file extension to prevent mismatches
        media_type = self._detect_media_type(media_url, media_type)

        access_token = await self._get_fb_token(config.get("credential_id", ""))
        edge = "photos" if media_type == "photo" else "videos"
        logger.info(f"FB Post: media_type={media_type}, edge={edge}, url={media_url[:80]}")

        if self._is_local_file(media_url):
            data = await self._post_binary(access_token, edge, media_type, media_url, message)
        else:
            data = await self._post_url(access_token, edge, media_type, media_url, message)

        # Return post ID for use by fb_comment step
        post_id = data.get("id", data.get("post_id", ""))
        return post_id if post_id else json.dumps(data, ensure_ascii=False)

    async def _post_binary(
        self, access_token: str, edge: str, media_type: str, file_path: str, message: str
    ) -> dict:
        """Upload local binary file to Facebook."""
        path = Path(file_path)
        mime = MIME_MAP.get(path.suffix.lower(), "application/octet-stream")
        file_bytes = path.read_bytes()

        msg_key = "message" if media_type == "photo" else "description"

        files = {"source": (path.name, file_bytes, mime)}
        form_data = {"access_token": access_token}
        if message:
            form_data[msg_key] = message

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{FB_GRAPH_URL}/me/{edge}",
                data=form_data,
                files=files,
            )
            _raise_fb_error(response)
            return response.json()

    async def _post_url(
        self, access_token: str, edge: str, media_type: str, media_url: str, message: str
    ) -> dict:
        """Post media via URL (Facebook downloads from the URL)."""
        url_key = "url" if media_type == "photo" else "file_url"
        msg_key = "message" if media_type == "photo" else "description"

        params = {
            "access_token": access_token,
            url_key: media_url,
        }
        if message:
            params[msg_key] = message

        async with httpx.AsyncClient(timeout=300) as client:
            response = await client.post(
                f"{FB_GRAPH_URL}/me/{edge}",
                data=params,
            )
            _raise_fb_error(response)
            return response.json()
