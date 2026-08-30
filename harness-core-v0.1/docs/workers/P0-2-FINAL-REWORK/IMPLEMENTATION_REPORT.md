# P0-2-INTEGRATOR — REWORK FINAL B1+B2

Status: `READY_FOR_INDEPENDENT_REAUDIT` pending CI on this exact report/freeze commit.

## Candidate

- Integration branch: `integration/p0-2-final-rework`
- Fixed rework base: `5a18ce034987b14617442fc48194bd9dec2f87f2`
- Worker A / B1 final SHA: `3d019d1fe8ce64b939d3337449e5e8d18b3528a3`
- Worker B / B2 final SHA: `4631d7d694d6341c2e191878ab78375c97885962`
- Last green implementation candidate before freeze documentation: `34a2f2d2f82418a29de87b880a1fd68f276ea0bd`
- Focused-evidence candidate: `de85ad06122bfc8e0baebf70ed526a94a412c8a5`
- CI-only PR: `#40`, draft, base `integration/p0-2-freshness-consolidated@5a18ce034987b14617442fc48194bd9dec2f87f2`; DO NOT MERGE.
- PR #17 was not merged or moved by this rework.
- PR #39 was not merged or moved by this rework.
- Canonical branch `harness-core-v0.1` was not merged or modified by this rework.

## Scope lock

The independent Phase-2 audit of exactly `5a18ce034987b14617442fc48194bd9dec2f87f2` identified only two blockers:

- **B1** — concurrent checkpoint replay;
- **B2** — incomplete Runtime success TRACE.

This rework changes production only for those two blockers. It does not reopen or redesign:

- Tool TOCTOU;
- Runtime revision TOCTOU;
- `VersionedReadSet / RevisionGuard`;
- authority execution binding;
- resume context isolation;
- runtime state firewall;
- cross-run real-world effect claim;
- T07;
- T11;
- T12.

## Production files changed from the fixed base

B1:

- `harness/core/state/manager.py`
- `harness/adapters/state/in_memory.py`
- `harness/ports/__init__.py`

B2:

- `harness/core/freshness/audit.py`

No ToolGateway, source versioning, RevisionGuard, authority resolver, context resolver, identity resolver, model/tool ports, or runtime adapter production files were changed.

## Test/evidence files

- `tests/test_resume_atomic_claim.py` — Worker A B1 regressions preserved;
- `tests/test_runtime_terminal_trace.py` — Worker B B2 regressions preserved;
- `tests/test_p0_2_final_rework_integration.py` — B1+B2 ordering/failure integration regressions;
- `tests/test_resume_freshness_gate.py` — one obsolete success-trace assertion strengthened to require B2 terminal `COMPLETED`; freshness assertions preserved;
- `tests/test_p0_2_red_team_revision_guard_convergence.py` — existing RT-12 tripwire strengthened to include all six prohibited duplicate-family symbols.

Temporary focused CI steps were used only to capture separated evidence and were removed afterward.

One non-production CI hardening remains intentionally in `.github/workflows/harness-core-ci.yml`: `actions/checkout` explicitly selects `${{ github.event.pull_request.head.sha || github.sha }}`. This is required by the second-freeze protocol so the final gate executes the exact candidate commit rather than GitHub's synthetic pull-request merge ref. It does not alter Harness production semantics.

## Git conflicts

No Git/content conflict remained in the consolidated tree.

One tooling attempt to move a synthesized commit ref was rejected by the connector before mutation; integration then continued through normal Contents API fast-forward writes on the branch created from the fixed base. This was a tooling-path rejection, not a repository merge conflict.

## Semantic conflicts resolved

There was one required B1+B2 composition point in `StateManager.resume()`:

- Worker A ended successful resume with canonical state persistence followed by resume-claim completion.
- Worker B supplied terminal Runtime TRACE finalization but deliberately did not wire it into `StateManager`.

The consolidated ordering inserts B2 terminal TRACE between canonical state persistence and B1 claim completion. No competing architecture was introduced.

## Final success path

