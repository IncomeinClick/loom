"""Datatable Update executor — update an existing row in content store."""
import json

from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.datatable import DataRow
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables


class DataTableUpdateExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, config: dict, variables: dict) -> str:
        table_id = resolve_variables(config.get("table_id", ""), variables)
        row_id = resolve_variables(config.get("row_id", ""), variables)
        columns_json = config.get("columns_json", "{}")

        # Parse row_id from JSON if it was a lookup/read/insert result
        # Supports both "id" (lookup executor) and "row_id" (read/insert executor) keys
        if row_id.startswith("{"):
            try:
                parsed = json.loads(row_id)
                row_id = parsed.get("row_id", parsed.get("id", row_id))
            except (json.JSONDecodeError, TypeError):
                pass

        # Parse columns
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

        row = await self.db.get(DataRow, row_id)
        if row is None:
            raise ValueError(f"Datatable Update: row '{row_id}' not found. It may have been deleted or the row_id variable is incorrect.")

        # Merge new data into existing
        try:
            existing = json.loads(row.data) if isinstance(row.data, str) else (row.data or {})
        except (json.JSONDecodeError, TypeError):
            existing = {}

        existing.update(resolved)
        row.data = json.dumps(existing, ensure_ascii=False)
        await self.db.flush()

        return json.dumps({"row_id": row_id, **existing}, ensure_ascii=False)
