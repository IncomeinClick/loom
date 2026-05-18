"""Ad Campaign model — tracks Facebook ad campaigns created through Loom."""
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AdCampaign(Base):
    __tablename__ = "ad_campaigns"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # local slug ID

    # Facebook IDs
    fb_campaign_id: Mapped[str | None] = mapped_column(String(100), default=None)
    fb_adset_id: Mapped[str | None] = mapped_column(String(100), default=None)

    # Loom references
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)

    # Campaign details
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="PAUSED")  # ACTIVE, PAUSED, DELETED, ARCHIVED
    objective: Mapped[str] = mapped_column(String(50), default="PAGE_LIKES")

    # Budget
    daily_budget: Mapped[float | None] = mapped_column(Float, default=None)  # in account currency (smallest unit)
    lifetime_budget: Mapped[float | None] = mapped_column(Float, default=None)
    currency: Mapped[str] = mapped_column(String(10), default="THB")

    # Targeting (JSON blob)
    targeting: Mapped[str | None] = mapped_column(Text, default=None)

    # Schedule
    start_time: Mapped[str | None] = mapped_column(String(50), default=None)  # ISO format
    end_time: Mapped[str | None] = mapped_column(String(50), default=None)

    # Ads (JSON array of {fb_ad_id, video_id, status})
    ads_json: Mapped[str | None] = mapped_column(Text, default=None)

    # Performance snapshot (updated on demand)
    spend: Mapped[float | None] = mapped_column(Float, default=None)
    impressions: Mapped[int | None] = mapped_column(Integer, default=None)
    reach: Mapped[int | None] = mapped_column(Integer, default=None)
    page_likes: Mapped[int | None] = mapped_column(Integer, default=None)
    cost_per_like: Mapped[float | None] = mapped_column(Float, default=None)
    insights_updated_at: Mapped[datetime | None] = mapped_column(default=None)

    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    page = relationship("Page", lazy="selectin")
