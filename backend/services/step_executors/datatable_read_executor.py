"""Datatable Read executor — read rows from a datatable with optional column filter."""
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.datatable import DataRow
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables


class DataTableReadExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, config: dict, variables: dict) -> str:
        table_id = resolve_variables(config.get("table_id", ""), variables)
        filter_column = config.get("filter_column", "")
        filter_mode = config.get("filter_mode", "")  # empty, not_empty, equals, not_equals
        filter_value = resolve_variables(config.get("filter_value", ""), variables)
        limit = int(config.get("limit", 1))

        # Fetch rows from table
        result = await self.db.execute(
            select(DataRow)
            .where(DataRow.datatable_id == table_id)
            .order_by(DataRow.created_at)
        )
        rows = result.scalars().all()

        # Parse and filter
        matched = []
        for row in rows:
            try:
                data = json.loads(row.data) if isinstance(row.data, str) else (row.data or {})
            except (json.JSONDecodeError, TypeError):
                continue

            if filter_column and filter_mode:
                col_val = str(data.get(filter_column, "")).strip()

                if filter_mode == "empty" and col_val != "":
                    continue
                elif filter_mode == "not_empty" and col_val == "":
                    continue
                elif filter_mode == "equals" and col_val != filter_value:
                    continue
                elif filter_mode == "not_equals" and col_val == filter_value:
                    continue

            matched.append({"row_id": row.id, **data})

            if len(matched) >= limit:
                break

        if not matched:
            raise ValueError("Datatable Read: no matching rows found with the given filter.")

        # Single row → return object; multiple → return array
        if limit == 1:
            return json.dumps(matched[0], ensure_ascii=False)
        return json.dumps(matched, ensure_ascii=False)
