"""Constrained pytest subprocess runner with junit-xml parsing and retry-once policy."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from backend.app.config import PROJECT_ROOT

ALLOWED_NODE_PREFIX = "tests_suite/"


@dataclass
class RunOutput:
    node_id: str
    outcome: str
    duration_s: float
    message: str = ""
    retried: bool = False


@dataclass
class RunReport:
    outputs: List[RunOutput] = field(default_factory=list)
    wall_time_s: float = 0.0

    @property
    def passed(self) -> int:
        return sum(1 for o in self.outputs if o.outcome == "passed")

    @property
    def failed(self) -> int:
        return sum(1 for o in self.outputs if o.outcome not in ("passed", "skipped"))

    def by_node(self) -> Dict[str, RunOutput]:
        return {o.node_id: o for o in self.outputs}


class RunnerError(RuntimeError):
    """Raised when the constrained runner refuses or fails a request."""


def _junit_node_id(classname: str, name: str) -> str:
    file_part = classname.replace(".", "/")
    if not file_part.endswith(".py"):
        file_part += ".py"
    return f"{file_part}::{name}"


def parse_junit(xml_path: Path) -> Dict[str, RunOutput]:
    results: Dict[str, RunOutput] = {}
    tree = ET.parse(xml_path)
    for case in tree.getroot().iter("testcase"):
        classname = case.get("classname", "")
        name = case.get("name", "")
        duration = float(case.get("time", "0") or 0)
        message = ""
        outcome = "passed"
        failure = case.find("failure")
        error = case.find("error")
        if failure is not None:
            outcome = "failed"
            message = (failure.text or "").strip()
            if failure.get("message"):
                message = f"{failure.get('message')}\n{message}"
        elif error is not None:
            outcome = "error"
            message = (error.text or "").strip()
        elif case.find("skipped") is not None:
            outcome = "skipped"
        node_id = _junit_node_id(classname, name)
        results[node_id] = RunOutput(node_id=node_id, outcome=outcome, duration_s=round(duration, 4), message=message[:4000])
    return results


class PytestRunner:
    """Runs whitelisted pytest node ids inside the project directory."""

    def __init__(self, project_root: Path = PROJECT_ROOT, timeout_s: int = 240) -> None:
        self.project_root = project_root
        self.timeout_s = timeout_s

    def _validate_nodes(self, node_ids: List[str]) -> None:
        if not node_ids:
            raise RunnerError("no node ids requested")
        for node in node_ids:
            if not node.startswith(ALLOWED_NODE_PREFIX) or ".." in node or "::" not in node:
                raise RunnerError(f"node id outside allowed suite root: {node}")

    def run_once(self, node_ids: List[str], env_extra: Optional[Dict[str, str]] = None) -> RunReport:
        self._validate_nodes(node_ids)
        tmp_dir = Path(tempfile.mkdtemp(prefix="qe_run_"))
        xml_path = tmp_dir / "report.xml"
        log_path = tmp_dir / "stdout.log"
        env = {**os.environ, "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1"}
        if env_extra:
            env.update(env_extra)
        cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "--junitxml",
            str(xml_path),
            *node_ids,
        ]
        started = time.monotonic()
        proc = subprocess.run(cmd, cwd=str(self.project_root), capture_output=True, text=True, timeout=self.timeout_s, env=env)
        elapsed = round(time.monotonic() - started, 3)
        log_path.write_text((proc.stdout or "") + "\n--- stderr ---\n" + (proc.stderr or ""), encoding="utf-8")
        report = RunReport(wall_time_s=elapsed)
        parsed = parse_junit(xml_path) if xml_path.exists() else {}
        requested = set(node_ids)
        matched: Dict[str, RunOutput] = {}
        for node_id, output in parsed.items():
            if node_id in requested:
                matched[node_id] = output
        summary_tail = ((proc.stdout or "").strip().splitlines() or ["no pytest summary"])[-1]
        for node_id in node_ids:
            if node_id in matched:
                report.outputs.append(matched[node_id])
            else:
                report.outputs.append(
                    RunOutput(node_id=node_id, outcome="error", duration_s=0.0, message=f"missing from junit xml; pytest tail: {summary_tail}")
                )
        return report

    def run_with_retry(self, node_ids: List[str], flaky_suspects: Optional[set[str]] = None, max_retries: int = 1, env_extra: Optional[Dict[str, str]] = None) -> RunReport:
        """Run once; failed suspected-flaky tests are retried individually once."""
        suspects = flaky_suspects or set()
        report = self.run_once(node_ids, env_extra=env_extra)
        for output in report.outputs:
            if max_retries < 1 or output.outcome in ("passed", "skipped") or output.node_id not in suspects:
                continue
            retried = self.run_once([output.node_id], env_extra=env_extra)
            replacement = next((o for o in retried.outputs if o.node_id == output.node_id), None)
            if replacement is not None:
                output.outcome = replacement.outcome
                output.message = replacement.message
                output.duration_s = round(output.duration_s + replacement.duration_s, 4)
                output.retried = True
        return report
