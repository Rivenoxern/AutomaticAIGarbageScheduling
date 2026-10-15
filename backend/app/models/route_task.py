"""
app/models/route_task.py
─────────────────────────
A route task assigns a truck to a sequence of bin waypoints.

waypoints (JSON): list of dicts, e.g.:
  [{"bin_id": 3, "lat": 10.5, "lng": 106.7}, ...]

Status values:
  pending   – created, not yet started
  active    – truck is executing the route
  completed – all bins emptied
  cancelled – e.g. truck broke down; re-assigned via CrisisEvent
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class RouteTaskStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class RouteTask(Base):
    __tablename__ = "route_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    truck_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("trucks.id"), nullable=False, index=True
    )
    waypoints: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[RouteTaskStatus] = mapped_column(
        SAEnum(RouteTaskStatus, name="route_task_status"),
        nullable=False,
        default=RouteTaskStatus.pending,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    truck: Mapped["Truck"] = relationship("Truck", back_populates="route_tasks")
