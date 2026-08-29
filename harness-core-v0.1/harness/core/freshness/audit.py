from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from harness.contracts import AuthoritySnapshot, ChainType, TaskContext
from harness.core.context import BootstrapResolution, ContextBuildResult


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class RevalidationAuditRecord:
    """Persistable audit evidence for a Core-owned freshness/revalidation boundary.

    This is an internal Core record, not a canonical institutional contract in V0.1.
    It preserves the exact authority snapshot, Bootstrap trace and TaskContext used
    to release a sensitive boundary such as RuntimePort.resume().
    """

    revalidation_id: str
    run_id: str
    boundary: str
    previous_authority_context_ref: str
    previous_task_context_ref: str | None
    authority_snapshot: dict[str, Any]
    authority_context_ref: str
    task_context: dict[str, Any]
    bootstrap_trace: dict[str, Any]
    changed_chains: tuple[str, ...]
    identity_changed: bool
    created_at: str = field(default_factory=_utcnow)

    @classmethod
    def from_preparation(
        cls,
        *,
        run_id: str,
        boundary: str,
        previous_authority_context_ref: str,
        previous_task_context_ref: str | None,
        authority_snapshot: AuthoritySnapshot,
        authority_context_ref: str,
        context: ContextBuildResult,
        changed_chains: frozenset[ChainType],
        identity_changed: bool,
    ) -> "RevalidationAuditRecord":
        bootstrap: BootstrapResolution = context.bootstrap
        return cls(
            revalidation_id=f"RV-{uuid4()}",
            run_id=run_id,
            boundary=boundary,
            previous_authority_context_ref=previous_authority_context_ref,
            previous_task_context_ref=previous_task_context_ref,
            authority_snapshot=authority_snapshot.model_dump(mode="json"),
            authority_context_ref=authority_context_ref,
            task_context=context.task_context.model_dump(mode="json"),
            bootstrap_trace={
                "trace_id": bootstrap.trace_id,
                "tactical_refs": list(bootstrap.tactical_refs),
                "technical_refs": list(bootstrap.technical_refs),
                "normative_refs": list(bootstrap.normative_refs),
            },
            changed_chains=tuple(sorted(chain.value for chain in changed_chains)),
            identity_changed=identity_changed,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
