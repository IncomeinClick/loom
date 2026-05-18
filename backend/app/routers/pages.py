import json
import shutil
from fastapi import APIRouter, Depends, HTTPException
from pathlib import Path

from app.auth import verify_api_key
from app.config import settings
from app.models import PageConfig, PageCreate, PageCloneRequest
from app.services.git_tracker import auto_commit

router = APIRouter(prefix="/api/pages", tags=["pages"], dependencies=[Depends(verify_api_key)])


def _page_path(page_id: str) -> Path:
    return settings.pages_path / f"{page_id}.json"


def _load_page(page_id: str) -> PageConfig:
    path = _page_path(page_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Page '{page_id}' not found")
    return PageConfig(**json.loads(path.read_text(encoding="utf-8")))


def _save_page(page: PageConfig):
    path = _page_path(page.id)
    path.write_text(json.dumps(page.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")


@router.get("")
async def list_pages():
    pages = []
    for f in sorted(settings.pages_path.glob("*.json")):
        try:
            pages.append(json.loads(f.read_text(encoding="utf-8")))
        except Exception:
            continue
    return pages


@router.get("/{page_id}")
async def get_page(page_id: str):
    return _load_page(page_id).model_dump()


@router.post("")
async def create_page(data: PageCreate):
    if _page_path(data.id).exists():
        raise HTTPException(status_code=409, detail=f"Page '{data.id}' already exists")
    page = PageConfig(
        id=data.id,
        name=data.name,
        niche=data.niche,
        language=data.language,
        market=data.market,
        hashtag=data.hashtag,
        credentials=data.credentials,
        datatable=f"{data.id}-content",
    )
    _save_page(page)
    auto_commit(f"Create page: {data.name}")
    return page.model_dump()


@router.put("/{page_id}")
async def update_page(page_id: str, data: dict):
    page = _load_page(page_id)
    page_dict = page.model_dump()
    page_dict.update({k: v for k, v in data.items() if k != "id"})
    updated = PageConfig(**page_dict)
    _save_page(updated)
    auto_commit(f"Update page: {page_id}")
    return updated.model_dump()


@router.delete("/{page_id}")
async def delete_page(page_id: str):
    path = _page_path(page_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Page '{page_id}' not found")
    path.unlink()
    auto_commit(f"Delete page: {page_id}")
    return {"deleted": page_id}


@router.post("/{page_id}/clone")
async def clone_page(page_id: str, data: PageCloneRequest):
    source = _load_page(page_id)
    if _page_path(data.new_id).exists():
        raise HTTPException(status_code=409, detail=f"Page '{data.new_id}' already exists")

    # Clone page config
    cloned = PageConfig(
        id=data.new_id,
        name=data.new_name,
        niche=source.niche,
        language=data.target_language,
        market=data.target_market,
        hashtag=data.new_hashtag or f"#{data.new_name.replace(' ', '')}",
        cloned_from=page_id,
        credentials={},
        datatable=f"{data.new_id}-content",
    )
    _save_page(cloned)

    # Clone workflows
    for wf_file in settings.workflows_path.glob("*.json"):
        try:
            wf = json.loads(wf_file.read_text(encoding="utf-8"))
            if wf.get("page") == page_id:
                new_wf = wf.copy()
                new_wf["id"] = wf["id"].replace(page_id, data.new_id)
                new_wf["name"] = wf["name"].replace(source.name, data.new_name)
                new_wf["page"] = data.new_id
                new_wf["active"] = False  # Start inactive for review
                new_path = settings.workflows_path / f"{new_wf['id']}.json"
                new_path.write_text(json.dumps(new_wf, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            continue

    auto_commit(f"Clone page: {page_id} → {data.new_id} ({data.target_language})")
    return cloned.model_dump()
