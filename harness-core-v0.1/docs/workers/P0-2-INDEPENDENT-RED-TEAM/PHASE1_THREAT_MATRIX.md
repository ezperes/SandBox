# P0-2-INDEPENDENT-RED-TEAM — Fase 1

Status: `PHASE1_PREPARED`

Role: `ARCH + DEFENSIVE SECURITY + TRACE` — independent red team, not primary implementer.

Baseline inspected: `worker/core-freshness-gate@530386c35e21066b11ffb5491a52418faae67269`

Red-team branch: `worker/p0-2-red-team`

Production changes: **none**.

Merge actions: **none**.

## 1. Scope and non-inheritance rule

This phase inspects the current candidate only to build adversarial probes. It does **not** grant an integration verdict and does not inherit the old verdict from `CORE_FRESHNESS_GATE_REAUDIT.md`, which audited SHA `61cd47670909469d0c684396d73b4572a1e4463a`.

The current baseline is 37 commits ahead of that old audit SHA and already changes freshness audit, resume, StateManager, ToolGateway and related tests. Therefore old PASS/FAIL conclusions are evidence of history, not evidence for the next frozen SHA.

Phase 2 must restart classification from zero against exactly the Integrator-provided frozen SHA.

## 2. Positive controls already present in the current baseline

The current candidate has materially improved over the old re-audit:

- side-effect ToolGateway without the concrete Core-owned `AuthorityFreshnessGate` fails closed;
- resume without the concrete Core-owned `ResumeFreshnessGate` fails closed;
- freshness rejection persists a boundary audit record;
- successful resume persists revalidation evidence before `RuntimePort.resume()`;
- `RunState.decision_refs` injected by a runtime are replaced with the Core-owned list;
- StatePort in-memory persistence uses deep copies;
- same-run exact idempotency key duplication is blocked atomically by the in-memory adapter;
- a dedicated technical-only T07 test exists in the current candidate.

These are controls, not a global security verdict.

## 3. Threat matrix

| ID | Boundary / invariant | Adversarial move | Current weak point at baseline | Prepared probe | Secure outcome required |
|---|---|---|---|---|---|
| RT-01 | `Run ↔ AuthorityContext` + cross-run/cross-agent | Submit `AuthorityContext(run=R2, agent=A2)` to `ToolGateway.execute(run_id=R1)` with valid revisions/scopes | ToolGateway receives only `run_id` + authority and never verifies `authority.run_id == run_id`; no expected agent/task binding is supplied | `test_red_team_authority_context_must_be_bound_to_run_and_agent_before_toolport` | Fail before ledger/ToolPort; no side effect |
| RT-02 | cross-run idempotency | Complete effect `operation+business_key` in R1; replay same real-world effect in R2 | Key is `run_id:operation:business_key`; changing run creates a fresh ledger identity | `test_red_team_same_real_world_effect_must_not_duplicate_across_runs` | A stable effect identity prevents replay across runs, or the architecture explicitly proves why the business key is run-scoped |
| RT-03 | Tool TOCTOU | Flip authority source rev-A→rev-B after freshness succeeds but before `ToolPort.invoke()` | `ensure_current()` is a read/check; no lease/fence/CAS/version token crosses ToolPort boundary | `test_red_team_tool_toctou_revision_flip_after_check_before_invoke_is_blocked` | Mutation in the check→invoke window prevents the effect |
| RT-04 | `Run ↔ RunState ↔ Checkpoint ↔ Task` | Persist same-run RunState with foreign `tarefa_trabalho_id`, checkpoint it, resume original run | Resume checks checkpoint/state `run_id`, but not state task vs run task; Checkpoint contains no task binding | `test_red_team_resume_rejects_foreign_task_in_runstate_before_runtime` | `CHECKPOINT_INVALID` before freshness/runtime |
| RT-05 | `HarnessRun.run_state_ref ↔ RunState.run_state_id` | Use checkpoint pointing to `RS-FOREIGN` while run expects `RS1` | Resume does not compare loaded state ID with `run.run_state_ref` | `test_red_team_resume_rejects_foreign_runstate_identity_before_runtime` | `CHECKPOINT_INVALID` before runtime |
| RT-06 | ResumeFreshnessGate execution binding | Construct gate with previous authority/context from R2 and prepare R1 | Gate validates current identity against run agent, but not previous authority/context run binding; ContextBuilder partial/no-change paths preserve `previous.task_context.run_id` | `test_red_team_resume_gate_rejects_previous_context_from_other_run` | Foreign previous context rejected or explicitly rebound with verified lineage to R1 |
| RT-07 | Runtime mutation of Core-owned `HarnessRun` | Runtime mutates `agent_id`, task, authority ref and state ref on the passed run object | StateManager deep-copies RunState, but passes the actual mutable `HarnessRun` object to `RuntimePort.resume()` | `test_red_team_runtime_cannot_mutate_core_owned_harness_run` | Runtime cannot change institutional identity/binding fields |
| RT-08 | Runtime output validation | Runtime returns RunState identifying a foreign run/state/task | StateManager restores only `decision_refs`; it does not validate returned `run_id`, `run_state_id`, `tarefa_trabalho_id` before persistence | `test_red_team_runtime_cannot_return_foreign_canonical_runstate` | Reject invalid runtime result; foreign state not persisted |
| RT-09 | Runtime resume TOCTOU | Flip authority rev-A→rev-B after revalidation record is RELEASED but before `RuntimePort.resume()` | `prepare()` and audit persistence precede runtime call; no fence/lease/recheck closes the final gap | `test_red_team_runtime_resume_toctou_revision_flip_after_revalidation_before_runtime_is_blocked` | Mutation in revalidate→resume window prevents runtime release |
| RT-10 | repeated resume | Call `resume()` twice on the same canonical checkpoint | No consumed/attempted checkpoint transition and no status gate prevents re-entry; same checkpoint remains referenced | `test_red_team_repeated_resume_same_checkpoint_does_not_reenter_runtime` | Runtime entered at most once for the same checkpoint attempt, or an explicit resume-attempt identity proves safe replay |
| RT-11 | TRACE attribution | Complete Tool side effect and reconstruct actor/run/task/authority revision/boundary/time/outcome from persisted record | Tool boundary audit has `run_id`, authority model/revisions, boundary, events/outcome; ToolGateway API does not receive task and audit has no explicit top-level actor/task attribution | `test_red_team_tool_trace_has_complete_actor_task_revision_boundary_time_outcome_attribution` | Persisted trace alone answers who/run/task/authority+revision/boundary/when/outcome |

