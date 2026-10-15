"""
app/models/driver.py
─────────────────────
Truck driver registered in the system.
"""
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    license_number: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=True)

    # Back-reference: one driver can be assigned to at most one truck at a time
    truck: Mapped["Truck"] = relationship("Truck", back_populates="driver", uselist=False)
