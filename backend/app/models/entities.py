"""ORM entities persisted by the quality engineering agent."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Module(Base):
    __tablename__ = "modules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True)
    complexity: Mapped[int] = mapped_column(Integer, default=1)
    criticality: Mapped[int] = mapped_column(Integer, default=3)
    security_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    historical_defects: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class CodeDependency(Base):
    __tablename__ = "code_dependencies"
    __table_args__ = (UniqueConstraint("module", "depends_on", name="uq_dep_pair"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    module: Mapped[str] = mapped_column(String(255))
    depends_on: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(32), default="import")


class Change(Base):
    __tablename__ = "changes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    source: Mapped[str] = mapped_column(String(64), default="api")
    manifest_json: Mapped[dict] = mapped_column(JSON, default=dict)
    lines_added: Mapped[int] = mapped_column(Integer, default=0)
    lines_deleted: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="received")
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class ImpactAnalysis(Base):
    __tablename__ = "impact_analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("changes.id"), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class TestRegistration(Base):
    __tablename__ = "test_registry"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    test_id: Mapped[str] = mapped_column(String(255), unique=True)
    node_id: Mapped[str] = mapped_column(String(500), unique=True)
    test_type: Mapped[str] = mapped_column(String(32), default="unit")
    module_mappings_json: Mapped[list] = mapped_column(JSON, default=list)
    avg_runtime_s: Mapped[float] = mapped_column(Float, default=0.1)
    flakiness_score: Mapped[float] = mapped_column(Float, default=0.0)
    historical_outcomes_json: Mapped[list] = mapped_column(JSON, default=list)
    security_relevant: Mapped[bool] = mapped_column(Boolean, default=False)


class SelectionRecord(Base):
    __tablename__ = "selections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("changes.id"), index=True)
    strategy: Mapped[str] = mapped_column(String(64), default="impact+critical-smoke+flaky-watch")
    total_tests: Mapped[int] = mapped_column(Integer, default=0)
    selected_count: Mapped[int] = mapped_column(Integer, default=0)
    reduction_pct: Mapped[float] = mapped_column(Float, default=0.0)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class Execution(Base):
    __tablename__ = "executions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("changes.id"), index=True)
    selection_id: Mapped[int] = mapped_column(ForeignKey("selections.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="running")
    total: Mapped[int] = mapped_column(Integer, default=0)
    passed: Mapped[int] = mapped_column(Integer, default=0)
    failed: Mapped[int] = mapped_column(Integer, default=0)
    retried: Mapped[int] = mapped_column(Integer, default=0)
    duration_s: Mapped[float] = mapped_column(Float, default=0.0)
    started_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)
    finished_at: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ExecutionResult(Base):
    __tablename__ = "execution_results"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), index=True)
    test_id: Mapped[str] = mapped_column(String(255))
    node_id: Mapped[str] = mapped_column(String(500))
    outcome: Mapped[str] = mapped_column(String(16), default="unknown")
    duration_s: Mapped[float] = mapped_column(Float, default=0.0)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    retried_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    message: Mapped[str] = mapped_column(Text, default="")


class FailureAnalysis(Base):
    __tablename__ = "failure_analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("changes.id"), index=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), index=True)
    test_id: Mapped[str] = mapped_column(String(255))
    node_id: Mapped[str] = mapped_column(String(500))
    stack_trace: Mapped[str] = mapped_column(Text, default="")
    log_excerpt: Mapped[str] = mapped_column(Text, default="")
    diff_ref: Mapped[str] = mapped_column(Text, default="")
    related_history_json: Mapped[list] = mapped_column(JSON, default=list)
    rca_id: Mapped[int | None] = mapped_column(ForeignKey("root_cause_analyses.id"), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class RootCauseAnalysisRecord(Base):
    __tablename__ = "root_cause_analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(128), unique=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("changes.id"), index=True)
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class FlakyReport(Base):
    __tablename__ = "flaky_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("changes.id"), index=True)
    execution_id: Mapped[int] = mapped_column(ForeignKey("executions.id"), index=True)
    test_id: Mapped[str] = mapped_column(String(255))
    classification: Mapped[str] = mapped_column(String(48), default="unknown")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    signals_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class ConfidenceScore(Base):
    __tablename__ = "confidence_scores"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("changes.id"), index=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    breakdown_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class QualityGateDecision(Base):
    __tablename__ = "quality_gate_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("changes.id"), index=True)
    decision: Mapped[str] = mapped_column(String(16), default="review")
    score: Mapped[float] = mapped_column(Float, default=0.0)
    reasons_json: Mapped[list] = mapped_column(JSON, default=list)
    narrative: Mapped[str] = mapped_column(Text, default="")
    override_status: Mapped[str] = mapped_column(String(32), default="open")
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class ReleaseWorkflow(Base):
    __tablename__ = "release_workflows"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    change_id: Mapped[int] = mapped_column(ForeignKey("changes.id"), unique=True, index=True)
    state: Mapped[str] = mapped_column(String(32), default="PROPOSED")
    history_json: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("release_workflows.id"), index=True)
    gate_decision_id: Mapped[int] = mapped_column(ForeignKey("quality_gate_decisions.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(16))
    approver: Mapped[str] = mapped_column(String(255))
    justification: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class ToolCall(Base):
    __tablename__ = "tool_calls"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    permission: Mapped[str] = mapped_column(String(16), default="safe")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    result_summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    change_id: Mapped[int | None] = mapped_column(ForeignKey("changes.id"), nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)


class KpiSnapshot(Base):
    __tablename__ = "kpi_snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    label: Mapped[str] = mapped_column(String(64), default="scheduled")
    payload_json: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[str] = mapped_column(String(64), default=utcnow_iso)
