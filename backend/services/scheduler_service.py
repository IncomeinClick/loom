"""APScheduler service for cron-based workflow scheduling."""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from uuid import uuid4

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import delete, select

from backend.database import async_session

logger = logging.getLogger(__name__)

TIMEZONE = ZoneInfo("Asia/Bangkok")


class SchedulerService:
    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone=TIMEZONE)
        self._started = False

    def start(self):
        if self._started:
            return
        self.scheduler.start()
        self._started = True
        logger.info("Scheduler started")
        # Load active workflows in background
        asyncio.ensure_future(self._load_active_workflows())
        # Periodic SSE queue cleanup every 5 minutes
        self.scheduler.add_job(
            self._cleanup_sse_queues,
            "interval",
            minutes=5,
            id="sse-queue-cleanup",
            replace_existing=True,
        )
        # Daily cleanup of old executions at 3:17 AM Bangkok time
        self.scheduler.add_job(
            self._cleanup_old_executions,
            CronTrigger(hour=3, minute=17, timezone=TIMEZONE),
            id="execution-cleanup",
            replace_existing=True,
        )
        # Run cleanup once on startup
        asyncio.ensure_future(self._cleanup_old_executions())

    @staticmethod
    async def _cleanup_sse_queues():
        """Periodic cleanup of stale SSE event queues."""
        from backend.services.workflow_engine import cleanup_stale_queues
        cleanup_stale_queues()

    @staticmethod
    async def _cleanup_old_executions(retention_days: int = 30):
        """Delete executions (and their step_outputs via CASCADE) older than retention_days."""
        from backend.models.execution import Execution

        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        try:
            async with async_session() as db:
                result = await db.execute(
                    delete(Execution).where(Execution.started_at < cutoff)
                )
                deleted = result.rowcount
                await db.commit()
                if deleted:
                    logger.info(f"Cleaned up {deleted} executions older than {retention_days} days")
        except Exception as e:
            logger.error(f"Execution cleanup failed: {e}")

    def shutdown(self):
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Scheduler shut down")

    async def _load_active_workflows(self):
        """Load all active workflows with schedules and register them."""
        try:
            from backend.models.workflow import Workflow

            async with async_session() as db:
                result = await db.execute(
                    select(Workflow).where(
                        Workflow.active == True,
                        Workflow.schedule != None,
                        Workflow.schedule != "",
                    )
                )
                workflows = result.scalars().all()

                for wf in workflows:
                    self.add_job(wf.id, wf.schedule)

                logger.info(f"Loaded {len(workflows)} scheduled workflows")
        except Exception as e:
            logger.error(f"Failed to load scheduled workflows: {e}")

    def add_job(self, workflow_id: str, cron_expr: str):
        """Register or update cron jobs for a workflow.

        Supports multiple comma-separated cron expressions (e.g. "0 9 * * *,0 15 * * *").
        Each expression gets its own APScheduler job.
        """
        # Remove all existing jobs for this workflow first
        self.remove_job(workflow_id)

        cron_list = [c.strip() for c in cron_expr.split(",") if c.strip()]
        for idx, single_cron in enumerate(cron_list):
            job_id = f"workflow_{workflow_id}_{idx}"
            try:
                parts = single_cron.split()
                if len(parts) != 5:
                    logger.warning(f"Invalid cron expression for {workflow_id}: {single_cron}")
                    continue

                trigger = CronTrigger(
                    minute=parts[0],
                    hour=parts[1],
                    day=parts[2],
                    month=parts[3],
                    day_of_week=parts[4],
                    timezone=TIMEZONE,
                )
                self.scheduler.add_job(
                    self._run_workflow,
                    trigger=trigger,
                    id=job_id,
                    args=[workflow_id],
                    replace_existing=True,
                )
                logger.info(f"Scheduled workflow {workflow_id} job {idx}: {single_cron}")
            except Exception as e:
                logger.error(f"Failed to schedule {workflow_id} job {idx}: {e}")

    def remove_job(self, workflow_id: str):
        """Remove all cron jobs for a workflow."""
        prefix = f"workflow_{workflow_id}_"
        removed = 0
        for job in self.scheduler.get_jobs():
            if job.id.startswith(prefix):
                self.scheduler.remove_job(job.id)
                removed += 1
        # Also remove legacy single-job format
        legacy_id = f"workflow_{workflow_id}"
        if self.scheduler.get_job(legacy_id):
            self.scheduler.remove_job(legacy_id)
            removed += 1
        if removed:
            logger.info(f"Removed {removed} schedule(s) for {workflow_id}")

    def get_next_run(self, workflow_id: str) -> str | None:
        """Get the earliest next scheduled run time across all jobs for a workflow."""
        prefix = f"workflow_{workflow_id}_"
        next_times = []
        for job in self.scheduler.get_jobs():
            if job.id.startswith(prefix) and job.next_run_time:
                next_times.append(job.next_run_time)
        # Also check legacy format
        legacy = self.scheduler.get_job(f"workflow_{workflow_id}")
        if legacy and legacy.next_run_time:
            next_times.append(legacy.next_run_time)
        if next_times:
            return min(next_times).isoformat()
        return None

    @property
    def is_running(self) -> bool:
        return self._started

    async def _run_workflow(self, workflow_id: str):
        """Called by APScheduler to run a workflow."""
        from backend.services.workflow_engine import run_workflow

        execution_id = str(uuid4())
        logger.info(f"Scheduled trigger for workflow {workflow_id}, execution {execution_id}")
        await run_workflow(workflow_id, execution_id, trigger_type="scheduled")


scheduler_service = SchedulerService()
