"""
app/routers/agents.py
──────────────────────
REST endpoints to manually trigger and inspect the AI agents.

Why manual triggers?
  The background runner fires agents automatically, but for demos,
  testing, and the admin dashboard, you often want to fire them on demand.

Endpoints:
  POST /agents/routing/run       – trigger one Routing Agent pass immediately
  POST /agents/crisis/run/{id}   – trigger Crisis Agent for a specific event
  GET  /agents/status            – get last cached run results from Redis
"""
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.crisis_event import CrisisEvent
from app.agents.routing_agent import run_routing_agent
from app.agents.crisis_agent import run_crisis_agent
from app.agents.runner import get_agent_status_from_cache

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["AI Agents"])


# ── Schemas ───────────────────────────────────────────────────────────────────

from pydantic import BaseModel

class RoutingAgentResponse(BaseModel):
    route_task_ids: list[int]
    message: str
    error: str

class CrisisAgentResponse(BaseModel):
    crisis_event_id: int
    broken_truck_id: int
    cancelled_task_ids: list[int]
    replacement_truck_id: int | None
    reassigned_task_id: int | None
    message: str
    error: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/routing/run", response_model=RoutingAgentResponse)
def trigger_routing_agent():
    """
    Manually trigger one full pass of the Dynamic Routing Agent.

    The agent will:
      1. Fetch bins with capacity ≥ 75%.
      2. Fetch idle trucks.
      3. Compute nearest-neighbour routes.
      4. Create RouteTask records and set trucks to 'en_route'.

    Runs synchronously and returns the final agent state.
    """
    logger.info("[API] Manual trigger: Routing Agent.")
    result = run_routing_agent()
    return RoutingAgentResponse(
        route_task_ids=result.get("route_task_ids", []),
        message=result.get("message", ""),
        error=result.get("error", ""),
    )


@router.post("/crisis/run/{crisis_event_id}", response_model=CrisisAgentResponse)
def trigger_crisis_agent(
    crisis_event_id: int,
    db: Session = Depends(get_db),
):
    """
    Manually trigger the Crisis Management Agent for a specific CrisisEvent ID.

    The agent will:
      1. Mark the broken truck as out_of_service.
      2. Cancel its active/pending route tasks.
      3. Find the nearest idle truck.
      4. Reassign the unfinished waypoints to that truck.
      5. Mark the CrisisEvent as resolved.

    Runs synchronously and returns the final agent state.
    """
    event = db.get(CrisisEvent, crisis_event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Crisis event not found")
    if event.resolved:
        raise HTTPException(status_code=400, detail="Crisis event is already resolved")

    logger.info(
        f"[API] Manual trigger: Crisis Agent for event #{crisis_event_id}, "
        f"truck #{event.truck_id}."
    )
    result = run_crisis_agent(
        crisis_event_id=event.id,
        broken_truck_id=event.truck_id,
    )
    return CrisisAgentResponse(
        crisis_event_id=result.get("crisis_event_id", crisis_event_id),
        broken_truck_id=result.get("broken_truck_id", event.truck_id),
        cancelled_task_ids=result.get("cancelled_task_ids", []),
        replacement_truck_id=result.get("replacement_truck_id"),
        reassigned_task_id=result.get("reassigned_task_id"),
        message=result.get("message", ""),
        error=result.get("error", ""),
    )


@router.get("/status")
def get_agent_status():
    """
    Retrieve the last cached run results for both agents from Redis.
    If Redis is unavailable, returns a degraded response.
    """
    return get_agent_status_from_cache()
