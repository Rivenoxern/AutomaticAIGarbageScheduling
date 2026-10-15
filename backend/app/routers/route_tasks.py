"""
app/routers/route_tasks.py
───────────────────────────
CRUD endpoints for RouteTask management.

Endpoints:
  GET    /tasks/              – list all tasks (filterable by status)
  GET    /tasks/{id}          – get task by ID (includes waypoints JSON)
  PATCH  /tasks/{id}/status   – update task status (e.g., mark completed)
  DELETE /tasks/{id}          – remove a task
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session
from datetime import datetime

from app.core.database import get_db
from app.models.route_task import RouteTask, RouteTaskStatus

router = APIRouter(prefix="/tasks", tags=["Route Tasks"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class RouteTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    truck_id: int
    waypoints: list[dict]
    status: RouteTaskStatus
    assigned_at: datetime


class RouteTaskStatusUpdate(BaseModel):
    status: RouteTaskStatus


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[RouteTaskOut])
def list_tasks(
    task_status: RouteTaskStatus | None = Query(default=None, alias="status"),
    truck_id: int | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """
    List route tasks. Optional filters:
      ?status=active   – only active tasks
      ?truck_id=1      – only tasks for truck #1
    """
    q = db.query(RouteTask)
    if task_status:
        q = q.filter(RouteTask.status == task_status)
    if truck_id:
        q = q.filter(RouteTask.truck_id == truck_id)
    return q.order_by(RouteTask.assigned_at.desc()).offset(skip).limit(limit).all()


@router.get("/{task_id}", response_model=RouteTaskOut)
def get_task(task_id: int, db: Session = Depends(get_db)):
    """Fetch a single route task by ID, including its full waypoints JSON."""
    task = db.get(RouteTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Route task not found")
    return task


@router.patch("/{task_id}/status", response_model=RouteTaskOut)
def update_task_status(
    task_id: int,
    payload: RouteTaskStatusUpdate,
    db: Session = Depends(get_db),
):
    """
    Update a task's status (e.g., driver marks it 'completed').
    When a task is marked 'completed', the truck's status is flipped
    back to 'idle' automatically.
    """
    task = db.get(RouteTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Route task not found")

    task.status = payload.status

    # Auto-reset truck to idle when task is finished
    if payload.status in (RouteTaskStatus.completed, RouteTaskStatus.cancelled):
        from app.models.truck import Truck, TruckStatus
        truck = db.get(Truck, task.truck_id)
        if truck:
            truck.status = TruckStatus.idle

    db.commit()
    db.refresh(task)
    return task


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    """Remove a route task record."""
    task = db.get(RouteTask, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Route task not found")
    db.delete(task)
    db.commit()
