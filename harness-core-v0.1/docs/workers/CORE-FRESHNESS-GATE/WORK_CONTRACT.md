# WORK CONTRACT — CORE-FRESHNESS-GATE

WORK_TASK_ID: `CORE-FRESHNESS-GATE`
BASE_BRANCH: `harness-core-v0.1`
BASE_SHA: `1a6842310b25474b15f071e074be90bcedf8920f`
WORK_BRANCH: `worker/core-freshness-gate`

## Objective
Implement a Core-owned freshness/revision boundary that prevents stale authority/context from crossing a sensitive boundary, starting with T11 before ToolPort side effects and designed for later reuse by T10 resume.

## Read set
- `harness/core/authority/**`
- `harness/core/context/**`
- `harness/core/tools/**`
- `harness/core/state/**`
- `harness/ports/**`
- relevant contracts, source adapters and tests

## Write set
- Core freshness/revalidation module(s)
- minimal ToolGateway wiring required for T11
- focused tests
- this worker documentation

## Protected set
- canonical contract semantics unless an explicit blocker requires escalation
- LangGraph adapter/runtime semantics
- provider/model identity semantics
- unrelated delegation/cross-domain features

## Acceptance
1. A context resolved from rev-A cannot authorize a new side effect after its canonical authority source changed to rev-B without freshness validation.
2. Mismatch is detected before ToolPort invocation.
3. The Core either re-resolves to a current safe AuthorityContext or fails closed/ESCALATE.
4. Historical snapshot/revision evidence remains traceable.
5. Existing A1/A2/A3/A5 behavior remains green.
6. Freshness primitive is reusable by T10 without implementing T10 opportunistically in this increment.
