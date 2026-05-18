"""Setup-wizard + login router for fresh installs.

On a fresh install API_BEARER_TOKEN and FERNET_KEY are blank, so the frontend
shows a one-time wizard that asks for an email + password. The wizard
generates a strong Fernet key + bearer token, hashes the password, and writes
.env. Subsequent visits show a login form that exchanges email + password for
the bearer token.

Legacy installs that already have a token but no login pair are also forced
through the setup wizard so that every install ends up on email + password.
"""
import hashlib
import secrets as sec
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.config import settings

router = APIRouter()

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def _load_env() -> dict:
    env: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    return env


def _save_env(env: dict) -> None:
    preferred_order = [
        "FERNET_KEY",
        "API_BEARER_TOKEN",
        "USER_EMAIL",
        "USER_PASS_HASH",
        "DATABASE_URL",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "ANTHROPIC_API_KEY",
        "FB_APP_ID",
        "FB_APP_SECRET",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_NOTIFY_CHAT_ID",
        "NOVA_VOICE_URL",
        "NOVA_VIDEO_URL",
        "GIT_AUTO_COMMIT",
    ]
    lines = ["# Loom configuration — managed by the setup wizard. Edit by hand if you know what you're doing."]
    written: set[str] = set()
    for k in preferred_order:
        if k in env:
            lines.append(f"{k}={env[k]}")
            written.add(k)
    for k, v in env.items():
        if k not in written:
            lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines) + "\n")


@router.get("/setup-status")
def setup_status():
    env = _load_env()
    has_login = bool(env.get("USER_EMAIL") and env.get("USER_PASS_HASH"))
    has_server_keys = bool(env.get("API_BEARER_TOKEN") and env.get("FERNET_KEY"))
    needs_setup = not has_login or not has_server_keys
    return {"needs_setup": needs_setup, "has_login": has_login}


class SetupRequest(BaseModel):
    email: str
    password: str


@router.post("/setup")
def setup(req: SetupRequest):
    env = _load_env()
    if env.get("API_BEARER_TOKEN") and env.get("USER_PASS_HASH"):
        raise HTTPException(400, "Already configured. Edit .env to change credentials.")

    if not req.email or not req.password:
        raise HTTPException(400, "Email and password are required.")
    if len(req.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters.")

    if not env.get("FERNET_KEY"):
        from cryptography.fernet import Fernet
        env["FERNET_KEY"] = Fernet.generate_key().decode()

    if not env.get("API_BEARER_TOKEN"):
        env["API_BEARER_TOKEN"] = sec.token_urlsafe(32)

    env["USER_EMAIL"] = req.email
    env["USER_PASS_HASH"] = hashlib.sha256(req.password.encode()).hexdigest()

    _save_env(env)

    settings.API_BEARER_TOKEN = env["API_BEARER_TOKEN"]
    settings.FERNET_KEY = env["FERNET_KEY"]
    settings.USER_EMAIL = env["USER_EMAIL"]
    settings.USER_PASS_HASH = env["USER_PASS_HASH"]

    return {"ok": True, "token": env["API_BEARER_TOKEN"]}


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login")
def login(req: LoginRequest):
    env = _load_env()
    user_email = env.get("USER_EMAIL", "")
    user_pass_hash = env.get("USER_PASS_HASH", "")
    api_token = env.get("API_BEARER_TOKEN", "")

    if not user_email or not user_pass_hash:
        raise HTTPException(400, "Login is not configured. Run the setup wizard first.")
    if not api_token:
        raise HTTPException(500, "API token is missing from server config.")

    pass_hash = hashlib.sha256(req.password.encode()).hexdigest()
    if req.email != user_email or pass_hash != user_pass_hash:
        raise HTTPException(401, "Invalid email or password.")

    return {"token": api_token}
