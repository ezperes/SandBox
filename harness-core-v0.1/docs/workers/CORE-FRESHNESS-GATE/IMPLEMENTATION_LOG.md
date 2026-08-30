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
- Implemented auditable persistence of freshness/revalidation evidence before resume. Added internal `RevalidationAuditRecord`, StatePort save/load methods, InMemoryStateAdapter storage, and linkage from canonical `RunState.decision_refs` to the persisted `RV-*` record.
- The persisted record captures: previous authority/task-context refs, the newly resolved `AuthoritySnapshot`, the new authority context ref, serialized `TaskContext`, Bootstrap trace, changed chains, identity-change flag and boundary name.
- `StateManager.resume()` now persists that revalidation record and the RunState pointer before invoking `RuntimePort.resume()`. A runtime-facing test proves the audit record already exists when the adapter is entered.
- First audit-persistence CI attempt failed because an older `PassFreshnessGate` test double returned only authority/context IDs and did not satisfy the now-explicit preparation contract (`authority_snapshot`, `changed_chains`, `identity_changed`, Bootstrap trace). Production behavior was correct. The test double was upgraded to represent the actual freshness preparation interface.
- Final audit-persistence CI run #149: `57 passed in 0.58s`; 17 schemas exported; schema drift clean; job success.
- No canonical Pydantic contract or generated schema changed; the new revalidation record remains an internal Core/StatePort persistence artifact in V0.1.

## failed attempt → cause → correct solution

1. Local clone/test → container could not resolve `github.com` → use GitHub Actions on the PR merge ref as executable evidence.
2. Initial PR creation before first branch commit → GitHub correctly rejected because there were no commits between base and head → create the work-contract commit, then open the draft PR.
3. T10 test expected `tactical_context_refs == [CTX-T1]` → Bootstrap legitimately also materializes route ref `AUT-T` → test the architectural invariant (old excerpt replaced, new excerpt present, unaffected chain preserved) instead of an incorrect exact list.
4. Legacy `PassFreshnessGate` test double omitted persisted-revalidation inputs → new resume boundary correctly requires a complete preparation record → update the test double to the real preparation shape instead of weakening production persistence.
