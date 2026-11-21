"""FastAPI routers for the v1 API."""
from fastapi import APIRouter

from backend.app.api import bugs, changes, gates, kpis, tests

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(changes.router)
api_v1_router.include_router(bugs.router)
api_v1_router.include_router(gates.router)
api_v1_router.include_router(tests.router)
api_v1_router.include_router(kpis.router)

__all__ = ["api_v1_router"]
