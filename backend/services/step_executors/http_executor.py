"""HTTP step executor — calls external APIs."""
import json

import httpx

from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables, resolve_dict


class HTTPExecutor(BaseExecutor):
    async def execute(self, config: dict, variables: dict) -> str:
        method = config.get("method", "GET").upper()
        url = resolve_variables(config.get("url", ""), variables)
        headers = resolve_dict(config.get("headers", {}), variables)
        body = config.get("body")
        json_path = config.get("json_path")

        if not url:
            raise ValueError("HTTP: url is required but is empty or unresolved.")

        # Resolve body variables
        if body and isinstance(body, dict):
            body = resolve_dict(body, variables)
        elif body and isinstance(body, str):
            body = resolve_variables(body, variables)

        # Inject credential auth if specified
        credential_token = config.get("credential_token")
        if credential_token:
            token = resolve_variables(credential_token, variables)
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=120) as client:
            if method in ("POST", "PUT", "PATCH"):
                if isinstance(body, dict):
                    response = await client.request(method, url, headers=headers, json=body)
                else:
                    response = await client.request(method, url, headers=headers, content=body)
            else:
                response = await client.request(method, url, headers=headers)

            response.raise_for_status()

            # Try to parse JSON response
            try:
                data = response.json()
                # If json_path specified, extract value
                if json_path:
                    for key in json_path.split("."):
                        if isinstance(data, dict):
                            data = data.get(key, data)
                        elif isinstance(data, list) and key.isdigit():
                            data = data[int(key)]
                    return str(data) if not isinstance(data, str) else data
                return json.dumps(data, ensure_ascii=False)
            except (json.JSONDecodeError, ValueError):
                return response.text
