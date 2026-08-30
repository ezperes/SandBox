# P0-2 — TOCTOU Runtime Resume — RevisionGuard convergence

## Status

**READY_FOR_INTEGRATION**, subject to the capability boundary documented below.

Reference base: `worker/core-freshness-gate` @ `530386c35e21066b11ffb5491a52418faae67269`  
Strong guard reference studied: `ae1a7a97a9baecca067628c7d23b06b33b8d3e7d`  
Worker branch: `worker/p0-2-runtime-toctou`

The previous rejected family (`RevisionLeasePort`, `RuntimeResumeFence`, `RevisionSnapshot`, `ResumeExecutionToken`) was removed by resetting the worker branch onto the existing strong Revision Guard line. This implementation creates no second revision/fence family.

## Central answer

Yes: the existing `VersionedReadSet + strong RevisionGuard` can provide the property needed for:

```text
ResumeFreshnessGate.prepare / re-resolution
                 |
                 v
        VersionedReadSet
                 |
                 v
 atomic COMPARE ALL + HOLD
        RevisionGuard
                 |
                 v
     RuntimePort.resume()
        while HOLD active
                 |
                 v
          release guard
```

The guarantee does **not** come from a final check immediately before resume. It comes from the existing guard contract: acquisition compares every mechanical `version_token` in one strong source-side synchronization boundary and, on success, holds those exact source refs against material mutation until Core releases the guard.

`StateManager.resume()` now acquires the canonical guard after preparation and keeps it active across the full synchronous `RuntimePort.resume()` call. Audit `RELEASED` is persisted only after guard acquisition.

## Protected property

For a conforming `SourcePort`, once Core releases a resume:

> no source in the exact `VersionedReadSet` used by that resume can materially advance between successful guard acquisition and return/raise of the synchronous `RuntimePort.resume()` boundary.

If a source changes after `prepare()` but before guard acquisition, acquisition fails with `RevisionConflictError` and runtime is not called.

If a writer attempts to change a protected source after acquisition — including immediately before runtime or concurrently while runtime is executing — the adapter must exclude/reject that mutation until guard release.

This is narrower and demonstrable. It is not an assertion of generic atomicity for arbitrary external storage.

## VersionedReadSet membership

`ResumeFreshnessGate.prepare()` now constructs one `VersionedReadSet` by routing Core reads through the existing `read_versioned_for_sensitive_use()` helper.

At minimum it contains every materially consumed source in these classes:

1. identity source;
2. tactical authority source(s);
3. technical authority source(s);
4. normative authority source(s), when applicable;
5. task source;
6. materialized tactical context source(s);
7. materialized technical context source(s);
8. materialized normative context source(s).

Bootstrap/selection sources read to decide materialization also enter the set because those reads materially influence the prepared context.

### Preserved context after partial rebuild

`ContextBuilder` now retains `materialized_source_refs` separately from TaskContext context/excerpt refs. This is Core provenance, not authority.

A partial rebuild intentionally avoids re-reading unchanged chains. Before returning preparation, `ResumeFreshnessGate` adds those exact preserved materialized source refs to the same `VersionedReadSet` using `read_versioned_for_sensitive_use()`.

If a preserved materialized context exists but exact source provenance is unavailable, resume fails closed instead of guessing that a context ref is a SourcePort source ref.

## Boundary ownership

### Core

Core decides whether resume may proceed, creates the read set, acquires the strong guard, persists revalidation evidence and owns the guard lifetime.

### Source adapter

The adapter supplies mechanism only:

- versioned read;
- atomic compare-all + hold acquisition;
- exclusion of material writes to protected refs while the guard is active;
- release with generation protection.

The adapter does not decide institutional authority.

### Runtime / LangGraph

`RuntimePort` and `LangGraphAdapter` are unchanged by this branch. No institutional identity, policy or authority moves into LangGraph.

The runtime checkpoint remains a technical resume locator. Its ID is used only to validate the requested technical checkpoint and to identify the guard owner/audit boundary; no authority is derived from checkpoint contents.

## Capability boundary / fail closed

The current repository has one source adapter implementation: `InMemorySourceAdapter`. The strong guard reference line already gives it a single `RLock` around COMPARE ALL + ACQUIRE ALL, version tokens that rotate on material mutation, mutation paths that reject protected writes, and guard generations that prevent a stale release from dropping a current hold.

A future/real external source adapter may be used for sensitive runtime resume only if it can provide equivalent semantics through the existing `SourcePort` strong-guard surface:

```python
read_versioned(source_ref) -> VersionedRead
acquire_revision_guard(expected_versions, owner_ref) -> RevisionGuard
release_revision_guard(guard) -> None
```

