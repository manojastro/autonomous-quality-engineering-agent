"""Injected-regression toggle endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import db_session, tools
from backend.app.schemas import BugStateOut
from backend.app.tools.base import ToolRegistry

router = APIRouter(prefix="/bugs", tags=["bugs"])


@router.post("/payments/{state}", response_model=BugStateOut)
def toggle_payments_bug(state: str, session: Session = Depends(db_session), registry: ToolRegistry = Depends(tools)) -> BugStateOut:
    if state not in ("on", "off"):
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="state must be 'on' or 'off'")
    result = registry.execute(session, "trigger_regression_bug_tool", {"active": state == "on"})
    data = result["data"]
    return BugStateOut(module=data["module"], active=data["active"], state_file=data["state_file"])
