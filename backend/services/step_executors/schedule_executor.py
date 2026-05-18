"""Schedule step executor — no-op trigger node."""
from datetime import datetime, timezone

from backend.services.step_executors.base import BaseExecutor


class ScheduleExecutor(BaseExecutor):
    async def execute(self, config: dict, variables: dict) -> str:
        return datetime.now(timezone.utc).isoformat()
