# GT P1-A — CORE-STATE-INTEGRITY — IMPLEMENTATION REPORT

## Work identity
- WORK_BASE_SHA: `530386c35e21066b11ffb5491a52418faae67269`
- Branch: `worker/p1-state-integrity`
- Historical audit evidence only: `57e5c83c66c1c6fa275a0a725b92e6b77cc36aff`
- Scope: T10/TRACE state-integrity blockers only.

## Decisions

### Resume binding
Before freshness, Core requires:

`checkpoint.run_id == state.run_id == run.run_id`

`checkpoint.run_state_ref == state.run_state_id == run.run_state_ref`

`state.tarefa_trabalho_id == run.tarefa_trabalho_id`

`state.checkpoint_ref == requested checkpoint`

Any mismatch is `CHECKPOINT_INVALID` before RuntimePort.

### Resumable status
V0.1 permits `RuntimePort.resume()` only from `RunStatus.INTERRUPTED`.

`WAITING_APPROVAL` and `WAITING_EXTERNAL` are not generic resume states because the V0.1 RuntimePort.resume contract carries no approval/external-event payload. No enum was added.

### ResumeFreshnessGate provenance
Core validates previous AuthorityContext/TaskContext run, agent and task provenance before revalidation. Current HarnessRun supplies the run_id used for rebuilt/rebound TaskContext.

### Runtime state ownership
Runtime may contribute only technical progress: `status`, `current_step`, `completed_steps`, `pending_steps`, `artifact_refs`.

Core preserves/reconstructs `run_state_id`, `run_id`, `tarefa_trabalho_id`, `checkpoint_ref`, `decision_refs`.

### Checkpoint reuse
Checkpoint is single-use in V0.1. StatePort atomically consumes `RunState.checkpoint_ref` before crossing `RuntimePort.resume()`. Second resume fails closed. If RuntimePort raises after boundary crossing, the checkpoint remains consumed; silent replay is not allowed.

## Contract impact
No canonical contract or enum changed. `StatePort` gains internal atomic `consume_checkpoint_ref`; `InMemoryStateAdapter` implements it.

## Validation
Pending final CI:
- pytest
- schema export
- schema drift

## Failed attempts
None before first CI execution. Any failed validation attempt must be appended with `attempt → cause → correct solution`.

## Explicit exclusions
- no ToolGateway/side-effect change;
- no TOCTOU architecture change;
- no ModelPort/provider/LangGraph semantic change;
- no A4/E2E release.
