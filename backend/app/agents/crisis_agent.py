"""
app/agents/crisis_agent.py
───────────────────────────
Crisis Management Agent — built with LangGraph.

Responsibility:
  When a truck reports a breakdown ("Fatal constraint"), this agent:
    1. Marks the truck as 'out_of_service'.
    2. Cancels all pending/active route tasks for that truck.
    3. Extracts the unfinished waypoints from those cancelled tasks.
    4. Finds the nearest idle truck (Euclidean distance on the 2D grid).
    5. Creates a new RouteTask for the replacement truck.
    6. Marks the CrisisEvent as resolved.

LangGraph flow:
  ┌─────────────┐
  │    START    │
  └──────┬──────┘
         ▼
  ┌─────────────────────┐
  │  mark_out_of_service│  Set broken truck status = out_of_service
  └──────┬──────────────┘
         ▼
  ┌─────────────────────┐
  │  cancel_tasks       │  Cancel pending/active tasks, collect waypoints
  └──────┬──────────────┘
         ▼
  ┌─────────────────────────────────────────────────────────┐
  │  check_waypoints  (conditional edge)                    │
  │   • waypoints exist  →  find_replacement_truck          │
  │   • no waypoints     →  resolve_crisis  (nothing to do) │
  └──────┬──────────────────────────────────────────────────┘
         ▼
  ┌──────────────────────────┐
  │  find_replacement_truck  │  Nearest idle truck to broken truck's location
  └──────┬───────────────────┘
         ▼
  ┌─────────────────────────────────────────────────────────┐
  │  check_replacement  (conditional edge)                  │
  │   • truck found    →  reassign_tasks                    │
  │   • none available →  resolve_crisis (with warning)     │
  └──────┬──────────────────────────────────────────────────┘
         ▼
  ┌─────────────────────┐
  │  reassign_tasks     │  Create new RouteTask for replacement truck
  └──────┬──────────────┘
         ▼
  ┌─────────────────────┐
  │  resolve_crisis     │  Mark CrisisEvent.resolved = True
  └──────┬──────────────┘
         ▼
       END
"""
import logging

from langgraph.graph import StateGraph, START, END
from sqlalchemy.orm import Session

from app.agents.state import CrisisAgentState
from app.agents import tools
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Node functions
# ═════════════════════════════════════════════════════════════════════════════

