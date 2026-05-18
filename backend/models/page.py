from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    niche_id: Mapped[str] = mapped_column(ForeignKey("niches.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    language: Mapped[str] = mapped_column(String(50), default="English")
    market: Mapped[str | None] = mapped_column(String(100), default=None)
    hashtag: Mapped[str | None] = mapped_column(String(200), default=None)
    bio: Mapped[str | None] = mapped_column(Text, default=None)
    profile_image: Mapped[str | None] = mapped_column(String(500), default=None)
    cover_photo: Mapped[str | None] = mapped_column(String(500), default=None)
    cloned_from: Mapped[str | None] = mapped_column(
        ForeignKey("pages.id", ondelete="SET NULL"), default=None
    )
    group_name: Mapped[str | None] = mapped_column(String(200), default=None)
    sort_order: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    niche = relationship("Niche", back_populates="pages", lazy="selectin")
    workflows = relationship(
        "Workflow", back_populates="page", cascade="all, delete-orphan", lazy="selectin"
    )
    credentials = relationship(
        "Credential", back_populates="page", cascade="all, delete-orphan", lazy="selectin"
    )
