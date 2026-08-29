from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from uuid import uuid4

from harness.contracts import AuthorityContext, ChainType, TaskContext
from harness.ports import SourcePort
from .bootstrap import BootstrapResolution, BootstrapResolver


@dataclass(frozen=True, slots=True)
class ContextBuildResult:
    task_context: TaskContext
    bootstrap: BootstrapResolution
    provenance: dict[str, ChainType]
    estimated_tokens: int


class ContextBuilder:
    """Materialize only the smallest sufficient context from Bootstrap routes."""

    def __init__(self, source: SourcePort, bootstrap: BootstrapResolver | None = None):
        self.source = source
        self.bootstrap = bootstrap or BootstrapResolver()

    def _select(self, refs: Iterable[str], budget: int, seen: set[str]) -> tuple[list[str], int]:
        candidates: list[tuple[int, int, str, bool]] = []
        for ref in refs:
            if ref in seen:
                continue
            raw = self.source.read(ref)
            candidates.append((
                int(raw.get("priority", 0)),
                max(1, int(raw.get("estimated_tokens", 1))),
                str(raw.get("excerpt_ref") or raw.get("context_ref") or ref),
                bool(raw.get("required", False)),
            ))
        candidates.sort(key=lambda item: (not item[3], -item[0], item[1], item[2]))

        selected: list[str] = []
        used = 0
        for _, tokens, context_ref, required in candidates:
            if context_ref in seen:
                continue
            if not required and used + tokens > budget:
                continue
            if required and used + tokens > budget:
                raise ValueError("context budget is insufficient for required context")
            selected.append(context_ref)
            seen.add(context_ref)
            used += tokens
        return selected, used

    def build(
        self,
        run_id: str,
        authority: AuthorityContext,
        task_source_ref: str,
        *,
        max_context_tokens: int = 4000,
    ) -> ContextBuildResult:
        task = self.source.read(task_source_ref)
        bootstrap = self.bootstrap.resolve(authority)
        seen: set[str] = set()
        provenance: dict[str, ChainType] = {}
        remaining = max_context_tokens

        tactical, used = self._select(bootstrap.tactical_refs, remaining, seen)
        remaining -= used
        provenance.update({ref: ChainType.TACTICAL for ref in tactical})

        technical, used = self._select(bootstrap.technical_refs, remaining, seen)
        remaining -= used
        provenance.update({ref: ChainType.TECHNICAL for ref in technical})

        normative, used = self._select(bootstrap.normative_refs, remaining, seen)
        remaining -= used
        provenance.update({ref: ChainType.NORMATIVE for ref in normative})

        context = TaskContext(
            task_context_id=f"TC-{uuid4()}",
            run_id=run_id,
            tarefa_trabalho_id=str(task["tarefa_trabalho_id"]),
            current_order=str(task["current_order"]),
            task_state_ref=str(task["task_state_ref"]),
            authority_context_ref=authority.authority_context_id,
            workspace_ref=str(task["workspace_ref"]),
            bootstrap_trace_ref=bootstrap.trace_id,
            tactical_context_refs=tactical,
            technical_context_refs=technical,
            normative_context_refs=normative,
            procedural_refs=list(task.get("procedural_refs", [])),
            knowledge_refs=list(task.get("knowledge_refs", [])),
            risk_refs=list(task.get("risk_refs", [])),
            memory_refs=list(task.get("memory_refs", [])),
        )
        return ContextBuildResult(
            task_context=context,
            bootstrap=bootstrap,
            provenance=provenance,
            estimated_tokens=max_context_tokens - remaining,
        )

    def rebuild_partial(
        self,
        previous: ContextBuildResult,
        authority: AuthorityContext,
        task_source_ref: str,
        changed_chains: set[ChainType],
        *,
        max_context_tokens: int = 4000,
    ) -> ContextBuildResult:
        if not changed_chains:
            return previous
        if ChainType.TACTICAL in changed_chains and authority.tactical_chain_trace.route_refs != previous.bootstrap.tactical_chain.route_refs:
            pass

        rebuilt = self.build(run_id=previous.task_context.run_id, authority=authority, task_source_ref=task_source_ref, max_context_tokens=max_context_tokens)
        new = rebuilt.task_context.model_copy(deep=True)
        provenance = dict(rebuilt.provenance)

        mapping = {
            ChainType.TACTICAL: "tactical_context_refs",
            ChainType.TECHNICAL: "technical_context_refs",
            ChainType.NORMATIVE: "normative_context_refs",
        }
        for chain_type, field in mapping.items():
            if chain_type in changed_chains:
                continue
            old_refs = list(getattr(previous.task_context, field))
            setattr(new, field, old_refs)
            for ref in old_refs:
                provenance[ref] = chain_type

        return ContextBuildResult(
            task_context=new,
            bootstrap=rebuilt.bootstrap,
            provenance=provenance,
            estimated_tokens=rebuilt.estimated_tokens,
        )
