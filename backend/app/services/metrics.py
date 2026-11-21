"""Hand-rolled Prometheus text metrics registry."""
from __future__ import annotations

from threading import Lock

_lock = Lock()
_counters: dict[str, float] = {}
_gauges: dict[str, float] = {}
_labeled: dict[tuple[str, str], float] = {}

_META = {
    "qe_changes_submitted_total": ("counter", "Changes submitted to the agent."),
    "qe_changes_analyzed_total": ("counter", "Full analysis pipeline runs."),
    "qe_tests_executed_total": ("counter", "Individual tests executed by the runner."),
    "qe_tests_failed_total": ("counter", "Individual test failures (post-retry)."),
    "qe_gate_decisions_total": ("counter", "Quality gate decisions by decision label."),
    "qe_overrides_total": ("counter", "Gate override actions by action label."),
    "qe_bug_toggles_total": ("counter", "Regression bug toggle operations by state."),
    "qe_flaky_classified_total": ("counter", "Flaky classification events."),
    "qe_last_confidence_score": ("gauge", "Most recent release confidence score."),
    "qe_last_suite_reduction_percent": ("gauge", "Suite reduction percent of latest selection."),
    "qe_selections_total": ("counter", "Selection computations performed."),
}


def incr(name: str, amount: float = 1.0) -> None:
    with _lock:
        _counters[name] = _counters.get(name, 0.0) + amount


def incr_labeled(name: str, label_value: str, amount: float = 1.0) -> None:
    with _lock:
        _labeled[(name, label_value)] = _labeled.get((name, label_value), 0.0) + amount


def set_gauge(name: str, value: float) -> None:
    with _lock:
        _gauges[name] = value


def snapshot() -> dict[str, float]:
    with _lock:
        data = {k: v for k, v in _counters.items()}
        data.update({f"{name}|{label}": v for (name, label), v in _labeled.items()})
        data.update(_gauges)
    return data


def render() -> str:
    lines: list[str] = []
    with _lock:
        counters = dict(_counters)
        labeled = dict(_labeled)
        gauges = dict(_gauges)
    for name, (kind, help_text) in _META.items():
        lines.append(f"# HELP {name} {help_text}")
        lines.append(f"# TYPE {name} {kind}")
    for name, value in sorted(counters.items()):
        lines.append(f"{name} {value}")
    per_counter: dict[str, list[tuple[str, float]]] = {}
    for (name, label), value in labeled.items():
        per_counter.setdefault(name, []).append((label, value))
    for name in sorted(per_counter):
        for label, value in sorted(per_counter[name]):
            safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in label)
            lines.append(f'{name}{{decision="{label}",action="{safe}"}} {value}')
    for name, value in sorted(gauges.items()):
        lines.append(f"{name} {value}")
    return "\n".join(lines) + "\n"
