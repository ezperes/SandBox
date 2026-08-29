from __future__ import annotations

from copy import deepcopy
from typing import Any


class FakeToolAdapter:
    def __init__(self, response: dict[str, Any] | None = None):
        self.response = deepcopy(response or {"ok": True})
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def invoke(self, tool_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((tool_id, deepcopy(payload)))
        return deepcopy(self.response)
