import json
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    workflow_id: Mapped[str] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="running")  # running, success, failed, cancelled
    trigger_type: Mapped[str] = mapped_column(String(20), default="manual")  # manual, scheduled
    started_at: Mapped[datetime] = mapped_column(default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    variables: Mapped[str] = mapped_column(Text, default="{}")  # JSON accumulated vars

    workflow = relationship("Workflow", back_populates="executions", lazy="selectin")
    step_outputs = relationship(
        "StepOutput",
        back_populates="execution",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="StepOutput.started_at",
    )

    @property
    def variables_dict(self) -> dict:
        return json.loads(self.variables) if self.variables else {}

    @variables_dict.setter
    def variables_dict(self, value: dict):
        self.variables = json.dumps(value, ensure_ascii=False)


class StepOutput(Base):
    __tablename__ = "step_outputs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    execution_id: Mapped[str] = mapped_column(
        ForeignKey("executions.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[str] = mapped_column(
        ForeignKey("steps.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, success, failed, skipped
    output: Mapped[str | None] = mapped_column(Text, default=None)
    error_message: Mapped[str | None] = mapped_column(Text, default=None)
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
    started_at: Mapped[datetime | None] = mapped_column(default=None)
    finished_at: Mapped[datetime | None] = mapped_column(default=None)

    execution = relationship("Execution", back_populates="step_outputs", lazy="selectin")
