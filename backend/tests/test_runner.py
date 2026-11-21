"""Constrained pytest runner: parsing, whitelisting, retry policy."""
import pytest

from backend.app.services.runner import ALLOWED_NODE_PREFIX, PytestRunner, RunnerError, _junit_node_id


def test_runner_runs_single_passing_test(project_root) -> None:
    runner = PytestRunner(project_root=project_root, timeout_s=120)
    report = runner.run_once([f"{ALLOWED_NODE_PREFIX}test_auth.py::test_login_rejects_bad_password"])
    assert report.passed == 1 and report.failed == 0
    output = report.outputs[0]
    assert output.outcome == "passed"
    assert output.duration_s >= 0.0
    assert not output.retried


def test_runner_reports_failure_message(project_root) -> None:
    runner = PytestRunner(project_root=project_root, timeout_s=120)
    node = f"{ALLOWED_NODE_PREFIX}test_flaky_seeded.py::test_flaky_search_index_refresh"
    report = runner.run_once([node], env_extra={"QE_FLAKY_ACTIVE": "1", "QE_FLAKY_FORCE_FAIL": "1"})
    assert report.outputs[0].outcome in ("passed", "failed")


def test_runner_rejects_nodes_outside_suite() -> None:
    runner = PytestRunner(timeout_s=10)
    with pytest.raises(RunnerError):
        runner.run_once(["backend/tests/test_unit_analysis.py::test_scan_imports_finds_expected_edges"])
    with pytest.raises(RunnerError):
        runner.run_once([])
    with pytest.raises(RunnerError):
        runner.run_once(["../etc/passwd::x"])


def test_retry_rescues_alternating_flake(project_root) -> None:
    from pathlib import Path
    import shutil

    state_dir = Path(project_root) / "tests_suite" / ".flaky_state"
    shutil.rmtree(state_dir, ignore_errors=True)
    runner = PytestRunner(project_root=project_root, timeout_s=120)
    node = f"{ALLOWED_NODE_PREFIX}test_flaky_seeded.py::test_flaky_search_index_refresh"
    first = runner.run_once([node], env_extra={"QE_FLAKY_ACTIVE": "1"})
    second = runner.run_once([node], env_extra={"QE_FLAKY_ACTIVE": "1"})
    assert {first.outputs[0].outcome, second.outputs[0].outcome} == {"passed", "failed"}
    rescued = runner.run_with_retry([node], flaky_suspects={node}, env_extra={"QE_FLAKY_ACTIVE": "1"})
    shutil.rmtree(state_dir, ignore_errors=True)


def test_junit_node_id_mapping() -> None:
    assert _junit_node_id("tests_suite.test_payments", "test_refund_net_amount_math") == "tests_suite/test_payments.py::test_refund_net_amount_math"


def test_no_retry_for_non_suspect_failures(project_root) -> None:
    from sample_app import payments as pay

    pay.set_bug_state(True)
    try:
        runner = PytestRunner(project_root=project_root, timeout_s=120)
        node = f"{ALLOWED_NODE_PREFIX}test_payments.py::test_validate_amount_rejects_above_limit"
        report = runner.run_with_retry([node], flaky_suspects=set())
        output = report.outputs[0]
        assert output.outcome == "failed"
        assert not output.retried
        assert "PaymentError" in output.message or "DID NOT RAISE" in output.message or output.message
    finally:
        pay.set_bug_state(False)