```text
load Checkpoint + RunState
-> RunStateBindingGuard
-> Resume Status Policy
-> ATOMIC RESUME CLAIM
-> audit PENDING
-> ResumeFreshnessGate
-> VersionedReadSet
-> RevisionGuard ACTIVE
-> audit REVALIDATED_AND_GUARDED
-> RuntimePort.resume()
-> runtime-state firewall
-> merge canonical
-> save_run_state(resumed)
-> finalize_runtime_resume_success(released)
-> save_revalidation_record(COMPLETED)
-> complete resume claim
-> return resumed
```

The Runtime terminal TRACE cannot become `COMPLETED` before all of these have happened:

1. `RuntimePort.resume()` returned;
2. runtime-state firewall/validation passed;
3. canonical merge was accepted;
4. `save_run_state(resumed)` completed successfully.

## B1 — atomic resume claim

Resume exclusivity is a separate invariant from revision protection.

Claim identity is exactly:

```text
run_id
+ tarefa_trabalho_id
+ run_state_id
+ checkpoint_id
```

Persisted representation:

- `operation = RuntimePort.resume`;
- ledger key remains run-scoped;
- business key is canonical JSON `[tarefa_trabalho_id, run_state_id, checkpoint_id]`.

Lifecycle:

- absent → atomic `PENDING` winner;
- existing `PENDING` → `RETRY_BLOCKED`;
- `COMPLETED` → consumed permanently;
- proven pre-runtime `FAILED` → whole-record CAS `FAILED -> PENDING`; at most one retry winner;
- post-runtime uncertainty → `UNKNOWN` + `reconciliation_required=True`; no blind retry.

`StatePort.compare_and_swap_idempotency_record()` is explicitly a mechanical linearizable CAS capability. It is not policy and it is not a revision fence. `InMemoryStateAdapter` implements it under its existing process-local lock. A future distributed StatePort must provide an equivalent datastore CAS/transaction, not read-then-write emulation.

## B2 — terminal Runtime success TRACE

`finalize_runtime_resume_success(record)` is wired only after canonical state persistence.

Successful temporal history is exactly:

```text
PENDING
-> RELEASED / REVALIDATED_AND_GUARDED
-> RELEASED / COMPLETED
```

The helper is pure and fail-closed:

- requires `boundary == RuntimePort.resume`;
- requires `status == RELEASED`;
- requires `outcome == REVALIDATED_AND_GUARDED`;
- refuses FAILED/BLOCKED/inconsistent histories;
- repeated terminalization is idempotent and does not append a second `COMPLETED` event.

## Failure ordering

Final ordering:

```text
save_run_state(resumed)
-> persist Runtime TRACE COMPLETED
-> complete resume claim
```

### Runtime/firewall failure

No terminal `COMPLETED` is emitted. Since Runtime was invoked, the resume claim becomes `UNKNOWN` with `reconciliation_required=True`. Replay is blocked.

### Canonical RunState persistence failure after Runtime

The pre-boundary `REVALIDATED_AND_GUARDED` TRACE remains non-terminal. No false `COMPLETED` exists. Resume claim becomes `UNKNOWN`; stale `INTERRUPTED` replay remains blocked.

### Terminal TRACE persistence failure after Runtime + canonical state

Canonical state may already be `COMPLETED`, but terminal TRACE was not persisted. Resume claim becomes `UNKNOWN`; no blind retry is authorized. A stale status rewrite still cannot replay the checkpoint.

### Claim COMPLETED persistence failure after terminal TRACE

The Runtime TRACE is terminal `COMPLETED`, but failure to persist claim completion cannot reopen execution. The outer conservative handler leaves/marks the claim fail-closed as `UNKNOWN` when possible; stale replay is blocked. No bookkeeping failure after Runtime authorizes retry.

### Proven pre-runtime failure

Claim becomes `FAILED`, which is the only state eligible for controlled reopening. Reopening is whole-record CAS and therefore admits at most one concurrent retry winner.

## B1 regression results

