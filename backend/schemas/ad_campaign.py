"""Pydantic schemas for Facebook Ads management."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# ---------- Request schemas ----------

class TargetingSpec(BaseModel):
    """Facebook targeting specification."""
    countries: list[str] = []  # e.g. ["TH", "PH"]
    age_min: int = 18
    age_max: int = 65
    genders: list[int] = []  # 1=male, 2=female, empty=all
    interests: list[dict] = []  # [{"id": "123", "name": "Astrology"}]
    locales: list[int] = []  # language locale IDs


class AdCreative(BaseModel):
    """Single ad creative — references a video/post from the page."""
    video_id: str  # FB video ID
    title: Optional[str] = None  # ad title
    body: Optional[str] = None  # ad body text
    thumbnail_url: Optional[str] = None


class CampaignCreate(BaseModel):
    """Create a full Page Likes campaign with ad set and ads."""
    name: str
    page_id: str  # Loom page ID

    # Budget (one of daily or lifetime required)
    daily_budget: Optional[float] = None  # in currency units (e.g. 100 = 100 THB)
    lifetime_budget: Optional[float] = None

    # Targeting
    targeting: TargetingSpec

    # Schedule
    start_time: Optional[str] = None  # ISO format, None = start immediately
    end_time: Optional[str] = None  # required if lifetime_budget

    # Ads — list of video IDs to use as creatives
    video_ids: list[str] = []

    # Start active or paused
    start_active: bool = False


class CampaignUpdate(BaseModel):
    """Update campaign status or budget."""
    status: Optional[str] = None  # ACTIVE, PAUSED
    daily_budget: Optional[float] = None
    name: Optional[str] = None


# ---------- Response schemas ----------

class AdInfo(BaseModel):
    fb_ad_id: str
    video_id: str
    status: str = "ACTIVE"


class CampaignResponse(BaseModel):
    id: str
    fb_campaign_id: Optional[str]
    fb_adset_id: Optional[str]
    page_id: str
    page_name: Optional[str] = None
    name: str
    status: str
    objective: str
    daily_budget: Optional[float]
    lifetime_budget: Optional[float]
    currency: str
    targeting: Optional[dict] = None
    start_time: Optional[str]
    end_time: Optional[str]
    ads: list[AdInfo] = []
    # Insights
    spend: Optional[float]
    impressions: Optional[int]
    reach: Optional[int]
    page_likes: Optional[int]
    cost_per_like: Optional[float]
    insights_updated_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReelInfo(BaseModel):
    """Video/reel info from Facebook page."""
    video_id: str
    title: Optional[str] = None
    description: Optional[str] = None
    thumbnail: Optional[str] = None
    created_time: Optional[str] = None
    length: Optional[float] = None
    views: Optional[int] = None


class AdAccountInfo(BaseModel):
    """Ad account basic info."""
    account_id: str
    name: str
    currency: str
    balance: Optional[str] = None
    amount_spent: Optional[str] = None
    status: int  # 1=active, 2=disabled, etc.
