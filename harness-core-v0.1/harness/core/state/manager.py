from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from harness.contracts import Checkpoint, HarnessErrorCode, HarnessRun, RunState
from harness.core.errors import HarnessResolutionError
from harness.core.freshness.audit import begin_boundary_audit, finalize_boundary_audit
from harness.core.freshness.resume import ResumeFreshnessGate
from harness.core.freshness.revision_guard import StrongRevisionGuardUnavailable, hold_strong_revision_guard
from harness.ports import RuntimePort, StatePort
from harness.ports.versioning import RevisionConflictError

from .binding import RunStateBindingGuard
from .resume_policy import require_resume_status_allowed
from .runtime_projection import CORE_OWNED_FIELDS, merge_runtime_result


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

    @staticmethod
    def _reject_runtime_core_owned_mutation(
        canonical: RunState,
        runtime_result: RunState,
        checkpoint_id: str,
    ) -> None:
        """Reject forged canonical identity while preserving F4 projection semantics.

        F4 deliberately strips conflicting Core-owned decision/checkpoint fields at
        merge time. At the sensitive RuntimePort.resume boundary we additionally
        reject attempts to replace canonical state/run/task identity, because such
        a result is a foreign RunState rather than merely excess technical output.
        """

        identity_fields = {"run_state_id", "run_id", "tarefa_trabalho_id"}
        assert identity_fields <= CORE_OWNED_FIELDS
        for field_name in identity_fields:
            if getattr(runtime_result, field_name) != getattr(canonical, field_name):
                raise HarnessResolutionError(
                    HarnessErrorCode.CHECKPOINT_INVALID,
                    f"runtime attempted to alter canonical RunState identity field: {field_name}",
                    checkpoint_id,
                )

    def resume(
        self,
        run: HarnessRun,
        runtime: RuntimePort,
        checkpoint_id: str,
        *,
        freshness_gate: ResumeFreshnessGate | None = None,
    ) -> RunState:
        try:
            checkpoint = self.state_port.load_checkpoint(checkpoint_id)
            state = self.state_port.load_run_state(checkpoint.run_state_ref)
        except KeyError as exc:
            raise HarnessResolutionError(
                HarnessErrorCode.CHECKPOINT_INVALID,
                f"checkpoint or run state not found: {exc}",
                checkpoint_id,
            ) from exc

        RunStateBindingGuard.ensure_bound(run, state, checkpoint)
        require_resume_status_allowed(state.status)

        valid_gate = freshness_gate if type(freshness_gate) is ResumeFreshnessGate else None
        audit = begin_boundary_audit(
            run_id=run.run_id,
            agent_id=run.agent_id,
            tarefa_trabalho_id=run.tarefa_trabalho_id,
            correlation_id=run.correlation_id,
            boundary="RuntimePort.resume",
            checkpoint_ref=checkpoint_id,
            previous_authority_context_ref=run.authority_context_ref,
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
            exc = HarnessResolutionError(
                HarnessErrorCode.AUTHORITY_UNRESOLVED,
                "resume requires the canonical Core ResumeFreshnessGate before RuntimePort.resume",
                checkpoint_id,
            )
            blocked = finalize_boundary_audit(
                audit,
                status="BLOCKED",
                outcome="FRESHNESS_GATE_INVALID",
                error=exc,
            )
            self.state_port.save_revalidation_record(audit["revalidation_id"], blocked)
            raise exc

        try:
            preparation = valid_gate.prepare(run)
        except HarnessResolutionError as exc:
            blocked = finalize_boundary_audit(
                audit,
                status="BLOCKED",
                outcome="FRESHNESS_REJECTED",
                error=exc,
            )
            self.state_port.save_revalidation_record(audit["revalidation_id"], blocked)
            raise
        except StrongRevisionGuardUnavailable as exc:
            blocked = finalize_boundary_audit(
                audit,
                status="BLOCKED",
                outcome="REVISION_GUARD_UNAVAILABLE",
                error=exc,
            )
            self.state_port.save_revalidation_record(audit["revalidation_id"], blocked)
            raise
        except Exception as exc:
            failed = finalize_boundary_audit(
                audit,
                status="FAILED",
                outcome="FRESHNESS_ERROR",
                error=exc,
            )
            self.state_port.save_revalidation_record(audit["revalidation_id"], failed)
            raise

        owner_ref = f"RESUME:{run.run_id}:{checkpoint_id}"
        read_set_audit = preparation.versioned_read_set.audit_data()
        guard = None
        released = None
        runtime_error: Exception | None = None
        resumed: RunState | None = None

        try:
            with hold_strong_revision_guard(
                valid_gate.source,
                preparation.versioned_read_set,
                owner_ref=owner_ref,
            ) as guard:
                released = finalize_boundary_audit(
                    audit,
                    status="RELEASED",
                    outcome="REVALIDATED_AND_GUARDED",
                    authority_snapshot=preparation.authority_snapshot,
                    authority_context_ref=preparation.authority.authority_context_id,
                    context=preparation.context,
                    changed_chains=preparation.changed_chains,
                    identity_changed=preparation.identity_changed,
                    metadata={
                        "versioned_read_set": read_set_audit,
                        "revision_guard": guard.audit_data(),
                    },
                )
                self.state_port.save_revalidation_record(audit["revalidation_id"], released)

                run.authority_context_ref = preparation.authority.authority_context_id
                run.task_context_ref = preparation.context.task_context.task_context_id
                runtime_run = run.model_copy(deep=True)
                self.state_port.save_run_state(state)

                canonical_before_runtime = state.model_copy(deep=True)
                try:
                    runtime_result = runtime.resume(
                        runtime_run,
                        state.model_copy(deep=True),
                    )
                    if not isinstance(runtime_result, RunState):
                        raise HarnessResolutionError(
                            HarnessErrorCode.CHECKPOINT_INVALID,
                            "RuntimePort.resume must return canonical RunState",
                            checkpoint_id,
                        )
                    self._reject_runtime_core_owned_mutation(
                        canonical_before_runtime,
                        runtime_result,
                        checkpoint_id,
                    )
                    resumed = merge_runtime_result(canonical_before_runtime, runtime_result)
                except Exception as exc:
                    runtime_error = exc
        except (StrongRevisionGuardUnavailable, RevisionConflictError) as exc:
            conflict_audit = exc.audit_data() if isinstance(exc, RevisionConflictError) else {}
            blocked = finalize_boundary_audit(
                audit,
                status="BLOCKED",
                outcome="REVISION_GUARD_REJECTED",
                error=exc,
                metadata={
                    "versioned_read_set": read_set_audit,
                    "revision_guard": conflict_audit,
                },
            )
            self.state_port.save_revalidation_record(audit["revalidation_id"], blocked)
            raise

        guard_final = guard.audit_data() if guard is not None else {}
        if runtime_error is not None:
            failed = finalize_boundary_audit(
                released if released is not None else audit,
                status="FAILED",
                outcome="RUNTIME_RESUME_ERROR",
                error=runtime_error,
                metadata={"revision_guard_final": guard_final},
            )
            self.state_port.save_revalidation_record(audit["revalidation_id"], failed)
            raise runtime_error

        assert resumed is not None
        assert released is not None
        released["metadata"]["revision_guard_final"] = guard_final
        self.state_port.save_revalidation_record(audit["revalidation_id"], released)
        self.state_port.save_run_state(resumed)
        return resumed

    @staticmethod
    def _effect_key(run_id: str, operation: str, business_key: str) -> str:
        # business_key names the real-world effect. It must survive run changes so
        # creating a fresh HarnessRun cannot replay an already completed effect.
        # run_id remains recorded as provenance in IdempotencyRecord, not identity.
        return f"{operation}:{business_key}"

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
