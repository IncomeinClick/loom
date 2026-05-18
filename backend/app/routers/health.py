from fastapi import APIRouter, Depends
from app.config import settings
from app.auth import verify_api_key
from app.engine.scheduler import get_scheduled_jobs, load_all_schedules

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "service": "loom",
        "data_dir": str(settings.data_path),
        "db": str(settings.db_path),
    }


@router.get("/api/schedules", dependencies=[Depends(verify_api_key)])
async def list_schedules():
    return get_scheduled_jobs()


@router.post("/api/schedules/reload", dependencies=[Depends(verify_api_key)])
async def reload_schedules():
    load_all_schedules()
    return {"status": "reloaded", "jobs": get_scheduled_jobs()}
