"""Test registry inspection endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import db_session
from backend.app.repositories import RegistryRepo
from backend.app.schemas import RegistryTestOut

router = APIRouter(prefix="/tests", tags=["tests"])


@router.get("/registry", response_model=list[RegistryTestOut])
def registry(session: Session = Depends(db_session)) -> list[RegistryTestOut]:
    rows = RegistryRepo(session).all()
    return [
        RegistryTestOut(
            test_id=row.test_id,
            node_id=row.node_id,
            test_type=row.test_type,
            module_mappings=row.module_mappings_json or [],
            avg_runtime_s=row.avg_runtime_s,
            flakiness_score=row.flakiness_score,
            historical_outcomes=row.historical_outcomes_json or [],
            security_relevant=row.security_relevant,
        )
        for row in rows
    ]
