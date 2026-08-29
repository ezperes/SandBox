from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from harness.contracts import (
    AgentIdentity, AuthorityContext, AuthoritySnapshot, ChainType, Decision,
    ResolutionChain, ResolutionStatus, HarnessErrorCode,
)
from harness.core.identity import HarnessResolutionError
from harness.ports import SourcePort


@dataclass(slots=True)
class AuthorityResolution:
    context: AuthorityContext
    snapshot: AuthoritySnapshot


class AuthorityResolver:
    def __init__(self, source: SourcePort):
        self.source = source

    def _read_chain(self, kind: ChainType, ref: str) -> tuple[ResolutionChain, dict]:
        try:
            raw = self.source.read(ref)
        except Exception as exc:
            raise HarnessResolutionError(HarnessErrorCode.AUTHORITY_UNRESOLVED, str(exc), ref) from exc
        return ResolutionChain(
            chain_type=kind,
            status=ResolutionStatus.RESOLVED,
            authority_ref=ref,
            route_refs=list(raw.get("route_refs", [ref])),
            applicable_refs=list(raw.get("applicable_refs", [])),
            loaded_excerpt_refs=list(raw.get("loaded_excerpt_refs", [])),
            source_revision_refs=[raw["revision_ref"]] if raw.get("revision_ref") else [],
        ), raw

    def resolve(self, run_id: str, identity: AgentIdentity) -> AuthorityResolution:
        tactical, t_raw = self._read_chain(ChainType.TACTICAL, identity.tactical_authority_ref)

        if identity.technical_authority_ref == "MESMA_CADEIA_TATICA":
            technical = ResolutionChain(
                chain_type=ChainType.TECHNICAL,
                status=ResolutionStatus.SAME_AS_TACTICAL,
                authority_ref=identity.tactical_authority_ref,
                route_refs=tactical.route_refs,
                applicable_refs=tactical.applicable_refs,
                source_revision_refs=tactical.source_revision_refs,
            )
            x_raw = t_raw
        elif identity.technical_authority_ref.startswith("NAO_APLICAVEL_JUSTIFICADO"):
            technical = ResolutionChain(
                chain_type=ChainType.TECHNICAL,
                status=ResolutionStatus.NOT_APPLICABLE_JUSTIFIED,
                justification=identity.technical_authority_ref.partition(":")[2] or "explicitly justified",
            )
            x_raw = {}
        else:
            technical, x_raw = self._read_chain(ChainType.TECHNICAL, identity.technical_authority_ref)

        normative = None
        n_raw = {}
        if identity.normative_authority_ref:
            normative, n_raw = self._read_chain(ChainType.NORMATIVE, identity.normative_authority_ref)

        snapshot = AuthoritySnapshot(
            snapshot_id=f"AS-{uuid4()}",
            identity_source_revision_ref=identity.source_revision_ref,
            tactical_source_revision_refs=tactical.source_revision_refs,
            technical_source_revision_refs=technical.source_revision_refs,
            normative_source_revision_refs=normative.source_revision_refs if normative else [],
        )
        raws = (t_raw, x_raw, n_raw)
        context = AuthorityContext(
            authority_context_id=f"AC-{uuid4()}", run_id=run_id, agent_id=identity.agent_id,
            tactical_authority_refs=[identity.tactical_authority_ref],
            technical_authority_refs=[identity.technical_authority_ref],
            normative_authority_refs=[identity.normative_authority_ref] if identity.normative_authority_ref else [],
            tactical_chain_trace=tactical, technical_chain_trace=technical, normative_chain_trace=normative,
            allowed_scopes=sorted({v for r in raws for v in r.get("allowed_scopes", [])}),
            forbidden_scopes=sorted({v for r in raws for v in r.get("forbidden_scopes", [])}),
            competence_refs=sorted({v for r in raws for v in r.get("competence_refs", [])}),
            registration_prerogatives=sorted({v for r in raws for v in r.get("registration_prerogatives", [])}),
            authority_snapshot_ref=snapshot.snapshot_id,
        )
        return AuthorityResolution(context=context, snapshot=snapshot)

    @staticmethod
    def decide(context: AuthorityContext, action_scope: str, required_competence: str | None = None, approval_required: bool = False) -> Decision:
        if action_scope in context.forbidden_scopes:
            return Decision.DENY
        chains = [context.tactical_chain_trace, context.technical_chain_trace, context.normative_chain_trace]
        if any(c and c.status == ResolutionStatus.UNRESOLVED for c in chains):
            return Decision.ESCALATE
        if required_competence and required_competence not in context.competence_refs:
            return Decision.ESCALATE
        if approval_required:
            return Decision.REQUIRE_APPROVAL
        if context.allowed_scopes and action_scope not in context.allowed_scopes:
            return Decision.ESCALATE
        return Decision.ALLOW
