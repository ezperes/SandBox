from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from threading import RLock
from typing import Any, Iterator, Mapping


class InMemorySourceAdapter:
    def __init__(self, records: dict[str, dict[str, Any]]):
        self.records = deepcopy(records)
        self._revision_lock = RLock()

    def read(self, source_ref: str) -> dict[str, Any]:
        with self._revision_lock:
            if source_ref not in self.records:
                raise KeyError(source_ref)
            return deepcopy(self.records[source_ref])

    def update_record(self, source_ref: str, values: Mapping[str, Any]) -> None:
        """Mutate a record through the adapter's fenced writer path.

        Tests and development code that need concurrency guarantees must mutate
        through this method. Direct writes to ``records`` are an intentionally
        unsupported escape hatch retained only for backward compatibility.
        """
        with self._revision_lock:
            if source_ref not in self.records:
                raise KeyError(source_ref)
            self.records[source_ref].update(deepcopy(dict(values)))

    @contextmanager
    def revision_fence(
        self,
        expected_revision_refs: Mapping[str, tuple[str, ...]],
    ) -> Iterator[None]:
        """Hold all in-memory authority revisions stable for one tool boundary.

        The adapter does not decide whether the revisions are authorized or
        current; Core revalidates them after this lock is acquired. The mapping
        is accepted to match the capability contract and to make the protected
        refs explicit for future adapters.
        """
        del expected_revision_refs
        with self._revision_lock:
            yield
