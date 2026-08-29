from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from harness.contracts import Checkpoint, HarnessErrorCode, HarnessRun, RunState, RunStatus
from harness.core.errors import HarnessResolutionError
from harness.core.freshness.audit import begin_boundary_audit, finalize_boundary_audit
from harness.core.freshness.resume import ResumeFreshnessGate
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

    RESUMABLE_STATUSES = frozenset({RunStatus.INTERRUPTED})

    def __init__(self, state_port: StatePort):
        self.state_port = state_port

    def persist(self, state: RunState) -> RunState:
        self.state_port.save_run_state(state)
        return state

    def checkpoint(self, state: RunState, *, validated_step: str, resume_instruction: str,
                   artifact_refs: list[str] | None = None, evidence_refs: list[str] | None = None) -> Checkpoint:
        checkpoint = Checkpoint(
            checkpoint_id=f"CP-{uuid4()}", run_id=state.run_id, run_state_ref=state.run_state_id,
            validated_step=validated_step, resume_instruction=resume_instruction,
            artifact_refs=list(artifact_refs or []), evidence_refs=list(evidence_refs or []),
        )
        state.checkpoint_ref = checkpoint.checkpoint_id
        self.state_port.save_checkpoint(checkpoint)
        self.state_port.save_run_state(state)
        return checkpoint

    @staticmethod
    def _checkpoint_invalid(message: str, checkpoint_id: str) -> HarnessResolutionError:
        return HarnessResolutionError(HarnessErrorCode.CHECKPOINT_INVALID, message, checkpoint_id)

    def _validate_resume_binding(self, run: HarnessRun, checkpoint: Checkpoint, state: RunState, checkpoint_id: str) -> None:
        if checkpoint.run_id != run.run_id:
            raise self._checkpoint_invalid("checkpoint does not belong to run", checkpoint_id)
        if checkpoint.run_state_ref != state.run_state_id:
            raise self._checkpoint_invalid("checkpoint run_state_ref does not match loaded RunState", checkpoint_id)
        if state.run_state_id != run.run_state_ref:
            raise self._checkpoint_invalid("RunState does not match HarnessRun.run_state_ref", checkpoint_id)
        if state.run_id != run.run_id:
            raise self._checkpoint_invalid("RunState does not belong to run", checkpoint_id)
        if state.tarefa_trabalho_id != run.tarefa_trabalho_id:
            raise self._checkpoint_invalid("RunState task does not match HarnessRun task", checkpoint_id)
        if state.checkpoint_ref != checkpoint_id:
            raise self._checkpoint_invalid("RunState does not point to requested checkpoint", checkpoint_id)
        if state.status not in self.RESUMABLE_STATUSES:
            raise self._checkpoint_invalid(f"RunState status {state.status.value} is not resumable in Harness V0.1", checkpoint_id)

    @staticmethod
    def _merge_runtime_state(canonical: RunState, runtime_state: RunState) -> RunState:
        if not isinstance(runtime_state, RunState):
            raise TypeError("RuntimePort.resume must return RunState")
        return RunState(
            run_state_id=canonical.run_state_id, run_id=canonical.run_id,
            tarefa_trabalho_id=canonical.tarefa_trabalho_id, status=runtime_state.status,
            current_step=runtime_state.current_step, completed_steps=list(runtime_state.completed_steps),
            pending_steps=list(runtime_state.pending_steps), artifact_refs=list(runtime_state.artifact_refs),
            decision_refs=list(canonical.decision_refs), checkpoint_ref=canonical.checkpoint_ref,
        )

    def resume(self, run: HarnessRun, runtime: RuntimePort, checkpoint_id: str, *,
               freshness_gate: ResumeFreshnessGate | None = None) -> RunState:
        try:
            checkpoint = self.state_port.load_checkpoint(checkpoint_id)
            state = self.state_port.load_run_state(checkpoint.run_state_ref)
        except KeyError as exc:
            raise self._checkpoint_invalid(f"checkpoint or run state not found: {exc}", checkpoint_id) from exc

        self._validate_resume_binding(run, checkpoint, state, checkpoint_id)

        valid_gate = freshness_gate if type(freshness_gate) is ResumeFreshnessGate else None
        audit = begin_boundary_audit(
            run_id=run.run_id, correlation_id=run.correlation_id, boundary="RuntimePort.resume",
            checkpoint_ref=checkpoint_id, previous_authority_context_ref=run.authority_context_ref,
            previous_task_context_ref=run.task_context_ref,
            previous_authority=valid_gate.previous_authority if valid_gate else None,
            previous_context=valid_gate.previous_context if valid_gate else None,
            metadata={
                "identity_source_ref": valid_gate.identity_source_ref if valid_gate else None,
                "task_source_ref": valid_gate.task_source_ref if valid_gate else None,
                "previous_identity_revision_ref": valid_gate.previous_identity_revision_ref if valid_gate else None,
            },
        )
        self.state_port.save_revalidation_record(audit["revalidation_id"], audit)
        if audit["revalidation_id"] not in state.decision_refs:
            state.decision_refs.append(audit["revalidation_id"])
        self.state_port.save_run_state(state)

        if valid_gate is None:
            exc = HarnessResolutionError(HarnessErrorCode.AUTHORITY_UNRESOLVED,
                "resume requires the canonical Core ResumeFreshnessGate before RuntimePort.resume", checkpoint_id)
            self.state_port.save_revalidation_record(audit["revalidation_id"],
                finalize_boundary_audit(audit, status="BLOCKED", outcome="FRESHNESS_GATE_INVALID", error=exc))
            raise exc

        try:
            valid_gate.validate_provenance(run)
            preparation = valid_gate.prepare(run)
        except HarnessResolutionError as exc:
            self.state_port.save_revalidation_record(audit["revalidation_id"],
                finalize_boundary_audit(audit, status="BLOCKED", outcome="FRESHNESS_REJECTED", error=exc))
            raise
        except Exception as exc:
            self.state_port.save_revalidation_record(audit["revalidation_id"],
                finalize_boundary_audit(audit, status="FAILED", outcome="FRESHNESS_ERROR", error=exc))
            raise

        if not self.state_port.consume_checkpoint_ref(state.run_state_id, checkpoint_id):
            exc = self._checkpoint_invalid("checkpoint was already consumed", checkpoint_id)
            self.state_port.save_revalidation_record(audit["revalidation_id"],
                finalize_boundary_audit(audit, status="BLOCKED", outcome="CHECKPOINT_ALREADY_CONSUMED", error=exc))
            raise exc
        state.checkpoint_ref = None

        released = finalize_boundary_audit(
            audit, status="RELEASED", outcome="REVALIDATED",
            authority_snapshot=preparation.authority_snapshot,
            authority_context_ref=preparation.authority.authority_context_id,
            context=preparation.context, changed_chains=preparation.changed_chains,
            identity_changed=preparation.identity_changed, metadata={"checkpoint_consumed": True},
        )
        self.state_port.save_revalidation_record(audit["revalidation_id"], released)
        run.authority_context_ref = preparation.authority.authority_context_id
        run.task_context_ref = preparation.context.task_context.task_context_id

        canonical_state = state.model_copy(deep=True)
        try:
            runtime_state = runtime.resume(run, canonical_state.model_copy(deep=True))
            resumed = self._merge_runtime_state(canonical_state, runtime_state)
        except Exception as exc:
            self.state_port.save_revalidation_record(audit["revalidation_id"],
                finalize_boundary_audit(released, status="FAILED", outcome="RUNTIME_RESUME_ERROR", error=exc))
            raise
        self.state_port.save_run_state(resumed)
        return resumed

    @staticmethod
    def _effect_key(run_id: str, operation: str, business_key: str) -> str:
        return f"{run_id}:{operation}:{business_key}"

    def begin_side_effect(self, run_id: str, operation: str, business_key: str, *, retry_failed: bool = False) -> IdempotencyRecord:
        key = self._effect_key(run_id, operation, business_key)
        record = IdempotencyRecord(key=key, run_id=run_id, operation=operation, business_key=business_key)
        if self.state_port.create_idempotency_record(key, record.to_dict()): return record
        current = self.get_side_effect(key)
        if current.status == IdempotencyStatus.FAILED and retry_failed:
            current.status = IdempotencyStatus.PENDING; current.attempt += 1; current.error = None
            current.reconciliation_required = False; current.updated_at = _utcnow()
            self.state_port.update_idempotency_record(key, current.to_dict()); return current
        reason = {IdempotencyStatus.PENDING:"side effect already pending; reconciliation required before retry",
                  IdempotencyStatus.COMPLETED:"side effect already completed; duplicate execution blocked",
                  IdempotencyStatus.UNKNOWN:"side effect outcome unknown; reconciliation required before retry",
                  IdempotencyStatus.FAILED:"side effect failed; retry requires explicit retry_failed=True"}[current.status]
        raise HarnessResolutionError(HarnessErrorCode.RETRY_BLOCKED, reason, key)

    def get_side_effect(self, key: str) -> IdempotencyRecord:
        return IdempotencyRecord.from_dict(self.state_port.load_idempotency_record(key))

    def complete_side_effect(self, key: str, *, result: dict[str, Any] | None = None,
                             evidence_refs: list[str] | None = None) -> IdempotencyRecord:
        record = self.get_side_effect(key); record.status = IdempotencyStatus.COMPLETED
        record.result = dict(result or {}); record.evidence_refs = list(evidence_refs or [])
        record.error = None; record.reconciliation_required = False; record.updated_at = _utcnow()
        self.state_port.update_idempotency_record(key, record.to_dict()); return record

    def fail_side_effect(self, key: str, error: str, *, outcome_unknown: bool = False) -> IdempotencyRecord:
        record = self.get_side_effect(key); record.status = IdempotencyStatus.UNKNOWN if outcome_unknown else IdempotencyStatus.FAILED
        record.error = error; record.reconciliation_required = outcome_unknown; record.updated_at = _utcnow()
        self.state_port.update_idempotency_record(key, record.to_dict()); return record

    def reconcile_side_effect(self, key: str, *, completed: bool, result: dict[str, Any] | None = None,
                              evidence_refs: list[str] | None = None, error: str | None = None) -> IdempotencyRecord:
        record = self.get_side_effect(key)
        if record.status not in {IdempotencyStatus.PENDING, IdempotencyStatus.UNKNOWN}:
            raise ValueError("only PENDING/UNKNOWN side effects may be reconciled")
        if completed: return self.complete_side_effect(key, result=result, evidence_refs=evidence_refs)
        record.status = IdempotencyStatus.FAILED; record.error = error or "reconciliation confirmed no completed side effect"
        record.reconciliation_required = False; record.updated_at = _utcnow()
        self.state_port.update_idempotency_record(key, record.to_dict()); return record
