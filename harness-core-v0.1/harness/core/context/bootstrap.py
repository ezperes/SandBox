from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from harness.contracts import AuthorityContext, ChainType, ResolutionChain, ResolutionStatus


@dataclass(frozen=True, slots=True)
class BootstrapResolution:
    trace_id: str
    tactical_refs: tuple[str, ...]
    technical_refs: tuple[str, ...]
    normative_refs: tuple[str, ...]
    tactical_chain: ResolutionChain
    technical_chain: ResolutionChain
    normative_chain: ResolutionChain | None

    def refs_for(self, chain_type: ChainType) -> tuple[str, ...]:
        return {
            ChainType.TACTICAL: self.tactical_refs,
            ChainType.TECHNICAL: self.technical_refs,
            ChainType.NORMATIVE: self.normative_refs,
        }[chain_type]


class BootstrapResolver:
    """Resolve the minimum candidate routes for ContextBuilder.

    Bootstrap resolves routes. It does not materialize document content.
    """

    @staticmethod
    def _candidate_refs(chain: ResolutionChain | None, tactical: ResolutionChain) -> tuple[str, ...]:
        if chain is None or chain.status == ResolutionStatus.NOT_APPLICABLE_JUSTIFIED:
            return ()
        source = tactical if chain.status == ResolutionStatus.SAME_AS_TACTICAL else chain
        refs = [*source.loaded_excerpt_refs, *source.applicable_refs, *source.route_refs]
        return tuple(dict.fromkeys(ref for ref in refs if ref))

    def resolve(self, authority: AuthorityContext) -> BootstrapResolution:
        tactical = authority.tactical_chain_trace
        if tactical.status != ResolutionStatus.RESOLVED:
            raise ValueError("tactical chain must be resolved before bootstrap")

        technical = authority.technical_chain_trace
        normative = authority.normative_chain_trace
        return BootstrapResolution(
            trace_id=f"BT-{uuid4()}",
            tactical_refs=self._candidate_refs(tactical, tactical),
            technical_refs=self._candidate_refs(technical, tactical),
            normative_refs=self._candidate_refs(normative, tactical),
            tactical_chain=tactical,
            technical_chain=technical,
            normative_chain=normative,
        )
