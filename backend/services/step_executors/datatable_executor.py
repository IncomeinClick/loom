"""DataTable step executor — read/write from content store."""
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.datatable import DataRow, DataTable
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables


class DataTableExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, config: dict, variables: dict) -> str:
        operation = config.get("operation", "read_next")
        table_id = resolve_variables(config.get("table_id", ""), variables)

        if operation == "read_next":
            return await self._read_next(table_id)
        elif operation == "write":
            data = config.get("data", {})
            if isinstance(data, dict):
                from backend.services.template_engine import resolve_dict
                data = resolve_dict(data, variables)
            return await self._write(table_id, data)
        elif operation == "mark_used":
            row_id = resolve_variables(config.get("row_id", ""), variables)
            return await self._mark_used(row_id)
        else:
            raise ValueError(f"Unknown datatable operation: {operation}")

    async def _read_next(self, table_id: str) -> str:
        result = await self.db.execute(
            select(DataRow)
            .where(DataRow.datatable_id == table_id, DataRow.used == False)
            .order_by(DataRow.created_at)
            .limit(1)
        )
        row = result.scalar_one_or_none()
        if row is None:
            raise ValueError("Datatable: no unused rows available in this table.")
        return row.data

    async def _write(self, table_id: str, data: dict) -> str:
        row = DataRow(
            id=str(uuid4()),
            datatable_id=table_id,
            data=json.dumps(data, ensure_ascii=False),
        )
        self.db.add(row)
        await self.db.flush()
        return json.dumps({"row_id": row.id, "data": data})

    async def _mark_used(self, row_id: str) -> str:
        row = await self.db.get(DataRow, row_id)
        if row is None:
            raise ValueError(f"Datatable: row '{row_id}' not found. It may have been deleted or the row_id variable is incorrect.")
        row.used = True
        await self.db.flush()
        return json.dumps({"row_id": row_id, "marked_used": True})
