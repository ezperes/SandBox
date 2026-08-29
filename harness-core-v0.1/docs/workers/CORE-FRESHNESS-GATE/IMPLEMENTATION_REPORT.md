# IMPLEMENTATION REPORT — CORE-FRESHNESS-GATE

Status: READY_FOR_INTEGRATION — T11 closed at side-effect boundary; T10 security path closed, audit persistence still to be formalized.

## Objective
Create one Core-owned freshness/revalidation family reusable by sensitive boundaries, closing T11 first and then preventing resume from reaching `RuntimePort` under stale or unverifiable institutional context.

## Base / branch
- BASE_SHA: `1a6842310b25474b15f071e074be90bcedf8920f`
- WORK_BRANCH: `worker/core-freshness-gate`
- Draft PR: #17

## Result
### T11
`AuthorityFreshnessGate` verifies that authority revisions captured in `AuthorityContext` still match current canonical revisions read through `SourcePort`.

`ToolGateway` invokes that gate for side-effect tools before authorization, idempotency reservation, or ToolPort invocation. A stale or unverifiable authority snapshot fails closed, so the external adapter is not called under stale authority.

### T10
`ResumeFreshnessGate` now re-resolves `AgentIdentity` and `AuthorityContext` from canonical sources before resume, detects changed authority chains and invokes `ContextBuilder.rebuild_partial()` only for affected chains. If freshness cannot be established or a changed authority source cannot resolve, the runtime is never called.

`StateManager.resume()` now requires a Core-owned freshness gate. Without one it fails closed with `AUTHORITY_UNRESOLVED`. On successful preparation it rebinds the run to fresh authority/task-context refs before calling `RuntimePort.resume()`.

## Functional files
- `harness/core/freshness/__init__.py`
- `harness/core/freshness/gate.py`
- `harness/core/freshness/resume.py`
- `harness/core/tools/gateway.py`
- `harness/core/state/manager.py`
- `tests/test_authority_freshness_gate.py`
- `tests/test_resume_freshness_gate.py`
- `tests/test_state_checkpoint.py`

## Preserved architecture
- `TÁTICA ∩ TÉCNICA ∩ NORMATIVA`
- `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`
- SourcePort remains the boundary to canonical sources.
- Tool/runtime adapters do not decide institutional freshness or authority.
- No canonical contract or schema was changed merely to fit the implementation.
- Rebuild is selective by changed authority chain.

## Executable proof
T11:
`authority rev-A → canonical source rev-B → old AuthorityContext reused → side-effect attempt → mismatch before adapter → fail-closed → ToolPort not called`

T10:
`interrupted run → tactical rev-1/context-1 → canonical tactical source changes to rev-2/context-2 → resume attempt → identity/authority re-resolved → tactical Active Context rebuilt while unaffected technical context is preserved → only then RuntimePort.resume()`

Negative T10:
`changed authority source becomes unresolvable → freshness preparation fails → RuntimePort.resume() call count remains zero`.

## Validation
Final GitHub Actions Harness Core CI run #140 succeeded on the PR merge ref:
- Python 3.11.16
- `56 passed in 0.49s`
- 17 schemas exported
- schema drift clean

An earlier T10 CI run failed because the test incorrectly assumed Bootstrap materialized only excerpt refs. Inspection showed the authority route ref is legitimately part of the materialized route. The test was corrected to assert the architectural invariant rather than an invalid exact list.

## Error semantics
The V0.1 canonical enum still has no `CONTEXT_INVALIDATED`. To avoid unauthorized contract expansion, stale/unverifiable freshness maps to `AUTHORITY_UNRESOLVED` with explicit revision context.

## Residual risk
The runtime can no longer be reached through `StateManager.resume()` without Core-owned freshness preparation, and stale authority chains are re-resolved/rebuilt before resume. However, V0.1 does not yet provide a dedicated persistence port for the newly produced `AuthoritySnapshot`, Bootstrap trace and TaskContext as first-class historical records during resume. The preparation objects/refs exist in-process and the run is rebound, but full audit persistence must be addressed before T10 should be classified `PROVEN` rather than `PARTIAL`.

T07/T12 should reuse the same revision detector/freshness family rather than introducing parallel mechanisms.

## Final worker state
`READY_FOR_INTEGRATION`
