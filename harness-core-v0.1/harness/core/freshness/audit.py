from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from harness.contracts import AuthorityContext, AuthoritySnapshot, ChainType
from harness.core.context import BootstrapResolution, ContextBuildResult
from harness.core.errors import HarnessResolutionError


_RUNTIME_RESUME_BOUNDARY = "RuntimePort.resume"
_RUNTIME_RESUME_RELEASE_OUTCOME = "REVALIDATED_AND_GUARDED"
_RUNTIME_RESUME_SUCCESS_OUTCOME = "COMPLETED"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bootstrap_dump(context: ContextBuildResult | None) -> dict[str, Any]:
    if context is None:
        return {}
    bootstrap: BootstrapResolution = context.bootstrap
    return {
        "trace_id": bootstrap.trace_id,
        "tactical_refs": list(bootstrap.tactical_refs),
        "technical_refs": list(bootstrap.technical_refs),
        "normative_refs": list(bootstrap.normative_refs),
    }


def _revision_lineage(authority: AuthorityContext | None) -> dict[str, list[str]]:
    if authority is None:
        return {}
    return {
        "tactical": list(authority.tactical_chain_trace.source_revision_refs) if authority.tactical_chain_trace else [],
        "technical": list(authority.technical_chain_trace.source_revision_refs) if authority.technical_chain_trace else [],
        "normative": list(authority.normative_chain_trace.source_revision_refs) if authority.normative_chain_trace else [],
    }


