from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import ContextManager, Iterator, Mapping, Protocol, runtime_checkable

from harness.contracts import AuthorityContext, HarnessErrorCode, ResolutionStatus
from harness.core.errors import HarnessResolutionError

from .gate import AuthorityFreshnessGate, FreshnessCheck


@runtime_checkable
class RevisionFenceSource(Protocol):
    """Source concurrency capability required for a TOCTOU-safe tool boundary.

    The adapter supplies only the concurrency primitive. The Core remains the
    policy owner: it chooses the expected revisions and revalidates them after
    the fence is acquired.

    Contract: while the returned context manager is active, no revision-changing
    writer covered by this source may make any requested authority ref advance.
    An implementation that merely rechecks a revision without preventing a
    concurrent change does not satisfy this contract.
    """

    def revision_fence(
        self,
        expected_revision_refs: Mapping[str, tuple[str, ...]],
    ) -> ContextManager[None]: ...


@dataclass(frozen=True, slots=True)
class ToolBoundaryLease:
    expected_revision_refs: tuple[tuple[str, tuple[str, ...]], ...]
    freshness_checks: tuple[FreshnessCheck, ...]


class ToolBoundaryFence:
    """Core-owned fence held from final freshness proof through ToolPort.invoke.

    General atomicity is impossible with SourcePort.read() alone. This boundary
    therefore fails closed unless the concrete source exposes a real
    ``revision_fence`` capability. Freshness is revalidated *after* fence
    acquisition and the caller must keep the context active across ToolPort.
    """

    def __init__(self, freshness_gate: AuthorityFreshnessGate):
        if type(freshness_gate) is not AuthorityFreshnessGate:
            raise TypeError("ToolBoundaryFence requires concrete AuthorityFreshnessGate")
        self.freshness_gate = freshness_gate

    def _expected_revisions(self, authority: AuthorityContext) -> dict[str, tuple[str, ...]]:
        expected_by_ref: dict[str, tuple[str, ...]] = {}
        for chain in (
            authority.tactical_chain_trace,
            authority.technical_chain_trace,
            authority.normative_chain_trace,
        ):
            if chain is None or chain.status == ResolutionStatus.NOT_APPLICABLE_JUSTIFIED:
                continue
            authority_ref = str(chain.authority_ref or "").strip()
            expected = tuple(str(ref).strip() for ref in chain.source_revision_refs if str(ref).strip())
            if not authority_ref or not expected:
                raise HarnessResolutionError(
                    HarnessErrorCode.AUTHORITY_UNRESOLVED,
                    "tool boundary fence cannot be built without authority_ref and source revision",
                    authority_ref or None,
                )
            prior = expected_by_ref.get(authority_ref)
            if prior is None:
                expected_by_ref[authority_ref] = expected
                continue
            intersection = tuple(ref for ref in prior if ref in expected)
            if not intersection:
                raise HarnessResolutionError(
                    HarnessErrorCode.AUTHORITY_UNRESOLVED,
                    "conflicting expected revisions for the same authority source",
                    authority_ref,
                )
            expected_by_ref[authority_ref] = intersection
        return expected_by_ref

    def ensure_supported(self) -> RevisionFenceSource:
        source = self.freshness_gate.source
        if not isinstance(source, RevisionFenceSource):
            raise HarnessResolutionError(
                HarnessErrorCode.AUTHORITY_UNRESOLVED,
                "side effect requires a source revision fence; SourcePort.read() alone cannot close TOCTOU",
            )
        return source

    @contextmanager
    def hold(self, authority: AuthorityContext) -> Iterator[ToolBoundaryLease]:
        source = self.ensure_supported()
        expected = self._expected_revisions(authority)
        # The source fence is acquired first. Only then may Core prove freshness.
        # The context remains held until the caller exits after ToolPort.invoke().
        with source.revision_fence(expected):
            checks = self.freshness_gate.ensure_current(authority)
            yield ToolBoundaryLease(
                expected_revision_refs=tuple(sorted(expected.items())),
                freshness_checks=checks,
            )
