"""Agent-layer unit tests: risk ordering, RCA synthesis, LLM narration."""
from backend.app.agents.agents import (
    CodeDependencyAgent,
    FailureRCAAgent,
    QualityGateAgent,
    ReleaseConfidenceAgent,
    RiskBasedTestingAgent,
)
from backend.app.services.rca_logic import build_rca
from backend.app.services.seeder import MODULES, TEST_REGISTRY


class _Reg:
    def __init__(self, fields: dict) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


class _Mod:
    def __init__(self, fields: dict) -> None:
        for key, value in fields.items():
            setattr(self, key, value)


MODULES_BY_NAME = {m["name"]: _Mod(m) for m in MODULES}
REGISTRY_BY_ID = {t["test_id"]: _Reg(t) for t in TEST_REGISTRY}


def test_risk_orders_security_critical_first() -> None:
    from backend.app.analysis.selection import select_tests

    registry = list(REGISTRY_BY_ID.values())
    plan = select_tests(registry, ["sample_app.payments", "sample_app.orders", "sample_app.reports"])
    from backend.app.analysis.risk import order_selection

    ordered = order_selection(plan["selected"], REGISTRY_BY_ID, list(MODULES_BY_NAME.values()), 0.2, ["sample_app.payments", "sample_app.orders", "sample_app.reports"])
    scores = [item["priority_score"] for item in ordered]
    assert scores == sorted(scores, reverse=True)
    top = ordered[0]
    factors = top["priority_factors"]
    assert factors["criticality_x3"] >= 9.0
    agent = RiskBasedTestingAgent()
    priorities = agent.run(None, {"selected": ordered})
    assert priorities["priority_order"][0] == top["test_id"]
    assert len(priorities["top_risks"]) <= 5


def test_dependency_agent_returns_graph() -> None:
    data = CodeDependencyAgent().run(None)
    assert data["nodes"] == 7 and data["edges"] == 5


def test_rca_names_injected_regression_when_bug_active(tmp_path, monkeypatch) -> None:
    from sample_app import payments as pay

    pay.set_bug_state(True)
    try:
        payload = build_rca(
            incident_id="INC-TEST-1",
            test_id="payments_boundary_above_limit",
            node_id="tests_suite/test_payments.py::test_validate_amount_rejects_above_limit",
            message="Failed: DID NOT RASE PaymentError",
            changed_functions={"sample_app.payments": ["validate_amount"]},
            module_mappings=["sample_app.payments"],
            history=["pass", "pass", "fail", "pass"],
        )
        assert "Injected regression" in payload["root_cause"]
        assert payload["confidence"] >= 0.9
        assert payload["rejected_hypotheses"]
        assert any("Disable the injected regression" in a for a in payload["recommended_actions"])
        assert payload["incident_id"] == "INC-TEST-1"
    finally:
        pay.set_bug_state(False)


def test_rca_without_bug_points_to_change_regression() -> None:
    from sample_app import payments as pay

    assert not pay.bug_active()
    payload = build_rca(
        incident_id="INC-TEST-2",
        test_id="orders_receipt_totals",
        node_id="tests_suite/test_orders.py::test_checkout_receipt_totals",
        message="AssertionError: assert 125.61 == 125.62",
        changed_functions={"sample_app.payments": ["transaction_fee"]},
        module_mappings=["sample_app.orders"],
        history=["pass", "pass", "pass"],
    )
    assert "Change-induced behavioral regression" in payload["root_cause"]
    assert any("pre-existing-defect" in h for h in payload["rejected_hypotheses"])


def test_llm_mock_narration_never_empty_and_prose_only() -> None:
    from backend.app.services.llm import LLMAdapter

    llm = LLMAdapter(mode="mock")
    for kind, context in (
        ("selection", {"impacted_modules": ["payments"], "selected_count": 18, "total_tests": 30, "reduction_pct": 40.0}),
        ("rca", {"root_cause": "injected regression active", "test_id": "t1"}),
        ("gate", {"decision": "block", "score": 57.5, "reasons": ["unresolved failures"]}),
        ("confidence", {"score": 100.0}),
    ):
        text = llm.narrate(kind, context)
        assert isinstance(text, str) and len(text) > 30


def test_llm_live_mode_falls_back_to_mock_without_key() -> None:
    from backend.app.services.llm import LLMAdapter

    llm = LLMAdapter(mode="live")
    llm.api_key = ""
    text = llm.narrate("gate", {"decision": "allow", "score": 100.0, "reasons": []})
    assert "allow" in text
