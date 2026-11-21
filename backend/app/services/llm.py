"""LLM adapter: deterministic mock narration by default, live OpenAI-compatible mode optional.

Narration is prose only. Scores, selections and gate decisions are always
produced by deterministic code; the LLM never computes them.
"""
from __future__ import annotations

import os
from typing import Optional

import httpx


class LLMAdapter:
    def __init__(self, mode: Optional[str] = None) -> None:
        self.mode = (mode or os.environ.get("LLM_MODE", "mock")).lower()
        self.api_key = os.environ.get("LLM_API_KEY", "")
        self.base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        self.model = os.environ.get("LLM_MODEL", "gpt-4o-mini")

    def narrate(self, kind: str, context: dict) -> str:
        """Return a short natural-language explanation for a pipeline artifact."""
        if self.mode == "live" and self.api_key:
            live = self._live(kind, context)
            if live:
                return live
        return self._mock(kind, context)

    def _mock(self, kind: str, context: dict) -> str:
        if kind == "selection":
            modules = ", ".join(context.get("impacted_modules", []) or ["no application modules"])
            return (
                f"Impact closure covers {modules}; {context.get('selected_count', 0)} of "
                f"{context.get('total_tests', 0)} registered tests were selected ({context.get('reduction_pct', 0)}% reduction), "
                "prioritizing critical-path smoke, security-sensitive areas and recently flaky tests."
            )
        if kind == "rca":
            root_cause = context.get("root_cause", "undetermined")
            failing = context.get("test_id", "unknown test")
            return (
                f"Evidence from stack trace, application logs, diff metadata and history was correlated for {failing}. "
                f"Most probable root cause: {root_cause}. Rejected hypotheses are retained for audit."
            )
        if kind == "gate":
            decision = context.get("decision", "review")
            score = context.get("score", 0)
            reasons = "; ".join(context.get("reasons", [])) or "no blocking signals"
            return (
                f"The release confidence score is {score}, which maps to a '{decision}' quality-gate decision. "
                f"Contributing factors: {reasons}. This narrative is advisory; the decision is rule-based."
            )
        if kind == "confidence":
            return (
                f"Deterministic confidence {context.get('score', 0)}/100 combines passed-result weight, changed-module coverage, "
                "critical-path validation minus unresolved-failure, flakiness and security penalties."
            )
        return "No narration available."

    def _live(self, kind: str, context: dict) -> str:
        prompt = (
            "You are assisting a release-quality agent. Write 2-3 sentences of plain prose. "
            f"Artifact type: {kind}. Facts: {context} Never invent numbers beyond these facts."
        )
        try:
            response = httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={"model": self.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 160, "temperature": 0.2},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            return str(content).strip()
        except Exception:
            return ""
