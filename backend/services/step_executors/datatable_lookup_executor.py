"""Datatable Lookup executor — read rows from content store with filtering."""
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.datatable import DataRow
from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables


class DataTableLookupExecutor(BaseExecutor):
    def __init__(self, db: AsyncSession):
        self.db = db

    async def execute(self, config: dict, variables: dict) -> str:
        table_id = resolve_variables(config.get("table_id", ""), variables)
        filter_column = config.get("filter_column", "")
        filter_condition = config.get("filter_condition", "")
        filter_value = resolve_variables(config.get("filter_value", ""), variables)
        limit = int(config.get("limit", 1))

        stmt = select(DataRow).where(DataRow.datatable_id == table_id)

        result = await self.db.execute(stmt.order_by(DataRow.created_at).limit(limit * 10))
        rows = list(result.scalars().all())

        # Apply column-level filter in Python (data is JSON blob)
        filtered = []
        for row in rows:
            try:
                data = json.loads(row.data) if isinstance(row.data, str) else row.data
            except (json.JSONDecodeError, TypeError):
                continue

            if not filter_column or not filter_condition:
                filtered.append({"id": row.id, **data})
                continue

            col_val = data.get(filter_column, "")

            if filter_condition == "isEmpty" and (col_val is None or col_val == ""):
                filtered.append({"id": row.id, **data})
            elif filter_condition == "isNotEmpty" and col_val not in (None, ""):
                filtered.append({"id": row.id, **data})
            elif filter_condition == "equals" and str(col_val) == filter_value:
                filtered.append({"id": row.id, **data})

            if len(filtered) >= limit:
                break

        if not filtered:
            raise ValueError("Datatable Lookup: no matching rows found with the given filter.")

        if limit == 1:
            return json.dumps(filtered[0], ensure_ascii=False)
        return json.dumps(filtered, ensure_ascii=False)
