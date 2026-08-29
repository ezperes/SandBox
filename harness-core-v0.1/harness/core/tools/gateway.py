from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from harness.contracts import AuthorityContext, Decision, HarnessErrorCode
from harness.core.authority import AuthorityResolver
from harness.core.identity import HarnessResolutionError
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
    def __init__(self, registry: ToolRegistry, state: StateManager):
        self.registry = registry
        self.state = state

    def execute(self, *, run_id: str, authority: AuthorityContext, tool_id: str,
                payload: dict[str, Any], business_key: str | None = None,
                approved: bool = False) -> ToolExecutionResult:
        try:
            registered = self.registry.resolve(tool_id)
        except KeyError as exc:
            raise HarnessResolutionError(HarnessErrorCode.TOOL_UNAVAILABLE, "tool is not registered", tool_id) from exc

        descriptor = registered.descriptor
        decision = AuthorityResolver.decide(
            authority, descriptor.action_scope,
            required_competence=descriptor.required_competence,
            approval_required=descriptor.approval_required and not approved,
        )
        if decision == Decision.DENY:
            raise HarnessResolutionError(HarnessErrorCode.ACTION_FORBIDDEN, "tool action forbidden", tool_id)
        if decision == Decision.REQUIRE_APPROVAL:
            raise HarnessResolutionError(HarnessErrorCode.APPROVAL_REQUIRED, "human approval required", tool_id)
        if decision == Decision.ESCALATE:
            code = HarnessErrorCode.COMPETENCE_INSUFFICIENT if descriptor.required_competence and descriptor.required_competence not in authority.competence_refs else HarnessErrorCode.AUTHORITY_UNRESOLVED
            raise HarnessResolutionError(code, "tool action cannot be safely authorized", tool_id)

        idempotency_key = None
        if descriptor.side_effect:
            if not business_key or not business_key.strip():
                raise HarnessResolutionError(HarnessErrorCode.SIDE_EFFECT_UNKNOWN, "side-effect tool requires explicit business_key", tool_id)
            record = self.state.begin_side_effect(run_id, tool_id, business_key)
            idempotency_key = record.key

        try:
            output = registered.adapter.invoke(tool_id, payload)
        except Exception as exc:
            if idempotency_key:
                self.state.fail_side_effect(idempotency_key, str(exc), outcome_unknown=True)
            raise

        evidence_refs = tuple(str(ref) for ref in output.get("evidence_refs", []))
        if idempotency_key:
            self.state.complete_side_effect(idempotency_key, result=output, evidence_refs=list(evidence_refs))

        if descriptor.evidence_required and not evidence_refs:
            raise HarnessResolutionError(HarnessErrorCode.VERIFICATION_FAILED, "tool completed but required evidence was not returned", tool_id)

        return ToolExecutionResult(tool_id=tool_id, decision=Decision.ALLOW, output=output,
                                   idempotency_key=idempotency_key, evidence_refs=evidence_refs)
