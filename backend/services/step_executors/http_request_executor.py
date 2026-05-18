"""HTTP Request executor — make generic HTTP requests.

Config:
  - method: GET, POST, PUT, DELETE, PATCH
  - url: target URL (supports {{variables}})
  - headers: JSON string of headers (supports {{variables}})
  - body: request body string (supports {{variables}})
  - body_type: "json" | "text" | "form" (default: "json")
  - credential_id: optional credential for Authorization header
"""
import json

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.credential import Credential
from backend.services.credential_service import credential_service
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables


class HTTPRequestExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, config: dict, variables: dict) -> str:
        method = config.get("method", "GET").upper()
        url = resolve_variables(config.get("url", ""), variables)
        body = resolve_variables(config.get("body", ""), variables)
        body_type = config.get("body_type", "json")

        if not url:
            raise ValueError("HTTP Request: url is required")

        # Parse headers
        headers = {}
        headers_raw = config.get("headers", "")
        if headers_raw:
            resolved = resolve_variables(headers_raw, variables)
            try:
                headers = json.loads(resolved)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid headers JSON: {resolved[:200]}")

        # Add credential as Authorization header if specified
        credential_id = config.get("credential_id", "")
        if credential_id:
            cred = await self.db.get(Credential, credential_id)
            if not cred:
                raise ValueError(f"HTTP Request: credential '{credential_id}' not found. It may have been deleted.")
            token = credential_service.decrypt(cred.encrypted_value)
            # Don't override if headers already has Authorization
            if "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {token}"

        # Build request kwargs
        kwargs: dict = {"method": method, "url": url, "headers": headers, "timeout": 120}

        if method in ("POST", "PUT", "PATCH") and body:
            if body_type == "json":
                try:
                    kwargs["json"] = json.loads(body)
                except json.JSONDecodeError:
                    # Fall back to sending as text
                    kwargs["content"] = body
                    headers.setdefault("Content-Type", "application/json")
            elif body_type == "form":
                try:
                    kwargs["data"] = json.loads(body)
                except json.JSONDecodeError:
                    kwargs["content"] = body
            else:
                kwargs["content"] = body

        async with httpx.AsyncClient() as client:
            response = await client.request(**kwargs)
            response.raise_for_status()

            # Try to return as JSON, fall back to text
            try:
                data = response.json()
                return json.dumps(data, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                return response.text
