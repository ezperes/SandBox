from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from harness.contracts import Checkpoint, HarnessErrorCode, HarnessRun, RunState
from harness.core.errors import HarnessResolutionError
from harness.ports import RuntimePort, StatePort


class IdempotencyStatus(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(slots=True)
class IdempotencyRecord:
    key: str
    run_id: str
    operation: str
    business_key: str
    status: IdempotencyStatus = IdempotencyStatus.PENDING
    attempt: int = 1
    result: dict[str, Any] | None = None
    evidence_refs: list[str] = field(default_factory=list)
    error: str | None = None
    reconciliation_required: bool = False
    created_at: str = field(default_factory=_utcnow)
    updated_at: str = field(default_factory=_utcnow)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "IdempotencyRecord":
        data = dict(raw)
        data["status"] = IdempotencyStatus(data["status"])
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        return data


class StateManager:
    """Own canonical RunState/Checkpoint persistence and side-effect ledger semantics."""

    def __init__(self, state_port: StatePort):
        self.state_port = state_port

    def persist(self, state: RunState) -> RunState:
        self.state_port.save_run_state(state)
        return state

    def checkpoint(
        self,
        state: RunState,
        *,
        validated_step: str,
        resume_instruction: str,
        artifact_refs: list[str] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> Checkpoint:
        checkpoint = Checkpoint(
            checkpoint_id=f"CP-{uuid4()}",
            run_id=state.run_id,
            run_state_ref=state.run_state_id,
            validated_step=validated_step,
            resume_instruction=resume_instruction,
            artifact_refs=list(artifact_refs or []),
            evidence_refs=list(evidence_refs or []),
        )
        state.checkpoint_ref = checkpoint.checkpoint_id
        self.state_port.save_checkpoint(checkpoint)
        self.state_port.save_run_state(state)
        return checkpoint

    def resume(self, run: HarnessRun, runtime: RuntimePort, checkpoint_id: str, *, freshness_gate=None) -> RunState:
        try:
            checkpoint = self.state_port.load_checkpoint(checkpoint_id)
            state = self.state_port.load_run_state(checkpoint.run_state_ref)
        except KeyError as exc:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                f"checkpoint or run state not found: {exc}",
                checkpoint_id,
            ) from exc

        if checkpoint.run_id != run.run_id or state.run_id != run.run_id:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                "checkpoint/run mismatch",
                checkpoint_id,
            )
        if state.checkpoint_ref != checkpoint_id:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                "run state does not point to requested checkpoint",
                checkpoint_id,
            )

        if freshness_gate is None:
            raise HarnessResolutionError(
                HarnessErrorCode.AUTHORITY_UNRESOLVED,
                "resume requires Core-owned freshness/revalidation before RuntimePort.resume",
                checkpoint_id,
            )

        preparation = freshness_gate.prepare(run)
        run.authority_context_ref = preparation.authority.authority_context_id
        run.task_context_ref = preparation.context.task_context.task_context_id

        resumed = runtime.resume(run, state)
        self.state_port.save_run_state(resumed)
        return resumed

    @staticmethod
    def _effect_key(run_id: str, operation: str, business_key: str) -> str:
        return f"{run_id}:{operation}:{business_key}"

    def begin_side_effect(
        self,
        run_id: str,
        operation: str,
        business_key: str,
        *,
        retry_failed: bool = False,
    ) -> IdempotencyRecord:
        key = self._effect_key(run_id, operation, business_key)
        record = IdempotencyRecord(key=key, run_id=run_id, operation=operation, business_key=business_key)
        if self.state_port.create_idempotency_record(key, record.to_dict()):
            return record

        current = self.get_side_effect(key)
        if current.status == IdempotencyStatus.FAILED and retry_failed:
            current.status = IdempotencyStatus.PENDING
            current.attempt += 1
            current.error = None
            current.reconciliation_required = False
            current.updated_at = _utcnow()
            self.state_port.update_idempotency_record(key, current.to_dict())
            return current

        reason = {
            IdempotencyStatus.PENDING: "side effect already pending; reconciliation required before retry",
            IdempotencyStatus.COMPLETED: "side effect already completed; duplicate execution blocked",
            IdempotencyStatus.UNKNOWN: "side effect outcome unknown; reconciliation required before retry",
            IdempotencyStatus.FAILED: "side effect failed; retry requires explicit retry_failed=True",
        }[current.status]
        raise HarnessResolutionError(HarnessErrorCode.RETRY_BLOCKED, reason, key)

    def get_side_effect(self, key: str) -> IdempotencyRecord:
        return IdempotencyRecord.from_dict(self.state_port.load_idempotency_record(key))

    def complete_side_effect(
        self,
        key: str,
        *,
        result: dict[str, Any] | None = None,
        evidence_refs: list[str] | None = None,
    ) -> IdempotencyRecord:
        record = self.get_side_effect(key)
        record.status = IdempotencyStatus.COMPLETED
        record.result = dict(result or {})
        record.evidence_refs = list(evidence_refs or [])
        record.error = None
        record.reconciliation_required = False
        record.updated_at = _utcnow()
        self.state_port.update_idempotency_record(key, record.to_dict())
        return record

    def fail_side_effect(self, key: str, error: str, *, outcome_unknown: bool = False) -> IdempotencyRecord:
        record = self.get_side_effect(key)
        record.status = IdempotencyStatus.UNKNOWN if outcome_unknown else IdempotencyStatus.FAILED
        record.error = error
        record.reconciliation_required = outcome_unknown
        record.updated_at = _utcnow()
        self.state_port.update_idempotency_record(key, record.to_dict())
        return record

    def reconcile_side_effect(
        self,
        key: str,
        *,
        completed: bool,
        result: dict[str, Any] | None = None,
        evidence_refs: list[str] | None = None,
        error: str | None = None,
    ) -> IdempotencyRecord:
        record = self.get_side_effect(key)
        if record.status not in {IdempotencyStatus.PENDING, IdempotencyStatus.UNKNOWN}:
            raise ValueError("only PENDING/UNKNOWN side effects may be reconciled")
        if completed:
            return self.complete_side_effect(key, result=result, evidence_refs=evidence_refs)
        record.status = IdempotencyStatus.FAILED
        record.error = error or "reconciliation confirmed no completed side effect"
        record.reconciliation_required = False
        record.updated_at = _utcnow()
        self.state_port.update_idempotency_record(key, record.to_dict())
        return record
