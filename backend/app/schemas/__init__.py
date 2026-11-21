"""API request/response contracts."""
from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator


class FileChange(BaseModel):
    path: str = Field(min_length=1)
    functions_changed: list[str] = Field(default_factory=list)
    lines_added: int = Field(default=0, ge=0)
    lines_deleted: int = Field(default=0, ge=0)

    @field_validator("path")
    @classmethod
    def _normalize(cls, value: str) -> str:
        return value.replace("\\", "/").strip()


class ChangeManifest(BaseModel):
    title: str = ""
    files: list[FileChange] = Field(min_length=1)
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_added(self) -> int:
        return sum(f.lines_added for f in self.files)

    @property
    def total_deleted(self) -> int:
        return sum(f.lines_deleted for f in self.files)


class ImpactedModule(BaseModel):
    module: str
    reason: str


class ImpactReport(BaseModel):
    change_id: int
    changed_modules: list[str]
    changed_functions: dict[str, list[str]]
    impacted_modules: list[ImpactedModule]
    graph_stats: dict[str, int]


class SelectionItem(BaseModel):
    test_id: str
    node_id: str
    test_type: str
    module_mappings: list[str]
    priority_score: float = 0.0
    priority_factors: dict[str, float] = Field(default_factory=dict)
    rationale: str


class SkippedTest(BaseModel):
    test_id: str
    node_id: str
    reason: str


class SelectionReport(BaseModel):
    change_id: int
    selection_id: int
    strategy: str
    total_tests: int
    selected_count: int
    reduction_pct: float
    selected: list[SelectionItem]
    skipped: list[SkippedTest]


class TestResultOut(BaseModel):
    test_id: str
    node_id: str
    outcome: str
    duration_s: float
    attempts: int
    retried_flag: bool
    message: str = ""


class ExecutionReport(BaseModel):
    execution_id: int
    change_id: int
    status: str
    total: int
    passed: int
    failed: int
    retried: int
    duration_s: float
    results: list[TestResultOut]


class RootCauseAnalysis(BaseModel):
    incident_id: str
    observations: list[str]
    evidence: list[str]
    hypotheses: list[str]
    rejected_hypotheses: list[str]
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_actions: list[str]


class FailureDetail(BaseModel):
    test_id: str
    node_id: str
    stack_trace: str
    log_excerpt: str
    diff_ref: str
    related_history: list[str]
    rca: Optional[RootCauseAnalysis] = None
    flaky_classification: Optional[str] = None


class FailuresReport(BaseModel):
    change_id: int
    execution_id: Optional[int] = None
    failures: list[FailureDetail]


class FlakyEntry(BaseModel):
    test_id: str
    classification: str
    confidence: float
    signals: dict[str, Any]


class FlakyReportOut(BaseModel):
    change_id: int
    entries: list[FlakyEntry]


class ConfidenceBreakdown(BaseModel):
    passed_results_ratio: float
    changed_module_coverage: float
    critical_path_validated: bool
    unresolved_failures: int
    flakiness_penalty_factor: float
    security_penalty_factor: float
    component_points: dict[str, float]


class ConfidenceReport(BaseModel):
    change_id: int
    score: float
    breakdown: ConfidenceBreakdown
    weights: dict[str, float]
    narrative: str = ""


class GateDecision(BaseModel):
    gate_id: int
    change_id: int
    decision: Literal["allow", "review", "block"]
    score: float
    reasons: list[str]
    override_status: str
    workflow_state: str
    narrative: str = ""
    override_eligible: bool = False


class OverrideRequest(BaseModel):
    action: Literal["approve", "reject"]
    approver: str = Field(min_length=3)
    justification: str = ""


class RegistryTestOut(BaseModel):
    test_id: str
    node_id: str
    test_type: str
    module_mappings: list[str]
    avg_runtime_s: float
    flakiness_score: float
    historical_outcomes: list[str]
    security_relevant: bool


class BugStateOut(BaseModel):
    module: str
    active: bool
    state_file: str


class WorkflowTransition(BaseModel):
    state: str
    at: str


class ChangeCreated(BaseModel):
    id: int
    title: str
    lines_added: int
    lines_deleted: int
    workflow_state: str
    created_at: str


class AnalyzeSummary(BaseModel):
    change_id: int
    impacted_modules: list[str]
    selected_count: int
    total_tests: int
    reduction_pct: float
    executed_total: int
    executed_passed: int
    executed_failed: int
    failures: int
    confidence: float
    decision: str
    workflow_state: str
