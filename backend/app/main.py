from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from app.config import settings
from app.database import init_db
from app.routers import health, pages, workflows, credentials, executions, assets
from app.engine.scheduler import start_scheduler, stop_scheduler
from app.services.git_tracker import init_repo


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure directories exist
    settings.data_path.mkdir(parents=True, exist_ok=True)
    settings.workflows_path.mkdir(parents=True, exist_ok=True)
    settings.pages_path.mkdir(parents=True, exist_ok=True)
    settings.assets_path.mkdir(parents=True, exist_ok=True)
    # Init database
    await init_db()
    # Init git repo
    init_repo()
    # Start scheduler
    start_scheduler()
    yield
    # Shutdown
    stop_scheduler()


app = FastAPI(
    title="Loom",
    description="Workflow Automation Platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routers
app.include_router(health.router)
app.include_router(pages.router)
app.include_router(workflows.router)
app.include_router(credentials.router)
app.include_router(executions.router)
app.include_router(assets.router)

# Serve frontend static files
frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
