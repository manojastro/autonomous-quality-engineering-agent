"""AST-based import scanner and dependency graph utilities."""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple

MODULE_PREFIX = "sample_app."


def known_modules(root: Path) -> Set[str]:
    pkg = root / "sample_app"
    return {f"sample_app.{p.stem}" for p in pkg.glob("*.py") if p.stem != "__init__"}


def normalize_manifest_path(path: str, root: Path) -> str | None:
    normalized = path.replace("\\", "/").strip().lstrip("./")
    if not normalized.startswith("sample_app/") or not normalized.endswith(".py"):
        return None
    stem = Path(normalized).stem
    module = f"sample_app.{stem}"
    return module if module in known_modules(root) else None


def scan_imports(root: Path) -> Dict[str, Set[str]]:
    """Parse every sample_app module and extract local import edges."""
    graph: Dict[str, Set[str]] = {}
    known = known_modules(root)
    for module in sorted(known):
        source_path = root / "sample_app" / f"{module.split('.')[-1]}.py"
        tree = ast.parse(source_path.read_text(encoding="utf-8"))
        targets: Set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in known:
                        targets.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    candidate = node.module if node.level == 0 else MODULE_PREFIX + node.module
                    if candidate in known:
                        targets.add(candidate)
        graph[module] = targets
    return graph


def build_dependents(graph: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    dependents: Dict[str, Set[str]] = {module: set() for module in list(graph) }
    for module, deps in graph.items():
        for dep in deps:
            dependents.setdefault(dep, set()).add(module)
    return dependents


def impacted_closure(
    changed_modules: List[str],
    graph: Dict[str, Set[str]],
    dependents: Dict[str, Set[str]],
) -> Tuple[List[dict], dict]:
    """BFS over reverse dependency edges returning impacted modules with reasons."""
    reasons: Dict[str, str] = {}
    queue: List[Tuple[str, str]] = []
    for module in changed_modules:
        reasons.setdefault(module, "directly changed by manifest")
        queue.append((module, ""))
    while queue:
        current, _via = queue.pop(0)
        for dependent in sorted(dependents.get(current, set())):
            if dependent in reasons:
                continue
            reasons[dependent] = f"depends on {current} via import"
            queue.append((dependent, current))
    impacted = [
        {"module": module, "reason": reason}
        for module, reason in sorted(reasons.items(), key=lambda kv: kv[0])
    ]
    stats = {
        "graph_nodes": len(graph),
        "graph_edges": sum(len(deps) for deps in graph.values()),
        "impacted_count": len(impacted),
    }
    return impacted, stats
