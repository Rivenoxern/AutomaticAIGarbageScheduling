"""
app/models/trash_bin.py
────────────────────────
A physical trash bin installed at a city location.

current_capacity_pct: 0–100 float.  Thresholds used by agents:
  ≥ 75  → triggers Dynamic Routing Agent
  ≥ 95  → critical / overflow warning
"""
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class TrashBin(Base):
    __tablename__ = "trash_bins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    location_name: Mapped[str] = mapped_column(String(200), nullable=False)

    # 2-D grid coordinates (mocked; no paid map API required)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)

    current_capacity_pct: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
