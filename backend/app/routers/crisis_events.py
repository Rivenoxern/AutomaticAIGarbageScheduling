"""
app/routers/crisis_events.py
─────────────────────────────
Endpoints for CrisisEvent management.

Endpoints:
  GET  /crises/            – list all crisis events (filterable by resolved)
  GET  /crises/unresolved  – convenience: list unresolved events only
  GET  /crises/{id}        – get one event
  POST /crises/            – manually report a crisis (for testing)
  PATCH /crises/{id}/resolve – manually mark an event as resolved
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.crisis_event import CrisisEvent

router = APIRouter(prefix="/crises", tags=["Crisis Events"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class CrisisEventCreate(BaseModel):
    truck_id: int
    issue_type: str = "breakdown"


class CrisisEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    truck_id: int
    issue_type: str
    reported_at: datetime
    resolved: bool


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/unresolved", response_model=list[CrisisEventOut])
def get_unresolved_crises(db: Session = Depends(get_db)):
    """Return all crisis events that have NOT yet been resolved."""
    return (
        db.query(CrisisEvent)
        .filter(CrisisEvent.resolved == False)  # noqa: E712
        .order_by(CrisisEvent.reported_at.desc())
        .all()
    )


@router.get("/", response_model=list[CrisisEventOut])
def list_crises(
    resolved: bool | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    List crisis events. Optional filter:
      ?resolved=false  – only unresolved
      ?resolved=true   – only resolved
    """
    q = db.query(CrisisEvent)
    if resolved is not None:
        q = q.filter(CrisisEvent.resolved == resolved)
    return q.order_by(CrisisEvent.reported_at.desc()).offset(skip).limit(limit).all()


@router.get("/{crisis_id}", response_model=CrisisEventOut)
def get_crisis(crisis_id: int, db: Session = Depends(get_db)):
    """Fetch a single crisis event by ID."""
    event = db.get(CrisisEvent, crisis_id)
    if not event:
        raise HTTPException(status_code=404, detail="Crisis event not found")
    return event


@router.post("/", response_model=CrisisEventOut, status_code=status.HTTP_201_CREATED)
def report_crisis(payload: CrisisEventCreate, db: Session = Depends(get_db)):
    """
    Manually report a truck crisis. The Crisis Agent background loop will
    detect and handle it automatically. You can also trigger it immediately
    via POST /api/v1/agents/crisis/run/{crisis_id}.
    """
    event = CrisisEvent(
        truck_id=payload.truck_id,
        issue_type=payload.issue_type,
        resolved=False,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


@router.patch("/{crisis_id}/resolve", response_model=CrisisEventOut)
def resolve_crisis(crisis_id: int, db: Session = Depends(get_db)):
    """Manually mark a crisis event as resolved (admin override)."""
    event = db.get(CrisisEvent, crisis_id)
    if not event:
        raise HTTPException(status_code=404, detail="Crisis event not found")
    event.resolved = True
    db.commit()
    db.refresh(event)
    return event