## 4. TOCTOU probes are active, not read-only arguments

### RT-03 — Tool TOCTOU

Injection point is `StatePort.create_idempotency_record()`, which is reached after `AuthorityFreshnessGate.ensure_current()` but before `ToolPort.invoke()`.

Attack schedule:

```text
freshness sees AUT-T @ T-REV-1
        ↓
StatePort.create_idempotency_record()
        ↓ attacker flips source to T-REV-2
persist AUTHORIZED
        ↓
ToolPort.invoke()
```

The secure invariant is that `ToolPort.invoke()` must not occur under the now-stale authorization.

### RT-09 — Runtime resume TOCTOU

Injection point is persistence of the RELEASED/REVALIDATED boundary record, after `ResumeFreshnessGate.prepare()` but before `RuntimePort.resume()`.

Attack schedule:

```text
prepare() proves T-REV-1
        ↓
persist RELEASED / REVALIDATED
        ↓ attacker flips source to T-REV-2
rebind run refs / persist state
        ↓
RuntimePort.resume()
```

The secure invariant is that runtime release must not occur after the authorization/freshness fact became stale.

## 5. Current fragile points discovered by inspection

### 5.1 Binding is fragmented rather than enforced as one execution identity

The contracts distribute identity across objects:

```text
HarnessRun: run + task + agent + run_state_ref + authority_context_ref
AuthorityContext: run + agent
TaskContext: run + task + authority_context_ref
RunState: run + task
Checkpoint: run + run_state_ref
```

No common validator or boundary check proves the whole relation at resume/tool execution. A matching `run_id` alone is insufficient to establish that task, state, agent and authority all belong to the same execution.

### 5.2 Tool authorization can be laundered across executions

`AuthorityResolver` correctly stamps `run_id` and `agent_id` into AuthorityContext, but `ToolGateway.execute()` does not verify that its `run_id` matches the authority context. The gateway also has no expected `agent_id` or task identity parameter. Fresh revisions therefore do not imply correct execution ownership.

### 5.3 Freshness check is not an execution fence

`SourcePort` currently exposes only `read(source_ref)`. There is no immutable snapshot token, lease, fence, conditional execute, transaction, CAS or adapter capability that binds a freshness proof to the actual external action.

Consequently:

```text
CHECK(rev-A) ≠ GUARANTEE(action still authorized under rev-A)
```

This is the central Tool TOCTOU hypothesis for Phase 2.

### 5.4 Resume freshness has the same final-release race

