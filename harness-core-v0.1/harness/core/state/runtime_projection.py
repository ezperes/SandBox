from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping

from harness.contracts import RunState, RunStatus


class RunStateOwnership(StrEnum):
    CORE_OWNED = "CORE_OWNED"
    RUNTIME_OWNED = "RUNTIME_OWNED"
    DERIVED_CONTROLLED = "DERIVED/CONTROLLED"


RUN_STATE_OWNERSHIP: dict[str, RunStateOwnership] = {
    "harness_contract_version": RunStateOwnership.DERIVED_CONTROLLED,
    "run_state_id": RunStateOwnership.CORE_OWNED,
    "run_id": RunStateOwnership.CORE_OWNED,
    "tarefa_trabalho_id": RunStateOwnership.CORE_OWNED,
    "status": RunStateOwnership.DERIVED_CONTROLLED,
    "current_step": RunStateOwnership.RUNTIME_OWNED,
    "completed_steps": RunStateOwnership.RUNTIME_OWNED,
    "pending_steps": RunStateOwnership.RUNTIME_OWNED,
    "artifact_refs": RunStateOwnership.RUNTIME_OWNED,
    "decision_refs": RunStateOwnership.CORE_OWNED,
    "checkpoint_ref": RunStateOwnership.CORE_OWNED,
    "updated_at": RunStateOwnership.DERIVED_CONTROLLED,
}

CORE_OWNED_FIELDS = frozenset(
    field for field, owner in RUN_STATE_OWNERSHIP.items() if owner is RunStateOwnership.CORE_OWNED
)
RUNTIME_OWNED_FIELDS = frozenset(
    field for field, owner in RUN_STATE_OWNERSHIP.items() if owner is RunStateOwnership.RUNTIME_OWNED
)
DERIVED_CONTROLLED_FIELDS = frozenset(
    field for field, owner in RUN_STATE_OWNERSHIP.items() if owner is RunStateOwnership.DERIVED_CONTROLLED
)

# Approval/rework/cancellation are institutional control transitions, not runtime
# decisions. The runtime may only report execution lifecycle outcomes.
RUNTIME_REPORTABLE_STATUSES = frozenset(
    {
        RunStatus.RUNNING,
        RunStatus.INTERRUPTED,
        RunStatus.WAITING_EXTERNAL,
        RunStatus.FAILED,
        RunStatus.COMPLETED,
    }
)


class RuntimeStateViolation(ValueError):
    """Runtime attempted to cross the Core-owned RunState boundary."""


def _assert_ownership_is_complete() -> None:
    contract_fields = set(RunState.model_fields)
    classified_fields = set(RUN_STATE_OWNERSHIP)
    missing = sorted(contract_fields - classified_fields)
    stale = sorted(classified_fields - contract_fields)
    if missing or stale:
        raise RuntimeError(
            "RunState ownership matrix must be updated with the contract; "
            f"missing={missing}, stale={stale}"
        )


_assert_ownership_is_complete()


def project_runtime_payload(state: RunState) -> dict[str, Any]:
    """Project canonical RunState into the technical subset visible as runtime state."""

    raw = state.model_dump(mode="python")
    allowed = RUNTIME_OWNED_FIELDS | {"status"}
    return {field: deepcopy(raw[field]) for field in allowed}


def validate_runtime_core_fields_unchanged(
    canonical: RunState,
    runtime_result: RunState | Mapping[str, Any],
) -> None:
    """Reject an explicit attempt to return different Core-owned state identity.

    ``merge_runtime_result`` remains a tolerant allow-list merger for direct
    projection use, preserving the F4 worker contract. The sensitive resume
    boundary calls this validator first so a hostile runtime cannot silently probe
    or attempt to rewrite canonical run/task/checkpoint/decision identity.
    """

    if isinstance(runtime_result, RunState):
        incoming = runtime_result.model_dump(mode="python")
    elif isinstance(runtime_result, Mapping):
        incoming = dict(runtime_result)
    else:
        raise TypeError("runtime result must be RunState or mapping")

    for field in sorted(CORE_OWNED_FIELDS.intersection(incoming)):
        if incoming[field] != getattr(canonical, field):
            raise RuntimeStateViolation(
                f"runtime attempted to override Core-owned field {field!r}"
            )


def merge_runtime_result(
    canonical: RunState,
    runtime_result: RunState | Mapping[str, Any],
) -> RunState:
    """Merge runtime output into canonical RunState using an explicit allow-list.

    - CORE_OWNED fields are always preserved from ``canonical`` even if the runtime
      returns conflicting values.
    - RUNTIME_OWNED fields may be updated and are revalidated through RunState.
    - ``status`` is accepted only for execution statuses the runtime is allowed to
      report.
    - contract version and ``updated_at`` are Core-controlled and runtime values are
      ignored.
    - unknown keys fail closed so new runtime payload cannot silently gain write
      authority.
    """

    if isinstance(runtime_result, RunState):
        incoming = runtime_result.model_dump(mode="python")
    elif isinstance(runtime_result, Mapping):
        incoming = dict(runtime_result)
    else:
        raise TypeError("runtime result must be RunState or mapping")

    unknown = sorted(set(incoming) - set(RUN_STATE_OWNERSHIP))
    if unknown:
        raise RuntimeStateViolation(f"unknown runtime state fields are forbidden: {unknown}")

    updates: dict[str, Any] = {}
    for field, value in incoming.items():
        ownership = RUN_STATE_OWNERSHIP[field]
        if ownership is RunStateOwnership.CORE_OWNED:
            continue
        if ownership is RunStateOwnership.RUNTIME_OWNED:
            updates[field] = deepcopy(value)
            continue
        if field == "status":
            try:
                status = value if isinstance(value, RunStatus) else RunStatus(value)
            except (TypeError, ValueError) as exc:
                raise RuntimeStateViolation(f"invalid runtime status: {value!r}") from exc
            if status not in RUNTIME_REPORTABLE_STATUSES:
                raise RuntimeStateViolation(f"runtime cannot control institutional status: {status.value}")
            updates[field] = status
        # harness_contract_version and updated_at are deliberately ignored.

    merged = canonical.model_dump(mode="python")
    merged.update(updates)
    merged["updated_at"] = datetime.now(timezone.utc)
    return RunState.model_validate(merged)
