"""
app/agents/tools.py
────────────────────
Pure database helper functions used by agent graph nodes.

Design rules:
  • Every function accepts a SQLAlchemy Session as its first argument.
  • Functions return plain dicts / lists — no ORM objects escape this module.
    This keeps agent nodes decoupled from SQLAlchemy internals.
  • Route math (nearest-neighbour) lives here so it can be unit-tested easily.
"""
import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.truck import Truck, TruckStatus
from app.models.trash_bin import TrashBin
from app.models.route_task import RouteTask, RouteTaskStatus
from app.models.crisis_event import CrisisEvent


# ═════════════════════════════════════════════════════════════════════════════
# Geometry helpers
# ═════════════════════════════════════════════════════════════════════════════

def euclidean_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """
    Simple Euclidean distance on the 2-D lat/lng grid.
    Good enough for the mocked coordinate system; no Haversine needed.
    """
    return math.sqrt((lat1 - lat2) ** 2 + (lng1 - lng2) ** 2)


def parse_gps(location_str: str | None) -> tuple[float, float]:
    """
    Parse a 'lat,lng' string into a (lat, lng) float tuple.
    Returns (0.0, 0.0) if the string is missing or malformed.
    """
    if not location_str:
        return (0.0, 0.0)
    try:
        lat, lng = location_str.split(",")
        return (float(lat.strip()), float(lng.strip()))
    except ValueError:
        return (0.0, 0.0)


def nearest_neighbour_route(
    start_lat: float,
    start_lng: float,
    bins: list[dict],
) -> list[dict]:
    """
    Greedy nearest-neighbour algorithm: starting from the truck's current
    position, repeatedly visit the closest unvisited bin.

    Args:
      start_lat / start_lng : Truck's current position.
      bins                  : List of bin dicts (must have 'latitude', 'longitude').

    Returns:
      Ordered list of bin dicts representing the visit sequence.
    """
    unvisited = list(bins)
    route: list[dict] = []
    cur_lat, cur_lng = start_lat, start_lng

    while unvisited:
        nearest = min(
            unvisited,
            key=lambda b: euclidean_distance(cur_lat, cur_lng, b["latitude"], b["longitude"]),
        )
        route.append(nearest)
        cur_lat, cur_lng = nearest["latitude"], nearest["longitude"]
        unvisited.remove(nearest)

    return route


# ═════════════════════════════════════════════════════════════════════════════
# Routing Agent DB helpers
# ═════════════════════════════════════════════════════════════════════════════

CAPACITY_THRESHOLD = 75.0   # %  — bins at or above this level need collection
MAX_BINS_PER_TRUCK = 5      # route task waypoint cap per truck


def get_overflowing_bins(db: Session, threshold: float = CAPACITY_THRESHOLD) -> list[dict]:
    """
    Fetch bins whose current_capacity_pct >= threshold.
    Returns list of plain dicts safe to put in agent state.
    """
    rows = (
        db.query(TrashBin)
        .filter(TrashBin.current_capacity_pct >= threshold)
        .order_by(TrashBin.current_capacity_pct.desc())
        .all()
    )
    return [
        {
            "id": b.id,
            "location_name": b.location_name,
            "latitude": b.latitude,
            "longitude": b.longitude,
            "current_capacity_pct": b.current_capacity_pct,
        }
        for b in rows
    ]


def get_idle_trucks(db: Session) -> list[dict]:
    """Fetch all trucks with status == 'idle'."""
    rows = db.query(Truck).filter(Truck.status == TruckStatus.idle).all()
    return [
        {
            "id": t.id,
            "plate_number": t.plate_number,
            "current_gps_location": t.current_gps_location,
        }
        for t in rows
    ]


def assign_bins_to_trucks(
    trucks: list[dict],
    bins: list[dict],
) -> list[dict]:
    """
    Distribute overflowing bins across available trucks.

    Strategy (simple & explainable for a college project):
      1. Sort bins by capacity descending (highest priority first).
      2. Round-robin assign bins to trucks in batches of MAX_BINS_PER_TRUCK.
      3. For each truck, order its assigned bins using nearest-neighbour
         starting from the truck's current GPS location.

    Returns a list of assignment dicts:
      {truck_id, plate_number, waypoints: [{bin_id, location_name, lat, lng, capacity_pct}]}
    """
    if not trucks or not bins:
        return []

    # Sort bins: highest capacity first (most urgent)
    sorted_bins = sorted(bins, key=lambda b: b["current_capacity_pct"], reverse=True)

    # Partition into chunks
    chunks: list[list[dict]] = []
    for i in range(0, len(sorted_bins), MAX_BINS_PER_TRUCK):
        chunks.append(sorted_bins[i : i + MAX_BINS_PER_TRUCK])

    assignments: list[dict] = []
    for idx, chunk in enumerate(chunks):
        if idx >= len(trucks):
            break  # no more trucks available

        truck = trucks[idx]
        t_lat, t_lng = parse_gps(truck["current_gps_location"])
        ordered_bins = nearest_neighbour_route(t_lat, t_lng, chunk)

        waypoints = [
            {
                "bin_id": b["id"],
                "location_name": b["location_name"],
                "latitude": b["latitude"],
                "longitude": b["longitude"],
                "capacity_pct": b["current_capacity_pct"],
            }
            for b in ordered_bins
        ]

        assignments.append(
            {
                "truck_id": truck["id"],
                "plate_number": truck["plate_number"],
                "waypoints": waypoints,
            }
        )

    return assignments


