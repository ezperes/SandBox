from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from harness.contracts import AuthorityContext, Decision, HarnessErrorCode
from harness.core.authority import AuthorityResolver
from harness.core.errors import HarnessResolutionError
from harness.core.freshness import AuthorityFreshnessGate, ToolBoundaryFence
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

    def _invoke_side_effect(
        self,
        *,
        run_id: str,
        authority: AuthorityContext,
        tool_id: str,
        payload: dict[str, Any],
        business_key: str,
        registered: Any,
        audit: dict[str, Any],
        decision: Decision,
        tool_boundary: ToolBoundaryFence,
        initial_freshness_checks: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], str, list[dict[str, Any]], dict[str, Any]]:
        """Acquire the revision fence, revalidate, then invoke while fenced."""
        idempotency_key: str | None = None
        freshness_checks = initial_freshness_checks
        failure_audited = False
        tool_started = False
        released_audit = audit

        try:
            with tool_boundary.hold(authority) as lease:
                # This is the decisive freshness proof. It happens after fence
                # acquisition and the same fence remains held through ToolPort.
                freshness_checks = [asdict(check) for check in lease.freshness_checks]

                try:
                    record = self.state.begin_side_effect(run_id, tool_id, business_key)
                except HarnessResolutionError as exc:
                    self._save_audit(finalize_boundary_audit(
                        audit, status="BLOCKED", outcome="IDEMPOTENCY_BLOCKED", decision=decision.value,
                        error=exc, freshness_checks=freshness_checks,
                    ))
                    failure_audited = True
                    raise
                idempotency_key = record.key

                released_audit = finalize_boundary_audit(
                    audit,
                    status="RELEASED",
                    outcome="AUTHORIZED",
                    decision=decision.value,
                    freshness_checks=freshness_checks,
                    authority_context_ref=authority.authority_context_id,
                    metadata={"idempotency_key": idempotency_key},
                )
                # Persist final authorization while the authority revisions are fenced.
                self._save_audit(released_audit)

                try:
                    tool_started = True
                    output = registered.adapter.invoke(tool_id, payload)
                except Exception as exc:
                    self.state.fail_side_effect(idempotency_key, str(exc), outcome_unknown=True)
                    self._save_audit(finalize_boundary_audit(
                        released_audit, status="FAILED", outcome="TOOLPORT_ERROR", decision=decision.value,
                        error=exc, freshness_checks=freshness_checks,
                    ))
                    failure_audited = True
                    raise
        except HarnessResolutionError as exc:
            if not failure_audited:
                if idempotency_key:
                    self.state.fail_side_effect(idempotency_key, str(exc), outcome_unknown=tool_started)
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="FAILED" if tool_started else "BLOCKED",
                    outcome="TOOL_BOUNDARY_REJECTED",
                    decision=decision.value,
                    error=exc,
                    freshness_checks=freshness_checks,
                    metadata={"idempotency_key": idempotency_key},
                ))
            raise
        except Exception as exc:
            if not failure_audited:
                if idempotency_key:
                    self.state.fail_side_effect(idempotency_key, str(exc), outcome_unknown=tool_started)
                self._save_audit(finalize_boundary_audit(
                    audit,
                    status="FAILED" if tool_started else "BLOCKED",
                    outcome="TOOL_BOUNDARY_ERROR",
                    decision=decision.value,
                    error=exc,
                    freshness_checks=freshness_checks,
                    metadata={"idempotency_key": idempotency_key},
                ))
            raise

        assert idempotency_key is not None
        return output, idempotency_key, freshness_checks, released_audit

    def execute(self, *, run_id: str, authority: AuthorityContext, tool_id: str,
                payload: dict[str, Any], business_key: str | None = None,
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
            },
        )
        self._save_audit(audit)
        freshness_checks: list[dict[str, Any]] = []
        tool_boundary: ToolBoundaryFence | None = None

        if descriptor.side_effect:
            # Every external side effect requires both the concrete Core-owned
            # freshness gate and a source-level revision fence capability.
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

            tool_boundary = ToolBoundaryFence(self.freshness_gate)
            try:
                # Early rejection remains useful, but is not the TOCTOU proof.
                checks = self.freshness_gate.ensure_current(authority)
                freshness_checks = [asdict(check) for check in checks]
            except HarnessResolutionError as exc:
                metadata: dict[str, Any] = {}
                if exc.source_ref:
                    for chain in (
                        authority.tactical_chain_trace,
                        authority.technical_chain_trace,
                        authority.normative_chain_trace,
                    ):
                        if chain and chain.authority_ref == exc.source_ref:
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

            try:
                tool_boundary.ensure_supported()
            except HarnessResolutionError as exc:
                self._save_audit(finalize_boundary_audit(
                    audit, status="BLOCKED", outcome="REVISION_FENCE_UNAVAILABLE",
                    decision=Decision.ESCALATE.value, error=exc,
                    freshness_checks=freshness_checks,
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
        released_audit = audit
        if descriptor.side_effect:
            if not business_key or not business_key.strip():
                exc = HarnessResolutionError(HarnessErrorCode.SIDE_EFFECT_UNKNOWN, "side-effect tool requires explicit business_key", tool_id)
                self._save_audit(finalize_boundary_audit(
                    audit, status="BLOCKED", outcome="BUSINESS_KEY_MISSING", decision=decision.value,
                    error=exc, freshness_checks=freshness_checks,
                ))
                raise exc
            assert tool_boundary is not None
            output, idempotency_key, freshness_checks, released_audit = self._invoke_side_effect(
                run_id=run_id,
                authority=authority,
                tool_id=tool_id,
                payload=payload,
                business_key=business_key,
                registered=registered,
                audit=audit,
                decision=decision,
                tool_boundary=tool_boundary,
                initial_freshness_checks=freshness_checks,
            )
        else:
            released_audit = finalize_boundary_audit(
                audit,
                status="RELEASED",
                outcome="AUTHORIZED",
                decision=decision.value,
                freshness_checks=freshness_checks,
                authority_context_ref=authority.authority_context_id,
            )
            self._save_audit(released_audit)
            try:
                output = registered.adapter.invoke(tool_id, payload)
            except Exception as exc:
                self._save_audit(finalize_boundary_audit(
                    released_audit, status="FAILED", outcome="TOOLPORT_ERROR", decision=decision.value,
                    error=exc, freshness_checks=freshness_checks,
                ))
                raise

        evidence_refs = tuple(str(ref) for ref in output.get("evidence_refs", []))
        if idempotency_key:
            self.state.complete_side_effect(idempotency_key, result=output, evidence_refs=list(evidence_refs))

        if descriptor.evidence_required and not evidence_refs:
            exc = HarnessResolutionError(HarnessErrorCode.VERIFICATION_FAILED, "tool completed but required evidence was not returned", tool_id)
            self._save_audit(finalize_boundary_audit(
                released_audit, status="FAILED", outcome="VERIFICATION_FAILED", decision=decision.value,
                error=exc, freshness_checks=freshness_checks,
                metadata={"idempotency_key": idempotency_key},
            ))
            raise exc

        self._save_audit(finalize_boundary_audit(
            released_audit,
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
            decision_ref=released_audit["revalidation_id"],
        )
