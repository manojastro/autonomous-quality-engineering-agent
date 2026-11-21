"""Flaky detection, alternation and classification."""
from backend.app.services.flaky_classifier import classify, detect_alternation


def test_detect_alternation_true_for_oscillation() -> None:
    assert detect_alternation(["pass", "fail", "pass", "fail", "pass"])
    assert detect_alternation(["pass", "pass", "fail", "pass", "fail", "pass", "fail"])


def test_detect_alternation_false_for_stable_history() -> None:
    assert not detect_alternation(["pass"] * 8)
    assert not detect_alternation(["pass", "pass", "fail", "fail", "fail"])


def test_rescued_retry_classifies_flaky() -> None:
    outcome = classify("failed", "passed", ["pass"] * 6, message="boom", retried=True)
    assert outcome["classification"] == "flaky_test"
    assert outcome["confidence"] >= 0.9
    assert outcome["signals"]["alternating_history"] is False


def test_deterministic_double_failure_is_product_defect() -> None:
    outcome = classify("failed", "failed", ["pass", "pass", "pass"], message="AssertionError: 2.16 != 2.17")
    assert outcome["classification"] == "product_defect"


def test_timeout_message_maps_to_environment() -> None:
    outcome = classify("failed", "failed", ["pass"], message="search index refresh timed out waiting for cluster")
    assert outcome["classification"] == "environment"


def test_harness_failure_maps_to_automation_defect() -> None:
    outcome = classify("failed", "failed", ["pass"], message="fixture payload missing: response fixture KeyError")
    assert outcome["classification"] == "automation_defect"


def test_unknown_when_signals_insufficient() -> None:
    outcome = classify("skipped", "skipped", [])
    assert outcome["classification"] == "unknown"
