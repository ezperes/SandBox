# A3-LANGGRAPH-REAL — Implementation Log

## Work contract

- WORK_TASK_ID: `A3-LANGGRAPH-REAL`
- BASE_BRANCH: `harness-core-v0.1`
- BASE_SHA: `59d3eb987136ec628bcaba4b45949fb81b2616a2`
- WORK_BRANCH: `worker/a3-langgraph-real`
- objective: prove a real LangGraph runtime integration without moving identity, authority, policy, competence, canonical checkpoint semantics, or institutional state into LangGraph.
- write scope: LangGraph adapter, A3 tests, LangGraph dependency configuration, this worker documentation.

## API/version investigation

- Stable LangGraph selected: `1.2.11` (PyPI release 2026-08-11).
- Current official API confirms `StateGraph`, compiled graphs, checkpointers, `thread_id`, static interrupts/breakpoints, dynamic `interrupt()`, and `Command(resume=...)`.
- LangGraph is kept outside `[project].dependencies`; it is an explicit optional runtime extra and a dev dependency only so CI can execute the real integration test.

## Implementation sequence

1. Resolved the integrator branch to the frozen BASE_SHA above.
2. Inspected `RuntimePort`, `FakeRuntimeAdapter`, `LangGraphAdapter`, `HarnessRun`, `RunState`, `Checkpoint`, and runtime tests.
3. Confirmed the previous A3 proof used only `StubGraph`, not a LangGraph object.
4. Added exact optional/dev dependency `langgraph==1.2.11`.
5. Added `tests/test_langgraph_real.py` using a real `StateGraph`, real compile, `MemorySaver`, static interrupt before a node, native state inspection, and resume through the existing adapter.
6. Clarified the adapter comment so `invoke(None)` is explicitly limited to V0.1 static-interrupt semantics.

## Evidence targeted by the real test

- real `StateGraph` and compiled graph;
- real in-memory LangGraph checkpointer;
- real pause before `step_two`;
- real persisted `thread_id == HarnessRun.run_id`;
- real technical `checkpoint_id` exists;
- technical checkpoint ID is distinct from canonical `Checkpoint` reference;
- runtime input does not receive `agent_id` or `authority_context_ref`;
- canonical decision/checkpoint refs survive resume and are not injected by LangGraph;
- core dependency set does not include LangGraph;
- exact LangGraph version is asserted in the test environment.

## INTERPRETATION_DIVERGENCE

**Question:** Does A3 require dynamic `interrupt()` specifically, or a real LangGraph interrupt/resume compatible with the current `RuntimePort`?

- Interpretation A: dynamic `interrupt()` + `Command(resume=<external payload>)` is mandatory.
- Interpretation B: a real static interrupt/breakpoint + same-thread `invoke(None)` satisfies A3 while preserving the current canonical `RuntimePort.resume(run, state)` contract.
- Evidence for A: current LangGraph documentation recommends dynamic interrupts for HITL and requires `Command(resume=...)` to pass the external value.
- Evidence for B: current LangGraph documentation also supports static `interrupt_before`/`interrupt_after`; these are resumed by re-invoking the same thread with `None` and require a checkpointer/thread ID.
- Recommendation for V0.1: B. The canonical port has no resume-payload parameter. Inventing an approval value in the adapter would risk giving runtime mechanics institutional meaning.
- Impact if A were silently chosen: it would require changing `RuntimePort`/canonical resume semantics or smuggling a decision payload through runtime state.
- Escalation: not blocking for A3's runtime proof; dynamic HITL payload support is a separate contract decision.

## OPPORTUNITY_FOUND

Future increment: define an explicit Core-owned resume-input contract if dynamic `interrupt()` is required for human/external decisions. The Core should resolve/authorize the decision first and only then project a non-authoritative resume payload to the runtime adapter.

- chain of value: runtime portability → HITL interoperability → safer approval flows.
- impact: high for future HITL breadth; no direct V0.1 requirement.
- acceleration/rework: avoids each runtime adapter inventing incompatible resume-payload conventions.

## Failed attempt → cause → correct path

- Attempt: clone `https://github.com/ezperes/SandBox.git` into the execution container for local integration tests.
- Failure: container DNS/network could not resolve `github.com`; LangGraph was also not preinstalled locally.
- Cause: execution container network limitation, not repository/code failure.
- Correct path: use the connected GitHub repository for isolated writes and GitHub Actions for the executable dependency/test proof.

## Pending

- Execute GitHub CI against the worker branch through a pull request.
- Record CI result and final HEAD SHA in `IMPLEMENTATION_REPORT.md`.
