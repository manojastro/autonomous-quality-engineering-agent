"""Quality-gate override endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.api.deps import db_session
from backend.app.repositories import GatesRepo
from backend.app.schemas import OverrideRequest
from backend.app.services.metrics import incr_labeled
from backend.app.services.workflow import ApprovalService, WorkflowError

router = APIRouter(prefix="/gates", tags=["gates"])


@router.post("/{gate_id}/override")
def override_gate(gate_id: int, request: OverrideRequest, session: Session = Depends(db_session)) -> dict:
    GatesRepo(session).require(gate_id)
    try:
        result = ApprovalService(session).override_gate(
            gate_id=gate_id,
            action=request.action,
            approver=request.approver,
            justification=request.justification,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    incr_labeled("qe_overrides_total", request.action)
    return result


@router.get("/{gate_id}")
def get_gate(gate_id: int, session: Session = Depends(db_session)) -> dict:
    row = GatesRepo(session).get(gate_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"gate {gate_id} not found")
    return {
        "gate_id": row.id,
        "change_id": row.change_id,
        "decision": row.decision,
        "score": row.score,
        "reasons": row.reasons_json,
        "override_status": row.override_status,
    }
