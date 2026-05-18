"""Loop step executor — iterates over a list variable and runs substeps."""
import json
import logging

from backend.services.step_executors.base import BaseExecutor
from backend.services.template_engine import resolve_variables

logger = logging.getLogger(__name__)


class LoopExecutor(BaseExecutor):
    def __init__(self, db=None):
        self.db = db

    async def execute(self, config: dict, variables: dict) -> str:
        source_var = config.get("source_var", "")
        item_var = config.get("item_var", "item")
        substeps = config.get("substeps", [])

        if not source_var:
            raise ValueError("Loop: source_var is required")

        # Resolve source list from variables
        raw = variables.get(source_var, "")
        if isinstance(raw, str):
            try:
                items = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                # Treat as single-item list
                items = [raw] if raw else []
        elif isinstance(raw, list):
            items = raw
        else:
            items = [raw]

        if not items:
            logger.warning(f"Loop: source_var '{source_var}' is empty")
            return json.dumps([], ensure_ascii=False)

        # Import executor map lazily to avoid circular imports
        from backend.services.step_executors import EXECUTOR_MAP, DB_EXECUTOR_TYPES

        results = []
        for idx, item in enumerate(items):
            logger.info(f"Loop iteration {idx + 1}/{len(items)}")

            # Make item available in variables
            loop_vars = dict(variables)
            loop_vars[item_var] = item if isinstance(item, str) else json.dumps(item, ensure_ascii=False)

            # Execute substeps sequentially
            for substep in substeps:
                sub_type = substep.get("type", "")
                sub_config = substep.get("config", {})
                sub_output_var = substep.get("output_var", "")

                executor_cls = EXECUTOR_MAP.get(sub_type)
                if not executor_cls:
                    raise ValueError(f"Loop: unknown substep type '{sub_type}'")

                if sub_type in DB_EXECUTOR_TYPES:
                    executor = executor_cls(self.db)
                else:
                    executor = executor_cls()

                # Render template variables in substep config
                rendered_config = {}
                for k, v in sub_config.items():
                    if isinstance(v, str):
                        rendered_config[k] = resolve_variables(v, loop_vars)
                    else:
                        rendered_config[k] = v

                output = await executor.execute(rendered_config, loop_vars)

                if sub_output_var:
                    loop_vars[sub_output_var] = output

            # Collect last substep output as iteration result
            last_output_var = substeps[-1].get("output_var", "") if substeps else ""
            if last_output_var and last_output_var in loop_vars:
                results.append(loop_vars[last_output_var])
            else:
                results.append(None)

        return json.dumps(results, ensure_ascii=False)
