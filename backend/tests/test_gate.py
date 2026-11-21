"""Quality-gate threshold and reason rules."""
from backend.app.services.gate_rules import decide


def test_allow_at_and_above_threshold() -> None:
    assert decide(85.0, 0, 0, 0, False)["decision"] == "allow"
    assert decide(100.0, 0, 0, 0, False)["decision"] == "allow"
    allow = decide(92.0, 0, 0, 0, False)
    assert any("no unresolved failures" in r for r in allow["reasons"])


def test_review_band() -> None:
    assert decide(84.9, 0, 0, 0, False)["decision"] == "review"
    assert decide(60.0, 0, 0, 0, False)["decision"] == "review"


def test_block_below_review_threshold() -> None:
    verdict = decide(59.9, 3, 0, 0, False)
    assert verdict["decision"] == "block"
    assert any("3 unresolved test failure(s)" in r for r in verdict["reasons"])
    assert any("59.9" in r for r in verdict["reasons"])


def test_reasons_report_security_and_critical_path() -> None:
    reasons = decide(50.0, 1, 2, 1, True)["reasons"]
    joined = "; ".join(reasons)
    assert "critical-path smoke suite did not pass" in joined
    assert "security finding(s)" in joined
    assert "critical-path or security-sensitive" not in joined
    assert "failure(s) on security-sensitive" in joined


def test_boundary_values_are_stable() -> None:
    decisions = {score: decide(score, 0, 0, 0, False)["decision"] for score in (85.01, 84.99, 60.01, 59.99)}
    assert decisions[85.01] == "allow"
    assert decisions[84.99] == "review"
    assert decisions[60.01] == "review"
    assert decisions[59.99] == "block"
