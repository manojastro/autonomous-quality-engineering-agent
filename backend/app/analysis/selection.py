"""Test selection: impacted modules to minimum high-value test set."""
from __future__ import annotations

from typing import Dict, List, Sequence

from backend.app.config import MIN_FLAKY_SELECT_SCORE
from backend.app.models import TestRegistration

STRATEGY = "impact+critical-smoke+flaky-watch"


def _mapping_hit(test: TestRegistration, impacted: Sequence[str]) -> str | None:
    impacted_set = set(impacted)
    for module in test.module_mappings_json or []:
        if module in impacted_set:
            return module
    return None


def select_tests(registry: Sequence[TestRegistration], impacted_modules: Sequence[str]) -> dict:
    """Select the minimum high-value set: impact-mapped tests, mandatory smoke, flaky watch."""
    selected: List[dict] = []
    skipped: List[dict] = []
    seen: Dict[str, dict] = {}
    for test in registry:
        hit = _mapping_hit(test, impacted_modules)
        is_flaky_watch = test.flakiness_score >= MIN_FLAKY_SELECT_SCORE and hit is not None
        if test.test_type == "smoke":
            entry = {
                "test_id": test.test_id,
                "node_id": test.node_id,
                "test_type": test.test_type,
                "module_mappings": list(test.module_mappings_json or []),
                "rationale": "mandatory critical-path smoke invariant",
            }
            selected.append(entry)
            seen[test.test_id] = entry
        elif hit is not None:
            rationale = f"maps impacted module {hit}"
            if is_flaky_watch:
                rationale += "; flakiness watch (score %.2f)" % test.flakiness_score
            entry = {
                "test_id": test.test_id,
                "node_id": test.node_id,
                "test_type": test.test_type,
                "module_mappings": list(test.module_mappings_json or []),
                "rationale": rationale,
            }
            selected.append(entry)
            seen[test.test_id] = entry
        else:
            mapped = ", ".join(sorted(test.module_mappings_json or [])) or "unmapped"
            skipped.append(
                {
                    "test_id": test.test_id,
                    "node_id": test.node_id,
                    "reason": f"mapped modules unaffected by impact set ({mapped})",
                }
            )
    total = len(registry)
    selected_count = len(selected)
    reduction = round(100.0 * (total - selected_count) / total, 1) if total else 0.0
    return {
        "selected": selected,
        "skipped": skipped,
        "total_tests": total,
        "selected_count": selected_count,
        "reduction_pct": reduction,
        "precision_inputs": {
            "relevant_selected": sum(1 for s in selected if s["test_type"] != "smoke"),
            "mandatory_invariants": sum(1 for s in selected if s["test_type"] == "smoke"),
            "flaky_watched": sum(1 for s in selected if "flakiness watch" in s["rationale"]),
        },
    }


def selection_precision_recall(selected: Sequence[dict], registry_by_id: Dict[str, TestRegistration], true_impacted: Sequence[str]) -> dict:
    """Precision/recall of a selection against a labeled ground-truth impact set."""
    true_set = set(true_impacted)
    tp = fp = 0
    for item in selected:
        reg = registry_by_id.get(item["test_id"])
        if reg is None:
            continue
        if item.get("test_type") == "smoke":
            continue
        mappings = set(reg.module_mappings_json or [])
        tp += 1 if mappings & true_set else 0
        fp += 0 if mappings & true_set else 1
    relevant_registry = [t for t in registry_by_id.values() if set(t.module_mappings_json or []) & true_set]
    fn = 0
    selected_ids = {item["test_id"] for item in selected}
    for test in relevant_registry:
        if test.test_id not in selected_ids:
            fn += 1
    precision = round(tp / (tp + fp), 3) if (tp + fp) else 1.0
    recall = round(tp / (tp + fn), 3) if (tp + fn) else 1.0
    return {"precision": precision, "recall": recall, "true_positives": tp, "false_positives": fp, "false_negatives": fn}
