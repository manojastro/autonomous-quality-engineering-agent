"""Change submission, analysis pipeline and artifact retrieval."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.agents.pipeline import AnalysisPipeline
from backend.app.api.deps import db_session
from backend.app.repositories import (
    ChangesRepo,
    ConfidenceRepo,
    ExecutionsRepo,
    FailuresRepo,
    FlakyRepo,
    GatesRepo,
    ImpactsRepo,
    RcaRepo,
    SelectionsRepo,
    WorkflowRepo,
)
from backend.app.schemas import AnalyzeSummary, ChangeCreated, ChangeManifest
from backend.app.services import metrics
from backend.app.services.workflow import ApprovalService, WorkflowError

router = APIRouter(prefix="/changes", tags=["changes"])


@router.post("", response_model=ChangeCreated, status_code=201)
def submit_change(manifest: ChangeManifest, session: Session = Depends(db_session)) -> ChangeCreated:
    repo = ChangesRepo(session)
    change = repo.create(
        title=manifest.title or f"change-{len(manifest.files)}-file(s)",
        manifest_json={"files": [f.model_dump() for f in manifest.files], **manifest.metadata_json},
        lines_added=manifest.total_added,
        lines_deleted=manifest.total_deleted,
    )
    WorkflowRepo(session).create(change.id)
    session.flush()
    metrics.incr("qe_changes_submitted_total")
    return ChangeCreated(
        id=change.id,
        title=change.title,
        lines_added=change.lines_added,
        lines_deleted=change.lines_deleted,
        workflow_state="PROPOSED",
        created_at=change.created_at,
    )


@router.post("/{change_id}/analyze", response_model=AnalyzeSummary)
def analyze_change(change_id: int, session: Session = Depends(db_session)) -> AnalyzeSummary:
    try:
        summary: dict[str, Any] = AnalysisPipeline(session).run(change_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (WorkflowError, RuntimeError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    gate = summary.get("gate", {})
    return AnalyzeSummary(
        change_id=change_id,
        impacted_modules=summary["selection"]["impacted_modules"],
        selected_count=summary["selection"]["selected_count"],
        total_tests=summary["selection"]["total_tests"],
        reduction_pct=summary["selection"]["reduction_pct"],
        executed_total=summary["execution"]["total"],
        executed_passed=summary["execution"]["passed"],
        executed_failed=summary["execution"]["failed"],
        failures=summary["rca_count"],
        confidence=summary["confidence"]["score"],
        decision=gate.get("decision", "review"),
        workflow_state=summary["workflow_state"],
    )


@router.get("")
def list_changes(session: Session = Depends(db_session)) -> list[dict]:
    svc = ApprovalService(session)
    rows = []
    for change in ChangesRepo(session).list():
        try:
            state = svc.state_of(change.id)
        except LookupError:
            state = "UNKNOWN"
        rows.append(
            {
                "id": change.id,
                "title": change.title,
                "status": change.status,
                "lines_added": change.lines_added,
                "lines_deleted": change.lines_deleted,
                "workflow_state": state,
                "created_at": change.created_at,
            }
        )
    return rows


@router.get("/{change_id}/impact")
def get_impact(change_id: int, session: Session = Depends(db_session)) -> dict:
    row = ImpactsRepo(session).latest(change_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no impact analysis for change {change_id}")
    return {"change_id": change_id, **row.payload_json}


@router.get("/{change_id}/selection")
def get_selection(change_id: int, session: Session = Depends(db_session)) -> dict:
    row = SelectionsRepo(session).latest(change_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no selection for change {change_id}")
    payload = dict(row.payload_json)
    return {
        "change_id": change_id,
        "selection_id": row.id,
        "strategy": row.strategy,
        "total_tests": row.total_tests,
        "selected_count": row.selected_count,
        "reduction_pct": row.reduction_pct,
        **payload,
    }


@router.get("/{change_id}/execution")
def get_execution(change_id: int, session: Session = Depends(db_session)) -> dict:
    execution = ExecutionsRepo(session).latest(change_id)
    if execution is None:
        raise HTTPException(status_code=404, detail=f"no execution for change {change_id}")
    results = [
        {
            "test_id": r.test_id,
            "node_id": r.node_id,
            "outcome": r.outcome,
            "duration_s": r.duration_s,
            "attempts": r.attempts,
            "retried_flag": r.retried_flag,
        }
        for r in ExecutionsRepo(session).results(execution.id)
    ]
    return {
        "change_id": change_id,
        "execution_id": execution.id,
        "status": execution.status,
        "total": execution.total,
        "passed": execution.passed,
        "failed": execution.failed,
        "retried": execution.retried,
        "duration_s": execution.duration_s,
        "results": results,
    }


@router.get("/{change_id}/failures")
def get_failures(change_id: int, session: Session = Depends(db_session)) -> dict:
    rows = FailuresRepo(session).for_change(change_id)
    rca_by_id = {row.id: row for row in RcaRepo(session).for_change(change_id)}
    flaky_by_node = {report.test_id: report.classification for report in FlakyRepo(session).for_change(change_id)}
    failures = []
    for row in rows:
        rca_record = next((r for r in rca_by_id.values() if r.payload_json.get("incident_id") == _incident_for(row)), None)
        rca_payload = rca_record.payload_json if rca_record else None
        failures.append(
            {
                "test_id": row.test_id,
                "node_id": row.node_id,
                "stack_trace": row.stack_trace,
                "log_excerpt": row.log_excerpt,
                "diff_ref": row.diff_ref,
                "related_history": row.related_history_json,
                "rca": rca_payload,
                "flaky_classification": flaky_by_node.get(row.test_id),
            }
        )
    return {"change_id": change_id, "failure_count": len(failures), "failures": failures}


def _incident_for(row) -> str:
    return f"INC-C{row.change_id}-E{row.execution_id}-{row.test_id}"


@router.get("/{change_id}/flaky")
def get_flaky(change_id: int, session: Session = Depends(db_session)) -> dict:
    reports = FlakyRepo(session).for_change(change_id)
    return {
        "change_id": change_id,
        "entries": [
            {
                "test_id": r.test_id,
                "classification": r.classification,
                "confidence": r.confidence,
                "signals": r.signals_json,
            }
            for r in reports
        ],
    }


@router.get("/{change_id}/confidence")
def get_confidence(change_id: int, session: Session = Depends(db_session)) -> dict:
    row = ConfidenceRepo(session).latest(change_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no confidence score for change {change_id}")
    from backend.app.config import CONFIDENCE_WEIGHTS

    return {
        "change_id": change_id,
        "score": row.score,
        "breakdown": row.breakdown_json,
        "weights": CONFIDENCE_WEIGHTS,
        "created_at": row.created_at,
    }


@router.get("/{change_id}/gate")
def get_gate(change_id: int, session: Session = Depends(db_session)) -> dict:
    row = GatesRepo(session).latest(change_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"no gate decision for change {change_id}")
    try:
        workflow_state = ApprovalService(session).state_of(change_id)
    except LookupError:
        workflow_state = "UNKNOWN"
    return {
        "gate_id": row.id,
        "change_id": change_id,
        "decision": row.decision,
        "score": row.score,
        "reasons": row.reasons_json,
        "override_status": row.override_status,
        "workflow_state": workflow_state,
        "override_eligible": row.override_status == "open" and workflow_state == "AWAITING_APPROVAL",
        "created_at": row.created_at,
    }


@router.get("/{change_id}/report")
def get_report(change_id: int, session: Session = Depends(db_session)) -> dict:
    ChangesRepo(session).require(change_id)
    sections = {}
    for name, fetch in (
        ("impact", lambda: get_impact(change_id, session)),
        ("selection", lambda: get_selection(change_id, session)),
        ("execution", lambda: get_execution(change_id, session)),
        ("failures", lambda: get_failures(change_id, session)),
        ("flaky", lambda: get_flaky(change_id, session)),
        ("confidence", lambda: get_confidence(change_id, session)),
        ("gate", lambda: get_gate(change_id, session)),
    ):
        try:
            sections[name] = fetch()
        except HTTPException as exc:
            sections[name] = {"error": exc.detail}
    return {"change_id": change_id, **sections}
