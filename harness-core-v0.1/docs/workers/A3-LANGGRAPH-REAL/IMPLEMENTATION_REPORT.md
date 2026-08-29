# A3-LANGGRAPH-REAL — Implementation Report

## Status

`READY_FOR_INTEGRATION`

This worker does not declare the global Harness increment complete. Integration, joint CI, incongruence review, global CODE_MAP consolidation, and final completion remain Integrator responsibilities.

## Identity

- WORK_TASK_ID: `A3-LANGGRAPH-REAL`
- BASE_BRANCH: `harness-core-v0.1`
- BASE_SHA: `59d3eb987136ec628bcaba4b45949fb81b2616a2`
- WORK_BRANCH: `worker/a3-langgraph-real`
- Draft PR for CI/integration review: `#1`
- Code HEAD validated before this report: `d5bd7e2121b1785561b09ee38984153d6216a934`

## Objective and result

Objective: replace the previous stub-only proof with an executable integration against the real LangGraph library while keeping LangGraph a replaceable Runtime Adapter.

Result: achieved for the V0.1 RuntimePort contract.

The branch proves with LangGraph `1.2.11`:

- real `StateGraph` construction;
- real compiled graph;
- real `MemorySaver` checkpointer;
- real static interrupt/breakpoint before a graph node;
- real resume on the same persisted LangGraph thread;
- `HarnessRun.run_id` projected as LangGraph `thread_id`;
- translation of native graph state into canonical `RunState`;
- technical LangGraph checkpoint ID distinct from canonical Core `Checkpoint` reference;
- runtime cannot inject canonical `decision_refs` or `checkpoint_ref` through the adapter;
- runtime input does not receive canonical `agent_id` or `authority_context_ref`;
- FakeRuntime/Core execution succeeds even when every `langgraph*` import is blocked;
- LangGraph remains absent from mandatory Core dependencies.

## Environment and versions

Validated in GitHub Actions:

- Ubuntu 24.04 runner;
- CPython `3.11.16`;
- LangGraph `1.2.11`;
- langgraph-checkpoint `4.2.0`;
- pytest `8.4.2`;
- Pydantic `2.13.5`.

LangGraph `1.2.11` was selected after checking the current PyPI release and current official LangGraph interrupt/persistence documentation.

## Files changed

| File | Purpose |
|---|---|
| `harness-core-v0.1/pyproject.toml` | Pin `langgraph==1.2.11` as optional runtime extra and dev dependency, not Core dependency. |
| `harness-core-v0.1/tests/test_langgraph_real.py` | Real StateGraph/checkpointer/interrupt/resume proof and Core-without-LangGraph proof. |
| `harness-core-v0.1/harness/adapters/runtimes/langgraph/runtime.py` | Clarify that V0.1 `resume()` uses LangGraph static-interrupt semantics because RuntimePort has no resume payload. No institutional semantics added. |
| `harness-core-v0.1/docs/workers/A3-LANGGRAPH-REAL/IMPLEMENTATION_LOG.md` | Work contract, decisions, divergence, opportunity, failed attempt and evidence trail. |
| `harness-core-v0.1/docs/workers/A3-LANGGRAPH-REAL/IMPLEMENTATION_REPORT.md` | This integration handoff report. |

No canonical contract, IdentityResolver, AuthorityResolver, ToolGateway, or institutional state semantics were changed.

## Implementation sequence

1. Resolve and freeze `BASE_SHA` from the integrator branch.
2. Read the runtime port, fake runtime, LangGraph adapter, canonical run/checkpoint models, StateManager, and runtime tests.
3. Verify that the previous proof used `StubGraph` only.
4. Research current LangGraph package/API.
5. Pin LangGraph as optional/dev dependency.
6. Add executable real-LangGraph integration test.
7. Open a draft PR only to execute repository CI.
8. Run adversarial diff review.
9. Strengthen the proof with a clean subprocess where `langgraph*` imports are deliberately blocked and FakeRuntime still executes.
10. Re-run CI and record evidence.

## Validation and evidence

GitHub Actions workflow: `Harness Core CI`, run `33276935563` against code HEAD `d5bd7e2121b1785561b09ee38984153d6216a934`.

Results:

- `python -m pip install -e '.[dev]'`: PASS; log explicitly shows installation of `langgraph-1.2.11`.
- `pytest`: PASS — `43 passed in 0.59s`.
- `python scripts/export_schemas.py`: PASS — `17 schemas` exported.
- `git diff --exit-code -- harness/schemas`: PASS.
- PR mergeability after validation: mergeable, draft, unmerged.

The earlier code HEAD `558d6734fdd7659d53eef000feb589b8e671581f` also passed CI with `42 passed`; the additional test then strengthened the Core-without-LangGraph proof.

## Contract/invariant checks