If an adapter only implements `read()` or implements `read_versioned()` without a strong compare-and-hold boundary, Core fails closed. A mutable remote system whose writers can bypass the adapter's hold does **not** satisfy the contract; it needs a canonical publication/transaction/epoch mechanism behind this same `RevisionGuard` abstraction.

No claim is made that Google Drive, a filesystem, a database, or another provider is automatically linearizable merely because it has revision IDs.

## Synchronous-runtime scope

The hold encloses the synchronous `RuntimePort.resume()` method call.

If a future runtime implementation starts protected work asynchronously and returns before that work stops depending on the authorized sources, the current boundary is insufficient for that adapter. That adapter must keep `RuntimePort.resume()` open for the protected execution segment or the **existing RevisionGuard lifetime contract** must be extended to an explicit begin/complete runtime boundary. A second lease/fence family must not be introduced.

## Repeated resume

`StateManager.resume()` now requires the canonical state to be in a resumable status:

- `INTERRUPTED`;
- `WAITING_APPROVAL`;
- `WAITING_EXTERNAL`.

After a successful runtime resume transitions state to `COMPLETED`, replaying the same checkpoint is rejected before a second runtime call. This is technical checkpoint lifecycle protection, not institutional authority.

## Audit

Successful resume revalidation now records:

- current authority snapshot;
- current TaskContext/bootstrap;
- `VersionedReadSet` audit data;
- acquired `RevisionGuard` audit data;
- final guard state after release.

A conflict records the read set plus `RevisionConflictError.audit_data()` and marks the revalidation `BLOCKED / REVISION_GUARD_REJECTED` before runtime.

These records are evidence; they are not sources of authority.

## Adversarial tests

`tests/test_runtime_resume_revision_guard.py` covers:

1. read-set membership: identity + T/X/N authority + task + materialized context;
2. source changes after prepare and before atomic acquisition;
3. stale identity after prepare;
4. stale technical authority chain after prepare;
5. stale task revision after prepare;
6. stale materialized technical context after prepare;
7. mutation attempted after guard acquisition and immediately before runtime;
8. concurrent writer during `RuntimePort.resume()`;
9. stale guard generation/replay cannot release a current guard;
10. repeated resume does not call runtime twice;
11. source without strong revision capability fails closed.

The existing `tests/test_revision_guard.py` remains the generic conformance suite for the one shared primitive, including compare-all atomicity, concurrent write exclusion, version-token rotation, all-or-nothing multi-source acquisition, fail-closed weak adapters and stale-generation behavior.

## CI evidence

A temporary draft PR was used solely to exercise the repository CI without altering PR #17 or merging anything.

First run intentionally exposed one over-specific new-test assertion: implementation selected authority route sources as material context candidates in addition to CTX refs. Result: `87 passed, 1 failed`. The test was corrected to assert the required coverage instead of an incorrect exact set.

Second run (`Harness Core CI` run `33324008326`, run number `219`) succeeded:

```text
88 passed
17 schemas exported
schema export matches the Git-tracked state
```

All workflow steps passed: install, pytest, schema export and schema drift check.

The temporary CI-only PR must remain unmerged and is closed after final branch validation.

## Failed attempt -> cause -> correct solution

### Failed attempt 1 — prior worker delivery

A new `RevisionLeasePort / RuntimeResumeFence / RevisionSnapshot / ResumeExecutionToken` family was introduced.

**Cause:** it solved the mechanical race shape but duplicated an existing revision protection architecture, creating two competing abstractions for Tool/Runtime fencing.

**Correct solution:** delete/abandon that family and converge Runtime resume onto the existing `VersionedReadSet + RevisionGuard` primitive.

### Failed attempt 2 — check immediately before resume

```text
check rev-A
source -> rev-B
RuntimePort.resume()
```

**Cause:** check and use remain independent operations.

**Correct solution:** one strong guard acquisition performs compare-all + hold; Core invokes `RuntimePort.resume()` while the hold remains active.

### Failed attempt 3 — infer source provenance from context refs

A TaskContext `context_ref` may be an excerpt/context identifier rather than the canonical SourcePort source ref.

**Cause:** protecting the wrong identifier can leave the actual material source outside the guard.

**Correct solution:** `ContextBuildResult` retains exact `materialized_source_refs`; missing provenance fails closed.

## Files changed by this Runtime TOCTOU correction over the strong-guard reference

- `harness/core/context/builder.py`
- `harness/core/freshness/resume.py`
- `harness/core/state/manager.py`
- `tests/test_runtime_resume_revision_guard.py`
- `docs/workers/P0-2-RUNTIME-TOCTOU/IMPLEMENTATION_REPORT.md`

The strong guard infrastructure itself is reused from the reference line; no parallel guard/lease/fence module is added.
