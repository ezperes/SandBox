from __future__ import annotations

from collections.abc import MutableMapping, MutableSequence
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable, Iterator
from uuid import uuid4

from harness.ports import RevisionGuard, VersionedRead, VersionedReadSet
from harness.ports.versioning import (
    GuardedRevision,
    RevisionConflictError,
    RevisionGuardActiveError,
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class _RecordStore(MutableMapping[str, dict[str, Any]]):
    """Compatibility view that routes all material mutations through the adapter."""

    def __init__(self, adapter: "InMemorySourceAdapter") -> None:
        self._adapter = adapter

    def __getitem__(self, source_ref: str) -> "_NestedMapping":
        with self._adapter._lock:
            if source_ref not in self._adapter._records:
                raise KeyError(source_ref)
            if not isinstance(self._adapter._records[source_ref], dict):
                raise TypeError("source records must be mappings")
        return _NestedMapping(self._adapter, source_ref, ())

    def __setitem__(self, source_ref: str, value: dict[str, Any]) -> None:
        self._adapter._replace_record(source_ref, value)

    def __delitem__(self, source_ref: str) -> None:
        self._adapter._delete_record(source_ref)

    def __iter__(self) -> Iterator[str]:
        with self._adapter._lock:
            return iter(tuple(self._adapter._records))

    def __len__(self) -> int:
        with self._adapter._lock:
            return len(self._adapter._records)

    def __deepcopy__(self, memo):
        with self._adapter._lock:
            return deepcopy(self._adapter._records, memo)


class _NestedMapping(MutableMapping[Any, Any]):
    def __init__(self, adapter: "InMemorySourceAdapter", source_ref: str, path: tuple[Any, ...]) -> None:
        self._adapter = adapter
        self._source_ref = source_ref
        self._path = path

    def __getitem__(self, key: Any) -> Any:
        return self._adapter._view_value(self._source_ref, self._path + (key,))

    def __setitem__(self, key: Any, value: Any) -> None:
        path = self._path

        def mutate(root: dict[str, Any]) -> None:
            target = self._adapter._resolve_path_unlocked(root, path)
            target[key] = deepcopy(value)

        self._adapter._mutate_record(self._source_ref, mutate)

    def __delitem__(self, key: Any) -> None:
        path = self._path

        def mutate(root: dict[str, Any]) -> None:
            target = self._adapter._resolve_path_unlocked(root, path)
            del target[key]

        self._adapter._mutate_record(self._source_ref, mutate)

    def __iter__(self) -> Iterator[Any]:
        snapshot = self._adapter._snapshot_path(self._source_ref, self._path)
        return iter(tuple(snapshot))

    def __len__(self) -> int:
        return len(self._adapter._snapshot_path(self._source_ref, self._path))

    def __deepcopy__(self, memo):
        return deepcopy(self._adapter._snapshot_path(self._source_ref, self._path), memo)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, _NestedMapping):
            other = other._adapter._snapshot_path(other._source_ref, other._path)
        return self._adapter._snapshot_path(self._source_ref, self._path) == other

    def __repr__(self) -> str:
        return repr(self._adapter._snapshot_path(self._source_ref, self._path))


class _NestedList(MutableSequence[Any]):
    def __init__(self, adapter: "InMemorySourceAdapter", source_ref: str, path: tuple[Any, ...]) -> None:
        self._adapter = adapter
        self._source_ref = source_ref
        self._path = path

    def __getitem__(self, index):
        if isinstance(index, slice):
            return deepcopy(self._adapter._snapshot_path(self._source_ref, self._path)[index])
        return self._adapter._view_value(self._source_ref, self._path + (index,))

    def __setitem__(self, index, value) -> None:
        path = self._path

        def mutate(root: dict[str, Any]) -> None:
            target = self._adapter._resolve_path_unlocked(root, path)
            target[index] = deepcopy(value)

        self._adapter._mutate_record(self._source_ref, mutate)

    def __delitem__(self, index) -> None:
        path = self._path

        def mutate(root: dict[str, Any]) -> None:
            target = self._adapter._resolve_path_unlocked(root, path)
            del target[index]

        self._adapter._mutate_record(self._source_ref, mutate)

    def insert(self, index: int, value: Any) -> None:
        path = self._path

        def mutate(root: dict[str, Any]) -> None:
            target = self._adapter._resolve_path_unlocked(root, path)
            target.insert(index, deepcopy(value))

        self._adapter._mutate_record(self._source_ref, mutate)

    def __len__(self) -> int:
        return len(self._adapter._snapshot_path(self._source_ref, self._path))

    def __deepcopy__(self, memo):
        return deepcopy(self._adapter._snapshot_path(self._source_ref, self._path), memo)

    def __repr__(self) -> str:
        return repr(self._adapter._snapshot_path(self._source_ref, self._path))


