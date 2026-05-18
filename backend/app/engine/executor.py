import json
import re
import uuid
from datetime import datetime, timezone

from app.database import get_db
from app.config import settings
from app.models import WorkflowConfig
from app.engine.steps import execute_step


def _resolve_template(text: str, variables: dict) -> str:
    """Replace {{var_name}} with actual values from the variables dict."""
    if not text:
        return text

    def replacer(match):
        var_name = match.group(1).strip()
        return str(variables.get(var_name, match.group(0)))

    return re.sub(r"\{\{(\w+)\}\}", replacer, text)


def _resolve_step_templates(step_dict: dict, variables: dict) -> dict:
    """Recursively resolve template variables in a step's config."""
    resolved = {}
    for key, value in step_dict.items():
        if isinstance(value, str):
            resolved[key] = _resolve_template(value, variables)
        elif isinstance(value, dict):
            resolved[key] = {
                k: _resolve_template(v, variables) if isinstance(v, str) else v
                for k, v in value.items()
            }
        else:
            resolved[key] = value
    return resolved


async def run_workflow(workflow: WorkflowConfig) -> str:
    """Execute a workflow sequentially. Returns execution ID."""
    execution_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    variables = {}

    db = await get_db()
    try:
        # Create execution record
        await db.execute(
            "INSERT INTO executions (id, workflow_id, status, started_at) VALUES (?, ?, ?, ?)",
            (execution_id, workflow.id, "running", now),
        )
        await db.commit()

        for step in workflow.steps:
            step_exec_id = f"{execution_id}-{step.id}"
            step_started = datetime.now(timezone.utc).isoformat()

            await db.execute(
                "INSERT INTO execution_steps (id, execution_id, step_id, step_name, status, started_at) VALUES (?, ?, ?, ?, ?, ?)",
                (step_exec_id, execution_id, step.id, step.name, "running", step_started),
            )
            await db.commit()

            try:
                # Resolve templates in step config
                step_dict = _resolve_step_templates(step.model_dump(), variables)

                # Execute the step
                output = await execute_step(step_dict, variables)

                # Store output variable
                if step.output_var and output is not None:
                    variables[step.output_var] = output

                step_completed = datetime.now(timezone.utc).isoformat()
                output_str = json.dumps(output) if not isinstance(output, str) else output

                await db.execute(
                    "UPDATE execution_steps SET status = ?, output = ?, completed_at = ? WHERE id = ?",
                    ("success", output_str, step_completed, step_exec_id),
                )
                await db.commit()

            except Exception as e:
                step_completed = datetime.now(timezone.utc).isoformat()
                await db.execute(
                    "UPDATE execution_steps SET status = ?, error = ?, completed_at = ? WHERE id = ?",
                    ("failed", str(e), step_completed, step_exec_id),
                )
                await db.execute(
                    "UPDATE executions SET status = ?, error = ?, completed_at = ? WHERE id = ?",
                    ("failed", f"Step '{step.name}' failed: {e}", step_completed, execution_id),
                )
                await db.commit()
                return execution_id

        # All steps completed
        completed = datetime.now(timezone.utc).isoformat()
        await db.execute(
            "UPDATE executions SET status = ?, completed_at = ? WHERE id = ?",
            ("success", completed, execution_id),
        )
        await db.commit()

    finally:
        await db.close()

    return execution_id
