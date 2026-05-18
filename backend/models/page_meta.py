from datetime import datetime, timezone
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from backend.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PageMeta(Base):
    __tablename__ = "page_meta"

    page_id: Mapped[str] = mapped_column(String(100), primary_key=True)

    # Stage timestamps (set when stage is reached)
    setup_at: Mapped[datetime | None] = mapped_column(default=None)        # Stage 1: Loom setup done
    fb_ready_at: Mapped[datetime | None] = mapped_column(default=None)     # Stage 2: FB token added
    video_live_at: Mapped[datetime | None] = mapped_column(default=None)   # Stage 3: Video workflow activated
    image_live_at: Mapped[datetime | None] = mapped_column(default=None)   # Stage 4: Image post activated
    ads_running_at: Mapped[datetime | None] = mapped_column(default=None)   # Stage 5: Running Facebook ads
    monetized_at: Mapped[datetime | None] = mapped_column(default=None)    # Stage 6: Content monetization approved

    # FB Page ID (for API queries)
    fb_page_id: Mapped[str | None] = mapped_column(String(100), default=None)

    # Notes
    notes: Mapped[str | None] = mapped_column(Text, default=None)

    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)
