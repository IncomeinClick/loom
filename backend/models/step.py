import json
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Step(Base):
    __tablename__ = "steps"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # llm, http, datatable, schedule
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    config: Mapped[str] = mapped_column(Text, default="{}")  # JSON blob
    output_var: Mapped[str | None] = mapped_column(String(100), default=None)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=_utcnow, onupdate=_utcnow)

    workflow = relationship("Workflow", back_populates="steps", lazy="selectin")

    @property
    def config_dict(self) -> dict:
        return json.loads(self.config) if self.config else {}

    @config_dict.setter
    def config_dict(self, value: dict):
        self.config = json.dumps(value, ensure_ascii=False)
