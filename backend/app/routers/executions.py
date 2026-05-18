from fastapi import APIRouter, Depends, HTTPException
from app.auth import verify_api_key
from app.database import get_db

router = APIRouter(prefix="/api/executions", tags=["executions"], dependencies=[Depends(verify_api_key)])


@router.get("")
async def list_executions(workflow_id: str = None, limit: int = 50):
    db = await get_db()
    try:
        if workflow_id:
            cursor = await db.execute(
                "SELECT * FROM executions WHERE workflow_id = ? ORDER BY started_at DESC LIMIT ?",
                (workflow_id, limit),
            )
        else:
            cursor = await db.execute(
                "SELECT * FROM executions ORDER BY started_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        await db.close()


@router.get("/{execution_id}")
async def get_execution(execution_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("SELECT * FROM executions WHERE id = ?", (execution_id,))
        row = await cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
        execution = dict(row)

        cursor = await db.execute(
            "SELECT * FROM execution_steps WHERE execution_id = ? ORDER BY started_at",
            (execution_id,),
        )
        steps = await cursor.fetchall()
        execution["steps"] = [dict(s) for s in steps]
        return execution
    finally:
        await db.close()


@router.delete("/{execution_id}")
async def delete_execution(execution_id: str):
    db = await get_db()
    try:
        cursor = await db.execute("DELETE FROM executions WHERE id = ?", (execution_id,))
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Execution '{execution_id}' not found")
        await db.commit()
        return {"deleted": execution_id}
    finally:
        await db.close()
