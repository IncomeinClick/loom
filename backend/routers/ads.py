"""Facebook Ads management router.

Manages Page Like campaigns through the Facebook Marketing API.
Tracks campaigns locally in ad_campaigns table.
"""
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_db, verify_token
from backend.models.ad_campaign import AdCampaign
from backend.models.credential import Credential
from backend.models.page import Page
from backend.models.page_meta import PageMeta
from backend.schemas.ad_campaign import (
    AdAccountInfo,
    AdInfo,
    CampaignCreate,
    CampaignResponse,
    CampaignUpdate,
    ReelInfo,
)
from backend.services.ads_service import ads_service
from backend.services.credential_service import credential_service
from backend.services.notification_service import notify_activity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ads", tags=["ads"], dependencies=[Depends(verify_token)])


# ---------- Helpers ----------

async def _get_user_token(db: AsyncSession) -> str:
    """Get the facebook_user credential token (used for ads management)."""
    result = await db.execute(
        select(Credential).where(Credential.type == "facebook_user")
    )
    cred = result.scalars().first()
    if not cred:
        raise HTTPException(status_code=400, detail="No facebook_user credential found. Add a user token with ads_management permission.")
    return credential_service.decrypt(cred.encrypted_value)


async def _sync_ads_running(db: AsyncSession, page_id: str):
    """Auto-toggle ads_running stage based on whether the page has any active campaigns."""
    result = await db.execute(
        select(AdCampaign).where(AdCampaign.page_id == page_id, AdCampaign.status == "ACTIVE")
    )
    has_active = len(result.scalars().all()) > 0
    meta = await db.get(PageMeta, page_id)
    if not meta:
        return
    if has_active and not meta.ads_running_at:
        meta.ads_running_at = datetime.now(timezone.utc)
        meta.updated_at = datetime.now(timezone.utc)
    elif not has_active and meta.ads_running_at:
        meta.ads_running_at = None
        meta.updated_at = datetime.now(timezone.utc)


async def _get_fb_page_id(db: AsyncSession, page_id: str) -> str:
    """Get the Facebook page ID from page_meta."""
    meta = await db.get(PageMeta, page_id)
    if not meta or not meta.fb_page_id:
        raise HTTPException(status_code=400, detail=f"Page '{page_id}' has no fb_page_id. Sync FB pages first.")
    return meta.fb_page_id


def _campaign_to_response(campaign: AdCampaign) -> CampaignResponse:
    """Convert DB model to response schema."""
    ads = []
    if campaign.ads_json:
        try:
            ads = [AdInfo(**a) for a in json.loads(campaign.ads_json)]
        except (json.JSONDecodeError, TypeError):
            pass

    targeting = None
    if campaign.targeting:
        try:
            targeting = json.loads(campaign.targeting)
        except json.JSONDecodeError:
            pass

    return CampaignResponse(
        id=campaign.id,
        fb_campaign_id=campaign.fb_campaign_id,
        fb_adset_id=campaign.fb_adset_id,
        page_id=campaign.page_id,
        page_name=campaign.page.name if campaign.page else None,
        name=campaign.name,
        status=campaign.status,
        objective=campaign.objective,
        daily_budget=campaign.daily_budget,
        lifetime_budget=campaign.lifetime_budget,
        currency=campaign.currency,
        targeting=targeting,
        start_time=campaign.start_time,
        end_time=campaign.end_time,
        ads=ads,
        spend=campaign.spend,
        impressions=campaign.impressions,
        reach=campaign.reach,
        page_likes=campaign.page_likes,
        cost_per_like=campaign.cost_per_like,
        insights_updated_at=campaign.insights_updated_at,
        created_at=campaign.created_at,
        updated_at=campaign.updated_at,
    )


# ---------- Routes ----------

@router.get("/account", response_model=AdAccountInfo)
async def get_ad_account(db: AsyncSession = Depends(get_db)):
    """Get ad account info (balance, status, currency)."""
    token = await _get_user_token(db)
    info = await ads_service.get_account_info(token)
    return AdAccountInfo(
        account_id=info.get("id", ""),
        name=info.get("name", ""),
        currency=info.get("currency", ""),
        balance=info.get("balance"),
        amount_spent=info.get("amount_spent"),
        status=info.get("account_status", 0),
    )


