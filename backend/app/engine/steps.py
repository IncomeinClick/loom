import json
import httpx
from app.database import get_db
from app.crypto import decrypt_value


async def execute_step(step: dict, variables: dict) -> str | None:
    """Execute a single step and return its output."""
    step_type = step.get("type", "")

    if step_type == "llm":
        return await _execute_llm(step)
    elif step_type == "http":
        return await _execute_http(step)
    elif step_type == "datatable":
        return await _execute_datatable(step)
    elif step_type == "schedule":
        return None  # Schedule steps are triggers, nothing to execute
    else:
        raise ValueError(f"Unknown step type: {step_type}")


async def _get_credential_value(credential_id: str) -> str:
    db = await get_db()
    try:
        cursor = await db.execute("SELECT encrypted_value FROM credentials WHERE id = ?", (credential_id,))
        row = await cursor.fetchone()
        if not row:
            raise ValueError(f"Credential '{credential_id}' not found")
        return decrypt_value(row["encrypted_value"])
    finally:
        await db.close()


async def _execute_llm(step: dict) -> str:
    model = step.get("model", "gpt-4o-mini")
    system_prompt = step.get("system_prompt", "")
    user_prompt = step.get("user_prompt", "")

    if "gpt" in model or "o1" in model or "o3" in model:
        return await _call_openai(model, system_prompt, user_prompt, step.get("credential"))
    elif "gemini" in model:
        return await _call_gemini(model, system_prompt, user_prompt, step.get("credential"))
    else:
        # Default to OpenAI-compatible
        return await _call_openai(model, system_prompt, user_prompt, step.get("credential"))


async def _call_openai(model: str, system_prompt: str, user_prompt: str, credential_id: str = None) -> str:
    if credential_id:
        api_key = await _get_credential_value(credential_id)
    else:
        # Find default openai credential
        db = await get_db()
        try:
            cursor = await db.execute("SELECT encrypted_value FROM credentials WHERE service = 'openai' LIMIT 1")
            row = await cursor.fetchone()
            if not row:
                raise ValueError("No OpenAI credential found")
            api_key = decrypt_value(row["encrypted_value"])
        finally:
            await db.close()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_prompt})

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages, "max_tokens": 2000},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"OpenAI API error ({resp.status_code}): {resp.text}")
        return resp.json()["choices"][0]["message"]["content"].strip()


async def _call_gemini(model: str, system_prompt: str, user_prompt: str, credential_id: str = None) -> str:
    if credential_id:
        api_key = await _get_credential_value(credential_id)
    else:
        db = await get_db()
        try:
            cursor = await db.execute("SELECT encrypted_value FROM credentials WHERE service = 'gemini' LIMIT 1")
            row = await cursor.fetchone()
            if not row:
                raise ValueError("No Gemini credential found")
            api_key = decrypt_value(row["encrypted_value"])
        finally:
            await db.close()

    contents = []
    if system_prompt:
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
    else:
        full_prompt = user_prompt

    contents.append({"parts": [{"text": full_prompt}]})

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{url}?key={api_key}",
            json={"contents": contents},
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini API error ({resp.status_code}): {resp.text}")
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"].strip()


async def _execute_http(step: dict) -> str:
    method = step.get("method", "GET").upper()
    url = step.get("url", "")
    headers = step.get("headers") or {}
    body = step.get("body")

    # Inject credential as bearer token if specified
    credential_id = step.get("credential")
    if credential_id:
        token = await _get_credential_value(credential_id)
        if "access_token" not in url and "access_token" not in str(body):
            if body is None:
                body = {}
            body["access_token"] = token

    async with httpx.AsyncClient(timeout=120) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers, params=body)
        elif method == "POST":
            resp = await client.post(url, headers=headers, json=body)
        elif method == "PUT":
            resp = await client.put(url, headers=headers, json=body)
        elif method == "DELETE":
            resp = await client.delete(url, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")

        if resp.status_code >= 400:
            raise RuntimeError(f"HTTP {method} {url} returned {resp.status_code}: {resp.text[:500]}")

        try:
            return json.dumps(resp.json())
        except Exception:
            return resp.text


async def _execute_datatable(step: dict) -> str | None:
    table_name = step.get("table_name", "")
    action = step.get("table_action", "read")

    db = await get_db()
    try:
        if action == "read":
            cursor = await db.execute(
                "SELECT row_data FROM datatables WHERE table_name = ? ORDER BY created_at DESC LIMIT 100",
                (table_name,),
            )
            rows = await cursor.fetchall()
            return json.dumps([json.loads(r["row_data"]) for r in rows])

        elif action == "write":
            row_data = step.get("body", {})
            await db.execute(
                "INSERT INTO datatables (table_name, row_data) VALUES (?, ?)",
                (table_name, json.dumps(row_data)),
            )
            await db.commit()
            return json.dumps(row_data)

        elif action == "clear":
            await db.execute("DELETE FROM datatables WHERE table_name = ?", (table_name,))
            await db.commit()
            return json.dumps({"cleared": table_name})

        else:
            raise ValueError(f"Unknown datatable action: {action}")
    finally:
        await db.close()