class InMemorySourceAdapter:
    """Development SourcePort with atomic compare-and-hold revision guards."""

    def __init__(self, records: dict[str, dict[str, Any]]):
        self._lock = RLock()
        self._records = deepcopy(records)
        self._version_tokens = {source_ref: self._new_version_token() for source_ref in self._records}
        self._active_guards: dict[str, RevisionGuard] = {}
        self._guard_generation = 0
        self.records = _RecordStore(self)

    @staticmethod
    def _new_version_token() -> str:
        return f"VT-{uuid4()}"

    @staticmethod
    def _resolve_path_unlocked(root: Any, path: tuple[Any, ...]) -> Any:
        current = root
        for part in path:
            current = current[part]
        return current

    def _snapshot_path(self, source_ref: str, path: tuple[Any, ...]) -> Any:
        with self._lock:
            if source_ref not in self._records:
                raise KeyError(source_ref)
            return deepcopy(self._resolve_path_unlocked(self._records[source_ref], path))

    def _view_value(self, source_ref: str, path: tuple[Any, ...]) -> Any:
        with self._lock:
            if source_ref not in self._records:
                raise KeyError(source_ref)
            value = self._resolve_path_unlocked(self._records[source_ref], path)
            if isinstance(value, dict):
                return _NestedMapping(self, source_ref, path)
            if isinstance(value, list):
                return _NestedList(self, source_ref, path)
            return deepcopy(value)

    def _guard_ids_for_source_unlocked(self, source_ref: str) -> tuple[str, ...]:
        guard_ids = []
        for guard in self._active_guards.values():
            if any(item.source_ref == source_ref for item in guard.protected_versions):
                guard_ids.append(guard.guard_id)
        return tuple(sorted(guard_ids))

    def _assert_mutation_allowed_unlocked(self, source_ref: str) -> None:
        guard_ids = self._guard_ids_for_source_unlocked(source_ref)
        if guard_ids:
            raise RevisionGuardActiveError(source_ref, guard_ids)

    def _bump_version_unlocked(self, source_ref: str) -> None:
        self._version_tokens[source_ref] = self._new_version_token()

    def _mutate_record(self, source_ref: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            if source_ref not in self._records:
                raise KeyError(source_ref)
            self._assert_mutation_allowed_unlocked(source_ref)
            before = deepcopy(self._records[source_ref])
            mutate(self._records[source_ref])
            if self._records[source_ref] != before:
                self._bump_version_unlocked(source_ref)

    def _replace_record(self, source_ref: str, value: dict[str, Any]) -> None:
        with self._lock:
            self._assert_mutation_allowed_unlocked(source_ref)
            replacement = deepcopy(value)
            previous = self._records.get(source_ref)
            if previous != replacement:
                self._records[source_ref] = replacement
                self._bump_version_unlocked(source_ref)

    def _delete_record(self, source_ref: str) -> None:
        with self._lock:
            if source_ref not in self._records:
                raise KeyError(source_ref)
            self._assert_mutation_allowed_unlocked(source_ref)
            del self._records[source_ref]
            self._version_tokens.pop(source_ref, None)

    def read(self, source_ref: str) -> dict[str, Any]:
        with self._lock:
            if source_ref not in self._records:
                raise KeyError(source_ref)
            return deepcopy(self._records[source_ref])

    def read_versioned(self, source_ref: str) -> VersionedRead:
        with self._lock:
            if source_ref not in self._records:
                raise KeyError(source_ref)
            payload = deepcopy(self._records[source_ref])
            revision = payload.get("revision_ref")
            return VersionedRead(
                source_ref=source_ref,
                payload=payload,
                revision_ref=str(revision) if revision is not None else None,
                version_token=self._version_tokens[source_ref],
            )

    def acquire_revision_guard(
        self,
        expected_versions: VersionedReadSet,
        owner_ref: str,
    ) -> RevisionGuard:
        if not owner_ref.strip():
            raise ValueError("owner_ref must be explicit")
        if not expected_versions:
            raise ValueError("expected_versions must not be empty")

        # One lock protects COMPARE ALL + ACQUIRE ALL as one logical operation.
        with self._lock:
            for expected in expected_versions.reads:
                observed = self._version_tokens.get(expected.source_ref)
                if observed != expected.version_token:
                    raise RevisionConflictError(
                        owner_ref=owner_ref,
                        source_ref=expected.source_ref,
                        expected_version_token=expected.version_token,
                        observed_version_token=observed,
                    )

            self._guard_generation += 1
            guard = RevisionGuard(
                guard_id=f"RG-{uuid4()}",
                owner_ref=owner_ref,
                generation=self._guard_generation,
                protected_versions=tuple(
                    GuardedRevision(
                        source_ref=read.source_ref,
                        revision_ref=read.revision_ref,
                        version_token=read.version_token,
                    )
                    for read in expected_versions.reads
                ),
            )
            self._active_guards[guard.guard_id] = guard
            return guard

    def release_revision_guard(self, guard: RevisionGuard) -> None:
        with self._lock:
            active = self._active_guards.get(guard.guard_id)
            if active is None:
                if guard.guard_result == "ACQUIRED":
                    object.__setattr__(guard, "released_at", _utcnow())
                    object.__setattr__(guard, "guard_result", "LOST")
                return
            if active.owner_ref != guard.owner_ref or active.generation != guard.generation:
                object.__setattr__(guard, "released_at", _utcnow())
                object.__setattr__(guard, "guard_result", "LOST")
                return

            del self._active_guards[guard.guard_id]
            if active.guard_result == "ACQUIRED":
                released_at = _utcnow()
                object.__setattr__(active, "released_at", released_at)
                object.__setattr__(active, "guard_result", "RELEASED")
                if guard is not active:
                    object.__setattr__(guard, "released_at", released_at)
                    object.__setattr__(guard, "guard_result", "RELEASED")
