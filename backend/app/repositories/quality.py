"""Repository grouping for failures, flaky reports, RCA, audit and KPIs."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import (
    Approval,
    FailureAnalysis,
    FlakyReport,
    KpiSnapshot,
    Module,
    RootCauseAnalysisRecord,
    ToolCall,
)


class ModulesRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def all(self) -> list[Module]:
        return list(self.session.execute(select(Module).order_by(Module.name)).scalars().all())

    def by_name(self, name: str) -> Module | None:
        return self.session.execute(select(Module).where(Module.name == name)).scalars().first()


class FailuresRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, **fields: object) -> FailureAnalysis:
        row = FailureAnalysis(**fields)  # type: ignore[arg-type]
        self.session.add(row)
        self.session.flush()
        return row

    def for_change(self, change_id: int) -> list[FailureAnalysis]:
        rows = self.session.execute(
            select(FailureAnalysis).where(FailureAnalysis.change_id == change_id).order_by(FailureAnalysis.id)
        ).scalars().all()
        return list(rows)

    def latest_change_failure_map(self, change_id: int) -> dict[str, FailureAnalysis]:
        return {row.node_id: row for row in self.for_change(change_id)}

    def set_rca(self, failure_id: int, rca_id: int) -> None:
        row = self.session.get(FailureAnalysis, failure_id)
        if row is not None:
            row.rca_id = rca_id
            self.session.flush()


class RcaRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, incident_id: str, change_id: int, payload_json: dict) -> RootCauseAnalysisRecord:
        row = RootCauseAnalysisRecord(incident_id=incident_id, change_id=change_id, payload_json=payload_json)
        self.session.add(row)
        self.session.flush()
        return row

    def get_by_incident(self, incident_id: str) -> RootCauseAnalysisRecord | None:
        return self.session.execute(select(RootCauseAnalysisRecord).where(RootCauseAnalysisRecord.incident_id == incident_id)).scalars().first()

    def for_change(self, change_id: int) -> list[RootCauseAnalysisRecord]:
        return list(
            self.session.execute(
                select(RootCauseAnalysisRecord).where(RootCauseAnalysisRecord.change_id == change_id).order_by(RootCauseAnalysisRecord.id)
            ).scalars().all()
        )


class FlakyRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, **fields: object) -> FlakyReport:
        row = FlakyReport(**fields)  # type: ignore[arg-type]
        self.session.add(row)
        self.session.flush()
        return row

    def for_change(self, change_id: int) -> list[FlakyReport]:
        return list(
            self.session.execute(select(FlakyReport).where(FlakyReport.change_id == change_id).order_by(FlakyReport.id)).scalars().all()
        )

    def recent(self, limit: int = 100) -> list[FlakyReport]:
        rows = self.session.execute(select(FlakyReport).order_by(FlakyReport.id.desc()).limit(limit)).scalars().all()
        return list(rows)


class ApprovalsRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, workflow_id: int, gate_decision_id: int | None, action: str, approver: str, justification: str) -> Approval:
        row = Approval(workflow_id=workflow_id, gate_decision_id=gate_decision_id, action=action, approver=approver, justification=justification)
        self.session.add(row)
        self.session.flush()
        return row

    def for_workflow(self, workflow_id: int) -> list[Approval]:
        return list(
            self.session.execute(select(Approval).where(Approval.workflow_id == workflow_id).order_by(Approval.id)).scalars().all()
        )


class ToolAuditRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, **fields: object) -> ToolCall:
        row = ToolCall(**fields)  # type: ignore[arg-type]
        self.session.add(row)
        self.session.flush()
        return row

    def count(self) -> int:
        return len(list(self.session.execute(select(ToolCall)).scalars().all()))


class KpiRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add_snapshot(self, label: str, payload_json: dict) -> KpiSnapshot:
        row = KpiSnapshot(label=label, payload_json=payload_json)
        self.session.add(row)
        self.session.flush()
        return row

    def history(self, limit: int = 50) -> list[KpiSnapshot]:
        rows = self.session.execute(select(KpiSnapshot).order_by(KpiSnapshot.id.desc()).limit(limit)).scalars().all()
        return list(reversed(rows))