Focused file: `tests/test_resume_atomic_claim.py`

Result on focused-evidence candidate `de85ad06122bfc8e0baebf70ed526a94a412c8a5`: **10 passed**.

Mandatory properties:

1. 2 concurrent callers, same checkpoint → Runtime exactly once: **PASS**;
2. 8 concurrent callers → exactly one winner: **PASS**;
3. second caller → deterministic `RETRY_BLOCKED`: **PASS**;
4. sequential replay → blocked: **PASS**;
5. new `StateManager` + stale `INTERRUPTED` → persisted claim blocks replay: **PASS**;
6. runtime exception after boundary → `UNKNOWN + reconciliation_required`: **PASS**;
7. proven pre-runtime `FAILED` → CAS permits at most one retry winner: **PASS**;
8. different checkpoints → independent claims: **PASS**.

Additional B1 checks preserved binding-before-claim, exact claim identity, stale/unresolvable source pre-runtime behavior, and persisted claim semantics.

## B2 regression results

Focused file: `tests/test_runtime_terminal_trace.py`

Result on focused-evidence candidate: **6 passed**.

Mandatory properties:

9. successful Runtime trace `PENDING -> REVALIDATED_AND_GUARDED -> COMPLETED`: **PASS**;
10. previous events preserved: **PASS**;
11. run/agent/task/correlation/authority/read-set/guard attribution preserved: **PASS**;
12. Runtime failure does not receive `COMPLETED`: **PASS**;
13. firewall failure does not receive `COMPLETED`: **PASS**;
14. `save_run_state` failure does not receive `COMPLETED`: **PASS**;
15. duplicate terminalization does not create two `COMPLETED` events: **PASS**.

Items 13 and 14 are additionally exercised by the integrated B1+B2 failure-injection suite because they require `StateManager` wiring.

## Integrated B1+B2 results

Focused file: `tests/test_p0_2_final_rework_integration.py`

Result on focused-evidence candidate: **8 passed**.

Mandatory integrated properties:

16. concurrent loser creates no terminal `COMPLETED`: **PASS**;
17. only the atomic-claim winner owns the successful Runtime boundary trace: **PASS**;
18. terminal TRACE persistence failure after Runtime does not release resume for retry: **PASS**;
19. claim `COMPLETED` persistence failure does not release resume for retry: **PASS**;
20. `RevisionGuard` remains ACTIVE during `RuntimePort.resume()`: **PASS**;
21. stale revision at guard acquisition still blocks before Runtime: **PASS**.

Additional integrated checks:

- firewall failure → no success terminal, claim `UNKNOWN`;
- canonical state save failure → no success terminal, claim `UNKNOWN`, replay blocked;
- terminal TRACE failure → state may persist but claim remains fail-closed, replay blocked;
- claim completion failure → terminal TRACE remains singular, claim fail-closed, replay blocked;
- concurrent CAS reopening of proven `FAILED` → one winner only.

## Red Team regression result

Focused command:

```text
pytest -q tests/test_p0_2_red_team_adversarial.py tests/test_p0_2_red_team_revision_guard_convergence.py
```

Result: **12 passed**.

Technical mapping:

| ID | Threat | Technical result |
|---|---|---|
| RT-01 | cross-run/cross-agent AuthorityContext laundering | PASS |
| RT-02 | cross-run real-world effect replay | PASS |
| RT-03 | Tool TOCTOU | PASS |
| RT-04 | RunState task mismatch | PASS |
| RT-05 | Run ↔ RunState identity mismatch | PASS |
| RT-06 | foreign/stale ResumeFreshnessGate lineage | PASS |
| RT-07 | Runtime mutation of Core-owned HarnessRun | PASS |
| RT-08 | Runtime state firewall | PASS |
| RT-09 | Runtime resume revision TOCTOU | PASS |
| RT-10 | repeated checkpoint resume | PASS |
| RT-11 | temporal trace attribution | PASS |
| RT-12 | competing revision-protection family | PASS |

These are technical regression results only. No independent Phase-2 audit verdict is asserted here.

