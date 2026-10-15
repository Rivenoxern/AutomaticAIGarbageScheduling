"""
app/routers/trash_bins.py
──────────────────────────
CRUD endpoints for TrashBin management.

Endpoints:
  GET    /bins/            – list all bins (supports filter: capacity_above)
  POST   /bins/            – create a new bin
  GET    /bins/{id}        – get bin by ID
  PATCH  /bins/{id}        – update bin fields (capacity, location)
  DELETE /bins/{id}        – remove a bin
  GET    /bins/overflowing – list bins with capacity ≥ threshold (default 75%)
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.trash_bin import TrashBin

router = APIRouter(prefix="/bins", tags=["Trash Bins"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class TrashBinCreate(BaseModel):
    location_name: str
    latitude: float
    longitude: float
    current_capacity_pct: float = Field(default=0.0, ge=0.0, le=100.0)


class TrashBinUpdate(BaseModel):
    location_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    current_capacity_pct: float | None = Field(default=None, ge=0.0, le=100.0)


class TrashBinOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    location_name: str
    latitude: float
    longitude: float
    current_capacity_pct: float
    last_updated: datetime


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/overflowing", response_model=list[TrashBinOut])
def get_overflowing_bins(
    threshold: float = Query(default=75.0, ge=0.0, le=100.0),
    db: Session = Depends(get_db),
):
    """
    Return all bins whose current_capacity_pct ≥ threshold (default 75%).
    The Dynamic Routing Agent will poll this endpoint.
    """
    return (
        db.query(TrashBin)
        .filter(TrashBin.current_capacity_pct >= threshold)
        .order_by(TrashBin.current_capacity_pct.desc())
        .all()
    )


@router.get("/", response_model=list[TrashBinOut])
def list_bins(
    skip: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
):
    """Return all trash bins, paginated."""
    return db.query(TrashBin).offset(skip).limit(limit).all()


@router.post("/", response_model=TrashBinOut, status_code=status.HTTP_201_CREATED)
def create_bin(payload: TrashBinCreate, db: Session = Depends(get_db)):
    """Register a new trash bin."""
    bin_obj = TrashBin(**payload.model_dump())
    db.add(bin_obj)
    db.commit()
    db.refresh(bin_obj)
    return bin_obj


@router.get("/{bin_id}", response_model=TrashBinOut)
def get_bin(bin_id: int, db: Session = Depends(get_db)):
    """Fetch a single bin by primary key."""
    bin_obj = db.get(TrashBin, bin_id)
    if not bin_obj:
        raise HTTPException(status_code=404, detail="Trash bin not found")
    return bin_obj


@router.patch("/{bin_id}", response_model=TrashBinOut)
def update_bin(
    bin_id: int,
    payload: TrashBinUpdate,
    db: Session = Depends(get_db),
):
    """Partially update a trash bin's fields."""
    bin_obj = db.get(TrashBin, bin_id)
    if not bin_obj:
        raise HTTPException(status_code=404, detail="Trash bin not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(bin_obj, field, value)

    # Manually refresh timestamp since SQLAlchemy onupdate only fires on flush
    bin_obj.last_updated = datetime.now(timezone.utc)

    db.commit()
    db.refresh(bin_obj)
    return bin_obj


@router.delete("/{bin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bin(bin_id: int, db: Session = Depends(get_db)):
    """Remove a trash bin record."""
    bin_obj = db.get(TrashBin, bin_id)
    if not bin_obj:
        raise HTTPException(status_code=404, detail="Trash bin not found")
    db.delete(bin_obj)
    db.commit()
