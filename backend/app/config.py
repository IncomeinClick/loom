import os
from pathlib import Path
from pydantic_settings import BaseSettings
from cryptography.fernet import Fernet


class Settings(BaseSettings):
    # Auth
    loom_api_key: str = "loom-dev-key-change-in-production"

    # Encryption
    loom_encryption_key: str = ""

    # Paths (relative to backend/)
    data_dir: str = "../data"
    workflows_dir: str = "../data/workflows"
    pages_dir: str = "../data/pages"
    assets_dir: str = "../data/assets"

    # Database
    database_url: str = "sqlite+aiosqlite:///../data/loom.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 8100

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

    @property
    def base_path(self) -> Path:
        return Path(__file__).parent.parent

    @property
    def data_path(self) -> Path:
        return (self.base_path / self.data_dir).resolve()

    @property
    def workflows_path(self) -> Path:
        return (self.base_path / self.workflows_dir).resolve()

    @property
    def pages_path(self) -> Path:
        return (self.base_path / self.pages_dir).resolve()

    @property
    def assets_path(self) -> Path:
        return (self.base_path / self.assets_dir).resolve()

    @property
    def db_path(self) -> Path:
        return self.data_path / "loom.db"

    def get_encryption_key(self) -> bytes:
        if self.loom_encryption_key:
            return self.loom_encryption_key.encode()
        # Auto-generate and persist if not set
        key = Fernet.generate_key()
        env_path = self.base_path / ".env"
        content = env_path.read_text() if env_path.exists() else ""
        content = content.replace(
            "LOOM_ENCRYPTION_KEY=",
            f"LOOM_ENCRYPTION_KEY={key.decode()}"
        )
        env_path.write_text(content)
        self.loom_encryption_key = key.decode()
        return key


settings = Settings()
