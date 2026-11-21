"""Repository grouping for change lifecycle artifacts."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Change, ConfidenceScore, ImpactAnalysis, ReleaseWorkflow, QualityGateDecision


class ChangesRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, title: str, manifest_json: dict, lines_added: int, lines_deleted: int, source: str = "api") -> Change:
        change = Change(title=title, manifest_json=manifest_json, lines_added=lines_added, lines_deleted=lines_deleted, source=source)
        self.session.add(change)
        self.session.flush()
        return change

    def get(self, change_id: int) -> Change | None:
        return self.session.get(Change, change_id)

    def require(self, change_id: int) -> Change:
        change = self.get(change_id)
        if change is None:
            raise LookupError(f"change {change_id} not found")
        return change

    def list(self) -> list[Change]:
        rows = self.session.execute(select(Change).order_by(Change.id.desc())).scalars().all()
        return list(rows)

    def set_status(self, change_id: int, status: str) -> None:
        self.require(change_id).status = status
        self.session.flush()


class ImpactsRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, change_id: int, payload_json: dict) -> ImpactAnalysis:
        row = ImpactAnalysis(change_id=change_id, payload_json=payload_json)
        self.session.add(row)
        self.session.flush()
        return row

    def latest(self, change_id: int) -> ImpactAnalysis | None:
        rows = (
            self.session.execute(
                select(ImpactAnalysis).where(ImpactAnalysis.change_id == change_id).order_by(ImpactAnalysis.id.desc())
            )
            .scalars()
            .first()
        )
        return rows


class ConfidenceRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, change_id: int, score: float, breakdown_json: dict) -> ConfidenceScore:
        row = ConfidenceScore(change_id=change_id, score=score, breakdown_json=breakdown_json)
        self.session.add(row)
        self.session.flush()
        return row

    def latest(self, change_id: int) -> ConfidenceScore | None:
        return (
            self.session.execute(
                select(ConfidenceScore).where(ConfidenceScore.change_id == change_id).order_by(ConfidenceScore.id.desc())
            )
            .scalars()
            .first()
        )


class GatesRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, change_id: int, decision: str, score: float, reasons: list[str], narrative: str = "") -> QualityGateDecision:
        row = QualityGateDecision(change_id=change_id, decision=decision, score=score, reasons_json=reasons, narrative=narrative)
        self.session.add(row)
        self.session.flush()
        return row

    def latest(self, change_id: int) -> QualityGateDecision | None:
        return (
            self.session.execute(
                select(QualityGateDecision)
                .where(QualityGateDecision.change_id == change_id)
                .order_by(QualityGateDecision.id.desc())
            )
            .scalars()
            .first()
        )

    def get(self, gate_id: int) -> QualityGateDecision | None:
        return self.session.get(QualityGateDecision, gate_id)

    def require(self, gate_id: int) -> QualityGateDecision:
        gate = self.get(gate_id)
        if gate is None:
            raise LookupError(f"gate {gate_id} not found")
        return gate


class WorkflowRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, change_id: int) -> ReleaseWorkflow:
        from backend.app.models import utcnow_iso

        row = ReleaseWorkflow(change_id=change_id, state="PROPOSED", history_json=[{"state": "PROPOSED", "at": utcnow_iso()}])
        self.session.add(row)
        self.session.flush()
        return row

    def by_change(self, change_id: int) -> ReleaseWorkflow | None:
        return self.session.execute(select(ReleaseWorkflow).where(ReleaseWorkflow.change_id == change_id)).scalars().first()

    def require_by_change(self, change_id: int) -> ReleaseWorkflow:
        row = self.by_change(change_id)
        if row is None:
            raise LookupError(f"workflow for change {change_id} not found")
        return row

    def require(self, workflow_id: int) -> ReleaseWorkflow:
        row = self.session.get(ReleaseWorkflow, workflow_id)
        if row is None:
            raise LookupError(f"workflow {workflow_id} not found")
        return row
