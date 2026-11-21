"""FastAPI application factory and lifespan wiring."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse

from backend.app.api import api_v1_router
from backend.app.config import DATA_DIR, FRONTEND_DIR, get_settings
from backend.app.db import create_all, get_session, modules_seeded, ping
from backend.app.services import metrics
from backend.app.services.seeder import seed


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    from backend.app.db import init_engine

    init_engine(settings.db_url)
    create_all()
    session = get_session()
    try:
        if not modules_seeded(session):
            seed(session)
            session.commit()
    finally:
        session.close()
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Autonomous Quality Engineering Agent", version="1.0.0", lifespan=lifespan)
    app.include_router(api_v1_router)

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "service": "qe-release-confidence-agent"}

    @app.get("/readiness")
    def readiness() -> JSONResponse:
        db_ok = ping()
        session = get_session()
        seeded = False
        try:
            seeded = modules_seeded(session)
        finally:
            session.close()
        ready = db_ok and seeded
        return JSONResponse(status_code=200 if ready else 503, content={"ready": ready, "db": db_ok, "seeded": seeded})

    @app.get("/metrics", response_class=PlainTextResponse)
    def prometheus_metrics() -> str:
        return metrics.render()

    @app.get("/dashboard", response_class=FileResponse)
    def dashboard() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html", media_type="text/html")

    return app


app = create_app()
