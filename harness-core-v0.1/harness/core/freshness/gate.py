from __future__ import annotations

from dataclasses import dataclass

from harness.contracts import AuthorityContext, ChainType, HarnessErrorCode, ResolutionChain, ResolutionStatus
from harness.core.errors import HarnessResolutionError
from harness.ports import SourcePort


@dataclass(frozen=True, slots=True)
class FreshnessCheck:
    chain_type: ChainType
    authority_ref: str
    expected_revision_refs: tuple[str, ...]
    current_revision_ref: str


class AuthorityFreshnessGate:
    """Fail-closed freshness boundary for authority snapshots.

    This component does not create authority and does not silently re-resolve it.
    It only proves that the authority-chain revisions used to build an
    AuthorityContext still match the canonical SourcePort at a sensitive
    boundary. A mismatch invalidates reuse of that context and requires the
    caller/coordinator to re-resolve before retrying.
    """

    def __init__(self, source: SourcePort):
        self.source = source

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

    def ensure_current(self, authority: AuthorityContext) -> tuple[FreshnessCheck, ...]:
        checks: list[FreshnessCheck] = []
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
