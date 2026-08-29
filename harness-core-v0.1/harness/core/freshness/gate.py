from __future__ import annotations

from dataclasses import dataclass

from harness.contracts import (
    AgentIdentity,
    AuthorityContext,
    ChainType,
    HarnessErrorCode,
    ResolutionChain,
    ResolutionStatus,
)
from harness.core.errors import HarnessResolutionError
from harness.core.identity import IdentityResolver
from harness.ports import SourcePort


@dataclass(frozen=True, slots=True)
class IdentityFreshnessCheck:
    source_ref: str
    agent_id: str
    expected_revision_ref: str
    current_revision_ref: str


@dataclass(frozen=True, slots=True)
class FreshnessCheck:
    chain_type: ChainType
    authority_ref: str
    expected_revision_refs: tuple[str, ...]
    current_revision_ref: str


class AuthorityFreshnessGate:
    """Fail-closed freshness boundary for identity and authority snapshots.

    The gate receives the AgentIdentity baseline that was used to resolve the
    AuthorityContext. At a sensitive boundary it proves both that identity and
    authority-chain revisions still match canonical SourcePort data. It does not
    silently re-resolve authority; any mismatch requires the caller/coordinator
    to obtain a fresh identity/authority context before retrying.
    """

    def __init__(self, source: SourcePort, identity: AgentIdentity):
        self.source = source
        self.identity = identity
        if not identity.source_revision_ref or not identity.source_revision_ref.strip():
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "authority freshness requires an identity baseline revision",
                identity.source_ref,
            )

    def _check_identity(self, authority: AuthorityContext) -> IdentityFreshnessCheck:
        if authority.agent_id != self.identity.agent_id:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "authority agent does not match the identity freshness baseline",
                self.identity.source_ref,
            )

        current = IdentityResolver(self.source).resolve(self.identity.source_ref)
        current_revision = str(current.source_revision_ref or "").strip()
        if not current_revision:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "identity freshness source has no revision_ref",
                self.identity.source_ref,
            )
        if current.agent_id != self.identity.agent_id:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                "canonical identity agent changed since authority resolution",
                self.identity.source_ref,
            )
        if current_revision != self.identity.source_revision_ref:
            raise HarnessResolutionError(
                HarnessErrorCode.IDENTITY_UNRESOLVED,
                (
                    "identity is stale: expected revision "
                    f"{self.identity.source_revision_ref!r}, current revision {current_revision!r}"
                ),
                self.identity.source_ref,
            )

        return IdentityFreshnessCheck(
            source_ref=self.identity.source_ref,
            agent_id=self.identity.agent_id,
            expected_revision_ref=self.identity.source_revision_ref,
            current_revision_ref=current_revision,
        )

    def _check_chain(self, chain: ResolutionChain | None) -> FreshnessCheck | None:
        if chain is None or chain.status == ResolutionStatus.NOT_APPLICABLE_JUSTIFIED:
            return None
        if not chain.authority_ref:
            raise HarnessResolutionError(
                HarnessErrorCode.AUTHORITY_UNRESOLVED,
                "authority freshness cannot be proven without authority_ref",
            )
        expected = tuple(chain.source_revision_refs)
        if not expected:
            raise HarnessResolutionError(
                HarnessErrorCode.AUTHORITY_UNRESOLVED,
                "authority freshness cannot be proven without source revision",
                chain.authority_ref,
            )
        try:
            raw = self.source.read(chain.authority_ref)
        except Exception as exc:
            raise HarnessResolutionError(
                HarnessErrorCode.AUTHORITY_UNRESOLVED,
                "authority freshness source cannot be read",
                chain.authority_ref,
            ) from exc
        current = str(raw.get("revision_ref") or "").strip()
        if not current:
            raise HarnessResolutionError(
                HarnessErrorCode.AUTHORITY_UNRESOLVED,
                "authority freshness source has no revision_ref",
                chain.authority_ref,
            )
        if current not in expected:
            raise HarnessResolutionError(
                HarnessErrorCode.AUTHORITY_UNRESOLVED,
                f"authority context is stale: expected revision {expected!r}, current revision {current!r}",
                chain.authority_ref,
            )
        return FreshnessCheck(
            chain_type=chain.chain_type,
            authority_ref=chain.authority_ref,
            expected_revision_refs=expected,
            current_revision_ref=current,
        )

    def ensure_current(
        self, authority: AuthorityContext
    ) -> tuple[IdentityFreshnessCheck | FreshnessCheck, ...]:
        checks: list[IdentityFreshnessCheck | FreshnessCheck] = [
            self._check_identity(authority)
        ]
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for chain in (
            authority.tactical_chain_trace,
            authority.technical_chain_trace,
            authority.normative_chain_trace,
        ):
            result = self._check_chain(chain)
            if result is None:
                continue
            key = (result.authority_ref, result.expected_revision_refs)
            if key in seen:
                continue
            seen.add(key)
            checks.append(result)
        return tuple(checks)
