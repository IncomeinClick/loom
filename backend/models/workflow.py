from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Workflow(Base):
    __tablename__ = "workflows"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    language: Mapped[str] = mapped_column(String(50), default="English")
    schedule: Mapped[str | None] = mapped_column(String(100), default=None)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    page = relationship("Page", back_populates="workflows", lazy="selectin")
    steps = relationship(
        "Step",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Step.sort_order",
    )
    executions = relationship(
        "Execution", back_populates="workflow", cascade="all, delete-orphan", lazy="noload"
    )
