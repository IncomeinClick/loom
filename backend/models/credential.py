from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Credential(Base):
    __tablename__ = "credentials"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    page_id: Mapped[str | None] = mapped_column(
        ForeignKey("pages.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # facebook, openai, gemini, nova_astra
    encrypted_value: Mapped[str] = mapped_column(String(500), nullable=False)
    last_four: Mapped[str | None] = mapped_column(String(4), default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    page = relationship("Page", back_populates="credentials", lazy="selectin")
