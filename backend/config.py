from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///data/loom.db"

    # Security
    FERNET_KEY: str = ""
    API_BEARER_TOKEN: str = ""

    # Operator login (optional — set via the in-app setup wizard on first run)
    USER_EMAIL: str = ""
    USER_PASS_HASH: str = ""

    # LLM API keys
    OPENAI_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Paths
    DATA_DIR: Path = Path("data")
    CONFIGS_DIR: Path = Path("data/configs")
    ASSETS_DIR: Path = Path("data/assets")

    # Facebook App credentials (optional — used to exchange short-lived for long-lived tokens)
    FB_APP_ID: str = ""
    FB_APP_SECRET: str = ""

    # Features
    GIT_AUTO_COMMIT: bool = False

    @property
    def db_path(self) -> Path:
        url = self.DATABASE_URL
        if ":///" in url:
            return Path(url.split(":///", 1)[1])
        return self.DATA_DIR / "loom.db"


settings = Settings()