@router.get("/fb/campaigns")
async def list_fb_campaigns(db: AsyncSession = Depends(get_db)):
    """List all campaigns directly from Facebook Ad Account."""
    token = await _get_user_token(db)
    return await ads_service.list_fb_campaigns(token)


@router.get("/fb/campaigns/{campaign_id}/detail")
async def get_fb_campaign_detail(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed campaign info from Facebook."""
    token = await _get_user_token(db)
    return await ads_service.get_fb_campaign_detail(token, campaign_id)


@router.get("/fb/campaigns/{campaign_id}/insights")
async def get_fb_campaign_insights(campaign_id: str, date_preset: str = "maximum", db: AsyncSession = Depends(get_db)):
    """Get insights for a FB campaign."""
    token = await _get_user_token(db)
    return await ads_service.get_campaign_insights(token, campaign_id, date_preset)



@router.get("/fb/campaigns/{campaign_id}/adsets")
async def list_fb_adsets(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """List ad sets for a campaign from Facebook."""
    token = await _get_user_token(db)
    return await ads_service.list_fb_adsets(token, campaign_id)


@router.get("/fb/campaigns/{campaign_id}/adsets/{adset_id}/ads")
async def list_fb_ads(campaign_id: str, adset_id: str, db: AsyncSession = Depends(get_db)):
    """List ads for an ad set from Facebook."""
    token = await _get_user_token(db)
    return await ads_service.list_fb_ads(token, adset_id)


@router.get("/pages/{page_id}/videos", response_model=list[ReelInfo])
async def get_page_videos(page_id: str, limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Get recent videos/reels from a Facebook page."""
    token = await _get_user_token(db)
    fb_page_id = await _get_fb_page_id(db, page_id)
    videos = await ads_service.get_page_videos(token, fb_page_id, limit=limit)
    return [ReelInfo(**v) for v in videos]


@router.get("/campaigns", response_model=list[CampaignResponse])
async def list_campaigns(
    page_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List all tracked campaigns, optionally filtered by page."""
    query = select(AdCampaign).order_by(AdCampaign.created_at.desc())
    if page_id:
        query = query.where(AdCampaign.page_id == page_id)
    result = await db.execute(query)
    campaigns = result.scalars().all()
    return [_campaign_to_response(c) for c in campaigns]


@router.post("/campaigns", response_model=CampaignResponse)
async def create_campaign(body: CampaignCreate, db: AsyncSession = Depends(get_db)):
    """Create a full Page Likes campaign with ad set and ads.

    Flow:
    1. Create FB campaign (OUTCOME_ENGAGEMENT)
    2. Create FB ad set (PAGE_LIKES optimization, targeting, budget)
    3. Create FB ads (one per video_id using video creative)
    4. Save everything to local DB for tracking
    """
    # Validate page exists
    page = await db.get(Page, body.page_id)
    if not page:
        raise HTTPException(status_code=404, detail=f"Page '{body.page_id}' not found")

    token = await _get_user_token(db)
    fb_page_id = await _get_fb_page_id(db, body.page_id)

    status = "ACTIVE" if body.start_active else "PAUSED"

    # 1. Create campaign on Facebook (with CBO budget)
    fb_campaign_id = await ads_service.create_campaign(
        token=token,
        name=body.name,
        daily_budget=body.daily_budget,
        lifetime_budget=body.lifetime_budget,
        status=status,
    )

    # 2. Create ad set (no budget — CBO handles it at campaign level)
    targeting_dict = body.targeting.model_dump() if body.targeting else {}
    fb_adset_id = await ads_service.create_adset(
        token=token,
        campaign_id=fb_campaign_id,
        name=f"{body.name} - Ad Set",
        fb_page_id=fb_page_id,
        targeting=targeting_dict,
        start_time=body.start_time,
        end_time=body.end_time,
        status=status,
    )

    # 3. Create ads (one per video)
    ads_list = []
    for i, video_id in enumerate(body.video_ids, 1):
        ad_name = f"{body.name} - Ad {i}"
        fb_ad_id = await ads_service.create_ad(
            token=token,
            adset_id=fb_adset_id,
            name=ad_name,
            fb_page_id=fb_page_id,
            video_id=video_id,
            status=status,
        )
        ads_list.append({
            "fb_ad_id": fb_ad_id,
            "video_id": video_id,
            "status": status,
        })

    # 4. Generate local ID and save to DB
    # Slugify: page_id + "-likes-" + counter
    existing = await db.execute(
        select(AdCampaign).where(AdCampaign.page_id == body.page_id)
    )
    count = len(existing.scalars().all())
    local_id = f"{body.page_id}-likes-{count + 1}"

    campaign = AdCampaign(
        id=local_id,
        fb_campaign_id=fb_campaign_id,
        fb_adset_id=fb_adset_id,
        page_id=body.page_id,
        name=body.name,
        status=status,
        objective="PAGE_LIKES",
        daily_budget=body.daily_budget,
        lifetime_budget=body.lifetime_budget,
        targeting=json.dumps(targeting_dict),
        start_time=body.start_time,
        end_time=body.end_time,
        ads_json=json.dumps(ads_list),
    )
    db.add(campaign)
    await db.flush()
    await db.refresh(campaign)

    logger.info(f"Created campaign {local_id}: FB campaign={fb_campaign_id}, adset={fb_adset_id}, {len(ads_list)} ads")
    await _sync_ads_running(db, body.page_id)
    await notify_activity("created", "ad campaign", local_id, f"Page: {body.page_id}, Budget: {body.daily_budget or body.lifetime_budget}, {len(ads_list)} ads")
    return _campaign_to_response(campaign)


@router.get("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def get_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Get campaign details."""
    campaign = await db.get(AdCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    return _campaign_to_response(campaign)


@router.put("/campaigns/{campaign_id}", response_model=CampaignResponse)
async def update_campaign(campaign_id: str, body: CampaignUpdate, db: AsyncSession = Depends(get_db)):
    """Update campaign (status, budget, name)."""
    campaign = await db.get(AdCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    token = await _get_user_token(db)

    # Update on Facebook
    if body.status and campaign.fb_campaign_id:
        await ads_service.update_campaign_status(token, campaign.fb_campaign_id, body.status)
        campaign.status = body.status

    if body.daily_budget is not None:
        campaign.daily_budget = body.daily_budget
        # Update ad set budget on FB
        if campaign.fb_adset_id:
            url = f"https://graph.facebook.com/v23.0/{campaign.fb_adset_id}"
            import httpx
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(url, params={
                    "access_token": token,
                    "daily_budget": str(int(body.daily_budget * 100)),
                })
                if not resp.is_success:
                    logger.warning(f"Failed to update ad set budget: {resp.text}")

    if body.name:
        campaign.name = body.name

    campaign.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await notify_activity("updated", "ad campaign", campaign_id)
    return _campaign_to_response(campaign)


@router.post("/campaigns/{campaign_id}/pause", response_model=CampaignResponse)
async def pause_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Pause a campaign (all levels: campaign, adset, ads)."""
    campaign = await db.get(AdCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    token = await _get_user_token(db)
    if campaign.fb_campaign_id:
        await ads_service.update_campaign_status(token, campaign.fb_campaign_id, "PAUSED")
    if campaign.fb_adset_id:
        await ads_service.update_adset_status(token, campaign.fb_adset_id, "PAUSED")
    if campaign.ads_json:
        for ad in json.loads(campaign.ads_json):
            if ad.get("fb_ad_id"):
                await ads_service.update_ad_status(token, ad["fb_ad_id"], "PAUSED")
    campaign.status = "PAUSED"
    campaign.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await _sync_ads_running(db, campaign.page_id)
    await notify_activity("paused", "ad campaign", campaign_id)
    return _campaign_to_response(campaign)


@router.post("/campaigns/{campaign_id}/resume", response_model=CampaignResponse)
async def resume_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Resume (activate) a paused campaign (all levels: campaign, adset, ads)."""
    campaign = await db.get(AdCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    token = await _get_user_token(db)
    if campaign.fb_campaign_id:
        await ads_service.update_campaign_status(token, campaign.fb_campaign_id, "ACTIVE")
    if campaign.fb_adset_id:
        await ads_service.update_adset_status(token, campaign.fb_adset_id, "ACTIVE")
    if campaign.ads_json:
        for ad in json.loads(campaign.ads_json):
            if ad.get("fb_ad_id"):
                await ads_service.update_ad_status(token, ad["fb_ad_id"], "ACTIVE")
    campaign.status = "ACTIVE"
    campaign.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await _sync_ads_running(db, campaign.page_id)
    await notify_activity("resumed", "ad campaign", campaign_id)
    return _campaign_to_response(campaign)


@router.delete("/campaigns/{campaign_id}")
async def delete_campaign(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Delete a campaign (from FB and local DB)."""
    campaign = await db.get(AdCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")

    token = await _get_user_token(db)

    # Delete on Facebook
    if campaign.fb_campaign_id:
        try:
            await ads_service.delete_campaign(token, campaign.fb_campaign_id)
        except Exception as e:
            logger.warning(f"Failed to delete FB campaign {campaign.fb_campaign_id}: {e}")

    page_id = campaign.page_id
    campaign_name = campaign.name
    await db.delete(campaign)
    await db.flush()
    await _sync_ads_running(db, page_id)
    await notify_activity("deleted", "ad campaign", campaign_id, f"Name: {campaign_name}")
    return {"detail": f"Campaign '{campaign_id}' deleted"}


@router.post("/campaigns/{campaign_id}/sync-insights", response_model=CampaignResponse)
async def sync_insights(campaign_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch latest insights from Facebook and update local record."""
    campaign = await db.get(AdCampaign, campaign_id)
    if not campaign:
        raise HTTPException(status_code=404, detail=f"Campaign '{campaign_id}' not found")
    if not campaign.fb_campaign_id:
        raise HTTPException(status_code=400, detail="Campaign has no Facebook campaign ID")

    token = await _get_user_token(db)

    # Sync campaign status
    try:
        status_data = await ads_service.get_campaign_status(token, campaign.fb_campaign_id)
        campaign.status = status_data.get("effective_status", campaign.status)
    except Exception as e:
        logger.warning(f"Failed to sync campaign status: {e}")

    # Sync insights
    try:
        insights = await ads_service.get_campaign_insights(token, campaign.fb_campaign_id)
        campaign.spend = insights.get("spend", 0)
        campaign.impressions = insights.get("impressions", 0)
        campaign.reach = insights.get("reach", 0)
        campaign.page_likes = insights.get("page_likes", 0)
        campaign.cost_per_like = insights.get("cost_per_like", 0)
        campaign.insights_updated_at = datetime.now(timezone.utc)
    except Exception as e:
        logger.warning(f"Failed to sync insights: {e}")

    campaign.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return _campaign_to_response(campaign)


@router.post("/campaigns/sync-all")
async def sync_all_insights(db: AsyncSession = Depends(get_db)):
    """Sync insights for all active campaigns."""
    result = await db.execute(
        select(AdCampaign).where(AdCampaign.status.in_(["ACTIVE", "PAUSED"]))
    )
    campaigns = result.scalars().all()
    token = await _get_user_token(db)
    synced = 0
    errors = 0

    for campaign in campaigns:
        if not campaign.fb_campaign_id:
            continue
        try:
            # Status
            status_data = await ads_service.get_campaign_status(token, campaign.fb_campaign_id)
            campaign.status = status_data.get("effective_status", campaign.status)

            # Insights
            insights = await ads_service.get_campaign_insights(token, campaign.fb_campaign_id)
            campaign.spend = insights.get("spend", 0)
            campaign.impressions = insights.get("impressions", 0)
            campaign.reach = insights.get("reach", 0)
            campaign.page_likes = insights.get("page_likes", 0)
            campaign.cost_per_like = insights.get("cost_per_like", 0)
            campaign.insights_updated_at = datetime.now(timezone.utc)
            synced += 1
        except Exception as e:
            logger.warning(f"Failed to sync campaign {campaign.id}: {e}")
            errors += 1

    await db.flush()

    # Sync ads_running stage for all affected pages
    synced_pages = set()
    for campaign in campaigns:
        if campaign.page_id not in synced_pages:
            await _sync_ads_running(db, campaign.page_id)
            synced_pages.add(campaign.page_id)

    return {"synced": synced, "errors": errors, "total": len(campaigns)}
