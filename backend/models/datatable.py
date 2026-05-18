import json
from datetime import datetime, timezone

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DataTable(Base):
    __tablename__ = "datatables"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    workflow_id: Mapped[str | None] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    columns: Mapped[str] = mapped_column(Text, default="[]")  # JSON array of column names
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    @property
    def columns_list(self) -> list[str]:
        return json.loads(self.columns) if self.columns else []

    @columns_list.setter
    def columns_list(self, value: list[str]):
        self.columns = json.dumps(value, ensure_ascii=False)

    rows = relationship(
        "DataRow", back_populates="datatable", cascade="all, delete-orphan", lazy="selectin"
    )


class DataRow(Base):
    __tablename__ = "datarows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)  # UUID
    datatable_id: Mapped[str] = mapped_column(
        ForeignKey("datatables.id", ondelete="CASCADE"), nullable=False
    )
    data: Mapped[str] = mapped_column(Text, default="{}")  # JSON blob
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(default=_utcnow)

    datatable = relationship("DataTable", back_populates="rows", lazy="selectin")

    @property
    def data_dict(self) -> dict:
        return json.loads(self.data) if self.data else {}

    @data_dict.setter
    def data_dict(self, value: dict):
        self.data = json.dumps(value, ensure_ascii=False)
