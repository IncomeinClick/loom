"""Code step executor — runs Python code with access to workflow variables."""
import json
import logging
import random
import time

from backend.services.step_executors.base import BaseExecutor

logger = logging.getLogger(__name__)

# Safe builtins for code execution
SAFE_BUILTINS = {
    "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
    "enumerate": enumerate, "filter": filter, "float": float, "format": format,
    "int": int, "isinstance": isinstance, "len": len, "list": list,
    "map": map, "max": max, "min": min, "print": print, "range": range,
    "reversed": reversed, "round": round, "set": set, "sorted": sorted,
    "str": str, "sum": sum, "tuple": tuple, "type": type, "zip": zip,
    "True": True, "False": False, "None": None,
    "json": json,
    "random": random,
    "time": time,
}


class CodeExecutor(BaseExecutor):
    async def execute(self, config: dict, variables: dict) -> str:
        code = config.get("code", "")
        if not code.strip():
            raise ValueError("No code provided")

        # Build execution namespace with variables and safe builtins
        namespace = {"__builtins__": SAFE_BUILTINS, "variables": dict(variables)}

        try:
            exec(code, namespace)
        except Exception as e:
            raise RuntimeError(f"Code execution error: {type(e).__name__}: {e}")

        result = namespace.get("result", "")
        if result is None:
            return ""
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        return str(result)
