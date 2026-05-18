import asyncio
import json

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, verify_token
from backend.exceptions import NotFoundError
from backend.models.execution import Execution
from backend.schemas.execution import ExecutionResponse, ExecutionDetailResponse
from backend.services.workflow_engine import get_event_queue, cleanup_event_queue

router = APIRouter(prefix="/executions", tags=["executions"])


@router.get("", response_model=list[ExecutionResponse], dependencies=[Depends(verify_token)])
async def list_executions(
    workflow_id: str | None = Query(None),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Execution).order_by(Execution.started_at.desc()).limit(limit)
    if workflow_id:
        stmt = stmt.where(Execution.workflow_id == workflow_id)
    if status:
        stmt = stmt.where(Execution.status == status)

    result = await db.execute(stmt)
    executions = result.scalars().all()

    responses = []
    for ex in executions:
        duration_ms = None
        if ex.started_at and ex.finished_at:
            delta = ex.finished_at - ex.started_at
            duration_ms = int(delta.total_seconds() * 1000)

        page_name = None
        if ex.workflow and ex.workflow.page:
            page_name = ex.workflow.page.name

        responses.append(
            ExecutionResponse(
                id=ex.id,
                workflow_id=ex.workflow_id,
                page_name=page_name,
                status=ex.status,
                trigger_type=ex.trigger_type,
                started_at=ex.started_at,
                finished_at=ex.finished_at,
                error_message=ex.error_message,
                duration_ms=duration_ms,
            )
        )
    return responses


@router.get("/{execution_id}", response_model=ExecutionDetailResponse, dependencies=[Depends(verify_token)])
async def get_execution(execution_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy.orm import selectinload
    ex = await db.get(Execution, execution_id, options=[selectinload(Execution.step_outputs)])
    if not ex:
        raise NotFoundError("Execution", execution_id)

    duration_ms = None
    if ex.started_at and ex.finished_at:
        delta = ex.finished_at - ex.started_at
        duration_ms = int(delta.total_seconds() * 1000)

    return ExecutionDetailResponse(
        id=ex.id,
        workflow_id=ex.workflow_id,
        status=ex.status,
        trigger_type=ex.trigger_type,
        started_at=ex.started_at,
        finished_at=ex.finished_at,
        error_message=ex.error_message,
        duration_ms=duration_ms,
        variables=ex.variables,
        step_outputs=ex.step_outputs,
    )


@router.get("/{execution_id}/stream")
async def stream_execution(
    execution_id: str,
    request: Request,
    token: str = Query(..., description="Bearer token for SSE auth"),
):
    """SSE endpoint for live execution streaming.

    Connect before triggering the workflow to receive all events.
    The stream ends when the execution completes or fails.
    Pass token as query parameter since EventSource doesn't support headers.
    """
    from backend.config import settings

    if token != settings.API_BEARER_TOKEN:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Invalid token")

    queue = get_event_queue(execution_id)

    async def event_generator():
        try:
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    data = json.dumps(event, default=str)
                    yield f"event: {event.get('type', 'message')}\ndata: {data}\n\n"

                    # End stream on terminal events
                    if event.get("type") in ("execution_completed", "execution_failed"):
                        break
                except asyncio.TimeoutError:
                    # Send keepalive
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            # Clean up queue when client disconnects
            cleanup_event_queue(execution_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
