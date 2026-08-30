from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from harness.ports import RevisionGuard, SourcePort, VersionedRead, VersionedReadSet


class StrongRevisionGuardUnavailable(RuntimeError):
    """Sensitive Core use cannot proceed without a strong SourcePort guard."""


def _require_callable(source: object, name: str):
    method = getattr(source, name, None)
    if not callable(method):
        raise StrongRevisionGuardUnavailable(
            f"SourcePort does not provide strong revision guard capability: {name}"
        )
    return method


def read_versioned_for_sensitive_use(
    source: SourcePort,
    source_ref: str,
    read_set: VersionedReadSet,
) -> VersionedRead:
    """Read one materially used source and accumulate its mechanical version."""

    read_versioned = _require_callable(source, "read_versioned")
    observed = read_versioned(source_ref)
    if not isinstance(observed, VersionedRead):
        raise StrongRevisionGuardUnavailable(
            "SourcePort.read_versioned() did not return VersionedRead"
        )
    read_set.add(observed)
    return observed


def acquire_strong_revision_guard(
    source: SourcePort,
    read_set: VersionedReadSet,
    *,
    owner_ref: str,
) -> RevisionGuard:
    """Fail closed unless the adapter can atomically compare-and-hold all reads."""

    if not owner_ref.strip():
        raise ValueError("owner_ref must be explicit")
    if not read_set:
        raise StrongRevisionGuardUnavailable(
            "sensitive use requires a non-empty VersionedReadSet"
        )

    acquire = _require_callable(source, "acquire_revision_guard")
    _require_callable(source, "release_revision_guard")
    guard = acquire(read_set, owner_ref)
    if not isinstance(guard, RevisionGuard) or guard.guard_result != "ACQUIRED":
        raise StrongRevisionGuardUnavailable(
            "SourcePort did not return an acquired strong RevisionGuard"
        )
    return guard


def release_strong_revision_guard(source: SourcePort, guard: RevisionGuard) -> None:
    release = _require_callable(source, "release_revision_guard")
    release(guard)


@contextmanager
def hold_strong_revision_guard(
    source: SourcePort,
    read_set: VersionedReadSet,
    *,
    owner_ref: str,
) -> Iterator[RevisionGuard]:
    """Core-owned lifetime wrapper: no sensitive boundary before acquisition."""

    guard = acquire_strong_revision_guard(source, read_set, owner_ref=owner_ref)
    try:
        yield guard
    finally:
        release_strong_revision_guard(source, guard)
