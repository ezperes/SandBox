from __future__ import annotations

from dataclasses import dataclass

from harness.contracts import AuthorityContext, AuthoritySnapshot, ChainType, HarnessErrorCode, HarnessRun
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuildResult, ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.identity import IdentityResolver
from harness.ports import SourcePort


@dataclass(frozen=True, slots=True)
class ResumePreparation:
    authority: AuthorityContext
    authority_snapshot: AuthoritySnapshot
    context: ContextBuildResult
    changed_chains: frozenset[ChainType]
    identity_changed: bool


class ResumeFreshnessGate:
    """Core-owned revalidation boundary required before RuntimePort.resume().

    It compares the revisions captured by the prior identity/authority context with
    current canonical sources. Any drift triggers canonical re-resolution and a
    selective Active Context rebuild before the runtime may resume.
    """

    def __init__(
        self,
        *,
        source: SourcePort,
        identity_source_ref: str,
        task_source_ref: str,
        previous_authority: AuthorityContext,
        previous_context: ContextBuildResult,
        max_context_tokens: int = 4000,
    ):
        self.source = source
        self.identity_source_ref = identity_source_ref
        self.task_source_ref = task_source_ref
        self.previous_authority = previous_authority
        self.previous_context = previous_context
        self.max_context_tokens = max_context_tokens

    @staticmethod
    def _chain_current_revision(source: SourcePort, authority_ref: str) -> str:
        try:
            raw = source.read(authority_ref)
        except Exception as exc:
            raise HarnessResolutionError(
                HarnessErrorCode.AUTHORITY_UNRESOLVED,
                "resume freshness source cannot be read",
                authority_ref,
            ) from exc
        revision = str(raw.get("revision_ref") or "").strip()
        if not revision:
            raise HarnessResolutionError(
                HarnessErrorCode.AUTHORITY_UNRESOLVED,
                "resume freshness source has no revision_ref",
                authority_ref,
            )
        return revision

    def _changed_chains(self) -> set[ChainType]:
        changed: set[ChainType] = set()
        seen: dict[str, str] = {}
        for chain in (
            self.previous_authority.tactical_chain_trace,
            self.previous_authority.technical_chain_trace,
            self.previous_authority.normative_chain_trace,
        ):
            if chain is None or not chain.authority_ref:
                continue
            expected = tuple(chain.source_revision_refs)
            if not expected:
                raise HarnessResolutionError(
                    HarnessErrorCode.AUTHORITY_UNRESOLVED,
                    "resume freshness cannot be proven without authority revision",
                    chain.authority_ref,
                )
            current = seen.get(chain.authority_ref)
            if current is None:
                current = self._chain_current_revision(self.source, chain.authority_ref)
                seen[chain.authority_ref] = current
            if current not in expected:
                changed.add(chain.chain_type)
        return changed

    def prepare(self, run: HarnessRun) -> ResumePreparation:
        current_identity = IdentityResolver(self.source).resolve(self.identity_source_ref)
        if current_identity.agent_id != run.agent_id:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "resume identity no longer matches the run agent",
                self.identity_source_ref,
            )

        previous_identity_revision = None
        try:
            previous_identity_raw = self.source.read(self.identity_source_ref)
            current_identity_revision = str(previous_identity_raw.get("revision_ref") or "").strip()
        except Exception as exc:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "resume identity source cannot be read for freshness",
                self.identity_source_ref,
            ) from exc

        # The prior identity revision is carried by the authority snapshot lineage
        # indirectly through the prior context's authority. If the current resolver
        # cannot provide a revision, freshness is not provable.
        if not current_identity.source_revision_ref or not current_identity_revision:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "resume identity freshness cannot be proven without revision",
                self.identity_source_ref,
            )

        # There is no persisted previous AgentIdentity in V0.1. Treat any authority
        # chain drift as requiring authority re-resolution; identity itself is always
        # re-resolved at the boundary. Identity route changes are therefore caught by
        # the new identity's authority refs and fail closed if they cannot resolve.
        changed_chains = self._changed_chains()
        resolution = AuthorityResolver(self.source).resolve(run.run_id, current_identity)

        previous_refs = {
            ChainType.TACTICAL: tuple(self.previous_authority.tactical_authority_refs),
            ChainType.TECHNICAL: tuple(self.previous_authority.technical_authority_refs),
            ChainType.NORMATIVE: tuple(self.previous_authority.normative_authority_refs),
        }
        current_refs = {
            ChainType.TACTICAL: tuple(resolution.context.tactical_authority_refs),
            ChainType.TECHNICAL: tuple(resolution.context.technical_authority_refs),
            ChainType.NORMATIVE: tuple(resolution.context.normative_authority_refs),
        }
        identity_changed = any(previous_refs[k] != current_refs[k] for k in previous_refs)
        if identity_changed:
            changed_chains = {ChainType.TACTICAL, ChainType.TECHNICAL, ChainType.NORMATIVE}

        builder = ContextBuilder(self.source)
        if changed_chains:
            context = builder.rebuild_partial(
                self.previous_context,
                resolution.context,
                self.task_source_ref,
                changed_chains,
                max_context_tokens=self.max_context_tokens,
            )
        else:
            # Rebind to the freshly resolved authority even when materialized chain
            # content is unchanged, so the resumed run points at a current snapshot.
            context = builder._task_context(
                run_id=self.previous_context.task_context.run_id,
                authority=resolution.context,
                task=self.source.read(self.task_source_ref),
                bootstrap=self.previous_context.bootstrap,
                chain_refs={
                    ChainType.TACTICAL: list(self.previous_context.task_context.tactical_context_refs),
                    ChainType.TECHNICAL: list(self.previous_context.task_context.technical_context_refs),
                    ChainType.NORMATIVE: list(self.previous_context.task_context.normative_context_refs),
                },
            )
            context = ContextBuildResult(
                task_context=context,
                bootstrap=self.previous_context.bootstrap,
                provenance=dict(self.previous_context.provenance),
                token_usage=dict(self.previous_context.token_usage),
                estimated_tokens=self.previous_context.estimated_tokens,
            )

        return ResumePreparation(
            authority=resolution.context,
            authority_snapshot=resolution.snapshot,
            context=context,
            changed_chains=frozenset(changed_chains),
            identity_changed=identity_changed,
        )
