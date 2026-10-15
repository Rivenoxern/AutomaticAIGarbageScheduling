"""
app/models/truck.py
────────────────────
Garbage truck entity.

Status values:
  idle        – parked, awaiting assignment
  en_route    – currently executing a route task
  out_of_service – broken down / under maintenance
"""
import enum

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TruckStatus(str, enum.Enum):
    idle = "idle"
    en_route = "en_route"
    out_of_service = "out_of_service"


class Truck(Base):
    __tablename__ = "trucks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    driver_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("drivers.id"), nullable=True
    )
    plate_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status: Mapped[TruckStatus] = mapped_column(
        SAEnum(TruckStatus, name="truck_status"),
        nullable=False,
        default=TruckStatus.idle,
    )
    # Stored as "lat,lng" string for simplicity; Phase 2 will use proper geo types.
    current_gps_location: Mapped[str | None] = mapped_column(String(60), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    driver: Mapped["Driver"] = relationship("Driver", back_populates="truck")
    route_tasks: Mapped[list["RouteTask"]] = relationship(
        "RouteTask", back_populates="truck"
    )
    crisis_events: Mapped[list["CrisisEvent"]] = relationship(
        "CrisisEvent", back_populates="truck"
    )
