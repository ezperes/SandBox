from __future__ import annotations

from copy import deepcopy
from typing import Any


class InMemorySourceAdapter:
    def __init__(self, records: dict[str, dict[str, Any]]):
        self.records = deepcopy(records)

    def read(self, source_ref: str) -> dict[str, Any]:
        if source_ref not in self.records:
            raise KeyError(source_ref)
        return deepcopy(self.records[source_ref])
