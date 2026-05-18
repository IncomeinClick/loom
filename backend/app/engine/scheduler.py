import json
import asyncio
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.models import WorkflowConfig
from app.engine.executor import run_workflow

logger = logging.getLogger("loom.scheduler")

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


def _parse_cron(expression: str) -> dict:
    """Parse a cron expression into APScheduler CronTrigger kwargs.
    Format: minute hour day_of_month month day_of_week
    """
    parts = expression.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {expression}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


async def _run_scheduled_workflow(workflow_id: str):
    """Callback for scheduled workflow execution."""
    wf_path = settings.workflows_path / f"{workflow_id}.json"
    if not wf_path.exists():
        logger.warning(f"Scheduled workflow '{workflow_id}' not found, skipping")
        return

    wf_data = json.loads(wf_path.read_text(encoding="utf-8"))
    wf = WorkflowConfig(**wf_data)

    if not wf.active:
        logger.info(f"Workflow '{workflow_id}' is inactive, skipping")
        return

    logger.info(f"Running scheduled workflow: {workflow_id}")
    try:
        execution_id = await run_workflow(wf)
        logger.info(f"Workflow '{workflow_id}' completed: execution={execution_id}")
    except Exception as e:
        logger.error(f"Workflow '{workflow_id}' failed: {e}")


def load_all_schedules():
    """Load all workflow schedules from JSON files."""
    scheduler = get_scheduler()

    # Remove existing jobs
    scheduler.remove_all_jobs()

    for wf_file in settings.workflows_path.glob("*.json"):
        try:
            wf_data = json.loads(wf_file.read_text(encoding="utf-8"))
            wf = WorkflowConfig(**wf_data)

            if not wf.active or not wf.schedule:
                continue

            cron_kwargs = _parse_cron(wf.schedule)
            scheduler.add_job(
                _run_scheduled_workflow,
                CronTrigger(**cron_kwargs),
                args=[wf.id],
                id=wf.id,
                name=wf.name,
                replace_existing=True,
            )
            logger.info(f"Scheduled workflow '{wf.id}': {wf.schedule}")

        except Exception as e:
            logger.warning(f"Failed to schedule workflow from {wf_file.name}: {e}")


def reload_workflow_schedule(workflow_id: str):
    """Reload schedule for a single workflow."""
    scheduler = get_scheduler()

    # Remove existing job if any
    try:
        scheduler.remove_job(workflow_id)
    except Exception:
        pass

    wf_path = settings.workflows_path / f"{workflow_id}.json"
    if not wf_path.exists():
        return

    wf_data = json.loads(wf_path.read_text(encoding="utf-8"))
    wf = WorkflowConfig(**wf_data)

    if not wf.active or not wf.schedule:
        return

    cron_kwargs = _parse_cron(wf.schedule)
    scheduler.add_job(
        _run_scheduled_workflow,
        CronTrigger(**cron_kwargs),
        args=[wf.id],
        id=wf.id,
        name=wf.name,
        replace_existing=True,
    )


def get_scheduled_jobs() -> list[dict]:
    """Return list of scheduled jobs with next run times."""
    scheduler = get_scheduler()
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })
    return jobs


def start_scheduler():
    scheduler = get_scheduler()
    load_all_schedules()
    if not scheduler.running:
        scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