def create_route_tasks(db: Session, assignments: list[dict]) -> list[int]:
    """
    Persist RouteTask rows and flip assigned trucks to 'en_route'.
    Returns list of created RouteTask IDs.
    """
    task_ids: list[int] = []

    for assignment in assignments:
        truck = db.get(Truck, assignment["truck_id"])
        if truck is None or truck.status != TruckStatus.idle:
            continue  # truck was grabbed by another agent run in between

        task = RouteTask(
            truck_id=assignment["truck_id"],
            waypoints=assignment["waypoints"],
            status=RouteTaskStatus.active,
            assigned_at=datetime.now(timezone.utc),
        )
        db.add(task)
        truck.status = TruckStatus.en_route

    db.commit()

    # Refresh to get IDs (flush already happened inside commit)
    tasks = (
        db.query(RouteTask)
        .filter(RouteTask.status == RouteTaskStatus.active)
        .order_by(RouteTask.id.desc())
        .limit(len(assignments))
        .all()
    )
    task_ids = [t.id for t in tasks]
    return task_ids


# ═════════════════════════════════════════════════════════════════════════════
# Crisis Agent DB helpers
# ═════════════════════════════════════════════════════════════════════════════

def get_unresolved_crises(db: Session) -> list[dict]:
    """Return all unresolved crisis events."""
    rows = db.query(CrisisEvent).filter(CrisisEvent.resolved == False).all()  # noqa: E712
    return [
        {
            "id": c.id,
            "truck_id": c.truck_id,
            "issue_type": c.issue_type,
            "reported_at": c.reported_at.isoformat(),
        }
        for c in rows
    ]


def mark_truck_out_of_service(db: Session, truck_id: int) -> None:
    """Set truck status to out_of_service."""
    truck = db.get(Truck, truck_id)
    if truck:
        truck.status = TruckStatus.out_of_service
        db.commit()


def cancel_truck_tasks(db: Session, truck_id: int) -> tuple[list[int], list[dict]]:
    """
    Cancel all pending/active RouteTasks for a broken truck.

    Returns:
      cancelled_ids     : list of cancelled RouteTask IDs
      merged_waypoints  : deduplicated waypoints across all cancelled tasks
    """
    tasks = (
        db.query(RouteTask)
        .filter(
            RouteTask.truck_id == truck_id,
            RouteTask.status.in_([RouteTaskStatus.pending, RouteTaskStatus.active]),
        )
        .all()
    )

    cancelled_ids: list[int] = []
    seen_bin_ids: set[int] = set()
    merged_waypoints: list[dict] = []

    for task in tasks:
        task.status = RouteTaskStatus.cancelled
        cancelled_ids.append(task.id)
        for wp in (task.waypoints or []):
            bid = wp.get("bin_id")
            if bid and bid not in seen_bin_ids:
                seen_bin_ids.add(bid)
                merged_waypoints.append(wp)

    db.commit()
    return cancelled_ids, merged_waypoints


def find_nearest_idle_truck(
    db: Session,
    broken_truck_id: int,
    reference_lat: float,
    reference_lng: float,
) -> dict | None:
    """
    Find the closest idle truck to a reference position,
    excluding the broken truck itself.
    """
    idle_trucks = (
        db.query(Truck)
        .filter(
            Truck.status == TruckStatus.idle,
            Truck.id != broken_truck_id,
        )
        .all()
    )

    if not idle_trucks:
        return None

    def truck_distance(t: Truck) -> float:
        t_lat, t_lng = parse_gps(t.current_gps_location)
        return euclidean_distance(reference_lat, reference_lng, t_lat, t_lng)

    nearest = min(idle_trucks, key=truck_distance)
    return {
        "id": nearest.id,
        "plate_number": nearest.plate_number,
        "current_gps_location": nearest.current_gps_location,
    }


def reassign_waypoints_to_truck(
    db: Session,
    truck_id: int,
    waypoints: list[dict],
) -> int | None:
    """
    Create a new RouteTask for the replacement truck and set it to 'en_route'.
    Returns the new RouteTask ID, or None if truck not found/available.
    """
    truck = db.get(Truck, truck_id)
    if not truck or truck.status != TruckStatus.idle:
        return None

    # Re-order waypoints using nearest-neighbour from replacement truck's position
    t_lat, t_lng = parse_gps(truck.current_gps_location)
    ordered_waypoints = nearest_neighbour_route(t_lat, t_lng, [
        {**wp, "latitude": wp.get("latitude", 0), "longitude": wp.get("longitude", 0)}
        for wp in waypoints
    ])

    task = RouteTask(
        truck_id=truck_id,
        waypoints=ordered_waypoints,
        status=RouteTaskStatus.active,
        assigned_at=datetime.now(timezone.utc),
    )
    db.add(task)
    truck.status = TruckStatus.en_route
    db.commit()
    db.refresh(task)
    return task.id


def resolve_crisis_event(db: Session, crisis_event_id: int) -> None:
    """Mark the given crisis event as resolved."""
    event = db.get(CrisisEvent, crisis_event_id)
    if event:
        event.resolved = True
        db.commit()
