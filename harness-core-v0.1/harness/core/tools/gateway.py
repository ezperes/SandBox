from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from harness.contracts import AuthorityContext, Decision, HarnessErrorCode
from harness.core.authority import AuthorityResolver
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate
from harness.core.freshness.audit import begin_boundary_audit, finalize_boundary_audit
from harness.core.state import StateManager
from .registry import ToolRegistry


@dataclass(frozen=True, slots=True)
class ToolExecutionResult:
    tool_id: str
    decision: Decision
    output: dict[str, Any] | None = None
    idempotency_key: str | None = None
    evidence_refs: tuple[str, ...] = ()


class ToolGateway:
    def __init__(self, registry: ToolRegistry, state: StateManager,
                 freshness_gate: AuthorityFreshnessGate | None = None):
        self.registry = registry
        self.state = state
        self.freshness_gate = freshness_gate

    def _save_audit(self, record: dict[str, Any]) -> None:
        self.state.state_port.save_revalidation_record(record["revalidation_id"], record)

    def execute(self, *, run_id: str, authority: AuthorityContext, tool_id: str,
                payload: dict[str, Any], business_key: str | None = None,
                approved: bool = False) -> ToolExecutionResult:
        try:
            registered = self.registry.resolve(tool_id)
        except KeyError as exc:
            raise HarnessResolutionError(HarnessErrorCode.TOOL_UNAVAILABLE, "tool is not registered", tool_id) from exc

        descriptor = registered.descriptor
        audit: dict[str, Any] | None = None
        freshness_checks: list[dict[str, Any]] = []

        if descriptor.side_effect:
            audit = begin_boundary_audit(
                run_id=run_id,
                boundary="ToolPort.invoke",
                previous_authority_context_ref=authority.authority_context_id,
                previous_authority=authority,
                metadata={
                    "tool_id": tool_id,
                    "action_scope": descriptor.action_scope,
                    "business_key": business_key,
                },
            )
            self._save_audit(audit)

            # T11 boundary: every new external side effect requires the concrete
            # Core-owned freshness gate. Absence of the gate, or a duck-typed/fake
            # replacement, fails closed before authorization, ledger reservation,
            # or ToolPort invocation.
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
                    error=exc,
                ))
                raise exc

            try:
                checks = self.freshness_gate.ensure_current(authority)
                freshness_checks = [asdict(check) for check in checks]
            except HarnessResolutionError as exc:
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="BLOCKED",
                    outcome="FRESHNESS_REJECTED",
                    error=exc,
                ))
                raise
            except Exception as exc:
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="FAILED",
                    outcome="FRESHNESS_ERROR",
                    error=exc,
                ))
                raise

        decision = AuthorityResolver.decide(
            authority, descriptor.action_scope,
            required_competence=descriptor.required_competence,
            approval_required=descriptor.approval_required and not approved,
        )
        if decision == Decision.DENY:
            exc = HarnessResolutionError(HarnessErrorCode.ACTION_FORBIDDEN, "tool action forbidden", tool_id)
            if audit:
                self._save_audit(finalize_boundary_audit(
                    audit, status="BLOCKED", outcome="DENY", decision=decision.value,
                    error=exc, freshness_checks=freshness_checks,
                ))
            raise exc
        if decision == Decision.REQUIRE_APPROVAL:
            exc = HarnessResolutionError(HarnessErrorCode.APPROVAL_REQUIRED, "human approval required", tool_id)
            if audit:
                self._save_audit(finalize_boundary_audit(
                    audit, status="BLOCKED", outcome="REQUIRE_APPROVAL", decision=decision.value,
                    error=exc, freshness_checks=freshness_checks,
                ))
            raise exc
        if decision == Decision.ESCALATE:
            code = HarnessErrorCode.COMPETENCE_INSUFFICIENT if descriptor.required_competence and descriptor.required_competence not in authority.competence_refs else HarnessErrorCode.AUTHORITY_UNRESOLVED
            exc = HarnessResolutionError(code, "tool action cannot be safely authorized", tool_id)
            if audit:
                self._save_audit(finalize_boundary_audit(
                    audit, status="BLOCKED", outcome="ESCALATE", decision=decision.value,
                    error=exc, freshness_checks=freshness_checks,
                ))
            raise exc

        idempotency_key = None
        if descriptor.side_effect:
            if not business_key or not business_key.strip():
                exc = HarnessResolutionError(HarnessErrorCode.SIDE_EFFECT_UNKNOWN, "side-effect tool requires explicit business_key", tool_id)
                self._save_audit(finalize_boundary_audit(
                    audit, status="BLOCKED", outcome="BUSINESS_KEY_MISSING", decision=decision.value,
                    error=exc, freshness_checks=freshness_checks,
                ))
                raise exc
            try:
                record = self.state.begin_side_effect(run_id, tool_id, business_key)
            except HarnessResolutionError as exc:
                self._save_audit(finalize_boundary_audit(
                    audit, status="BLOCKED", outcome="IDEMPOTENCY_BLOCKED", decision=decision.value,
                    error=exc, freshness_checks=freshness_checks,
                ))
                raise
            idempotency_key = record.key
            audit = finalize_boundary_audit(
                audit,
                status="RELEASED",
                outcome="AUTHORIZED",
                decision=decision.value,
                freshness_checks=freshness_checks,
                metadata={"idempotency_key": idempotency_key},
            )
            # Persist authorization before the external ToolPort boundary.
            self._save_audit(audit)

        try:
            output = registered.adapter.invoke(tool_id, payload)
        except Exception as exc:
            if idempotency_key:
                self.state.fail_side_effect(idempotency_key, str(exc), outcome_unknown=True)
            if audit:
                self._save_audit(finalize_boundary_audit(
                    audit, status="FAILED", outcome="TOOLPORT_ERROR", decision=decision.value,
                    error=exc, freshness_checks=freshness_checks,
                ))
            raise

        evidence_refs = tuple(str(ref) for ref in output.get("evidence_refs", []))
        if idempotency_key:
            self.state.complete_side_effect(idempotency_key, result=output, evidence_refs=list(evidence_refs))

        if descriptor.evidence_required and not evidence_refs:
            exc = HarnessResolutionError(HarnessErrorCode.VERIFICATION_FAILED, "tool completed but required evidence was not returned", tool_id)
            if audit:
                self._save_audit(finalize_boundary_audit(
                    audit, status="FAILED", outcome="VERIFICATION_FAILED", decision=decision.value,
                    error=exc, freshness_checks=freshness_checks,
                    metadata={"idempotency_key": idempotency_key},
                ))
            raise exc

        if audit:
            self._save_audit(finalize_boundary_audit(
                audit,
                status="RELEASED",
                outcome="COMPLETED",
                decision=decision.value,
                freshness_checks=freshness_checks,
                metadata={
                    "idempotency_key": idempotency_key,
                    "evidence_refs": list(evidence_refs),
                },
            ))

        return ToolExecutionResult(tool_id=tool_id, decision=Decision.ALLOW, output=output,
                                   idempotency_key=idempotency_key, evidence_refs=evidence_refs)
