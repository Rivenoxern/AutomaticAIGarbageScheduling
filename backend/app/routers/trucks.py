"""
app/routers/trucks.py
──────────────────────
CRUD endpoints for Truck management.

Endpoints:
  GET    /trucks/          – list all trucks
  POST   /trucks/          – create a new truck
  GET    /trucks/{id}      – get truck by ID
  PATCH  /trucks/{id}      – update truck fields (status, GPS, driver)
  DELETE /trucks/{id}      – remove a truck
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.truck import Truck, TruckStatus

router = APIRouter(prefix="/trucks", tags=["Trucks"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class TruckCreate(BaseModel):
    plate_number: str
    driver_id: int | None = None
    status: TruckStatus = TruckStatus.idle
    current_gps_location: str | None = None


class TruckUpdate(BaseModel):
    driver_id: int | None = None
    status: TruckStatus | None = None
    current_gps_location: str | None = None


class TruckOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plate_number: str
    driver_id: int | None
    status: TruckStatus
    current_gps_location: str | None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[TruckOut])
def list_trucks(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Return all trucks, paginated."""
    return db.query(Truck).offset(skip).limit(limit).all()


@router.post("/", response_model=TruckOut, status_code=status.HTTP_201_CREATED)
def create_truck(payload: TruckCreate, db: Session = Depends(get_db)):
    """Register a new truck."""
    truck = Truck(**payload.model_dump())
    db.add(truck)
    db.commit()
    db.refresh(truck)
    return truck


@router.get("/{truck_id}", response_model=TruckOut)
def get_truck(truck_id: int, db: Session = Depends(get_db)):
    """Fetch a single truck by primary key."""
    truck = db.get(Truck, truck_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    return truck


@router.patch("/{truck_id}", response_model=TruckOut)
def update_truck(
    truck_id: int,
    payload: TruckUpdate,
    db: Session = Depends(get_db),
):
    """Partially update truck fields (status, GPS location, driver)."""
    truck = db.get(Truck, truck_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(truck, field, value)

    db.commit()
    db.refresh(truck)
    return truck


@router.delete("/{truck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_truck(truck_id: int, db: Session = Depends(get_db)):
    """Remove a truck record."""
    truck = db.get(Truck, truck_id)
    if not truck:
        raise HTTPException(status_code=404, detail="Truck not found")
    db.delete(truck)
    db.commit()
