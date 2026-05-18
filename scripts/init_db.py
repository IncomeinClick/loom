"""Initialize the database - create all tables."""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.database import engine
from backend.models import Base


async def init():
    # Ensure data directory exists
    Path("data").mkdir(exist_ok=True)
    Path("data/configs/niches").mkdir(parents=True, exist_ok=True)
    Path("data/configs/pages").mkdir(parents=True, exist_ok=True)
    Path("data/configs/workflows").mkdir(parents=True, exist_ok=True)
    Path("data/assets").mkdir(parents=True, exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("Database initialized successfully")


if __name__ == "__main__":
    asyncio.run(init())
