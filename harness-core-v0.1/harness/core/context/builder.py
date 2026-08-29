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
    token_usage: dict[str, int]
    estimated_tokens: int


class ContextBuilder:
    """Materialize only the smallest sufficient context from Bootstrap routes."""

    def __init__(self, source: SourcePort, bootstrap: BootstrapResolver | None = None):
        self.source = source
        self.bootstrap = bootstrap or BootstrapResolver()

    def _select(self, refs: Iterable[str], budget: int, seen: set[str]) -> tuple[list[str], dict[str, int]]:
        candidates: list[tuple[int, int, str, bool]] = []
        for ref in refs:
            if ref in seen: continue
            raw = self.source.read(ref)
            candidates.append((int(raw.get("priority", 0)), max(1, int(raw.get("estimated_tokens", 1))),
                str(raw.get("excerpt_ref") or raw.get("context_ref") or ref), bool(raw.get("required", False))))
        candidates.sort(key=lambda item: (not item[3], -item[0], item[1], item[2]))
        selected: list[str] = []; usage: dict[str, int] = {}; used = 0
        for _, tokens, context_ref, required in candidates:
            if context_ref in seen: continue
            if not required and used + tokens > budget: continue
            if required and used + tokens > budget: raise ValueError("context budget is insufficient for required context")
            selected.append(context_ref); seen.add(context_ref); usage[context_ref] = tokens; used += tokens
        return selected, usage

    @staticmethod
    def _field(chain_type: ChainType) -> str:
        return {ChainType.TACTICAL:"tactical_context_refs", ChainType.TECHNICAL:"technical_context_refs",
                ChainType.NORMATIVE:"normative_context_refs"}[chain_type]

    def _task_context(self, *, run_id: str, authority: AuthorityContext, task: dict,
                      bootstrap: BootstrapResolution, chain_refs: dict[ChainType, list[str]]) -> TaskContext:
        return TaskContext(task_context_id=f"TC-{uuid4()}", run_id=run_id,
            tarefa_trabalho_id=str(task["tarefa_trabalho_id"]), current_order=str(task["current_order"]),
            task_state_ref=str(task["task_state_ref"]), authority_context_ref=authority.authority_context_id,
            workspace_ref=str(task["workspace_ref"]), bootstrap_trace_ref=bootstrap.trace_id,
            tactical_context_refs=chain_refs[ChainType.TACTICAL], technical_context_refs=chain_refs[ChainType.TECHNICAL],
            normative_context_refs=chain_refs[ChainType.NORMATIVE], procedural_refs=list(task.get("procedural_refs", [])),
            knowledge_refs=list(task.get("knowledge_refs", [])), risk_refs=list(task.get("risk_refs", [])),
            memory_refs=list(task.get("memory_refs", [])))

    def build(self, run_id: str, authority: AuthorityContext, task_source_ref: str, *, max_context_tokens: int = 4000) -> ContextBuildResult:
        task = self.source.read(task_source_ref); bootstrap = self.bootstrap.resolve(authority)
        seen: set[str] = set(); provenance: dict[str, ChainType] = {}; token_usage: dict[str, int] = {}
        chain_refs: dict[ChainType, list[str]] = {}; remaining = max_context_tokens
        for chain_type in (ChainType.TACTICAL, ChainType.TECHNICAL, ChainType.NORMATIVE):
            selected, usage = self._select(bootstrap.refs_for(chain_type), remaining, seen)
            chain_refs[chain_type] = selected; token_usage.update(usage)
            provenance.update({ref:chain_type for ref in selected}); remaining -= sum(usage.values())
        context = self._task_context(run_id=run_id, authority=authority, task=task, bootstrap=bootstrap, chain_refs=chain_refs)
        return ContextBuildResult(task_context=context, bootstrap=bootstrap, provenance=provenance,
            token_usage=token_usage, estimated_tokens=sum(token_usage.values()))

    def rebuild_partial(self, previous: ContextBuildResult, authority: AuthorityContext, task_source_ref: str,
                        changed_chains: set[ChainType], *, run_id: str | None = None,
                        max_context_tokens: int = 4000) -> ContextBuildResult:
        if not changed_chains: return previous
        task = self.source.read(task_source_ref); bootstrap = self.bootstrap.resolve(authority)
        chain_refs: dict[ChainType, list[str]] = {}; provenance: dict[str, ChainType] = {}; token_usage: dict[str, int] = {}; seen: set[str] = set()
        for chain_type in (ChainType.TACTICAL, ChainType.TECHNICAL, ChainType.NORMATIVE):
            if chain_type in changed_chains: continue
            refs = list(getattr(previous.task_context, self._field(chain_type))); chain_refs[chain_type] = refs
            for ref in refs:
                seen.add(ref); provenance[ref] = chain_type; token_usage[ref] = previous.token_usage.get(ref, 1)
        remaining = max_context_tokens - sum(token_usage.values())
        if remaining < 0: raise ValueError("preserved context already exceeds context budget")
        for chain_type in (ChainType.TACTICAL, ChainType.TECHNICAL, ChainType.NORMATIVE):
            if chain_type not in changed_chains: continue
            selected, usage = self._select(bootstrap.refs_for(chain_type), remaining, seen)
            chain_refs[chain_type] = selected; token_usage.update(usage)
            provenance.update({ref:chain_type for ref in selected}); remaining -= sum(usage.values())
        for chain_type in (ChainType.TACTICAL, ChainType.TECHNICAL, ChainType.NORMATIVE): chain_refs.setdefault(chain_type, [])
        context = self._task_context(run_id=run_id if run_id is not None else previous.task_context.run_id,
            authority=authority, task=task, bootstrap=bootstrap, chain_refs=chain_refs)
        return ContextBuildResult(task_context=context, bootstrap=bootstrap, provenance=provenance,
            token_usage=token_usage, estimated_tokens=sum(token_usage.values()))
