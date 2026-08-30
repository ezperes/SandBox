from __future__ import annotations

from collections.abc import Iterator, Mapping, MutableMapping
from contextlib import contextmanager
from copy import deepcopy
from threading import RLock
from typing import Any


class _LockedMapping(MutableMapping[str, Any]):
    """Lock-aware mutable view used to preserve the legacy ``records`` API."""

    def __init__(self, data: dict[str, Any], lock: RLock):
        self._data = data
        self._lock = lock

    def __getitem__(self, key: str) -> Any:
        with self._lock:
            value = self._data[key]
            if isinstance(value, dict):
                return _LockedMapping(value, self._lock)
            return deepcopy(value)

    def __setitem__(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = deepcopy(value)

    def __delitem__(self, key: str) -> None:
        with self._lock:
            del self._data[key]

    def __iter__(self) -> Iterator[str]:
        with self._lock:
            keys = tuple(self._data.keys())
        return iter(keys)

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

    def pop(self, key: str, default: Any = ...):
        with self._lock:
            if default is ...:
                value = self._data.pop(key)
            else:
                value = self._data.pop(key, default)
            return deepcopy(value)


class InMemorySourceAdapter:
    def __init__(self, records: dict[str, dict[str, Any]]):
        self._revision_lock = RLock()
        self._records = deepcopy(records)
        # Backward-compatible mutable surface. Nested writes are now lock-aware,
        # so legacy tests/callers cannot bypass an active revision fence.
        self.records: MutableMapping[str, Any] = _LockedMapping(self._records, self._revision_lock)

    def read(self, source_ref: str) -> dict[str, Any]:
        with self._revision_lock:
            if source_ref not in self._records:
                raise KeyError(source_ref)
            return deepcopy(self._records[source_ref])

    def update_record(self, source_ref: str, values: Mapping[str, Any]) -> None:
        with self._revision_lock:
            if source_ref not in self._records:
                raise KeyError(source_ref)
            self._records[source_ref].update(deepcopy(dict(values)))

    @contextmanager
    def revision_fence(
        self,
        expected_revision_refs: Mapping[str, tuple[str, ...]],
    ) -> Iterator[None]:
        """Hold all in-memory authority revisions stable for one tool boundary.

        The adapter supplies exclusion only. It does not decide whether the
        revisions are authorized or current; Core revalidates them after this
        lock is acquired. All public mutation paths honor the same lock.
        """
        del expected_revision_refs
        with self._revision_lock:
            yield
