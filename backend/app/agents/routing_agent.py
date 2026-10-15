"""
app/agents/routing_agent.py
────────────────────────────
Dynamic Routing Agent — built with LangGraph.

Responsibility:
  Monitor trash bins. When bins exceed 75% capacity, find idle trucks,
  compute an optimised route (nearest-neighbour on a 2D grid), and
  persist RouteTask records to the database.

LangGraph flow:
  ┌─────────────┐
  │    START    │
  └──────┬──────┘
         ▼
  ┌─────────────────┐
  │  fetch_bins     │  Query DB for overflowing bins
  └──────┬──────────┘
         ▼
  ┌─────────────────────────────────────────────────────┐
  │  check_bins_exist  (conditional edge)               │
  │   • bins found  →  fetch_trucks                     │
  │   • no bins     →  END  (nothing to do)             │
  └──────┬──────────────────────────────────────────────┘
         ▼
  ┌─────────────────┐
  │  fetch_trucks   │  Query DB for idle trucks
  └──────┬──────────┘
         ▼
  ┌─────────────────────────────────────────────────────┐
  │  check_trucks_exist  (conditional edge)             │
  │   • trucks found  →  calculate_routes               │
  │   • no trucks     →  END  (log "no trucks avail")   │
  └──────┬──────────────────────────────────────────────┘
         ▼
  ┌─────────────────────┐
  │  calculate_routes   │  Assign bins to trucks, build waypoints
  └──────┬──────────────┘
         ▼
  ┌─────────────────────┐
  │  persist_tasks      │  Write RouteTasks to DB, update truck status
  └──────┬──────────────┘
         ▼
       END
"""
import logging

from langgraph.graph import StateGraph, START, END
from sqlalchemy.orm import Session

from app.agents.state import RoutingAgentState
from app.agents import tools
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# Node functions
# Each node receives the full state dict and returns a partial update dict.
# ═════════════════════════════════════════════════════════════════════════════

def node_fetch_bins(state: RoutingAgentState) -> dict:
    """Node 1 – Query database for bins at or above the capacity threshold."""
    db: Session = SessionLocal()
    try:
        bins = tools.get_overflowing_bins(db)
        logger.info(f"[RoutingAgent] fetch_bins → found {len(bins)} overflowing bin(s).")
        return {"overflowing_bins": bins, "error": ""}
    except Exception as exc:
        logger.error(f"[RoutingAgent] fetch_bins error: {exc}")
        return {"overflowing_bins": [], "error": str(exc)}
    finally:
        db.close()


def node_fetch_trucks(state: RoutingAgentState) -> dict:
    """Node 2 – Query database for idle trucks."""
    db: Session = SessionLocal()
    try:
        trucks = tools.get_idle_trucks(db)
        logger.info(f"[RoutingAgent] fetch_trucks → {len(trucks)} idle truck(s) available.")
        return {"available_trucks": trucks}
    except Exception as exc:
        logger.error(f"[RoutingAgent] fetch_trucks error: {exc}")
        return {"available_trucks": [], "error": str(exc)}
    finally:
        db.close()


def node_calculate_routes(state: RoutingAgentState) -> dict:
    """
    Node 3 – Distribute overflowing bins across available trucks using the
    nearest-neighbour heuristic. Produces an 'assignments' list.
    """
    assignments = tools.assign_bins_to_trucks(
        trucks=state["available_trucks"],
        bins=state["overflowing_bins"],
    )
    logger.info(f"[RoutingAgent] calculate_routes → {len(assignments)} assignment(s) built.")
    return {"assignments": assignments}


def node_persist_tasks(state: RoutingAgentState) -> dict:
    """Node 4 – Write RouteTask rows to DB and flip trucks to 'en_route'."""
    if not state.get("assignments"):
        return {"route_task_ids": [], "message": "No assignments to persist."}

    db: Session = SessionLocal()
    try:
        task_ids = tools.create_route_tasks(db, state["assignments"])
        msg = (
            f"✅ Routing Agent: Created {len(task_ids)} route task(s). "
            f"Task IDs: {task_ids}"
        )
        logger.info(f"[RoutingAgent] {msg}")
        return {"route_task_ids": task_ids, "message": msg}
    except Exception as exc:
        logger.error(f"[RoutingAgent] persist_tasks error: {exc}")
        return {"route_task_ids": [], "error": str(exc)}
    finally:
        db.close()


# ═════════════════════════════════════════════════════════════════════════════
# Conditional edge functions (routing logic between nodes)
# ═════════════════════════════════════════════════════════════════════════════

def edge_check_bins_exist(state: RoutingAgentState) -> str:
    """Route to 'fetch_trucks' if bins exist, otherwise end the graph."""
    if state.get("error"):
        return END
    return "fetch_trucks" if state.get("overflowing_bins") else END


def edge_check_trucks_exist(state: RoutingAgentState) -> str:
    """Route to 'calculate_routes' if trucks are available, otherwise end."""
    if state.get("error"):
        return END
    if not state.get("available_trucks"):
        logger.warning("[RoutingAgent] No idle trucks available. Skipping route creation.")
        return END
    return "calculate_routes"


# ═════════════════════════════════════════════════════════════════════════════
# Graph construction
# ═════════════════════════════════════════════════════════════════════════════

def build_routing_graph() -> StateGraph:
    """
    Construct and compile the Dynamic Routing Agent LangGraph StateGraph.
    Call once at startup; reuse the compiled graph for every agent run.
    """
    graph = StateGraph(RoutingAgentState)

    # Add nodes
    graph.add_node("fetch_bins",        node_fetch_bins)
    graph.add_node("fetch_trucks",      node_fetch_trucks)
    graph.add_node("calculate_routes",  node_calculate_routes)
    graph.add_node("persist_tasks",     node_persist_tasks)

    # Add edges
    graph.add_edge(START, "fetch_bins")
    graph.add_conditional_edges("fetch_bins",   edge_check_bins_exist)
    graph.add_conditional_edges("fetch_trucks", edge_check_trucks_exist)
    graph.add_edge("calculate_routes", "persist_tasks")
    graph.add_edge("persist_tasks",    END)

    return graph.compile()


# ═════════════════════════════════════════════════════════════════════════════
# Public runner function
# ═════════════════════════════════════════════════════════════════════════════

# Compiled graph singleton — built once, reused across all invocations
_routing_graph = None


def run_routing_agent() -> RoutingAgentState:
    """
    Execute one full pass of the Dynamic Routing Agent.

    Returns the final agent state dict (useful for API responses and logging).
    """
    global _routing_graph
    if _routing_graph is None:
        _routing_graph = build_routing_graph()

    initial_state: RoutingAgentState = {
        "overflowing_bins": [],
        "available_trucks": [],
        "assignments": [],
        "route_task_ids": [],
        "message": "",
        "error": "",
    }

    logger.info("[RoutingAgent] ▶ Starting run.")
    final_state = _routing_graph.invoke(initial_state)
    logger.info(f"[RoutingAgent] ■ Run complete. Message: {final_state.get('message')}")
    return final_state