## Convergence check

Revision protection remains one family only:

```text
VersionedRead
-> VersionedReadSet
-> RevisionGuard
```

Resume exclusivity is orthogonal:

```text
persisted ResumeClaim / atomic idempotency claim
```

The RT-12 structural scan over production Python passed with all prohibited symbols absent:

- `RevisionLeasePort`;
- `RuntimeResumeFence`;
- `RevisionSnapshot`;
- `ResumeExecutionToken`;
- `RevisionFenceSource`;
- `ToolBoundaryFence`.

No resume claim was used as a substitute for `RevisionGuard`, and no revision guard was used as a substitute for resume exclusivity.

## CI evidence before final exact-SHA freeze gate

Harness Core CI run `33330667277`, head `8210bd0a73e48f2dd83b41483a26d46adc705714`:

```text
182 passed in 1.30s
exported 17 schemas
schema export matches the Git-tracked state
```

Focused evidence run `33330763019`, head `de85ad06122bfc8e0baebf70ed526a94a412c8a5`:

```text
B1:          10 passed
B2:           6 passed
B1+B2:        8 passed
RT:          12 passed
full pytest: 182 passed
schemas:     17 exported
drift:       clean
```

A later run on report SHA `94b8ed45915315db86374be9d4fe9ec41ae9deaf` also passed `182` tests, exported `17` schemas and had clean drift, but its checkout used GitHub's synthetic PR merge ref. Because the freeze requirement says **CI on the exact final commit**, that run is supporting evidence only and is not used as the final freeze gate.

Commit `90fd4dbe2c8c3e82055063f2919a95395de9254b` hardens the CI checkout to select the exact PR head SHA (or `github.sha` for push). This report update is the new proposed second-freeze commit; no Harness production file changed after the previously green implementation candidate.

## Incongruence check

- fixed merge base remains exactly `5a18ce034987b14617442fc48194bd9dec2f87f2`;
- only B1/B2 production areas changed;
- the additional workflow delta is CI-only and exists solely to prove the exact freeze commit;
- no second revision/fence architecture exists;
- resume claim and RevisionGuard protect different invariants;
- success TRACE cannot precede canonical state persistence;
- post-runtime bookkeeping failures are fail-closed and never authorize blind replay;
- pre-runtime proven failures alone may reopen, through linearizable CAS;
- PR #17 remains open/draft and unmerged;
- PR #39 remains open/draft and unmerged;
- canonical `harness-core-v0.1` remains unchanged at its pre-existing institutional SHA;
- CI-only PR #40 is not an integration target and must not be merged.

## failed attempt -> cause -> correct solution

1. **Synthetic tree ref move rejected by connector before mutation** → tooling path could not update the branch ref through that action → continue with Contents API fast-forward writes on the already-fixed branch.
2. **Integration CAS-retry fixture could consume its barrier during setup** → synchronization primitive covered setup as well as contenders → scope/enable the barrier only for concurrent contenders; assertions unchanged.
3. **First consolidated full CI: 181 pass / 1 fail** → an old T10 test still expected successful Runtime history to end at `REVALIDATED_AND_GUARDED` → strengthen the test to require B2's terminal `PENDING -> REVALIDATED_AND_GUARDED -> COMPLETED`; no production rollback and no freshness assertion weakened.
4. **First report/freeze CI checked out PR merge ref rather than exact head commit** → GitHub's default `pull_request` checkout materializes `refs/pull/<n>/merge` → harden checkout to `${{ github.event.pull_request.head.sha || github.sha }}` and issue a new freeze commit; do not claim the synthetic-merge run as exact-SHA evidence.

## Freeze rule

This report update is the proposed **second freeze commit**. It must pass the canonical Harness Core CI with checkout proving `git HEAD` equals this exact commit SHA before its SHA may be returned as `SECOND_FROZEN_SHA`.

Final external state after green exact-SHA CI: `READY_FOR_INDEPENDENT_REAUDIT`.

This report does **not** declare `ACCEPT`.
