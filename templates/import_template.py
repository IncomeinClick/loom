"""Import a Loom workflow template JSON file into your Loom instance.

Usage:
    python import_template.py video-workflow-template.json
    python import_template.py image-workflow-template.json

Reads LOOM_URL and LOOM_TOKEN from environment, or from the script flags.

Before running:
1. Open the JSON file and replace every <PLACEHOLDER> with your real values
   (page_id, credential_ids, language, schedule, etc.)
2. Make sure the page and credentials already exist in your Loom dashboard.
3. Make sure your data table (e.g. <YOUR_PAGE_ID>-content) is set up with the
   right columns (seed, idea, script, caption, video, image).
"""
import argparse
import json
import os
import sys
import urllib.request
import urllib.parse


def call(method: str, path: str, base: str, token: str, body=None):
    url = f"{base.rstrip('/')}/api{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        raw = resp.read()
        return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def strip_comments(obj):
    """Recursively remove keys starting with '_' (template comments)."""
    if isinstance(obj, dict):
        return {k: strip_comments(v) for k, v in obj.items() if not k.startswith("_")}
    if isinstance(obj, list):
        return [strip_comments(x) for x in obj]
    return obj


def check_placeholders(obj, path=""):
    """Raise if any <...> placeholder is still present."""
    if isinstance(obj, str) and "<" in obj and ">" in obj:
        # naive check — any "<...>" substring is suspicious
        import re
        matches = re.findall(r"<[A-Z_][A-Z0-9_]*>|<your[^>]*>", obj)
        if matches:
            raise ValueError(f"Unfilled placeholder in {path}: {matches}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            check_placeholders(v, f"{path}.{k}")
    if isinstance(obj, list):
        for i, v in enumerate(obj):
            check_placeholders(v, f"{path}[{i}]")


def import_template(template_path: str, base: str, token: str):
    with open(template_path) as f:
        tpl = strip_comments(json.load(f))

    check_placeholders(tpl)

    wf = tpl["workflow"]
    steps = tpl["steps"]

    print(f"[import] Creating workflow: {wf['id']} ({len(steps)} steps)")

    status, body = call("POST", "/workflows", base, token, wf)
    if status not in (200, 201):
        print(f"[error] workflow create failed: {status} {body}")
        sys.exit(1)
    print(f"[import] Workflow created ({status})")

    workflow_id = wf["id"]
    for step in steps:
        step_payload = {
            "workflow_id": workflow_id,
            "type": step["type"],
            "name": step["name"],
            "sort_order": step["sort_order"],
            "output_var": step["output_var"],
            "config": step["config"],
        }
        status, body = call("POST", "/steps", base, token, step_payload)
        if status not in (200, 201):
            print(f"[error] step '{step['name']}' failed: {status} {body}")
            sys.exit(1)
        print(f"[import]   step {step['sort_order']:2d} '{step['name']}' OK")

    print(f"\n[import] DONE — workflow {workflow_id} created with {len(steps)} steps.")
    print(f"[import] Open your Loom dashboard to activate the workflow when ready.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("template", help="Path to template JSON")
    parser.add_argument("--url", default=os.environ.get("LOOM_URL", "http://127.0.0.1:8000"),
                        help="Loom base URL (env: LOOM_URL)")
    parser.add_argument("--token", default=os.environ.get("LOOM_TOKEN"),
                        help="Loom API bearer token (env: LOOM_TOKEN)")
    args = parser.parse_args()

    if not args.token:
        print("error: provide --token or set LOOM_TOKEN env var")
        sys.exit(1)

    import_template(args.template, args.url, args.token)
