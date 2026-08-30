from __future__ import annotations

from dataclasses import dataclass

from harness.contracts import AuthorityContext, AuthoritySnapshot, ChainType, HarnessErrorCode, HarnessRun
from harness.core.authority import AuthorityResolver
from harness.core.context import ContextBuildResult, ContextBuilder
from harness.core.errors import HarnessResolutionError
from harness.core.identity import IdentityResolver
from harness.ports import SourcePort, VersionedReadSet

from .revision_guard import StrongRevisionGuardUnavailable, read_versioned_for_sensitive_use


class _VersionedReadSource:
    """Source view that records every Core read into one VersionedReadSet.

    This is not a second guard/lease abstraction. It is only a read-tracking view
    over the canonical SourcePort so existing resolvers/builders participate in
    the same VersionedReadSet consumed by RevisionGuard.
    """

    def __init__(self, source: SourcePort, read_set: VersionedReadSet):
        self._source = source
        self._read_set = read_set

    def read(self, source_ref: str) -> dict:
        return read_versioned_for_sensitive_use(self._source, source_ref, self._read_set).payload


@dataclass(frozen=True, slots=True)
class ResumePreparation:
    authority: AuthorityContext
    authority_snapshot: AuthoritySnapshot
    context: ContextBuildResult
    changed_chains: frozenset[ChainType]
    identity_changed: bool
    versioned_read_set: VersionedReadSet


class ResumeFreshnessGate:
    """Core-owned revalidation boundary required before RuntimePort.resume().

    Preparation re-resolves identity/authority/context and records every canonical
    source materially used in a VersionedReadSet. The caller must acquire and hold
    the canonical strong RevisionGuard for that exact set across RuntimePort.resume().
    """

    def __init__(
        self,
        *,
        source: SourcePort,
        identity_source_ref: str,
        task_source_ref: str,
        previous_identity_revision_ref: str,
        previous_authority: AuthorityContext,
        previous_context: ContextBuildResult,
        max_context_tokens: int = 4000,
    ):
        if not previous_identity_revision_ref.strip():
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "resume requires the previously captured identity revision",
                identity_source_ref,
            )
        self.source = source
        self.identity_source_ref = identity_source_ref
        self.task_source_ref = task_source_ref
        self.previous_identity_revision_ref = previous_identity_revision_ref
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

    def _changed_chains(self, source: SourcePort) -> set[ChainType]:
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
                current = self._chain_current_revision(source, chain.authority_ref)
                seen[chain.authority_ref] = current
            if current not in expected:
                changed.add(chain.chain_type)
        return changed

    @staticmethod
    def _context_field(chain_type: ChainType) -> str:
        return {
            ChainType.TACTICAL: "tactical_context_refs",
            ChainType.TECHNICAL: "technical_context_refs",
            ChainType.NORMATIVE: "normative_context_refs",
        }[chain_type]

    def _record_preserved_materialized_sources(
        self,
        context: ContextBuildResult,
        read_set: VersionedReadSet,
    ) -> None:
        """Add preserved materialized context sources not re-read by partial rebuild.

        ContextBuilder now retains exact canonical source refs separately from the
        context/excerpt refs exposed in TaskContext. If a selected preserved chain
        lacks that provenance, strong protection cannot be proven and resume fails
        closed rather than guessing that a context_ref is itself a source_ref.
        """

        for chain_type in (ChainType.TACTICAL, ChainType.TECHNICAL, ChainType.NORMATIVE):
            selected_context_refs = tuple(getattr(context.task_context, self._context_field(chain_type)))
            source_refs = tuple(context.materialized_source_refs.get(chain_type, ()))
            if selected_context_refs and not source_refs:
                raise StrongRevisionGuardUnavailable(
                    f"resume context lacks materialized source provenance for {chain_type.value}"
                )
            for source_ref in source_refs:
                if read_set.get(source_ref) is None:
                    read_versioned_for_sensitive_use(self.source, source_ref, read_set)

    def prepare(self, run: HarnessRun) -> ResumePreparation:
        read_set = VersionedReadSet()
        versioned_source = _VersionedReadSource(self.source, read_set)

        current_identity = IdentityResolver(versioned_source).resolve(self.identity_source_ref)
        if current_identity.agent_id != run.agent_id:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "resume identity no longer matches the run agent",
                self.identity_source_ref,
            )
        if not current_identity.source_revision_ref:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "resume identity freshness cannot be proven without revision",
                self.identity_source_ref,
            )

        identity_revision_changed = current_identity.source_revision_ref != self.previous_identity_revision_ref
        changed_chains = self._changed_chains(versioned_source)
        resolution = AuthorityResolver(versioned_source).resolve(run.run_id, current_identity)

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
        authority_route_changed = any(previous_refs[k] != current_refs[k] for k in previous_refs)
        identity_changed = identity_revision_changed or authority_route_changed
        if identity_changed:
            changed_chains = {ChainType.TACTICAL, ChainType.TECHNICAL, ChainType.NORMATIVE}

        builder = ContextBuilder(versioned_source)
        if changed_chains:
            context = builder.rebuild_partial(
                self.previous_context,
                resolution.context,
                self.task_source_ref,
                changed_chains,
                max_context_tokens=self.max_context_tokens,
            )
        else:
            # Rebind to freshly resolved authority while preserving the previously
            # selected context refs. TASK itself is read through versioned_source.
            context = builder._task_context(
                run_id=self.previous_context.task_context.run_id,
                authority=resolution.context,
                task=versioned_source.read(self.task_source_ref),
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
                materialized_source_refs=dict(self.previous_context.materialized_source_refs),
            )

        # Partial rebuild deliberately avoids reading preserved materialized
        # documents. Add those exact sources now so the strong guard protects them
        # across RuntimePort.resume as part of the same VersionedReadSet.
        self._record_preserved_materialized_sources(context, read_set)

        return ResumePreparation(
            authority=resolution.context,
            authority_snapshot=resolution.snapshot,
            context=context,
            changed_chains=frozenset(changed_chains),
            identity_changed=identity_changed,
            versioned_read_set=read_set,
        )
