from __future__ import annotations

from dataclasses import dataclass

from harness.contracts import AuthorityContext, ChainType, HarnessErrorCode, ResolutionChain, ResolutionStatus
from harness.core.errors import HarnessResolutionError
from harness.ports import SourcePort, VersionedReadSet

from .revision_guard import StrongRevisionGuardUnavailable, read_versioned_for_sensitive_use


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

    When a VersionedReadSet is supplied, every canonical read used by this
    freshness decision is captured in that same set so the caller can protect the
    later sensitive use with the canonical strong RevisionGuard.
    """

    def __init__(self, source: SourcePort):
        self.source = source

    def _check_chain(
        self,
        chain: ResolutionChain | None,
        read_set: VersionedReadSet | None = None,
    ) -> FreshnessCheck | None:
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
            if read_set is None:
                raw = self.source.read(chain.authority_ref)
            else:
                raw = read_versioned_for_sensitive_use(
                    self.source,
                    chain.authority_ref,
                    read_set,
                ).payload
        except StrongRevisionGuardUnavailable:
            # Capability absence is different from a stale/unreadable authority
            # document. Preserve that signal so sensitive callers can explicitly
            # fail closed on the missing strong-guard contract.
            raise
        except HarnessResolutionError:
            raise
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
        self,
        authority: AuthorityContext,
        read_set: VersionedReadSet | None = None,
    ) -> tuple[FreshnessCheck, ...]:
        checks: list[FreshnessCheck] = []
        seen: set[tuple[str, tuple[str, ...]]] = set()
        for chain in (
            authority.tactical_chain_trace,
            authority.technical_chain_trace,
            authority.normative_chain_trace,
        ):
            result = self._check_chain(chain, read_set)
            if result is None:
                continue
            key = (result.authority_ref, result.expected_revision_refs)
            if key in seen:
                continue
            seen.add(key)
            checks.append(result)
        return tuple(checks)
