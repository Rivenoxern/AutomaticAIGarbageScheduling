"""
app/models/__init__.py
───────────────────────
Re-exports all ORM models so Alembic and create_all() can discover them
by importing this single module.
"""
from app.models.admin import Admin          # noqa: F401
from app.models.driver import Driver        # noqa: F401
from app.models.truck import Truck          # noqa: F401
from app.models.trash_bin import TrashBin   # noqa: F401
from app.models.route_task import RouteTask # noqa: F401
from app.models.crisis_event import CrisisEvent  # noqa: F401
