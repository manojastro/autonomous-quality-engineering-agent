"""Change manifest to impacted-module analysis."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from backend.app.analysis.ast_graph import build_dependents, impacted_closure, normalize_manifest_path, scan_imports
from backend.app.config import PROJECT_ROOT


class ImpactResult:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    @property
    def changed_modules(self) -> List[str]:
        return list(self._payload["changed_modules"])

    @property
    def changed_functions(self) -> Dict[str, List[str]]:
        return dict(self._payload["changed_functions"])

    @property
    def impacted_modules(self) -> List[str]:
        return [entry["module"] for entry in self._payload["impacted_modules"]]

    @property
    def payload(self) -> dict:
        return self._payload


def analyze_change(manifest_files: List[dict], root: Path = PROJECT_ROOT) -> ImpactResult:
    """Compute the impacted-module closure for a change manifest."""
    graph = scan_imports(root)
    dependents = build_dependents(graph)
    changed: List[str] = []
    functions: Dict[str, List[str]] = {}
    ignored: List[str] = []
    for file_entry in manifest_files:
        module = normalize_manifest_path(str(file_entry.get("path", "")), root)
        if module is None:
            ignored.append(str(file_entry.get("path", "")))
            continue
        if module not in changed:
            changed.append(module)
        fns = [str(f) for f in file_entry.get("functions_changed", [])]
        if fns or module not in functions:
            functions[module] = sorted(set(functions.get(module, [])) | set(fns))
    impacted, stats = impacted_closure(sorted(changed), graph, dependents)
    payload = {
        "changed_modules": sorted(changed),
        "ignored_paths": sorted(ignored),
        "changed_functions": {k: v for k, v in sorted(functions.items())},
        "impacted_modules": impacted,
        "graph_stats": stats,
    }
    return ImpactResult(payload)
