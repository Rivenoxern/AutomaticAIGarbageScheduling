"""
app/agents/state.py
────────────────────
Shared TypedDict state definitions for all LangGraph agents.

LangGraph passes these dictionaries between graph nodes, accumulating
and overwriting fields as the graph executes. Each node receives the
full state and returns a partial dict with only the fields it changed.
"""
from typing import TypedDict


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic Routing Agent State
# ─────────────────────────────────────────────────────────────────────────────
class RoutingAgentState(TypedDict):
    """
    State that flows through the Dynamic Routing Agent graph.

    Fields:
      overflowing_bins  : Bins fetched from DB with capacity >= threshold.
      available_trucks  : Idle trucks available for assignment.
      assignments       : List of {truck_id, waypoints} dicts computed by
                          the route-calculation node.
      route_task_ids    : DB IDs of RouteTasks created in this run.
      message           : Human-readable summary for logging / API response.
      error             : Non-empty string if something went wrong.
    """
    overflowing_bins: list[dict]
    available_trucks: list[dict]
    assignments: list[dict]
    route_task_ids: list[int]
    message: str
    error: str


# ─────────────────────────────────────────────────────────────────────────────
# Crisis Management Agent State
# ─────────────────────────────────────────────────────────────────────────────
class CrisisAgentState(TypedDict):
    """
    State that flows through the Crisis Management Agent graph.

    Fields:
      crisis_event_id       : PK of the CrisisEvent being handled.
      broken_truck_id       : PK of the truck that broke down.
      cancelled_task_ids    : RouteTasks cancelled because of the breakdown.
      waypoints_to_reassign : Merged waypoints extracted from cancelled tasks.
      replacement_truck_id  : PK of the idle truck chosen for reassignment.
      reassigned_task_id    : PK of the new RouteTask created for the
                              replacement truck (None if none were found).
      message               : Human-readable summary.
      error                 : Non-empty string if something went wrong.
    """
    crisis_event_id: int
    broken_truck_id: int
    cancelled_task_ids: list[int]
    waypoints_to_reassign: list[dict]
    replacement_truck_id: int | None
    reassigned_task_id: int | None
    message: str
    error: str
