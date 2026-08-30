# P0-2 — Consolidated Freshness Integration Report

Status: `READY_FOR_INDEPENDENT_REAUDIT` pending CI on this exact report commit.

## Candidate

- Integration branch: `integration/p0-2-freshness-consolidated`
- Institutional base: `worker/core-freshness-gate@530386c35e21066b11ffb5491a52418faae67269`
- Last pre-freeze green candidate: `b86841e1a9140e5833f44cd1907b161729abcf31`
- PR #17 was not merged or moved by this integration.
- Canonical branch `harness-core-v0.1` was not merged or modified by this integration.

## Incorporated source fronts

The consolidated tree incorporates the compatible content/requirements from:

- F1 Run Binding: `ba2c4371e72f6ec1a18825e0560f93be28658f9d`
- F2 Resume Status Policy: `f127331a82d1d19c569016783bdb976529db3b21`
- F3 Resume Context Isolation: `52b9573aba6b96bea438222e51843e3ede65e0cf`
- F4 Runtime State Firewall: `1f512a21a48eee2b8ffa9a540a97431a3a30d3dc`
- F5 Authority Execution Binding: `add59f9c0cc0c88bd9319d1430eefcfcef9ad73f`
- F6 Strong Revision Guard infrastructure: `ae1a7a97a9baecca067628c7d23b06b33b8d3e7d`
- F8 Runtime TOCTOU delta over F6: `774552162905c91609469710add5dfd9b32d908e`
- F9 Idempotency/Resume regression tests: `18bf7c91d4d23a7a691a7f17e6ea4ced1b22162b`
- F10 Red Team Phase-1 probes: `4120b28cc1ffe8cc584194ad486d00810f22302a`

F7 `f4d10fca92ce940022471535056bc87266f37ce5` was **not** integrated as a production architecture. Its behavioral attacks were retained, but `RevisionFenceSource` / `ToolBoundaryFence` were superseded by the canonical `VersionedReadSet + RevisionGuard` family.

The earlier runtime-only family `RevisionLeasePort / RuntimeResumeFence / RevisionSnapshot / ResumeExecutionToken` is superseded and absent from production.

## Single revision-protection family

The consolidated architecture has one mechanical revision-protection family:

```text
VersionedRead
  -> VersionedReadSet
  -> RevisionGuard
  -> sensitive boundary while guard ACTIVE
  -> release in finally/context-manager lifetime
```

This family protects both Tool and Runtime boundaries. The RT-12 structural tripwire scans all production Python files for the known duplicate-family symbols and passes.

## Final Tool boundary

For side-effecting tools the Core-owned flow is:

```text
canonical HarnessRun + TaskContext
-> validate_authority_execution_binding
-> AuthorityFreshnessGate / VersionedReadSet
-> AuthorityResolver decision
-> approval / competence / business-key validation
-> acquire strong RevisionGuard
-> cross-run real-world effect claim
-> run-scoped idempotency ledger reservation
-> audit AUTHORIZED_AND_GUARDED
-> ToolPort.invoke() while RevisionGuard ACTIVE
-> ledger/evidence finalization
-> release guard
```

### Idempotency ordering decision

The strong guard is acquired only after authority/freshness/approval/competence validation, so it is not held during human/external waits and stale attempts do not create misleading ledger history.

Inside the active guard:

1. a cross-run **effect claim** is reserved from `tool_id + business_key + canonical payload`;
2. the run-scoped execution ledger is then reserved as `run_id:operation:business_key`.

This resolves the F9/F10 apparent conflict without weakening either property:

- distinct real-world effects in separate runs may retain separate execution ledgers;
- an identical real-world effect cannot be replayed merely by changing `run_id`.

## Final Runtime boundary

```text
load Checkpoint + RunState
-> RunStateBindingGuard
-> require_resume_status_allowed
-> audit PENDING
-> exact Core ResumeFreshnessGate
-> run/task/context lineage isolation
-> canonical re-resolution / selective context rebuild
-> complete VersionedReadSet
-> acquire strong RevisionGuard
-> audit REVALIDATED_AND_GUARDED
-> RuntimePort.resume() while RevisionGuard ACTIVE
-> runtime-state firewall / merge_runtime_result
-> persist canonical state
-> release guard
```

Runtime receives copied technical state. Core-owned institutional fields cannot be minted or changed by Runtime/LangGraph. Checkpoint remains technical; it does not confer authority.

## Resume status policy

F2 is authoritative for this conflict:

- `INTERRUPTED` -> direct resume allowed.
- `WAITING_APPROVAL` -> `BLOCK_APPROVAL_GATE`; must return through explicit institutional transition before resume.
- `WAITING_EXTERNAL` -> `BLOCK_EXTERNAL_WAIT`; no direct resume.
- terminal/non-resumable states -> blocked.

