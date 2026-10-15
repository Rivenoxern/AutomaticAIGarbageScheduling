"""
app/models/crisis_event.py
───────────────────────────
Records a crisis (e.g. truck breakdown) and tracks its resolution.

issue_type examples:
  "breakdown"       – mechanical failure
  "accident"        – road incident
  "flat_tire"       – minor mechanical
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CrisisEvent(Base):
    __tablename__ = "crisis_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    truck_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trucks.id"), nullable=False, index=True
    )
    issue_type: Mapped[str] = mapped_column(String(60), nullable=False)
    reported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Relationships ─────────────────────────────────────────────────────────
    truck: Mapped["Truck"] = relationship("Truck", back_populates="crisis_events")
