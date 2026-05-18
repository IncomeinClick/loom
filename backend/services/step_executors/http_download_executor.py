"""HTTP Download executor — download a URL to a local binary file."""
import json
from pathlib import Path
from uuid import uuid4

import httpx

from backend.config import settings
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables

# Map common content-types to extensions
EXT_MAP = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/quicktime": ".mov",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
}


class HTTPDownloadExecutor(BaseExecutor):
    async def execute(self, config: dict, variables: dict) -> str:
        url = resolve_variables(config.get("url", ""), variables)
        if not url:
            raise ValueError("No URL provided for download")

        save_dir = settings.ASSETS_DIR / "downloads"
        save_dir.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=300, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Determine file extension from content-type
            content_type = response.headers.get("content-type", "").split(";")[0].strip()
            ext = EXT_MAP.get(content_type, "")

            # Fallback: try to get extension from URL path
            if not ext:
                url_path = url.split("?")[0]
                if "." in url_path.split("/")[-1]:
                    ext = "." + url_path.split("/")[-1].rsplit(".", 1)[-1]
                else:
                    ext = ".bin"

            filename = f"{uuid4().hex[:12]}{ext}"
            save_path = save_dir / filename
            save_path.write_bytes(response.content)

        return str(save_path)