The Core orders revalidation before runtime correctly, but ordering alone does not make the pair atomic. A canonical source can change after `prepare()` and before runtime execution.

### 5.5 Runtime trust boundary remains wider than the comment implies

The Core protects `decision_refs` and deep-copies RunState passed into runtime, but `HarnessRun` is mutable and passed by reference. Returned RunState identifiers are not revalidated before persistence. A hostile/buggy runtime can therefore attempt to rewrite Core-owned identity/binding data outside `decision_refs`.

### 5.6 Checkpoint is under-bound

Checkpoint contains `run_id` and `run_state_ref`, but no task, agent, authority context/snapshot, resume-attempt identity or consumed marker. StateManager does not currently compensate by checking all corresponding HarnessRun/RunState fields.

### 5.7 Repeated resume is not independently gated

A checkpoint can be reused after a successful resume. The side-effect ledger may block an identical same-run tool key later, but that is not equivalent to proving resume itself is exactly-once, nor does it protect non-ledgered runtime effects.

### 5.8 Idempotency is strong only inside the current key domain

The in-memory adapter makes `create_idempotency_record()` atomic for one process, and exact same-run duplicate keys are blocked. The semantic key includes `run_id`, so a new run resets the deduplication domain. Phase 2 must decide whether `business_key` denotes a real-world effect that must survive run changes; if yes, current keying is insufficient.

### 5.9 Tool TRACE cannot currently prove the full requested attribution

The boundary audit preserves useful temporal events and revision checks. However the ToolGateway call has no task identity, so persisted Tool trace cannot independently prove the requested tuple:

```text
who + run + task + authority/revision + boundary + moment + outcome
```

Actor can be inferred from nested AuthorityContext, but inference is weaker than explicit execution binding, and task is absent.

### 5.10 Task freshness/version lineage is weaker than authority lineage

ResumeFreshnessGate explicitly versions identity/authority, while task is read through ContextBuilder without a comparable persisted task revision/fence contract. Even after task/run IDs are bound, Phase 2 should verify whether a task/order update in the final release window can cause stale resume.

## 6. Prepared adversarial test set

File:

`harness-core-v0.1/tests/test_p0_2_red_team_adversarial.py`

The tests assert the secure invariant, not the vulnerable behavior. A red test therefore means the candidate allowed the adversarial path. They are intentionally suitable as a regression gate once the architecture is fixed.

Expected baseline pressure points:

- cross-run/cross-agent AuthorityContext binding;
- cross-run real-world effect replay;
- Tool TOCTOU;
- RunState task mismatch;
- RunState identity mismatch;
- stale ResumeFreshnessGate from another run;
- mutable HarnessRun handed to runtime;
- unvalidated foreign RunState returned by runtime;
- resume TOCTOU;
- repeated resume;
- incomplete Tool trace attribution.

No production patch is included.

## 7. Phase 2 classification protocol

When and only when the Integrator supplies a new frozen SHA:

1. Verify the provided SHA exists and record it verbatim.
2. Do not inspect `latest` as a substitute.
3. Create a clean audit execution against exactly that SHA plus the red-team tests.
4. Run repository CI and the adversarial suite.
5. Treat CI green only as a control, never as approval.
6. Attempt RT-03 and RT-09 TOCTOU injections physically in the test run.
7. Reconstruct trace records from persisted state, not from Python call-stack knowledge.
8. Classify independently: `T07`, `T10`, `T11`, `T12`, `TRACE`, `DEFENSIVE SECURITY` as `PROVEN | PARTIAL | NOT_PROVEN | CONTRADICTED`.
9. Derive final gate: `ACCEPT | ACCEPT_WITH_FIXES | REWORK`.
10. Do not inherit classification from this baseline or any prior SHA.

## 8. Failure log

### Attempt F-01

- failed attempt: local `git clone` for direct pytest execution;
- cause: execution container has no DNS/outbound access to `github.com` (`Could not resolve host`);
- correct solution: use the authenticated GitHub connector for exact-SHA reads/writes, then trigger repository GitHub Actions through a draft pull request without merge.

### Attempt F-02

- failed attempt: first red-team test draft referenced `manager.state.state_port`;
- cause: incorrect test-only attribute path;
- correct solution: corrected to `manager.state_port` before CI execution; no production code was touched.

## 9. Phase 1 exit condition

After the red-team branch is committed and the adversarial suite has been exercised against the current baseline for calibration, Phase 1 exits as:

`WAITING_FROZEN_SHA`

No Phase 2 acceptance/rejection is issued until a new Integrator SHA is explicitly frozen.
