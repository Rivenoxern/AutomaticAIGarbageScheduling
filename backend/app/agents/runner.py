"""
app/agents/runner.py
─────────────────────
Background agent runner using a daemon thread.

What it does:
  • Every ROUTING_INTERVAL seconds, fires the Dynamic Routing Agent.
  • Every CRISIS_POLL_INTERVAL seconds, polls for unresolved CrisisEvents
    and fires the Crisis Management Agent for each one.
  • Caches the last result of each agent run in Redis (if available) so
    the API can expose agent status without touching the DB.

Usage (called from main.py lifespan):
    from app.agents.runner import start_agent_runner
    start_agent_runner()
"""
import json
import logging
import threading
import time
from datetime import datetime, timezone

import redis as redis_lib

from app.agents.routing_agent import run_routing_agent
from app.agents.crisis_agent import run_crisis_agent
from app.agents.tools import get_unresolved_crises
from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

# ── Tunable intervals (seconds) ───────────────────────────────────────────────
ROUTING_INTERVAL    = 30   # how often to check for overflowing bins
CRISIS_POLL_INTERVAL = 10  # how often to check for unresolved crises

# ── Redis keys ────────────────────────────────────────────────────────────────
REDIS_KEY_ROUTING_STATUS = "wasteway:agent:routing:last_run"
REDIS_KEY_CRISIS_STATUS  = "wasteway:agent:crisis:last_run"
REDIS_RESULT_TTL         = 300  # seconds (5 min)


def _get_redis() -> redis_lib.Redis | None:
    """Return a Redis client, or None if Redis is unreachable."""
    try:
        client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)
        client.ping()
        return client
    except Exception:
        logger.warning("[Runner] Redis unavailable – running without cache.")
        return None


def _cache_result(redis_client, key: str, data: dict) -> None:
    """Serialize and store a result dict in Redis with TTL."""
    if redis_client is None:
        return
    try:
        payload = json.dumps(data, default=str)
        redis_client.set(key, payload, ex=REDIS_RESULT_TTL)
    except Exception as exc:
        logger.warning(f"[Runner] Redis write failed: {exc}")


def _routing_loop(redis_client) -> None:
    """Daemon loop: fires the Routing Agent every ROUTING_INTERVAL seconds."""
    logger.info(f"[Runner] Routing Agent loop started (interval={ROUTING_INTERVAL}s).")
    while True:
        try:
            result = run_routing_agent()
            _cache_result(
                redis_client,
                REDIS_KEY_ROUTING_STATUS,
                {
                    "ran_at": datetime.now(timezone.utc).isoformat(),
                    "route_task_ids": result.get("route_task_ids", []),
                    "message": result.get("message", ""),
                    "error": result.get("error", ""),
                },
            )
        except Exception as exc:
            logger.error(f"[Runner] Routing Agent run error: {exc}")

        time.sleep(ROUTING_INTERVAL)


def _crisis_loop(redis_client) -> None:
    """Daemon loop: polls for unresolved crises and dispatches Crisis Agent."""
    logger.info(f"[Runner] Crisis Agent loop started (poll={CRISIS_POLL_INTERVAL}s).")
    while True:
        try:
            db = SessionLocal()
            try:
                crises = get_unresolved_crises(db)
            finally:
                db.close()

            for crisis in crises:
                logger.info(
                    f"[Runner] Dispatching CrisisAgent for event "
                    f"#{crisis['id']} (truck #{crisis['truck_id']})."
                )
                result = run_crisis_agent(
                    crisis_event_id=crisis["id"],
                    broken_truck_id=crisis["truck_id"],
                )
                _cache_result(
                    redis_client,
                    f"{REDIS_KEY_CRISIS_STATUS}:{crisis['id']}",
                    {
                        "ran_at": datetime.now(timezone.utc).isoformat(),
                        "crisis_event_id": crisis["id"],
                        "broken_truck_id": crisis["truck_id"],
                        "reassigned_task_id": result.get("reassigned_task_id"),
                        "message": result.get("message", ""),
                        "error": result.get("error", ""),
                    },
                )
        except Exception as exc:
            logger.error(f"[Runner] Crisis Agent loop error: {exc}")

        time.sleep(CRISIS_POLL_INTERVAL)


def start_agent_runner() -> None:
    """
    Spawn background daemon threads for both agent loops.
    Called once from main.py lifespan startup.
    Daemon threads automatically die when the main process exits.
    """
    redis_client = _get_redis()

    routing_thread = threading.Thread(
        target=_routing_loop,
        args=(redis_client,),
        daemon=True,
        name="RoutingAgentLoop",
    )
    crisis_thread = threading.Thread(
        target=_crisis_loop,
        args=(redis_client,),
        daemon=True,
        name="CrisisAgentLoop",
    )

    routing_thread.start()
    crisis_thread.start()

    logger.info("✅  Agent runner threads started (Routing + Crisis).")


def get_agent_status_from_cache() -> dict:
    """
    Read the last agent run results from Redis.
    Returns a dict suitable for the /api/v1/agents/status endpoint.
    """
    redis_client = _get_redis()
    if redis_client is None:
        return {"redis": "unavailable", "routing": None, "crisis_events": []}

    routing_raw = redis_client.get(REDIS_KEY_ROUTING_STATUS)
    routing_data = json.loads(routing_raw) if routing_raw else None

    # Collect all crisis keys
    crisis_keys = redis_client.keys(f"{REDIS_KEY_CRISIS_STATUS}:*")
    crisis_data = []
    for key in crisis_keys:
        raw = redis_client.get(key)
        if raw:
            crisis_data.append(json.loads(raw))

    return {
        "redis": "connected",
        "routing": routing_data,
        "crisis_events": crisis_data,
    }
