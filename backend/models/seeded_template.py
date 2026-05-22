from datetime import datetime, timezone

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from backend.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SeededTemplate(Base):
    """Tracks template workflow IDs that have been seeded at least once.

    Once a row exists for a given template_id, the seeder will skip it
    forever — even if the user deletes the workflow afterwards.
    """
    __tablename__ = "seeded_templates"

    template_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    seeded_at: Mapped[datetime] = mapped_column(default=_utcnow)
