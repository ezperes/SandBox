# P0-2-RUN-BINDING — Implementation Report

## Scope

- Repository: `ezperes/SandBox`
- Work base: `530386c35e21066b11ffb5491a52418faae67269`
- Parent branch: `worker/core-freshness-gate`
- Worker branch: `worker/p0-2-run-binding`
- PR #17 untouched.
- No StateManager integration performed in this worker.
- No ToolGateway, runtime adapter, AuthorityResolver, contracts, or E2E change.

## Existing contract inventory

No new contract fields were required.

`HarnessRun` already carries:

- `run_id`
- `tarefa_trabalho_id`
- `agent_id`
- `run_state_ref`

`RunState` already carries:

- `run_state_id`
- `run_id`
- `tarefa_trabalho_id`
- `checkpoint_ref`

`Checkpoint` already carries:

- `checkpoint_id`
- `run_id`
- `run_state_ref`

`RunState` and `Checkpoint` do not carry `agent_id`. This worker therefore does not invent an agent field. Agent ownership is anchored in the Core-owned `HarnessRun`; state/checkpoint ownership is proved by binding both objects to that run's canonical `run_id` and state reference.

## Core-owned primitive

New module:

`harness/core/state/binding.py`

Public API:

```python
RunStateBindingGuard.ensure_bound(
    run: HarnessRun,
    state: RunState,
    checkpoint: Checkpoint,
) -> RunStateBinding
```

`RunStateBinding` is an immutable dataclass containing the normalized institutional binding:

- `run_id`
- `tarefa_trabalho_id`
- `agent_id`
- `run_state_id`
- `checkpoint_id`

The guard performs no persistence and mutates none of its inputs.

## Fail-closed invariants

Before returning a binding proof, the guard requires non-empty institutional identifiers and proves:

1. `RunState.run_id == HarnessRun.run_id`;
2. `Checkpoint.run_id == HarnessRun.run_id`;
3. `RunState.tarefa_trabalho_id == HarnessRun.tarefa_trabalho_id`;
4. `RunState.run_state_id == HarnessRun.run_state_ref`;
5. `Checkpoint.run_state_ref == RunState.run_state_id`;
6. `RunState.checkpoint_ref == Checkpoint.checkpoint_id`;
7. `HarnessRun.agent_id` is explicit/non-empty.

Any failure raises `HarnessResolutionError(CHECKPOINT_INVALID, ...)` with the mismatching field identifiable in the message.

## RED → GREEN

### RED — CI #203

The first commit added only `tests/test_run_state_binding.py`.

Expected result occurred:

- test collection failed;
- cause: `ModuleNotFoundError: No module named 'harness.core.state.binding'`;
- no production behavior was relaxed to make the test pass.

### Correct solution

Added the isolated Core module `harness/core/state/binding.py` implementing the invariant without modifying existing contracts or `StateManager`.

### GREEN — CI #204

- `76 passed`;
- `17 schemas` exported;
- schema drift clean.

## Tests added

Dedicated tests prove:

- same run/task/checkpoint passes;
- different run blocks;
- different `tarefa_trabalho_id` blocks;
- checkpoint from another run blocks;
- checkpoint pointing to another RunState blocks;
- mandatory binding reference missing blocks;
- correct binding does not mutate `HarnessRun`, `RunState`, or `Checkpoint`.

## Integration point for the Integrator

`StateManager.resume()` currently loads:

1. `Checkpoint` by `checkpoint_id`;
2. `RunState` by `checkpoint.run_state_ref`;

and then performs a subset of binding checks inline.

The intended integration point is immediately after both objects are loaded and before audit creation, freshness preparation, persistence changes, or `RuntimePort.resume()`:

```python
RunStateBindingGuard.ensure_bound(run, state, checkpoint)
```

This worker intentionally does not edit `StateManager.resume()` because that belongs to another integration front.

`ResumeFreshnessGate` may reuse the same primitive if it ever receives the same three canonical objects, but duplicate enforcement should not replace the StateManager boundary check.

## Agent ownership note

There is no independent `agent_id` field on `RunState` or `Checkpoint` in V0.1. Therefore the primitive can prove that the state/checkpoint belong to the canonical `HarnessRun` by `run_id`/references and can require the run's `agent_id` to be explicit, but it cannot compare a second agent identity that the current contracts do not encode.

Integration must therefore supply the canonical Core-owned `HarnessRun`, not an arbitrary caller-constructed substitute. No contract expansion was made in this worker.

## Protected-set check

No changes to:

- `harness/core/state/manager.py`;
- `harness/core/tools/**`;
- runtime adapter;
- authority resolver;
- institutional contracts/schemas;
- PR #17;
- E2E.

## Status

The reusable binding primitive is ready for integration at the resume boundary. It does not itself modify resume behavior until the Integrator calls it from the canonical boundary.
