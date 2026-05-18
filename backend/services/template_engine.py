"""Template engine for resolving {{variable}} placeholders in prompts and configs."""
import json
import re


def resolve_variables(template: str, variables: dict) -> str:
    """Replace {{var_name}} with values from variables dict.

    Unresolved variables are left as-is.
    Dot notation for field access: {{Step Name.field}}
    JSON strings are auto-parsed when dot access is used.
    """
    def replacer(match: re.Match) -> str:
        key = match.group(1).strip()
        parts = key.split(".")
        # Try longest-first matching for base variable name
        # e.g. "Generate Content.title" → base="Generate Content", field="title"
        value = None
        remaining = []
        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in variables:
                value = variables[candidate]
                remaining = parts[i:]
                break
        if value is None:
            return match.group(0)  # Leave unresolved
        if not remaining:
            return str(value)
        # Auto-parse JSON string for dot access
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return match.group(0)
        # Navigate into parsed object
        for part in remaining:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return match.group(0)
        return str(value)

    return re.sub(r"\{\{(.+?)\}\}", replacer, template)


def resolve_dict(data: dict, variables: dict) -> dict:
    """Recursively resolve variables in a dict's string values."""
    result = {}
    for key, value in data.items():
        if isinstance(value, str):
            result[key] = resolve_variables(value, variables)
        elif isinstance(value, dict):
            result[key] = resolve_dict(value, variables)
        elif isinstance(value, list):
            result[key] = [
                resolve_variables(item, variables) if isinstance(item, str)
                else resolve_dict(item, variables) if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result
