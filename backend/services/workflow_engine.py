"""Core workflow execution engine.

Runs a workflow's steps sequentially, accumulating variables,
and recording execution + step output records.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import async_session
from backend.models.execution import Execution, StepOutput
from backend.models.step import Step
from backend.models.workflow import Workflow
from backend.services.step_executors import EXECUTOR_MAP, DB_EXECUTOR_TYPES
from backend.services.notification_service import notify_error

logger = logging.getLogger(__name__)

# In-memory event queues for live SSE streaming
_execution_events: dict[str, asyncio.Queue] = {}
_execution_event_created: dict[str, float] = {}  # track creation time for TTL cleanup

_QUEUE_TTL_SECONDS = 600  # 10 minutes


def get_event_queue(execution_id: str) -> asyncio.Queue:
    """Get or create an event queue for SSE streaming."""
    if execution_id not in _execution_events:
        _execution_events[execution_id] = asyncio.Queue()
        _execution_event_created[execution_id] = time.time()
    return _execution_events[execution_id]


def cleanup_event_queue(execution_id: str):
    """Remove event queue after execution completes."""
    _execution_events.pop(execution_id, None)
    _execution_event_created.pop(execution_id, None)


def cleanup_stale_queues():
    """Remove event queues older than TTL. Called periodically."""
    now = time.time()
    stale = [eid for eid, created in _execution_event_created.items()
             if now - created > _QUEUE_TTL_SECONDS]
    for eid in stale:
        _execution_events.pop(eid, None)
        _execution_event_created.pop(eid, None)
    if stale:
        logger.info(f"Cleaned up {len(stale)} stale SSE queues")


async def _emit_event(execution_id: str, event: dict):
    """Push an event to the SSE queue if listeners exist."""
    queue = _execution_events.get(execution_id)
    if queue:
        await queue.put(event)


async def run_workflow(
    workflow_id: str,
    execution_id: str,
    trigger_type: str = "manual",
    stop_after_step_id: str | None = None,
):
    """Execute a workflow's steps sequentially.

    This runs in a background task with its own DB session.
    If stop_after_step_id is provided, execution stops after that step completes.
    """
    async with async_session() as db:
        try:
            # Load workflow with steps
            result = await db.execute(
                select(Workflow).where(Workflow.id == workflow_id)
            )
            workflow = result.scalar_one_or_none()
            if not workflow:
                logger.error(f"Workflow {workflow_id} not found")
                return

            # Load steps ordered by sort_order
            steps_result = await db.execute(
                select(Step)
                .where(Step.workflow_id == workflow_id)
                .order_by(Step.sort_order)
            )
            all_steps = list(steps_result.scalars().all())

            # If stop_after_step_id given, truncate steps at that point
            if stop_after_step_id:
                stop_idx = next(
                    (i for i, s in enumerate(all_steps) if s.id == stop_after_step_id),
                    None,
                )
                steps = all_steps[: stop_idx + 1] if stop_idx is not None else all_steps
            else:
                steps = all_steps

            # Create execution record
            execution = Execution(
                id=execution_id,
                workflow_id=workflow_id,
                status="running",
                trigger_type=trigger_type,
            )
            db.add(execution)
            await db.commit()

            await _emit_event(execution_id, {
                "type": "execution_started",
                "execution_id": execution_id,
                "workflow_id": workflow_id,
                "step_count": len(steps),
            })

            # Accumulated variables from step outputs
            variables: dict = {}

            # Execute each step
            for i, step in enumerate(steps):
                step_output = StepOutput(
                    id=str(uuid4()),
                    execution_id=execution_id,
                    step_id=step.id,
                    status="running",
                    started_at=datetime.now(timezone.utc),
                )
                db.add(step_output)
                await db.commit()

                await _emit_event(execution_id, {
                    "type": "step_started",
                    "step_id": step.id,
                    "step_name": step.name,
                    "step_type": step.type,
                    "step_index": i,
                })

                start_time = time.monotonic()

                try:
                    config = step.config_dict

                    # Get the executor for this step type
                    executor_cls = EXECUTOR_MAP.get(step.type)
                    if not executor_cls:
                        raise ValueError(f"Unknown step type: {step.type}")

                    # Some executors need DB session (datatable, nova, fb)
                    if step.type in DB_EXECUTOR_TYPES:
                        executor = executor_cls(db)
                    else:
                        executor = executor_cls()

                    # Execute the step (with optional retry)
                    retry_on_error = config.pop("retry_on_error", False)
                    max_attempts = 3 if retry_on_error else 1

                    for attempt in range(1, max_attempts + 1):
                        try:
                            output = await executor.execute(config, variables)
                            break
                        except Exception as retry_exc:
                            if attempt < max_attempts:
                                logger.warning(
                                    "Step %s failed (attempt %d/%d), retrying: %s",
                                    step.id, attempt, max_attempts, retry_exc,
                                )
                                await asyncio.sleep(2 * attempt)
                            else:
                                raise

                    # Store output in variables
                    if step.output_var:
                        variables[step.output_var] = output

                    # Update step output record
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    step_output.status = "success"
                    step_output.output = output
                    step_output.duration_ms = elapsed_ms
                    step_output.finished_at = datetime.now(timezone.utc)

                    await db.commit()

                    await _emit_event(execution_id, {
                        "type": "step_completed",
                        "step_id": step.id,
                        "step_name": step.name,
                        "status": "success",
                        "output_preview": output[:500] if output else "",
                        "duration_ms": elapsed_ms,
                    })

                except Exception as e:
                    elapsed_ms = int((time.monotonic() - start_time) * 1000)
                    error_msg = str(e)
                    logger.error(f"Step {step.id} failed: {error_msg}")

                    step_output.status = "failed"
                    step_output.error_message = error_msg
                    step_output.duration_ms = elapsed_ms
                    step_output.finished_at = datetime.now(timezone.utc)

                    # Mark execution as failed
                    execution.status = "failed"
                    execution.error_message = f"Step '{step.name}' failed: {error_msg}"
                    execution.finished_at = datetime.now(timezone.utc)
                    execution.variables = json.dumps(variables, ensure_ascii=False)

                    await db.commit()
                    
                    # Notify via Telegram
                    await notify_error(workflow_id, execution_id, execution.error_message)

                    await _emit_event(execution_id, {
                        "type": "step_failed",
                        "step_id": step.id,
                        "step_name": step.name,
                        "error": error_msg,
                        "duration_ms": elapsed_ms,
                    })
                    await _emit_event(execution_id, {
                        "type": "execution_failed",
                        "execution_id": execution_id,
                        "error": execution.error_message,
                    })

                    cleanup_event_queue(execution_id)
                    return

            # All steps completed successfully
            execution.status = "success"
            execution.finished_at = datetime.now(timezone.utc)
            execution.variables = json.dumps(variables, ensure_ascii=False)

            await db.commit()

            await _emit_event(execution_id, {
                "type": "execution_completed",
                "execution_id": execution_id,
                "status": "success",
                "variables": variables,
            })

        except Exception as e:
            logger.error(f"Workflow execution failed: {e}", exc_info=True)
            try:
                ex_record = locals().get("execution")
                if ex_record is not None:
                    ex_record.status = "failed"
                    ex_record.error_message = str(e)
                    ex_record.finished_at = datetime.now(timezone.utc)
                    await db.commit()
                    await notify_error(workflow_id, execution_id, str(e))
            except Exception as inner:
                logger.error(f"Failed to mark execution {execution_id} as failed: {inner}")

            await _emit_event(execution_id, {
                "type": "execution_failed",
                "execution_id": execution_id,
                "error": str(e),
            })

        finally:
            cleanup_event_queue(execution_id)
