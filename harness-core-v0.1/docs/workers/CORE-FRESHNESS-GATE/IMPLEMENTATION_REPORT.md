# IMPLEMENTATION REPORT — CORE-FRESHNESS-GATE

Status: READY_FOR_INTEGRATION — T11 scope.

## Objective
Close the T11 architectural blocker at the side-effect boundary without introducing a second authority system and without implementing T10 resume semantics opportunistically.

## Base / branch
- BASE_SHA: `1a6842310b25474b15f071e074be90bcedf8920f`
- WORK_BRANCH: `worker/core-freshness-gate`
- Draft PR: #17

## Result
A reusable Core-owned `AuthorityFreshnessGate` now verifies that authority revisions captured in `AuthorityContext` still match current canonical revisions read through `SourcePort`.

`ToolGateway` invokes that gate for side-effect tools before authorization, idempotency reservation, or ToolPort invocation. A stale or unverifiable authority snapshot fails closed, so the external adapter is not called under stale authority.

## Files changed for the functional implementation
- `harness/core/freshness/__init__.py`
- `harness/core/freshness/gate.py`
- `harness/core/tools/gateway.py`
- `tests/test_authority_freshness_gate.py`

## Preserved architecture
- `TÁTICA ∩ TÉCNICA ∩ NORMATIVA`
- `CONTRATOS CANÔNICOS ← CORE ← PORTS ← ADAPTERS ← TECNOLOGIAS EXTERNAS`
- SourcePort remains the boundary to canonical sources.
- Tool adapters do not decide freshness or authority.
- No canonical contract was changed merely to fit the implementation.
- T10 resume behavior remains outside this implementation.

## T11 proof
Required scenario is covered:

`authority rev-A → canonical source changes to rev-B → old AuthorityContext reused → side-effect attempt → freshness mismatch detected before adapter → AUTHORITY_UNRESOLVED/fail-closed → ToolPort not called`

Additional coverage proves current revisions permit the side effect and missing revision data fails closed.

## Validation
GitHub Actions Harness Core CI run #128 succeeded on the PR merge ref:
- Python 3.11.16
- LangGraph 1.2.11 installed
- `53 passed in 0.74s`
- 17 schemas exported
- schema drift clean

## Error semantics
The current V0.1 canonical enum does not expose `CONTEXT_INVALIDATED`. To avoid unauthorized contract expansion, stale freshness currently maps to `AUTHORITY_UNRESOLVED` with an explicit stale-revision message. Formalizing a dedicated invalidation error remains a future contract-version decision.

## Residual risks / next work
- The gate blocks stale side effects but does not yet auto-re-resolve Identity/Authority and rebuild Active Context. The safe current behavior is fail-closed and retry only after re-resolution by a future coordinator.
- T10 remains `CONTRADICTED` until the same primitive is inserted before `RuntimePort.resume()` together with required re-resolution/rebuild semantics.
- T07/T12 can later reuse the revision detector rather than creating another mechanism.
- Temporary worker-only setup markers should be removed before final integration; they are not production dependencies.

## Final worker state
`READY_FOR_INTEGRATION`
