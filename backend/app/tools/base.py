"""Typed tool infrastructure with permission levels and audit logging."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Type

from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from backend.app.models import ToolCall
from backend.app.services import metrics


class ToolError(RuntimeError):
    """Raised when a tool invocation is invalid or fails."""


class ToolDefinition(ABC):
    name: str = ""
    description: str = ""
    permission: str = "safe"
    timeout_s: int = 60
    input_model: Type[BaseModel] = BaseModel

    @abstractmethod
    def run(self, session: Session, params: BaseModel) -> Dict[str, Any]:
        ...


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolError(f"unknown tool {name}")
        return tool

    def names(self) -> list[str]:
        return sorted(self._tools)

    def execute(self, session: Session, name: str, payload: Dict[str, Any], change_id: int | None = None) -> Dict[str, Any]:
        started = time.perf_counter()
        tool = self.get(name)
        ok = True
        error = ""
        data: Dict[str, Any] = {}
        try:
            try:
                params = tool.input_model.model_validate(payload)
            except ValidationError as exc:
                raise ToolError(f"invalid input for {name}: {exc}") from exc
            data = tool.run(session, params)
        except Exception as exc:
            ok = False
            error = f"{type(exc).__name__}: {exc}"
            data = {}
        duration_ms = int((time.perf_counter() - started) * 1000)
        if session is not None:
            session.add(
                ToolCall(
                    name=name,
                    permission=tool.permission,
                    payload_json=payload,
                    result_summary_json={"ok": ok, "keys": list(data)[:12]},
                    ok=ok,
                    error=error,
                    duration_ms=duration_ms,
                    change_id=change_id,
                )
            )
            session.flush()
        metrics.incr("qe_tool_calls_total")
        return {"ok": ok, "error": error, "duration_ms": duration_ms, "data": data}


registry = ToolRegistry()
