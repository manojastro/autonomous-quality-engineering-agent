"""Repository grouping for test registry, selections and executions."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Execution, ExecutionResult, SelectionRecord, TestRegistration


class RegistryRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(self, **fields: object) -> TestRegistration:
        test_id = str(fields["test_id"])
        row = self.session.execute(select(TestRegistration).where(TestRegistration.test_id == test_id)).scalars().first()
        if row is None:
            row = TestRegistration(test_id=test_id)
            self.session.add(row)
        for key, value in fields.items():
            setattr(row, key, value)
        self.session.flush()
        return row

    def all(self) -> list[TestRegistration]:
        return list(self.session.execute(select(TestRegistration).order_by(TestRegistration.id)).scalars().all())

    def count(self) -> int:
        return len(self.all())


class SelectionsRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, change_id: int, strategy: str, total_tests: int, selected_count: int, reduction_pct: float, payload_json: dict) -> SelectionRecord:
        row = SelectionRecord(
            change_id=change_id,
            strategy=strategy,
            total_tests=total_tests,
            selected_count=selected_count,
            reduction_pct=reduction_pct,
            payload_json=payload_json,
        )
        self.session.add(row)
        self.session.flush()
        return row

    def latest(self, change_id: int) -> SelectionRecord | None:
        return (
            self.session.execute(select(SelectionRecord).where(SelectionRecord.change_id == change_id).order_by(SelectionRecord.id.desc()))
            .scalars()
            .first()
        )


class ExecutionsRepo:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, change_id: int, selection_id: int | None) -> Execution:
        row = Execution(change_id=change_id, selection_id=selection_id)
        self.session.add(row)
        self.session.flush()
        return row

    def latest(self, change_id: int) -> Execution | None:
        return (
            self.session.execute(select(Execution).where(Execution.change_id == change_id).order_by(Execution.id.desc()))
            .scalars()
            .first()
        )

    def get(self, execution_id: int) -> Execution | None:
        return self.session.get(Execution, execution_id)

    def add_result(self, execution_id: int, **fields: object) -> ExecutionResult:
        row = ExecutionResult(execution_id=execution_id, **fields)  # type: ignore[arg-type]
        self.session.add(row)
        self.session.flush()
        return row

    def results(self, execution_id: int) -> list[ExecutionResult]:
        return list(
            self.session.execute(select(ExecutionResult).where(ExecutionResult.execution_id == execution_id).order_by(ExecutionResult.id))
            .scalars()
            .all()
        )
