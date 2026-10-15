"""
main.py  –  WasteWay FastAPI Application Entry Point
──────────────────────────────────────────────────────
Starts the API server, initialises the database tables on first run,
mounts all routers, and starts the background AI agent runner threads.

Run with:
    uvicorn main:app --reload --port 8000
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine

# Import models so SQLAlchemy registers them before create_all()
import app.models  # noqa: F401

from app.routers import trucks, trash_bins, route_tasks, crisis_events, agents
from app.agents.runner import start_agent_runner

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
      1. Create / verify all DB tables.
      2. Start background agent runner threads (Routing + Crisis).
    """
    Base.metadata.create_all(bind=engine)
    logger.info("✅  Database tables verified / created.")

    start_agent_runner()
    logger.info("✅  Background agent runner started.")

    yield
    # (graceful shutdown logic can go here in future phases)


# ── App factory ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="WasteWay API",
    description=(
        "Agentic AI backend for dynamic garbage truck scheduling.\n\n"
        "**Phase 2**: Dynamic Routing Agent + Crisis Management Agent (LangGraph)."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(trucks.router,        prefix="/api/v1")
app.include_router(trash_bins.router,    prefix="/api/v1")
app.include_router(route_tasks.router,   prefix="/api/v1")
app.include_router(crisis_events.router, prefix="/api/v1")
app.include_router(agents.router,        prefix="/api/v1")


# ── Health check ──────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "version": "0.2.0", "env": settings.APP_ENV}
