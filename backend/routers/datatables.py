import json
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, verify_token
from backend.exceptions import NotFoundError
from backend.models.datatable import DataTable, DataRow
from backend.schemas.datatable import DataTableCreate, DataTableUpdate, DataTableResponse, DataRowCreate, DataRowResponse
from backend.services.notification_service import notify_activity

router = APIRouter(prefix="/datatables", tags=["datatables"], dependencies=[Depends(verify_token)])


@router.get("", response_model=list[DataTableResponse])
async def list_datatables(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DataTable))
    tables = result.scalars().all()
    return [
        DataTableResponse(
            id=t.id,
            workflow_id=t.workflow_id,
            name=t.name,
            columns=t.columns,
            row_count=len(t.rows),
            created_at=t.created_at,
        )
        for t in tables
    ]


@router.post("", response_model=DataTableResponse, status_code=201)
async def create_datatable(body: DataTableCreate, db: AsyncSession = Depends(get_db)):
    table = DataTable(
        id=body.id, name=body.name, workflow_id=body.workflow_id,
        columns=json.dumps(body.columns, ensure_ascii=False),
    )
    db.add(table)
    await db.flush()
    await notify_activity("created", "data table", table.id, f"Name: {table.name}")
    return DataTableResponse(
        id=table.id,
        workflow_id=table.workflow_id,
        name=table.name,
        columns=table.columns,
        row_count=0,
        created_at=table.created_at,
    )


@router.put("/{table_id}", response_model=DataTableResponse)
async def update_datatable(table_id: str, body: DataTableUpdate, db: AsyncSession = Depends(get_db)):
    table = await db.get(DataTable, table_id)
    if not table:
        raise NotFoundError("DataTable", table_id)
    if body.name is not None:
        table.name = body.name
    if body.columns is not None:
        table.columns = json.dumps(body.columns, ensure_ascii=False)
    await db.flush()
    await notify_activity("updated", "data table", table_id)
    return DataTableResponse(
        id=table.id,
        workflow_id=table.workflow_id,
        name=table.name,
        columns=table.columns,
        row_count=len(table.rows),
        created_at=table.created_at,
    )


@router.post("/{table_id}/rename")
async def rename_datatable(table_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """Rename a datatable's ID and/or name, updating all references."""
    from fastapi import HTTPException
    table = await db.get(DataTable, table_id)
    if not table:
        raise NotFoundError("DataTable", table_id)

    new_id = body.get("new_id", "").strip()
    new_name = body.get("new_name", "").strip()

    if new_name:
        table.name = new_name

    if new_id and new_id != table_id:
        # Check for conflicts
        existing = await db.get(DataTable, new_id)
        if existing:
            raise HTTPException(status_code=409, detail=f"DataTable ID '{new_id}' already exists")

        # Update step configs that reference the old datatable ID
        from backend.models.step import Step
        steps_result = await db.execute(select(Step))
        for step in steps_result.scalars().all():
            if table_id in (step.config or ""):
                cfg = json.loads(step.config)
                changed = False
                if cfg.get("table_id") == table_id:
                    cfg["table_id"] = new_id
                    changed = True
                if cfg.get("lookup_table_id") == table_id:
                    cfg["lookup_table_id"] = new_id
                    changed = True
                if changed:
                    step.config = json.dumps(cfg, ensure_ascii=False)

        # Update DataRow FK and datatable PK via raw SQL
        from sqlalchemy import text
        await db.execute(text("UPDATE datarows SET datatable_id = :new WHERE datatable_id = :old"), {"new": new_id, "old": table_id})
        await db.execute(text("UPDATE datatables SET id = :new WHERE id = :old"), {"new": new_id, "old": table_id})
        await db.flush()

        # Re-fetch with new ID
        table = await db.get(DataTable, new_id)

    await db.flush()
    await notify_activity("renamed", "data table", table.id, f"From: {table_id}")
    return DataTableResponse(
        id=table.id,
        workflow_id=table.workflow_id,
        name=table.name,
        columns=table.columns,
        row_count=len(table.rows),
        created_at=table.created_at,
    )


@router.delete("/{table_id}", status_code=204)
async def delete_datatable(table_id: str, db: AsyncSession = Depends(get_db)):
    table = await db.get(DataTable, table_id)
    if not table:
        raise NotFoundError("DataTable", table_id)
    table_name = table.name
    await db.delete(table)
    await db.flush()
    await notify_activity("deleted", "data table", table_id, f"Name: {table_name}")


@router.get("/{table_id}")
async def get_datatable(
    table_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    table = await db.get(DataTable, table_id)
    if not table:
        raise NotFoundError("DataTable", table_id)

    result = await db.execute(
        select(DataRow)
        .where(DataRow.datatable_id == table_id)
        .order_by(DataRow.created_at)
        .offset(offset)
        .limit(limit)
    )
    rows = result.scalars().all()

    return {
        "id": table.id,
        "workflow_id": table.workflow_id,
        "name": table.name,
        "columns": json.loads(table.columns) if table.columns else [],
        "row_count": len(table.rows),
        "created_at": table.created_at,
        "rows": [DataRowResponse.model_validate(r) for r in rows],
    }


@router.post("/{table_id}/rows", response_model=DataRowResponse, status_code=201)
async def add_row(table_id: str, body: DataRowCreate, db: AsyncSession = Depends(get_db)):
    table = await db.get(DataTable, table_id)
    if not table:
        raise NotFoundError("DataTable", table_id)

    row = DataRow(
        id=str(uuid4()),
        datatable_id=table_id,
        data=json.dumps(body.data, ensure_ascii=False),
    )
    db.add(row)
    await db.flush()
    return DataRowResponse.model_validate(row)


@router.delete("/{table_id}/rows", status_code=204)
async def clear_rows(table_id: str, db: AsyncSession = Depends(get_db)):
    table = await db.get(DataTable, table_id)
    if not table:
        raise NotFoundError("DataTable", table_id)

    await db.execute(delete(DataRow).where(DataRow.datatable_id == table_id))
    await db.flush()


@router.post("/{table_id}/rows/bulk-delete", status_code=204)
async def bulk_delete_rows(
    table_id: str,
    row_ids: list[str] = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
):
    table = await db.get(DataTable, table_id)
    if not table:
        raise NotFoundError("DataTable", table_id)
    await db.execute(
        delete(DataRow).where(DataRow.datatable_id == table_id, DataRow.id.in_(row_ids))
    )
    await db.flush()


@router.put("/{table_id}/rows/{row_id}", response_model=DataRowResponse)
async def update_row(
    table_id: str, row_id: str, body: DataRowCreate, db: AsyncSession = Depends(get_db)
):
    row = await db.get(DataRow, row_id)
    if not row or row.datatable_id != table_id:
        raise NotFoundError("DataRow", row_id)
    row.data = json.dumps(body.data, ensure_ascii=False)
    await db.flush()
    return DataRowResponse.model_validate(row)


@router.delete("/{table_id}/rows/{row_id}", status_code=204)
async def delete_row(table_id: str, row_id: str, db: AsyncSession = Depends(get_db)):
    row = await db.get(DataRow, row_id)
    if not row or row.datatable_id != table_id:
        raise NotFoundError("DataRow", row_id)
    await db.delete(row)
    await db.flush()
