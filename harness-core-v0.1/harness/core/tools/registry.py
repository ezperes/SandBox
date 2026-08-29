from __future__ import annotations

from dataclasses import dataclass

from harness.contracts import RiskLevel
from harness.ports import ToolPort


@dataclass(frozen=True, slots=True)
class ToolDescriptor:
    tool_id: str
    action_scope: str
    risk_level: RiskLevel = RiskLevel.LOW
    side_effect: bool = False
    required_competence: str | None = None
    approval_required: bool = False
    evidence_required: bool = False
    idempotency_required: bool = True

    def __post_init__(self) -> None:
        if not self.tool_id.strip():
            raise ValueError("tool_id must be explicit")
        if not self.action_scope.strip():
            raise ValueError("action_scope must be explicit")
        if self.side_effect and not self.idempotency_required:
            raise ValueError("side-effect tools must require idempotency")


@dataclass(frozen=True, slots=True)
class RegisteredTool:
    descriptor: ToolDescriptor
    adapter: ToolPort


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, descriptor: ToolDescriptor, adapter: ToolPort) -> None:
        if descriptor.tool_id in self._tools:
            raise ValueError(f"tool already registered: {descriptor.tool_id}")
        self._tools[descriptor.tool_id] = RegisteredTool(descriptor=descriptor, adapter=adapter)

    def resolve(self, tool_id: str) -> RegisteredTool:
        if tool_id not in self._tools:
            raise KeyError(tool_id)
        return self._tools[tool_id]

    def descriptors(self) -> tuple[ToolDescriptor, ...]:
        return tuple(item.descriptor for item in self._tools.values())
