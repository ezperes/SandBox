# IMPLEMENTATION LOG — CORE-FRESHNESS-GATE

## 2026-08-29

- Started from canonical `1a6842310b25474b15f071e074be90bcedf8920f`.
- Created branch `worker/core-freshness-gate`.
- Opened draft PR #17 after initial work-contract commit.
- Canonical priority confirmed: close T11 first with a reusable Core-owned freshness primitive; then reuse the same primitive family at the resume boundary for T10.
- Inspected `ToolGateway`, `AuthorityResolver`, `IdentityResolver`, `ContextBuilder`, `StateManager`, `AuthorityContext`, `ResolutionChain`, `SourcePort`, `InMemorySourceAdapter`, existing tests and CI workflow.
- Implemented `harness.core.freshness.AuthorityFreshnessGate` as a Core-owned fail-closed revision boundary before side effects.
- The T11 gate compares each applicable authority chain's captured `source_revision_refs` with the current canonical `revision_ref` obtained through `SourcePort`.
- Missing authority ref, missing captured revision, unreadable source, missing current revision, or revision mismatch fails closed with `AUTHORITY_UNRESOLVED` in V0.1; canonical error contracts were not expanded silently.
- Integrated T11 freshness into `ToolGateway` before authorization, idempotency reservation and adapter invocation for side-effect tools.
- Added TDD coverage proving current revisions allow execution; rev-A reused after source changes to rev-B is blocked before adapter; missing revision fails closed.
- Implemented `ResumeFreshnessGate` for T10. It re-resolves identity and authority from canonical sources, detects changed authority chains, rebuilds only affected Active Context chains, and returns a fresh authority snapshot/context before `RuntimePort.resume()`.
- Changed `StateManager.resume()` to fail closed when no Core-owned freshness gate is supplied. A successful preparation rebinds `HarnessRun.authority_context_ref` and `task_context_ref` before the runtime boundary.
- Added tests proving a changed tactical revision triggers tactical-only context rebuild while technical context is preserved; an unresolvable changed authority prevents any runtime resume call.
- First T10 CI attempt failed: test assumed Bootstrap materialized only `loaded_excerpt_refs`, but canonical Bootstrap also carries the authority route ref (`AUT-T`). Cause was an over-specific test expectation, not production behavior. Correct solution: assert semantic inclusion/replacement (`CTX-T1` → `CTX-T2`) and preservation of the unaffected technical refs rather than an invalid exact list.
- Final CI run #140: `56 passed in 0.49s`; 17 schemas exported; schema drift clean; job success.
- No canonical contracts or schemas changed.

## failed attempt → cause → correct solution

1. Local clone/test → container could not resolve `github.com` → use GitHub Actions on the PR merge ref as executable evidence.
2. Initial PR creation before first branch commit → GitHub correctly rejected because there were no commits between base and head → create the work-contract commit, then open the draft PR.
3. T10 test expected `tactical_context_refs == [CTX-T1]` → Bootstrap legitimately also materializes route ref `AUT-T` → test the architectural invariant (old excerpt replaced, new excerpt present, unaffected chain preserved) instead of an incorrect exact list.
