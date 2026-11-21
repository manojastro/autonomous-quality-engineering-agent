"""Tool registry: typed inputs, permissions, audit trail, bug toggle."""
from sqlalchemy import select

from sample_app import payments as pay
from backend.app.models import ToolCall
from backend.app.tools import default_registry
from backend.app.tools.base import ToolError


def test_registry_executes_and_audits(session_with_seed) -> None:
    result = default_registry.execute(session_with_seed, "scan_dependencies_tool", {})
    assert result["ok"] is True
    assert result["data"]["nodes"] == 7
    assert result["data"]["edges"] == 5
    calls = list(session_with_seed.execute(select(ToolCall)).scalars().all())
    assert any(call.name == "scan_dependencies_tool" and call.ok for call in calls)
    assert all(call.permission == "safe" for call in calls)


def test_unknown_tool_raises(session_with_seed) -> None:
    try:
        default_registry.execute(session_with_seed, "does_not_exist", {})
        raised = False
    except ToolError as exc:
        raised = True
        assert "unknown tool" in str(exc)
    assert raised


def test_invalid_payload_is_audited_as_failure(session_with_seed) -> None:
    result = default_registry.execute(session_with_seed, "trigger_regression_bug_tool", {"active": "not-a-bool"})
    assert result["ok"] is False
    row = session_with_seed.execute(select(ToolCall).order_by(ToolCall.id.desc())).scalars().first()
    assert row.ok is False and "invalid input" in row.error


def test_bug_toggle_mutates_state_file(session_with_seed) -> None:
    pay.set_bug_state(False)
    result_on = default_registry.execute(session_with_seed, "trigger_regression_bug_tool", {"active": True})
    assert result_on["data"]["active"] is True and pay.bug_active()
    result_off = default_registry.execute(session_with_seed, "trigger_regression_bug_tool", {"active": False})
    assert result_off["data"]["active"] is False and not pay.bug_active()


def test_default_registry_has_all_eight_tools() -> None:
    expected = {
        "scan_dependencies_tool",
        "select_tests_tool",
        "execute_tests_tool",
        "analyze_failures_tool",
        "classify_flaky_tool",
        "compute_confidence_tool",
        "evaluate_quality_gate_tool",
        "trigger_regression_bug_tool",
    }
    assert set(default_registry.names()) == expected