def begin_boundary_audit(
    *,
    run_id: str,
    boundary: str,
    previous_authority_context_ref: str | None,
    previous_task_context_ref: str | None = None,
    previous_authority: AuthorityContext | None = None,
    previous_context: ContextBuildResult | None = None,
    correlation_id: str | None = None,
    checkpoint_ref: str | None = None,
    agent_id: str | None = None,
    tarefa_trabalho_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create the persisted PENDING record before a sensitive boundary check.

    The record intentionally stores the prior authority/context lineage by value,
    so a later BLOCKED/FAILED result remains reconstructible even if canonical
    sources change again after the attempt. Execution identity is recorded
    explicitly when the Core boundary has canonical HarnessRun/TaskContext data.
    """
    now = _utcnow()
    revalidation_id = f"RV-{uuid4()}"
    return {
        "revalidation_id": revalidation_id,
        "run_id": run_id,
        "agent_id": agent_id,
        "tarefa_trabalho_id": tarefa_trabalho_id,
        "correlation_id": correlation_id,
        "boundary": boundary,
        "status": "PENDING",
        "outcome": None,
        "decision": None,
        "previous_authority_context_ref": previous_authority_context_ref,
        "previous_task_context_ref": previous_task_context_ref,
        "previous_authority_snapshot_ref": previous_authority.authority_snapshot_ref if previous_authority else None,
        "previous_authority_context": previous_authority.model_dump(mode="json") if previous_authority else {},
        "previous_task_context": previous_context.task_context.model_dump(mode="json") if previous_context else {},
        "previous_bootstrap_trace": _bootstrap_dump(previous_context),
        "previous_revision_refs": _revision_lineage(previous_authority),
        "authority_snapshot": {},
        "authority_context_ref": None,
        "task_context": {},
        "bootstrap_trace": {},
        "changed_chains": (),
        "identity_changed": False,
        "freshness_checks": [],
        "checkpoint_ref": checkpoint_ref,
        "error_code": None,
        "error_message": None,
        "error_source_ref": None,
        "metadata": deepcopy(metadata or {}),
        "events": [{"status": "PENDING", "at": now}],
        "created_at": now,
        "updated_at": now,
    }


def finalize_boundary_audit(
    record: dict[str, Any],
    *,
    status: str,
    outcome: str | None = None,
    decision: str | None = None,
    error: BaseException | None = None,
    authority_snapshot: AuthoritySnapshot | None = None,
    authority_context_ref: str | None = None,
    context: ContextBuildResult | None = None,
    changed_chains: frozenset[ChainType] | set[ChainType] | None = None,
    identity_changed: bool | None = None,
    freshness_checks: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    updated = deepcopy(record)
    updated["status"] = status
    updated["outcome"] = outcome
    updated["decision"] = decision
    if authority_snapshot is not None:
        updated["authority_snapshot"] = authority_snapshot.model_dump(mode="json")
    if authority_context_ref is not None:
        updated["authority_context_ref"] = authority_context_ref
    if context is not None:
        updated["task_context"] = context.task_context.model_dump(mode="json")
        updated["bootstrap_trace"] = _bootstrap_dump(context)
    if changed_chains is not None:
        updated["changed_chains"] = tuple(sorted(chain.value for chain in changed_chains))
    if identity_changed is not None:
        updated["identity_changed"] = identity_changed
    if freshness_checks is not None:
        updated["freshness_checks"] = [deepcopy(item) for item in freshness_checks]
    if metadata:
        updated["metadata"].update(deepcopy(metadata))
    if error is not None:
        if isinstance(error, HarnessResolutionError):
            updated["error_code"] = error.code.value
            updated["error_source_ref"] = error.source_ref
            updated["error_message"] = error.message
        else:
            updated["error_code"] = type(error).__name__
            updated["error_message"] = str(error)
    now = _utcnow()
    updated["events"].append({"status": status, "at": now, "outcome": outcome, "decision": decision})
    updated["updated_at"] = now
    return updated


def finalize_runtime_resume_success(record: dict[str, Any]) -> dict[str, Any]:
    """Append the terminal success event for a Core-owned Runtime resume trace.

    This function is intentionally pure: it does not persist anything and it does
    not invoke the Runtime. The caller may use it only after RuntimePort.resume()
    returned, the runtime result passed the Core firewall/validation, and the
    accepted canonical RunState was persisted successfully.

    The function fails closed unless the supplied record is exactly the released
    Runtime resume state produced immediately before the sensitive boundary:
    RELEASED / REVALIDATED_AND_GUARDED. A repeated call on an already valid
    terminal COMPLETED record is idempotent and does not append a duplicate event.
    """
    current = deepcopy(record)
    events = current.get("events")
    if current.get("boundary") != _RUNTIME_RESUME_BOUNDARY:
        raise ValueError("runtime terminal success requires RuntimePort.resume boundary")
    if not isinstance(events, list) or not events:
        raise ValueError("runtime terminal success requires an existing audit event history")

    if current.get("outcome") == _RUNTIME_RESUME_SUCCESS_OUTCOME:
        last = events[-1]
        if current.get("status") == "RELEASED" and last.get("outcome") == _RUNTIME_RESUME_SUCCESS_OUTCOME:
            return current
        raise ValueError("runtime audit has inconsistent COMPLETED terminal state")

    if current.get("status") != "RELEASED" or current.get("outcome") != _RUNTIME_RESUME_RELEASE_OUTCOME:
        raise ValueError("runtime terminal success requires RELEASED / REVALIDATED_AND_GUARDED")

    if any(
        event.get("status") in {"FAILED", "BLOCKED"}
        or event.get("outcome") == _RUNTIME_RESUME_SUCCESS_OUTCOME
        for event in events
    ):
        raise ValueError("runtime terminal success cannot follow a failed, blocked, or completed history")

    return finalize_boundary_audit(
        current,
        status="RELEASED",
        outcome=_RUNTIME_RESUME_SUCCESS_OUTCOME,
    )


@dataclass(frozen=True, slots=True)
class RevalidationAuditRecord:
    """Compatibility view for successful Core-owned resume revalidation evidence."""

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
    status: str = "RELEASED"
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
        return cls(
            revalidation_id=f"RV-{uuid4()}",
            run_id=run_id,
            boundary=boundary,
            previous_authority_context_ref=previous_authority_context_ref,
            previous_task_context_ref=previous_task_context_ref,
            authority_snapshot=authority_snapshot.model_dump(mode="json"),
            authority_context_ref=authority_context_ref,
            task_context=context.task_context.model_dump(mode="json"),
            bootstrap_trace=_bootstrap_dump(context),
            changed_chains=tuple(sorted(chain.value for chain in changed_chains)),
            identity_changed=identity_changed,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
