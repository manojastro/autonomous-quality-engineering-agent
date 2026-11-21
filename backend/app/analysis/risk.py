"""Risk-based priority ordering for selected tests."""
from __future__ import annotations

from typing import Dict, List, Sequence

from backend.app.models import Module, TestRegistration

TYPE_WEIGHTS = {"smoke": 2.0, "integration": 1.5, "contract": 1.25, "api": 1.0, "unit": 0.5}


def risk_score(
    test: TestRegistration,
    modules_by_name: Dict[str, Module],
    change_size_norm: float,
    impacted_modules: set[str],
) -> dict:
    """Deterministic priority: criticality x complexity x size x security x defects x gap."""
    mapped = [m for m in (test.module_mappings_json or []) if m in modules_by_name]
    criticality = max((modules_by_name[m].criticality for m in mapped), default=1)
    complexity = max((modules_by_name[m].complexity for m in mapped), default=1)
    security = 4 if any(modules_by_name[m].security_sensitive for m in mapped) else 0
    historical_defects = sum(
        1 for outcome in (test.historical_outcomes_json or []) if outcome == "fail"
    )
    recent = (test.historical_outcomes_json or [])[-8:]
    coverage_gap = round(recent.count("fail") / len(recent), 3) if recent else 0.5
    impact_bonus = 2.0 if any(m in impacted_modules for m in (test.module_mappings_json or [])) else 0.0
    factors = {
        "criticality_x3": criticality * 3.0,
        "complexity": float(complexity),
        "change_size_x5": round(change_size_norm * 5.0, 3),
        "security_x4": float(security),
        "historical_defects": float(historical_defects),
        "coverage_gap_x2": round(coverage_gap * 2.0, 3),
        "type_weight": TYPE_WEIGHTS.get(test.test_type, 0.5),
        "impact_bonus": impact_bonus,
    }
    return {"priority_score": round(sum(factors.values()), 3), "factors": factors}


def order_selection(selected: List[dict], registry_by_id: Dict[str, TestRegistration], modules: Sequence[Module], change_size_norm: float, impacted_modules: Sequence[str]) -> List[dict]:
    """Annotate and sort selected tests by descending risk priority."""
    by_name = {m.name: m for m in modules}
    annotated: List[dict] = []
    for item in selected:
        reg = registry_by_id.get(item["test_id"])
        if reg is None:
            continue
        scored = risk_score(reg, by_name, change_size_norm, set(impacted_modules))
        enriched = dict(item)
        enriched["priority_score"] = scored["priority_score"]
        enriched["priority_factors"] = scored["factors"]
        enriched["avg_runtime_s"] = reg.avg_runtime_s
        enriched["flakiness_score"] = reg.flakiness_score
        annotated.append(enriched)
    annotated.sort(key=lambda item: (-item["priority_score"], item.get("avg_runtime_s", 0.0)))
    return annotated
