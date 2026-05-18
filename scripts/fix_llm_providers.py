"""Fix LLM provider/model settings to match n8n backup configurations."""
import json
import urllib.request

BASE = "http://localhost:8003/api"
TOKEN = "dev-token"


def api(method, path, data=None):
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(
        f"{BASE}{path}", data=body, method=method,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(req).read())


def get_steps(wf_id):
    return api("GET", f"/workflows/{wf_id}")["steps"]


def update_step(wf_id, step_id, config):
    return api("PUT", f"/workflows/{wf_id}/steps/{step_id}", {"config": config})


# Correction map based on n8n backup analysis
# Format: step_id -> (correct_provider, correct_model)
corrections = {
    # thodfan-video: ALL gemini/gemini-3-flash-preview
    "thodfan-video-step-00": ("gemini", "gemini-3-flash-preview"),
    "thodfan-video-step-01": ("gemini", "gemini-3-flash-preview"),
    "thodfan-video-step-02": ("gemini", "gemini-3-flash-preview"),
    "thodfan-video-step-03": ("gemini", "gemini-3-flash-preview"),
    # thodfan-image: Gen Content=openai/gpt-4o, Gen Prompt=gemini
    "thodfan-image-step-01": ("openai", "gpt-4o"),
    "thodfan-image-step-02": ("gemini", "gemini-2.0-flash"),
    # mit-sakitham-video: ALL gemini/gemini-3-flash-preview
    "mit-sakitham-video-step-00": ("gemini", "gemini-3-flash-preview"),
    "mit-sakitham-video-step-01": ("gemini", "gemini-3-flash-preview"),
    "mit-sakitham-video-step-02": ("gemini", "gemini-3-flash-preview"),
    "mit-sakitham-video-step-03": ("gemini", "gemini-3-flash-preview"),
    # mit-sakitham-image
    "mit-sakitham-image-step-01": ("openai", "gpt-4o"),
    "mit-sakitham-image-step-02": ("gemini", "gemini-2.0-flash"),
    # lihim-video: ALL gemini/gemini-3-flash-preview
    "lihim-video-step-00": ("gemini", "gemini-3-flash-preview"),
    "lihim-video-step-01": ("gemini", "gemini-3-flash-preview"),
    "lihim-video-step-02": ("gemini", "gemini-3-flash-preview"),
    "lihim-video-step-03": ("gemini", "gemini-3-flash-preview"),
    # lihim-image
    "lihim-image-step-01": ("openai", "gpt-4o"),
    "lihim-image-step-02": ("gemini", "gemini-2.0-flash"),
    # bulong-video (the-stars-whisperer Philippines)
    "bulong-video-step-00": ("openai", "gpt-4o-mini"),
    "bulong-video-step-01": ("gemini", "gemini-3-flash-preview"),
    "bulong-video-step-02": ("gemini", "gemini-3-flash-preview"),
    "bulong-video-step-03": ("openai", "gpt-4o"),
    "bulong-video-step-04": ("openai", "gpt-4o"),
    # bulong-image
    "bulong-image-step-01": ("openai", "gpt-4o"),
    "bulong-image-step-02": ("gemini", "gemini-2.0-flash"),
    # fakfa-video-2569 (ทำนายดวง2569)
    "fakfa-video-2569-step-00": ("openai", "gpt-4o-mini"),
    "fakfa-video-2569-step-01": ("gemini", "gemini-3-flash-preview"),
    "fakfa-video-2569-step-02": ("gemini", "gemini-3-flash-preview"),
    "fakfa-video-2569-step-03": ("openai", "gpt-5.2"),
    "fakfa-video-2569-step-04": ("openai", "gpt-4o-mini"),
    # fakfa-video-now (ทำนายดวงในช่วงนี้)
    "fakfa-video-now-step-00": ("openai", "gpt-4o-mini"),
    "fakfa-video-now-step-01": ("gemini", "gemini-3-flash-preview"),
    "fakfa-video-now-step-02": ("gemini", "gemini-3-flash-preview"),
    "fakfa-video-now-step-03": ("openai", "gpt-5.2"),
    "fakfa-video-now-step-04": ("openai", "gpt-4o-mini"),
    # fakfa-image (Image Post เสียงจากฟากฟ้า)
    "fakfa-image-step-01": ("openai", "gpt-4o"),
    "fakfa-image-step-02": ("gemini", "gemini-2.0-flash"),
    # wanwan-video-days (ทำนายดวงวันเกิด)
    "wanwan-video-days-step-00": ("openai", "gpt-4o-mini"),
    "wanwan-video-days-step-01": ("gemini", "gemini-3-flash-preview"),
    "wanwan-video-days-step-02": ("gemini", "gemini-3-flash-preview"),
    "wanwan-video-days-step-03": ("openai", "gpt-5.2"),
    "wanwan-video-days-step-04": ("openai", "gpt-4o-mini"),
    # wanwan-video-dates (ถอดรหัสลับวันเกิด)
    "wanwan-video-dates-step-00": ("openai", "gpt-4o-mini"),
    "wanwan-video-dates-step-01": ("gemini", "gemini-3-flash-preview"),
    "wanwan-video-dates-step-02": ("gemini", "gemini-3-flash-preview"),
    "wanwan-video-dates-step-03": ("openai", "gpt-5.2"),
    "wanwan-video-dates-step-04": ("openai", "gpt-4o-mini"),
    # wanwan-image (Image Post เสียงจากวันวาน)
    "wanwan-image-step-01": ("openai", "gpt-4o"),
    "wanwan-image-step-02": ("gemini", "gemini-2.0-flash"),
}

# Group by workflow
wf_map = {}
for step_id, (prov, model) in corrections.items():
    wf_id = step_id.rsplit("-step-", 1)[0]
    wf_map.setdefault(wf_id, []).append((step_id, prov, model))

updated = 0
skipped = 0

for wf_id, step_fixes in sorted(wf_map.items()):
    steps = get_steps(wf_id)
    step_map = {s["id"]: s for s in steps}
    print(f"\n{wf_id}:")

    for step_id, correct_provider, correct_model in step_fixes:
        step = step_map.get(step_id)
        if not step:
            print(f"  SKIP {step_id}: not found")
            skipped += 1
            continue

        cfg = step["config"]
        cur_provider = cfg.get("provider", "?")
        cur_model = cfg.get("model", "?")

        if cur_provider == correct_provider and cur_model == correct_model:
            print(f"  OK   {step['name']}: {cur_provider}/{cur_model}")
            skipped += 1
            continue

        cfg["provider"] = correct_provider
        cfg["model"] = correct_model
        update_step(wf_id, step_id, cfg)
        print(f"  FIX  {step['name']}: {cur_provider}/{cur_model} -> {correct_provider}/{correct_model}")
        updated += 1

print(f"\nDone: {updated} updated, {skipped} already correct")