| Invariant | Evidence |
|---|---|
| LangGraph is replaceable | Mandatory dependencies contain only Pydantic; LangGraph is an optional extra. |
| Core executes without LangGraph | Subprocess blocks all `langgraph*` imports and executes `FakeRuntimeAdapter` successfully. |
| Identity is Core-owned | Adapter input excludes `agent_id`; real graph records observed input keys and test asserts absence. |
| Authority is Core-owned | Adapter input excludes `authority_context_ref`; test asserts absence in real graph state. |
| Canonical checkpoint is Core-owned | `StateManager.checkpoint()` creates/persists canonical `Checkpoint`; real test separately observes LangGraph technical `checkpoint_id`. |
| Technical checkpoint != canonical checkpoint | Test asserts LangGraph checkpoint ID differs from `CP-CANONICAL-1`. |
| Canonical refs cannot be injected | Existing adapter regression behavior is preserved; resume carries prior Core refs. |
| Traceability | LangGraph `thread_id` equals `HarnessRun.run_id`. |
| No silent contract expansion | `RuntimePort`, `RunState`, `Checkpoint` and other canonical contracts remain unchanged. |

## INTERPRETATION_DIVERGENCE

Question: should “real interrupt/resume” require dynamic `interrupt()` + `Command(resume=<payload>)` specifically?

Decision for this worker: no contract expansion. The current canonical `RuntimePort.resume(run, state)` contains no external resume payload. LangGraph's current API requires `Command(resume=<payload>)` for dynamic interrupts, whereas static interrupts/breakpoints are real persisted interrupts and resume on the same thread with `invoke(None)`.

Therefore A3 uses real static interrupt semantics compatible with the existing port. Inventing an approval/decision payload inside the adapter would risk giving runtime mechanics institutional authority.

Dynamic HITL resume payload remains a separate Core contract decision.

## OPPORTUNITY_FOUND

Future contract increment: define a Core-owned resume-input object if dynamic LangGraph `interrupt()` or equivalent HITL mechanisms are needed across runtimes.

Recommended flow:

`external decision → Core authority/policy validation → canonical resume input → RuntimePort projection → Command(resume=...)`

Value-chain impact: runtime portability → HITL interoperability → safer approvals. Main benefit is avoiding later adapter-specific resume conventions and rework.

## Failed attempt → cause → correct solution

- Failed attempt: clone the repository into the execution container and install/run LangGraph locally.
- Cause: container could not resolve `github.com`; LangGraph was not preinstalled.
- Correct solution: use the connected GitHub repository for isolated branch writes and GitHub Actions as the executable environment. CI then installed the exact pinned package and ran the real integration test successfully.

## Commits

- `8630d425f5623755e40a1200e2522f3f85507bd3` — optional/dev LangGraph pin.
- `ef0cee57f99f14a03793409dbb12340a59ca0a53` — initial real LangGraph integration test.
- `9af8e998e4bd696037ac25c18694feef2ab575d5` — clarify V0.1 resume boundary.
- `558d6734fdd7659d53eef000feb589b8e671581f` — implementation log.
- `d5bd7e2121b1785561b09ee38984153d6216a934` — strengthen Core-without-LangGraph execution proof.

## Worker code map

No global `docs/CODE_MAP.md` edit was made because shared/global documentation belongs to the Integrator in parallel execution.

A3-local map:

`RuntimePort → LangGraphAdapter → compiled StateGraph`

`HarnessRun.run_id → configurable.thread_id → LangGraph technical checkpoint`

`LangGraph native dict → LangGraphAdapter._canonical_state() → RunState`

`StateManager → canonical RunState + canonical Checkpoint`

`FakeRuntimeAdapter → RuntimePort` independently of LangGraph.

## Minimum reproduction

From repository root:

```bash
cd harness-core-v0.1
python -m pip install -e '.[dev]'
pytest
python scripts/export_schemas.py
git diff --exit-code -- harness/schemas
```

Expected test result at the validated code HEAD: `43 passed`.

For the focused physical proof:

```bash
pytest -q tests/test_langgraph_real.py
```

Expected: all A3 real-runtime tests pass.

## Residual risks

1. Dynamic `interrupt()` resume payload is intentionally not implemented because the canonical RuntimePort lacks such a contract.
2. `MemorySaver` proves physical semantics but is not a durable production store; selecting a durable checkpointer is deployment/runtime configuration, not canonical state ownership.
3. Existing audit item B3 remains: a runtime-native `harness_status=COMPLETED` must not be treated by system composition as institutional completion before Core verification gates. A3 does not alter that existing architectural rule.

## Handoff

`READY_FOR_INTEGRATION`

Integrator should review PR `#1`, verify combined CI against concurrent workers, reconcile global CODE_MAP/audit documents, and decide whether dynamic resume-input deserves a later canonical contract increment.
