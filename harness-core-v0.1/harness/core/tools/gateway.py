from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from harness.contracts import AuthorityContext, Decision, HarnessErrorCode, HarnessRun, TaskContext
from harness.core.authority import AuthorityResolver
from harness.core.authority.execution_binding import validate_authority_execution_binding
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate
from harness.core.freshness.audit import begin_boundary_audit, finalize_boundary_audit
from harness.core.freshness.revision_guard import StrongRevisionGuardUnavailable, hold_strong_revision_guard
from harness.core.state import StateManager
from harness.ports import VersionedReadSet
from harness.ports.versioning import RevisionConflictError, RevisionGuardActiveError

from .registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    tool_id: str
    decision: Decision
    output: dict[str, Any] | None = None
    idempotency_key: str | None = None
    evidence_refs: tuple[str, ...] = ()
    decision_ref: str | None = None


class ToolGateway:
    """Core-owned authorization and strong-revision boundary for ToolPort."""

    def __init__(self, registry: ToolRegistry, state: StateManager,
                 freshness_gate: AuthorityFreshnessGate | None = None):
        self.registry = registry
        self.state = state
        self.freshness_gate = freshness_gate

    def _save_audit(self, record: dict[str, Any]) -> None:
        self.state.state_port.save_revalidation_record(record["revalidation_id"], record)

    @staticmethod
    def _guard_error(exc: BaseException, tool_id: str) -> HarnessResolutionError:
        source_ref = getattr(exc, "source_ref", None)
        return HarnessResolutionError(
            HarnessErrorCode.AUTHORITY_UNRESOLVED,
            f"strong revision guard rejected ToolPort boundary: {exc}",
            source_ref or tool_id,
        )

    def execute(
        self,
        *,
        run_id: str,
        authority: AuthorityContext,
        tool_id: str,
        payload: dict[str, Any],
        business_key: str | None = None,
        approved: bool = False,
        run: HarnessRun | None = None,
        task_context: TaskContext | None = None,
    ) -> ToolExecutionResult:
        try:
            registered = self.registry.resolve(tool_id)
        except KeyError as exc:
            raise HarnessResolutionError(
                HarnessErrorCode.TOOL_UNAVAILABLE,
                "tool is not registered",
                tool_id,
            ) from exc

        descriptor = registered.descriptor
        audit = begin_boundary_audit(
            run_id=run_id,
            agent_id=run.agent_id if run is not None else None,
            tarefa_trabalho_id=run.tarefa_trabalho_id if run is not None else None,
            correlation_id=run.correlation_id if run is not None else None,
            boundary="ToolPort.invoke",
            previous_authority_context_ref=authority.authority_context_id,
            previous_task_context_ref=task_context.task_context_id if task_context is not None else None,
            previous_authority=authority,
            metadata={
                "tool_id": tool_id,
                "action_scope": descriptor.action_scope,
                "business_key": business_key,
                "side_effect": descriptor.side_effect,
            },
        )
        self._save_audit(audit)
        freshness_checks: list[dict[str, Any]] = []
        read_set = VersionedReadSet()

        # F5: every side effect must name a complete current execution. No
        # inference from AuthorityContext is allowed because historically valid
        # authority from another run/agent/task must fail closed.
        if descriptor.side_effect:
            if run is None or task_context is None:
                exc = HarnessResolutionError(
                    HarnessErrorCode.AUTHORITY_UNRESOLVED,
                    "side effect requires canonical HarnessRun and TaskContext execution binding",
                    tool_id,
                )
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="BLOCKED",
                    outcome="EXECUTION_BINDING_MISSING",
                    decision=Decision.ESCALATE.value,
                    error=exc,
                ))
                raise exc
            if run.run_id != run_id:
                exc = HarnessResolutionError(
                    HarnessErrorCode.AUTHORITY_UNRESOLVED,
                    "ToolGateway run_id does not match canonical HarnessRun.run_id",
                    run_id,
                )
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="BLOCKED",
                    outcome="EXECUTION_BINDING_REJECTED",
                    decision=Decision.ESCALATE.value,
                    error=exc,
                ))
                raise exc
            try:
                validate_authority_execution_binding(
                    authority,
                    run=run,
                    task_context=task_context,
                    boundary="ToolPort.invoke",
                )
            except HarnessResolutionError as exc:
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="BLOCKED",
                    outcome="EXECUTION_BINDING_REJECTED",
                    decision=Decision.ESCALATE.value,
                    error=exc,
                ))
                raise

            # Every new external side effect requires the concrete Core-owned
            # freshness gate, and its canonical reads are accumulated in the same
            # VersionedReadSet consumed by the one shared RevisionGuard family.
            if type(self.freshness_gate) is not AuthorityFreshnessGate:
                exc = HarnessResolutionError(
                    HarnessErrorCode.AUTHORITY_UNRESOLVED,
                    "side effect requires Core-owned authority freshness before ToolPort",
                    tool_id,
                )
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="BLOCKED",
                    outcome="FRESHNESS_GATE_INVALID",
                    decision=Decision.ESCALATE.value,
                    error=exc,
                ))
                raise exc

            try:
                checks = self.freshness_gate.ensure_current(authority, read_set)
                freshness_checks = [asdict(check) for check in checks]
            except HarnessResolutionError as exc:
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="BLOCKED",
                    outcome="FRESHNESS_REJECTED",
                    decision=Decision.ESCALATE.value,
                    error=exc,
                ))
                raise
            except StrongRevisionGuardUnavailable as exc:
                wrapped = self._guard_error(exc, tool_id)
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="BLOCKED",
                    outcome="REVISION_GUARD_UNAVAILABLE",
                    decision=Decision.ESCALATE.value,
                    error=wrapped,
                ))
                raise wrapped from exc
            except Exception as exc:
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="FAILED",
                    outcome="FRESHNESS_ERROR",
                    error=exc,
                ))
                raise

        decision = AuthorityResolver.decide(
            authority,
            descriptor.action_scope,
            required_competence=descriptor.required_competence,
            approval_required=descriptor.approval_required and not approved,
        )
        if decision == Decision.DENY:
            exc = HarnessResolutionError(HarnessErrorCode.ACTION_FORBIDDEN, "tool action forbidden", tool_id)
            self._save_audit(finalize_boundary_audit(
                audit,
                status="BLOCKED",
                outcome="DENY",
                decision=decision.value,
                error=exc,
                freshness_checks=freshness_checks,
            ))
            raise exc
        if decision == Decision.REQUIRE_APPROVAL:
            exc = HarnessResolutionError(HarnessErrorCode.APPROVAL_REQUIRED, "human approval required", tool_id)
            self._save_audit(finalize_boundary_audit(
                audit,
                status="BLOCKED",
                outcome="REQUIRE_APPROVAL",
                decision=decision.value,
                error=exc,
                freshness_checks=freshness_checks,
            ))
            raise exc
        if decision == Decision.ESCALATE:
            code = (
                HarnessErrorCode.COMPETENCE_INSUFFICIENT
                if descriptor.required_competence and descriptor.required_competence not in authority.competence_refs
                else HarnessErrorCode.AUTHORITY_UNRESOLVED
            )
            exc = HarnessResolutionError(code, "tool action cannot be safely authorized", tool_id)
            self._save_audit(finalize_boundary_audit(
                audit,
                status="BLOCKED",
                outcome="ESCALATE",
                decision=decision.value,
                error=exc,
                freshness_checks=freshness_checks,
            ))
            raise exc

        if not descriptor.side_effect:
            released = finalize_boundary_audit(
                audit,
                status="RELEASED",
                outcome="AUTHORIZED",
                decision=decision.value,
                freshness_checks=freshness_checks,
                authority_context_ref=authority.authority_context_id,
            )
            self._save_audit(released)
            try:
                output = registered.adapter.invoke(tool_id, payload)
            except Exception as exc:
                self._save_audit(finalize_boundary_audit(
                    released,
                    status="FAILED",
                    outcome="TOOLPORT_ERROR",
                    decision=decision.value,
                    error=exc,
                ))
                raise
            evidence_refs = tuple(str(ref) for ref in output.get("evidence_refs", []))
            completed = finalize_boundary_audit(
                released,
                status="RELEASED",
                outcome="COMPLETED",
                decision=decision.value,
                metadata={"evidence_refs": list(evidence_refs)},
            )
            self._save_audit(completed)
            return ToolExecutionResult(
                tool_id=tool_id,
                decision=Decision.ALLOW,
                output=output,
                evidence_refs=evidence_refs,
                decision_ref=audit["revalidation_id"],
            )

        if not business_key or not business_key.strip():
            exc = HarnessResolutionError(
                HarnessErrorCode.SIDE_EFFECT_UNKNOWN,
                "side-effect tool requires explicit business_key",
                tool_id,
            )
            self._save_audit(finalize_boundary_audit(
                audit,
                status="BLOCKED",
                outcome="BUSINESS_KEY_MISSING",
                decision=decision.value,
                error=exc,
                freshness_checks=freshness_checks,
            ))
            raise exc

        idempotency_key: str | None = None
        output: dict[str, Any] | None = None
        guard = None
        guarded_audit = None
        try:
            # Deliberate ordering: acquire the strong guard before reserving the
            # side-effect ledger. A stale authorization therefore creates no
            # misleading PENDING entry. The hold then spans the short reservation
            # and the full synchronous ToolPort.invoke call.
            with hold_strong_revision_guard(
                self.freshness_gate.source,
                read_set,
                owner_ref=f"TOOL:{run_id}:{tool_id}:{business_key}",
            ) as guard:
                try:
                    record = self.state.begin_side_effect(run_id, tool_id, business_key)
                    idempotency_key = record.key
                except HarnessResolutionError as exc:
                    self._save_audit(finalize_boundary_audit(
                        audit,
                        status="BLOCKED",
                        outcome="IDEMPOTENCY_BLOCKED",
                        decision=decision.value,
                        error=exc,
                        freshness_checks=freshness_checks,
                        metadata={
                            "versioned_read_set": read_set.audit_data(),
                            "revision_guard": guard.audit_data(),
                        },
                    ))
                    raise
                except RevisionGuardActiveError as exc:
                    wrapped = self._guard_error(exc, tool_id)
                    self._save_audit(finalize_boundary_audit(
                        audit,
                        status="BLOCKED",
                        outcome="REVISION_GUARD_ACTIVE_WRITER",
                        decision=decision.value,
                        error=wrapped,
                        freshness_checks=freshness_checks,
                        metadata={
                            "versioned_read_set": read_set.audit_data(),
                            "revision_guard": guard.audit_data(),
                        },
                    ))
                    raise wrapped from exc

                guarded_audit = finalize_boundary_audit(
                    audit,
                    status="RELEASED",
                    outcome="AUTHORIZED_AND_GUARDED",
                    decision=decision.value,
                    freshness_checks=freshness_checks,
                    authority_context_ref=authority.authority_context_id,
                    metadata={
                        "idempotency_key": idempotency_key,
                        "versioned_read_set": read_set.audit_data(),
                        "revision_guard": guard.audit_data(),
                    },
                )
                self._save_audit(guarded_audit)

                try:
                    output = registered.adapter.invoke(tool_id, payload)
                except Exception as exc:
                    if idempotency_key:
                        self.state.fail_side_effect(idempotency_key, str(exc), outcome_unknown=True)
                    self._save_audit(finalize_boundary_audit(
                        guarded_audit,
                        status="FAILED",
                        outcome="TOOLPORT_ERROR",
                        decision=decision.value,
                        error=exc,
                        freshness_checks=freshness_checks,
                    ))
                    raise
        except RevisionConflictError as exc:
            wrapped = self._guard_error(exc, tool_id)
            self._save_audit(finalize_boundary_audit(
                audit,
                status="BLOCKED",
                outcome="REVISION_GUARD_REJECTED",
                decision=decision.value,
                error=wrapped,
                freshness_checks=freshness_checks,
                metadata={
                    "versioned_read_set": read_set.audit_data(),
                    "revision_guard": exc.audit_data(),
                },
            ))
            raise wrapped from exc
        except StrongRevisionGuardUnavailable as exc:
            wrapped = self._guard_error(exc, tool_id)
            self._save_audit(finalize_boundary_audit(
                audit,
                status="BLOCKED",
                outcome="REVISION_GUARD_UNAVAILABLE",
                decision=decision.value,
                error=wrapped,
                freshness_checks=freshness_checks,
                metadata={"versioned_read_set": read_set.audit_data()},
            ))
            raise wrapped from exc

        assert output is not None
        assert idempotency_key is not None
        assert guarded_audit is not None
        guard_final = guard.audit_data() if guard is not None else {}
        evidence_refs = tuple(str(ref) for ref in output.get("evidence_refs", []))
        self.state.complete_side_effect(
            idempotency_key,
            result=output,
            evidence_refs=list(evidence_refs),
        )

        if descriptor.evidence_required and not evidence_refs:
            exc = HarnessResolutionError(
                HarnessErrorCode.VERIFICATION_FAILED,
                "tool completed but required evidence was not returned",
                tool_id,
            )
            self._save_audit(finalize_boundary_audit(
                guarded_audit,
                status="FAILED",
                outcome="VERIFICATION_FAILED",
                decision=decision.value,
                error=exc,
                freshness_checks=freshness_checks,
                metadata={
                    "idempotency_key": idempotency_key,
                    "revision_guard_final": guard_final,
                },
            ))
            raise exc

        completed = finalize_boundary_audit(
            guarded_audit,
            status="RELEASED",
            outcome="COMPLETED",
            decision=decision.value,
            freshness_checks=freshness_checks,
            metadata={
                "idempotency_key": idempotency_key,
                "evidence_refs": list(evidence_refs),
                "revision_guard_final": guard_final,
            },
        )
        self._save_audit(completed)

        return ToolExecutionResult(
            tool_id=tool_id,
            decision=Decision.ALLOW,
            output=output,
            idempotency_key=idempotency_key,
            evidence_refs=evidence_refs,
            decision_ref=audit["revalidation_id"],
        )
