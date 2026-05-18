"""LLM step executor — calls OpenAI, Gemini, or Anthropic APIs.

Supports optional datatable lookup: if config contains `lookup_table_id`,
all rows from that table are fetched and injected as {{datatable}} variable
before prompt resolution.

Keyword dedup: when lookup is configured with a single column, the executor
checks whether the LLM output duplicates an existing value and retries up
to 3 times with increasing temperature.
"""
import json
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.models.credential import Credential
from backend.models.datatable import DataRow
from backend.services.credential_service import credential_service
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables

log = logging.getLogger(__name__)


class LLMExecutor(BaseExecutor):
    DEDUP_MAX_RETRIES = 3

    def __init__(self, db: AsyncSession | None = None):
        self.db = db

    async def _get_api_key(self, credential_id: str) -> str | None:
        """Look up API key from stored credential. Returns None to fall back to env vars.

        Raises if credential_id is set but the credential no longer exists.
        """
        if not credential_id or not self.db:
            return None
        cred = await self.db.get(Credential, credential_id)
        if not cred:
            raise ValueError(f"LLM: credential '{credential_id}' not found. It may have been deleted.")
        return credential_service.decrypt(cred.encrypted_value)

    async def execute(self, config: dict, variables: dict) -> str:
        # Optional datatable lookup — inject as {{datatable}}
        lookup_table_id = config.get("lookup_table_id", "")
        dedup_values: set[str] = set()
        if lookup_table_id and self.db:
            lookup_columns = config.get("lookup_columns", "")
            columns = [c.strip() for c in lookup_columns.split(",") if c.strip()] if lookup_columns else []
            lookup_limit = config.get("lookup_limit", None)
            if lookup_limit is not None:
                try:
                    lookup_limit = int(lookup_limit)
                except (ValueError, TypeError):
                    lookup_limit = None
            lookup_data, dedup_values = await self._lookup_datatable(lookup_table_id, columns, lookup_limit)
            variables["datatable"] = lookup_data

        model = config.get("model", "gpt-4o-mini")
        provider = config.get("provider", "")
        system_prompt = resolve_variables(config.get("system_prompt", ""), variables)
        user_prompt = resolve_variables(config.get("user_prompt", ""), variables)
        # Gemini 3 thinking level — defaults to "minimal" (no thinking) when unset.
        # Valid values: minimal, low, medium, high. Only applies to gemini-3* models.
        thinking_level = config.get("thinking_level", "minimal")

        # Resolve API key: credential is required for LLM steps
        credential_id = config.get("credential_id", "")
        if not credential_id:
            raise ValueError(f"LLM: no credential selected. Please choose a {provider} credential for this step.")
        api_key = await self._get_api_key(credential_id)

        # Route by explicit provider field; fall back to model prefix for legacy configs
        if not provider:
            if model.startswith("gemini"):
                provider = "gemini"
            elif model.startswith("claude"):
                provider = "anthropic"
            else:
                provider = "openai"

        # Call LLM with dedup retry when lookup is active
        result = await self._call_llm(provider, model, system_prompt, user_prompt, api_key, thinking_level=thinking_level)

        if dedup_values:
            base_temp = 0.7
            for attempt in range(1, self.DEDUP_MAX_RETRIES + 1):
                if result.strip().lower() not in dedup_values:
                    break
                retry_temp = min(base_temp + attempt * 0.3, 1.5)
                log.warning(
                    "LLM dedup: '%s' already exists (attempt %d/%d), retrying with temp=%.1f",
                    result.strip(), attempt, self.DEDUP_MAX_RETRIES, retry_temp,
                )
                result = await self._call_llm(
                    provider, model, system_prompt, user_prompt, api_key,
                    temperature=retry_temp,
                    thinking_level=thinking_level,
                )

        return result

    async def _lookup_datatable(
        self, table_id: str, columns: list[str] | None = None, limit: int | None = None,
    ) -> tuple[str, set[str]]:
        """Fetch rows from a datatable.

        Returns:
            (lookup_text, dedup_values)
            - lookup_text: If a single column is requested, returns a simple
              comma-separated list (much easier for LLMs to read).
              Otherwise returns a JSON array of objects.
            - dedup_values: A lowercase set of all single-column values, used
              for the retry dedup check. Empty set if multiple/no columns.
        """
        query = (
            select(DataRow)
            .where(DataRow.datatable_id == table_id)
            .order_by(DataRow.created_at.desc())
        )
        if limit and limit > 0:
            query = query.limit(limit)
        result = await self.db.execute(query)
        rows = result.scalars().all()

        parsed = []
        dedup_values: set[str] = set()
        single_col = columns[0] if columns and len(columns) == 1 else None

        for row in rows:
            try:
                data = json.loads(row.data) if isinstance(row.data, str) else row.data
                if columns:
                    data = {k: v for k, v in data.items() if k in columns}
                parsed.append(data)
                if single_col and single_col in data and data[single_col]:
                    dedup_values.add(str(data[single_col]).strip().lower())
            except (json.JSONDecodeError, TypeError):
                continue

        # Single column → comma-separated list for clarity
        if single_col:
            values = [str(d[single_col]) for d in parsed if single_col in d and d[single_col]]
            # Deduplicate the display list to save tokens
            seen = set()
            unique_values = []
            for v in values:
                if v.lower() not in seen:
                    seen.add(v.lower())
                    unique_values.append(v)
            lookup_text = ", ".join(unique_values)
        else:
            lookup_text = json.dumps(parsed, ensure_ascii=False)

        return lookup_text, dedup_values

    async def _call_llm(
        self, provider: str, model: str, system_prompt: str, user_prompt: str,
        api_key: str, temperature: float = 0.7, thinking_level: str = "minimal",
    ) -> str:
        """Route to the correct provider."""
        if provider == "gemini":
            return await self._call_gemini(model, system_prompt, user_prompt, api_key, temperature, thinking_level)
        elif provider == "anthropic":
            return await self._call_anthropic(model, system_prompt, user_prompt, api_key, temperature)
        else:
            return await self._call_openai(model, system_prompt, user_prompt, api_key, temperature)

    async def _call_openai(self, model: str, system_prompt: str, user_prompt: str, api_key: str, temperature: float = 0.7) -> str:
        key = api_key
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()

    async def _call_gemini(self, model: str, system_prompt: str, user_prompt: str, api_key: str, temperature: float = 0.7, thinking_level: str = "minimal") -> str:
        key = api_key
        generation_config: dict = {"temperature": temperature}
        # Gemini 3 supports thinkingLevel in {minimal, low, medium, high}.
        # Default is "minimal" (no thinking) when the step config doesn't set one.
        # Gemini 2.5 uses a different field (thinkingBudget) — leave it alone here.
        if model.startswith("gemini-3"):
            generation_config["thinkingConfig"] = {"thinkingLevel": thinking_level}
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                params={"key": key},
                headers={"Content-Type": "application/json"},
                json={
                    "system_instruction": {
                        "parts": [{"text": system_prompt}]
                    },
                    "contents": [
                        {
                            "parts": [{"text": user_prompt}]
                        }
                    ],
                    "generationConfig": generation_config,
                },
            )
            response.raise_for_status()
            data = response.json()

            # Handle missing or blocked responses from Gemini
            candidates = data.get("candidates")
            if not candidates:
                block_reason = data.get("promptFeedback", {}).get("blockReason", "unknown")
                raise ValueError(f"Gemini returned no candidates (blockReason: {block_reason})")

            content = candidates[0].get("content")
            if not content or not content.get("parts"):
                finish_reason = candidates[0].get("finishReason", "unknown")
                raise ValueError(f"Gemini returned no content parts (finishReason: {finish_reason})")

            return content["parts"][0]["text"].strip()

    async def _call_anthropic(self, model: str, system_prompt: str, user_prompt: str, api_key: str, temperature: float = 0.7) -> str:
        key = api_key
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": [
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["content"][0]["text"].strip()
