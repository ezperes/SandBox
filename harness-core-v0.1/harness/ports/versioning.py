from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class VersionedRead:
    """Technical SourcePort read coupled to the mechanical version observed."""

    source_ref: str
    payload: dict[str, Any]
    revision_ref: str | None
    version_token: str

    def audit_data(self) -> dict[str, Any]:
        return {
            "source_ref": self.source_ref,
            "revision_ref": self.revision_ref,
            "version_token": self.version_token,
        }


@dataclass(slots=True)
class VersionedReadSet:
    """Exact set of canonical sources materially used by one Core operation."""

    _reads: dict[str, VersionedRead] = field(default_factory=dict, repr=False)

    def add(self, read: VersionedRead) -> VersionedRead:
        current = self._reads.get(read.source_ref)
        if current is not None and current != read:
            raise ValueError(
                f"source {read.source_ref!r} changed while building VersionedReadSet"
            )
        self._reads[read.source_ref] = read
        return read

    def extend(self, reads: Iterable[VersionedRead]) -> "VersionedReadSet":
        for read in reads:
            self.add(read)
        return self

    def get(self, source_ref: str) -> VersionedRead | None:
        return self._reads.get(source_ref)

    @property
    def reads(self) -> tuple[VersionedRead, ...]:
        return tuple(self._reads[key] for key in sorted(self._reads))

    @property
    def expected_versions(self) -> dict[str, str]:
        return {read.source_ref: read.version_token for read in self.reads}

    def audit_data(self) -> list[dict[str, Any]]:
        return [read.audit_data() for read in self.reads]

    def __len__(self) -> int:
        return len(self._reads)

    def __bool__(self) -> bool:
        return bool(self._reads)


@dataclass(frozen=True, slots=True)
class _GuardedRevision:
    source_ref: str
    revision_ref: str | None
    version_token: str


@dataclass(frozen=True, slots=True)
class RevisionGuard:
    """Opaque fencing token proving an atomic compare-and-hold acquisition."""

    guard_id: str
    owner_ref: str
    generation: int
    protected_versions: tuple[_GuardedRevision, ...]
    acquired_at: str = field(default_factory=_utcnow)
    released_at: str | None = None
    guard_result: str = "ACQUIRED"

    def audit_data(self) -> dict[str, Any]:
        return {
            "guard_id": self.guard_id,
            "guard_owner_ref": self.owner_ref,
            "guard_generation": self.generation,
            "protected_versions": [
                {
                    "source_ref": item.source_ref,
                    "revision_ref": item.revision_ref,
                    "version_token": item.version_token,
                }
                for item in self.protected_versions
            ],
            "guard_acquired_at": self.acquired_at,
            "guard_released_at": self.released_at,
            "guard_result": self.guard_result,
            "conflict_source_ref": None,
            "expected_version_token": None,
            "observed_version_token": None,
        }


class RevisionConflictError(RuntimeError):
    """Atomic guard acquisition failed because at least one version changed."""

    def __init__(
        self,
        *,
        owner_ref: str,
        source_ref: str,
        expected_version_token: str,
        observed_version_token: str | None,
    ) -> None:
        self.owner_ref = owner_ref
        self.source_ref = source_ref
        self.expected_version_token = expected_version_token
        self.observed_version_token = observed_version_token
        super().__init__(
            "REVISION_CONFLICT: "
            f"{source_ref} expected {expected_version_token!r}, "
            f"observed {observed_version_token!r}"
        )

    def audit_data(self) -> dict[str, Any]:
        return {
            "guard_id": None,
            "guard_owner_ref": self.owner_ref,
            "guard_generation": None,
            "protected_versions": [],
            "guard_acquired_at": None,
            "guard_released_at": None,
            "guard_result": "REVISION_CONFLICT",
            "conflict_source_ref": self.source_ref,
            "expected_version_token": self.expected_version_token,
            "observed_version_token": self.observed_version_token,
        }


class RevisionGuardActiveError(RuntimeError):
    """A material source mutation was rejected while a guard protects it."""

    def __init__(self, source_ref: str, guard_ids: tuple[str, ...]) -> None:
        self.source_ref = source_ref
        self.guard_ids = guard_ids
        super().__init__(
            f"source {source_ref!r} is protected by active revision guard(s): "
            + ", ".join(guard_ids)
        )