def node_mark_out_of_service(state: CrisisAgentState) -> dict:
    """Node 1 – Mark the broken truck as out_of_service in the DB."""
    truck_id = state["broken_truck_id"]
    db: Session = SessionLocal()
    try:
        tools.mark_truck_out_of_service(db, truck_id)
        logger.info(f"[CrisisAgent] Truck {truck_id} marked out_of_service.")
        return {"error": ""}
    except Exception as exc:
        logger.error(f"[CrisisAgent] mark_out_of_service error: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


def node_cancel_tasks(state: CrisisAgentState) -> dict:
    """
    Node 2 – Cancel all pending/active RouteTasks for the broken truck
    and collect their unfinished waypoints for reassignment.
    """
    truck_id = state["broken_truck_id"]
    db: Session = SessionLocal()
    try:
        cancelled_ids, waypoints = tools.cancel_truck_tasks(db, truck_id)
        logger.info(
            f"[CrisisAgent] Cancelled {len(cancelled_ids)} task(s). "
            f"Collected {len(waypoints)} unfinished waypoint(s)."
        )
        return {
            "cancelled_task_ids": cancelled_ids,
            "waypoints_to_reassign": waypoints,
        }
    except Exception as exc:
        logger.error(f"[CrisisAgent] cancel_tasks error: {exc}")
        return {"cancelled_task_ids": [], "waypoints_to_reassign": [], "error": str(exc)}
    finally:
        db.close()


def node_find_replacement_truck(state: CrisisAgentState) -> dict:
    """
    Node 3 – Find the nearest idle truck to the broken truck's last
    known GPS location.
    """
    truck_id = state["broken_truck_id"]
    db: Session = SessionLocal()
    try:
        # Use the broken truck's GPS as the reference point for distance calc
        from app.models.truck import Truck
        broken_truck = db.get(Truck, truck_id)
        ref_lat, ref_lng = tools.parse_gps(
            broken_truck.current_gps_location if broken_truck else None
        )

        replacement = tools.find_nearest_idle_truck(db, truck_id, ref_lat, ref_lng)

        if replacement:
            logger.info(
                f"[CrisisAgent] Nearest idle truck: ID={replacement['id']} "
                f"({replacement['plate_number']})"
            )
        else:
            logger.warning("[CrisisAgent] No idle trucks found for reassignment.")

        return {"replacement_truck_id": replacement["id"] if replacement else None}
    except Exception as exc:
        logger.error(f"[CrisisAgent] find_replacement_truck error: {exc}")
        return {"replacement_truck_id": None, "error": str(exc)}
    finally:
        db.close()


def node_reassign_tasks(state: CrisisAgentState) -> dict:
    """
    Node 4 – Create a new RouteTask for the replacement truck containing
    all the unfinished waypoints from the cancelled tasks.
    """
    replacement_id = state["replacement_truck_id"]
    waypoints = state["waypoints_to_reassign"]
    db: Session = SessionLocal()
    try:
        new_task_id = tools.reassign_waypoints_to_truck(db, replacement_id, waypoints)
        logger.info(
            f"[CrisisAgent] Reassigned {len(waypoints)} waypoint(s) → "
            f"Truck {replacement_id} → RouteTask ID={new_task_id}."
        )
        return {"reassigned_task_id": new_task_id}
    except Exception as exc:
        logger.error(f"[CrisisAgent] reassign_tasks error: {exc}")
        return {"reassigned_task_id": None, "error": str(exc)}
    finally:
        db.close()


def node_resolve_crisis(state: CrisisAgentState) -> dict:
    """Node 5 – Mark the CrisisEvent as resolved and compose the summary message."""
    db: Session = SessionLocal()
    try:
        tools.resolve_crisis_event(db, state["crisis_event_id"])

        if state.get("reassigned_task_id"):
            msg = (
                f"✅ Crisis resolved. Truck {state['broken_truck_id']} is out_of_service. "
                f"{len(state.get('cancelled_task_ids', []))} task(s) cancelled. "
                f"Replacement truck {state['replacement_truck_id']} assigned "
                f"RouteTask #{state['reassigned_task_id']}."
            )
        elif state.get("waypoints_to_reassign"):
            msg = (
                f"⚠️ Crisis partially resolved. Truck {state['broken_truck_id']} is "
                f"out_of_service. {len(state.get('cancelled_task_ids', []))} task(s) "
                f"cancelled but NO idle truck available for reassignment."
            )
        else:
            msg = (
                f"✅ Crisis resolved. Truck {state['broken_truck_id']} is out_of_service. "
                f"No active tasks needed reassignment."
            )

        logger.info(f"[CrisisAgent] {msg}")
        return {"message": msg}
    except Exception as exc:
        logger.error(f"[CrisisAgent] resolve_crisis error: {exc}")
        return {"message": "", "error": str(exc)}
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════════
# Conditional edge functions
# ═════════════════════════════════════════════════════════════════════════════

def edge_check_waypoints(state: CrisisAgentState) -> str:
    """If there are unfinished waypoints, look for a replacement truck."""
    if state.get("error"):
        return "resolve_crisis"
    return "find_replacement_truck" if state.get("waypoints_to_reassign") else "resolve_crisis"


def edge_check_replacement(state: CrisisAgentState) -> str:
    """If a replacement truck was found, reassign; otherwise skip to resolve."""
    if state.get("error"):
        return "resolve_crisis"
    return "reassign_tasks" if state.get("replacement_truck_id") else "resolve_crisis"


# ═════════════════════════════════════════════════════════════════════════════
# Graph construction
# ═════════════════════════════════════════════════════════════════════════════

def build_crisis_graph() -> StateGraph:
    """
    Construct and compile the Crisis Management Agent LangGraph StateGraph.
    """
    graph = StateGraph(CrisisAgentState)

    # Add nodes
    graph.add_node("mark_out_of_service",     node_mark_out_of_service)
    graph.add_node("cancel_tasks",            node_cancel_tasks)
    graph.add_node("find_replacement_truck",  node_find_replacement_truck)
    graph.add_node("reassign_tasks",          node_reassign_tasks)
    graph.add_node("resolve_crisis",          node_resolve_crisis)

    # Add edges
    graph.add_edge(START, "mark_out_of_service")
    graph.add_edge("mark_out_of_service", "cancel_tasks")
    graph.add_conditional_edges("cancel_tasks", edge_check_waypoints)
    graph.add_conditional_edges("find_replacement_truck", edge_check_replacement)
    graph.add_edge("reassign_tasks",    "resolve_crisis")
    graph.add_edge("resolve_crisis",    END)

    return graph.compile()


# ═════════════════════════════════════════════════════════════════════════════
# Public runner function
# ═════════════════════════════════════════════════════════════════════════════

_crisis_graph = None


def run_crisis_agent(
    crisis_event_id: int,
    broken_truck_id: int,
) -> CrisisAgentState:
    """
    Execute one full pass of the Crisis Management Agent for a specific event.

    Args:
      crisis_event_id : PK of the CrisisEvent row to handle.
      broken_truck_id : PK of the truck that broke down.

    Returns the final agent state dict.
    """
    global _crisis_graph
    if _crisis_graph is None:
        _crisis_graph = build_crisis_graph()

    initial_state: CrisisAgentState = {
        "crisis_event_id": crisis_event_id,
        "broken_truck_id": broken_truck_id,
        "cancelled_task_ids": [],
        "waypoints_to_reassign": [],
        "replacement_truck_id": None,
        "reassigned_task_id": None,
        "message": "",
        "error": "",
    }

    logger.info(
        f"[CrisisAgent] ▶ Starting run for CrisisEvent #{crisis_event_id}, "
        f"Truck #{broken_truck_id}."
    )
    final_state = _crisis_graph.invoke(initial_state)
    logger.info(f"[CrisisAgent] ■ Run complete. Message: {final_state.get('message')}")
    return final_state