The broader status set from the Runtime TOCTOU worker was intentionally not preserved.

## Source capability boundary

No generic atomicity is claimed for arbitrary stores.

Sensitive Tool/Runtime execution requires a SourcePort capable of the existing strong semantics:

```text
read_versioned(source_ref)
acquire_revision_guard(VersionedReadSet, owner_ref)  # atomic compare-all + hold
release_revision_guard(RevisionGuard)
```

A source that cannot keep protected material stable for the full sensitive boundary fails closed. A future external adapter must provide equivalent transaction/publication/epoch semantics behind this same abstraction; it must not introduce a parallel fence family.

## Conflicts resolved during integration

### 1. F7 parallel Tool fence

Failed attempt: `RevisionFenceSource / ToolBoundaryFence`.
Cause: second revision-proof architecture diverging from F6.
Correct solution: reuse `VersionedReadSet + RevisionGuard` and retain only the adversarial behavior requirements.

### 2. Runtime parallel lease/fence family

Failed attempt: `RevisionLeasePort / RuntimeResumeFence`.
Cause: duplicated the same responsibility already provided by the strong guard.
Correct solution: F8 was rebuilt as the delta `ae1a7a... -> 774552...` using the one common guard.

### 3. Resume status conflict

Failed integrated state: Runtime TOCTOU worker allowed `INTERRUPTED | WAITING_APPROVAL | WAITING_EXTERNAL`.
Cause: worker-local technical policy conflicted with the dedicated F2 institutional policy.
Correct solution: F2 prevails; only `INTERRUPTED` is directly resumable.

### 4. F9 vs F10 idempotency identity

Apparent conflict: F9 requires run-scoped ledgers; F10 forbids replay of the same real-world effect under another run.
Cause: one identifier was being asked to represent both execution history and real-world effect identity.
Correct solution: preserve run-scoped ledger and add an orthogonal cross-run effect claim keyed by tool + business key + canonical payload.

### 5. Phase-1 probes against the converged guard

Initial integrated runs exposed probes expecting a writer mutation itself to succeed before the sensitive call.
Cause: once the strong guard is active, the correct secure behavior is that the writer is rejected immediately with `RevisionGuardActiveError`.
Correct solution: preserve the attack and strengthen its assertion to require the mechanical guard rejection, unchanged protected revision, and an unreachable Tool/Runtime boundary.

## RT-01..RT-12 technical result on pre-freeze green candidate

| ID | Threat | Technical result |
|---|---|---|
| RT-01 | cross-run/cross-agent AuthorityContext laundering | PASS |
| RT-02 | idempotency reset across runs | PASS |
| RT-03 | Tool TOCTOU | PASS |
| RT-04 | RunState task mismatch | PASS |
| RT-05 | Run↔RunState identity mismatch | PASS |
| RT-06 | stale/foreign ResumeFreshnessGate lineage | PASS |
| RT-07 | Runtime mutation of Core-owned HarnessRun | PASS |
| RT-08 | Runtime state firewall | PASS |
| RT-09 | Runtime resume TOCTOU | PASS |
| RT-10 | repeated resume | PASS |
| RT-11 | temporal trace attribution | PASS |
| RT-12 | competing revision-proof families | PASS |

These are technical test results only. They are not an independent Red Team Phase-2 architectural verdict.

## CI evidence before freeze report commit

`Harness Core CI` run `33325980196` / run number `245` on `b86841e1a9140e5833f44cd1907b161729abcf31`:

```text
158 passed in 0.75s
17 schemas exported
schema export matches the Git-tracked state
```

All workflow steps completed successfully: installation, pytest, schema export, schema drift.

The report commit must itself pass the same CI before its SHA is declared `FROZEN_SHA`.

## Incongruence check

Pre-freeze checks:

- one revision family: `VersionedReadSet + RevisionGuard`;
- no `RevisionLeasePort` production symbol;
- no `RuntimeResumeFence` production symbol;
- no `ToolBoundaryFence` production symbol;
- no `RevisionFenceSource` production symbol;
- ToolPort is behind an active strong guard;
- RuntimePort.resume is behind an active strong guard;
- runtime checkpoint remains technical;
- Core owns authority/policy;
- adapter owns mechanical guard mechanism only;
- LangGraph has no institutional authority;
- F2 resume status policy preserved;
- run/task/agent/binding and runtime-state firewall are preserved;
- cross-run effect claim and run-scoped idempotency are separate concerns;
- audit attribution retains run/agent/task/boundary/time/revision/outcome.

## Freeze rule

If CI for the exact report commit is green, that exact SHA becomes the frozen candidate and the state is:

`READY_FOR_INDEPENDENT_REAUDIT`

No integration acceptance verdict is claimed here; independent Phase 2 must recompute its classifications from zero on the exact frozen SHA.
