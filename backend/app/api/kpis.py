"""KPI and snapshot endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.app.api.deps import db_session
from backend.app.repositories import KpiRepo
from backend.app.services.kpis import compute_all

router = APIRouter(prefix="/kpis", tags=["kpis"])


@router.get("")
def kpis(session: Session = Depends(db_session)) -> dict:
    return compute_all(session)


@router.post("/snapshot")
def snapshot(label: str = Query(default="manual"), session: Session = Depends(db_session)) -> dict:
    payload = compute_all(session)
    row = KpiRepo(session).add_snapshot(label=label, payload_json=payload)
    return {"snapshot_id": row.id, "label": row.label, "kpis": payload}


@router.get("/history")
def history(limit: int = Query(default=20, ge=1, le=100), session: Session = Depends(db_session)) -> list[dict]:
    rows = KpiRepo(session).history(limit=limit)
    return [
        {
            "snapshot_id": row.id,
            "label": row.label,
            "created_at": row.created_at,
            "payload": row.payload_json,
        }
        for row in rows
    ]
