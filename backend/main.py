import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import engine
from backend.exceptions import generic_exception_handler
from backend.models import Base


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure directories and tables exist
    settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings.CONFIGS_DIR.mkdir(parents=True, exist_ok=True)
    settings.ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    (settings.CONFIGS_DIR / "niches").mkdir(exist_ok=True)
    (settings.CONFIGS_DIR / "pages").mkdir(exist_ok=True)
    (settings.CONFIGS_DIR / "workflows").mkdir(exist_ok=True)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Mark any executions stuck in "running" as failed (from previous server crash/restart)
    import logging
    from datetime import datetime, timezone
    from sqlalchemy import update
    from backend.database import async_session
    from backend.models.execution import Execution
    async with async_session() as db:
        result = await db.execute(
            update(Execution)
            .where(Execution.status == "running")
            .values(
                status="failed",
                error_message="Execution interrupted (server restarted)",
                finished_at=datetime.now(timezone.utc),
            )
        )
        await db.commit()
        if result.rowcount:
            logging.getLogger(__name__).warning(
                f"Marked {result.rowcount} stuck execution(s) as failed on startup"
            )

    # Seed example workflow templates (idempotent — inserts only what is missing)
    try:
        from backend.services.template_seeder import seed_templates
        async with async_session() as db:
            await seed_templates(db)
    except Exception as e:
        logging.getLogger(__name__).error(f"Template seeding failed: {e}")

    # Start scheduler if available
    import logging
    logging.basicConfig(level=logging.INFO)
    try:
        from backend.services.scheduler_service import scheduler_service
        scheduler_service.start()
        logging.getLogger(__name__).info("Scheduler started successfully")
    except Exception as e:
        logging.getLogger(__name__).error(f"Scheduler failed to start: {e}")

    yield

    # Shutdown
    try:
        from backend.services.scheduler_service import scheduler_service
        scheduler_service.shutdown()
    except Exception:
        pass


app = FastAPI(
    title="Loom",
    description="Workflow automation platform",
    version="1.0.1",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
app.add_exception_handler(Exception, generic_exception_handler)

# Routers
from backend.routers import auth, health, niches, pages, workflows, steps, executions, triggers, credentials, datatables, assets, dashboard, ads  # noqa: E402

app.include_router(auth.router, prefix="/api")
app.include_router(health.router, prefix="/api")
app.include_router(niches.router, prefix="/api")
app.include_router(pages.router, prefix="/api")
app.include_router(workflows.router, prefix="/api")
app.include_router(steps.router, prefix="/api")
app.include_router(executions.router, prefix="/api")
app.include_router(triggers.router, prefix="/api")
app.include_router(credentials.router, prefix="/api")
app.include_router(datatables.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(ads.router, prefix="/api")

# Serve frontend static files
frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

# Serve generated assets
assets_dir = settings.ASSETS_DIR
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")


def run():
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
