from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from harness.contracts import AuthorityContext, Decision, HarnessErrorCode, HarnessRun
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
    decision_ref: str | None = None


class ToolGateway:
    def __init__(self, registry: ToolRegistry, state: StateManager,
                 freshness_gate: AuthorityFreshnessGate | None = None):
        self.registry = registry
        self.state = state
        self.freshness_gate = freshness_gate

    def _save_audit(self, record: dict[str, Any]) -> None:
        self.state.state_port.save_revalidation_record(record["revalidation_id"], record)

    def _block_binding(
        self,
        audit: dict[str, Any],
        *,
        outcome: str,
        message: str,
        source_ref: str,
        metadata: dict[str, Any],
    ) -> None:
        exc = HarnessResolutionError(HarnessErrorCode.AUTHORITY_UNRESOLVED, message, source_ref)
        self._save_audit(finalize_boundary_audit(
            audit,
            status="BLOCKED",
            outcome=outcome,
            decision=Decision.ESCALATE.value,
            error=exc,
            metadata=metadata,
        ))
        raise exc

    def execute(self, *, run_id: str, run: HarnessRun | None, authority: AuthorityContext,
                tool_id: str, payload: dict[str, Any], business_key: str | None = None,
                approved: bool = False) -> ToolExecutionResult:
        try:
            registered = self.registry.resolve(tool_id)
        except KeyError as exc:
            raise HarnessResolutionError(HarnessErrorCode.TOOL_UNAVAILABLE, "tool is not registered", tool_id) from exc

        descriptor = registered.descriptor
        audit = begin_boundary_audit(
            run_id=run_id,
            boundary="ToolPort.invoke",
            previous_authority_context_ref=authority.authority_context_id,
            previous_authority=authority,
            metadata={
                "tool_id": tool_id,
                "action_scope": descriptor.action_scope,
                "business_key": business_key,
                "side_effect": descriptor.side_effect,
                "expected_run_id": run.run_id if run else None,
                "expected_agent_id": run.agent_id if run else None,
                "authority_run_id": authority.run_id,
                "authority_agent_id": authority.agent_id,
            },
        )
        self._save_audit(audit)

        # Execution identity is Core-owned through HarnessRun. The ToolPort never
        # supplies or influences these binding values. Binding failures are
        # unresolved authority, not institutional ALLOW/DENY decisions.
        if run is None:
            self._block_binding(
                audit,
                outcome="RUN_BINDING_UNRESOLVED",
                message="tool execution requires the Core-owned HarnessRun binding",
                source_ref=run_id,
                metadata={"expected_run_id": run_id},
            )
        if run.run_id != run_id:
            self._block_binding(
                audit,
                outcome="RUN_BINDING_MISMATCH",
                message="provided HarnessRun does not match the requested run_id",
                source_ref=run.run_id,
                metadata={"expected_run_id": run_id, "observed_run_id": run.run_id},
            )
        if authority.run_id != run_id:
            self._block_binding(
                audit,
                outcome="AUTHORITY_RUN_MISMATCH",
                message="AuthorityContext belongs to a different run",
                source_ref=authority.authority_context_id,
                metadata={"expected_run_id": run_id, "authority_run_id": authority.run_id},
            )
        if authority.agent_id != run.agent_id:
            self._block_binding(
                audit,
                outcome="AUTHORITY_AGENT_MISMATCH",
                message="AuthorityContext belongs to a different agent",
                source_ref=authority.authority_context_id,
                metadata={"expected_agent_id": run.agent_id, "authority_agent_id": authority.agent_id},
            )

        freshness_checks: list[dict[str, Any]] = []

        if descriptor.side_effect:
            # Every new external side effect requires the concrete Core-owned gate.
            # Absence/duck typing fails closed before authorization or ToolPort.
            if type(self.freshness_gate) is not AuthorityFreshnessGate:
                exc = HarnessResolutionError(
                    HarnessErrorCode.AUTHORITY_UNRESOLVED,
                    "side effect requires Core-owned authority freshness before ToolPort",
                    tool_id,
                )
                self._save_audit(finalize_boundary_audit(
                    audit, status="BLOCKED", outcome="FRESHNESS_GATE_INVALID",
                    decision=Decision.ESCALATE.value, error=exc,
                ))
                raise exc

            try:
                checks = self.freshness_gate.ensure_current(authority)
                freshness_checks = [asdict(check) for check in checks]
            except HarnessResolutionError as exc:
                metadata: dict[str, Any] = {}
                if exc.source_ref:
                    if exc.source_ref == self.freshness_gate.identity.source_ref:
                        metadata["freshness_subject"] = "IDENTITY"
                        metadata["expected_revision_refs"] = [
                            self.freshness_gate.identity.source_revision_ref
                        ]
                    else:
                        for chain in (
                            authority.tactical_chain_trace,
                            authority.technical_chain_trace,
                            authority.normative_chain_trace,
                        ):
                            if chain and chain.authority_ref == exc.source_ref:
                                metadata["freshness_subject"] = chain.chain_type.value
                                metadata["expected_revision_refs"] = list(chain.source_revision_refs)
                                break
                    try:
                        current = self.freshness_gate.source.read(exc.source_ref)
                        metadata["observed_revision_ref"] = current.get("revision_ref")
                    except Exception:
                        metadata["observed_revision_ref"] = None
                self._save_audit(finalize_boundary_audit(
                    audit, status="BLOCKED", outcome="FRESHNESS_REJECTED",
                    decision=Decision.ESCALATE.value, error=exc, metadata=metadata,
                ))
                raise
            except Exception as exc:
                self._save_audit(finalize_boundary_audit(
                    audit, status="FAILED", outcome="FRESHNESS_ERROR", error=exc,
                ))
                raise

        decision = AuthorityResolver.decide(
            authority, descriptor.action_scope,
            required_competence=descriptor.required_competence,
            approval_required=descriptor.approval_required and not approved,
        )
        if decision == Decision.DENY:
            exc = HarnessResolutionError(HarnessErrorCode.ACTION_FORBIDDEN, "tool action forbidden", tool_id)
            self._save_audit(finalize_boundary_audit(
                audit, status="BLOCKED", outcome="DENY", decision=decision.value,
                error=exc, freshness_checks=freshness_checks,
            ))
            raise exc
        if decision == Decision.REQUIRE_APPROVAL:
            exc = HarnessResolutionError(HarnessErrorCode.APPROVAL_REQUIRED, "human approval required", tool_id)
            self._save_audit(finalize_boundary_audit(
                audit, status="BLOCKED", outcome="REQUIRE_APPROVAL", decision=decision.value,
                error=exc, freshness_checks=freshness_checks,
            ))
            raise exc
        if decision == Decision.ESCALATE:
            code = HarnessErrorCode.COMPETENCE_INSUFFICIENT if descriptor.required_competence and descriptor.required_competence not in authority.competence_refs else HarnessErrorCode.AUTHORITY_UNRESOLVED
            exc = HarnessResolutionError(code, "tool action cannot be safely authorized", tool_id)
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
            authority_context_ref=authority.authority_context_id,
            metadata={"idempotency_key": idempotency_key},
        )
        # Persist authorization before the external ToolPort boundary.
        self._save_audit(audit)

        try:
            output = registered.adapter.invoke(tool_id, payload)
        except Exception as exc:
            if idempotency_key:
                self.state.fail_side_effect(idempotency_key, str(exc), outcome_unknown=True)
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
            self._save_audit(finalize_boundary_audit(
                audit, status="FAILED", outcome="VERIFICATION_FAILED", decision=decision.value,
                error=exc, freshness_checks=freshness_checks,
                metadata={"idempotency_key": idempotency_key},
            ))
            raise exc

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

        return ToolExecutionResult(
            tool_id=tool_id,
            decision=Decision.ALLOW,
            output=output,
            idempotency_key=idempotency_key,
            evidence_refs=evidence_refs,
            decision_ref=audit["revalidation_id"],
        )
