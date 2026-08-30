# P0-2 — Resume Status Policy

## Scope

Worker branch: `worker/p0-2-resume-status`

Working base: `530386c35e21066b11ffb5491a52418faae67269`

This worker formalizes only the Core-owned policy that decides whether a `RunState.status` may proceed toward `RuntimePort.resume()`.

It does not modify `StateManager`, canonical Pydantic contracts, RuntimePort, LangGraph, approval semantics, or external-event semantics.

## Observed behavior at working base

`StateManager.resume()` loads Checkpoint and RunState, checks checkpoint/run linkage and `state.checkpoint_ref`, then proceeds to freshness/re-resolution and can call `RuntimePort.resume()`.

There is no RunState.status gate in that path at the working base. Therefore possession of a valid checkpoint is currently sufficient to proceed to later resume gates regardless of lifecycle status.

## V0.1 policy

Direct `RuntimePort.resume()` admission is intentionally narrow: only `INTERRUPTED` is directly resumable.

| RunState.status | Decision | Direct resume | Required Core action |
|---|---|---:|---|
| CREATED | BLOCK_NOT_STARTED | no | use normal start/execute flow |
| READY | BLOCK_NOT_STARTED | no | use normal start/execute flow |
| RUNNING | BLOCK_ACTIVE | no | do not create replay/concurrent execution |
| INTERRUPTED | ALLOW | yes | continue normal resume gates |
| WAITING_APPROVAL | BLOCK_APPROVAL_GATE | no | Approval Gate resolves first; then explicit Core transition to INTERRUPTED |
| WAITING_EXTERNAL | BLOCK_EXTERNAL_WAIT | no | Core recognizes external condition first; then explicit transition to INTERRUPTED |
| REWORK | BLOCK_REWORK | no | Core prepares rework continuation; then explicit transition to INTERRUPTED |
| FAILED | BLOCK_TERMINAL | no | explicit lifecycle recovery/retry policy required; no direct resume |
| COMPLETED | BLOCK_TERMINAL | no | terminal |
| CANCELLED | BLOCK_TERMINAL | no | terminal |
| unknown/invalid | BLOCK_INVALID | no | fail closed |

## Why WAITING_APPROVAL is blocked

`RuntimePort.resume()` is a technical execution boundary. It must not become an implicit approval mechanism. The resume policy never accepts a boolean such as `approved=True` and never interprets approval evidence. A separate Core-owned Approval Gate must resolve approval and perform/authorize the lifecycle transition before resume admission is evaluated again.

## Why WAITING_EXTERNAL is blocked

A checkpoint does not prove that an external wait condition has been satisfied. A separate Core-owned external-event/reconciliation path must recognize the condition and transition the state before direct resume becomes admissible.

## Runtime neutrality

The policy is evaluated entirely in Harness Core and returns a Core-owned decision. RuntimePort and runtime adapters receive no authority to reinterpret lifecycle status. No LangGraph state or primitive participates in the decision.

## Integration point

Recommended integration in `StateManager.resume()`:

1. load Checkpoint and RunState;
2. validate checkpoint/run/state referential integrity;
3. create/persist the resume boundary attempt audit if the integrated trace design requires every blocked attempt to be reconstructible;
4. call `require_resume_status_allowed(state.status)`;
5. on `ResumeStatusRejected`, finalize the attempt as a Core-owned blocked resume and do not call freshness preparation or RuntimePort;
6. only an allowed result proceeds to freshness/re-resolution/revision guard and eventually `RuntimePort.resume()`.

At the original working-base implementation, the concrete insertion point is after the `state.checkpoint_ref != checkpoint_id` validation and before freshness-gate processing. If the Integrator preserves the current PENDING audit-before-gates trace pattern, enforce the policy immediately after that PENDING audit persistence and before the first gate capable of releasing the runtime boundary.

## Public worker API

`evaluate_resume_status(status)` returns a stable `ResumeStatusPolicyResult` without throwing.

`require_resume_status_allowed(status)` fails closed by raising `ResumeStatusRejected` unless the decision is `ALLOW`.

`resume_status_policy_table()` exposes the complete canonical table for conformance/audit tests.

## Acceptance coverage

Tests cover:

- INTERRUPTED;
- WAITING_EXTERNAL;
- WAITING_APPROVAL;
- COMPLETED;
- CANCELLED;
- FAILED;
- RUNNING;
- invalid/unknown values;
- CREATED / READY / REWORK policy completeness;
- complete one-to-one coverage of every canonical `RunStatus`.

## Integration conflicts

`StateManager` is intentionally untouched to avoid overlapping the state-integrity integration front. The Integrator only needs to import and call the policy at the resume admission point.

## Failed attempt → cause → correct solution

No code/test failure occurred during the policy implementation itself. Any CI/tooling attempt that fails will be recorded in the final worker handoff with cause and corrected validation path.

## Status

Implementation is designed to be `READY_FOR_INTEGRATION` if full CI, schema export, and schema drift validation remain green.
