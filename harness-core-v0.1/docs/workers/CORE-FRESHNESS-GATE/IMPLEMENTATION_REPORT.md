# IMPLEMENTATION REPORT — CORE-FRESHNESS-GATE

Status: READY_FOR_INTEGRATION — T11 side-effect freshness gate implemented; T10 resume freshness + audit persistence implemented.

## Objective
Create one Core-owned freshness/revalidation family reusable by sensitive boundaries, closing T11 first and then preventing resume from reaching `RuntimePort` under stale or unverifiable institutional context while preserving an auditable revalidation trail.

## Base / branch
- BASE_SHA: `1a6842310b25474b15f071e074be90bcedf8920f`
- WORK_BRANCH: `worker/core-freshness-gate`
- Draft PR: #17

## Result
### T11
`AuthorityFreshnessGate` verifies that authority revisions captured in `AuthorityContext` still match current canonical revisions read through `SourcePort`.

`ToolGateway` invokes that gate for side-effect tools before authorization, idempotency reservation, or ToolPort invocation. A stale or unverifiable authority snapshot fails closed, so the external adapter is not called under stale authority.

### T10
`ResumeFreshnessGate` re-resolves `AgentIdentity` and `AuthorityContext` from canonical sources before resume, detects changed authority chains and invokes `ContextBuilder.rebuild_partial()` only for affected chains. If freshness cannot be established or a changed authority source cannot resolve, the runtime is never called.

`StateManager.resume()` requires a Core-owned freshness gate. On successful preparation it creates and persists a `RevalidationAuditRecord` before `RuntimePort.resume()`, rebinds the run to the fresh authority/task-context refs, links the `RV-*` record through `RunState.decision_refs`, persists that state, and only then crosses the runtime boundary.

The audit record preserves:
- previous authority context ref;
- previous task context ref;
- fresh `AuthoritySnapshot` including source revision refs;
- fresh authority context ref;
- serialized `TaskContext`;
- Bootstrap trace and route refs;
- changed authority chains;
- identity-change flag;
- sensitive boundary name and timestamp.

`RevalidationAuditRecord` is deliberately an internal Core persistence artifact in V0.1, not a new canonical Pydantic/institutional contract.

## Functional files
- `harness/core/freshness/__init__.py`
- `harness/core/freshness/gate.py`
- `harness/core/freshness/resume.py`
- `harness/core/freshness/audit.py`
- `harness/core/tools/gateway.py`
- `harness/core/state/manager.py`
- `harness/ports/__init__.py`
- `harness/adapters/state/in_memory.py`
- `tests/test_authority_freshness_gate.py`
- `tests/test_resume_freshness_gate.py`
- `tests/test_state_checkpoint.py`

## Preserved architecture
- `TÁTICA ∩ TÉCNICA ∩ NORMATIVA`
- `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`
- SourcePort remains the boundary to canonical sources.
- Tool/runtime adapters do not decide institutional freshness or authority.
- No canonical Pydantic contract or generated schema was changed merely to fit the implementation.
- Rebuild is selective by changed authority chain.
- Audit persistence happens before the runtime boundary and remains owned by Core/StatePort.

## Executable proof
T11:
`authority rev-A → canonical source rev-B → old AuthorityContext reused → side-effect attempt → mismatch before adapter → fail-closed → ToolPort not called`

T10 changed-chain path:
`interrupted run → tactical rev-1/context-1 → canonical tactical source changes to rev-2/context-2 → resume attempt → identity/authority re-resolved → tactical Active Context rebuilt while unaffected technical context is preserved → revalidation record persisted → RunState points to RV-* → RuntimePort.resume()`

T10 audit-order proof:
`StateManager.resume() → persist RV-* record + RunState decision ref → adapter entered → adapter can already load the same RV-* record`.

Negative T10:
`changed authority source becomes unresolvable → freshness preparation fails → no RV-* record persisted → RuntimePort.resume() call count remains zero`.

## Validation
Final GitHub Actions Harness Core CI run #149 succeeded on the PR merge ref:
- Python 3.11.16
- `57 passed in 0.58s`
- 17 schemas exported
- schema drift clean

Two relevant failed attempts were retained as evidence:
1. T10 test initially assumed Bootstrap exact refs and failed because canonical Bootstrap legitimately includes the authority route ref. Corrected the test to the architectural invariant rather than altering production behavior.
2. First audit-persistence run failed because a legacy `PassFreshnessGate` test double did not implement the now-required preparation evidence. Corrected the test double to the real interface; production persistence was not weakened.

## Error semantics
The V0.1 canonical enum still has no `CONTEXT_INVALIDATED`. To avoid unauthorized contract expansion, stale/unverifiable freshness maps to `AUTHORITY_UNRESOLVED` with explicit revision context.

## Residual risk / audit status
The previously identified executable T10/T11 stale paths are now blocked by Core-owned boundaries. T10 additionally has persisted revalidation evidence before resume. This implementation is therefore ready for independent architectural reclassification; it does not itself declare T10/T11 globally `PROVEN` because that status belongs to the integrator/auditor after re-running T07/T10/T11/T12 against the composed branch.

T07/T12 should reuse the same revision detector/freshness family rather than introducing parallel mechanisms.

## Final worker state
`READY_FOR_INTEGRATION`
