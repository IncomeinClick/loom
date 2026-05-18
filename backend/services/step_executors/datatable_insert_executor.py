"""Datatable Insert executor — insert a new row into content store."""
import json
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.datatable import DataRow
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables


class DataTableInsertExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, config: dict, variables: dict) -> str:
        table_id = resolve_variables(config.get("table_id", ""), variables)
        columns_json = config.get("columns_json", "{}")

        # Parse columns — could be string or already dict
        if isinstance(columns_json, str):
            try:
                columns = json.loads(columns_json)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid columns JSON: {columns_json}")
        else:
            columns = columns_json

        # Resolve {{variables}} in values
        resolved = {}
        for k, v in columns.items():
            resolved[k] = resolve_variables(str(v), variables) if isinstance(v, str) else v

        row = DataRow(
            id=str(uuid4()),
            datatable_id=table_id,
            data=json.dumps(resolved, ensure_ascii=False),
        )
        self.db.add(row)
        await self.db.flush()

        return json.dumps({"row_id": row.id, **resolved}, ensure_ascii=False)
